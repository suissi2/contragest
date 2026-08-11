#requires -Version 5.1
<#
.SYNOPSIS
    Stops and removes the ContragestSync Windows service.

.DESCRIPTION
    Removes the service, deletes its Event Log source registration, removes
    the optional health-endpoint firewall rule, and (by default) keeps logs
    and the database untouched.

.PARAMETER AppDir
    Directory that contains service_main.py (defaults to this script's parent).

.PARAMETER RemoveLogs
    Also delete the logs directory.

.PARAMETER Silent
    Do not prompt for confirmation.
#>
param(
    [string]$AppDir,
    [switch]$RemoveLogs,
    [switch]$Silent
)

$ErrorActionPreference = 'Stop'
$ServiceName = 'ContragestSync'

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'This script must run from an elevated PowerShell.'
}

$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $svc) {
    Write-Host "Service '$ServiceName' is not installed."
}
else {
    if (-not $Silent) {
        $answer = Read-Host "Stop and remove service '$ServiceName'? [y/N]"
        if ($answer -notin @('y', 'Y', 'yes')) { Write-Host 'Aborted.'; exit 0 }
    }
    if ($svc.Status -ne 'Stopped') {
        Write-Host "[uninstall] Stopping service..."
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        $svc.WaitForStatus('Stopped', [TimeSpan]::FromSeconds(30))
    }
    Write-Host "[uninstall] Removing service..."
    & sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 1
}

# Remove the Event Log source registration (idempotent).
$srcPath = "HKLM:\SYSTEM\CurrentControlSet\Services\EventLog\Application\ContragestSync"
if (Test-Path $srcPath) {
    Remove-Item -LiteralPath $srcPath -Recurse -Force
    Write-Host "[uninstall] Removed Event Log source."
}

# Remove the optional health-endpoint firewall rule (idempotent).
try {
    $null = & netsh.exe advfirewall firewall delete rule name='ContragestSync Health'
    Write-Host "[uninstall] Removed firewall rule (if present)."
}
catch { }

# Optional log cleanup.
if ($RemoveLogs) {
    if (-not $AppDir) { $AppDir = Split-Path -Parent $PSScriptRoot }
    $logDir = Join-Path $AppDir 'logs'
    if (Test-Path -LiteralPath $logDir) {
        Remove-Item -LiteralPath $logDir -Recurse -Force
        Write-Host "[uninstall] Deleted $logDir"
    }
}

Write-Host "Service '$ServiceName' removed." -ForegroundColor Green
