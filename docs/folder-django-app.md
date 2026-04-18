# Folder: Django Application Folders

This document covers the four main Django folders in the FANS-C project: `fans/` (project configuration), `accounts/` (user authentication), `beneficiaries/` (beneficiary management), and `verification/` (face verification engine).

---

## Overview

Django organizes a project into one project package and multiple app packages. Each app handles a specific part of the system:

```
fans/           Project root — settings, URL routing, WSGI
accounts/       User accounts, login, role-based access control
beneficiaries/  Beneficiary registration, records, data sync
verification/   FaceNet face verification, liveness detection
```

---

## fans/ — Django Project Configuration

### Purpose

The `fans/` folder is the Django project package. It is the top-level configuration that ties all apps together. It defines global settings, the URL routing table, and the WSGI entry point used by Waitress.

### Why it exists

Every Django project requires a project package that contains the settings file and URL configuration. This is where Django looks for the list of installed apps, the database configuration, middleware stack, and security settings.

### Important files inside

**fans/settings.py**
- Django's global configuration file
- Reads from `.env` (via python-dotenv) to load secrets and environment-specific settings
- Configures: database (SQLite or PostgreSQL), installed apps, middleware, static file paths, HTTPS settings (SECURE_PROXY_SSL_HEADER, USE_X_FORWARDED_HOST), WhiteNoise for static file serving, session security, CSRF protection
- Key settings sourced from `.env`: SECRET_KEY, DEBUG, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, EMBEDDING_ENCRYPTION_KEY, DEMO_MODE, LIVENESS_REQUIRED, face recognition thresholds

**fans/urls.py**
- Maps URL paths to views across all installed apps
- Includes URL patterns from `accounts.urls`, `beneficiaries.urls`, and `verification.urls`
- Serves the Django admin interface at `/admin/`
- Serves media files (uploaded images) in development

**fans/wsgi.py**
- The WSGI callable that Waitress imports to serve the Django application
- Waitress calls this as: `waitress-serve --listen=127.0.0.1:8000 fans.wsgi:application`

**fans/views.py**
- Project-level views (dashboard, home page, error pages)

**fans/context_processors.py**
- Adds global context variables available to all templates (e.g., system name, version, current user role)

### How it connects to the system

- Waitress imports `fans.wsgi:application` to serve the application
- Caddy forwards all HTTPS requests to Waitress, which passes them through Django's middleware stack defined in `fans/settings.py`
- All other apps (`accounts`, `beneficiaries`, `verification`) are listed in `INSTALLED_APPS` in settings.py — without that listing, Django ignores them entirely
- The `EMBEDDING_ENCRYPTION_KEY` from `.env` is read in settings.py and passed to the verification app for face embedding encryption

### Runtime flow

| Phase | How fans/ is involved |
|---|---|
| Setup | `manage.py migrate` reads settings.py to create database tables; `manage.py collectstatic` reads STATICFILES_DIRS |
| Startup | Waitress imports fans.wsgi:application and begins serving |
| Runtime | Every HTTP request passes through middleware defined in settings.py |
| All phases | settings.py is loaded once at startup and stays in memory for the process lifetime |

### Defense notes

**Why are settings in a Python file, not a JSON or YAML file?**
Django's settings.py is a Python module, which means it can use conditionals, environment variable reads, and imports. This flexibility is used in FANS-C to read all secrets from the `.env` file via `python-dotenv`, so no secrets are hardcoded.

**What breaks if settings.py is misconfigured?**
- `SECRET_KEY` missing: Django refuses to start
- `ALLOWED_HOSTS` missing: All requests are rejected with 400 Bad Request
- `CSRF_TRUSTED_ORIGINS` missing: Staff cannot submit forms (stipend distribution stops)
- `SECURE_PROXY_SSL_HEADER` missing: Django doesn't know it's behind HTTPS and may reject secure cookies

---

## accounts/ — User Authentication and Role Management

### Purpose

The `accounts/` app manages user accounts: login, logout, password management, and role-based access control. It defines the custom user model with three active FANS-C roles (Head Barangay, IT/Admin, Staff); the legacy `admin` role has been fully migrated to IT/Admin via database migration `accounts/0006`.

### Why it exists

Django's built-in user model has no application-specific roles. FANS-C extends it with a `CustomUser` model that adds a `role` field and helper properties used by every view decorator in the system.

### Role system

| Role | DB value | Properties that return True | Intended user |
|---|---|---|---|
| Head Barangay | `head_brgy` | `is_admin`, `is_head_barangay` | Barangay captain / operational admin |
| IT / Admin | `admin_it` | `is_admin`, `is_admin_it` | Technical administrator |
| Staff | `staff` | `is_staff_member` | Barangay encoder / frontline staff |
| ~~Admin (legacy)~~ | `admin` | `is_admin`, `is_admin_it` | **Fully migrated.** Migration `0006` converted all existing `admin` rows to `admin_it`. Not assignable to new users. Constant kept as safety fallback only. |

`is_admin` = head_brgy OR admin_it OR admin. Gates all management-level access.
`is_admin_it` = admin_it OR admin. Gates system-diagnostic, connection, and network pages.
`is_head_barangay` = head_brgy only. Gates Head-Barangay-exclusive actions (pending claim approval, password reset for admin accounts).

### Important files inside

**accounts/models.py**
- Defines `CustomUser` — extends Django's `AbstractUser`
- Adds `role` CharField and role-helper properties (`is_admin`, `is_admin_it`, `is_head_barangay`, `is_staff_member`)

**accounts/views.py**
- Login / logout views
- `change_password` — any logged-in user can change their own password; session is kept alive after the change
- `admin_reset_password` — Head Barangay can reset any user's password; IT/Admin can reset Staff accounts only; all resets logged in `AuditLog`

**accounts/forms.py**
- `LoginForm`, `UserCreateForm`, `UserUpdateForm` — role dropdowns show only the three active roles (Head Barangay, IT/Admin, Staff); the legacy `admin` value never appears for new users
- `PasswordChangeForm` — self-service change (requires current password)
- `AdminPasswordResetForm` — admin reset (no current password needed); runs Django's full password validator suite

**accounts/urls.py**
- `login/`, `logout/`
- `password/change/` — self-service change for any logged-in user
- `password/reset/<user_id>/` — admin reset (Head Barangay / IT/Admin only)

**accounts/admin.py**
- Registers `CustomUser` in Django's admin interface (`/admin/`)
- Allows IT/Admin to manage users directly from the admin panel

**accounts/decorators.py**
- `@admin_required` — restricts a view to admin-role users only
- `@staff_required` — restricts a view to authenticated users (admin or staff)
- Applied to views in `beneficiaries/` and `verification/` that require authentication

**accounts/management/commands/**

| Command | What it does |
|---|---|
| `create_admin.py` | Creates an admin-role user non-interactively (used in scripts) |
| `generate_key.py` | Generates a new Fernet encryption key (for EMBEDDING_ENCRYPTION_KEY) |
| `init_config.py` | Initializes required system configuration (called during setup) |
| `normalize_roles.py` | Ensures all user role values are valid (migration/cleanup tool) |
| `check_system.py` | System-level diagnostics from within Django |

### How it connects to the system

- All other apps (`beneficiaries`, `verification`) import `@admin_required` and `@staff_required` from `accounts.decorators` to protect their views
- `fans/settings.py` sets `AUTH_USER_MODEL = 'accounts.CustomUser'` to use the custom model system-wide
- The setup script calls `python manage.py createsuperuser` (which creates a Django superuser) and then separately sets the FANS-C `role = 'admin_it'` via the `create_admin` management command
- Both Django's `is_superuser`/`is_staff` flags and the FANS-C `role` field must be set for full admin access

### Runtime flow

| Phase | How accounts/ is involved |
|---|---|
| Setup | `migrate` creates the CustomUser table; `createsuperuser` creates the first admin user |
| Runtime (every request) | Django's session middleware validates the session; decorators check the role before allowing access |
| Daily use | Staff log in via the login view; session persists until logout or timeout |

### Defense notes

**Why a custom user model?**
FANS-C needs role-based access control beyond what Django's built-in permissions system provides out of the box. A custom user model with a `role` field is the standard Django approach for application-level roles. It also allows adding future fields (e.g., assigned barangay, phone number) without a separate profile model.

**What happens if the admin role is not set?**
A user created with `createsuperuser` gets Django's `is_superuser=True` but the FANS-C `role` field defaults to `staff`. If the role is not explicitly set to `admin_it` or `head_brgy`, the user can access the Django admin panel (via `is_superuser`) but cannot access FANS-C admin views (which check the `role` field). The `create_admin` management command handles this automatically.

---

## beneficiaries/ — Beneficiary Management

### Purpose

The `beneficiaries/` app manages senior citizen beneficiary records: registration, listing, editing, and data synchronization. Each beneficiary in the system has a profile with personal information and an enrolled face embedding (stored in the database, encrypted).

### Why it exists

The beneficiary registry is the core data layer of the system. Before any verification can happen, a beneficiary must be registered with their face. This app handles that registration process and provides the interface for managing the beneficiary list.

### Important files inside

**beneficiaries/models.py**
- `Beneficiary` model — represents a registered senior citizen
- Stores: name, date of birth, address, contact information, barangay assignment, face embedding (encrypted bytes), enrollment date, status

**beneficiaries/views.py**
- Registration view: collects personal information and captures a face image via the browser camera
- List view: displays all registered beneficiaries with search and filter
- Detail view: shows a single beneficiary's profile and verification history
- Edit view: update beneficiary information (Admin only)

**beneficiaries/forms.py**
- BeneficiaryRegistrationForm — validates all required fields for registration
- BeneficiaryUpdateForm — subset of fields for editing existing records

**beneficiaries/urls.py**
- Maps URLs for registration, list, detail, and edit views

**beneficiaries/admin.py**
- Registers `Beneficiary` in the Django admin panel
- Allows IT/Admin to inspect or edit records directly

**beneficiaries/sync.py**
- Synchronization logic for updating beneficiary records from an external data source (if configured)
- Called by the `sync_beneficiaries` management command

**beneficiaries/management/commands/sync_beneficiaries.py**
- Django management command to trigger a beneficiary data sync
- Can be run from the command line: `python manage.py sync_beneficiaries`

### How it connects to the system

- The `verification` app looks up beneficiary records (and their stored face embeddings) when processing a verification request
- The face embedding stored in `Beneficiary.face_embedding` is encrypted with `EMBEDDING_ENCRYPTION_KEY` from `.env` — the `verification` app decrypts it before comparing
- The `accounts` app's decorators protect beneficiary views — Staff can register and view; Admin can also edit
- The `templates/beneficiaries/` folder contains all HTML templates for beneficiary pages

### Runtime flow

| Phase | How beneficiaries/ is involved |
|---|---|
| Setup | `migrate` creates the Beneficiary table |
| Daily use (registration) | Staff fills out registration form, camera captures face, face embedding is computed by verification/face_utils.py and stored encrypted |
| Daily use (verification) | verification/ looks up the beneficiary record to retrieve the stored face embedding |
| Administration | Admin views the beneficiary list, checks for duplicates, manages records |

### Defense notes

**Why store face embeddings instead of photos?**
Face embeddings are compact (128 floating-point numbers vs. kilobytes for a photo), encrypted at rest, and are not directly reversible to a photo. Storing embeddings also means the computationally expensive FaceNet model only needs to run during enrollment — verification is just a vector comparison.

**What happens if the embedding key changes?**
If `EMBEDDING_ENCRYPTION_KEY` changes (or is not set, causing a random key to be generated each restart), all previously stored embeddings cannot be decrypted. Verification will fail for all previously enrolled beneficiaries. This is why backing up `.env` is critical.

---

## verification/ — Face Verification Engine

### Purpose

The `verification/` app is the core of the FANS-C system. It processes face verification requests: capturing a live camera image, running it through FaceNet to generate an embedding, comparing it against the stored embedding, and returning a match decision.

### Why it exists

Face verification is the primary innovation of FANS-C and requires dedicated logic separate from general Django views. The verification app encapsulates the FaceNet model loading, face detection (MTCNN), embedding generation, anti-spoofing (liveness detection), and the similarity comparison threshold logic.

### Important files inside

**verification/apps.py**
- `VerificationConfig(AppConfig)` — registers the app and runs `ready()` on Django startup
- `ready()` starts a background daemon thread (`fans-facenet-warmup`) that calls `get_facenet_model()` and `_get_mtcnn()` immediately after Django initializes
- This means the FaceNet model is loaded into memory by the time any staff opens a browser, eliminating the 5-15 second first-request delay that would otherwise occur when TensorFlow builds its computation graph
- If the model is unavailable (TensorFlow not installed), the warmup logs a clear message and falls back to mock mode

**verification/face_utils.py**
- The core FaceNet integration module
- Loads the keras-facenet model (~90 MB, cached in `~/.keras` after first download) as a module-level singleton — loaded once per process, reused for every request
- `get_facenet_model()` — lazy-init with global cache; called by `apps.py` at startup and by every embedding request
- `get_embedding(face_img)` — CLAHE → BGR→RGB → FaceNet → L2-normalize; identical pipeline for registration and verification
- `compare_with_all_embeddings(live, beneficiary)` — best cosine similarity across primary + all additional templates
- Face similarity threshold is read from `SystemConfig` (db-backed) respecting `DEMO_MODE`

**verification/liveness.py**
- Anti-spoofing module
- Analyzes image texture using frequency domain analysis to distinguish a live face from a printed photo or screen
- Returns a liveness confidence score and a pass/fail decision
- Threshold is read from `.env` (`ANTI_SPOOF_THRESHOLD`)
- If `LIVENESS_REQUIRED=True` in `.env`, a failed liveness check blocks verification entirely

**verification/views.py**
- Handles POST requests from the browser (face image submitted via webcam capture)
- Orchestrates the full verification pipeline:
  1. Decode the incoming image
  2. Run liveness check (liveness.py)
  3. Run FaceNet embedding (face_utils.py)
  4. Look up the beneficiary's stored embedding from the database
  5. Decrypt the stored embedding (using EMBEDDING_ENCRYPTION_KEY)
  6. Compute similarity
  7. Apply threshold to determine VERIFIED or NOT VERIFIED
  8. Write the verification record to the database
  9. Return the result to the browser

**verification/models.py**
Key models:
- `StipendEvent` — distribution event with `date` (reference/announcement), `payout_start_date`, `payout_end_date`; `get_active_event_for_date()` returns the event whose payout window contains today; supports multi-day payout periods
- `VerificationAttempt` — records every face scan attempt (score, liveness, decision, claimant type)
- `ClaimRecord` — completed or pending payout claim; `STATUS_CLAIMED` = finalized, `STATUS_PENDING_APPROVAL` = awaiting Head Barangay approval (used when no active event exists), `STATUS_REJECTED`
- `ManualVerificationRequest`, `FaceUpdateRequest`, `SpecialClaimRequest` — admin approval queue items
- `FaceEmbedding`, `AdditionalFaceEmbedding`, `RepresentativeFaceEmbedding` — encrypted biometric data

**verification/views.py**
Handles the full verification workflow plus:
- `report_claims` — filterable claims report; `?export=excel` → Excel download, `?export=print` → print-ready HTML
- `report_event_summary` — per-event payout totals (claimed / pending / rejected / attempts / fallback)
- `pending_claim_review` — Head Barangay/IT Admin approves or rejects a claim that was submitted without an active event
- Pending-claim logic in `verify_submit`: if face passes but no active event, Head Barangay creates `STATUS_CLAIMED` directly; Staff/IT Admin creates `STATUS_PENDING_APPROVAL` logged as `ACTION_CLAIM_PENDING`

**verification/urls.py**
- Core verification flow, admin queue, stipend events, face updates, registration review, rep face registration
- `reports/claims/` — Claims Report (HTML + Excel + print)
- `reports/event-summary/` — Event Summary Report
- `manual-review/pending-claim/<claim_id>/` — pending claim approval page

**verification/admin.py**
- Registers `VerificationLog` in the Django admin panel
- Allows Admin to review the full audit trail of all verification attempts

### How it connects to the system

- Depends on `beneficiaries/` to look up the registered face embedding for a beneficiary
- Depends on `accounts/` for authentication (staff must be logged in to run a verification)
- Depends on `fans/settings.py` for configuration values (thresholds, LIVENESS_REQUIRED, EMBEDDING_ENCRYPTION_KEY)
- The browser JavaScript sends the webcam frame as a base64-encoded image in a POST request; the view decodes it and passes it through the verification pipeline
- FaceNet model is loaded once at Django startup (not on every request) and kept in memory — this is why the first request after a cold start may be slightly slower

### Runtime flow

| Phase | How verification/ is involved |
|---|---|
| Startup | face_utils.py loads the FaceNet model into memory (or logs a failure and falls back to mock) |
| Runtime | Every verification request flows through views.py → liveness.py → face_utils.py → beneficiary lookup → similarity comparison |
| Diagnostics | `/verification/config/` shows the model status (real model or mock) and current threshold settings |

### Defense notes

**Why does FaceNet need to download ~90 MB on first use?**
The keras-facenet package contains the model architecture but not the trained weights. The weights are downloaded from Hugging Face on the first call to load the model and then cached in `~/.keras`. After the first startup, the model is fully local — no internet access is needed. This is a standard practice for pre-trained deep learning models distributed via Python packages.

**What is the mock model?**
If the FaceNet model fails to load (wrong Python version, TensorFlow error, path issue), the system falls back to a mock model that returns random similarity scores. The system stays up (staff can still log in) but face verification is unreliable. The model status is visible at `/verification/config/`.

**Why is liveness detection important?**
Without liveness detection, an attacker could hold a photo of a beneficiary's face in front of the camera and pass verification. The liveness check analyzes image texture patterns — a photo printed on paper or displayed on a screen has different frequency characteristics than a real face. This is a software-only check (no specialized hardware required).

**How is the similarity threshold chosen?**
The threshold is the minimum cosine similarity score required to declare a match. A score of 1.0 means identical embeddings; a score of 0.0 means completely unrelated. The default threshold in `DEMO_MODE` (0.60) is intentionally lower to account for variations in lighting and camera quality. A stricter threshold reduces false positives but increases false rejections. The threshold can be tuned in `.env` without changing any code.

---

## How all apps connect

```
accounts/           Provides authentication and authorization
    |
    |-- decorators imported by beneficiaries/ and verification/
    |-- CustomUser referenced throughout the system
    |
beneficiaries/      Provides beneficiary records
    |
    |-- Beneficiary model referenced by verification/
    |-- face embedding stored here, encrypted
    |
verification/       Core verification engine
    |
    |-- Reads beneficiary embeddings from beneficiaries/
    |-- Writes VerificationLog records
    |-- face_utils.py: FaceNet (keras-facenet + MTCNN)
    |-- liveness.py: anti-spoofing
    |
fans/               Ties everything together
    |
    |-- settings.py: configures all apps, reads .env
    |-- urls.py: routes requests to the correct app
    |-- wsgi.py: entry point for Waitress
```

---

## Related folders/files

- `templates/` — all HTML templates for all apps live here
- `static/` — CSS, JavaScript, and images referenced by templates
- `staticfiles/` — production copy of static files (served by WhiteNoise)
- `media/` — uploaded face images stored during registration
- `.env` — provides all configuration values read by `fans/settings.py`
- `db.sqlite3` — the database where all model data is stored
- `.venv/` — contains Django, Waitress, TensorFlow, keras-facenet, and all dependencies

---

## Summary

The four Django folders form the application core of FANS-C. `fans/` is the project glue. `accounts/` controls who can access what. `beneficiaries/` manages the senior citizen registry. `verification/` runs the FaceNet biometric verification. Each app is self-contained but connected through Django's standard mechanisms: shared models, imported decorators, and URL includes.
