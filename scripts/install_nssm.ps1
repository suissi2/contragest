#requires -Version 5.1
<#
.SYNOPSIS
    Installs Contragest as a Windows service using NSSM (alternative to the
    native pywin32 service).

.DESCRIPTION
    NSSM wraps `python.exe service_main.py run` so no pywin32 is required on
    the target machine.  It provides auto-start, automatic restart on failure,
    stdout/stderr capture with rotation, and graceful stop via console events.

    Install NSSM first (https://nssm.cc).  If -NssmPath is omitted the script
    looks for nssm.exe on PATH, then downloads nssm 2.24 from nssm.cc.

.PARAMETER AppDir
    Directory containing service_main.py (defaults to this script's parent).

.PARAMETER Python
    Path to python.exe.  Defaults to $AppDir\.venv\Scripts\python.exe.

.PARAMETER NssmPath
    Path to nssm.exe.  Default: nssm.exe on PATH, else downloaded to .tmp.

.PARAMETER ServiceAccount
    Optional DOMAIN\user to run under (default LocalSystem).

.PARAMETER ServicePassword
    Password for ServiceAccount.

.PARAMETER SyncInterval
    Seconds between attendance download passes (default 30).

.PARAMETER HealthPort
    Optional HTTP /health endpoint port.

.PARAMETER NoStart
    Configure but do not start.
#>
param(
    [string]$AppDir,
    [string]$Python,
    [string]$NssmPath,
    [string]$ServiceAccount,
    [string]$ServicePassword,
    [int]$SyncInterval = 30,
    [int]$HealthPort = 0,
    [switch]$NoStart
)

$ErrorActionPreference = 'Stop'
$ServiceName = 'ContragestSync'

function Assert-Admin {
    $pr = New-Object Security.Principal.WindowsPrincipal(
        [Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'This script must run from an elevated PowerShell.'
    }
}

if (-not $AppDir) { $AppDir = Split-Path -Parent $PSScriptRoot }
$AppDir = (Resolve-Path -LiteralPath $AppDir).Path
if (-not (Test-Path -LiteralPath (Join-Path $AppDir 'service_main.py'))) {
    throw "service_main.py not found under $AppDir"
}
if (-not $Python) {
    $Python = Join-Path $AppDir '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $Python)) { $Python = 'python.exe' }
}
if (-not (Test-Path -LiteralPath $Python) -and (Get-Command $Python -ErrorAction SilentlyContinue) -eq $null) {
    throw "Python not found: $Python"
}

# Locate nssm.exe
if (-not $NssmPath) {
    $cmd = Get-Command nssm.exe -ErrorAction SilentlyContinue
    if ($cmd) { $NssmPath = $cmd.Source }
}
if (-not $NssmPath) {
    $NssmPath = Join-Path $AppDir '.tmp\nssm\nssm.exe'
    if (-not (Test-Path -LiteralPath $NssmPath)) {
        Write-Host '[nssm] nssm.exe not found - downloading nssm 2.24...'
        $zip = Join-Path $env:TEMP 'nssm-2.24.zip'
        Invoke-WebRequest 'https://nssm.cc/release/nssm-2.24.zip' -OutFile $zip
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $NssmPath) | Out-Null
        Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $env:TEMP 'nssm-2.24') -Force
        Copy-Item (Join-Path $env:TEMP 'nssm-2.24\nssm-2.24\win64\nssm.exe') $NssmPath -Force
    }
}
Write-Host "[nssm] Using $NssmPath"

$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($svc) {
    throw "Service '$ServiceName' already exists. Uninstall it first (scripts\uninstall_nssm.ps1)."
}

$args = 'service_main.py run --sync-interval ' + $SyncInterval
if ($HealthPort -gt 0) { $args += " --health-port $HealthPort" }

& $NssmPath install $ServiceName $Python $args | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'nssm install failed' }

& $NssmPath set $ServiceName AppDirectory $AppDir | Out-Null
& $NssmPath set $ServiceName AppEnvironmentExtra "CONTRAGEST_BASE_DIR=$AppDir" "CONTRAGEST_DB_PATH=$($AppDir)\contragest.db" | Out-Null
& $NssmPath set $ServiceName Description 'Keeps Contragest attendance data current 24/7 (NSSM): ZK machine sync, contract alerts, daily audit/auto-correction and clock sync.' | Out-Null
& $NssmPath set $ServiceName Start SERVICE_AUTO_START | Out-Null

# Log capture with rotation (5 MB)
$logDir = Join-Path $AppDir 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
& $NssmPath set $ServiceName AppStdout (Join-Path $logDir 'service_stdout.log') | Out-Null
& $NssmPath set $ServiceName AppStderr (Join-Path $logDir 'service_stderr.log') | Out-Null
& $NssmPath set $ServiceName AppRotateFiles 1 | Out-Null
& $NssmPath set $ServiceName AppRotateBytes 5242880 | Out-Null

# Graceful stop: send Ctrl+C/close to the console process first, wait 10s,
# then wait 10s more before killing.
& $NssmPath set $ServiceName AppStopMethodConsole 10000 | Out-Null
& $NssmPath set $ServiceName AppStopMethodThreads 5000 | Out-Null
& $NssmPath set $ServiceName AppStopMethodProcess 0 | Out-Null

# Restart on crash / unexpected exit
& $NssmPath set $ServiceName AppExit Default Restart | Out-Null
& $NssmPath set $ServiceName AppRestartDelay 5000 | Out-Null

# Service account
if ($ServiceAccount -and $ServiceAccount -ine 'LocalSystem') {
    if (-not $ServicePassword) { $ServicePassword = Read-Host "Password for $ServiceAccount" }
    & $NssmPath set $ServiceName ObjectName $ServiceAccount $ServicePassword | Out-Null
}

Write-Host "[nssm] Service '$ServiceName' configured."

if ($NoStart) {
    Write-Host '[nssm] Skipping start (-NoStart).'
}
else {
    & $NssmPath start $ServiceName | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'nssm start failed' }
    Write-Host "[nssm] Service '$ServiceName' STARTED."
}

Write-Host ''
Write-Host 'Useful commands:' -ForegroundColor Green
Write-Host '  nssm restart ContragestSync'
Write-Host '  nssm status ContragestSync'
Write-Host "  python service_main.py healthcheck"
