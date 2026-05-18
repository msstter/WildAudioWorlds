import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.join(os.path.dirname(__file__), "..")
GUI_DIR = os.path.join(ROOT, "GUI")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if GUI_DIR not in sys.path:
    sys.path.insert(0, GUI_DIR)

import pandas as pd
from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

from pipeline_gui import ExtractorPanel, MainWindow, MuterPanel
from panels.pipeline_prep_panel import PipelinePrepPanel
from scripts import excel_onset_io, onset_finder, thebeat_extractor


def _make_audio_folder(tmp_path):
    folder = tmp_path / "audio"
    folder.mkdir()
    for name in ("alpha.wav", "beta.mp3", "notes.txt"):
        (folder / name).write_bytes(b"")
    return folder


def _make_pipeline_workbook(tmp_path):
    workbook = tmp_path / "Cross_Species_Rhythm_Data.xlsx"
    summary = pd.DataFrame({
        "File Name": ["ALPHA.WAV", "beta.mp3"],
        "Exact Onset Times Used (s)": ["0.100000, 0.600000, 1.100000", None],
        "Total Onsets Used": [3, 0],
        "Stable Dyads Retained": [1, 0],
    })
    raw_dyads = pd.DataFrame(columns=excel_onset_io._DYAD_COLUMNS)
    stable_dyads = pd.DataFrame(columns=excel_onset_io._DYAD_COLUMNS)
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="File Summaries", index=False)
        raw_dyads.to_excel(writer, sheet_name="Dyadic Events (For Plots)", index=False)
        stable_dyads.to_excel(writer, sheet_name="Dyadic Events (Stable Rhythms)", index=False)
    return str(workbook)


def test_muter_panel_defaults_first_selected_file(tmp_path):
    folder = _make_audio_folder(tmp_path)
    panel = MuterPanel()

    panel.input_folder.setText(str(folder))
    panel.specify_files_cb.setChecked(True)

    assert panel.selected_files_combo.selected_files() == ["alpha.wav"]

    vals = panel.get_values()
    assert vals["MUTER_SPECIFY_FILES"] is True
    assert vals["MUTER_SELECTED_FILES"] == ["alpha.wav"]


def test_muter_panel_set_values_restores_selected_files(tmp_path):
    folder = _make_audio_folder(tmp_path)
    panel = MuterPanel()

    panel.set_values({
        "MUTER_INPUT_FOLDER": str(folder),
        "MUTER_SPECIFY_FILES": True,
        "MUTER_SELECTED_FILES": ["beta.mp3"],
    })

    assert panel.specify_files_cb.isChecked() is True
    assert panel.selected_files_combo.selected_files() == ["beta.mp3"]


def test_extractor_panel_defaults_first_selected_file(tmp_path):
    folder = _make_audio_folder(tmp_path)
    panel = ExtractorPanel()

    panel.audio_folder.setText(str(folder))
    panel.specify_files_cb.setChecked(True)

    assert panel.selected_files_combo.selected_files() == ["alpha.wav"]

    vals = panel.get_values()
    assert vals["EXTRACTOR_SPECIFY_FILES"] is True
    assert vals["EXTRACTOR_SELECTED_FILES"] == ["alpha.wav"]


def test_extractor_panel_set_values_restores_selected_files(tmp_path):
    folder = _make_audio_folder(tmp_path)
    panel = ExtractorPanel()

    panel.set_values({
        "audio_folder": str(folder),
        "EXTRACTOR_SPECIFY_FILES": True,
        "EXTRACTOR_SELECTED_FILES": ["beta.mp3"],
    })

    assert panel.specify_files_cb.isChecked() is True
    assert panel.selected_files_combo.selected_files() == ["beta.mp3"]


def test_onset_finder_resolve_audio_files_filters_requested_names(tmp_path):
    folder = _make_audio_folder(tmp_path)

    files, missing = onset_finder.resolve_audio_files(
        str(folder), ["beta.mp3", "missing.wav"])

    assert files == ["beta.mp3"]
    assert missing == ["missing.wav"]


def test_thebeat_resolve_audio_files_filters_requested_names(tmp_path):
    folder = _make_audio_folder(tmp_path)

    files, missing = thebeat_extractor.resolve_audio_files(
        str(folder), ["alpha.wav", "missing.wav"])

    assert files == ["alpha.wav"]
    assert missing == ["missing.wav"]


def test_main_window_autosets_beat_tempo_output_excel_from_extractor(tmp_path):
    window = MainWindow()
    extractor_excel = str(tmp_path / "AudioData_OnsetFinder.xlsx")

    window.extractor_panel.output_excel.setText(extractor_excel)
    _app.processEvents()

    assert window.beat_tempo_panel.output_excel.text() == extractor_excel

    config = window._build_config()
    assert config["beat_tempo"]["output_excel_path"] == extractor_excel

    window.close()
    _app.processEvents()


def test_pipeline_prep_panel_previews_and_imports_outside_onsets(tmp_path):
    folder = _make_audio_folder(tmp_path)
    workbook = _make_pipeline_workbook(tmp_path)
    source_csv = tmp_path / "outside_onsets.csv"
    pd.DataFrame({
        "External File": ["alpha.wav", "beta", "missing.wav"],
        "Detected Onsets": [
            "0.000000, 0.500000, 1.000000",
            "0.200000, 0.700000, 1.200000",
            "0.100000, 0.200000",
        ],
    }).to_csv(source_csv, index=False)

    panel = PipelinePrepPanel()
    panel.input_folder.setText(str(folder))
    panel.excel_path.setText(workbook)

    preview = panel._preview_outside_onset_matches(
        str(source_csv),
        source_sheet=0,
        source_filename_col="External File",
        source_onset_col="Detected Onsets",
    )

    assert [match["audio_filename"] for match in preview["matches"]] == ["alpha.wav", "beta.mp3"]
    alpha_match = preview["matches"][0]
    beta_match = preview["matches"][1]
    assert alpha_match["target_row_exists"] is True
    assert alpha_match["current_onset_count"] == 3
    assert beta_match["target_row_exists"] is True
    assert beta_match["current_onset_count"] == 0
    assert preview["unmatched_source_names"] == ["missing.wav"]

    result = panel._import_outside_onsets(
        str(source_csv),
        source_sheet=0,
        source_filename_col="External File",
        source_onset_col="Detected Onsets",
        overwrite_existing=False,
    )

    assert result["imported"] == 1
    assert result["skipped_existing"] == ["alpha.wav"]

    summary = pd.read_excel(workbook, sheet_name="File Summaries", engine="openpyxl")
    beta_row = summary.loc[
        summary["File Name"].astype(str).str.strip().str.lower() == "beta.mp3"
    ].iloc[0]
    assert excel_onset_io.parse_onset_string(str(beta_row["Exact Onset Times Used (s)"])) == [0.2, 0.7, 1.2]

    panel.close()
    _app.processEvents()