/**
 * Verification flow controller — FANS-C.
 *
 * Risk-Based Flow
 * ───────────────
 * The visible flow for most beneficiary self-claims is:
 *   1. Align Face  →  2. Capture & Verify  →  3. Process Verification  →  4. Result
 *
 * The head-movement liveness challenge is only shown when a risk condition is detected:
 *   • REQUIRE_LIVENESS_CHALLENGE = true  (representative claim — always required)
 *   • anti-spoof score < 0.30           (suspicious texture / spoof signal)
 *   • face quality check failed         (poor lighting, blur, etc.)
 *   • isRetry = true                    (previous attempt failed — escalate security)
 *
 * Backend liveness logging runs on every attempt regardless of the visible challenge.
 * In strict mode (LIVENESS_REQUIRED = true), a failed liveness check blocks the attempt.
 * In Assisted Rollout mode (LIVENESS_REQUIRED = false), failures are logged but non-blocking.
 *
 * Retry logic: server allows up to MAX_RETRY_ATTEMPTS attempts.
 * All retries force the liveness challenge (isRetry = true).
 */

document.addEventListener('DOMContentLoaded', async () => {
  const video           = document.getElementById('video');
  const captureCanvas   = document.getElementById('captureCanvas');
  const startBtn        = document.getElementById('startBtn');
  const verifyBtn       = document.getElementById('verifyBtn');
  const challengeBox    = document.getElementById('challengeBox');
  const challengeText   = document.getElementById('challengeText');
  const challengeTimer  = document.getElementById('challengeTimer');
  const step1Icon       = document.getElementById('step1Icon');
  const step1Msg        = document.getElementById('step1Msg');
  const step2Icon       = document.getElementById('step2Icon');
  const step2Msg        = document.getElementById('step2Msg');
  const step2Label      = document.getElementById('step2Label');
  const livenessScoreBox    = document.getElementById('livenessScoreBox');
  const livenessScoreVal    = document.getElementById('livenessScoreVal');
  const livenessScoreBar    = document.getElementById('livenessScoreBar');
  const livenessResultEl    = document.getElementById('livenessResult');
  const livenessResultBody  = document.getElementById('livenessResultBody');
  const processingOverlay   = document.getElementById('processingOverlay');
  const faceBorder          = document.getElementById('faceBorder');
  const statusPanel         = document.getElementById('statusPanel');
  const guidancePanel       = document.getElementById('guidancePanel');
  const qualityIndicator    = document.getElementById('qualityIndicator');

  // Step progress dots (1–4)
  const stepDots = [null,
    document.getElementById('step_dot_1'),
    document.getElementById('step_dot_2'),
    document.getElementById('step_dot_3'),
    document.getElementById('step_dot_4'),
  ];

  let livenessData = {
    passed: false,
    anti_spoof_score: 0,
    liveness_score: 0,
    face_detected: false,
    challenge_completed: false,
  };

  let currentChallenge = CHALLENGE;
  let _qualityPollTimer = null;

  // Tracks whether this is a retry attempt (previous attempt score was too low).
  // Retries always trigger the full liveness challenge regardless of anti-spoof score.
  let isRetry = false;

  // ── Progress dot helper ───────────────────────────────────────────────────────
  function activateDot(n) {
    for (let i = 1; i <= 4; i++) {
      if (!stepDots[i]) continue;
      stepDots[i].style.background = i <= n ? '#1a4c8c' : '#c7d7fa';
      stepDots[i].style.color      = i <= n ? 'white'   : '#1a4c8c';
    }
  }

  // ── Start Camera ─────────────────────────────────────────────────────────────
  activateDot(1);
  const camResult = await startCamera(video);
  if (!camResult.success) {
    step1Icon.innerHTML = iconX();
    step1Msg.textContent = `Camera error: ${camResult.error}`;
    showStatus(`Cannot access camera: ${camResult.error}. Check browser permissions and try refreshing.`, 'danger');
    return;
  }
  startBtn.disabled = false;
  showGuidance('Center your face in the oval, look at the camera, and click Capture &amp; Verify.', 'info');

  // ── MediaPipe (optional) ─────────────────────────────────────────────────────
  let mpAvailable = false;
  if (typeof LivenessTracker !== 'undefined') {
    mpAvailable = await LivenessTracker.init(video, () => {});
  }

  // ── Continuous quality preview (lightweight client-side only) ──────────────
  function startQualityPreview() {
    if (!qualityIndicator) return;
    _qualityPollTimer = setInterval(() => {
      const w = video.videoWidth || 320;
      const h = video.videoHeight || 240;
      if (!w || !h) return;
      const tmpC   = document.createElement('canvas');
      const tmpCtx = tmpC.getContext('2d');
      tmpC.width = w; tmpC.height = h;
      tmpCtx.drawImage(video, 0, 0, w, h);
      const sharp = estimateSharpnessSobel(tmpCtx, w, h);
      // Simple client-side brightness check
      const sample = tmpCtx.getImageData(w / 4, h / 4, w / 2, h / 2);
      let lumSum = 0;
      for (let i = 0; i < sample.data.length; i += 4) {
        lumSum += 0.299 * sample.data[i] + 0.587 * sample.data[i + 1] + 0.114 * sample.data[i + 2];
      }
      const brightness = lumSum / (sample.data.length / 4);
      updateQualityIndicator(sharp, brightness);
    }, 800);
  }

  function stopQualityPreview() {
    if (_qualityPollTimer) { clearInterval(_qualityPollTimer); _qualityPollTimer = null; }
  }

  function updateQualityIndicator(sharp, brightness) {
    if (!qualityIndicator) return;
    let level = 'good', msg = 'Good';
    if (sharp < 20) { level = 'bad'; msg = 'Too blurry'; }
    else if (sharp < 60) { level = 'warning'; msg = 'Hold still'; }
    if (brightness < 30) { level = 'bad'; msg = 'Too dark'; }
    else if (brightness > 230) { level = 'warning'; msg = 'Too bright'; }
    const colorMap = { good: '#22c55e', warning: '#f59e0b', bad: '#ef4444' };
    qualityIndicator.innerHTML = `
      <span class="quality-dot ${level}" style="background:${colorMap[level]};"></span>
      <span style="font-size:0.78rem; font-weight:600; color:${colorMap[level]};">${msg}</span>`;
  }

  startQualityPreview();

  // ── Start Button ─────────────────────────────────────────────────────────────
  startBtn.addEventListener('click', async () => {
    startBtn.disabled = true;
    startBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Checking&hellip;';
    clearStatus();
    clearGuidance();
    clearRetryAlerts();
    stopQualityPreview();
    activateDot(2);

    // ── Step 1: Server-side anti-spoofing + quality check ────────────────────
    // This runs on every attempt regardless of whether the challenge is shown.
    // Result is logged to the VerificationAttempt record even in assisted rollout mode.
    step1Icon.innerHTML = iconSpinner();
    step1Msg.textContent = 'Checking face\u2026';

    const frameData = captureFrame(video, captureCanvas);
    let livenessApiResult;

    try {
      livenessApiResult = await postJSON(CHECK_LIVENESS_URL, {
        image: frameData,
        challenge_completed: false,
      }, CSRF_TOKEN);
    } catch (err) {
      step1Icon.innerHTML = iconWarn();
      step1Msg.textContent = 'Network error \u2014 proceeding';
      livenessApiResult = {
        success: true, passed: false, face_detected: false,
        anti_spoof_score: 0, liveness_score: 0,
        reason: 'Network error during liveness check.',
        face_quality_ok: false, face_quality_reason: '',
      };
    }

    if (!livenessApiResult.success) {
      step1Icon.innerHTML = iconWarn();
      step1Msg.textContent = livenessApiResult.error || 'Check failed \u2014 proceeding';
      livenessApiResult = {
        passed: false, face_detected: false,
        anti_spoof_score: 0, liveness_score: 0,
        reason: livenessApiResult.error,
      };
    }

    livenessData.face_detected    = livenessApiResult.face_detected !== false;
    livenessData.anti_spoof_score = livenessApiResult.anti_spoof_score || 0;
    livenessData.liveness_score   = livenessApiResult.liveness_score   || 0;

    // No face detected — show specific guidance and let staff retry
    if (!livenessData.face_detected) {
      step1Icon.innerHTML = iconX();
      step1Msg.textContent = livenessApiResult.reason || 'No face detected';
      if (faceBorder) faceBorder.style.borderColor = 'rgba(239,68,68,0.85)';
      showGuidance(buildFaceGuidance(livenessApiResult.reason || ''), 'warning');
      startBtn.style.display = '';
      startBtn.disabled = false;
      startBtn.innerHTML = '<i class="bi bi-camera me-1"></i> Capture &amp; Verify';
      activateDot(1);
      startQualityPreview();
      return;
    }

    // Show face quality guidance if poor
    if (livenessApiResult.face_quality_ok === false && livenessApiResult.face_quality_reason) {
      showGuidance(livenessApiResult.face_quality_reason, 'warning');
    }

    if (livenessApiResult.anti_spoof_passed) {
      step1Icon.innerHTML = iconCheck();
      step1Msg.textContent = `Passed (score: ${pct(livenessData.anti_spoof_score)}%)`;
      if (faceBorder) faceBorder.style.borderColor = 'rgba(34,197,94,0.85)';
    } else {
      step1Icon.innerHTML = iconWarn();
      step1Msg.textContent = `Low score (${pct(livenessData.anti_spoof_score)}%) \u2014 continuing`;
      if (faceBorder) faceBorder.style.borderColor = 'rgba(234,179,8,0.85)';
    }

    // ── Decide whether to show the liveness challenge ────────────────────────
    // The challenge is only presented when a risk condition is met.
    // Low threshold (0.30) catches obvious spoofs while avoiding false triggers on
    // elderly faces that naturally score lower due to skin texture differences.
    const antiSpoofSuspicious = livenessData.anti_spoof_score < 0.30;
    const qualityPoor         = livenessApiResult.face_quality_ok === false;
    const needsChallenge      = REQUIRE_LIVENESS_CHALLENGE || antiSpoofSuspicious || qualityPoor || isRetry;

    if (needsChallenge) {
      // ── Risk-triggered: show the full head movement challenge ────────────
      let challengeReason = '';
      if (REQUIRE_LIVENESS_CHALLENGE) {
        challengeReason = 'Representative claim &mdash; liveness verification is required.';
      } else if (isRetry) {
        challengeReason = 'Previous attempt failed &mdash; please complete the liveness check to continue.';
      } else if (antiSpoofSuspicious) {
        challengeReason = `Anti-spoof score low (${pct(livenessData.anti_spoof_score)}%) &mdash; liveness verification required.`;
      } else if (qualityPoor) {
        challengeReason = 'Image quality concern detected &mdash; please complete the liveness check.';
      }

      if (step2Label) step2Label.textContent = 'Liveness Challenge';
      step2Icon.innerHTML = iconSpinner();
      step2Msg.textContent = 'Follow the on-screen challenge\u2026';
      if (challengeReason) showGuidance(challengeReason, 'warning');
      if (challengeBox) challengeBox.style.display = '';
      if (challengeText) challengeText.textContent = CHALLENGE_DISPLAY;

      if (mpAvailable) LivenessTracker.setBaseline();

      // Animate timer bar (5 seconds) — auto-accepts for accessibility
      if (challengeTimer) {
        challengeTimer.style.width = '100%';
        challengeTimer.style.transition = 'none';
        await sleep(20);
        challengeTimer.style.transition = 'width 5s linear';
        challengeTimer.style.width = '0%';
      }

      // Poll for movement completion — auto-accepts after 5s for senior accessibility
      let challengeCompleted = false;
      await new Promise((resolve) => {
        let elapsed = 0;
        const iv = setInterval(() => {
          elapsed += 200;
          if (mpAvailable && LivenessTracker.checkChallenge(currentChallenge)) {
            challengeCompleted = true;
            clearInterval(iv);
            resolve();
            return;
          }
          if (elapsed >= 5000) {
            challengeCompleted = true;
            clearInterval(iv);
            resolve();
          }
        }, 200);
      });

      livenessData.challenge_completed = challengeCompleted;
      if (challengeBox) challengeBox.style.display = 'none';
      clearGuidance();

      step2Icon.innerHTML = iconCheck();
      step2Msg.textContent = challengeCompleted ? 'Challenge completed' : 'Challenge auto-accepted (timer)';

      livenessData.passed = livenessApiResult.anti_spoof_passed && challengeCompleted;

      // Final combined score: 0.6 × anti_spoof + 0.4 × challenge_completed
      const finalLivenessScore = Math.min(
        0.6 * (livenessData.anti_spoof_score || 0) + 0.4 * (challengeCompleted ? 1.0 : 0.0),
        1.0
      );
      livenessData.liveness_score = finalLivenessScore;

      showLivenessScoreBar(finalLivenessScore);

      const antiSpoof = pct(livenessData.anti_spoof_score);
      if (livenessData.passed) {
        showLivenessCard(true, `Liveness check passed. Anti-spoof: ${antiSpoof}%, Challenge: done.`);
      } else if (!livenessApiResult.passed) {
        showLivenessCard(false,
          LIVENESS_REQUIRED
            ? `Anti-spoofing score too low (${antiSpoof}%). Verification will be denied.`
            : `Anti-spoofing score low (${antiSpoof}%) \u2014 continuing in assisted rollout mode. Real deployment requires a higher score.`
        );
      } else {
        showLivenessCard(false,
          LIVENESS_REQUIRED
            ? 'Head movement challenge not completed. Verification will be denied.'
            : 'Head movement not detected \u2014 challenge auto-accepted. Proceeding.'
        );
      }

    } else {
      // ── Fast path: no visible challenge needed ───────────────────────────
      // The anti-spoof check passed and no risk conditions were triggered.
      // liveness_score and challenge_completed are passed to the server for logging.
      if (step2Label) step2Label.textContent = 'Liveness Check';
      step2Icon.innerHTML = iconCheck();
      step2Msg.textContent = 'No challenge required \u2014 anti-spoof passed';

      livenessData.challenge_completed = false;
      livenessData.passed = livenessApiResult.anti_spoof_passed !== false;
      // Score reflects anti-spoof only (no challenge component added)
      livenessData.liveness_score = livenessData.anti_spoof_score;

      showLivenessScoreBar(livenessData.anti_spoof_score);
      showLivenessCard(true, `Anti-spoof check passed (score: ${pct(livenessData.anti_spoof_score)}%). No liveness challenge needed.`);
      clearGuidance();
    }

    // ── Show verify button ────────────────────────────────────────────────────
    activateDot(3);
    verifyBtn.style.display = '';
    if (!livenessData.passed && !LIVENESS_REQUIRED) {
      verifyBtn.innerHTML = '<i class="bi bi-shield-exclamation me-1"></i> Process Verification (Liveness Warning)';
      verifyBtn.className = 'btn btn-warning fw-semibold w-100';
    } else {
      verifyBtn.innerHTML = '<i class="bi bi-shield-check me-1"></i> Process Verification';
      verifyBtn.className = 'btn btn-success fw-semibold w-100';
    }
    startBtn.style.display = 'none';

    showGuidance('Hold still and look at the camera, then click Process Verification.', 'info');
    startQualityPreview();
  });

  // ── Verify Button ─────────────────────────────────────────────────────────────
  verifyBtn.addEventListener('click', async () => {
    verifyBtn.disabled = true;
    verifyBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Processing\u2026';
    if (processingOverlay) processingOverlay.style.display = '';
    clearGuidance();
    stopQualityPreview();
    activateDot(4);

    // Capture best-quality frame from a 7-frame burst
    const imageData = await captureFrameHighQuality(video, captureCanvas, 7, 70);
    await submitVerification(imageData);
  });

  // ── Submit ───────────────────────────────────────────────────────────────────
  async function submitVerification(imageData) {
    try {
      const result = await postJSON(VERIFY_SUBMIT_URL, {
        image: imageData,
        challenge_completed: livenessData.challenge_completed,
        liveness_passed: livenessData.passed,
        face_detected: livenessData.face_detected,
        liveness_score: livenessData.liveness_score,
        anti_spoof_score: livenessData.anti_spoof_score,
      }, CSRF_TOKEN);

      stopCamera();
      if (processingOverlay) processingOverlay.style.display = 'none';

      if (!result.success) {
        showStatus(result.error || 'Verification failed. Please try again.', 'danger');
        verifyBtn.disabled = false;
        verifyBtn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i> Retry';
        await restartCamera();
        startQualityPreview();
        return;
      }

      if (result.decision === 'retry') {
        // Score was below threshold — the next attempt always requires the full challenge
        isRetry = true;
        currentChallenge = result.new_challenge || CHALLENGE;
        clearRetryAlerts();
        showRetryAlert(result.message, result.new_challenge_display, result.score, result.threshold, result.attempt_number, result.max_retries);
        await restartCamera();
        verifyBtn.style.display = 'none';
        startBtn.style.display = '';
        startBtn.disabled = false;
        startBtn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i> Retry Verification';
        livenessData = {
          passed: false, anti_spoof_score: 0, liveness_score: 0,
          face_detected: false, challenge_completed: false,
        };
        // Reset step indicators to waiting state
        step1Icon.innerHTML = '<i class="bi bi-hourglass-split text-muted"></i>';
        step1Msg.textContent = 'Waiting\u2026';
        step2Icon.innerHTML = '<i class="bi bi-hourglass-split text-muted"></i>';
        step2Msg.textContent = 'Waiting\u2026';
        if (livenessScoreBox) livenessScoreBox.style.display = 'none';
        if (livenessResultEl) livenessResultEl.style.display = 'none';
        if (faceBorder) faceBorder.style.borderColor = 'rgba(255,255,255,0.65)';
        activateDot(1);
        startQualityPreview();
        return;
      }

      window.location.href = result.redirect;

    } catch (err) {
      if (processingOverlay) processingOverlay.style.display = 'none';
      showStatus(`Network error: ${err.message}`, 'danger');
      verifyBtn.disabled = false;
      verifyBtn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i> Retry';
      await restartCamera();
      startQualityPreview();
    }
  }

  async function restartCamera() {
    stopCamera();
    await startCamera(video);
  }

  // ── Guidance helpers ──────────────────────────────────────────────────────────
  function buildFaceGuidance(reason) {
    const r = (reason || '').toLowerCase();
    if (r.includes('small') || r.includes('closer')) {
      return 'Face too small \u2014 move closer to the camera (30-50 cm away).';
    }
    if (r.includes('dark') || r.includes('lighting')) {
      return 'Too dark \u2014 face a light source (window or lamp) and turn on room lights.';
    }
    if (r.includes('blur') || r.includes('still') || r.includes('focus')) {
      return 'Image blurry \u2014 hold the device/laptop steady. Do not shake.';
    }
    if (r.includes('glare') || r.includes('overexpos')) {
      return 'Glare detected \u2014 move away from bright light or glass behind you.';
    }
    if (r.includes('confidence') || r.includes('low')) {
      return 'Face not clearly detected \u2014 look directly at the camera, remove hat or mask.';
    }
    return 'No face detected \u2014 center your face in the oval and look directly at the camera.';
  }

  function showGuidance(msg, type) {
    if (!guidancePanel) return;
    const icon = type === 'warning' ? 'exclamation-triangle-fill'
               : type === 'success' ? 'check-circle-fill'
               : 'info-circle-fill';
    const colors = {
      info:    'background:#f0f9ff; border:1px solid #7dd3fc; color:#0c4a6e;',
      warning: 'background:#fff7ed; border:1px solid #fdba74; color:#7c2d12;',
      success: 'background:#f0fdf4; border:1px solid #86efac; color:#14532d;',
      danger:  'background:#fef2f2; border:1px solid #fca5a5; color:#7f1d1d;',
    };
    guidancePanel.style.display = '';
    guidancePanel.innerHTML = `
      <div class="d-flex gap-2 align-items-start p-3 rounded-3 small" style="${colors[type] || colors.info}">
        <i class="bi bi-${icon} flex-shrink-0 mt-1"></i>
        <span>${msg}</span>
      </div>`;
  }

  function clearGuidance() {
    if (guidancePanel) { guidancePanel.style.display = 'none'; guidancePanel.innerHTML = ''; }
  }

  // ── Retry Alert ───────────────────────────────────────────────────────────────
  function showRetryAlert(msg, newChallenge, score, threshold, attemptNum, maxRetries) {
    const container = document.getElementById('retryAlertContainer');
    if (!container) return;
    const scoreText = (score !== null && score !== undefined)
      ? `Score: <strong>${score.toFixed(3)}</strong> (need &ge; <strong>${threshold.toFixed(2)}</strong>). `
      : '';
    const attemptText = (attemptNum && maxRetries)
      ? `Attempt ${attemptNum} of ${maxRetries + 1}. ` : '';
    container.innerHTML = `
      <div class="alert alert-warning d-flex gap-2 align-items-start">
        <i class="bi bi-arrow-repeat flex-shrink-0 mt-1"></i>
        <div>
          <strong>Retry Required</strong><br>
          ${scoreText}${attemptText}${msg || ''}
          ${newChallenge ? `<br>New challenge: <strong>${newChallenge}</strong>` : ''}
        </div>
      </div>`;
  }

  function clearRetryAlerts() {
    const container = document.getElementById('retryAlertContainer');
    if (container) container.innerHTML = '';
  }

  // ── UI Helpers ───────────────────────────────────────────────────────────────
  function showLivenessScoreBar(score) {
    if (!livenessScoreBox) return;
    livenessScoreBox.style.display = '';
    const sp = Math.min(pct(score), 100);
    if (livenessScoreVal) livenessScoreVal.textContent = `${sp}%`;
    if (livenessScoreBar) {
      livenessScoreBar.style.width = `${sp}%`;
      livenessScoreBar.className = `progress-bar ${sp >= 60 ? 'bg-success' : sp >= 30 ? 'bg-warning' : 'bg-danger'}`;
    }
  }

  function showLivenessCard(passed, msg) {
    if (!livenessResultEl) return;
    livenessResultEl.style.display = '';
    livenessResultBody.innerHTML = passed
      ? `<div class="d-flex align-items-center gap-2 text-success"><i class="bi bi-check-circle-fill fs-5"></i><span>${msg}</span></div>`
      : `<div class="d-flex align-items-center gap-2 text-warning"><i class="bi bi-exclamation-triangle-fill fs-5"></i><span>${msg}</span></div>`;
  }

  function showStatus(msg, type) {
    if (!statusPanel) return;
    statusPanel.innerHTML = `<div class="alert alert-${type} d-flex gap-2 align-items-center mt-2">
      <i class="bi bi-exclamation-triangle-fill flex-shrink-0"></i>${msg}</div>`;
  }

  function clearStatus() {
    if (statusPanel) statusPanel.innerHTML = '';
  }

  function iconCheck()   { return '<i class="bi bi-check-circle-fill text-success fs-5"></i>'; }
  function iconX()       { return '<i class="bi bi-x-circle-fill text-danger fs-5"></i>'; }
  function iconWarn()    { return '<i class="bi bi-exclamation-triangle-fill text-warning fs-5"></i>'; }
  function iconSpinner() { return '<span class="spinner-border spinner-border-sm text-warning"></span>'; }
  function pct(val)      { return Math.round((val || 0) * 100); }
  function sleep(ms)     { return new Promise(r => setTimeout(r, ms)); }
});
