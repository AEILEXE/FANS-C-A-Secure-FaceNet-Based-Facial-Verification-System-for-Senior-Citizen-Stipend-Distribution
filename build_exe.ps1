#Requires -Version 5.1
<#
.SYNOPSIS
    Build the FANS-C Windows desktop application (.exe + dist folder).

.DESCRIPTION
    This script automates the full PyInstaller packaging process:

      1. Verifies Python 3.11 and the project .venv are present.
      2. Installs packaging-only dependencies (PyInstaller, waitress).
      3. Runs `collectstatic` to ensure staticfiles/ is up to date.
      4. Runs `pyinstaller fans_c.spec` to produce dist/FANS-C/.
      5. Copies post-build assets (.env.example, SETUP.md) into dist/FANS-C/
         so the distribution folder is self-contained for a new user.
      6. Prints a summary of the build output.

    After this script succeeds, run the Inno Setup compiler on
    installer/fans_c.iss to produce the final Windows installer
    (FANS-C-Setup.exe).

.NOTES
    Prerequisites
    -------------
    * Python 3.11 must be installed and accessible via `py -3.11`.
    * The project .venv must exist (run .\setup.ps1 first if it does not).
    * PyInstaller and waitress are installed into .venv by this script.
    * UPX (optional)  --  if present in PATH, it will compress binaries slightly.
      Download from https://upx.github.io/.  Not required.

    Why waitress?
    -------------
    waitress is a pure-Python threaded WSGI server that works reliably
    inside a PyInstaller bundle.  Django's development server (runserver)
    uses multiprocessing internally for its autoreloader, which cannot be
    safely frozen.  waitress replaces it for the packaged build only.
    Django itself remains unchanged.

    Expected output
    ---------------
    dist\FANS-C\            --  the packaged application directory
    dist\FANS-C\FANS-C.exe  --  the launcher executable
    dist\FANS-C\.env.example  --  user copies this to .env before first launch
    dist\FANS-C\SETUP.md    --  first-run setup instructions for the target machine

.EXAMPLE
    .\build_exe.ps1
    .\build_exe.ps1 -SkipCollectStatic
    .\build_exe.ps1 -Clean
#>

param(
    # Skip `collectstatic` (faster rebuild when templates/static haven't changed)
    [switch]$SkipCollectStatic,

    # Delete dist/ and build/ before building (full clean build)
    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot  = $PSScriptRoot
$venvPython   = Join-Path $projectRoot '.venv\Scripts\python.exe'
$venvPip      = Join-Path $projectRoot '.venv\Scripts\pip.exe'
$specFile     = Join-Path $projectRoot 'fans_c.spec'
$distDir      = Join-Path $projectRoot 'dist\FANS-C'

Set-Location $projectRoot

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor DarkCyan
Write-Host "   FANS-C  |  Windows Build Script  |  PyInstaller packaging      " -ForegroundColor Cyan
Write-Host "  ================================================================" -ForegroundColor DarkCyan
Write-Host ""

# ---------------------------------------------------------------------------
# Step 0  --  Prerequisites
# ---------------------------------------------------------------------------
Write-Host "  [1/6] Checking prerequisites ..." -ForegroundColor DarkGray

# Require .venv
if (-not (Test-Path $venvPython)) {
    Write-Host "  [FAIL] .venv not found at $venvPython" -ForegroundColor Red
    Write-Host "         Run .\setup.ps1 first to create the virtual environment." -ForegroundColor Yellow
    exit 1
}

# Require fans_c.spec
if (-not (Test-Path $specFile)) {
    Write-Host "  [FAIL] fans_c.spec not found at $specFile" -ForegroundColor Red
    exit 1
}

# Verify Python version is 3.11.x
$pyVersion = & $venvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
if ($pyVersion -ne '3.11') {
    Write-Host "  [FAIL] .venv Python is $pyVersion  --  FANS-C requires Python 3.11." -ForegroundColor Red
    Write-Host "         TensorFlow 2.13 does not support Python 3.12 or later." -ForegroundColor Yellow
    exit 1
}

Write-Host "  [OK]  Python $pyVersion in .venv" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 1  --  Optional clean
# ---------------------------------------------------------------------------
if ($Clean) {
    Write-Host "  [..] Cleaning previous build artefacts ..." -ForegroundColor DarkGray
    $toRemove = @('dist', 'build')
    foreach ($d in $toRemove) {
        $path = Join-Path $projectRoot $d
        if (Test-Path $path) {
            Remove-Item -Recurse -Force $path
            Write-Host "       Removed $path" -ForegroundColor DarkGray
        }
    }
    Write-Host "  [OK]  Clean complete." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Step 2  --  Install packaging dependencies
# ---------------------------------------------------------------------------
Write-Host "  [2/6] Installing packaging dependencies ..." -ForegroundColor DarkGray

# PyInstaller  --  produces the .exe and dist/ folder
# Pin to a known-good version compatible with Python 3.11 + TF 2.13
& $venvPip install --quiet "pyinstaller>=6.3,<7.0" 2>&1 | ForEach-Object { Write-Host "       $_" -ForegroundColor DarkGray }
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [FAIL] Failed to install PyInstaller." -ForegroundColor Red
    exit 1
}

# waitress  --  the WSGI server used by launcher.py in packaged mode.
# Pure Python, no compiled extensions -> reliable inside PyInstaller.
& $venvPip install --quiet "waitress>=3.0,<4.0" 2>&1 | ForEach-Object { Write-Host "       $_" -ForegroundColor DarkGray }
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [FAIL] Failed to install waitress." -ForegroundColor Red
    exit 1
}

Write-Host "  [OK]  PyInstaller and waitress ready." -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 3  --  collectstatic
# ---------------------------------------------------------------------------
# whitenoise (DEBUG=False) serves from staticfiles/ using hashed filenames.
# The bundle must include the collected files, not just the source static/.
# If staticfiles/ is empty or stale, CSS/JS will 404 in the packaged app.
#
# WHY THE SPECIAL stderr HANDLING BELOW:
# When Python writes to stderr (e.g. Django's RuntimeWarning about SECRET_KEY
# being the placeholder value), PowerShell wraps each stderr line in an
# ErrorRecord object.  Under $ErrorActionPreference = 'Stop' those objects are
# promoted to terminating errors inside ForEach-Object, crashing the script
# even when collectstatic itself succeeded (exit code 0).
#
# Fix: lower ErrorActionPreference to 'Continue' only for this call, then
# type-check every pipeline object.  ErrorRecord items are Django warnings --
# display them in yellow.  Plain strings are normal Django output -- display
# them in gray.  Real failures are still caught via $LASTEXITCODE after the
# pipeline completes.  ErrorActionPreference is always restored afterwards.

if (-not $SkipCollectStatic) {
    Write-Host "  [3/6] Running collectstatic ..." -ForegroundColor DarkGray

    # Save and lower ErrorActionPreference so stderr lines from Python do not
    # become terminating errors in the pipeline.
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'

    # Collect warning lines so we can report a count in the summary.
    $csWarnings = [System.Collections.Generic.List[string]]::new()

    & $venvPython manage.py collectstatic --noinput --clear 2>&1 |
        ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) {
                # Stderr from Python -- typically Django startup RuntimeWarnings
                # (e.g. SECRET_KEY placeholder, missing .env).  Not a crash.
                $csWarnings.Add($_.ToString())
                Write-Host "       [warn] $_" -ForegroundColor Yellow
            } else {
                # Normal stdout from collectstatic (file counts, paths copied)
                Write-Host "       $_" -ForegroundColor DarkGray
            }
        }

    # Capture exit code before restoring ErrorActionPreference.
    $csExit = $LASTEXITCODE

    # Always restore -- even if something throws unexpectedly above.
    $ErrorActionPreference = $prevEAP

    if ($csExit -ne 0) {
        # Non-zero exit = real failure (missing app, broken template, bad
        # INSTALLED_APPS, etc.).  Stop the build so the user sees it clearly.
        Write-Host "  [FAIL] collectstatic failed (exit code $csExit)." -ForegroundColor Red
        Write-Host "         Check the output above for errors, then re-run build_exe.ps1." -ForegroundColor Yellow
        exit 1
    }

    if ($csWarnings.Count -gt 0) {
        Write-Host "  [OK]  staticfiles/ up to date ($($csWarnings.Count) warning(s) shown above)." -ForegroundColor Green
        Write-Host "        Warnings during collectstatic are usually non-fatal." -ForegroundColor DarkGray
        Write-Host "        The SECRET_KEY warning is expected when .env uses the placeholder value." -ForegroundColor DarkGray
    } else {
        Write-Host "  [OK]  staticfiles/ up to date." -ForegroundColor Green
    }
} else {
    Write-Host "  [3/6] Skipping collectstatic (-SkipCollectStatic)." -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# Step 4  --  PyInstaller
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  [4/6] Running PyInstaller (this will take several minutes) ..." -ForegroundColor DarkGray
Write-Host "        TensorFlow has thousands of files  --  the first build is slow." -ForegroundColor DarkGray
Write-Host "        Subsequent builds use the cache and are much faster." -ForegroundColor DarkGray
Write-Host ""

# Run PyInstaller using the .venv Python so it picks up the .venv packages
& $venvPython -m PyInstaller fans_c.spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  [FAIL] PyInstaller build failed (exit code $LASTEXITCODE)." -ForegroundColor Red
    Write-Host "         Common causes:" -ForegroundColor Yellow
    Write-Host "           * ImportError for a package  --  add it to hiddenimports in fans_c.spec" -ForegroundColor Yellow
    Write-Host "           * Missing data file  --  add it to the datas list in fans_c.spec" -ForegroundColor Yellow
    Write-Host "           * TensorFlow DLL load error  --  ensure Python 3.11 is in use" -ForegroundColor Yellow
    Write-Host "           * Long path issue  --  move project to D:\FANS or shorter path" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "  [OK]  PyInstaller build succeeded." -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 5  --  Post-build: copy distribution assets
# ---------------------------------------------------------------------------
Write-Host "  [5/6] Copying distribution assets into dist\FANS-C\ ..." -ForegroundColor DarkGray

# .env.example  --  user creates .env from this on the target machine
$envExample = Join-Path $projectRoot '.env.example'
if (Test-Path $envExample) {
    Copy-Item $envExample -Destination $distDir -Force
    Write-Host "       Copied .env.example" -ForegroundColor DarkGray
}

# SETUP.md  --  first-run instructions for the person who installs the app
$setupMd = Join-Path $projectRoot 'SETUP.md'
if (Test-Path $setupMd) {
    Copy-Item $setupMd -Destination $distDir -Force
    Write-Host "       Copied SETUP.md" -ForegroundColor DarkGray
}

# Icon  --  included for the installer script if present
$ico = Join-Path $projectRoot 'fans_c.ico'
if (Test-Path $ico) {
    Copy-Item $ico -Destination $distDir -Force
    Write-Host "       Copied fans_c.ico" -ForegroundColor DarkGray
}

Write-Host "  [OK]  Assets copied." -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 6  --  Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  [6/6] Build complete." -ForegroundColor Green
Write-Host ""

if (Test-Path $distDir) {
    $sizeBytes = (Get-ChildItem $distDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
    $sizeMB = [math]::Round($sizeBytes / 1MB, 1)
    $fileCount = (Get-ChildItem $distDir -Recurse -File).Count
    Write-Host "  Output folder : $distDir" -ForegroundColor Cyan
    Write-Host "  Total size    : $sizeMB MB ($fileCount files)" -ForegroundColor Cyan
} else {
    Write-Host "  WARNING: dist\FANS-C\ not found after build." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  -- Next steps -------------------------------------------------" -ForegroundColor DarkCyan
Write-Host "  1. Test the build locally:" -ForegroundColor White
Write-Host "       Copy dist\FANS-C\.env.example to dist\FANS-C\.env" -ForegroundColor DarkGray
Write-Host "       Edit dist\FANS-C\.env (add EMBEDDING_ENCRYPTION_KEY + SECRET_KEY)" -ForegroundColor DarkGray
Write-Host "       Run dist\FANS-C\FANS-C.exe" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  2. Build the installer:" -ForegroundColor White
Write-Host "       Open installer\fans_c.iss in Inno Setup Compiler" -ForegroundColor DarkGray
Write-Host "       Click Build -> Compile (or press F9)" -ForegroundColor DarkGray
Write-Host "       The installer will be created as installer\Output\FANS-C-Setup.exe" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  3. Distribute:" -ForegroundColor White
Write-Host "       Share FANS-C-Setup.exe with the target machine." -ForegroundColor DarkGray
Write-Host "       The user installs it, then creates .env before first launch." -ForegroundColor DarkGray
Write-Host ""
Write-Host "  -- Packaging notes --------------------------------------------" -ForegroundColor DarkCyan
Write-Host "  * .env is NOT included in the build  --  it contains secrets." -ForegroundColor Yellow
Write-Host "  * db.sqlite3 is NOT included  --  created fresh on first launch." -ForegroundColor Yellow
Write-Host "  * FaceNet weights download to ~/.keras on first import (~90 MB)." -ForegroundColor Yellow
Write-Host "  * See README.md section 'Windows .exe Packaging' for full documentation." -ForegroundColor Yellow
Write-Host ""
