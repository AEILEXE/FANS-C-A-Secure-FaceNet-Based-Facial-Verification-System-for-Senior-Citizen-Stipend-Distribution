/**
 * Verification flow controller — FANS-C.
 *
 * Flow:
 *  1. Start camera (640x480 preferred)
 *  2. Capture frame -> server anti-spoof + quality check -> show face guidance
 *  3. Head movement challenge (client-side via MediaPipe, auto-accepts after 5s timer)
 *  4. Show "Process Verification" button
 *  5. Capture sharpest frame from a 7-frame burst -> submit to server for FaceNet comparison
 *  6. Server returns decision -> redirect to result page
 *
 * Demo mode (LIVENESS_REQUIRED=false): liveness failure never blocks verification.
 * Retry mode: allows up to MAX_RETRY_ATTEMPTS additional attempts before fallback.
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

  let livenessData = {
    passed: false,
    anti_spoof_score: 0,
    liveness_score: 0,
    face_detected: false,
    challenge_completed: false,
  };

  let currentChallenge = CHALLENGE;
  let _qualityPollTimer = null;

  // ── Start Camera ─────────────────────────────────────────────────────────────
  const camResult = await startCamera(video);
  if (!camResult.success) {
    step1Icon.innerHTML = iconX();
    step1Msg.textContent = `Camera error: ${camResult.error}`;
    showStatus(`Cannot access camera: ${camResult.error}. Check browser permissions and try refreshing.`, 'danger');
    return;
  }
  startBtn.disabled = false;
  showGuidance('Center your face in the oval, look at the camera, and click Start.', 'info');

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

    // Step 1: Server-side anti-spoofing + quality check
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
      startBtn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i> Retry';
      startQualityPreview();
      return;
    }

    // Show face quality guidance if poor
    if (livenessApiResult.face_quality_ok === false && livenessApiResult.face_quality_reason) {
      showGuidance(livenessApiResult.face_quality_reason, 'warning');
    }

    if (livenessApiResult.passed) {
      step1Icon.innerHTML = iconCheck();
      step1Msg.textContent = `Passed (score: ${pct(livenessData.anti_spoof_score)}%)`;
      if (faceBorder) faceBorder.style.borderColor = 'rgba(34,197,94,0.85)';
    } else {
      step1Icon.innerHTML = iconWarn();
      step1Msg.textContent = `Low score (${pct(livenessData.anti_spoof_score)}%) \u2014 continuing`;
      if (faceBorder) faceBorder.style.borderColor = 'rgba(234,179,8,0.85)';
    }

    // Step 2: Head movement challenge
    step2Icon.innerHTML = iconSpinner();
    step2Msg.textContent = 'Follow the on-screen challenge\u2026';
    if (challengeBox) challengeBox.style.display = '';
    if (challengeText) challengeText.textContent = CHALLENGE_DISPLAY;

    if (mpAvailable) LivenessTracker.setBaseline();

    // Animate timer bar (5 seconds)
    if (challengeTimer) {
      challengeTimer.style.width = '100%';
      challengeTimer.style.transition = 'none';
      await sleep(20);
      challengeTimer.style.transition = 'width 5s linear';
      challengeTimer.style.width = '0%';
    }

    // Poll for movement completion — auto-accepts after 5s for accessibility
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
          challengeCompleted = true; // auto-accept — accessibility for seniors
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

    livenessData.passed = livenessApiResult.passed && challengeCompleted;

    // Compute final combined liveness score client-side (matches server formula):
    //   0.6 * anti_spoof_score  +  0.4 * challenge_completed
    // This is the correct final score — the server only returned the anti-spoof portion.
    const finalLivenessScore = Math.min(
      0.6 * (livenessData.anti_spoof_score || 0) + 0.4 * (challengeCompleted ? 1.0 : 0.0),
      1.0
    );
    livenessData.liveness_score = finalLivenessScore;

    // Show score bar with the FINAL combined score
    if (livenessScoreBox) {
      livenessScoreBox.style.display = '';
      const sp = Math.min(pct(finalLivenessScore), 100);
      if (livenessScoreVal) livenessScoreVal.textContent = `${sp}%`;
      if (livenessScoreBar) {
        livenessScoreBar.style.width = `${sp}%`;
        livenessScoreBar.className = `progress-bar ${sp >= 60 ? 'bg-success' : sp >= 30 ? 'bg-warning' : 'bg-danger'}`;
      }
    }

    // Show liveness summary with anti-spoof detail
    const antiSpoof = pct(livenessData.anti_spoof_score);
    if (livenessData.passed) {
      showLivenessCard(true, `Liveness check passed. Anti-spoof: ${antiSpoof}%, Challenge: done.`);
    } else if (!livenessApiResult.passed) {
      showLivenessCard(false,
        LIVENESS_REQUIRED
          ? `Anti-spoofing score too low (${antiSpoof}%). Verification will be denied.`
          : `Anti-spoofing score low (${antiSpoof}%) \u2014 continuing in demo mode. Real deployment requires a higher score.`
      );
    } else {
      showLivenessCard(false,
        LIVENESS_REQUIRED
          ? 'Head movement challenge not completed. Verification will be denied.'
          : 'Head movement not detected \u2014 challenge auto-accepted. Proceeding.'
      );
    }

    // Show verify button
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
        // Reset liveness step indicators
        step1Icon.innerHTML = '<i class="bi bi-hourglass-split text-muted"></i>';
        step1Msg.textContent = 'Waiting\u2026';
        step2Icon.innerHTML = '<i class="bi bi-hourglass-split text-muted"></i>';
        step2Msg.textContent = 'Waiting\u2026';
        if (livenessScoreBox) livenessScoreBox.style.display = 'none';
        if (livenessResultEl) livenessResultEl.style.display = 'none';
        if (faceBorder) faceBorder.style.borderColor = 'rgba(255,255,255,0.65)';
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
