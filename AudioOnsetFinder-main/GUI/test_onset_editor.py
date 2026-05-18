"""Tests for the OnsetEditorPanel module."""

import json
import os
import sys
import tempfile

import numpy as np
import pytest

# Ensure GUI/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "GUI"))

from onset_editor import (
    OnsetManagerDialog,
    _EditAudioDialog,
    _LayerCheckboxMenu,
    _PerSignalConfigDialog,
    OnsetEditorPanel,
    _AnalyzeSignalsDialog,
    _DetectOnsetsDialog,
    _UndoStack,
    _build_region_detector_kwargs,
    _build_uniform_probe_times,
    _candidate_peak_times_for_region,
    _compute_per_signal_variable_score_threshold,
    _compute_per_signal_spectral_threshold,
    _compute_ioi,
    _compute_rk,
    _compute_stable,
    _diagnose_candidate_matches,
    _evaluate_exemplar_self_check,
    _extract_recommended_detect_settings,
    _format_match_miss_reason,
    _load_labels,
    _merge_negative_detection_hits,
    _recover_focus_region_onset,
    _region_contains_onset,
    _score_onsets_by_variable_match,
    _save_labels,
    _find_label_file,
)
from onset_editor_io import _write_focus_regions_json, _write_onset_layer_settings


# ═══════════════════════════════════════════════════════════════════════════
# Unit tests — pure functions (no Qt required)
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeIOI:
    def test_empty(self):
        assert _compute_ioi([]) == []

    def test_single(self):
        assert _compute_ioi([1.0]) == [None]

    def test_basic(self):
        result = _compute_ioi([0.0, 0.5, 1.5])
        assert result[0] is None
        assert abs(result[1] - 500.0) < 0.01
        assert abs(result[2] - 1000.0) < 0.01


class TestComputeRk:
    def test_empty(self):
        assert _compute_rk([]) == []

    def test_two(self):
        assert _compute_rk([0.0, 1.0]) == [None, None]

    def test_isochronous(self):
        # Equal intervals → r_k = 0.5
        result = _compute_rk([0.0, 1.0, 2.0])
        assert result[0] is None
        assert result[1] is None
        assert abs(result[2] - 0.5) < 0.0001

    def test_unequal(self):
        # Intervals: 1.0, 3.0 → r_k = 1.0/4.0 = 0.25
        result = _compute_rk([0.0, 1.0, 4.0])
        assert abs(result[2] - 0.25) < 0.0001


class TestComputeStable:
    def test_empty(self):
        assert _compute_stable([]) == []

    def test_short(self):
        assert _compute_stable([0.0, 1.0]) == [None, None]

    def test_stable_pattern(self):
        # Perfectly repeating pattern: intervals 1,2,1,2,1,2
        times = [0, 1, 3, 4, 6, 7, 9]
        result = _compute_stable(times)
        # First two are None
        assert result[0] is None
        assert result[1] is None
        # Middle ones should be stable (pattern repeats)
        for i in range(2, min(len(result), 5)):
            if result[i] is not None:
                assert result[i] is True, f"Expected stable at index {i}"

    def test_unstable_pattern(self):
        # Wildly varying intervals
        times = [0, 1, 5, 5.1, 20, 20.01]
        result = _compute_stable(times, tolerance=0.1)
        # With such varied intervals, most should be unstable
        unstable_count = sum(1 for s in result if s is False)
        assert unstable_count >= 1


class TestLabelIO:
    def test_roundtrip(self):
        times = [0.123456, 1.234567, 2.345678]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            path = f.name
        try:
            _save_labels(path, times)
            loaded = _load_labels(path)
            assert len(loaded) == len(times)
            for a, b in zip(times, loaded):
                assert abs(a - b) < 1e-5
        finally:
            os.unlink(path)

    def test_load_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            path = f.name
        try:
            assert _load_labels(path) == []
        finally:
            os.unlink(path)

    def test_save_format(self):
        times = [1.5]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            path = f.name
        try:
            _save_labels(path, times)
            with open(path) as f:
                line = f.readline().strip()
            parts = line.split("\t")
            assert len(parts) == 3
            assert parts[2] == "OnsetR_1"
            assert abs(float(parts[0]) - 1.5) < 1e-5
        finally:
            os.unlink(path)


class TestFindLabelFile:
    def test_found(self):
        with tempfile.TemporaryDirectory() as d:
            audio = os.path.join(d, "song.wav")
            label = os.path.join(d, "song_labels.txt")
            open(audio, "w").close()
            open(label, "w").close()
            assert _find_label_file(audio) == label

    def test_not_found(self):
        with tempfile.TemporaryDirectory() as d:
            audio = os.path.join(d, "song.wav")
            open(audio, "w").close()
            assert _find_label_file(audio) is None


class TestWorkbenchPersistenceIO:
    def test_write_focus_regions_json_merges_non_empty_regions(self):
        layers = [
            {
                "focus_regions": {
                    "song.wav": [{"t_start": 0.1, "t_end": 0.2, "polarity": "positive"}],
                    "skip.wav": [],
                }
            },
            {
                "focus_regions": {
                    "song.wav": [{"t_start": 0.3, "t_end": 0.4, "polarity": "negative"}],
                    "other.wav": [{"t_start": 1.0, "t_end": 1.1, "polarity": "positive"}],
                }
            },
        ]

        with tempfile.TemporaryDirectory() as d:
            out_path = _write_focus_regions_json(d, "song", layers)

            assert out_path == os.path.join(d, "song_focus_regions.json")
            with open(out_path, encoding="utf-8") as handle:
                payload = json.load(handle)

        assert set(payload.keys()) == {"song.wav", "other.wav"}
        assert len(payload["song.wav"]) == 2
        assert payload["other.wav"][0]["t_start"] == 1.0

    def test_write_onset_layer_settings_writes_per_layer_json(self):
        layers = [
            {
                "name": "Layer A",
                "focus_regions": {
                    "song.wav": [{"t_start": 0.1, "t_end": 0.2, "polarity": "positive"}]
                },
                "onset_times": [0.1234567, 1.0],
            },
            {
                "name": "Layer B",
                "focus_regions": {"other.wav": [{"t_start": 0.9, "t_end": 1.0, "polarity": "negative"}]},
                "onset_times": [2.3456789],
            },
        ]

        with tempfile.TemporaryDirectory() as d:
            audio_path = os.path.join(d, "song.wav")
            open(audio_path, "w").close()

            layers_dir = _write_onset_layer_settings(audio_path, layers)

            assert layers_dir == os.path.join(d, "song_OnsetLayers")

            with open(os.path.join(layers_dir, "Layer_1.json"), encoding="utf-8") as handle:
                first = json.load(handle)
            with open(os.path.join(layers_dir, "Layer_2.json"), encoding="utf-8") as handle:
                second = json.load(handle)

        assert first["name"] == "Layer A"
        assert first["audio_filename"] == "song.wav"
        assert first["focus_regions"][0]["polarity"] == "positive"
        assert first["onset_times"] == [0.123457, 1.0]
        assert second["name"] == "Layer B"
        assert second["focus_regions"] == []
        assert second["onset_times"] == [2.345679]


class TestUndoStack:
    def test_undo_redo(self):
        stack = _UndoStack()
        stack.push([1.0, 2.0])
        stack.push([1.0, 2.0, 3.0])
        assert stack.can_undo()
        result = stack.undo()
        assert result == [1.0, 2.0]
        assert stack.can_redo()
        result = stack.redo()
        assert result == [1.0, 2.0, 3.0]

    def test_empty_undo(self):
        stack = _UndoStack()
        assert not stack.can_undo()
        assert stack.undo() is None

    def test_push_clears_redo(self):
        stack = _UndoStack()
        stack.push([1.0])
        stack.push([1.0, 2.0])
        stack.undo()
        assert stack.can_redo()
        stack.push([1.0, 3.0])  # new action clears redo
        assert not stack.can_redo()


class TestPerSignalHelpers:
    def test_extract_recommended_detect_settings_prefers_nested_settings(self):
        result = {
            "analysis": {"best_method": "superflux"},
            "settings": {
                "ONSET_METHOD": "superflux",
                "ONSET_DELTA": 0.07,
                "ONSET_HOP_LENGTH": 128,
            },
        }

        extracted = _extract_recommended_detect_settings(result)

        assert extracted == {
            "ONSET_METHOD": "superflux",
            "ONSET_DELTA": 0.07,
            "ONSET_HOP_LENGTH": 128,
        }

    def test_extract_recommended_detect_settings_accepts_flat_settings_dict(self):
        extracted = _extract_recommended_detect_settings({
            "ONSET_METHOD": "adaptive_hp",
            "ONSET_DELTA": 0.05,
        })

        assert extracted == {
            "ONSET_METHOD": "adaptive_hp",
            "ONSET_DELTA": 0.05,
        }

    def test_compute_per_signal_spectral_threshold_stays_moderate_by_default(self):
        cfg = {
            "peak_frequency_hz": {"enabled": True, "lower_pct": 20, "upper_pct": 20},
            "spectral_centroid_hz": {"enabled": True, "lower_pct": 20, "upper_pct": 20},
            "spectral_bandwidth_hz": {"enabled": True, "lower_pct": 30, "upper_pct": 30},
            "harmonicity": {"enabled": True, "lower_pct": 25, "upper_pct": 25},
            "attack_sharpness": {"enabled": True, "lower_pct": 30, "upper_pct": 30},
            "energy_ratio": {"enabled": True, "lower_pct": 40, "upper_pct": 40},
            "duration_s": {"enabled": True, "lower_pct": 50, "upper_pct": 50},
        }

        threshold = _compute_per_signal_spectral_threshold(cfg)

        assert 0.35 <= threshold <= 0.50

    def test_compute_per_signal_variable_score_threshold_stays_reasonable(self):
        cfg = {
            "peak_frequency_hz": {"enabled": True, "lower_pct": 20, "upper_pct": 20},
            "spectral_centroid_hz": {"enabled": True, "lower_pct": 20, "upper_pct": 20},
            "spectral_bandwidth_hz": {"enabled": True, "lower_pct": 30, "upper_pct": 30},
        }

        threshold = _compute_per_signal_variable_score_threshold(cfg)

        assert 0.55 <= threshold <= 0.70

    def test_score_onsets_by_variable_match_uses_soft_scoring(self, monkeypatch):
        from analysis import signal_profiles

        def fake_analyze_region(_y, _sr, t0, t1, _f_low, _f_high, **_kwargs):
            centre = round((t0 + t1) / 2.0, 2)
            if abs(centre - 0.10) < 0.02:
                return {"peak_frequency_hz": 100.0, "spectral_centroid_hz": 100.0}
            if abs(centre - 0.20) < 0.02:
                return {"peak_frequency_hz": 120.0, "spectral_centroid_hz": 100.0}
            return {"peak_frequency_hz": 170.0, "spectral_centroid_hz": 100.0}

        monkeypatch.setattr(signal_profiles, "analyze_region", fake_analyze_region)

        scores = _score_onsets_by_variable_match(
            [0.10, 0.20, 0.30],
            np.zeros(8000, dtype=float),
            8000,
            {"peak_frequency_hz": 100.0, "spectral_centroid_hz": 100.0},
            {
                "peak_frequency_hz": {"enabled": True, "lower_pct": 20, "upper_pct": 20},
                "spectral_centroid_hz": {"enabled": True, "lower_pct": 20, "upper_pct": 20},
            },
            {"f_low": 50, "f_high": 200},
        )

        assert scores[0]["score"] > scores[1]["score"] > scores[2]["score"]
        assert scores[1]["score"] > 0.0

    def test_evaluate_exemplar_self_check_uses_best_probe(self, monkeypatch):
        monkeypatch.setattr(
            "onset_editor._compute_spectral_similarity_at_time",
            lambda t, *_args, **_kwargs: 0.1 if t < 0.2 else 0.8,
        )
        monkeypatch.setattr(
            "onset_editor._score_onsets_by_variable_match",
            lambda times, *_args, **_kwargs: [
                {"time": float(t), "score": (0.2 if t < 0.2 else 0.9), "failed_keys": ["peak_frequency_hz"] if t < 0.2 else [], "candidate": {}}
                for t in times
            ],
        )

        report = _evaluate_exemplar_self_check(
            np.zeros(16000, dtype=float),
            8000,
            {"regions": [{"t_start": 0.0, "t_end": 0.4, "f_low": 100, "f_high": 400, "peak_frequency_hz": 200.0}]},
            {"peak_frequency_hz": {"enabled": True, "lower_pct": 20, "upper_pct": 20}},
            {"_spectral_match_threshold": 0.3, "_per_signal_variable_score_threshold": 0.6},
        )

        assert report["passed"] is True
        assert report["best_result"]["spectral_similarity"] == 0.8
        assert report["best_result"]["score"] == 0.9

    def test_region_contains_onset_accepts_small_margin(self):
        region = {"t_start": 1.0, "t_end": 1.1}
        assert _region_contains_onset([0.99, 1.05], region) is True
        assert _region_contains_onset([0.8], region) is False

    def test_build_uniform_probe_times_spans_region(self):
        region = {"t_start": 2.0, "t_end": 2.4}
        probes = _build_uniform_probe_times(region)
        assert probes[0] >= 2.0
        assert probes[-1] <= 2.4
        assert len(probes) >= 3

    def test_candidate_peak_times_for_region_falls_back_cleanly_on_short_audio(self):
        peaks = _candidate_peak_times_for_region(
            np.zeros(10, dtype=float),
            8000,
            {"t_start": 0.0, "t_end": 0.001},
        )
        assert peaks == []

    def test_diagnose_candidate_matches_reports_threshold_failures(self, monkeypatch):
        monkeypatch.setattr(
            "onset_editor._compute_spectral_similarity_at_time",
            lambda t, *_args, **_kwargs: 0.2 if t < 0.2 else 0.9,
        )
        monkeypatch.setattr(
            "onset_editor._score_onsets_by_variable_match",
            lambda times, *_args, **_kwargs: [
                {"time": float(t), "score": (0.3 if t < 0.2 else 0.85), "failed_keys": ["peak_frequency_hz"] if t < 0.2 else [], "candidate": {}}
                for t in times
            ],
        )

        report = _diagnose_candidate_matches(
            [0.1, 0.3],
            np.zeros(16000, dtype=float),
            8000,
            {"regions": [{"t_start": 0.0, "t_end": 0.4, "f_low": 100, "f_high": 400, "peak_frequency_hz": 200.0}]},
            {"peak_frequency_hz": {"enabled": True, "lower_pct": 20, "upper_pct": 20}},
            {"_spectral_match_threshold": 0.3, "_per_signal_variable_score_threshold": 0.6},
        )

        assert report["passed"] is True
        assert report["best_result"]["time"] == 0.3

    def test_recover_focus_region_onset_prefers_earliest_near_best_pass(self, monkeypatch):
        monkeypatch.setattr("onset_editor._build_uniform_probe_times", lambda _region: [1.02, 1.06])
        monkeypatch.setattr("onset_editor._candidate_peak_times_for_region", lambda *_args, **_kwargs: [1.04])
        monkeypatch.setattr(
            "onset_editor._diagnose_candidate_matches",
            lambda times, *_args, **_kwargs: {
                "results": [
                    {"time": 1.02, "passed": True, "combined_ratio": 0.95, "score": 0.8, "spectral_similarity": 0.7, "spectral_threshold": 0.3, "variable_threshold": 0.6, "failed_keys": []},
                    {"time": 1.04, "passed": True, "combined_ratio": 0.98, "score": 0.85, "spectral_similarity": 0.75, "spectral_threshold": 0.3, "variable_threshold": 0.6, "failed_keys": []},
                    {"time": 1.06, "passed": False, "combined_ratio": 0.5, "score": 0.4, "spectral_similarity": 0.2, "spectral_threshold": 0.3, "variable_threshold": 0.6, "failed_keys": ["peak_frequency_hz"]},
                ],
                "best_result": {"time": 1.04, "passed": True, "combined_ratio": 0.98, "score": 0.85, "spectral_similarity": 0.75, "spectral_threshold": 0.3, "variable_threshold": 0.6, "failed_keys": []},
                "passed": True,
                "spectral_threshold": 0.3,
                "variable_threshold": 0.6,
            },
        )

        report = _recover_focus_region_onset(
            np.zeros(16000, dtype=float),
            8000,
            {"t_start": 1.0, "t_end": 1.1, "f_low": 100, "f_high": 400},
            {"regions": [{"t_start": 1.0, "t_end": 1.1, "f_low": 100, "f_high": 400, "peak_frequency_hz": 200.0}]},
            {"peak_frequency_hz": {"enabled": True, "lower_pct": 20, "upper_pct": 20}},
            {"ONSET_HOP_LENGTH": 128, "_spectral_match_threshold": 0.3, "_per_signal_variable_score_threshold": 0.6},
        )

        assert report["recovered_time"] == 1.02

    def test_format_match_miss_reason_lists_main_failure_modes(self):
        text = _format_match_miss_reason({
            "spectral_similarity": 0.21,
            "spectral_threshold": 0.30,
            "score": 0.42,
            "variable_threshold": 0.60,
            "failed_keys": ["peak_frequency_hz", "harmonicity"],
        })

        assert "spectral 0.21/0.30" in text
        assert "variable 0.42/0.60" in text
        assert "peak_frequency_hz" in text

    def test_merge_negative_detection_hits_coalesces_duplicates(self):
        hits = []

        _merge_negative_detection_hits(hits, 1.0, 0.42, 1)
        _merge_negative_detection_hits(hits, 1.0005, 0.73, 2)
        _merge_negative_detection_hits(hits, 1.2, 0.25, 3)

        assert len(hits) == 2
        assert abs(hits[0]["time"] - 1.0) < 1e-6
        assert hits[0]["similarity"] == 0.73
        assert hits[0]["signal_nums"] == [1, 2]
        assert abs(hits[1]["time"] - 1.2) < 1e-6
        assert hits[1]["signal_nums"] == [3]




# ═══════════════════════════════════════════════════════════════════════════
# Widget tests (require Qt event loop)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_panel_construction(qapp):
    """OnsetEditorPanel can be constructed without errors."""
    panel = OnsetEditorPanel()
    assert panel is not None
    assert panel._table.columnCount() == 5


def test_panel_get_set_values(qapp):
    """get_values / set_values roundtrip."""
    panel = OnsetEditorPanel()
    vals = panel.get_values()
    assert "folder" in vals
    assert "file" in vals


def test_panel_add_remove_onset(qapp):
    """Adding and removing onsets updates internal state."""
    panel = OnsetEditorPanel()
    panel._add_onset(1.0)
    assert len(panel._onset_times) == 1
    assert abs(panel._onset_times[0] - 1.0) < 1e-6
    panel._add_onset(0.5)
    assert len(panel._onset_times) == 2
    assert panel._onset_times[0] < panel._onset_times[1]  # sorted
    panel._remove_onset(0)
    assert len(panel._onset_times) == 1
    assert abs(panel._onset_times[0] - 1.0) < 1e-6


def test_panel_undo_redo(qapp):
    """Undo/redo works for onset edits."""
    panel = OnsetEditorPanel()
    panel._add_onset(1.0)
    panel._add_onset(2.0)
    assert len(panel._onset_times) == 2
    panel._undo()
    assert len(panel._onset_times) == 1
    panel._redo()
    assert len(panel._onset_times) == 2


def test_panel_duplicate_prevention(qapp):
    """Adding an onset within 1ms of existing is rejected."""
    panel = OnsetEditorPanel()
    panel._add_onset(1.0)
    panel._add_onset(1.0005)  # within 1ms
    assert len(panel._onset_times) == 1


def test_panel_table_sync(qapp):
    """Table row count matches onset count."""
    panel = OnsetEditorPanel()
    panel._add_onset(0.5)
    panel._add_onset(1.5)
    panel._add_onset(2.5)
    assert panel._table.rowCount() == 3
    panel._remove_onset(1)
    assert panel._table.rowCount() == 2


def test_analyze_signals_dialog_shows_recommendations(qapp):
    """AnalyzeSignalsDialog should display recommendation text when provided."""
    recommendation = {
        "settings": {
            "ONSET_METHOD": "superflux",
            "ONSET_HOP_LENGTH": 128,
            "ONSET_DELTA": 0.07,
            "ONSET_BACKTRACK": False,
            "MIN_INTER_ONSET_MS": 12,
            "ONSET_AMPLITUDE_GATE": 0.05,
            "ONSET_SHARPNESS_GATE": 0.11,
            "CLUSTER_OVERLAPPING_ONSETS": True,
            "ONSET_CLUSTER_WINDOW_MS": 18,
            "ONSET_REFINE_ENABLED": True,
            "ONSET_REFINE_WINDOW_MS": 6.0,
        },
        "reasoning": {"ONSET_METHOD": "best match"},
    }
    profile = {
        "summary": {"n_regions": 1, "freq_range_hz": [400, 1200], "signal_character": "percussive", "harmonicity": 0.2, "attack_sharpness": 0.9, "avg_signal_duration_s": 0.04},
        "negative_summary": {"n_regions": 1, "freq_range_hz": [1800, 3200], "signal_character": "harmonic", "harmonicity": 0.8, "attack_sharpness": 0.1},
    }

    dlg = _AnalyzeSignalsDialog(
        recommendation_result=recommendation,
        signal_profile=profile,
    )

    text = dlg._recommended_text.toPlainText()
    assert "superflux" in text.lower() or "ONSET_METHOD" in text
    # Frame should be marked visible (not hidden) when recommendations are provided
    assert not dlg._recommended_frame.isHidden()


def test_analyze_signals_dialog_apply_callback(qapp):
    """Apply to Onset Finder should forward recommended settings."""
    recommendation = {
        "settings": {
            "ONSET_METHOD": "adaptive_hp",
            "ONSET_HOP_LENGTH": 512,
        },
    }
    applied = []
    dlg = _AnalyzeSignalsDialog(
        recommendation_result=recommendation,
        apply_callback=lambda settings: applied.append(settings),
    )
    dlg._apply_to_onset_finder()

    assert applied
    assert applied[0]["ONSET_METHOD"] == "adaptive_hp"
    assert applied[0]["ONSET_HOP_LENGTH"] == 512


def test_per_signal_config_dialog_defaults(qapp):
    profiles = [
        {
            "region": {"t_start": 0.25, "t_end": 0.5, "f_low": 100.0, "f_high": 1200.0},
            "analysis": {
                "spectral_centroid_hz": 600.0,
                "spectral_bandwidth_hz": 300.0,
                "harmonicity": 0.5,
                "duration_s": 0.25,
            },
        }
    ]

    dlg = _PerSignalConfigDialog(profiles)

    assert dlg.windowTitle() == "Per-Signal Match Settings"
    assert dlg.get_profiles() == profiles

    configs = dlg.get_configs()
    assert len(configs) == 1
    assert configs[0]["spectral_centroid_hz"]["enabled"] is True
    assert configs[0]["spectral_centroid_hz"]["lower_bound"] == pytest.approx(480.0)
    assert configs[0]["spectral_centroid_hz"]["upper_bound"] == pytest.approx(720.0)
    assert configs[0]["harmonicity"]["lower_bound"] == pytest.approx(0.375)
    assert configs[0]["duration_s"]["upper_bound"] == pytest.approx(0.375)


def test_per_signal_config_dialog_negative_title(qapp):
    dlg = _PerSignalConfigDialog(
        [{"region": {}, "analysis": {"spectral_centroid_hz": 500.0}}],
        mode="negative",
    )

    assert dlg.windowTitle() == "Negative Signal Match Settings"


def test_layer_checkbox_menu_rebuild_sort_and_toggle(qapp):
    menu = _LayerCheckboxMenu()
    layers = [
        {"name": "Beta", "onset_times": [0.1, 0.2]},
        {"name": "Alpha", "onset_times": [0.3]},
        {"name": "Gamma", "onset_times": [0.4, 0.5, 0.6]},
    ]

    menu.rebuild(layers, {1, 2})
    assert menu.get_checked_indices() == [1, 2]
    assert menu.get_sort_mode() == menu.SORT_CREATED

    menu._cycle_sort()
    menu.rebuild(layers, {0, 1, 2})
    assert menu.get_sort_mode() == menu.SORT_COUNT
    assert menu.get_checked_indices() == [2, 0, 1]

    menu._toggle_select_all()
    assert menu.get_checked_indices() == []
    assert menu._select_all_btn.text() == "☐ None"


def test_onset_manager_dialog_tracks_changes(qapp):
    dlg = OnsetManagerDialog(
        audio_path="/tmp/example.wav",
        label_path="/tmp/example.txt",
        onset_times=[0.1, 0.2, 0.3],
        comp_files=[
            {
                "path": "/tmp/compare.txt",
                "label": "compare.txt",
                "times": [0.1, 0.4],
                "color": (0, 200, 255, 200),
            }
        ],
        comp_palette=[(0, 200, 255, 200), (255, 165, 0, 200)],
        tolerance_ms=8.5,
        filter_idx=1,
        color_main_only=(255, 80, 80, 220),
        color_shared=(255, 255, 255, 240),
    )

    dlg._tol_spin.setValue(12.0)
    dlg._filter_combo.setCurrentIndex(3)
    dlg._remove_comp(0)

    changes = dlg.get_changes()

    assert changes["tolerance_ms"] == pytest.approx(12.0)
    assert changes["filter_idx"] == 3
    assert changes["comp_files"] == []
    assert dlg._comp_empty_label.isHidden() is False
    assert dlg._add_shared_btn.isEnabled() is False


def test_detect_dialog_effective_settings(qapp):
    """DetectOnsetsDialog should expose effective settings from its controls."""
    dlg = _DetectOnsetsDialog(
        0.0,
        1.0,
        3.0,
        selection_available=True,
    )
    dlg._method_combo.setCurrentText("adaptive_hp")
    dlg._hop_spin.setValue(512)
    dlg._post_enabled_cb.setChecked(False)

    effective = dlg.effective_settings()
    assert effective["ONSET_METHOD"] == "adaptive_hp"
    assert effective["ONSET_HOP_LENGTH"] == 512
    assert effective["ONSET_REFINE_ENABLED"] is False


def test_panel_build_focus_signal_profile(qapp):
    """Current positive/negative focus regions should build a usable profile."""
    panel = OnsetEditorPanel()
    sr = 8000
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    y = 0.6 * np.sin(2 * np.pi * 600 * t)
    y += 0.3 * np.sin(2 * np.pi * 2200 * t)

    class _ViewerStub:
        audioData = y
        sampleRate = sr

    panel._viewer = _ViewerStub()
    panel._audio_path = "/tmp/example.wav"
    panel._focus_regions = {
        "example.wav": [
            {"t_start": 0.05, "t_end": 0.15, "f_low": 450, "f_high": 900, "polarity": "positive"},
            {"t_start": 0.25, "t_end": 0.35, "f_low": 1800, "f_high": 2600, "polarity": "negative"},
        ]
    }

    profile = panel._build_focus_signal_profile()
    assert profile is not None
    assert profile["summary"]["n_regions"] == 1
    assert profile["negative_summary"]["n_regions"] == 1
    assert profile["summary"]["freq_range_hz"][0] <= 500
    assert profile["negative_summary"]["freq_range_hz"][1] >= 2400


def test_build_region_detector_kwargs_adaptive_hp_uses_expected_keys():
    """Adaptive HP region detection should translate to onset_detectors kwargs."""
    method, kwargs = _build_region_detector_kwargs({
        "ONSET_METHOD": "adaptive_hp",
        "HP_SMOOTH_LAMBDA": 25,
        "HP_THRESHOLD_LAMBDA": 1e6,
        "HP_ENVELOPE_WINDOW_MS": 8,
        "HP_ENVELOPE_HOP_MS": 2,
    })

    assert method == "adaptive_hp"
    assert kwargs == {
        "hp_smooth_lambda": 25.0,
        "hp_threshold_lambda": 1e6,
        "envelope_window_ms": 8.0,
        "envelope_hop_ms": 2.0,
    }


def test_run_simple_detection_dispatches_selected_method(monkeypatch):
    """Region detection should dispatch through onset_detectors using effective settings."""
    import onset_detectors
    import onset_postprocessing

    called = {}

    def fake_detect_onsets(method, signal, sr, **kwargs):
        called["method"] = method
        called["kwargs"] = kwargs
        return np.array([0.1, 0.3], dtype=float)

    monkeypatch.setattr(onset_detectors, "detect_onsets", fake_detect_onsets)
    monkeypatch.setattr(onset_detectors, "refine_onsets_to_sample", lambda onsets, *a, **k: onsets)
    monkeypatch.setattr(onset_postprocessing, "cluster_onsets", lambda onsets, *_: onsets)
    monkeypatch.setattr(onset_postprocessing, "gate_onsets_by_amplitude", lambda onsets, *a, **k: onsets)
    monkeypatch.setattr(onset_postprocessing, "gate_onsets_by_sharpness", lambda onsets, *a, **k: onsets)
    monkeypatch.setattr(onset_postprocessing, "enforce_min_interval", lambda onsets, *_: onsets)

    result = OnsetEditorPanel._run_simple_detection(
        np.zeros(2048, dtype=float),
        8000,
        999,
        settings={
            "ONSET_METHOD": "adaptive_hp",
            "HP_SMOOTH_LAMBDA": 30,
            "HP_THRESHOLD_LAMBDA": 2e6,
            "HP_ENVELOPE_WINDOW_MS": 9,
            "HP_ENVELOPE_HOP_MS": 2,
            "CLUSTER_OVERLAPPING_ONSETS": False,
            "ONSET_REFINE_ENABLED": False,
        },
    )

    assert result == [0.1, 0.3]
    assert called["method"] == "adaptive_hp"
    assert called["kwargs"]["hp_smooth_lambda"] == 30.0
    assert called["kwargs"]["hp_threshold_lambda"] == 2e6


def test_detect_dialog_effective_settings_include_method_specific_values(qapp):
    """Effective settings should include advanced controls for the chosen method."""
    dlg = _DetectOnsetsDialog(0.0, 1.0, 3.0, selection_available=True)
    dlg._method_combo.setCurrentText("per_band")
    dlg._perband_bands_spin.setValue(9)
    dlg._perband_fmin_spin.setValue(350)
    dlg._perband_fmax_spin.setValue(7200)
    dlg._perband_minbands_spin.setValue(3)

    effective = dlg.effective_settings()
    assert effective["ONSET_METHOD"] == "per_band"
    assert effective["PER_BAND_N_BANDS"] == 9
    assert effective["PER_BAND_FREQ_MIN"] == 350
    assert effective["PER_BAND_FREQ_MAX"] == 7200
    assert effective["PER_BAND_MIN_BANDS"] == 3


def test_detect_dialog_full_clip_controls_and_sorted_range(qapp):
    """Onset Finder should support full-clip fallback and typed range edits."""
    dlg = _DetectOnsetsDialog(0.4, 1.2, 2.5, selection_available=True)

    assert dlg.selected_range() == (0.4, 1.2)
    dlg._apply_full_clip_range()
    assert dlg.selected_range() == (0.0, 2.5)
    assert dlg.using_full_clip() is True

    dlg._start_spin.setValue(1.8)
    dlg._end_spin.setValue(0.6)
    assert dlg.selected_range() == (0.6, 1.8)


def test_detect_dialog_uses_scroll_area_for_large_content(qapp):
    """Quick Onset Finder should remain navigable via a scroll area."""
    from PyQt6.QtWidgets import QScrollArea

    dlg = _DetectOnsetsDialog(0.1, 0.9, 2.5, selection_available=True)
    scroll_areas = dlg.findChildren(QScrollArea)

    assert scroll_areas, "Expected Quick Onset Finder dialog to include a QScrollArea"
    assert scroll_areas[0].widgetResizable() is True
    assert scroll_areas[0].widget() is not None


def test_detect_dialog_locked_to_focus_range(qapp):
    """Quick Onset Finder should lock timing controls when a focus range is enforced."""
    dlg = _DetectOnsetsDialog(
        0.1,
        0.9,
        2.5,
        selection_available=True,
        locked_range=(0.2, 0.6),
    )

    assert dlg.selected_range() == (0.2, 0.6)
    assert dlg._start_spin.isEnabled() is False
    assert dlg._end_spin.isEnabled() is False
    assert dlg._use_selection_btn.isEnabled() is False
    assert dlg._use_full_btn.isEnabled() is False


def test_edit_audio_dialog_full_clip_controls(qapp):
    """Audio Editor should expose editable ranges and full-clip mode."""
    dlg = _EditAudioDialog(0.25, 0.75, 2.0, selection_available=False)

    assert dlg._use_selection_btn.isEnabled() is False
    assert dlg.selected_range() == (0.25, 0.75)
    dlg._apply_full_clip_range()
    assert dlg.selected_range() == (0.0, 2.0)
    assert dlg.using_full_clip() is True


def test_edit_audio_dialog_uses_scroll_area_for_large_content(qapp):
    """Quick Audio Editor should remain navigable via a scroll area."""
    from PyQt6.QtWidgets import QScrollArea

    dlg = _EditAudioDialog(0.25, 0.75, 2.0, selection_available=True)
    scroll_areas = dlg.findChildren(QScrollArea)

    assert scroll_areas, "Expected Quick Audio Editor dialog to include a QScrollArea"
    assert scroll_areas[0].widgetResizable() is True
    assert scroll_areas[0].widget() is not None


def test_edit_audio_dialog_locked_to_focus_range(qapp):
    """Quick Audio Editor should lock timing controls when a focus range is enforced."""
    dlg = _EditAudioDialog(
        0.25,
        0.75,
        2.0,
        selection_available=True,
        locked_range=(0.3, 0.5),
    )

    assert dlg.selected_range() == (0.3, 0.5)
    assert dlg._start_spin.isEnabled() is False
    assert dlg._end_spin.isEnabled() is False
    assert dlg._use_selection_btn.isEnabled() is False
    assert dlg._use_full_btn.isEnabled() is False


def test_focus_locked_time_range_uses_selected_focus_region(qapp):
    """When focus mode is enabled, quick tools should use selected focus region time bounds."""
    panel = OnsetEditorPanel()
    panel._focus_mode = True

    class _ViewerStub:
        audioData = np.zeros(4000, dtype=float)
        duration = 2.0

        def get_selected_focus_region(self):
            return {"t_start": 0.45, "t_end": 1.25}

    panel._viewer = _ViewerStub()

    assert panel._get_focus_locked_time_range() == (0.45, 1.25)


def test_focus_locked_time_range_none_without_selected_focus_region(qapp):
    """Focus-locked range should be unavailable when no focus region is selected."""
    panel = OnsetEditorPanel()
    panel._focus_mode = True

    class _ViewerStub:
        audioData = np.zeros(4000, dtype=float)
        duration = 2.0

        def get_selected_focus_region(self):
            return None

    panel._viewer = _ViewerStub()

    assert panel._get_focus_locked_time_range() is None


def test_quick_audio_editor_button_label(qapp):
    """The Onset Editor should expose a Quick Audio Editor button."""
    panel = OnsetEditorPanel()
    assert "Quick Audio Editor" in panel._edit_audio_btn.text()


def test_update_button_states_keeps_tools_enabled_without_selection(qapp):
    """Onset Finder and Audio Editor should stay available when audio is loaded."""
    panel = OnsetEditorPanel()
    panel._audio_path = "/tmp/example.wav"
    panel._selected_region = None

    class _ViewerStub:
        audioData = np.zeros(8000, dtype=float)
        duration = 1.0

        def clear_selection_region(self):
            return None

        def clear_focus_region_selection(self, emit_signal=False):
            return None

        def clear_loop(self):
            return None

    panel._viewer = _ViewerStub()
    panel._clear_selection_state()
    panel._update_button_states()

    assert panel._detect_region_btn.isEnabled() is True
    assert panel._edit_audio_btn.isEnabled() is True
    assert panel._play_sel_btn.isEnabled() is False
    assert panel._loop_sel_btn.isEnabled() is False


def test_delete_current_selection_prefers_focus_region(qapp):
    """Delete should remove the selected focus region before touching onset rows."""
    panel = OnsetEditorPanel()
    panel._audio_path = "/tmp/example.wav"
    panel._focus_regions = {"example.wav": [{"polarity": "positive"}]}

    class _ViewerStub:
        def __init__(self):
            self.deleted = False

        def remove_selected_focus_region(self):
            self.deleted = True
            return True

    viewer = _ViewerStub()
    panel._viewer = viewer

    called = []
    panel._remove_selected_onset = lambda: called.append(True)

    panel._delete_current_selection()

    assert viewer.deleted is True
    assert called == []


def test_play_selection_prefers_selected_focus_region(qapp):
    """Play Selection should audition the selected focus ROI as a band-limited clip."""
    panel = OnsetEditorPanel()
    panel._selected_region = (0.2, 0.6)

    class _ViewerStub:
        def __init__(self):
            self.calls = []
            self._playing = False

        def stop(self):
            self.calls.append(("stop",))

        def get_selected_focus_region(self):
            return {"t_start": 0.2, "t_end": 0.6, "f_low": 400, "f_high": 1400}

        def play_focus_region(self, region, loop=False):
            self.calls.append(("focus", region, loop))

    panel._viewer = _ViewerStub()
    panel._loop_sel_btn.setChecked(False)
    panel._play_selection()

    assert panel._viewer.calls[0] == ("stop",)
    assert panel._viewer.calls[1][0] == "focus"
    assert panel._viewer.calls[1][2] is False


def test_table_selection_highlights_and_centers_onset(qapp):
    """Selecting a table row should highlight and center the same onset in the viewer."""
    panel = OnsetEditorPanel()
    panel._onset_times = [0.5, 1.25, 2.0]

    class _ViewerStub:
        def __init__(self):
            self.calls = []

        def select_onset(self, index, center=False, seek_playhead=False):
            self.calls.append(("select_onset", index, center, seek_playhead))

    panel._viewer = _ViewerStub()

    panel._focus_table_onset(1)

    assert panel._viewer.calls == [("select_onset", 1, True, False)]


def test_table_click_refocuses_same_onset(qapp):
    """Clicking an already-selected table cell should still re-center the onset."""
    panel = OnsetEditorPanel()
    panel._onset_times = [0.5, 1.25, 2.0]

    class _ViewerStub:
        def __init__(self):
            self.calls = []

        def select_onset(self, index, center=False, seek_playhead=False):
            self.calls.append(("select_onset", index, center, seek_playhead))

    panel._viewer = _ViewerStub()

    panel._on_table_cell_clicked(2, panel._COL_TIME)

    assert panel._viewer.calls == [("select_onset", 2, True, False)]


# ═══════════════════════════════════════════════════════════════════════════
# Excel column-preservation tests
# ═══════════════════════════════════════════════════════════════════════════

class TestWriteRecordingToExcel:
    """Verify _write_recording_to_excel preserves all columns."""

    @staticmethod
    def _make_source_excel(path):
        """Create a 27-column source Excel like onset_finder produces."""
        import pandas as pd
        cols = {
            "File Name": ["drum01.wav", "drum02.wav"],
            "Total Duration (s)": [10.5, 12.0],
            "Estimated Overall BPM": [120.0, 130.0],
            "Average Cycle Duration (ms)": [500.0, 460.0],
            "Avg Loudness (Energy)": [0.5, 0.6],
            "Avg Brightness (Centroid Hz)": [3000.0, 3200.0],
            "Total Onsets Found (Raw)": [20, 25],
            "Total Onsets Used": [15, 20],
            "Onsets Merged by Clustering": [5, 5],
            "High-Pass Filter Hz": [100, 100],
            "Amplitude Gate Threshold": [0.02, 0.02],
            "Sharpness Gate Threshold": [0.5, 0.5],
            "Min Inter-Onset (ms)": [50, 50],
            "Onset Delta": [0.07, 0.07],
            "Onset Method": ["hfc", "hfc"],
            "Active Preset": ["Default", "Default"],
            "Onset Refinement": ["enabled", "enabled"],
            "Stable Dyads Retained": [8, 10],
            "Stable Rhythm Filter Enabled": [True, True],
            "nPVI (Isochrony)": [25.0, 30.0],
            "CV of Intervals": [0.15, 0.12],
            "r_k Std Dev": [0.08, 0.07],
            "r_k Entropy (Categorical Measure)": [1.5, 1.6],
            "Stable Rhythm nPVI": [20.0, 25.0],
            "Stable Rhythm CV": [0.10, 0.09],
            "Stable Rhythm r_k Std Dev": [0.05, 0.04],
            "Stable Rhythm Entropy": [1.2, 1.3],
            "Exact Onset Times Used (s)": [
                "0.1, 0.6, 1.1, 1.6, 2.1",
                "0.2, 0.7, 1.2, 1.7, 2.2",
            ],
        }
        df = pd.DataFrame(cols)
        with pd.ExcelWriter(path, engine="openpyxl") as w:
            df.to_excel(w, sheet_name="File Summaries", index=False)
            # Add an extra sheet to verify preservation
            pd.DataFrame({"note": ["hello"]}).to_excel(
                w, sheet_name="Metadata", index=False)

    def test_overwrite_preserves_all_columns(self, qapp, tmp_path):
        """Overwriting onsets in an existing file must keep all 27+ columns."""
        import pandas as pd
        xls = str(tmp_path / "test.xlsx")
        self._make_source_excel(xls)

        panel = OnsetEditorPanel()
        new_onsets = [0.1, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        panel._write_recording_to_excel(xls, "drum01.wav", new_onsets)

        result = pd.read_excel(xls, sheet_name="File Summaries")
        # All 27 original columns must still be present
        assert len(result.columns) >= 27, (
            f"Expected >=27 columns, got {len(result.columns)}: {list(result.columns)}")
        # Non-onset columns must be untouched
        row = result[result["File Name"] == "drum01.wav"].iloc[0]
        assert row["Total Duration (s)"] == 10.5
        assert row["Estimated Overall BPM"] == 120.0
        assert row["Avg Loudness (Energy)"] == 0.5
        assert row["Onset Method"] == "hfc"
        # Onset columns must reflect the new data
        assert row["Total Onsets Used"] == 7
        assert "0.100000" in str(row["Exact Onset Times Used (s)"])
        # Other row untouched
        row2 = result[result["File Name"] == "drum02.wav"].iloc[0]
        assert row2["Total Onsets Used"] == 20

    def test_overwrite_preserves_extra_sheets(self, qapp, tmp_path):
        """Extra sheets in the workbook must survive a save."""
        import pandas as pd
        xls = str(tmp_path / "test.xlsx")
        self._make_source_excel(xls)

        panel = OnsetEditorPanel()
        panel._write_recording_to_excel(xls, "drum01.wav", [0.5, 1.0, 1.5])

        sheets = pd.ExcelFile(xls, engine="openpyxl").sheet_names
        assert "Metadata" in sheets

    def test_new_file_from_source_preserves_columns(self, qapp, tmp_path):
        """Save-as-new from a source Excel must copy all columns."""
        import pandas as pd
        src = str(tmp_path / "source.xlsx")
        dst = str(tmp_path / "dest.xlsx")
        self._make_source_excel(src)

        panel = OnsetEditorPanel()
        panel._write_recording_to_excel(
            dst, "drum01.wav", [0.2, 0.8, 1.4, 2.0], source_excel=src)

        result = pd.read_excel(dst, sheet_name="File Summaries")
        assert len(result.columns) >= 27
        row = result[result["File Name"] == "drum01.wav"].iloc[0]
        assert row["Total Onsets Used"] == 4
        assert row["Total Duration (s)"] == 10.5  # preserved from source

    def test_rhythm_metrics_recomputed(self, qapp, tmp_path):
        """nPVI, CV, etc. must be recomputed, not just kept from old data."""
        import pandas as pd
        xls = str(tmp_path / "test.xlsx")
        self._make_source_excel(xls)

        # Use perfectly isochronous onsets → nPVI should be ~0
        even = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        panel = OnsetEditorPanel()
        panel._write_recording_to_excel(xls, "drum01.wav", even)

        result = pd.read_excel(xls, sheet_name="File Summaries")
        row = result[result["File Name"] == "drum01.wav"].iloc[0]
        npvi = row["nPVI (Isochrony)"]
        assert npvi != "N/A"
        assert float(npvi) < 5.0  # near-isochronous → low nPVI


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
