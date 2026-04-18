# FANS-C: A Secure FaceNet-Based Facial Verification System for Senior Citizen Stipend Distribution

> **A functional biometric identity verification system built for real-world barangay deployment.**
> Designed to streamline senior citizen stipend distribution through secure facial recognition — no paper lists, no manual identity checks.

Developed as a capstone project for deployment in controlled government environments (Quezon City).

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

---

## Key Features

- **Facial Verification** — Uses FaceNet biometric matching to confirm a senior citizen's identity before releasing their stipend
- **Centralized LAN Server** — One server PC serves the entire barangay office; staff access via any browser on the same network
- **Secure HTTPS Access** — All connections are encrypted; camera access (required for face scanning) only works over HTTPS
- **Auto-Start on Boot** — The system starts automatically when the server PC turns on; no manual steps required
- **Self-Healing Watchdog** — A background monitor checks the system every 45 seconds and automatically restarts services if they fail
- **Health Check Tool** — IT/Admin can run a single script at any time to see the live status of every component
- **Offline-Safe Design** — The system runs entirely within the barangay's local network; no internet connection is required for normal operation
- **Role-Based Access** — Separate accounts for IT/Admin and barangay staff with appropriate permissions

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

---

### Step 2 — Trust the certificate on each client device

On every device that staff will use to access the system, run the certificate trust script once:

```
CLIENT-SETUP\trust-local-cert.bat
```

> This allows the browser on that device to accept the local HTTPS certificate without a security warning.
> Without this step, the browser will block access or disable the camera.

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
| System did not start after reboot | Task Scheduler task missing or disabled | Run `setup-complete.ps1` again as Admin |
| Watchdog shows repeated `[ALERT]` | Service crashing on startup | Run `start-fans.bat` to see full error output |
| `.env` keys missing | Setup was not completed | Re-run `setup-complete.ps1` |

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
| `scripts\admin\create-admin-user.ps1` | Create or add a Django admin account | IT/Admin |
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

*For additional reference files, see [SETUP.md](SETUP.md) (developer setup) and [CLIENT_ACCESS.md](CLIENT_ACCESS.md) (staff browser access guide).*
