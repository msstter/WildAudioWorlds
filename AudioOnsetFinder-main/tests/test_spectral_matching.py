"""Tests for spectral profile building and onset matching."""
import os
import sys
import json
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scripts.onset_postprocessing import (
    build_spectral_profile,
    gate_onsets_by_spectral_match,
)
from analysis.spectral_profiles import (
    build_spectral_profile as build_shared_spectral_profile,
    compute_spectral_similarity_at_time,
)


# ── Helpers ─────────────────────────────────────────────────────────────


def _make_tone(freq, duration, sr=22050):
    """Generate a pure sine tone."""
    t = np.arange(int(sr * duration)) / sr
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def _make_click_train(times, sr=22050, duration=3.0, click_dur=0.01):
    """Generate clicks (short bursts) at specified times."""
    y = np.zeros(int(sr * duration), dtype=np.float32)
    click_len = int(sr * click_dur)
    for t in times:
        start = int(t * sr)
        end = min(len(y), start + click_len)
        y[start:end] = 0.8
    return y


# ── build_spectral_profile ──────────────────────────────────────────────


def test_profile_returns_none_no_regions():
    y = _make_tone(440, 1.0)
    result = build_spectral_profile(y, 22050, [])
    assert result is None


def test_profile_returns_none_negative_only():
    y = _make_tone(440, 1.0)
    regions = [{"t_start": 0.0, "t_end": 1.0, "f_low": 100, "f_high": 1000,
                "polarity": "negative"}]
    result = build_spectral_profile(y, 22050, regions)
    assert result is None


def test_profile_returns_dict_with_positive():
    y = _make_tone(440, 1.0)
    sr = 22050
    regions = [{"t_start": 0.1, "t_end": 0.9, "f_low": 200, "f_high": 800,
                "polarity": "positive"}]
    profile = build_spectral_profile(y, sr, regions)
    assert profile is not None
    assert "mean_spectrum" in profile
    assert "freqs" in profile
    assert "f_low" in profile
    assert "f_high" in profile
    assert profile["f_low"] == 200
    assert profile["f_high"] == 800


def test_profile_spectrum_is_normalised():
    y = _make_tone(440, 1.0)
    sr = 22050
    regions = [{"t_start": 0.0, "t_end": 1.0, "f_low": 0, "f_high": 11025,
                "polarity": "positive"}]
    profile = build_spectral_profile(y, sr, regions)
    norm = np.linalg.norm(profile["mean_spectrum"])
    assert abs(norm - 1.0) < 1e-6


def test_profile_concentrates_energy_at_tone_frequency():
    """A 1 kHz tone should peak near 1 kHz in the profile."""
    sr = 22050
    y = _make_tone(1000, 1.0, sr=sr)
    regions = [{"t_start": 0.0, "t_end": 1.0, "f_low": 0, "f_high": sr // 2,
                "polarity": "positive"}]
    profile = build_spectral_profile(y, sr, regions)
    peak_freq = profile["freqs"][np.argmax(profile["mean_spectrum"])]
    assert abs(peak_freq - 1000) < 50  # within ~50 Hz


def test_profile_zeros_outside_freq_box():
    """Frequencies outside the drawn box should be zeroed."""
    sr = 22050
    y = _make_tone(440, 1.0, sr=sr)
    regions = [{"t_start": 0.0, "t_end": 1.0, "f_low": 400, "f_high": 500,
                "polarity": "positive"}]
    profile = build_spectral_profile(y, sr, regions)
    freqs = profile["freqs"]
    spec = profile["mean_spectrum"]
    # Bins well below 400 Hz should be zero
    low_mask = freqs < 350
    assert np.all(spec[low_mask] == 0)
    # Bins well above 500 Hz should be zero
    high_mask = freqs > 550
    assert np.all(spec[high_mask] == 0)


def test_profile_multiple_regions_averaged():
    """Multiple positive regions should be weighted by duration."""
    sr = 22050
    # Two tones at different frequencies concatenated
    y = np.concatenate([
        _make_tone(500, 1.0, sr=sr),
        _make_tone(2000, 1.0, sr=sr),
    ])
    regions = [
        {"t_start": 0.0, "t_end": 1.0, "f_low": 0, "f_high": sr // 2,
         "polarity": "positive"},
        {"t_start": 1.0, "t_end": 2.0, "f_low": 0, "f_high": sr // 2,
         "polarity": "positive"},
    ]
    profile = build_spectral_profile(y, sr, regions)
    spec = profile["mean_spectrum"]
    freqs = profile["freqs"]
    # Both frequency regions should have energy
    low_zone = spec[(freqs > 450) & (freqs < 550)]
    high_zone = spec[(freqs > 1900) & (freqs < 2100)]
    assert np.max(low_zone) > 0.01
    assert np.max(high_zone) > 0.01


def test_shared_analysis_profile_matches_compatibility_wrapper():
    sr = 22050
    y = _make_tone(440, 1.0, sr=sr)
    regions = [{
        "t_start": 0.1,
        "t_end": 0.9,
        "f_low": 200,
        "f_high": 800,
        "polarity": "positive",
    }]

    shared = build_shared_spectral_profile(y, sr, regions)
    compat = build_spectral_profile(y, sr, regions)

    assert shared is not None
    assert compat is not None
    assert shared["f_low"] == compat["f_low"]
    assert shared["f_high"] == compat["f_high"]
    np.testing.assert_allclose(shared["freqs"], compat["freqs"])
    np.testing.assert_allclose(shared["mean_spectrum"], compat["mean_spectrum"])


def test_compute_spectral_similarity_at_time_prefers_matching_tone():
    sr = 22050
    y_match = _make_tone(1000, 2.0, sr=sr)
    y_mismatch = _make_tone(4000, 2.0, sr=sr)
    regions = [{
        "t_start": 0.0,
        "t_end": 1.0,
        "f_low": 0,
        "f_high": sr // 2,
        "polarity": "positive",
    }]
    profile = build_shared_spectral_profile(y_match, sr, regions)

    match_similarity = compute_spectral_similarity_at_time(0.5, y_match, sr, profile)
    mismatch_similarity = compute_spectral_similarity_at_time(0.5, y_mismatch, sr, profile)

    assert match_similarity is not None
    assert mismatch_similarity is not None
    assert match_similarity > 0.9
    assert mismatch_similarity < match_similarity


# ── gate_onsets_by_spectral_match ───────────────────────────────────────


def test_gate_none_profile_passthrough():
    """With no profile, all onsets should pass through."""
    onsets = np.array([0.5, 1.0, 1.5])
    y = _make_tone(440, 2.0)
    result = gate_onsets_by_spectral_match(onsets, y, 22050, None)
    np.testing.assert_array_equal(result, onsets)


def test_gate_empty_onsets():
    y = _make_tone(440, 1.0)
    sr = 22050
    profile = build_spectral_profile(
        y, sr,
        [{"t_start": 0.0, "t_end": 1.0, "f_low": 0, "f_high": sr // 2,
          "polarity": "positive"}])
    result = gate_onsets_by_spectral_match([], y, sr, profile)
    assert len(result) == 0


def test_gate_keeps_matching_onset():
    """An onset at a matching frequency should be kept."""
    sr = 22050
    y = _make_tone(1000, 2.0, sr=sr)
    regions = [{"t_start": 0.0, "t_end": 1.0, "f_low": 0, "f_high": sr // 2,
                "polarity": "positive"}]
    profile = build_spectral_profile(y, sr, regions)
    # An onset in the same 1 kHz tone should match
    result = gate_onsets_by_spectral_match(
        np.array([0.5, 1.0, 1.5]), y, sr, profile, threshold=0.3)
    assert len(result) == 3


def test_gate_rejects_different_frequency():
    """An onset in a very different spectrum should be rejected."""
    sr = 22050

    # Profile built from a low-frequency tone
    y_low = _make_tone(200, 1.0, sr=sr)
    regions = [{"t_start": 0.0, "t_end": 1.0, "f_low": 100, "f_high": 300,
                "polarity": "positive"}]
    profile = build_spectral_profile(y_low, sr, regions)

    # Audio with a high-frequency tone only
    y_high = _make_tone(8000, 2.0, sr=sr)
    result = gate_onsets_by_spectral_match(
        np.array([0.5, 1.0]), y_high, sr, profile, threshold=0.5)
    # Should reject onsets — spectrum doesn't match
    assert len(result) < 2


def test_gate_threshold_zero_keeps_all():
    """With threshold=0, everything should pass."""
    sr = 22050
    y = _make_tone(440, 2.0, sr=sr)
    regions = [{"t_start": 0.0, "t_end": 1.0, "f_low": 0, "f_high": sr // 2,
                "polarity": "positive"}]
    profile = build_spectral_profile(y, sr, regions)
    result = gate_onsets_by_spectral_match(
        np.array([0.3, 0.7, 1.2]), y, sr, profile, threshold=0.0)
    assert len(result) == 3


# ── Focus regions JSON export ──────────────────────────────────────────


def test_save_focus_regions_json(tmp_path):
    from PyQt6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    from GUI.onset_editor import OnsetEditorPanel

    panel = OnsetEditorPanel()
    panel._save_layer_state()

    fname = "test.wav"
    panel._layers[0]["focus_regions"] = {fname: [
        {"t_start": 0.5, "t_end": 1.5, "f_low": 200, "f_high": 4000, "polarity": "positive"},
        {"t_start": 2.0, "t_end": 3.0, "f_low": 100, "f_high": 2000, "polarity": "negative"},
    ]}
    panel._save_focus_regions_json(str(tmp_path), "test")

    json_path = tmp_path / "test_focus_regions.json"
    assert json_path.exists()

    with open(json_path) as f:
        data = json.load(f)
    assert fname in data
    assert len(data[fname]) == 2
    assert data[fname][0]["f_low"] == 200
    assert data[fname][0]["f_high"] == 4000
    assert data[fname][1]["polarity"] == "negative"


def test_save_focus_regions_json_multi_layer(tmp_path):
    from PyQt6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    from GUI.onset_editor import OnsetEditorPanel

    panel = OnsetEditorPanel()
    fname = "clip.wav"
    # Set up layer 0 regions via the live attribute (which IS layer 0's dict)
    panel._focus_regions[fname] = [
        {"t_start": 0.0, "t_end": 1.0, "f_low": 100, "f_high": 500, "polarity": "positive"},
    ]
    # Add layer — this saves layer 0 state, then switches to empty layer 1
    panel._add_layer()
    # Set up layer 1 regions
    panel._focus_regions[fname] = [
        {"t_start": 2.0, "t_end": 3.0, "f_low": 1000, "f_high": 4000, "polarity": "positive"},
    ]
    # Save current layer state so _layers[1] is up-to-date
    panel._save_layer_state()

    panel._save_focus_regions_json(str(tmp_path), "clip")

    with open(tmp_path / "clip_focus_regions.json") as f:
        data = json.load(f)
    # Both layers' regions merged under same filename
    assert len(data[fname]) == 2


def test_save_focus_regions_json_empty_no_file(tmp_path):
    from PyQt6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    from GUI.onset_editor import OnsetEditorPanel

    panel = OnsetEditorPanel()
    panel._save_focus_regions_json(str(tmp_path), "test")
    assert not (tmp_path / "test_focus_regions.json").exists()


# ── cluster_signal_regions ──────────────────────────────────────────────

from analysis.signal_profiles import cluster_signal_regions


def test_cluster_single_region():
    """A single region should return 1 cluster."""
    regions = [{"spectral_centroid_hz": 500, "spectral_bandwidth_hz": 100,
                "harmonicity": 0.8, "attack_sharpness": 0.1,
                "f_low": 200, "f_high": 800}]
    result = cluster_signal_regions(regions)
    assert result["n_clusters"] == 1
    assert result["labels"] == [0]
    assert len(result["descriptions"]) == 1


def test_cluster_two_distinct_groups():
    """Two very different groups of regions should yield 2 clusters."""
    # Group A: low-frequency percussive
    group_a = [
        {"spectral_centroid_hz": 200, "spectral_bandwidth_hz": 50,
         "harmonicity": 0.1, "attack_sharpness": 0.9,
         "f_low": 50, "f_high": 400},
        {"spectral_centroid_hz": 220, "spectral_bandwidth_hz": 60,
         "harmonicity": 0.12, "attack_sharpness": 0.85,
         "f_low": 60, "f_high": 420},
    ]
    # Group B: high-frequency harmonic
    group_b = [
        {"spectral_centroid_hz": 4000, "spectral_bandwidth_hz": 500,
         "harmonicity": 0.9, "attack_sharpness": 0.05,
         "f_low": 2000, "f_high": 6000},
        {"spectral_centroid_hz": 4200, "spectral_bandwidth_hz": 550,
         "harmonicity": 0.88, "attack_sharpness": 0.06,
         "f_low": 2100, "f_high": 6200},
    ]
    result = cluster_signal_regions(group_a + group_b)
    assert result["n_clusters"] == 2
    # First two should be in one cluster, last two in another
    assert result["labels"][0] == result["labels"][1]
    assert result["labels"][2] == result["labels"][3]
    assert result["labels"][0] != result["labels"][2]


def test_cluster_similar_regions_single_cluster():
    """Nearly identical regions should stay in one cluster."""
    regions = [
        {"spectral_centroid_hz": 1000 + i * 5, "spectral_bandwidth_hz": 200,
         "harmonicity": 0.5, "attack_sharpness": 0.3,
         "f_low": 500, "f_high": 1500}
        for i in range(5)
    ]
    result = cluster_signal_regions(regions)
    assert result["n_clusters"] == 1
