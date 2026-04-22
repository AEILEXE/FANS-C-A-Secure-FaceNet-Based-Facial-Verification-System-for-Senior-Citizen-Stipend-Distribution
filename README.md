# FANS-C: A Secure FaceNet-Based Facial Verification System for Senior Citizen Stipend Distribution

> **A functional biometric identity verification system built for real-world barangay deployment.**
> Designed to streamline senior citizen stipend distribution through secure facial recognition — no paper lists, no manual identity checks.

Developed as a capstone project for deployment in controlled government environments (Quezon City).

---

## Quick Deployment Guide

> Use this if you are setting up FANS-C for the first time. Follow each step in order.

---

### Part 1 — Server PC Setup (do this once)

> This is the PC that will run the system. All other staff connect to it over the network.

**Before you start, make sure you have:**
- The FANS-C project folder (e.g., `D:\FANS` or `C:\FANSC`)
- Python 3.11 installed — check "Add Python to PATH" during install
- `caddy.exe` placed in the `tools\` folder inside the project
- `mkcert.exe` placed in `tools\mkcert\` inside the project
- You are logged in as **Administrator**

**Steps:**

1. Open the project folder
2. Right-click `scripts\setup\setup-complete.ps1` → select **Run with PowerShell**
3. Wait for the script to finish — all steps should show **PASS**
4. Write down the **Server IP** shown at the end (example: `192.168.1.50`) — you will need it

That's it. The server will now **start automatically every time the PC is turned on.**

> **Important:** During real deployment, the system needed more startup time at boot because Django + FaceNet warmup can be slow. If auto-start fails after reboot, see the **Auto-Start After Reboot** section in Troubleshooting below.

---

### Part 2 — Staff PC Setup (do this once per device)

> Do this on every computer or tablet that staff will use to access the system.

**You need:**
- The `CLIENT-SETUP` folder from the server PC (copy it to a USB drive)
- The server's IP address (from Part 1, Step 4)

**Steps:**

1. Copy the `CLIENT-SETUP` folder to the staff PC (via USB or network share)
2. Double-click `CLIENT-SETUP\trust-local-cert.bat` and approve the prompt
3. Open the file `C:\Windows\System32\drivers\etc\hosts` in Notepad **(as Administrator)**
4. Add this line at the bottom — replace the IP with your server's actual IP:
   ```
   192.168.1.50   fans-barangay.local
   ```
5. Save the file

> **Tip:** If your router supports "Local DNS" or "Hostname Mapping", you can configure it there once instead of editing each device's hosts file.

> **Important:** Do **not** point `fans-barangay.local` to the router/gateway IP such as `192.168.1.1`. It must point to the **actual server IP**, or the browser may show the wrong page, a certificate warning, or fail to connect correctly.

---

### Part 3 — Daily Use (no setup needed)

Once setup is complete, staff do not need to run any scripts or commands.

**Every day:**

1. Turn on the **server PC** and wait about **30 seconds**
2. On any staff device, open a browser (Chrome, Edge, or Firefox)
3. Go to: **`https://fans-barangay.local`**
4. Log in and start processing beneficiaries

Nothing else is required. If the system does not load after 30 seconds, wait another 30 seconds and try again.

---

## Table of Contents

1. [Key Features](#key-features)
2. [System Overview](#system-overview)
3. [Quick Setup — IT/Admin (One Time Only)](#-quick-setup--itadmin--one-time-only)
4. [Daily Use — Head Barangay](#-daily-use--head-barangay)
5. [Troubleshooting — IT/Admin](#-troubleshooting--itadmin)
6. [Script Reference](#-script-reference)
7. [Important Notes](#-important-notes)
8. [System Architecture](#-system-architecture)
9. [Role Summary](#-role-summary)
10. [Reports & Export](#-reports--export)
11. [Password Management](#-password-management)

---

## Key Features

- **Facial Verification** — Uses FaceNet biometric matching to confirm a senior citizen's identity before releasing their stipend
- **Centralized LAN Server** — One server PC serves the entire barangay office; staff access via any browser on the same network
- **Secure HTTPS Access** — All connections are encrypted; camera access (required for face scanning) only works over HTTPS
- **Auto-Start on Boot** — The system starts automatically when the server PC turns on; no manual steps required
- **Self-Healing Watchdog** — A background monitor checks the system every 45 seconds and automatically restarts services if they fail
- **Health Check Tool** — IT/Admin can run a single script at any time to see the live status of every component
- **Offline-Safe Design** — The system runs entirely within the barangay's local network; no internet connection is required for normal operation
- **Role-Based Access** — Three active roles: Head Barangay (operational admin), IT/Admin (technical admin), Staff (operational)
- **Multi-Day Payout Windows** — Distribution events can span multiple days with a start and end date
- **Claims Reporting & Export** — Admins can export claims and event summaries as Excel (.xlsx) or print-ready PDF
- **Approval Workflow** — Claims submitted outside an active payout event go to the Head Barangay for approval
- **Password Management** — Users can change their own password; admins can reset other users' passwords (logged)
- **FaceNet Startup Warmup** — Model is loaded in the background at boot so the first verification is fast

---

## System Overview

The FANS-C system runs on **one dedicated server PC** inside the barangay office.

- All barangay staff connect to it using a regular web browser on their own devices — no software installation needed on their end.
- The system starts automatically every time the server PC is turned on. Staff do not need to run any scripts or commands.
- If a service ever fails or crashes, the built-in watchdog detects this within 45 seconds and automatically restarts it.
- All face data and stipend records are stored securely on the server, not on individual devices.
- The system does **not** require an internet connection to operate. Everything stays inside the barangay's local network.

**What staff do every day:**
1. Open a browser
2. Go to `https://fans-barangay.local`
3. Log in and start processing beneficiaries

That is the entire daily workflow. No scripts. No commands. No technical knowledge required.

---

## 🚀 Quick Setup — IT/Admin (One Time Only)

> Run this once when setting up the server for the first time. You do not need to repeat it unless reinstalling.

**Requirements before you begin:**
- You are logged in to the server PC as an Administrator
- All devices are connected to the same local network (LAN/Wi-Fi)
- `caddy.exe` is placed in the `tools\` folder inside the project
- `mkcert.exe` is placed in `tools\mkcert\`

---

### Step 1 — Run the master setup script (on the server PC)

Right-click the file below and select **Run with PowerShell**:

```
scripts\setup\setup-complete.ps1
```

Or open PowerShell as Administrator and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup\setup-complete.ps1
```

This single script handles everything in order:
- Creates the Python virtual environment and installs dependencies
- Generates the local HTTPS certificate (`fans-cert.pem`)
- Configures Django and generates security keys in `.env`
- Registers the auto-start task in Windows Task Scheduler
- Registers the watchdog (self-healing monitor)
- Runs a live validation to confirm both services are working

Wait for it to finish and confirm all steps show **PASS**.

> **Important real-world note:** During actual deployment, if setup completed but `waitress-serve.exe` was still missing, the server could not start correctly. In that case, install `waitress` manually in the project virtual environment:
>
> ```powershell
> cd C:\FANSC
> .venv\Scripts\activate
> pip install waitress
> ```
>
> If needed, also add `waitress` to `requirements.txt` so fresh installs include it automatically.

---

### Step 2 — Trust the certificate on each client device

On every device that staff will use to access the system, run the certificate trust script once:

```
CLIENT-SETUP\trust-local-cert.bat
```

> This allows the browser on that device to accept the local HTTPS certificate without a security warning.
> Without this step, the browser will block access or disable the camera.

> **Important real-world note:** If the script complains that `rootCA.pem` is missing, copy the file from the server's mkcert CA folder into `CLIENT-SETUP`. On the server, you can find the mkcert CA folder with:
>
> ```powershell
> C:\FANSC\tools\mkcert\mkcert.exe -CAROOT
> ```
>
> Copy **only** `rootCA.pem` into `CLIENT-SETUP`. **Do not distribute** `rootCA-key.pem`.

---

### Step 3 — Open the system in a browser

On any device on the same network:

```
https://fans-barangay.local
```

Log in with the admin credentials created during setup.

---

**Setup notes:**
- Must be run as Administrator — the script will not work otherwise
- All devices must be on the same LAN or Wi-Fi network as the server
- Do not close the PowerShell window while setup is running
- If setup fails partway, fix the reported issue and re-run `setup-complete.ps1` — it is safe to run again

---

## 👤 Daily Use — Head Barangay

Once setup is complete, the daily workflow is:

1. **Turn on the server PC**
2. **Wait about 30 seconds** for the system to start automatically
3. **Open any browser** (Chrome, Edge, Firefox)
4. **Go to:** `https://fans-barangay.local`
5. **Log in** and begin processing beneficiaries

**Nothing else is required.** No scripts. No terminal. No technical steps.

> If the browser cannot connect after 30 seconds, wait another 30 seconds and try again. If it still does not work, contact IT/Admin.

---

## 🛠 Troubleshooting — IT/Admin

### Run the health check first

When something is not working, the first step is always:

```
scripts\admin\check-system-health.ps1
```

Right-click and select **Run with PowerShell**, or run it from any PowerShell window.

This script checks every component and tells you exactly what is and is not working:
- Is Waitress (the app server) running?
- Is port 8000 responding?
- Is Caddy (HTTPS) running?
- Is port 443 responding?
- Are the certificate files present?
- Are `.env` keys configured?
- Is the auto-start task registered?
- Is the watchdog active?

It prints **[OK]** or **[FAIL]** for each item and gives specific fix instructions.

---

### Check the logs

| Log file | What it contains |
|---|---|
| `logs\fans-startup.log` | What happened during the last automatic startup |
| `logs\fans-watchdog.log` | Every health check, restart attempt, and alert from the watchdog |

If the watchdog log shows repeated `[ALERT]` entries for the same service, automatic recovery has given up and IT/Admin inspection is required.

---

### Manual startup (if auto-start fails)

To start the system manually without rebooting:

```
scripts\start\start-fans-quiet.bat
```

Double-click this file. It starts both services in the background and shows port verification results.

---

### Debug mode (to see full error output)

If a service is failing to start and you need to see the exact error message:

```
scripts\start\start-fans.bat
```

This opens both server windows visibly so you can read all output. Use this when diagnosing a startup crash.

---

### Stop the system

```
scripts\admin\stop-fans.ps1
```

Run with PowerShell to cleanly stop Waitress and Caddy.

---

### Common issues and fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| Browser cannot reach `https://fans-barangay.local` | Services not running | Run health check; check logs |
| Camera not working in browser | Certificate not trusted on this device | Run `CLIENT-SETUP\trust-local-cert.bat` on that device |
| System did not start after reboot | Auto-start timing too short or backend crashed during startup | Run health check; check startup log; see **Auto-Start After Reboot** below |
| Watchdog shows repeated `[ALERT]` | Service crashing on startup | Run `start-fans.bat` to see full error output |
| `.env` keys missing | Setup was not completed | Re-run `setup-complete.ps1` |
| `waitress-serve.exe` not found | `waitress` package missing in `.venv` | Activate `.venv` and run `pip install waitress` |
| `NET::ERR_CERT_AUTHORITY_INVALID` / privacy warning | Certificate not trusted or wrong hosts mapping | Trust certificate on that device; verify hosts entry points to the server |
| `HTTP ERROR 502` | Caddy is running but Waitress/Django is not | Run health check, then `start-fans.bat` |
| `ERR_CONNECTION_REFUSED` | Services are down | Start the system and verify health |
| `Bad Request (400)` | `fans-barangay.local` missing from `ALLOWED_HOSTS` | Add it to `.env` and restart |
| `CSRF verification failed` | `CSRF_TRUSTED_ORIGINS` missing | Add `https://fans-barangay.local` to `.env` and restart |
| `Internal Server Error (500)` / `Missing staticfiles manifest entry` | Static files not collected | Run `python manage.py collectstatic --noinput` |
| `EMBEDDING_ENCRYPTION_KEY` invalid | `.env` key format is wrong | Generate a new key with `python manage.py generate_key` and update `.env` |

---

### Real deployment fixes that were required

#### 1) Waitress missing from `.venv`

During actual deployment, `start-fans.bat` failed because `.venv\Scripts\waitress-serve.exe` did not exist.

**Fix:**

```powershell
cd C:\FANSC
.venv\Scripts\activate
pip install waitress
```

**Recommended permanent fix:** Add `waitress` to `requirements.txt`.

---

#### 2) Wrong hosts mapping caused browser issues

During actual testing, the system failed when `fans-barangay.local` pointed to the wrong IP (for example, the router/gateway IP).

**Correct mapping:**
- On the **server itself**, `fans-barangay.local` can point to `127.0.0.1`
- On **client/staff devices**, `fans-barangay.local` must point to the **server's actual LAN IP** (for example, `192.168.1.50`)

Examples:

**Server hosts file**
```text
127.0.0.1   fans-barangay.local
```

**Client hosts file**
```text
192.168.1.50   fans-barangay.local
```

After editing, run:

```powershell
ipconfig /flushdns
```

---

#### 3) `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` needed updating

The app returned `Bad Request (400)` until the local domain was added.

**In `.env`:**

```env
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.50,fans-barangay.local
CSRF_TRUSTED_ORIGINS=https://fans-barangay.local
```

---

#### 4) Static files had to be collected

The login page failed with a staticfiles manifest error until static files were built.

**Fix:**

```powershell
cd C:\FANSC
.venv\Scripts\activate
python manage.py collectstatic --noinput
```

---

#### 5) `EMBEDDING_ENCRYPTION_KEY` had to be regenerated

The system logged a Fernet key error until the `.env` value was corrected.

**Generate a new key:**

```powershell
cd C:\FANSC
.venv\Scripts\activate
python manage.py generate_key
```

Then paste the generated value into `.env`:

```env
EMBEDDING_ENCRYPTION_KEY=YOUR_GENERATED_KEY_HERE
```

**Important:** Keep this key secret. Losing it can make encrypted embeddings unreadable.

---

#### 6) Auto-start after reboot needed a timing fix

During real deployment, the Task Scheduler startup task ran correctly, but the boot-time hidden launcher checked port 8000 too early and marked startup as failed before Django + FaceNet finished loading.

**Symptom:**
- After reboot, Caddy was up but Waitress was reported as down
- Health check showed the task had run, but port 8000 was not yet responding
- Watchdog then attempted recovery

**Cause:**
- The hidden startup script did not wait long enough for Django/FaceNet warmup

**Required fix in `scripts\start\start-fans-hidden.ps1`:**

Change this:
```powershell
Start-Sleep -Seconds 6
```

To:
```powershell
Start-Sleep -Seconds 25
```

And change this:
```powershell
$port8000OK = Test-PortListening -Port 8000 -Retries 6 -DelayMs 1000
```

To:
```powershell
$port8000OK = Test-PortListening -Port 8000 -Retries 25 -DelayMs 1000
```

**Result after fix:**
- Waitress had enough time to start during boot
- Health check passed
- HTTPS end-to-end worked
- Watchdog confirmed the system became healthy

---

### How to verify startup is really working

After a reboot:

1. Do **not** manually run any start script
2. Wait about **30–60 seconds**
3. Open:
   ```
   https://fans-barangay.local
   ```
4. Run:
   ```powershell
   C:\FANSC\scripts\admin\check-system-health.ps1
   ```

You want to see:
- `Waitress process` → Running
- `Port 8000 (app)` → LISTENING
- `Caddy process` → Running
- `Port 443 (HTTPS)` → LISTENING
- `HTTPS end-to-end` → responds correctly
- Final line:
  ```
  HEALTH: ALL CHECKS PASSED
  ```

---

## 📂 Script Reference

| Script | Purpose | Who Uses It |
|---|---|---|
| `scripts\setup\setup-complete.ps1` | **Master one-time setup** — runs the entire setup flow from start to finish | IT/Admin (once) |
| `scripts\setup\setup-secure-server.ps1` | Lower-level setup: venv, dependencies, certificates, Django configuration | IT/Admin (advanced) |
| `scripts\setup\setup-autostart.ps1` | Registers the auto-start task in Windows Task Scheduler only | IT/Admin (advanced) |
| `scripts\setup\Create-Desktop-Shortcut.ps1` | Creates a desktop shortcut for easy manual startup | IT/Admin (optional) |
| `scripts\start\start-fans-hidden.ps1` | Silent startup launcher — called by Task Scheduler at boot only, never manually | Task Scheduler only |
| `scripts\start\start-fans-quiet.bat` | Manual daily launcher — starts both services minimized in the background | IT/Admin (manual start) |
| `scripts\start\start-fans.bat` | Debug launcher — starts both services in visible windows for troubleshooting | IT/Admin (debug only) |
| `scripts\admin\fans-control-center.ps1` | All-in-one admin menu: start, stop, restart, health check, logs, repair tools | IT/Admin (recommended) |
| `scripts\admin\check-system-health.ps1` | Live health diagnostic — read-only, checks every component and reports status | IT/Admin (any time) |
| `scripts\admin\watchdog.ps1` | Self-healing monitor — runs automatically via Task Scheduler 150s after boot, never manually | Task Scheduler only |
| `scripts\admin\start-now.ps1` | Start services immediately without rebooting or re-running any setup | IT/Admin |
| `scripts\admin\stop-fans.ps1` | Stops Waitress and Caddy cleanly | IT/Admin |
| `scripts\admin\repair-autostart.ps1` | Re-register auto-start Task Scheduler task only (targeted fix) | IT/Admin |
| `scripts\admin\repair-watchdog.ps1` | Re-register watchdog Task Scheduler task only (targeted fix) | IT/Admin |
| `scripts\admin\repair-hosts.ps1` | Add fans-barangay.local to server hosts file (targeted fix) | IT/Admin |
| `scripts\admin\create-admin-user.ps1` | Create or add user accounts with selectable role | IT/Admin |
| `CLIENT-SETUP\trust-local-cert.bat` | Installs the local HTTPS certificate on a client device | IT/Admin (per device, once) |

---

## ⚠️ Important Notes

- **Run setup as Administrator.** `setup-complete.ps1` requires Administrator rights to register Task Scheduler tasks and bind to port 443. Right-click → Run with PowerShell, or open PowerShell as Admin first.

- **Do not run setup multiple times unnecessarily.** `setup-complete.ps1` is safe to re-run if something failed, but running it repeatedly when everything is working is not needed and may regenerate security keys.

- **All devices must be on the same network.** Staff devices and the server PC must be connected to the same LAN or Wi-Fi. The system does not work over the internet or from outside the barangay network.

- **Install the certificate on every client device.** The `CLIENT-SETUP\trust-local-cert.bat` script must be run once on each device that staff will use. Without it, the browser will show a security warning and the camera will not work.

- **Do not move script files.** Scripts calculate the project root from their own location. Moving them to different folders will break path resolution.

- **The watchdog runs automatically.** Do not run `watchdog.ps1` manually. It is managed by Task Scheduler and starts automatically 150 seconds after each boot (after the main startup task and FaceNet model load finish). To stop or reset it, use Windows Task Scheduler and look for the task named **FANS-C Watchdog**.

- **Backup your `.env` file.** This file contains the `SECRET_KEY` and `EMBEDDING_ENCRYPTION_KEY`. If it is lost, encrypted face data cannot be read. Store a secure copy of this file off the server.

- **FaceNet warmup makes startup slower.** A slower first startup after boot is normal. Give the system time to finish loading before deciding it failed.

---

## 🏗 System Architecture

```
Browser (staff device)
        |
        | HTTPS — port 443
        v
   [ Caddy ]  — HTTPS reverse proxy
        |
        | HTTP — port 8000 (local only)
        v
   [ Waitress ] — Python WSGI server
        |
        v
   [ Django ] — FANS-C application
        |
        v
   [ SQLite / Database ]  +  [ FaceNet model ]
```

**In plain terms:**

- **Django** is the application itself — it handles logins, records, face verification logic, and the web pages staff see.
- **Waitress** serves the Django application on port 8000. It is a production-grade Python server.
- **Caddy** sits in front of Waitress and handles HTTPS (the secure, encrypted connection). It terminates SSL and forwards requests to Waitress. HTTPS is required for the browser camera to work.
- **FaceNet** is the facial recognition model. It converts a face image into a numerical fingerprint and compares it against enrolled data to verify identity.
- **Task Scheduler** starts Waitress and Caddy automatically at boot, and runs the watchdog in the background.
- **The watchdog** monitors Waitress and Caddy every 45 seconds. If either stops responding, it restarts the failed service automatically — up to 3 attempts per 10-minute window.

Everything runs on one server PC, inside the barangay's local network. No cloud. No internet dependency.

---

## 🔐 Role Summary

| Role | DB Value | What they can do |
|---|---|---|
| **Head Barangay** | `head_brgy` | All operational tasks: verify, register, approve claims/manual-reviews, manage users, run reports, reset passwords |
| **IT / Admin** | `admin_it` | All Head Barangay permissions + system diagnostics, connection info, technical setup pages |
| **Staff** | `staff` | Register beneficiaries, run verification, submit manual-review or special-claim requests; no user management or reports |
| ~~Admin (legacy)~~ | `admin` | **Fully migrated.** Migration `accounts/0006` converted all existing rows to IT/Admin. No longer assignable. Constant retained as safety fallback only. |

> Staff cannot approve pending claims or access reports. Pending claims (submitted without an active event) appear in the Admin Review Queue for Head Barangay to approve.

### Creating users

Use:

```powershell
scripts\admin\create-admin-user.ps1
```

The updated script now supports selectable role creation:

1. `IT/Admin`
2. `Head Barangay`
3. `Staff`

This is useful for controlled user creation from PowerShell when needed.

---

## 📊 Reports & Export

Head Barangay and IT/Admin have access to two report views. They are accessible from two places:
- **Navbar → Admin → Claims Report / Event Summary**
- **Dashboard → Quick Actions → Claims Report / Event Summary**

| Report | URL | Export options |
|---|---|---|
| Claims Report | `/verification/reports/claims/` | Print / Save as PDF, Excel (.xlsx) |
| Event Summary | `/verification/reports/event-summary/` | Print / Save as PDF, Excel (.xlsx) |

Reports can be filtered by date range, event, status, and claimant type. All exports are logged in the audit trail.

**To export as PDF:** Click **Print / Save as PDF** — this opens a clean print-ready page in a new browser tab. Use the browser's built-in print dialog (Ctrl+P or Cmd+P) and select "Save as PDF" as the printer destination.

**To export as Excel:** Click **Export Excel** — the browser downloads a `.xlsx` file immediately.

---

## 🔑 Password Management

- **Change own password** — Available to all users via the user menu (top right) → *Change Password*
- **Reset another user's password** — Head Barangay can reset any user's password. IT/Admin can reset Staff accounts only. Go to **Admin → User Management** and click the key icon next to the user
- All password resets are recorded in the audit log with the resetting admin's identity

---

*For additional reference files, see [SETUP.md](SETUP.md) (developer setup) and [CLIENT_ACCESS.md](CLIENT_ACCESS.md) (staff browser access guide).*