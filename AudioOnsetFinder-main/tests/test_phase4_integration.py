"""Tests for Phase 4: Config persistence, focus masking, keyboard shortcuts."""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

from GUI.onset_editor import OnsetEditorPanel
import scripts.onset_finder as onset_finder
from scripts.onset_finder import apply_focus_regions


# ── 4.1 Config persistence ─────────────────────────────────────────────


def test_get_values_includes_focus_fields():
    panel = OnsetEditorPanel()
    vals = panel.get_values()
    assert "focus_mode" in vals
    assert "focus_polarity" in vals
    assert "active_layer_idx" in vals
    assert "layers" in vals


def test_get_values_layers_serializable():
    panel = OnsetEditorPanel()
    panel._onset_times.extend([1.0, 2.5])
    panel._focus_regions["test.wav"] = [
        {"t_start": 0.0, "t_end": 1.0, "f_low": 100, "f_high": 8000, "polarity": "positive"}
    ]
    vals = panel.get_values()
    layers = vals["layers"]
    assert len(layers) == 1
    assert layers[0]["onset_times"] == [1.0, 2.5]
    assert layers[0]["focus_regions"]["test.wav"][0]["polarity"] == "positive"
    # Should NOT contain undo_stack (not JSON-serializable)
    assert "undo_stack" not in layers[0]


def test_get_set_values_roundtrip():
    panel = OnsetEditorPanel()
    panel._onset_times.extend([0.5, 1.5, 3.0])
    panel._focus_regions["demo.wav"] = [
        {"t_start": 0.0, "t_end": 2.0, "f_low": 50, "f_high": 10000, "polarity": "positive"},
        {"t_start": 3.0, "t_end": 4.0, "f_low": 50, "f_high": 10000, "polarity": "negative"},
    ]
    panel._focus_polarity = "negative"
    panel._add_layer()
    panel._onset_times.extend([10.0, 20.0])
    vals = panel.get_values()

    # Create a fresh panel and restore
    panel2 = OnsetEditorPanel()
    panel2.set_values(vals)
    assert panel2._active_layer_idx == 1
    assert len(panel2._layers) == 2
    assert panel2._layers[0]["onset_times"] == [0.5, 1.5, 3.0]
    assert panel2._layers[1]["onset_times"] == [10.0, 20.0]
    assert len(panel2._layers[0]["focus_regions"]["demo.wav"]) == 2
    assert panel2._focus_polarity == "negative"


def test_set_values_empty_layers():
    """set_values with no layers key should not break."""
    panel = OnsetEditorPanel()
    panel.set_values({"folder_auto": True})
    assert len(panel._layers) == 1


def test_set_values_clamps_active_idx():
    panel = OnsetEditorPanel()
    panel.set_values({
        "layers": [
            {"name": "L1", "onset_times": [], "focus_regions": {}, "dirty": False},
        ],
        "active_layer_idx": 99,
    })
    assert panel._active_layer_idx == 0


def test_set_values_focus_mode_false():
    """set_values with focus_mode=False should not enable focus."""
    panel = OnsetEditorPanel()
    panel.set_values({"focus_mode": False})
    assert panel._focus_mode is False
    assert panel._focus_onsets_btn.isChecked() is False


def test_set_values_invalid_polarity_ignored():
    """Invalid polarity values should not be applied."""
    panel = OnsetEditorPanel()
    panel.set_values({"focus_polarity": "invalid_value"})
    assert panel._focus_polarity == "positive"  # default unchanged


# ── 4.2 Focus region masking (onset_finder) ────────────────────────────


def test_apply_focus_regions_empty():
    onsets = np.array([1.0, 2.0, 3.0])
    result = apply_focus_regions(onsets, [])
    np.testing.assert_array_equal(result, onsets)


def test_apply_focus_regions_no_onsets():
    regions = [{"t_start": 0.0, "t_end": 5.0, "polarity": "positive"}]
    result = apply_focus_regions([], regions)
    assert len(result) == 0


def test_apply_focus_regions_positive():
    onsets = np.array([0.5, 1.5, 2.5, 3.5, 4.5])
    regions = [{"t_start": 1.0, "t_end": 3.0, "polarity": "positive"}]
    result = apply_focus_regions(onsets, regions)
    np.testing.assert_array_equal(result, [1.5, 2.5])


def test_apply_focus_regions_negative():
    onsets = np.array([0.5, 1.5, 2.5, 3.5, 4.5])
    regions = [{"t_start": 1.0, "t_end": 3.0, "polarity": "negative"}]
    result = apply_focus_regions(onsets, regions)
    np.testing.assert_array_equal(result, [0.5, 3.5, 4.5])


def test_apply_focus_regions_multiple_positive():
    onsets = np.array([0.5, 1.5, 3.5, 5.5, 7.5])
    regions = [
        {"t_start": 1.0, "t_end": 2.0, "polarity": "positive"},
        {"t_start": 5.0, "t_end": 6.0, "polarity": "positive"},
    ]
    result = apply_focus_regions(onsets, regions)
    np.testing.assert_array_equal(result, [1.5, 5.5])


def test_apply_focus_regions_mixed_polarity():
    onsets = np.array([0.5, 1.5, 2.5, 3.5, 4.5])
    regions = [
        {"t_start": 0.0, "t_end": 4.0, "polarity": "positive"},
        {"t_start": 2.0, "t_end": 3.0, "polarity": "negative"},
    ]
    result = apply_focus_regions(onsets, regions)
    np.testing.assert_array_equal(result, [0.5, 1.5, 3.5])


def test_apply_focus_regions_boundary_inclusive():
    onsets = np.array([1.0, 2.0, 3.0])
    regions = [{"t_start": 1.0, "t_end": 3.0, "polarity": "positive"}]
    result = apply_focus_regions(onsets, regions)
    np.testing.assert_array_equal(result, [1.0, 2.0, 3.0])


# ── 4.4 Keyboard shortcuts ─────────────────────────────────────────────


def test_shortcut_methods_exist():
    panel = OnsetEditorPanel()
    assert hasattr(panel, '_toggle_focus_mode_shortcut')
    assert hasattr(panel, '_prev_layer_shortcut')
    assert hasattr(panel, '_next_layer_shortcut')


def test_onset_finder_comment_author_defined():
    assert isinstance(onset_finder.COLUMN_COMMENT_AUTHOR, str)
    assert onset_finder.COLUMN_COMMENT_AUTHOR.strip()


def test_toggle_focus_mode_shortcut():
    panel = OnsetEditorPanel()
    assert panel._focus_mode is False
    panel._toggle_focus_mode_shortcut()
    assert panel._focus_onsets_btn.isChecked() is True
    assert panel._focus_mode is True
    # Toggle back off
    panel._toggle_focus_mode_shortcut()
    assert panel._focus_onsets_btn.isChecked() is False
    assert panel._focus_mode is False


def test_layer_switching_shortcuts():
    panel = OnsetEditorPanel()
    panel._add_layer()
    panel._add_layer()
    # Now at layer 2 (index 2)
    assert panel._layer_combo.currentIndex() == 2
    panel._prev_layer_shortcut()
    assert panel._layer_combo.currentIndex() == 1
    panel._prev_layer_shortcut()
    assert panel._layer_combo.currentIndex() == 0
    # Should not go below 0
    panel._prev_layer_shortcut()
    assert panel._layer_combo.currentIndex() == 0
    panel._next_layer_shortcut()
    assert panel._layer_combo.currentIndex() == 1
    panel._next_layer_shortcut()
    assert panel._layer_combo.currentIndex() == 2
    # Should not go above max
    panel._next_layer_shortcut()
    assert panel._layer_combo.currentIndex() == 2
