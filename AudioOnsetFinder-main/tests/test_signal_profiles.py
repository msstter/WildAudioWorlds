"""Tests for the shared signal-profile analysis boundary."""

import numpy as np

from analysis import (
    build_per_signal_profiles,
    build_signal_profile,
    summarize_signal_region_analyses,
)
from scripts.signal_selector import build_signal_profile as build_signal_profile_wrapper


def _make_tone(freq, duration, sr=22050):
    timeline = np.arange(int(sr * duration)) / sr
    return np.sin(2 * np.pi * freq * timeline).astype(np.float32)


def test_shared_signal_profile_matches_signal_selector_wrapper():
    sr = 22050
    y = _make_tone(600, 1.0, sr=sr)
    regions = [
        {
            "t_start": 0.1,
            "t_end": 0.6,
            "f_low": 300,
            "f_high": 900,
            "polarity": "positive",
        }
    ]

    shared = build_signal_profile(y, sr, regions)
    compat = build_signal_profile_wrapper(y, sr, regions)

    assert shared["summary"] == compat["summary"]
    assert shared["regions"] == compat["regions"]


def test_build_per_signal_profiles_returns_one_entry_per_region():
    sr = 22050
    y = _make_tone(750, 1.0, sr=sr)
    regions = [
        {"t_start": 0.05, "t_end": 0.15, "f_low": 500, "f_high": 1000, "polarity": "positive"},
        {"t_start": 0.40, "t_end": 0.50, "f_low": 500, "f_high": 1000, "polarity": "negative"},
    ]

    profiles = build_per_signal_profiles(y, sr, regions)

    assert len(profiles) == 2
    assert profiles[0]["index"] == 0
    assert profiles[1]["index"] == 1
    assert profiles[0]["region"]["polarity"] == "positive"
    assert profiles[1]["region"]["polarity"] == "negative"
    assert profiles[0]["analysis"]["peak_frequency_hz"] >= 500


def test_summarize_signal_region_analyses_aggregates_character_and_count():
    summary = summarize_signal_region_analyses(
        [
            {
                "f_low": 100.0,
                "f_high": 400.0,
                "spectral_centroid_hz": 220.0,
                "spectral_bandwidth_hz": 80.0,
                "harmonicity": 0.2,
                "attack_sharpness": 0.8,
                "energy_ratio": 0.6,
                "duration_s": 0.1,
            },
            {
                "f_low": 120.0,
                "f_high": 420.0,
                "spectral_centroid_hz": 240.0,
                "spectral_bandwidth_hz": 90.0,
                "harmonicity": 0.25,
                "attack_sharpness": 0.75,
                "energy_ratio": 0.5,
                "duration_s": 0.12,
            },
        ]
    )

    assert summary["n_regions"] == 2
    assert summary["signal_character"] == "percussive"
    assert summary["freq_range_hz"] == [100.0, 420.0]