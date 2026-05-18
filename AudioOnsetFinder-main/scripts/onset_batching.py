"""Helpers for onset-finder batch routing and per-file runtime overrides."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


ONSET_SETTING_NAMES = [
    "ONSET_DELTA", "ONSET_HOP_LENGTH", "ONSET_BACKTRACK",
    "ONSET_METHOD", "ONSET_REFINE_ENABLED", "ONSET_REFINE_WINDOW_MS",
    "ONSET_REFINE_ENERGY_GATE", "ONSET_AMPLITUDE_GATE",
    "ONSET_AMPLITUDE_WINDOW_MS", "ONSET_SHARPNESS_GATE",
    "ONSET_SHARPNESS_WINDOW_MS", "MIN_INTER_ONSET_MS",
    "ONSET_CLUSTER_WINDOW_MS", "STABLE_RHYTHM_TOLERANCE",
    "CLUSTER_OVERLAPPING_ONSETS", "FILTER_STABLE_RHYTHMS",
    "APPLY_HIGHPASS_FILTER", "HIGHPASS_CUTOFF_HZ",
    "HP_SMOOTH_LAMBDA", "HP_THRESHOLD_LAMBDA",
    "HP_ENVELOPE_WINDOW_MS", "HP_ENVELOPE_HOP_MS",
    "MEDIAN_WINDOW_MS", "MEDIAN_THRESHOLD_SCALE",
    "SUPERFLUX_LAG", "SUPERFLUX_MAX_SIZE",
    "CFAR_GUARD_MS", "CFAR_TRAINING_MS", "CFAR_THRESHOLD_FACTOR",
    "PER_BAND_N_BANDS", "PER_BAND_FREQ_MIN", "PER_BAND_FREQ_MAX",
    "PER_BAND_MEDIAN_MS", "PER_BAND_THRESHOLD_SCALE", "PER_BAND_MIN_BANDS",
    "SYLLABLE_INTENSITY_THRESHOLD", "SYLLABLE_MIN_DIP_DB",
    "SYLLABLE_MIN_PAUSE_MS", "SYLLABLE_VOICING_THRESHOLD",
    "SYLLABLE_TIME_STEP",
    "WHISPER_MODEL_SIZE", "WHISPER_LANGUAGE", "WHISPER_WORD_TIMESTAMPS",
    "PAUSE_THRESHOLD_MS", "EXPORT_TEXTGRID", "EXPORT_TRANSCRIPT",
    "WHISPERX_MODEL_SIZE", "WHISPERX_LANGUAGE", "WHISPERX_DEVICE",
    "MADMOM_MIN_BPM", "MADMOM_MAX_BPM", "MADMOM_FPS",
    "MADMOM_DOWNBEATS", "MADMOM_TRANSITION_LAMBDA",
    "PITCH_TRACKER", "PITCH_FMIN", "PITCH_FMAX",
    "TEMPO_ADAPTIVE_MIN_IOI", "TEMPO_ADAPTIVE_FRACTION",
]


@dataclass(frozen=True)
class BatchRoutingInputs:
    per_file_cfg: dict[str, dict]
    per_file_focus: dict[str, list[dict]]
    layer_configs: dict[str, list[dict]]


def snapshot_module_settings(module: Any, setting_names=ONSET_SETTING_NAMES) -> dict[str, Any]:
    """Snapshot the selected module attributes into a plain settings dict."""
    return {name: getattr(module, name) for name in setting_names}


@contextmanager
def temporary_module_settings(module: Any, overrides: dict[str, Any] | None,
                              setting_names=ONSET_SETTING_NAMES):
    """Temporarily apply per-file onset-setting overrides to *module*."""
    saved: dict[str, Any] = {}
    if overrides:
        for name in setting_names:
            if name in overrides:
                saved[name] = getattr(module, name)
                setattr(module, name, overrides[name])
    try:
        yield saved
    finally:
        for name, value in saved.items():
            setattr(module, name, value)


def resolve_audio_files(audio_folder_path, selected_files=None,
                        valid_extensions=(".wav", ".mp3", ".flac", ".ogg")):
    """Return supported audio filenames, optionally filtered to *selected_files*."""
    available = [
        name for name in sorted(os.listdir(audio_folder_path))
        if name.lower().endswith(valid_extensions)
    ]
    requested = list(dict.fromkeys(selected_files or []))
    if not requested:
        return available, []
    requested_set = set(requested)
    filtered = [name for name in available if name in requested_set]
    missing = [name for name in requested if name not in available]
    return filtered, missing


def _coerce_per_file_onset_payload(payload: dict) -> dict:
    onset = payload.get("onset_recommendations")
    if isinstance(onset, dict) and onset:
        return onset
    settings = payload.get("settings", payload)
    return settings if isinstance(settings, dict) else {}


def _collect_named_per_file_settings(source: dict, target: dict[str, dict]) -> None:
    for key, value in source.items():
        if key.startswith("__") or not isinstance(value, dict):
            continue
        target[key] = _coerce_per_file_onset_payload(value)


def load_per_file_onset_settings(path: str) -> dict[str, dict]:
    """Load per-file onset-setting overrides from a JSON file or folder."""
    loaded: dict[str, dict] = {}
    if not path:
        return loaded

    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            _collect_named_per_file_settings(payload, loaded)
        return loaded

    if os.path.isdir(path):
        for name in sorted(os.listdir(path)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(path, name), encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                continue
            filename = payload.get("filename")
            if isinstance(filename, str):
                loaded[filename] = _coerce_per_file_onset_payload(payload)
            else:
                _collect_named_per_file_settings(payload, loaded)
    return loaded


def load_per_file_focus_regions(path: str) -> dict[str, list[dict]]:
    """Load per-file focus-region routing data from a JSON file."""
    if not path or not os.path.isfile(path):
        return {}

    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def load_selected_layer_configs(audio_folder: str, audio_files: list[str],
                                selected_layers: list[str] | None) -> dict[str, list[dict]]:
    """Load selected per-file onset layers from each ``*_OnsetLayers`` folder."""
    if not selected_layers:
        return {}

    selected_set = set(selected_layers)
    loaded: dict[str, list[dict]] = {}
    for audio_file in audio_files:
        stem = os.path.splitext(audio_file)[0]
        layer_dir = os.path.join(audio_folder, f"{stem}_OnsetLayers")
        if not os.path.isdir(layer_dir):
            continue

        file_layers = []
        for name in sorted(os.listdir(layer_dir)):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(layer_dir, name), encoding="utf-8") as handle:
                    payload = json.load(handle)
            except (OSError, ValueError):
                continue
            if isinstance(payload, dict) and payload.get("name") in selected_set:
                file_layers.append(payload)

        if file_layers:
            loaded[audio_file] = file_layers

    return loaded


def load_batch_routing_inputs(audio_folder: str, audio_files: list[str], *,
                              per_file_settings_path: str = "",
                              focus_regions_path: str = "",
                              specify_layers: bool = False,
                              selected_layers: list[str] | None = None) -> BatchRoutingInputs:
    """Load the per-file routing inputs needed by the onset-finder batch loop."""
    per_file_cfg = load_per_file_onset_settings(per_file_settings_path)
    per_file_focus = load_per_file_focus_regions(focus_regions_path)
    layer_configs = {}
    if specify_layers:
        layer_configs = load_selected_layer_configs(audio_folder, audio_files, selected_layers)
    return BatchRoutingInputs(
        per_file_cfg=per_file_cfg,
        per_file_focus=per_file_focus,
        layer_configs=layer_configs,
    )


__all__ = [
    "BatchRoutingInputs",
    "ONSET_SETTING_NAMES",
    "load_batch_routing_inputs",
    "load_per_file_focus_regions",
    "load_per_file_onset_settings",
    "load_selected_layer_configs",
    "resolve_audio_files",
    "snapshot_module_settings",
    "temporary_module_settings",
]