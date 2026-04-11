import json
import base64
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from django.utils import timezone

from .models import Beneficiary, Representative
from .forms import BeneficiaryInfoForm, BeneficiaryEditForm, RepresentativeForm, ConsentForm
from verification.models import FaceEmbedding
from verification.face_utils import process_face_for_registration, check_duplicate_face
from logs.models import AuditLog
from accounts.models import CustomUser
from accounts.forms import UserCreateForm, UserUpdateForm


@login_required
def dashboard(request):
    total_beneficiaries = Beneficiary.objects.count()
    active_beneficiaries = Beneficiary.objects.filter(status='active').count()
    pending_beneficiaries = Beneficiary.objects.filter(status='pending').count()

    from verification.models import VerificationAttempt, StipendEvent
    today = timezone.now().date()
    verifications_today = VerificationAttempt.objects.filter(timestamp__date=today).count()
    verified_today = VerificationAttempt.objects.filter(
        timestamp__date=today, decision='verified'
    ).count()
    manual_review_pending = VerificationAttempt.objects.filter(
        decision=VerificationAttempt.DECISION_MANUAL_REVIEW,
        overridden=False,
    ).count()

    recent_logs = AuditLog.objects.select_related('user').order_by('-timestamp')[:10]

    # Upcoming stipend events (next 60 days)
    from datetime import timedelta
    upcoming_events = StipendEvent.objects.filter(
        is_active=True, date__gte=today, date__lte=today + timedelta(days=60)
    ).order_by('date')[:5]

    # Active event today
    active_event = StipendEvent.get_active_event_for_date(today)
    next_event = upcoming_events.first()

    return render(request, 'dashboard/index.html', {
        'total_beneficiaries': total_beneficiaries,
        'active_beneficiaries': active_beneficiaries,
        'pending_beneficiaries': pending_beneficiaries,
        'pending_registrations_count': pending_beneficiaries,
        'verifications_today': verifications_today,
        'verified_today': verified_today,
        'manual_review_pending': manual_review_pending,
        'recent_logs': recent_logs,
        'upcoming_events': upcoming_events,
        'active_event': active_event,
        'next_event': next_event,
    })


@login_required
def beneficiary_list(request):
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    beneficiaries = Beneficiary.objects.all()
    if query:
        beneficiaries = (
            beneficiaries.filter(last_name__icontains=query) |
            beneficiaries.filter(first_name__icontains=query) |
            beneficiaries.filter(beneficiary_id__icontains=query) |
            beneficiaries.filter(senior_citizen_id__icontains=query)
        )
    if status_filter:
        beneficiaries = beneficiaries.filter(status=status_filter)
    beneficiaries = beneficiaries.order_by('last_name', 'first_name')
    return render(request, 'beneficiaries/list.html', {
        'beneficiaries': beneficiaries,
        'query': query,
        'status_filter': status_filter,
    })


@login_required
def beneficiary_detail(request, pk):
    beneficiary = get_object_or_404(Beneficiary, pk=pk)
    has_embedding = hasattr(beneficiary, 'face_embedding')
    from verification.models import VerificationAttempt, ClaimRecord, StipendEvent
    attempts = (
        VerificationAttempt.objects
        .filter(beneficiary=beneficiary)
        .select_related('representative')
        .order_by('-timestamp')[:20]
    )
    claims = (
        ClaimRecord.objects
        .filter(beneficiary=beneficiary)
        .select_related('stipend_event', 'claimed_by', 'approved_by', 'verification_attempt', 'representative')
        .order_by('-claimed_at')
    )
    today = timezone.now().date()
    active_event = StipendEvent.get_active_event_for_date(today)
    current_event_claimed = False
    if active_event:
        current_event_claimed = ClaimRecord.objects.filter(
            beneficiary=beneficiary,
            stipend_event=active_event,
            status=ClaimRecord.STATUS_CLAIMED,
        ).exists()
    pending_special = beneficiary.special_claim_requests.filter(
        status='pending'
    ).select_related('stipend_event').first() if active_event else None
    representatives = (
        beneficiary.representatives
        .select_related('face_embedding')
        .order_by('-is_active', 'last_name')
    )
    return render(request, 'beneficiaries/detail.html', {
        'beneficiary': beneficiary,
        'has_embedding': has_embedding,
        'attempts': attempts,
        'claims': claims,
        'active_event': active_event,
        'current_event_claimed': current_event_claimed,
        'pending_special': pending_special,
        'representatives': representatives,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def beneficiary_edit(request, pk):
    beneficiary = get_object_or_404(Beneficiary, pk=pk)

    # Editing personal records (name, DOB, ID numbers, representative info)
    # is admin-only, consistent with all other write operations on existing
    # records.  Staff register new beneficiaries but do not edit existing ones.
    if not request.user.is_admin:
        messages.error(request, 'Admin access required to edit beneficiary records.')
        return redirect('beneficiaries:beneficiary_detail', pk=pk)

    if request.method == 'POST':
        form = BeneficiaryEditForm(request.POST, request.FILES, instance=beneficiary)
        if form.is_valid():
            changed_fields = [f for f in form.changed_data]
            form.save()
            AuditLog.log(
                action=AuditLog.ACTION_UPDATE,
                user=request.user,
                target_type='Beneficiary',
                target_id=beneficiary.id,
                details={
                    'beneficiary_id': beneficiary.beneficiary_id,
                    'changed_fields': changed_fields,
                },
                request=request
            )
            messages.success(request, 'Beneficiary record updated successfully.')
            return redirect('beneficiaries:beneficiary_detail', pk=beneficiary.pk)
    else:
        form = BeneficiaryEditForm(instance=beneficiary)

    return render(request, 'beneficiaries/edit.html', {
        'form': form,
        'beneficiary': beneficiary,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def beneficiary_deactivate(request, pk):
    """
    Deactivate or mark a beneficiary as deceased.
    Does NOT delete — preserves all historical records for audit.
    Only admins can deactivate.
    """
    if not request.user.is_admin:
        messages.error(request, 'Admin access required to change beneficiary status.')
        return redirect('beneficiaries:beneficiary_detail', pk=pk)

    beneficiary = get_object_or_404(Beneficiary, pk=pk)

    if request.method == 'POST':
        new_status = request.POST.get('new_status', Beneficiary.STATUS_INACTIVE)
        reason = request.POST.get('reason', '').strip()

        if new_status not in (Beneficiary.STATUS_INACTIVE, Beneficiary.STATUS_DECEASED):
            messages.error(request, 'Invalid status selected.')
            return redirect('beneficiaries:beneficiary_detail', pk=pk)

        if not reason:
            messages.error(request, 'A reason is required for deactivation.')
            return render(request, 'beneficiaries/deactivate.html', {
                'beneficiary': beneficiary,
                'error': 'Reason is required.',
            })

        old_status = beneficiary.status
        beneficiary.status = new_status
        beneficiary.deactivated_at = timezone.now()
        beneficiary.deactivated_by = request.user
        beneficiary.deactivated_reason = reason
        beneficiary.save()

        AuditLog.log(
            action=AuditLog.ACTION_UPDATE,
            user=request.user,
            target_type='Beneficiary',
            target_id=beneficiary.id,
            details={
                'beneficiary_id': beneficiary.beneficiary_id,
                'old_status': old_status,
                'new_status': new_status,
                'reason': reason,
            },
            request=request
        )
        status_label = 'Deceased' if new_status == Beneficiary.STATUS_DECEASED else 'Inactive'
        messages.success(request, f'{beneficiary.full_name} marked as {status_label}.')
        return redirect('beneficiaries:beneficiary_detail', pk=pk)

    return render(request, 'beneficiaries/deactivate.html', {'beneficiary': beneficiary})


@login_required
@require_http_methods(['POST'])
def beneficiary_reactivate(request, pk):
    """Re-activate a previously deactivated beneficiary (admin only)."""
    if not request.user.is_admin:
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:beneficiary_detail', pk=pk)

    beneficiary = get_object_or_404(Beneficiary, pk=pk)
    old_status = beneficiary.status
    beneficiary.status = Beneficiary.STATUS_ACTIVE
    beneficiary.deactivated_at = None
    beneficiary.deactivated_by = None
    beneficiary.deactivated_reason = ''
    beneficiary.save()

    AuditLog.log(
        action=AuditLog.ACTION_UPDATE,
        user=request.user,
        target_type='Beneficiary',
        target_id=beneficiary.id,
        details={
            'beneficiary_id': beneficiary.beneficiary_id,
            'old_status': old_status,
            'new_status': 'active',
            'reason': 'Reactivated by admin',
        },
        request=request
    )
    messages.success(request, f'{beneficiary.full_name} reactivated to Active status.')
    return redirect('beneficiaries:beneficiary_detail', pk=pk)


# ─── Registration ─────────────────────────────────────────────────────────────

@login_required
@require_http_methods(['GET', 'POST'])
def register_step1(request):
    if request.method == 'POST':
        form = BeneficiaryInfoForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data.copy()
            data['date_of_birth'] = str(data['date_of_birth'])
            request.session['reg_step1'] = data
            return redirect('beneficiaries:register_step2')
    else:
        form = BeneficiaryInfoForm()
    return render(request, 'beneficiaries/register_step1.html', {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
def register_step2(request):
    if 'reg_step1' not in request.session:
        return redirect('beneficiaries:register_step1')

    if request.method == 'POST':
        form = RepresentativeForm(request.POST)
        if form.is_valid():
            request.session['reg_step2'] = form.cleaned_data
            return redirect('beneficiaries:register_step3')
    else:
        form = RepresentativeForm()
    return render(request, 'beneficiaries/register_step2.html', {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
def register_step3(request):
    if 'reg_step1' not in request.session:
        return redirect('beneficiaries:register_step1')

    if request.method == 'POST':
        form = ConsentForm(request.POST)
        if form.is_valid():
            request.session['reg_step3'] = {'consent': True}
            return redirect('beneficiaries:register_face')
    else:
        form = ConsentForm()
    return render(request, 'beneficiaries/register_step3.html', {'form': form})


@login_required
def register_face(request):
    if 'reg_step1' not in request.session or 'reg_step3' not in request.session:
        return redirect('beneficiaries:register_step1')
    return render(request, 'beneficiaries/register_face.html')


@login_required
@require_POST
def register_submit_face(request):
    if 'reg_step1' not in request.session:
        return JsonResponse({'success': False, 'error': 'Session expired. Please restart registration.'})

    try:
        data = json.loads(request.body)
        image_data = data.get('image', '')
        if not image_data:
            return JsonResponse({'success': False, 'error': 'No image received.'})

        if ',' in image_data:
            image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)

        result = process_face_for_registration(image_bytes)
        if not result['success']:
            return JsonResponse({'success': False, 'error': result['error']})

        import datetime
        step1 = request.session['reg_step1']
        step2 = request.session.get('reg_step2', {})

        dob = datetime.date.fromisoformat(step1['date_of_birth'])

        # ── Duplicate check ────────────────────────────────────────────────────
        sc_id = step1.get('senior_citizen_id', '').strip()
        if sc_id and Beneficiary.objects.filter(senior_citizen_id=sc_id).exists():
            return JsonResponse({
                'success': False,
                'error': (
                    f'A beneficiary with Senior Citizen ID "{sc_id}" is already registered. '
                    'Check existing records before proceeding.'
                ),
            })

        name_dob_qs = Beneficiary.objects.filter(
            first_name__iexact=step1['first_name'],
            last_name__iexact=step1['last_name'],
            date_of_birth=dob,
        )
        if name_dob_qs.exists():
            existing = name_dob_qs.first()
            return JsonResponse({
                'success': False,
                'error': (
                    f'A beneficiary named "{existing.full_name}" with the same date of birth '
                    f'({dob}) is already registered (ID: {existing.beneficiary_id}). '
                    'Verify this is not a duplicate before proceeding.'
                ),
            })
        # ──────────────────────────────────────────────────────────────────────

        # ── Duplicate face check (CRITICAL SECURITY) ───────────────────────
        from django.conf import settings as django_settings
        dup_threshold = getattr(django_settings, 'FACE_DEDUP_THRESHOLD', 0.80)
        from verification.face_utils import get_embedding, decrypt_embedding
        import numpy as np
        # Decrypt and re-use embedding from the registration result
        live_emb = decrypt_embedding(result['encrypted_embedding'])

        dup_result = check_duplicate_face(live_emb, threshold=dup_threshold)
        if dup_result['duplicates_found']:
            top = dup_result['matches'][0]
            AuditLog.log(
                action=AuditLog.ACTION_DUPLICATE_FACE,
                user=request.user,
                target_type='Beneficiary',
                target_id=top['beneficiary_id'],
                details={
                    'attempted_name': f"{step1['first_name']} {step1['last_name']}",
                    'matched_beneficiary_id': top['beneficiary_id'],
                    'matched_name': top['full_name'],
                    'score': top['score'],
                    'threshold': dup_threshold,
                    'total_matches': len(dup_result['matches']),
                },
                request=request,
            )
            return JsonResponse({
                'success': False,
                'error': (
                    f'Registration blocked: Face already registered for '
                    f'beneficiary {top["beneficiary_id"]} ({top["full_name"]}) '
                    f'with similarity score {top["score"]:.2%}. '
                    'Contact your supervisor if this is a legitimate new enrollment.'
                ),
            })
        # ──────────────────────────────────────────────────────────────────────

        beneficiary = Beneficiary(
            first_name=step1['first_name'],
            middle_name=step1.get('middle_name', ''),
            last_name=step1['last_name'],
            date_of_birth=dob,
            gender=step1['gender'],
            address=step1['address'],
            barangay=step1['barangay'],
            municipality=step1['municipality'],
            province=step1['province'],
            contact_number=step1.get('contact_number', ''),
            senior_citizen_id=step1.get('senior_citizen_id', ''),
            valid_id_type=step1.get('valid_id_type', ''),
            valid_id_number=step1.get('valid_id_number', ''),
            has_representative=step2.get('has_representative', False),
            rep_first_name=step2.get('rep_first_name', ''),
            rep_last_name=step2.get('rep_last_name', ''),
            rep_relationship=step2.get('rep_relationship', ''),
            rep_contact=step2.get('rep_contact', ''),
            rep_id_type=step2.get('rep_id_type', ''),
            rep_id_number=step2.get('rep_id_number', ''),
            consent_given=True,
            consent_date=timezone.now(),
            status=Beneficiary.STATUS_PENDING,
            registered_by=request.user,
        )
        beneficiary.save()

        # Mark this record as created on an offline device so sync.py
        # knows which workstation to attribute the registration to.
        # This is a no-op in centralized mode (SYNC_API_URL not configured).
        from beneficiaries import sync as _sync
        _sync.mark_created(beneficiary)

        FaceEmbedding.objects.create(
            beneficiary=beneficiary,
            embedding_data=result['encrypted_embedding'],
            created_by=request.user,
        )

        for key in ['reg_step1', 'reg_step2', 'reg_step3']:
            request.session.pop(key, None)

        AuditLog.log(
            action=AuditLog.ACTION_REGISTER,
            user=request.user,
            target_type='Beneficiary',
            target_id=beneficiary.id,
            details={
                'beneficiary_id': beneficiary.beneficiary_id,
                'name': beneficiary.full_name,
                'status': 'pending_approval',
                'highest_dedup_score': dup_result['highest_score'],
            },
            request=request
        )

        quality_msg = ''
        if result.get('quality') and not result['quality']['ok']:
            quality_msg = f' Note: {result["quality"]["reason"]}'

        return JsonResponse({
            'success': True,
            'message': (
                f'Registration submitted (ID: {beneficiary.beneficiary_id}). '
                f'Pending admin approval before the beneficiary can be verified.{quality_msg}'
            ),
            'redirect': f'/dashboard/beneficiaries/{beneficiary.id}/'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Registration failed: {str(e)}'})


# ─── Representative Management ───────────────────────────────────────────────

@login_required
@require_http_methods(['POST'])
def add_representative(request, pk):
    """Add an authorized representative to a beneficiary."""
    beneficiary = get_object_or_404(Beneficiary, pk=pk)
    first_name = request.POST.get('rep_first_name', '').strip()
    last_name = request.POST.get('rep_last_name', '').strip()
    relationship = request.POST.get('rep_relationship', '').strip()
    contact_number = request.POST.get('rep_contact', '').strip()
    valid_id_type = request.POST.get('rep_id_type', '').strip()
    valid_id_number = request.POST.get('rep_id_number', '').strip()

    from .forms import REP_ID_CHOICES
    allowed_id_types = [v for v, _ in REP_ID_CHOICES if v]

    errors = []
    if not first_name:
        errors.append('First name is required.')
    if not last_name:
        errors.append('Last name is required.')
    if not contact_number:
        errors.append('Contact number is required.')
    if not valid_id_type:
        errors.append('ID type must be selected.')
    elif valid_id_type not in allowed_id_types:
        errors.append(f'"{valid_id_type}" is not a valid ID type. Please select from the list.')
    if not valid_id_number:
        errors.append('Valid ID number is required.')

    if errors:
        for e in errors:
            messages.error(request, e)
        return redirect('beneficiaries:beneficiary_detail', pk=pk)

    rep = Representative.objects.create(
        beneficiary=beneficiary,
        first_name=first_name,
        last_name=last_name,
        relationship=relationship,
        contact_number=contact_number,
        valid_id_type=valid_id_type,
        valid_id_number=valid_id_number,
        registered_by=request.user,
    )
    # Also update legacy inline fields for backward compat
    beneficiary.has_representative = True
    beneficiary.rep_first_name = first_name
    beneficiary.rep_last_name = last_name
    beneficiary.rep_relationship = relationship
    beneficiary.rep_contact = contact_number
    beneficiary.rep_id_type = valid_id_type
    beneficiary.rep_id_number = valid_id_number
    beneficiary.save()

    AuditLog.log(
        action=AuditLog.ACTION_UPDATE,
        user=request.user,
        target_type='Representative',
        target_id=rep.id,
        details={
            'beneficiary_id': beneficiary.beneficiary_id,
            'representative_name': rep.full_name,
            'action': 'Representative added',
        },
        request=request,
    )
    messages.success(
        request,
        f'{rep.full_name} added as representative. '
        'Register their face data now to enable verification.'
    )
    return redirect('verification:register_rep_face', pk=beneficiary.pk, rep_pk=rep.pk)


@login_required
@require_POST
def deactivate_representative(request, pk, rep_pk):
    """Deactivate a representative (soft delete)."""
    beneficiary = get_object_or_404(Beneficiary, pk=pk)
    rep = get_object_or_404(Representative, pk=rep_pk, beneficiary=beneficiary)
    rep.is_active = False
    rep.save()
    AuditLog.log(
        action=AuditLog.ACTION_UPDATE,
        user=request.user,
        target_type='Representative',
        target_id=rep.id,
        details={
            'beneficiary_id': beneficiary.beneficiary_id,
            'representative_name': rep.full_name,
            'action': 'Representative deactivated',
        },
        request=request,
    )
    messages.warning(request, f'{rep.full_name} has been deactivated as representative.')
    return redirect('beneficiaries:beneficiary_detail', pk=pk)


# ─── Address Data API ─────────────────────────────────────────────────────────

@login_required
def address_municipalities(request):
    """Return municipalities/cities for a given province."""
    province = request.GET.get('province', '')
    from django.conf import settings as django_settings
    import os

    data_file = os.path.join(django_settings.BASE_DIR, 'static', 'data', 'ph_addresses.json')
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            address_data = json.load(f)
        municipalities = address_data.get('municipalities', {}).get(province, [])
    except (FileNotFoundError, json.JSONDecodeError):
        municipalities = []

    return JsonResponse({'municipalities': municipalities})


@login_required
def address_barangays(request):
    """Return barangays for a given municipality."""
    municipality = request.GET.get('municipality', '')
    from django.conf import settings as django_settings
    import os

    data_file = os.path.join(django_settings.BASE_DIR, 'static', 'data', 'ph_addresses.json')
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            address_data = json.load(f)
        barangays = address_data.get('barangays', {}).get(municipality, [])
    except (FileNotFoundError, json.JSONDecodeError):
        barangays = []

    return JsonResponse({'barangays': barangays})


# ─── User Management (Admin only) ────────────────────────────────────────────

@login_required
def user_list(request):
    if not request.user.is_admin:
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:dashboard')
    users = CustomUser.objects.all().order_by('last_name', 'first_name')
    return render(request, 'admin_panel/users.html', {'users': users})


@login_required
@require_http_methods(['GET', 'POST'])
def user_create(request):
    if not request.user.is_admin:
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:dashboard')

    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            AuditLog.log(
                action=AuditLog.ACTION_USER_CREATE,
                user=request.user,
                target_type='User',
                target_id=user.id,
                details={'username': user.username, 'role': user.role},
                request=request
            )
            messages.success(request, f'User {user.username} created successfully.')
            return redirect('beneficiaries:user_list')
    else:
        form = UserCreateForm()
    return render(request, 'admin_panel/user_form.html', {'form': form, 'action': 'Create'})


@login_required
@require_http_methods(['GET', 'POST'])
def user_edit(request, pk):
    if not request.user.is_admin:
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:dashboard')

    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            AuditLog.log(
                action=AuditLog.ACTION_USER_UPDATE,
                user=request.user,
                target_type='User',
                target_id=user.id,
                details={'username': user.username},
                request=request
            )
            messages.success(request, 'User updated successfully.')
            return redirect('beneficiaries:user_list')
    else:
        form = UserUpdateForm(instance=user)
    return render(request, 'admin_panel/user_form.html', {'form': form, 'action': 'Edit', 'edited_user': user})


# ─── Sync Conflict Dashboard (Admin only) ─────────────────────────────────────

@login_required
def sync_conflict_list(request):
    """
    Admin-only view: list all beneficiary records in sync_conflict or
    sync_rejected state that require manual review.

    These records were created offline and, when sync was attempted:
    - sync_conflict  — the central server already has a different record for
                       the same ID (HTTP 409).  Admin must decide which version
                       is authoritative.
    - sync_rejected  — the central server refused the payload (HTTP 400/422).
                       Admin must correct the data or accept the local record.

    Records in this list cannot claim stipends until the conflict is resolved.
    """
    if not request.user.is_admin:
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:dashboard')

    conflict_records = Beneficiary.objects.filter(
        sync_status__in=[Beneficiary.SYNC_CONFLICT, Beneficiary.SYNC_REJECTED]
    ).select_related('registered_by').order_by('sync_status', 'created_at')

    from beneficiaries.sync import conflict_count, rejected_count
    return render(request, 'beneficiaries/sync_conflict_list.html', {
        'conflict_records': conflict_records,
        'conflict_count': conflict_count(),
        'rejected_count': rejected_count(),
        'SYNC_CONFLICT': Beneficiary.SYNC_CONFLICT,
        'SYNC_REJECTED': Beneficiary.SYNC_REJECTED,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def sync_conflict_review(request, pk):
    """
    Admin-only view: review a single beneficiary in sync_conflict or sync_rejected.

    POST actions:
      retry   — reset sync_status to 'pending_sync' so the next sync run will
                re-attempt to send this record.  Use when the conflict may have
                been transient (e.g. a previously-deleted duplicate on the server).
      accept  — mark sync_status as 'synced' locally.  Use when the admin has
                determined that the local record is authoritative and the central
                server's conflicting copy should be disregarded.
      reject  — keep sync_status as 'sync_rejected' with an admin note.  Use
                when the local record is invalid and should never be synced.
                The beneficiary remains in the system for audit purposes.

    All decisions are permanently recorded in the audit log.
    """
    if not request.user.is_admin:
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:sync_conflict_list')

    beneficiary = get_object_or_404(
        Beneficiary,
        pk=pk,
        sync_status__in=[Beneficiary.SYNC_CONFLICT, Beneficiary.SYNC_REJECTED],
    )

    if request.method == 'POST':
        action = request.POST.get('action', '').strip()
        review_notes = request.POST.get('review_notes', '').strip()

        if not review_notes:
            messages.error(request, 'Review notes are required.')
            return render(request, 'beneficiaries/sync_conflict_review.html', {
                'beneficiary': beneficiary,
            })

        if action == 'retry':
            old_status = beneficiary.sync_status
            beneficiary.sync_status = Beneficiary.SYNC_PENDING
            beneficiary.sync_error = ''
            beneficiary.save(update_fields=['sync_status', 'sync_error'])
            AuditLog.log(
                action=AuditLog.ACTION_UPDATE,
                user=request.user,
                target_type='Beneficiary',
                target_id=beneficiary.id,
                details={
                    'beneficiary_id': beneficiary.beneficiary_id,
                    'sync_action': 'retry',
                    'old_sync_status': old_status,
                    'new_sync_status': Beneficiary.SYNC_PENDING,
                    'review_notes': review_notes,
                    'offline_device': beneficiary.offline_device,
                },
                request=request,
            )
            messages.success(
                request,
                f'{beneficiary.full_name} reset to pending_sync. '
                'The record will be re-sent on the next sync run.'
            )

        elif action == 'accept':
            old_status = beneficiary.sync_status
            beneficiary.sync_status = Beneficiary.SYNC_SYNCED
            beneficiary.sync_error = f'Admin-accepted after {old_status}. Notes: {review_notes}'
            beneficiary.save(update_fields=['sync_status', 'sync_error'])
            AuditLog.log(
                action=AuditLog.ACTION_SYNC_ACCEPTED,
                user=request.user,
                target_type='Beneficiary',
                target_id=beneficiary.id,
                details={
                    'beneficiary_id': beneficiary.beneficiary_id,
                    'sync_action': 'accept',
                    'old_sync_status': old_status,
                    'review_notes': review_notes,
                    'offline_device': beneficiary.offline_device,
                },
                request=request,
            )
            messages.success(
                request,
                f'{beneficiary.full_name} accepted as synced. '
                'The local record is now treated as authoritative.'
            )

        elif action == 'reject':
            beneficiary.sync_status = Beneficiary.SYNC_REJECTED
            beneficiary.sync_error = f'Admin-rejected. Notes: {review_notes}'
            beneficiary.save(update_fields=['sync_status', 'sync_error'])
            AuditLog.log(
                action=AuditLog.ACTION_SYNC_REJECTED,
                user=request.user,
                target_type='Beneficiary',
                target_id=beneficiary.id,
                details={
                    'beneficiary_id': beneficiary.beneficiary_id,
                    'sync_action': 'reject',
                    'review_notes': review_notes,
                    'offline_device': beneficiary.offline_device,
                },
                request=request,
            )
            messages.warning(
                request,
                f'{beneficiary.full_name} marked as sync_rejected. '
                'The record is retained for audit but will not be synced.'
            )

        else:
            messages.error(request, 'Invalid action. Choose retry, accept, or reject.')
            return render(request, 'beneficiaries/sync_conflict_review.html', {
                'beneficiary': beneficiary,
            })

        return redirect('beneficiaries:sync_conflict_list')

    return render(request, 'beneficiaries/sync_conflict_review.html', {
        'beneficiary': beneficiary,
    })
