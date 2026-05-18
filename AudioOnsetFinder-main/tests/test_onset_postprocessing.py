"""Tests for shared onset post-processing helpers."""

import numpy as np

from scripts.onset_postprocessing import (
    apply_highpass,
    gate_onsets_by_broadband,
    gate_onsets_by_variable_bounds,
)


def _sine_projection_amplitude(signal, frequency_hz, sr):
    timeline = np.arange(len(signal), dtype=float) / sr
    basis = np.sin(2 * np.pi * frequency_hz * timeline)
    return abs(np.dot(signal, basis)) / len(signal)


def test_apply_highpass_reduces_low_frequency_component_more_than_high_frequency():
    sr = 2000
    timeline = np.arange(sr, dtype=float) / sr
    low_component = np.sin(2 * np.pi * 20 * timeline)
    high_component = 0.5 * np.sin(2 * np.pi * 300 * timeline)
    signal = (low_component + high_component).astype(np.float64)

    filtered = apply_highpass(signal, sr, 100.0)

    low_before = _sine_projection_amplitude(signal, 20, sr)
    low_after = _sine_projection_amplitude(filtered, 20, sr)
    high_before = _sine_projection_amplitude(signal, 300, sr)
    high_after = _sine_projection_amplitude(filtered, 300, sr)

    assert low_after < low_before * 0.25
    assert high_after > high_before * 0.6
    assert (low_after / low_before) < (high_after / high_before)


def test_gate_onsets_by_broadband_keeps_frames_with_enough_active_bands(monkeypatch):
    spectrogram = np.array(
        [
            [10.0, 10.0, 0.0],
            [10.0, 10.0, 0.0],
            [0.0, 10.0, 10.0],
            [0.0, 10.0, 10.0],
        ]
    )

    monkeypatch.setattr(
        "scripts.onset_postprocessing.librosa.stft",
        lambda signal, n_fft, hop_length: spectrogram,
    )
    monkeypatch.setattr(
        "scripts.onset_postprocessing.librosa.time_to_frames",
        lambda onset_times, sr, hop_length, n_fft: np.array([0, 1, 2], dtype=int),
    )

    kept = gate_onsets_by_broadband(
        np.array([0.1, 0.2, 0.3], dtype=float),
        np.zeros(1024, dtype=float),
        8000,
        min_bands=2,
        n_bands=2,
        threshold=0.5,
    )

    assert np.allclose(kept, np.array([0.2], dtype=float))


def test_gate_onsets_by_variable_bounds_uses_injected_region_analyzer():
    def fake_analyze_region(signal, sr, start_time, end_time, f_low, f_high):
        centre = round((start_time + end_time) / 2.0, 1)
        if centre == 0.1:
            return {"peak_frequency_hz": 105.0}
        if centre == 0.2:
            return {"peak_frequency_hz": 121.0}
        return {}

    kept = gate_onsets_by_variable_bounds(
        np.array([0.1, 0.2, 0.3], dtype=float),
        np.zeros(2000, dtype=float),
        1000,
        ref_analysis={"peak_frequency_hz": 100.0},
        per_var_config={
            "peak_frequency_hz": {"enabled": True, "lower_pct": 10, "upper_pct": 10},
            "duration_s": {"enabled": True, "lower_pct": 10, "upper_pct": 10},
        },
        ref_region={"f_low": 50.0, "f_high": 400.0},
        analyze_region_fn=fake_analyze_region,
    )

    assert np.allclose(kept, np.array([0.1], dtype=float))