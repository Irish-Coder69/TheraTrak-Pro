Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$icon = Join-Path $root 'Theratrak-Pro.ico'
$mainPy = Join-Path $root 'main.py'
$installerPy = Join-Path $root 'installer\installer.py'
$versionJson = Join-Path $root 'version.json'
$distDir = Join-Path $root 'dist'
$buildDir = Join-Path $root 'build'
$releaseDir = Join-Path $root 'release'
$installerExe = Join-Path $releaseDir 'TheraTrak-Pro-Installer.exe'

if (-not (Test-Path $python)) {
    throw 'Python virtual environment not found at .venv\Scripts\python.exe'
}

Remove-Item $buildDir, $distDir, $releaseDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

$pyInstallerArgs = @(
    '-m', 'PyInstaller',
    '--noconfirm',
    '--clean',
    '--windowed',
    '--onefile',
    '--name', 'TheraTrak Pro',
    '--icon', $icon,
    '--collect-all', 'PIL',
    '--collect-all', 'reportlab',
    $mainPy
)

& $python @pyInstallerArgs

$installerArgs = @(
    '-m', 'PyInstaller',
    '--noconfirm',
    '--clean',
    '--windowed',
    '--onefile',
    '--name', 'TheraTrak-Pro-Installer',
    '--icon', $icon,
    '--distpath', $releaseDir,
    '--workpath', (Join-Path $buildDir 'installer'),
    '--specpath', $buildDir,
    '--add-data', ((Join-Path $distDir 'TheraTrak Pro.exe') + ';.'),
    '--add-data', ($icon + ';.'),
    '--add-data', ($versionJson + ';.'),
    $installerPy
)

& $python @installerArgs

Write-Host "Installer created at: $installerExe"