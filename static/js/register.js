/**
 * Registration face capture logic.
 */
document.addEventListener('DOMContentLoaded', async () => {
  const video = document.getElementById('video');
  const captureCanvas = document.getElementById('captureCanvas');
  const captureBtn = document.getElementById('captureBtn');
  const retakeBtn = document.getElementById('retakeBtn');
  const submitBtn = document.getElementById('submitBtn');
  const statusMsg = document.getElementById('statusMsg');
  const capturedPreview = document.getElementById('capturedPreview');
  const previewImg = document.getElementById('previewImg');
  const processingSpinner = document.getElementById('processingSpinner');

  let capturedImageData = null;

  // Start camera
  statusMsg.className = 'alert alert-info mb-3';
  statusMsg.innerHTML = '<i class="bi bi-hourglass-split me-1"></i> Starting camera...';

  const camResult = await startCamera(video);
  if (!camResult.success) {
    statusMsg.className = 'alert alert-danger mb-3';
    statusMsg.innerHTML = `<i class="bi bi-camera-video-off me-1"></i> Camera error: ${camResult.error}`;
    return;
  }

  video.addEventListener('play', () => {
    statusMsg.className = 'alert alert-success mb-3';
    statusMsg.innerHTML = '<i class="bi bi-check-circle me-1"></i> Camera ready. Position face in the frame and click Capture.';
    captureBtn.disabled = false;
  });

  captureBtn.addEventListener('click', () => {
    capturedImageData = captureFrame(video, captureCanvas);
    previewImg.src = capturedImageData;
    capturedPreview.style.display = '';
    captureBtn.style.display = 'none';
    retakeBtn.style.display = '';
    submitBtn.style.display = '';
    statusMsg.className = 'alert alert-info mb-3';
    statusMsg.innerHTML = '<i class="bi bi-check me-1"></i> Image captured. Click Submit to register, or Retake to try again.';
  });

  retakeBtn.addEventListener('click', () => {
    capturedImageData = null;
    capturedPreview.style.display = 'none';
    captureBtn.style.display = '';
    retakeBtn.style.display = 'none';
    submitBtn.style.display = 'none';
    statusMsg.className = 'alert alert-success mb-3';
    statusMsg.innerHTML = '<i class="bi bi-camera me-1"></i> Ready. Position your face and click Capture.';
  });

  submitBtn.addEventListener('click', async () => {
    if (!capturedImageData) return;

    submitBtn.disabled = true;
    retakeBtn.disabled = true;
    processingSpinner.style.display = '';
    statusMsg.className = 'alert alert-info mb-3';
    statusMsg.innerHTML = '<i class="bi bi-hourglass-split me-1"></i> Processing face embedding...';

    try {
      const result = await postJSON(SUBMIT_URL, { image: capturedImageData }, CSRF_TOKEN);
      if (result.success) {
        stopCamera();
        statusMsg.className = 'alert alert-success mb-3';
        statusMsg.innerHTML = `<i class="bi bi-check-circle me-1"></i> ${result.message}`;
        processingSpinner.style.display = 'none';
        setTimeout(() => { window.location.href = result.redirect; }, 1500);
      } else {
        statusMsg.className = 'alert alert-danger mb-3';
        statusMsg.innerHTML = `<i class="bi bi-x-circle me-1"></i> Error: ${result.error}`;
        processingSpinner.style.display = 'none';
        submitBtn.disabled = false;
        retakeBtn.disabled = false;
      }
    } catch (err) {
      statusMsg.className = 'alert alert-danger mb-3';
      statusMsg.innerHTML = `<i class="bi bi-x-circle me-1"></i> Network error: ${err.message}`;
      processingSpinner.style.display = 'none';
      submitBtn.disabled = false;
      retakeBtn.disabled = false;
    }
  });
});
