"""Tests for Excel/CSV onset I/O integration.

Covers:
- excel_onset_io utility functions (parsing, loading, saving)
- OnsetEditorPanel Excel integration
- Backward compatibility with .txt labels
"""

import os
import sys
import tempfile

import numpy as np
import pandas as pd
import pytest

# Ensure scripts/ and GUI/ are on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "GUI"))

import excel_onset_io as eio


# ═══════════════════════════════════════════════════════════════════════════
# parse_onset_string
# ═══════════════════════════════════════════════════════════════════════════

class TestParseOnsetString:
    def test_comma_separated(self):
        result = eio.parse_onset_string("0.5, 1.2, 2.1")
        assert result == [0.5, 1.2, 2.1]

    def test_bracketed(self):
        result = eio.parse_onset_string("[0.5, 1.2, 2.1]")
        assert result == [0.5, 1.2, 2.1]

    def test_semicolons(self):
        result = eio.parse_onset_string("0.5;1.2;2.1")
        assert result == [0.5, 1.2, 2.1]

    def test_spaces(self):
        result = eio.parse_onset_string("0.5 1.2 2.1")
        assert result == [0.5, 1.2, 2.1]

    def test_mixed_whitespace(self):
        result = eio.parse_onset_string(" 0.5 ,  1.2 , 2.1 ")
        assert result == [0.5, 1.2, 2.1]

    def test_empty(self):
        assert eio.parse_onset_string("") == []
        assert eio.parse_onset_string(None) == []

    def test_single_value(self):
        assert eio.parse_onset_string("1.5") == [1.5]

    def test_sorted_output(self):
        result = eio.parse_onset_string("3.0, 1.0, 2.0")
        assert result == [1.0, 2.0, 3.0]

    def test_high_precision(self):
        result = eio.parse_onset_string("0.123456, 1.234567")
        assert len(result) == 2
        assert abs(result[0] - 0.123456) < 1e-10
        assert abs(result[1] - 1.234567) < 1e-10

    def test_parentheses(self):
        result = eio.parse_onset_string("(0.5, 1.2)")
        assert result == [0.5, 1.2]

    def test_invalid_values_skipped(self):
        result = eio.parse_onset_string("0.5, abc, 1.2")
        assert result == [0.5, 1.2]


# ═══════════════════════════════════════════════════════════════════════════
# format_onset_string
# ═══════════════════════════════════════════════════════════════════════════

class TestFormatOnsetString:
    def test_basic(self):
        result = eio.format_onset_string([0.5, 1.2, 2.1])
        assert result == "0.500000, 1.200000, 2.100000"

    def test_custom_precision(self):
        result = eio.format_onset_string([0.5, 1.2], precision=2)
        assert result == "0.50, 1.20"

    def test_empty(self):
        assert eio.format_onset_string([]) == ""

    def test_sorted(self):
        # Even if input is unsorted, output should be sorted
        result = eio.format_onset_string([2.0, 1.0, 3.0])
        assert result == "1.000000, 2.000000, 3.000000"


# ═══════════════════════════════════════════════════════════════════════════
# Excel file creation helper
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_excel(tmp_path):
    """Create a sample Excel file resembling Onset Finder output."""
    data = {
        "File Name": ["song1.wav", "song2.wav", "song3.wav"],
        "Total Onsets Used": [5, 3, 4],
        "Average Cycle Duration (ms)": [500.0, 600.0, 450.0],
        "Exact Onset Times Used (s)": [
            "0.100000, 0.500000, 1.000000, 1.500000, 2.000000",
            "0.200000, 0.800000, 1.400000",
            "0.300000, 0.700000, 1.100000, 1.500000",
        ],
    }
    df = pd.DataFrame(data)
    excel_path = str(tmp_path / "test_data.xlsx")
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="File Summaries", index=False)
        # Also add a dyads sheet
        dyads = pd.DataFrame({
            "File Name": ["song1.wav", "song1.wav"],
            "Dyad Index": [1, 2],
            "Interval 1 (ms)": [400.0, 500.0],
        })
        dyads.to_excel(writer, sheet_name="Dyadic Events (For Plots)", index=False)
    return excel_path


@pytest.fixture
def sample_csv(tmp_path):
    """Create a sample CSV file with onset data."""
    data = {
        "File Name": ["song1.wav", "song2.wav"],
        "Onsets": [
            "0.1, 0.5, 1.0",
            "[0.2, 0.8, 1.4]",
        ],
    }
    df = pd.DataFrame(data)
    csv_path = str(tmp_path / "test_data.csv")
    df.to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def pipeline_workbook(tmp_path):
    """Workbook resembling the pipeline summary/raw/stable output layout."""
    summary = pd.DataFrame({
        "File Name": ["Song1.WAV", "song2.wav"],
        "Group": ["A", "B"],
        "Estimated Overall BPM": [120.0, "N/A"],
        "Total Onsets Used": [3, 0],
        "Average Cycle Duration (ms)": [1000.0, "N/A"],
        "Stable Dyads Retained": [1, 0],
        "nPVI (Isochrony)": [0.0, "N/A"],
        "CV of Intervals": [0.0, "N/A"],
        "r_k Std Dev": [0.0, "N/A"],
        "r_k Entropy (Categorical Measure)": [0.0, "N/A"],
        "Stable Rhythm nPVI": [0.0, "N/A"],
        "Stable Rhythm CV": [0.0, "N/A"],
        "Stable Rhythm r_k Std Dev": [0.0, "N/A"],
        "Stable Rhythm Entropy": [0.0, "N/A"],
        "Exact Onset Times Used (s)": ["0.100000, 0.600000, 1.100000", np.nan],
    })
    raw_dyads = pd.DataFrame([
        {
            "File Name": "Song1.WAV",
            "Dyad Index": 1,
            "Interval 1 (ms)": 500.0,
            "Interval 2 (ms)": 500.0,
            "Cycle Duration [cd] (ms)": 1000.0,
            "Short Interval [i_s] (ms)": 500.0,
            "Long Interval [i_l] (ms)": 500.0,
            "Rhythm Ratio [r_k]": 0.5,
            "Stable Rhythm": True,
        },
        {
            "File Name": "song2.wav",
            "Dyad Index": 1,
            "Interval 1 (ms)": 700.0,
            "Interval 2 (ms)": 300.0,
            "Cycle Duration [cd] (ms)": 1000.0,
            "Short Interval [i_s] (ms)": 300.0,
            "Long Interval [i_l] (ms)": 700.0,
            "Rhythm Ratio [r_k]": 0.3,
            "Stable Rhythm": False,
        },
    ], columns=eio._DYAD_COLUMNS)
    stable_dyads = pd.DataFrame([
        {
            "File Name": "Song1.WAV",
            "Dyad Index": 1,
            "Interval 1 (ms)": 500.0,
            "Interval 2 (ms)": 500.0,
            "Cycle Duration [cd] (ms)": 1000.0,
            "Short Interval [i_s] (ms)": 500.0,
            "Long Interval [i_l] (ms)": 500.0,
            "Rhythm Ratio [r_k]": 0.5,
            "Stable Rhythm": True,
        },
        {
            "File Name": "song2.wav",
            "Dyad Index": 1,
            "Interval 1 (ms)": 700.0,
            "Interval 2 (ms)": 300.0,
            "Cycle Duration [cd] (ms)": 1000.0,
            "Short Interval [i_s] (ms)": 300.0,
            "Long Interval [i_l] (ms)": 700.0,
            "Rhythm Ratio [r_k]": 0.3,
            "Stable Rhythm": True,
        },
    ], columns=eio._DYAD_COLUMNS)
    meta = pd.DataFrame({"Note": ["preserve me"]})
    excel_path = str(tmp_path / "pipeline_workbook.xlsx")
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="File Summaries", index=False)
        raw_dyads.to_excel(writer, sheet_name="Dyadic Events (For Plots)", index=False)
        stable_dyads.to_excel(writer, sheet_name="Dyadic Events (Stable Rhythms)", index=False)
        meta.to_excel(writer, sheet_name="Meta", index=False)
    return excel_path


# ═══════════════════════════════════════════════════════════════════════════
# get_sheet_names, get_columns, get_filenames
# ═══════════════════════════════════════════════════════════════════════════

class TestSheetInfo:
    def test_get_sheet_names_excel(self, sample_excel):
        sheets = eio.get_sheet_names(sample_excel)
        assert "File Summaries" in sheets
        assert "Dyadic Events (For Plots)" in sheets

    def test_get_sheet_names_csv(self, sample_csv):
        sheets = eio.get_sheet_names(sample_csv)
        assert sheets == ["Sheet1"]

    def test_get_columns(self, sample_excel):
        cols = eio.get_columns(sample_excel, "File Summaries")
        assert "File Name" in cols
        assert "Exact Onset Times Used (s)" in cols

    def test_get_columns_csv(self, sample_csv):
        cols = eio.get_columns(sample_csv)
        assert "File Name" in cols
        assert "Onsets" in cols

    def test_get_filenames(self, sample_excel):
        names = eio.get_filenames(sample_excel, "File Name", "File Summaries")
        assert set(names) == {"song1.wav", "song2.wav", "song3.wav"}


# ═══════════════════════════════════════════════════════════════════════════
# load_onsets_for_file
# ═══════════════════════════════════════════════════════════════════════════

class TestLoadOnsets:
    def test_load_single_file(self, sample_excel):
        times = eio.load_onsets_for_file(
            sample_excel, "song1.wav",
            "File Name", "Exact Onset Times Used (s)", "File Summaries")
        assert len(times) == 5
        assert abs(times[0] - 0.1) < 1e-6
        assert abs(times[4] - 2.0) < 1e-6

    def test_load_second_file(self, sample_excel):
        times = eio.load_onsets_for_file(
            sample_excel, "song2.wav",
            "File Name", "Exact Onset Times Used (s)", "File Summaries")
        assert len(times) == 3

    def test_file_not_found(self, sample_excel):
        times = eio.load_onsets_for_file(
            sample_excel, "nonexistent.wav",
            "File Name", "Exact Onset Times Used (s)", "File Summaries")
        assert times == []

    def test_case_insensitive(self, sample_excel):
        times = eio.load_onsets_for_file(
            sample_excel, "SONG1.WAV",
            "File Name", "Exact Onset Times Used (s)", "File Summaries")
        assert len(times) == 5

    def test_load_from_csv(self, sample_csv):
        times = eio.load_onsets_for_file(
            sample_csv, "song1.wav", "File Name", "Onsets")
        assert len(times) == 3
        assert abs(times[0] - 0.1) < 1e-6

    def test_load_bracketed_csv(self, sample_csv):
        times = eio.load_onsets_for_file(
            sample_csv, "song2.wav", "File Name", "Onsets")
        assert len(times) == 3

    def test_wrong_column(self, sample_excel):
        times = eio.load_onsets_for_file(
            sample_excel, "song1.wav",
            "File Name", "NonexistentColumn", "File Summaries")
        assert times == []


# ═══════════════════════════════════════════════════════════════════════════
# load_all_onsets
# ═══════════════════════════════════════════════════════════════════════════

class TestLoadAllOnsets:
    def test_load_all(self, sample_excel):
        all_onsets = eio.load_all_onsets(
            sample_excel, "File Name",
            "Exact Onset Times Used (s)", "File Summaries")
        assert len(all_onsets) == 3
        assert "song1.wav" in all_onsets
        assert len(all_onsets["song1.wav"]) == 5


# ═══════════════════════════════════════════════════════════════════════════
# save_onsets_to_excel — overwrite mode
# ═══════════════════════════════════════════════════════════════════════════

class TestSaveOnsets:
    def test_overwrite_existing(self, sample_excel):
        new_times = [0.111, 0.222, 0.333]
        result = eio.save_onsets_to_excel(
            file_path=sample_excel,
            audio_filename="song1.wav",
            onset_times=new_times,
            filename_col="File Name",
            onset_col="Exact Onset Times Used (s)",
            sheet_name="File Summaries",
        )
        assert result["column"] == "Exact Onset Times Used (s)"
        assert result["old_value"] is not None  # had previous data

        # Verify the data was actually written
        reloaded = eio.load_onsets_for_file(
            sample_excel, "song1.wav",
            "File Name", "Exact Onset Times Used (s)", "File Summaries")
        assert len(reloaded) == 3
        assert abs(reloaded[0] - 0.111) < 1e-6

    def test_other_rows_preserved(self, sample_excel):
        new_times = [9.999]
        eio.save_onsets_to_excel(
            file_path=sample_excel,
            audio_filename="song1.wav",
            onset_times=new_times,
            filename_col="File Name",
            onset_col="Exact Onset Times Used (s)",
            sheet_name="File Summaries",
        )
        # song2 should be unchanged
        times2 = eio.load_onsets_for_file(
            sample_excel, "song2.wav",
            "File Name", "Exact Onset Times Used (s)", "File Summaries")
        assert len(times2) == 3

    def test_other_sheets_preserved(self, sample_excel):
        eio.save_onsets_to_excel(
            file_path=sample_excel,
            audio_filename="song1.wav",
            onset_times=[1.0, 2.0],
            filename_col="File Name",
            onset_col="Exact Onset Times Used (s)",
            sheet_name="File Summaries",
        )
        # Dyadic Events sheet should still exist
        sheets = eio.get_sheet_names(sample_excel)
        assert "Dyadic Events (For Plots)" in sheets

    def test_file_not_found_raises(self, sample_excel):
        with pytest.raises(ValueError, match="not found"):
            eio.save_onsets_to_excel(
                file_path=sample_excel,
                audio_filename="nonexistent.wav",
                onset_times=[1.0],
                filename_col="File Name",
                onset_col="Exact Onset Times Used (s)",
                sheet_name="File Summaries",
            )


# ═══════════════════════════════════════════════════════════════════════════
# save_onsets_to_excel — new column mode
# ═══════════════════════════════════════════════════════════════════════════

class TestSaveNewColumn:
    def test_save_to_new_column(self, sample_excel):
        new_times = [0.111, 0.222]
        result = eio.save_onsets_to_excel(
            file_path=sample_excel,
            audio_filename="song1.wav",
            onset_times=new_times,
            filename_col="File Name",
            onset_col="Exact Onset Times Used (s)",
            sheet_name="File Summaries",
            new_col_name="Exact Onset Times Used (s)_OnsetEdits",
        )
        assert result["column"] == "Exact Onset Times Used (s)_OnsetEdits"
        assert result["column_existed"] is False

        # Verify new column data
        edited = eio.load_onsets_for_file(
            sample_excel, "song1.wav",
            "File Name", "Exact Onset Times Used (s)_OnsetEdits",
            "File Summaries")
        assert len(edited) == 2

        # Original column should be unchanged
        original = eio.load_onsets_for_file(
            sample_excel, "song1.wav",
            "File Name", "Exact Onset Times Used (s)", "File Summaries")
        assert len(original) == 5

    def test_save_to_existing_column_name(self, sample_excel):
        """Saving to a new column name that already exists."""
        # First call creates the column
        eio.save_onsets_to_excel(
            file_path=sample_excel,
            audio_filename="song1.wav",
            onset_times=[1.0],
            filename_col="File Name",
            onset_col="Exact Onset Times Used (s)",
            sheet_name="File Summaries",
            new_col_name="MyEdits",
        )
        # Second call — column_existed should be True
        result = eio.save_onsets_to_excel(
            file_path=sample_excel,
            audio_filename="song2.wav",
            onset_times=[2.0],
            filename_col="File Name",
            onset_col="Exact Onset Times Used (s)",
            sheet_name="File Summaries",
            new_col_name="MyEdits",
        )
        assert result["column_existed"] is True


# ═══════════════════════════════════════════════════════════════════════════
# save_onsets_to_excel — duplicate file mode
# ═══════════════════════════════════════════════════════════════════════════

class TestSaveDuplicate:
    def test_save_to_new_file(self, sample_excel, tmp_path):
        output = str(tmp_path / "output_copy.xlsx")
        eio.save_onsets_to_excel(
            file_path=sample_excel,
            audio_filename="song1.wav",
            onset_times=[0.5, 1.5],
            filename_col="File Name",
            onset_col="Exact Onset Times Used (s)",
            sheet_name="File Summaries",
            output_path=output,
        )
        assert os.path.isfile(output)

        # Verify output has updated data
        edited = eio.load_onsets_for_file(
            output, "song1.wav",
            "File Name", "Exact Onset Times Used (s)", "File Summaries")
        assert len(edited) == 2

        # Original file should be unchanged
        original = eio.load_onsets_for_file(
            sample_excel, "song1.wav",
            "File Name", "Exact Onset Times Used (s)", "File Summaries")
        assert len(original) == 5


# ═══════════════════════════════════════════════════════════════════════════
# CSV save operations
# ═══════════════════════════════════════════════════════════════════════════

class TestCSVSave:
    def test_overwrite_csv(self, sample_csv):
        eio.save_onsets_to_excel(
            file_path=sample_csv,
            audio_filename="song1.wav",
            onset_times=[9.0, 10.0],
            filename_col="File Name",
            onset_col="Onsets",
        )
        reloaded = eio.load_onsets_for_file(
            sample_csv, "song1.wav", "File Name", "Onsets")
        assert len(reloaded) == 2

    def test_new_column_csv(self, sample_csv):
        eio.save_onsets_to_excel(
            file_path=sample_csv,
            audio_filename="song1.wav",
            onset_times=[9.0],
            filename_col="File Name",
            onset_col="Onsets",
            new_col_name="Onsets_Edited",
        )
        # Verify new column
        df = pd.read_csv(sample_csv)
        assert "Onsets_Edited" in df.columns
        # Original column unchanged
        original = eio.load_onsets_for_file(
            sample_csv, "song1.wav", "File Name", "Onsets")
        assert len(original) == 3


# ═══════════════════════════════════════════════════════════════════════════
# Backward compatibility — existing .txt functionality
# ═══════════════════════════════════════════════════════════════════════════

class TestBackwardCompatibility:
    """Ensure existing Audacity .txt file functionality still works."""

    def test_load_labels_still_works(self):
        from onset_editor import _load_labels, _save_labels
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                         delete=False) as f:
            f.write("0.123456\t0.123456\tOnsetR_1\n")
            f.write("1.234567\t1.234567\tOnsetR_2\n")
            path = f.name
        try:
            times = _load_labels(path)
            assert len(times) == 2
            assert abs(times[0] - 0.123456) < 1e-5
        finally:
            os.unlink(path)

    def test_save_labels_still_works(self):
        from onset_editor import _save_labels
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            path = f.name
        try:
            _save_labels(path, [0.5, 1.5, 2.5])
            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 3
            assert "OnsetR_1" in lines[0]
        finally:
            os.unlink(path)

    def test_find_label_file_still_works(self):
        from onset_editor import _find_label_file
        with tempfile.TemporaryDirectory() as d:
            audio = os.path.join(d, "song.wav")
            label = os.path.join(d, "song_labels.txt")
            open(audio, "w").close()
            open(label, "w").close()
            assert _find_label_file(audio) == label


# ═══════════════════════════════════════════════════════════════════════════
# Multi-file Excel support
# ═══════════════════════════════════════════════════════════════════════════

class TestMultiFileExcel:
    def test_load_multiple_files(self, sample_excel):
        """Each audio file gets its own onset times from the same Excel."""
        t1 = eio.load_onsets_for_file(
            sample_excel, "song1.wav",
            "File Name", "Exact Onset Times Used (s)", "File Summaries")
        t2 = eio.load_onsets_for_file(
            sample_excel, "song2.wav",
            "File Name", "Exact Onset Times Used (s)", "File Summaries")
        t3 = eio.load_onsets_for_file(
            sample_excel, "song3.wav",
            "File Name", "Exact Onset Times Used (s)", "File Summaries")
        assert len(t1) == 5
        assert len(t2) == 3
        assert len(t3) == 4

    def test_save_one_preserves_others(self, sample_excel):
        """Saving onsets for one file doesn't affect other files."""
        eio.save_onsets_to_excel(
            file_path=sample_excel,
            audio_filename="song2.wav",
            onset_times=[99.0],
            filename_col="File Name",
            onset_col="Exact Onset Times Used (s)",
            sheet_name="File Summaries",
        )
        t1 = eio.load_onsets_for_file(
            sample_excel, "song1.wav",
            "File Name", "Exact Onset Times Used (s)", "File Summaries")
        t3 = eio.load_onsets_for_file(
            sample_excel, "song3.wav",
            "File Name", "Exact Onset Times Used (s)", "File Summaries")
        assert len(t1) == 5  # unchanged
        assert len(t3) == 4  # unchanged


# ═══════════════════════════════════════════════════════════════════════════
#  Onset_Layer column (layer_name parameter)
# ═══════════════════════════════════════════════════════════════════════════

class TestLayerNameColumn:
    def test_layer_name_creates_column(self, sample_excel):
        """Passing layer_name creates an Onset_Layer column."""
        result = eio.save_onsets_to_excel(
            file_path=sample_excel,
            audio_filename="song1.wav",
            onset_times=[1.0, 2.0],
            filename_col="File Name",
            onset_col="Exact Onset Times Used (s)",
            sheet_name="File Summaries",
            layer_name="Drums",
        )
        df = pd.read_excel(sample_excel, sheet_name="File Summaries",
                           engine="openpyxl")
        assert "Onset_Layer" in df.columns
        row_idx = result["row_index"]
        assert df.at[row_idx, "Onset_Layer"] == "Drums"

    def test_layer_name_custom_col(self, sample_excel):
        """Custom layer_col_name is used when specified."""
        eio.save_onsets_to_excel(
            file_path=sample_excel,
            audio_filename="song1.wav",
            onset_times=[1.0],
            filename_col="File Name",
            onset_col="Exact Onset Times Used (s)",
            sheet_name="File Summaries",
            layer_name="Vocals",
            layer_col_name="Onset_Layer_2",
        )
        df = pd.read_excel(sample_excel, sheet_name="File Summaries",
                           engine="openpyxl")
        assert "Onset_Layer_2" in df.columns
        mask = df["File Name"].str.strip().str.lower() == "song1.wav"
        assert df.loc[mask, "Onset_Layer_2"].iloc[0] == "Vocals"

    def test_no_layer_name_no_column(self, sample_excel):
        """When layer_name is None, no Onset_Layer column is created."""
        eio.save_onsets_to_excel(
            file_path=sample_excel,
            audio_filename="song1.wav",
            onset_times=[1.0],
            filename_col="File Name",
            onset_col="Exact Onset Times Used (s)",
            sheet_name="File Summaries",
        )
        df = pd.read_excel(sample_excel, sheet_name="File Summaries",
                           engine="openpyxl")
        assert "Onset_Layer" not in df.columns

    def test_layer_name_csv(self, sample_csv):
        """Layer name column works with CSV files too."""
        eio.save_onsets_to_excel(
            file_path=sample_csv,
            audio_filename="song1.wav",
            onset_times=[1.0],
            filename_col="File Name",
            onset_col="Exact Onset Times Used (s)",
            layer_name="Buttress",
        )
        df = pd.read_csv(sample_csv)
        assert "Onset_Layer" in df.columns
        mask = df["File Name"].str.strip().str.lower() == "song1.wav"
        assert df.loc[mask, "Onset_Layer"].iloc[0] == "Buttress"


# ═══════════════════════════════════════════════════════════════════════════
# combine_onset_columns
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def multi_layer_excel(tmp_path):
    """Excel file with multiple onset layer columns."""
    data = {
        "File Name": ["song1.wav", "song2.wav"],
        "Exact Onset Times Used (s)": [
            "0.1, 0.5, 1.0",
            "0.2, 0.8",
        ],
        "Onset_Times_1": [
            "0.1, 0.5",
            "0.2",
        ],
        "Onset_Times_2": [
            "0.5, 1.0, 1.5",
            "0.8, 1.2",
        ],
    }
    df = pd.DataFrame(data)
    path = str(tmp_path / "layers.xlsx")
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="File Summaries", index=False)
    return path


class TestCombineOnsetColumns:
    def test_basic_combine(self, multi_layer_excel):
        result = eio.combine_onset_columns(
            file_path=multi_layer_excel,
            filename_col="File Name",
            source_columns=["Onset_Times_1", "Onset_Times_2"],
        )
        assert result["column"] == "Onset Times Used (s)_Combined"
        assert result["rows_updated"] == 2

        df = pd.read_excel(multi_layer_excel, engine="openpyxl")
        assert "Onset Times Used (s)_Combined" in df.columns
        combined_row1 = eio.parse_onset_string(
            str(df.loc[0, "Onset Times Used (s)_Combined"]))
        # Union of [0.1, 0.5] and [0.5, 1.0, 1.5] → [0.1, 0.5, 1.0, 1.5]
        assert len(combined_row1) == 4
        assert abs(combined_row1[0] - 0.1) < 0.01
        assert abs(combined_row1[3] - 1.5) < 0.01

    def test_custom_column_name(self, multi_layer_excel):
        result = eio.combine_onset_columns(
            file_path=multi_layer_excel,
            filename_col="File Name",
            source_columns=["Onset_Times_1", "Onset_Times_2"],
            combined_col_name="My Combined",
        )
        assert result["column"] == "My Combined"
        df = pd.read_excel(multi_layer_excel, engine="openpyxl")
        assert "My Combined" in df.columns

    def test_insert_before(self, multi_layer_excel):
        result = eio.combine_onset_columns(
            file_path=multi_layer_excel,
            filename_col="File Name",
            source_columns=["Onset_Times_1", "Onset_Times_2"],
            insert_before="Exact Onset Times Used (s)",
        )
        df = pd.read_excel(multi_layer_excel, engine="openpyxl")
        cols = list(df.columns)
        combined_pos = cols.index("Onset Times Used (s)_Combined")
        exact_pos = cols.index("Exact Onset Times Used (s)")
        assert combined_pos < exact_pos

    def test_deduplication(self, multi_layer_excel):
        """Overlapping onsets across layers are deduplicated."""
        result = eio.combine_onset_columns(
            file_path=multi_layer_excel,
            filename_col="File Name",
            source_columns=["Onset_Times_1", "Onset_Times_2"],
        )
        df = pd.read_excel(multi_layer_excel, engine="openpyxl")
        # song1: Onset_Times_1=[0.1, 0.5], Onset_Times_2=[0.5, 1.0, 1.5]
        #   → combined should have 4 unique onsets (0.5 deduped)
        times = eio.parse_onset_string(
            str(df.loc[0, "Onset Times Used (s)_Combined"]))
        assert len(times) == 4

    def test_missing_column_raises(self, multi_layer_excel):
        with pytest.raises(ValueError, match="not found"):
            eio.combine_onset_columns(
                file_path=multi_layer_excel,
                filename_col="File Name",
                source_columns=["Nonexistent_Column"],
            )

    def test_output_to_different_path(self, multi_layer_excel, tmp_path):
        out = str(tmp_path / "combined_output.xlsx")
        result = eio.combine_onset_columns(
            file_path=multi_layer_excel,
            filename_col="File Name",
            source_columns=["Onset_Times_1", "Onset_Times_2"],
            output_path=out,
        )
        assert result["path"] == out
        assert os.path.isfile(out)
        df = pd.read_excel(out, engine="openpyxl")
        assert "Onset Times Used (s)_Combined" in df.columns


# ═══════════════════════════════════════════════════════════════════════════
# Pipeline workbook rewrite / outside import helpers
# ═══════════════════════════════════════════════════════════════════════════

class TestPipelineWorkbookHelpers:
    def test_write_recording_to_workbook_updates_summary_and_preserves_other_sheets(self, pipeline_workbook):
        result = eio.write_recording_to_workbook(
            pipeline_workbook,
            "song1.wav",
            [0.0, 0.5, 1.0, 1.5],
            stable_tolerance=0.25,
        )

        assert result["updated"] == 1
        assert result["file_name"] == "song1.wav"
        assert result["onset_count"] == 4

        sheets = pd.read_excel(pipeline_workbook, sheet_name=None, engine="openpyxl")
        summary = sheets["File Summaries"]
        song1 = summary.loc[
            summary["File Name"].astype(str).str.strip().str.lower() == "song1.wav"
        ].iloc[0]
        assert song1["Group"] == "A"
        assert int(song1["Total Onsets Used"]) == 4
        assert int(song1["Stable Dyads Retained"]) == 1
        assert eio.parse_onset_string(str(song1["Exact Onset Times Used (s)"])) == [0.0, 0.5, 1.0, 1.5]

        raw_dyads = sheets["Dyadic Events (For Plots)"]
        stable_dyads = sheets["Dyadic Events (Stable Rhythms)"]
        assert len(raw_dyads.loc[raw_dyads["File Name"].astype(str).str.strip().str.lower() == "song1.wav"]) == 2
        assert len(raw_dyads.loc[raw_dyads["File Name"].astype(str).str.strip().str.lower() == "song2.wav"]) == 1
        assert len(stable_dyads.loc[stable_dyads["File Name"].astype(str).str.strip().str.lower() == "song1.wav"]) == 1
        assert len(stable_dyads.loc[stable_dyads["File Name"].astype(str).str.strip().str.lower() == "song2.wav"]) == 1
        assert sheets["Meta"].iloc[0]["Note"] == "preserve me"

    def test_import_matching_onsets_to_workbook_skips_existing_case_insensitively(self, pipeline_workbook, tmp_path):
        source_path = tmp_path / "outside_onsets.csv"
        pd.DataFrame({
            "Audio": ["song1.wav", "song2", "other.wav", "SONG1.WAV"],
            "Outside Onsets": [
                "0.000000, 0.300000, 0.600000",
                "0.200000, 0.700000, 1.200000",
                "0.100000, 0.200000",
                "0.000000, 0.900000",
            ],
        }).to_csv(source_path, index=False)

        result = eio.import_matching_onsets_to_workbook(
            str(source_path),
            pipeline_workbook,
            ["song1.wav", "song2.wav"],
            source_filename_col="Audio",
            source_onset_col="Outside Onsets",
            overwrite_existing=False,
        )

        assert result["matched"] == 2
        assert result["imported"] == 1
        assert result["skipped_existing"] == ["song1.wav"]
        assert result["overwritten_files"] == []
        assert result["unmatched_source_names"] == ["other.wav"]
        assert len(result["duplicate_targets"]) == 1

        summary = pd.read_excel(pipeline_workbook, sheet_name="File Summaries", engine="openpyxl")
        song1 = summary.loc[
            summary["File Name"].astype(str).str.strip().str.lower() == "song1.wav"
        ].iloc[0]
        song2 = summary.loc[
            summary["File Name"].astype(str).str.strip().str.lower() == "song2.wav"
        ].iloc[0]
        assert eio.parse_onset_string(str(song1["Exact Onset Times Used (s)"])) == [0.1, 0.6, 1.1]
        assert eio.parse_onset_string(str(song2["Exact Onset Times Used (s)"])) == [0.2, 0.7, 1.2]
