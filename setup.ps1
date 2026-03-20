# ============================================================
# FANS-C Setup Script — PowerShell
# Run this ONCE to set up the project from scratch.
# ============================================================
# REQUIREMENTS BEFORE RUNNING:
#   1. Python 3.11 installed (NOT 3.12 or 3.13)
#      Download: https://www.python.org/downloads/release/python-3119/
#   2. Git (optional, only needed if you cloned the repo)
#   3. This script must be run from the project root folder:
#        D:\FANS\FANS-C-A-Secure-FaceNet-Based-Facial-Verification-System-...
# ============================================================
# HOW TO RUN (from the project root in PowerShell):
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#   .\setup.ps1
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  FANS-C Setup Script" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Verify Python 3.11 ───────────────────────────────────────────────
Write-Host "[1/8] Checking Python version..." -ForegroundColor Yellow
$pyVersion = python --version 2>&1
Write-Host "      Found: $pyVersion"

if ($pyVersion -notmatch "3\.11") {
    Write-Host ""
    Write-Host "ERROR: Python 3.11 is required." -ForegroundColor Red
    Write-Host "       Found: $pyVersion" -ForegroundColor Red
    Write-Host "       Download Python 3.11 from: https://www.python.org/downloads/release/python-3119/" -ForegroundColor Red
    Write-Host "       During install: check 'Add Python to PATH'" -ForegroundColor Red
    exit 1
}
Write-Host "      OK" -ForegroundColor Green

# ── Step 2: Enable long paths (Windows) ──────────────────────────────────────
Write-Host "[2/8] Enabling Windows long path support..." -ForegroundColor Yellow
try {
    $regPath = "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem"
    $current = (Get-ItemProperty -Path $regPath -Name "LongPathsEnabled" -ErrorAction SilentlyContinue).LongPathsEnabled
    if ($current -ne 1) {
        New-ItemProperty -Path $regPath -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force | Out-Null
        Write-Host "      Enabled." -ForegroundColor Green
    } else {
        Write-Host "      Already enabled." -ForegroundColor Green
    }
} catch {
    Write-Host "      Could not set registry (run as Administrator to enable this)." -ForegroundColor Yellow
    Write-Host "      Continuing — long path issues may occur during TensorFlow install." -ForegroundColor Yellow
}

# ── Step 3: Create virtual environment ───────────────────────────────────────
Write-Host "[3/8] Creating virtual environment (.venv)..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "      .venv already exists — skipping creation." -ForegroundColor Yellow
} else {
    python -m venv .venv
    Write-Host "      Created." -ForegroundColor Green
}

# ── Step 4: Activate virtual environment ─────────────────────────────────────
Write-Host "[4/8] Activating .venv..." -ForegroundColor Yellow
& ".venv\Scripts\Activate.ps1"
Write-Host "      Activated." -ForegroundColor Green

# ── Step 5: Upgrade pip ───────────────────────────────────────────────────────
Write-Host "[5/8] Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
Write-Host "      Done." -ForegroundColor Green

# ── Step 6: Install numpy first (must precede scipy + tensorflow) ─────────────
Write-Host "[6/8] Installing numpy 1.24.4 first (required before scipy/tensorflow)..." -ForegroundColor Yellow
pip install "numpy==1.24.4" --quiet
Write-Host "      Done." -ForegroundColor Green

# ── Step 7: Install all requirements ─────────────────────────────────────────
Write-Host "[7/8] Installing requirements (this may take 5-15 minutes)..." -ForegroundColor Yellow
Write-Host "      tensorflow-cpu downloads ~350MB. Please be patient." -ForegroundColor Yellow
Write-Host "      keras-facenet downloads ~90MB weights on first model load." -ForegroundColor Yellow
pip install -r requirements.txt
Write-Host "      Done." -ForegroundColor Green

# ── Step 8: Django setup ──────────────────────────────────────────────────────
Write-Host "[8/8] Setting up Django..." -ForegroundColor Yellow

# Copy .env if missing
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "      Copied .env.example -> .env" -ForegroundColor Green
        Write-Host "      IMPORTANT: Edit .env and set EMBEDDING_ENCRYPTION_KEY" -ForegroundColor Yellow
    } else {
        Write-Host "      No .env found. Create one from .env.example." -ForegroundColor Yellow
    }
}

# Generate encryption key if not set
$envContent = Get-Content ".env" -Raw -ErrorAction SilentlyContinue
if ($envContent -notmatch "EMBEDDING_ENCRYPTION_KEY=.+") {
    Write-Host "      Generating EMBEDDING_ENCRYPTION_KEY..." -ForegroundColor Yellow
    python manage.py generate_key 2>&1 | Tee-Object -Variable keyOutput
    Write-Host "      $keyOutput" -ForegroundColor Green
}

# Run migrations
Write-Host "      Running migrations..." -ForegroundColor Yellow
python manage.py migrate

# Collect static files
Write-Host "      Collecting static files..." -ForegroundColor Yellow
python manage.py collectstatic --noinput --quiet

Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Create admin user:" -ForegroundColor Cyan
Write-Host "       python manage.py create_admin" -ForegroundColor White
Write-Host "  2. Start the server:" -ForegroundColor Cyan
Write-Host "       .\run.ps1" -ForegroundColor White
Write-Host "  3. Open in browser:  http://127.0.0.1:8000/" -ForegroundColor Cyan
Write-Host ""
Write-Host "  To run the system again later, just use:  .\run.ps1" -ForegroundColor Cyan
Write-Host ""
