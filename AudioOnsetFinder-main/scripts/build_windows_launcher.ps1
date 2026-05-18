$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$launcherScript = Join-Path $repoRoot "GUI\launch_gui.py"
$iconPath = Join-Path $repoRoot "GUI\DesktopIcon.ico"
$buildRoot = Join-Path $repoRoot "build\windows-launcher"
$specPath = Join-Path $buildRoot "spec"
$workPath = Join-Path $buildRoot "work"
$distPath = Join-Path $repoRoot "GUI"

if (-not (Test-Path $launcherScript)) {
    throw "Launcher script not found: $launcherScript"
}

if (-not (Test-Path $iconPath)) {
    throw "Windows icon not found: $iconPath"
}

New-Item -ItemType Directory -Force -Path $buildRoot, $specPath, $workPath | Out-Null

python -m pip install --upgrade pyinstaller

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "BioacousticsRhythmPipeline" `
    --icon "$iconPath" `
    --specpath "$specPath" `
    --workpath "$workPath" `
    --distpath "$distPath" `
    "$launcherScript"

Write-Host "Built launcher exe:" (Join-Path $distPath "BioacousticsRhythmPipeline.exe")