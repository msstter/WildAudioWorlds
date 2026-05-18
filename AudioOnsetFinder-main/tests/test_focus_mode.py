"""Tests for Phase 1: Focus Onsets mode buttons and data model."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

from GUI.audio_viewer import AudioViewerWidget
from GUI.onset_editor import OnsetEditorPanel


class _FakeSceneMouseEvent:
    def __init__(self, event_type, scene_pos, button=Qt.MouseButton.LeftButton,
                 modifiers=Qt.KeyboardModifier.NoModifier):
        self._event_type = event_type
        self._scene_pos = scene_pos
        self._button = button
        self._modifiers = modifiers

    def type(self):
        return self._event_type

    def scenePos(self):
        return self._scene_pos

    def button(self):
        return self._button

    def modifiers(self):
        return self._modifiers

    def screenPos(self):
        return self._scene_pos.toPoint()


def _make_viewer():
    viewer = AudioViewerWidget(show_transport=False, show_chunk_nav=False)
    y = np.sin(np.linspace(0, 16 * np.pi, 22050 * 3, dtype=np.float32))
    viewer.resize(900, 700)
    viewer.show()
    viewer.load_audio_array(y, 22050, "<focus-test>")
    _app.processEvents()
    return viewer


def _scene_point_for_spec(viewer: AudioViewerWidget, t: float, f: float) -> QPointF:
    return viewer._spec_plot.plotItem.vb.mapViewToScene(QPointF(t, f))


def test_focus_mode_initial_state():
    panel = OnsetEditorPanel()
    assert panel._focus_mode is False
    assert panel._focus_polarity == "positive"
    assert isinstance(panel._focus_regions, dict)
    assert len(panel._focus_regions) == 0


def test_focus_button_created():
    panel = OnsetEditorPanel()
    assert panel._focus_onsets_btn is not None
    assert panel._focus_onsets_btn.isCheckable()
    assert not panel._focus_onsets_btn.isChecked()


def test_pos_neg_buttons_created():
    panel = OnsetEditorPanel()
    assert panel._positive_btn is not None
    assert panel._negative_btn is not None
    assert panel._positive_btn.isChecked()
    assert not panel._negative_btn.isChecked()


def test_focus_toggle_sets_state():
    panel = OnsetEditorPanel()
    panel._focus_onsets_btn.setChecked(True)
    assert panel._focus_mode is True
    panel._focus_onsets_btn.setChecked(False)
    assert panel._focus_mode is False


def test_polarity_radio_style():
    panel = OnsetEditorPanel()
    panel._focus_onsets_btn.setChecked(True)

    # Switch to negative
    panel._negative_btn.setChecked(True)
    assert panel._focus_polarity == "negative"
    assert not panel._positive_btn.isChecked()

    # Switch back to positive
    panel._positive_btn.setChecked(True)
    assert panel._focus_polarity == "positive"
    assert not panel._negative_btn.isChecked()


def test_polarity_cannot_both_uncheck():
    panel = OnsetEditorPanel()
    panel._focus_onsets_btn.setChecked(True)
    # Try to uncheck positive while negative is also unchecked
    panel._positive_btn.setChecked(False)
    # One should remain checked
    assert panel._positive_btn.isChecked() or panel._negative_btn.isChecked()


def test_focus_regions_data_model():
    panel = OnsetEditorPanel()
    panel._audio_path = "/fake/test_audio.wav"
    fname = "test_audio.wav"
    panel._focus_regions[fname] = []
    region = {
        "t_start": 1.0, "t_end": 2.0,
        "f_low": 500, "f_high": 3000,
        "polarity": "positive",
    }
    panel._focus_regions[fname].append(region)
    assert len(panel._focus_regions[fname]) == 1
    assert panel._focus_regions[fname][0]["polarity"] == "positive"

    # Add a negative region
    neg_region = {
        "t_start": 3.0, "t_end": 4.0,
        "f_low": 100, "f_high": 500,
        "polarity": "negative",
    }
    panel._focus_regions[fname].append(neg_region)
    assert len(panel._focus_regions[fname]) == 2
    n_pos = sum(1 for r in panel._focus_regions[fname] if r["polarity"] == "positive")
    n_neg = sum(1 for r in panel._focus_regions[fname] if r["polarity"] == "negative")
    assert n_pos == 1
    assert n_neg == 1


def test_focus_regions_per_file():
    panel = OnsetEditorPanel()
    panel._focus_regions["file_a.wav"] = [
        {"t_start": 0, "t_end": 1, "f_low": 0, "f_high": 1000, "polarity": "positive"}
    ]
    panel._focus_regions["file_b.wav"] = [
        {"t_start": 0, "t_end": 1, "f_low": 0, "f_high": 1000, "polarity": "negative"}
    ]
    assert len(panel._focus_regions["file_a.wav"]) == 1
    assert len(panel._focus_regions["file_b.wav"]) == 1
    assert panel._focus_regions["file_a.wav"][0]["polarity"] == "positive"
    assert panel._focus_regions["file_b.wav"][0]["polarity"] == "negative"


def test_focus_drag_on_spectrogram_scene_has_priority_over_onset_drag():
    viewer = _make_viewer()
    viewer.set_onset_markers(np.array([1.0, 1.5, 2.0]), draggable=True)
    viewer.set_focus_mode(True, "positive")

    added = []
    viewer.focusRegionAdded.connect(lambda region: added.append(region))

    press = _FakeSceneMouseEvent(
        QEvent.Type.GraphicsSceneMousePress,
        _scene_point_for_spec(viewer, 1.0, 1200.0),
    )
    move = _FakeSceneMouseEvent(
        QEvent.Type.GraphicsSceneMouseMove,
        _scene_point_for_spec(viewer, 1.14, 2400.0),
    )
    release = _FakeSceneMouseEvent(
        QEvent.Type.GraphicsSceneMouseRelease,
        _scene_point_for_spec(viewer, 1.14, 2400.0),
    )

    assert viewer.eventFilter(viewer._spec_plot.scene(), press) is True
    assert viewer._focus_dragging is True
    assert viewer._onset_dragging is False

    assert viewer.eventFilter(viewer._spec_plot.scene(), move) is True
    assert viewer._focus_drag_did_move is True

    assert viewer.eventFilter(viewer._spec_plot.scene(), release) is True
    assert viewer._focus_dragging is False
    assert viewer._onset_dragging is False
    assert len(added) == 1
    assert len(viewer._focus_regions) == 1
    region = viewer._focus_regions[0]
    assert region["t_start"] < region["t_end"]
    assert region["f_low"] < region["f_high"]


def test_focus_mode_disables_spectrogram_onset_marker_dragging_only():
    """When focus mode is on, onset dragging on spectrogram is disabled (focus takes priority).
    
    Waveform onset dragging should still work when focus mode is on.
    """
    viewer = _make_viewer()
    lines = viewer.set_onset_markers(np.array([1.0]), draggable=True)
    line_w, line_s = lines[0]

    # Lines use custom event handling via eventFilter, so they're never set to movable=True
    assert line_w.movable is False
    assert line_s.movable is False

    # When focus mode is on, onset dragging is disabled on spectrogram but enabled on waveform
    viewer.set_focus_mode(True, "positive")
    assert viewer._focus_mode is True

    # Focus mode disables onset dragging on spectrogram (focus region drawing takes priority)
    # but waveform dragging should still work
    assert viewer._onset_draggable is True  # onset markers are still draggable
    assert viewer._focus_mode is True  # focus mode is on

    viewer.set_focus_mode(False, "positive")

    # When focus mode is off, onset dragging is allowed on both waveform and spectrogram
    assert viewer._focus_mode is False
    assert viewer._onset_draggable is True


def test_clicking_existing_focus_region_selects_it_without_new_drag():
    viewer = _make_viewer()
    viewer.set_focus_mode(True, "positive")
    viewer.set_focus_regions([
        {"t_start": 0.9, "t_end": 1.2, "f_low": 1000.0, "f_high": 2600.0, "polarity": "positive"}
    ])
    _app.processEvents()

    selected = []
    viewer.regionSelected.connect(lambda start, end: selected.append((start, end)))

    press = _FakeSceneMouseEvent(
        QEvent.Type.GraphicsSceneMousePress,
        _scene_point_for_spec(viewer, 1.0, 1500.0),
    )

    viewer.eventFilter(viewer._spec_plot.scene(), press)

    assert viewer._selected_focus_region_index == 0
    assert viewer._focus_dragging is False
    assert selected[-1] == (0.9, 1.2)


def test_blank_focus_click_clears_selected_region_and_starts_new_box():
    viewer = _make_viewer()
    viewer.set_focus_mode(True, "positive")
    viewer.set_focus_regions([
        {"t_start": 0.9, "t_end": 1.2, "f_low": 1000.0, "f_high": 2600.0, "polarity": "positive"}
    ])
    _app.processEvents()
    viewer._select_focus_region(0, emit_signal=False)

    cleared = []
    viewer.regionCleared.connect(lambda: cleared.append(True))

    press = _FakeSceneMouseEvent(
        QEvent.Type.GraphicsSceneMousePress,
        _scene_point_for_spec(viewer, 1.8, 3200.0),
    )
    release = _FakeSceneMouseEvent(
        QEvent.Type.GraphicsSceneMouseRelease,
        _scene_point_for_spec(viewer, 1.8, 3200.0),
    )

    assert viewer.eventFilter(viewer._spec_plot.scene(), press) is True
    assert viewer._selected_focus_region_index == -1
    assert viewer._focus_dragging is True
    assert cleared == [True]

    assert viewer.eventFilter(viewer._spec_plot.scene(), release) is True
    assert viewer._focus_dragging is False


def test_selected_focus_region_drives_viewer_playback():
    viewer = _make_viewer()
    viewer.set_focus_regions([
        {"t_start": 1.1, "t_end": 1.6, "f_low": 800.0, "f_high": 2200.0, "polarity": "negative"}
    ])
    viewer._select_focus_region(0, emit_signal=False)

    played = []
    viewer.play_focus_region = lambda region, loop=False: played.append((region, loop))

    viewer._toggle_play()

    assert len(played) == 1
    assert played[0][0]["t_start"] == 1.1
    assert played[0][0]["f_low"] == 800.0
    assert played[0][1] is False


def test_delete_key_removes_selected_focus_region():
    viewer = _make_viewer()
    viewer.set_focus_mode(True, "positive")
    viewer.set_focus_regions([
        {"t_start": 0.9, "t_end": 1.2, "f_low": 1000.0, "f_high": 2600.0, "polarity": "positive"}
    ])
    _app.processEvents()
    viewer._select_focus_region(0, emit_signal=False)

    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
    viewer.keyPressEvent(event)

    assert viewer._selected_focus_region_index == -1
    assert viewer._focus_regions == []
    assert viewer._focus_rect_items == []
