"""
Verification views — FANS-C (FaceNet-Based Verification System).

This module implements the core stipend verification workflow:

1. verify_select     — Staff searches for a beneficiary by name or ID.
2. verify_start      — Loads the camera capture page; initialises the session with a
                       random liveness challenge and claimant type (beneficiary or representative).
3. verify_check_liveness — AJAX endpoint called immediately after the staff clicks
                       "Capture & Verify". Runs server-side anti-spoofing (texture analysis)
                       and face quality check. Result is logged on every attempt.
                       Does NOT gate the face match — that decision is made by the client
                       using the risk-based logic in verify.js.
4. verify_submit     — Main verification endpoint. Receives the captured frame plus
                       liveness data from the client, runs FaceNet face matching, and
                       returns a decision: verified / manual_review / retry / fallback.

Risk-Based Liveness Strategy
──────────────────────────────
The head-movement liveness challenge is NOT shown for every verification (it would frustrate
elderly beneficiaries). Instead, verify.js triggers the challenge only when a risk condition
is detected: low anti-spoof score, poor image quality, a retry attempt, or a representative
claim. Backend liveness logging is always on regardless of the visible challenge.

Decision Flow (verify_submit)
──────────────────────────────
  strict mode (LIVENESS_REQUIRED=True) + liveness failed  →  denied immediately
  face match score >= threshold                            →  verified (+ ClaimRecord created)
  score in review band [threshold * 0.85, threshold)      →  manual_review
  score < review band AND retries remain                  →  retry (new challenge)
  retries exhausted                                        →  fallback (ID-based verification)
  possible lookalike (another beneficiary within
    LOOKALIKE_BAND of the target score)                    →  escalated to manual_review

Multi-template matching (compare_with_all_embeddings) uses the best score across all
stored FaceEmbedding / AdditionalFaceEmbedding records for the beneficiary. This helps
seniors whose appearance has changed since initial registration.
"""
import json
import base64
import uuid
import logging
from django.shortcuts import render, redirect, get_object_or_404

logger = logging.getLogger('verification')
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings as django_settings

from beneficiaries.models import Beneficiary
from .models import (
    FaceEmbedding, VerificationAttempt, SystemConfig, StipendEvent,
    AdditionalFaceEmbedding, FaceUpdateLog,
    FaceUpdateRequest, ManualVerificationRequest,
    ClaimRecord, SpecialClaimRequest,
    RepresentativeFaceEmbedding,
)
from beneficiaries.models import Representative
from .face_utils import (
    process_face_for_verification,
    process_face_for_registration,
    compare_with_all_embeddings,
    compare_with_stored,
    load_image_from_bytes,
    detect_and_align_face,
    is_using_mock_model,
    get_model_load_error,
    encrypt_embedding,
)
from .liveness import (
    run_full_liveness_check,
    get_random_challenge,
)
from logs.models import AuditLog


def _challenge_display(direction: str) -> str:
    return {
        'left':  'Tilt your whole head slowly to the LEFT',
        'right': 'Tilt your whole head slowly to the RIGHT',
        'up':    'Tilt your whole head slightly UP',
        'down':  'Tilt your whole head slightly DOWN',
    }.get(direction, 'Slowly move your head')


def _get_demo_mode():
    return getattr(django_settings, 'DEMO_MODE', True)


def _get_liveness_required():
    return getattr(django_settings, 'LIVENESS_REQUIRED', False)


# ─── Verification Selection ───────────────────────────────────────────────────

@login_required
def verify_select(request):
    query = request.GET.get('q', '')
    beneficiaries = []
    if query:
        beneficiaries = (
            Beneficiary.objects.filter(status=Beneficiary.STATUS_ACTIVE, last_name__icontains=query) |
            Beneficiary.objects.filter(status=Beneficiary.STATUS_ACTIVE, first_name__icontains=query) |
            Beneficiary.objects.filter(status=Beneficiary.STATUS_ACTIVE, beneficiary_id__icontains=query) |
            Beneficiary.objects.filter(status=Beneficiary.STATUS_ACTIVE, senior_citizen_id__icontains=query)
        ).distinct().order_by('last_name', 'first_name').prefetch_related('representatives__face_embedding')

    today = timezone.now().date()
    active_event = StipendEvent.get_active_event_for_date(today)

    # Show upcoming events for context in the sidebar
    from datetime import timedelta
    upcoming_events = StipendEvent.objects.filter(
        is_active=True, date__gte=today, date__lte=today + timedelta(days=30)
    ).order_by('date')[:3]

    return render(request, 'verification/verify_select.html', {
        'beneficiaries': beneficiaries,
        'query': query,
        'active_event': active_event,
        'upcoming_events': upcoming_events,
        'today': today,
    })


# ─── Verify Start ─────────────────────────────────────────────────────────────

@login_required
def verify_start(request, pk):
    """
    Load the camera capture page for a specific beneficiary.

    Responsibilities:
    - Guard against ineligible beneficiaries (inactive, deceased, pending).
    - Guard against birthday-bonus events for ineligible birth months.
    - Prevent duplicate claims for the same stipend event.
    - Route representative claims (verifies the representative's face, not the beneficiary's).
    - Generate a unique session ID and random liveness challenge.
    - Pass require_liveness_challenge to the template so JS knows whether the
      head-movement challenge is always required (True for rep claims) or risk-based
      (False for self-claims — JS decides dynamically from anti-spoof + quality signals).
    """
    beneficiary = get_object_or_404(Beneficiary, pk=pk)

    # Guard: only active beneficiaries can claim
    if not beneficiary.is_eligible_to_claim:
        from django.contrib import messages
        messages.error(
            request,
            f'{beneficiary.full_name} is not eligible to claim '
            f'(status: {beneficiary.get_status_display()}). '
            'Inactive, deceased, or pending beneficiaries cannot claim a stipend.'
        )
        return redirect('verification:verify_select')

    claimant_type = request.GET.get('claimant', VerificationAttempt.CLAIMANT_BENEFICIARY)
    if claimant_type not in (VerificationAttempt.CLAIMANT_BENEFICIARY, VerificationAttempt.CLAIMANT_REPRESENTATIVE):
        claimant_type = VerificationAttempt.CLAIMANT_BENEFICIARY

    # Detect active stipend event using payout window
    today = timezone.now().date()
    active_event = StipendEvent.get_active_event_for_date(today)

    # Birthday bonus eligibility check
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

    # Duplicate claim guard
    if active_event:
        already_claimed = ClaimRecord.objects.filter(
            beneficiary=beneficiary,
            stipend_event=active_event,
            status=ClaimRecord.STATUS_CLAIMED,
        ).exists()
        if already_claimed:
            from django.contrib import messages
            messages.warning(
                request,
                f'{beneficiary.full_name} has already claimed the stipend for '
                f'"{active_event.title}". To request an additional claim, '
                'go to the beneficiary profile and submit a Special Claim Request.'
            )
            return redirect('beneficiaries:beneficiary_detail', pk=beneficiary.pk)

    # Representative claim → biometric face verification (NOT ID-only)
    if claimant_type == VerificationAttempt.CLAIMANT_REPRESENTATIVE:
        from django.contrib import messages
        rep_id_param = request.GET.get('rep_id')
        qs = beneficiary.representatives.filter(is_active=True).select_related('face_embedding')
        if rep_id_param:
            try:
                rep = qs.get(pk=rep_id_param)
            except (Representative.DoesNotExist, Exception):
                messages.error(request, 'The specified representative was not found or is not active.')
                return redirect('beneficiaries:beneficiary_detail', pk=beneficiary.pk)
        else:
            rep = qs.first()

        if not rep:
            messages.error(
                request,
                'No active representative registered for this beneficiary. '
                'Add a representative and register their face on the beneficiary profile.'
            )
            return redirect('beneficiaries:beneficiary_detail', pk=beneficiary.pk)

        if not rep.has_face_data:
            messages.error(
                request,
                f'{rep.full_name} is registered as representative but has no face data. '
                'Register their face before verifying.'
            )
            return redirect('verification:register_rep_face', pk=beneficiary.pk, rep_pk=rep.pk)

        session_id = str(uuid.uuid4())
        challenge = get_random_challenge()
        request.session['verification_session'] = {
            'beneficiary_id': str(pk),
            'representative_id': str(rep.id),
            'session_id': session_id,
            'attempt_number': 1,
            'challenge': challenge,
            'claimant_type': claimant_type,
            'stipend_event_id': str(active_event.id) if active_event else None,
        }
        liveness_required = _get_liveness_required()
        demo_mode = _get_demo_mode()
        using_mock = is_using_mock_model()
        # Representative claims always require the visible liveness challenge — higher-risk
        # since a third party is claiming on the beneficiary's behalf.
        require_liveness_challenge = True
        return render(request, 'verification/verify_capture.html', {
            'beneficiary': beneficiary,
            'representative': rep,
            'session_id': session_id,
            'challenge': challenge,
            'challenge_display': _challenge_display(challenge),
            'claimant_type': claimant_type,
            'liveness_required': liveness_required,
            'demo_mode': demo_mode,
            'require_liveness_challenge': require_liveness_challenge,
            'active_event': active_event,
            'is_birthday_event': False,
            'using_mock': using_mock,
            'model_load_error': get_model_load_error() if using_mock else None,
        })

    # Beneficiary face scan — requires an embedding
    if not hasattr(beneficiary, 'face_embedding'):
        from django.contrib import messages
        messages.error(request, 'No face embedding found for this beneficiary. Please complete face registration first.')
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

    liveness_required = _get_liveness_required()
    demo_mode = _get_demo_mode()

    using_mock = is_using_mock_model()
    is_birthday_event = (
        active_event and active_event.event_type == StipendEvent.EVENT_TYPE_BIRTHDAY
    )
    # Beneficiary self-claims use the risk-based fast path: the liveness challenge
    # is only triggered by the client when a risk condition is detected (low anti-spoof
    # score, poor image quality, or a retry attempt). Pre-set to False here; JS decides.
    require_liveness_challenge = False
    return render(request, 'verification/verify_capture.html', {
        'beneficiary': beneficiary,
        'session_id': session_id,
        'challenge': challenge,
        'challenge_display': _challenge_display(challenge),
        'claimant_type': claimant_type,
        'liveness_required': liveness_required,
        'demo_mode': demo_mode,
        'require_liveness_challenge': require_liveness_challenge,
        'active_event': active_event,
        'is_birthday_event': is_birthday_event,
        'using_mock': using_mock,
        'model_load_error': get_model_load_error() if using_mock else None,
    })


# ─── Liveness Check ───────────────────────────────────────────────────────────

@login_required
@require_POST
def verify_check_liveness(request):
    """
    Server-side anti-spoofing + quality check — called immediately after capture.

    This endpoint runs on EVERY verification attempt. It is called by verify.js
    as step 1 ("Anti-Spoof Check") before the main face match submit.

    What it does:
    - Decodes the JPEG frame sent from the browser.
    - Runs face detection (RetinaFace → MTCNN → OpenCV cascade fallback).
    - Computes a texture-based anti-spoof score (Laplacian + LBP + Sobel).
    - Runs a face quality assessment (sharpness, brightness, contrast, glare).
    - Returns face_detected, anti_spoof_passed, anti_spoof_score, face_quality_ok.

    What it does NOT do:
    - It does not compute the FaceNet embedding.
    - It does not gate the verification — the client (verify.js) decides whether
      to trigger the head-movement challenge based on the returned scores.

    The result is logged later as part of the VerificationAttempt record in verify_submit.
    """
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

        from .face_utils import check_face_quality
        quality = check_face_quality(face_img)

        return JsonResponse({
            'success': True,
            'face_detected': True,
            'passed': liveness_result['passed'],
            'anti_spoof_passed': liveness_result.get('anti_spoof_passed', liveness_result['anti_spoof_score'] >= anti_spoof_threshold),
            'anti_spoof_score': liveness_result['anti_spoof_score'],
            'liveness_score': liveness_result['liveness_score'],
            'reason': liveness_result['reason'],
            'face_quality_ok': quality['ok'],
            'face_quality_score': round(quality['score'], 3),
            'face_quality_reason': quality['reason'],
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ─── Verify Submit ────────────────────────────────────────────────────────────

@login_required
@require_POST
def verify_submit(request):
    """
    Main verification endpoint — face matching and final decision.

    Called when the staff clicks "Process Verification" after the camera capture.
    Receives the best-quality frame from a 7-frame burst plus liveness data from the client.

    Processing pipeline:
    1. Validate session (anti-CSRF, session expiry guard).
    2. Decode the JPEG frame and compute the 128-d FaceNet embedding.
    3. Compare against stored embedding(s) — multi-template best score.
    4. Evaluate the score against the threshold and make a decision.
    5. Run lookalike detection if the score would pass (prevents twin/family fraud).
    6. Persist the VerificationAttempt and write an AuditLog entry.
    7. Return the decision as JSON; client redirects to the result page.

    Decision outcomes:
      verified       — score >= threshold; ClaimRecord created if a StipendEvent is active.
      manual_review  — score in review band, or lookalike detected.
      retry          — score failed but retries remain; new challenge issued.
      fallback       — all retries exhausted; redirects to ID-based fallback flow.
      denied         — strict liveness failed or face processing error.
    """
    session_data = request.session.get('verification_session')
    if not session_data:
        return JsonResponse({'success': False, 'error': 'Verification session expired. Please start again.'})

    try:
        data = json.loads(request.body)
        image_data = data.get('image', '')
        challenge_completed = data.get('challenge_completed', False)
        liveness_score = float(data.get('liveness_score', 0.0))
        anti_spoof_score = float(data.get('anti_spoof_score', 0.0))
        liveness_passed_client = bool(data.get('liveness_passed', False))
        face_detected_client = bool(data.get('face_detected', True))

        if not image_data:
            return JsonResponse({'success': False, 'error': 'No image provided.'})

        beneficiary_id = session_data['beneficiary_id']
        attempt_number = session_data.get('attempt_number', 1)
        session_id = session_data['session_id']
        claimant_type = session_data.get('claimant_type', VerificationAttempt.CLAIMANT_BENEFICIARY)
        stipend_event_id = session_data.get('stipend_event_id')

        beneficiary = get_object_or_404(Beneficiary, pk=beneficiary_id)
        threshold = SystemConfig.get_threshold()
        liveness_required = _get_liveness_required()
        demo_mode = _get_demo_mode()

        # Resolve representative (for representative claims)
        representative = None
        if claimant_type == VerificationAttempt.CLAIMANT_REPRESENTATIVE:
            rep_id = session_data.get('representative_id')
            if rep_id:
                try:
                    representative = (
                        Representative.objects
                        .select_related('face_embedding')
                        .get(pk=rep_id, beneficiary=beneficiary, is_active=True)
                    )
                except Representative.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Representative not found or no longer active.',
                    })

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
            representative=representative,
            liveness_passed=liveness_passed_client,
            liveness_score=liveness_score,
            anti_spoof_score=anti_spoof_score,
            head_movement_completed=challenge_completed,
            threshold_used=threshold,
            attempt_number=attempt_number,
            session_id=session_id,
            stipend_event=stipend_event,
            demo_mode_active=demo_mode,
        )

        # ── Strict mode: deny if liveness failed ──────────────────────────────
        if liveness_required and not liveness_passed_client:
            attempt.decision = VerificationAttempt.DECISION_DENIED
            attempt.decision_reason = (
                f'Denied: liveness check failed (strict mode). '
                f'Liveness score: {liveness_score:.3f}.'
            )
            attempt.notes = 'Liveness required and not passed.'
            attempt.save()
            _log_verify(request, beneficiary, 'denied', attempt_number,
                        liveness_passed_client, None, threshold, claimant_type,
                        'Liveness failed (strict mode)', stipend_event)
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
            attempt.decision_reason = f'Denied: {face_result["error"]}'
            if face_result.get('quality'):
                q = face_result['quality']
                attempt.face_quality_score = q.get('score')
                attempt.face_quality_ok = q.get('ok')
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
            q = face_result['quality']
            attempt.face_quality_score = q.get('score')
            attempt.face_quality_ok = q.get('ok')

        # Deny if model not loaded (mock mode)
        if face_result.get('using_mock'):
            attempt.decision = VerificationAttempt.DECISION_DENIED
            attempt.decision_reason = (
                'Denied: face recognition model not loaded. '
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

        # Compare against representative's face if rep claim, else beneficiary's
        if representative:
            if not representative.has_face_data:
                attempt.decision = VerificationAttempt.DECISION_DENIED
                attempt.decision_reason = 'Denied: representative has no registered face data.'
                attempt.save()
                return JsonResponse({
                    'success': True,
                    'decision': 'denied',
                    'reason': attempt.decision_reason,
                    'redirect': f'/verification/result/{attempt.id}/',
                })
            rep_result = compare_with_stored(live_embedding, representative.face_embedding.embedding_data)
            if not rep_result['success']:
                comparison = {'success': False, 'error': rep_result.get('error', 'Rep comparison failed'), 'score': 0.0}
            else:
                comparison = {
                    'success': True,
                    'score': rep_result['score'],
                    'matched_template': 'representative_primary',
                    'templates_checked': 1,
                    'all_scores': [{'template': 'representative_primary', 'score': rep_result['score']}],
                }
        else:
            # Use multi-template comparison (best score across all stored templates)
            comparison = compare_with_all_embeddings(live_embedding, beneficiary)

        if not comparison['success']:
            attempt.decision = VerificationAttempt.DECISION_DENIED
            attempt.decision_reason = f'Comparison error: {comparison.get("error", "unknown")}'
            attempt.notes = attempt.decision_reason
            attempt.save()
            return JsonResponse({'success': False, 'error': comparison.get('error', 'Comparison failed')})

        score = comparison['score']
        attempt.similarity_score = score
        attempt.matched_template = comparison.get('matched_template', '')
        attempt.templates_checked = comparison.get('templates_checked', 0)

        logger.info(
            '[VERIFY] beneficiary=%s score=%.4f threshold=%.4f gap=%+.4f '
            'matched=%s checked=%d demo=%s',
            beneficiary.beneficiary_id,
            score,
            threshold,
            score - threshold,
            comparison.get('matched_template', '?'),
            comparison.get('templates_checked', 0),
            demo_mode,
        )
        print(
            f'[FANS-C] VERIFY RESULT | beneficiary={beneficiary.beneficiary_id} '
            f'| score={score:.4f} | threshold={threshold:.4f} '
            f'| gap={score - threshold:+.4f} '
            f'| {"PASS" if score >= threshold else "FAIL"} '
            f'| matched={comparison.get("matched_template", "?")} '
            f'| checked={comparison.get("templates_checked", 0)} '
            f'| demo={demo_mode}',
            flush=True,
        )
        if comparison.get('all_scores'):
            for entry in comparison['all_scores']:
                print(
                    f'[FANS-C]   template={entry["template"]} score={entry["score"]:.4f}',
                    flush=True,
                )

        # ── Decision logic ────────────────────────────────────────────────────
        # Review band: scores just below threshold trigger manual review
        review_band = threshold * 0.85
        gap = score - threshold  # positive = above threshold, negative = below

        tmpl_info = f'template={comparison.get("matched_template", "?")}, checked={comparison.get("templates_checked", 0)}'

        liveness_warning = ''
        if not liveness_passed_client and not liveness_required:
            liveness_warning = ' [Liveness warning — assisted rollout mode, non-blocking]'

        if score >= threshold:
            decision = VerificationAttempt.DECISION_VERIFIED
            reason = (
                f'Verified: score {score:.3f} >= threshold {threshold:.2f} '
                f'(+{gap:.3f}). {tmpl_info}.'
                + liveness_warning
            )
        elif score >= review_band:
            decision = VerificationAttempt.DECISION_MANUAL_REVIEW
            reason = (
                f'Manual review: score {score:.3f} in review band '
                f'({review_band:.2f}–{threshold:.2f}), gap {gap:.3f}. '
                f'{tmpl_info}. Administrator action required.'
            )
        else:
            decision = VerificationAttempt.DECISION_NOT_VERIFIED
            reason = (
                f'Not verified: score {score:.3f} < threshold {threshold:.2f} '
                f'(gap {gap:.3f}). {tmpl_info}.'
            )

        # Append quality note if applicable
        if face_result.get('quality') and not face_result['quality']['ok']:
            reason += f' Note: {face_result["quality"]["reason"]}'

        # ── Lookalike / twin detection ─────────────────────────────────────────
        # If the target would pass, check whether another registered beneficiary
        # also has a score within LOOKALIKE_BAND of the target score. If so,
        # escalate to manual review — staff must confirm with ID before releasing.
        LOOKALIKE_BAND = getattr(django_settings, 'LOOKALIKE_BAND', 0.05)
        if decision == VerificationAttempt.DECISION_VERIFIED and score >= threshold:
            from .face_utils import check_duplicate_face as _check_dup
            lookalike_threshold = max(score - LOOKALIKE_BAND, threshold * 0.85)
            dup_check = _check_dup(
                live_embedding,
                threshold=lookalike_threshold,
                exclude_beneficiary_id=str(beneficiary.beneficiary_id),
            )
            if dup_check['duplicates_found']:
                top_match = dup_check['matches'][0]
                decision = VerificationAttempt.DECISION_MANUAL_REVIEW
                reason = (
                    f'Manual review — possible lookalike: score {score:.3f} >= threshold {threshold:.2f}, '
                    f'but beneficiary {top_match["beneficiary_id"]} ({top_match["full_name"]}) '
                    f'also scored {top_match["score"]:.3f} (within {LOOKALIKE_BAND:.2f} band). '
                    'Staff must confirm identity with ID before releasing stipend.'
                )
                AuditLog.log(
                    action=AuditLog.ACTION_DUPLICATE_FACE,
                    user=request.user,
                    target_type='VerificationAttempt',
                    target_id=attempt.id,
                    details={
                        'beneficiary_id': beneficiary.beneficiary_id,
                        'score': round(score, 4),
                        'lookalike_id': top_match['beneficiary_id'],
                        'lookalike_name': top_match['full_name'],
                        'lookalike_score': top_match['score'],
                        'band': LOOKALIKE_BAND,
                    },
                    request=request,
                )
        # ──────────────────────────────────────────────────────────────────────

        attempt.decision = decision
        attempt.decision_reason = reason
        attempt.save()

        max_retries = getattr(django_settings, 'MAX_RETRY_ATTEMPTS', 2)
        _log_verify(request, beneficiary, decision, attempt_number,
                    liveness_passed_client, score, threshold, claimant_type,
                    reason, stipend_event,
                    all_scores=comparison.get('all_scores', []))

        if decision == VerificationAttempt.DECISION_VERIFIED:
            # Create ClaimRecord (race guard: skip if one already exists)
            if stipend_event and not ClaimRecord.objects.filter(
                beneficiary=beneficiary,
                stipend_event=stipend_event,
                status=ClaimRecord.STATUS_CLAIMED,
            ).exists():
                ClaimRecord.objects.create(
                    beneficiary=beneficiary,
                    stipend_event=stipend_event,
                    claimant_type=claimant_type,
                    representative=representative,
                    claimed_by=request.user,
                    verification_attempt=attempt,
                    status=ClaimRecord.STATUS_CLAIMED,
                )
                AuditLog.log(
                    action=AuditLog.ACTION_CLAIM,
                    user=request.user,
                    target_type='Beneficiary',
                    target_id=beneficiary.id,
                    details={
                        'beneficiary_id': beneficiary.beneficiary_id,
                        'stipend_event': stipend_event.title,
                        'claimant_type': claimant_type,
                        'attempt_id': str(attempt.id),
                    },
                    request=request,
                )
            request.session.pop('verification_session', None)
            return JsonResponse({
                'success': True,
                'decision': 'verified',
                'score': round(score, 3),
                'threshold': threshold,
                'reason': reason,
                'redirect': f'/verification/result/{attempt.id}/',
            })

        elif decision == VerificationAttempt.DECISION_MANUAL_REVIEW:
            request.session.pop('verification_session', None)
            return JsonResponse({
                'success': True,
                'decision': 'manual_review',
                'score': round(score, 3),
                'threshold': threshold,
                'reason': reason,
                'redirect': f'/verification/result/{attempt.id}/',
            })

        elif attempt_number <= max_retries:
            new_challenge = get_random_challenge()
            session_data['attempt_number'] = attempt_number + 1
            session_data['challenge'] = new_challenge
            request.session['verification_session'] = session_data
            request.session.modified = True
            return JsonResponse({
                'success': True,
                'decision': 'retry',
                'score': round(score, 3),
                'threshold': threshold,
                'reason': reason,
                'message': (
                    f'Score {score:.3f} is below threshold {threshold:.2f}. '
                    f'Attempt {attempt_number} of {max_retries + 1}. '
                    'Ensure good lighting, center your face, and hold still.'
                ),
                'new_challenge': new_challenge,
                'new_challenge_display': _challenge_display(new_challenge),
                'attempt_id': str(attempt.id),
                'attempt_number': attempt_number,
                'max_retries': max_retries,
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
                details={
                    'score': round(score, 3),
                    'reason': f'Max retries ({max_retries}) reached — fallback triggered',
                    'threshold': threshold,
                },
                request=request
            )
            return JsonResponse({
                'success': True,
                'decision': 'fallback',
                'score': round(score, 3),
                'threshold': threshold,
                'reason': reason,
                'message': (
                    f'Facial verification failed after {max_retries + 1} attempts. '
                    'Proceeding to ID verification.'
                ),
                'redirect': f'/verification/fallback/{attempt.id}/',
            })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Verification error: {str(e)}'})


def _log_verify(request, beneficiary, decision, attempt_number,
                liveness_passed, score, threshold, claimant_type, reason,
                stipend_event=None, all_scores=None):
    """
    Write a structured AuditLog entry for a completed verification attempt.

    Captures the full decision context — score, threshold, liveness result, template
    breakdown, and demo_mode flag — so administrators can audit each decision later.
    all_scores contains per-template similarity scores for multi-template beneficiaries.
    """
    AuditLog.log(
        action=AuditLog.ACTION_VERIFY,
        user=request.user,
        target_type='Beneficiary',
        target_id=beneficiary.id,
        details={
            'decision': decision,
            'claimant_type': claimant_type,
            'score': round(score, 3) if score is not None else None,
            'threshold': threshold,
            'liveness_passed': liveness_passed,
            'attempt_number': attempt_number,
            'reason': reason,
            'stipend_event': str(stipend_event.id) if stipend_event else None,
            'stipend_event_title': stipend_event.title if stipend_event else None,
            'demo_mode': getattr(django_settings, 'DEMO_MODE', True),
            'all_template_scores': [
                {'template': s['template'], 'score': round(s['score'], 3)}
                for s in (all_scores or [])
            ],
        },
        request=request
    )


# ─── Result / Fallback / Override ────────────────────────────────────────────

@login_required
def verify_result(request, attempt_id):
    attempt = get_object_or_404(VerificationAttempt, pk=attempt_id)
    mock_denial = (
        attempt.similarity_score is None
        and 'model not loaded' in (attempt.decision_reason or '').lower()
    )

    # Detect specific denial sub-reasons for clearer UI labels
    denial_reason_label = ''
    if attempt.decision in (
        VerificationAttempt.DECISION_DENIED,
        VerificationAttempt.DECISION_NOT_VERIFIED,
    ):
        reason_lower = (attempt.decision_reason or '').lower()
        if attempt.liveness_passed is False:
            denial_reason_label = 'liveness_failed'
        elif attempt.similarity_score is not None and attempt.similarity_score < attempt.threshold_used:
            if attempt.claimant_type == VerificationAttempt.CLAIMANT_REPRESENTATIVE:
                denial_reason_label = 'rep_face_mismatch'
            else:
                denial_reason_label = 'face_mismatch'
        elif attempt.claimant_type == VerificationAttempt.CLAIMANT_REPRESENTATIVE:
            if 'no registered face data' in reason_lower or 'no face data' in reason_lower:
                denial_reason_label = 'rep_no_face'
            elif 'not found or no longer active' in reason_lower or 'deactivated' in reason_lower:
                denial_reason_label = 'rep_not_active'

    # Check if there is a pending manual verification request for this attempt
    pending_manual_request = ManualVerificationRequest.objects.filter(
        verification_attempt=attempt,
        status=ManualVerificationRequest.STATUS_PENDING,
    ).first()

    # Find the ClaimRecord linked to this attempt (if any)
    claim_record = ClaimRecord.objects.filter(verification_attempt=attempt).first()

    return render(request, 'verification/result.html', {
        'attempt': attempt,
        'mock_denial': mock_denial,
        'model_load_error': get_model_load_error() if mock_denial else None,
        'denial_reason_label': denial_reason_label,
        'pending_manual_request': pending_manual_request,
        'claim_record': claim_record,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def verify_fallback(request, attempt_id):
    attempt = get_object_or_404(VerificationAttempt, pk=attempt_id)
    from django.contrib import messages

    # Representatives must use biometric face verification — ID-only is blocked.
    if attempt.claimant_type == VerificationAttempt.CLAIMANT_REPRESENTATIVE:
        messages.error(
            request,
            'Representatives must verify using face scan. '
            'ID-only verification is not permitted for representatives.'
        )
        return redirect('beneficiaries:beneficiary_detail', pk=attempt.beneficiary.pk)

    if request.method == 'POST':
        id_type = request.POST.get('id_type', '').strip()
        id_verified = request.POST.get('id_verified') == 'true'
        notes = request.POST.get('notes', '').strip()
        reason = request.POST.get('reason', '').strip()

        attempt.fallback_id_verified = id_verified
        attempt.fallback_id_type = id_type

        is_representative = False  # always False now (blocked above)

        if is_representative:
            # ── Representative path: direct ID verification — no face match involved ──
            attempt.decision = (
                VerificationAttempt.DECISION_VERIFIED if id_verified
                else VerificationAttempt.DECISION_DENIED
            )
            attempt.decision_reason = (
                f'Representative ID verification: {id_type} '
                f'{"accepted" if id_verified else "rejected"}. '
                f'Fallback used by {request.user.get_full_name() or request.user.username}.'
            )
            attempt.notes = notes
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
                    'beneficiary_id': attempt.beneficiary.beneficiary_id,
                },
                request=request
            )
            # Representative path verified — create ClaimRecord
            if id_verified and attempt.stipend_event and not ClaimRecord.objects.filter(
                beneficiary=attempt.beneficiary,
                stipend_event=attempt.stipend_event,
                status=ClaimRecord.STATUS_CLAIMED,
            ).exists():
                ClaimRecord.objects.create(
                    beneficiary=attempt.beneficiary,
                    stipend_event=attempt.stipend_event,
                    claimant_type=attempt.claimant_type,
                    claimed_by=request.user,
                    verification_attempt=attempt,
                    status=ClaimRecord.STATUS_CLAIMED,
                )
                AuditLog.log(
                    action=AuditLog.ACTION_CLAIM,
                    user=request.user,
                    target_type='Beneficiary',
                    target_id=attempt.beneficiary.id,
                    details={
                        'beneficiary_id': attempt.beneficiary.beneficiary_id,
                        'stipend_event': attempt.stipend_event.title,
                        'claimant_type': attempt.claimant_type,
                        'via': 'representative_fallback',
                    },
                    request=request,
                )
            return redirect('verification:verify_result', attempt_id=attempt.id)

        else:
            # ── Beneficiary path: face scan failed; ID check alone is insufficient ──
            # Staff cannot directly release the stipend.  Create a ManualVerificationRequest
            # for admin review.  Attempt stays in manual_review state until admin acts.

            if not id_verified:
                # ID also failed — outright denial, no request needed
                attempt.decision = VerificationAttempt.DECISION_DENIED
                attempt.decision_reason = (
                    f'Face match failed and ID verification also rejected '
                    f'({id_type}). Denied by {request.user.get_full_name() or request.user.username}.'
                )
                attempt.notes = notes
                attempt.save()
                AuditLog.log(
                    action=AuditLog.ACTION_FALLBACK,
                    user=request.user,
                    target_type='VerificationAttempt',
                    target_id=attempt.id,
                    details={
                        'id_type': id_type,
                        'id_verified': False,
                        'decision': attempt.decision,
                        'claimant_type': attempt.claimant_type,
                        'beneficiary_id': attempt.beneficiary.beneficiary_id,
                    },
                    request=request
                )
                return redirect('verification:verify_result', attempt_id=attempt.id)

            # ID passed — submit pending manual verification request for admin approval
            if not reason:
                reason = (
                    f'Face match failed. ID check ({id_type}) passed by staff. '
                    'Requesting admin approval to release stipend.'
                )

            mvr = ManualVerificationRequest.objects.create(
                beneficiary=attempt.beneficiary,
                claimant_type=attempt.claimant_type,
                requested_by=request.user,
                verification_attempt=attempt,
                stipend_event=attempt.stipend_event,
                reason=reason,
                notes=notes,
                similarity_score=attempt.similarity_score,
                liveness_passed=attempt.liveness_passed,
                liveness_score=attempt.liveness_score,
                id_type_checked=id_type,
                id_verified=True,
            )

            # Keep attempt in manual_review — decision only updates when admin approves/rejects
            attempt.decision = VerificationAttempt.DECISION_MANUAL_REVIEW
            attempt.decision_reason = (
                f'Pending admin approval — manual verification request submitted by '
                f'{request.user.get_full_name() or request.user.username}. '
                f'ID check ({id_type}) passed.'
            )
            attempt.notes = notes
            attempt.save()

            AuditLog.log(
                action=AuditLog.ACTION_MANUAL_VERIFY_REQUEST,
                user=request.user,
                target_type='ManualVerificationRequest',
                target_id=mvr.id,
                details={
                    'beneficiary_id': attempt.beneficiary.beneficiary_id,
                    'id_type': id_type,
                    'similarity_score': attempt.similarity_score,
                    'liveness_passed': attempt.liveness_passed,
                    'reason': reason,
                },
                request=request
            )

            messages.info(
                request,
                'Manual verification request submitted. An admin must approve '
                'before the stipend can be released.'
            )
            return redirect('verification:verify_result', attempt_id=attempt.id)

    rep_id_type = ''
    rep_id_number = ''
    rep_name = ''
    if attempt.claimant_type == VerificationAttempt.CLAIMANT_REPRESENTATIVE:
        rep_id_type = attempt.beneficiary.rep_id_type
        rep_id_number = attempt.beneficiary.rep_id_number
        rep_name = f'{attempt.beneficiary.rep_first_name} {attempt.beneficiary.rep_last_name}'.strip()

    return render(request, 'verification/fallback.html', {
        'attempt': attempt,
        'rep_id_type': rep_id_type,
        'rep_id_number': rep_id_number,
        'rep_name': rep_name,
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

        if decision not in (
            VerificationAttempt.DECISION_VERIFIED,
            VerificationAttempt.DECISION_DENIED,
            VerificationAttempt.DECISION_NOT_VERIFIED,
        ):
            from django.contrib import messages
            messages.error(request, 'Invalid decision selected.')
            return render(request, 'verification/override.html', {'attempt': attempt})

        if len(reason) < 20:
            from django.contrib import messages
            messages.error(request, 'Override reason must be at least 20 characters.')
            return render(request, 'verification/override.html', {'attempt': attempt})

        attempt.overridden = True
        attempt.override_by = request.user
        attempt.override_reason = reason
        attempt.override_at = timezone.now()
        attempt.decision = decision
        attempt.decision_reason = (
            f'Admin override by {request.user.get_full_name() or request.user.username}: '
            f'{reason[:200]}'
        )
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
                'beneficiary_id': attempt.beneficiary.beneficiary_id,
                'original_score': attempt.similarity_score,
            },
            request=request
        )
        return redirect('verification:verify_result', attempt_id=attempt.id)

    return render(request, 'verification/override.html', {'attempt': attempt})


# ─── System Config ────────────────────────────────────────────────────────────

@login_required
def verify_config(request):
    if not request.user.is_admin:
        from django.contrib import messages
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:dashboard')

    current_threshold = SystemConfig.get_threshold()
    demo_mode = _get_demo_mode()

    if request.method == 'POST':
        try:
            new_threshold = float(request.POST.get('threshold', 0.60))
            if not 0.1 <= new_threshold <= 1.0:
                raise ValueError('Threshold must be between 0.1 and 1.0')

            config, _ = SystemConfig.objects.get_or_create(
                key='verification_threshold',
                defaults={'description': 'Cosine similarity threshold for FaceNet face matching'}
            )
            old_value = config.value
            config.value = str(new_threshold)
            config.updated_by = request.user
            config.save()

            AuditLog.log(
                action=AuditLog.ACTION_CONFIG_CHANGE,
                user=request.user,
                details={
                    'key': 'verification_threshold',
                    'old_value': old_value,
                    'new_value': new_threshold,
                },
                request=request
            )
            from django.contrib import messages
            messages.success(request, f'Threshold updated to {new_threshold:.2f}')
            current_threshold = new_threshold
        except ValueError as e:
            from django.contrib import messages
            messages.error(request, str(e))

    review_band_min = round(current_threshold * 0.85, 3)
    review_band_max = round(current_threshold - 0.001, 3)
    using_mock = is_using_mock_model()
    return render(request, 'verification/config.html', {
        'current_threshold': current_threshold,
        'threshold_review_min': review_band_min,
        'threshold_review_max': review_band_max,
        'liveness_required': _get_liveness_required(),
        'anti_spoof_threshold': getattr(django_settings, 'ANTI_SPOOF_THRESHOLD', 0.15),
        'demo_mode': demo_mode,
        'demo_threshold': getattr(django_settings, 'DEMO_THRESHOLD', 0.60),
        'prod_threshold': getattr(django_settings, 'VERIFICATION_THRESHOLD', 0.75),
        'max_retries': getattr(django_settings, 'MAX_RETRY_ATTEMPTS', 2),
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
    active_event = StipendEvent.get_active_event_for_date(today)
    return render(request, 'verification/stipend_list.html', {
        'upcoming': upcoming,
        'past': past,
        'today': today,
        'active_event': active_event,
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
        payout_start_str = request.POST.get('payout_start_date', '').strip()
        payout_end_str = request.POST.get('payout_end_date', '').strip()

        if event_type not in (StipendEvent.EVENT_TYPE_REGULAR, StipendEvent.EVENT_TYPE_BIRTHDAY):
            event_type = StipendEvent.EVENT_TYPE_REGULAR

        if not title or not date_str:
            from django.contrib import messages
            messages.error(request, 'Title and date are required.')
            return render(request, 'verification/stipend_form.html', {'action': 'Create'})

        import datetime
        try:
            event_date = datetime.date.fromisoformat(date_str)
            payout_start = datetime.date.fromisoformat(payout_start_str) if payout_start_str else None
            payout_end = datetime.date.fromisoformat(payout_end_str) if payout_end_str else None
        except ValueError:
            from django.contrib import messages
            messages.error(request, 'Invalid date format.')
            return render(request, 'verification/stipend_form.html', {'action': 'Create'})

        if payout_start and payout_end and payout_start > payout_end:
            from django.contrib import messages
            messages.error(request, 'Payout start date must be before or equal to end date.')
            return render(request, 'verification/stipend_form.html', {'action': 'Create'})

        event = StipendEvent.objects.create(
            title=title,
            date=event_date,
            event_type=event_type,
            description=description,
            payout_start_date=payout_start,
            payout_end_date=payout_end,
            created_by=request.user,
        )
        AuditLog.log(
            action=AuditLog.ACTION_CONFIG_CHANGE,
            user=request.user,
            details={
                'stipend_event': title,
                'date': str(event_date),
                'event_type': event_type,
                'payout_start': str(payout_start) if payout_start else None,
                'payout_end': str(payout_end) if payout_end else None,
            },
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
        payout_start_str = request.POST.get('payout_start_date', '').strip()
        payout_end_str = request.POST.get('payout_end_date', '').strip()

        if event_type not in (StipendEvent.EVENT_TYPE_REGULAR, StipendEvent.EVENT_TYPE_BIRTHDAY):
            event_type = StipendEvent.EVENT_TYPE_REGULAR

        if not title or not date_str:
            from django.contrib import messages
            messages.error(request, 'Title and date are required.')
            return render(request, 'verification/stipend_form.html', {'action': 'Edit', 'event': event})

        import datetime
        try:
            event.date = datetime.date.fromisoformat(date_str)
            event.payout_start_date = datetime.date.fromisoformat(payout_start_str) if payout_start_str else None
            event.payout_end_date = datetime.date.fromisoformat(payout_end_str) if payout_end_str else None
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
        title = event.title
        event.delete()
        from django.contrib import messages
        messages.success(request, f'Stipend event "{title}" deleted.')

    return redirect('verification:stipend_list')


# ─── Face Update (Re-enrollment) ─────────────────────────────────────────────

@login_required
@require_http_methods(['GET'])
def update_face_data(request, pk):
    """
    Show the face update UI for a beneficiary.
    Staff selects a reason then captures a new face image.
    Available for all staff (not admin-only) since barangay encoders handle this.
    """
    beneficiary = get_object_or_404(Beneficiary, pk=pk)

    if not beneficiary.is_eligible_to_claim:
        from django.contrib import messages
        messages.error(
            request,
            f'{beneficiary.full_name} is not active — face update is only allowed for active beneficiaries.'
        )
        return redirect('beneficiaries:beneficiary_detail', pk=pk)

    has_embedding = hasattr(beneficiary, 'face_embedding')
    recent_failures = beneficiary.verification_attempts.filter(
        decision__in=[
            VerificationAttempt.DECISION_NOT_VERIFIED,
            VerificationAttempt.DECISION_DENIED,
        ],
    ).order_by('-timestamp')[:5]

    update_history = FaceUpdateLog.objects.filter(beneficiary=beneficiary).order_by('-timestamp')[:10]
    additional_count = AdditionalFaceEmbedding.objects.filter(beneficiary=beneficiary).count()

    using_mock = is_using_mock_model()
    return render(request, 'verification/update_face.html', {
        'beneficiary': beneficiary,
        'has_embedding': has_embedding,
        'recent_failures': recent_failures,
        'update_history': update_history,
        'additional_count': additional_count,
        'update_reasons': FaceUpdateLog.REASON_CHOICES,
        'using_mock': using_mock,
        'model_load_error': get_model_load_error() if using_mock else None,
    })


@login_required
@require_POST
def update_face_submit(request, pk):
    """
    Process the face update form submission (JSON from webcam capture).

    Action 'replace': replaces the primary FaceEmbedding. Old embedding is gone.
    Action 'augment': adds a new AdditionalFaceEmbedding; primary is kept.
                      Use when appearance changed but original still partially works.

    Both actions are fully logged in FaceUpdateLog.
    """
    beneficiary = get_object_or_404(Beneficiary, pk=pk)

    try:
        data = json.loads(request.body)
        image_data = data.get('image', '')
        reason = data.get('reason', FaceUpdateLog.REASON_STAFF_DECISION)
        action = data.get('action', FaceUpdateLog.ACTION_REPLACE)
        notes = data.get('notes', '').strip()

        if not image_data:
            return JsonResponse({'success': False, 'error': 'No image received.'})

        if reason not in dict(FaceUpdateLog.REASON_CHOICES):
            reason = FaceUpdateLog.REASON_STAFF_DECISION
        if action not in (FaceUpdateLog.ACTION_REPLACE, FaceUpdateLog.ACTION_AUGMENT):
            action = FaceUpdateLog.ACTION_REPLACE

        if ',' in image_data:
            image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)

        # Run full registration pipeline (detection + quality + embedding + encrypt)
        result = process_face_for_registration(image_bytes)

        if not result['success']:
            FaceUpdateLog.objects.create(
                beneficiary=beneficiary,
                performed_by=request.user,
                reason=reason,
                action=action,
                notes=notes or result.get('error', ''),
                success=False,
            )
            return JsonResponse({'success': False, 'error': result['error']})

        encrypted = result['encrypted_embedding']

        # ── Security: face updates do NOT apply immediately ──────────────────
        # Create a pending FaceUpdateRequest; an admin must approve before the
        # active embedding is changed.  The encrypted embedding is stored here
        # and only written to FaceEmbedding / AdditionalFaceEmbedding on approval.
        fur = FaceUpdateRequest.objects.create(
            beneficiary=beneficiary,
            requested_by=request.user,
            reason=reason,
            action=action,
            notes=notes,
            new_embedding_data=encrypted,
        )

        AuditLog.log(
            action=AuditLog.ACTION_FACE_UPDATE_REQUEST,
            user=request.user,
            target_type='FaceUpdateRequest',
            target_id=fur.id,
            details={
                'beneficiary_id': beneficiary.beneficiary_id,
                'reason': reason,
                'action': action,
                'notes': notes,
                'quality_ok': result.get('quality', {}).get('ok'),
            },
            request=request,
        )

        quality_note = ''
        if result.get('quality') and not result['quality']['ok']:
            quality_note = f' Note: {result["quality"]["reason"]}'

        return JsonResponse({
            'success': True,
            'pending': True,
            'message': (
                f'Face capture submitted for {beneficiary.full_name}.{quality_note} '
                'An admin must approve this request before the face data is updated.'
            ),
            'redirect': f'/dashboard/beneficiaries/{beneficiary.id}/',
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Update failed: {str(e)}'})


# ─── Admin Approval: Unified Queue ────────────────────────────────────────────

@login_required
def manual_review_list(request):
    if not request.user.is_admin:
        from django.contrib import messages
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:dashboard')

    pending_verifications = VerificationAttempt.objects.filter(
        decision=VerificationAttempt.DECISION_MANUAL_REVIEW,
        overridden=False,
    ).select_related('beneficiary', 'performed_by', 'stipend_event').order_by('-timestamp')

    pending_manual_requests = ManualVerificationRequest.objects.filter(
        status=ManualVerificationRequest.STATUS_PENDING,
    ).select_related(
        'beneficiary', 'requested_by', 'verification_attempt', 'stipend_event'
    ).order_by('-created_at')

    pending_face_requests = FaceUpdateRequest.objects.filter(
        status=FaceUpdateRequest.STATUS_PENDING,
    ).select_related('beneficiary', 'requested_by').order_by('-created_at')

    pending_special_claims = SpecialClaimRequest.objects.filter(
        status=SpecialClaimRequest.STATUS_PENDING,
    ).select_related('beneficiary', 'requested_by', 'stipend_event', 'original_claim').order_by('-created_at')

    pending_registrations = (
        Beneficiary.objects
        .filter(status=Beneficiary.STATUS_PENDING)
        .select_related('registered_by')
        .order_by('created_at')
    )

    return render(request, 'verification/manual_review.html', {
        'pending': pending_verifications,
        'pending_manual_requests': pending_manual_requests,
        'pending_face_requests': pending_face_requests,
        'pending_special_claims': pending_special_claims,
        'pending_registrations': pending_registrations,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def manual_verify_review(request, request_id):
    """Admin approves or rejects a ManualVerificationRequest."""
    from django.contrib import messages

    if not request.user.is_admin:
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:dashboard')

    mvr = get_object_or_404(ManualVerificationRequest, pk=request_id)

    if request.method == 'POST':
        action = request.POST.get('action', '')
        review_notes = request.POST.get('review_notes', '').strip()

        if action not in ('approve', 'reject'):
            messages.error(request, 'Invalid action.')
            return redirect('verification:manual_review')

        mvr.reviewed_by = request.user
        mvr.reviewed_at = timezone.now()
        mvr.review_notes = review_notes

        if action == 'approve':
            mvr.status = ManualVerificationRequest.STATUS_APPROVED
            # Update the linked verification attempt to verified
            if mvr.verification_attempt:
                attempt = mvr.verification_attempt
                attempt.decision = VerificationAttempt.DECISION_VERIFIED
                attempt.decision_reason = (
                    f'Manual verification approved by '
                    f'{request.user.get_full_name() or request.user.username}. '
                    f'{review_notes[:200]}'
                )
                attempt.overridden = True
                attempt.override_by = request.user
                attempt.override_reason = f'Admin approved manual verification request: {review_notes}'
                attempt.override_at = timezone.now()
                attempt.save()
            AuditLog.log(
                action=AuditLog.ACTION_MANUAL_VERIFY_APPROVED,
                user=request.user,
                target_type='ManualVerificationRequest',
                target_id=mvr.id,
                details={
                    'beneficiary_id': mvr.beneficiary.beneficiary_id,
                    'review_notes': review_notes,
                    'attempt_id': str(mvr.verification_attempt_id) if mvr.verification_attempt_id else None,
                },
                request=request,
            )
            # Create ClaimRecord for approved manual verification
            if mvr.stipend_event and not ClaimRecord.objects.filter(
                beneficiary=mvr.beneficiary,
                stipend_event=mvr.stipend_event,
                status=ClaimRecord.STATUS_CLAIMED,
            ).exists():
                ClaimRecord.objects.create(
                    beneficiary=mvr.beneficiary,
                    stipend_event=mvr.stipend_event,
                    claimant_type=mvr.claimant_type,
                    claimed_by=mvr.requested_by,
                    verification_attempt=mvr.verification_attempt,
                    approved_by=request.user,
                    approved_at=timezone.now(),
                    status=ClaimRecord.STATUS_CLAIMED,
                    notes=f'Admin manual verification approved by {request.user.get_full_name() or request.user.username}.',
                )
                AuditLog.log(
                    action=AuditLog.ACTION_CLAIM,
                    user=request.user,
                    target_type='Beneficiary',
                    target_id=mvr.beneficiary.id,
                    details={
                        'beneficiary_id': mvr.beneficiary.beneficiary_id,
                        'stipend_event': mvr.stipend_event.title,
                        'claimant_type': mvr.claimant_type,
                        'via': 'manual_verification_approved',
                    },
                    request=request,
                )
            messages.success(
                request,
                f'Manual verification approved for {mvr.beneficiary.full_name}.'
            )
        else:
            mvr.status = ManualVerificationRequest.STATUS_REJECTED
            if mvr.verification_attempt:
                attempt = mvr.verification_attempt
                attempt.decision = VerificationAttempt.DECISION_DENIED
                attempt.decision_reason = (
                    f'Manual verification rejected by '
                    f'{request.user.get_full_name() or request.user.username}. '
                    f'{review_notes[:200]}'
                )
                attempt.save()
            AuditLog.log(
                action=AuditLog.ACTION_MANUAL_VERIFY_REJECTED,
                user=request.user,
                target_type='ManualVerificationRequest',
                target_id=mvr.id,
                details={
                    'beneficiary_id': mvr.beneficiary.beneficiary_id,
                    'review_notes': review_notes,
                },
                request=request,
            )
            messages.warning(
                request,
                f'Manual verification request rejected for {mvr.beneficiary.full_name}.'
            )

        mvr.save()
        return redirect('verification:manual_review')

    return render(request, 'verification/manual_verify_review.html', {'mvr': mvr})


@login_required
@require_http_methods(['GET', 'POST'])
def face_update_review(request, request_id):
    """Admin approves or rejects a FaceUpdateRequest."""
    from django.contrib import messages

    if not request.user.is_admin:
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:dashboard')

    fur = get_object_or_404(FaceUpdateRequest, pk=request_id)

    if request.method == 'POST':
        action = request.POST.get('action', '')
        review_notes = request.POST.get('review_notes', '').strip()

        if action not in ('approve', 'reject'):
            messages.error(request, 'Invalid action.')
            return redirect('verification:manual_review')

        fur.reviewed_by = request.user
        fur.reviewed_at = timezone.now()
        fur.review_notes = review_notes

        if action == 'approve':
            fur.status = FaceUpdateRequest.STATUS_APPROVED

            # Now apply the stored embedding to the active face data
            beneficiary = fur.beneficiary
            encrypted = bytes(fur.new_embedding_data)

            if fur.action == FaceUpdateLog.ACTION_REPLACE:
                if hasattr(beneficiary, 'face_embedding'):
                    emb = beneficiary.face_embedding
                    emb.embedding_data = encrypted
                    emb.created_by = fur.requested_by
                    emb.save()
                else:
                    FaceEmbedding.objects.create(
                        beneficiary=beneficiary,
                        embedding_data=encrypted,
                        created_by=fur.requested_by,
                    )
                action_label = 'Primary embedding replaced'
            else:
                AdditionalFaceEmbedding.objects.create(
                    beneficiary=beneficiary,
                    embedding_data=encrypted,
                    label=f'update-{fur.created_at.strftime("%Y-%m-%d")}',
                    created_by=fur.requested_by,
                )
                action_label = 'Additional template added'

            FaceUpdateLog.objects.create(
                beneficiary=beneficiary,
                performed_by=fur.requested_by,
                reason=fur.reason,
                action=fur.action,
                notes=f'Approved by {request.user.get_full_name() or request.user.username}. {review_notes}',
                success=True,
            )

            AuditLog.log(
                action=AuditLog.ACTION_FACE_UPDATE_APPROVED,
                user=request.user,
                target_type='FaceUpdateRequest',
                target_id=fur.id,
                details={
                    'beneficiary_id': beneficiary.beneficiary_id,
                    'action': fur.action,
                    'action_label': action_label,
                    'review_notes': review_notes,
                },
                request=request,
            )
            messages.success(
                request,
                f'Face update approved and applied for {beneficiary.full_name}.'
            )
        else:
            fur.status = FaceUpdateRequest.STATUS_REJECTED
            FaceUpdateLog.objects.create(
                beneficiary=fur.beneficiary,
                performed_by=fur.requested_by,
                reason=fur.reason,
                action=fur.action,
                notes=f'Rejected by {request.user.get_full_name() or request.user.username}. {review_notes}',
                success=False,
            )
            AuditLog.log(
                action=AuditLog.ACTION_FACE_UPDATE_REJECTED,
                user=request.user,
                target_type='FaceUpdateRequest',
                target_id=fur.id,
                details={
                    'beneficiary_id': fur.beneficiary.beneficiary_id,
                    'review_notes': review_notes,
                },
                request=request,
            )
            messages.warning(
                request,
                f'Face update request rejected for {fur.beneficiary.full_name}.'
            )

        fur.save()
        return redirect('verification:manual_review')

    return render(request, 'verification/face_update_review.html', {'fur': fur})


# ─── Special Claim Request ────────────────────────────────────────────────────

@login_required
@require_POST
def special_claim_request(request, pk):
    """
    Staff submits a SpecialClaimRequest to allow a second claim for a beneficiary
    that has already claimed the current stipend event.
    """
    from django.contrib import messages

    beneficiary = get_object_or_404(Beneficiary, pk=pk)
    today = timezone.now().date()
    active_event = StipendEvent.get_active_event_for_date(today)

    reason = request.POST.get('reason', '').strip()

    if not reason:
        messages.error(request, 'A reason is required for the special claim request.')
        return redirect('beneficiaries:beneficiary_detail', pk=pk)

    if not active_event:
        messages.error(request, 'No active stipend event found. Special claim requests require an active event.')
        return redirect('beneficiaries:beneficiary_detail', pk=pk)

    # Find the original claim to reference
    original_claim = ClaimRecord.objects.filter(
        beneficiary=beneficiary,
        stipend_event=active_event,
        status=ClaimRecord.STATUS_CLAIMED,
    ).first()

    # Check for an already-pending request to avoid duplicates
    if SpecialClaimRequest.objects.filter(
        beneficiary=beneficiary,
        stipend_event=active_event,
        status=SpecialClaimRequest.STATUS_PENDING,
    ).exists():
        messages.warning(
            request,
            'A special claim request for this beneficiary and event is already pending admin review.'
        )
        return redirect('beneficiaries:beneficiary_detail', pk=pk)

    scr = SpecialClaimRequest.objects.create(
        beneficiary=beneficiary,
        stipend_event=active_event,
        original_claim=original_claim,
        requested_by=request.user,
        reason=reason,
        notes=request.POST.get('notes', '').strip(),
    )

    AuditLog.log(
        action=AuditLog.ACTION_SPECIAL_CLAIM_REQUEST,
        user=request.user,
        target_type='SpecialClaimRequest',
        target_id=scr.id,
        details={
            'beneficiary_id': beneficiary.beneficiary_id,
            'stipend_event': active_event.title,
            'reason': reason,
        },
        request=request,
    )

    messages.info(
        request,
        f'Special claim request submitted for {beneficiary.full_name}. '
        'An admin must approve before a second claim can be recorded.'
    )
    return redirect('beneficiaries:beneficiary_detail', pk=pk)


@login_required
@require_http_methods(['GET', 'POST'])
def special_claim_review(request, request_id):
    """Admin approves or rejects a SpecialClaimRequest."""
    from django.contrib import messages

    if not request.user.is_admin:
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:dashboard')

    scr = get_object_or_404(SpecialClaimRequest, pk=request_id)

    if request.method == 'POST':
        action = request.POST.get('action', '')
        review_notes = request.POST.get('review_notes', '').strip()

        if action not in ('approve', 'reject'):
            messages.error(request, 'Invalid action.')
            return redirect('verification:manual_review')

        scr.reviewed_by = request.user
        scr.reviewed_at = timezone.now()
        scr.review_notes = review_notes

        if action == 'approve':
            scr.status = SpecialClaimRequest.STATUS_APPROVED

            # Create the additional ClaimRecord
            if scr.stipend_event:
                ClaimRecord.objects.create(
                    beneficiary=scr.beneficiary,
                    stipend_event=scr.stipend_event,
                    claimant_type=VerificationAttempt.CLAIMANT_BENEFICIARY,
                    claimed_by=scr.requested_by,
                    approved_by=request.user,
                    approved_at=timezone.now(),
                    status=ClaimRecord.STATUS_CLAIMED,
                    is_special_additional=True,
                    notes=f'Special additional claim approved by {request.user.get_full_name() or request.user.username}. {review_notes}',
                )

            AuditLog.log(
                action=AuditLog.ACTION_SPECIAL_CLAIM_APPROVED,
                user=request.user,
                target_type='SpecialClaimRequest',
                target_id=scr.id,
                details={
                    'beneficiary_id': scr.beneficiary.beneficiary_id,
                    'stipend_event': scr.stipend_event.title if scr.stipend_event else None,
                    'review_notes': review_notes,
                },
                request=request,
            )
            messages.success(
                request,
                f'Special claim approved for {scr.beneficiary.full_name}. A second claim record has been created.'
            )
        else:
            scr.status = SpecialClaimRequest.STATUS_REJECTED
            AuditLog.log(
                action=AuditLog.ACTION_SPECIAL_CLAIM_REJECTED,
                user=request.user,
                target_type='SpecialClaimRequest',
                target_id=scr.id,
                details={
                    'beneficiary_id': scr.beneficiary.beneficiary_id,
                    'stipend_event': scr.stipend_event.title if scr.stipend_event else None,
                    'review_notes': review_notes,
                },
                request=request,
            )
            messages.warning(
                request,
                f'Special claim request rejected for {scr.beneficiary.full_name}.'
            )

        scr.save()
        return redirect('verification:manual_review')

    return render(request, 'verification/special_claim_review.html', {'scr': scr})


# ─── Registration Approval ────────────────────────────────────────────────────

@login_required
def registration_review_list(request):
    """Admin queue showing all pending beneficiary registrations."""
    from django.contrib import messages

    if not request.user.is_admin:
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:dashboard')

    pending = (
        Beneficiary.objects
        .filter(status=Beneficiary.STATUS_PENDING)
        .select_related('registered_by')
        .order_by('created_at')
    )
    return render(request, 'verification/registration_review_list.html', {
        'pending': pending,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def registration_review(request, pk):
    """Admin approves or rejects a single pending beneficiary registration."""
    from django.contrib import messages

    if not request.user.is_admin:
        messages.error(request, 'Admin access required.')
        return redirect('beneficiaries:dashboard')

    beneficiary = get_object_or_404(Beneficiary, pk=pk, status=Beneficiary.STATUS_PENDING)

    if request.method == 'POST':
        action = request.POST.get('action', '')
        review_notes = request.POST.get('review_notes', '').strip()

        if action not in ('approve', 'reject'):
            messages.error(request, 'Invalid action.')
            return redirect('verification:registration_review_list')

        if not review_notes:
            messages.error(request, 'Review notes are required.')
            return render(request, 'verification/registration_review.html', {
                'beneficiary': beneficiary,
            })

        if action == 'approve':
            beneficiary.status = Beneficiary.STATUS_ACTIVE
            beneficiary.save()

            AuditLog.log(
                action=AuditLog.ACTION_REGISTER_APPROVED,
                user=request.user,
                target_type='Beneficiary',
                target_id=beneficiary.id,
                details={
                    'beneficiary_id': beneficiary.beneficiary_id,
                    'name': beneficiary.full_name,
                    'review_notes': review_notes,
                },
                request=request,
            )
            messages.success(
                request,
                f'Registration approved for {beneficiary.full_name} '
                f'(ID: {beneficiary.beneficiary_id}). They are now active.'
            )
        else:
            beneficiary.status = Beneficiary.STATUS_INACTIVE
            beneficiary.deactivated_reason = (
                f'Registration rejected by '
                f'{request.user.get_full_name() or request.user.username}: {review_notes}'
            )
            beneficiary.save()

            AuditLog.log(
                action=AuditLog.ACTION_REGISTER_REJECTED,
                user=request.user,
                target_type='Beneficiary',
                target_id=beneficiary.id,
                details={
                    'beneficiary_id': beneficiary.beneficiary_id,
                    'name': beneficiary.full_name,
                    'review_notes': review_notes,
                },
                request=request,
            )
            messages.warning(
                request,
                f'Registration rejected for {beneficiary.full_name}.'
            )

        return redirect('verification:registration_review_list')

    return render(request, 'verification/registration_review.html', {
        'beneficiary': beneficiary,
    })


# ─── Representative Face Registration ────────────────────────────────────────

@login_required
@require_http_methods(['GET'])
def register_rep_face(request, pk, rep_pk):
    """Show the face capture UI for a representative."""
    beneficiary = get_object_or_404(Beneficiary, pk=pk)
    rep = get_object_or_404(Representative, pk=rep_pk, beneficiary=beneficiary)
    return render(request, 'verification/register_rep_face.html', {
        'beneficiary': beneficiary,
        'representative': rep,
        'using_mock': is_using_mock_model(),
        'model_load_error': get_model_load_error() if is_using_mock_model() else None,
    })


@login_required
@require_POST
def register_rep_face_submit(request, pk, rep_pk):
    """Ajax endpoint to save a representative's face embedding."""
    beneficiary = get_object_or_404(Beneficiary, pk=pk)
    rep = get_object_or_404(Representative, pk=rep_pk, beneficiary=beneficiary)
    try:
        data = json.loads(request.body)
        image_data = data.get('image', '')
        if not image_data:
            return JsonResponse({'success': False, 'error': 'No image provided.'})

        if ',' in image_data:
            image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)

        result = process_face_for_registration(image_bytes)
        if not result['success']:
            return JsonResponse({'success': False, 'error': result['error']})

        RepresentativeFaceEmbedding.objects.update_or_create(
            representative=rep,
            defaults={
                'embedding_data': result['encrypted_embedding'],
                'created_by': request.user,
            },
        )

        AuditLog.log(
            action=AuditLog.ACTION_REGISTER,
            user=request.user,
            target_type='Representative',
            target_id=rep.id,
            details={
                'representative_name': rep.full_name,
                'beneficiary_id': beneficiary.beneficiary_id,
                'action': 'face_registered',
            },
            request=request,
        )
        return JsonResponse({
            'success': True,
            'message': f'Face registered for {rep.full_name}.',
            'redirect': f'/dashboard/beneficiaries/{beneficiary.pk}/',
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
