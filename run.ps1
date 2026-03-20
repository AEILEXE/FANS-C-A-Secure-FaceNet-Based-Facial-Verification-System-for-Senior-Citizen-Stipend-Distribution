# ============================================================
# FANS-C Run Script — PowerShell
# Use this every time you want to start the system.
# ============================================================
# HOW TO RUN (from the project root):
#   .\run.ps1
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  FANS-C — Starting Server" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check .venv exists
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "ERROR: .venv not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Activate venv
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".venv\Scripts\Activate.ps1"

# Check .env
if (-not (Test-Path ".env")) {
    Write-Host "WARNING: .env not found. Copy .env.example to .env and configure it." -ForegroundColor Yellow
}

# Apply any pending migrations
Write-Host "Checking for pending migrations..." -ForegroundColor Yellow
python manage.py migrate --run-syncdb 2>&1 | Out-Null
Write-Host "Done." -ForegroundColor Green

Write-Host ""
Write-Host "Starting Django development server..." -ForegroundColor Green
Write-Host "Open your browser at:  http://127.0.0.1:8000/" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Yellow
Write-Host ""

python manage.py runserver
