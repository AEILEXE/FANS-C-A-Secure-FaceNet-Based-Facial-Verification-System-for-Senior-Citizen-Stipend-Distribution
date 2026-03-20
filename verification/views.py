import json
import base64
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings as django_settings

from beneficiaries.models import Beneficiary
from .models import FaceEmbedding, VerificationAttempt, SystemConfig, StipendEvent
from .face_utils import (
    process_face_for_verification,
    compare_with_stored,
    load_image_from_bytes,
    detect_and_align_face,
    is_using_mock_model,
    get_model_load_error,
)
from .liveness import (
    run_full_liveness_check,
    get_random_challenge,
)
from logs.models import AuditLog


def _challenge_display(direction: str) -> str:
    return {
        'left': 'Slowly turn your head to the LEFT',
        'right': 'Slowly turn your head to the RIGHT',
        'up': 'Slowly look UP',
        'down': 'Slowly look DOWN',
    }.get(direction, 'Move your head')


# ─── Verification Selection ───────────────────────────────────────────────────

@login_required
def verify_select(request):
    query = request.GET.get('q', '')
    beneficiaries = []
    if query:
        beneficiaries = (
            Beneficiary.objects.filter(status=Beneficiary.STATUS_ACTIVE, last_name__icontains=query) |
            Beneficiary.objects.filter(status=Beneficiary.STATUS_ACTIVE, first_name__icontains=query) |
            Beneficiary.objects.filter(status=Beneficiary.STATUS_ACTIVE, beneficiary_id__icontains=query)
        ).distinct()

    # Show upcoming stipend events for context
    today = timezone.now().date()
    from datetime import timedelta
    upcoming_events = StipendEvent.objects.filter(
        is_active=True, date__gte=today, date__lte=today + timedelta(days=30)
    ).order_by('date')[:3]

    return render(request, 'verification/verify_select.html', {
        'beneficiaries': beneficiaries,
        'query': query,
        'upcoming_events': upcoming_events,
    })


# ─── Verify Start ─────────────────────────────────────────────────────────────

@login_required
def verify_start(request, pk):
    beneficiary = get_object_or_404(Beneficiary, pk=pk, status=Beneficiary.STATUS_ACTIVE)

    # Guard: inactive/deceased beneficiaries cannot claim
    if not beneficiary.is_eligible_to_claim:
        from django.contrib import messages
        messages.error(request, f'{beneficiary.full_name} is not eligible to claim (status: {beneficiary.get_status_display()}).')
        return redirect('verification:verify_select')

    claimant_type = request.GET.get('claimant', VerificationAttempt.CLAIMANT_BENEFICIARY)
    if claimant_type not in (VerificationAttempt.CLAIMANT_BENEFICIARY, VerificationAttempt.CLAIMANT_REPRESENTATIVE):
        claimant_type = VerificationAttempt.CLAIMANT_BENEFICIARY

    # Detect active stipend event
    today = timezone.now().date()
    active_event = StipendEvent.objects.filter(is_active=True, date=today).first()

    # Birthday bonus eligibility check: if today's event is a birthday bonus,
    # only beneficiaries whose birth month matches the event month can claim via face scan.
    if (active_event
            and active_event.event_type == StipendEvent.EVENT_TYPE_BIRTHDAY
            and claimant_type == VerificationAttempt.CLAIMANT_BENEFICIARY):
        if not active_event.is_beneficiary_eligible(beneficiary):
            from django.contrib import messages
            messages.error(
                request,
                f'{beneficiary.full_name} is not eligible for this Birthday Bonus event. '
                f'Only beneficiaries born in {active_event.date.strftime("%B")} are eligible.'
            )
            return redirect('verification:verify_select')

    if claimant_type == VerificationAttempt.CLAIMANT_REPRESENTATIVE:
        if not beneficiary.has_representative:
            from django.contrib import messages
            messages.error(request, 'This beneficiary has no registered representative.')
            return redirect('verification:verify_select')

        session_id = str(uuid.uuid4())
        attempt = VerificationAttempt.objects.create(
            beneficiary=beneficiary,
            performed_by=request.user,
            claimant_type=VerificationAttempt.CLAIMANT_REPRESENTATIVE,
            liveness_passed=None,
            fallback_triggered=True,
            threshold_used=SystemConfig.get_threshold(),
            session_id=session_id,
            decision=VerificationAttempt.DECISION_NOT_VERIFIED,
            decision_reason='Representative claim — ID verification required.',
            notes='Sent to fallback: representative claimant.',
            stipend_event=active_event,
        )
        AuditLog.log(
            action=AuditLog.ACTION_VERIFY,
            user=request.user,
            target_type='Beneficiary',
            target_id=beneficiary.id,
            details={'claimant_type': 'representative', 'reason': 'Redirected to fallback ID check'},
            request=request
        )
        return redirect('verification:verify_fallback', attempt_id=attempt.id)

    # Beneficiary face scan — requires an embedding
    if not hasattr(beneficiary, 'face_embedding'):
        from django.contrib import messages
        messages.error(request, 'No face embedding found for this beneficiary. Please re-register.')
        return redirect('verification:verify_select')

    session_id = str(uuid.uuid4())
    challenge = get_random_challenge()
    request.session['verification_session'] = {
        'beneficiary_id': str(pk),
        'session_id': session_id,
        'attempt_number': 1,
        'challenge': challenge,
        'claimant_type': claimant_type,
        'stipend_event_id': str(active_event.id) if active_event else None,
    }

    liveness_required = getattr(django_settings, 'LIVENESS_REQUIRED', False)
    demo_mode = getattr(django_settings, 'DEMO_MODE', True)

    using_mock = is_using_mock_model()
    is_birthday_event = (
        active_event and active_event.event_type == StipendEvent.EVENT_TYPE_BIRTHDAY
    )
    return render(request, 'verification/verify_capture.html', {
        'beneficiary': beneficiary,
        'session_id': session_id,
        'challenge': challenge,
        'challenge_display': _challenge_display(challenge),
        'claimant_type': claimant_type,
        'liveness_required': liveness_required,
        'demo_mode': demo_mode,
        'active_event': active_event,
        'is_birthday_event': is_birthday_event,
        'using_mock': using_mock,
        'model_load_error': get_model_load_error() if using_mock else None,
    })


# ─── Liveness Check ───────────────────────────────────────────────────────────

@login_required
@require_POST
def verify_check_liveness(request):
    """Server-side anti-spoofing check. Does NOT gate verification."""
    try:
        data = json.loads(request.body)
        image_data = data.get('image', '')
        challenge_completed = data.get('challenge_completed', False)

        if not image_data:
            return JsonResponse({'success': False, 'error': 'No image provided.'})

        if ',' in image_data:
            image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)

        img = load_image_from_bytes(image_bytes)
        try:
            face_img = detect_and_align_face(img)
            face_detected = True
        except ValueError as e:
            return JsonResponse({
                'success': True,
                'passed': False,
                'face_detected': False,
                'anti_spoof_score': 0.0,
                'liveness_score': 0.0,
                'reason': str(e),
            })

        anti_spoof_threshold = getattr(django_settings, 'ANTI_SPOOF_THRESHOLD', 0.15)
        liveness_result = run_full_liveness_check(
            face_img=face_img,
            challenge_completed=challenge_completed,
            anti_spoof_threshold=anti_spoof_threshold,
        )

        # Also check face quality for user guidance
        from .face_utils import check_face_quality
        quality = check_face_quality(face_img)

        return JsonResponse({
            'success': True,
            'face_detected': True,
            'passed': liveness_result['passed'],
            'anti_spoof_score': liveness_result['anti_spoof_score'],
            'liveness_score': liveness_result['liveness_score'],
            'reason': liveness_result['reason'],
            'face_quality_ok': quality['ok'],
            'face_quality_score': quality['score'],
            'face_quality_reason': quality['reason'],
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ─── Verify Submit ────────────────────────────────────────────────────────────

@login_required
@require_POST
def verify_submit(request):
    session_data = request.session.get('verification_session')
    if not session_data:
        return JsonResponse({'success': False, 'error': 'Verification session expired. Please start again.'})

    try:
        data = json.loads(request.body)
        image_data = data.get('image', '')
        challenge_completed = data.get('challenge_completed', False)
        liveness_score = data.get('liveness_score', 0.0)
        anti_spoof_score = data.get('anti_spoof_score', 0.0)
        liveness_passed_client = data.get('liveness_passed', False)
        face_detected_client = data.get('face_detected', True)

        if not image_data:
            return JsonResponse({'success': False, 'error': 'No image provided.'})

        beneficiary_id = session_data['beneficiary_id']
        attempt_number = session_data.get('attempt_number', 1)
        session_id = session_data['session_id']
        claimant_type = session_data.get('claimant_type', VerificationAttempt.CLAIMANT_BENEFICIARY)
        stipend_event_id = session_data.get('stipend_event_id')

        beneficiary = get_object_or_404(Beneficiary, pk=beneficiary_id)
        threshold = SystemConfig.get_threshold()
        liveness_required = getattr(django_settings, 'LIVENESS_REQUIRED', False)

        if ',' in image_data:
            image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)

        # Resolve stipend event
        stipend_event = None
        if stipend_event_id:
            try:
                stipend_event = StipendEvent.objects.get(pk=stipend_event_id)
            except StipendEvent.DoesNotExist:
                pass

        # Build attempt record
        attempt = VerificationAttempt(
            beneficiary=beneficiary,
            performed_by=request.user,
            claimant_type=claimant_type,
            liveness_passed=liveness_passed_client,
            liveness_score=liveness_score,
            anti_spoof_score=anti_spoof_score,
            head_movement_completed=challenge_completed,
            threshold_used=threshold,
            attempt_number=attempt_number,
            session_id=session_id,
            stipend_event=stipend_event,
        )

        # ── Strict mode: deny if liveness failed ──────────────────────────────
        if liveness_required and not liveness_passed_client:
            attempt.decision = VerificationAttempt.DECISION_DENIED
            attempt.decision_reason = 'Liveness check failed (strict mode).'
            attempt.notes = attempt.decision_reason
            attempt.save()
            _log_verify(request, beneficiary, 'denied', attempt_number,
                        liveness_passed_client, None, threshold, claimant_type,
                        'Liveness failed')
            request.session.pop('verification_session', None)
            return JsonResponse({
                'success': True,
                'decision': 'denied',
                'reason': attempt.decision_reason,
                'redirect': f'/verification/result/{attempt.id}/',
            })

        # ── Run face matching ──────────────────────────────────────────────────
        face_result = process_face_for_verification(image_bytes)

        if not face_result['success']:
            attempt.decision = VerificationAttempt.DECISION_DENIED
            attempt.decision_reason = f'Face not detected: {face_result["error"]}'
            attempt.notes = attempt.decision_reason
            attempt.save()
            return JsonResponse({
                'success': True,
                'decision': 'denied',
                'reason': attempt.decision_reason,
                'score': None,
                'redirect': f'/verification/result/{attempt.id}/',
            })

        # Store face quality
        if face_result.get('quality'):
            attempt.face_quality_score = face_result['quality'].get('score')

        # Warn if mock model
        if face_result.get('using_mock'):
            attempt.decision = VerificationAttempt.DECISION_DENIED
            attempt.decision_reason = (
                'Face recognition model not loaded. '
                'Verification requires keras-facenet — see README for setup.'
            )
            attempt.save()
            return JsonResponse({
                'success': True,
                'decision': 'denied',
                'reason': attempt.decision_reason,
                'redirect': f'/verification/result/{attempt.id}/',
            })

        live_embedding = face_result['embedding']
        stored_encrypted = beneficiary.face_embedding.embedding_data
        comparison = compare_with_stored(live_embedding, stored_encrypted)

        if not comparison['success']:
            attempt.decision = VerificationAttempt.DECISION_DENIED
            attempt.decision_reason = f'Comparison error: {comparison["error"]}'
            attempt.notes = attempt.decision_reason
            attempt.save()
            return JsonResponse({'success': False, 'error': comparison['error']})

        score = comparison['score']
        attempt.similarity_score = score

        # ── Decision logic ────────────────────────────────────────────────────
        review_band = threshold * 0.85

        if score >= threshold:
            decision = VerificationAttempt.DECISION_VERIFIED
            reason = f'Score {score:.4f} >= threshold {threshold:.2f}.'
            if not liveness_passed_client and not liveness_required:
                reason += ' Liveness warning (non-blocking in demo mode).'
        elif score >= review_band:
            decision = VerificationAttempt.DECISION_MANUAL_REVIEW
            reason = f'Score {score:.4f} in review band ({review_band:.2f}-{threshold:.2f}).'
        else:
            decision = VerificationAttempt.DECISION_NOT_VERIFIED
            reason = f'Score {score:.4f} below threshold {threshold:.2f}.'

        # Append quality note
        if face_result.get('quality') and not face_result['quality']['ok']:
            reason += f' Image: {face_result["quality"]["reason"]}'

        attempt.decision = decision
        attempt.decision_reason = reason
        attempt.save()

        max_retries = getattr(django_settings, 'MAX_RETRY_ATTEMPTS', 1)
        _log_verify(request, beneficiary, decision, attempt_number,
                    liveness_passed_client, score, threshold, claimant_type, reason)

        if decision == VerificationAttempt.DECISION_VERIFIED:
            request.session.pop('verification_session', None)
            return JsonResponse({
                'success': True,
                'decision': 'verified',
                'score': score,
                'threshold': threshold,
                'reason': reason,
                'redirect': f'/verification/result/{attempt.id}/',
            })

        elif decision == VerificationAttempt.DECISION_MANUAL_REVIEW:
            request.session.pop('verification_session', None)
            return JsonResponse({
                'success': True,
                'decision': 'manual_review',
                'score': score,
                'threshold': threshold,
                'reason': reason,
                'redirect': f'/verification/result/{attempt.id}/',
            })

        elif attempt_number <= max_retries:
            session_data['attempt_number'] = attempt_number + 1
            session_data['challenge'] = get_random_challenge()
            request.session['verification_session'] = session_data
            request.session.modified = True
            return JsonResponse({
                'success': True,
                'decision': 'retry',
                'score': score,
                'threshold': threshold,
                'reason': reason,
                'message': (
                    f'Score {score:.4f} is below threshold {threshold:.2f}. '
                    f'Ensure good lighting, center your face, and hold still.'
                ),
                'new_challenge': session_data['challenge'],
                'new_challenge_display': _challenge_display(session_data['challenge']),
                'attempt_id': str(attempt.id),
            })

        else:
            attempt.fallback_triggered = True
            attempt.save()
            request.session.pop('verification_session', None)
            AuditLog.log(
                action=AuditLog.ACTION_FALLBACK,
                user=request.user,
                target_type='Beneficiary',
                target_id=beneficiary.id,
                details={'score': score, 'reason': 'Max retries reached — fallback triggered'},
                request=request
            )
            return JsonResponse({
                'success': True,
                'decision': 'fallback',
                'score': score,
                'threshold': threshold,
                'reason': reason,
                'message': 'Facial verification failed after retry. Proceeding to ID verification.',
                'redirect': f'/verification/fallback/{attempt.id}/',
            })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Verification error: {str(e)}'})


def _log_verify(request, beneficiary, decision, attempt_number,
                liveness_passed, score, threshold, claimant_type, reason):
    AuditLog.log(
        action=AuditLog.ACTION_VERIFY,
        user=request.user,
        target_type='Beneficiary',
        target_id=beneficiary.id,
        details={
            'decision': decision,
            'claimant_type': claimant_type,
            'score': round(score, 4) if score is not None else None,
            'threshold': threshold,
            'liveness_passed': liveness_passed,
            'attempt_number': attempt_number,
            'reason': reason,
        },
        request=request
    )


# ─── Result / Fallback / Override ────────────────────────────────────────────

@login_required
def verify_result(request, attempt_id):
    attempt = get_object_or_404(VerificationAttempt, pk=attempt_id)
    # Detect attempts that were denied because the model was not loaded (mock mode).
    # Used to show an honest "no real verification occurred" banner on the result page.
    mock_denial = (
        attempt.similarity_score is None
        and 'model not loaded' in (attempt.decision_reason or '').lower()
    )
    return render(request, 'verification/result.html', {
        'attempt': attempt,
        'mock_denial': mock_denial,
        'model_load_error': get_model_load_error() if mock_denial else None,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def verify_fallback(request, attempt_id):
    attempt = get_object_or_404(VerificationAttempt, pk=attempt_id)

    if request.method == 'POST':
        id_type = request.POST.get('id_type', '')
        id_verified = request.POST.get('id_verified') == 'true'
        notes = request.POST.get('notes', '')

        attempt.fallback_id_verified = id_verified
        attempt.fallback_id_type = id_type
        attempt.notes = notes
        attempt.decision = (
            VerificationAttempt.DECISION_VERIFIED if id_verified
            else VerificationAttempt.DECISION_DENIED
        )
        attempt.decision_reason = (
            f'ID verification: {id_type} {"accepted" if id_verified else "rejected"}.'
        )
        attempt.save()

        AuditLog.log(
            action=AuditLog.ACTION_FALLBACK,
            user=request.user,
            target_type='VerificationAttempt',
            target_id=attempt.id,
            details={
                'id_type': id_type,
                'id_verified': id_verified,
                'decision': attempt.decision,
                'claimant_type': attempt.claimant_type,
            },
            request=request
        )
        return redirect('verification:verify_result', attempt_id=attempt.id)

    rep_id_type = ''
    rep_id_number = ''
    if attempt.claimant_type == VerificationAttempt.CLAIMANT_REPRESENTATIVE:
        rep_id_type = attempt.beneficiary.rep_id_type
        rep_id_number = attempt.beneficiary.rep_id_number

    return render(request, 'verification/fallback.html', {
        'attempt': attempt,
        'rep_id_type': rep_id_type,
        'rep_id_number': rep_id_number,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def admin_override(request, attempt_id):
    if not request.user.is_admin:
        from django.contrib import messages
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:dashboard')

    attempt = get_object_or_404(VerificationAttempt, pk=attempt_id)

    if request.method == 'POST':
        decision = request.POST.get('decision', '')
        reason = request.POST.get('reason', '').strip()

        if len(reason) < 20:
            from django.contrib import messages
            messages.error(request, 'Override reason must be at least 20 characters.')
            return render(request, 'verification/override.html', {'attempt': attempt})

        attempt.overridden = True
        attempt.override_by = request.user
        attempt.override_reason = reason
        attempt.override_at = timezone.now()
        attempt.decision = decision
        attempt.decision_reason = f'Admin override by {request.user.username}: {reason[:120]}'
        attempt.save()

        AuditLog.log(
            action=AuditLog.ACTION_OVERRIDE,
            user=request.user,
            target_type='VerificationAttempt',
            target_id=attempt.id,
            details={
                'decision': decision,
                'reason': reason,
                'beneficiary': str(attempt.beneficiary.id),
            },
            request=request
        )
        return redirect('verification:verify_result', attempt_id=attempt.id)

    return render(request, 'verification/override.html', {'attempt': attempt})


@login_required
def manual_review_list(request):
    if not request.user.is_admin:
        from django.contrib import messages
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:dashboard')

    pending = VerificationAttempt.objects.filter(
        decision=VerificationAttempt.DECISION_MANUAL_REVIEW,
        overridden=False,
    ).select_related('beneficiary', 'performed_by').order_by('-timestamp')

    return render(request, 'verification/manual_review.html', {'pending': pending})


# ─── System Config ────────────────────────────────────────────────────────────

@login_required
def verify_config(request):
    if not request.user.is_admin:
        from django.contrib import messages
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:dashboard')

    current_threshold = SystemConfig.get_threshold()
    demo_mode = getattr(django_settings, 'DEMO_MODE', True)

    if request.method == 'POST':
        try:
            new_threshold = float(request.POST.get('threshold', 0.60))
            if not 0.1 <= new_threshold <= 1.0:
                raise ValueError('Threshold must be between 0.1 and 1.0')

            config, _ = SystemConfig.objects.get_or_create(
                key='verification_threshold',
                defaults={'description': 'Cosine similarity threshold for face matching'}
            )
            config.value = str(new_threshold)
            config.updated_by = request.user
            config.save()

            AuditLog.log(
                action=AuditLog.ACTION_CONFIG_CHANGE,
                user=request.user,
                details={'key': 'verification_threshold', 'new_value': new_threshold},
                request=request
            )
            from django.contrib import messages
            messages.success(request, f'Threshold updated to {new_threshold}')
            current_threshold = new_threshold
        except ValueError as e:
            from django.contrib import messages
            messages.error(request, str(e))

    threshold_review_min = round(current_threshold * 0.85, 2)
    threshold_review_max = round(current_threshold - 0.01, 2)
    using_mock = is_using_mock_model()
    return render(request, 'verification/config.html', {
        'current_threshold': current_threshold,
        'threshold_review_min': threshold_review_min,
        'threshold_review_max': threshold_review_max,
        'liveness_required': getattr(django_settings, 'LIVENESS_REQUIRED', False),
        'anti_spoof_threshold': getattr(django_settings, 'ANTI_SPOOF_THRESHOLD', 0.15),
        'demo_mode': demo_mode,
        'demo_threshold': getattr(django_settings, 'DEMO_THRESHOLD', 0.60),
        'using_mock': using_mock,
        'model_load_error': get_model_load_error() if using_mock else None,
    })


# ─── Stipend Events ───────────────────────────────────────────────────────────

@login_required
def stipend_list(request):
    from datetime import timedelta
    today = timezone.now().date()
    upcoming = StipendEvent.objects.filter(is_active=True, date__gte=today).order_by('date')
    past = StipendEvent.objects.filter(date__lt=today).order_by('-date')[:20]
    return render(request, 'verification/stipend_list.html', {
        'upcoming': upcoming,
        'past': past,
        'today': today,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def stipend_create(request):
    if not request.user.is_admin:
        from django.contrib import messages
        messages.error(request, 'Admin access required.')
        return redirect('verification:stipend_list')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        date_str = request.POST.get('date', '')
        description = request.POST.get('description', '').strip()
        event_type = request.POST.get('event_type', StipendEvent.EVENT_TYPE_REGULAR)
        if event_type not in (StipendEvent.EVENT_TYPE_REGULAR, StipendEvent.EVENT_TYPE_BIRTHDAY):
            event_type = StipendEvent.EVENT_TYPE_REGULAR

        if not title or not date_str:
            from django.contrib import messages
            messages.error(request, 'Title and date are required.')
            return render(request, 'verification/stipend_form.html', {'action': 'Create'})

        import datetime
        try:
            event_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            from django.contrib import messages
            messages.error(request, 'Invalid date format.')
            return render(request, 'verification/stipend_form.html', {'action': 'Create'})

        event = StipendEvent.objects.create(
            title=title,
            date=event_date,
            event_type=event_type,
            description=description,
            created_by=request.user,
        )
        AuditLog.log(
            action=AuditLog.ACTION_CONFIG_CHANGE,
            user=request.user,
            details={'stipend_event': title, 'date': str(event_date), 'event_type': event_type},
            request=request
        )
        from django.contrib import messages
        messages.success(request, f'Stipend event "{title}" created.')
        return redirect('verification:stipend_list')

    return render(request, 'verification/stipend_form.html', {'action': 'Create'})


@login_required
@require_http_methods(['GET', 'POST'])
def stipend_edit(request, event_id):
    if not request.user.is_admin:
        from django.contrib import messages
        messages.error(request, 'Admin access required.')
        return redirect('verification:stipend_list')

    event = get_object_or_404(StipendEvent, pk=event_id)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        date_str = request.POST.get('date', '')
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        event_type = request.POST.get('event_type', StipendEvent.EVENT_TYPE_REGULAR)
        if event_type not in (StipendEvent.EVENT_TYPE_REGULAR, StipendEvent.EVENT_TYPE_BIRTHDAY):
            event_type = StipendEvent.EVENT_TYPE_REGULAR

        if not title or not date_str:
            from django.contrib import messages
            messages.error(request, 'Title and date are required.')
            return render(request, 'verification/stipend_form.html', {'action': 'Edit', 'event': event})

        import datetime
        try:
            event.date = datetime.date.fromisoformat(date_str)
        except ValueError:
            from django.contrib import messages
            messages.error(request, 'Invalid date format.')
            return render(request, 'verification/stipend_form.html', {'action': 'Edit', 'event': event})

        event.title = title
        event.event_type = event_type
        event.description = description
        event.is_active = is_active
        event.save()

        from django.contrib import messages
        messages.success(request, f'Stipend event "{title}" updated.')
        return redirect('verification:stipend_list')

    return render(request, 'verification/stipend_form.html', {'action': 'Edit', 'event': event})


@login_required
@require_POST
def stipend_delete(request, event_id):
    if not request.user.is_admin:
        from django.contrib import messages
        messages.error(request, 'Admin access required.')
        return redirect('verification:stipend_list')

    event = get_object_or_404(StipendEvent, pk=event_id)
    # Soft-delete: deactivate rather than hard delete if there are linked claims
    if event.claims.exists():
        event.is_active = False
        event.save()
        from django.contrib import messages
        messages.warning(request, f'"{event.title}" has linked claims — deactivated instead of deleted.')
    else:
        event.delete()
        from django.contrib import messages
        messages.success(request, 'Stipend event deleted.')

    return redirect('verification:stipend_list')
