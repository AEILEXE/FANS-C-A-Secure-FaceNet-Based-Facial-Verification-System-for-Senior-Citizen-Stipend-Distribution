# FANS-C Setup and Recovery Guide (Windows)

This guide covers initial setup and full recovery after folder moves, broken venvs, and TensorFlow failures.

---

## Python Version Requirement

**Python 3.10 or 3.11 is required.**

`tensorflow-cpu 2.13.x` (used by keras-facenet) does not support Python 3.12 or 3.13. Using the wrong Python version produces a DLL load error at runtime, even if pip install succeeded.

Check what you have:
```
py --list
python --version
```

Download Python 3.11 if needed: https://www.python.org/downloads/release/python-3119/
Install it with "Add Python to PATH" checked.

After install, confirm it is visible:
```
py -3.11 --version
```

---

## Path Length Warning

Windows limits file paths to 260 characters by default. TensorFlow's wheel contains deeply nested files that exceed this limit during extraction. The symptom is pip failing with `No such file or directory` on a path that clearly exists.

**Option 1 (recommended): Use a short project path.**

Clone or copy the project to `D:\FANS`. All project paths use Django's `BASE_DIR` (relative to `manage.py`), so moving does not break any code.

**Option 2: Enable long path support (requires admin).**

Run PowerShell as Administrator:
```powershell
reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f
```
Restart Windows. Then retry pip install.

---

## Initial Setup (Clean Install)

Assumes the project is at `D:\FANS` and Python 3.11 is installed.

```powershell
py -3.11 -m venv D:\FANS\.venv
D:\FANS\.venv\Scripts\activate
python --version
pip install --upgrade pip
pip install -r D:\FANS\requirements.txt
```

Copy and configure the environment file:
```powershell
copy D:\FANS\.env.example D:\FANS\.env
```

Edit `D:\FANS\.env`. Minimum required for local demo:
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

Generate a stable encryption key (do this once; losing it makes stored embeddings unreadable):
```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Paste the output into `.env` as `EMBEDDING_ENCRYPTION_KEY=<value>`.

Apply migrations and finish setup:
```powershell
python manage.py makemigrations
python manage.py migrate
python manage.py init_config
python manage.py create_admin
python manage.py collectstatic --noinput
python manage.py runserver
```

Open http://127.0.0.1:8000/ and log in with admin / Admin@1234. Change the password immediately.

---

## Recovery After Moving or Renaming the Project Folder

Virtual environments store absolute paths inside `pyvenv.cfg` and all scripts. After a folder move, the venv is broken and cannot be repaired in place.

### Step 1: Clean up broken venvs

Delete the old `.venv` inside the project folder:
```powershell
rmdir /s /q D:\old-path\.venv
```

Delete any accidental venvs created in wrong locations (e.g., `D:\.venv` created by mistake):
```powershell
rmdir /s /q D:\.venv
```

### Step 2: Confirm the project is at a short path

If the project is still at the long path, copy it:
```powershell
robocopy "D:\FANS-C-A-Secure-FaceNet-Based-Facial-Verification-System-for-Senior-Citizen-Stipend-Distribution" "D:\FANS" /E /XD .git
```
Then work from `D:\FANS`.

### Step 3: Rebuild the venv

```powershell
py -3.11 -m venv D:\FANS\.venv
D:\FANS\.venv\Scripts\activate
python --version
pip install --upgrade pip
pip install -r D:\FANS\requirements.txt
```

### Step 4: Apply any pending migrations

```powershell
cd D:\FANS
python manage.py makemigrations
python manage.py migrate
```

If `makemigrations` says "No changes detected", your migration state is already correct.

### Step 5: Verify the face model loaded

Start the server and go to http://127.0.0.1:8000/verification/config/

The "Face Recognition Model Status" card shows either:
- **FaceNet (keras-facenet)** in green: real model loaded, verification works.
- **MOCK -- not loaded** in red: model failed to load. Do not attempt real verifications. See TF troubleshooting below.

---

## TensorFlow Troubleshooting

### DLL Load Failure

**Error message:**
```
DLL load failed while importing _pywrap_tensorflow_lite_metrics_wrapper: The specified procedure could not be found.
```

**Cause:** Python version mismatch. Your venv was created with Python 3.12 or 3.13.

**Fix:**

1. Delete `.venv`.
2. Install Python 3.11.
3. Recreate venv with `py -3.11 -m venv .venv`.
4. Reinstall: `pip install -r requirements.txt`.

### TensorFlow Installs but keras-facenet Fails to Import

```
Cannot import name 'xxx' from 'keras'
```

This means keras-facenet is trying to use Keras 3 (bundled with TF 2.16+) but was written for Keras 2 (TF 2.13.x). The fix is to stay on `tensorflow-cpu>=2.13.0,<2.14.0` with Python 3.11. Do not upgrade TensorFlow without also upgrading keras-facenet.

### tensorflow-cpu Install Fails with Long Path Error

```
OSError: [Errno 2] No such file or directory: ...memory_allocator_impl.h
HINT: This error might have been caused by long path support being disabled.
```

Fix: Move project to `D:\FANS` and retry, or enable long path support (see Path Length Warning above).

### How to Tell If Verification Is Real

On the verification capture screen, a red banner appears if the mock model is active.
On the result screen, a red banner appears if that specific attempt was rejected because the model was not loaded.
At `/verification/config/`, the model status card shows the exact load error.

---

## Demo Mode vs. Mock Model

These are different things. Do not confuse them.

| What | Meaning |
|---|---|
| `DEMO_MODE=True` | Uses a lower threshold (0.60) and makes liveness non-blocking. Real face matching still runs if the model is loaded. |
| Mock model active | keras-facenet failed to load. All similarity scores are random. No real face matching happens at all. |

`DEMO_MODE` is a threshold and UX setting. Mock model is a model loading failure.

---

## User Roles

| Role | Permissions |
|---|---|
| Admin | Full access: users, override, config, logs, stipend events |
| Staff | Register beneficiaries and process verification claims |

---

## ML Model Notes

| Model | How it loads |
|---|---|
| FaceNet (keras-facenet) | Downloaded ~90MB on first use from Hugging Face. Requires internet on first run. Cached in ~/.keras. |
| RetinaFace | Optional. Downloaded ~100MB on first use. Commented out in requirements.txt by default. |
| Anti-spoofing | Texture analysis only. No external model needed. Not production-grade against adversarial attacks. |
| MediaPipe (head movement) | Loaded from CDN in the browser. No server-side install needed. |

---

## Database Notes

By default (`USE_SQLITE=True` in `.env`), the project uses `db.sqlite3` in the project root. This is fine for capstone demos.

For PostgreSQL: set `USE_SQLITE=False` in `.env` and add DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT. Uncomment `psycopg2-binary` in `requirements.txt` and reinstall.

---

## EMBEDDING_ENCRYPTION_KEY Warning

If `EMBEDDING_ENCRYPTION_KEY` is blank in `.env`, a random key is generated each time the server starts. This means:

- Embeddings registered in one session cannot be read in the next session.
- Verification will always fail after a server restart.

Set a stable key once and store it safely. See Initial Setup above.
