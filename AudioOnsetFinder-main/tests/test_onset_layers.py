"""Tests for Phase 2: Onset Layers system."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

import GUI.onset_editor as onset_editor_module
from PyQt6.QtWidgets import QDialog
from GUI.onset_editor_io import (
    _list_audio_files,
    _load_saved_onset_session_for_audio,
    _load_saved_onsets_for_audio,
    _review_audio_paths,
    _resolve_restored_file_selection,
)
from GUI.onset_editor_state import (
    add_shared_comparison_onsets,
    add_unique_comparison_onsets,
    activate_layer_range,
    append_layer_state,
    build_panel_config_snapshot,
    build_loaded_onset_session,
    build_save_selections_export_plan,
    build_comparison_display_state,
    build_layer_overlay_markers,
    classify_comparison_onsets,
    extract_scalar_config_restore_values,
    format_checked_layer_label,
    remove_active_layer,
    remove_main_only_onsets,
    restore_loaded_focus_regions,
    restore_configured_layers,
    select_exclusive_layer,
    summarize_loaded_selections_feedback,
    summarize_save_selections_preflight,
    summarize_focus_region_status,
    summarize_focus_restore_state,
    summarize_review_finish_state,
    summarize_review_navigation_state,
    summarize_layer_selection_change,
    switch_active_layer,
)
from GUI.onset_editor import OnsetEditorPanel


# ── Data model ──────────────────────────────────────────────────────────


def test_initial_layer_state():
    panel = OnsetEditorPanel()
    assert len(panel._layers) == 1
    assert panel._active_layer_idx == 0
    assert panel._layers[0]["name"] == "Layer 1"
    # Live attributes should match layer 0
    assert panel._onset_times is panel._layers[0]["onset_times"]
    assert panel._focus_regions is panel._layers[0]["focus_regions"]
    assert panel._undo_stack is panel._layers[0]["undo_stack"]


def test_make_default_layer():
    layer = OnsetEditorPanel._make_default_layer("Test Layer")
    assert layer["name"] == "Test Layer"
    assert layer["onset_times"] == []
    assert layer["focus_regions"] == {}
    assert layer["dirty"] is False


def test_append_layer_state_copies_initial_state():
    layers = [OnsetEditorPanel._make_default_layer("Layer 1")]
    source_regions = {
        "example.wav": [
            {
                "t_start": 0.5,
                "t_end": 1.0,
                "f_low": 100,
                "f_high": 600,
                "polarity": "positive",
            }
        ]
    }
    source_onsets = [0.1, 0.2]

    new_idx = append_layer_state(
        layers,
        layer_name="Signal 1",
        onset_times=source_onsets,
        focus_regions=source_regions,
        dirty=True,
    )

    assert new_idx == 1
    assert layers[1]["name"] == "Signal 1"
    assert layers[1]["onset_times"] == [0.1, 0.2]
    assert layers[1]["dirty"] is True
    assert layers[1]["focus_regions"]["example.wav"][0]["polarity"] == "positive"

    source_onsets.append(0.3)
    source_regions["example.wav"][0]["polarity"] = "negative"
    assert layers[1]["onset_times"] == [0.1, 0.2]
    assert layers[1]["focus_regions"]["example.wav"][0]["polarity"] == "positive"

def test_remove_active_layer_reindexes_checked_layers():
    layers = [OnsetEditorPanel._make_default_layer("Layer 1")]
    append_layer_state(layers, layer_name="Layer 2")
    append_layer_state(layers, layer_name="Layer 3")

    result = remove_active_layer(layers, active_layer_idx=1, checked_layer_indices={0, 1, 2})

    assert result is not None
    assert len(layers) == 2
    assert result["removed_name"] == "Layer 2"
    assert result["active_layer_idx"] == 1
    assert result["checked_layer_indices"] == {0, 1}
    assert [layer["name"] for layer in layers] == ["Layer 1", "Layer 3"]


def test_switch_active_layer_persists_and_loads_live_state():
    layers = [OnsetEditorPanel._make_default_layer("Layer 1")]
    append_layer_state(
        layers,
        layer_name="Layer 2",
        onset_times=[10.0, 20.0],
        focus_regions={
            "file.wav": [
                {
                    "t_start": 2.0,
                    "t_end": 3.0,
                    "f_low": 100,
                    "f_high": 200,
                    "polarity": "negative",
                }
            ]
        },
    )
    live_onsets = [1.0, 2.0]
    live_regions = {
        "file.wav": [
            {
                "t_start": 0.0,
                "t_end": 1.0,
                "f_low": 50,
                "f_high": 150,
                "polarity": "positive",
            }
        ]
    }
    live_undo = onset_editor_module._UndoStack()
    live_undo.push(list(live_onsets))

    result = switch_active_layer(
        layers,
        active_layer_idx=0,
        new_idx=1,
        onset_times=live_onsets,
        focus_regions=live_regions,
        undo_stack=live_undo,
        dirty=True,
    )

    assert result is not None
    assert layers[0]["onset_times"] is live_onsets
    assert layers[0]["focus_regions"] is live_regions
    assert layers[0]["undo_stack"] is live_undo
    assert layers[0]["dirty"] is True
    assert result["active_layer_idx"] == 1
    assert result["onset_times"] == [10.0, 20.0]
    assert result["focus_regions"]["file.wav"][0]["polarity"] == "negative"


def test_summarize_layer_selection_change_returns_primary_and_merge_state():
    result = summarize_layer_selection_change([2, 0])

    assert result["checked_layer_indices"] == {0, 2}
    assert result["primary_layer_idx"] == 2
    assert result["merge_enabled"] is True

    empty_result = summarize_layer_selection_change([])
    assert empty_result["checked_layer_indices"] == set()
    assert empty_result["primary_layer_idx"] is None
    assert empty_result["merge_enabled"] is False


def test_activate_layer_range_marks_new_layers_checked():
    result = activate_layer_range({0}, 1, 4)

    assert result is not None
    assert result["active_layer_idx"] == 1
    assert result["checked_layer_indices"] == {0, 1, 2, 3}
    assert activate_layer_range({0}, 5, 4) is None


def test_select_exclusive_layer_returns_single_checked_layer():
    result = select_exclusive_layer(2, 4)

    assert result is not None
    assert result["checked_layer_indices"] == {2}
    assert result["primary_layer_idx"] == 2
    assert result["merge_enabled"] is False
    assert select_exclusive_layer(5, 4) is None


def test_classify_comparison_onsets_splits_shared_and_unique():
    result = classify_comparison_onsets(
        [0.1, 0.2, 0.5],
        [
            {"times": [0.1004, 0.7], "color": (0, 0, 0, 0)},
            {"times": [0.5], "color": (1, 1, 1, 1)},
        ],
        tolerance_ms=5.0,
    )

    assert result["shared_main"] == {0, 2}
    assert result["main_only"] == {1}
    assert result["comp_only_per_file"] == [[0.7], []]


def test_add_shared_comparison_onsets_adds_only_nonduplicate_matches():
    updated_onsets, added = add_shared_comparison_onsets(
        [0.1],
        [{"times": [0.103, 0.1035, 0.1004, 0.7], "color": (0, 0, 0, 0)}],
        tolerance_ms=5.0,
    )

    assert updated_onsets == [0.1, 0.103]
    assert added == 1


def test_add_unique_comparison_onsets_dedupes_across_files():
    updated_onsets, added = add_unique_comparison_onsets(
        [0.1, 0.2],
        [[0.2, 0.3], [0.3005, 0.5]],
    )

    assert updated_onsets == [0.1, 0.2, 0.3, 0.5]
    assert added == 2


def test_remove_main_only_onsets_keeps_nonremoved_order():
    updated_onsets, removed = remove_main_only_onsets(
        [0.1, 0.2, 0.3, 0.4],
        {1, 3},
    )

    assert updated_onsets == [0.1, 0.3]
    assert removed == 2


def test_build_loaded_onset_session_seeds_fresh_undo_history():
    source_onsets = [0.4, 0.1]

    result = build_loaded_onset_session(source_onsets)

    assert result["onset_times"] == [0.4, 0.1]
    assert result["dirty"] is False
    source_onsets.append(0.8)
    assert result["onset_times"] == [0.4, 0.1]

    result["undo_stack"].push([0.4])
    assert result["undo_stack"].undo() == [0.4, 0.1]


def test_summarize_review_navigation_state_derives_counter_and_buttons():
    middle = summarize_review_navigation_state(3, 1)

    assert middle["counter_text"] == "File 2 / 3"
    assert middle["prev_enabled"] is True
    assert middle["next_enabled"] is True
    assert middle["save_next_enabled"] is True

    empty = summarize_review_navigation_state(0, 0)
    assert empty["counter_text"] == "File 0 / 0"
    assert empty["prev_enabled"] is False
    assert empty["next_enabled"] is False
    assert empty["save_next_enabled"] is False


def test_summarize_review_finish_state_derives_prompt_and_reset_state():
    dirty = summarize_review_finish_state(True, "/tmp/sample.wav")

    assert dirty["require_save_prompt"] is True
    assert dirty["prompt_text"] == "Save changes to sample.wav before finishing?"
    assert dirty["review_mode"] is False
    assert dirty["review_files"] == []
    assert dirty["review_index"] == 0
    assert dirty["status_text"] == "Review complete."

    clean = summarize_review_finish_state(False, None)
    assert clean["require_save_prompt"] is False
    assert clean["prompt_text"] is None


def test_summarize_loaded_selections_feedback_derives_messages_and_status():
    restored = summarize_loaded_selections_feedback(
        {
            "regions": [{"t_start": 0.5, "t_end": 1.0}],
            "geometry_restored": True,
            "profile": None,
        }
    )
    assert restored["geometry_restored"] is True
    assert restored["status_text"] == "Loaded 1 saved selection(s) onto the spectrogram"
    assert restored["info_title"] is None

    missing_geometry = summarize_loaded_selections_feedback(
        {
            "regions": [],
            "geometry_restored": False,
            "profile": {"summary": {"n_regions": 2}},
        }
    )
    assert missing_geometry["geometry_restored"] is False
    assert missing_geometry["info_title"] == "Geometry Metadata Missing"
    assert "geometry metadata missing" in missing_geometry["status_text"].lower()

    empty = summarize_loaded_selections_feedback(
        {
            "regions": [],
            "geometry_restored": False,
            "profile": None,
        }
    )
    assert empty["info_title"] == "No Saved Selections Found"
    assert empty["status_text"] is None


def test_build_save_selections_export_plan_selects_requested_layers():
    layers = [
        OnsetEditorPanel._make_default_layer("Layer 1"),
        OnsetEditorPanel._make_default_layer("Layer 2"),
    ]

    all_layers = build_save_selections_export_plan(
        {
            "positive_output_dir": "/tmp/positive",
            "negative_output_dir": "/tmp/negative",
            "individual_mode": False,
            "bandpass_enabled": True,
            "export_all_layers": True,
        },
        layers=layers,
        active_layer_idx=1,
    )
    assert all_layers["layers_to_export"] == [(0, layers[0]), (1, layers[1])]
    assert all_layers["individual_mode"] is False
    assert all_layers["bandpass_enabled"] is True

    active_only = build_save_selections_export_plan(
        {
            "positive_output_dir": "/tmp/positive",
            "negative_output_dir": "/tmp/negative",
            "individual_mode": True,
            "bandpass_enabled": False,
            "export_all_layers": False,
        },
        layers=layers,
        active_layer_idx=1,
    )
    assert active_only["layers_to_export"] == [(1, layers[1])]

    single_layer = build_save_selections_export_plan(
        {
            "positive_output_dir": "/tmp/positive",
            "negative_output_dir": "/tmp/negative",
            "individual_mode": True,
            "bandpass_enabled": False,
            "export_all_layers": True,
        },
        layers=[layers[0]],
        active_layer_idx=0,
    )
    assert single_layer["layers_to_export"] == [(0, layers[0])]


def test_summarize_save_selections_preflight_derives_regions_and_feedback():
    silent = summarize_save_selections_preflight(
        audio_path=None,
        viewer_available=True,
        focus_regions={},
    )
    assert silent["can_open"] is False
    assert silent["info_title"] is None

    missing_regions = summarize_save_selections_preflight(
        audio_path="/tmp/example.wav",
        viewer_available=True,
        focus_regions={},
    )
    assert missing_regions["can_open"] is False
    assert missing_regions["info_title"] == "No Regions"
    assert "spectrogram first" in missing_regions["info_message"]

    regions = [{"t_start": 0.1, "t_end": 0.2, "polarity": "positive"}]
    ready = summarize_save_selections_preflight(
        audio_path="/tmp/example.wav",
        viewer_available=True,
        focus_regions={"example.wav": regions},
    )
    assert ready["can_open"] is True
    assert ready["regions"] == regions
    assert ready["info_title"] is None


def test_build_panel_config_snapshot_serializes_layers_and_empty_excel_path():
    layers = [OnsetEditorPanel._make_default_layer("Drums")]
    append_layer_state(layers, layer_name="Vocals")

    result = build_panel_config_snapshot(
        folder="/tmp/audio",
        file_name="sample.wav",
        folder_auto=True,
        onset_auto=False,
        onset_source="labels",
        excel_onset_path=None,
        excel_onset_col="B",
        excel_filename_col="A",
        excel_sheet_name="Sheet1",
        focus_mode=True,
        focus_polarity="positive",
        active_layer_idx=1,
        layers=layers,
    )

    assert result["folder"] == "/tmp/audio"
    assert result["file"] == "sample.wav"
    assert result["excel_onset_path"] == ""
    assert result["active_layer_idx"] == 1
    assert result["layers"][0]["name"] == "Drums"
    assert result["layers"][1]["name"] == "Vocals"


def test_restore_configured_layers_clamps_active_index_and_names():
    result = restore_configured_layers(
        [
            {"name": "Drums", "onset_times": [0.1], "focus_regions": {}, "dirty": False},
            {"name": "Vocals", "onset_times": [0.2], "focus_regions": {}, "dirty": True},
        ],
        5,
    )

    assert result is not None
    assert result["active_layer_idx"] == 1
    assert [layer["name"] for layer in result["layers"]] == ["Drums", "Vocals"]
    assert result["layers"][1]["dirty"] is True
    assert restore_configured_layers([], 0) is None


def test_extract_scalar_config_restore_values_normalizes_supported_fields():
    result = extract_scalar_config_restore_values(
        {
            "folder_auto": False,
            "onset_auto": True,
            "onset_source": "excel",
            "excel_onset_path": "/tmp/onsets.xlsx",
            "excel_onset_col": "B",
            "excel_filename_col": "A",
            "excel_sheet_name": "Sheet1",
            "folder": "/tmp/audio",
            "file": "sample.wav",
            "focus_polarity": "negative",
        }
    )

    assert result == {
        "folder_auto": False,
        "onset_auto": True,
        "onset_source": "excel",
        "excel_onset_path": "/tmp/onsets.xlsx",
        "excel_onset_col": "B",
        "excel_filename_col": "A",
        "excel_sheet_name": "Sheet1",
        "folder": "/tmp/audio",
        "file_name": "sample.wav",
        "focus_polarity": "negative",
    }

    invalid = extract_scalar_config_restore_values({"focus_polarity": "sideways"})
    assert invalid["focus_polarity"] is None


def test_set_values_restores_scalar_config_fields():
    panel = OnsetEditorPanel()
    panel._focus_onsets_btn.setChecked(True)

    panel.set_values(
        {
            "folder_auto": False,
            "onset_auto": True,
            "onset_source": "excel",
            "excel_onset_path": "/tmp/onsets.xlsx",
            "excel_onset_col": "B",
            "excel_filename_col": "A",
            "excel_sheet_name": "Sheet1",
            "focus_polarity": "negative",
        }
    )

    assert panel._folder_auto_cb.isChecked() is False
    assert panel._onset_auto_cb.isChecked() is True
    assert panel._onset_source == "excel"
    assert panel._excel_onset_path == "/tmp/onsets.xlsx"
    assert panel._excel_onset_col == "B"
    assert panel._excel_filename_col == "A"
    assert panel._excel_sheet_name == "Sheet1"
    assert panel._focus_polarity == "negative"
    assert panel._positive_btn.isChecked() is False
    assert panel._negative_btn.isChecked() is True
    assert panel._focus_onsets_btn.isChecked() is False


def test_resolve_restored_file_selection_prefers_saved_file_and_falls_back():
    with tempfile.TemporaryDirectory() as tmpdir:
        for file_name in ["b.mp3", "a.wav", "notes.txt"]:
            with open(os.path.join(tmpdir, file_name), "w", encoding="utf-8") as handle:
                handle.write("test")

        folder_exists, files, selected_idx = _resolve_restored_file_selection(
            tmpdir,
            "b.mp3",
        )
        assert folder_exists is True
        assert files == ["a.wav", "b.mp3"]
        assert selected_idx == 1

        fallback = _resolve_restored_file_selection(tmpdir, "missing.wav")
        assert fallback == (True, ["a.wav", "b.mp3"], 0)

    assert _resolve_restored_file_selection("/does/not/exist", "missing.wav") == (
        False,
        [],
        -1,
    )


def test_review_audio_paths_wraps_sorted_audio_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        for file_name in ["b.MP3", "a.wav", "notes.txt"]:
            with open(os.path.join(tmpdir, file_name), "w", encoding="utf-8") as handle:
                handle.write("test")

        assert _review_audio_paths(tmpdir) == [
            os.path.join(tmpdir, "a.wav"),
            os.path.join(tmpdir, "b.MP3"),
        ]


def test_set_values_restores_saved_folder_and_file_selection():
    panel = OnsetEditorPanel()
    panel._suppress_file_selection_handler = True
    loaded_indices = []
    panel._on_file_selected = lambda index: loaded_indices.append(index)
    panel._file_combo.addItem("stale.wav")

    with tempfile.TemporaryDirectory() as tmpdir:
        for file_name in ["b.mp3", "a.wav"]:
            with open(os.path.join(tmpdir, file_name), "w", encoding="utf-8") as handle:
                handle.write("test")

        panel.set_values({"folder": tmpdir, "file": "b.mp3"})

        assert panel._folder_edit.text() == tmpdir
        assert panel._file_combo.count() == 2
        assert [panel._file_combo.itemText(idx) for idx in range(panel._file_combo.count())] == [
            "a.wav",
            "b.mp3",
        ]
        assert panel._file_combo.currentText() == "b.mp3"
        assert loaded_indices == [1]


def test_set_values_refreshes_restored_layer_widgets(monkeypatch):
    panel = OnsetEditorPanel()
    refresh_calls = []
    monkeypatch.setattr(
        panel,
        "_refresh_signal_browser_combo",
        lambda: refresh_calls.append(panel._active_layer_idx),
    )

    panel.set_values(
        {
            "layers": [
                {"name": "Drums", "onset_times": [0.1], "focus_regions": {}, "dirty": False},
                {"name": "Vocals", "onset_times": [0.2], "focus_regions": {}, "dirty": True},
            ],
            "active_layer_idx": 1,
        }
    )

    assert panel._layer_combo.count() == 2
    assert panel._layer_combo.itemText(0) == "Drums"
    assert panel._layer_combo.itemText(1) == "Vocals"
    assert panel._layer_combo.currentIndex() == 1
    assert panel._onset_times == [0.2]
    assert refresh_calls == [1]


def test_apply_active_focus_region_widgets_refreshes_requested_ui(monkeypatch):
    panel = OnsetEditorPanel()
    panel._focus_mode = True
    calls = []
    monkeypatch.setattr(panel, "_refresh_focus_regions_in_viewer", lambda: calls.append("viewer"))
    monkeypatch.setattr(panel, "_update_button_states", lambda: calls.append("buttons"))
    monkeypatch.setattr(panel, "_refresh_signal_browser_combo", lambda: calls.append("signals"))

    panel._apply_active_focus_region_widgets(refresh_signal_browser=True)

    assert calls == ["viewer", "buttons", "signals"]


def test_append_layer_names_to_combo_appends_in_order():
    panel = OnsetEditorPanel()

    panel._append_layer_names_to_combo(["Signals", "Merged"], block_signals=True)

    assert [panel._layer_combo.itemText(idx) for idx in range(panel._layer_combo.count())] == [
        "Layer 1",
        "Signals",
        "Merged",
    ]


def test_apply_new_layer_range_activation_updates_active_layer_and_combo():
    panel = OnsetEditorPanel()
    panel._add_layer()

    panel._apply_new_layer_range_activation(
        {"checked_layer_indices": {0, 1}, "active_layer_idx": 1},
        1,
    )

    assert panel._checked_layer_indices == {0, 1}
    assert panel._active_layer_idx == 1
    assert panel._layer_combo.currentIndex() == 1
    assert panel._focus_regions is panel._layers[1]["focus_regions"]


def test_set_layer_combo_index_updates_hidden_combo():
    panel = OnsetEditorPanel()
    panel._add_layer()

    panel._set_layer_combo_index(1)

    assert panel._layer_combo.currentIndex() == 1


def test_refresh_layer_structure_widgets_rebuilds_menu_and_views(monkeypatch):
    panel = OnsetEditorPanel()
    calls = []
    monkeypatch.setattr(panel, "_rebuild_layer_menu", lambda: calls.append("menu"))
    monkeypatch.setattr(panel, "_refresh_viewer_markers", lambda: calls.append("viewer"))
    monkeypatch.setattr(panel, "_refresh_table", lambda: calls.append("table"))

    panel._refresh_layer_structure_widgets()

    assert calls == ["menu", "viewer", "table"]


def test_refresh_layer_data_views_updates_viewer_and_table(monkeypatch):
    panel = OnsetEditorPanel()
    calls = []
    monkeypatch.setattr(panel, "_refresh_viewer_markers", lambda: calls.append("viewer"))
    monkeypatch.setattr(panel, "_refresh_table", lambda: calls.append("table"))

    panel._refresh_layer_data_views()

    assert calls == ["viewer", "table"]


def test_refresh_layer_overlay_widgets_updates_viewer_and_overlays(monkeypatch):
    panel = OnsetEditorPanel()
    calls = []
    monkeypatch.setattr(panel, "_push_layer_info_to_viewer", lambda: calls.append("viewer"))
    monkeypatch.setattr(panel, "_refresh_layer_overlays", lambda: calls.append("overlays"))

    panel._refresh_layer_overlay_widgets()

    assert calls == ["viewer", "overlays"]


def test_clear_comparison_markers_clears_when_viewer_available(monkeypatch):
    panel = OnsetEditorPanel()
    calls = []
    panel._viewer = type("ViewerStub", (), {"clear_comparison_markers": lambda self: calls.append("cleared")})()

    panel._clear_comparison_markers()

    assert calls == ["cleared"]


def test_refresh_active_layer_focus_widgets_refreshes_focus_and_optional_layer_info(monkeypatch):
    panel = OnsetEditorPanel()
    calls = []
    monkeypatch.setattr(
        panel,
        "_apply_active_focus_region_widgets",
        lambda refresh_signal_browser=False: calls.append(("focus", refresh_signal_browser)),
    )
    monkeypatch.setattr(panel, "_push_layer_info_to_viewer", lambda: calls.append(("info", None)))

    panel._refresh_active_layer_focus_widgets(
        refresh_signal_browser=True,
        push_layer_info=True,
    )

    assert calls == [("focus", True), ("info", None)]


def test_refresh_post_layer_change_widgets_refreshes_focus_and_overlays(monkeypatch):
    panel = OnsetEditorPanel()
    calls = []
    monkeypatch.setattr(
        panel,
        "_refresh_active_layer_focus_widgets",
        lambda refresh_signal_browser=False: calls.append(("focus", refresh_signal_browser)),
    )
    monkeypatch.setattr(panel, "_refresh_layer_overlay_widgets", lambda: calls.append(("overlay", None)))

    panel._refresh_post_layer_change_widgets(refresh_signal_browser=True)

    assert calls == [("focus", True), ("overlay", None)]


def test_refresh_structural_layer_mutation_widgets_refreshes_structure_then_post(monkeypatch):
    panel = OnsetEditorPanel()
    calls = []
    monkeypatch.setattr(panel, "_refresh_layer_structure_widgets", lambda: calls.append("structure"))
    monkeypatch.setattr(
        panel,
        "_refresh_post_layer_change_widgets",
        lambda refresh_signal_browser=False: calls.append(("post", refresh_signal_browser)),
    )

    panel._refresh_structural_layer_mutation_widgets(refresh_signal_browser=True)

    assert calls == ["structure", ("post", True)]


def test_activate_exclusive_layer_switches_and_refreshes(monkeypatch):
    panel = OnsetEditorPanel()
    panel._add_layer()
    calls = []
    monkeypatch.setattr(panel, "_switch_layer", lambda index: calls.append(("switch", index)))
    monkeypatch.setattr(panel, "_rebuild_layer_menu", lambda: calls.append(("menu", None)))
    monkeypatch.setattr(panel, "_refresh_layer_selection_widgets", lambda update_buttons=False: calls.append(("selection", update_buttons)))

    result = panel._activate_exclusive_layer(0)

    assert result is True
    assert panel._checked_layer_indices == {0}
    assert calls == [("switch", 0), ("menu", None), ("selection", False)]


def test_activate_exclusive_layer_updates_buttons_when_layer_unchanged(monkeypatch):
    panel = OnsetEditorPanel()
    calls = []
    monkeypatch.setattr(panel, "_switch_layer", lambda index: calls.append(("switch", index)))
    monkeypatch.setattr(panel, "_rebuild_layer_menu", lambda: calls.append(("menu", None)))
    monkeypatch.setattr(
        panel,
        "_refresh_layer_selection_widgets",
        lambda update_buttons=False: calls.append(("selection", update_buttons)),
    )

    result = panel._activate_exclusive_layer(0, update_buttons=True)

    assert result is True
    assert panel._checked_layer_indices == {0}
    assert calls == [("menu", None), ("selection", True)]


def test_refresh_layer_selection_widgets_updates_overlays_and_optional_buttons(monkeypatch):
    panel = OnsetEditorPanel()
    calls = []
    monkeypatch.setattr(panel, "_refresh_layer_overlays", lambda: calls.append("overlays"))
    monkeypatch.setattr(panel, "_update_button_states", lambda: calls.append("buttons"))

    panel._refresh_layer_selection_widgets(update_buttons=True)

    assert calls == ["overlays", "buttons"]


def test_set_merge_selection_enabled_updates_button_state():
    panel = OnsetEditorPanel()

    panel._set_merge_selection_enabled(True)
    assert panel._merge_sel_btn.isEnabled()

    panel._set_merge_selection_enabled(False)
    assert not panel._merge_sel_btn.isEnabled()


def test_get_checked_layer_indices_returns_menu_selection_and_empty_fallback():
    panel = OnsetEditorPanel()
    panel._layer_menu.rebuild(panel._layers, {0})

    assert panel._get_checked_layer_indices() == [0]

    panel._layer_menu = None

    assert panel._get_checked_layer_indices() == []


def test_refresh_layer_menu_widgets_rebuilds_when_menu_present(monkeypatch):
    panel = OnsetEditorPanel()
    calls = []
    monkeypatch.setattr(panel, "_rebuild_layer_menu", lambda: calls.append("menu"))

    panel._refresh_layer_menu_widgets()

    assert calls == ["menu"]


def test_apply_checked_layer_selection_switches_refreshes_and_updates_merge(monkeypatch):
    panel = OnsetEditorPanel()
    calls = []
    monkeypatch.setattr(panel, "_switch_layer", lambda index: calls.append(("switch", index)))
    monkeypatch.setattr(panel, "_refresh_layer_selection_widgets", lambda update_buttons=False: calls.append(("selection", update_buttons)))

    panel._apply_checked_layer_selection(
        {"primary_layer_idx": 0, "merge_enabled": True}
    )

    assert calls == [("selection", False)]
    assert panel._merge_sel_btn.isEnabled()


def test_summarize_focus_region_status_counts_positive_and_negative_regions():
    status = summarize_focus_region_status(
        [
            {"polarity": "positive"},
            {"polarity": "negative"},
            {"polarity": "positive"},
        ]
    )

    assert status == {
        "positive_count": 2,
        "negative_count": 1,
        "status_text": "Focus regions: 2 positive, 1 negative",
    }


def test_apply_focus_region_status_widgets_updates_label_and_browser(monkeypatch):
    panel = OnsetEditorPanel()
    calls = []
    monkeypatch.setattr(panel, "_update_button_states", lambda: calls.append("buttons"))
    monkeypatch.setattr(panel, "_refresh_signal_browser_combo", lambda: calls.append("signals"))

    panel._apply_focus_region_status_widgets("Focus regions: 1 positive, 0 negative")

    assert panel._status_label.text() == "Focus regions: 1 positive, 0 negative"
    assert calls == ["buttons", "signals"]


def test_viewer_focus_region_add_remove_updates_status_text():
    panel = OnsetEditorPanel()
    panel._audio_path = "/tmp/example.wav"
    signal_browser_calls = []
    panel._refresh_signal_browser_combo = lambda: signal_browser_calls.append(True)

    panel._on_viewer_focus_region_added(
        {"t_start": 0.0, "t_end": 0.2, "f_low": 100, "f_high": 300, "polarity": "positive"}
    )
    panel._on_viewer_focus_region_added(
        {"t_start": 0.3, "t_end": 0.5, "f_low": 150, "f_high": 350, "polarity": "negative"}
    )

    assert panel._status_label.text() == "Focus regions: 1 positive, 1 negative"

    panel._on_viewer_focus_region_removed(0)

    assert panel._status_label.text() == "Focus regions: 0 positive, 1 negative"
    assert signal_browser_calls == [True, True, True]


def test_restore_loaded_focus_regions_returns_created_names_and_active_focus_regions():
    layers = [OnsetEditorPanel._make_default_layer("Layer 1")]

    result = restore_loaded_focus_regions(
        layers,
        active_layer_idx=0,
        audio_path="/tmp/example.wav",
        restored_regions=[
            {
                "t_start": 0.1,
                "t_end": 0.2,
                "f_low": 100,
                "f_high": 300,
                "polarity": "positive",
                "layer_name": "Layer 1",
            },
            {
                "t_start": 0.3,
                "t_end": 0.4,
                "f_low": 150,
                "f_high": 350,
                "polarity": "negative",
                "layer_name": "Signals",
            },
        ],
    )

    assert result["created_layer_names"] == ["Signals"]
    assert result["focus_regions"] is layers[0]["focus_regions"]
    assert result["focus_regions"]["example.wav"][0]["polarity"] == "positive"
    assert layers[1]["name"] == "Signals"
    assert layers[1]["focus_regions"]["example.wav"][0]["polarity"] == "negative"


def test_panel_restore_loaded_focus_regions_updates_combo_and_active_focus_regions():
    panel = OnsetEditorPanel()
    panel._audio_path = "/tmp/example.wav"
    signal_browser_calls = []
    panel._refresh_signal_browser_combo = lambda: signal_browser_calls.append(True)

    panel._restore_loaded_focus_regions(
        [
            {
                "t_start": 0.1,
                "t_end": 0.2,
                "f_low": 100,
                "f_high": 300,
                "polarity": "positive",
                "layer_name": "Signals",
            }
        ]
    )

    assert panel._layer_combo.count() == 2
    assert panel._layer_combo.itemText(1) == "Signals"
    assert panel._focus_regions is panel._layers[0]["focus_regions"]
    assert panel._layers[1]["focus_regions"]["example.wav"][0]["polarity"] == "positive"
    assert signal_browser_calls == []


def test_summarize_focus_restore_state_derives_button_checks_and_reset():
    negative = summarize_focus_restore_state("negative")
    assert negative == {
        "focus_polarity": "negative",
        "positive_checked": False,
        "negative_checked": True,
        "focus_mode_enabled": False,
    }

    missing = summarize_focus_restore_state(None)
    assert missing == {
        "focus_polarity": None,
        "positive_checked": None,
        "negative_checked": None,
        "focus_mode_enabled": False,
    }


def test_build_comparison_display_state_builds_all_filter_payloads():
    display_state = build_comparison_display_state(
        [0.1, 0.2, 0.5],
        [{"times": [0.7], "color": "red"}, {"times": [], "color": "blue"}],
        0,
        main_only={1},
        shared_main={0, 2},
        comp_only_per_file=[[0.7], []],
        main_only_color="main-blue",
        shared_color="shared-green",
        comparison_style="dash",
    )

    assert display_state["visible_main_times"] == [0.1, 0.2, 0.5]
    assert display_state["visible_main_colors"] == [
        "shared-green",
        "main-blue",
        "shared-green",
    ]
    assert display_state["comparison_layers"] == [
        {"times": [0.7], "color": "red", "style": "dash"}
    ]
    assert display_state["status_text"] == "Main: 1 unique, 2 shared  |  Comparison: 1 unique"


def test_build_comparison_display_state_hides_overlay_outside_overlay_filters():
    display_state = build_comparison_display_state(
        [0.1, 0.2, 0.5],
        [{"times": [0.7], "color": "red"}],
        2,
        main_only={1},
        shared_main={0, 2},
        comp_only_per_file=[[0.7]],
        main_only_color="main-blue",
        shared_color="shared-green",
        comparison_style="dash",
    )

    assert display_state["visible_main_times"] == [0.1, 0.5]
    assert display_state["visible_main_colors"] == ["shared-green", "shared-green"]
    assert display_state["comparison_layers"] == []


def test_list_audio_files_filters_to_audio_files_only():
    with tempfile.TemporaryDirectory() as tmpdir:
        for file_name in ["b.MP3", "a.wav", "notes.txt"]:
            with open(os.path.join(tmpdir, file_name), "w", encoding="utf-8") as handle:
                handle.write("test")
        os.mkdir(os.path.join(tmpdir, "nested.wav"))

        assert _list_audio_files(tmpdir) == ["a.wav", "b.MP3"]


def test_load_saved_onsets_for_audio_reads_matching_label_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "sample.wav")
        with open(audio_path, "w", encoding="utf-8") as handle:
            handle.write("audio")

        label_path = os.path.join(tmpdir, "sample_labels.txt")
        with open(label_path, "w", encoding="utf-8") as handle:
            handle.write("0.400000\t0.400000\tOnsetR_2\n")
            handle.write("0.100000\t0.100000\tOnsetR_1\n")

        found_label_path, onset_times = _load_saved_onsets_for_audio(audio_path)

        assert found_label_path == label_path
        assert onset_times == [0.1, 0.4]


def test_load_saved_onset_session_for_audio_builds_fresh_session():
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "sample.wav")
        with open(audio_path, "w", encoding="utf-8") as handle:
            handle.write("audio")

        label_path = os.path.join(tmpdir, "sample_labels.txt")
        with open(label_path, "w", encoding="utf-8") as handle:
            handle.write("0.400000\t0.400000\tOnsetR_2\n")
            handle.write("0.100000\t0.100000\tOnsetR_1\n")

        found_label_path, session = _load_saved_onset_session_for_audio(audio_path)

        assert found_label_path == label_path
        assert session["onset_times"] == [0.1, 0.4]

        session["undo_stack"].push([0.1])
        assert session["undo_stack"].undo() == [0.1, 0.4]


def test_review_revert_restores_saved_label_session():
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "sample.wav")
        with open(audio_path, "w", encoding="utf-8") as handle:
            handle.write("audio")

        label_path = os.path.join(tmpdir, "sample_labels.txt")
        with open(label_path, "w", encoding="utf-8") as handle:
            handle.write("0.400000\t0.400000\tOnsetR_2\n")
            handle.write("0.100000\t0.100000\tOnsetR_1\n")

        panel = OnsetEditorPanel()
        panel._audio_path = audio_path
        panel._onset_times = [1.25]
        panel._dirty = True

        panel._review_revert()

        assert panel._label_path == label_path
        assert panel._onset_times == [0.1, 0.4]
        assert panel._dirty is False
        assert panel._status_label.text() == "Reverted to saved labels for sample.wav"
        assert panel._table.rowCount() == 2


def test_load_review_file_restores_saved_label_session_and_updates_review_ui():
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "sample.wav")
        with open(audio_path, "w", encoding="utf-8") as handle:
            handle.write("audio")

        label_path = os.path.join(tmpdir, "sample_labels.txt")
        with open(label_path, "w", encoding="utf-8") as handle:
            handle.write("0.400000\t0.400000\tOnsetR_2\n")
            handle.write("0.100000\t0.100000\tOnsetR_1\n")

        panel = OnsetEditorPanel()
        panel._viewer = None
        panel._review_files = [audio_path]
        panel._file_combo.addItem("other.wav")
        panel._file_combo.addItem("sample.wav")
        panel._file_combo.setCurrentIndex(0)
        panel._dirty = False

        panel._load_review_file(0)

        assert panel._review_index == 0
        assert panel._file_combo.currentText() == "sample.wav"
        assert panel._label_path == label_path
        assert panel._onset_times == [0.1, 0.4]
        assert panel._dirty is False
        assert panel._review_counter.text() == "File 1 / 1"
        assert panel._status_label.text() == "Review 1/1: sample.wav"


def test_load_review_file_uses_prompt_save_and_respects_cancel(monkeypatch):
    panel = OnsetEditorPanel()
    panel._dirty = True
    panel._audio_path = "/tmp/original.wav"
    panel._review_files = ["/tmp/next.wav"]

    prompt_calls = []
    monkeypatch.setattr(
        panel,
        "_prompt_save",
        lambda **kwargs: prompt_calls.append(kwargs) or onset_editor_module.QMessageBox.StandardButton.Cancel,
    )

    panel._load_review_file(0)

    assert prompt_calls == [{}]
    assert panel._audio_path == "/tmp/original.wav"
    assert panel._review_index == 0


def test_review_finish_uses_prompt_save_and_respects_cancel(monkeypatch):
    panel = OnsetEditorPanel()
    panel._dirty = True
    panel._audio_path = "/tmp/sample.wav"
    panel._review_mode = True
    panel._review_files = ["/tmp/sample.wav"]
    panel._review_index = 0

    prompt_calls = []
    monkeypatch.setattr(
        panel,
        "_prompt_save",
        lambda **kwargs: prompt_calls.append(kwargs) or onset_editor_module.QMessageBox.StandardButton.Cancel,
    )

    panel._review_finish()

    assert prompt_calls == [{"prompt_text": "Save changes to sample.wav before finishing?"}]
    assert panel._review_mode is True
    assert panel._review_files == ["/tmp/sample.wav"]
    assert panel._review_index == 0


def test_apply_review_finish_state_resets_review_mode_widgets():
    panel = OnsetEditorPanel()
    panel._review_mode = True
    panel._review_files = ["/tmp/sample.wav"]
    panel._review_index = 3
    panel._review_bar.show()

    panel._apply_review_finish_state(
        {
            "review_mode": False,
            "review_files": [],
            "review_index": 0,
            "status_text": "Review complete.",
        }
    )

    assert panel._review_mode is False
    assert panel._review_files == []
    assert panel._review_index == 0
    assert panel._review_bar.isHidden() is True
    assert panel._status_label.text() == "Review complete."


def test_start_review_applies_review_state_and_loads_first_file(monkeypatch, tmp_path):
    panel = OnsetEditorPanel()
    populate_calls = []
    load_calls = []

    monkeypatch.setattr(panel, "_populate_files", lambda folder: populate_calls.append(folder))
    monkeypatch.setattr(panel, "_load_review_file", lambda index: load_calls.append(index))
    monkeypatch.setattr(
        onset_editor_module,
        "_review_audio_paths",
        lambda folder: [os.path.join(folder, "a.wav"), os.path.join(folder, "b.wav")],
    )

    panel.start_review(str(tmp_path))

    assert panel._review_folder == str(tmp_path)
    assert panel._folder_edit.text() == str(tmp_path)
    assert populate_calls == [str(tmp_path)]
    assert panel._review_files == [
        os.path.join(str(tmp_path), "a.wav"),
        os.path.join(str(tmp_path), "b.wav"),
    ]
    assert panel._review_mode is True
    assert panel._review_index == 0
    assert panel._review_bar.isHidden() is False
    assert load_calls == [0]


def test_start_review_shows_message_when_folder_has_no_audio(monkeypatch, tmp_path):
    panel = OnsetEditorPanel()
    populate_calls = []
    info_calls = []

    monkeypatch.setattr(panel, "_populate_files", lambda folder: populate_calls.append(folder))
    monkeypatch.setattr(onset_editor_module, "_review_audio_paths", lambda folder: [])
    monkeypatch.setattr(
        onset_editor_module.QMessageBox,
        "information",
        lambda *args: info_calls.append((args[1], args[2])),
    )

    panel.start_review(str(tmp_path))

    assert populate_calls == [str(tmp_path)]
    assert panel._review_folder == str(tmp_path)
    assert panel._folder_edit.text() == str(tmp_path)
    assert panel._review_files == []
    assert panel._review_mode is False
    assert panel._review_bar.isHidden() is True
    assert info_calls == [("No Files", f"No audio files found in:\n{tmp_path}")]


def test_apply_onset_manager_changes_updates_panel_state(monkeypatch):
    panel = OnsetEditorPanel()
    refresh_calls = []
    monkeypatch.setattr(panel, "_refresh_comparison_display", lambda: refresh_calls.append(True))

    panel._apply_onset_manager_changes(
        {
            "main_label_path": "/tmp/renamed_labels.txt",
            "comp_files": [{"path": "/tmp/compare.txt", "times": [0.4], "color": (1, 2, 3, 4)}],
            "tolerance_ms": 12.5,
            "filter_idx": 3,
            "color_main_only": (5, 6, 7, 8),
            "color_shared": (9, 10, 11, 12),
            "comp_palette": [(13, 14, 15, 16)],
        }
    )

    assert panel._label_path == "/tmp/renamed_labels.txt"
    assert panel._onset_file_edit.text() == "renamed_labels.txt"
    assert panel._comp_files == [{"path": "/tmp/compare.txt", "times": [0.4], "color": (1, 2, 3, 4)}]
    assert panel._comp_tolerance_ms == 12.5
    assert panel._comp_filter_idx == 3
    assert panel._COLOR_MAIN_ONLY == (5, 6, 7, 8)
    assert panel._COLOR_SHARED == (9, 10, 11, 12)
    assert panel._comp_palette == [(13, 14, 15, 16)]
    assert refresh_calls == [True]


def test_prompt_onset_manager_changes_returns_acceptance_payload(monkeypatch):
    panel = OnsetEditorPanel()
    created_kwargs = []

    class _AcceptedDialog:
        def __init__(self, **kwargs):
            created_kwargs.append(kwargs)

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_changes(self):
            return {"filter_idx": 2}

    class _RejectedDialog:
        def __init__(self, **kwargs):
            created_kwargs.append(kwargs)

        def exec(self):
            return QDialog.DialogCode.Rejected

        def get_changes(self):
            raise AssertionError("get_changes should not be called on cancel")

    monkeypatch.setattr("GUI.onset_editor.OnsetManagerDialog", _AcceptedDialog)
    accepted = panel._prompt_onset_manager_changes()

    assert accepted == {"filter_idx": 2}
    assert created_kwargs[-1]["parent"] is panel
    assert created_kwargs[-1]["tolerance_ms"] == panel._comp_tolerance_ms
    assert created_kwargs[-1]["comp_palette"] == list(panel._comp_palette)

    monkeypatch.setattr("GUI.onset_editor.OnsetManagerDialog", _RejectedDialog)
    rejected = panel._prompt_onset_manager_changes()

    assert rejected is None


def test_format_checked_layer_label_summarizes_selection():
    layers = [OnsetEditorPanel._make_default_layer("Layer 1")]
    append_layer_state(layers, layer_name="Layer 2")
    append_layer_state(layers, layer_name="Layer 3")

    assert format_checked_layer_label(layers, [1, 2]) == "Layer 2 +1 ▾"
    assert format_checked_layer_label(layers, []) == "(none) ▾"


def test_build_layer_overlay_markers_splits_unique_and_shared_onsets():
    layers = [OnsetEditorPanel._make_default_layer("Layer 1")]
    append_layer_state(layers, layer_name="Layer 2", onset_times=[0.2, 0.4])
    layers[0]["onset_times"] = [0.1, 0.2]

    markers = build_layer_overlay_markers(
        layers,
        [0, 1],
        ["overlay-red"],
        "shared-white",
        unique_style="solid",
        shared_style="dash",
    )

    assert markers == [
        {"times": [0.4], "color": "overlay-red", "style": "solid"},
        {"times": [0.2], "color": "shared-white", "style": "dash"},
    ]


def test_add_layer():
    panel = OnsetEditorPanel()
    panel._onset_times.extend([1.0, 2.0, 3.0])
    panel._add_layer()
    assert len(panel._layers) == 2
    assert panel._active_layer_idx == 1
    assert panel._layers[1]["name"] == "Layer 2"
    # New layer should be empty
    assert panel._onset_times == []
    assert panel._focus_regions == {}
    # Old layer should still have its onsets
    assert panel._layers[0]["onset_times"] == [1.0, 2.0, 3.0]


def test_remove_layer():
    panel = OnsetEditorPanel()
    panel._add_layer()  # now on Layer 2
    panel._onset_times.extend([5.0, 6.0])
    assert len(panel._layers) == 2
    panel._remove_layer()
    assert len(panel._layers) == 1
    assert panel._active_layer_idx == 0
    # Should be back to Layer 1's data
    assert panel._onset_times is panel._layers[0]["onset_times"]


def test_cannot_remove_last_layer():
    panel = OnsetEditorPanel()
    initial_count = len(panel._layers)
    panel._remove_layer()  # should be a no-op
    assert len(panel._layers) == initial_count


def test_switch_layer():
    panel = OnsetEditorPanel()
    # Put data on Layer 1
    panel._onset_times.extend([1.0, 2.0])
    panel._focus_regions["file.wav"] = [
        {"t_start": 0, "t_end": 1, "f_low": 0, "f_high": 1000, "polarity": "positive"}
    ]
    # Add Layer 2 and put different data
    panel._add_layer()
    panel._onset_times.extend([10.0, 20.0])
    panel._focus_regions["file.wav"] = [
        {"t_start": 2, "t_end": 3, "f_low": 0, "f_high": 2000, "polarity": "negative"}
    ]
    # Switch back to Layer 1
    panel._switch_layer(0)
    assert panel._active_layer_idx == 0
    assert panel._onset_times == [1.0, 2.0]
    assert panel._focus_regions["file.wav"][0]["polarity"] == "positive"
    # Switch to Layer 2
    panel._switch_layer(1)
    assert panel._active_layer_idx == 1
    assert panel._onset_times == [10.0, 20.0]
    assert panel._focus_regions["file.wav"][0]["polarity"] == "negative"


def test_switch_to_same_layer_noop():
    panel = OnsetEditorPanel()
    panel._onset_times.extend([1.0])
    panel._switch_layer(0)  # should be a no-op
    assert panel._onset_times == [1.0]


def test_switch_layer_invalid_index():
    panel = OnsetEditorPanel()
    panel._switch_layer(-1)  # should be a no-op
    panel._switch_layer(999)  # should be a no-op
    assert panel._active_layer_idx == 0


# ── UI ──────────────────────────────────────────────────────────────────


def test_layer_combo_created():
    panel = OnsetEditorPanel()
    assert panel._layer_combo is not None
    assert panel._layer_combo.count() == 1
    assert panel._layer_combo.currentText() == "Layer 1"


def test_layer_combo_updates_on_add():
    panel = OnsetEditorPanel()
    panel._add_layer()
    assert panel._layer_combo.count() == 2
    assert panel._layer_combo.currentIndex() == 1
    assert panel._layer_combo.itemText(1) == "Layer 2"


def test_on_layer_selection_changed_switches_primary_layer():
    panel = OnsetEditorPanel()
    panel._onset_times.extend([1.0, 2.0])
    panel._save_layer_state()
    panel._add_layer()
    panel._onset_times.extend([10.0])
    panel._save_layer_state()

    panel._layer_menu.rebuild(panel._layers, {1})
    panel._on_layer_selection_changed()

    assert panel._checked_layer_indices == {1}
    assert panel._active_layer_idx == 1
    assert panel._layer_combo.currentIndex() == 1
    assert panel._layer_combo_btn.text() == "Layer 2 ▾"
    assert not panel._merge_sel_btn.isEnabled()


def test_on_layer_selection_changed_with_no_checked_layers_disables_merge():
    panel = OnsetEditorPanel()
    panel._layer_menu.rebuild(panel._layers, set())

    panel._on_layer_selection_changed()

    assert panel._checked_layer_indices == set()
    assert panel._layer_combo_btn.text() == "(none) ▾"
    assert not panel._merge_sel_btn.isEnabled()


def test_layer_combo_updates_on_remove():
    panel = OnsetEditorPanel()
    panel._add_layer()
    panel._add_layer()
    assert panel._layer_combo.count() == 3
    # Remove current (Layer 3)
    panel._remove_layer()
    assert panel._layer_combo.count() == 2
    # Should be on last layer now (Layer 2)
    assert panel._active_layer_idx == 1


def test_layer_combo_triggers_switch():
    panel = OnsetEditorPanel()
    panel._onset_times.extend([1.0, 2.0])
    panel._add_layer()
    panel._onset_times.extend([10.0])
    # Switching via combo
    panel._layer_combo.setCurrentIndex(0)
    assert panel._active_layer_idx == 0
    assert panel._onset_times == [1.0, 2.0]


def test_layer_combo_switch_clears_multi_selection():
    panel = OnsetEditorPanel()
    panel._onset_times.extend([1.0, 2.0])
    panel._save_layer_state()
    panel._add_layer()
    panel._onset_times.extend([10.0])
    panel._save_layer_state()
    panel._checked_layer_indices = {0, 1}
    panel._layer_menu.rebuild(panel._layers, panel._checked_layer_indices)
    panel._rebuild_layer_menu()

    panel._layer_combo.setCurrentIndex(0)

    assert panel._active_layer_idx == 0
    assert panel._checked_layer_indices == {0}
    assert panel._layer_combo_btn.text() == "Layer 1 ▾"
    assert not panel._merge_sel_btn.isEnabled()


def test_add_remove_layer_buttons():
    panel = OnsetEditorPanel()
    assert panel._add_layer_btn is not None
    assert panel._remove_layer_btn is not None
    # Remove should be disabled with 1 layer
    panel._update_button_states()
    assert not panel._remove_layer_btn.isEnabled()
    panel._add_layer()
    panel._update_button_states()
    assert panel._remove_layer_btn.isEnabled()


# ── Undo per layer ─────────────────────────────────────────────────────


def test_undo_stack_per_layer():
    panel = OnsetEditorPanel()
    # Add onset to Layer 1 and push undo
    panel._onset_times.append(1.0)
    panel._undo_stack.push(list(panel._onset_times))
    # Add Layer 2
    panel._add_layer()
    panel._onset_times.append(5.0)
    panel._undo_stack.push(list(panel._onset_times))
    # Switch to Layer 1: its undo should have 2 entries (initial + 1 onset)
    panel._switch_layer(0)
    assert panel._undo_stack.can_undo()
    # Switch to Layer 2: should also have its own undo state
    panel._switch_layer(1)
    assert panel._undo_stack.can_undo()


# ── Save / Export ──────────────────────────────────────────────────────


def test_save_single_layer_label(tmp_path):
    panel = OnsetEditorPanel()
    audio_path = str(tmp_path / "test.wav")
    label_path = str(tmp_path / "test_labels.txt")
    panel._audio_path = audio_path
    panel._label_path = label_path
    panel._onset_times.extend([1.0, 2.0, 3.0])
    panel._save_labels()
    assert os.path.isfile(label_path)
    with open(label_path) as f:
        lines = f.readlines()
    assert len(lines) == 3


def test_save_multi_layer_labels(tmp_path):
    panel = OnsetEditorPanel()
    audio_path = str(tmp_path / "test.wav")
    label_path = str(tmp_path / "test_labels.txt")
    panel._audio_path = audio_path
    panel._label_path = label_path
    panel._onset_times.extend([1.0, 2.0])
    panel._add_layer()
    panel._onset_times.extend([5.0, 6.0, 7.0])
    panel._save_labels()
    # Should create numbered files
    assert os.path.isfile(str(tmp_path / "test_labels_1.txt"))
    assert os.path.isfile(str(tmp_path / "test_labels_2.txt"))
    # Also main path
    assert os.path.isfile(label_path)
    # Layer 1 file should have 2 lines
    with open(str(tmp_path / "test_labels_1.txt")) as f:
        assert len(f.readlines()) == 2
    # Layer 2 file should have 3 lines
    with open(str(tmp_path / "test_labels_2.txt")) as f:
        assert len(f.readlines()) == 3


def test_dirty_flag_per_layer():
    panel = OnsetEditorPanel()
    panel._dirty = True
    panel._save_layer_state()
    assert panel._layers[0]["dirty"] is True
    panel._add_layer()
    assert panel._dirty is False  # new layer starts clean
    panel._dirty = True
    panel._save_layer_state()
    # Both layers should have their own dirty state
    assert panel._layers[0]["dirty"] is True
    assert panel._layers[1]["dirty"] is True


# ── Focus regions per layer ────────────────────────────────────────────


def test_focus_regions_per_layer():
    panel = OnsetEditorPanel()
    panel._audio_path = "/fake/test.wav"
    fname = "test.wav"
    # Layer 1 gets positive regions
    panel._focus_regions[fname] = [
        {"t_start": 0, "t_end": 1, "f_low": 0, "f_high": 1000, "polarity": "positive"}
    ]
    # Layer 2 gets negative regions
    panel._add_layer()
    panel._focus_regions[fname] = [
        {"t_start": 2, "t_end": 3, "f_low": 0, "f_high": 2000, "polarity": "negative"}
    ]
    # Switch back: should get Layer 1's positive regions
    panel._switch_layer(0)
    assert panel._focus_regions[fname][0]["polarity"] == "positive"
    panel._switch_layer(1)
    assert panel._focus_regions[fname][0]["polarity"] == "negative"


# ── Layer name editing ──────────────────────────────────────────────────


def test_layer_name_edit_initial_blank():
    """Layer 1 starts with default name 'Layer 1'."""
    panel = OnsetEditorPanel()
    assert panel._layers[0]["name"] == "Layer 1"


def test_layer_name_edit_updates_layer_dict():
    """Updating the layer name updates the layer dict and combo text."""
    panel = OnsetEditorPanel()
    panel._on_layer_name_changed("Drums")
    assert panel._layers[0]["name"] == "Drums"
    assert panel._layer_combo.itemText(0) == "Drums"


def test_layer_name_edit_empty_resets_to_default():
    """Clearing the name reverts to the default."""
    panel = OnsetEditorPanel()
    panel._on_layer_name_changed("Drums")
    assert panel._layers[0]["name"] == "Drums"
    panel._on_layer_name_changed("")
    assert panel._layers[0]["name"] == "Layer 1"


def test_layer_name_survives_switch():
    """Custom names survive switching between layers."""
    panel = OnsetEditorPanel()
    panel._on_layer_name_changed("Drums")
    panel._add_layer()
    panel._on_layer_name_changed("Vocals")
    # Switch back to layer 0
    panel._switch_layer(0)
    assert panel._layers[0]["name"] == "Drums"
    # Switch to layer 1
    panel._switch_layer(1)
    assert panel._layers[1]["name"] == "Vocals"


def test_layer_name_in_get_values():
    """Custom layer names are serialized in get_values."""
    panel = OnsetEditorPanel()
    panel._on_layer_name_changed("Drums")
    panel._add_layer()
    panel._on_layer_name_changed("Vocals")
    vals = panel.get_values()
    assert vals["layers"][0]["name"] == "Drums"
    assert vals["layers"][1]["name"] == "Vocals"


def test_layer_name_roundtrip_set_values():
    """Layer names survive get_values → set_values round-trip."""
    panel = OnsetEditorPanel()
    panel._on_layer_name_changed("Drums")
    panel._add_layer()
    panel._on_layer_name_changed("Vocals")
    vals = panel.get_values()

    panel2 = OnsetEditorPanel()
    panel2.set_values(vals)
    assert panel2._layers[0]["name"] == "Drums"
    assert panel2._layers[1]["name"] == "Vocals"
    assert panel2._layer_combo.itemText(0) == "Drums"
    assert panel2._layer_combo.itemText(1) == "Vocals"


def test_add_layer_clears_name_edit():
    """Adding a new layer gives it the default name."""
    panel = OnsetEditorPanel()
    panel._on_layer_name_changed("Drums")
    panel._add_layer()
    assert panel._layers[1]["name"] == "Layer 2"


def test_remove_layer_updates_name_edit():
    """Removing a layer keeps the remaining layer's name."""
    panel = OnsetEditorPanel()
    panel._on_layer_name_changed("Drums")
    panel._add_layer()
    panel._on_layer_name_changed("Vocals")
    # Remove layer 1 (Vocals) — should go back to layer 0 (Drums)
    panel._remove_layer()
    assert panel._layers[0]["name"] == "Drums"


# ── Move / Copy focus regions between layers ────────────────────────────


def test_move_focus_region_to_layer():
    """Moving a region removes it from source and adds to target."""
    panel = OnsetEditorPanel()
    panel._audio_path = "/fake/audio.wav"
    panel._focus_regions["audio.wav"] = [
        {"t_start": 0.0, "t_end": 1.0, "f_low": 100, "f_high": 500, "polarity": "positive"},
        {"t_start": 2.0, "t_end": 3.0, "f_low": 200, "f_high": 600, "polarity": "negative"},
    ]
    panel._add_layer()  # switch to Layer 2
    panel._switch_layer(0)  # back to Layer 1

    # Move region 0 (positive) to Layer 2 (index 1)
    panel._transfer_focus_region(0, 1, remove_from_source=True)

    # Source layer should now have only the negative region
    assert len(panel._focus_regions["audio.wav"]) == 1
    assert panel._focus_regions["audio.wav"][0]["polarity"] == "negative"
    # Target layer should have the moved region
    target_regions = panel._layers[1]["focus_regions"].get("audio.wav", [])
    assert len(target_regions) == 1
    assert target_regions[0]["polarity"] == "positive"
    assert target_regions[0]["t_start"] == 0.0


def test_copy_focus_region_to_layer():
    """Copying a region keeps it in source and adds to target."""
    panel = OnsetEditorPanel()
    panel._audio_path = "/fake/audio.wav"
    panel._focus_regions["audio.wav"] = [
        {"t_start": 1.0, "t_end": 2.0, "f_low": 300, "f_high": 800, "polarity": "positive"},
    ]
    panel._add_layer()  # Layer 2
    panel._switch_layer(0)

    panel._transfer_focus_region(0, 1, remove_from_source=False)

    # Source should still have the region
    assert len(panel._focus_regions["audio.wav"]) == 1
    # Target should also have it
    target_regions = panel._layers[1]["focus_regions"].get("audio.wav", [])
    assert len(target_regions) == 1
    assert target_regions[0]["t_start"] == 1.0


def test_move_to_new_layer():
    """Moving to target_layer_idx=-1 creates a new layer."""
    panel = OnsetEditorPanel()
    panel._audio_path = "/fake/audio.wav"
    panel._focus_regions["audio.wav"] = [
        {"t_start": 0.5, "t_end": 1.5, "f_low": 100, "f_high": 400, "polarity": "positive"},
    ]

    assert len(panel._layers) == 1
    panel._transfer_focus_region(0, -1, remove_from_source=True)

    # A new layer should have been created
    assert len(panel._layers) == 2
    # Region should be in the new layer
    new_layer_regions = panel._layers[1]["focus_regions"].get("audio.wav", [])
    assert len(new_layer_regions) == 1
    assert new_layer_regions[0]["t_start"] == 0.5
    # Source should be empty
    assert len(panel._focus_regions["audio.wav"]) == 0


def test_copy_to_new_layer():
    """Copying to target_layer_idx=-1 creates a new layer and keeps source."""
    panel = OnsetEditorPanel()
    panel._audio_path = "/fake/audio.wav"
    panel._focus_regions["audio.wav"] = [
        {"t_start": 0.5, "t_end": 1.5, "f_low": 100, "f_high": 400, "polarity": "positive"},
    ]

    panel._transfer_focus_region(0, -1, remove_from_source=False)

    assert len(panel._layers) == 2
    # Source keeps its region
    assert len(panel._focus_regions["audio.wav"]) == 1
    # New layer also has it
    new_layer_regions = panel._layers[1]["focus_regions"].get("audio.wav", [])
    assert len(new_layer_regions) == 1


def test_transfer_focus_region_updates_status_and_browser():
    panel = OnsetEditorPanel()
    panel._audio_path = "/fake/audio.wav"
    panel._focus_regions["audio.wav"] = [
        {"t_start": 0.5, "t_end": 1.5, "f_low": 100, "f_high": 400, "polarity": "positive"},
    ]
    signal_browser_calls = []
    panel._refresh_signal_browser_combo = lambda: signal_browser_calls.append(True)

    panel._transfer_focus_region(0, -1, remove_from_source=False)

    assert panel._status_label.text() == "Copied positive region to Layer 2"
    assert signal_browser_calls == [True]


def test_move_to_same_layer_noop():
    """Moving a region to the same layer does nothing."""
    panel = OnsetEditorPanel()
    panel._audio_path = "/fake/audio.wav"
    panel._focus_regions["audio.wav"] = [
        {"t_start": 0.0, "t_end": 1.0, "f_low": 100, "f_high": 500, "polarity": "positive"},
    ]
    # Try to move to the active layer (index 0)
    panel._transfer_focus_region(0, 0, remove_from_source=True)
    # Region should still be there
    assert len(panel._focus_regions["audio.wav"]) == 1


# ── Layer merging workflows ────────────────────────────────────────────


def test_merge_selected_layers_creates_deduped_layer(monkeypatch):
    panel = OnsetEditorPanel()
    panel._onset_times.extend([0.1, 0.2])
    panel._save_layer_state()

    panel._add_layer()
    panel._onset_times.extend([0.2, 0.4])
    panel._save_layer_state()

    panel._checked_layer_indices = {0, 1}
    panel._layer_menu.rebuild(panel._layers, panel._checked_layer_indices)

    monkeypatch.setattr(
        onset_editor_module.QMessageBox,
        "question",
        lambda *_args, **_kwargs: onset_editor_module.QMessageBox.StandardButton.Yes,
    )

    panel._merge_selected_layers()

    assert len(panel._layers) == 3
    assert panel._layers[2]["name"] == "Merged (selected)"
    assert panel._layers[2]["onset_times"] == [0.1, 0.2, 0.4]
    assert panel._active_layer_idx == 2
    assert panel._layer_combo.currentIndex() == 2
    assert panel._checked_layer_indices == {2}


def test_confirm_and_merge_layers_creates_final_merged_layer(monkeypatch):
    panel = OnsetEditorPanel()
    panel._onset_times.extend([0.1, 0.2])
    panel._save_layer_state()

    panel._add_layer()
    panel._onset_times.extend([0.2, 0.5])
    panel._save_layer_state()

    monkeypatch.setattr(
        onset_editor_module.QMessageBox,
        "question",
        lambda *_args, **_kwargs: onset_editor_module.QMessageBox.StandardButton.Yes,
    )

    panel._confirm_and_merge_layers()

    assert len(panel._layers) == 3
    assert panel._layers[2]["name"] == "FinalMergedOnsets"
    assert panel._layers[2]["onset_times"] == [0.1, 0.2, 0.5]
    assert panel._active_layer_idx == 2
    assert panel._layer_combo.currentIndex() == 2
    assert panel._checked_layer_indices == {2}


def test_apply_cluster_layers_creates_layer_per_cluster():
    panel = OnsetEditorPanel()
    panel._audio_path = "/fake/example.wav"
    panel._focus_regions["example.wav"] = [
        {"t_start": 0.0, "t_end": 0.5, "f_low": 100, "f_high": 400, "polarity": "positive"},
        {"t_start": 0.6, "t_end": 1.0, "f_low": 500, "f_high": 900, "polarity": "positive"},
        {"t_start": 1.1, "t_end": 1.4, "f_low": 50, "f_high": 1200, "polarity": "negative"},
    ]

    panel._apply_cluster_layers(
        {
            "n_clusters": 2,
            "labels": [0, 1],
            "descriptions": ["Low Band", "High Band"],
        }
    )

    assert len(panel._layers) == 3
    assert panel._layers[1]["name"] == "Layer 2 — Low Band"
    assert panel._layers[2]["name"] == "Layer 3 — High Band"
    assert len(panel._layers[1]["focus_regions"]["example.wav"]) == 2
    assert len(panel._layers[2]["focus_regions"]["example.wav"]) == 2
    assert panel._layers[1]["focus_regions"]["example.wav"][0]["polarity"] == "positive"
    assert panel._layers[1]["focus_regions"]["example.wav"][1]["polarity"] == "negative"
    assert panel._active_layer_idx == 1
    assert panel._checked_layer_indices == {0, 1, 2}
