"""Shared detector-routing helpers for onset analysis and extraction.

This module translates onset-finder style settings dictionaries into the
method name and keyword arguments expected by ``onset_detectors.py``.
Keeping that translation here lets the batch pipeline, onset analyzer, and
GUI workbench reuse one routing vocabulary instead of duplicating per-method
kwargs builders.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


DELTA_TUNABLE_METHODS = frozenset({"librosa", "superflux"})


def _optional_frequency_limit(value: Any) -> float | None:
    if value in (0, "", None):
        return None
    return float(value)


def build_detector_call(settings: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    """Translate onset-finder style settings into an onset-detectors call."""
    method = str(settings.get("ONSET_METHOD", "librosa"))
    hop_length = int(settings.get("ONSET_HOP_LENGTH", 256))
    delta = float(settings.get("ONSET_DELTA", 0.30))
    backtrack = bool(settings.get("ONSET_BACKTRACK", False))

    if method == "adaptive_hp":
        kwargs = {
            "hp_smooth_lambda": float(settings.get("HP_SMOOTH_LAMBDA", 50)),
            "hp_threshold_lambda": float(settings.get("HP_THRESHOLD_LAMBDA", 5e7)),
            "envelope_window_ms": float(settings.get("HP_ENVELOPE_WINDOW_MS", 10)),
            "envelope_hop_ms": float(settings.get("HP_ENVELOPE_HOP_MS", 1)),
        }
    elif method == "moving_median":
        kwargs = {
            "envelope_window_ms": float(settings.get("HP_ENVELOPE_WINDOW_MS", 10)),
            "envelope_hop_ms": float(settings.get("HP_ENVELOPE_HOP_MS", 1)),
            "median_window_ms": float(settings.get("MEDIAN_WINDOW_MS", 200)),
            "threshold_scale": float(settings.get("MEDIAN_THRESHOLD_SCALE", 1.5)),
        }
    elif method == "superflux":
        kwargs = {
            "hop_length": hop_length,
            "n_fft": int(settings.get("SUPERFLUX_N_FFT", 2048)),
            "lag": int(settings.get("SUPERFLUX_LAG", 2)),
            "max_size": int(settings.get("SUPERFLUX_MAX_SIZE", 3)),
            "delta": delta,
        }
    elif method == "cfar":
        kwargs = {
            "envelope_window_ms": float(settings.get("HP_ENVELOPE_WINDOW_MS", 10)),
            "envelope_hop_ms": float(settings.get("HP_ENVELOPE_HOP_MS", 1)),
            "guard_ms": float(settings.get("CFAR_GUARD_MS", 20)),
            "training_ms": float(settings.get("CFAR_TRAINING_MS", 200)),
            "threshold_factor": float(settings.get("CFAR_THRESHOLD_FACTOR", 4.0)),
        }
    elif method == "per_band":
        kwargs = {
            "hop_length": hop_length,
            "n_fft": int(settings.get("PER_BAND_N_FFT", 2048)),
            "n_bands": int(settings.get("PER_BAND_N_BANDS", 6)),
            "freq_min": float(settings.get("PER_BAND_FREQ_MIN", 200)),
            "freq_max": _optional_frequency_limit(settings.get("PER_BAND_FREQ_MAX", None)),
            "median_window_ms": float(settings.get("PER_BAND_MEDIAN_MS", 200)),
            "threshold_scale": float(settings.get("PER_BAND_THRESHOLD_SCALE", 1.5)),
            "min_bands": int(settings.get("PER_BAND_MIN_BANDS", 2)),
        }
    elif method == "syllable_nuclei":
        kwargs = {
            "intensity_threshold": float(settings.get("SYLLABLE_INTENSITY_THRESHOLD", -25.0)),
            "min_dip_db": float(settings.get("SYLLABLE_MIN_DIP_DB", 2.0)),
            "min_pause_ms": float(settings.get("SYLLABLE_MIN_PAUSE_MS", 30.0)),
            "voicing_threshold": float(settings.get("SYLLABLE_VOICING_THRESHOLD", 0.3)),
            "time_step": float(settings.get("SYLLABLE_TIME_STEP", 0.01)),
        }
    elif method == "whisper_words":
        kwargs = {
            "model_size": settings.get("WHISPER_MODEL_SIZE", "base"),
            "language": settings.get("WHISPER_LANGUAGE", None),
            "word_timestamps": bool(settings.get("WHISPER_WORD_TIMESTAMPS", True)),
        }
    elif method == "whisperx_phonemes":
        kwargs = {
            "model_size": settings.get("WHISPERX_MODEL_SIZE", "base"),
            "language": settings.get("WHISPERX_LANGUAGE", None),
            "device": settings.get("WHISPERX_DEVICE", "cpu"),
        }
    elif method == "madmom_beats":
        kwargs = {
            "min_bpm": float(settings.get("MADMOM_MIN_BPM", 40)),
            "max_bpm": float(settings.get("MADMOM_MAX_BPM", 240)),
            "fps": float(settings.get("MADMOM_FPS", 100)),
            "downbeats": bool(settings.get("MADMOM_DOWNBEATS", False)),
            "transition_lambda": float(settings.get("MADMOM_TRANSITION_LAMBDA", 100)),
        }
    else:
        kwargs = {
            "hop_length": hop_length,
            "delta": delta,
            "backtrack": backtrack,
        }

    return method, kwargs


__all__ = ["DELTA_TUNABLE_METHODS", "build_detector_call"]