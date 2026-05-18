from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    from form_widgets import FilePicker, FolderPicker, _add_row, _make_auto_set
except ImportError:
    from GUI.form_widgets import FilePicker, FolderPicker, _add_row, _make_auto_set


class BeatTempoPanel(QScrollArea):
    """Settings panel for the Beat and Tempo step."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setSpacing(14)
        lay.setContentsMargins(16, 16, 16, 16)

        grp = QGroupBox("Input / Output")
        g = QVBoxLayout(grp)

        self.audio_folder = FolderPicker("")
        self.audio_folder.line_edit.setPlaceholderText(
            "Audio folder to analyse (same folder as Onset Finder input)")
        _add_row(g, "Input audio folder", self.audio_folder,
                 "Folder of audio files to analyse for beat and tempo.",
                 extended_desc="Should point to the same cleaned audio folder used by "
                 "the Onset Finder (Step 3).  All .wav/.mp3/.flac files in this folder "
                 "are processed.",
                 label_width=140)
        self._input_auto_cb, self._input_auto_desc = _make_auto_set(
            self.audio_folder, g,
            "↳ Auto: Set to the <b>Input folder</b> from Step 3 (Onset Finder)",
            step_name="Beat & Tempo", io_type="input",
            auto_config={"source_step": "Onset Finder", "source_io": "input",
                         "suffix": "", "use_dirname": False,
                         "use_basename": False})

        self.output_excel = FilePicker("", "Excel files (*.xlsx *.xls)")
        self.output_excel.line_edit.setPlaceholderText(
            "Excel file path (auto-set from Onset Finder output)")
        _add_row(g, "Output Excel file", self.output_excel,
                 "Path for the Beat and Tempo output Excel workbook (.xlsx).",
                 extended_desc="Results are added as a separate sheet within the Onset "
                 "Finder's output Excel workbook.  Data is added on a per-cell basis (only "
                 "rows for processed files are updated).",
                 label_width=140)
        self._output_auto_cb, self._output_auto_desc = _make_auto_set(
            self.output_excel, g,
            "↳ Auto: Set to the <b>Output Excel</b> from Step 3 (Onset Finder)",
            step_name="Beat & Tempo", io_type="output",
            auto_config={"source_step": "Onset Finder", "source_io": "output",
                         "suffix": "", "use_dirname": False,
                         "use_basename": False})
        self._output_auto_cb.stateChanged.connect(self._on_output_auto_toggled)

        self.output_sheet_name = QLineEdit("Beat-Tempo")
        self.output_sheet_name.setPlaceholderText("Sheet name for beat/tempo data")
        _add_row(g, "Output sheet name", self.output_sheet_name,
                 "Name of the sheet within the Excel file for beat and tempo data.",
                 extended_desc="If this sheet does not exist, it will be created.  "
                 "Only data rows for files in this batch are updated; other rows "
                 "are preserved.",
                 label_width=140)

        lay.addWidget(grp)

        grp = QGroupBox("Beat Tracking  (librosa.beat.beat_track)")
        g = QVBoxLayout(grp)

        self.beat_hop_length = QLineEdit("512")
        _add_row(g, "Hop length (frames)", self.beat_hop_length,
                 "FFT hop length used for onset-strength envelope computation.",
                 extended_desc="Smaller values give finer time resolution but increase "
                 "processing time.  512 is a safe default for most recordings.",
                 label_width=200)

        self.beat_start_bpm = QLineEdit("120.0")
        _add_row(g, "Start BPM", self.beat_start_bpm,
                 "Prior tempo estimate for the beat tracker (BPM).",
                 extended_desc="The tracker uses this as an initialisation hint.  "
                 "If your recordings have a strongly different tempo range, adjust "
                 "this value accordingly.",
                 label_width=200)

        self.beat_tightness = QLineEdit("100.0")
        _add_row(g, "Tightness", self.beat_tightness,
                 "How tightly beats cluster around the estimated tempo.",
                 extended_desc="Higher values force beats closer to the global tempo "
                 "estimate.  Lower values allow more local variability.  100 is the "
                 "librosa default.",
                 label_width=200)

        self.beat_trim = QCheckBox("Trim weak boundary beats")
        self.beat_trim.setChecked(True)
        self.beat_trim.setToolTip(
            "When checked, beats at the start and end of the file with weak onset "
            "strength are discarded.  Recommended for sparse bioacoustic recordings.")
        g.addWidget(self.beat_trim)

        self.beat_bpm_override = QLineEdit("0")
        _add_row(g, "BPM override (0 = auto)", self.beat_bpm_override,
                 "Fix the tempo to this BPM instead of estimating it automatically.",
                 extended_desc="Set to 0 (the default) to let librosa estimate tempo "
                 "from the recording.  Set to a positive value to force a specific "
                 "tempo (useful when the species has a known drumming rate).",
                 label_width=200)

        lay.addWidget(grp)

        grp = QGroupBox("Predominant Local Pulse  (librosa.beat.plp)")
        g = QVBoxLayout(grp)

        self.plp_hop_length = QLineEdit("512")
        _add_row(g, "Hop length (frames)", self.plp_hop_length,
                 "Hop length for the PLP analysis window.",
                 label_width=200)

        self.plp_win_length = QLineEdit("384")
        _add_row(g, "Window length (frames)", self.plp_win_length,
                 "Length of the periodicity analysis window in frames.",
                 extended_desc="384 frames at 22 050 Hz / 512 hop ≈ 8 seconds.  "
                 "Longer windows capture slower rhythms more reliably.",
                 label_width=200)

        self.plp_tempo_min = QLineEdit("30.0")
        _add_row(g, "Min tempo (BPM)", self.plp_tempo_min,
                 "Minimum tempo considered in the PLP periodicity search.",
                 label_width=200)

        self.plp_tempo_max = QLineEdit("300.0")
        _add_row(g, "Max tempo (BPM)", self.plp_tempo_max,
                 "Maximum tempo considered in the PLP periodicity search.",
                 label_width=200)

        self.derive_plp_peaks = QCheckBox("Derive PLP beat peaks")
        self.derive_plp_peaks.setChecked(True)
        self.derive_plp_peaks.setToolTip(
            "When checked, local maxima of the PLP pulse curve are detected and "
            "exported as PLP Peak Times in the output Excel.")
        g.addWidget(self.derive_plp_peaks)

        self.plp_peak_spacing = QLineEdit("100")
        _add_row(g, "Peak min spacing (ms)", self.plp_peak_spacing,
                 "Minimum gap between consecutive PLP peak candidates (milliseconds).",
                 extended_desc="Prevents neighbouring samples from both being reported "
                 "as peaks.  Increase this for recordings with slower inter-beat "
                 "intervals.",
                 label_width=200)

        self.export_pulse_detail = QCheckBox("Export per-frame pulse detail sheet")
        self.export_pulse_detail.setChecked(False)
        self.export_pulse_detail.setToolTip(
            "When checked, every PLP frame is written to a 'Tempo Pulse Detail' sheet.  "
            "This can produce large files for long recordings.")
        g.addWidget(self.export_pulse_detail)

        lay.addWidget(grp)

        lay.addStretch()
        self.setWidget(content)

    def _on_output_auto_toggled(self, state):
        self._output_auto_desc.setVisible(bool(state))

    def get_values(self) -> dict:
        return {
            "audio_folder": self.audio_folder.text(),
            "output_excel_path": self.output_excel.text(),
            "BEAT_HOP_LENGTH": int(self.beat_hop_length.text() or 512),
            "BEAT_START_BPM": float(self.beat_start_bpm.text() or 120.0),
            "BEAT_TIGHTNESS": float(self.beat_tightness.text() or 100.0),
            "BEAT_TRIM": self.beat_trim.isChecked(),
            "BEAT_BPM_OVERRIDE": float(self.beat_bpm_override.text() or 0),
            "PLP_HOP_LENGTH": int(self.plp_hop_length.text() or 512),
            "PLP_WIN_LENGTH": int(self.plp_win_length.text() or 384),
            "PLP_TEMPO_MIN": float(self.plp_tempo_min.text() or 30.0),
            "PLP_TEMPO_MAX": float(self.plp_tempo_max.text() or 300.0),
            "DERIVE_PLP_PEAKS": self.derive_plp_peaks.isChecked(),
            "PLP_PEAK_MIN_SPACING_MS": int(self.plp_peak_spacing.text() or 100),
            "EXPORT_PULSE_DETAIL": self.export_pulse_detail.isChecked(),
        }

    def set_values(self, d: dict):
        if "audio_folder" in d:
            self.audio_folder.setText(d["audio_folder"])
        if "output_excel_path" in d:
            self.output_excel.setText(d["output_excel_path"])
        if "output_sheet_name" in d:
            self.output_sheet_name.setText(d["output_sheet_name"])
        if "BEAT_HOP_LENGTH" in d:
            self.beat_hop_length.setText(str(d["BEAT_HOP_LENGTH"]))
        if "BEAT_START_BPM" in d:
            self.beat_start_bpm.setText(str(d["BEAT_START_BPM"]))
        if "BEAT_TIGHTNESS" in d:
            self.beat_tightness.setText(str(d["BEAT_TIGHTNESS"]))
        if "BEAT_TRIM" in d:
            self.beat_trim.setChecked(bool(d["BEAT_TRIM"]))
        if "BEAT_BPM_OVERRIDE" in d:
            self.beat_bpm_override.setText(str(d["BEAT_BPM_OVERRIDE"]))
        if "PLP_HOP_LENGTH" in d:
            self.plp_hop_length.setText(str(d["PLP_HOP_LENGTH"]))
        if "PLP_WIN_LENGTH" in d:
            self.plp_win_length.setText(str(d["PLP_WIN_LENGTH"]))
        if "PLP_TEMPO_MIN" in d:
            self.plp_tempo_min.setText(str(d["PLP_TEMPO_MIN"]))
        if "PLP_TEMPO_MAX" in d:
            self.plp_tempo_max.setText(str(d["PLP_TEMPO_MAX"]))
        if "DERIVE_PLP_PEAKS" in d:
            self.derive_plp_peaks.setChecked(bool(d["DERIVE_PLP_PEAKS"]))
        if "PLP_PEAK_MIN_SPACING_MS" in d:
            self.plp_peak_spacing.setText(str(d["PLP_PEAK_MIN_SPACING_MS"]))
        if "EXPORT_PULSE_DETAIL" in d:
            self.export_pulse_detail.setChecked(bool(d["EXPORT_PULSE_DETAIL"]))

    def save_settings_if_enabled(self):
        return ""