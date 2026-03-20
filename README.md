# FANS-C: Secure FaceNet-Based Facial Verification System for Senior Citizen Stipend Distribution

A Django web application for Quezon City barangay offices. Staff register senior citizen beneficiaries with facial biometrics, then verify their identity at each monthly stipend payout using face recognition.

---

## System Overview

| Component | Technology |
|---|---|
| Backend | Django 4.2 (Python) |
| Face Detection | RetinaFace (landmark-based, falls back to OpenCV Haar cascade) |
| Face Alignment | 4-DOF similarity transform to canonical eye positions (MTCNN/FaceNet standard) |
| Face Recognition | FaceNet via keras-facenet (128-d L2-normalized embeddings) |
| Similarity Metric | Cosine similarity with configurable threshold |
| Liveness Detection | Texture anti-spoofing + MediaPipe head movement challenge |
| Embedding Storage | Fernet symmetric encryption (AES-128 via cryptography library) |
| Database | SQLite (dev) / PostgreSQL (production) |
| UI | Bootstrap 5, Quezon City government portal theme (blue, red, white, gold) |

---

## Target Users

- **Barangay staff** — register beneficiaries and process stipend claims
- **Barangay administrators** — manage users, override decisions, deactivate records, schedule stipend events

---

## Beneficiary Registration Flow

1. **Step 1 — Personal Info**: Name, date of birth, gender, address (cascading province/municipality/barangay dropdowns), contact, government IDs (Senior Citizen ID, valid ID type and number).
2. **Step 2 — Representative**: Optionally register an authorized representative who can claim on behalf of the senior citizen. Requires name, relationship, contact, and a government-issued ID.
3. **Step 3 — Consent**: Beneficiary or guardian must consent to biometric data collection.
4. **Step 4 — Face Capture**: Staff captures the beneficiary's face using the webcam. The system detects and aligns the face using RetinaFace landmarks, generates a 128-d FaceNet embedding, encrypts it with Fernet, and stores it in the database.

---

## Stipend Claim Workflow

When a beneficiary or representative arrives to claim the stipend:

1. Staff opens **Verify** and searches by name or beneficiary ID.
2. Staff selects who is claiming: **Beneficiary** (face scan) or **Representative** (ID check).
3. **If beneficiary**:
   - Liveness check runs: anti-spoofing texture check + head movement challenge.
   - A burst of frames is captured; the sharpest is submitted for face matching.
   - Cosine similarity is computed against the stored embedding.
   - Decision: Verified, Manual Review, or Not Verified.
   - If not verified after one retry: fallback to ID verification form.
4. **If representative**:
   - Goes directly to the ID fallback — representative presents their registered government ID.
   - Staff cross-checks the presented ID type and number against the registered record.
   - Decision: Verified or Denied.
5. Result is recorded, linked to the active stipend event (if today's date matches), and logged to the audit trail.

---

## Verification Process (Technical)

1. Camera is opened at up to 640x480.
2. **Liveness check** (server-side, non-blocking in demo mode):
   - Anti-spoofing via texture analysis (Laplacian variance + local pixel variance).
   - Head movement challenge (left/right/up/down) via MediaPipe, 5-second timeout, auto-accepts on timeout (accessibility for senior citizens).
3. On "Process Verification": a burst of 5 frames is captured; the sharpest (by pixel variance) is submitted.
4. **Face matching**:
   - RetinaFace detects landmarks including eye positions.
   - A 4-DOF similarity transform maps detected eye landmarks to canonical positions in a 160x160 output image (left eye at 38,52; right eye at 74,52 — MTCNN/FaceNet standard).
   - FaceNet generates a 128-d embedding; keras-facenet applies per-image whitening internally.
   - The embedding is L2-normalized.
   - Cosine similarity is computed against the stored (decrypted) embedding.
5. **Decision**:
   - Score >= threshold: **Verified** — release stipend
   - Score >= threshold * 0.85: **Manual Review** — admin must decide
   - Score < threshold * 0.85: **Not Verified** — retry once, then fallback
6. All results are written to `VerificationAttempt` and the `AuditLog`.

---

## Liveness Explanation

Two-layer liveness to reduce spoofing risk:

- **Anti-spoofing (texture)**: Measures focus sharpness (Laplacian variance) and local texture complexity. Printed photos and screen replays tend to have lower values. Threshold: 0.15 (permissive for webcam quality).
- **Head movement challenge**: A random direction (left/right/up/down) is shown. MediaPipe tracks face landmarks to detect movement. Auto-accepts after 5 seconds to accommodate senior citizens with limited mobility.

In `LIVENESS_REQUIRED=True` (production): liveness failure blocks the verification.
In `LIVENESS_REQUIRED=False` (demo/default): liveness failure is recorded as metadata but face matching still runs.

---

## Manual Review

When a verification score falls in the review band (threshold * 0.85 to threshold), the decision is set to **Manual Review**. Administrators can review the attempt and apply an **Admin Override** with a documented reason (minimum 20 characters). All overrides are logged with who performed them, when, and why.

---

## Beneficiary Lifecycle Management

Beneficiaries are **never hard-deleted**. Instead, their status is changed:

- **Active**: Eligible to claim stipends.
- **Inactive**: No longer eligible (moved away, data correction, etc.).
- **Deceased**: Senior citizen has passed away.
- **Pending**: Registered but not yet fully activated.

Inactive/deceased beneficiaries cannot receive stipend claims. All historical verification attempts, audit logs, and data are preserved for accountability. Deactivation requires an admin and a documented reason. Records can be reactivated if needed.

---

## Stipend Calendar Feature

Administrators can create **Stipend Events** (payout periods):

- Title (e.g., "March 2026 Monthly Stipend"), date, optional description.
- Upcoming events (within 60 days) appear on the dashboard as a reminder.
- Each verification/claim attempt is automatically linked to the active stipend event when the claim date matches, so audit logs show which payout period was claimed.

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

## Setup Instructions

### Prerequisites

- Python 3.10 or 3.11
- pip

### 1. Clone and create virtual environment

```
git clone <repo-url>
cd FANS-C-A-Secure-FaceNet-Based-Facial-Verification-System-for-Senior-Citizen-Stipend-Distribution
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install dependencies

```
pip install -r requirements.txt
```

> TensorFlow is required by keras-facenet. On Windows, TensorFlow 2.10 is the last version with native GPU support; CPU-only works fine for capstone demos. Installation may take several minutes.

### 3. Create environment file

Create a file named `.env` in the project root:

```
SECRET_KEY=your-secret-key-here
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

> **EMBEDDING_ENCRYPTION_KEY**: Leave blank during dev (a temporary key is generated per restart — registered embeddings become unreadable after restart). For a stable key, run `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and paste the output into `.env`.

### 4. Apply migrations

```
python manage.py migrate
```

### 5. Create admin user

```
python manage.py createsuperuser
```

Then log in and set the user's role to `admin` via the Django admin at `/admin/` or the User Management page.

### 6. Collect static files (first run or after CSS/JS changes)

```
python manage.py collectstatic --noinput
```

### 7. Run the server

```
python manage.py runserver
```

Open `http://localhost:8000/dashboard/` and log in.

---

## Migrations Reference

| App | Migration | Description |
|---|---|---|
| beneficiaries | 0001 | Initial beneficiary model |
| beneficiaries | 0002 | Senior citizen ID, valid ID fields |
| beneficiaries | 0003 | Lifecycle: deceased status, deactivated_at/by/reason |
| verification | 0001 | FaceEmbedding, VerificationAttempt, SystemConfig |
| verification | 0002 | claimant_type, decision_reason on VerificationAttempt |
| verification | 0003 | StipendEvent model, stipend_event FK, face_quality_score |

---

## PostgreSQL Setup (Production)

In `.env`:

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

## Demo Mode Behavior

When `DEMO_MODE=True` and `LIVENESS_REQUIRED=False` (both default):

- Threshold defaults to `DEMO_THRESHOLD` (0.60) — more forgiving of webcam quality and pose variation.
- Liveness failure does not block face matching — result is logged as a warning.
- A blue info banner appears on the verification screen.
- The "Process Verification" button shows a warning label if liveness failed.
- If the face recognition model is not loaded (keras-facenet missing), a clear error banner is shown.

For strict production: set `DEMO_MODE=False`, `LIVENESS_REQUIRED=True`.

---

## Limitations

- **Anti-spoofing is heuristic** (texture analysis), not a trained CNN. It is not production-grade against adversarial attacks. For production, replace with a trained model (e.g., Silent-Face-Anti-Spoofing).
- **One face template per beneficiary** — if appearance changes significantly, re-registration is required.
- **Eyeglasses**: If a beneficiary wears glasses, the registration and verification photos should both include them for consistent embeddings.
- **Lighting sensitivity**: Avoid strong backlight. Face a light source, 30-50 cm from camera, and hold still.
- **No multi-face handling**: The system uses the highest-confidence detected face only.

---

## Recommended .env for Capstone Demo

```
SECRET_KEY=fans-demo-secret-change-for-production
DEBUG=True
USE_SQLITE=True
EMBEDDING_ENCRYPTION_KEY=<output of Fernet.generate_key()>
DEMO_MODE=True
LIVENESS_REQUIRED=False
DEMO_THRESHOLD=0.60
ANTI_SPOOF_THRESHOLD=0.15
MAX_RETRY_ATTEMPTS=1
```

---

## Migrations Reference (Updated)

| App | Migration | Description |
|---|---|---|
| accounts | 0001 | CustomUser model |
| accounts | 0002 | is_active field (remove verbose_name from AbstractUser override) |
| beneficiaries | 0001 | Initial beneficiary model |
| beneficiaries | 0002 | Senior citizen ID, valid ID fields |
| beneficiaries | 0003 | Lifecycle: deceased status, deactivated_at/by/reason |
| logs | 0001 | AuditLog model |
| logs | 0002 | Add 'update' action choice for record edits |
| verification | 0001 | FaceEmbedding, VerificationAttempt, SystemConfig |
| verification | 0002 | claimant_type, decision_reason on VerificationAttempt |
| verification | 0003 | StipendEvent model, stipend_event FK, face_quality_score |
| verification | 0004 | StipendEvent.event_type (regular / birthday_bonus) |

---

## Troubleshooting

### TensorFlow Installation Fails on Windows (Long Path Error)

**Symptom:**
```
Could not install packages due to an OSError: [Errno 2] No such file or directory: ...memory_allocator_impl.h
HINT: This error might have been caused by long path support being disabled.
```

**Root cause:** Windows limits file paths to 260 characters by default. TensorFlow wheels contain source files with deeply nested paths that exceed this limit during extraction.

**Fix 1 — Enable Windows Long Path Support (recommended):**

Run PowerShell as Administrator:
```powershell
reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f
```
Then restart your computer. After restart, `pip install` should succeed.

**Fix 2 — Use a shorter project path:**

Move or clone the project to a short path such as `D:\FANS`, then run pip install from there. The shorter path leaves enough room for TensorFlow's internal paths.

```
D:\FANS\       (works — short root)
D:\3RD YEAR 2ND SEM\Capstone Project\FANS-C-A-...\   (may fail — too long)
```

**Fix 3 — Use tensorflow-cpu (already in requirements.txt):**

`requirements.txt` already specifies `tensorflow-cpu==2.13.0` instead of `tensorflow`. This is a CPU-only build — smaller, no CUDA/GPU setup needed, and uses the same code paths. It works correctly for capstone demos.

---

### How to Tell Whether Real Face Verification Is Active

After starting the server, go to **Admin > Threshold Configuration** (`/verification/config/`). The "Face Recognition Model Status" card shows one of:

| Status | Meaning |
|---|---|
| **FaceNet (keras-facenet)** — green | Real model loaded. Face matching produces meaningful scores. |
| **MOCK — not loaded** — red | Model failed to load. All similarity scores are random (~0). Verification always fails or produces nonsense results. |

The card also shows the exact error message (e.g., `TensorFlow not installed`) and a link to this troubleshooting guide.

A red banner also appears on the Verification screen whenever mock mode is active, making it impossible to accidentally proceed without noticing.

---

### Mock Mode vs Demo Mode

These are two separate concepts that are often confused:

| Setting | What it does |
|---|---|
| `DEMO_MODE=True` | Uses a lower threshold (0.60) and makes liveness non-blocking. Real face matching still runs. |
| Mock model active | keras-facenet failed to load. All similarity scores are random. No real face matching happens. |

`DEMO_MODE` is a **threshold and UX setting**. Mock model is a **model loading failure**. You can have demo mode on with a real model (correct for capstone), or demo mode off with a mock model (broken — verification never works).

---

### Verification Scores Are Very Low (e.g., 0.05) Even for the Same Person

If the model is loaded correctly but scores are near zero:

1. **Re-register the beneficiary.** If the encryption key changed between registration and verification (e.g., `EMBEDDING_ENCRYPTION_KEY` was blank and the server restarted), the stored embedding is unreadable. Set a stable key in `.env` first, then re-register.
2. **Check lighting.** Register and verify under similar lighting. Strong backlight or very dim light degrades the embedding.
3. **Face too far from camera.** Move to 30-50 cm from the lens. Eye distance must be at least 20px in the captured image.
4. **Re-registration required.** If conditions were very different at registration time, re-capture the face embedding.

---

### python manage.py migrate reports unapplied migrations

If you see warnings like `Your models in app(s): 'accounts', 'logs' have changes that are not yet reflected in a migration`, simply run:

```
python manage.py migrate
```

All migrations including the new `accounts/0002`, `logs/0002`, and `verification/0004` are included in the repository. No `makemigrations` is needed unless you add new fields yourself.
