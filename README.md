# FANS-C: A Secure FaceNet-Based Facial Verification System for Senior Citizen Stipend Distribution

> **A functional biometric identity verification system ready for real-world use in a controlled barangay setting — built for senior citizen stipend distribution in Quezon City.**
> Developed as a capstone project for deployment in controlled government environments.

---

## Quick Access

| Guide | Audience |
|---|---|
| [Developer Setup](SETUP.md) | Developers setting up the system on a new machine |
| [Client Access Guide](CLIENT_ACCESS.md) | Barangay staff accessing the system from a browser |
| Full Documentation | This README |

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
15. [Risk-Based Verification Flow](#risk-based-verification-flow)
16. [Assisted Rollout Mode](#assisted-rollout-mode)
17. [Offline-First Operation and Sync](#offline-first-operation-and-sync)
18. [Limitations and Known Constraints](#limitations-and-known-constraints)
19. [Future Improvements](#future-improvements)
20. [Project Structure](#project-structure)
21. [Migrations Reference](#migrations-reference)
22. [Critical Notes](#critical-notes)
23. [Troubleshooting](#troubleshooting)
24. [Centralized Deployment Architecture](#centralized-deployment-architecture)
    - [Architecture Overview](#architecture-overview)
    - [Why Centralized, Not Separate Local Databases](#why-centralized-not-separate-local-databases)
    - [Deployment Modes Compared](#deployment-modes-compared)
    - [Setting Up Centralized Deployment](#setting-up-centralized-deployment)
    - [Reverse Proxy with nginx](#reverse-proxy-with-nginx)
    - [Offline Sync as Fallback](#offline-sync-as-fallback)
    - [Defense-Ready Architecture Explanation](#defense-ready-architecture-explanation)
25. [Barangay LAN Deployment Guide](#barangay-lan-deployment-guide)
    - [Why This Architecture Fits a Barangay](#why-this-architecture-fits-a-barangay)
    - [Recommended Setup for a Barangay Office](#recommended-setup-for-a-barangay-office)
    - [Step-by-Step: Setting Up the Central Server](#step-by-step-setting-up-the-central-server)
    - [Client Device Access](#client-device-access)
    - [Local Network Access Flow](#local-network-access-flow)
    - [Offline Fallback Behavior](#offline-fallback-behavior)
    - [Admin Account Creation](#admin-account-creation)
    - [Security Notes](#security-notes)
    - [Backup and Maintenance](#backup-and-maintenance)
    - [Development vs Production Mode](#development-vs-production-mode)
    - [Defense Notes: Why Centralized LAN](#defense-notes-why-centralized-lan-is-the-right-architecture)
26. [LAN vs Internet: What the System Actually Needs](#lan-vs-internet-what-the-system-actually-needs)
27. [Secure HTTPS LAN Deployment](#secure-https-lan-deployment)
    - [Why HTTPS Is Required for Camera Access](#why-https-is-required-for-camera-access)
    - [Recommended Stack: Waitress + Caddy](#recommended-stack-waitress--caddy)
    - [How Requests Flow](#how-requests-flow)
    - [Why fans-barangay.local Instead of a Raw IP](#why-fans-barangaylocal-instead-of-a-raw-ip)
    - [Step-by-Step: Secure Windows LAN Deployment](#step-by-step-secure-windows-lan-deployment)
    - [Hostname Resolution: fans-barangay.local](#hostname-resolution-fans-barangaylocal)
    - [Django Settings for HTTPS Behind Caddy](#django-settings-for-https-behind-caddy)
    - [Verifying Camera Access from a Client Device](#verifying-camera-access-from-a-client-device)
    - [Insecure Browser Flags Are Not the Answer](#insecure-browser-flags-are-not-the-answer)
    - [Security Notes for HTTPS Deployment](#security-notes-for-https-deployment)
    - [Defense Notes: Why This Stack](#defense-notes-why-this-stack)
28. [Windows .exe Packaging and Distribution](#windows-exe-packaging-and-distribution)
    - [Overview](#packaging-overview)
    - [How the Launcher Works](#how-the-launcher-works)
    - [Files Added for Packaging](#files-added-for-packaging)
    - [Build Prerequisites](#build-prerequisites)
    - [Step 1 — Build the .exe](#step-1--build-the-exe)
    - [Step 2 — Test the Packaged App](#step-2--test-the-packaged-app)
    - [Step 3 — Build the Installer](#step-3--build-the-installer)
    - [Step 4 — Distribute to Another Machine](#step-4--distribute-to-another-machine)
    - [What Is and Is Not Bundled](#what-is-and-is-not-bundled)
    - [Keras-FaceNet Model Weights](#keras-facenet-model-weights)
    - [onedir vs onefile](#onedir-vs-onefile)
    - [TensorFlow and PyInstaller Caveats](#tensorflow-and-pyinstaller-caveats)
    - [Common Packaging Problems and Fixes](#common-packaging-problems-and-fixes)
    - [Limitations of the Packaged Version](#limitations-of-the-packaged-version)

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
- Risk-based liveness detection: server-side texture anti-spoofing runs on every attempt; the visible head-movement challenge is shown only when a risk condition is detected (low anti-spoof score, poor image quality, representative claim, or retry attempt)
- Burst capture (7 frames, sharpest selected by Laplacian variance) for reliable frame quality
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

### Liveness Detection — Risk-Based Two-Layer

**Layer 1 — Texture anti-spoofing (always runs):** After the staff clicks "Capture & Verify", the server immediately runs a texture analysis on the captured frame using Laplacian variance, local variance (LBP proxy), and Sobel edge density. Photographs and screens have different frequency-domain statistics from real skin. The result is a continuous score (0.0–1.0); the configurable `ANTI_SPOOF_THRESHOLD` determines the pass/fail boundary. This runs on every attempt and is always logged.

**Layer 2 — MediaPipe head movement challenge (risk-triggered):** The visible challenge is only shown when a risk condition is detected:
- Anti-spoof score is below 0.30 (suspicious texture — possible photo/screen)
- Face quality check failed (poor lighting, blur, or glare)
- Claimant is a representative (always required — higher-risk third-party claim)
- This is a retry attempt (previous face match failed — escalate security)

When triggered, `liveness.js` uses MediaPipe Face Mesh in the browser to measure angular head displacement. A displacement exceeding 12 degrees in the required direction (left/right/up/down) confirms the user is live. A 5-second timer auto-accepts for senior citizens with limited mobility.

For normal beneficiary self-claims where the anti-spoof score is acceptable and quality is good, the challenge is skipped entirely. The UX is simply: Align Face → Capture → Processing → Result.

Both layers produce independent signals. In Assisted Rollout Mode (`LIVENESS_REQUIRED=False`), failures are recorded in the audit log but do not block face matching. In strict mode (`LIVENESS_REQUIRED=True`), a liveness failure immediately denies the attempt before face matching runs.

### Embedding Storage — Fernet Encryption

Face embeddings are never stored as raw photographs or plaintext vectors. After the 128-d float32 array is computed, it is serialized and encrypted with Fernet (a symmetric authenticated encryption scheme using AES-128-CBC with PKCS7 padding and HMAC-SHA256 authentication). The encrypted bytes are stored in a binary database field.

The encryption key is supplied via the `EMBEDDING_ENCRYPTION_KEY` environment variable. If the key changes between registration and verification, the stored embedding cannot be decrypted and the comparison produces a near-zero score. The key must therefore be stable across server restarts in any deployment that will reuse registered embeddings.

### Database — SQLite / PostgreSQL

SQLite is used by default for development and controlled deployments where a single-server setup is sufficient. For multi-server or high-concurrency deployments, PostgreSQL is supported via the `USE_SQLITE=False` setting and the `DB_*` environment variables. UUID primary keys are used throughout to avoid collision in distributed environments and to prevent enumeration of records by sequential integer IDs.

### Frontend — Bootstrap 5 + Vanilla JavaScript

The UI uses Bootstrap 5 with a custom Quezon City government portal theme (deep blue `#003d99`, government red `#c62828`, gold `#d4a017`). Three client-side JavaScript modules handle the webcam workflow:

- `webcam.js` — camera initialization, 640×480 resolution, burst capture, Laplacian-based sharpness scoring
- `liveness.js` — MediaPipe Face Mesh integration, head movement angle tracking, challenge evaluation
- `verify.js` — orchestrates the risk-based verification flow: capture → anti-spoof check → conditional liveness challenge (only when risk conditions are met) → burst capture → POST to server

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
[Client: burst 7 frames → select sharpest by Laplacian variance]
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
[Client: captures frame → "Capture & Verify" button]
        |
        v
[Server: verify_check_liveness — anti-spoof texture score + face quality check (always runs)]
        |
        v
[Client: risk evaluation]
        |
        +-- REQUIRE_LIVENESS_CHALLENGE (rep claim) OR anti-spoof < 0.30 OR
        |   poor quality OR retry attempt:
        |       → show head movement challenge (user tilts head)
        |
        +-- Otherwise (normal fast path):
        |       → skip visible challenge, proceed directly to "Process Verification"
        |
        v
[Client: burst 7 frames → select sharpest → POST to /verification/submit/]
        |
        v
[Server: verify_submit — liveness enforcement check]
        |
        +-- LIVENESS_REQUIRED=True and liveness_passed=False --> Denied (immediate)
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
- A random head movement challenge direction is pre-assigned (left, right, up, or down) but only shown if a risk condition is triggered
- For most beneficiary self-claims, the visible flow is simply: **Align Face → Capture & Verify → Process Verification → Result**

**Risk-based liveness triggering**
The head-movement challenge is shown only when one of these conditions is detected:
- The server's anti-spoof score is below 0.30 (suspicious texture)
- The image quality check fails (blur, poor lighting, glare)
- The claimant is a representative (always required)
- This is a retry attempt after a previous failed face match

**Submitting the result**
- The client selects the sharpest frame from a 7-frame burst and POSTs it to the server along with liveness signals
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

**Step 1 — Anti-spoof check (always runs)**
When the staff clicks "Capture & Verify", `verify.js` captures a frame and POSTs it to `verify_check_liveness`. The server returns: `face_detected`, `anti_spoof_passed`, `anti_spoof_score` (0–1), and `face_quality_ok`. This runs on every attempt regardless of outcome.

**Step 2 — Risk evaluation (in browser)**
`verify.js` evaluates whether the visible liveness challenge is needed:
- `REQUIRE_LIVENESS_CHALLENGE = true` (set by server for representative claims) → always show challenge
- `anti_spoof_score < 0.30` → suspicious — show challenge
- `face_quality_ok = false` → poor image — show challenge
- `isRetry = true` → previous attempt failed — show challenge
- Otherwise → skip challenge, proceed directly to "Process Verification"

**Step 3 — Head movement challenge (conditional)**
When triggered, `liveness.js` loads MediaPipe Face Mesh (WASM, runs locally in the browser) and tracks 468 3D facial landmarks. The angular displacement from the neutral head position is measured in the required direction (left/right/up/down). A displacement exceeding 12 degrees marks the challenge as completed. A 5-second auto-accept timer ensures accessibility for seniors with limited mobility.

**Step 4 — Burst capture and submit**
`webcam.js` captures a burst of 7 JPEG frames. Each frame is evaluated for sharpness using a JavaScript Laplacian variance estimate. The sharpest frame is selected and POSTed to `verify_submit`.

The client submits:
- `image_data` — base64-encoded JPEG of the selected sharpest frame
- `liveness_passed` — boolean (anti-spoof passed; challenge passed if it was shown)
- `liveness_score` — combined score (0.6 × anti_spoof + 0.4 × challenge_completed)
- `anti_spoof_score` — texture analysis score (float)
- `challenge_completed` — head movement result (false if challenge was skipped)

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

### 2. Risk-Based Liveness Detection

A photograph or video replay of the beneficiary's face is detected by two independent layers:
- **Texture anti-spoofing (always runs):** printed photos and screen displays have frequency-domain texture statistics that differ from real skin. An anti-spoof score below 0.30 automatically triggers the full liveness challenge.
- **MediaPipe head movement challenge (risk-triggered):** a random directional challenge that a static photograph or pre-recorded video cannot pass. Triggered when anti-spoof is suspicious, quality is poor, the claimant is a representative, or the attempt is a retry.

The challenge is not shown for every verification by design — doing so would frustrate elderly beneficiaries. Instead, the system escalates to the full challenge precisely when the risk signal warrants it. Backend liveness logging runs on every attempt regardless of whether the challenge was visible.

In strict mode (`LIVENESS_REQUIRED=True`), failure of either layer immediately denies the attempt before face matching runs.

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
13. Prompts to create the admin account via `python manage.py createsuperuser` (interactive — you choose the credentials)
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

# 9. Create admin user (interactive -- you will be prompted for username and password)
python manage.py createsuperuser

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
3. If claiming as beneficiary — risk-based flow:
   - Click **Capture & Verify**. The server runs a background anti-spoof check.
   - **Normal path (most cases):** If the anti-spoof check passes and image quality is good, the head-movement challenge is skipped. A burst of 7 frames is captured and the sharpest is submitted for face matching.
   - **Risk-triggered path:** If the anti-spoof score is low, image quality is poor, or this is a retry attempt, a head-movement challenge appears before submission.
   - Result: **Verified**, **Manual Review**, or **Not Verified**.
   - On failure, the system offers a retry (up to `MAX_RETRY_ATTEMPTS`). After retries are exhausted, an ID Fallback path is offered (beneficiaries only). All retries always trigger the liveness challenge.
4. If claiming as representative:
   - The liveness challenge **always runs** (representative claims are always risk-flagged).
   - FaceNet face matching runs against the representative's enrolled face, not the beneficiary's.
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

## Risk-Based Verification Flow

### Why Not Show the Liveness Challenge Every Time?

The head-movement liveness challenge (tilt head left/right/up/down) is effective at detecting spoofing — but asking an elderly senior citizen to perform it on every single verification creates unnecessary friction:

- Many seniors have limited neck mobility due to age or health conditions.
- The 5-second auto-accept timer helps, but the challenge still adds time and stress.
- A face match alone is strong biometric proof when anti-spoofing also passes.

The risk-based approach applies a proportionate response: use the minimum friction needed to achieve the required security level.

### When the Challenge Is Shown

| Condition | Reason |
|---|---|
| Anti-spoof score < 0.30 | Texture suggests a printed photo or screen — escalate |
| Image quality check failed | Poor lighting or blur — face match may be unreliable; challenge confirms liveness |
| Representative claim | Third-party claim always requires extra verification |
| Retry attempt | Previous face match failed — score was borderline; liveness adds a second signal |

### When the Challenge Is Skipped (Fast Path)

| Condition | Why it is safe to skip |
|---|---|
| Anti-spoof score ≥ 0.30 and quality OK | Server-side texture check passed — live face confirmed |
| Beneficiary self-claim | Claimant is the enrolled person themselves |
| First attempt | No prior failure signals |

### What Happens in Each Path

**Fast path (most beneficiary self-claims):**
```
[Click "Capture & Verify"]
→ Anti-spoof check: PASSED
→ Step 2: "No challenge required — anti-spoof passed" ✓
→ [Click "Process Verification"]
→ Face match → result
```

**Risk-triggered path:**
```
[Click "Capture & Verify"]
→ Anti-spoof check: low score (< 0.30)
→ Step 2: "Liveness Challenge" shown — "Tilt your whole head slowly to the LEFT"
→ Challenge completed (or auto-accepted after 5s)
→ [Click "Process Verification"]
→ Face match → result
```

### Backend Logging — Always On

Regardless of which path the user sees, the server:
- Always runs the anti-spoof texture check.
- Always records `anti_spoof_score`, `liveness_score`, `liveness_passed`, and `challenge_completed` in the `VerificationAttempt` record.
- Always writes a full `AuditLog` entry.

This means the liveness data is complete for audit and analysis, even when the visible challenge was skipped.

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

## Hybrid Centralized + Offline Fallback Sync

### Architecture overview

FANS-C is designed **primarily for centralized LAN deployment** where all staff workstations write directly to a shared PostgreSQL database over a local network. No synchronization is needed in this configuration — all data lives on one authoritative server from the moment it is entered.

The offline sync pipeline exists as a **fallback** for barangay outreach scenarios where a workstation temporarily loses access to the central server (power outage, physical relocation, network disruption). Registrations captured offline are stored locally and pushed to the central server once connectivity is restored.

| Mode | When used | Data location | Sync needed? |
|---|---|---|---|
| **Centralized (primary)** | Normal LAN operation | Central PostgreSQL | No |
| **Offline fallback** | Workstation loses LAN access | Local SQLite | Yes — on reconnect |

### Sync state machine

Every `Beneficiary` record carries a `sync_status` field that progresses through four states:

```
[created offline]
        │
        ▼
  pending_sync  ──── HTTP 200/201 ──►  synced        (accepted)
        │
        ├──── HTTP 409 ──────────────►  sync_conflict  (admin review)
        │
        └──── HTTP 400/422 ──────────►  sync_rejected  (admin review)

  sync_conflict ──── admin retry ──►  pending_sync
  sync_rejected ──── admin retry ──►  pending_sync
```

| State | Meaning | Action |
|---|---|---|
| `pending_sync` | Record created locally, not yet accepted by central server | Retried on every sync run |
| `synced` | Central server accepted (HTTP 200/201) | No action needed |
| `sync_conflict` | Server returned 409 — conflicting record already on server | Admin must review at `/sync/conflicts/` |
| `sync_rejected` | Server returned 400/422 — payload invalid | Admin must review at `/sync/conflicts/` |

Transient network failures (5xx, timeout) leave the record at `pending_sync` and it is retried on the next run. Only 409 and 4xx responses permanently change the state, because those indicate server-side decisions that require human review.

### Offline-device audit trail

When a registration is saved on an offline workstation, `sync.mark_created()` stamps:
- `offline_device` — hostname of the workstation (from `socket.gethostname()`)
- `sync_status = 'pending_sync'`

When sync is attempted, `sync_attempted_at` is updated regardless of outcome. This means the audit log always shows *which device created the record*, *when it was created*, *when sync was attempted*, and *what the server said*.

### Enabling sync (offline fallback mode)

Configure the central server endpoint in `.env`:

```
SYNC_API_URL=https://central.fans-c.gov.ph/api
SYNC_API_KEY=your-secret-bearer-token
SYNC_TIMEOUT=30
SYNC_BATCH_SIZE=50
```

Leave `SYNC_API_URL` empty in centralized deployment — the sync pipeline stays dormant.

### Running sync

**Automatically:** `run.ps1` triggers a background sync on every server start (if `SYNC_API_URL` is configured).

**Manually:**
```powershell
.\.venv\Scripts\python.exe manage.py sync_beneficiaries
.\.venv\Scripts\python.exe manage.py sync_beneficiaries --force    # skip connectivity check
.\.venv\Scripts\python.exe manage.py sync_beneficiaries --batch 100
```

**Programmatically:**
```python
from beneficiaries.sync import is_online, sync_all, pending_count, conflict_count

if is_online():
    result = sync_all()
    # result = {'synced': 5, 'failed': 0, 'conflicts': 1, 'rejected': 0, 'skipped': 0}
```

Exit codes from the management command:
- `0` — all records synced cleanly
- `1` — transient failures (will retry automatically)
- `2` — conflicts or rejections present (requires admin review)

### Admin conflict review

Records in `sync_conflict` or `sync_rejected` appear in the admin queue at:

```
/dashboard/sync/conflicts/
```

For each record, the admin can:

| Action | Effect | When to use |
|---|---|---|
| **Retry Sync** | Resets to `pending_sync`; re-sent on next sync run | Conflict was transient or central record was since deleted |
| **Accept Local** | Marks as `synced`; local record treated as authoritative | Admin confirms local capture is correct, central copy should be disregarded |
| **Reject Permanently** | Keeps `sync_rejected`; record retained for audit only | Local data was invalid or a true duplicate |

Every admin decision is logged in the audit log with the admin's name, timestamp, beneficiary ID, device hostname, and review notes.

### What operations are allowed offline

| Operation | Offline allowed? | Notes |
|---|---|---|
| Register new beneficiary | Yes | Queued as `pending_sync` |
| Capture face embedding | Yes | Encrypted locally |
| Stipend verification | Yes | Runs against local embedding store |
| Claim recording | Yes | Stored locally |
| Admin approval (registrations) | Yes | If admin is on the same workstation |
| Sync conflict review | No | Requires access to central server data to make informed decision |

### Encryption key sharing

`EMBEDDING_ENCRYPTION_KEY` encrypts face embeddings before they leave the device. The central server must use the **same key** to decrypt and match received embeddings.

**Transfer procedure:**
1. Copy the key value from the source device's `.env` to the central server's `.env`.
2. Do **not** re-generate the key — all existing embeddings will become unreadable.
3. Transfer via USB or an encrypted channel — never plain email or chat.

### Defense-ready explanation

FANS-C addresses a real tension in Philippine government field operations: rural barangays often have unreliable internet, but stipend distribution cannot stop when the network goes down. The system resolves this by treating the central server as authoritative for all normal operations (centralized LAN mode) while providing a structured offline fallback that does not silently corrupt data.

The four-state sync machine (pending → synced / conflict / rejected) ensures that offline-captured records are never silently merged with central data. A conflict means a human must decide which version is correct — the system does not guess. A rejection means the data failed central validation — again, a human reviews rather than the record being silently discarded.

Per-device attribution (`offline_device`, `sync_attempted_at`) provides a complete audit trail: regulators can see exactly which barangay workstation captured each record, when it was captured, when sync was attempted, and what the central server said. This satisfies data governance requirements for government social protection programs.

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

- **Client-side liveness can be bypassed technically.** Liveness signals (`liveness_passed`, `challenge_completed`) are submitted by the client and trusted by the server. A technically capable attacker who can intercept and modify the HTTP request could submit `liveness_passed=True` regardless of the actual video. The server-side texture anti-spoofing runs independently and cannot be faked by the client, but the challenge boolean can be. Fully server-side liveness evaluation would require streaming the video frames to the server rather than just the final image. This is a known limitation of browser-based liveness systems.

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
    verify.js               Risk-based verification flow: capture → anti-spoof → conditional challenge → submit
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
| beneficiaries | 0006 | Offline sync fields: sync_error, last_synced_at (is_synced now replaced by 0008) |
| beneficiaries | 0007 | Partial unique index on senior_citizen_id (non-empty values only) |
| beneficiaries | 0008 | Replace is_synced bool with sync_status CharField (4-state machine); add offline_device, sync_attempted_at |
| logs | 0001 | AuditLog model |
| logs | 0002 | Add 'update' action choice for record edits |
| logs | 0003 | Add face_update, manual_verify, claim, special_claim, register_approved/rejected, duplicate_face actions |
| logs | 0004 | Add sync_accepted, sync_conflict, sync_rejected audit actions |
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

---

## Centralized Deployment Architecture

This section describes the recommended real-world deployment of FANS-C for a barangay or multi-office environment where multiple staff members operate the system simultaneously from different devices.

---

### Architecture Overview

```
                          +----------------------------+
  Staff Station A  -----> |                            |
  (browser / LAN)         |   Central Django Server    |
                          |   (one Python process,     |
  Staff Station B  -----> |    gunicorn + nginx)       |
  (browser / LAN)         |                            |
                          +------------+---------------+
  Admin Workstation -----> |           |
  (browser / LAN)         |           v
                          |   Shared PostgreSQL DB     |
                          |   (single source of truth) |
                          +----------------------------+
```

**One server. One database. All clients connect to the same backend through a web browser.** This is the same pattern used by every major web application: Django is the server, PostgreSQL is the database, and staff workstations are just browsers.

- Person 1 (Staff Station A) registers a beneficiary.
- Person 2 (Staff Station B) verifies that beneficiary in the next room.
- Person 3 (Admin Workstation) reviews pending manual approvals from any device.
- All three see the same live data because they are all hitting the same database.

---

### Why Centralized, Not Separate Local Databases

Each workstation running its own SQLite database is not suitable for real simultaneous multi-user operation:

| Problem | Separate local SQLite databases | Centralized PostgreSQL |
|---|---|---|
| Person 1 registers, Person 2 cannot see it | Yes — data is trapped on Person 1's machine | No — shared DB, visible immediately |
| Duplicate beneficiary IDs across stations | Yes — each generates IDs independently | No — single sequence, database-locked |
| Duplicate claim records (two stations, one event) | Yes — no shared lock | No — row-locked transaction prevents it |
| Audit trail is split across machines | Yes — no single log | No — one audit log for all actions |
| Admin approval visible to all staff | No — approvals on one machine only | Yes |
| Conflict resolution required | Yes — merge conflicts, sync errors | No — no merge, one truth |

**The offline-first sync architecture (SYNC_API_URL, sync_beneficiaries command) exists for edge deployments** where workstations genuinely cannot connect to a network — for example, a barangay distribution event in a location with no internet. It is not the recommended primary mode when a LAN or internet connection is available. For anything beyond a single-operator installation, centralized deployment is the correct choice.

---

### Deployment Modes Compared

| Mode | Database | Who can use it | When to use |
|---|---|---|---|
| **Local development** | SQLite on dev machine | 1 developer | Writing and testing code |
| **Standalone workstation** | SQLite, local | 1 staff operator | Single-device barangay with no LAN |
| **Centralized (recommended)** | Shared PostgreSQL | All staff, all devices | Normal barangay operation with LAN or internet |
| **Offline sync (fallback)** | Local SQLite + push sync | 1 offline operator | Remote distribution event, no network |

---

### Setting Up Centralized Deployment

**Requirements on the server machine:**

- Python 3.11
- PostgreSQL 14+ (or 15/16)
- gunicorn (`pip install gunicorn`)
- nginx (strongly recommended for media serving and HTTPS)

**Step 1 — Install dependencies**

```bash
pip install -r requirements.txt
```

`psycopg2-binary` is now included in `requirements.txt` and will be installed automatically.

**Step 2 — Create the PostgreSQL database**

```sql
CREATE USER fans_user WITH PASSWORD 'choose_a_strong_password';
CREATE DATABASE fans_db OWNER fans_user;
```

**Step 3 — Configure `.env` on the server**

Copy `.env.example` to `.env` and edit for production:

```
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(50))">
DEBUG=False
ALLOWED_HOSTS=192.168.1.50,fans-c.yourdomain.gov.ph

USE_SQLITE=False
DB_NAME=fans_db
DB_USER=fans_user
DB_PASSWORD=choose_a_strong_password
DB_HOST=localhost
DB_PORT=5432
CONN_MAX_AGE=60

EMBEDDING_ENCRYPTION_KEY=<generate with: python manage.py generate_key>

# If using HTTPS through nginx:
CSRF_TRUSTED_ORIGINS=https://fans-c.yourdomain.gov.ph
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https
USE_X_FORWARDED_HOST=True
```

**Step 4 — Initialize the database**

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

**Step 5 — Create the admin account**

Use Django's built-in interactive command. Do not use `create_admin` with any default or hardcoded password in production — credentials must be chosen at setup time by the person responsible for the deployment.

```bash
python manage.py createsuperuser
```

You will be prompted for a username, email address, and password. Choose a strong password and record it securely. This account controls access to all beneficiary records and admin functions.

**Step 6 — Run with gunicorn**

```bash
gunicorn fans.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 3 \
    --timeout 120
```

Use `--workers 3` as a starting point. Each worker handles one request at a time; with 3 workers, 3 staff stations can submit verifications simultaneously without queuing.

For a production server, run gunicorn as a systemd service so it restarts automatically:

```ini
# /etc/systemd/system/fans-c.service
[Unit]
Description=FANS-C Gunicorn
After=network.target

[Service]
User=www-data
WorkingDirectory=/srv/fans-c
ExecStart=/srv/fans-c/.venv/bin/gunicorn fans.wsgi:application \
    --bind 127.0.0.1:8000 --workers 3 --timeout 120
Restart=always

[Install]
WantedBy=multi-user.target
```

---

### Reverse Proxy with nginx

nginx sits in front of gunicorn and handles:
- HTTPS termination (TLS certificates via Let's Encrypt or a government CA)
- Static file serving (faster than Django/WhiteNoise for high-traffic deployments)
- Media file serving (profile pictures, face capture frames)

**Minimal nginx config:**

```nginx
server {
    listen 443 ssl;
    server_name fans-c.yourdomain.gov.ph;

    ssl_certificate     /etc/letsencrypt/live/fans-c.yourdomain.gov.ph/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/fans-c.yourdomain.gov.ph/privkey.pem;

    # Static files — served directly by nginx, not through Django
    location /static/ {
        alias /srv/fans-c/staticfiles/;
        expires 7d;
    }

    # Media files — profile pictures, face captures
    location /media/ {
        alias /srv/fans-c/media/;
    }

    # Everything else goes to gunicorn
    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}

# Redirect plain HTTP to HTTPS
server {
    listen 80;
    server_name fans-c.yourdomain.gov.ph;
    return 301 https://$host$request_uri;
}
```

**Why media files must not be served through Django in production:**

Profile pictures and face capture images can be several hundred KB each. Routing them through the Python WSGI process ties up a gunicorn worker for the duration of the file transfer, reducing the number of verification requests the server can handle in parallel. nginx serves files from disk directly, releasing the worker immediately.

In local development (`DEBUG=True`), Django serves media automatically. In production (`DEBUG=False`), the `urlpatterns` no longer include media routes and nginx takes over.

---

### Offline Sync as Fallback

The offline sync feature (`SYNC_API_URL`, `sync_beneficiaries` management command) remains in the codebase as a secondary option for edge scenarios:

- A registration team operates from a remote location with no network.
- Registrations are stored locally (SQLite) and pushed to the central server when connectivity is restored.

**This is not the primary multi-user mode.** In the centralized architecture, all workstations connect directly to the shared PostgreSQL database — no sync is required because there is only one database.

If offline sync is used alongside centralized deployment, the central server's `EMBEDDING_ENCRYPTION_KEY` must be identical to the offline workstation's key. Keys that differ make face embeddings from the offline device permanently unreadable on the server.

---

### Defense-Ready Architecture Explanation

**Why centralized deployment is better for real multi-user use:**

A centralized architecture means there is exactly one database, one source of truth. Every read and write from every staff station goes to the same place at the same time. This eliminates an entire category of problems:

- A beneficiary registered by one staff member is immediately visible to another — no sync lag, no "not found" errors because the record is still on the registering machine.
- A stipend claim recorded by one station is immediately visible to the admin approval queue on another station.
- The audit log is unified: every action by every user appears in one chronological sequence.
- Race conditions on duplicate claims are resolved at the database level through row-level locking (`SELECT FOR UPDATE`), not through application-level merge logic.

**Why separate local SQLite databases are not suitable for simultaneous operations:**

SQLite is a file-based embedded database. It has no network server component. Each machine running its own SQLite file has its own completely independent copy of the data. To share data, records must be exported, transmitted, and merged — the offline sync workflow. Merge introduces conflict risk: two machines can independently create a beneficiary with the same sequential ID, two machines can independently mark the same event as claimed for the same beneficiary, and audit logs must be manually reconciled. None of these problems exist in a centralized deployment.

SQLite is entirely appropriate for single-operator use and local development. The moment a second operator on a second machine needs to see live data from the first operator, a shared database server is the correct solution.

**Why offline sync should be fallback, not primary multi-user mode:**

Offline sync was designed for the specific scenario of a distribution event at a location with no network access. It is not designed for an office with two staff members who both need to register and verify beneficiaries at the same time. Operating two offline nodes concurrently and merging them later requires careful conflict resolution and creates windows where one node has stale data. The centralized model avoids this entirely: if the network is available, use it and share one database. Offline sync is the plan B for when the network genuinely is not available.

---

## Barangay LAN Deployment Guide

This is the practical, operator-focused guide for setting up FANS-C in a real barangay office using a centralized LAN architecture. It is written for the person responsible for the initial setup, and assumes a barangay office environment with a local Wi-Fi network or wired switch.

**Architecture in one sentence:** One machine in the barangay office runs the FANS-C server. All other staff devices open a browser and navigate to that machine's address over HTTPS. No software installation is needed on client devices.

> **Camera access requires HTTPS.** Browsers only allow webcam access (`getUserMedia`) from a secure context — that means `https://` or `localhost`. A plain `http://192.168.x.x` URL will block the camera on client devices. For the server itself this is not an issue (it is localhost), but for any other device on the LAN it must be HTTPS. See the [Secure HTTPS LAN Deployment](#secure-https-lan-deployment) section for the full setup guide. This plain-HTTP guide covers basic connectivity; the HTTPS guide is what to follow for real deployment.

> **This is the recommended production deployment for any barangay with two or more staff members, or any setup where a shared database is required.** The offline sync mode and the Windows .exe packaging are alternative paths for specific edge scenarios — not the primary deployment model.

---

### Why This Architecture Fits a Barangay

| Concern | Why centralized LAN is the right answer |
|---|---|
| Multiple staff members need to see the same data | One server, one database — everyone sees the same records in real time |
| Installing full Python / Django / TensorFlow on every computer is impractical | Only the server machine needs the software; other devices just use a browser |
| Face embeddings and beneficiary records must not be duplicated | A single shared database eliminates the risk of conflicting or out-of-sync records |
| Internet connectivity may be unreliable | LAN operates entirely within the office network — no internet required for daily use |
| Audit trail must be centralized | One server produces one audit log covering all staff actions from all devices |
| Updates must be consistent | Update once on the server; all connected browsers get the updated system immediately |

---

### Recommended Setup for a Barangay Office

```
  [Barangay Server Machine]             [Staff Laptop / Tablet / Desktop]
    One PC or laptop in the office        Any device with a web browser
    Runs Waitress + Caddy + FaceNet       No installation needed
    Holds the database and media          Open browser -> https://fans-barangay.local
    Connected to office Wi-Fi / LAN       Log in and work normally (camera enabled)

  [Second Staff Device]
    Same as above -- just a browser
    Connects via https://fans-barangay.local (hostname resolves to server IP)
```

All data stays on the server machine inside the office network. No data is sent to the internet during normal operation.

**Preferred access URL:** `https://fans-barangay.local`
The server LAN IP (e.g. `192.168.1.77`) is used internally and during plain-HTTP fallback testing only. See [Secure HTTPS LAN Deployment](#secure-https-lan-deployment) for full setup.

---

### Step-by-Step: Setting Up the Central Server

This is done once on the machine that will act as the server. After this is done, no other machine needs to be configured.

**Prerequisites on the server machine:**

- Windows 10 / 11 (or Ubuntu Linux)
- Python 3.11 — TensorFlow does not support Python 3.12 or later
- Git (optional, for cloning the repository)

**Step 1 — Get the project files on the server**

Copy the project folder to the server machine (via USB, shared folder, or git clone):

```
D:\FANS\FANS-C\   (or any path you choose)
```

**Step 2 — Create the virtual environment and install dependencies**

Open Command Prompt or PowerShell in the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

The first run downloads TensorFlow and all dependencies. This requires internet and may take several minutes.

**Step 3 — Find the server's LAN IP address**

In Command Prompt on the server machine:

```
ipconfig
```

Look for **IPv4 Address** under your active network adapter (Wi-Fi or Ethernet). Example:

```
IPv4 Address . . . . . . . . . . : 192.168.1.77
```

Write this down. This is the address that other devices will use to connect.

**Step 4 — Configure the environment file**

Copy `.env.example` to `.env` and open it in Notepad:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set these values (minimum required for LAN deployment):

```
# Replace with a strong random string:
#   python -c "import secrets; print(secrets.token_urlsafe(50))"
SECRET_KEY=<generated value>

# Barangay server: include the LAN IP and localhost
# Replace 192.168.1.77 with the actual IP from Step 3
ALLOWED_HOSTS=192.168.1.77,localhost,127.0.0.1

DEBUG=False

# SQLite is appropriate for a single-server barangay deployment
USE_SQLITE=True

# Generate with: python manage.py generate_key
# BACK THIS UP -- losing this key means all face data is unreadable
EMBEDDING_ENCRYPTION_KEY=<generated value>

# Leave empty -- offline sync is not needed in centralized LAN mode
SYNC_API_URL=
```

Generate the encryption key:

```powershell
python manage.py generate_key
```

Copy the output and paste it into `.env` as `EMBEDDING_ENCRYPTION_KEY`.

**Step 5 — Initialize the database**

```powershell
python manage.py migrate
python manage.py collectstatic --noinput
```

**Step 6 — Create the admin account**

```powershell
python manage.py createsuperuser
```

You will be prompted for:
- **Username** (e.g., `barangay_admin` or the administrator's name)
- **Email address**
- **Password** — choose a strong password and store it securely

This is the account that controls all admin functions. Do not use a simple or shared password.

**Step 7 — Start the server**

For Assisted Rollout (recommended during initial deployment):

```powershell
python manage.py runserver 0.0.0.0:8000
```

The `0.0.0.0` makes Django listen on all network interfaces so other devices on the LAN can connect. Leave this terminal window open while the system is in use.

For a more stable production setup (optional):

```powershell
pip install waitress
waitress-serve --listen=0.0.0.0:8000 fans.wsgi:application
```

**Step 8 — Verify LAN access from another device**

On another device connected to the same Wi-Fi or network switch:

1. Open a web browser
2. Go to `http://192.168.1.77:8000` (replace with the server IP from Step 3)
3. The FANS-C login page should appear

If the page does not load, check that:
- The server's Windows Firewall allows inbound connections on port 8000
- Both devices are on the same Wi-Fi network or connected to the same switch
- `ALLOWED_HOSTS` in `.env` includes the server's LAN IP

**Windows Firewall rule (if needed):**

```powershell
# Run as Administrator
netsh advfirewall firewall add rule `
  name="FANS-C Django Server" `
  dir=in action=allow protocol=TCP localport=8000
```

---

### Client Device Access

Client devices need **no installation at all**. They only need a web browser and a connection to the same office network.

**Steps for a staff member:**

1. Connect to the barangay office Wi-Fi (or plug in the network cable)
2. Open a web browser (Chrome, Edge, or Firefox)
3. Go to `https://fans-barangay.local` — the FANS-C login page should appear
4. Log in with the username and password assigned by the administrator

If `fans-barangay.local` does not resolve yet (hostname not configured), use the plain-HTTP fallback `http://192.168.1.77:8000` for basic connectivity testing. Camera capture will not work over plain HTTP on client devices — HTTPS is required. See [Hostname Resolution: fans-barangay.local](#hostname-resolution-fans-barangaylocal) for setup.

**VS Code, Python, and the terminal are not needed on client machines.**

Staff members access the system through the browser only. The developer tools (VS Code, Python environment, command line) are only needed on the server machine for initial setup and maintenance tasks. Normal daily operations — registering beneficiaries, running verifications, processing claims — all happen through the browser.

---

### Local Network Access Flow

```
  Staff Device (browser)
          |
          | https://fans-barangay.local  (LAN -- no internet needed)
          |
          v
  Central Server Machine (one PC in the barangay office)
    [Caddy -- HTTPS termination, TLS certificate, port 443]
          |
          | plain HTTP, 127.0.0.1:8000 (internal only)
          v
    [Waitress -- WSGI server]
          |
          v
    [Django application -- FaceNet pipeline]
          |
          v
    [SQLite database, encrypted face embeddings, media files]
```

Everything runs on the server machine. Client devices send HTTPS requests and display results. No biometric data passes to the internet. The LAN is entirely self-contained within the barangay office. Caddy handles TLS so Django itself never needs to deal with certificates.

---

### Offline Fallback Behavior

The offline sync feature (`SYNC_API_URL` in `.env`) is designed for edge cases where a device cannot reach the central server — for example, a mobile registration team operating at a remote distribution site with no network.

**In normal barangay office LAN operation, offline sync is not enabled and is not needed.** All staff devices connect directly to the central server through the browser. Leave `SYNC_API_URL` empty in `.env`.

#### What "offline" means in practice

The term "offline" in FANS-C means a **specific device** has temporarily lost its connection to the central server. It does not mean the system has no internet — this system does not require public internet at all. A device goes offline when the LAN cable is unplugged, it is taken outside the Wi-Fi range, or the server PC is turned off.

#### What the server being off means

If the **server PC is shut down**:

- The entire centralized system is unavailable — no staff can log in, no verifications can be processed through the main system
- Staff PCs will show "This site can't be reached" or a similar browser error
- The system comes back online as soon as the server PC is restarted and the startup scripts are run
- No reinstallation is required — all data, registrations, and configuration are preserved on the server

#### What operations are allowed offline (fallback mode only)

When a device has lost connection and offline mode is active, only clearly defined low-risk operations are permitted:

| Operation | Offline allowed? | Notes |
|---|---|---|
| Register new beneficiary | Yes | Stored as `pending_sync` — provisional only |
| Capture face embedding | Yes | Encrypted locally |
| Stipend verification | Yes | Runs against local embedding store |
| Claim recording | Yes | Stored locally — must sync before treated as final |
| Admin approval of pending registrations | Yes | Only if admin account is on the same offline device |
| Sync conflict review | **No** | Requires access to central server data to make an informed decision |
| Admin override of manual review | **No** | Server validation required |
| Any action that requires central server state | **No** | Must wait for reconnection |

**Offline records are always provisional.** They are marked `pending_sync` and must be reviewed and accepted by the central server before they are treated as authoritative. If the central server detects a conflict (e.g., a beneficiary was already registered or already claimed), the record enters a conflict queue for admin review — it is never silently merged.

#### When connectivity returns

When the device reconnects to the server:

1. The sync command (`python manage.py sync_beneficiaries`) pushes `pending_sync` records to the central server
2. The server validates each record — it may accept, reject, or flag a conflict
3. Records accepted by the server move to `synced` status
4. Conflicts and rejections appear in the admin review queue at `/dashboard/sync/conflicts/`
5. An admin must resolve each conflict manually — the system does not auto-merge

Offline sync adds operational complexity and conflict-resolution overhead. Enable it only when a device genuinely cannot be networked to the LAN.

---

### Admin Account Creation

**Always use `python manage.py createsuperuser` for deployment.** This is Django's built-in secure admin creation command.

```powershell
python manage.py createsuperuser
```

Why this matters:

- The command prompts for credentials interactively — they are never stored in code, scripts, or source control
- Django's full password validation suite runs (minimum length, complexity, common-password check)
- The password is hashed with PBKDF2 before storage — it is never stored as plain text
- The person setting up the system chooses the password at setup time, not a developer months earlier

**What not to do:**

- Do not hardcode a password in any script or config file (e.g., `--password Admin123`)
- Do not commit a script that calls `create_admin` with a default password
- Do not share a single admin account among multiple users — create individual accounts

After creating the first admin account, additional staff accounts can be created through the Django admin panel at `/admin/` or through the system's user management interface.

---

### Security Notes

1. **Change the admin password immediately after setup.** If the initial password was communicated to someone during setup, change it before regular operation begins.

2. **Keep `.env` secure.** The `EMBEDDING_ENCRYPTION_KEY` in `.env` encrypts every stored face embedding. If this key is lost or changed, all enrolled beneficiaries must re-register from scratch. Never transmit `.env` over plain email — use a USB drive or an encrypted message.

3. **Set `DEBUG=False` on the deployed server.** With `DEBUG=True`, Django shows detailed error pages that expose source code and internal settings to anyone who triggers an error. Always set `DEBUG=False` in `.env` on any server that is accessible to staff.

4. **Lock the server machine screen when unattended.** The server machine holds all biometric data. Enable Windows automatic screen lock or set a short screensaver lock time.

5. **Use individual accounts for each staff member.** Do not share login credentials. Individual accounts ensure the audit log identifies which staff member performed each action.

6. **Keep the server machine on a trusted internal network only.** For a barangay office, the server should be on the local Wi-Fi or wired switch. Caddy listens on port 443 (HTTPS). Waitress listens on `127.0.0.1:8000` (internal only — not accessible from outside the server machine). Do not expose either port to the internet.

---

### Backup and Maintenance

**What to back up (on the server machine):**

| File / Folder | Why | How often |
|---|---|---|
| `.env` | Contains the encryption key — losing this makes all face data permanently unreadable | Once after setup; after any key change |
| `db.sqlite3` | The main database — all beneficiary records, claims, and audit logs | Daily |
| `media/` | Uploaded photos and face capture references | Daily |

**Simple daily backup (run on the server machine at end of each working day):**

```powershell
# Run in the project folder
$date = Get-Date -Format 'yyyyMMdd'
Copy-Item db.sqlite3 "D:\Backups\db_$date.sqlite3"
xcopy media "D:\Backups\media_$date" /E /I /Q
```

Or copy `db.sqlite3`, `media\`, and `.env` to a USB drive after each session.

**Restarting Django after the server machine reboots:**

The project does **not** need to be reinstalled after a reboot. The virtual environment, `.env`, database, certificates, and all registered data remain in place. Only the two server processes — Waitress and Caddy — need to be started again.

**Quickest method:** Double-click `start-fans.bat` in the project root folder. It opens two windows — one for Waitress and one for Caddy — and shows progress messages.

**With pre-flight checks:** Run `.\start-fans-production.ps1` from PowerShell. It validates the environment (encryption key, certificates, Caddy installation) before starting anything.

**Manual method:**

```powershell
# Window 1 — Waitress
cd D:\FANS\fans-c
.\.venv\Scripts\Activate.ps1
waitress-serve --listen=127.0.0.1:8000 fans.wsgi:application

# Window 2 — Caddy (same folder)
caddy run --config Caddyfile
```

**Automatic startup on Windows boot (Task Scheduler):** Use Windows Task Scheduler to run `start-fans.bat` automatically at login, so the system comes online without manual steps after every reboot. Full instructions are in [SETUP.md](SETUP.md) — "Starting the Server After a Reboot".

**Applying updates:**

When the source code is updated (bug fixes, new features):

1. Pull or copy the updated files to the server machine
2. Activate the virtual environment and run `pip install -r requirements.txt` if requirements changed
3. Run `python manage.py migrate` to apply any new database migrations
4. Run `python manage.py collectstatic --noinput` if static files changed
5. Restart Django

Client devices need no changes — they will automatically use the updated system when they next open the browser.

---

### Development vs Production Mode

| Context | Command / setup | Notes |
|---|---|---|
| Developer testing on own machine | `python manage.py runserver` | `localhost` only; camera works because it is a secure context |
| Basic LAN connectivity test (no camera) | `python manage.py runserver 0.0.0.0:8000` | Plain HTTP; camera blocked on client devices |
| Barangay production deployment (recommended) | Waitress on `127.0.0.1:8000` + Caddy HTTPS on port 443 | Camera works on all LAN devices; access via `https://fans-barangay.local` |

**VS Code is a developer tool, not a daily operator tool.**

- **Developers** use VS Code, Python, the terminal, and `manage.py` commands to build, maintain, and debug the system
- **Barangay staff** open a browser, navigate to the server IP, log in, and work normally
- After initial setup, the server machine runs Django in the background and staff devices use the system through the browser — no terminal, no VS Code, no Python commands

The only time a terminal is needed on the server machine after setup is to restart Django after a reboot, or to apply software updates.

---

### Defense Notes: Why Centralized LAN Is the Right Architecture

**For the academic reviewer or panel evaluator:** This section explains the architectural reasoning for the design choices.

The FANS-C system uses a standard web application architecture: one Django server process, one shared database, browser-based clients. This is not an architectural shortcut or a simplification — it is the correct architecture for a multi-user application that requires a consistent shared state.

**Why not install a full copy of the system on every device?**

Installing Python, TensorFlow, Django, and a local database on every staff laptop would require:
- Significant technical expertise to set up and maintain on each machine
- Manual data synchronization between devices (with conflict resolution)
- Separate backup management for each machine
- Coordinated updates applied to every device separately

None of these problems exist with a centralized server. One machine runs the software; all others use a browser.

**Why is browser-based client access appropriate for a barangay setting?**

Every modern device — laptop, tablet, or desktop — ships with a web browser. The browser is the universal client interface. A staff member needs no technical knowledge to use the system: they open a browser and navigate to an IP address. This is the same model used by Philippine government information systems, banking portals, hospital management systems, and every major web application.

**Why is offline sync restricted to fallback only?**

Offline sync was designed for a specific scenario: a registration team at a remote location with no network. It is not designed for simultaneous multi-user operation in an office where a network is available. Running two offline nodes concurrently creates windows where each node has stale data, and merging them later requires conflict resolution. The centralized model eliminates this entirely: if the network is available, there is one database and no merge step.

**Comparison:**

| Criterion | Full install on every device | Centralized LAN (this system) |
|---|---|---|
| Data consistency | Each device has its own database; data diverges over time | One database, one source of truth |
| Duplicate claim prevention | Requires distributed coordination | Row-level lock on one database enforces it |
| Audit trail completeness | Split across every device | One unified audit log |
| Software updates | Must be applied to every device | Update once on the server |
| Encryption key management | Keys must be identical and managed on every device | One key, one server |
| Staff training | Each staff member needs to manage their own Python environment | Open browser, enter IP, log in |

---

## LAN vs Internet: What the System Actually Needs

This section is for non-expert readers — barangay staff, administrators, and capstone panelists — to clearly understand how this system works in a real office.

### This system is LAN-based (on-premise)

FANS-C is installed on one server PC inside the barangay office. All staff computers and tablets connect to that server over the local Wi-Fi or wired network. The system does **not** communicate with the internet during normal operation.

### Does the system need internet?

| Task | Internet needed? |
|---|---|
| Daily use — registration, verification, stipend claims | **No.** Runs on local network only. |
| FaceNet model download (first startup only, done once during setup) | Yes — model is ~90 MB, downloaded once and cached. |
| Software updates | Yes — only when the developer applies updates manually. |

After initial setup, the system operates entirely within the office network. Public internet going down has no effect on the system.

### What happens in each scenario

| Scenario | What staff experience |
|---|---|
| Internet is down, office Wi-Fi and server are running | System works normally. Staff log in and process verifications as usual. |
| Office Wi-Fi is running, internet is also working | System works. Internet connectivity is irrelevant. |
| Server PC is turned off | System unavailable. Browser shows "This site can't be reached". Staff must wait for the server to be restarted. |
| Staff PC loses Wi-Fi connection | That PC cannot reach the system. Other PCs on the network are unaffected. Reconnecting to Wi-Fi restores access. |
| Power outage | System goes offline until power is restored and the server PC is restarted. |

### What happens when the server comes back online

No reinstallation is needed. When the server PC is turned back on:

1. Open `start-fans.bat` (or `start-fans-production.ps1`) on the server machine
2. Two windows appear — Waitress and Caddy — and start up automatically
3. After a few seconds, `https://fans-barangay.local` becomes available again on the network
4. Staff log in and continue working from where they left off

All data, registered beneficiaries, and audit logs are preserved on the server's database. Nothing is lost from a reboot.

### Server machine vs client/staff PCs

| Machine type | What it needs | Who manages it |
|---|---|---|
| **Server PC** | Python, Django, the full project, Waitress, Caddy, TLS certificates, `.env`, database | IT person / developer (setup once) |
| **Client / staff PC** | A web browser | Any staff member |

Staff PCs do not need Python, the project files, or any installation beyond a browser and the hosts file entry for `fans-barangay.local` (done once per device by the IT person).

---

## Secure HTTPS LAN Deployment

This section covers the recommended production deployment for a barangay office: Django served by Waitress behind Caddy as a local HTTPS reverse proxy, accessed by staff devices at `https://fans-barangay.local`.

---

### Why HTTPS Is Required for Camera Access

Browsers enforce a **secure context** rule for sensitive hardware APIs. The `getUserMedia` API — which powers webcam access for face capture — is only available under two conditions:

1. The page is served from `localhost` or `127.0.0.1` (the server machine itself)
2. The page is served over `https://`

A plain `http://192.168.1.77:8000` URL fails condition 2. The browser will block camera access silently — the verification flow will either show a blank camera or an error, depending on the browser. This is not a bug; it is a deliberate browser security policy that cannot be bypassed through Django configuration.

**This means HTTPS is not optional for a multi-device LAN deployment — it is required for the core biometric capture feature to function.**

The fix is a locally-trusted TLS certificate issued by `mkcert` and served by Caddy. No internet or public CA is needed. Everything is self-contained within the barangay office network.

> **Why not just use the `--unsafely-treat-insecure-origin-as-secure` Chrome flag?**
> That flag is a temporary developer workaround. It must be set manually on every client device, it is not available on all browsers, it disables other security protections, and it is not appropriate for a production deployment. The correct solution is HTTPS with a locally-trusted certificate, which takes about 10 minutes to set up and works on all browsers without any client-side configuration.

---

### Recommended Stack: Waitress + Caddy

| Component | Role | Why |
|---|---|---|
| **Django** | Application server | The FANS-C application logic, database, FaceNet pipeline |
| **Waitress** | WSGI server | Pure-Python, no compilation needed, reliable on Windows, handles concurrent requests |
| **Caddy** | Reverse proxy + TLS | Single binary, zero configuration for local HTTPS, handles certificates automatically with mkcert integration |
| **mkcert** | Local CA + certificate tool | Issues browser-trusted certificates for local hostnames on LAN without internet |

**Why Caddy instead of nginx?**

Caddy is a single `.exe` file with no dependencies. On Windows, nginx requires manual configuration of multiple files, a separate TLS configuration, and does not integrate with `mkcert` as cleanly. For a barangay deployment, Caddy's simplicity is a significant practical advantage. Caddy's `Caddyfile` format is also much easier to understand and audit than nginx config.

**Why Waitress instead of Django's runserver?**

Django's development server (`manage.py runserver`) is explicitly not designed for production use. It handles one request at a time and is not suitable when multiple staff devices submit verification requests simultaneously. Waitress is a simple, reliable WSGI server that handles concurrent requests correctly and runs well inside a Windows environment without compilation.

---

### How Requests Flow

```
  Staff device browser
          |
          | HTTPS request to https://fans-barangay.local (port 443)
          | TLS certificate issued by local mkcert CA (browser-trusted)
          |
          v
  Caddy (on server machine, listening on 0.0.0.0:443)
    - Terminates TLS (decrypts HTTPS)
    - Adds X-Forwarded-Proto: https header
    - Forwards plain HTTP to Waitress
          |
          | Plain HTTP to 127.0.0.1:8000 (internal only, never leaves server)
          v
  Waitress (on server machine, listening on 127.0.0.1:8000)
    - WSGI server, handles concurrent requests
    - Passes request to Django application
          |
          v
  Django application
    - Reads X-Forwarded-Proto header (SECURE_PROXY_SSL_HEADER setting)
    - Sets secure session and CSRF cookies correctly
    - Runs FaceNet pipeline, queries database, returns response
          |
          v
  Response travels back up the same chain to the browser
```

Django only ever sees plain HTTP from `127.0.0.1`. It never handles TLS directly. Caddy owns the certificate and encryption. This is the standard reverse-proxy pattern used by virtually every production web deployment.

---

### Why `fans-barangay.local` Instead of a Raw IP

| Criterion | `http://192.168.1.77:8000` | `https://fans-barangay.local` |
|---|---|---|
| Camera access on client devices | Blocked (not a secure context) | Works |
| Memorable for staff | Hard to remember a raw IP | Easy hostname |
| Survives IP change (DHCP reassignment) | Breaks — all clients must update | Update hosts file once on server side |
| Certificate issuance | `mkcert` does not issue for raw IPs by default | `mkcert` issues for hostnames cleanly |
| Looks professional | Raw IP in address bar | Hostname in address bar |

---

### Step-by-Step: Secure Windows LAN Deployment

This is a one-time setup on the server machine. Client devices need only a hosts file entry (or router DNS entry) — no software installation.

#### Prerequisites

- Python 3.11 and project dependencies already installed (see [Barangay LAN Deployment Guide](#step-by-step-setting-up-the-central-server))
- The project is at `D:\FANS\FANS-C` (or your chosen path)
- `.env` is configured with `DEBUG=False` and valid `SECRET_KEY` / `EMBEDDING_ENCRYPTION_KEY`
- Admin account already created with `python manage.py createsuperuser`

#### Step 1 — Install Waitress

```powershell
.\.venv\Scripts\activate
pip install waitress
```

Verify it works:

```powershell
waitress-serve --listen=127.0.0.1:8000 fans.wsgi:application
```

You should see `Serving on http://127.0.0.1:8000`. Open `http://127.0.0.1:8000` in a browser on the server machine and confirm the login page loads. Press `Ctrl+C` to stop.

#### Step 2 — Install mkcert

`mkcert` is a small Windows executable that creates a local Certificate Authority and issues TLS certificates that browsers trust automatically (after the CA is installed).

1. Download the latest `mkcert-v*-windows-amd64.exe` from the mkcert releases page
2. Rename it to `mkcert.exe` and copy it to `C:\Windows\System32\` (or any folder in your PATH)
3. Open PowerShell **as Administrator** and install the local CA:

```powershell
mkcert -install
```

This adds a root certificate to Windows' Trusted Root store and to Firefox's NSS store. You will see a prompt to confirm — click Yes. This step is done once per machine and affects only the local server machine. Client devices are handled separately (see hostname resolution section).

#### Step 3 — Issue a Certificate for `fans-barangay.local`

In PowerShell (does not need to be Administrator):

```powershell
cd D:\FANS\FANS-C
mkcert fans-barangay.local 192.168.1.77 localhost 127.0.0.1
```

Replace `192.168.1.77` with your server's actual LAN IP address.

This creates two files in the current directory:

```
fans-barangay.local+3.pem       -- the certificate (public)
fans-barangay.local+3-key.pem   -- the private key (keep this secret)
```

The `+3` suffix means the certificate covers four names: the hostname, the LAN IP, localhost, and 127.0.0.1.

#### Step 4 — Create a Caddyfile

Create a file named `Caddyfile` (no extension) in the project root (`D:\FANS\FANS-C\Caddyfile`):

```
fans-barangay.local {
    tls D:\FANS\FANS-C\fans-barangay.local+3.pem D:\FANS\FANS-C\fans-barangay.local+3-key.pem

    reverse_proxy 127.0.0.1:8000 {
        header_up X-Forwarded-Proto https
    }
}
```

**What each line does:**
- `fans-barangay.local` — Caddy listens on port 443 for this hostname
- `tls ...` — uses the mkcert certificate and key (no automatic certificate fetching, no internet needed)
- `reverse_proxy 127.0.0.1:8000` — forwards requests to Waitress
- `header_up X-Forwarded-Proto https` — sets the header Django reads to know the request came over HTTPS

#### Step 5 — Download and Install Caddy

1. Download the latest `caddy_*_windows_amd64.zip` from the Caddy releases page
2. Extract `caddy.exe` to `C:\Windows\System32\` (or any folder in your PATH)
3. Verify it works:

```powershell
caddy version
```

#### Step 6 — Configure Django `.env` for HTTPS

Open `D:\FANS\FANS-C\.env` and add or update these values:

```
DEBUG=False
ALLOWED_HOSTS=fans-barangay.local,192.168.1.77,localhost,127.0.0.1

# Required: Caddy forwards plain HTTP to Django but browser uses https://
# Without this, Django rejects all form POSTs with HTTP 403 Forbidden
CSRF_TRUSTED_ORIGINS=https://fans-barangay.local

# Required: tells Django to trust the X-Forwarded-Proto header from Caddy
# This makes session and CSRF cookies use the Secure flag correctly
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https

# Required: use the Host header from Caddy (fans-barangay.local), not 127.0.0.1
USE_X_FORWARDED_HOST=True
```

#### Step 7 — Open Windows Firewall for Port 443

```powershell
# Run as Administrator
netsh advfirewall firewall add rule `
  name="FANS-C Caddy HTTPS" `
  dir=in action=allow protocol=TCP localport=443
```

Port 8000 does **not** need a firewall rule — Waitress binds to `127.0.0.1:8000` (loopback only) so it is not reachable from outside the server machine.

#### Step 8 — Start Waitress and Caddy

Open two PowerShell windows on the server machine:

**Window 1 — Start Waitress:**

```powershell
cd D:\FANS\FANS-C
.\.venv\Scripts\activate
waitress-serve --listen=127.0.0.1:8000 fans.wsgi:application
```

**Window 2 — Start Caddy:**

```powershell
cd D:\FANS\FANS-C
caddy run --config Caddyfile
```

You should see Caddy output similar to:

```
{"level":"info","msg":"serving initial configuration"}
{"level":"info","msg":"serving","address":"fans-barangay.local:443"}
```

#### Step 9 — Test on the Server Machine

Open a browser on the server machine and go to `https://fans-barangay.local`. You should see the FANS-C login page with a valid padlock (no certificate warning) because the mkcert CA was installed on this machine in Step 2. Log in and confirm the verification page loads and the camera works.

---

### Hostname Resolution: `fans-barangay.local`

The hostname `fans-barangay.local` must resolve to the server's LAN IP address on every device that needs to connect. There are two ways to do this.

#### Option A — Hosts File (Small Deployment / Demo)

Edit the `hosts` file on each client device. This is the simplest approach and requires no router configuration.

**On Windows client devices (run as Administrator):**

```powershell
notepad C:\Windows\System32\drivers\etc\hosts
```

Add this line (replace `192.168.1.77` with your server's actual LAN IP):

```
192.168.1.77    fans-barangay.local
```

Save and close. No restart needed — open a new browser tab and go to `https://fans-barangay.local`.

**On Android / iOS clients:**

Android and iOS do not allow direct hosts file editing. Use Option B (router DNS) for mobile devices, or use a third-party DNS app.

For a barangay deployment where clients are primarily Windows PCs or laptops, Option A is sufficient.

#### Option B — Router / Local DNS (Preferred if Available)

If the office router supports custom DNS entries (most modern routers do under Advanced Settings > DNS or Local Hosts):

1. Log in to the router admin panel (usually `192.168.1.1` or `192.168.0.1`)
2. Find the local DNS or static host mapping section
3. Add: `fans-barangay.local` → `192.168.1.77`
4. Save and apply

All devices on the network will now automatically resolve `fans-barangay.local` without any per-device hosts file changes. This is the preferred approach for larger deployments or when client devices change frequently.

#### Installing the mkcert CA on Client Devices

After configuring hostname resolution, client devices also need to trust the mkcert root certificate so the browser shows a padlock instead of a certificate warning.

**Option 1 — Copy and install the mkcert root CA manually (Windows):**

On the server machine, find the mkcert CA certificate:

```powershell
mkcert -CAROOT
```

This prints a path like `C:\Users\YourName\AppData\Local\mkcert`. Copy `rootCA.pem` from that folder to each client device (via USB or shared folder).

On each Windows client, run as Administrator:

```powershell
certutil -addstore -f "Root" rootCA.pem
```

After this, Chrome and Edge on that client will trust the certificate. Firefox uses its own store — import `rootCA.pem` via Firefox Settings > Privacy & Security > Certificates > Import.

**Option 2 — Use a self-signed certificate and click through the browser warning (demo only):**

If you skip the CA installation, browsers will show a "Your connection is not private" warning. You can click "Advanced" and "Proceed anyway" to continue. This still gives you HTTPS and camera access — the only difference is the visual warning. This is acceptable for a controlled barangay demo but not ideal for regular staff use.

**Note:** This certificate warning only appears because the CA is local (not a public CA like Let's Encrypt). The encryption itself is identical — data is fully encrypted in transit. The warning means "the browser does not recognize who issued this certificate", not "the connection is insecure."

---

### Django Settings for HTTPS Behind Caddy

This is a summary of what must be set in `.env` for the HTTPS deployment to work correctly. All of these settings are already supported by `fans/settings.py` — no code changes are needed.

```
# Deployment identity
DEBUG=False
SECRET_KEY=<strong random value>

# Accept requests for the HTTPS hostname and internal addresses
ALLOWED_HOSTS=fans-barangay.local,192.168.1.77,localhost,127.0.0.1

# Tell Django to trust HTTPS POST requests coming through Caddy
# Without this: HTTP 403 on every form submission (login, verification, etc.)
CSRF_TRUSTED_ORIGINS=https://fans-barangay.local

# Tell Django the real protocol (https) from the X-Forwarded-Proto header
# Without this: session and CSRF cookies lack the Secure flag
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https

# Use the hostname from the forwarded Host header
USE_X_FORWARDED_HOST=True

# Face embedding security (keep stable across server restarts)
EMBEDDING_ENCRYPTION_KEY=<Fernet key from: python manage.py generate_key>

# Offline sync disabled for centralized LAN mode
SYNC_API_URL=
```

**What each setting does in the HTTPS context:**

| Setting | What happens without it |
|---|---|
| `CSRF_TRUSTED_ORIGINS` | Every form POST returns HTTP 403. Login fails. Verification fails. |
| `SECURE_PROXY_SSL_HEADER` | `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` are set based on `not DEBUG`. Without this header setting, Django may not set the `Secure` flag correctly. |
| `USE_X_FORWARDED_HOST` | Django uses `127.0.0.1` as the host in redirect URLs and error messages instead of `fans-barangay.local`. |
| `ALLOWED_HOSTS` includes hostname | Django returns HTTP 400 Bad Request for requests arriving with a Host header it does not recognise. |

---

### Verifying Camera Access from a Client Device

After completing the setup, run this checklist from a client device:

1. Hostname resolution: in Command Prompt, run `ping fans-barangay.local` — it should reply from `192.168.1.77`
2. HTTPS access: open `https://fans-barangay.local` — padlock should appear (no warning, if CA installed)
3. Login: log in with a staff account — login page should submit without HTTP 403
4. Verification page: navigate to a beneficiary's verification page
5. Camera: click the capture button — the browser should request camera permission (not silently block it)
6. Capture: allow camera access, click Capture and Verify — the face pipeline should run normally

If step 5 fails (camera blocked despite HTTPS): check that the browser address bar shows `https://` and not `http://`. If it shows `http://`, Caddy is not routing the request — confirm `caddy run` is active and the firewall rule for port 443 is in place.

---

### Insecure Browser Flags Are Not the Answer

Some guides suggest using Chrome's `--unsafely-treat-insecure-origin-as-secure` flag to allow camera access on plain HTTP origins. **Do not use this as the production solution.** Here is why:

| Issue | Detail |
|---|---|
| Must be set on every client device | No central control — each machine needs a custom browser shortcut |
| Requires command-line browser launch | Normal shortcuts do not pass flags; staff must use a special shortcut |
| Not available on Firefox or Safari | Only Chrome/Edge support this flag |
| Disables other security protections | The flag affects more than just camera access |
| Not appropriate for real deployment | It signals to any reviewer that the security model is bypassed rather than solved |

The HTTPS + Caddy + mkcert solution described in this section takes approximately the same time to set up and requires no per-client configuration beyond a hosts file entry and a one-time CA installation. It is the correct solution.

---

### Security Notes for HTTPS Deployment

1. **Protect the certificate private key.** The file `fans-barangay.local+3-key.pem` must not be accessible to non-administrator users. Store it in the project folder with restricted permissions. Anyone who obtains this key can impersonate your server to devices that trust the mkcert CA.

2. **The mkcert CA is machine-specific.** The CA keypair in `%LOCALAPPDATA%\mkcert` must be backed up alongside `.env`. If the server machine is replaced, regenerate the CA on the new machine and re-distribute `rootCA.pem` to client devices. Certificates issued by the old CA will not be trusted by the new CA.

3. **Do not use the mkcert CA for anything other than this deployment.** The CA is trusted by all browsers on machines where it is installed. Keep it on the server machine only.

4. **Waitress listens on 127.0.0.1 only.** This is intentional — Waitress is not exposed to the network directly. Only Caddy is. If you change Waitress to listen on `0.0.0.0`, plain HTTP access from other devices becomes possible, bypassing the HTTPS requirement.

5. **Set `DEBUG=False` before starting Caddy.** With `DEBUG=True`, Django's detailed error pages will be visible to all LAN users and will expose internal paths, settings, and code.

---

### Defense Notes: Why This Stack

**For the academic reviewer or panel evaluator:**

**Why HTTPS is architecturally necessary, not just recommended:**

The `getUserMedia` webcam API is gated on a secure context (HTTPS or localhost) by all modern browsers as a W3C specification requirement. This is not a browser quirk that can be configured away — it is a security boundary enforced at the browser level to prevent malicious websites from silently accessing cameras. For a biometric system where camera access is the primary input, HTTPS is a hard requirement for multi-device deployment.

**Why Caddy over nginx for this context:**

Nginx is a capable production reverse proxy but has a steeper configuration curve and no built-in integration with local certificate tools on Windows. Caddy's configuration is a single Caddyfile that a reviewer can read and understand in 30 seconds. For an academic capstone, demonstrating a working secure deployment with minimal configuration is more appropriate than a complex nginx setup.

**Why mkcert over self-signed certificates:**

A manually generated self-signed certificate with `openssl` requires either installing the CA on every client (same as mkcert) or clicking through browser warnings. `mkcert` automates the CA creation and installation and is specifically designed for local development and LAN deployment. It is widely used and its security model (trust limited to machines where the CA is explicitly installed) is appropriate for a controlled barangay environment.

**Why Waitress over Django runserver:**

Django's runserver documentation explicitly states it should not be used in production. It uses a single-threaded request loop which would queue all concurrent verification requests from multiple staff devices. Waitress is a production-grade WSGI server that handles multiple concurrent requests correctly, requires no compilation, and installs with a single `pip install` command.

---

## Windows .exe Packaging and Distribution

This section covers everything needed to package FANS-C as a Windows desktop application that can be installed and launched like standard Windows software  --  no Python installation, no virtual environment activation, no command line required on the target machine.

The existing Django + FaceNet architecture is completely preserved. The packaging layer wraps the running system in a launcher executable and a standard Windows installer.

---

### Packaging Overview

The packaging system has four layers:

| Layer | File | What it does |
|---|---|---|
| Launcher | `launcher.py` | Starts Django, runs migrations, opens browser |
| PyInstaller spec | `fans_c.spec` | Defines what gets bundled into the exe |
| Build script | `build_exe.ps1` | Automates the full build process |
| Installer script | `installer/fans_c.iss` | Compiles the Windows installer with Inno Setup |

**User experience after installation:**

1. User runs `FANS-C-Setup.exe` (the installer).
2. App is installed to `%LocalAppData%\Programs\FANS-C\`.
3. A Start Menu shortcut and optional desktop shortcut are created.
4. User creates `.env` in the install directory (one-time setup).
5. User opens the shortcut -> FANS-C.exe starts -> Django server launches -> browser opens automatically.

---

### How the Launcher Works

`launcher.py` is the entry point for the packaged executable. It runs the following sequence on every launch:

**1. Path setup**
When frozen by PyInstaller (`sys.frozen == True`), `sys.executable` points to `FANS-C.exe`. All bundled files (Django apps, templates, static files) are in the same directory. `BASE_DIR` is set to that directory so Django's `settings.py` resolves all paths correctly.

**2. Preflight checks**
Before Django starts, the launcher validates:
- `.env` exists in the same directory as `FANS-C.exe`
- `EMBEDDING_ENCRYPTION_KEY` is set and non-empty in `.env`
- The encryption key is a valid Fernet key (format check)

If any check fails, a user-friendly dialog box is shown explaining what is wrong and how to fix it. No confusing Python tracebacks are shown to end users.

**3. Django setup and migrations**
- `os.environ['DJANGO_SETTINGS_MODULE']` is set to `fans.settings`.
- `DEBUG` is forced to `False` in packaged mode so whitenoise serves static files correctly.
- `django.setup()` initialises the Django application.
- `migrate --noinput` runs automatically. This creates `db.sqlite3` on the first launch and applies any pending migrations silently.

**4. Server startup**
- When packaged: **waitress** is used as the WSGI server (see [onedir vs onefile](#onedir-vs-onefile)).
- When running from source: Django's `runserver --noreload` is used (developer-friendly).
- The server runs on `http://127.0.0.1:8765/` in a background thread.

Port `8765` was chosen specifically because it avoids conflicts with common development servers (`8000`, `8080`, `3000`, `5000`).

**5. Browser opening**
The launcher polls `127.0.0.1:8765` every 500 ms until the server responds (up to 90 seconds). This accounts for TensorFlow's slow first-import time (10-20 seconds on average hardware). Once the server is ready, `webbrowser.open()` opens the system in the user's default browser. No fixed sleep  --  it opens exactly when ready.

**6. Keep-alive**
The main thread waits on the server thread so the process stays alive. When the user closes the console window, the OS terminates all threads.

---

### Files Added for Packaging

```
launcher.py           --  Windows desktop launcher (entry point)
fans_c.spec           --  PyInstaller build specification
build_exe.ps1         --  PowerShell build automation script
installer/
  fans_c.iss          --  Inno Setup 6 installer script
  Output/             --  Created by Inno Setup (contains FANS-C-Setup.exe)
dist/
  FANS-C/             --  Created by PyInstaller (the packaged application)
    FANS-C.exe        --  The launcher executable
    .env.example      --  Template for user to create .env
    SETUP.md          --  First-run instructions
    fans/             --  Django project package
    accounts/         --  Auth app
    beneficiaries/    --  Core beneficiary app
    verification/     --  FaceNet verification app
    logs/             --  Audit log app
    templates/        --  Django templates
    static/           --  Source static files
    staticfiles/      --  Collected/hashed static files (whitenoise)
    (+ tensorflow, keras, cv2, and all other dependencies)
```

---

### Build Prerequisites

The build machine (where you run `build_exe.ps1`) needs:

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11.x | TensorFlow 2.13 requires Python 3.11. Python 3.12+ is not supported. |
| Project `.venv` |  --  | Run `.\setup.ps1` first if it does not exist |
| Inno Setup 6 | 6.x | For building the installer only. [Download](https://jrsoftware.org/isdl.php) |
| UPX | any | Optional. Compresses exe slightly. [Download](https://upx.github.io/) |

PyInstaller and waitress are installed automatically by `build_exe.ps1`  --  you do not need to install them manually.

---

### Step 1  --  Build the .exe

```powershell
# From the project root, in a normal PowerShell window (not admin required)
.\build_exe.ps1
```

**What the build script does:**

1. Verifies Python 3.11 is in `.venv`
2. Installs `pyinstaller>=6.3` and `waitress>=3.0` into `.venv`
3. Runs `python manage.py collectstatic --noinput --clear` (updates `staticfiles/`)
4. Runs `pyinstaller fans_c.spec --noconfirm`
5. Copies `.env.example` and `SETUP.md` into `dist\FANS-C\`

**Clean rebuild:**

```powershell
.\build_exe.ps1 -Clean
```

**Skip collectstatic (faster, when only Python code changed):**

```powershell
.\build_exe.ps1 -SkipCollectStatic
```

**Expected build time:**

| Machine | First build | Subsequent builds |
|---|---|---|
| Mid-range laptop | 10-20 minutes | 3-7 minutes |
| Workstation | 5-10 minutes | 2-4 minutes |

The slow part is `collect_all('tensorflow')` which walks thousands of TensorFlow files. PyInstaller caches this between builds.

**Expected output size:** 2-4 GB in `dist\FANS-C\` (mostly TensorFlow and OpenCV DLLs).

---

### Step 2  --  Test the Packaged App

Before building the installer, always test the packaged app locally:

```powershell
# 1. Create a test .env in the dist folder
Copy-Item .env.example dist\FANS-C\.env

# 2. Edit dist\FANS-C\.env  --  set EMBEDDING_ENCRYPTION_KEY and SECRET_KEY
notepad dist\FANS-C\.env

# 3. Run the packaged executable
.\dist\FANS-C\FANS-C.exe
```

**What to verify:**

- The console window appears with the FANS-C banner
- Preflight checks pass (no error dialogs)
- "Applying database migrations" runs without errors
- "Server is ready" message appears
- The browser opens to `http://127.0.0.1:8765/`
- The login page loads with CSS/JS (no broken styles)
- Login works and the dashboard loads
- Camera/webcam works for verification

**If the browser shows unstyled pages:**
Static files are not being served. Confirm `DEBUG=False` is set (or not overridden) and that `staticfiles/` was populated by `collectstatic`. Check the console for whitenoise errors.

**If the console shows import errors:**
Add the missing module to `hiddenimports` in `fans_c.spec` and rebuild.

---

### Step 3  --  Build the Installer

After the packaged app works correctly:

**Using the Inno Setup IDE:**
1. Install Inno Setup 6 from [jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php)
2. Open `installer\fans_c.iss` in Inno Setup Compiler
3. Press **F9** (Build -> Compile)
4. The installer is created at `installer\Output\FANS-C-Setup.exe`

**Using the command line:**
```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\fans_c.iss
```

The installer bundles the entire `dist\FANS-C\` directory (2-4 GB) into a single compressed `.exe` using LZMA solid compression. Expect the installer to be roughly half the size of the dist folder.

---

### Step 4  --  Distribute to Another Machine

**What to give the user:**
- `FANS-C-Setup.exe` (the installer)

No manual key exchange is needed for a fresh installation.
The launcher generates a unique `EMBEDDING_ENCRYPTION_KEY` automatically on first run.

---

#### Case A  --  Fresh install (no existing beneficiary data)

1. Run `FANS-C-Setup.exe`. No admin rights required.
2. Accept the install directory (`%LocalAppData%\Programs\FANS-C\`).
3. Optionally create a desktop shortcut.
4. Leave the "Launch FANS-C now" checkbox checked and click Finish.
5. On first launch, FANS-C creates `.env` automatically with generated keys
   and shows a confirmation dialog.
6. On the very first launch, FaceNet model weights (~90 MB) are downloaded to
   `%USERPROFILE%\.keras\`. Ensure internet access is available that one time.

**Subsequent launches:** No internet required. Everything works offline.

**Back up `.env` after first launch.** It is stored at:
```
%LocalAppData%\Programs\FANS-C\.env
```
The `EMBEDDING_ENCRYPTION_KEY` in that file is the only way to decrypt face
embeddings. If it is lost, all registered beneficiaries must re-register.

---

#### Case B  --  Restoring an existing database to a new machine

Use this path when you are migrating an existing deployment (e.g. replacing
a broken workstation, or setting up a second workstation that shares the same
beneficiary records).

**What to give the new machine:**
- `FANS-C-Setup.exe`
- The `.env` file (or just the `EMBEDDING_ENCRYPTION_KEY` value) from the
  original installation

**Steps:**

1. Run `FANS-C-Setup.exe`. At the finish page, **uncheck** "Launch FANS-C now".
2. Copy `db.sqlite3` and `media/` from the original machine to the install
   directory (`%LocalAppData%\Programs\FANS-C\`).
3. Open `%LocalAppData%\Programs\FANS-C\.env` in a text editor.
   - If `.env` was automatically created during install, replace the generated
     `EMBEDDING_ENCRYPTION_KEY` with the key from the original `.env`.
   - If `.env` does not exist yet, create it from `.env.example` and paste in
     the original `EMBEDDING_ENCRYPTION_KEY`.
4. Launch FANS-C from the Start Menu.

**Why the key must match:** Every face embedding is encrypted with
`EMBEDDING_ENCRYPTION_KEY` using AES-128 (Fernet). If the key on the new
machine differs from the key used at registration time, Django can load the
database but every verification attempt will fail with a decryption error.
The face data itself is never stored as a plain image.

---

### What Is and Is Not Bundled

| Item | Bundled? | Reason |
|---|---|---|
| Django apps (`fans/`, `accounts/`, etc.) | Yes | Required for the application to run |
| Templates | Yes | Required for the web UI |
| `static/` (source assets) | Yes | Referenced during development/fallback |
| `staticfiles/` (collected assets) | Yes | Required by whitenoise in production mode |
| TensorFlow, keras-facenet, mtcnn, OpenCV | Yes | Core ML dependencies |
| All other Python dependencies | Yes | PyInstaller bundles everything from `.venv` |
| `.env` | **No** | Created automatically by the launcher on first run |
| `db.sqlite3` | **No** | Created fresh by migrate on first launch |
| `media/` (uploaded photos) | **No** (by default) | Runtime data -- should not be in a fresh install |
| FaceNet model weights | **No** | Downloaded to `~/.keras/` on first import (~90 MB) |
| `.venv/` | **No** | PyInstaller extracts the needed files; the venv itself is not needed |

---

### Keras-FaceNet Model Weights

keras-facenet downloads the FaceNet model weights (~90 MB) from the internet to `%USERPROFILE%\.keras\keras_facenet\` on the **first time** `keras_facenet` is imported. This is a one-time download per Windows user account.

**If the target machine has no internet access:**

Pre-populate the weights directory before packaging or before first run:

```powershell
# On a machine with internet access, import keras_facenet to trigger the download
python -c "import keras_facenet"

# The weights are at:
# %USERPROFILE%\.keras\keras_facenet\
# Copy this folder to the same path on the target machine.
```

Alternatively, add the weights directory to the `datas` list in `fans_c.spec`:

```python
import os
keras_home = os.path.join(os.path.expanduser('~'), '.keras', 'keras_facenet')
if os.path.isdir(keras_home):
    project_datas.append((keras_home, os.path.join('.keras', 'keras_facenet')))
```

Then set `KERAS_HOME` to point to the bundle directory in `launcher.py`:
```python
if getattr(sys, 'frozen', False):
    os.environ['KERAS_HOME'] = BASE_DIR
```

---

### onedir vs onefile

**This project uses `onedir` (recommended). Do not switch to `onefile`.**

| | onedir | onefile |
|---|---|---|
| How it works | All files extracted once to `dist/FANS-C/` at install time | All files re-extracted to `%TEMP%` on every launch |
| Launch time | 2-5 seconds (TF import only) | 30-120 seconds (extract 2+ GB on every launch) |
| Disk usage | One-time 2-4 GB in install dir | 2-4 GB in `%TEMP%` per launch (cleared on restart) |
| Antivirus compatibility | Good (stable file paths) | Poor (AV tools flag DLL drops from `%TEMP%`) |
| Suitable for TensorFlow | Yes | No  --  startup time is unacceptably slow |

---

### TensorFlow and PyInstaller Caveats

**1. Python version must be 3.11**
TensorFlow 2.13 only supports Python 3.10 and 3.11. Python 3.12+ will produce a `DLL load failed` error at import time. PyInstaller must be run from the `.venv` that uses Python 3.11.

**2. Build time is long on the first run**
`collect_all('tensorflow')` walks thousands of files. Expect 5-20 minutes for the first build. Subsequent builds use the PyInstaller cache (`build/` directory) and are much faster.

**3. UPX must not compress TensorFlow DLLs**
UPX compression of `_tensorflow_*.pyd` and `_pywrap_*.pyd` files frequently corrupts them. The spec file excludes these files from UPX compression via the `upx_exclude` list.

**4. console=True is intentional**
The EXE is built with `console=True`. This keeps the terminal window visible so staff can see Django logs, verification scores, and error messages. To run silently, set `console=False` in `fans_c.spec` and ensure all logging is directed to a file in `settings.py`.

**5. TensorFlow GPU variant not supported**
The project uses `tensorflow-cpu`. If a GPU build is needed, the spec file would need to be updated with the correct CUDA DLLs in `binaries`.

**6. Long path issue on Windows**
If PyInstaller fails with `OSError: [Errno 2] No such file or directory` on TensorFlow files, your project path is too long. Move the project to a shorter path (`D:\FANS`) and rebuild. Alternatively, enable Windows long path support:
```powershell
# Run as administrator
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
    -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

---

### Common Packaging Problems and Fixes

**`build_exe.ps1` fails immediately with a parser error or garbled output**

Root cause: the `.ps1` file contains non-ASCII characters (em dashes, bullet points,
arrow symbols, box-drawing characters) that PowerShell misreads when the console code
page is not UTF-8.  This is a known Windows issue -- PowerShell versions before 7 and
consoles with code page 1252 or 437 silently misinterpret multi-byte UTF-8 sequences
and report syntax errors on otherwise valid lines.

All packaging files (`build_exe.ps1`, `launcher.py`, `fans_c.spec`, `installer/fans_c.iss`)
have been scrubbed to pure 7-bit ASCII.  If you ever edit these files and paste content
from a browser or word processor, watch for:

| Unsafe character | Looks like | ASCII replacement used here |
|---|---|---|
| U+2014 em dash | -- | ` -- ` (two hyphens with spaces) |
| U+2013 en dash | - | `-` (hyphen) |
| U+2022 bullet | * | `*` (asterisk) |
| U+2192 right arrow | -> | `->` |
| U+2500 box drawing | - | `-` |
| U+201C/201D smart quotes | " " | `"` |
| U+2018/2019 smart quotes | ' ' | `'` |

To detect non-ASCII characters in a file before committing:

```powershell
# PowerShell: scan a file for non-ASCII bytes
$bytes = [System.IO.File]::ReadAllBytes('build_exe.ps1')
$bad = $bytes | Where-Object { $_ -gt 127 }
if ($bad) { Write-Host "Non-ASCII bytes found: $($bad.Count)" } else { Write-Host "Clean" }
```

```python
# Python: scan any file
with open('build_exe.ps1', 'rb') as f:
    bad = [i for i, b in enumerate(f.read()) if b > 127]
print('non-ASCII at bytes:', bad[:10] if bad else 'none')
```

---

**`build_exe.ps1` crashes at the collectstatic step with a NativeCommandError or RuntimeWarning**

Symptom: the script dies at Step 3 with output similar to:

```
[warn] ...\settings.py:221: RuntimeWarning: SECRET_KEY is the default placeholder...
NativeCommandError
```

Root cause: `$ErrorActionPreference = 'Stop'` is active globally.  When Python writes
to stderr (Django emits a `RuntimeWarning` about the placeholder `SECRET_KEY` at import
time), PowerShell wraps that stderr line in an `ErrorRecord` object.  Under `Stop`,
any `ErrorRecord` flowing through `ForEach-Object` becomes a terminating error --
even though collectstatic itself exited with code 0.

This is fixed in the current `build_exe.ps1`.  The collectstatic block now:

1. Temporarily lowers `$ErrorActionPreference` to `'Continue'` for that one call only.
2. Type-checks every pipeline object: `ErrorRecord` items (stderr) are shown as
   `[warn]` in yellow; plain strings (stdout) are shown in gray.
3. Captures `$LASTEXITCODE` after the pipeline to detect real failures.
4. Restores `$ErrorActionPreference = 'Stop'` unconditionally before moving on.

The `SECRET_KEY` warning itself is expected when your `.env` still has the placeholder
value.  It does not prevent collectstatic from running.  Set a real `SECRET_KEY` in
`.env` to suppress it.

If you see this error on a modified copy of `build_exe.ps1`, apply the same pattern:

```powershell
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'

& $yourCommand 2>&1 | ForEach-Object {
    if ($_ -is [System.Management.Automation.ErrorRecord]) {
        Write-Host "  [warn] $_" -ForegroundColor Yellow
    } else {
        Write-Host "  $_" -ForegroundColor DarkGray
    }
}
$exitCode = $LASTEXITCODE
$ErrorActionPreference = $prevEAP

if ($exitCode -ne 0) { exit 1 }
```

---

**`ModuleNotFoundError: No module named 'fans'` at runtime**

The Django project root is not in the bundle's `sys.path`. In `launcher.py`, `BASE_DIR` is added to `sys.path` before Django starts. If this error occurs, ensure `launcher.py` is being used as the entry point (not `manage.py`).

**`ModuleNotFoundError: No module named 'xyz'` for a Django app or dependency**

Add `'xyz'` to the `hiddenimports` list in `fans_c.spec` and rebuild. This is the most common packaging error  --  Django and TensorFlow both use many string-based dynamic imports that static analysis misses.

**Missing template or static file (404 on CSS/JS)**

1. Confirm `collectstatic` ran before the build (`build_exe.ps1` runs it automatically).
2. Confirm `staticfiles/` in `project_datas` includes the right path.
3. Confirm `DEBUG=False` is set (the launcher forces this when `sys.frozen` is True).

**`PermissionError` writing `db.sqlite3`**

The install directory must be writable. The installer installs to `%LocalAppData%\Programs\FANS-C\` which is always writable by the current user. If you changed the install path to `Program Files`, the database write will fail on a standard-user account.

**App starts but verification gives `Model status: MOCK`**

TensorFlow or keras-facenet failed to import in the bundle. Check the console for `ImportError` or `DLL load failed` messages. The most common cause is a missing TensorFlow DLL  --  ensure the spec uses `collect_all('tensorflow')` (it does by default).

**Antivirus quarantines `FANS-C.exe`**

Some AV tools flag PyInstaller executables as suspicious. This is a false positive. Add `FANS-C.exe` and the `dist\FANS-C\` directory to the AV exclusion list. For institutional deployment, consider code-signing the executable.

**Inno Setup: `Source file does not exist` error**

`build_exe.ps1` must run successfully before Inno Setup is used. Confirm `dist\FANS-C\FANS-C.exe` exists before opening `installer\fans_c.iss`.

---

### Limitations of the Packaged Version

1. **No automatic updates.** A new installer must be built and distributed when the application is updated. The installer preserves existing `db.sqlite3` and `.env` during upgrades.

2. **Single-user per Windows account.** The app installs to `%LocalAppData%` which is per-user. On a multi-user machine, each Windows user would need their own installation and `.env` (with the same `EMBEDDING_ENCRYPTION_KEY`).

3. **No service/tray mode.** The app runs in a console window. Closing the console stops the server. A future improvement would be to run as a Windows service or system-tray application.

4. **FaceNet weights require internet on first launch.** Approximately 90 MB is downloaded from the internet on the very first launch on a new machine. Pre-populate `%USERPROFILE%\.keras\keras_facenet\` if internet is not available.

5. **Large distribution size.** The installer is approximately 1-2 GB due to TensorFlow. This is unavoidable  --  TensorFlow's minimum CPU-only footprint is large.

6. **Development server limitations.** When `waitress` is unavailable (fallback path), Django's `runserver --noreload` is used. This is not optimised for concurrent requests and is not suitable for high-volume production use. For a barangay workstation with one operator, this is not a concern.

7. **No PostgreSQL support in the packaged build.** The packaged build is configured for SQLite (`USE_SQLITE=True`). Switching to PostgreSQL in the packaged version would require `psycopg2-binary` to be added to the spec and the PostgreSQL server to be separately installed on the target machine.

