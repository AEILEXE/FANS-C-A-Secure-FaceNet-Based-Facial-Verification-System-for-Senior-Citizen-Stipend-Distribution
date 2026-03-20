/**
 * Registration face capture logic — FANS-C.
 *
 * Uses captureFrameHighQuality() to select the sharpest frame from a
 * 7-frame burst. This improves embedding quality significantly compared
 * to capturing a single arbitrary frame.
 */
document.addEventListener('DOMContentLoaded', async () => {
  const video           = document.getElementById('video');
  const captureCanvas   = document.getElementById('captureCanvas');
  const captureBtn      = document.getElementById('captureBtn');
  const retakeBtn       = document.getElementById('retakeBtn');
  const submitBtn       = document.getElementById('submitBtn');
  const statusMsg       = document.getElementById('statusMsg');
  const capturedPreview = document.getElementById('capturedPreview');
  const previewImg      = document.getElementById('previewImg');
  const processingSpinner = document.getElementById('processingSpinner');
  const qualityHint     = document.getElementById('qualityHint');

  let capturedImageData = null;

  // Start camera
  statusMsg.className = 'alert alert-info mb-3';
  statusMsg.innerHTML = '<i class="bi bi-hourglass-split me-1"></i> Starting camera\u2026';

  const camResult = await startCamera(video);
  if (!camResult.success) {
    statusMsg.className = 'alert alert-danger mb-3';
    statusMsg.innerHTML = `<i class="bi bi-camera-video-off me-1"></i> Camera error: ${camResult.error}`;
    if (captureBtn) captureBtn.disabled = true;
    return;
  }

  // Wait for video to start playing
  await new Promise((resolve) => {
    video.addEventListener('play', resolve, { once: true });
    setTimeout(resolve, 1500);
  });

  statusMsg.className = 'alert alert-success mb-3';
  statusMsg.innerHTML = '<i class="bi bi-check-circle me-1"></i> Camera ready. Position face in the oval and click Capture.';
  if (captureBtn) captureBtn.disabled = false;

  captureBtn.addEventListener('click', async () => {
    captureBtn.disabled = true;
    statusMsg.className = 'alert alert-info mb-3';
    statusMsg.innerHTML = '<i class="bi bi-hourglass-split me-1"></i> Capturing best frame\u2026';

    // Capture sharpest frame from a 7-frame burst
    capturedImageData = await captureFrameHighQuality(video, captureCanvas, 7, 70);

    previewImg.src = capturedImageData;
    capturedPreview.style.display = '';
    captureBtn.style.display = 'none';
    retakeBtn.style.display = '';
    submitBtn.style.display = '';

    statusMsg.className = 'alert alert-info mb-3';
    statusMsg.innerHTML = '<i class="bi bi-eye me-1"></i> Check the preview. If the face is clear and centered, click Submit. Otherwise, click Retake.';

    if (qualityHint) {
      qualityHint.style.display = '';
    }
  });

  retakeBtn.addEventListener('click', () => {
    capturedImageData = null;
    capturedPreview.style.display = 'none';
    captureBtn.style.display = '';
    captureBtn.disabled = false;
    retakeBtn.style.display = 'none';
    submitBtn.style.display = 'none';
    if (qualityHint) qualityHint.style.display = 'none';
    statusMsg.className = 'alert alert-success mb-3';
    statusMsg.innerHTML = '<i class="bi bi-camera me-1"></i> Ready. Position your face and click Capture.';
  });

  submitBtn.addEventListener('click', async () => {
    if (!capturedImageData) return;

    submitBtn.disabled = true;
    retakeBtn.disabled = true;
    if (processingSpinner) processingSpinner.style.display = '';
    statusMsg.className = 'alert alert-info mb-3';
    statusMsg.innerHTML = '<i class="bi bi-hourglass-split me-1"></i> Processing face embedding\u2026 Please wait.';

    try {
      const result = await postJSON(SUBMIT_URL, { image: capturedImageData }, CSRF_TOKEN);
      if (result.success) {
        stopCamera();
        statusMsg.className = 'alert alert-success mb-3';
        statusMsg.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i> ${result.message}`;
        if (processingSpinner) processingSpinner.style.display = 'none';
        setTimeout(() => { window.location.href = result.redirect; }, 1500);
      } else {
        statusMsg.className = 'alert alert-danger mb-3';
        statusMsg.innerHTML = `<i class="bi bi-x-circle me-1"></i> ${result.error}`;
        if (processingSpinner) processingSpinner.style.display = 'none';
        submitBtn.disabled = false;
        retakeBtn.disabled = false;
      }
    } catch (err) {
      statusMsg.className = 'alert alert-danger mb-3';
      statusMsg.innerHTML = `<i class="bi bi-x-circle me-1"></i> Network error: ${err.message}`;
      if (processingSpinner) processingSpinner.style.display = 'none';
      submitBtn.disabled = false;
      retakeBtn.disabled = false;
    }
  });
});
