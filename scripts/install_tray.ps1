#requires -Version 5.1
<#
.SYNOPSIS
    Installs the Contragest system-tray agent (per-user autostart + elevated
    service-control tasks).

.DESCRIPTION
    Sets up everything the tray agent needs:

      * installs requirements-tray.txt (pystray, pillow, pywin32) into the venv,
      * registers the HKCU Run key so the agent auto-starts at user logon
        (tray icon only, hidden window - the user opens the app from the tray),
      * creates three SYSTEM scheduled tasks that perform elevated service
        control on behalf of the non-elevated tray agent:

            ContragestServiceControlStart    -> service_main.py tray-action start
            ContragestServiceControlStop     -> service_main.py tray-action stop
            ContragestServiceControlRestart  -> service_main.py tray-action restart

        These run silently as SYSTEM, so "Restart service" from the tray needs
        no UAC prompt.

    The ContragestSync *service* itself is installed separately with
    scripts\install_service.ps1 (it starts at boot for all users via the SCM).

.PARAMETER AppDir
    Directory containing tray_main.py and service_main.py.  Defaults to this
    script's parent.

.PARAMETER VenvPython
    venv python to install deps with and to register for the tasks.
    Defaults to $AppDir\.venv\Scripts\python.exe.

.PARAMETER SkipPip
    Do not run pip install (assume deps are present).

.PARAMETER NoStart
    Register autostart/tasks but do not launch the agent now.

.PARAMETER RestartAgent
    Stop any currently running tray agent (python/pythonw running tray_main.py)
    before launching the new one.

.PARAMETER TasksOnly
    Create ONLY the elevated SYSTEM control tasks (no Run key, no launch).
    Use this when UAC elevates to a *different* account than the one you log
    in with (then run the same script with -AutostartOnly as the interactive
    user afterwards).

.PARAMETER AutostartOnly
    Register ONLY the per-user HKCU Run key (+ optionally launch the agent).
    No elevation required.  Run as the interactive user you log in as.

.PARAMETER Silent
    Do not prompt; fail fast instead.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\install_tray.ps1 -RestartAgent

.EXAMPLE
    .\scripts\install_tray.ps1 -AppDir C:\Contragest -VenvPython C:\Contragest\.venv\Scripts\python.exe -Silent

.EXAMPLE
    # UAC elevates to a different admin account? Split the install:
    powershell -ExecutionPolicy Bypass -File .\scripts\install_tray.ps1 -TasksOnly     # elevated
    powershell -ExecutionPolicy Bypass -File .\scripts\install_tray.ps1 -AutostartOnly # your session
#>
param(
    [string]$AppDir,
    [string]$VenvPython,
    [switch]$SkipPip,
    [switch]$NoStart,
    [switch]$RestartAgent,
    [switch]$TasksOnly,
    [switch]$AutostartOnly,
    [switch]$Silent
)

$ErrorActionPreference = 'Stop'

$ServiceName   = 'ContragestSync'
$TaskPrefix    = 'ContragestServiceControl'
$RunKeyName    = 'ContragestTray'
$RunKeyPath    = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$AgentActions  = @('start', 'stop', 'restart')

function Write-Step([string]$msg) { Write-Host "[tray-install] $msg" -ForegroundColor Cyan }

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

function Register-ControlTask([string]$Verb) {
    # NOTE: tasks are created with schtasks.exe + inline XML, NOT with the
    # ScheduledTasks cmdlets: New-ScheduledTaskAction/Register-ScheduledTask
    # fail to bind (-Action : PSTypeName MSFT_TaskAction) under Windows
    # PowerShell 5.1 on Windows 11 build 26100+.  schtasks is deterministic
    # and works on every supported Windows version.
    #
    # Two schtasks quirks discovered during field deployment (Win11 26100):
    #  * a <Principals> block with <UserId>S-1-5-18</UserId> +
    #    <LogonType>ServiceAccount</LogonType> is REJECTED ("task XML contains a
    #    value that is incorrectly formatted or out of range") -> the principal
    #    is therefore passed on the command line with /RU SYSTEM instead.
    #  * /RL is not allowed together with /XML (only /S /U /P /RU /RP /F /IT
    #    /TN are) -> no /RL here; SYSTEM tasks are high-integrity anyway.
    $taskName = "$TaskPrefix$((Get-Culture).TextInfo.ToTitleCase($Verb))"
    $py = [Security.SecurityElement]::Escape($Python)
    $wd = [Security.SecurityElement]::Escape($AppDir)
    $xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Elevated $Verb of the ContragestSync service, triggered by the Contragest tray agent.</Description>
  </RegistrationInfo>
  <Triggers />
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>false</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <Hidden>true</Hidden>
    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$py</Command>
      <Arguments>service_main.py tray-action $Verb</Arguments>
      <WorkingDirectory>$wd</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@
    $tmpXml = Join-Path $env:TEMP "contragest-task-$Verb.xml"
    [System.IO.File]::WriteAllText($tmpXml, $xml, [System.Text.Encoding]::Unicode)
    try {
        $out = & schtasks.exe /Create /TN $taskName /XML $tmpXml /RU SYSTEM /F 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            throw "schtasks /Create failed for $taskName (exit $LASTEXITCODE): $out"
        }
        Write-Step "Registered task: $taskName"
    }
    finally {
        Remove-Item -LiteralPath $tmpXml -Force -ErrorAction SilentlyContinue
    }
}

function Get-Pythonw([string]$Python) {
    # pythonw.exe is required for autostart so no console window appears.
    # ChangeExtension('.exe') does nothing useful; we derive the path explicitly.
    $dir = [System.IO.Path]::GetDirectoryName($Python)
    $pw = [System.IO.Path]::Combine($dir, 'pythonw.exe')
    if (Test-Path -LiteralPath $pw) { return $pw }
    return $Python   # fallback to console interpreter (a console may flash)
}

function Set-AutostartRunKey {
    $pythonw = Get-Pythonw $Python
    $launcher = Join-Path $AppDir 'tray_main.py'
    $value = "`"$pythonw`" `"$launcher`""
    if (-not (Test-Path -LiteralPath $RunKeyPath)) {
        New-Item -Path $RunKeyPath -Force | Out-Null
    }
    Set-ItemProperty -Path $RunKeyPath -Name $RunKeyName -Value $value
    Write-Step "Autostart registered: $RunKeyName = $value"
}

function Stop-RunningAgent {
    $procs = Get-CimInstance Win32_Process |
        Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match 'tray_main\.py' }
    if ($procs) {
        foreach ($p in $procs) {
            Write-Step "Stopping running agent PID $($p.ProcessId)"
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
}

# ── 0. Preflight ────────────────────────────────────────────────────────────
if ($TasksOnly -and $AutostartOnly) {
    throw '-TasksOnly and -AutostartOnly are mutually exclusive.'
}
if (-not $AutostartOnly) {
    # Task creation requires admin; plain autostart does not.
    Assert-Admin
}
if (-not $AppDir) { $AppDir = Split-Path -Parent $PSScriptRoot }
$AppDir = (Resolve-Path -LiteralPath $AppDir).Path
if (-not (Test-Path -LiteralPath (Join-Path $AppDir 'tray_main.py'))) {
    throw "tray_main.py not found under $AppDir"
}
if (-not (Test-Path -LiteralPath (Join-Path $AppDir 'service_main.py'))) {
    throw "service_main.py not found under $AppDir (required for the control tasks)"
}

$Python = Find-Python $AppDir $VenvPython
Write-Step "Using Python: $Python"
Write-Step "App dir    : $AppDir"

# ── 1. Dependencies ─────────────────────────────────────────────────────────
if (-not $SkipPip) {
    Write-Step 'Installing requirements-tray.txt...'
    & $Python -m pip install -r (Join-Path $AppDir 'requirements-tray.txt')
    if ($LASTEXITCODE -ne 0) { throw "pip install failed (exit $LASTEXITCODE)" }
}

# ── 2. Elevated control tasks (SYSTEM) ─────────────────────────────────────
# Skipped in -AutostartOnly mode (no elevation needed for autostart).
if (-not $AutostartOnly) {
    foreach ($a in $AgentActions) { Register-ControlTask $a }
}

# ── 3. Per-user autostart (HKCU Run key) ───────────────────────────────────
# IMPORTANT: HKCU refers to whoever runs this script.  When UAC elevates to a
# *different* account (common on shared PCs), the elevated process would write
# the Run key into the wrong hive.  Use -TasksOnly elevated, then -AutostartOnly
# as the interactive user, or run the full install from your own elevated console.
if (-not $TasksOnly) {
    Set-AutostartRunKey
}

# ── 4. Launch now (optional) ───────────────────────────────────────────────
if (-not $TasksOnly) {
    if ($RestartAgent) { Stop-RunningAgent }
    if ($NoStart) {
        Write-Step 'Skipping agent launch (-NoStart). It will start at next logon.'
    }
    else {
        $pythonw = Get-Pythonw $Python
        $launcher = Join-Path $AppDir 'tray_main.py'
        Start-Process -FilePath $pythonw -ArgumentList "`"$launcher`"" -WorkingDirectory $AppDir
        Start-Sleep -Milliseconds 400
        $proc = Get-CimInstance Win32_Process |
            Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match 'tray_main\.py' } |
            Sort-Object CreationDate -Descending | Select-Object -First 1
        if ($proc) { Write-Step "Tray agent launched (PID $($proc.ProcessId))" }
        else       { Write-Step "Tray agent launched (PID unknown)" }
    }
}

# ── 5. Summary ─────────────────────────────────────────────────────────────
$mode = if ($TasksOnly) { 'TasksOnly (elevated part)' }
        elseif ($AutostartOnly) { 'AutostartOnly (user part)' }
        else { 'Full install' }
Write-Host ''
Write-Host "Tray agent installation summary ($mode):" -ForegroundColor Green
if (-not $AutostartOnly) {
    Write-Host "  Control tasks        : $TaskPrefix Start / Stop / Restart"
}
if (-not $TasksOnly) {
    Write-Host "  Autostart (HKCU Run) : $RunKeyName"
}
Write-Host '  Service (separate)   : ContragestSync  -> scripts\install_service.ps1'
Write-Host ''
Write-Host 'Verify:'
Write-Host '  Get-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Run -Name ContragestTray'
Write-Host '  Get-ScheduledTask ContragestServiceControl*'
Write-Host '  (reboot or re-logon, then check the tray icon next to the clock)'
