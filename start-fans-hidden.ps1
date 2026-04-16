#Requires -Version 5.1
<#
.SYNOPSIS
    FANS-C Hidden Launcher — called by Windows Task Scheduler at startup.
    Starts Waitress and Caddy as background processes with NO visible windows.

.DESCRIPTION
    This script is designed to be invoked automatically by Task Scheduler
    every time the PC starts. The Head Barangay does not run it manually.

    What it does:
      1. Waits 12 seconds for Windows networking to fully initialize
      2. Starts Waitress (Django WSGI server) — no window
      3. Waits 5 seconds for Waitress to be ready
      4. Starts Caddy (HTTPS reverse proxy) — no window
      5. Writes a startup log to logs\fans-startup.log

    After this script exits, both services keep running in the background.
    The system is accessible at https://fans-barangay.local from any
    browser on the LAN.

    FOR DAILY USE:   Runs automatically. Do nothing.
    TO STOP:         Run stop-fans.ps1 (IT/Admin only).
    TO DEBUG ISSUES: Check logs\fans-startup.log first,
                     then use start-fans.bat (visible windows).
    TO SET UP:       Run setup-autostart.ps1 once (IT/Admin, as Admin).
#>

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
Set-Location $projectRoot

# -- Log helper ----------------------------------------------------------------
$logsDir = Join-Path $projectRoot 'logs'
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}
$logFile = Join-Path $logsDir 'fans-startup.log'

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    "$ts  $Message" | Add-Content -Path $logFile -Encoding UTF8
}

Write-Log '============================================================'
Write-Log 'FANS-C auto-start: beginning startup sequence'

# -- Wait for Windows networking to be fully available -------------------------
# Task Scheduler fires at startup before all network adapters are ready.
# A short delay prevents Caddy from failing to bind its interface.
Write-Log 'Waiting 12 seconds for Windows networking...'
Start-Sleep -Seconds 12

# -- Locate waitress-serve.exe -------------------------------------------------
$waitressExe = Join-Path $projectRoot '.venv\Scripts\waitress-serve.exe'
if (-not (Test-Path $waitressExe)) {
    Write-Log "FAIL: waitress-serve.exe not found at: $waitressExe"
    Write-Log '      Run setup-secure-server.ps1 to complete installation.'
    exit 1
}

# -- Check .env ----------------------------------------------------------------
$envFile = Join-Path $projectRoot '.env'
if (-not (Test-Path $envFile)) {
    Write-Log "FAIL: .env not found at: $envFile"
    Write-Log '      Ask IT to complete server configuration.'
    exit 1
}

# -- Locate caddy.exe ----------------------------------------------------------
$caddyExe = $null

# 1. Bundled in tools\ (handles both caddy.exe and caddy.exe.exe naming)
foreach ($candidate in @(
        (Join-Path $projectRoot 'tools\caddy.exe'),
        (Join-Path $projectRoot 'tools\caddy.exe.exe')
    )) {
    if (Test-Path $candidate) { $caddyExe = $candidate; break }
}

# 2. System PATH
if (-not $caddyExe) {
    try {
        $found = Get-Command caddy -ErrorAction Stop
        $caddyExe = $found.Source
    } catch { }
}

# 3. Legacy fallback
if (-not $caddyExe -and (Test-Path 'D:\Tools\caddy.exe')) {
    $caddyExe = 'D:\Tools\caddy.exe'
}

if (-not $caddyExe) {
    Write-Log 'FAIL: caddy.exe not found in tools\, PATH, or D:\Tools\'
    Write-Log '      Waitress will still start; HTTPS will NOT be available.'
    Write-Log '      Place caddy.exe in the project tools\ folder.'
}

# -- Warn if stable cert is missing --------------------------------------------
$stableCert = Join-Path $projectRoot 'fans-cert.pem'
if (-not (Test-Path $stableCert)) {
    Write-Log 'WARN: fans-cert.pem not found. Caddy may fail to start.'
    Write-Log '      Run setup-secure-server.ps1 to generate certificates.'
}

# -- Helper: start a process with NO console window ---------------------------
function Start-Hidden {
    param(
        [string]$Exe,
        [string]$Args,
        [string]$WorkDir
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName         = $Exe
    $psi.Arguments        = $Args
    $psi.WorkingDirectory = $WorkDir
    $psi.CreateNoWindow   = $true
    $psi.UseShellExecute  = $false
    return [System.Diagnostics.Process]::Start($psi)
}

# -- Start Waitress (no window) ------------------------------------------------
Write-Log "Starting Waitress: $waitressExe"
try {
    $procWaitress = Start-Hidden `
        -Exe     $waitressExe `
        -Args    '--listen=127.0.0.1:8000 fans.wsgi:application' `
        -WorkDir $projectRoot
    Write-Log "Waitress started (PID $($procWaitress.Id))"
    $procWaitress.Id | Set-Content (Join-Path $projectRoot '.fans-waitress.pid') -Encoding UTF8
} catch {
    Write-Log "FAIL: Could not start Waitress: $_"
    exit 1
}

# Wait for Waitress to initialize before Caddy starts accepting connections
Write-Log 'Waiting 5 seconds for Waitress to initialize...'
Start-Sleep -Seconds 5

# -- Start Caddy (no window) ---------------------------------------------------
if ($caddyExe) {
    Write-Log "Starting Caddy: $caddyExe"
    try {
        $procCaddy = Start-Hidden `
            -Exe     $caddyExe `
            -Args    'run --config Caddyfile' `
            -WorkDir $projectRoot
        Write-Log "Caddy started (PID $($procCaddy.Id))"
        $procCaddy.Id | Set-Content (Join-Path $projectRoot '.fans-caddy.pid') -Encoding UTF8
    } catch {
        Write-Log "FAIL: Could not start Caddy: $_"
        Write-Log '      Waitress is still running. Direct HTTP access works.'
        Write-Log '      HTTPS will NOT be available until Caddy is fixed.'
    }
} else {
    Write-Log 'SKIP: Caddy not found — skipping HTTPS proxy startup.'
}

Write-Log 'Startup sequence complete.'
Write-Log '============================================================'
