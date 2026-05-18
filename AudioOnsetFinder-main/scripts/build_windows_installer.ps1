$ErrorActionPreference = "Stop"

function Get-IsccPath {
    $command = Get-Command iscc -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(@(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    ) | Where-Object { $_ -and (Test-Path $_) })

    if ($candidates.Count -gt 0) {
        return $candidates[0]
    }

    return $null
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$launcherBuildScript = Join-Path $repoRoot "scripts\build_windows_launcher.ps1"
$installerScript = Join-Path $repoRoot "installer\BioacousticsRhythmPipeline.iss"
$outputDir = Join-Path $repoRoot "build\windows-installer"
$appVersion = Get-Date -Format "yyyy.MM.dd"

if (-not (Test-Path $launcherBuildScript)) {
    throw "Launcher build script not found: $launcherBuildScript"
}

if (-not (Test-Path $installerScript)) {
    throw "Installer definition not found: $installerScript"
}

& powershell -ExecutionPolicy Bypass -File $launcherBuildScript

$isccPath = Get-IsccPath
if (-not $isccPath) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Inno Setup is not installed and winget is unavailable. Install Inno Setup 6, then re-run this script."
    }

    winget install --id JRSoftware.InnoSetup --accept-package-agreements --accept-source-agreements --disable-interactivity
    $isccPath = Get-IsccPath
}

if (-not $isccPath) {
    throw "Could not locate ISCC.exe after installing Inno Setup."
}

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$isccProcess = Start-Process -FilePath ([string]$isccPath) `
    -ArgumentList @(
        "/DRepoRoot=$repoRoot",
        "/DOutputDir=$outputDir",
        "/DAppVersion=$appVersion",
        $installerScript
    ) `
    -Wait `
    -NoNewWindow `
    -PassThru

if ($isccProcess.ExitCode -ne 0) {
    throw "ISCC.exe failed with exit code $($isccProcess.ExitCode)."
}

Write-Host "Built installer:" (Join-Path $outputDir "BioacousticsRhythmPipelineSetup.exe")