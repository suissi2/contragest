#requires -Version 5.1
<#
.SYNOPSIS
    Builds the ContragestSync Windows service executable with PyInstaller.

.DESCRIPTION
    * installs requirements-service.txt (pywin32, pyinstaller) into the venv,
    * runs pyinstaller against packaging\contragest-service.spec (onedir),
    * copies the bootstrap contragest.db (holding app_config.db_custom_path)
      into the dist folder if present,
    * prints deployment instructions.

.PARAMETER AppDir
    Repository root (defaults to this script's parent).

.PARAMETER VenvPython
    venv python to build with (default $AppDir\.venv\Scripts\python.exe).

.PARAMETER DistDir
    Output directory (default $AppDir\dist).
#>
param(
    [string]$AppDir,
    [string]$VenvPython,
    [string]$DistDir
)

$ErrorActionPreference = 'Stop'

if (-not $AppDir) { $AppDir = Split-Path -Parent $PSScriptRoot }
$AppDir = (Resolve-Path -LiteralPath $AppDir).Path
if (-not $VenvPython) { $VenvPython = Join-Path $AppDir '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "venv python not found: $VenvPython"
}
if (-not $DistDir) { $DistDir = Join-Path $AppDir 'dist' }

Write-Host "[build] venv python : $VenvPython"
Write-Host "[build] installing requirements-service.txt..."
& $VenvPython -m pip install -r (Join-Path $AppDir 'requirements-service.txt')
if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }

Write-Host "[build] running PyInstaller..."
Push-Location $AppDir
try {
    & $VenvPython -m PyInstaller (Join-Path $AppDir 'packaging\contragest-service.spec') `
        --noconfirm --distpath $DistDir --workpath (Join-Path $AppDir 'build')
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed (exit $LASTEXITCODE)" }
}
finally { Pop-Location }

$exe = Join-Path $DistDir 'ContragestSync\ContragestSync.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    throw "Expected exe not found: $exe"
}

# Copy the bootstrap DB (holds app_config.db_custom_path -> network DB).
$srcDb = Join-Path $AppDir 'contragest.db'
$dstDb = Join-Path $DistDir 'ContragestSync\contragest.db'
if (Test-Path -LiteralPath $srcDb) {
    Copy-Item -LiteralPath $srcDb -Destination $dstDb -Force
    Write-Host "[build] Copied bootstrap contragest.db next to the exe."
    Write-Warning 'Verify the bootstrap DB points at the real network DB (app_config.db_custom_path) before deploying!'
}

Write-Host ''
Write-Host 'Build complete:' -ForegroundColor Green
Write-Host "  $exe"
Write-Host ''
Write-Host 'Deploy:'
Write-Host '  1. Copy the ContragestSync folder to the server.'
Write-Host '  2. If a service account is used, grant it access to the data share.'
Write-Host "  3. Run: powershell -File scripts\install_service.ps1 -AppDir '<server path>\ContragestSync' [-ServiceAccount DOMAIN\user -ServicePassword ***]"
Write-Host '  4. Monitor: <exe dir>\service_main.py status / healthcheck'
