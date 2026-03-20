"""
Liveness detection module.

Two-layer approach:
1. Anti-spoofing: texture/frequency analysis to detect printed photos or screens.
2. Head movement challenge: user performs a random movement verified via MediaPipe.

In dev/demo mode (LIVENESS_REQUIRED=False in settings), liveness failure is
recorded but does NOT block face matching. Set LIVENESS_REQUIRED=True for strict
production enforcement.
"""
import numpy as np
import cv2


# ─── Anti-Spoofing ────────────────────────────────────────────────────────────

def compute_texture_score(face_img: np.ndarray) -> float:
    """
    Liveness score based on texture analysis.
    Uses Laplacian variance (focus measure) and local variance (LBP proxy).
    Returns float in [0, 1] — higher = more likely real.

    NOTE: This heuristic is intentionally lenient for webcam/browser captures.
    For production, replace with a trained CNN (e.g., Silent-Face-Anti-Spoofing).
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

    # Normalize — tuned for typical browser/webcam captures.
    # lap_var for a real webcam face is usually 50-300; normalize against 300.
    lap_normalized = min(lap_var / 300.0, 1.0)
    lbp_normalized = min(lbp_score / 150.0, 1.0)

    score = 0.6 * lap_normalized + 0.4 * lbp_normalized
    return float(np.clip(score, 0.0, 1.0))


def check_anti_spoofing(face_img: np.ndarray, threshold: float = 0.15) -> dict:
    """
    Run anti-spoofing check on a face image.

    Args:
        threshold: minimum score to pass (0.15 is permissive for webcam captures).

    Returns:
        {'passed': bool, 'score': float, 'reason': str}
    """
    score = compute_texture_score(face_img)
    passed = score >= threshold
    return {
        'passed': passed,
        'score': score,
        'reason': 'Real face detected.' if passed else f'Low texture score ({score:.3f}); possible spoofing.',
    }


# ─── Head Movement Challenge ──────────────────────────────────────────────────

CHALLENGE_DIRECTIONS = ['left', 'right', 'up', 'down']


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
    threshold_deg: float = 12.0,
) -> dict:
    """
    Check whether the user moved their head in the required direction.
    threshold_deg lowered to 12 for accessibility (senior citizens).
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
    Combined liveness check: anti-spoofing + head movement.

    Returns:
        {
            'passed': bool,
            'anti_spoof_score': float,
            'liveness_score': float,
            'reason': str,
        }
    """
    spoof_result = check_anti_spoofing(face_img, threshold=anti_spoof_threshold)

    if not spoof_result['passed']:
        return {
            'passed': False,
            'anti_spoof_score': spoof_result['score'],
            'liveness_score': spoof_result['score'],
            'reason': f'Anti-spoofing: {spoof_result["reason"]}',
        }

    if not challenge_completed:
        return {
            'passed': False,
            'anti_spoof_score': spoof_result['score'],
            'liveness_score': spoof_result['score'] * 0.6,
            'reason': 'Head movement challenge not completed.',
        }

    return {
        'passed': True,
        'anti_spoof_score': spoof_result['score'],
        'liveness_score': spoof_result['score'],
        'reason': 'Liveness check passed.',
    }
