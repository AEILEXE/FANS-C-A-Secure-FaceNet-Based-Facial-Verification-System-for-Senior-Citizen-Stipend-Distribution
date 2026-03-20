/**
 * Verification flow controller.
 *
 * Flow:
 *  1. Start camera (640x480 preferred)
 *  2. Capture frame -> server anti-spoof check -> show face guidance
 *  3. Head movement challenge (client-side via MediaPipe, graceful fallback)
 *  4. Show "Process Verification" button (always, unless no face detected)
 *  5. Capture high-quality burst frame -> submit for face comparison
 *  6. Server returns decision -> redirect to result page
 *
 * In DEMO_MODE (LIVENESS_REQUIRED=false): liveness failure never blocks verification.
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
  const livenessScoreBox   = document.getElementById('livenessScoreBox');
  const livenessScoreVal   = document.getElementById('livenessScoreVal');
  const livenessScoreBar   = document.getElementById('livenessScoreBar');
  const livenessResultEl   = document.getElementById('livenessResult');
  const livenessResultBody = document.getElementById('livenessResultBody');
  const processingOverlay  = document.getElementById('processingOverlay');
  const faceBorder         = document.getElementById('faceBorder');
  const statusPanel        = document.getElementById('statusPanel');
  const guidancePanel      = document.getElementById('guidancePanel');

  let livenessData = {
    passed: false,
    anti_spoof_score: 0,
    liveness_score: 0,
    face_detected: false,
    challenge_completed: false,
  };

  let currentChallenge = CHALLENGE;

  // ── Start Camera ─────────────────────────────────────────────────────────────
  const camResult = await startCamera(video);
  if (!camResult.success) {
    step1Icon.innerHTML = iconX();
    step1Msg.textContent = `Camera error: ${camResult.error}`;
    showStatus(`Cannot access camera: ${camResult.error}. Check browser permissions.`, 'danger');
    return;
  }
  startBtn.disabled = false;
  showGuidance('Position your face in the oval, look at the camera, and click Start.', 'info');

  // ── MediaPipe (optional) ─────────────────────────────────────────────────────
  let mpAvailable = false;
  if (typeof LivenessTracker !== 'undefined') {
    mpAvailable = await LivenessTracker.init(video, () => {});
  }

  // ── Start Button ─────────────────────────────────────────────────────────────
  startBtn.addEventListener('click', async () => {
    startBtn.disabled = true;
    startBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Checking&hellip;';
    clearStatus();
    clearGuidance();

    // Step 1: Anti-spoofing check — capture current frame
    step1Icon.innerHTML = iconSpinner();
    step1Msg.textContent = 'Checking face&hellip;';

    const frameData = captureFrame(video, captureCanvas);
    let livenessApiResult;

    try {
      livenessApiResult = await postJSON(CHECK_LIVENESS_URL, {
        image: frameData,
        challenge_completed: false,
      }, CSRF_TOKEN);
    } catch (err) {
      step1Icon.innerHTML = iconWarn();
      step1Msg.textContent = 'Network error — proceeding';
      livenessApiResult = {
        success: true, passed: false, face_detected: false,
        anti_spoof_score: 0, liveness_score: 0,
        reason: 'Network error during liveness check.',
        face_quality_ok: false, face_quality_reason: '',
      };
    }

    if (!livenessApiResult.success) {
      step1Icon.innerHTML = iconWarn();
      step1Msg.textContent = livenessApiResult.error || 'Check failed — proceeding';
      livenessApiResult = {
        passed: false, face_detected: false,
        anti_spoof_score: 0, liveness_score: 0,
        reason: livenessApiResult.error,
      };
    }

    livenessData.face_detected = livenessApiResult.face_detected !== false;
    livenessData.anti_spoof_score = livenessApiResult.anti_spoof_score || 0;
    livenessData.liveness_score = livenessApiResult.liveness_score || 0;

    // Handle no-face-detected case with specific guidance
    if (!livenessData.face_detected) {
      step1Icon.innerHTML = iconX();
      step1Msg.textContent = livenessApiResult.reason || 'No face detected';
      faceBorder.style.borderColor = 'rgba(239,68,68,0.85)';
      showGuidance(buildFaceGuidance(livenessApiResult.reason || ''), 'warning');
      startBtn.style.display = '';
      startBtn.disabled = false;
      startBtn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i> Retry';
      return;
    }

    // Show face quality guidance
    if (livenessApiResult.face_quality_ok === false && livenessApiResult.face_quality_reason) {
      showGuidance(livenessApiResult.face_quality_reason, 'warning');
    }

    if (livenessApiResult.passed) {
      step1Icon.innerHTML = iconCheck();
      step1Msg.textContent = `Passed (${pct(livenessData.anti_spoof_score)}%)`;
      faceBorder.style.borderColor = 'rgba(34,197,94,0.85)';
    } else {
      step1Icon.innerHTML = iconWarn();
      step1Msg.textContent = `Low score (${pct(livenessData.anti_spoof_score)}%) — continuing`;
      faceBorder.style.borderColor = 'rgba(234,179,8,0.85)';
    }

    // Step 2: Head movement challenge
    step2Icon.innerHTML = iconSpinner();
    step2Msg.textContent = 'Follow the on-screen challenge&hellip;';
    challengeBox.style.display = '';
    challengeText.textContent = CHALLENGE_DISPLAY;

    if (mpAvailable) LivenessTracker.setBaseline();

    // Animate timer bar
    challengeTimer.style.width = '100%';
    challengeTimer.style.transition = 'none';
    await sleep(20);
    challengeTimer.style.transition = 'width 5s linear';
    challengeTimer.style.width = '0%';

    // Poll for movement (5 seconds, then auto-accept — accessibility for seniors)
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
          // Timeout: auto-accept — the challenge is an accessibility aid, not a hard gate
          challengeCompleted = true;
          clearInterval(iv);
          resolve();
        }
      }, 200);
    });

    livenessData.challenge_completed = challengeCompleted;
    challengeBox.style.display = 'none';
    clearGuidance();

    step2Icon.innerHTML = iconCheck();
    step2Msg.textContent = 'Challenge done';

    livenessData.passed = livenessApiResult.passed && challengeCompleted;

    // Show score bar
    livenessScoreBox.style.display = '';
    const sp = pct(livenessData.liveness_score);
    livenessScoreVal.textContent = `${sp}%`;
    livenessScoreBar.style.width = `${sp}%`;
    livenessScoreBar.className = `progress-bar ${sp >= 60 ? 'bg-success' : sp >= 30 ? 'bg-warning' : 'bg-danger'}`;

    // Show liveness summary
    if (livenessData.passed) {
      showLivenessCard(true, 'Liveness check passed.');
    } else {
      showLivenessCard(false,
        LIVENESS_REQUIRED
          ? 'Liveness check failed. Verification will be denied in strict mode.'
          : 'Liveness score low — proceeding with face matching (demo mode).'
      );
    }

    // Show verify button
    verifyBtn.style.display = '';
    if (!livenessData.passed && !LIVENESS_REQUIRED) {
      verifyBtn.innerHTML = '<i class="bi bi-shield-exclamation me-1"></i> Process Verification (Liveness Warning)';
      verifyBtn.className = 'btn btn-warning fw-semibold';
    } else {
      verifyBtn.innerHTML = '<i class="bi bi-shield-check me-1"></i> Process Verification';
      verifyBtn.className = 'btn btn-success fw-semibold';
    }
    startBtn.style.display = 'none';

    showGuidance('Hold still and look at the camera, then click Process Verification.', 'info');
  });

  // ── Verify Button ─────────────────────────────────────────────────────────────
  verifyBtn.addEventListener('click', async () => {
    verifyBtn.disabled = true;
    verifyBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Processing&hellip;';
    processingOverlay.style.display = '';
    clearGuidance();

    // Capture best-quality frame from a short burst
    const imageData = await captureFrameHighQuality(video, captureCanvas, 5, 80);
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
      processingOverlay.style.display = 'none';

      if (!result.success) {
        showStatus(result.error || 'Verification failed. Please try again.', 'danger');
        verifyBtn.disabled = false;
        verifyBtn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i> Retry';
        await restartCamera();
        return;
      }

      if (result.decision === 'retry') {
        currentChallenge = result.new_challenge || CHALLENGE;
        showRetryAlert(result.message, result.new_challenge_display, result.score, result.threshold);
        await restartCamera();
        verifyBtn.style.display = 'none';
        startBtn.style.display = '';
        startBtn.disabled = false;
        startBtn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i> Retry Verification';
        livenessData = { passed: false, anti_spoof_score: 0, liveness_score: 0,
                         face_detected: false, challenge_completed: false };
        showGuidance(result.message, 'warning');
        return;
      }

      window.location.href = result.redirect;

    } catch (err) {
      processingOverlay.style.display = 'none';
      showStatus(`Network error: ${err.message}`, 'danger');
      verifyBtn.disabled = false;
      verifyBtn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i> Retry';
      await restartCamera();
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
      return 'Face too small — move closer to the camera (30-50 cm away).';
    }
    if (r.includes('dark') || r.includes('lighting')) {
      return 'Too dark — face a light source or turn on more lights.';
    }
    if (r.includes('blur') || r.includes('still')) {
      return 'Image blurry — hold the device steady and hold still.';
    }
    return 'No face detected — center your face in the oval, look at the camera.';
  }

  function showGuidance(msg, type) {
    if (!guidancePanel) return;
    const icon = type === 'warning' ? 'exclamation-triangle-fill' : 'info-circle-fill';
    const colors = {
      info: 'background:#f0f9ff; border:1px solid #7dd3fc; color:#0c4a6e;',
      warning: 'background:#fff7ed; border:1px solid #fdba74; color:#7c2d12;',
      success: 'background:#f0fdf4; border:1px solid #86efac; color:#14532d;',
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

  // ── UI Helpers ───────────────────────────────────────────────────────────────
  function showLivenessCard(passed, msg) {
    livenessResultEl.style.display = '';
    livenessResultBody.innerHTML = passed
      ? `<div class="d-flex align-items-center gap-2 text-success"><i class="bi bi-check-circle-fill fs-5"></i><span>${msg}</span></div>`
      : `<div class="d-flex align-items-center gap-2 text-warning"><i class="bi bi-exclamation-triangle-fill fs-5"></i><span>${msg}</span></div>`;
  }

  function showRetryAlert(msg, newChallenge, score, threshold) {
    const el = document.createElement('div');
    el.className = 'alert alert-warning d-flex gap-2 align-items-start mt-3';
    const scoreText = (score !== null && score !== undefined)
      ? `Score: <strong>${score.toFixed(4)}</strong> (need &ge; ${threshold}).<br>` : '';
    el.innerHTML = `<i class="bi bi-arrow-repeat flex-shrink-0 mt-1"></i>
      <div><strong>Retry:</strong> ${msg}<br>${scoreText}
      ${newChallenge ? `New challenge: <strong>${newChallenge}</strong>` : ''}</div>`;
    const col = document.querySelector('.col-lg-5') || document.body;
    col.appendChild(el);
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
