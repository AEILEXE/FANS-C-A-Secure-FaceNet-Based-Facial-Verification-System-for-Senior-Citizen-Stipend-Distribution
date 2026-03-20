/**
 * Shared webcam utility for FANS.
 * Provides startCamera(), captureFrame(), stopCamera(), captureFrameHighQuality().
 *
 * Camera is requested at 640x480 for better face quality.
 * captureFrameHighQuality() takes multiple frames and picks the sharpest.
 */

let _stream = null;

async function startCamera(videoEl) {
  try {
    // Prefer 640x480; fall back to any resolution
    const constraints = {
      video: {
        width: { ideal: 640, min: 320 },
        height: { ideal: 480, min: 240 },
        facingMode: 'user',
        frameRate: { ideal: 30, min: 15 },
      },
      audio: false,
    };
    _stream = await navigator.mediaDevices.getUserMedia(constraints);
    videoEl.srcObject = _stream;
    // Wait for video to be ready
    await new Promise((resolve) => {
      videoEl.onloadedmetadata = () => resolve();
      setTimeout(resolve, 2000); // fallback
    });
    return { success: true };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

/**
 * Capture a single frame from the video element.
 * Un-mirrors the feed so the captured image matches real-world face orientation.
 */
function captureFrame(videoEl, canvasEl, width, height) {
  const w = width || videoEl.videoWidth || 480;
  const h = height || videoEl.videoHeight || 360;
  canvasEl.width = w;
  canvasEl.height = h;
  const ctx = canvasEl.getContext('2d');
  // Un-mirror: video CSS has scaleX(-1), so draw without mirroring for correct orientation
  ctx.drawImage(videoEl, 0, 0, w, h);
  return canvasEl.toDataURL('image/jpeg', 0.92);
}

/**
 * Capture the best-quality frame from a short burst.
 * Estimates sharpness via pixel variance on a downsampled version.
 * Returns the sharpest frame's data URL.
 */
async function captureFrameHighQuality(videoEl, canvasEl, frames = 5, delayMs = 80) {
  const w = videoEl.videoWidth || 480;
  const h = videoEl.videoHeight || 360;
  const tmpCanvas = document.createElement('canvas');
  const tmpCtx = tmpCanvas.getContext('2d');
  tmpCanvas.width = w;
  tmpCanvas.height = h;

  let bestFrame = null;
  let bestSharpness = -1;

  for (let i = 0; i < frames; i++) {
    tmpCanvas.width = w;
    tmpCanvas.height = h;
    tmpCtx.drawImage(videoEl, 0, 0, w, h);
    const dataUrl = tmpCanvas.toDataURL('image/jpeg', 0.92);
    const sharpness = estimateSharpness(tmpCtx, w, h);
    if (sharpness > bestSharpness) {
      bestSharpness = sharpness;
      bestFrame = dataUrl;
    }
    if (i < frames - 1) {
      await new Promise(r => setTimeout(r, delayMs));
    }
  }

  // Write the best frame into the shared canvas (for consistent dimensions)
  canvasEl.width = w;
  canvasEl.height = h;
  return bestFrame || captureFrame(videoEl, canvasEl, w, h);
}

/**
 * Estimate sharpness of the current canvas content via pixel variance.
 * Higher = sharper. Only samples a small region for speed.
 */
function estimateSharpness(ctx, w, h) {
  const sampleW = Math.min(w, 160);
  const sampleH = Math.min(h, 120);
  const sx = Math.floor((w - sampleW) / 2);
  const sy = Math.floor((h - sampleH) / 2);
  try {
    const imageData = ctx.getImageData(sx, sy, sampleW, sampleH);
    const d = imageData.data;
    let sum = 0, sumSq = 0, n = 0;
    for (let i = 0; i < d.length; i += 4) {
      const lum = 0.299 * d[i] + 0.587 * d[i+1] + 0.114 * d[i+2];
      sum += lum;
      sumSq += lum * lum;
      n++;
    }
    const mean = sum / n;
    return sumSq / n - mean * mean; // variance = sharpness proxy
  } catch (e) {
    return 0;
  }
}

function stopCamera() {
  if (_stream) {
    _stream.getTracks().forEach(t => t.stop());
    _stream = null;
  }
}

async function postJSON(url, data, csrfToken) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    body: JSON.stringify(data),
  });
  return res.json();
}
