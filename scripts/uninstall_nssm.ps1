#requires -Version 5.1
<#
.SYNOPSIS
    Stops and removes the NSSM-based ContragestSync service.

.PARAMETER NssmPath
    Path to nssm.exe.  Defaults to nssm.exe on PATH.
#>
param([string]$NssmPath)

$ErrorActionPreference = 'Stop'
$ServiceName = 'ContragestSync'

$pr = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'This script must run from an elevated PowerShell.'
}

if (-not $NssmPath) {
    $cmd = Get-Command nssm.exe -ErrorAction SilentlyContinue
    if (-not $cmd) { throw 'nssm.exe not found; pass -NssmPath.' }
    $NssmPath = $cmd.Source
}

$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $svc) {
    Write-Host "Service '$ServiceName' is not installed."
    exit 0
}

if ($svc.Status -ne 'Stopped') {
    Write-Host '[nssm] Stopping service...'
    & $NssmPath stop $ServiceName | Out-Null
}

& $NssmPath remove $ServiceName confirm | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'nssm remove failed' }
Write-Host "Service '$ServiceName' removed." -ForegroundColor Green
