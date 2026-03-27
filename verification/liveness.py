"""
Liveness detection module — FANS-C.

Two-layer approach
───────────────────
1. Anti-spoofing (server-side, always runs)
   Texture analysis on the captured face image: Laplacian variance, local variance
   (LBP proxy), and Sobel edge density. Returns a score in [0, 1]. Scores below the
   ANTI_SPOOF_THRESHOLD (default 0.15) are flagged as suspicious. This runs on every
   attempt and is always logged, regardless of whether the visible challenge is shown.

   NOTE: This is a heuristic suitable for webcam captures. For higher-security
   deployments, replace compute_texture_score() with a trained CNN anti-spoofing model
   (e.g. Silent-Face-Anti-Spoofing) for proper Presentation Attack Detection (PAD).

2. Head movement challenge (client-side, risk-triggered)
   The user is asked to tilt their head in a random direction (left/right/up/down).
   Pose estimation uses MediaPipe Face Mesh in the browser (static/js/liveness.js).
   The server receives challenge_completed=True/False; it trusts the client report
   because the challenge is a usability/accessibility layer, not the primary security gate.

   In the risk-based flow, this challenge is only shown when a risk condition is detected
   (low anti-spoof score, poor image quality, representative claim, or retry attempt).
   The 5-second auto-accept timer ensures the challenge is accessible for senior citizens
   who may have limited range of motion.

Operating modes
────────────────
Assisted Rollout Mode (LIVENESS_REQUIRED=False, the default):
  Liveness result is recorded in the VerificationAttempt but does NOT block face matching.
  Use this during initial deployment to calibrate thresholds against real-world captures.

Strict Mode (LIVENESS_REQUIRED=True):
  A failed liveness check immediately denies the attempt before face matching runs.

Server-side threshold: 12 degrees (must match CHALLENGE_THRESHOLD_DEG in liveness.js).
Combined liveness score formula: 0.6 × anti_spoof_score + 0.4 × challenge_completed.
"""
import numpy as np
import cv2


# ─── Anti-Spoofing ────────────────────────────────────────────────────────────

def compute_texture_score(face_img: np.ndarray) -> float:
    """
    Liveness score based on combined texture analysis.

    Uses:
      - Laplacian variance: real faces have higher focus variance than prints/screens
      - Local variance (LBP proxy): real faces have more micro-texture
      - Edge density via Sobel: printed photos tend to have smoother gradients

    Returns float in [0, 1] — higher = more likely real.

    NOTE: This heuristic is intentionally lenient for webcam/browser captures.
    For production deployment, replace with a trained CNN (Silent-Face-Anti-Spoofing
    or similar) for proper PAD (Presentation Attack Detection).
    """
    if face_img is None or face_img.size == 0:
        return 0.0

    gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)

    # Laplacian variance — screens/prints tend to have lower focus variance
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    # Local variance (LBP proxy)
    kernel = np.ones((5, 5), np.float32) / 25
    local_mean = cv2.filter2D(gray.astype(np.float32), -1, kernel)
    local_variance = cv2.filter2D((gray.astype(np.float32) - local_mean) ** 2, -1, kernel)
    lbp_score = local_variance.mean()

    # Edge density via Sobel — real faces have more natural edge distribution
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    edge_mag = np.sqrt(sobel_x ** 2 + sobel_y ** 2)
    edge_density = float(np.mean(edge_mag > 10))  # fraction of "edge" pixels

    # Normalize — tuned for typical browser/webcam captures.
    # lap_var for a real webcam face is usually 50-300; normalize against 300.
    lap_normalized = min(lap_var / 300.0, 1.0)
    lbp_normalized = min(lbp_score / 150.0, 1.0)
    edge_normalized = min(edge_density / 0.25, 1.0)

    score = 0.50 * lap_normalized + 0.30 * lbp_normalized + 0.20 * edge_normalized
    return float(np.clip(score, 0.0, 1.0))


def check_anti_spoofing(face_img: np.ndarray, threshold: float = 0.15) -> dict:
    """
    Run anti-spoofing check on a face image.

    Args:
        threshold: minimum score to pass (0.15 is permissive for webcam captures).
          Raise to 0.30+ with a trained CNN model in production.

    Returns:
        {'passed': bool, 'score': float, 'reason': str}
    """
    score = compute_texture_score(face_img)
    passed = score >= threshold
    return {
        'passed': passed,
        'score': score,
        'reason': (
            'Real face detected.'
            if passed
            else f'Low texture score ({score:.3f}); possible spoofing or very low quality image.'
        ),
    }


# ─── Head Movement Challenge ──────────────────────────────────────────────────

CHALLENGE_DIRECTIONS = ['left', 'right', 'up', 'down']

# Server-side head pose threshold in degrees.
# Must match CHALLENGE_THRESHOLD_DEG in static/js/liveness.js (12 degrees).
SERVER_CHALLENGE_THRESHOLD_DEG = 12.0


def get_random_challenge() -> str:
    import random
    return random.choice(CHALLENGE_DIRECTIONS)


def analyze_head_pose(landmarks_json: list) -> dict:
    """
    Analyze head pose from MediaPipe face landmarks.
    `landmarks_json` is a list of {x, y, z} dicts from the client.
    """
    if not landmarks_json or len(landmarks_json) < 468:
        return {'yaw': 0.0, 'pitch': 0.0}

    nose = landmarks_json[1]
    left_eye = landmarks_json[33]
    right_eye = landmarks_json[263]
    chin = landmarks_json[152]
    forehead = landmarks_json[10]

    eye_center_x = (left_eye['x'] + right_eye['x']) / 2
    yaw = (nose['x'] - eye_center_x) * 90

    face_center_y = (forehead['y'] + chin['y']) / 2
    pitch = (nose['y'] - face_center_y) * 90

    return {'yaw': float(yaw), 'pitch': float(pitch)}


def validate_movement(
    initial_pose: dict,
    current_pose: dict,
    required_direction: str,
    threshold_deg: float = SERVER_CHALLENGE_THRESHOLD_DEG,
) -> dict:
    """
    Check whether the user moved their head in the required direction.
    threshold_deg = 12 matches the client-side CHALLENGE_THRESHOLD_DEG in liveness.js.
    Accessible for senior citizens who may have limited range of motion.
    """
    yaw_delta = current_pose['yaw'] - initial_pose['yaw']
    pitch_delta = current_pose['pitch'] - initial_pose['pitch']

    if required_direction == 'left' and yaw_delta < -threshold_deg:
        return {'completed': True, 'reason': 'Turned left.'}
    elif required_direction == 'right' and yaw_delta > threshold_deg:
        return {'completed': True, 'reason': 'Turned right.'}
    elif required_direction == 'up' and pitch_delta < -threshold_deg:
        return {'completed': True, 'reason': 'Tilted up.'}
    elif required_direction == 'down' and pitch_delta > threshold_deg:
        return {'completed': True, 'reason': 'Tilted down.'}
    else:
        return {
            'completed': False,
            'reason': f'Movement not detected for direction: {required_direction}.',
        }


# ─── Full Liveness Check ──────────────────────────────────────────────────────

def run_full_liveness_check(
    face_img: np.ndarray,
    challenge_completed: bool,
    anti_spoof_threshold: float = 0.15,
) -> dict:
    """
    Combined liveness check: anti-spoofing texture analysis + head movement challenge.

    Design:
    - Anti-spoofing and head movement are evaluated independently.
    - A combined liveness_score is computed from both.
    - 'passed' = True only if BOTH anti-spoofing AND challenge are satisfied.
    - If anti-spoofing fails but challenge was completed, liveness_score is still
      returned (not zeroed) so the UI can show partial results clearly.

    Returns:
        {
            'passed': bool,
            'anti_spoof_score': float,
            'challenge_completed': bool,
            'liveness_score': float,   # combined 0-1 score
            'reason': str,
        }
    """
    spoof_result = check_anti_spoofing(face_img, threshold=anti_spoof_threshold)
    anti_spoof_score = spoof_result['score']
    spoof_passed = spoof_result['passed']

    # Combined score: weight anti-spoof more heavily (0.6) than movement (0.4)
    # challenge_completed is boolean from client; treat True=1.0, False=0.0
    challenge_score = 1.0 if challenge_completed else 0.0
    liveness_score = float(0.6 * anti_spoof_score + 0.4 * challenge_score)

    overall_passed = spoof_passed and challenge_completed

    if not spoof_passed and not challenge_completed:
        reason = f'Liveness failed: {spoof_result["reason"]} Head movement challenge not completed.'
    elif not spoof_passed:
        reason = f'Anti-spoofing failed: {spoof_result["reason"]}'
    elif not challenge_completed:
        reason = 'Head movement challenge not completed.'
    else:
        reason = 'Liveness check passed.'

    return {
        'passed': overall_passed,
        'anti_spoof_score': anti_spoof_score,
        'challenge_completed': challenge_completed,
        'liveness_score': liveness_score,
        'reason': reason,
    }
