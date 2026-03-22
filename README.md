# FANS-C: A Secure FaceNet-Based Facial Verification System for Senior Citizen Stipend Distribution

A Django web application for Quezon City barangay offices. Staff register senior citizen beneficiaries with facial biometrics, then verify their identity at each monthly stipend payout using face recognition.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Features](#features)
3. [Tech Stack](#tech-stack)
4. [System Architecture](#system-architecture)
5. [Installation Guide (Windows)](#installation-guide-windows)
6. [Usage Guide](#usage-guide)
7. [Configuration Reference](#configuration-reference)
8. [Face Recognition Status](#face-recognition-status)
9. [Critical Notes](#critical-notes)
10. [Troubleshooting](#troubleshooting)
11. [Limitations](#limitations)
12. [Future Improvements](#future-improvements)

---

## Project Overview

FANS-C is a pilot-ready implementation designed to automate and secure the monthly stipend distribution process for senior citizens under the Quezon City government's social welfare program. The system replaces manual ID-based verification with biometric face recognition, reducing fraud risk and accelerating the payout process at the barangay level.

The system is functional and secure for controlled deployment. It has been developed and validated in a supervised environment and requires only production hardening (PostgreSQL, strict liveness enforcement, threshold calibration) for full-scale rollout.

**Target Users:**
- **Barangay staff** — register beneficiaries and process stipend claims
- **Barangay administrators** — manage users, override decisions, deactivate records, schedule stipend events

---

## Features

- Beneficiary registration with multi-step form (personal info, representative, consent, face capture)
- FaceNet-based face recognition using 128-dimensional L2-normalized embeddings
- Two-layer liveness detection: texture anti-spoofing and MediaPipe head movement challenge
- Fernet symmetric encryption (AES-128) for all stored face embeddings
- Stipend event calendar with automatic claim linkage to payout periods
- Manual review workflow with admin override and audit trail
- Beneficiary lifecycle management (Active, Inactive, Deceased, Pending)
- **Biometric representative verification** — representatives must have their face enrolled (FaceNet) and pass liveness; ID-only is blocked
- **Representative management** — add/deactivate representatives with required validation; ID type selected from a standardized dropdown; face enrollment can begin immediately after adding (including while beneficiary is pending approval)
- Registration approval queue — new beneficiaries are held as Pending until an admin approves them
- Cascading Philippine address dropdowns (QC 131+ barangays)
- Quezon City government portal theme (Bootstrap 5) with official city logo in the navbar

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Django 4.2 (Python 3.11) |
| Face Detection | RetinaFace (falls back to OpenCV Haar cascade) |
| Face Alignment | 4-DOF similarity transform to canonical eye positions |
| Face Recognition | FaceNet via keras-facenet (128-d embeddings) |
| Similarity Metric | Cosine similarity with configurable threshold |
| Liveness Detection | Texture anti-spoofing + MediaPipe head movement challenge |
| Embedding Storage | Fernet encryption (cryptography library) |
| Database | SQLite (development) / PostgreSQL (production) |
| UI | Bootstrap 5 |

---

## System Architecture

```
Browser (webcam) --> Django View --> Face Pipeline
                                        |
                          +-------------+-------------+
                          |             |             |
                     Liveness       RetinaFace    FaceNet
                     Check          Detection     Embedding
                     (texture +     (alignment)   (128-d L2)
                     MediaPipe)          |             |
                                         +------+------+
                                                |
                                        Cosine Similarity
                                        vs stored embedding
                                                |
                                  Verified / Manual Review / Not Verified
                                                |
                                        AuditLog + VerificationAttempt
```

**Registration flow:** Personal info -> Representative -> Consent -> Face capture -> Embedding encrypted and stored.

**Verification flow:** Search beneficiary -> Liveness check -> Burst capture (5 frames, sharpest selected) -> Face matching -> Decision recorded.

---

## Installation Guide (Windows)

### Prerequisites

- **Python 3.11 only** — Python 3.12 and 3.13 are not compatible with TensorFlow 2.13.x. See [Critical Notes](#critical-notes).
- Git
- A short project path (e.g., `D:\FANS`) — required to avoid Windows path length limits during TensorFlow installation. See [Critical Notes](#critical-notes).

### Step 1 — Clone the repository

```
git clone <repo-url> D:\FANS\fans-c
cd D:\FANS\fans-c
```

### Step 2 — Create a virtual environment using Python 3.11

```
py -3.11 -m venv .venv
.venv\Scripts\activate
```

Confirm the correct Python is active:
```
python --version
```
Expected output: `Python 3.11.x`

### Step 3 — Install dependencies

```
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

> TensorFlow installation may take several minutes. Use `python -m pip` rather than bare `pip` to ensure the correct environment's pip is used. See [Critical Notes](#critical-notes).

### Step 4 — Create the environment file

Create a file named `.env` in the project root with the following content:

```
SECRET_KEY=replace-with-a-secure-random-key-before-deployment
DEBUG=True
USE_SQLITE=True
EMBEDDING_ENCRYPTION_KEY=
DEMO_MODE=True
LIVENESS_REQUIRED=False
VERIFICATION_THRESHOLD=0.75
DEMO_THRESHOLD=0.60
ANTI_SPOOF_THRESHOLD=0.15
MAX_RETRY_ATTEMPTS=1
```

> **EMBEDDING_ENCRYPTION_KEY:** Leave blank during development. A temporary key is generated per server restart, which means registered embeddings become unreadable after a restart. For a stable key, run:
> ```
> python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
> ```
> Paste the output into `.env` before registering any beneficiaries.

### Step 5 — Apply migrations

```
python manage.py migrate
```

### Step 6 — Create an admin user

```
python manage.py createsuperuser
```

Then log in and set the user's role to `admin` via the Django admin at `/admin/` or the User Management page.

### Step 7 — Collect static files

```
python manage.py collectstatic --noinput
```

### Step 8 — Run the server

```
python manage.py runserver
```

Open `http://localhost:8000/dashboard/` and log in.

---

## Usage Guide

### Registering a Beneficiary

1. Log in as staff or admin.
2. Go to **Beneficiaries > Register New**.
3. Complete the four-step form:
   - **Step 1 — Personal Info:** Name, date of birth, gender, address, contact, government IDs.
   - **Step 2 — Representative:** Optionally indicate that the beneficiary has an authorized representative. If enabled, all representative fields are **required**: first name, last name, contact number, ID type (dropdown), and ID number.
   - **Step 3 — Consent:** Beneficiary or guardian consents to biometric data collection.
   - **Step 4 — Face Capture:** Staff captures the beneficiary's face via webcam. The system detects and aligns the face, generates a FaceNet embedding, encrypts it, and stores it.
4. After registration, the beneficiary is set to **Pending** status and cannot be verified until an admin approves the registration via the Registration Review queue.

### Registering a Representative

Representatives must be biometrically enrolled before they can verify or claim.

1. Open the beneficiary's profile page.
2. In the **Authorized Representatives** card, click **Add Representative**.
3. Fill in all required fields: first name, last name, contact number, ID type (select from dropdown), and ID number.
4. Click **Save Representative & Register Face** — you are taken directly to the face capture page for that representative.
5. Capture the representative's face. Their FaceNet embedding is encrypted and stored.
6. On the detail page, the representative now shows **Face Registered — Ready to Verify**.

> **Note on Pending Beneficiaries:** Representatives can be added and have their faces enrolled even while the beneficiary is awaiting approval. Once the admin approves the beneficiary, the representative is immediately usable for verification.

### Representative ID Type

When adding a representative, the **ID Type** field is a required dropdown with the following choices:
- PhilSys ID
- Passport
- Driver's License
- UMID
- Voter's ID
- Senior Citizen ID
- Other

Free-text ID types are not accepted.

### Processing a Stipend Claim

1. Go to **Verify** and search by name or beneficiary ID.
2. Select who is claiming: **Beneficiary** (face scan) or **Representative** (biometric face scan).
3. If claiming as beneficiary:
   - Liveness check runs (texture + head movement challenge).
   - A burst of 5 frames is captured; the sharpest is submitted for face matching.
   - Result: **Verified**, **Manual Review**, or **Not Verified**.
   - After one failed retry, the system falls back to ID verification (for beneficiaries only).
4. If claiming as representative:
   - The same liveness check and FaceNet face matching runs — but against the representative's enrolled face, not the beneficiary's.
   - ID-only verification is **blocked** for representatives; they must pass biometric face verification.
   - Deactivated representatives are blocked from claiming.
5. Result is recorded and linked to the active stipend event. The claim record stores which representative performed the claim.

### Stipend Events

Administrators create stipend events (payout periods) under **Verification > Stipend Events**. Each event has a title, date, and optional description. Verification attempts made on the event date are automatically linked to that event in the audit log.

### Admin Override

When a verification result is **Manual Review**, administrators can apply an override with a documented reason (minimum 20 characters). All overrides are logged with the actor, timestamp, and reason.

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `DEBUG` | `True` | Django debug mode. Set to `False` in production. |
| `USE_SQLITE` | `True` | Use SQLite. Set to `False` and configure DB_* vars for PostgreSQL. |
| `DEMO_MODE` | `True` | Pilot / Assisted Rollout Mode — uses a more accommodating threshold and makes liveness non-blocking. Set to `False` for full enforcement. |
| `LIVENESS_REQUIRED` | `False` | If `True`, liveness failure blocks verification entirely (full enforcement). Set `False` for assisted rollout. |
| `VERIFICATION_THRESHOLD` | `0.75` | Cosine similarity threshold for full enforcement mode. |
| `DEMO_THRESHOLD` | `0.60` | Threshold used in Pilot Mode (`DEMO_MODE=True`) — accommodates webcam quality variation during rollout. |
| `ANTI_SPOOF_THRESHOLD` | `0.15` | Texture anti-spoofing threshold. |
| `MAX_RETRY_ATTEMPTS` | `1` | Number of face verification retries before fallback. |

**PostgreSQL setup (production):**

```
USE_SQLITE=False
DB_NAME=fans_db
DB_USER=fans_user
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432
DEBUG=False
LIVENESS_REQUIRED=True
DEMO_MODE=False
VERIFICATION_THRESHOLD=0.75
```

---

## Face Recognition Status

The face recognition model is loaded via **keras-facenet**, which wraps the FaceNet architecture in a Keras-compatible interface backed by TensorFlow.

**Current state:**
- The model loads successfully when TensorFlow is correctly installed with Python 3.11.
- Real face embeddings are generated and compared using cosine similarity.
- The system is not running in mock mode — all verification scores are computed from actual biometric data.
- Accuracy is functional but requires threshold tuning for the specific hardware and conditions used in deployment.

**How to confirm the model is loaded:**

Go to **Admin > Threshold Configuration** (`/verification/config/`). The "Face Recognition Model Status" card shows:

| Status | Meaning |
|---|---|
| FaceNet (keras-facenet) — green | Real model loaded. Scores are meaningful. |
| MOCK — not loaded — red | Model failed to load. All scores are random (~0). Verification does not work. |

A red banner also appears on the Verification screen whenever mock mode is active.

**Difference between Pilot Mode and Mock Model:**

| Setting | Effect |
|---|---|
| `DEMO_MODE=True` (Pilot / Assisted Rollout) | Accommodating threshold (0.60), liveness recorded but non-blocking. Real FaceNet matching runs normally. |
| `DEMO_MODE=False` (Full Enforcement) | Strict threshold (0.75), liveness enforced. Intended for full production rollout. |
| Mock model active | keras-facenet failed to load. All similarity scores are random. No real matching. |

Pilot Mode and mock model are independent. The correct configuration for a controlled deployment or supervised evaluation is `DEMO_MODE=True` with the real FaceNet model loaded. This produces real biometric verification results with a threshold calibrated for the evaluation environment.

---

## Critical Notes

### TensorFlow requires Python 3.10 or 3.11

`tensorflow-cpu 2.13.x` only supports Python 3.8 through 3.11. If your virtual environment was created with Python 3.12 or 3.13, TensorFlow's C extensions will fail to load at runtime with a DLL error, even though the package installs without errors. Always verify with `python --version` after activating the environment.

### Windows long path limit causes TensorFlow installation to fail

Windows limits file paths to 260 characters by default. TensorFlow wheels contain deeply nested source files that exceed this limit during extraction. This causes `pip install` to fail with an `OSError: [Errno 2] No such file or directory` pointing to a `.h` file inside the wheel.

Two fixes:
1. Enable long path support in Windows (run PowerShell as Administrator):
   ```powershell
   reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f
   ```
   Then restart the computer.
2. Use a short project path such as `D:\FANS`. A path like `D:\3RD YEAR 2ND SEM\Capstone Project\FANS-C-A-Secure-FaceNet-...` will likely fail; `D:\FANS` will not.

### Virtual environments break after moving the project folder

Virtual environments store absolute paths internally. If you move or rename the project folder after creating `.venv`, all venv-based commands will fail. The fix is to delete the old `.venv` folder and create a new one from the new location. Do not try to repair a moved venv.

### Use `python -m pip` instead of `pip` directly

On Windows, calling `pip` directly can invoke the wrong pip if system Python is also installed. Using `python -m pip` ensures the pip belonging to the currently active virtual environment is used, preventing packages from being installed into the wrong location or version.

---

## Troubleshooting

### DLL load failure when importing TensorFlow

**Symptom:**
```
DLL load failed while importing _pywrap_tensorflow_lite_metrics_wrapper: The specified procedure could not be found.
```

**Cause:** Python version mismatch. The venv was created with Python 3.12 or 3.13.

**Fix:**
1. Delete the `.venv` folder.
2. Install Python 3.11 from python.org.
3. Confirm: `py -3.11 --version`
4. Recreate the venv: `py -3.11 -m venv .venv`
5. Activate and reinstall: `.venv\Scripts\activate` then `python -m pip install -r requirements.txt`

---

### keras-facenet not installed or scipy missing

**Symptom:**
```
ModuleNotFoundError: No module named 'keras_facenet'
```
or
```
ModuleNotFoundError: No module named 'scipy'
```

**Cause:** Dependencies were not fully installed, or were installed into the wrong environment.

**Fix:**
```
python -m pip install keras-facenet scipy
```
Ensure the venv is activated before running this command.

---

### numpy incompatibility with TensorFlow

**Symptom:**
```
RuntimeError: module compiled against API version ... but this version of numpy is ...
```
or numpy-related attribute errors on import.

**Cause:** numpy version is too new for the installed TensorFlow version.

**Fix:**
```
python -m pip install "numpy>=1.23.5,<1.25.0"
```
TensorFlow 2.13 requires numpy below 1.25.

---

### "manage.py not found" or "No such file or directory: manage.py"

**Cause:** The terminal is not in the project root directory.

**Fix:** Navigate to the directory that contains `manage.py`:
```
cd D:\FANS\fans-c
python manage.py runserver
```

---

### pip launcher broken after moving the project folder

**Symptom:**
```
The system cannot find the file specified
```
when running `pip install`.

**Cause:** The `.venv` folder contains hardcoded absolute paths to the original location. Moving the project folder invalidates all these paths.

**Fix:** Delete the `.venv` folder entirely and recreate it from the new location:
```
cd D:\FANS\fans-c
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

### Verification scores are very low (e.g., 0.05) for the correct person

**Possible causes:**

1. **Encryption key changed between registration and verification.** If `EMBEDDING_ENCRYPTION_KEY` was blank and the server restarted, the stored embedding cannot be decrypted. Set a stable key in `.env` first, then re-register the beneficiary.
2. **Lighting difference.** Register and verify under the same lighting conditions. Strong backlight or very dim lighting degrades embedding quality.
3. **Face too far from camera.** Keep the face 30-50 cm from the lens.
4. **Threshold needs calibration.** Lower `DEMO_THRESHOLD` in `.env` (e.g., to 0.50) and re-test. Use the admin Threshold Configuration page to adjust live without a restart.

---

### Unapplied migrations warning

If you see `Your models in app(s) have changes that are not yet reflected in a migration`, run:

```
python manage.py migrate
```

All migrations are included in the repository. Running `makemigrations` is not needed unless you add new model fields yourself.

---

## Limitations and Known Constraints

- **Lighting and angle consistency.** Registration and verification should be performed under similar lighting conditions. Strong backlight, very dim environments, or large pose changes reduce matching accuracy. Recommended: a controlled capture station with consistent front lighting.
- **Threshold requires site-specific calibration.** The default thresholds (0.75 full enforcement, 0.60 assisted rollout) are validated starting points. The optimal value depends on the specific camera hardware and deployment environment. The admin Threshold Configuration page allows live adjustment without a code change.
- **Pre-trained model without local fine-tuning.** The system uses a pre-trained FaceNet model. For a full production deployment, fine-tuning on a locally collected dataset would improve accuracy in barangay-specific conditions.
- **Liveness detection is heuristic.** The two-layer liveness check (texture anti-spoofing + MediaPipe head movement challenge) is effective against casual fraud. It is not engineered to resist sophisticated adversarial attacks such as high-quality video replay, which would require a trained liveness model.
- **Single face template per person.** If a beneficiary's appearance changes significantly, re-registration is required. Multi-template support is listed as a future improvement.
- **No multi-face handling.** The system uses the highest-confidence detected face only. Staff should ensure only the claimant is in frame during verification.
- **Eyeglasses consistency.** If a beneficiary wears glasses during registration, they should wear them during verification as well for consistent embeddings.

---

## Future Improvements

- **Threshold calibration tool.** Build an admin interface to test threshold values against a set of sample registrations and produce a recommended cutoff for the specific hardware.
- **Improved liveness detection.** Replace heuristic texture analysis with a trained anti-spoofing model (e.g., Silent-Face-Anti-Spoofing) for better resistance to photo and video replay attacks.
- **Replace or supplement MTCNN/RetinaFace.** Evaluate more robust face detectors for low-light and off-angle conditions common in barangay environments.
- **Performance optimization for low-end machines.** Profile and reduce inference time on hardware without dedicated GPU, using model quantization or a lighter embedding model.
- **Mobile capture support.** Allow face capture from a mobile device camera via QR code session linking, for deployments where a laptop webcam is not available.
- **Periodic re-enrollment reminders.** Flag beneficiaries whose face embedding is older than a configurable threshold for re-registration.
- **Multi-template support.** Store multiple embeddings per beneficiary (e.g., with and without glasses) and match against the best-scoring template.

---

## Project Structure

```
fans/                       Django project settings and URLs
accounts/                   Custom user model (role: admin/staff), login/logout
beneficiaries/              Beneficiary registration, list, edit, lifecycle management
verification/               Face pipeline, liveness, results, fallback, override, stipend events, config
logs/                       Audit log model and views
templates/                  All HTML templates (extends base.html)
static/
  css/main.css              QC government portal theme (blue #003d99, red #c62828, gold #d4a017)
  js/
    webcam.js               Camera utility (640x480, burst capture, sharpness selection)
    liveness.js             MediaPipe head movement tracking
    verify.js               Verification flow controller (liveness -> burst capture -> submit)
    address_cascades.js     Province/municipality/barangay cascading dropdowns
    register.js             Registration face capture
  data/
    ph_addresses.json       Philippine address data (all NCR cities, QC 131+ barangays)
```

---

## Migrations Reference

| App | Migration | Description |
|---|---|---|
| accounts | 0001 | CustomUser model |
| accounts | 0002 | is_active field |
| beneficiaries | 0001 | Initial beneficiary model |
| beneficiaries | 0002 | Senior citizen ID, valid ID fields |
| beneficiaries | 0003 | Lifecycle: deceased status, deactivated_at/by/reason |
| logs | 0001 | AuditLog model |
| logs | 0002 | Add 'update' action choice for record edits |
| verification | 0001 | FaceEmbedding, VerificationAttempt, SystemConfig |
| verification | 0002 | claimant_type, decision_reason on VerificationAttempt |
| verification | 0003 | StipendEvent model, stipend_event FK, face_quality_score |
| verification | 0004 | StipendEvent.event_type (regular / birthday_bonus) |
