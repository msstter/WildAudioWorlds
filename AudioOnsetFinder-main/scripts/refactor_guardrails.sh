#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
PROJECT_PYTHON_POSIX="${PROJECT_ROOT}/.conda/bin/python"
PROJECT_PYTHON_WINDOWS="${PROJECT_ROOT}/.conda/Scripts/python.exe"

SMOKE_TESTS=(
  GUI/test_audio_viewer.py
  GUI/test_onset_editor.py
  tests/test_onset_routing.py
  tests/test_onset_batching.py
  tests/test_onset_postprocessing.py
  tests/test_beat_tempo_engine.py
)

WIDER_TESTS=(
  GUI/test_audio_viewer.py
  GUI/test_onset_editor.py
  tests/test_save_selections.py
  tests/test_focus_mode.py
  tests/test_signal_profiles.py
  tests/test_mfcc_template.py
  tests/test_recommendation_analysis.py
  tests/test_onset_layers.py
  tests/test_selection.py
  tests/test_onset_routing.py
  tests/test_onset_batching.py
  tests/test_onset_postprocessing.py
  tests/test_onset_metrics.py
  tests/test_onset_metadata.py
  tests/test_onset_exports.py
  tests/test_pipeline_file_selection.py
  tests/test_spectral_matching.py
  tests/test_excel_onset_io.py
  tests/test_phase3.py
  tests/test_phase4_integration.py
  tests/test_new_analyses.py
  tests/test_dual_profile.py
  tests/test_beat_tempo_engine.py
)

usage() {
  cat <<'EOF'
Usage: bash scripts/refactor_guardrails.sh <command> [extra args]

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
EOF
}

is_usable_python() {
  local candidate=${1:-}
  [[ -n "${candidate}" && ( -x "${candidate}" || -f "${candidate}" ) ]]
}

resolve_python() {
  if [[ -n "${BIOACOUSTICS_PYTHON:-}" ]]; then
    if is_usable_python "${BIOACOUSTICS_PYTHON}"; then
      printf '%s\n' "${BIOACOUSTICS_PYTHON}"
      return
    fi
    echo "BIOACOUSTICS_PYTHON is set but not executable: ${BIOACOUSTICS_PYTHON}" >&2
    exit 1
  fi

  local candidates=()

  if [[ -n "${CONDA_PREFIX:-}" ]]; then
    candidates+=(
      "${CONDA_PREFIX}/bin/python"
      "${CONDA_PREFIX}/python.exe"
    )
  fi

  candidates+=(
    "${PROJECT_PYTHON_POSIX}"
    "${PROJECT_PYTHON_WINDOWS}"
    "${HOME}/anaconda3/envs/rhythm_env/bin/python"
    "${HOME}/miniconda3/envs/rhythm_env/bin/python"
    "${HOME}/anaconda3/envs/rhythm_env/python.exe"
    "${HOME}/miniconda3/envs/rhythm_env/python.exe"
    "/opt/anaconda3/envs/rhythm_env/bin/python"
    "/opt/miniconda3/envs/rhythm_env/bin/python"
    "/c/ProgramData/anaconda3/envs/rhythm_env/python.exe"
    "/c/ProgramData/miniconda3/envs/rhythm_env/python.exe"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    if is_usable_python "${candidate}"; then
      printf '%s\n' "${candidate}"
      return
    fi
  done

  candidate=$(command -v python3 2>/dev/null || true)
  if [[ -n "${candidate}" ]]; then
    printf '%s\n' "${candidate}"
    return
  fi

  candidate=$(command -v python 2>/dev/null || true)
  if [[ -n "${candidate}" ]]; then
    printf '%s\n' "${candidate}"
    return
  fi

  echo "Could not find a usable project interpreter." >&2
  echo "Expected one of:" >&2
  for candidate in "${candidates[@]}"; do
    echo "  ${candidate}" >&2
  done
  echo "Set BIOACOUSTICS_PYTHON to override." >&2
  exit 1
}

PYTHON_BIN=$(resolve_python)

run_pytest() {
  (
    cd "${PROJECT_ROOT}"
    PYTHONPATH="${PROJECT_ROOT}/GUI" \
    QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" \
    "${PYTHON_BIN}" -m pytest -q "$@"
  )
}

run_phase12() {
  (
    cd "${PROJECT_ROOT}"
    PYTHONPATH="${PROJECT_ROOT}/GUI" \
    QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" \
    "${PYTHON_BIN}" tests/test_phase12.py "$@"
  )
}

command_name=${1:-help}

case "${command_name}" in
  help|-h|--help)
    usage
    ;;
  doctor)
    "${PYTHON_BIN}" -V
    echo "Python: ${PYTHON_BIN}"
    "${PYTHON_BIN}" -c 'import PyQt6, pyqtgraph, matplotlib, librosa, pandas, numpy; print("gui-deps-ok")'
    ;;
  launch)
    shift
    cd "${PROJECT_ROOT}"
    PYTHONPATH="${PROJECT_ROOT}/GUI" "${PYTHON_BIN}" GUI/pipeline_gui.py "$@"
    ;;
  launch-offscreen)
    shift
    cd "${PROJECT_ROOT}"
    PYTHONPATH="${PROJECT_ROOT}/GUI" \
    QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" \
    "${PYTHON_BIN}" GUI/pipeline_gui.py "$@"
    ;;
  smoke)
    shift
    run_pytest "${SMOKE_TESTS[@]}" "$@"
    ;;
  wider)
    shift
    run_pytest "${WIDER_TESTS[@]}" "$@"
    ;;
  phase12)
    shift
    run_phase12 "$@"
    ;;
  python)
    shift
    exec "${PYTHON_BIN}" "$@"
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac