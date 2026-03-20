/**
 * Liveness detection helpers using MediaPipe Face Mesh.
 * Tracks head pose to validate challenge completion (client-side).
 *
 * CHALLENGE_THRESHOLD_DEG = 12 degrees — matches SERVER_CHALLENGE_THRESHOLD_DEG
 * in verification/liveness.py. Senior-citizen friendly (accessible movement range).
 *
 * Loaded lazily — MediaPipe scripts are loaded from CDN in templates that need it.
 */

const LivenessTracker = (() => {
  let faceMesh = null;
  let initialPose = null;
  let challengeCompleted = false;
  let currentLandmarks = null;
  let _initialized = false;

  // Must match SERVER_CHALLENGE_THRESHOLD_DEG in verification/liveness.py
  const CHALLENGE_THRESHOLD_DEG = 12;

  function estimatePose(landmarks) {
    if (!landmarks || landmarks.length < 468) return { yaw: 0, pitch: 0 };
    const nose     = landmarks[1];
    const leftEye  = landmarks[33];
    const rightEye = landmarks[263];
    const chin     = landmarks[152];
    const forehead = landmarks[10];

    const eyeCenterX = (leftEye.x + rightEye.x) / 2;
    const yaw        = (nose.x - eyeCenterX) * 90;

    const faceCenterY = (forehead.y + chin.y) / 2;
    const pitch       = (nose.y - faceCenterY) * 90;

    return { yaw, pitch };
  }

  function checkChallenge(direction) {
    if (!initialPose || !currentLandmarks) return false;
    const current   = estimatePose(currentLandmarks);
    const yawDelta  = current.yaw - initialPose.yaw;
    const pitchDelta = current.pitch - initialPose.pitch;

    if (direction === 'left'  && yawDelta  < -CHALLENGE_THRESHOLD_DEG) return true;
    if (direction === 'right' && yawDelta  >  CHALLENGE_THRESHOLD_DEG) return true;
    if (direction === 'up'    && pitchDelta < -CHALLENGE_THRESHOLD_DEG) return true;
    if (direction === 'down'  && pitchDelta >  CHALLENGE_THRESHOLD_DEG) return true;
    return false;
  }

  async function init(videoEl, onResults) {
    if (typeof FaceMesh === 'undefined') {
      console.warn('FANS-C: MediaPipe FaceMesh not loaded. Head tracking unavailable — challenge will auto-accept after timer.');
      return false;
    }
    try {
      faceMesh = new FaceMesh({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`,
      });
      faceMesh.setOptions({
        maxNumFaces: 1,
        refineLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5,
      });
      faceMesh.onResults((results) => {
        if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
          currentLandmarks = results.multiFaceLandmarks[0];
          if (onResults) onResults(currentLandmarks);
        } else {
          currentLandmarks = null;
        }
      });

      const camera = new Camera(videoEl, {
        onFrame: async () => {
          if (faceMesh) await faceMesh.send({ image: videoEl });
        },
        width: 480,
        height: 360,
      });
      await camera.start();
      _initialized = true;
      return true;
    } catch (err) {
      console.warn('FANS-C: MediaPipe init failed:', err);
      return false;
    }
  }

  function setBaseline() {
    if (currentLandmarks) {
      initialPose = estimatePose(currentLandmarks);
      return true;
    }
    // No landmarks yet — set a neutral baseline so challenge can still proceed
    initialPose = { yaw: 0, pitch: 0 };
    return false;
  }

  function reset() {
    initialPose = null;
    challengeCompleted = false;
    currentLandmarks = null;
  }

  function getCurrentPose() {
    return currentLandmarks ? estimatePose(currentLandmarks) : null;
  }

  return { init, setBaseline, checkChallenge, reset, getCurrentPose };
})();
