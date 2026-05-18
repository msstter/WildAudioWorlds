"""Tests for shared detector-routing helpers."""

import numpy as np

from scripts import onset_analyzer
from scripts.onset_routing import DELTA_TUNABLE_METHODS, build_detector_call


def test_build_detector_call_per_band_normalizes_freq_max_and_fft_defaults():
    method, kwargs = build_detector_call({
        "ONSET_METHOD": "per_band",
        "ONSET_HOP_LENGTH": 192,
        "PER_BAND_N_BANDS": 9,
        "PER_BAND_FREQ_MIN": 350,
        "PER_BAND_FREQ_MAX": "",
        "PER_BAND_MEDIAN_MS": 180,
        "PER_BAND_THRESHOLD_SCALE": 1.8,
        "PER_BAND_MIN_BANDS": 3,
    })

    assert method == "per_band"
    assert kwargs == {
        "hop_length": 192,
        "n_fft": 2048,
        "n_bands": 9,
        "freq_min": 350.0,
        "freq_max": None,
        "median_window_ms": 180.0,
        "threshold_scale": 1.8,
        "min_bands": 3,
    }


def test_build_detector_call_supports_speech_and_beat_methods():
    method, kwargs = build_detector_call({
        "ONSET_METHOD": "whisperx_phonemes",
        "WHISPERX_MODEL_SIZE": "small",
        "WHISPERX_LANGUAGE": "en",
        "WHISPERX_DEVICE": "cpu",
    })
    assert method == "whisperx_phonemes"
    assert kwargs == {
        "model_size": "small",
        "language": "en",
        "device": "cpu",
    }

    method, kwargs = build_detector_call({
        "ONSET_METHOD": "madmom_beats",
        "MADMOM_MIN_BPM": 60,
        "MADMOM_MAX_BPM": 180,
        "MADMOM_FPS": 120,
        "MADMOM_DOWNBEATS": True,
        "MADMOM_TRANSITION_LAMBDA": 80,
    })
    assert method == "madmom_beats"
    assert kwargs == {
        "min_bpm": 60.0,
        "max_bpm": 180.0,
        "fps": 120.0,
        "downbeats": True,
        "transition_lambda": 80.0,
    }


def test_delta_tunable_methods_match_gui_probe_expectations():
    assert DELTA_TUNABLE_METHODS == {"librosa", "superflux"}


def test_onset_analyzer_try_detection_method_uses_shared_kwarg_names(monkeypatch):
    called = {}

    def fake_detect_onsets(method, signal, sr, **kwargs):
        called["method"] = method
        called["kwargs"] = kwargs
        return np.array([0.1], dtype=float)

    monkeypatch.setattr(onset_analyzer, "detect_onsets", fake_detect_onsets)

    onset_analyzer.try_detection_method(
        "adaptive_hp",
        np.zeros(1024, dtype=float),
        8000,
        0.06,
        256,
    )

    assert called["method"] == "adaptive_hp"
    assert called["kwargs"]["hp_smooth_lambda"] == 50.0
    assert called["kwargs"]["hp_threshold_lambda"] == 5e7
    assert "smooth_lambda" not in called["kwargs"]