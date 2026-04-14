@echo off
:: ============================================================
::  FANS-C Quiet Launcher  (daily operational use)
::  ──────────────────────────────────────────────
::  Starts Waitress and Caddy MINIMIZED to the taskbar.
::  Only this one window stays visible — shows status and URL.
::
::  For debugging (full visible windows): use start-fans.bat instead.
::
::  HOW TO USE:
::    Double-click this file from the project root folder.
::    Keep it running — close it only when you want to shut down.
::    To stop: press any key in this window (then manually close
::    the two minimized windows in the taskbar if still open).
::
::  REQUIREMENTS (already done during initial setup):
::    - .venv must exist           (run setup.ps1 or setup-secure-server.ps1)
::    - .env must be configured    (copy from .env.example, fill in values)
::    - Caddyfile must be present  (already in the project root)
::    - TLS certificates must exist
::    - caddy.exe must be reachable (PATH or D:\Tools\caddy.exe)
:: ============================================================

title FANS-C System
mode con cols=68 lines=30

echo.
echo  ================================================================
echo   FANS-C  ^|  FaceNet Facial Verification System
echo   Daily Startup  (Quiet Mode — servers run minimized)
echo  ================================================================
echo.

:: ── Pre-flight checks ─────────────────────────────────────────────

if not exist ".venv\Scripts\waitress-serve.exe" (
    echo  [FAIL] Virtual environment not found.
    echo.
    echo         Run setup-secure-server.ps1 or setup.ps1 first.
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    echo  [FAIL] .env file not found.
    echo.
    echo         Copy .env.example to .env and fill in your values.
    echo.
    pause
    exit /b 1
)

if not exist "Caddyfile" (
    echo  [FAIL] Caddyfile not found.
    echo.
    echo         Run this script from the project root folder.
    echo.
    pause
    exit /b 1
)

if not exist "fans-barangay.local+3.pem" (
    if not exist "fans-barangay.local+2.pem" (
        echo  [WARN] TLS certificate not found.
        echo         Run setup-secure-server.ps1 to generate it.
        echo         Caddy may fail to start.
        echo.
    )
)

echo  [OK]  Pre-flight checks passed.
echo.

:: ── Start Waitress minimized ──────────────────────────────────────

echo  [1/2] Starting Waitress (minimized)...
start /MIN "FANS-C Waitress" cmd /k "cd /d %~dp0 && "%~dp0.venv\Scripts\waitress-serve.exe" --listen=127.0.0.1:8000 fans.wsgi:application"

:: Wait for Waitress to initialize before Caddy starts
timeout /t 4 /nobreak >nul

:: ── Start Caddy minimized ─────────────────────────────────────────

echo  [2/2] Starting Caddy (minimized)...

:: Locate caddy.exe: bundled (tools\caddy.exe.exe) -> D:\Tools\caddy.exe -> PATH
set "CADDY_EXE="

if exist "%~dp0tools\caddy.exe.exe" (
    set "CADDY_EXE=%~dp0tools\caddy.exe.exe"
    echo  [OK]  Caddy found (bundled): %~dp0tools\caddy.exe.exe
) else (
    if exist "D:\Tools\caddy.exe" (
        set "CADDY_EXE=D:\Tools\caddy.exe"
        echo  [OK]  Caddy found (D:\Tools): D:\Tools\caddy.exe
    ) else (
        where caddy >nul 2>&1
        if not errorlevel 1 (
            for /f "delims=" %%C in ('where caddy') do if not defined CADDY_EXE set "CADDY_EXE=%%C"
            echo  [OK]  Caddy found on PATH: %CADDY_EXE%
        )
    )
)

if not defined CADDY_EXE (
    echo  [FAIL] caddy.exe not found.
    echo.
    echo         Checked:
    echo           - %~dp0tools\caddy.exe.exe  (bundled)
    echo           - D:\Tools\caddy.exe        (custom path)
    echo           - System PATH
    echo.
    echo         Place caddy.exe in the project's tools\ folder for automatic detection.
    echo         Download from: https://caddyserver.com/docs/install
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
echo   FANS-C is running.
echo.
echo   SECURE ACCESS (Recommended):
echo     https://fans-barangay.local
echo     Camera enabled - full features
echo.
echo   FALLBACK ACCESS (Camera disabled):
if defined LAN_IP (
echo     http://%LAN_IP%:8000
) else (
echo     (LAN IP not detected - connect server to the network)
)
echo.
echo   Waitress and Caddy are running minimized in the taskbar.
echo   DO NOT close those windows while the system is in use.
echo.
echo   To shut down completely:
echo     1. Close this window
echo     2. Close the minimized Waitress and Caddy taskbar windows
echo  ================================================================
echo.
echo  Press any key to close this launcher window.
echo  (Waitress and Caddy will continue running until you close them.)
pause >nul
