"""
Face processing utilities: RetinaFace detection + alignment, FaceNet embeddings,
embedding encryption/decryption.

Key design decisions:
- _align_face uses a 4-DOF similarity transform (rotation+scale+translation) mapping
  detected eye landmarks to canonical positions in a 160x160 output. This is the standard
  MTCNN/FaceNet pre-processing and ensures consistent crops regardless of face distance,
  head tilt, or camera resolution.
- get_embedding converts BGR->RGB, resizes to 160x160, and lets keras-facenet apply
  its own per-image whitening (prewhiten). We also L2-normalize the output.
- Preprocessing is identical for registration and verification, ensuring comparable embeddings.
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


# ─── Face Detection (RetinaFace) ──────────────────────────────────────────────

def detect_and_align_face(img: np.ndarray) -> np.ndarray:
    """
    Detect face using RetinaFace and return a 160x160 aligned face crop.
    Uses a proper similarity transform so the result is consistent regardless
    of face distance, tilt, or camera resolution.
    Falls back to OpenCV Haar cascade if RetinaFace is not available.
    Raises ValueError with a user-friendly message if no usable face is found.
    """
    try:
        from retinaface import RetinaFace
        faces = RetinaFace.detect_faces(img)
    except ImportError:
        return _detect_face_opencv(img)

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

        # Validate face size — too small means too far from camera
        inter_eye_dist = float(np.linalg.norm(right_eye - left_eye))
        if inter_eye_dist < 20:
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
    A low-quality crop will produce unreliable embeddings.
    """
    import cv2
    if face_img is None or face_img.size == 0:
        return {'ok': False, 'score': 0.0, 'reason': 'Empty face image.'}

    gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)

    # Sharpness via Laplacian variance (higher = sharper)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    # Brightness
    brightness = float(gray.mean())

    issues = []
    if blur_score < 15:
        issues.append('image too blurry — hold still')
    if brightness < 30:
        issues.append('too dark — improve lighting')
    elif brightness > 230:
        issues.append('overexposed — reduce bright light behind you')

    # Normalize score 0-1
    sharpness_score = min(blur_score / 200.0, 1.0)
    brightness_score = 1.0 - abs(brightness - 128) / 128.0
    quality_score = 0.7 * sharpness_score + 0.3 * brightness_score

    ok = len(issues) == 0
    reason = 'Good quality.' if ok else ('Poor quality: ' + '; '.join(issues) + '.')

    return {
        'ok': ok,
        'score': float(np.clip(quality_score, 0.0, 1.0)),
        'blur_score': blur_score,
        'brightness': brightness,
        'reason': reason,
    }


# ─── FaceNet Embedding ────────────────────────────────────────────────────────

_facenet_model = None
_using_mock = False


def get_facenet_model():
    global _facenet_model, _using_mock
    if _facenet_model is None:
        try:
            from keras_facenet import FaceNet
            _facenet_model = FaceNet()
            _using_mock = False
        except (ImportError, Exception) as e:
            import warnings
            warnings.warn(
                f'keras-facenet not available ({e}). Using MOCK embeddings — '
                'verification scores will be random. Install keras-facenet.',
                RuntimeWarning
            )
            _facenet_model = _MockFaceNet()
            _using_mock = True
    return _facenet_model


def is_using_mock_model() -> bool:
    """Returns True if the real FaceNet model is not loaded (embeddings are random)."""
    get_facenet_model()
    return _using_mock


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
    Preprocessing: BGR->RGB, resize to 160x160 (keras-facenet applies prewhiten internally).
    Output is L2-normalized.
    """
    import cv2
    face_rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
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
      load image -> detect & align face -> quality check -> generate embedding -> encrypt
    Returns dict with 'success', 'encrypted_embedding', 'quality', or 'error'.
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


def process_face_for_verification(image_bytes: bytes) -> dict:
    """
    Full pipeline for verification:
      load image -> detect & align face -> quality check -> generate embedding
    Returns dict with 'success', 'embedding', 'quality', or 'error'.
    """
    try:
        img = load_image_from_bytes(image_bytes)
        face_img = detect_and_align_face(img)
        quality = check_face_quality(face_img)
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
    """Compare live embedding against stored encrypted embedding."""
    try:
        stored_embedding = decrypt_embedding(encrypted_stored)
        score = cosine_similarity(live_embedding, stored_embedding)
        return {'success': True, 'score': score}
    except Exception as e:
        return {'success': False, 'error': f'Comparison error: {str(e)}', 'score': 0.0}
