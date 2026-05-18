"""Tests for Phase 3: Save Selections dialog and export logic."""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog

_app = QApplication.instance() or QApplication([])

from GUI.onset_editor import OnsetEditorPanel, _LoadSelectionsDialog, _SaveSelectionsDialog
from GUI.onset_editor_io import _build_load_selections_request, _summarize_load_selections_error


# ── Dialog UI ──────────────────────────────────────────────────────────


def test_dialog_creation():
    regions = [
        {"t_start": 0.0, "t_end": 1.0, "f_low": 100, "f_high": 2000, "polarity": "positive"},
        {"t_start": 2.0, "t_end": 3.0, "f_low": 200, "f_high": 3000, "polarity": "negative"},
    ]
    dlg = _SaveSelectionsDialog("/fake/test.wav", regions)
    assert dlg.windowTitle() == "Save Selections"
    assert dlg.positive_output_dir() == "/fake/test_PositiveSignals"
    assert dlg.negative_output_dir() == "/fake/test_NegativeSignals"
    assert dlg.individual_mode() is True
    assert dlg.bandpass_enabled() is False
    assert dlg.export_all_layers() is False


def test_load_dialog_creation():
    dlg = _LoadSelectionsDialog("/fake/test.wav")
    assert dlg.windowTitle() == "Load Selections"
    assert dlg.positive_input_dir() == "/fake/test_PositiveSignals"
    assert dlg.negative_input_dir() == "/fake/test_NegativeSignals"


def test_load_selections_request_and_error_helpers():
    request = _build_load_selections_request("/tmp/positive", "/tmp/negative")
    assert request == {
        "positive_input_dir": "/tmp/positive",
        "negative_input_dir": "/tmp/negative",
    }

    error = _summarize_load_selections_error(RuntimeError("boom"))
    assert error["title"] == "Load Selections Error"
    assert "boom" in error["message"]


def test_dialog_with_layers():
    regions = [
        {"t_start": 0.0, "t_end": 1.0, "f_low": 100, "f_high": 2000, "polarity": "positive"},
    ]
    layers = [
        {"name": "Layer 1", "onset_times": [], "focus_regions": {}, "dirty": False},
        {"name": "Layer 2", "onset_times": [], "focus_regions": {}, "dirty": False},
    ]
    dlg = _SaveSelectionsDialog("/fake/test.wav", regions, layers=layers, active_layer_idx=0)
    # Layer export options should exist
    assert dlg._active_layer_rb is not None
    assert dlg._all_layers_rb is not None
    assert dlg._active_layer_rb.isChecked()


def test_dialog_single_layer_no_layer_options():
    regions = [
        {"t_start": 0.0, "t_end": 1.0, "f_low": 100, "f_high": 2000, "polarity": "positive"},
    ]
    dlg = _SaveSelectionsDialog("/fake/test.wav", regions, layers=[])
    assert dlg._active_layer_rb is None
    assert dlg._all_layers_rb is None


# ── Button state ───────────────────────────────────────────────────────


def test_save_selections_button_exists():
    panel = OnsetEditorPanel()
    assert hasattr(panel, '_save_selections_btn')
    assert panel._save_selections_btn is not None
    assert hasattr(panel, '_load_selections_btn')
    assert panel._load_selections_btn is not None


def test_save_selections_button_disabled_without_regions():
    panel = OnsetEditorPanel()
    panel._audio_path = "/fake/test.wav"
    panel._focus_mode = True
    panel._update_button_states()
    assert not panel._save_selections_btn.isEnabled()
    assert panel._load_selections_btn.isEnabled()


def test_save_selections_button_enabled_with_regions():
    panel = OnsetEditorPanel()
    panel._audio_path = "/fake/test.wav"
    panel._focus_mode = True
    panel._focus_regions["test.wav"] = [
        {"t_start": 0, "t_end": 1, "f_low": 0, "f_high": 1000, "polarity": "positive"}
    ]
    panel._update_button_states()
    assert panel._save_selections_btn.isEnabled()
    assert panel._load_selections_btn.isEnabled()


def test_save_selections_button_disabled_when_focus_off():
    panel = OnsetEditorPanel()
    panel._audio_path = "/fake/test.wav"
    panel._focus_mode = False
    panel._focus_regions["test.wav"] = [
        {"t_start": 0, "t_end": 1, "f_low": 0, "f_high": 1000, "polarity": "positive"}
    ]
    panel._update_button_states()
    assert not panel._save_selections_btn.isEnabled()
    assert not panel._load_selections_btn.isEnabled()


# ── Extract region audio ──────────────────────────────────────────────


def test_extract_region_no_bandpass():
    sr = 16000
    y = np.sin(2 * np.pi * 440 * np.arange(sr * 5) / sr).astype(np.float32)
    region = {"t_start": 1.0, "t_end": 2.0, "f_low": 100, "f_high": 2000, "polarity": "positive"}
    seg = OnsetEditorPanel._extract_region_audio(y, sr, region, bandpass=False)
    assert seg is not None
    assert len(seg) == sr  # 1 second of audio
    np.testing.assert_array_equal(seg, y[sr:2*sr])


def test_extract_region_with_bandpass():
    sr = 16000
    # Mix of 440 Hz and 5000 Hz
    t = np.arange(sr * 2) / sr
    y = (np.sin(2 * np.pi * 440 * t) + np.sin(2 * np.pi * 5000 * t)).astype(np.float32)
    region = {"t_start": 0.0, "t_end": 1.0, "f_low": 200, "f_high": 800, "polarity": "positive"}
    seg = OnsetEditorPanel._extract_region_audio(y, sr, region, bandpass=True)
    assert seg is not None
    assert len(seg) == sr
    # The 5000 Hz component should be attenuated significantly
    # Check that energy in the segment is less than the unfiltered version
    unfiltered = y[:sr]
    assert np.sum(seg**2) < np.sum(unfiltered**2)


def test_extract_region_empty():
    sr = 16000
    y = np.zeros(sr, dtype=np.float32)
    # Region beyond audio length
    region = {"t_start": 5.0, "t_end": 6.0, "f_low": 0, "f_high": 8000, "polarity": "positive"}
    seg = OnsetEditorPanel._extract_region_audio(y, sr, region, bandpass=False)
    assert seg is None


# ── Export logic ──────────────────────────────────────────────────────


def _make_test_panel_with_audio(tmp_path, sr=16000, duration=5.0):
    """Create a panel with fake audio loaded."""
    panel = OnsetEditorPanel()
    y = np.random.randn(int(sr * duration)).astype(np.float32) * 0.1
    audio_path = str(tmp_path / "test.wav")
    # Write a test audio file
    try:
        import soundfile as sf
        sf.write(audio_path, y, sr)
    except ImportError:
        import pytest
        pytest.skip("soundfile not installed")
    panel._audio_path = audio_path
    return panel, y, sr


def test_export_individual_positive(tmp_path):
    panel, y, sr = _make_test_panel_with_audio(tmp_path)
    fname = "test.wav"
    regions = [
        {"t_start": 0.5, "t_end": 1.5, "f_low": 100, "f_high": 3000, "polarity": "positive"},
        {"t_start": 2.0, "t_end": 3.0, "f_low": 200, "f_high": 4000, "polarity": "positive"},
    ]
    # Build a simple mock viewer
    class _MockViewer:
        audioData = y
        sampleRate = sr
    panel._viewer = _MockViewer()

    layer = OnsetEditorPanel._make_default_layer("Layer 1")
    layer["focus_regions"] = {fname: regions}
    layers_to_export = [(0, layer)]

    count = panel._export_selections(str(tmp_path), layers_to_export,
                                     individual=True, bandpass=False)
    assert count == 2
    wav_files = sorted(tmp_path.glob("test_Positive*.wav"))
    assert len(wav_files) == 2
    assert wav_files[0].name == "test_Positive1.wav"
    assert wav_files[1].name == "test_Positive2.wav"


def test_export_concatenated(tmp_path):
    panel, y, sr = _make_test_panel_with_audio(tmp_path)
    fname = "test.wav"
    regions = [
        {"t_start": 0.5, "t_end": 1.0, "f_low": 100, "f_high": 3000, "polarity": "positive"},
        {"t_start": 1.5, "t_end": 2.0, "f_low": 200, "f_high": 4000, "polarity": "positive"},
    ]
    class _MockViewer:
        audioData = y
        sampleRate = sr
    panel._viewer = _MockViewer()

    layer = OnsetEditorPanel._make_default_layer("Layer 1")
    layer["focus_regions"] = {fname: regions}
    layers_to_export = [(0, layer)]

    count = panel._export_selections(str(tmp_path), layers_to_export,
                                     individual=False, bandpass=False)
    assert count == 1
    wav_files = sorted(tmp_path.glob("test_Positive_all*.wav"))
    assert len(wav_files) == 1
    # Verify concatenated length
    import soundfile as sf
    data, _ = sf.read(str(wav_files[0]))
    expected_len = int(0.5 * sr) + int(0.5 * sr)
    assert abs(len(data) - expected_len) <= 1


def test_export_positive_and_negative(tmp_path):
    panel, y, sr = _make_test_panel_with_audio(tmp_path)
    fname = "test.wav"
    pos_dir = tmp_path / "test_PositiveSignals"
    neg_dir = tmp_path / "test_NegativeSignals"
    regions = [
        {"t_start": 0.5, "t_end": 1.0, "f_low": 100, "f_high": 3000, "polarity": "positive"},
        {"t_start": 2.0, "t_end": 3.0, "f_low": 100, "f_high": 3000, "polarity": "negative"},
    ]
    class _MockViewer:
        audioData = y
        sampleRate = sr
    panel._viewer = _MockViewer()

    layer = OnsetEditorPanel._make_default_layer("Layer 1")
    layer["focus_regions"] = {fname: regions}
    layers_to_export = [(0, layer)]

    count = panel._export_selections(str(pos_dir), layers_to_export,
                                     individual=True, bandpass=False,
                                     negative_out_dir=str(neg_dir))
    assert count == 2
    assert (pos_dir / "test_Positive1.wav").exists()
    assert (neg_dir / "test_Negative1.wav").exists()
    assert (pos_dir / "test_PositiveSignals.json").exists()
    assert (neg_dir / "test_NegativeSignals.json").exists()

    with open(pos_dir / "test_PositiveSignals.json", "r", encoding="utf-8") as handle:
        pos_manifest = json.load(handle)
    with open(neg_dir / "test_NegativeSignals.json", "r", encoding="utf-8") as handle:
        neg_manifest = json.load(handle)

    assert pos_manifest["regions"][0]["polarity"] == "positive"
    assert neg_manifest["regions"][0]["polarity"] == "negative"


def test_export_with_bandpass(tmp_path):
    panel, y, sr = _make_test_panel_with_audio(tmp_path)
    fname = "test.wav"
    regions = [
        {"t_start": 0.5, "t_end": 1.5, "f_low": 500, "f_high": 2000, "polarity": "positive"},
    ]
    class _MockViewer:
        audioData = y
        sampleRate = sr
    panel._viewer = _MockViewer()

    layer = OnsetEditorPanel._make_default_layer("Layer 1")
    layer["focus_regions"] = {fname: regions}
    layers_to_export = [(0, layer)]

    count = panel._export_selections(str(tmp_path), layers_to_export,
                                     individual=True, bandpass=True)
    assert count == 1
    # Verify the file exists and has been filtered
    wav_files = sorted(tmp_path.glob("test_Positive*.wav"))
    assert len(wav_files) == 1
    assert wav_files[0].name == "test_Positive1.wav"


def test_export_multi_layer(tmp_path):
    panel, y, sr = _make_test_panel_with_audio(tmp_path)
    fname = "test.wav"

    class _MockViewer:
        audioData = y
        sampleRate = sr
    panel._viewer = _MockViewer()

    layer1 = OnsetEditorPanel._make_default_layer("Layer 1")
    layer1["focus_regions"] = {fname: [
        {"t_start": 0.5, "t_end": 1.0, "f_low": 100, "f_high": 3000, "polarity": "positive"},
    ]}
    layer2 = OnsetEditorPanel._make_default_layer("Layer 2")
    layer2["focus_regions"] = {fname: [
        {"t_start": 2.0, "t_end": 3.0, "f_low": 200, "f_high": 4000, "polarity": "negative"},
    ]}
    layers_to_export = [(0, layer1), (1, layer2)]

    count = panel._export_selections(str(tmp_path), layers_to_export,
                                     individual=True, bandpass=False)
    assert count == 2
    assert (tmp_path / "test_Positive1_Layer_1.wav").exists()
    assert (tmp_path / "test_Negative1_Layer_2.wav").exists()


def test_export_no_regions(tmp_path):
    panel, y, sr = _make_test_panel_with_audio(tmp_path)

    class _MockViewer:
        audioData = y
        sampleRate = sr
    panel._viewer = _MockViewer()

    layer = OnsetEditorPanel._make_default_layer("Layer 1")
    layer["focus_regions"] = {}
    layers_to_export = [(0, layer)]

    count = panel._export_selections(str(tmp_path), layers_to_export,
                                     individual=True, bandpass=False)
    assert count == 0


def test_auto_increment_numbering(tmp_path):
    """Exporting twice should not overwrite — numbers keep incrementing."""
    panel, y, sr = _make_test_panel_with_audio(tmp_path)
    fname = "test.wav"
    regions = [
        {"t_start": 0.5, "t_end": 1.5, "f_low": 100, "f_high": 3000, "polarity": "positive"},
    ]
    class _MockViewer:
        audioData = y
        sampleRate = sr
    panel._viewer = _MockViewer()

    layer = OnsetEditorPanel._make_default_layer("Layer 1")
    layer["focus_regions"] = {fname: regions}
    layers_to_export = [(0, layer)]

    # First export
    count1 = panel._export_selections(str(tmp_path), layers_to_export,
                                      individual=True, bandpass=False)
    assert count1 == 1
    assert (tmp_path / "test_Positive1.wav").exists()

    # Second export — should get number 2
    count2 = panel._export_selections(str(tmp_path), layers_to_export,
                                      individual=True, bandpass=False)
    assert count2 == 1
    assert (tmp_path / "test_Positive2.wav").exists()


def test_next_export_number_empty_dir(tmp_path):
    assert OnsetEditorPanel._next_export_number(str(tmp_path), "clip", "Positive") == 1


def test_next_export_number_existing_files(tmp_path):
    # Create some existing files
    (tmp_path / "clip_Positive1.wav").write_text("")
    (tmp_path / "clip_Positive2.wav").write_text("")
    (tmp_path / "clip_Positive5.wav").write_text("")
    assert OnsetEditorPanel._next_export_number(str(tmp_path), "clip", "Positive") == 6


def test_next_export_number_with_layer_suffix(tmp_path):
    (tmp_path / "clip_Positive1_Layer_1.wav").write_text("")
    (tmp_path / "clip_Positive3_Layer_1.wav").write_text("")
    assert OnsetEditorPanel._next_export_number(
        str(tmp_path), "clip", "Positive", "_Layer_1") == 4


def test_quick_export_handler_exists():
    panel = OnsetEditorPanel()
    assert hasattr(panel, '_on_quick_export_region')


def test_load_saved_selections_restores_regions_from_manifest(tmp_path):
    panel = OnsetEditorPanel()
    panel._audio_path = str(tmp_path / "test.wav")

    pos_dir = tmp_path / "test_PositiveSignals"
    neg_dir = tmp_path / "test_NegativeSignals"
    pos_dir.mkdir()
    neg_dir.mkdir()

    with open(pos_dir / "test_PositiveSignals.json", "w", encoding="utf-8") as handle:
        json.dump({
            "source_file": "test.wav",
            "polarity": "positive",
            "regions": [
                {"t_start": 0.5, "t_end": 1.0, "f_low": 100.0, "f_high": 2000.0, "polarity": "positive", "layer_name": "Layer 1"}
            ],
            "files": [],
        }, handle)
    with open(neg_dir / "test_NegativeSignals.json", "w", encoding="utf-8") as handle:
        json.dump({
            "source_file": "test.wav",
            "polarity": "negative",
            "regions": [
                {"t_start": 1.5, "t_end": 2.0, "f_low": 150.0, "f_high": 2500.0, "polarity": "negative", "layer_name": "Layer 1"}
            ],
            "files": [],
        }, handle)

    result = panel._load_saved_selections(str(pos_dir), str(neg_dir))
    assert result["geometry_restored"] is True
    assert len(result["regions"]) == 2
    assert result["profile"] is None

    panel._restore_loaded_focus_regions(result["regions"])
    assert len(panel._focus_regions["test.wav"]) == 2


def test_restore_loaded_focus_regions_creates_missing_named_layers(tmp_path):
    panel, _y, _sr = _make_test_panel_with_audio(tmp_path)
    restored = [
        {
            "t_start": 0.5,
            "t_end": 1.0,
            "f_low": 100.0,
            "f_high": 2000.0,
            "polarity": "positive",
            "layer_name": "Layer 1",
        },
        {
            "t_start": 1.5,
            "t_end": 2.0,
            "f_low": 150.0,
            "f_high": 2500.0,
            "polarity": "negative",
            "layer_name": "Imported Layer",
        },
    ]

    panel._restore_loaded_focus_regions(restored)

    assert restored[0]["layer_name"] == "Layer 1"
    assert restored[1]["layer_name"] == "Imported Layer"
    assert len(panel._layers) == 2
    assert panel._layers[1]["name"] == "Imported Layer"
    assert panel._layers[0]["focus_regions"]["test.wav"][0]["polarity"] == "positive"
    assert panel._layers[1]["focus_regions"]["test.wav"][0]["polarity"] == "negative"
    assert panel._layer_combo.itemText(1) == "Imported Layer"


def test_load_saved_selections_falls_back_to_clip_profile_without_manifest(tmp_path):
    panel, y, sr = _make_test_panel_with_audio(tmp_path)
    pos_dir = tmp_path / "saved_positive"
    neg_dir = tmp_path / "saved_negative"
    pos_dir.mkdir()
    neg_dir.mkdir()

    try:
        import soundfile as sf
    except ImportError:
        import pytest
        pytest.skip("soundfile not installed")

    clip = y[:sr]
    sf.write(pos_dir / "example_positive.wav", clip, sr)

    result = panel._load_saved_selections(str(pos_dir), str(neg_dir))
    assert result["geometry_restored"] is False
    assert result["profile"] is not None
    assert result["profile"]["summary"]["n_regions"] == 1


def test_apply_loaded_selections_result_updates_status_and_feedback(monkeypatch):
    panel = OnsetEditorPanel()

    restored_calls = []
    info_messages = []

    monkeypatch.setattr(panel, "_restore_loaded_focus_regions", lambda regions: restored_calls.append(regions))
    monkeypatch.setattr(
        "GUI.onset_editor.QMessageBox.information",
        lambda *_args: info_messages.append((_args[1], _args[2])),
    )

    restored_regions = [
        {"t_start": 0.5, "t_end": 1.0, "f_low": 100.0, "f_high": 2000.0, "polarity": "positive"}
    ]
    panel._apply_loaded_selections_result(
        {
            "regions": restored_regions,
            "geometry_restored": True,
            "profile": None,
        }
    )

    assert restored_calls == [restored_regions]
    assert panel._loaded_signal_profile is None
    assert panel._status_label.text() == "Loaded 1 saved selection(s) onto the spectrogram"

    loaded_profile = {"summary": {"n_regions": 2}}
    panel._apply_loaded_selections_result(
        {
            "regions": [],
            "geometry_restored": False,
            "profile": loaded_profile,
        }
    )

    assert panel._loaded_signal_profile == loaded_profile
    assert info_messages[-1][0] == "Geometry Metadata Missing"
    assert panel._status_label.text() == (
        "Loaded saved signal clips for settings recommendations; geometry metadata missing"
    )

    panel._apply_loaded_selections_result(
        {
            "regions": [],
            "geometry_restored": False,
            "profile": None,
        }
    )

    assert info_messages[-1][0] == "No Saved Selections Found"


def test_prompt_load_selections_result_handles_accept_cancel_and_errors(monkeypatch):
    panel = OnsetEditorPanel()
    panel._audio_path = "/tmp/example.wav"

    critical_messages = []
    dialog_args = []

    class _AcceptedDialog:
        def __init__(self, audio_path, parent=None):
            dialog_args.append((audio_path, parent))

        def exec(self):
            return QDialog.DialogCode.Accepted

        def positive_input_dir(self):
            return "/tmp/positive"

        def negative_input_dir(self):
            return "/tmp/negative"

    class _RejectedDialog:
        def __init__(self, audio_path, parent=None):
            dialog_args.append((audio_path, parent))

        def exec(self):
            return QDialog.DialogCode.Rejected

        def positive_input_dir(self):
            raise AssertionError("positive_input_dir should not be called on cancel")

        def negative_input_dir(self):
            raise AssertionError("negative_input_dir should not be called on cancel")

    monkeypatch.setattr("GUI.onset_editor._LoadSelectionsDialog", _AcceptedDialog)
    monkeypatch.setattr(
        panel,
        "_load_saved_selections",
        lambda pos_dir, neg_dir: {"dirs": (pos_dir, neg_dir)},
    )
    monkeypatch.setattr(
        "GUI.onset_editor.QMessageBox.critical",
        lambda *_args: critical_messages.append((_args[1], _args[2])),
    )

    accepted = panel._prompt_load_selections_result()
    assert accepted == {"dirs": ("/tmp/positive", "/tmp/negative")}
    assert dialog_args[-1] == ("/tmp/example.wav", panel)

    monkeypatch.setattr("GUI.onset_editor._LoadSelectionsDialog", _RejectedDialog)
    rejected = panel._prompt_load_selections_result()
    assert rejected is None

    monkeypatch.setattr("GUI.onset_editor._LoadSelectionsDialog", _AcceptedDialog)
    monkeypatch.setattr(
        panel,
        "_load_saved_selections",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    failed = panel._prompt_load_selections_result()
    assert failed is None
    assert critical_messages[-1][0] == "Load Selections Error"
    assert "boom" in critical_messages[-1][1]


def test_prompt_save_selections_request_handles_accept_and_cancel(monkeypatch):
    panel = OnsetEditorPanel()
    panel._audio_path = "/tmp/example.wav"
    regions = [
        {"t_start": 0.1, "t_end": 0.2, "f_low": 100.0, "f_high": 2000.0, "polarity": "positive"}
    ]

    saved_state_calls = []
    dialog_args = []

    class _AcceptedDialog:
        def __init__(self, audio_path, dialog_regions, *, layers=None, active_layer_idx=0, parent=None):
            dialog_args.append((audio_path, dialog_regions, layers, active_layer_idx, parent))

        def exec(self):
            return QDialog.DialogCode.Accepted

        def positive_output_dir(self):
            return "/tmp/positive"

        def negative_output_dir(self):
            return "/tmp/negative"

        def individual_mode(self):
            return False

        def bandpass_enabled(self):
            return True

        def export_all_layers(self):
            return True

    class _RejectedDialog:
        def __init__(self, *args, **kwargs):
            dialog_args.append((args, kwargs))

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(panel, "_save_layer_state", lambda: saved_state_calls.append(True))
    monkeypatch.setattr("GUI.onset_editor._SaveSelectionsDialog", _AcceptedDialog)

    accepted = panel._prompt_save_selections_request(regions)

    assert accepted == {
        "positive_output_dir": "/tmp/positive",
        "negative_output_dir": "/tmp/negative",
        "individual_mode": False,
        "bandpass_enabled": True,
        "export_all_layers": True,
    }
    assert saved_state_calls == [True]
    assert dialog_args[-1][0] == "/tmp/example.wav"
    assert dialog_args[-1][1] == regions
    assert dialog_args[-1][3] == panel._active_layer_idx
    assert dialog_args[-1][4] is panel

    monkeypatch.setattr("GUI.onset_editor._SaveSelectionsDialog", _RejectedDialog)
    rejected = panel._prompt_save_selections_request(regions)

    assert rejected is None
    assert saved_state_calls == [True, True]


def test_open_save_selections_dialog_applies_request_and_updates_status(monkeypatch):
    panel = OnsetEditorPanel()
    panel._audio_path = "/tmp/example.wav"
    panel._viewer = object()
    panel._focus_regions["example.wav"] = [
        {"t_start": 0.1, "t_end": 0.2, "f_low": 100.0, "f_high": 2000.0, "polarity": "positive"}
    ]

    panel._layers = [
        {"name": "Layer 1", "onset_times": [], "focus_regions": {}, "dirty": False},
        {"name": "Layer 2", "onset_times": [], "focus_regions": {}, "dirty": False},
    ]

    export_calls = []
    monkeypatch.setattr(
        panel,
        "_prompt_save_selections_request",
        lambda regions: {
            "positive_output_dir": "/tmp/positive",
            "negative_output_dir": "/tmp/negative",
            "individual_mode": False,
            "bandpass_enabled": True,
            "export_all_layers": True,
        },
    )
    monkeypatch.setattr(
        panel,
        "_export_selections",
        lambda pos_dir, layers_to_export, individual, bandpass, negative_out_dir=None: export_calls.append(
            (pos_dir, layers_to_export, individual, bandpass, negative_out_dir)
        ) or 4,
    )

    panel._open_save_selections_dialog()

    assert len(export_calls) == 1
    pos_dir, layers_to_export, individual, bandpass, negative_out_dir = export_calls[0]
    assert pos_dir == "/tmp/positive"
    assert negative_out_dir == "/tmp/negative"
    assert individual is False
    assert bandpass is True
    assert layers_to_export == [(0, panel._layers[0]), (1, panel._layers[1])]
    assert panel._status_label.text() == "Exported 4 WAV file(s) to positive/negative signal folders"


def test_open_save_selections_dialog_shows_no_regions_feedback(monkeypatch):
    panel = OnsetEditorPanel()
    panel._audio_path = "/tmp/example.wav"
    panel._viewer = object()

    info_messages = []
    prompt_calls = []

    monkeypatch.setattr(
        "GUI.onset_editor.QMessageBox.information",
        lambda *_args: info_messages.append((_args[1], _args[2])),
    )
    monkeypatch.setattr(
        panel,
        "_prompt_save_selections_request",
        lambda regions: prompt_calls.append(regions),
    )

    panel._open_save_selections_dialog()

    assert prompt_calls == []
    assert info_messages == [
        ("No Regions", "Draw positive/negative regions on the spectrogram first.")
    ]
