# FANS-C Developer Setup Guide (Windows)

> For barangay staff accessing the system from a browser, see [CLIENT_ACCESS.md](CLIENT_ACCESS.md) instead.
>
> **New to this repo?** The project was reorganized for clarity. Scripts are now under `scripts/` (setup, start, admin), dev/build tools under `dev/`, and deprecated files under `legacy/`. See the folder structure below.

---

## Quick Setup — Barangay Server (IT/Admin)

> **This is the recommended IT/Admin setup path.** Run `setup-complete.ps1` once on the server machine. It orchestrates every required step, verifies the result of each one, and confirms the system is actually serving before declaring success.

### Prerequisites

Before running setup, ensure:

- **Python 3.11** is installed (TensorFlow does not support 3.12 or 3.13)
  Download: https://www.python.org/downloads/release/python-3119/
  During install, check **"Add Python to PATH"**
- **caddy.exe** is placed in `tools\caddy.exe` — download from https://caddyserver.com/docs/install
- **mkcert.exe** is placed in `tools\mkcert\mkcert.exe` — download from https://github.com/FiloSottile/mkcert/releases

Confirm Python 3.11 is installed:
```powershell
py -3.11 --version
```

> Tip: Keep the project at a short path like `D:\FANS`. Windows has a 260-character path limit that causes TensorFlow installs to fail on long paths.

### Step 1 — Clone the repo

Using GitHub Desktop: File → Clone Repository → paste the repo URL.

Or using git:
```powershell
git clone <repo-url> D:\FANS
cd D:\FANS
```

### Step 2 — Run the master setup (recommended)

Right-click `scripts\setup\setup-complete.ps1` and choose **Run with PowerShell** (as Admin), or:

```powershell
cd D:\FANS
.\scripts\setup\setup-complete.ps1
```

This single script runs every required setup step in order:

1. Runs `setup-secure-server.ps1` — creates `.venv`, installs dependencies, generates TLS certs, runs Django migrations
2. Verifies `fans-cert.pem` and `fans-cert-key.pem` exist
3. Verifies `caddy.exe` is found
4. Verifies `.env` has `SECRET_KEY` and `EMBEDDING_ENCRYPTION_KEY`
5. Runs `setup-autostart.ps1` — registers the Task Scheduler task for automatic startup at boot
6. Optionally creates a desktop shortcut
7. Runs a **live startup validation** — starts services and confirms ports 8000 and 443 are actually listening
8. Registers the **watchdog task** — a self-healing background monitor that automatically restarts Waitress or Caddy if either stops responding during the day

At the end, prints a clear PASS / FAIL summary for every step.

> If you get an error about execution policy, run this first:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

> **Re-running setup:** Pass `-SkipDeps` to skip the long pip install when `.venv` already exists:
> `.\scripts\setup\setup-complete.ps1 -SkipDeps`

### Step 3 — Edit .env (required for production)

After setup completes, open `.env` and set:

```
ALLOWED_HOSTS=fans-barangay.local,192.168.1.77,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://fans-barangay.local
DEBUG=False
```

Replace `192.168.1.77` with your server's actual LAN IP (shown during setup).

### Step 4 — Set up client devices

Copy the `CLIENT-SETUP\` folder to a USB drive. On each client PC, run:

```
CLIENT-SETUP\trust-local-cert.bat
```

(as Administrator — double-click and approve the UAC prompt)

### Step 5 — Daily use

After setup is complete, the Head Barangay workflow is:

1. Turn on the PC
2. Wait about 30 seconds for the system to start automatically
3. Open any browser
4. Go to `https://fans-barangay.local`
5. Log in normally

No scripts, no terminal, no troubleshooting for daily use.

The system is now **self-healing**: if Waitress or Caddy stops responding during the day, the watchdog detects it within 45 seconds and restarts the failed service automatically. The Head Barangay does not need to do anything.

---

## Script Reference

| Script | Who runs it | When |
|---|---|---|
| `scripts\setup\setup-complete.ps1` | IT/Admin | **Once** — recommended master setup entry point |
| `scripts\setup\setup-secure-server.ps1` | IT/Admin | Once (called by setup-complete, or standalone) |
| `scripts\setup\setup-autostart.ps1` | IT/Admin | Once (called by setup-complete, or standalone) |
| `scripts\setup\Create-Desktop-Shortcut.ps1` | IT/Admin | Optional, once |
| `CLIENT-SETUP\trust-local-cert.bat` | IT/Admin | Once per client device |
| `scripts\admin\stop-fans.ps1` | IT/Admin | To stop services for maintenance |
| `scripts\admin\check-system-health.ps1` | IT/Admin | Diagnostics — anytime |
| `scripts\admin\watchdog.ps1` | Task Scheduler | Called automatically 90s after boot — never run manually |
| `scripts\start\start-fans-quiet.bat` | IT/Admin | Manual start (if auto-start not configured) |
| `scripts\start\start-fans.bat` | IT/Admin | Debug start (visible windows, full output) |
| `scripts\start\start-fans-hidden.ps1` | Task Scheduler | Called automatically at boot — never run manually |

---

## Quick Setup — Developer

For a developer on a fresh Windows laptop running the app locally:

### Step 1 — Clone

```powershell
git clone <repo-url> D:\FANS
cd D:\FANS
```

### Step 2 — Run setup

```powershell
.\scripts\setup\setup-secure-server.ps1
```

### Step 3 — Start the server

For a visible debug start (shows all output):
```powershell
.\scripts\start\start-fans.bat
```

For normal daily use (minimized background services):
```powershell
.\scripts\start\start-fans-quiet.bat
```

Or manually:
```powershell
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

### Step 4 — Open the app

Go to: https://fans-barangay.local (production) or http://127.0.0.1:8000/ (dev)

Log in with the admin account you created during setup.

---

## That's it for development mode.

The steps above are everything needed to run the system locally. The sections below cover optional configuration and production deployment.

---

## Detailed Setup

### Installing Python 3.11

1. Download from: https://www.python.org/downloads/release/python-3119/
2. Run the installer
3. Check **"Add Python to PATH"** on the first screen
4. Click Install Now

After install, confirm:
```powershell
py -3.11 --version
```

**Why Python 3.11 specifically?** `tensorflow-cpu 2.13.x` (used by keras-facenet) does not support Python 3.12 or 3.13. Using the wrong version produces a DLL load error at runtime, even if pip install succeeds.

### Path Length Warning

Windows limits file paths to 260 characters by default. TensorFlow's wheel contains deeply nested files that exceed this limit. The symptom is pip failing with `No such file or directory` on a path that clearly exists.

**Option 1 (recommended):** Clone to a short path like `D:\FANS`.

**Option 2:** Enable long path support (requires Admin PowerShell):
```powershell
reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f
```
Restart Windows, then retry.

### Manual Setup (without setup-secure-server.ps1)

If you prefer to set up manually instead of using `setup-secure-server.ps1`:

```powershell
# Create virtual environment
py -3.11 -m venv D:\FANS\.venv
D:\FANS\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

Copy and edit the environment file:
```powershell
copy .env.example .env
```

Minimum `.env` values for local development:
```
SECRET_KEY=fans-demo-secret-change-for-production
DEBUG=True
USE_SQLITE=True
DEMO_MODE=True
LIVENESS_REQUIRED=False
DEMO_THRESHOLD=0.60
ANTI_SPOOF_THRESHOLD=0.15
MAX_RETRY_ATTEMPTS=1
```

Generate an encryption key (do this once — losing it makes stored face data unreadable):
```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Paste the output into `.env` as `EMBEDDING_ENCRYPTION_KEY=<value>`.

Run migrations and finish setup:
```powershell
python manage.py migrate
python manage.py init_config
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver
```

### Full .env Reference

| Variable | Description | Development value |
|---|---|---|
| `SECRET_KEY` | Django secret key | Any random string |
| `DEBUG` | Enable debug mode | `True` |
| `USE_SQLITE` | Use SQLite instead of PostgreSQL | `True` |
| `DEMO_MODE` | Lower thresholds, non-blocking liveness | `True` |
| `LIVENESS_REQUIRED` | Block verification if liveness fails | `False` |
| `DEMO_THRESHOLD` | Face similarity threshold in demo mode | `0.60` |
| `ANTI_SPOOF_THRESHOLD` | Anti-spoof confidence cutoff | `0.15` |
| `MAX_RETRY_ATTEMPTS` | Retries before failing a verification | `2` |
| `EMBEDDING_ENCRYPTION_KEY` | Fernet key for stored face embeddings | Generate once |
| `ALLOWED_HOSTS` | Comma-separated allowed hostnames | `localhost,127.0.0.1` |

### Database Setup (PostgreSQL)

By default the project uses SQLite (`db.sqlite3` in the project root). This is fine for capstone demos.

To use PostgreSQL:
1. Install PostgreSQL and create a database
2. In `.env`, set `USE_SQLITE=False` and add:
   ```
   DB_NAME=fans_db
   DB_USER=fans_user
   DB_PASSWORD=yourpassword
   DB_HOST=localhost
   DB_PORT=5432
   ```
3. Uncomment `psycopg2-binary` in `requirements.txt`
4. Reinstall: `pip install -r requirements.txt`
5. Run `python manage.py migrate`

### Admin Account Setup

`setup-secure-server.ps1` calls `createsuperuser` interactively. If you need to set the FANS-C in-app admin role separately:

```powershell
python manage.py shell -c "
from accounts.models import CustomUser
u = CustomUser.objects.get(username='yourusername')
u.role = 'admin'
u.save()
print('Admin role set for:', u)
"
```

Django's `is_superuser`/`is_staff` (set by `createsuperuser`) and the FANS-C `role` field are separate. Both must be set for full admin access.

---

## Production Deployment (Waitress + Caddy)

For barangay deployment on a LAN server, run Django with Waitress behind Caddy for HTTPS.

### Prerequisites

```powershell
pip install waitress
```

Caddy must be installed (single `.exe`) and TLS certificates must be generated with `mkcert`.
See the `Caddyfile` in the project root for the full checklist.

### Collect static files (once before first production start)

```powershell
python manage.py collectstatic --noinput
```

### Start the system (two PowerShell windows)

**Window 1 — Waitress:**
```powershell
cd D:\FANS
.\.venv\Scripts\Activate.ps1
waitress-serve --listen=127.0.0.1:8000 fans.wsgi:application
```

**Window 2 — Caddy:**
```powershell
cd D:\FANS
caddy run --config Caddyfile
```

### Required .env values for HTTPS

```
DEBUG=False
ALLOWED_HOSTS=fans-barangay.local,192.168.1.77,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://fans-barangay.local
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https
USE_X_FORWARDED_HOST=True
```

### What remains manual on the server

| Task | When |
|---|---|
| Run `mkcert -install` (as Admin) | Once per server machine — creates the server's local CA |
| Run `mkcert fans-barangay.local 192.168.1.77 localhost 127.0.0.1` | Once; redo only if cert expires or IP changes |
| Run `mkcert -CAROOT` and copy `rootCA.pem` to each client device | Once; distribute to clients alongside `trust-local-cert.bat` |
| On each client: run `trust-local-cert.bat` (as Admin) | Once per client device — imports the **server's** rootCA.pem into Windows trust store |
| Add firewall rule for port 443 (as Admin) | Once per server machine |
| Start Waitress and Caddy after each reboot | Every time the server restarts (see startup scripts below) |
| Configure hostname resolution on client devices | Once-total if router DNS is used; once per device if hosts file fallback is used (see CLIENT_ACCESS.md) |

> **Certificate trust model:** The server generates the HTTPS certificate with its own mkcert CA. Client devices must trust the **server's** CA (`rootCA.pem`) — they do not generate or install their own mkcert CA. Running `mkcert -install` on a client machine creates a different CA that does not sign the server's certificate and does not fix the browser warning.

---

## Starting the Server After a Reboot

The project does **not** need to be reinstalled after every reboot. The `.venv`, `.env`, database, and certificates all remain in place. Only the two server processes — Waitress and Caddy — need to be started again each time the server PC is turned on.

### Option 1 — Auto-start via Task Scheduler (recommended)

If you ran `setup-complete.ps1`, the Task Scheduler task is already registered. The system starts automatically at every boot — no scripts, no windows, no IT visits required.

To verify the task is registered:
```powershell
.\scripts\admin\check-system-health.ps1
```

To register the task manually (if not already done):
```powershell
.\scripts\setup\setup-autostart.ps1
```

### Option 2 — Double-click startup (manual, with verification)

For normal manual start (minimized background, verifies ports after startup):

```
scripts\start\start-fans-quiet.bat
```

This now verifies that ports 8000 and 443 are actually listening before reporting success.

For debugging (all server windows visible, full output):

```
scripts\start\start-fans.bat
```

### Option 3 — Desktop shortcut

Run once to create a branded shortcut on the Desktop:

```powershell
.\scripts\setup\Create-Desktop-Shortcut.ps1
```

The shortcut points to `scripts\start\start-fans-quiet.bat` with the correct working directory.

### Option 4 — Manual startup

If you prefer to start manually each time:

**Window 1 — Waitress:**
```powershell
cd D:\FANS
.\.venv\Scripts\Activate.ps1
waitress-serve --listen=127.0.0.1:8000 fans.wsgi:application
```

**Window 2 — Caddy (run from project root so cert paths resolve):**
```powershell
cd D:\FANS
caddy run --config Caddyfile
```

### Diagnosing startup problems

If the browser shows `ERR_CONNECTION_REFUSED` or `This site can't be reached`:

```powershell
.\scripts\admin\check-system-health.ps1
```

This reports which services are running, which ports are listening, whether certs are present, and shows the last startup log and recent watchdog activity — without changing anything.

---

## Self-Healing Watchdog

The watchdog is a background monitor registered automatically by `setup-complete.ps1`. It runs continuously after every boot and catches failures that startup validation cannot — problems that happen hours into the day while the system is in use.

### What it does

- Checks Waitress and Caddy every **45 seconds**
- If Waitress is down: stops any stale process and starts a clean replacement
- If Caddy is down: stops any stale process and starts a clean replacement
- Confirms recovery by re-checking the port after restart

### Safeguards

| Safeguard | Detail |
|---|---|
| No duplicate processes | Kills any stale instance before starting a new one |
| Pre-restart port check | If the port recovered on its own, skips the restart |
| 60-second cooldown | Waits 60 seconds between successive restart attempts |
| Max 3 restarts per 10 minutes | Stops trying after 3 failures in a 10-minute window |
| ALERT on repeated failure | Logs a clear ALERT message and instructs IT/Admin to inspect |
| Auto-reset | If services recover (e.g., IT/Admin manually fixed them), resets failure counters |

### Log file

```
logs\fans-watchdog.log
```

Entries use these levels:

| Level | Meaning |
|---|---|
| `HEALTHY` | All services OK (logged every ~7.5 minutes to reduce noise) |
| `WARN` | A service is not responding |
| `ACTION` | A restart is being attempted |
| `OK` | Recovery was successful |
| `FAIL` | Restart was attempted but service still not responding |
| `ALERT` | Max restart attempts reached — IT/Admin inspection required |
| `WAIT` | Cooldown period — restart deferred |
| `SKIP` | Recovery skipped (already gave up after repeated failures) |

### How to read ALERT entries

If the watchdog log shows `[ALERT]` entries:

1. Run `scripts\admin\check-system-health.ps1` to see current state
2. Run `scripts\start\start-fans.bat` to see the full error output from Waitress or Caddy
3. After fixing the underlying issue, reset the watchdog by restarting the `FANS-C Watchdog` task in Windows Task Scheduler

### Task Scheduler details

| Property | Value |
|---|---|
| Task name | `FANS-C Watchdog` |
| Trigger | System startup + 90-second delay |
| Account | SYSTEM (no UAC, always elevated) |
| Window | Hidden (no visible window) |
| Auto-restart if crashed | Yes (up to 3 times, 2-minute interval) |

The 90-second delay ensures the main startup task (`FANS-C Verification System`) has fully started Waitress and Caddy before the watchdog takes its first reading.

---

## Recommended Network Setup (No Per-Device Configuration)

This section explains the best-practice network setup for a real barangay deployment. The goal is simple: once the server is configured, staff just connect to the office Wi-Fi and open one link in a browser — no one has to touch their individual devices.

### The problem with editing hosts files on every device

The default approach (editing `C:\Windows\System32\drivers\etc\hosts` on each PC) works, but has real drawbacks in practice:

- Every new staff device requires an admin to manually edit a system file
- If the server IP ever changes, every device must be updated again
- Android and iOS devices do not support hosts file editing at all
- It requires running Notepad as Administrator — staff cannot do it themselves

### The better approach: configure the router once

A standard office Wi-Fi router can be configured to handle both problems — stable IP assignment and automatic domain name resolution — in one place, for the whole network.

---

### A. DHCP Reservation — Give the Server a Stable IP

**What is DHCP?**
DHCP (Dynamic Host Configuration Protocol) is the service your router uses to automatically assign IP addresses to devices that join the network. By default, these addresses can change — your server PC might get `192.168.1.77` today and `192.168.1.82` after a reboot.

**What is a DHCP Reservation (also called a Static Lease)?**
A DHCP reservation tells the router: "always give this specific device the same IP address, every time." The device is identified by its MAC address (a permanent hardware identifier burned into its network card).

**Why this is better than setting a static IP in Windows:**

| Approach | How it works | Drawback |
|---|---|---|
| Windows static IP | You manually type the IP into Windows Network Settings | Breaks if the router's DHCP range overlaps; can cause IP conflicts; requires knowing the correct gateway and DNS values |
| Router DHCP Reservation | Router always hands out the same IP to the server's MAC address | Zero risk of IP conflict; router manages everything; survives Windows reinstall |

**How to set it up (generic steps — exact menu names vary by router brand):**

1. Log in to your router admin panel. The address is usually `192.168.1.1` or `192.168.0.1` — type it in a browser on any device connected to the router.
2. Look for a section called **DHCP**, **LAN**, or **Network Settings**.
3. Inside it, find **DHCP Reservations**, **Static Leases**, or **Address Reservation**.
4. Find the server PC's MAC address. You can find it on the server PC by running this in Command Prompt:
   ```
   ipconfig /all
   ```
   Look for **Physical Address** under your active network adapter (Wi-Fi or Ethernet). It looks like: `A4-B1-C2-D3-E4-F5`
5. Enter the MAC address and choose a fixed IP (e.g., `192.168.1.150`). Pick a number that is outside the router's normal DHCP range (e.g., if DHCP range is `.100` to `.149`, pick `.150`).
6. Save and apply. Restart the server PC — it should now always get that IP.

> **What this achieves:** The server's IP address never changes, even after a reboot or power cut. You never need to update any configuration because of an IP change.

---

### B. Local DNS / Hostname Mapping — Resolve the Domain Automatically

**What is DNS?**
DNS (Domain Name System) is the service that translates a name like `fans-barangay.local` into an IP address like `192.168.1.150`. Normally this happens via public internet DNS servers. For local names, the router can handle it instead.

**What does "hostname mapping" mean?**
It means telling the router: "when any device on this network asks what IP `fans-barangay.local` is, respond with `192.168.1.150`."

Once this is set on the router, every device on the network — Windows PCs, laptops, tablets, phones — can automatically resolve `fans-barangay.local` without any changes to the device itself.

**How to set it up (generic steps):**

1. Log in to your router admin panel.
2. Look for a section called **DNS**, **Advanced DNS**, **Local DNS**, **Hostname Mapping**, or **Static Hosts**. This varies by router — check under Advanced Settings if you do not see it immediately.
3. Add an entry:
   - Hostname / Domain: `fans-barangay.local`
   - IP Address: the fixed IP you assigned in step A (e.g., `192.168.1.150`)
4. Save and apply.

> **What this achieves:** Every device that joins the office Wi-Fi can immediately reach `https://fans-barangay.local` — no hosts file edits, no per-device setup, no IT visit needed for new devices.

---

### Does every router support this?

Most modern home and office routers support DHCP reservations. Local DNS / hostname mapping is less universal but available on most branded routers (TP-Link, ASUS, Netgear, D-Link, Mikrotik, Ubiquiti, and most ISP-provided routers).

If the router does not support local DNS entries, use the hosts file fallback described in the next section.

---

### Comparison: Which approach is right for your barangay?

| Method | Setup Effort | Maintenance | Works on mobile? | Recommended |
|---|---|---|---|---|
| Hosts file (manual) | Per device — IT must visit each PC | High — must redo if IP changes | No (iOS/Android) | Fallback only |
| Static IP in Windows | One device | Medium — risk of IP conflict | N/A | Not recommended |
| Router DHCP Reservation + Local DNS | One-time on the router | Low — set and forget | Yes | **BEST** |

---

### Fallback / Manual Setup (for testing or when router config is not available)

If router DNS configuration is not available, use the hosts file method on each client device:

1. Open Notepad **as Administrator** on the client device
2. Open the file: `C:\Windows\System32\drivers\etc\hosts`
3. Add this line at the bottom (replace the IP with your server's actual IP):
   ```
   192.168.1.150   fans-barangay.local
   ```
4. Save the file. Open a new browser tab and go to `https://fans-barangay.local`.

This must be done once per device. If the server IP ever changes, every device's hosts file must be updated.

See [CLIENT_ACCESS.md](CLIENT_ACCESS.md) for the staff-facing version of these instructions.

---

## LAN vs Internet — What This System Actually Needs

This system is **LAN-based (on-premise)**. It runs on a server PC inside the barangay office and is accessed by staff using browsers on the same local Wi-Fi or wired network.

| Scenario | System status |
|---|---|
| Server PC is on, LAN is working, internet is down | **System works normally.** No internet required. |
| Server PC is on, internet is working | System also works (internet is irrelevant to operation). |
| Server PC is off | System is unavailable. Staff cannot log in until the server is restarted. |
| Staff device loses Wi-Fi but server is still on | Staff device cannot reach the system until Wi-Fi reconnects. |

### What requires internet?

- **FaceNet model download** — only on the very first startup after setup. After that it is cached locally.
- **Software updates** — only when manually updating the project.
- **Nothing else.** Day-to-day operation is 100% local.

### Staff PCs

Staff PCs do not need Python, PostgreSQL, GitHub Desktop, or any project files. They only need:
- A web browser (Chrome, Edge, or Firefox)
- Connection to the same Wi-Fi or LAN as the server PC
- Domain resolution for `fans-barangay.local` — handled automatically if the router is configured with a local DNS entry (recommended), or done once per device via the hosts file (fallback)

---

## Troubleshooting

### DLL Load Failure

```
DLL load failed while importing _pywrap_tensorflow_lite_metrics_wrapper
```

**Cause:** Wrong Python version. Your venv was created with Python 3.12 or 3.13.

**Fix:** Delete `.venv`, install Python 3.11, recreate the venv with `py -3.11 -m venv .venv`, reinstall.

### keras-facenet Import Error

```
Cannot import name 'xxx' from 'keras'
```

**Cause:** keras-facenet requires Keras 2 (bundled with TF 2.13.x). TF 2.16+ bundles Keras 3, which breaks it.

**Fix:** Stay on `tensorflow-cpu>=2.13.0,<2.14.0` with Python 3.11.

### TensorFlow Install Fails with Long Path Error

```
OSError: [Errno 2] No such file or directory: ...memory_allocator_impl.h
```

**Fix:** Move the project to `D:\FANS` and retry, or enable long path support (see above).

### Face Verification Returns Random Results

Go to `/verification/config/`. If the "Face Recognition Model Status" card shows **MOCK — not loaded** in red, keras-facenet failed to load. Check the error shown and follow the TF troubleshooting steps above.

### Recovery After Moving the Project Folder

Virtual environments store absolute paths and break after a folder move.

1. Delete the old `.venv`: `rmdir /s /q .venv`
2. Move the project to a short path (e.g., `D:\FANS`)
3. Re-run `.\scripts\setup\setup-secure-server.ps1`

---

## Usage Modes

### Developer Mode

- Full setup required (Python, venv, requirements, `.env`)
- Used for development, testing, and running the server
- Access via: http://127.0.0.1:8000/ (or HTTPS if Waitress+Caddy are running)

### Client Mode (Barangay Staff)

- No installation required
- Access the system from any browser on the same LAN
- URL: `https://fans-barangay.local`
- See [CLIENT_ACCESS.md](CLIENT_ACCESS.md) for setup instructions

---

## Demo Mode vs. Mock Model

These are different things.

| What | Meaning |
|---|---|
| `DEMO_MODE=True` | Uses a lower threshold and non-blocking liveness. Real face matching still runs if the model loaded. |
| Mock model active | keras-facenet failed to load. All similarity scores are random. No real face matching at all. |

`DEMO_MODE` is a threshold/UX setting. The mock model is a load failure.

---

## User Roles

| Role | Permissions |
|---|---|
| Admin | Full access: users, manual review, config, logs, stipend events, Django `/admin` panel |
| Staff | Register beneficiaries and process verification claims |

---

## ML Model Notes

| Model | How it loads |
|---|---|
| FaceNet (keras-facenet) | Downloaded ~90 MB on first use from Hugging Face. Cached in `~/.keras`. Requires internet on first run. |
| Anti-spoofing | Texture analysis only. No external model needed. |
| MediaPipe (head movement) | Loaded from CDN in the browser. No server-side install. |

---

## EMBEDDING_ENCRYPTION_KEY Warning

If this key is blank in `.env`, a random key is generated each server start. This means face embeddings registered in one session cannot be read in the next session — verification will always fail after a restart.

Set a stable key once with:
```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Paste the output into `.env` as `EMBEDDING_ENCRYPTION_KEY=<value>` and back it up securely.
