#Requires -Version 5.1
<#
.SYNOPSIS
    FANS-C -- Create or add a Django admin (superuser) account.
    Safe to run any time: checks if one already exists first.

.DESCRIPTION
    Checks how many superuser accounts currently exist, then optionally
    creates a new one. Will not silently overwrite or delete existing accounts.

    Use this when:
      - Setting up the first admin account on a fresh install
      - Adding an additional admin account (e.g. for a second IT/Admin)
      - The admin password needs to be reset (use Django admin panel instead
        for password resets -- this creates a NEW account)

    Does NOT require Administrator rights.
    Requires the .venv virtual environment to be set up first.

.EXAMPLE
    .\scripts\admin\create-admin-user.ps1
#>

$ErrorActionPreference = 'Continue'
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $projectRoot

$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

Write-Host ''
Write-Host '  ================================================================' -ForegroundColor DarkCyan
Write-Host '   FANS-C  |  Create / Add Admin User' -ForegroundColor Cyan
Write-Host '  ================================================================' -ForegroundColor DarkCyan
Write-Host ''

if (-not (Test-Path $venvPython)) {
    Write-Host '  [FAIL] .venv not found.' -ForegroundColor Red
    Write-Host "         Expected: $venvPython" -ForegroundColor Yellow
    Write-Host '         Run setup-complete.ps1 first to set up the virtual environment.' -ForegroundColor Yellow
    Write-Host ''
    Read-Host '  Press Enter to exit'
    exit 1
}

# -- Check existing superusers -------------------------------------------------
Write-Host '  Checking existing admin accounts...' -ForegroundColor DarkGray

$suCheckRaw = & $venvPython manage.py shell --no-color -c `
    "from django.contrib.auth import get_user_model; U=get_user_model(); print(U.objects.filter(is_superuser=True).count())" `
    2>&1
$suCheckStr = (($suCheckRaw | Where-Object { $_ -match '^\d+$' }) -join '').Trim()

if ($suCheckStr -match '^\d+$') {
    $suCount = [int]$suCheckStr
    if ($suCount -gt 0) {
        Write-Host "  [OK]  $suCount admin account(s) already exist." -ForegroundColor Green
        Write-Host ''
        $createMore = Read-Host '  Create an additional admin account? [Y/N]'
        if ($createMore -notmatch '^[Yy]') {
            Write-Host ''
            Write-Host '  No changes made.' -ForegroundColor DarkGray
            Write-Host '  To reset a password: log in at https://fans-barangay.local/admin' -ForegroundColor DarkGray
            Write-Host ''
            Read-Host '  Press Enter to close'
            exit 0
        }
    } else {
        Write-Host '  [INFO] No admin accounts found. Proceeding to create first admin...' -ForegroundColor Yellow
    }
} else {
    Write-Host '  [WARN] Could not check existing admin count. Proceeding anyway.' -ForegroundColor Yellow
}

# -- Create superuser ----------------------------------------------------------
Write-Host ''
Write-Host '  Django will now prompt for username, email, and password.' -ForegroundColor White
Write-Host '  Choose a strong password and store it securely.' -ForegroundColor White
Write-Host ''

& $venvPython manage.py createsuperuser
$exitCode = $LASTEXITCODE

Write-Host ''
if ($exitCode -eq 0) {
    Write-Host '  [OK]  Admin user created successfully.' -ForegroundColor Green
    Write-Host '        Log in at: https://fans-barangay.local/admin' -ForegroundColor Cyan
} else {
    Write-Host "  [WARN] createsuperuser exited with code $exitCode." -ForegroundColor Yellow
    Write-Host '         The account may not have been created. Try again.' -ForegroundColor DarkGray
}

Write-Host ''
Write-Host '  ================================================================' -ForegroundColor DarkCyan
Write-Host ''
Read-Host '  Press Enter to close'
