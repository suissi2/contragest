#requires -Version 5.1
<#
.SYNOPSIS
    Removes the Contragest system-tray agent autostart and the elevated
    service-control scheduled tasks.

.DESCRIPTION
    * removes the HKCU Run key entry (per-user autostart),
    * unregisters ContragestServiceControlStart/Stop/Restart,
    * optionally stops the running tray agent (-StopAgent).

    Does NOT touch the ContragestSync service itself — use
    scripts\uninstall_service.ps1 for that.

.PARAMETER StopAgent
    Stop a running tray agent (python/pythonw running tray_main.py).

.PARAMETER Silent
    Do not prompt; fail fast instead.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_tray.ps1 -StopAgent
#>
param(
    [switch]$StopAgent,
    [switch]$Silent
)

$ErrorActionPreference = 'Stop'

$RunKeyName = 'ContragestTray'
$RunKeyPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$TaskPrefix = 'ContragestServiceControl'

function Write-Step([string]$msg) { Write-Host "[tray-uninstall] $msg" -ForegroundColor Cyan }

# ── 1. Running agent ────────────────────────────────────────────────────────
if ($StopAgent) {
    $procs = Get-CimInstance Win32_Process |
        Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match 'tray_main\.py' }
    foreach ($p in $procs) {
        Write-Step "Stopping running agent PID $($p.ProcessId)"
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

# ── 2. Autostart Run key ───────────────────────────────────────────────────
if (Test-Path -LiteralPath $RunKeyPath) {
    $existing = Get-ItemProperty -Path $RunKeyPath -Name $RunKeyName -ErrorAction SilentlyContinue
    if ($existing) {
        Remove-ItemProperty -Path $RunKeyPath -Name $RunKeyName
        Write-Step "Removed autostart key $RunKeyName"
    }
}

# ── 3. Elevated control tasks ──────────────────────────────────────────────
# schtasks.exe is used instead of Unregister-ScheduledTask (see the matching
# note in install_tray.ps1 about the ScheduledTasks cmdlets on 5.1/26100).
foreach ($name in 'Start', 'Stop', 'Restart') {
    $task = "$TaskPrefix$name"
    & schtasks.exe /Query /TN $task | Out-Null
    if ($LASTEXITCODE -eq 0) {
        & schtasks.exe /Delete /TN $task /F | Out-Null
        Write-Step "Unregistered task: $task"
    }
}

Write-Step 'Tray agent removed. The ContragestSync service is untouched.'
