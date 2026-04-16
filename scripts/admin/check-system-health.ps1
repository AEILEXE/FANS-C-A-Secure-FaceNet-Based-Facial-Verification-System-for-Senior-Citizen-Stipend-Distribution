#Requires -Version 5.1
<#
.SYNOPSIS
    FANS-C System Health Check -- IT/Admin diagnostic tool.
    Reports the live status of all system components.

.DESCRIPTION
    Run this script any time to see the current state of the FANS-C system.
    It does not start, stop, or change anything. It only reads and reports.

    What it checks:
      1. Waitress process  -- is waitress-serve.exe running?
      2. Port 8000         -- is Waitress actually accepting connections?
      3. Caddy process     -- is caddy.exe running?
      4. Port 443          -- is Caddy actually accepting HTTPS connections?
      5. Certificate files -- are fans-cert.pem / fans-cert-key.pem present?
      6. .env keys         -- are SECRET_KEY and EMBEDDING_ENCRYPTION_KEY set?
      7. Task Scheduler    -- is the auto-start task registered and ready?
      8. Startup log       -- what did the last startup attempt report?

    Use this when:
      - The browser cannot reach https://fans-barangay.local
      - The system seems unresponsive after boot
      - You want to confirm everything is healthy before a deployment
      - A staff member reports problems

.NOTES
    Does not require Administrator privileges to read process and port state.
    Administrator rights are needed to check Task Scheduler task state.

.EXAMPLE
    Right-click scripts\admin\check-system-health.ps1 -> Run with PowerShell
    -- or --
    powershell -ExecutionPolicy Bypass -File .\scripts\admin\check-system-health.ps1
#>

$ErrorActionPreference = 'Continue'
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

# -- Helpers ------------------------------------------------------------------

function Write-Check {
    param([string]$Label, [bool]$OK, [string]$OKMsg, [string]$FailMsg)
    $pad = 30
    $labelPadded = $Label.PadRight($pad)
    if ($OK) {
        Write-Host "   [OK]   $labelPadded $OKMsg" -ForegroundColor Green
    } else {
        Write-Host "   [FAIL] $labelPadded $FailMsg" -ForegroundColor Red
    }
}

function Write-Info {
    param([string]$Label, [string]$Value)
    $pad = 30
    $labelPadded = $Label.PadRight($pad)
    Write-Host "   [INFO] $labelPadded $Value" -ForegroundColor DarkGray
}

function Write-Warn {
    param([string]$Msg)
    Write-Host "   [WARN] $Msg" -ForegroundColor Yellow
}

function Test-PortOpen {
    param([int]$Port)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect('127.0.0.1', $Port)
        $tcp.Close()
        return $true
    } catch {
        return $false
    }
}

# -- Banner -------------------------------------------------------------------
Write-Host ''
Write-Host '  ================================================================' -ForegroundColor DarkCyan
Write-Host '   FANS-C  |  System Health Check' -ForegroundColor Cyan
Write-Host '   IT/Admin diagnostic tool -- read-only, no changes made' -ForegroundColor DarkGray
Write-Host '  ================================================================' -ForegroundColor DarkCyan
Write-Host ''
Write-Host "  Project  : $projectRoot" -ForegroundColor DarkGray
Write-Host "  Checked  : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host ''

$anyFail = $false

# =============================================================================
# 1 + 2: WAITRESS PROCESS AND PORT 8000
# =============================================================================
Write-Host '  -- Application Server (Waitress) ----------------------------' -ForegroundColor DarkCyan

$waitressProcs = Get-Process -Name 'waitress-serve' -ErrorAction SilentlyContinue
$waitressRunning = ($null -ne $waitressProcs -and $waitressProcs.Count -gt 0)

if ($waitressRunning) {
    $pidList = ($waitressProcs | ForEach-Object { $_.Id }) -join ', '
    Write-Check 'Waitress process' $true 'Running' ''
    Write-Info  'Process ID(s)' $pidList
} else {
    Write-Check 'Waitress process' $false '' 'NOT running'
    $anyFail = $true
}

$port8000 = Test-PortOpen -Port 8000
Write-Check 'Port 8000 (app)' $port8000 'LISTENING -- accepting connections' 'NOT listening -- app server down'
if (-not $port8000) { $anyFail = $true }

if ($waitressRunning -and -not $port8000) {
    Write-Warn 'Waitress is running but port 8000 is not responding.'
    Write-Warn 'Possible cause: Django crashed after launch. Check startup log below.'
}
if (-not $waitressRunning -and $port8000) {
    Write-Warn 'Port 8000 is listening but no Waitress process was found.'
    Write-Warn 'Another process may be using port 8000.'
}

Write-Host ''

# =============================================================================
# 3 + 4: CADDY PROCESS AND PORT 443
# =============================================================================
Write-Host '  -- HTTPS Proxy (Caddy) --------------------------------------' -ForegroundColor DarkCyan

$caddyProcs = Get-Process -Name 'caddy' -ErrorAction SilentlyContinue
$caddyRunning = ($null -ne $caddyProcs -and $caddyProcs.Count -gt 0)

if ($caddyRunning) {
    $pidList = ($caddyProcs | ForEach-Object { $_.Id }) -join ', '
    Write-Check 'Caddy process' $true 'Running' ''
    Write-Info  'Process ID(s)' $pidList
} else {
    Write-Check 'Caddy process' $false '' 'NOT running'
    $anyFail = $true
}

$port443 = Test-PortOpen -Port 443
Write-Check 'Port 443 (HTTPS)' $port443 'LISTENING -- HTTPS is available' 'NOT listening -- HTTPS is down'
if (-not $port443) { $anyFail = $true }

if ($caddyRunning -and -not $port443) {
    Write-Warn 'Caddy is running but port 443 is not responding.'
    Write-Warn 'Possible cause: Caddy cannot read fans-cert.pem, or Caddyfile error.'
    Write-Warn 'For details: run scripts\start\start-fans.bat (shows Caddy error output).'
}

Write-Host ''

# =============================================================================
# 5: TLS CERTIFICATE FILES
# =============================================================================
Write-Host '  -- TLS Certificate Files ------------------------------------' -ForegroundColor DarkCyan

$certPath    = Join-Path $projectRoot 'fans-cert.pem'
$certKeyPath = Join-Path $projectRoot 'fans-cert-key.pem'
$certOK      = Test-Path $certPath
$certKeyOK   = Test-Path $certKeyPath

Write-Check 'fans-cert.pem' $certOK 'Found' 'MISSING -- Caddy cannot start HTTPS'
Write-Check 'fans-cert-key.pem' $certKeyOK 'Found' 'MISSING -- Caddy cannot start HTTPS'

if (-not $certOK -or -not $certKeyOK) {
    $anyFail = $true
    Write-Warn 'Fix: run scripts\setup\setup-complete.ps1 to regenerate the certificate.'
} else {
    # Show cert file age
    try {
        $certAge = (Get-Date) - (Get-Item $certPath).LastWriteTime
        $ageStr  = if ($certAge.Days -gt 0) {
            "$($certAge.Days) days old"
        } else {
            "$([int]$certAge.TotalHours) hours old"
        }
        Write-Info 'Cert file age' $ageStr
    } catch { }
}

Write-Host ''

# =============================================================================
# 6: .ENV KEY CONFIGURATION
# =============================================================================
Write-Host '  -- .env Configuration ---------------------------------------' -ForegroundColor DarkCyan

$envFile = Join-Path $projectRoot '.env'

if (-not (Test-Path $envFile)) {
    Write-Check '.env file' $false '' 'MISSING -- system is not configured'
    $anyFail = $true
} else {
    Write-Check '.env file' $true 'Found' ''
    $envRaw = Get-Content $envFile -Raw -Encoding UTF8

    $skOK  = $envRaw -match '(?m)^SECRET_KEY\s*=\s*\S+'
    $eekOK = $envRaw -match '(?m)^EMBEDDING_ENCRYPTION_KEY\s*=\s*\S+'

    Write-Check 'SECRET_KEY' $skOK 'Set' 'MISSING or empty -- Django cannot start'
    Write-Check 'EMBEDDING_ENCRYPTION_KEY' $eekOK 'Set' 'MISSING -- face data is unreadable'

    if (-not $skOK -or -not $eekOK) { $anyFail = $true }

    # Show DEBUG mode
    if ($envRaw -match '(?m)^DEBUG\s*=\s*True') {
        Write-Warn 'DEBUG=True is set. For production use, set DEBUG=False in .env.'
    } else {
        Write-Info 'DEBUG mode' 'False (production mode)'
    }
}

Write-Host ''

# =============================================================================
# 7: TASK SCHEDULER AUTO-START
# =============================================================================
Write-Host '  -- Task Scheduler Auto-Start --------------------------------' -ForegroundColor DarkCyan

$taskName = 'FANS-C Verification System'

try {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
    $taskState = $task.State.ToString()
    $isTaskOK  = ($task.State -eq 'Ready' -or $task.State -eq 'Running')
    Write-Check 'Task registered' $true 'Found' ''
    Write-Info  'Task name'   $taskName
    Write-Info  'Task state'  $taskState

    if (-not $isTaskOK) {
        Write-Warn "Task state is '$taskState' (expected: Ready)."
        Write-Warn 'Re-run scripts\setup\setup-autostart.ps1 to fix the task.'
        $anyFail = $true
    }

    # Show last run result
    try {
        $taskInfo = Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction Stop
        if ($taskInfo.LastRunTime -and $taskInfo.LastRunTime -gt [DateTime]::MinValue) {
            $lastRun = $taskInfo.LastRunTime.ToString('yyyy-MM-dd HH:mm:ss')
            Write-Info 'Last run' $lastRun
        }
        if ($taskInfo.LastTaskResult -ne $null) {
            $resultCode = '0x{0:X8}' -f $taskInfo.LastTaskResult
            $resultText = if ($taskInfo.LastTaskResult -eq 0) { 'Success (0x00000000)' } else { "Code $resultCode" }
            Write-Info 'Last result' $resultText
        }
    } catch { }

} catch {
    Write-Check 'Task registered' $false '' 'NOT registered -- auto-start is disabled'
    Write-Warn 'The system will NOT start automatically after a reboot.'
    Write-Warn 'Fix: run scripts\setup\setup-autostart.ps1 (as Admin) to register it.'
    $anyFail = $true
}

Write-Host ''

# =============================================================================
# 8: RECENT STARTUP LOG
# =============================================================================
Write-Host '  -- Startup Log (last startup attempt) -----------------------' -ForegroundColor DarkCyan

$logFile = Join-Path $projectRoot 'logs\fans-startup.log'

if (-not (Test-Path $logFile)) {
    Write-Info 'Log file' 'Not found (system has not been started via Task Scheduler yet)'
} else {
    $logAge = (Get-Date) - (Get-Item $logFile).LastWriteTime
    $ageStr = if ($logAge.TotalMinutes -lt 60) {
        "$([int]$logAge.TotalMinutes) minutes ago"
    } elseif ($logAge.TotalHours -lt 24) {
        "$([int]$logAge.TotalHours) hours ago"
    } else {
        "$([int]$logAge.TotalDays) days ago"
    }
    Write-Info 'Log file' "Found (last modified: $ageStr)"

    # Show last startup block (from last separator line)
    $allLines = Get-Content $logFile -Encoding UTF8 -ErrorAction SilentlyContinue
    if ($allLines) {
        # Find the last occurrence of the separator line
        $sepIdx = -1
        for ($i = $allLines.Count - 1; $i -ge 0; $i--) {
            if ($allLines[$i] -match '={3,}') {
                $sepIdx = $i
                break
            }
        }

        if ($sepIdx -ge 0) {
            $block = $allLines[($sepIdx)..($allLines.Count - 1)]
        } else {
            # No separator: show last 20 lines
            $block = $allLines | Select-Object -Last 20
        }

        Write-Host ''
        Write-Host '  Last startup log:' -ForegroundColor DarkGray
        foreach ($line in $block) {
            # Color STARTUP STATUS lines
            if ($line -match 'STARTUP STATUS.*OK') {
                Write-Host "    $line" -ForegroundColor Green
            } elseif ($line -match 'STARTUP STATUS.*PARTIAL') {
                Write-Host "    $line" -ForegroundColor Yellow
            } elseif ($line -match 'STARTUP STATUS.*FAIL') {
                Write-Host "    $line" -ForegroundColor Red
            } elseif ($line -match '\bFAIL\b') {
                Write-Host "    $line" -ForegroundColor Red
            } elseif ($line -match '\bWARN\b') {
                Write-Host "    $line" -ForegroundColor Yellow
            } elseif ($line -match '\bOK\b|\bLISTENING\b') {
                Write-Host "    $line" -ForegroundColor Green
            } else {
                Write-Host "    $line" -ForegroundColor DarkGray
            }
        }
    }
}

Write-Host ''

# =============================================================================
# SUMMARY
# =============================================================================
Write-Host '  ================================================================' -ForegroundColor DarkCyan

if ($anyFail) {
    Write-Host '   HEALTH: ISSUES FOUND (see [FAIL] items above)' -ForegroundColor Red
    Write-Host ''
    Write-Host '  Quick fix guide:' -ForegroundColor Yellow
    Write-Host ''

    if (-not $waitressRunning -or -not $port8000) {
        Write-Host '   Waitress/port 8000 down:' -ForegroundColor Yellow
        Write-Host '     1. Check the startup log above for error details.' -ForegroundColor DarkGray
        Write-Host '     2. Run scripts\start\start-fans.bat to see Django output.' -ForegroundColor DarkGray
        Write-Host '     3. If .env keys are missing: re-run setup-complete.ps1.' -ForegroundColor DarkGray
        Write-Host ''
    }

    if (-not $caddyRunning -or -not $port443) {
        Write-Host '   Caddy/port 443 down:' -ForegroundColor Yellow
        Write-Host '     1. Run scripts\start\start-fans.bat to see Caddy error output.' -ForegroundColor DarkGray
        Write-Host '     2. If fans-cert.pem is missing: re-run setup-complete.ps1.' -ForegroundColor DarkGray
        Write-Host '     3. Check Caddyfile -- confirm "fans-cert.pem" path is correct.' -ForegroundColor DarkGray
        Write-Host '     4. Run: netstat -ano | findstr :443  (check for port conflicts).' -ForegroundColor DarkGray
        Write-Host ''
    }

    if (-not $waitressRunning -and -not $caddyRunning) {
        Write-Host '   Nothing is running:' -ForegroundColor Yellow
        Write-Host '     Option A (auto-start): reboot the server PC.' -ForegroundColor DarkGray
        Write-Host '     Option B (manual):     double-click start-fans-quiet.bat.' -ForegroundColor DarkGray
        Write-Host '     Option C (debug):      run start-fans.bat to see all output.' -ForegroundColor DarkGray
    }
} else {
    Write-Host '   HEALTH: ALL CHECKS PASSED' -ForegroundColor Green
    Write-Host ''
    Write-Host '   System is running correctly.' -ForegroundColor Green
    Write-Host '   Staff can access:  https://fans-barangay.local' -ForegroundColor Cyan
}

Write-Host ''
Write-Host '  ================================================================' -ForegroundColor DarkCyan
Write-Host ''
Read-Host '  Press Enter to close'
