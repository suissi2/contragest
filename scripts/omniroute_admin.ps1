<#
.SYNOPSIS
    Admin tool for the OmniRoute gateway: health-check + restart now, and
    install a scheduled watchdog so "Server is unreachable" never happens again.

.DESCRIPTION
    Wraps start_omniroute.ps1 (which is now reliable: it launches the gateway
    through the npm .cmd shim, not the .ps1 shim that silently no-ops under
    Start-Process, and it is guarded by a mutex so concurrent starters never
    double-launch).

    This script adds the "next occurrence" defence:
      * A health check you can run any time (default action): if port 20128
        is not listening, start the gateway.
      * -InstallWatchdog registers a per-user scheduled task
        "OmniRouteGatewayWatchdog" that runs the health check at logon/startup
        and then every N minutes (default 5). If the gateway dies or fails to
        come up at boot, it self-heals within the interval.
      * -RemoveWatchdog removes that task.
      * -Status prints the current state (port, HTTP answer, task, log tail).

    No admin rights are needed (everything is per-user).

.PARAMETER InstallWatchdog
    Register the watchdog scheduled task and run a health check now.

.PARAMETER RemoveWatchdog
    Unregister the watchdog scheduled task.

.PARAMETER Status
    Print current gateway + watchdog state.

.PARAMETER IntervalMinutes
    Watchdog check frequency when -InstallWatchdog is used. Default 5.

.PARAMETER TaskName
    Name of the scheduled task. Default "OmniRouteGatewayWatchdog".

.EXAMPLE
    .\scripts\omniroute_admin.ps1                 # check now, start if down

.EXAMPLE
    .\scripts\omniroute_admin.ps1 -InstallWatchdog   # self-heal every 5 min

.EXAMPLE
    .\scripts\omniroute_admin.ps1 -Status

.EXAMPLE
    .\scripts\omniroute_admin.ps1 -RemoveWatchdog
#>
param(
    [switch]$InstallWatchdog,
    [switch]$RemoveWatchdog,
    [switch]$Status,
    [int]$IntervalMinutes = 5,
    [string]$TaskName = 'OmniRouteGatewayWatchdog'
)

$ErrorActionPreference = 'Stop'

$Port           = 20128
$StartScript    = Join-Path $PSScriptRoot 'start_omniroute.ps1'
$RunKeyPath     = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$RunKeyName     = 'OmniRouteGateway'
$LogFile        = Join-Path (Split-Path -Parent $PSScriptRoot) '.tmp\omniroute_start.log'

function Write-Step([string]$m) { Write-Host "[omniroute-admin] $m" -ForegroundColor Cyan }
function Write-Info([string]$m) { Write-Host "[omniroute-admin] $m" -ForegroundColor Gray }

function Test-PortListening([int]$p) {
    return [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}

function Test-GatewayHttp {
    # True if the gateway answers an HTTP request on its own port (the API
    # works, not just a TCP socket being open). Probes /v1/models: it is the
    # canonical health endpoint and much faster than the Next.js dashboard
    # page, which cold-compiles on first hit. One retry covers a cold start.
    for ($i = 1; $i -le 2; $i++) {
        try {
            $null = Invoke-WebRequest -Uri "http://localhost:$Port/v1/models" -TimeoutSec 10 -UseBasicParsing
            return $true
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    return $false
}

function Get-WatchdogTask {
    return Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
}

function Get-HkuRunCommand {
    $v = (Get-ItemProperty -Path $RunKeyPath -Name $RunKeyName -ErrorAction SilentlyContinue).$RunKeyName
    return $v
}

# ── Sanity: the wrapped script must exist ───────────────────────────────────
if (-not (Test-Path -LiteralPath $StartScript)) {
    Write-Host "[omniroute-admin] ERROR: $StartScript not found (repo moved?)." -ForegroundColor Red
    exit 1
}

# ── -Status ─────────────────────────────────────────────────────────────────
if ($Status) {
    $listening = Test-PortListening $Port   # NOT $port: PowerShell vars are case-insensitive
    $http = if ($listening) { Test-GatewayHttp } else { $false }
    Write-Step "Port $Port listening: $listening"
    Write-Step "HTTP answering:      $http"
    $task = Get-WatchdogTask
    if ($task) {
        $state = $task.State
        $trig  = $task.Triggers | ForEach-Object { $_.ToString() } | Sort-Object -Unique
        Write-Step "Watchdog task:       $($task.TaskName) ($state)"
        Write-Info "  Triggers: $($trig -join '; ')"
        if ($task.Actions) { Write-Info "  Action: $((($task.Actions | ForEach-Object { $_.Execute }) -join '; '))" }
    }
    else {
        Write-Step "Watchdog task:       NOT INSTALLED (run -InstallWatchdog)"
    }
    $runCmd = Get-HkuRunCommand
    Write-Step "Logon autostart:     $(if ($runCmd) { $RunKeyName } else { 'not set' })"
    Write-Info "Log file: $LogFile"
    if (Test-Path -LiteralPath $LogFile) {
        Write-Info "--- last log lines ---"
        Get-Content -LiteralPath $LogFile -Tail 6 | ForEach-Object { Write-Info $_ }
    }
    exit 0
}

# ── -RemoveWatchdog ─────────────────────────────────────────────────────────
if ($RemoveWatchdog) {
    $task = Get-WatchdogTask
    if ($task) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Step "Watchdog task '$TaskName' removed."
    }
    else {
        Write-Info "Watchdog task '$TaskName' is not installed."
    }
    exit 0
}

# ── -InstallWatchdog ────────────────────────────────────────────────────────
if ($InstallWatchdog) {
    $action = New-ScheduledTaskAction `
        -Execute 'powershell.exe' `
        -Argument ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -Silent -WaitSeconds 60' -f $StartScript)

    $interval = New-TimeSpan -Minutes $IntervalMinutes
    # No -RepetitionDuration on purpose: an omitted Duration means the
    # repetition is INDEFINITE. ([TimeSpan]::MaxValue serializes to an
    # out-of-range XML duration and Register-ScheduledTask rejects it.)
    $rep      = (New-ScheduledTaskTrigger -Once -At (Get-Date) `
        -RepetitionInterval $interval).Repetition

    # Only AtLogOn: an AtStartup trigger requires admin rights, and the
    # gateway is per-user anyway (logon autostart + this task cover it).
    $atLogon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $atLogon.Repetition = $rep

    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $atLogon -Settings $settings -Description 'OmniRoute gateway watchdog: start/restart http://localhost:20128 if down.' -Force | Out-Null

    Write-Step "Watchdog task '$TaskName' installed (at logon, then every $IntervalMinutes min)."
    Write-Info "Action: $StartScript -Silent -WaitSeconds 60"
}

# ── Health check now (default action) ───────────────────────────────────────
if (Test-PortListening $Port) {
    Write-Step "Gateway already up on port $Port."
}
else {
    Write-Step "Gateway is DOWN on port $Port; starting it..."
    & $StartScript -WaitSeconds 60
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[omniroute-admin] ERROR: gateway did not come up. See $LogFile" -ForegroundColor Red
        exit 1
    }
    Write-Step "Gateway is UP on port $Port."
}

if ($InstallWatchdog) {
    Write-Info "Watchdog installed; on the next occurrence the gateway will self-heal within $IntervalMinutes min."
}
