#Requires -Version 5.1
<#
.SYNOPSIS
    FANS-C Production Startup Script.
    Starts Waitress (Django) and Caddy (HTTPS) as separate visible processes.

.DESCRIPTION
    Use this script to bring the FANS-C system online after a server reboot,
    without opening VS Code or typing commands manually.

    This script:
      - Runs pre-flight checks (.venv, .env, certificates, encryption key)
      - Starts Waitress in a new PowerShell window (Django WSGI server)
      - Waits for Waitress to initialize
      - Starts Caddy in a new PowerShell window (HTTPS reverse proxy)

    Requirements:
      - setup.ps1 must have been run at least once on this machine
      - caddy.exe must be on the system PATH (or in this folder)
      - mkcert TLS certificates must exist in the project root
      - .env must be configured for production (DEBUG=False, etc.)

.NOTES
    Run this from the project root folder: D:\FANS\fans-c\
    Do not run as a different working directory — Caddy resolves cert
    paths relative to its working directory.

.EXAMPLE
    .\start-fans-production.ps1

    To allow this script to run if execution policy blocks it:
    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
Set-Location $projectRoot

$venvWaitress = Join-Path $projectRoot '.venv\Scripts\waitress-serve.exe'
$envFile      = Join-Path $projectRoot '.env'
$caddyFile    = Join-Path $projectRoot 'Caddyfile'
$certFile     = Join-Path $projectRoot 'fans-barangay.local+3.pem'

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor DarkCyan
Write-Host "   FANS-C  |  FaceNet Facial Verification System                 " -ForegroundColor Cyan
Write-Host "   Starting Production Server (Waitress + Caddy)...              " -ForegroundColor Cyan
Write-Host "  ================================================================" -ForegroundColor DarkCyan
Write-Host ""

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
$passed = $true

# 1. .venv / waitress
if (-not (Test-Path $venvWaitress)) {
    Write-Host "  [FAIL] waitress-serve.exe not found at:" -ForegroundColor Red
    Write-Host "         $venvWaitress" -ForegroundColor Red
    Write-Host "         Run .\setup.ps1 first to set up the virtual environment." -ForegroundColor Yellow
    $passed = $false
}

# 2. .env
if (-not (Test-Path $envFile)) {
    Write-Host "  [FAIL] .env not found." -ForegroundColor Red
    Write-Host "         Copy .env.example to .env and run .\setup.ps1." -ForegroundColor Yellow
    $passed = $false
}

if (-not $passed) {
    Write-Host ""
    Write-Host "  Setup is incomplete. Resolve the issues above, then retry." -ForegroundColor Yellow
    Read-Host "  Press Enter to exit"
    exit 1
}

# Read .env for additional checks
$envRaw = Get-Content $envFile -Raw -Encoding UTF8

# 3. EMBEDDING_ENCRYPTION_KEY
if ($envRaw -match '(?m)^EMBEDDING_ENCRYPTION_KEY\s*=\s*$') {
    Write-Host "  [FAIL] EMBEDDING_ENCRYPTION_KEY is empty in .env" -ForegroundColor Red
    Write-Host "         Without this key, face embeddings cannot be decrypted." -ForegroundColor Yellow
    Write-Host "         Run: .\.venv\Scripts\python.exe manage.py generate_key" -ForegroundColor Cyan
    Write-Host "         Then paste the output into .env" -ForegroundColor Yellow
    Read-Host "  Press Enter to exit"
    exit 1
}

# 4. Caddyfile
if (-not (Test-Path $caddyFile)) {
    Write-Host "  [FAIL] Caddyfile not found in project root." -ForegroundColor Red
    Write-Host "         Cannot start Caddy without it." -ForegroundColor Yellow
    Read-Host "  Press Enter to exit"
    exit 1
}

# 5. TLS certificate (warning only — Caddy will produce its own error)
if (-not (Test-Path $certFile)) {
    Write-Host "  [WARN] TLS certificate not found: fans-barangay.local+3.pem" -ForegroundColor Yellow
    Write-Host "         Caddy may fail to start." -ForegroundColor Yellow
    Write-Host "         See SETUP.md — 'Production Deployment (Waitress + Caddy)'" -ForegroundColor Yellow
    Write-Host "         Continuing anyway..." -ForegroundColor DarkGray
    Write-Host ""
}

# 6. Check caddy is available
try {
    $null = Get-Command caddy -ErrorAction Stop
} catch {
    Write-Host "  [FAIL] 'caddy' command not found on PATH." -ForegroundColor Red
    Write-Host "         Download caddy.exe and add it to your PATH, or place it" -ForegroundColor Yellow
    Write-Host "         in the project root folder ($projectRoot)." -ForegroundColor Yellow
    Read-Host "  Press Enter to exit"
    exit 1
}

Write-Host "  [OK]  All pre-flight checks passed." -ForegroundColor Green
Write-Host ""

# ---------------------------------------------------------------------------
# Start Waitress in a new PowerShell window
# ---------------------------------------------------------------------------
Write-Host "  [1/2] Starting Waitress (Django WSGI server)..." -ForegroundColor Cyan

$waitressCmd = @"
`$host.UI.RawUI.WindowTitle = 'FANS-C Waitress'
Write-Host ''
Write-Host '  ================================================================' -ForegroundColor DarkCyan
Write-Host '   FANS-C Waitress -- Django App Server                          ' -ForegroundColor Cyan
Write-Host '   DO NOT CLOSE THIS WINDOW while the system is in use.          ' -ForegroundColor Yellow
Write-Host '  ================================================================' -ForegroundColor DarkCyan
Write-Host ''
Set-Location '$projectRoot'
& '$venvWaitress' --listen=127.0.0.1:8000 fans.wsgi:application
Write-Host ''
Write-Host '  Waitress has stopped. Press Enter to close.' -ForegroundColor Red
Read-Host
"@

Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $waitressCmd

# Give Waitress time to initialize before starting Caddy
Write-Host "  [..] Waiting 5 seconds for Waitress to initialize..." -ForegroundColor DarkGray
Start-Sleep -Seconds 5

# ---------------------------------------------------------------------------
# Start Caddy in a new PowerShell window
# ---------------------------------------------------------------------------
Write-Host "  [2/2] Starting Caddy (HTTPS reverse proxy)..." -ForegroundColor Cyan

$caddyCmd = @"
`$host.UI.RawUI.WindowTitle = 'FANS-C Caddy'
Write-Host ''
Write-Host '  ================================================================' -ForegroundColor DarkCyan
Write-Host '   FANS-C Caddy -- HTTPS Reverse Proxy                           ' -ForegroundColor Cyan
Write-Host '   DO NOT CLOSE THIS WINDOW while the system is in use.          ' -ForegroundColor Yellow
Write-Host '  ================================================================' -ForegroundColor DarkCyan
Write-Host ''
Set-Location '$projectRoot'
caddy run --config Caddyfile
Write-Host ''
Write-Host '  Caddy has stopped. Press Enter to close.' -ForegroundColor Red
Read-Host
"@

Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $caddyCmd

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor DarkCyan
Write-Host "   Both servers are starting in their own windows.               " -ForegroundColor Green
Write-Host ""
Write-Host "   System URL  : https://fans-barangay.local                     " -ForegroundColor Cyan
Write-Host "   Staff access: Any browser on the same Wi-Fi or LAN network    " -ForegroundColor Cyan
Write-Host ""
Write-Host "   Internet is NOT required for normal operation.                 " -ForegroundColor Yellow
Write-Host "   The system runs entirely on your local network.                " -ForegroundColor Yellow
Write-Host ""
Write-Host "   To stop: Close both the Waitress and Caddy windows.            " -ForegroundColor DarkGray
Write-Host "  ================================================================" -ForegroundColor DarkCyan
Write-Host ""
Read-Host "  Press Enter to close this launcher window"
