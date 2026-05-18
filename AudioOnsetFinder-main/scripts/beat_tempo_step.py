"""Compatibility entrypoint for the beat and tempo pipeline step."""

import os
import sys

try:
    from .beat_tempo_engine import (
        AUDIO_EXTENSIONS,
        BeatTempoConfig,
        append_summary_row,
        ensure_column,
        find_audio_files,
        find_summary_row,
        format_times,
        load_or_create_workbook,
        plp_local_maxima,
        process_file as process_beat_tempo_file,
        run_beat_tempo_step,
        safe_scalar,
        write_summary_columns,
        ws_header_map,
    )
except ImportError:
    from beat_tempo_engine import (
        AUDIO_EXTENSIONS,
        BeatTempoConfig,
        append_summary_row,
        ensure_column,
        find_audio_files,
        find_summary_row,
        format_times,
        load_or_create_workbook,
        plp_local_maxima,
        process_file as process_beat_tempo_file,
        run_beat_tempo_step,
        safe_scalar,
        write_summary_columns,
        ws_header_map,
    )


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_SCRIPT_DIR)


def _resolve_output_excel_path(
    beat_tempo_cfg: dict,
    extractor_cfg: dict,
    current_path: str,
) -> str:
    """Prefer the beat-tempo workbook, but reuse the extractor workbook when blank."""
    beat_tempo_path = str(beat_tempo_cfg.get("output_excel_path", current_path) or "").strip()
    if beat_tempo_path:
        return beat_tempo_path
    extractor_path = str(extractor_cfg.get("output_excel_path", current_path) or "").strip()
    if extractor_path:
        return extractor_path
    return current_path

audio_folder = os.path.join(_PROJECT_DIR, "audioFiles")
output_excel_path = ""
output_sheet_name = "Beat-Tempo"
BEAT_HOP_LENGTH = 512
BEAT_START_BPM = 120.0
BEAT_TIGHTNESS = 100.0
BEAT_TRIM = True
BEAT_BPM_OVERRIDE = 0.0
PLP_HOP_LENGTH = 512
PLP_WIN_LENGTH = 384
PLP_TEMPO_MIN = 30.0
PLP_TEMPO_MAX = 300.0
EXPORT_PULSE_DETAIL = False
DERIVE_PLP_PEAKS = True
PLP_PEAK_MIN_SPACING_MS = 100

_config_path = os.path.join(_PROJECT_DIR, "pipeline_config.json")
if os.path.isfile(_config_path):
    import json as _json

    with open(_config_path, encoding="utf-8") as _f:
        _all_cfg = _json.load(_f)
    _cfg = _all_cfg.get("beat_tempo", {})
    _extractor_cfg = _all_cfg.get("extractor", {})
    audio_folder = _cfg.get("audio_folder", audio_folder)
    output_excel_path = _resolve_output_excel_path(
        _cfg,
        _extractor_cfg,
        output_excel_path,
    )
    output_sheet_name = _cfg.get("output_sheet_name", output_sheet_name)
    BEAT_HOP_LENGTH = int(_cfg.get("BEAT_HOP_LENGTH", BEAT_HOP_LENGTH))
    BEAT_START_BPM = float(_cfg.get("BEAT_START_BPM", BEAT_START_BPM))
    BEAT_TIGHTNESS = float(_cfg.get("BEAT_TIGHTNESS", BEAT_TIGHTNESS))
    BEAT_TRIM = bool(_cfg.get("BEAT_TRIM", BEAT_TRIM))
    BEAT_BPM_OVERRIDE = float(_cfg.get("BEAT_BPM_OVERRIDE", BEAT_BPM_OVERRIDE))
    PLP_HOP_LENGTH = int(_cfg.get("PLP_HOP_LENGTH", PLP_HOP_LENGTH))
    PLP_WIN_LENGTH = int(_cfg.get("PLP_WIN_LENGTH", PLP_WIN_LENGTH))
    PLP_TEMPO_MIN = float(_cfg.get("PLP_TEMPO_MIN", PLP_TEMPO_MIN))
    PLP_TEMPO_MAX = float(_cfg.get("PLP_TEMPO_MAX", PLP_TEMPO_MAX))
    EXPORT_PULSE_DETAIL = bool(_cfg.get("EXPORT_PULSE_DETAIL", EXPORT_PULSE_DETAIL))
    DERIVE_PLP_PEAKS = bool(_cfg.get("DERIVE_PLP_PEAKS", DERIVE_PLP_PEAKS))
    PLP_PEAK_MIN_SPACING_MS = int(
        _cfg.get("PLP_PEAK_MIN_SPACING_MS", PLP_PEAK_MIN_SPACING_MS)
    )
    del _json, _f, _all_cfg, _cfg, _extractor_cfg
del _config_path

_AUDIO_EXTENSIONS = AUDIO_EXTENSIONS
_find_audio_files = find_audio_files
_plp_local_maxima = plp_local_maxima
_safe_scalar = safe_scalar
_format_times = format_times
_load_or_create_workbook = load_or_create_workbook
_ws_header_map = ws_header_map
_ensure_column = ensure_column
_find_summary_row = find_summary_row
_append_summary_row = append_summary_row
_write_summary_columns = write_summary_columns


def _build_config() -> BeatTempoConfig:
    """Build a reusable engine config from the current script globals."""
    return BeatTempoConfig(
        audio_folder=audio_folder,
        output_excel_path=output_excel_path,
        output_sheet_name=output_sheet_name,
        beat_hop_length=BEAT_HOP_LENGTH,
        beat_start_bpm=BEAT_START_BPM,
        beat_tightness=BEAT_TIGHTNESS,
        beat_trim=BEAT_TRIM,
        beat_bpm_override=BEAT_BPM_OVERRIDE,
        plp_hop_length=PLP_HOP_LENGTH,
        plp_win_length=PLP_WIN_LENGTH,
        plp_tempo_min=PLP_TEMPO_MIN,
        plp_tempo_max=PLP_TEMPO_MAX,
        export_pulse_detail=EXPORT_PULSE_DETAIL,
        derive_plp_peaks=DERIVE_PLP_PEAKS,
        plp_peak_min_spacing_ms=PLP_PEAK_MIN_SPACING_MS,
    )


def process_file(file_path: str, basename: str) -> dict:
    """Compatibility wrapper that keeps the historic process_file signature."""
    del basename
    return process_beat_tempo_file(file_path, _build_config())


def main() -> int:
    """Run the beat and tempo step using the current script settings."""
    return run_beat_tempo_step(_build_config())


if __name__ == "__main__":
    sys.exit(main())
