#requires -Version 5.1
<#
.SYNOPSIS
    Installs Contragest as a native Windows service (pywin32 + SCM).

.DESCRIPTION
    Production-grade installer that:
      * creates/updates the "ContragestSync" service via pywin32
        (auto-start, configurable service account),
      * grants "Logon as a service" to the service account,
      * sets SCM recovery actions (self-restart on crash/hang) via sc.exe,
      * sets the LanmanWorkstation dependency (UNC share access),
      * grants the service account least-privilege ACLs on the app/log dirs
        and (optionally) on the data share path,
      * registers the Event Log source and optionally opens the firewall for
        the HTTP health endpoint.

.PARAMETER AppDir
    Directory that contains service_main.py.  Defaults to this script's parent.

.PARAMETER VenvPython
    Path to the Python interpreter to run the service with.  Defaults to
    $AppDir\.venv\Scripts\python.exe, then to python.exe on PATH.

.PARAMETER ServiceAccount
    Account to run the service under (DOMAIN\user or .\user).  Default:
    LocalSystem (uses the computer account for network access).

.PARAMETER ServicePassword
    Password for ServiceAccount (required when a non-LocalSystem account is
    used in silent mode; otherwise you are prompted).

.PARAMETER Startup
    Service start type: auto | delayed-auto | manual.  Default: auto.

.PARAMETER DataSharePath
    Optional UNC/local path of the shared database folder to grant the service
    account access to (e.g. \\srv-hotix\pointage\Contragest).

.PARAMETER HealthPort
    Optional port of the HTTP /health endpoint.  When set, a firewall rule
    (TCP inbound) is created and the service is started with --health-port.

.PARAMETER SyncInterval
    Seconds between attendance download passes (default 30, min 10).

.PARAMETER Force
    Reinstall/update the service if it already exists.

.PARAMETER Silent
    Do not prompt; fail fast instead.

.PARAMETER NoStart
    Create/configure the service but do not start it.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\install_service.ps1 -Silent

.EXAMPLE
    .\scripts\install_service.ps1 -ServiceAccount .\contragest-svc `
        -ServicePassword 'P@ssw0rd!' -DataSharePath '\\srv-hotix\pointage\Contragest'
#>
param(
    [string]$AppDir,
    [string]$VenvPython,
    [string]$ServiceAccount,
    [string]$ServicePassword,
    [ValidateSet('auto', 'delayed-auto', 'manual')][string]$Startup = 'auto',
    [string]$DataSharePath,
    [int]$HealthPort = 0,
    [int]$SyncInterval = 30,
    [switch]$Force,
    [switch]$Silent,
    [switch]$NoStart
)

$ErrorActionPreference = 'Stop'
$ServiceName = 'ContragestSync'

function Write-Step([string]$msg) { Write-Host "[install] $msg" -ForegroundColor Cyan }

function Assert-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $pr = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'This script must run from an elevated PowerShell.'
    }
}

function Find-Python([string]$AppDir, [string]$VenvPython) {
    if ($VenvPython) {
        if (-not (Test-Path -LiteralPath $VenvPython)) { throw "VenvPython not found: $VenvPython" }
        return (Resolve-Path -LiteralPath $VenvPython).Path
    }
    $candidates = @(
        (Join-Path $AppDir '.venv\Scripts\python.exe'),
        (Join-Path $AppDir '.venv\python.exe'),
        'python.exe'
    )
    foreach ($c in $candidates) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
        if (Test-Path -LiteralPath $c) { return (Resolve-Path -LiteralPath $c).Path }
    }
    throw 'Could not locate a Python interpreter. Pass -VenvPython explicitly.'
}

function Grant-LogonAsService([string]$Account) {
    # Adds "Log on as a service" (SeServiceLogonRight) using secedit (admin).
    $tmp = Join-Path $env:TEMP ("secpol-{0}.inf" -f [guid]::NewGuid())
    $db  = Join-Path $env:TEMP ("secedit-{0}.sdb" -f [guid]::NewGuid())
    try {
        & secedit.exe /export /cfg $tmp /areas USER_RIGHTS | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "secedit /export failed (exit $LASTEXITCODE)" }

        $lines = [System.Collections.Generic.List[string]]::new()
        $lines.AddRange([System.IO.File]::ReadAllLines($tmp, [System.Text.Encoding]::Unicode))
        $pattern = '^\s*SeServiceLogonRight\s*='
        $found = $false
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match $pattern) {
                $found = $true
                $members = ($lines[$i] -split '=', 2)[1] -split ','
                $members = $members | ForEach-Object { $_.Trim() } | Where-Object { $_ -and $_ -ne $Account }
                $lines[$i] = 'SeServiceLogonRight = ' + ($members + $Account) -join ','
            }
        }
        if (-not $found) {
            $idx = [array]::IndexOf($lines, '[Privilege Rights]')
            if ($idx -lt 0) { throw 'secedit export did not contain [Privilege Rights]' }
            $lines.Insert($idx + 1, 'SeServiceLogonRight = ' + $Account)
        }
        [System.IO.File]::WriteAllLines($tmp, $lines.ToArray(), [System.Text.Encoding]::Unicode)

        & secedit.exe /configure /db $db /cfg $tmp /areas USER_RIGHTS | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "secedit /configure failed (exit $LASTEXITCODE)" }
        Write-Step "Granted 'Log on as a service' to $Account"
    }
    finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $db -Force -ErrorAction SilentlyContinue
    }
}

function Grant-FolderAccess([string]$Account, [string]$Path, [string]$Rights) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return }
    try {
        $acl = Get-Acl -LiteralPath $Path
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
            $Account, $Rights, 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
        Set-Acl -LiteralPath $Path -AclObject $acl
        Write-Step "Granted $Rights on $Path to $Account"
    }
    catch {
        Write-Warning "Could not set ACL on $Path : $_"
    }
}

function Invoke-RequirePassword([string]$Account) {
    if ($ServicePassword) { return $ServicePassword }
    if ($Silent) { throw "ServicePassword is required for account $Account in silent mode." }
    $sec = Read-Host -AsSecureString "Password for $Account"
    return [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
}

# ── 0. Preflight ────────────────────────────────────────────────────────────
Assert-Admin
if (-not $AppDir) { $AppDir = Split-Path -Parent $PSScriptRoot }
$AppDir = (Resolve-Path -LiteralPath $AppDir).Path
if (-not (Test-Path -LiteralPath (Join-Path $AppDir 'service_main.py'))) {
    throw "service_main.py not found under $AppDir"
}

$Existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($Existing -and -not $Force) {
    throw "Service '$ServiceName' already exists. Re-run with -Force to update."
}

$Python = Find-Python $AppDir $VenvPython
Write-Step "Using Python: $Python"
Write-Step "App dir    : $AppDir"

# ── 1. Service account ─────────────────────────────────────────────────────
$UseSystem = -not $ServiceAccount -or $ServiceAccount -ieq 'LocalSystem'
$Win32User = @()
if ($UseSystem) {
    Write-Step 'Running as LocalSystem (computer account used for network access)'
}
else {
    $winArgs = @('--username', $ServiceAccount)
    $pwd = Invoke-RequirePassword $ServiceAccount
    $winArgs += @('--password', $pwd)
    Grant-LogonAsService $ServiceAccount
    Write-Step "Service account: $ServiceAccount"
}

# ── 2. Create / update the service (pywin32) ───────────────────────────────
$installArgs = @('service_main.py', 'install', '--startup', $Startup) + $winArgs
Write-Step "Running: $Python $($installArgs -join ' ')"
Push-Location $AppDir
try {
    & $Python @installArgs
    if ($LASTEXITCODE -ne 0) { throw "pywin32 install failed (exit $LASTEXITCODE)" }
}
finally { Pop-Location }

# ── 3. SCM configuration (sc.exe) ──────────────────────────────────────────
Write-Step 'Configuring SCM recovery actions (restart 60s / 120s / 300s)'
& sc.exe failure $ServiceName reset= 86400 actions= restart/60000/restart/120000/restart/300000 | Out-Null
& sc.exe failureflag $ServiceName 1 | Out-Null
& sc.exe config $ServiceName depend= LanmanWorkstation | Out-Null
& sc.exe description $ServiceName 'Keeps Contragest attendance data current 24/7: ZK machine sync, contract alerts, daily audit/auto-correction and clock sync.' | Out-Null
if ($Startup -eq 'delayed-auto') {
    & sc.exe config $ServiceName start= delayed-auto | Out-Null
}

# ── 4. Least-privilege ACLs ────────────────────────────────────────────────
if (-not $UseSystem) {
    Grant-FolderAccess $ServiceAccount (Join-Path $AppDir 'logs') 'Modify'
    Grant-FolderAccess $ServiceAccount $AppDir 'ReadAndExecute'
    if ($DataSharePath) { Grant-FolderAccess $ServiceAccount $DataSharePath 'Modify' }
}
elseif ($DataSharePath) {
    Write-Warning "Data share ACLs for the computer account ($env:COMPUTERNAME`$) must be granted on the share server."
}

# ── 5. Optional HTTP health endpoint + firewall rule ───────────────────────
# Engine tuning is stored in service_config.json (read by the engine at
# startup), NOT in the SCM binPath - binPath must stay the bare script so the
# SCM startup path (no arguments -> service dispatcher) keeps working.
$cfgPath = Join-Path $AppDir 'service_config.json'
$cfg = @{}
if (Test-Path -LiteralPath $cfgPath) {
    try { $cfg = Get-Content -LiteralPath $cfgPath -Raw | ConvertFrom-Json -AsHashtable }
    catch { $cfg = @{} }
}
if ($HealthPort -gt 0) {
    $cfg['health_port'] = $HealthPort
    try {
        & netsh.exe advfirewall firewall add rule name='ContragestSync Health' `
            dir=in action=allow protocol=TCP localport=$HealthPort | Out-Null
        Write-Step "Firewall rule added for TCP $HealthPort"
    }
    catch { Write-Warning "Firewall rule not added: $_" }
}
if ($SyncInterval -gt 0) {
    $cfg['sync_interval_seconds'] = $SyncInterval
}
if ($cfg.Count -gt 0) {
    $cfg | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $cfgPath -Encoding utf8
    Write-Step "Wrote $cfgPath"
}

# ── 6. Start ───────────────────────────────────────────────────────────────
Write-Step 'Installing ContragestSync service... done.'
if ($NoStart) {
    Write-Step 'Skipping service start (-NoStart).'
}
else {
    Write-Step 'Starting service...'
    & sc.exe start $ServiceName | Out-Null
    Start-Sleep -Seconds 2
    $svc = Get-Service -Name $ServiceName
    if ($svc.Status -ne 'Running') {
        throw "Service did not reach Running. Check Event Viewer (source ContragestSync) and logs\contragest.log"
    }
    Write-Step "Service '$ServiceName' is RUNNING."
}

# ── 7. Summary ─────────────────────────────────────────────────────────────
Write-Host ''
Write-Host 'Installation summary:' -ForegroundColor Green
Write-Host "  Service       : $ServiceName"
Write-Host "  Display name  : Contragest Sync Service"
Write-Host "  Python        : $Python"
Write-Host "  App dir       : $AppDir"
Write-Host "  Startup       : $Startup"
$acctLabel = if ($UseSystem) { 'LocalSystem' } else { $ServiceAccount }
Write-Host "  Account       : $acctLabel"
if ($HealthPort -gt 0) {
    Write-Host "  Health URL    : http://127.0.0.1:$HealthPort/health"
}
Write-Host ''
Write-Host 'Useful commands:' -ForegroundColor Green
Write-Host '  python service_main.py status       -> SCM status'
Write-Host '  python service_main.py healthcheck  -> heartbeat freshness'
Write-Host '  .\scripts\uninstall_service.ps1     -> remove the service'
