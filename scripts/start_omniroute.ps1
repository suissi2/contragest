#requires -Version 5.1
<#
.SYNOPSIS
    Ensures the OmniRoute gateway (npm package "omniroute") is running on
    http://localhost:20128, and optionally registers it for auto-start at
    user logon.

.DESCRIPTION
    OmniRoute is a global npm package (CLI + dashboard on one port, 20128).
    Starting it by hand is error-prone: the server locks its own dist/ folder
    while running, so `npm install -g omniroute` (or an update) fails with
    EBUSY while the gateway is up.  This script exists to make "is the
    gateway up?" a one-shot deterministic check:

      * If something already listens on TCP port 20128  -> nothing to do
        (idempotent: never spawns a second instance).
      * Otherwise it locates the omniroute launcher (npm global shim),
        starts it hidden with --no-open, and waits until the port answers.
      * If omniroute is not installed it exits with a clear message and a
        non-zero code instead of a cryptic failure.

    Run from anywhere; it needs no admin rights.

.PARAMETER Port
    TCP port the gateway listens on.  Default 20128 (OmniRoute's canonical).

.PARAMETER WaitSeconds
    How long to wait for the port to come up after launching.  Default 30.

.PARAMETER Restart
    Stop any existing gateway on $Port first, then start fresh.  Used for
    testing or after a version upgrade.

.PARAMETER Register
    Add the per-user HKCU Run key so the gateway auto-starts at logon.

.PARAMETER Unregister
    Remove the HKCU Run key (gateway will no longer auto-start).

.PARAMETER NoStart
    Register/unregister autostart only; do not launch the gateway now.

.PARAMETER Silent
    No console output; exit codes only (0 = up, 1 = error).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_omniroute.ps1

.EXAMPLE
    .\scripts\start_omniroute.ps1 -Register   # auto-start at next logon + launch now

.EXAMPLE
    .\scripts\start_omniroute.ps1 -Restart    # kill current instance, start fresh
#>
param(
    [int]$Port = 20128,
    [int]$WaitSeconds = 30,
    [switch]$Restart,
    [switch]$Register,
    [switch]$Unregister,
    [switch]$NoStart,
    [switch]$Silent
)

$ErrorActionPreference = 'Stop'

$RunKeyPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$RunKeyName = 'OmniRouteGateway'
$AppDir     = Split-Path -Parent $PSScriptRoot          # project root
$LogDir     = Join-Path $AppDir '.tmp'
$LogFile    = Join-Path $LogDir 'omniroute_start.log'
$ShimArgs   = '--no-open'                                # no browser popup

if (-not $Silent) { function Write-Step([string]$m) { Write-Host "[omniroute] $m" -ForegroundColor Cyan } }
else { function Write-Step([string]$m) { } }

function Write-Log([string]$msg) {
    try {
        if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
        $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
        Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
    }
    catch { }
}

function Test-PortListening([int]$p) {
    return [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}

function Find-OmnirouteLauncher {
    $cands = @()
    $cmd = Get-Command omniroute -ErrorAction SilentlyContinue
    if ($cmd) { $cands += $cmd.Source }
    try {
        $prefix = (npm prefix -g 2>$null | Select-Object -First 1).Trim()
        if ($prefix) {
            if (Test-Path (Join-Path $prefix 'omniroute.cmd')) { $cands += (Join-Path $prefix 'omniroute.cmd') }
            elseif (Test-Path (Join-Path $prefix 'omniroute.ps1')) { $cands += (Join-Path $prefix 'omniroute.ps1') }
            elseif (Test-Path (Join-Path $prefix 'bin\omniroute')) { $cands += (Join-Path $prefix 'bin\omniroute') }
        }
    }
    catch { }
    foreach ($c in $cands) {
        if (Test-Path -LiteralPath $c) { return (Resolve-Path -LiteralPath $c).Path }
    }
    return $null
}

function Stop-GatewayOnPort([int]$p) {
    Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            Write-Step "Stopping gateway PID $($_.OwningProcess)..."
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    Start-Sleep -Seconds 2
}

# ── 1. Autostart bookkeeping ────────────────────────────────────────────────
if ($Register -and $Unregister) { throw '-Register and -Unregister are mutually exclusive.' }

if ($Register -or $Unregister) {
    $runCmd = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f $PSCommandPath
    if ($Register) {
        Set-ItemProperty -Path $RunKeyPath -Name $RunKeyName -Value $runCmd
        Write-Step "Autostart registered: $RunKeyName = $runCmd"
        Write-Log "Autostart registered: $RunKeyName"
    }
    else {
        Remove-ItemProperty -Path $RunKeyPath -Name $RunKeyName -ErrorAction SilentlyContinue
        Write-Step "Autostart removed: $RunKeyName"
        Write-Log "Autostart removed: $RunKeyName"
    }
    if ($NoStart) {
        Write-Step 'NoStart: skipping gateway launch.'
        exit 0
    }
}

# ── 2. Idempotency check ────────────────────────────────────────────────────
if (Test-PortListening $Port) {
    if (-not $Restart) {
        Write-Step "Gateway already listening on port $Port. Nothing to do."
        exit 0
    }
    Write-Step "Port $Port is occupied but -Restart was requested; restarting."
    Stop-GatewayOnPort $Port
}

# ── 3. Locate launcher ──────────────────────────────────────────────────────
$launcher = Find-OmnirouteLauncher
if (-not $launcher) {
    Write-Log "ERROR: omniroute not found (npm install -g omniroute required)"
    if (-not $Silent) { Write-Host '[omniroute] ERROR: omniroute package not installed. Run: npm install -g omniroute' -ForegroundColor Red }
    exit 1
}
Write-Step "Launcher: $launcher"

# ── 4. Launch hidden ────────────────────────────────────────────────────────
Write-Step "Starting gateway (port $Port)..."
Start-Process -FilePath $launcher -ArgumentList $ShimArgs -WindowStyle Hidden
Write-Log "Launched: $launcher $ShimArgs"

# ── 5. Wait for the port ────────────────────────────────────────────────────
$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
    if (Test-PortListening $Port) {
        Write-Step "Gateway is UP on port $Port."
        Write-Log "Gateway UP on port $Port"
        exit 0
    }
}

Write-Log "ERROR: port $Port did not open within ${WaitSeconds}s"
if (-not $Silent) { Write-Host "[omniroute] ERROR: port $Port did not open within ${WaitSeconds}s - see $LogFile" -ForegroundColor Red }
exit 1
