param(
    [Parameter(Position = 0)]
    [string]$Command = 'help',

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

$smokeTests = @(
    'GUI/test_audio_viewer.py'
    'GUI/test_onset_editor.py'
    'tests/test_onset_routing.py'
    'tests/test_onset_batching.py'
    'tests/test_onset_postprocessing.py'
    'tests/test_beat_tempo_engine.py'
)

$widerTests = @(
    'GUI/test_audio_viewer.py'
    'GUI/test_onset_editor.py'
    'tests/test_save_selections.py'
    'tests/test_focus_mode.py'
    'tests/test_signal_profiles.py'
    'tests/test_mfcc_template.py'
    'tests/test_recommendation_analysis.py'
    'tests/test_onset_layers.py'
    'tests/test_selection.py'
    'tests/test_onset_routing.py'
    'tests/test_onset_batching.py'
    'tests/test_onset_postprocessing.py'
    'tests/test_onset_metrics.py'
    'tests/test_onset_metadata.py'
    'tests/test_onset_exports.py'
    'tests/test_pipeline_file_selection.py'
    'tests/test_spectral_matching.py'
    'tests/test_excel_onset_io.py'
    'tests/test_phase3.py'
    'tests/test_phase4_integration.py'
    'tests/test_new_analyses.py'
    'tests/test_dual_profile.py'
    'tests/test_beat_tempo_engine.py'
)

function Show-Usage {
    @'
Usage: powershell -ExecutionPolicy Bypass -File scripts/refactor_guardrails.ps1 <command> [extra args]

Commands:
  doctor           Show the chosen interpreter and verify core GUI dependencies.
  launch           Launch the GUI with the chosen interpreter.
  launch-offscreen Launch the GUI in offscreen mode for startup validation.
  smoke            Run the representative refactor smoke suite.
  wider            Run the wider regression sweep.
  phase12          Run tests/test_phase12.py directly.
  python           Run the chosen interpreter with the remaining arguments.

Environment:
  BIOACOUSTICS_PYTHON   Override the detected project interpreter.
  QT_QPA_PLATFORM       Override the default offscreen Qt platform for test commands.
'@ | Write-Host
}

function Test-ExecutablePath {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $false
    }
    return (Test-Path -LiteralPath $Path)
}

function Resolve-Python {
    if ($env:BIOACOUSTICS_PYTHON) {
        if (Test-ExecutablePath $env:BIOACOUSTICS_PYTHON) {
            return $env:BIOACOUSTICS_PYTHON
        }
        throw "BIOACOUSTICS_PYTHON is set but not executable: $($env:BIOACOUSTICS_PYTHON)"
    }

    $candidates = @(
        (Join-Path $projectRoot '.conda\python.exe'),
        (Join-Path $projectRoot '.conda\Scripts\python.exe'),
        (Join-Path $projectRoot '.conda\bin\python'),
        (Join-Path $HOME 'anaconda3\envs\rhythm_env\python.exe'),
        (Join-Path $HOME 'miniconda3\envs\rhythm_env\python.exe'),
        (Join-Path $HOME 'anaconda3/envs/rhythm_env/bin/python'),
        (Join-Path $HOME 'miniconda3/envs/rhythm_env/bin/python'),
        (Join-Path $env:LOCALAPPDATA 'anaconda3\envs\rhythm_env\python.exe'),
        'C:\ProgramData\anaconda3\envs\rhythm_env\python.exe',
        'C:\ProgramData\miniconda3\envs\rhythm_env\python.exe',
        '/opt/anaconda3/envs/rhythm_env/bin/python',
        '/opt/miniconda3/envs/rhythm_env/bin/python'
    )

    if ($env:CONDA_PREFIX) {
        $candidates = @(
            (Join-Path $env:CONDA_PREFIX 'python.exe'),
            (Join-Path $env:CONDA_PREFIX 'bin/python')
        ) + $candidates
    }

    foreach ($candidate in $candidates) {
        if (Test-ExecutablePath $candidate) {
            return $candidate
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return $pythonCommand.Source
    }

    $python3Command = Get-Command python3 -ErrorAction SilentlyContinue
    if ($python3Command) {
        return $python3Command.Source
    }

    throw "Could not find a usable project interpreter. Set BIOACOUSTICS_PYTHON to override."
}

function Invoke-ProjectPython {
    param(
        [string]$PythonBin,
        [string[]]$Arguments,
        [hashtable]$ExtraEnv = @{}
    )

    Push-Location $projectRoot
    try {
        $previous = @{}
        foreach ($key in $ExtraEnv.Keys) {
            $previous[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
            [Environment]::SetEnvironmentVariable($key, $ExtraEnv[$key], 'Process')
        }

        $commandArgs = @($Arguments)
        & $PythonBin $commandArgs
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
    finally {
        foreach ($key in $ExtraEnv.Keys) {
            [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process')
        }
        Pop-Location
    }
}

$pythonBin = Resolve-Python
$commandName = $Command
$extraArgs = @($CommandArgs)
$qtPlatform = if ($env:QT_QPA_PLATFORM) { $env:QT_QPA_PLATFORM } else { 'offscreen' }
$projectPythonPath = Join-Path $projectRoot 'GUI'

switch ($commandName) {
    'help' {
        Show-Usage
    }
    '-h' {
        Show-Usage
    }
    '--help' {
        Show-Usage
    }
    'doctor' {
        & $pythonBin -V
        Write-Host "Python: $pythonBin"
        & $pythonBin -c 'import PyQt6, pyqtgraph, matplotlib, librosa, pandas, numpy; print("gui-deps-ok")'
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
    'launch' {
        Invoke-ProjectPython -PythonBin $pythonBin -Arguments @('GUI/pipeline_gui.py') + $extraArgs -ExtraEnv @{
            PYTHONPATH = $projectPythonPath
        }
    }
    'launch-offscreen' {
        Invoke-ProjectPython -PythonBin $pythonBin -Arguments @('GUI/pipeline_gui.py') + $extraArgs -ExtraEnv @{
            PYTHONPATH = $projectPythonPath
            QT_QPA_PLATFORM = $qtPlatform
        }
    }
    'smoke' {
        Invoke-ProjectPython -PythonBin $pythonBin -Arguments @('-m', 'pytest', '-q') + $smokeTests + $extraArgs -ExtraEnv @{
            PYTHONPATH = $projectPythonPath
            QT_QPA_PLATFORM = $qtPlatform
        }
    }
    'wider' {
        Invoke-ProjectPython -PythonBin $pythonBin -Arguments @('-m', 'pytest', '-q') + $widerTests + $extraArgs -ExtraEnv @{
            PYTHONPATH = $projectPythonPath
            QT_QPA_PLATFORM = $qtPlatform
        }
    }
    'phase12' {
        Invoke-ProjectPython -PythonBin $pythonBin -Arguments @('tests/test_phase12.py') + $extraArgs -ExtraEnv @{
            PYTHONPATH = $projectPythonPath
            QT_QPA_PLATFORM = $qtPlatform
        }
    }
    'python' {
        $pythonArgs = @($extraArgs)
        & $pythonBin $pythonArgs
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
    default {
        Show-Usage
        exit 1
    }
}