@echo off
:: ============================================================
::  FANS-C Debug Launcher  (verbose mode — for IT/admin use)
::  ─────────────────────────────────────────────────────────
::  Opens BOTH server windows VISIBLY so you can see all output.
::  Use this when troubleshooting startup or configuration issues.
::
::  FOR NORMAL DAILY USE: use start-fans-quiet.bat instead.
::  FOR DESKTOP SHORTCUT: run Create-Desktop-Shortcut.ps1 once.
::
::  What it does:
::    1. Opens a visible window for Waitress (Django app server)
::    2. Opens a visible window for Caddy (HTTPS reverse proxy)
::
::  To stop the system:
::    - Close the two server windows that this script opens.
::
::  NOTE: This script lives in scripts\start\ and computes the
::        project root automatically. Do not move without updating paths.
:: ============================================================

title FANS-C Debug Launcher

:: ----------------------------------------------------------
:: Compute project root (two levels up: scripts\start\ -> root)
:: ----------------------------------------------------------
pushd "%~dp0..\.."
set "PROJECT_ROOT=%CD%"
popd
cd /d "%PROJECT_ROOT%"

echo.
echo  ================================================================
echo   FANS-C  ^|  Barangay Senior Citizen Verification System
echo   Debug Launcher  (verbose mode — IT/admin use)
echo  ================================================================
echo.

:: ----------------------------------------------------------
:: Pre-flight checks
:: ----------------------------------------------------------
if not exist "%PROJECT_ROOT%\.venv\Scripts\waitress-serve.exe" (
    echo  [FAIL] .venv\Scripts\waitress-serve.exe not found.
    echo.
    echo         Make sure you have already run:
    echo           scripts\setup\setup-secure-server.ps1
    echo.
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%\Caddyfile" (
    echo  [FAIL] Caddyfile not found in project root.
    echo.
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%\.env" (
    echo  [FAIL] .env file not found.
    echo.
    echo         Copy .env.example to .env and fill in your values,
    echo         then re-run scripts\setup\setup-secure-server.ps1.
    echo.
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%\fans-cert.pem" (
    echo  [WARN] TLS certificate not found: fans-cert.pem
    echo.
    echo         Caddy may fail to start.
    echo         Run scripts\setup\setup-secure-server.ps1 to generate certificates.
    echo.
)

echo  [OK]  Pre-flight checks passed.
echo.

:: ----------------------------------------------------------
:: Stop any stale instances before starting (prevents conflicts)
:: ----------------------------------------------------------
echo  [..] Stopping any stale Waitress or Caddy instances...
taskkill /F /IM waitress-serve.exe /T >nul 2>&1
taskkill /F /IM caddy.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul

:: ----------------------------------------------------------
:: Start Waitress (Django app server) in a new window
:: ----------------------------------------------------------
echo  [1/2] Starting Waitress (Django WSGI server)...
echo        This serves the FANS-C application on 127.0.0.1:8000
echo.
start "FANS-C Waitress" "%PROJECT_ROOT%\.venv\Scripts\waitress-serve.exe" --listen=127.0.0.1:8000 fans.wsgi:application

:: Wait a few seconds for Waitress to initialize before Caddy starts
echo  [..] Waiting 4 seconds for Waitress to initialize...
timeout /t 4 /nobreak >nul

:: ----------------------------------------------------------
:: Locate and start Caddy (HTTPS reverse proxy)
:: ----------------------------------------------------------
echo  [2/2] Starting Caddy (HTTPS reverse proxy)...
echo        This handles HTTPS on port 443 and forwards to Waitress.
echo.

:: Locate caddy.exe: tools\caddy.exe -> D:\Tools\caddy.exe -> PATH
set "CADDY_EXE="
if exist "%PROJECT_ROOT%\tools\caddy.exe" set "CADDY_EXE=%PROJECT_ROOT%\tools\caddy.exe"
if not defined CADDY_EXE if exist "D:\Tools\caddy.exe" set "CADDY_EXE=D:\Tools\caddy.exe"
if not defined CADDY_EXE (
    where caddy >nul 2>&1
    if not errorlevel 1 for /f "delims=" %%C in ('where caddy') do if not defined CADDY_EXE set "CADDY_EXE=%%C"
)
if defined CADDY_EXE echo  [OK]  Caddy found: "%CADDY_EXE%"

if not defined CADDY_EXE (
    echo  [FAIL] caddy.exe not found.
    echo.
    echo         Checked:
    echo           - %PROJECT_ROOT%\tools\caddy.exe
    echo           - D:\Tools\caddy.exe
    echo           - System PATH
    echo.
    echo         Place caddy.exe in the project's tools\ folder for automatic detection.
    echo         Download from: https://caddyserver.com/docs/install
    echo.
    pause
    exit /b 1
)

start "FANS-C Caddy" "%CADDY_EXE%" run --config "%PROJECT_ROOT%\Caddyfile"

:: ----------------------------------------------------------
:: Detect LAN IP (for staff connection guidance)
:: ----------------------------------------------------------
set "LAN_IP="
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /i "IPv4 Address"') do (
    if not defined LAN_IP (
        for /f "tokens=*" %%B in ("%%A") do set "LAN_IP=%%B"
    )
)

:: ----------------------------------------------------------
:: Done
:: ----------------------------------------------------------
echo.
echo  ================================================================
echo   Both servers are starting in their own windows.
echo.
echo   SECURE ACCESS (Recommended):
echo     https://fans-barangay.local
echo     Camera enabled - full features - requires hosts file setup
echo.
echo   FALLBACK ACCESS (No setup needed):
if defined LAN_IP (
echo     http://%LAN_IP%:8000
echo     Works immediately - no hosts file - camera disabled
) else (
echo     LAN IP not detected -- connect server to the network
)
echo.
echo   Server only (this device): http://127.0.0.1:8000
echo.
if defined LAN_IP (
echo   TIP: Give staff the FALLBACK URL to connect right away.
echo        Switch to SECURE ACCESS once hosts file is set up.
) else (
echo   TIP: Connect this server to the network, then restart to
echo        get the Fallback URL for staff devices.
)
echo.
echo   - Keep both server windows open while the system is in use.
echo   - Close both windows to shut down the system.
echo   - Connection help: https://fans-barangay.local/help/connect/
echo  ================================================================
echo.
echo  Press any key to close this startup window.
echo  (The two server windows will keep running.)
pause >nul
