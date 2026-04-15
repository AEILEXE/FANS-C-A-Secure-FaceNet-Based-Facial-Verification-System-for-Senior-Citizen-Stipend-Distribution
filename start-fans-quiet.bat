@echo off
:: ============================================================
::  FANS-C Daily Launcher  (recommended for normal daily use)
::  ─────────────────────────────────────────────────────────
::  Starts the verification system with both services running
::  minimized in the background.  Only this window is visible
::  while starting up, then you can close it.
::
::  FOR DEBUGGING (full visible windows): use start-fans.bat
::
::  HOW TO USE:
::    Double-click this file — or use the desktop shortcut.
::    Keep the system running as long as staff need access.
::    To stop: close the two minimized taskbar windows.
::
::  FIRST-TIME SETUP:  Run setup-secure-server.ps1 first.
::  DESKTOP SHORTCUT:  Run Create-Desktop-Shortcut.ps1 once.
:: ============================================================

title FANS-C Verification System
mode con cols=68 lines=32

echo.
echo  ================================================================
echo   FANS-C  ^|  Barangay Senior Citizen Verification System
echo   Starting up...
echo  ================================================================
echo.

:: ── Pre-flight checks ─────────────────────────────────────────────

if not exist ".venv\Scripts\waitress-serve.exe" (
    echo.
    echo  ERROR: System setup is not complete.
    echo.
    echo  Please ask your IT administrator to run
    echo  setup-secure-server.ps1 before using this launcher.
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    echo.
    echo  ERROR: Configuration file is missing.
    echo.
    echo  Please ask your IT administrator to complete
    echo  the server configuration before starting.
    echo.
    pause
    exit /b 1
)

if not exist "Caddyfile" (
    echo.
    echo  ERROR: This launcher must be run from the FANS-C project folder.
    echo.
    echo  Please do not move this file to another location.
    echo  Use the desktop shortcut created by Create-Desktop-Shortcut.ps1.
    echo.
    pause
    exit /b 1
)

:: -- Migrate old mkcert cert filenames to the stable name (one-time) --------
:: setup-secure-server.ps1 now creates fans-cert.pem directly, but if the
:: server was set up with an older version we copy the first matching cert
:: we find so Caddy can always use the stable filename.
if not exist "fans-cert.pem" (
    for %%F in ("fans-barangay.local+*.pem") do (
        if not "%%~nxF"=="fans-cert.pem" (
            echo  NOTE: Migrating certificate to stable filename...
            copy "%%F" "fans-cert.pem" >nul
        )
    )
)
if not exist "fans-cert-key.pem" (
    for %%F in ("fans-barangay.local+*-key.pem") do (
        copy "%%F" "fans-cert-key.pem" >nul
    )
)

if not exist "fans-cert.pem" (
    echo  NOTE: HTTPS certificate not found.
    echo        The secure connection may not work correctly.
    echo        Contact your IT administrator to run setup-secure-server.ps1.
    echo.
)

echo  All checks passed.  Starting services...
echo.

:: ── Start Waitress minimized ──────────────────────────────────────

echo  [1/2] Starting application server...
start /MIN "FANS-C Waitress" cmd /k "cd /d %~dp0 && "%~dp0.venv\Scripts\waitress-serve.exe" --listen=127.0.0.1:8000 fans.wsgi:application"

:: Wait for Waitress to initialize before Caddy starts
timeout /t 4 /nobreak >nul

:: ── Start Caddy minimized ─────────────────────────────────────────

echo  [2/2] Starting HTTPS service...

:: Locate caddy.exe: bundled (tools\caddy.exe.exe) -> D:\Tools\caddy.exe -> PATH
set "CADDY_EXE="

if exist "%~dp0tools\caddy.exe.exe" (
    set "CADDY_EXE=%~dp0tools\caddy.exe.exe"
) else (
    if exist "D:\Tools\caddy.exe" (
        set "CADDY_EXE=D:\Tools\caddy.exe"
    ) else (
        where caddy >nul 2>&1
        if not errorlevel 1 (
            for /f "delims=" %%C in ('where caddy') do if not defined CADDY_EXE set "CADDY_EXE=%%C"
        )
    )
)

if not defined CADDY_EXE (
    echo.
    echo  ERROR: HTTPS service component (Caddy) could not be found.
    echo.
    echo  Please contact your IT administrator.
    echo  Caddy must be placed in the project's tools\ folder.
    echo.
    pause
    exit /b 1
)

start /MIN "FANS-C Caddy" cmd /k "cd /d %~dp0 && "%CADDY_EXE%" run --config Caddyfile"

:: ── Detect LAN IP ─────────────────────────────────────────────────

set "LAN_IP="
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /i "IPv4 Address"') do (
    if not defined LAN_IP (
        for /f "tokens=*" %%B in ("%%A") do set "LAN_IP=%%B"
    )
)

:: ── Status display ────────────────────────────────────────────────

echo.
echo  ================================================================
echo   FANS-C is running.  Staff can now open the system.
echo.
echo   OPEN THIS ADDRESS IN THE BROWSER:
echo     https://fans-barangay.local
echo     (Camera enabled -- full face verification)
echo.
echo   BACKUP ADDRESS (if browser shows a security warning):
if defined LAN_IP (
echo     http://%LAN_IP%:8000
echo     (Camera disabled -- for troubleshooting only)
) else (
echo     Not available -- connect this PC to the network first.
)
echo.
echo   Both services are running minimized in the taskbar.
echo   Do NOT close those taskbar windows while staff are using the system.
echo.
echo   TO SHUT DOWN:
echo     1. Close this window
echo     2. Close "FANS-C Waitress" in the taskbar
echo     3. Close "FANS-C Caddy" in the taskbar
echo  ================================================================
echo.
echo  You may close this window.  The system will keep running.
pause >nul
