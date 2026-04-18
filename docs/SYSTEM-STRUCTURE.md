# FANS-C System Structure

**FANS-C: A Secure FaceNet-Based Facial Verification System for Senior Citizen Stipend Distribution**

This document is the master technical reference for the FANS-C system. It explains how the entire system is organized, how all parts connect, and how the system behaves during setup, startup, daily use, and failure recovery. It is intended for IT/Admin staff, developers, and thesis/capstone defense preparation.

---

## Table of Contents

1. [Repository Overview](#1-repository-overview)
2. [Full System Flow](#2-full-system-flow)
3. [Folder Map](#3-folder-map)
4. [How All Parts Connect](#4-how-all-parts-connect)
5. [Component Roles](#5-component-roles)
6. [Defense Guide — Q&A](#6-defense-guide--qa)
7. [Critical Folders](#7-critical-folders)

---

## 1. Repository Overview

FANS-C is a **LAN-based biometric verification system** deployed on a single Windows server PC inside a barangay office. Barangay staff access it using a web browser — no software needs to be installed on staff devices.

The system uses **FaceNet** (a deep learning facial recognition model) to verify the identity of senior citizens before their stipend is released. A live camera feed is captured in the browser and processed server-side by the FaceNet model.

**Core technology stack:**

| Layer | Technology |
|---|---|
| Web framework | Django 4.2 (Python) |
| Application server | Waitress (WSGI) |
| HTTPS proxy | Caddy |
| Face recognition | FaceNet via keras-facenet |
| Anti-spoofing | Texture analysis (liveness.py) |
| Database | SQLite (default) or PostgreSQL |
| Auto-start | Windows Task Scheduler |
| Self-healing | watchdog.ps1 (background monitor) |
| Certificate authority | mkcert (local CA, LAN-trusted) |

**What makes this system unusual for a capstone project:**

- It runs entirely without internet after initial setup
- It uses production-grade components (Waitress + Caddy) rather than Django's development server
- It includes a self-healing watchdog with rate limiting, cooldown, and recovery logging
- All face embeddings are stored encrypted using a Fernet key
- HTTPS is enforced (required for browser camera access)

---

## 2. Full System Flow

### 2.1 Setup Flow (IT/Admin, one time)

```
IT/Admin runs:
scripts\setup\setup-complete.ps1 (as Administrator)
        |
        |-- Step 1: setup-secure-server.ps1
        |       |-- Creates Python virtual environment (.venv)
        |       |-- Installs all dependencies (pip install -r requirements.txt)
        |       |-- Runs mkcert to generate TLS certificate (fans-cert.pem, fans-cert-key.pem)
        |       |-- Generates SECRET_KEY and EMBEDDING_ENCRYPTION_KEY into .env
        |       |-- Runs Django migrations (creates database tables)
        |       |-- Runs collectstatic (copies static files to staticfiles/)
        |       |-- Prompts to create admin account (createsuperuser)
        |
        |-- Step 2: Verify certificate files exist
        |
        |-- Step 3: Verify caddy.exe is present
        |
        |-- Step 4: Verify .env has required keys
        |
        |-- Step 5: setup-autostart.ps1
        |       |-- Registers "FANS-C Verification System" Task Scheduler task
        |       |-- This task runs start-fans-hidden.ps1 at every system boot
        |
        |-- Step 6: Optionally create desktop shortcut
        |
        |-- Step 7: Live validation
        |       |-- Starts Waitress (port 8000)
        |       |-- Waits 8 seconds
        |       |-- Starts Caddy (port 443)
        |       |-- Waits 8 seconds
        |       |-- Tests TCP connections to both ports
        |       |-- Reports PASS or FAIL
        |
        |-- Step 8: Register watchdog
                |-- Registers "FANS-C Watchdog" Task Scheduler task
                |-- This task runs watchdog.ps1 150 seconds after every boot
```

After setup completes, IT/Admin:
- Edits `.env` to set `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DEBUG=False`
- Copies `CLIENT-SETUP\` folder to a USB drive
- Runs `trust-local-cert.bat` on every staff device (as Administrator)

---

### 2.2 Startup Flow (every boot, automatic)

```
Server PC turns on
        |
        |-- Windows Task Scheduler fires: "FANS-C Verification System"
        |       |-- Runs: scripts\start\start-fans-hidden.ps1
        |       |-- Activates Python virtual environment
        |       |-- Starts Waitress: waitress-serve --listen=127.0.0.1:8000 fans.wsgi:application
        |       |-- Waits for port 8000 to respond
        |       |-- Starts Caddy: caddy run --config Caddyfile
        |       |-- Waits for port 443 to respond
        |       |-- Writes result to logs\fans-startup.log
        |
        |-- 150 seconds later, Task Scheduler fires: "FANS-C Watchdog"
                |-- Runs: scripts\admin\watchdog.ps1
                |-- Begins continuous monitoring loop (every 45 seconds)
```

Head Barangay workflow after boot:
1. Turn on PC
2. Wait 30 seconds
3. Open browser → `https://fans-barangay.local`
4. Log in and begin processing

---

### 2.3 Browser Access Flow

```
Staff device (browser)
        |
        | HTTPS request to fans-barangay.local:443
        | (TLS certificate trusted because trust-local-cert.bat was run)
        |
        v
   [ Caddy — port 443 ]
        |
        | Plain HTTP forwarded to 127.0.0.1:8000
        | (loopback only — not accessible from network)
        |
        v
   [ Waitress — port 8000 ]
        |
        | Calls Django WSGI application
        |
        v
   [ Django — FANS-C application ]
        |
        |-- Reads .env for configuration
        |-- Queries SQLite (or PostgreSQL) for records
        |-- Renders HTML templates (templates/)
        |-- Serves static files via WhiteNoise (staticfiles/)
        |-- Processes face images via verification/ app
```

---

### 2.4 Face Verification Flow

```
Staff submits beneficiary for verification
        |
        v
Browser opens camera (HTTPS required for camera access)
        |
        | Captures face image frame
        | Sends image to server via POST request
        |
        v
verification/views.py receives the request
        |
        v
verification/liveness.py — Anti-spoofing check
        |-- Analyzes image texture for liveness signals
        |-- If liveness fails and LIVENESS_REQUIRED=True: blocks verification
        |
        v
verification/face_utils.py — FaceNet processing
        |-- Loads keras-facenet model (cached after first load)
        |-- MTCNN detects and crops face from image
        |-- FaceNet generates 128-dimensional embedding vector
        |-- Decrypts stored embedding from database (using EMBEDDING_ENCRYPTION_KEY)
        |-- Computes cosine similarity between new embedding and stored embedding
        |-- Compares similarity score to threshold (DEMO_THRESHOLD in demo mode)
        |
        v
Result: VERIFIED or NOT VERIFIED
        |
        v
Verification record written to database
Staff sees result on screen
```

---

### 2.5 Watchdog Recovery Flow

```
watchdog.ps1 runs every 45 seconds
        |
        |-- Check Waitress:
        |       Is waitress-serve.exe process running?
        |       Is port 8000 accepting TCP connections?
        |       Does Django respond to HTTP probe on port 8000?
        |
        |-- If Waitress is healthy: continue
        |
        |-- If Waitress is unhealthy:
        |       Check restart history (prune entries older than 10 minutes)
        |       If restart count >= 3: log [ALERT], stop attempting, wait for IT/Admin
        |       If cooldown active (< 60s since last restart): log [WAIT], skip
        |       If port recovered on its own: log [SKIP], no action needed
        |       Otherwise:
        |               Kill any stale Waitress process
        |               Start new Waitress instance
        |               Wait for initialization
        |               Re-check port
        |               If recovered: log [OK]
        |               If still down: log [FAIL]
        |
        |-- Same logic applied to Caddy (port 443)
        |
        |-- Log result to logs\fans-watchdog.log
        |-- If all healthy: log [HEALTHY] (once every ~7.5 minutes to reduce noise)
```

---

### 2.6 Diagnostic Flow

```
IT/Admin suspects a problem
        |
        v
Run: scripts\admin\check-system-health.ps1
        |
        |-- Checks (read-only, no changes made):
        |       1. Waitress process and port 8000
        |       2. Caddy process and port 443
        |       3. TLS certificate files present and current
        |       4. .env configuration (required keys set, DEBUG mode)
        |       5. Task Scheduler auto-start task (state, last run)
        |       6. Task Scheduler watchdog task (state, last run)
        |       7. Recent entries from logs\fans-startup.log
        |       8. Recent entries from logs\fans-watchdog.log
        |
        v
Prints [OK] / [FAIL] / [WARN] for each check
Prints specific fix instructions for any failures
```

---

## 3. Folder Map

```
project root/
|
|-- fans/                       Django project configuration (settings, URLs, WSGI)
|-- accounts/                   User authentication and role management
|-- beneficiaries/              Beneficiary records and management
|-- verification/               FaceNet facial verification engine
|
|-- templates/                  HTML templates (all pages)
|-- static/                     Source static files (CSS, JS, images)
|-- staticfiles/                Collected static files served in production
|-- media/                      User-uploaded files (face images)
|-- assets/                     Additional frontend assets
|
|-- scripts/
|   |-- setup/                  One-time setup scripts (IT/Admin)
|   |-- start/                  Service launcher scripts
|   |-- admin/                  Diagnostic and maintenance scripts
|
|-- CLIENT-SETUP/               Scripts to run on each staff device (once)
|-- tools/                      External binaries (caddy.exe, mkcert.exe)
|-- logs/                       Runtime log files
|-- docs/                       Technical documentation (this folder)
|-- dev/                        Developer utilities
|-- legacy/                     Deprecated or archived files
|
|-- .venv/                      Python virtual environment (auto-created by setup)
|-- db.sqlite3                  SQLite database (default storage)
|-- .env                        Environment configuration (secrets, settings)
|-- .env.example                Template for .env
|-- Caddyfile                   Caddy HTTPS reverse proxy configuration
|-- manage.py                   Django management entry point
|-- requirements.txt            Python package dependencies
|-- fans-cert.pem               TLS certificate (generated by mkcert during setup)
|-- fans-cert-key.pem           TLS private key (generated by mkcert during setup)
```

---

## 4. How All Parts Connect

### Django ↔ Waitress

Waitress is the production WSGI server for Django. It imports the WSGI callable from `fans/wsgi.py` and listens on `127.0.0.1:8000`. Django never handles TCP directly — Waitress does that and passes requests to Django as WSGI calls.

### Waitress ↔ Caddy

Caddy receives all incoming HTTPS traffic on port 443, terminates TLS (decrypts the connection), and forwards the request as plain HTTP to Waitress on `127.0.0.1:8000`. Caddy adds `X-Forwarded-Proto: https` and `X-Real-IP` headers so Django knows the original protocol and client IP. Django uses these headers because `SECURE_PROXY_SSL_HEADER` and `USE_X_FORWARDED_HOST` are set in `.env`.

### Django ↔ Database

Django uses its ORM (Object-Relational Mapper) to read and write records. By default the database is `db.sqlite3` (SQLite) in the project root. The `USE_SQLITE` setting in `.env` controls whether SQLite or PostgreSQL is used. All beneficiary records, user accounts, and verification logs are stored in the database.

### Django ↔ FaceNet

The `verification` Django app contains `face_utils.py`, which loads the keras-facenet model and runs inference. When a verification request arrives, Django calls functions in `face_utils.py` to:
1. Detect and crop the face (MTCNN)
2. Generate a face embedding (FaceNet, 128-dimensional vector)
3. Decrypt the stored embedding from the database
4. Compute cosine similarity and return a match decision

### Django ↔ Media Folder

When a beneficiary's face image is uploaded during registration, Django stores it in the `media/` folder. Face embeddings (the numerical representation produced by FaceNet) are stored encrypted in the database using the `EMBEDDING_ENCRYPTION_KEY` from `.env`.

### Django ↔ Templates and Static Files

Django renders HTML responses using templates from the `templates/` folder. Static files (CSS, JavaScript, images) are collected into `staticfiles/` by `collectstatic` and served in production by WhiteNoise (a middleware that serves static files directly from Django/Waitress without a separate file server).

### Watchdog ↔ Task Scheduler ↔ Services

Windows Task Scheduler manages two background tasks:
- **FANS-C Verification System** — starts Waitress and Caddy at boot
- **FANS-C Watchdog** — starts the watchdog 150 seconds after boot

The watchdog does not use Task Scheduler to restart services. It directly calls PowerShell commands to kill and relaunch Waitress and Caddy processes when it detects a failure.

### mkcert ↔ Caddy ↔ Client Browsers

mkcert generates two files: `fans-cert.pem` (the TLS certificate) and `fans-cert-key.pem` (the private key). These are referenced in the `Caddyfile` and loaded by Caddy to enable HTTPS. mkcert also creates a local Certificate Authority (CA). The `trust-local-cert.bat` script installs this CA on each staff device, which causes the browser to trust the FANS-C certificate without a warning.

---

## 5. Component Roles

| Component | Role | What breaks without it |
|---|---|---|
| Django | Application logic, web pages, database access, verification | Nothing works |
| Waitress | Serves Django over HTTP on port 8000 | Django is unreachable |
| Caddy | HTTPS termination on port 443 | Browser cannot connect (no HTTPS = no camera access) |
| FaceNet (keras-facenet) | Generates face embeddings for matching | Verification returns random or mock results |
| MTCNN | Detects and crops faces from images | FaceNet cannot process raw images |
| SQLite / PostgreSQL | Stores all records | No data persists between requests |
| Task Scheduler | Auto-starts services at boot | System requires manual start after every reboot |
| watchdog.ps1 | Detects and recovers from service crashes during the day | Failures require IT/Admin intervention to fix |
| mkcert CA + trust-local-cert.bat | Browser trusts the local HTTPS certificate | Certificate warnings block camera access |
| .env | All configuration and encryption keys | System fails to start or loads defaults that break security |
| EMBEDDING_ENCRYPTION_KEY | Encrypts/decrypts stored face embeddings | All stored face data becomes unreadable |

---

## 6. Defense Guide — Q&A

### Why Waitress + Caddy instead of Django's built-in server?

Django's built-in development server (`manage.py runserver`) is explicitly not suitable for production. It is single-threaded, does not handle concurrent requests well, and has no security hardening. Waitress is a production-grade WSGI server that handles concurrent requests safely. Caddy is added on top to handle HTTPS, which is required for the browser camera API (`getUserMedia`) to work — browsers refuse camera access on plain HTTP.

### Why HTTPS? Why not just HTTP?

Modern browsers enforce the Web Security Model: the `navigator.mediaDevices.getUserMedia()` API (used to access the camera) is only available in secure contexts — meaning the page must be served over HTTPS or from localhost. Since staff devices access the system over a LAN (not localhost), HTTPS is mandatory. Without HTTPS, the camera button will silently fail or not appear at all.

### Why use mkcert instead of a real SSL certificate?

Real SSL certificates (from Let's Encrypt or a commercial CA) require a publicly accessible domain name and internet access to verify domain ownership. FANS-C runs on a private LAN with no public domain — `fans-barangay.local` is not resolvable from the internet. mkcert creates a locally-trusted CA that signs the certificate for the local domain. Once that CA is installed on staff devices, the certificate is trusted exactly like a real one — no browser warnings, full camera access.

### Why is the watchdog a separate script and not part of the main startup?

The watchdog needs to continue running after the startup script has finished. If it were part of the startup script, it would block the startup script from completing. As a separate Task Scheduler task, it starts 150 seconds after boot (giving the main startup time to complete) and then runs indefinitely in the background, independent of any other process.

### Why the 150-second delay before the watchdog starts?

The main startup task (FANS-C Verification System) needs time to:
1. Activate the Python virtual environment
2. Start Waitress (Django takes 4-8 seconds to initialize; FaceNet model download takes up to 90 seconds on first run)
3. Start Caddy

If the watchdog started immediately at boot, it would see both services as down and immediately attempt a restart, which would conflict with the normal startup already in progress and could result in duplicate processes.

### How does the system recover from a crash?

1. Watchdog detects the failed service within 45 seconds (the monitoring interval)
2. Checks if a restart should be attempted (cooldown, max attempt limits)
3. Kills any stale process to ensure a clean state
4. Starts a fresh process
5. Waits for the port to respond, then confirms recovery
6. If recovery fails after 3 attempts in 10 minutes, logs an [ALERT] and stops retrying

The Head Barangay does not see this recovery — the system comes back on its own within about 45-60 seconds of a crash. If the system cannot recover automatically, IT/Admin is alerted via the watchdog log.

### What happens if the EMBEDDING_ENCRYPTION_KEY is lost?

Face embeddings (the numerical fingerprints of enrolled faces) are stored in the database encrypted with this key. If the key is lost or changed, the encrypted embeddings cannot be decrypted — all enrolled beneficiaries would need to be re-registered. This key must be backed up securely outside the server. It is stored in the `.env` file in the project root.

### Why store face embeddings instead of raw photos?

Face embeddings (128-dimensional floating-point vectors) are a compact numerical representation of a face. They are:
- Smaller than photos (much less storage)
- Encrypted at rest (secure)
- Not directly reversible to the original image (unlike photos, embeddings cannot trivially reconstruct someone's appearance)
- Faster to compare (cosine similarity of two vectors vs. running a full model on two images)

### What is the difference between DEMO_MODE and the mock model?

`DEMO_MODE=True` lowers the face similarity threshold and makes liveness non-blocking. Real face matching still runs if the FaceNet model loaded correctly. The mock model is what activates when `keras-facenet` fails to load — in that case, all similarity scores are random numbers. You can check `/verification/config/` in the web interface to see which state the model is in.

### Why must client devices run trust-local-cert.bat?

Each client device has its own browser trust store — a list of Certificate Authorities it trusts. The FANS-C server's HTTPS certificate was signed by the mkcert CA created on the server. That CA is not in any browser's default trust store. `trust-local-cert.bat` installs the server's CA into the Windows trust store on the client device, which causes Chrome, Edge, and Firefox to automatically trust any certificate signed by that CA — including the FANS-C certificate.

### What is the role of the Caddyfile?

The Caddyfile is Caddy's configuration file. It tells Caddy:
- Which domain to serve (`fans-barangay.local`)
- Which port to listen on (443, HTTPS)
- Which TLS certificate files to use (`fans-cert.pem`, `fans-cert-key.pem`)
- Where to forward requests (127.0.0.1:8000, Waitress)
- Which headers to add (X-Forwarded-Proto, X-Real-IP)

Without the Caddyfile, Caddy does not know any of this and will not start correctly.

### Why does the project need to be at a short path like D:\FANS?

Windows limits file paths to 260 characters by default. TensorFlow's Python wheel (the package that keras-facenet depends on) contains deeply nested file paths that exceed this limit when extracted in a deeply nested project folder. The symptom is `pip install` failing with a "No such file or directory" error even though the directory exists. Placing the project at `D:\FANS` keeps all paths short enough to avoid this.

### What is the role of WhiteNoise?

WhiteNoise is a Python middleware for Django that enables serving static files (CSS, JavaScript, images) directly from the Django/Waitress process without a separate web server. In a typical production Django setup, a separate server (like Nginx) serves static files. Because FANS-C uses Caddy only as an HTTPS proxy (not a file server), WhiteNoise fills that role within the Waitress process.

---

## 7. Critical Folders

These folders are required for the system to function. Missing or corrupted content in any of them will prevent the system from working.

### `.venv/` — Python Virtual Environment

**What it contains:** The Python interpreter, all installed packages (Django, Waitress, TensorFlow, keras-facenet, etc.)

**What breaks if missing:** The system cannot start at all. Waitress is a Python command and requires the virtual environment.

**How to recreate:** Run `scripts\setup\setup-complete.ps1` or `scripts\setup\setup-secure-server.ps1` as Administrator. Do not move the project folder after creating the venv — the venv stores absolute paths and breaks if moved.

---

### `.env` — Configuration and Secrets

**What it contains:** `SECRET_KEY`, `EMBEDDING_ENCRYPTION_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, database settings, face recognition thresholds.

**What breaks if missing:**
- Django refuses to start (SECRET_KEY required)
- Stored face embeddings become permanently unreadable (EMBEDDING_ENCRYPTION_KEY required)
- Staff browsers are blocked by Django's CSRF/ALLOWED_HOSTS checks

**How to recreate:** Run `setup-complete.ps1` to generate a new `.env`. WARNING: This generates a new `EMBEDDING_ENCRYPTION_KEY`, which makes all previously stored face embeddings unreadable. Back up the original `.env` file and restore the original key.

---

### `fans-cert.pem` and `fans-cert-key.pem` — TLS Certificate

**What they contain:** The HTTPS certificate and private key for `fans-barangay.local`, generated by mkcert.

**What breaks if missing:** Caddy cannot start (it requires the certificate files). The system cannot serve HTTPS. Browser camera access stops working.

**How to recreate:** Run `setup-secure-server.ps1`. The new certificate has a different fingerprint — you may need to re-run `trust-local-cert.bat` on client devices if the browser starts warning again.

---

### `db.sqlite3` — Database

**What it contains:** All beneficiary records, user accounts, verification logs, stipend event records.

**What breaks if missing:** The application starts but has no data. All registrations and verification history is lost.

**How to recover:** Restore from backup. If no backup exists, run `python manage.py migrate` to create an empty database, but all data is permanently lost.

---

### `staticfiles/` — Production Static Files

**What it contains:** Collected copies of all CSS, JavaScript, and images, ready for WhiteNoise to serve.

**What breaks if missing:** Web pages load without styles and scripts. The application may be partially usable but the interface is broken.

**How to recreate:** Run `python manage.py collectstatic --noinput` (with the virtual environment activated).

---

### `tools/caddy.exe` — HTTPS Proxy

**What it contains:** The Caddy binary, a single self-contained executable.

**What breaks if missing:** HTTPS cannot start. Staff browsers cannot connect. Camera access is blocked.

**How to fix:** Download `caddy.exe` from the official Caddy website and place it at `tools\caddy.exe`.

---

*For folder-level documentation, see the individual docs in this folder:*
- [folder-scripts.md](folder-scripts.md) — scripts/ folder
- [folder-django-app.md](folder-django-app.md) — Django application folders
- [folder-static-templates.md](folder-static-templates.md) — templates, static, staticfiles, media
- [folder-logs.md](folder-logs.md) — logs/ folder
- [folder-client-setup.md](folder-client-setup.md) — CLIENT-SETUP/ folder
