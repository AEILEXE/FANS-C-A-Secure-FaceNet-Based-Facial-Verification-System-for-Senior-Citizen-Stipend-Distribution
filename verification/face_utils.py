"""
Face processing utilities: RetinaFace detection + alignment, FaceNet embeddings,
embedding encryption/decryption.

Key design decisions:
- _align_face_similarity uses a 4-DOF similarity transform (rotation+scale+translation)
  mapping detected eye landmarks to canonical positions in a 160x160 output. This is the
  standard MTCNN/FaceNet pre-processing and ensures consistent crops regardless of face
  distance, head tilt, or camera resolution.
- get_embedding converts BGR->RGB, applies CLAHE for contrast normalisation, resizes to
  160x160, and lets keras-facenet apply its own per-image whitening (prewhiten). We also
  L2-normalize the output.
- Preprocessing is identical for registration and verification, ensuring comparable embeddings.
- CLAHE (Contrast Limited Adaptive Histogram Equalization) is applied to the L channel in
  LAB colour space before FaceNet input. This significantly improves accuracy for low-light
  webcam captures, dark skin tones, and poorly lit barangay offices.
"""
import io
import os
import numpy as np
import base64
import json
from django.conf import settings


# ─── Encryption ──────────────────────────────────────────────────────────────

def get_fernet():
    from cryptography.fernet import Fernet
    key = settings.EMBEDDING_ENCRYPTION_KEY
    if not key:
        import warnings
        warnings.warn(
            'EMBEDDING_ENCRYPTION_KEY not set. Generating a temporary key. '
            'Set this in .env for production!',
            RuntimeWarning
        )
        key = Fernet.generate_key().decode()
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_embedding(embedding: np.ndarray) -> bytes:
    fernet = get_fernet()
    embedding_json = json.dumps(embedding.tolist())
    return fernet.encrypt(embedding_json.encode())


def decrypt_embedding(encrypted_data: bytes) -> np.ndarray:
    fernet = get_fernet()
    if isinstance(encrypted_data, memoryview):
        encrypted_data = bytes(encrypted_data)
    decrypted = fernet.decrypt(encrypted_data)
    return np.array(json.loads(decrypted.decode()), dtype=np.float32)


# ─── Image Loading ────────────────────────────────────────────────────────────

def load_image_from_bytes(image_bytes: bytes) -> np.ndarray:
    import cv2
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError('Failed to decode image.')
    return img


def load_image_from_base64(b64_string: str) -> np.ndarray:
    if ',' in b64_string:
        b64_string = b64_string.split(',')[1]
    image_bytes = base64.b64decode(b64_string)
    return load_image_from_bytes(image_bytes)


# ─── CLAHE Preprocessing ─────────────────────────────────────────────────────

def _apply_clahe(img: np.ndarray) -> np.ndarray:
    """
    Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to improve
    contrast in the face image before FaceNet embedding.

    Operates on the L channel of LAB colour space to avoid distorting hue/saturation.
    This substantially improves recognition accuracy for:
      - Low-light barangay office environments
      - Webcams with poor auto-exposure
      - Users with darker skin tones

    clipLimit=2.0 is conservative — enough to lift shadows without over-sharpening.
    """
    import cv2
    try:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l_ch)
        lab_enhanced = cv2.merge([l_enhanced, a_ch, b_ch])
        return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
    except Exception:
        return img  # fallback: return original if CLAHE fails


# ─── Face Detection (RetinaFace / MTCNN / OpenCV cascade) ────────────────────

_mtcnn_detector = None  # cached MTCNN instance (lazy init, thread-safe enough for Django dev)


def _get_mtcnn():
    global _mtcnn_detector
    if _mtcnn_detector is None:
        from mtcnn import MTCNN
        _mtcnn_detector = MTCNN()
    return _mtcnn_detector


def _detect_face_mtcnn(img: np.ndarray) -> np.ndarray:
    """
    Detect face with MTCNN and return an aligned 160x160 crop.

    MTCNN provides 5-point landmarks (left_eye, right_eye, nose, mouth_left,
    mouth_right).  We feed the eye positions into _align_face_similarity() for
    the same 4-DOF similarity transform used by the RetinaFace path, giving
    rotation- and scale-normalised crops that are directly comparable across
    registration and verification sessions.

    Falls back to the OpenCV Haar cascade if MTCNN fails or is not installed.
    """
    import cv2
    try:
        detector = _get_mtcnn()
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        detections = detector.detect_faces(img_rgb)
    except Exception:
        return _detect_face_opencv(img)

    if not detections:
        raise ValueError(
            'No face detected. Center your face in the frame and ensure good lighting.'
        )

    # Best detection by confidence
    best = max(detections, key=lambda d: d.get('confidence', 0))
    if best.get('confidence', 0) < 0.85:
        raise ValueError(
            f"Face detection confidence too low ({best.get('confidence', 0):.2f}). "
            'Move closer to the camera or improve lighting.'
        )

    kp = best.get('keypoints', {})
    if 'left_eye' in kp and 'right_eye' in kp:
        left_eye  = np.array(kp['left_eye'],  dtype=np.float32)
        right_eye = np.array(kp['right_eye'], dtype=np.float32)

        inter_eye_dist = float(np.linalg.norm(right_eye - left_eye))
        if inter_eye_dist < 15:
            raise ValueError(
                f'Face too small (eye distance {inter_eye_dist:.0f}px). '
                'Move closer to the camera.'
            )

        return _align_face_similarity(img, left_eye, right_eye, output_size=(160, 160))

    # Fallback: bounding box only (no landmarks)
    x, y, w, h = best['box']
    x, y = max(0, x), max(0, y)
    x2, y2 = min(img.shape[1], x + w), min(img.shape[0], y + h)
    face_crop = img[y:y2, x:x2]
    if face_crop.size == 0:
        raise ValueError('Face bounding box is empty.')
    return cv2.resize(face_crop, (160, 160))


def detect_and_align_face(img: np.ndarray) -> np.ndarray:
    """
    Detect face and return a 160x160 aligned face crop.

    Detection priority:
      1. RetinaFace  (best accuracy, requires optional retinaface package)
      2. MTCNN       (installed by default — provides eye landmarks for alignment)
      3. OpenCV Haar (last resort — bounding box only, no alignment)

    Steps 1 and 2 both use _align_face_similarity() for consistent 4-DOF
    similarity-transform crops regardless of head tilt or camera distance.
    This is the primary reason false-rejects occur when OpenCV is used:
    unaligned crops vary between registration and verification sessions,
    lowering cosine similarity even for the same person.

    Raises ValueError with a user-friendly message if no face is found.
    """
    try:
        from retinaface import RetinaFace
        faces = RetinaFace.detect_faces(img)
    except ImportError:
        return _detect_face_mtcnn(img)

    if not faces or isinstance(faces, tuple):
        raise ValueError(
            'No face detected. Center your face in the frame and ensure good lighting.'
        )

    # Pick the face with the highest confidence score
    best_key = max(faces, key=lambda k: faces[k].get('score', 0))
    face_data = faces[best_key]
    score = face_data.get('score', 0)

    if score < 0.5:
        raise ValueError(
            f'Face detection confidence too low ({score:.2f}). '
            'Move closer to the camera or improve lighting.'
        )

    landmarks = face_data.get('landmarks', {})
    facial_area = face_data.get('facial_area', [])

    if landmarks and 'left_eye' in landmarks and 'right_eye' in landmarks:
        left_eye = np.array(landmarks['left_eye'], dtype=np.float32)
        right_eye = np.array(landmarks['right_eye'], dtype=np.float32)

        # Validate face size — too small means too far from camera.
        # Lowered from 20 to 15 to be more forgiving at normal desk distance.
        inter_eye_dist = float(np.linalg.norm(right_eye - left_eye))
        if inter_eye_dist < 15:
            raise ValueError(
                f'Face too small (eye distance {inter_eye_dist:.0f}px). '
                'Move closer to the camera.'
            )

        face_crop = _align_face_similarity(img, left_eye, right_eye, output_size=(160, 160))
    elif facial_area:
        # Fallback: use bounding box without alignment
        x1, y1, x2, y2 = facial_area
        h, w = img.shape[:2]
        pad = int((x2 - x1) * 0.15)
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)
        face_crop = img[y1:y2, x1:x2]
        if face_crop.size == 0:
            raise ValueError('Face crop area is empty.')
        import cv2
        face_crop = cv2.resize(face_crop, (160, 160))
    else:
        raise ValueError('Face detected but landmarks/area unavailable.')

    return face_crop


def _align_face_similarity(
    img: np.ndarray,
    left_eye: np.ndarray,
    right_eye: np.ndarray,
    output_size=(160, 160),
) -> np.ndarray:
    """
    Align face using a 4-DOF similarity transform (rotation + uniform scale + translation).
    Maps the detected left_eye and right_eye to canonical positions in output_size.

    Canonical positions (FaceNet/MTCNN standard for 160x160):
      left_eye  -> (38.29, 51.70)
      right_eye -> (73.53, 51.50)

    The transform is computed analytically from 2 point pairs and is exact.
    """
    import cv2

    # Canonical target positions in the 160x160 output
    dst_left  = np.array([38.29, 51.70], dtype=np.float64)
    dst_right = np.array([73.53, 51.50], dtype=np.float64)

    src = np.array([left_eye, right_eye], dtype=np.float64)
    dst = np.array([dst_left, dst_right], dtype=np.float64)

    # Compute similarity transform analytically from 2 point pairs
    # Transform: [x'] = [a -b] [x] + [tx]
    #            [y']   [b  a] [y]   [ty]
    src_vec = src[1] - src[0]        # source eye-to-eye vector
    dst_vec = dst[1] - dst[0]        # destination eye-to-eye vector
    src_len_sq = float(np.dot(src_vec, src_vec))

    if src_len_sq < 1e-6:
        raise ValueError('Eye landmarks are at the same position — cannot align.')

    a = float(np.dot(src_vec, dst_vec)) / src_len_sq
    b = float(src_vec[0] * dst_vec[1] - src_vec[1] * dst_vec[0]) / src_len_sq

    tx = dst[0][0] - (a * src[0][0] - b * src[0][1])
    ty = dst[0][1] - (b * src[0][0] + a * src[0][1])

    M = np.array([[a, -b, tx],
                  [b,  a, ty]], dtype=np.float32)

    aligned = cv2.warpAffine(
        img, M, output_size,
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    return aligned


def _detect_face_opencv(img: np.ndarray) -> np.ndarray:
    """Fallback face detector using OpenCV Haar cascade."""
    import cv2
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
    )
    if len(faces) == 0:
        raise ValueError(
            'No face detected. Center your face and ensure adequate lighting.'
        )
    # Use the largest detected face
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    pad = int(w * 0.10)
    img_h, img_w = img.shape[:2]
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(img_w, x + w + pad)
    y2 = min(img_h, y + h + pad)
    face_crop = img[y1:y2, x1:x2]
    face_crop = cv2.resize(face_crop, (160, 160))
    return face_crop


# ─── Face Quality Check ───────────────────────────────────────────────────────

def check_face_quality(face_img: np.ndarray) -> dict:
    """
    Assess face crop quality. Returns a dict with 'ok', 'score', and 'reason'.
    A low-quality crop will produce unreliable FaceNet embeddings.

    Checks:
      - Sharpness via Laplacian variance (blur detection)
      - Brightness (underexposure / overexposure)
      - Contrast via standard deviation of grayscale
      - Glare detection (overexposed highlight regions)
    """
    import cv2
    if face_img is None or face_img.size == 0:
        return {'ok': False, 'score': 0.0, 'reason': 'Empty face image.'}

    gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)

    # Sharpness via Laplacian variance (higher = sharper)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    # Brightness
    brightness = float(gray.mean())
    # Contrast: std deviation of grayscale
    contrast = float(gray.std())
    # Glare: fraction of pixels that are overexposed (>250)
    glare_fraction = float(np.mean(gray > 250))

    issues = []
    if blur_score < 15:
        issues.append('image too blurry — hold still and stay in focus')
    if brightness < 30:
        issues.append('too dark — face a light source or turn on more lights')
    elif brightness > 230:
        issues.append('overexposed — reduce bright light or backlight behind you')
    if contrast < 12:
        issues.append('low contrast — improve lighting')
    if glare_fraction > 0.15:
        issues.append('glare detected — move away from direct light or glass')

    # Composite score [0-1]
    sharpness_score  = min(blur_score / 200.0, 1.0)
    brightness_score = 1.0 - abs(brightness - 120) / 120.0
    contrast_score   = min(contrast / 60.0, 1.0)
    glare_penalty    = max(0.0, 1.0 - glare_fraction * 4)

    quality_score = (
        0.50 * sharpness_score
        + 0.25 * brightness_score
        + 0.15 * contrast_score
        + 0.10 * glare_penalty
    )

    ok = len(issues) == 0
    reason = 'Good quality.' if ok else ('Poor quality: ' + '; '.join(issues) + '.')

    return {
        'ok': ok,
        'score': float(np.clip(quality_score, 0.0, 1.0)),
        'blur_score': blur_score,
        'brightness': brightness,
        'contrast': contrast,
        'glare_fraction': glare_fraction,
        'reason': reason,
    }


# ─── FaceNet Embedding ────────────────────────────────────────────────────────

_facenet_model = None
_using_mock = False
_model_load_error = None  # stores actual error message for UI display


def get_facenet_model():
    global _facenet_model, _using_mock, _model_load_error
    if _facenet_model is not None:
        return _facenet_model

    import warnings

    # Step 1: check TensorFlow separately for a clearer error message
    try:
        import tensorflow as tf  # noqa: F401
    except ImportError as e:
        err_str = str(e)
        if 'DLL load failed' in err_str or 'DLL' in err_str:
            _model_load_error = (
                f'TensorFlow DLL load failed: {e}. '
                'This almost always means Python version mismatch. '
                'tensorflow-cpu 2.13.x requires Python 3.10 or 3.11. '
                'Your Python is likely 3.12 or 3.13. '
                'Fix: delete .venv, install Python 3.11, recreate .venv, '
                'then run: pip install -r requirements.txt'
            )
        else:
            _model_load_error = (
                f'TensorFlow not installed ({e}). '
                'Run: pip install tensorflow-cpu>=2.13.0,<2.14.0'
            )
        warnings.warn(_model_load_error, RuntimeWarning)
        _facenet_model = _MockFaceNet()
        _using_mock = True
        return _facenet_model

    # Step 2: load keras-facenet
    try:
        from keras_facenet import FaceNet
        _facenet_model = FaceNet()
        _using_mock = False
        _model_load_error = None
    except ImportError as e:
        _model_load_error = (
            f'keras-facenet not installed ({e}). '
            'Run: pip install keras-facenet'
        )
        warnings.warn(_model_load_error, RuntimeWarning)
        _facenet_model = _MockFaceNet()
        _using_mock = True
    except Exception as e:
        _model_load_error = (
            f'Model load failed ({type(e).__name__}: {e}). '
            'Check TensorFlow version compatibility.'
        )
        warnings.warn(_model_load_error, RuntimeWarning)
        _facenet_model = _MockFaceNet()
        _using_mock = True

    return _facenet_model


def is_using_mock_model() -> bool:
    """Returns True if the real FaceNet model is not loaded (embeddings are random)."""
    get_facenet_model()
    return _using_mock


def get_model_load_error() -> str:
    """Returns the error that caused mock fallback, or None if model loaded successfully."""
    get_facenet_model()
    return _model_load_error


class _MockFaceNet:
    """
    Fallback for environments where keras-facenet is not installed.
    Returns random unit-normalized embeddings — useful only for UI testing,
    NOT for real verification (similarity scores will be random ~0).
    """
    def embeddings(self, faces):
        import warnings
        warnings.warn(
            'MOCK FaceNet: embeddings are random. Install keras-facenet for real matching.',
            RuntimeWarning
        )
        n = len(faces)
        embs = np.random.randn(n, 128).astype(np.float32)
        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        return embs / (norms + 1e-10)


def get_embedding(face_img: np.ndarray) -> np.ndarray:
    """
    Generate a 128-d FaceNet embedding from a 160x160 BGR face crop.

    Preprocessing pipeline:
      1. Apply CLAHE for contrast normalisation (helps low-light captures)
      2. BGR -> RGB conversion
      3. Resize to 160x160
      4. keras-facenet applies per-image prewhiten internally
      5. L2-normalize output

    This pipeline is identical for registration and verification, ensuring that
    embeddings from both stages are directly comparable via cosine similarity.
    """
    import cv2
    # Apply CLAHE before colour conversion for better low-light performance
    face_enhanced = _apply_clahe(face_img)
    face_rgb = cv2.cvtColor(face_enhanced, cv2.COLOR_BGR2RGB)
    face_resized = cv2.resize(face_rgb, (160, 160))
    faces_batch = np.expand_dims(face_resized, axis=0)  # (1, 160, 160, 3) uint8

    model = get_facenet_model()
    embedding = model.embeddings(faces_batch)[0]

    # L2-normalize (keras-facenet already does this, but enforce it)
    norm = np.linalg.norm(embedding)
    if norm > 1e-10:
        embedding = embedding / norm

    return embedding.astype(np.float32)


# ─── Similarity ───────────────────────────────────────────────────────────────

def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
    """Cosine similarity between two embeddings (re-normalizes for safety)."""
    n1 = np.linalg.norm(emb1)
    n2 = np.linalg.norm(emb2)
    if n1 < 1e-10 or n2 < 1e-10:
        return 0.0
    return float(np.dot(emb1 / n1, emb2 / n2))


# ─── Full Pipeline ────────────────────────────────────────────────────────────

def process_face_for_registration(image_bytes: bytes) -> dict:
    """
    Full pipeline for registration:
      load image -> detect & align face -> quality check -> CLAHE -> embedding -> encrypt

    Quality gate: rejects clearly unusable captures so the stored embedding is reliable.
    The threshold is intentionally lenient (blur_score < 8) — staff can retake if needed.
    """
    try:
        img = load_image_from_bytes(image_bytes)
        face_img = detect_and_align_face(img)

        quality = check_face_quality(face_img)
        # Reject severely blurry or dark images during registration
        if quality['blur_score'] < 8:
            return {
                'success': False,
                'error': f'Image quality too poor for registration. {quality["reason"]}',
            }

        embedding = get_embedding(face_img)

        if is_using_mock_model():
            return {
                'success': False,
                'error': (
                    'Face recognition model not loaded. '
                    'Install keras-facenet and tensorflow, then restart the server.'
                ),
            }

        encrypted = encrypt_embedding(embedding)
        return {
            'success': True,
            'encrypted_embedding': encrypted,
            'quality': quality,
            'embedding_shape': embedding.shape,
        }
    except ValueError as e:
        return {'success': False, 'error': str(e)}
    except Exception as e:
        return {'success': False, 'error': f'Face processing error: {str(e)}'}


def process_face_for_verification(image_bytes: bytes, reject_poor_quality: bool = True) -> dict:
    """
    Full pipeline for verification:
      load image -> detect & align face -> quality check -> CLAHE -> embedding

    Args:
        reject_poor_quality: If True, frames with blur_score < 5 are rejected
          rather than producing an unreliable embedding. This prevents random
          low scores from very blurry captures misleading the decision.

    Returns dict with 'success', 'embedding', 'quality', or 'error'.
    """
    try:
        img = load_image_from_bytes(image_bytes)
        face_img = detect_and_align_face(img)
        quality = check_face_quality(face_img)

        # Hard reject extremely blurry frames during verification
        if reject_poor_quality and quality['blur_score'] < 5:
            return {
                'success': False,
                'error': (
                    f'Frame too blurry for reliable verification. '
                    f'{quality["reason"]} Please hold still and retry.'
                ),
                'quality': quality,
            }

        embedding = get_embedding(face_img)

        return {
            'success': True,
            'embedding': embedding,
            'quality': quality,
            'using_mock': is_using_mock_model(),
        }
    except ValueError as e:
        return {'success': False, 'error': str(e)}
    except Exception as e:
        return {'success': False, 'error': f'Face processing error: {str(e)}'}


def compare_with_stored(live_embedding: np.ndarray, encrypted_stored: bytes) -> dict:
    """Compare live embedding against a single stored encrypted embedding."""
    try:
        stored_embedding = decrypt_embedding(encrypted_stored)
        score = cosine_similarity(live_embedding, stored_embedding)
        return {'success': True, 'score': score}
    except Exception as e:
        return {'success': False, 'error': f'Comparison error: {str(e)}', 'score': 0.0}


def compare_with_all_embeddings(live_embedding: np.ndarray, beneficiary) -> dict:
    """
    Compare live embedding against ALL stored embeddings for a beneficiary
    and return the best (highest) score plus template tracking details.

    Supports multi-template matching: primary FaceEmbedding + any additional
    AdditionalFaceEmbedding records. Returns the best score across all templates.

    Return keys:
      success          – bool
      score            – float, best cosine similarity found
      matched_template – str, label of the winning template
      templates_checked– int, number of templates compared
      all_scores       – list of {'template': str, 'score': float}
      error            – str (only when success=False)
    """
    best_score = None
    matched_template = ''
    all_scores = []
    errors = []

    # Primary embedding
    try:
        primary = beneficiary.face_embedding
        result = compare_with_stored(live_embedding, primary.embedding_data)
        if result['success']:
            s = result['score']
            all_scores.append({'template': 'primary', 'score': s})
            if best_score is None or s > best_score:
                best_score = s
                matched_template = 'primary'
        else:
            errors.append(result.get('error', 'Primary comparison failed'))
    except Exception as e:
        errors.append(f'Primary embedding error: {e}')

    # Additional templates (AdditionalFaceEmbedding)
    try:
        additional = list(beneficiary.additional_embeddings.all())
        for idx, tmpl in enumerate(additional, start=1):
            label = getattr(tmpl, 'label', None) or f'additional_{idx}'
            r = compare_with_stored(live_embedding, tmpl.embedding_data)
            if r['success']:
                s = r['score']
                all_scores.append({'template': label, 'score': s})
                if best_score is None or s > best_score:
                    best_score = s
                    matched_template = label
    except AttributeError:
        pass  # No additional embeddings model — fine
    except Exception as e:
        errors.append(f'Additional template error: {e}')

    templates_checked = len(all_scores)

    if best_score is None:
        return {
            'success': False,
            'error': '; '.join(errors) or 'No embeddings available.',
            'score': 0.0,
            'matched_template': '',
            'templates_checked': 0,
            'all_scores': [],
        }

    return {
        'success': True,
        'score': best_score,
        'matched_template': matched_template,
        'templates_checked': templates_checked,
        'all_scores': all_scores,
    }
