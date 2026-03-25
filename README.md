# FANS-C: A Secure FaceNet-Based Facial Verification System for Senior Citizen Stipend Distribution

> **A functional biometric identity verification system ready for real-world use in a controlled barangay setting — built for senior citizen stipend distribution in Quezon City.**
> Developed as a capstone project for deployment in controlled government environments.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Features](#features)
3. [Technology Stack](#technology-stack)
4. [System Architecture](#system-architecture)
5. [Core Workflows](#core-workflows)
   - [Beneficiary Registration](#1-beneficiary-registration)
   - [Representative Enrollment](#2-representative-enrollment)
   - [Stipend Verification](#3-stipend-verification)
   - [Claim System](#4-claim-system)
   - [Admin Approval Queue](#5-admin-approval-queue)
6. [Verification Pipeline — Technical](#verification-pipeline--technical)
7. [Claim System Design](#claim-system-design)
8. [Fraud Prevention Mechanisms](#fraud-prevention-mechanisms)
9. [Edge Cases and System Handling](#edge-cases-and-system-handling)
10. [Deployment Readiness](#deployment-readiness)
11. [Installation Guide (Windows)](#installation-guide-windows)
12. [Usage Guide](#usage-guide)
13. [Configuration Reference](#configuration-reference)
14. [Face Recognition Status](#face-recognition-status)
15. [Limitations and Known Constraints](#limitations-and-known-constraints)
16. [Future Improvements](#future-improvements)
17. [Project Structure](#project-structure)
18. [Migrations Reference](#migrations-reference)
19. [Critical Notes](#critical-notes)
20. [Troubleshooting](#troubleshooting)

---

## System Overview

FANS-C (Facial Authentication and Notification System — Controlled) is a fully functional web application ready for real-world use in a controlled government environment, designed to automate and secure the monthly stipend distribution process for senior citizens under the Quezon City government's social welfare program.

The system replaces manual ID-based verification with biometric face recognition, reducing fraud risk and accelerating the payout process at the barangay level. Every claim decision is cryptographically traceable — from the webcam capture through liveness validation, embedding comparison, and final release — with a tamper-evident audit trail stored alongside each record.

**The problem it solves:**

Under the manual process, barangay staff verify a beneficiary's identity by checking a physical ID card at the point of payout. This is vulnerable to impersonation (using a deceased person's ID), proxy fraud (an unauthorized person collecting on behalf of another), and clerical errors. FANS-C replaces or supplements the ID check with real-time biometric face matching, requiring any claimant — beneficiary or authorized representative — to physically present their enrolled face before a stipend is released.

**Target deployment:**

- Barangay offices within Quezon City with a webcam-equipped workstation
- Staff-assisted operation: a barangay staff member operates the system while the beneficiary presents their face

**Target users:**

| Role | Permissions |
|---|---|
| **Barangay Staff** | Register beneficiaries, process stipend claims, submit fallback and re-enrollment requests |
| **Barangay Administrator** | All staff permissions + approve registrations, override decisions, manage users, configure thresholds, schedule stipend events |

**Deployment status:**

The system is functional and secure for controlled deployment. It has been developed and validated in a supervised environment. Transitioning to full-scale rollout requires only production hardening steps: switching to PostgreSQL, enabling strict liveness enforcement, setting a stable encryption key, and calibrating the similarity threshold for the specific hardware environment.

---

## Features

**Biometric verification**
- FaceNet-based face recognition using 128-dimensional L2-normalized embeddings
- Two-layer liveness detection: texture anti-spoofing and MediaPipe head movement challenge
- Burst capture (5 frames, sharpest selected by Laplacian variance) for reliable frame quality
- CLAHE histogram equalization to normalize lighting across captures
- Multi-template matching: compare live face against all stored embeddings and take the best score

**Security and integrity**
- Fernet symmetric encryption (AES-128-CBC) for all stored face embeddings — never stored as raw images
- Duplicate face detection at registration (cosine similarity threshold 0.80 against all stored embeddings)
- Lookalike / twin detection during verification — escalates to manual review if another beneficiary scores within 0.05 of the matching score
- Immutable audit log recording every action: login, registration, verification, override, config change, with IP address and user agent
- One-claim-per-event enforcement with race guard to prevent double-payout

**Representative verification**
- Biometric representative verification — representatives must have their FaceNet face enrolled; ID-only is explicitly blocked
- Each representative has their own encrypted face embedding stored independently
- Deactivated representatives are blocked from all claim paths at the database level
- Claim records store exactly which representative was verified

**Admin controls**
- Registration approval queue — new beneficiaries are held as Pending until an admin reviews and approves
- Manual review workflow with admin override (documented reason required, minimum 20 characters)
- Face re-enrollment requires admin approval before the new embedding is applied
- Special claim request workflow for legitimate second claims on the same stipend event
- Admin override of Manual Review decisions with full audit trail

**Operational**
- Beneficiary lifecycle management: Active, Pending, Inactive, Deceased
- Stipend event calendar with payout windows; claims are automatically linked to the active event
- Birthday bonus event type with birth-month eligibility check
- Cascading Philippine address dropdowns (131+ QC barangays)
- Role-based access: staff cannot access admin-only functions
- Quezon City government portal theme (Bootstrap 5) with official city logo

---

## Technology Stack

### Backend — Django 4.2 (Python 3.11)

Django was selected for its mature ORM, built-in authentication, form validation, CSRF protection, and session management. The MTV (Model-Template-View) pattern cleanly separates the face pipeline logic (utility modules), database schema (models), and presentation (templates). Django's migration system provides a versioned schema history that can be reproduced exactly on any deployment target.

Python 3.11 specifically is required because TensorFlow 2.13.x, which backs keras-facenet, does not support Python 3.12 or later at the C-extension level.

### Face Detection — RetinaFace (OpenCV fallback)

RetinaFace is a multi-scale single-stage face detector that simultaneously localizes the face bounding box and five facial landmarks (left eye, right eye, nose tip, left mouth corner, right mouth corner). These landmarks are used directly for alignment. RetinaFace performs well at moderate off-axis angles and is robust to partial occlusion, making it suitable for senior citizens who may not hold still perfectly.

If RetinaFace fails to load (dependency issues), the system falls back to OpenCV's Haar cascade classifier, which is less accurate but ensures the pipeline does not fail entirely.

### Face Alignment — 4-DOF Similarity Transform

Before embedding generation, the detected face is geometrically normalized using a 4-degree-of-freedom similarity transform (rotation, scale, and 2D translation — no shear or perspective). The transform maps the five detected facial landmarks to a canonical set of target positions on a 112×112-pixel output image.

This step is critical for FaceNet accuracy: the model was trained on aligned faces, and presenting a significantly rotated or scaled face produces a very different embedding even for the same person. Proper alignment reduces false negatives caused by pose variation between registration and verification sessions.

### Preprocessing — CLAHE

After alignment, Contrast Limited Adaptive Histogram Equalization (CLAHE) is applied to the face image. CLAHE normalizes local contrast across the face, which reduces the effect of uneven or harsh lighting (e.g., one side of the face in shadow, or a bright backlight). This is particularly important in barangay environments where lighting conditions are not always controlled.

### Face Recognition — FaceNet via keras-facenet

FaceNet (Schroff, Kalenichenko, and Philbin, Google, 2015) is a convolutional neural network trained with a triplet loss objective to map face images to a compact 128-dimensional Euclidean space where distances directly correspond to face similarity. The model has been pre-trained on a large corpus of face images (CASIA-WebFace / VGGFace2 variants depending on the keras-facenet checkpoint).

`keras-facenet` wraps the FaceNet architecture in a Keras-compatible interface backed by TensorFlow 2.x, allowing the model to run on CPU without a GPU.

The embedding output is a 128-dimensional float32 vector. Before storage and comparison, it is L2-normalized to unit length so that cosine similarity equals the dot product, simplifying the comparison computation.

### Similarity Metric — Cosine Similarity with Decision Bands

Identity comparison uses cosine similarity between the live embedding and the stored embedding. The result is a float in [−1, 1], in practice always positive for valid face comparisons. Three decision zones are applied:

| Zone | Condition | Decision |
|---|---|---|
| Verified | score ≥ threshold | Release stipend |
| Manual Review | score ≥ threshold × 0.85 | Administrator must decide |
| Not Verified | score < threshold × 0.85 | Deny / offer fallback |

The threshold is configurable at runtime via the admin interface without a server restart.

### Liveness Detection — Two-Layer

**Layer 1 — Texture anti-spoofing:** Analyzes the frequency content of the face image to detect characteristics of printed photos or screen displays. Photographs and screens have different texture statistics from real skin. The result is a continuous score (0.0–1.0); the configurable `ANTI_SPOOF_THRESHOLD` determines the pass/fail boundary.

**Layer 2 — MediaPipe head movement challenge:** The client-side `liveness.js` module uses the MediaPipe Face Mesh model (running in the browser) to track 3D facial landmark positions across frames. The user is prompted to perform a random directional head movement (left, right, up, or down). The system measures angular displacement from the neutral position; a displacement exceeding `CHALLENGE_THRESHOLD_DEG` (12 degrees) in the required direction confirms the user is a live, present, cooperating person rather than a static photograph.

Both layers produce independent signals. In assisted rollout mode (`LIVENESS_REQUIRED=False`), failures are recorded in the audit log but do not block face matching. In full enforcement mode (`LIVENESS_REQUIRED=True`), a liveness failure immediately denies the attempt before face matching runs.

### Embedding Storage — Fernet Encryption

Face embeddings are never stored as raw photographs or plaintext vectors. After the 128-d float32 array is computed, it is serialized and encrypted with Fernet (a symmetric authenticated encryption scheme using AES-128-CBC with PKCS7 padding and HMAC-SHA256 authentication). The encrypted bytes are stored in a binary database field.

The encryption key is supplied via the `EMBEDDING_ENCRYPTION_KEY` environment variable. If the key changes between registration and verification, the stored embedding cannot be decrypted and the comparison produces a near-zero score. The key must therefore be stable across server restarts in any deployment that will reuse registered embeddings.

### Database — SQLite / PostgreSQL

SQLite is used by default for development and controlled deployments where a single-server setup is sufficient. For multi-server or high-concurrency deployments, PostgreSQL is supported via the `USE_SQLITE=False` setting and the `DB_*` environment variables. UUID primary keys are used throughout to avoid collision in distributed environments and to prevent enumeration of records by sequential integer IDs.

### Frontend — Bootstrap 5 + Vanilla JavaScript

The UI uses Bootstrap 5 with a custom Quezon City government portal theme (deep blue `#003d99`, government red `#c62828`, gold `#d4a017`). Three client-side JavaScript modules handle the webcam workflow:

- `webcam.js` — camera initialization, 640×480 resolution, burst capture, Laplacian-based sharpness scoring
- `liveness.js` — MediaPipe Face Mesh integration, head movement angle tracking, challenge evaluation
- `verify.js` — orchestrates the full verification flow: liveness check → burst capture → sharpness selection → POST to server

---

## System Architecture

### Application Layer

FANS-C is structured as five Django applications:

```
accounts/          Custom user model (role: staff / admin), login, logout
beneficiaries/     Beneficiary CRUD, lifecycle management, representative management
verification/      Face pipeline, liveness, verification flow, stipend events, config
logs/              AuditLog model and views
fans/              Project settings, root URL configuration
```

### Data Flow — Registration

```
Staff fills form (Step 1-3)
        |
        v
Beneficiary record created (status = Pending)
        |
        v
Staff captures face via webcam
        |
        v
[Client: burst 5 frames → select sharpest by Laplacian variance]
        |
        v
[Server: RetinaFace detect → 4-DOF align → CLAHE → FaceNet 128-d]
        |
        v
Duplicate face check against all stored embeddings (threshold 0.80)
        |
        +-- Duplicate found --> Warn staff, require admin review
        |
        v
Encrypt embedding (Fernet/AES-128) → store in FaceEmbedding table
        |
        v
Admin reviews in Pending Registrations queue → Approve / Reject
        |
        v
Beneficiary status = Active → eligible to claim
```

### Data Flow — Verification

```
Staff searches beneficiary → selects claimant type (Beneficiary / Representative)
        |
        v
[Client: MediaPipe challenge + texture anti-spoof → liveness result]
        |
        v
[Client: burst 5 frames → select sharpest → POST to /verification/submit/]
        |
        v
[Server: liveness check]
        |
        +-- LIVENESS_REQUIRED=True and failed --> Denied (immediate)
        |
        v
[Server: RetinaFace detect → 4-DOF align → CLAHE → FaceNet 128-d embedding]
        |
        v
[Server: decrypt stored embedding(s) → cosine similarity]
        |
        +-- Representative claim: compare against rep's embedding (1 template)
        +-- Beneficiary claim:  compare against all templates, take best score
        |
        v
[Server: decision bands]
        |
        +-- score >= threshold          --> Verified
        |       |
        |       v
        |   Lookalike check (all other beneficiaries within LOOKALIKE_BAND=0.05)
        |       |
        |       +-- Lookalike found --> escalate to Manual Review + AuditLog
        |
        +-- score >= threshold * 0.85  --> Manual Review
        +-- score < threshold * 0.85   --> Not Verified / Denied
        |
        v
VerificationAttempt saved → AuditLog written
        |
        +-- Verified + active StipendEvent --> ClaimRecord created (race guard)
        +-- Not Verified (beneficiary, within retries) --> offer retry
        +-- Not Verified (beneficiary, retries exhausted) --> offer ID Fallback
        +-- Manual Review --> admin review queue
```

### Database Schema (Core Tables)

```
accounts_customuser          Staff and admin accounts (role field)

fans_beneficiaries           Beneficiary personal data, lifecycle status,
                             legacy inline representative fields (maintained for compat)

fans_representatives         Representative records (linked to Beneficiary)
fans_rep_face_embeddings     Encrypted FaceNet embedding for each representative

fans_face_embeddings         Primary encrypted embedding per beneficiary
fans_additional_face_embeds  Extra templates (added via face update workflow)

fans_verification_attempts   Raw attempt log: scores, decision, liveness, threshold, assisted rollout flag
fans_claim_records           Canonical payout record (one per beneficiary per event normally)
fans_stipend_events          Payout calendar with payout windows

fans_manual_verification_req ID-fallback requests awaiting admin approval
fans_face_update_requests    Re-enrollment requests awaiting admin approval
fans_special_claim_requests  Second-claim requests awaiting admin approval

fans_audit_logs              Immutable action log (actor, action, target, IP, timestamp)
fans_system_config           Key-value store for runtime settings (similarity threshold)
```

---

## Core Workflows

### 1. Beneficiary Registration

Registration is a four-step wizard that must be completed in sequence. The beneficiary is held in **Pending** status until an admin approves the registration.

**Step 1 — Personal Information**
- Full name (first, middle, last), date of birth, gender
- Complete Philippine address (province → municipality → barangay via cascading dropdowns)
- Contact number, Senior Citizen ID number, government-issued valid ID type and number
- Server-side age validation: beneficiary must be at least 60 years old

**Step 2 — Representative (optional)**
- Toggle to indicate whether an authorized representative exists
- When enabled, the following fields become required: first name, last name, contact number, ID type (standardized dropdown), and ID number
- Validation is enforced both client-side (HTML `required` attribute toggled by JS) and server-side (form `clean()` method)

**Step 3 — Consent**
- Beneficiary or legal guardian must explicitly consent to biometric data collection under the Data Privacy Act of 2012 (RA 10173)
- Two separate checkboxes: consent to processing, and acknowledgement of the privacy notice
- Registration cannot proceed without both

**Step 4 — Face Capture**
- Staff positions the beneficiary in front of the webcam
- The system captures a burst of frames, selects the sharpest, and runs the full face pipeline
- A quality gate rejects severely blurry or dark captures (blur score < 8) — staff are prompted to retake
- A duplicate face check runs against all stored beneficiary embeddings; if a near-match is found (cosine similarity ≥ 0.80), staff are warned and the record is flagged for admin review
- On success, the 128-d embedding is encrypted and stored; the beneficiary record is created with `status = pending`

**Post-registration**
- An admin reviews the registration in the Pending Registrations section of the Admin Review Queue
- The admin can view the beneficiary's details and approve or reject
- On approval, `status` changes to `active` and the beneficiary becomes eligible to claim
- On rejection, the record is soft-deleted or deactivated with a reason recorded

### 2. Representative Enrollment

A representative is a third party (typically a family member) authorized to collect the stipend on behalf of a beneficiary who cannot be present. Unlike the legacy manual process, FANS-C requires each representative to be biometrically enrolled before they can claim.

**Adding a representative**
1. Open the beneficiary's profile page
2. In the Authorized Representatives card, fill in the representative's details: first name, last name, relationship to beneficiary, contact number, ID type (dropdown), and ID number
3. Submit — the representative record is created and the system immediately redirects to the face capture page for that representative

**Representative face enrollment**
- The same face pipeline runs: burst capture → sharpest frame → RetinaFace → alignment → CLAHE → FaceNet → encrypt
- The encrypted embedding is stored in `fans_rep_face_embeddings`, linked one-to-one to the representative record
- Until this step is complete, the representative cannot be used for any claim — the Verify button will not appear and the system actively blocks attempts

**Key policy constraints**
- Representatives can be added and their faces enrolled even while the beneficiary is in Pending status. Once the beneficiary is approved, the representative is immediately usable
- A representative can be deactivated by admin at any time. Deactivated representatives are blocked from all claim paths regardless of their face data
- Multiple representatives per beneficiary are supported; each gets their own face embedding and appears as a separate Verify button

### 3. Stipend Verification

Verification is the core runtime workflow — the process that determines whether a claimant's face matches their registered biometric data.

**Selecting a beneficiary**
- Staff goes to the Verify page and searches by name, Beneficiary ID, or Senior Citizen ID
- Search returns only Active beneficiaries
- For each result, buttons appear: Verify Beneficiary (beneficiary self-claim) and, for each active representative with face data, Verify [Rep Name]
- Representatives without face data are shown with a warning badge; no Verify button appears for them

**The capture session**
- The selected beneficiary (and representative, if applicable) is loaded with a unique session ID
- The active StipendEvent (if today falls within any payout window) is automatically detected and stored in the session
- A random head movement challenge direction is assigned (left, right, up, or down)
- The client runs liveness checks while the staff member prompts the beneficiary to look at the camera

**Submitting the result**
- The client selects the sharpest frame from the burst and POSTs it to the server along with liveness signals
- The server runs the full verification pipeline (see [Verification Pipeline — Technical](#verification-pipeline--technical))
- The decision is recorded as a `VerificationAttempt`

**Retry and fallback (beneficiaries only)**
- If the first attempt is Not Verified, the system offers a retry (up to `MAX_RETRY_ATTEMPTS`)
- After retries are exhausted, a fallback path is offered: staff check the beneficiary's physical ID in person and submit a `ManualVerificationRequest`
- The manual request is queued for admin approval; only after approval is a ClaimRecord created
- Representatives do not have an ID fallback path — they must pass biometric face verification

### 4. Claim System

A claim represents a completed payout release. The claim system is separate from the verification attempt log to distinguish between the raw attempt record (which includes failed attempts) and the canonical record that a stipend was released.

**Automatic claim creation**
- When a VerificationAttempt results in `decision = verified` and there is an active StipendEvent, a ClaimRecord is automatically created
- A race guard (`ClaimRecord.objects.filter(...).exists()` before creation) prevents duplicate records if concurrent requests arrive
- The ClaimRecord stores: beneficiary, stipend event, claimant type, representative (if applicable), staff member who performed the verification, and a link back to the VerificationAttempt

**Stipend events and payout windows**
- Administrators create StipendEvents with a title, date, and optional payout window (start date → end date)
- If a payout window is defined, claims are accepted on any day within the window, not only on the exact event date
- Two event types are supported: Regular Monthly Stipend (all active beneficiaries eligible) and Birthday Bonus (only beneficiaries born in the event month are eligible)

**Second claims (special claims)**
- Under normal circumstances, each beneficiary can claim once per StipendEvent
- If a second claim is genuinely required (e.g., representative substitution, system error), staff can submit a `SpecialClaimRequest` from the beneficiary profile page
- An admin must approve the request; only then is a second ClaimRecord created with `is_special_additional = True`

### 5. Admin Approval Queue

The Admin Review Queue (`/verification/manual-review/`) consolidates all items requiring administrator action into a single interface. It contains four sections:

**Pending Registrations**
- New beneficiaries submitted by staff, currently in `pending` status
- Admin sees: submission timestamp, beneficiary ID, full name, barangay, and registering staff member
- Admin clicks Review to see full details before approving or rejecting

**Manual Verification Requests**
- Submitted when a beneficiary's face scan fails and the ID fallback path is used
- Admin sees: the similarity score from the failed attempt, liveness result, which ID type was checked, and the staff member's notes
- Approving creates a ClaimRecord; rejecting records a denial with reason

**Face Update Requests**
- Submitted when staff re-enroll a beneficiary's face (due to appearance change, repeated failures, or poor original quality)
- The new encrypted embedding is held in `fans_face_update_requests` until approved
- Admin approves → embedding is applied (either replacing the primary or added as an additional template); admin rejects → the captured data is discarded

**Special Claim Requests**
- Submitted when a second claim on the same event is needed
- Admin reviews the reason before approving or rejecting

All admin decisions are recorded in the AuditLog with actor, timestamp, and any notes provided.

---

## Verification Pipeline — Technical

This section describes the exact sequence of operations from image receipt to decision output.

### 1. Client-Side (Browser)

**Burst capture**
`webcam.js` holds the `MediaStream` from `getUserMedia` at 640×480 resolution. During verification, a burst of 5 JPEG frames is captured at short intervals. Each frame is evaluated for sharpness using a JavaScript implementation of the Laplacian variance method (sum of squared second derivatives of luminance). The frame with the highest variance score — indicating the sharpest edges — is selected for submission. Blurry or motion-affected frames are automatically discarded.

**Liveness evaluation**
`liveness.js` runs MediaPipe Face Mesh in the browser, loading the WASM-backed model locally. The 468 3D facial landmarks are tracked across frames. The angular displacement of the face normal vector from the neutral forward-facing position is computed in the required challenge direction. A displacement exceeding `CHALLENGE_THRESHOLD_DEG` (12 degrees) within the challenge window marks the movement as completed. In parallel, the texture anti-spoofing analysis is applied to a center crop of the face region using frequency-domain statistics.

The client submits:
- `image_data` — base64-encoded JPEG of the selected sharpest frame
- `liveness_passed` — boolean (both layers must pass)
- `liveness_score` — anti-spoof texture score (float)
- `anti_spoof_score` — anti-spoof score (float)
- `challenge_completed` — head movement challenge result (boolean)

### 2. Server-Side (Django View — `verify_submit`)

**Session validation**
The server reads the verification session stored in `request.session`. This session was created by `verify_start` and contains: `beneficiary_id`, `session_id`, `claimant_type`, `attempt_number`, `challenge`, and optionally `representative_id` and `stipend_event_id`. If the session is missing or expired, the submission is rejected.

**Representative resolution**
For representative claims, the representative is fetched from the database with `select_related('face_embedding')`, verifying that `is_active=True` and that the representative belongs to the correct beneficiary. If the representative is not found, deactivated, or has no face data, the attempt is denied immediately before face processing runs.

**Liveness enforcement**
If `LIVENESS_REQUIRED=True` and `liveness_passed=False`, the attempt is immediately recorded as Denied with reason `liveness check failed (strict mode)`. No face matching runs.

**Image decoding**
The base64 image string is decoded to bytes and parsed into a numpy array via OpenCV's `imdecode`.

**Face detection and alignment**
`detect_and_align_face()` runs RetinaFace on the image to obtain five facial landmarks. A 4-DOF similarity transform matrix is computed from the landmark positions to a set of canonical target positions, and `cv2.warpAffine` produces the normalized 112×112 face crop. If no face is detected, the function raises `ValueError`, which is caught and recorded as a denial.

**CLAHE preprocessing**
The aligned face is converted to LAB color space. CLAHE (clip limit 2.0, tile grid 8×8) is applied to the L channel only to avoid distorting hue and saturation. The result is converted back to RGB.

**Embedding generation**
`get_embedding()` passes the preprocessed face through the FaceNet model via keras-facenet's `embeddings()` method. The 128-d output vector is L2-normalized to unit length. If the model is not loaded (mock mode), the function returns a random vector; the server detects `using_mock=True` in the result and records an immediate denial.

**Cosine similarity**
For a beneficiary claim, `compare_with_all_embeddings()` decrypts and compares against the primary `FaceEmbedding` plus all `AdditionalFaceEmbedding` records, returning the best (highest) score and which template matched. For a representative claim, `compare_with_stored()` compares against the single `RepresentativeFaceEmbedding`. Dimension mismatch between live and stored embeddings (e.g., after a model version change) produces an error result with score 0.0 and a diagnostic message.

**Decision bands**
```
review_band = threshold * 0.85

score >= threshold         → VERIFIED
score >= review_band       → MANUAL_REVIEW
score < review_band        → NOT_VERIFIED / DENIED
```

**Lookalike detection (post-pass)**
If the decision is VERIFIED, a secondary check runs against all other beneficiaries. `check_duplicate_face()` is called with `threshold = max(score - LOOKALIKE_BAND, threshold * 0.85)` and `exclude_beneficiary_id` set to the current beneficiary. If any other beneficiary's stored embedding scores above this lookalike threshold, the decision is escalated to MANUAL_REVIEW and an `ACTION_DUPLICATE_FACE` entry is written to the AuditLog with the matched beneficiary's ID, name, and score.

**Saving and responding**
The `VerificationAttempt` record is saved with all collected signals: similarity score, liveness results, anti-spoof score, face quality, threshold used, attempt number, session ID, assisted rollout mode flag, and the final decision and reason string. The response JSON includes the decision and a redirect URL to the result page.

---

## Claim System Design

### Separation of Concerns

FANS-C maintains a strict separation between `VerificationAttempt` and `ClaimRecord`:

- **`VerificationAttempt`** is a raw event record. It is written for every submission, including failed attempts, retries, and denials. It records what happened biometrically: score, liveness, decision, threshold, attempt number. Multiple attempts can exist per beneficiary per day.

- **`ClaimRecord`** is the canonical payout record. It is written only when a stipend is actually released: on a Verified attempt, on an approved ManualVerificationRequest, or on an approved SpecialClaimRequest. Exactly one ClaimRecord per beneficiary per StipendEvent exists under normal circumstances.

This separation ensures that the attempt log provides a complete audit trail of every biometric event while the claim log provides an unambiguous record of what was actually paid out.

### One-Claim-Per-Event Enforcement

Before creating a ClaimRecord, the system checks:

```python
ClaimRecord.objects.filter(
    beneficiary=beneficiary,
    stipend_event=stipend_event,
    status=ClaimRecord.STATUS_CLAIMED,
).exists()
```

If a record already exists, no new ClaimRecord is created, regardless of the verification result. The beneficiary profile page also detects this state and surfaces the Special Claim Request option if a second claim is genuinely needed.

### Claim States

| Status | Meaning |
|---|---|
| `claimed` | Stipend released; canonical completed claim |
| `pending_approval` | Awaiting admin review (manual or special request) |
| `rejected` | Admin rejected the claim request |
| `cancelled` | Claim voided by admin |

### StipendEvent Payout Windows

StipendEvents support a payout window defined by `payout_start_date` and `payout_end_date`. If both are set, claims are accepted on any date within that range. This supports multi-day distribution periods (e.g., a five-day payout window in which different barangays process on different days). If no window is set, only the exact event `date` is matched (single-day event for backward compatibility).

---

## Fraud Prevention Mechanisms

FANS-C implements multiple independent layers of protection against stipend fraud.

### 1. Biometric Identity Verification

The core control: releasing a stipend requires the physical presence of the enrolled face. A cosine similarity threshold of 0.60 (assisted rollout) or 0.75 (full enforcement) means the presented face must closely match the stored embedding. This cannot be bypassed by presenting a different person, a deceased person's ID card, or a photograph (subject to the liveness layer below).

### 2. Two-Layer Liveness Detection

A photograph or video replay of the beneficiary's face is rejected by:
- **Texture anti-spoofing:** printed photos and screen displays have frequency-domain texture statistics that differ from real skin, detected via the anti-spoof score
- **MediaPipe head movement challenge:** a random directional challenge that a static photograph or pre-recorded video cannot pass

In full enforcement mode, failure of either layer immediately denies the attempt before any face matching runs.

### 3. Duplicate Face Detection at Registration

When a new beneficiary is registered, their face embedding is compared against every existing registered beneficiary at a tight threshold (0.80). If a near-match is found, staff are warned and the registration is flagged. This prevents the same person from registering under two different identities to claim twice.

### 4. Lookalike / Twin Detection During Verification

Even when a face passes the primary similarity threshold, the system checks whether any other registered beneficiary also scores within `LOOKALIKE_BAND` (default 0.05) of the matching score. If so, the decision is escalated to Manual Review. Staff must physically confirm the beneficiary's identity with a secondary document before the stipend is released. This case is also written to the AuditLog as `ACTION_DUPLICATE_FACE` for administrator visibility.

### 5. One-Claim-Per-Event Guard

A database-level existence check prevents a beneficiary from claiming twice for the same StipendEvent. Even if two staff members submit simultaneous verification requests for the same beneficiary, only the first to write the ClaimRecord will succeed; the second will find the record already exists and not create another.

### 6. Biometric Representative Requirement

Representatives cannot use a physical ID card to claim on behalf of a beneficiary. Their face must be enrolled in the system and they must pass biometric verification. There is no ID-only fallback path for representatives. This prevents someone from presenting a representative's ID card without that person being physically present.

### 7. Deactivated Representative Blocking

At the point of claim, the system re-queries the representative's `is_active` status from the database, even if the session was established earlier. A representative deactivated after the session was created will be blocked when the submission arrives.

### 8. Admin Approval Queue

Four categories of sensitive actions require explicit admin approval before taking effect:
- New beneficiary registrations (pending queue)
- Face re-enrollment requests (new embedding held until approved)
- ID-fallback manual verification requests
- Second-claim (special claim) requests

This means staff cannot unilaterally register a fraudulent beneficiary, replace an embedding, or release a stipend without biometric confirmation.

### 9. Immutable Audit Trail

Every sensitive action is written to `fans_audit_logs` immediately: login, logout, failed login, registration, verification attempts, overrides, config changes, deactivations, face updates, claims, and duplicate face detections. Each log entry includes the actor's user ID, the action type, the target record ID, a JSON detail blob, the IP address, and the timestamp. Log entries are never deleted or modified by application code.

### 10. Encrypted Embeddings at Rest

Face embeddings are never stored as raw photographs or plaintext numeric vectors. The 128-d float32 array is serialized, then encrypted with AES-128-CBC (Fernet) before being written to the database. An attacker who obtains a database dump cannot extract usable biometric data without the `EMBEDDING_ENCRYPTION_KEY`.

### 11. Admin Override Requires Documentation

When an admin overrides a Manual Review decision, a reason string of at least 20 characters is required. The override is recorded with the admin's identity and timestamp. This prevents undocumented overrides and creates a clear accountability trail.

---

## Edge Cases and System Handling

### Identical or Very Similar Faces (Twins, Lookalikes)

**During registration:** If two people with very similar faces attempt to register, the duplicate face check (threshold 0.80) detects the similarity and warns staff. The registration can still proceed after staff review, but the event is logged.

**During verification:** If a verified score passes the primary threshold but another beneficiary also scores within 0.05 of that score, the decision is automatically escalated to Manual Review. Staff must confirm with ID before releasing. The AuditLog entry records both beneficiary IDs and their scores for the administrator's review.

### Duplicate Registration Attempt

If the same person attempts to register twice, the face captured in the second registration will score ≥ 0.80 against the first registration's stored embedding, triggering the duplicate detection warning. The registering staff member is informed and the record is flagged.

### No Face Detected

If RetinaFace and the OpenCV fallback both fail to detect a face in the submitted frame (e.g., the camera is pointing away, the face is obscured, or the image is too dark), the pipeline raises a `ValueError`. The attempt is recorded as Denied with the reason. Staff can retry.

### Poor Image Quality

A quality check runs after alignment. If the blur score (Laplacian variance) falls below the rejection threshold (< 5 for verification, < 8 for registration), the frame is rejected. At verification time, the client's sharpest-frame selection usually prevents this, but if all burst frames are poor, the quality rejection triggers and staff are prompted to retake.

### Beneficiary Appearance Change

If a beneficiary's appearance changes significantly (illness, significant weight change, or time elapsed), their similarity score may fall below the threshold. Staff can submit a Face Update Request to re-enroll. The new embedding is held for admin approval; once approved, it either replaces the primary embedding or is added as an additional template (which the multi-template comparison considers on all future verifications).

### Encryption Key Change

If the server restarts with a different or absent `EMBEDDING_ENCRYPTION_KEY`, stored embeddings cannot be decrypted and the comparison produces a near-zero score. The system does not crash — it records the attempt as Not Verified with the relevant reason. The fix is to set a stable key in `.env` before registering any beneficiaries and never change it thereafter.

### Multiple Retries Exhausted

The `attempt_number` field tracks how many attempts have been made in the current session. Once the count reaches `MAX_RETRY_ATTEMPTS`, the system stops offering a retry option and instead presents the ID fallback path (for beneficiaries) or a clear denial message (for representatives). Each attempt is independently logged.

### Representative Has No Face Data

If a representative is added but their face has not been captured yet, the Verify button for that representative does not appear in the Verify search results. If staff manually construct a URL with the representative's `rep_id` parameter, the `verify_start` view detects the missing face data and redirects to the face registration page for that representative.

### Deactivated Representative During Active Session

A representative's status is re-validated at submission time (`verify_submit`), not only at session creation (`verify_start`). If the representative is deactivated after the session is established but before submission arrives, the submission is rejected and recorded as Denied.

### Birthday Bonus Eligibility

When a Birthday Bonus StipendEvent is active, the `verify_start` view checks whether the beneficiary's birth month matches the event month. If it does not match, the beneficiary is blocked from that event with a clear error message and redirected to the Verify page. This check runs before liveness or face matching.

### Already Claimed for Active Event

If a beneficiary has already claimed for the current StipendEvent, the `verify_start` view detects the existing ClaimRecord and redirects to the beneficiary profile with a warning message. The Special Claim Request option is surfaced if a second claim is genuinely needed. Staff cannot accidentally process a double payment by running the verification flow again.

### Pending Beneficiary Attempting to Claim

`verify_start` checks `beneficiary.is_eligible_to_claim` before proceeding. Pending, Inactive, and Deceased beneficiaries all fail this check. The system redirects to the Verify page with a clear status message. Face registration for representatives can still be performed while a beneficiary is pending, so the setup work is not blocked.

---

## Deployment Readiness

FANS-C is designed for two operational tiers that can be toggled entirely through environment variables without any code changes.

### Tier 1 — Assisted Rollout (Current Configuration)

Suitable for: controlled evaluation, supervised deployment, staff training, and demonstration.

```
DEMO_MODE=True          # Accommodating threshold (0.60); liveness non-blocking
LIVENESS_REQUIRED=False # Liveness recorded but does not deny claims
DEBUG=True              # Detailed error pages visible to staff
USE_SQLITE=True         # File-based database, no database server required
```

In this configuration the system performs real biometric verification using FaceNet. The lower similarity threshold (0.60) accommodates consumer webcam quality and variable lighting typical of a barangay office environment. Liveness failures are recorded and visible in the audit log, allowing administrators to monitor results, but they do not block the payout. This lets operations begin before the environment is fully optimized.

### Tier 2 — Full Production Enforcement

Suitable for: unassisted operation, high-volume deployment, or when fraud risk warrants strict controls.

```
DEMO_MODE=False             # Strict threshold (0.75); liveness blocking
LIVENESS_REQUIRED=True      # Liveness failure immediately denies the attempt
DEBUG=False                 # No debug pages visible to staff
USE_SQLITE=False            # PostgreSQL for concurrent access and durability
EMBEDDING_ENCRYPTION_KEY=<stable 32-byte Fernet key>
```

### Hardening Checklist for Full Production

| Step | Action |
|---|---|
| Generate stable encryption key | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` → paste into `.env` as `EMBEDDING_ENCRYPTION_KEY` |
| Set `DEBUG=False` | Prevents stack traces from being shown to users |
| Switch to PostgreSQL | Set `USE_SQLITE=False` and configure `DB_*` variables |
| Enable strict liveness | Set `LIVENESS_REQUIRED=True` |
| Enforce strict threshold | Set `DEMO_MODE=False`, tune `VERIFICATION_THRESHOLD` for the specific hardware |
| Serve static files | Configure Nginx or WhiteNoise to serve `static/` and `media/` |
| Set `SECRET_KEY` | Replace the placeholder with a securely generated 50+ character random string |
| Enable HTTPS | Configure SSL/TLS termination on the reverse proxy |
| Calibrate threshold | Run a set of test verifications with enrolled beneficiaries to find the optimal threshold for the specific webcam and lighting environment. Use the admin Threshold Configuration page to adjust live |

### Threshold Calibration Guidance

The similarity threshold is the most environment-sensitive parameter. Guidelines:

| Threshold | Behavior | When to use |
|---|---|---|
| 0.55 – 0.65 | Lenient; lower false rejects, higher false accept risk | Assisted rollout with variable webcam quality |
| 0.70 – 0.75 | Balanced; recommended starting point for production | Well-lit, consistent webcam setup |
| 0.80+ | Strict; very low false accepts, higher false reject risk | High-confidence hardware, re-enrolled under controlled conditions |

The admin Threshold Configuration page (`/verification/config/`) shows the active threshold and the current decision reference guide (Verified / Manual Review / Not Verified bands) in real time.

---

## Installation Guide (Windows)

### Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.11** | Python 3.12 and 3.13 are NOT supported by TensorFlow 2.13.x. [Download Python 3.11.9](https://www.python.org/downloads/release/python-3119/) |
| **Short project path** | Use `C:\FANSC` or `D:\FANS`. Paths longer than ~80 characters can cause TensorFlow install failures on Windows. |
| **PowerShell 5.1+** | Included with Windows 10/11. Right-click Start → "Windows PowerShell". |

---

### Quickstart (Recommended) — One-Command Setup

Copy or clone the project to a short path (e.g., `D:\FANS\fans-c`), then open PowerShell in that folder and run:

```powershell
# Allow the setup script to run (one-time)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Run the full automated setup
.\setup.ps1
```

`setup.ps1` handles everything automatically:

1. Checks Python 3.11
2. Warns if the project path is too long
3. Creates `.venv` virtual environment
4. Upgrades pip
5. Installs `numpy==1.24.3` first (required before TensorFlow)
6. Installs `tensorflow-cpu==2.13.1`
7. Installs all remaining dependencies from `requirements.txt`
8. Creates `.env` from `.env.example`
9. Generates and writes `SECRET_KEY` automatically
10. Generates and writes `EMBEDDING_ENCRYPTION_KEY` automatically
11. Runs all database migrations
12. Initialises system configuration
13. Creates the default admin user (`admin` / `Admin@1234`)
14. Collects static files
15. Runs a system health check

**After setup, start the server with:**

```powershell
.\run.ps1
```

Then open: `http://127.0.0.1:8000/`

**Change the default admin password immediately after first login.**

---

### Manual Setup (Alternative)

If you prefer not to use the PowerShell scripts:

```powershell
# 1. Create and activate virtual environment (must use Python 3.11)
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Upgrade pip
python -m pip install --upgrade pip

# 3. Install numpy FIRST (must precede tensorflow and scipy)
pip install numpy==1.24.3

# 4. Install tensorflow-cpu
pip install tensorflow-cpu==2.13.1

# 5. Install remaining dependencies
pip install -r requirements.txt

# 6. Create .env from template
Copy-Item .env.example .env
# Edit .env — set SECRET_KEY and generate EMBEDDING_ENCRYPTION_KEY:
python manage.py generate_key   # copy the output into .env

# 7. Run migrations
python manage.py migrate

# 8. Initialise system config
python manage.py init_config

# 9. Create admin user
python manage.py create_admin

# 10. Collect static files
python manage.py collectstatic --noinput

# 11. Start server
python manage.py runserver
```

---

### Setting Up on Another Device

1. Copy the project folder to the new device (to a short path, e.g., `C:\FANSC`).
2. **Copy your `.env` file** from the original device — it contains the `EMBEDDING_ENCRYPTION_KEY` that all stored face embeddings depend on.
3. Open PowerShell in the project root and run:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   .\setup.ps1 -SkipAdminCreate
   ```
   (`-SkipAdminCreate` skips creating a second admin since users are already in the database.)
4. Start with `.\run.ps1`.

> **Critical:** If the `EMBEDDING_ENCRYPTION_KEY` is different from the original device, all registered face embeddings will be unreadable. Always transfer the entire `.env` file — never re-generate the key on a second device.

---

### Verifying the Installation

Run the health check at any time:

```powershell
.\.venv\Scripts\python.exe manage.py check_system
```

This checks: Python version, TensorFlow, keras-facenet, OpenCV, scipy, numpy, encryption key validity, database connection, and pending migrations.

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
2. Select who is claiming: **Beneficiary** (face scan) or **Representative** (biometric face scan — one button per active enrolled representative).
3. If claiming as beneficiary:
   - Liveness check runs (texture + head movement challenge).
   - A burst of 5 frames is captured; the sharpest is submitted for face matching.
   - Result: **Verified**, **Manual Review**, or **Not Verified**.
   - After one failed retry, the system offers an ID Fallback path (beneficiaries only).
4. If claiming as representative:
   - The same liveness check and FaceNet face matching runs — but against the representative's enrolled face, not the beneficiary's.
   - ID-only verification is **blocked** for representatives; they must pass biometric face verification.
   - Deactivated representatives are blocked from claiming.
5. Result is recorded and linked to the active stipend event. The claim record stores which representative performed the claim.

### Stipend Events

Administrators create stipend events (payout periods) under **Admin > Stipend Schedule**. Each event has:
- **Title** — display name shown on the result page and in claim records
- **Date** — primary payout date
- **Event type** — Regular Monthly Stipend or Birthday Bonus
- **Payout window** (optional) — if set, claims are accepted on any date within the window, not only on the exact date

### Admin Override

When a verification result is **Manual Review**, administrators can apply an override with a documented reason (minimum 20 characters). All overrides are logged with the actor, timestamp, and reason.

### Face Update (Re-enrollment)

When a beneficiary's appearance changes significantly:
1. Go to the beneficiary's profile and click **Update Face Data**.
2. Select the reason (repeated failure, appearance change, poor original, staff decision) and action (replace primary or add as additional template).
3. Capture the new face.
4. A Face Update Request is created and queued for admin approval.
5. On approval, the new embedding is applied.

---

## Configuration Reference

**Core settings:**

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | — | Django secret key. Must be a long random string. Never commit to version control. Auto-generated by `setup.ps1`. |
| `DEBUG` | `True` | Django debug mode. Set to `False` in production. |
| `USE_SQLITE` | `True` | Use SQLite. Set to `False` and configure `DB_*` vars for PostgreSQL. |
| `EMBEDDING_ENCRYPTION_KEY` | — | Fernet key for embedding encryption. **Required.** Auto-generated by `setup.ps1`. Back up securely. |
| `DEMO_MODE` | `True` | Assisted Rollout Mode — uses `DEMO_THRESHOLD` (0.60) and makes liveness non-blocking. Set to `False` for full strict enforcement. |
| `LIVENESS_REQUIRED` | `False` | If `True`, liveness failure blocks verification entirely. Set `False` for Assisted Rollout Mode. |
| `VERIFICATION_THRESHOLD` | `0.75` | Cosine similarity threshold for strict enforcement mode (`DEMO_MODE=False`). |
| `DEMO_THRESHOLD` | `0.60` | Threshold used in Assisted Rollout Mode — accommodates webcam quality variation during rollout. |
| `ANTI_SPOOF_THRESHOLD` | `0.15` | Texture anti-spoofing threshold (0.0–1.0). Lower = more permissive. Raise to 0.30–0.50 in strict production. |
| `MAX_RETRY_ATTEMPTS` | `2` | Number of face verification retries before the ID fallback path is offered. |

**Offline sync settings:**

| Variable | Default | Description |
|---|---|---|
| `SYNC_API_URL` | _(empty)_ | Central server API base URL. Leave blank for offline-only / standalone operation. |
| `SYNC_API_KEY` | _(empty)_ | Bearer token for the central server. Keep secret. |
| `SYNC_TIMEOUT` | `30` | HTTP timeout in seconds for each sync request. |
| `SYNC_BATCH_SIZE` | `50` | Maximum records sent per sync run. |

**Database variables (PostgreSQL only):**

| Variable | Description |
|---|---|
| `DB_NAME` | Database name |
| `DB_USER` | Database user |
| `DB_PASSWORD` | Database password |
| `DB_HOST` | Database host (default: `localhost`) |
| `DB_PORT` | Database port (default: `5432`) |

**Full production `.env` example:**

```
SECRET_KEY=<50+ char random string>
DEBUG=False
USE_SQLITE=False
DB_NAME=fans_db
DB_USER=fans_user
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432
EMBEDDING_ENCRYPTION_KEY=<Fernet key from Fernet.generate_key()>
DEMO_MODE=False
LIVENESS_REQUIRED=True
VERIFICATION_THRESHOLD=0.75
DEMO_THRESHOLD=0.60
ANTI_SPOOF_THRESHOLD=0.15
MAX_RETRY_ATTEMPTS=2
```

---

## Assisted Rollout Mode

### What Is It?

Assisted Rollout Mode (`DEMO_MODE=True`, `LIVENESS_REQUIRED=False`) is a deliberately lenient configuration designed for the **initial deployment phase** of the system. It allows the system to serve real users without blocking legitimate seniors who fail the liveness challenge — which can happen due to webcam quality, lighting, or age-related limited head movement.

### Why It Exists

When deploying a biometric system for the first time:
- False negatives (blocking a real person) have high social cost — a senior citizen denied their stipend.
- Liveness detection accuracy depends heavily on the specific webcam, lighting, and facial features of the population.
- Collecting real-world data in permissive mode builds the evidence needed to calibrate thresholds and liveness enforcement confidently before strict enforcement begins.

### What It Does

| Setting | Assisted Rollout Mode | Strict Mode |
|---|---|---|
| `DEMO_MODE` | `True` | `False` |
| `LIVENESS_REQUIRED` | `False` | `True` |
| Similarity threshold | 0.60 (`DEMO_THRESHOLD`) | 0.75 (`VERIFICATION_THRESHOLD`) |
| Liveness failure | Logged, **does not block** verification | **Blocks** verification (denied) |
| UI badge | "ASSISTED" shown on result | No badge |

### UI Display

When Assisted Rollout Mode is active:
- The verification result screen shows an **"ASSISTED"** badge next to the decision.
- The Threshold Configuration page shows the mode clearly under "Assisted Rollout Mode".
- The liveness section of the config page shows "Assisted Rollout — non-blocking (logged only)".

### Audit and Logging

Every verification attempt records:
- `liveness_score` — combined texture + challenge score (0–1)
- `liveness_passed` — whether the check technically passed
- `anti_spoof_score` — texture analysis score
- `demo_mode_active` — whether Assisted Rollout Mode was active at the time

These fields are always populated, regardless of mode. The mode flag allows retrospective analysis of data collected during rollout.

### Threshold Configuration

Thresholds are controlled by `.env` variables:
- `DEMO_THRESHOLD=0.60` — threshold used in Assisted Rollout Mode (adjustable 0.50–0.70)
- `VERIFICATION_THRESHOLD=0.75` — threshold used in strict mode (adjustable 0.70–0.85)
- `ANTI_SPOOF_THRESHOLD=0.15` — texture score required to pass liveness (adjustable)

Administrators can also adjust the active threshold live via **Admin > Threshold Configuration** without restarting the server.

### Transition to Strict Mode

Transition from Assisted Rollout Mode to strict enforcement when:
1. You have at least 2–4 weeks of real verification data.
2. The false negative rate (real people being denied) is consistently below 5%.
3. The anti-spoofing score distribution shows clear separation between real and spoofed faces.

**Steps to enable strict mode:**

```
# In .env:
DEMO_MODE=False
LIVENESS_REQUIRED=True
VERIFICATION_THRESHOLD=0.75   # adjust based on observed score distribution
ANTI_SPOOF_THRESHOLD=0.25     # raise if webcam quality is reliable
```

Restart the server after changing these values. Monitor the verification logs for the first week to catch any unexpected denials.

### Risks of Keeping Assisted Rollout Mode Indefinitely

- The lower threshold (0.60 vs 0.75) slightly increases the risk of a face match false accept.
- Liveness is not enforced, so a determined attacker with a high-quality printed photo could potentially pass anti-spoofing if the printed texture score is above 0.15.
- Recommended maximum duration in Assisted Rollout Mode: 60 days from first live deployment.

### Error Handling

Liveness detection failures never crash the system. If liveness detection encounters an unexpected error:
- The error is logged to the server console.
- The verification continues with `liveness_passed=False` and `liveness_score=0.0`.
- In Assisted Rollout Mode, the verification is not blocked.
- In strict mode, the attempt is denied with reason "Liveness check error."

---

## Offline-First Operation and Sync

### How It Works

The system operates fully offline — no internet connection is required for:
- Beneficiary registration
- Face capture and embedding storage
- Stipend claim verification
- Audit logging

All data is stored locally in SQLite. Each beneficiary record has an `is_synced` field (default: `False`) that tracks whether the record has been sent to the central server.

### Enabling Sync

Configure the central server endpoint in `.env`:

```
SYNC_API_URL=https://central.fans-c.gov.ph/api
SYNC_API_KEY=your-secret-bearer-token
SYNC_TIMEOUT=30
SYNC_BATCH_SIZE=50
```

### Running Sync

**Automatically:** `run.ps1` triggers a background sync on every server start (if `SYNC_API_URL` is configured).

**Manually:**
```powershell
.\.venv\Scripts\python.exe manage.py sync_beneficiaries
.\.venv\Scripts\python.exe manage.py sync_beneficiaries --force    # skip connectivity check
.\.venv\Scripts\python.exe manage.py sync_beneficiaries --batch 100
```

**Programmatically:**
```python
from beneficiaries.sync import is_online, sync_all

if is_online():
    result = sync_all()
    print(result)  # {'synced': 5, 'failed': 0, 'skipped': 0}
```

### Retry Logic

- Failed sync attempts are not marked as synced; they remain `is_synced=False`.
- The error message is stored in `sync_error` on the record.
- The next sync run retries all failed records automatically.
- Records are retried indefinitely until they succeed (or are manually resolved).

### Encryption Key Sharing

The `EMBEDDING_ENCRYPTION_KEY` encrypts face embeddings **before** they leave this device. The central server must use the **same key** to decrypt and use the received embeddings.

**Transfer procedure:**
1. Copy the `.env` file from the source device to the central server (or all workstations).
2. Do NOT re-generate the key — all existing embeddings will become unreadable.
3. Transfer via USB or encrypted channel — never plain email.

### Conflict Prevention

Records use UUIDs as primary keys. The central API should treat a duplicate UUID as an upsert (update) rather than an error. This prevents duplicate records when a record is re-sent after a partial network failure.

The `beneficiary_id` field (e.g., `BEN-2025-00001`) is also unique and can be used for cross-device deduplication.

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

**Difference between Assisted Rollout Mode and Mock Model:**

| Setting | Effect |
|---|---|
| `DEMO_MODE=True` (Assisted Rollout) | Accommodating threshold (0.60), liveness recorded but non-blocking. Real FaceNet matching runs normally. |
| `DEMO_MODE=False` (Full Enforcement) | Strict threshold (0.75), liveness enforced. Intended for full production rollout. |
| Mock model active | keras-facenet failed to load. All similarity scores are random. No real matching. |

Assisted Rollout Mode and mock model are independent. The correct configuration for a controlled deployment or supervised evaluation is `DEMO_MODE=True` with the real FaceNet model loaded. This produces real biometric verification results with a threshold calibrated for the evaluation environment.

---

## Limitations and Known Constraints

- **Lighting and angle consistency.** Registration and verification should be performed under similar lighting conditions. Strong backlight, very dim environments, or large pose changes reduce matching accuracy. Recommended: a controlled capture station with consistent front lighting.

- **Threshold requires site-specific calibration.** The default thresholds (0.75 full enforcement, 0.60 assisted rollout) are validated starting points. The optimal value depends on the specific camera hardware and deployment environment. The admin Threshold Configuration page allows live adjustment without a code change.

- **Pre-trained model without local fine-tuning.** The system uses a pre-trained FaceNet model. For a full production deployment, fine-tuning on a locally collected dataset would improve accuracy in barangay-specific conditions.

- **Liveness detection is heuristic.** The two-layer liveness check (texture anti-spoofing + MediaPipe head movement challenge) is effective against casual fraud. It is not engineered to resist sophisticated adversarial attacks such as high-quality video replay, which would require a trained liveness model.

- **Single primary face template per person.** Each beneficiary has one primary FaceEmbedding. If appearance changes significantly, re-registration is required. The face update workflow supports adding additional templates to mitigate this, but multi-template support is not yet exposed at registration time.

- **No multi-face handling.** The system uses the highest-confidence detected face only. Staff should ensure only the claimant is in frame during verification.

- **Eyeglasses consistency.** If a beneficiary wears glasses during registration, they should wear them during verification as well for consistent embeddings.

- **Single-server deployment assumed.** The current architecture uses a single `SystemConfig` record for the threshold. For multi-server deployments behind a load balancer, PostgreSQL and a cache layer would be required to keep the threshold consistent across instances.

- **Client-side liveness can be bypassed technically.** Liveness signals (`liveness_passed`, `challenge_completed`) are submitted by the client and trusted by the server. A technically capable attacker who can intercept and modify the HTTP request could submit `liveness_passed=True` regardless of the actual video. Fully server-side liveness evaluation would require streaming the video frames to the server rather than just the final image. This is a known limitation of browser-based liveness systems.

---

## Future Improvements

- **Server-side liveness verification.** Move challenge evaluation to the server by streaming landmark coordinates rather than trusting the client boolean. Eliminates the client-side bypass vector.

- **Trained anti-spoofing model.** Replace the heuristic texture analysis with a trained liveness model (e.g., Silent-Face-Anti-Spoofing) for better resistance to photo and video replay attacks.

- **Threshold calibration tool.** Build an admin interface that tests candidate threshold values against a labeled set of successful registrations and produces a recommended cutoff with estimated false-accept and false-reject rates for the specific hardware.

- **Multi-template support at registration.** Allow capture of 2–3 enrollment frames per beneficiary (e.g., frontal, slight left, slight right) to improve matching robustness across pose variation.

- **Mobile capture support.** Allow face capture from a mobile device camera via QR code session linking, for deployments where a laptop webcam is not available.

- **Periodic re-enrollment reminders.** Flag beneficiaries whose face embedding is older than a configurable threshold (e.g., 2 years) for re-registration, accounting for age-related appearance change.

- **Replace or supplement RetinaFace.** Evaluate more robust face detectors optimized for low-light and off-axis conditions (e.g., InsightFace's SCRFD) for environments where lighting control is not possible.

- **PostgreSQL migration and multi-server support.** Cache the `SystemConfig` threshold in Redis for zero-latency reads across multiple application instances.

- **Performance optimization.** Profile and reduce inference time on CPU-only hardware, using model quantization (TensorFlow Lite) or a lighter embedding model (e.g., MobileFaceNet) for low-end deployment machines.

---

## Project Structure

```
fans/                       Django project settings and root URL configuration
accounts/                   Custom user model (role: admin/staff), login/logout views
beneficiaries/              Beneficiary registration, list, edit, lifecycle management,
                            representative management
verification/               Face pipeline, liveness module, verification views,
                            fallback, override, stipend events, threshold config
  face_utils.py             Core face processing: detect, align, CLAHE, embed, compare, dedup
  liveness.py               Server-side liveness scoring (texture anti-spoof)
  models.py                 All verification models (see schema above)
  views.py                  All verification views: select, start, submit, result,
                            fallback, override, config, stipend CRUD, approval actions
logs/                       AuditLog model and views (verification log, audit log)
templates/
  base.html                 Base layout: QC navbar, flash messages, footer
  beneficiaries/            Registration steps, detail, list, edit, deactivate
  verification/             Capture, result, config, manual review, stipend list,
                            register_rep_face, update_face
  logs/                     Verification logs, audit logs
static/
  css/main.css              QC government portal theme (blue #003d99, red #c62828, gold #d4a017)
  js/
    webcam.js               Camera utility: 640×480, burst capture, Laplacian sharpness
    liveness.js             MediaPipe Face Mesh head movement tracking
    verify.js               Verification flow controller: liveness → capture → submit
    register.js             Registration face capture controller
    address_cascades.js     Province/municipality/barangay cascading dropdowns
  data/
    ph_addresses.json       Philippine address data (all NCR cities, QC 131+ barangays)
  img/
    Quezon_City.svg.png     Official Quezon City logo (used in navbar)
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
| beneficiaries | 0004 | profile_picture field on Beneficiary |
| beneficiaries | 0005 | Representative model (fans_representatives) |
| beneficiaries | 0006 | Offline sync fields: is_synced, sync_error, last_synced_at |
| logs | 0001 | AuditLog model |
| logs | 0002 | Add 'update' action choice for record edits |
| verification | 0001 | FaceEmbedding, VerificationAttempt, SystemConfig |
| verification | 0002 | claimant_type, decision_reason on VerificationAttempt |
| verification | 0003 | StipendEvent model, stipend_event FK, face_quality_score |
| verification | 0004 | StipendEvent.event_type (regular / birthday_bonus) |
| verification | 0005 | VerificationAttempt.demo_mode_active, AdditionalFaceEmbedding, FaceUpdateLog |
| verification | 0006 | FaceUpdateRequest (pending re-enrollment approval) |
| verification | 0007 | ManualVerificationRequest |
| verification | 0008 | ClaimRecord, SpecialClaimRequest |
| verification | 0009 | VerificationAttempt.representative FK |
| verification | 0010 | StipendEvent payout_start_date / payout_end_date |
| verification | 0011 | profile_picture on Beneficiary |
| verification | 0012 | ClaimRecord.representative FK |

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

### EMBEDDING_ENCRYPTION_KEY must be stable

If the key is left blank, a temporary key is generated each time the server starts. Any embeddings registered in a previous server session will be unreadable after a restart, producing near-zero similarity scores. Always set a stable key before registering any beneficiaries for real use.

---

## Troubleshooting

### setup.ps1 says "running scripts is disabled"

**Symptom:**
```
.\setup.ps1 cannot be loaded because running scripts is disabled on this system.
```

**Fix:** Run this once in PowerShell (no admin required):
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Then retry `.\setup.ps1`.

---

### DLL load failure when importing TensorFlow

**Symptom:**
```
DLL load failed while importing _pywrap_tensorflow_lite_metrics_wrapper: The specified procedure could not be found.
```

**Cause:** Python version mismatch. The venv was created with Python 3.12 or 3.13.

**Fix (using setup.ps1):**
```powershell
Remove-Item -Recurse -Force .venv
.\setup.ps1
```

**Fix (manual):**
1. Delete the `.venv` folder.
2. Install Python 3.11 from python.org.
3. Confirm: `py -3.11 --version`
4. Recreate the venv: `py -3.11 -m venv .venv`
5. Activate and reinstall using the correct order:
   ```powershell
   .venv\Scripts\Activate.ps1
   pip install numpy==1.24.3
   pip install tensorflow-cpu==2.13.1
   pip install -r requirements.txt
   ```

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
```powershell
pip install numpy==1.24.3
```
TensorFlow 2.13 requires numpy < 2.0. The pinned version `numpy==1.24.3` in `requirements.txt` is the correct version.

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

**Fix:** Delete the `.venv` folder and re-run setup from the new location:
```powershell
Remove-Item -Recurse -Force .venv
.\setup.ps1
```
Or manually:
```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install numpy==1.24.3
pip install tensorflow-cpu==2.13.1
pip install -r requirements.txt
```

---

### Verification scores are very low (e.g., 0.05) for the correct person

**Possible causes:**

1. **Encryption key changed between registration and verification.** If `EMBEDDING_ENCRYPTION_KEY` was blank and the server restarted, the stored embedding cannot be decrypted. Set a stable key in `.env` first, then re-register the beneficiary.
2. **Lighting difference.** Register and verify under the same lighting conditions. Strong backlight or very dim lighting degrades embedding quality.
3. **Face too far from camera.** Keep the face 30–50 cm from the lens.
4. **Threshold needs calibration.** Lower `DEMO_THRESHOLD` in `.env` (e.g., to 0.50) and re-test. Use the admin Threshold Configuration page to adjust live without a restart.

---

### Model status shows MOCK — not loaded

**Cause:** keras-facenet or TensorFlow failed to load. The system falls back to a mock model that returns random scores.

**Fix:** Confirm dependencies are installed and that Python 3.11 is in use:
```
python -c "import keras_facenet; print('OK')"
python -c "import tensorflow as tf; print(tf.__version__)"
```
If either fails, resolve the error (see DLL, scipy, or numpy sections above), then restart the server.

---

### Unapplied migrations warning

If you see `Your models in app(s) have changes that are not yet reflected in a migration`, run:

```
python manage.py migrate
```

All migrations are included in the repository. Running `makemigrations` is not needed unless you add new model fields yourself.
