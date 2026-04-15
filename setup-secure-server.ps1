#Requires -Version 5.1
<#
.SYNOPSIS
    FANS-C One-Time Secure Server Setup.
    Run this ONCE on the server machine before first use.

.DESCRIPTION
    This script performs the complete one-time setup needed to run FANS-C
    over HTTPS on the barangay LAN. It is safe to re-run if something
    needs to be fixed.

    What it does (in order):
      1.  Checks for Administrator rights
      2.  Finds mkcert.exe (in tools\mkcert\ or on PATH)
      3.  Installs the mkcert local CA into the Windows trust store
      4.  Detects the server LAN IP automatically
      5.  Generates TLS certificates for:
             fans-barangay.local  <LAN-IP>  localhost  127.0.0.1
      6.  Places certificate files in the project root (where Caddy expects them)
      7.  Verifies that .env exists and EMBEDDING_ENCRYPTION_KEY is set
      8.  Runs Django database migrations
      9.  Runs collectstatic
     10.  Adds a Windows Firewall rule for HTTPS (port 443) if missing
     11.  Optionally starts Waitress + Caddy
     12.  Optionally opens the browser

    What still requires manual steps:
      - Editing .env for your site's actual ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS
      - Installing the mkcert root CA on client devices (use trust-local-cert.ps1)
      - Adding fans-barangay.local to each client's hosts file

.NOTES
    Run from the project root as Administrator:
      Right-click setup-secure-server.ps1 -> Run with PowerShell (as Admin)
      -- or --
      Start-Process powershell -Verb RunAs -ArgumentList "-File .\setup-secure-server.ps1"

.EXAMPLE
    .\setup-secure-server.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
Set-Location $projectRoot

# -- Paths --------------------------------------------------------------------
$venvPython   = Join-Path $projectRoot '.venv\Scripts\python.exe'
$venvWaitress = Join-Path $projectRoot '.venv\Scripts\waitress-serve.exe'
$envFile      = Join-Path $projectRoot '.env'
$caddyFile    = Join-Path $projectRoot 'Caddyfile'
# mkcert bundled with the project (tools\mkcert\mkcert.exe.exe)
$mkcertBundled = Join-Path $projectRoot 'tools\mkcert\mkcert.exe.exe'
# Caddy bundled with the project (tools\caddy.exe.exe)
$caddyBundled  = Join-Path $projectRoot 'tools\caddy.exe.exe'

# -- Banner -------------------------------------------------------------------
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor DarkCyan
Write-Host "   FANS-C  |  One-Time Secure Server Setup                       " -ForegroundColor Cyan
Write-Host "  ================================================================" -ForegroundColor DarkCyan
Write-Host ""

# -- Step 1: Administrator check ----------------------------------------------
Write-Host "  [1/10] Checking Administrator rights..." -ForegroundColor Cyan
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host ""
    Write-Host "  [FAIL] This script must be run as Administrator." -ForegroundColor Red
    Write-Host "         Right-click the script and choose 'Run with PowerShell'," -ForegroundColor Yellow
    Write-Host "         then approve the UAC prompt." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}
Write-Host "         Administrator rights confirmed." -ForegroundColor Green

# -- Step 2: Find mkcert ------------------------------------------------------
Write-Host "  [2/10] Locating mkcert.exe..." -ForegroundColor Cyan
$mkcertExe = $null

if (Test-Path $mkcertBundled) {
    $mkcertExe = $mkcertBundled
    Write-Host "         Found (bundled): $mkcertExe" -ForegroundColor Green
} else {
    # Try PATH
    try {
        $found = Get-Command mkcert -ErrorAction Stop
        $mkcertExe = $found.Source
        Write-Host "         Found on PATH: $mkcertExe" -ForegroundColor Green
    } catch {
        Write-Host ""
        Write-Host "  [FAIL] mkcert.exe not found." -ForegroundColor Red
        Write-Host "         Expected location: $mkcertBundled" -ForegroundColor Yellow
        Write-Host "         Or place mkcert.exe anywhere on your system PATH." -ForegroundColor Yellow
        Write-Host "         Download from: https://github.com/FiloSottile/mkcert/releases" -ForegroundColor Cyan
        Write-Host ""
        Read-Host "  Press Enter to exit"
        exit 1
    }
}

# -- Step 3: Install mkcert local CA -----------------------------------------
Write-Host "  [3/10] Installing mkcert local Certificate Authority..." -ForegroundColor Cyan
Write-Host "         (Creates the CA that will sign the FANS-C HTTPS certificate.)" -ForegroundColor DarkGray
Write-Host "         The rootCA.pem from this CA must be copied to each client device." -ForegroundColor DarkGray
try {
    & $mkcertExe -install
    Write-Host "         Local CA installed successfully." -ForegroundColor Green
} catch {
    Write-Host "  [WARN] mkcert -install reported an error. Continuing..." -ForegroundColor Yellow
    Write-Host "         $_" -ForegroundColor DarkGray
}


# -- Step 4: Detect LAN IP -----------------------------------------------------
Write-Host "  [4/10] Detecting server LAN IP address..." -ForegroundColor Cyan
$lanIp = $null
try {
    $udp = New-Object System.Net.Sockets.UdpClient
    $udp.Connect('8.8.8.8', 80)
    $lanIp = $udp.Client.LocalEndPoint.Address.ToString()
    $udp.Close()
} catch { }

if (-not $lanIp) {
    try {
        $lanIp = (Get-NetIPAddress -AddressFamily IPv4 |
                  Where-Object { $_.IPAddress -notmatch '^127\.' -and
                                 $_.IPAddress -notmatch '^169\.254\.' } |
                  Select-Object -First 1).IPAddress
    } catch { }
}

if ($lanIp) {
    Write-Host "         LAN IP: $lanIp" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Could not detect LAN IP. Certificate will cover localhost only." -ForegroundColor Yellow
    Write-Host "         Connect the server to the network and re-run this script to add the LAN IP." -ForegroundColor Yellow
    $lanIp = $null
}

# -- Step 5: Generate TLS certificate -----------------------------------------
Write-Host "  [5/10] Generating TLS certificate for fans-barangay.local..." -ForegroundColor Cyan

# Build the name list for mkcert
$certNames = @('fans-barangay.local', 'localhost', '127.0.0.1')
if ($lanIp) { $certNames = @('fans-barangay.local', $lanIp, 'localhost', '127.0.0.1') }

# mkcert names the file based on the first name + count of additional SANs.
# With 4 names: fans-barangay.local+3.pem / fans-barangay.local+3-key.pem
# With 3 names: fans-barangay.local+2.pem / fans-barangay.local+2-key.pem
$sanCount   = $certNames.Count - 1
$certFile   = Join-Path $projectRoot "fans-barangay.local+$sanCount.pem"
$certKeyFile = Join-Path $projectRoot "fans-barangay.local+$sanCount-key.pem"

try {
    Push-Location $projectRoot
    & $mkcertExe @certNames
    Pop-Location
} catch {
    Write-Host "  [FAIL] mkcert certificate generation failed." -ForegroundColor Red
    Write-Host "         $_" -ForegroundColor DarkGray
    Read-Host "  Press Enter to exit"
    exit 1
}

if (-not (Test-Path $certFile)) {
    Write-Host "  [FAIL] Expected certificate file not found: $certFile" -ForegroundColor Red
    Write-Host "         mkcert may have named it differently. Check the project root folder." -ForegroundColor Yellow
    Read-Host "  Press Enter to exit"
    exit 1
}

Write-Host "         Certificate: $certFile" -ForegroundColor Green
Write-Host "         Private key: $certKeyFile" -ForegroundColor Green

# Copy to stable names so Caddyfile never needs updating when cert is regenerated
$stableCert    = Join-Path $projectRoot 'fans-cert.pem'
$stableCertKey = Join-Path $projectRoot 'fans-cert-key.pem'
Copy-Item $certFile    $stableCert    -Force
Copy-Item $certKeyFile $stableCertKey -Force
Write-Host "         Stable cert: $stableCert" -ForegroundColor Green
Write-Host "         Stable key:  $stableCertKey" -ForegroundColor Green

# -- Step 6: Verify Caddyfile exists and references the stable cert name ------
Write-Host "  [6/10] Checking Caddyfile..." -ForegroundColor Cyan
if (-not (Test-Path $caddyFile)) {
    Write-Host "  [FAIL] Caddyfile not found in project root." -ForegroundColor Red
    Read-Host "  Press Enter to exit"
    exit 1
}

$caddyContent = Get-Content $caddyFile -Raw
if ($caddyContent -notmatch [regex]::Escape('fans-cert.pem')) {
    Write-Host ""
    Write-Host "  [WARN] Caddyfile does not reference 'fans-cert.pem'." -ForegroundColor Yellow
    Write-Host "         Check the 'tls' line in your Caddyfile." -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "         Caddyfile cert reference OK (fans-cert.pem)." -ForegroundColor Green
}

# -- Step 7: Verify .env ------------------------------------------------------
Write-Host "  [7/10] Checking .env configuration..." -ForegroundColor Cyan
if (-not (Test-Path $envFile)) {
    Write-Host "  [FAIL] .env not found." -ForegroundColor Red
    Write-Host "         Copy .env.example to .env, fill in your values, then re-run." -ForegroundColor Yellow
    Read-Host "  Press Enter to exit"
    exit 1
}

$envRaw = Get-Content $envFile -Raw -Encoding UTF8

if ($envRaw -match '(?m)^EMBEDDING_ENCRYPTION_KEY\s*=\s*$') {
    Write-Host "  [FAIL] EMBEDDING_ENCRYPTION_KEY is empty in .env." -ForegroundColor Red
    Write-Host "         Generate one: .\.venv\Scripts\python.exe manage.py generate_key" -ForegroundColor Cyan
    Write-Host "         Then paste the output into .env." -ForegroundColor Yellow
    Read-Host "  Press Enter to exit"
    exit 1
}

Write-Host "         .env looks OK." -ForegroundColor Green

# -- Step 8: Run migrations ---------------------------------------------------
Write-Host "  [8/10] Running Django database migrations..." -ForegroundColor Cyan
if (-not (Test-Path $venvPython)) {
    Write-Host "  [FAIL] .venv not found. Run .\setup.ps1 first." -ForegroundColor Red
    Read-Host "  Press Enter to exit"
    exit 1
}
try {
    & $venvPython manage.py migrate --noinput
    Write-Host "         Migrations applied." -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] Migration failed." -ForegroundColor Red
    Write-Host "         $_" -ForegroundColor DarkGray
    Read-Host "  Press Enter to exit"
    exit 1
}

# -- Step 9: Run collectstatic ------------------------------------------------
Write-Host "  [9/10] Collecting static files..." -ForegroundColor Cyan
try {
    & $venvPython manage.py collectstatic --noinput --clear 2>&1 | Out-Null
    Write-Host "         Static files collected." -ForegroundColor Green
} catch {
    Write-Host "  [WARN] collectstatic reported an error (non-fatal):" -ForegroundColor Yellow
    Write-Host "         $_" -ForegroundColor DarkGray
}

# -- Step 10: Firewall rule ---------------------------------------------------
Write-Host "  [10/10] Checking Windows Firewall rule for HTTPS (port 443)..." -ForegroundColor Cyan
$fwRuleName = 'FANS-C Caddy HTTPS'
$existing = netsh advfirewall firewall show rule name="$fwRuleName" 2>&1
if ($existing -match 'No rules match') {
    try {
        netsh advfirewall firewall add rule `
            name="$fwRuleName" `
            dir=in action=allow protocol=TCP localport=443 | Out-Null
        Write-Host "         Firewall rule added (port 443 inbound allowed)." -ForegroundColor Green
    } catch {
        Write-Host "  [WARN] Could not add firewall rule automatically." -ForegroundColor Yellow
        Write-Host "         Run manually as Admin:" -ForegroundColor Yellow
        Write-Host '         netsh advfirewall firewall add rule name="FANS-C Caddy HTTPS" dir=in action=allow protocol=TCP localport=443' -ForegroundColor Cyan
    }
} else {
    Write-Host "         Firewall rule already exists." -ForegroundColor Green
}

# -- Summary ------------------------------------------------------------------
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor DarkCyan
Write-Host "   Setup complete!                                                " -ForegroundColor Green
Write-Host ""
Write-Host "   Certificate files in project root:" -ForegroundColor DarkGray
Write-Host "     $certFile  (mkcert original)" -ForegroundColor DarkGray
Write-Host "     $stableCert  (stable — used by Caddy)" -ForegroundColor Cyan
Write-Host "     $stableCertKey" -ForegroundColor Cyan
if ($lanIp) {
    Write-Host ""
    Write-Host "   Server LAN IP detected: $lanIp" -ForegroundColor DarkGray
    Write-Host "   Staff can access the system at:" -ForegroundColor DarkGray
    Write-Host "     https://fans-barangay.local  (requires client hosts setup)" -ForegroundColor Cyan
    Write-Host "     http://${lanIp}:8000          (fallback, camera disabled)" -ForegroundColor DarkGray
}
Write-Host ""
Write-Host "   What still needs to be done manually:" -ForegroundColor Yellow
Write-Host ""
Write-Host "     1. Edit .env: set ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS" -ForegroundColor Yellow
if ($lanIp) {
    Write-Host "        Example:" -ForegroundColor DarkGray
    Write-Host "          ALLOWED_HOSTS=fans-barangay.local,$lanIp,localhost,127.0.0.1" -ForegroundColor DarkGray
    Write-Host "          CSRF_TRUSTED_ORIGINS=https://fans-barangay.local" -ForegroundColor DarkGray
}
Write-Host ""
Write-Host "     2. For each client device - distribute the server root CA:" -ForegroundColor Yellow
Write-Host "        Run trust-local-cert.ps1 on each client device to remove browser warnings." -ForegroundColor DarkGray
$caRootDir = $null
try { $caRootDir = (& $mkcertExe -CAROOT 2>&1) -join '' | ForEach-Object { $_.Trim() } } catch { }

if ($caRootDir -and (Test-Path $caRootDir)) {
    $rootCaPem = Join-Path $caRootDir 'rootCA.pem'
    Write-Host ""
    Write-Host "        The server's root CA file is at:" -ForegroundColor Yellow
    Write-Host "          $rootCaPem" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "        Copy this file together with trust-local-cert.ps1 to each client device." -ForegroundColor Yellow
} else {
    Write-Warning "Could not determine mkcert CA root directory automatically."
    Write-Host "        Find the server root CA:" -ForegroundColor DarkGray
    Write-Host "          Run: mkcert -CAROOT     (on this server, in any terminal)" -ForegroundColor DarkGray
    Write-Host "          Copy rootCA.pem from that folder to each client device." -ForegroundColor DarkGray
    Write-Host "          Then run trust-local-cert.ps1 (as Admin) on each client." -ForegroundColor DarkGray
}
Write-Host ""
Write-Host "        NOTE: Do NOT run 'mkcert -install' on client devices - that" -ForegroundColor Yellow
Write-Host "              creates a different CA that does NOT trust this server's cert." -ForegroundColor Yellow
Write-Host ""
Write-Host "     3. On each client device: add fans-barangay.local to hosts file" -ForegroundColor Yellow
Write-Host "        (trust-local-cert.ps1 handles this step too)" -ForegroundColor DarkGray
if ($lanIp) {
    Write-Host "        Entry to add:  $lanIp  fans-barangay.local" -ForegroundColor DarkGray
}
Write-Host "  ================================================================" -ForegroundColor DarkCyan
Write-Host ""

# -- Optional: start servers --------------------------------------------------
$startNow = Read-Host "  Start the server now? (Waitress + Caddy) [Y/N]"
if ($startNow -match '^[Yy]') {
    Write-Host ""
    Write-Host "  Starting Waitress and Caddy..." -ForegroundColor Cyan

    # Waitress (minimized)
    $waitressCmd = "Set-Location '$projectRoot'; & '$venvWaitress' --host=0.0.0.0 --port=8000 fans.wsgi:application; Read-Host 'Waitress stopped. Press Enter'"
    Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $waitressCmd -WindowStyle Minimized

    Start-Sleep -Seconds 4

    # Caddy (minimized) — locate: bundled → PATH → fallback D:\Tools\caddy.exe
    $caddyExe = $null
    if (Test-Path $caddyBundled) {
        $caddyExe = $caddyBundled
        Write-Host "  Caddy found (bundled): $caddyExe" -ForegroundColor Green
    } else {
        try {
            $found = Get-Command caddy -ErrorAction Stop
            $caddyExe = $found.Source
            Write-Host "  Caddy found on PATH: $caddyExe" -ForegroundColor Green
        } catch {
            $fallback = 'D:\Tools\caddy.exe'
            if (Test-Path $fallback) {
                $caddyExe = $fallback
                Write-Host "  Caddy found (fallback D:\Tools): $caddyExe" -ForegroundColor Green
            }
        }
    }

    if ($caddyExe) {
        $caddyCmd = "Set-Location '$projectRoot'; & '$caddyExe' run --config Caddyfile; Read-Host 'Caddy stopped. Press Enter'"
        Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $caddyCmd -WindowStyle Minimized
    } else {
        Write-Host "  [WARN] caddy.exe not found. Start Caddy manually." -ForegroundColor Yellow
        Write-Host "         Checked bundled: $caddyBundled" -ForegroundColor Yellow
        Write-Host "         Or place caddy.exe on your system PATH." -ForegroundColor Yellow
        Write-Host "         Download from: https://caddyserver.com/docs/install" -ForegroundColor Yellow
    }

    Start-Sleep -Seconds 2

    $openBrowser = Read-Host "  Open https://fans-barangay.local in the browser? [Y/N]"
    if ($openBrowser -match '^[Yy]') {
        Start-Process "https://fans-barangay.local"
    }
}

Write-Host ""
Read-Host "Press Enter to close this window"
