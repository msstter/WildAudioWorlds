from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    from form_widgets import (
        FilePicker,
        FolderPicker,
        PresetReasonLabel,
        _CheckableAudioFileCombo,
        _CheckableLayerCombo,
        _ALL_IO_SUMMARIES,
        _add_checkbox,
        _add_row,
        _make_auto_set,
        _resolve_auto_config,
        get_form_widget_palette,
    )
except ImportError:
    from GUI.form_widgets import (
        FilePicker,
        FolderPicker,
        PresetReasonLabel,
        _CheckableAudioFileCombo,
        _CheckableLayerCombo,
        _ALL_IO_SUMMARIES,
        _add_checkbox,
        _add_row,
        _make_auto_set,
        _resolve_auto_config,
        get_form_widget_palette,
    )

try:
    from panel_settings_helpers import (
        _build_settings_preset_section,
        _export_settings_for,
        _import_settings_for,
        _on_saved_settings_selected,
        _save_settings_if_enabled,
    )
except ImportError:
    from GUI.panel_settings_helpers import (
        _build_settings_preset_section,
        _export_settings_for,
        _import_settings_for,
        _on_saved_settings_selected,
        _save_settings_if_enabled,
    )

try:
    from per_file_settings_support import (
        _MUTER_PREFIX,
        _ONSET_KEY_ORDER,
        _mark_perfile_setting,
        PerFileOverridesBox,
        PerFileToggleIndicator,
    )
except ImportError:
    from GUI.per_file_settings_support import (
        _MUTER_PREFIX,
        _ONSET_KEY_ORDER,
        _mark_perfile_setting,
        PerFileOverridesBox,
        PerFileToggleIndicator,
    )

try:
    from panel_presets import PRESETS, _ONSET_PRESET_REASONS
except ImportError:
    from GUI.panel_presets import PRESETS, _ONSET_PRESET_REASONS


_BORDER = "#3a3a50"
_TEXT_DIM = "#8888a0"


def _sync_theme_aliases() -> None:
    global _BORDER, _TEXT_DIM
    palette = get_form_widget_palette()
    _BORDER = palette.border
    _TEXT_DIM = palette.text_dim


def _to_int(text, default):
    try:
        return int(text)
    except (ValueError, TypeError):
        return default


def _to_float(text, default):
    try:
        return float(text)
    except (ValueError, TypeError):
        return default


class ExtractorPanel(QScrollArea):
    def __init__(self, parent=None):
        _sync_theme_aliases()
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._applying_preset = False
        self._preset_reason_labels = {}
        self._onset_presets = PRESETS
        self._onset_preset_reasons = _ONSET_PRESET_REASONS
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setSpacing(14)
        lay.setContentsMargins(16, 16, 16, 16)

        self._per_file_overrides = PerFileOverridesBox(
            section_key="onset_recommendations",
            panel_label="Onset Finder",
            key_filter=lambda k: not k.startswith(_MUTER_PREFIX),
            key_order_list=_ONSET_KEY_ORDER,
            parent=content,
        )
        lay.addWidget(self._per_file_overrides)

        grp = QGroupBox("Input / Output")
        g = QVBoxLayout(grp)

        self.audio_folder = FolderPicker("")
        self.audio_folder.line_edit.setPlaceholderText(
            "Cleaned audio folder (from Audio Editor output)")
        _add_row(g, "Input audio folder", self.audio_folder,
                 "Folder of pre-processed (muted) audio to analyse.",
                 extended_desc="Should point to the Audio Editor's output folder (or any folder of .wav/.mp3/.mp4 files you want to extract rhythms from).",
                 label_width=140)
        self._input_auto_cb, self._input_auto_desc = _make_auto_set(
            self.audio_folder, g,
            "↳ Auto: Set to the <b>Output folder</b> from Step 2 (Audio Editor)",
            step_name="Onset Finder", io_type="input",
            auto_config={"source_step": "Audio Editor", "source_io": "output",
                         "suffix": "", "use_dirname": False,
                         "use_basename": False})
        self.specify_files_cb = QCheckBox("Specify files:")
        self.specify_files_cb.setChecked(False)
        self.specify_files_cb.setToolTip(
            "When off, all supported audio files in the input folder are analysed. When on, only the checked files are included.")
        self.selected_files_combo = _CheckableAudioFileCombo()
        self.selected_files_combo.setEnabled(False)
        self.selected_files_combo.setToolTip(
            "Choose which cleaned audio files should be sent to the Onset Finder.")
        files_row = QHBoxLayout()
        files_row.setSpacing(12)
        files_spacer = QLabel("")
        files_spacer.setFixedWidth(140)
        files_row.addWidget(files_spacer)
        files_row.addWidget(self.specify_files_cb)
        files_row.addWidget(self.selected_files_combo, stretch=1)
        g.addLayout(files_row)

        self.specify_layers_cb = QCheckBox("Specify layers:")
        self.specify_layers_cb.setChecked(False)
        self.specify_layers_cb.setToolTip(
            "When on, only the checked onset layers are processed per file.\nLayers are discovered from *_OnsetLayers/ folders saved by the Onset Editor.")
        self.selected_layers_combo = _CheckableLayerCombo()
        self.selected_layers_combo.setEnabled(False)
        self.selected_layers_combo.setToolTip(
            "Choose which saved onset layers should be used for detection.\nEach layer can have its own focus regions and detection settings.")
        layers_row = QHBoxLayout()
        layers_row.setSpacing(12)
        layers_spacer = QLabel("")
        layers_spacer.setFixedWidth(140)
        layers_row.addWidget(layers_spacer)
        layers_row.addWidget(self.specify_layers_cb)
        layers_row.addWidget(self.selected_layers_combo, stretch=1)
        g.addLayout(layers_row)

        self.output_excel = FilePicker(
            "", "Excel files (*.xlsx *.xls)")
        self.output_excel.line_edit.setPlaceholderText(
            "Output Excel file path (auto-set from input)")
        _add_row(g, "Output Excel file", self.output_excel,
                 "Path for the output Excel workbook (.xlsx).",
                 extended_desc="The 3-sheet workbook (File Summaries, Dyadic Events, Stable Dyadic Events) is written here. Steps 3 and 4 read from this file.",
                 label_width=140)
        self._output_auto_cb, self._output_auto_desc = _make_auto_set(
            self.output_excel, g,
            "↳ Auto: Excel placed in '<i>{input}/data/AudioData_OnsetFinder.xlsx</i>'",
            step_name="Onset Finder", io_type="output",
            auto_config={"source_step": "(this step)", "source_io": "input",
                         "suffix": "data/AudioData_OnsetFinder.xlsx",
                         "use_dirname": False, "use_basename": False})
        self._output_auto_cb.stateChanged.connect(self._on_output_auto_toggled)

        self._io_summary = QLabel()
        self._io_summary.setWordWrap(True)
        self._io_summary.setStyleSheet(
            f"color: {_TEXT_DIM}; background: transparent; font-size: 11px; padding: 4px 6px; border: 1px solid {_BORDER}; border-radius: 4px;"
        )
        g.addWidget(self._io_summary)
        _ALL_IO_SUMMARIES.append(self._io_summary)
        self._io_summary.hide()

        self.add_column_comments = QCheckBox("Add explanatory comments to Excel column headers")
        self.add_column_comments.setChecked(True)
        _add_checkbox(g, self.add_column_comments,
            "Attach a comment/note to each column header in the output Excel file explaining what it represents.",
            "When enabled, every column header cell in each sheet gets an Excel comment (visible on hover) with a plain-English explanation of what that column contains and how to interpret its values. Useful for collaborators or reviewers who haven't used this pipeline before.")

        self.add_formula_sheet = QCheckBox("Add sheet of formulas used")
        self.add_formula_sheet.setChecked(True)
        _add_checkbox(g, self.add_formula_sheet,
            "Append a reference sheet listing the Python and Excel formulas used for every column.",
            "When enabled, an extra sheet called 'Formulas Used' is added to the Excel output. For each column in the File Summaries and Dyadic Events sheets, it shows: (1) the Python code/formula used to compute the value, and (2) the equivalent Excel formula you could use to verify the result yourself.")

        lay.addWidget(grp)

        _build_settings_preset_section(
            self, lay, "Onset Finder", self.audio_folder,
            presets_dict=self._onset_presets, preset_combo_attr="preset")
        self._import_settings_btn.clicked.connect(
            lambda: _import_settings_for(self, "Onset Finder"))
        self._export_settings_btn.clicked.connect(
            lambda: _export_settings_for(self, "Onset Finder"))
        self._saved_settings_combo.currentTextChanged.connect(
            lambda name: _on_saved_settings_selected(self, "Onset Finder", name))
        self._save_preset_btn.clicked.connect(self._save_as_preset)
        self.preset.currentTextChanged.connect(self._on_preset_changed)

        grp = QGroupBox("General")
        g = QVBoxLayout(grp)

        self.engine = QComboBox()
        self.engine.addItems(["standard", "thebeat"])
        _add_row(g, "Extractor engine", self.engine,
                 "standard = full-featured (onset clustering, stable-rhythm, spectrograms). thebeat = lightweight alternative using the thebeat package.",
                 extended_desc="'standard' is the primary engine with all features: 6 onset detection algorithms, sample-level refinement, clustering, amplitude gating, stable-rhythm filtering, spectrograms, and Audacity labels. 'thebeat' uses the thebeat.Sequence class for IOI computation but now also supports all the same features. Choose thebeat for compatibility with thebeat-based downstream analysis.")

        lay.addWidget(grp)

        grp = QGroupBox("Onset Detection Core")
        g = QVBoxLayout(grp)

        self.onset_method = QComboBox()
        self.onset_method.addItems([
            "adaptive_hp", "librosa", "moving_median",
            "superflux", "cfar", "per_band",
            "syllable_nuclei", "whisper_words", "whisperx_phonemes",
            "madmom_beats",
        ])
        self.onset_method.currentTextChanged.connect(self._update_method_groups)
        _add_row(g, "Onset method", self.onset_method,
                 "Which onset detection algorithm to use. adaptive_hp = robust to noise (default). librosa = simple spectral flux. syllable_nuclei = speech syllables (Praat). whisper_words = word onsets (Whisper ASR). See docs for full comparison.",
                 extended_desc="adaptive_hp: Hodrick-Prescott trend filter + dynamic threshold — most robust to noise, best default. librosa: standard spectral-flux via librosa.onset.onset_detect. moving_median: local median baseline subtraction. superflux: spectral-flux with max-filtering for vibrato tolerance. cfar: radar-inspired Constant False-Alarm Rate detector. per_band: independent detection across frequency bands, then merging. syllable_nuclei: Praat-based syllable nucleus detection (requires parselmouth). whisper_words: OpenAI Whisper word-level timestamps (requires openai-whisper).")
        prl = PresetReasonLabel("ONSET_METHOD")
        g.addWidget(prl)
        self._preset_reason_labels["ONSET_METHOD"] = prl

        self.onset_delta = QLineEdit("0.10")
        _add_row(g, "Onset delta", self.onset_delta,
                 "Peak-picking sensitivity (used by librosa and superflux). Higher = fewer onsets. 0.03-0.15.",
                 extended_desc="Controls the minimum rise in the spectral flux onset-strength envelope needed to register a peak. Used by librosa and superflux methods. Lower values (0.03) catch quiet onsets but increase false positives; higher values (0.12-0.15) are stricter. Has no effect on adaptive_hp, moving_median, cfar, or per_band methods.")
        prl = PresetReasonLabel("ONSET_DELTA")
        g.addWidget(prl)
        self._preset_reason_labels["ONSET_DELTA"] = prl

        self.onset_hop = QLineEdit("256")
        _add_row(g, "Hop length (samples)", self.onset_hop,
                 "Spectrogram hop length (samples). 128 = fine, 256 = balanced (default), 512 = coarse. Used by librosa and superflux.",
                 extended_desc="Determines the time resolution of the internal spectrogram. At 44.1 kHz: 128 samples ~= 2.9 ms, 256 ~= 5.8 ms, 512 ~= 11.6 ms. Smaller hops give finer onset placement but increase processing time. Only affects librosa and superflux methods; other methods use their own windowing.")
        prl = PresetReasonLabel("ONSET_HOP_LENGTH")
        g.addWidget(prl)
        self._preset_reason_labels["ONSET_HOP_LENGTH"] = prl

        self.onset_backtrack = QCheckBox("Backtrack onsets")
        self.onset_backtrack.setChecked(False)
        _add_checkbox(g, self.onset_backtrack,
            "Roll onsets backward to nearest energy minimum. Can overshoot on noisy recordings. Usually leave off.",
            "After detecting each onset, searches backward for the nearest local energy minimum and repositions the onset there. Theoretically gives a more accurate attack start, but in practice often overshoots on noisy field recordings, pulling onsets into silence. Leave OFF unless using very clean studio recordings.")
        prl = PresetReasonLabel("ONSET_BACKTRACK")
        g.addWidget(prl)
        self._preset_reason_labels["ONSET_BACKTRACK"] = prl

        self.min_ioi = QLineEdit("30")
        _add_row(g, "Min inter-onset (ms)", self.min_ioi,
                 "Minimum gap (ms) between onsets. Closer onsets are dropped. 10 = insects, 12 = birdsong, 30 = percussion, 40 = primate.",
                 extended_desc="After detection, any onset that falls within this many milliseconds of the previous onset is removed. Acts as a 'refractory period'. Set based on the fastest expected inter-event interval in your target species. Too low = spurious doubles survive. Too high = genuine rapid events are lost.")
        prl = PresetReasonLabel("MIN_INTER_ONSET_MS")
        g.addWidget(prl)
        self._preset_reason_labels["MIN_INTER_ONSET_MS"] = prl

        lay.addWidget(grp)

        grp = QGroupBox("Sample-Level Refinement")
        g = QVBoxLayout(grp)

        self.refine_enabled = QCheckBox("Enable refinement")
        self.refine_enabled.setChecked(True)
        _add_checkbox(g, self.refine_enabled,
            "Refine each coarse onset to sub-millisecond precision (~0.023 ms at 44.1 kHz) using the Hilbert envelope.",
            "After coarse onset detection (frame-level), searches a small window around each onset for the peak of the analytic signal (Hilbert) envelope, giving sample-level accuracy (~0.023 ms at 44.1 kHz). Critical for precise rhythm timing. Window size and energy gate are controlled below. Recommended ON.")
        prl = PresetReasonLabel("ONSET_REFINE_ENABLED")
        g.addWidget(prl)
        self._preset_reason_labels["ONSET_REFINE_ENABLED"] = prl

        self.refine_window = QLineEdit("10")
        _add_row(g, "Refine window (ms)", self.refine_window,
                 "Half-width (ms) of the search window for refinement. 5 = narrow, 10 = default, 20 = wide.",
                 extended_desc="Sets the half-width of the window searched around each coarse onset when looking for the Hilbert envelope peak. A 10 ms window searches +/-10 ms (20 ms total). Narrower windows are faster and avoid jumping to nearby events; wider windows help when coarse detection is imprecise.")
        prl = PresetReasonLabel("ONSET_REFINE_WINDOW_MS")
        g.addWidget(prl)
        self._preset_reason_labels["ONSET_REFINE_WINDOW_MS"] = prl

        self.refine_energy_gate = QLineEdit("0.0")
        _add_row(g, "Refine energy gate", self.refine_energy_gate,
                 "Energy threshold (0-1) for refinement. Below this fraction of peak envelope, onsets keep coarse timing. 0 = disabled.",
                 extended_desc="If the Hilbert envelope peak found during refinement is below this fraction of the file's maximum envelope, the refined position is discarded and the original coarse onset time is kept. Prevents refinement from snapping to noise in quiet passages. 0 = always accept refined position.")
        prl = PresetReasonLabel("ONSET_REFINE_ENERGY_GATE")
        g.addWidget(prl)
        self._preset_reason_labels["ONSET_REFINE_ENERGY_GATE"] = prl

        lay.addWidget(grp)

        grp = QGroupBox("Onset Sharpness Filter")
        g = QVBoxLayout(grp)

        self.sharpness_gate = QLineEdit("0.0")
        _add_row(g, "Onset sharpness gate", self.sharpness_gate,
                 "Discard onsets whose attack slope (Hilbert envelope derivative) is below this fraction (0-1) of the steepest attack. 0 = disabled.",
                 extended_desc="Measures how sharply each onset rises by computing the peak derivative of the Hilbert analytic envelope in a window around it. Onsets with slopes below this fraction of the file's sharpest onset are discarded. Useful for filtering gradual amplitude changes that are not true percussive events. 0.0 = disabled, 0.05-0.15 = moderate, 0.3+ = aggressive.")
        prl = PresetReasonLabel("ONSET_SHARPNESS_GATE")
        g.addWidget(prl)
        self._preset_reason_labels["ONSET_SHARPNESS_GATE"] = prl

        self.sharpness_window = QLineEdit("20")
        _add_row(g, "Sharpness window (ms)", self.sharpness_window,
                 "Window (ms) around each onset for measuring attack slope.",
                 extended_desc="Half-width of the window around each onset used to compute the Hilbert envelope derivative for the sharpness gate. Larger windows capture slower attacks; smaller windows focus on the immediate transient. 10-20 ms works for most percussive signals; increase to 30-50 ms for slower calls.")
        prl = PresetReasonLabel("ONSET_SHARPNESS_WINDOW_MS")
        g.addWidget(prl)
        self._preset_reason_labels["ONSET_SHARPNESS_WINDOW_MS"] = prl

        self.broadband_min_bands = QLineEdit("0")
        _add_row(g, "Broadband min bands", self.broadband_min_bands,
                 "Minimum number of frequency bands that must be active at an onset. 0 = disabled.",
                 extended_desc="The spectrum is divided into N equal-width bands. At each onset, bands whose energy exceeds the threshold fraction of that band's peak energy across the file are counted as 'active'. Onsets with fewer active bands than this value are discarded. Real percussion hits produce broadband energy (vertical stripes on the spectrogram) while noise artifacts tend to activate only one or two bands.")
        prl = PresetReasonLabel("ONSET_BROADBAND_MIN_BANDS")
        g.addWidget(prl)
        self._preset_reason_labels["ONSET_BROADBAND_MIN_BANDS"] = prl

        self.broadband_n_bands = QLineEdit("6")
        _add_row(g, "Broadband N bands", self.broadband_n_bands,
                 "Number of frequency bands to divide the spectrum into (default: 6).",
                 extended_desc="Controls the granularity of the broadband check. More bands means each band spans a narrower frequency range. 4-8 bands works well for percussion; increase for finer spectral discrimination.")
        prl = PresetReasonLabel("ONSET_BROADBAND_N_BANDS")
        g.addWidget(prl)
        self._preset_reason_labels["ONSET_BROADBAND_N_BANDS"] = prl

        self.broadband_threshold = QLineEdit("0.15")
        _add_row(g, "Broadband threshold", self.broadband_threshold,
                 "Fraction (0-1) of band peak energy required to count a band as active.",
                 extended_desc="A band is 'active' at an onset time if its STFT energy exceeds this fraction of that band's maximum energy across the file. Lower values are more permissive (more bands counted as active); higher values are stricter. 0.10-0.20 is typical for percussion.")
        prl = PresetReasonLabel("ONSET_BROADBAND_THRESHOLD")
        g.addWidget(prl)
        self._preset_reason_labels["ONSET_BROADBAND_THRESHOLD"] = prl

        lay.addWidget(grp)

        grp = QGroupBox("Output & Export")
        g = QVBoxLayout(grp)

        self.create_spectrograms = QCheckBox("Create spectrogram of onsets")
        self.create_spectrograms.setChecked(True)
        _add_checkbox(g, self.create_spectrograms,
            "Generate PNG spectrogram images with onset markers for visual review.",
            "Saves a mel-scaled spectrogram PNG for each audio file with vertical lines at detected onsets. Useful for visually verifying that onsets align with percussive events. Files are written alongside the input audio. Adds ~0.5 s per file.")

        self.spectrogram_chunk_enabled = QCheckBox("Split spectrograms into timed chunks")
        self.spectrogram_chunk_enabled.setChecked(False)
        _add_checkbox(g, self.spectrogram_chunk_enabled,
            "Split each spectrogram into sequential images of a fixed duration.",
            "For long recordings, a single spectrogram image makes it hard to see where onsets land. When enabled, the spectrogram is split into consecutive images of the duration below (e.g. 30 s each), saved as FileName_1.png, FileName_2.png, etc. If the recording is shorter than the chunk duration, a single image is produced at the recording's full length.")

        self.spectrogram_chunk_seconds = QLineEdit("30")
        _add_row(g, "Chunk duration (s)", self.spectrogram_chunk_seconds,
                 "Duration in seconds for each spectrogram chunk image.",
                 extended_desc="Each spectrogram image will cover this many seconds of audio. The final chunk uses whatever time remains, even if shorter than this value. Only used when 'Split spectrograms into timed chunks' is enabled.")

        self.create_labels = QCheckBox("Create Audacity labels")
        self.create_labels.setChecked(True)
        _add_checkbox(g, self.create_labels,
            "Export .txt label files importable into Audacity for manual onset auditing.",
            "Writes tab-separated label files that Audacity can import via File -> Import -> Labels. Each line contains onset-time, end-time, and a label. Lets you listen to each detected onset in context and manually verify accuracy.")

        self.cluster_onsets = QCheckBox("Cluster overlapping onsets")
        self.cluster_onsets.setChecked(True)
        _add_checkbox(g, self.cluster_onsets,
            "Merge onsets occurring within the cluster window into a single averaged onset.",
            "When multiple onset detections fire within a short window (e.g. from spectral leakage), they are averaged into a single representative onset. The window size is set by Cluster window (ms) below. Recommended ON to avoid inflated onset counts.")

        self.cluster_window = QLineEdit("25")
        _add_row(g, "Cluster window (ms)", self.cluster_window,
                 "Window (ms) for merging nearby onsets. Onsets within this distance are averaged into one.",
                 extended_desc="When two or more onsets fall within this time window, they are merged into a single onset at their mean time. Prevents double-counting from spectral artifacts. 25 ms works well for percussion; use 15 ms for fast birdsong trills; increase to 40 ms for slow primate drumming.")
        prl = PresetReasonLabel("ONSET_CLUSTER_WINDOW_MS")
        g.addWidget(prl)
        self._preset_reason_labels["ONSET_CLUSTER_WINDOW_MS"] = prl

        self.filter_stable = QCheckBox("Filter stable rhythms")
        self.filter_stable.setChecked(True)
        _add_checkbox(g, self.filter_stable,
            "Export a separate Excel sheet and plot set containing only stable (consistent) rhythmic sequences.",
            "Identifies consecutive inter-onset intervals that are close in duration (within the Stable rhythm tolerance) and flags them as 'stable dyads'. A separate Excel sheet, raster plot, and histogram are generated for stable rhythms only. Essential for cross-species comparisons of isochronous timing.")

        self.stable_tolerance = QLineEdit("0.25")
        _add_row(g, "Stable rhythm tolerance", self.stable_tolerance,
                 "How similar consecutive intervals must be (0-1, fraction) to count as a stable rhythm. Lower = stricter.",
                 extended_desc="Two consecutive IOIs are flagged as a 'stable dyad' if their ratio difference is within this tolerance (e.g. 0.25 means IOIs within 25% of each other). 0.15 = very strict (isochronous only), 0.25 = default, 0.35 = permissive (captures more variable rhythms). Results go to a separate 'stable' Excel sheet and plot subfolder.")
        prl = PresetReasonLabel("STABLE_RHYTHM_TOLERANCE")
        g.addWidget(prl)
        self._preset_reason_labels["STABLE_RHYTHM_TOLERANCE"] = prl

        lay.addWidget(grp)

        grp = QGroupBox("Noise-Handling Fallbacks (normally off)")
        g = QVBoxLayout(grp)

        self.apply_highpass = QCheckBox("Apply high-pass filter")
        self.apply_highpass.setChecked(False)
        _add_checkbox(g, self.apply_highpass,
            "Apply a high-pass filter inside the extractor. Normally off because the muter handles this. Enable only if running on raw audio.",
            "Applies a Butterworth high-pass filter before onset detection to remove low-frequency rumble (wind, traffic). Redundant when the Audio Editor already high-passes; enable only when running the extractor directly on raw/unmuted audio files. Cutoff is controlled by High-pass cutoff below.")

        self.highpass_cutoff = QLineEdit("200")
        _add_row(g, "High-pass cutoff (Hz)", self.highpass_cutoff,
                 "Cutoff frequency (Hz) for the extractor's built-in high-pass filter.",
                 extended_desc="Frequencies below this value are attenuated by the extractor's built-in Butterworth high-pass filter. Only active when 'Apply high-pass filter' is enabled. 200 Hz removes most wind and traffic rumble. Use higher values (500-1000 Hz) for birdsong or insect recordings where the target signal is purely high-frequency.")
        prl = PresetReasonLabel("HIGHPASS_CUTOFF_HZ")
        g.addWidget(prl)
        self._preset_reason_labels["HIGHPASS_CUTOFF_HZ"] = prl

        self.amplitude_gate = QLineEdit("0.05")
        _add_row(g, "Onset amplitude gate", self.amplitude_gate,
                 "Discard onsets whose local RMS is below this fraction (0-1) of the file's peak RMS. 0 = disabled.",
                 extended_desc="After onset detection, computes the RMS energy in a window around each onset and discards those whose energy falls below this fraction of the file's peak RMS. Filters out ghost triggers in silent passages. 0.0 = disabled, 0.03 = mild, 0.05 = default, 0.10+ = aggressive. Redundant if the Audio Editor already muted silent regions.")
        prl = PresetReasonLabel("ONSET_AMPLITUDE_GATE")
        g.addWidget(prl)
        self._preset_reason_labels["ONSET_AMPLITUDE_GATE"] = prl

        self.amplitude_window = QLineEdit("50")
        _add_row(g, "Amplitude window (ms)", self.amplitude_window,
                 "RMS window (ms) for the amplitude gate.",
                 extended_desc="Half-width of the window used to compute RMS energy around each onset for the amplitude gate. 50 ms (default) captures a 100 ms total window. Shorter windows (20 ms) respond to brief transients; longer windows (100 ms) average over more context.")
        prl = PresetReasonLabel("ONSET_AMPLITUDE_WINDOW_MS")
        g.addWidget(prl)
        self._preset_reason_labels["ONSET_AMPLITUDE_WINDOW_MS"] = prl

        lay.addWidget(grp)

        self.hp_group = QGroupBox("Adaptive HP Parameters")
        g = QVBoxLayout(self.hp_group)
        self.hp_smooth = QLineEdit("50")
        _add_row(g, "HP smooth lambda", self.hp_smooth,
                 "HP trend stiffness. Higher = smoother trend = more sensitive to transients. Range: 10-500.",
                 extended_desc="Controls the Hodrick-Prescott filter's smoothness penalty. Higher values produce a smoother trend line, making transients stand out more. 50 (default) works for most percussion. Increase to 100-200 for noisy field recordings with slow amplitude fluctuations; decrease to 20-30 for studio recordings with subtle onsets.")
        self.hp_threshold = QLineEdit("5e7")
        _add_row(g, "HP threshold lambda", self.hp_threshold,
                 "Dynamic threshold scale. Higher = fewer onsets. Range: 1e6-1e9.",
                 extended_desc="Scales the adaptive threshold above which residual peaks are accepted as onsets. Higher values raise the bar, rejecting weaker peaks. 5e7 (default) balances sensitivity and specificity. Use 1e6-1e7 for quiet or sparse signals; 1e8-1e9 to suppress false alarms in dense recordings.")
        self.hp_env_window = QLineEdit("10")
        _add_row(g, "Envelope window (ms)", self.hp_env_window,
                 "RMS envelope window (ms). Shorter = sharper but noisier.",
                 extended_desc="Width of the RMS window used to compute the amplitude envelope before HP filtering. Shorter windows (3-5 ms) preserve fast transients but introduce estimation noise; longer windows (15-20 ms) produce a cleaner envelope but may smear closely-spaced onsets. 10 ms is a good default.")
        self.hp_env_hop = QLineEdit("1")
        _add_row(g, "Envelope hop (ms)", self.hp_env_hop,
                 "Envelope hop (ms). 1 ms gives ~1 ms coarse resolution.",
                 extended_desc="Step size for the envelope computation. 1 ms gives ~1 ms coarse onset resolution before refinement. Increasing to 2-5 ms reduces computation time for very long recordings but sacrifices temporal precision at the coarse stage.")
        lay.addWidget(self.hp_group)

        self.median_group = QGroupBox("Moving Median Parameters")
        g = QVBoxLayout(self.median_group)
        self.median_window = QLineEdit("200")
        _add_row(g, "Median window (ms)", self.median_window,
                 "Sliding median window (ms). Must be wider than the longest expected note/call.",
                 extended_desc="The sliding median estimates a local noise baseline from a window of this width (in ms). If the window is shorter than a sustained note, the note itself raises the baseline and its onset may be missed. 200 ms covers most bird calls; use 500+ ms for long primate pant-hoots.")
        self.median_scale = QLineEdit("1.5")
        _add_row(g, "Threshold scale", self.median_scale,
                 "Multiplier on the median baseline. Higher = fewer onsets. Range: 1.2-3.0.",
                 extended_desc="An onset is accepted when the signal exceeds median x this factor. 1.2 = sensitive (catches soft onsets, more false alarms), 1.5 = balanced default, 2.0-3.0 = conservative (only strong transients pass). Adjust alongside the median window to fine-tune detection.")
        lay.addWidget(self.median_group)

        self.superflux_group = QGroupBox("Superflux Parameters")
        g = QVBoxLayout(self.superflux_group)
        self.sf_lag = QLineEdit("2")
        _add_row(g, "Lag (frames)", self.sf_lag,
                 "Number of frames for temporal comparison. Higher = ignores slow modulation. Range: 1-4.",
                 extended_desc="Superflux compares each spectrogram frame to a frame this many steps in the past. Lag 1 detects the fastest changes but is sensitive to vibrato. Lag 2 (default) smooths out vibrato. Lag 3-4 ignores even slow frequency modulation but may miss very rapid onsets.")
        self.sf_max_size = QLineEdit("3")
        _add_row(g, "Max size (bins)", self.sf_max_size,
                 "Frequency bins for local-max filtering. Higher = suppresses more spectral ripple. Range: 1-7.",
                 extended_desc="Number of frequency bins used for max-pooling the spectrogram before computing spectral flux. Larger values smooth out harmonic ripple and vibrato, reducing false onsets from tonal signals. 3 (default) works for most signals. Increase to 5-7 for highly harmonic sources (e.g., singing).")
        lay.addWidget(self.superflux_group)

        self.cfar_group = QGroupBox("CFAR Parameters")
        g = QVBoxLayout(self.cfar_group)
        self.cfar_guard = QLineEdit("20")
        _add_row(g, "Guard interval (ms)", self.cfar_guard,
                 "Guard interval (ms) on each side of the test cell. Must be wider than the sharpest attack.",
                 extended_desc="Width of the guard zone on each side of the sample under test. Prevents energy from the onset itself leaking into the noise estimate. Must be at least as wide as the sharpest attack transient (~10-30 ms for percussion, ~5-10 ms for birdsong clicks). Too narrow = missed onsets; too wide = noise estimate may include other events.")
        self.cfar_training = QLineEdit("200")
        _add_row(g, "Training window (ms)", self.cfar_training,
                 "Noise estimation window (ms) on each side. Must be wider than the longest note.",
                 extended_desc="Width of the training region on each side of the guard zone, used to estimate the local noise floor. Must be wider than the longest expected note or call to avoid biasing the noise estimate upward. 200 ms works for most percussion; use 500+ ms for long primate calls.")
        self.cfar_factor = QLineEdit("4.0")
        _add_row(g, "Threshold factor", self.cfar_factor,
                 "Multiplier on estimated noise floor. Higher = fewer false alarms. Range: 2-6.",
                 extended_desc="An onset is accepted when the signal exceeds the estimated noise floor x this factor. 2-3 = sensitive (catches soft onsets, more false alarms). 4 = balanced default. 5-6 = conservative (strong transients only). Adjust based on the signal-to-noise ratio of your recordings.")
        lay.addWidget(self.cfar_group)

        self.per_band_group = QGroupBox("Per-Band Parameters")
        g = QVBoxLayout(self.per_band_group)
        self.pb_n_bands = QLineEdit("6")
        _add_row(g, "Number of bands", self.pb_n_bands,
                 "Number of Mel frequency bands. Range: 3-12.",
                 extended_desc="The audio is split into this many Mel-spaced frequency bands, each analysed independently for onsets. More bands give finer frequency resolution but each band has less energy, reducing sensitivity. 6 (default) balances resolution and robustness. Use 3-4 for narrow-band signals; 8-12 for broadband signals with many simultaneous sources.")
        self.pb_freq_min = QLineEdit("200")
        _add_row(g, "Freq min (Hz)", self.pb_freq_min,
                 "Lowest frequency (Hz) for the filterbank.",
                 extended_desc="Lower boundary of the Mel filterbank. Energy below this frequency is ignored. 200 Hz (default) excludes wind and traffic rumble. Use 500-1000 Hz for birdsong to focus on vocalisations; use 50-100 Hz for low-pitched drums.")
        self.pb_freq_max = QLineEdit("")
        _add_row(g, "Freq max (Hz)", self.pb_freq_max,
                 "Highest frequency (Hz). Leave blank or 'None' for Nyquist (sr/2).",
                 extended_desc="Upper boundary of the Mel filterbank. Leave blank to use the Nyquist frequency (half the sample rate, e.g. 22050 Hz at 44.1 kHz). Set explicitly (e.g. 8000) to exclude high-frequency hiss or to focus the analysis on the spectral range of your target species.")
        self.pb_median = QLineEdit("200")
        _add_row(g, "Per-band median (ms)", self.pb_median,
                 "Per-band sliding median window (ms).",
                 extended_desc="Width of the sliding median window used within each frequency band to estimate the local noise baseline. Same principle as the Moving Median method but applied per-band. Must be wider than the longest expected note in each band. 200 ms is a good default.")
        self.pb_thresh_scale = QLineEdit("1.5")
        _add_row(g, "Per-band threshold scale", self.pb_thresh_scale,
                 "Per-band threshold multiplier on the median baseline.",
                 extended_desc="Within each band, an onset is detected when the signal exceeds median x this factor. Same as the Moving Median threshold scale but applied independently in each band. 1.5 (default) is balanced; lower for sensitivity, higher for specificity.")
        self.pb_min_bands = QLineEdit("2")
        _add_row(g, "Min agreeing bands", self.pb_min_bands,
                 "Minimum number of bands that must agree to confirm an onset. 1 = sensitive, 3+ = conservative.",
                 extended_desc="An onset is only confirmed when at least this many frequency bands detect it simultaneously. Acts as a voting mechanism to filter out noise that appears in only one band. 1 = accept any band (sensitive), 2 = default (good noise rejection), 3+ = conservative (requires broadband events).")
        lay.addWidget(self.per_band_group)

        self.syllable_group = QGroupBox("Syllable Nuclei Parameters (Praat)")
        g = QVBoxLayout(self.syllable_group)
        self.syl_intensity_thresh = QLineEdit("-25.0")
        _add_row(g, "Intensity threshold (dB)", self.syl_intensity_thresh,
                 "Minimum intensity (dB) for a peak to be considered a syllable nucleus.",
                 extended_desc="Peaks in the Praat intensity contour below this absolute threshold are ignored. -25 dB is a good default for clean speech. Lower (e.g. -35) to catch very quiet syllables; raise (e.g. -15) for noisy recordings.")
        self.syl_min_dip = QLineEdit("2.0")
        _add_row(g, "Min dip (dB)", self.syl_min_dip,
                 "Minimum dip between two intensity peaks to count them as separate syllables.",
                 extended_desc="Adjacent intensity peaks must have a valley at least this deep (in dB) to be counted as distinct syllables. Higher values merge co-articulated syllables. 2 dB follows de Jong & Wempe (2009).")
        self.syl_min_pause = QLineEdit("30.0")
        _add_row(g, "Min pause (ms)", self.syl_min_pause,
                 "Minimum silent gap (ms) to separate syllable groups.",
                 extended_desc="Intensity valleys longer than this duration are treated as pauses between speech phrases. Does not affect within-phrase syllable detection. 30 ms is a good default.")
        self.syl_voicing_thresh = QLineEdit("0.3")
        _add_row(g, "Voicing threshold", self.syl_voicing_thresh,
                 "Praat voicing probability threshold (0-1). Higher = stricter.",
                 extended_desc="Peaks are only accepted as syllable nuclei if the Praat pitch tracker detects voicing above this probability. 0.3 (default) keeps most voiced syllables. 0.0 disables voicing filtering; 0.6+ restricts to strongly voiced segments.")
        self.syl_time_step = QLineEdit("0.01")
        _add_row(g, "Time step (s)", self.syl_time_step,
                 "Analysis time step for Praat intensity calculation.",
                 extended_desc="Temporal resolution of the Praat intensity contour in seconds. 0.01 s (10 ms) gives good balance of resolution and speed. Smaller values (e.g. 0.005) increase precision but slow computation.")
        lay.addWidget(self.syllable_group)

        self.whisper_group = QGroupBox("Whisper Parameters (Word Onsets)")
        g = QVBoxLayout(self.whisper_group)
        self.whisper_model_size = QComboBox()
        self.whisper_model_size.addItems(["tiny", "base", "small", "medium", "large"])
        self.whisper_model_size.setCurrentText("base")
        _add_row(g, "Model size", self.whisper_model_size,
                 "Whisper model size: tiny (fastest) -> large (most accurate).",
                 extended_desc="tiny: 39M params, fastest, least accurate. base: 74M params, good balance (default). small: 244M params, good accuracy. medium: 769M params, very good. large: 1550M params, best accuracy but slow and GPU-heavy.")
        self.whisper_language = QLineEdit("")
        _add_row(g, "Language", self.whisper_language,
                 "Language code (e.g. 'en', 'fr'). Leave blank for auto-detection.",
                 extended_desc="ISO language code to force Whisper to transcribe in a specific language. Leave blank to let Whisper auto-detect the language from the first 30 seconds of audio.")
        self.whisper_word_ts = QCheckBox("Enabled")
        self.whisper_word_ts.setChecked(True)
        _add_row(g, "Word timestamps", self.whisper_word_ts,
                 "Enable word-level timestamp extraction.",
                 extended_desc="When enabled, Whisper returns individual word start times. When disabled, only segment-level (sentence/phrase) timestamps are returned. Must be enabled for word-onset detection (the usual case).")
        lay.addWidget(self.whisper_group)

        self.whisperx_group = QGroupBox("WhisperX Parameters (Phoneme Alignment)")
        g = QVBoxLayout(self.whisperx_group)
        self.whisperx_model_size = QComboBox()
        self.whisperx_model_size.addItems(["tiny", "base", "small", "medium", "large"])
        self.whisperx_model_size.setCurrentText("base")
        _add_row(g, "Model size", self.whisperx_model_size,
                 "Whisper model for transcription (same sizes as whisper_words).",
                 extended_desc="Used for the initial transcription step before forced alignment.")
        self.whisperx_language = QLineEdit("")
        _add_row(g, "Language", self.whisperx_language,
                 "Language code (e.g. 'en'). Required for forced alignment.",
                 extended_desc="WhisperX needs the language code to select the correct wav2vec2 alignment model. Leave blank for auto-detection, but specifying it is recommended.")
        self.whisperx_device = QComboBox()
        self.whisperx_device.addItems(["cpu", "cuda"])
        _add_row(g, "Device", self.whisperx_device,
                 "Torch device: cpu or cuda (GPU).",
                 extended_desc="Use 'cuda' if you have a compatible NVIDIA GPU for faster processing.")
        lay.addWidget(self.whisperx_group)

        self.madmom_group = QGroupBox("madmom Parameters (Beat Tracking)")
        g = QVBoxLayout(self.madmom_group)
        self.madmom_min_bpm = QLineEdit("40")
        _add_row(g, "Min BPM", self.madmom_min_bpm,
                 "Minimum tempo hypothesis (BPM). Default 40.",
                 extended_desc="Lower bound of the tempo search range. Set lower for very slow music or rituals (e.g. 20), higher to exclude false slow-tempo hypotheses.")
        self.madmom_max_bpm = QLineEdit("240")
        _add_row(g, "Max BPM", self.madmom_max_bpm,
                 "Maximum tempo hypothesis (BPM). Default 240.",
                 extended_desc="Upper bound of the tempo search range. Raise for very fast music (e.g. 300 for fast electronic music), lower for slow genres.")
        self.madmom_fps = QLineEdit("100")
        _add_row(g, "Frames per second", self.madmom_fps,
                 "Resolution of the beat activation function. Default 100 (= 10 ms).",
                 extended_desc="Higher values give finer time resolution but slower processing. 100 fps (10 ms frames) is the standard default.")
        self.madmom_transition_lambda = QLineEdit("100")
        _add_row(g, "Transition lambda", self.madmom_transition_lambda,
                 "Tempo continuity strictness (higher = more stable tempo). Default 100.",
                 extended_desc="Controls how much the DBN penalises tempo changes between beats. Higher values enforce a more constant tempo. Lower values (e.g. 16) allow more tempo flexibility, useful for rubato or free-rhythm music.")
        self.madmom_downbeats = QCheckBox("Enabled")
        self.madmom_downbeats.setChecked(False)
        _add_row(g, "Detect downbeats", self.madmom_downbeats,
                 "Also detect downbeats (bar-level '1' positions).",
                 extended_desc="When enabled, the tracker attempts to identify the first beat of each bar (the 'one'). Results appear in the Excel summary as N Downbeats.")
        lay.addWidget(self.madmom_group)

        self.pitch_group = QGroupBox("Pitch Tracker")
        g = QVBoxLayout(self.pitch_group)
        self.pitch_tracker = QComboBox()
        self.pitch_tracker.addItems(["none", "pyin", "crepe", "praat"])
        _add_row(g, "Method", self.pitch_tracker,
                 "Standalone F0 pitch tracker to run after onset detection.",
                 extended_desc="pYIN (Mauch & Dixon 2014): probabilistic YIN, fast, built into librosa. CREPE (Kim et al. 2018): neural-network pitch tracker, very accurate for monophonic singing - requires torchcrepe. Praat: classic autocorrelation pitch tracker via parselmouth. 'none' disables standalone pitch tracking (syllable_nuclei always computes Praat F0 internally).")
        self.pitch_fmin = QLineEdit("65.0")
        _add_row(g, "F0 min (Hz)", self.pitch_fmin,
                 "Minimum expected fundamental frequency. Default 65 Hz (~ C2).",
                 extended_desc="Lower values allow tracking bass voices or low-pitched calls. Setting too low increases octave errors.")
        self.pitch_fmax = QLineEdit("1047.0")
        _add_row(g, "F0 max (Hz)", self.pitch_fmax,
                 "Maximum expected fundamental frequency. Default 1047 Hz (~ C6).",
                 extended_desc="Upper bound for pitch search. Setting too high increases spurious high-frequency detections.")
        lay.addWidget(self.pitch_group)

        self.tempo_adaptive_group = QGroupBox("Tempo-Adaptive Min IOI")
        g = QVBoxLayout(self.tempo_adaptive_group)
        self.tempo_adaptive_enabled = QCheckBox("Enabled")
        self.tempo_adaptive_enabled.setChecked(False)
        _add_row(g, "Enable tempo-adaptive", self.tempo_adaptive_enabled,
                 "Auto-compute MIN_INTER_ONSET_MS from detected tempo.",
                 extended_desc="When enabled, the pipeline estimates BPM from the madmom beat tracker (if available) or from the median inter-onset interval, then sets the minimum spacing to (beat interval x fraction). This prevents removing legitimate fast onsets in slow music or keeping spurious doubles in fast music.")
        self.tempo_adaptive_fraction = QLineEdit("0.5")
        _add_row(g, "Fraction of beat", self.tempo_adaptive_fraction,
                 "Fraction of the beat interval used as minimum spacing. Default 0.5.",
                 extended_desc="0.5 means onsets closer than half a beat are merged. Lower values (0.25) preserve more ornamental notes; higher values (0.75) aggressively thin to main beats only.")
        lay.addWidget(self.tempo_adaptive_group)

        self.speech_opts_group = QGroupBox("Speech Analysis Options")
        g = QVBoxLayout(self.speech_opts_group)
        self.pause_threshold = QLineEdit("250.0")
        _add_row(g, "Pause threshold (ms)", self.pause_threshold,
                 "IOIs longer than this are classified as pauses (Dellwo 2006).",
                 extended_desc="Standard threshold in speech rhythm research is 250 ms. Intervals exceeding this value are excluded from articulation rate calculation and counted as pauses. 150 ms for rapid speech, 300+ for read speech.")
        self.export_textgrid = QCheckBox("Enabled")
        self.export_textgrid.setChecked(True)
        _add_row(g, "Export Praat TextGrid", self.export_textgrid,
                 "Export onset times as Praat TextGrid files for manual verification.",
                 extended_desc="Creates .TextGrid files alongside the audio with an Onsets point tier. When using whisper_words, also adds a Words interval tier with the transcript. These files can be opened directly in Praat.")
        self.export_transcript = QCheckBox("Enabled")
        self.export_transcript.setChecked(True)
        _add_row(g, "Export Whisper transcript", self.export_transcript,
                 "Save Whisper transcription as .txt and .srt files (whisper_words only).",
                 extended_desc="Creates a timestamped transcript (.txt) and subtitle file (.srt) alongside the audio. Only active when using whisper_words or whisperx_phonemes. The full transcript text is also added to the Excel summary.")
        lay.addWidget(self.speech_opts_group)

        lay.addStretch()
        self.setWidget(content)

        self._update_method_groups(self.onset_method.currentText())
        self._register_perfile_indicators()

        self.audio_folder.textChanged.connect(self._on_audio_folder_changed)
        self.specify_files_cb.stateChanged.connect(self._on_specify_files_toggled)
        self.specify_layers_cb.stateChanged.connect(self._on_specify_layers_toggled)

        self.create_spectrograms.stateChanged.connect(self._update_io_summary)
        self.create_labels.stateChanged.connect(self._update_io_summary)
        self.filter_stable.stateChanged.connect(self._update_io_summary)
        self.spectrogram_chunk_enabled.stateChanged.connect(self._update_io_summary)
        self._update_io_summary()

    def _on_audio_folder_changed(self, text):
        self.selected_files_combo.set_folder(text)
        self.selected_layers_combo.set_folder(text)
        if self.specify_files_cb.isChecked():
            self.selected_files_combo.ensure_first_selected()
        if self.specify_layers_cb.isChecked():
            self.selected_layers_combo.ensure_first_selected()
        if self._output_auto_cb.isChecked():
            cfg = self._output_auto_cb.auto_config
            src = cfg.get("source_step", "(this step)")
            if src in ("(this step)", "Onset Finder") and cfg.get("source_io") == "input":
                resolved = _resolve_auto_config(text, cfg)
                if resolved:
                    self.output_excel.setText(resolved)

    def _on_specify_files_toggled(self, state):
        enabled = bool(state)
        self.selected_files_combo.setEnabled(enabled)
        if enabled:
            self.selected_files_combo.set_folder(self.audio_folder.text())
            self.selected_files_combo.ensure_first_selected()

    def _on_specify_layers_toggled(self, state):
        enabled = bool(state)
        self.selected_layers_combo.setEnabled(enabled)
        if enabled:
            self.selected_layers_combo.set_folder(self.audio_folder.text())
            self.selected_layers_combo.ensure_first_selected()

    def _on_output_auto_toggled(self, state):
        if bool(state):
            self._on_audio_folder_changed(self.audio_folder.text())

    def _update_io_summary(self):
        lines = ["<b>Reads:</b> .wav, .mp3, .mp4 audio files from Input folder"]
        out = ["<b>Produces:</b>"]
        out.append("• Excel workbook (.xlsx) → Output Excel file")
        if self.create_spectrograms.isChecked():
            chunk = " (chunked)" if self.spectrogram_chunk_enabled.isChecked() else ""
            out.append(f"• Spectrogram .png{chunk} → inside Input folder")
        if self.create_labels.isChecked():
            out.append("• Audacity label .txt → inside Input folder")
        if self.filter_stable.isChecked():
            out.append("• Extra 'Stable Rhythms' sheet in Excel workbook")
        self._io_summary.setText("<br>".join(lines + out))

    def _update_method_groups(self, method):
        self.hp_group.setVisible(method == "adaptive_hp")
        self.median_group.setVisible(method == "moving_median")
        self.superflux_group.setVisible(method == "superflux")
        self.cfar_group.setVisible(method == "cfar")
        self.per_band_group.setVisible(method == "per_band")
        self.syllable_group.setVisible(method == "syllable_nuclei")
        self.whisper_group.setVisible(method == "whisper_words")
        self.whisperx_group.setVisible(method == "whisperx_phonemes")
        self.madmom_group.setVisible(method == "madmom_beats")
        is_speech = method in ("syllable_nuclei", "whisper_words", "whisperx_phonemes")
        self.speech_opts_group.setVisible(is_speech)

    def _save_as_preset(self):
        _export_settings_for(self, "Onset Finder")

    def save_settings_if_enabled(self):
        return _save_settings_if_enabled(self)

    def _on_preset_changed(self, name):
        for preset_reason_label in self._preset_reason_labels.values():
            preset_reason_label.hide()
        self._preset_desc.hide()

        if name == "None" or name not in self._onset_presets:
            return
        self._applying_preset = True
        preset = self._onset_presets[name]

        self._preset_desc.setText(preset.get("description", ""))
        self._preset_desc.show()

        self.highpass_cutoff.setText(str(preset["HIGHPASS_CUTOFF_HZ"]))
        self.amplitude_gate.setText(str(preset["ONSET_AMPLITUDE_GATE"]))
        self.amplitude_window.setText(str(preset["ONSET_AMPLITUDE_WINDOW_MS"]))
        self.sharpness_gate.setText(str(preset["ONSET_SHARPNESS_GATE"]))
        self.sharpness_window.setText(str(preset["ONSET_SHARPNESS_WINDOW_MS"]))
        self.broadband_min_bands.setText(str(preset.get("ONSET_BROADBAND_MIN_BANDS", 0)))
        self.broadband_n_bands.setText(str(preset.get("ONSET_BROADBAND_N_BANDS", 6)))
        self.broadband_threshold.setText(str(preset.get("ONSET_BROADBAND_THRESHOLD", 0.15)))
        self.min_ioi.setText(str(preset["MIN_INTER_ONSET_MS"]))
        self.cluster_window.setText(str(preset["ONSET_CLUSTER_WINDOW_MS"]))
        self.stable_tolerance.setText(str(preset["STABLE_RHYTHM_TOLERANCE"]))
        self.onset_delta.setText(str(preset["ONSET_DELTA"]))
        self.onset_hop.setText(str(preset["ONSET_HOP_LENGTH"]))
        self.onset_backtrack.setChecked(preset["ONSET_BACKTRACK"])
        self.refine_enabled.setChecked(preset["ONSET_REFINE_ENABLED"])
        self.refine_window.setText(str(preset["ONSET_REFINE_WINDOW_MS"]))
        self.refine_energy_gate.setText(str(preset["ONSET_REFINE_ENERGY_GATE"]))
        self.onset_method.setCurrentText(preset["ONSET_METHOD"])

        if "APPLY_HIGHPASS_FILTER" in preset:
            self.apply_highpass.setChecked(bool(preset["APPLY_HIGHPASS_FILTER"]))
        if "CLUSTER_OVERLAPPING_ONSETS" in preset:
            self.cluster_onsets.setChecked(bool(preset["CLUSTER_OVERLAPPING_ONSETS"]))
        if "FILTER_STABLE_RHYTHMS" in preset:
            self.filter_stable.setChecked(bool(preset["FILTER_STABLE_RHYTHMS"]))
        if "HP_SMOOTH_LAMBDA" in preset:
            self.hp_smooth.setText(str(preset["HP_SMOOTH_LAMBDA"]))
        if "HP_THRESHOLD_LAMBDA" in preset:
            self.hp_threshold.setText(str(preset["HP_THRESHOLD_LAMBDA"]))
        if "HP_ENVELOPE_WINDOW_MS" in preset:
            self.hp_env_window.setText(str(preset["HP_ENVELOPE_WINDOW_MS"]))
        if "HP_ENVELOPE_HOP_MS" in preset:
            self.hp_env_hop.setText(str(preset["HP_ENVELOPE_HOP_MS"]))
        if "SYLLABLE_INTENSITY_THRESHOLD" in preset:
            self.syl_intensity_thresh.setText(str(preset["SYLLABLE_INTENSITY_THRESHOLD"]))
        if "SYLLABLE_MIN_DIP_DB" in preset:
            self.syl_min_dip.setText(str(preset["SYLLABLE_MIN_DIP_DB"]))
        if "SYLLABLE_MIN_PAUSE_MS" in preset:
            self.syl_min_pause.setText(str(preset["SYLLABLE_MIN_PAUSE_MS"]))
        if "SYLLABLE_VOICING_THRESHOLD" in preset:
            self.syl_voicing_thresh.setText(str(preset["SYLLABLE_VOICING_THRESHOLD"]))
        if "SYLLABLE_TIME_STEP" in preset:
            self.syl_time_step.setText(str(preset["SYLLABLE_TIME_STEP"]))
        if "WHISPER_MODEL_SIZE" in preset:
            self.whisper_model_size.setCurrentText(str(preset["WHISPER_MODEL_SIZE"]))
        if "WHISPER_LANGUAGE" in preset:
            whisper_language = preset["WHISPER_LANGUAGE"]
            self.whisper_language.setText("" if whisper_language is None else str(whisper_language))
        if "WHISPER_WORD_TIMESTAMPS" in preset:
            self.whisper_word_ts.setChecked(bool(preset["WHISPER_WORD_TIMESTAMPS"]))
        if "WHISPERX_MODEL_SIZE" in preset:
            self.whisperx_model_size.setCurrentText(str(preset["WHISPERX_MODEL_SIZE"]))
        if "WHISPERX_LANGUAGE" in preset:
            whisperx_language = preset["WHISPERX_LANGUAGE"]
            self.whisperx_language.setText("" if whisperx_language is None else str(whisperx_language))
        if "WHISPERX_DEVICE" in preset:
            self.whisperx_device.setCurrentText(str(preset["WHISPERX_DEVICE"]))
        if "MADMOM_MIN_BPM" in preset:
            self.madmom_min_bpm.setText(str(preset["MADMOM_MIN_BPM"]))
        if "MADMOM_MAX_BPM" in preset:
            self.madmom_max_bpm.setText(str(preset["MADMOM_MAX_BPM"]))
        if "MADMOM_FPS" in preset:
            self.madmom_fps.setText(str(preset["MADMOM_FPS"]))
        if "MADMOM_TRANSITION_LAMBDA" in preset:
            self.madmom_transition_lambda.setText(str(preset["MADMOM_TRANSITION_LAMBDA"]))
        if "MADMOM_DOWNBEATS" in preset:
            self.madmom_downbeats.setChecked(bool(preset["MADMOM_DOWNBEATS"]))
        if "PITCH_TRACKER" in preset:
            idx = self.pitch_tracker.findText(str(preset["PITCH_TRACKER"]))
            if idx >= 0:
                self.pitch_tracker.setCurrentIndex(idx)
        if "PITCH_FMIN" in preset:
            self.pitch_fmin.setText(str(preset["PITCH_FMIN"]))
        if "PITCH_FMAX" in preset:
            self.pitch_fmax.setText(str(preset["PITCH_FMAX"]))
        if "TEMPO_ADAPTIVE_MIN_IOI" in preset:
            self.tempo_adaptive_enabled.setChecked(bool(preset["TEMPO_ADAPTIVE_MIN_IOI"]))
        if "TEMPO_ADAPTIVE_FRACTION" in preset:
            self.tempo_adaptive_fraction.setText(str(preset["TEMPO_ADAPTIVE_FRACTION"]))
        if "PAUSE_THRESHOLD_MS" in preset:
            self.pause_threshold.setText(str(preset["PAUSE_THRESHOLD_MS"]))
        if "EXPORT_TEXTGRID" in preset:
            self.export_textgrid.setChecked(bool(preset["EXPORT_TEXTGRID"]))
        if "EXPORT_TRANSCRIPT" in preset:
            self.export_transcript.setChecked(bool(preset["EXPORT_TRANSCRIPT"]))

        reasons = self._onset_preset_reasons.get(name, {})
        for key, reason_text in reasons.items():
            preset_reason_label = self._preset_reason_labels.get(key)
            if preset_reason_label:
                preset_reason_label.setText(f"✱ Preset: {reason_text}")
                preset_reason_label.show()

        self._applying_preset = False

    def attach_per_file_manager(self, manager, open_dialog_callback=None):
        self._per_file_overrides.set_manager(manager)
        if open_dialog_callback is not None:
            self._per_file_overrides._open_dialog_callback = open_dialog_callback
        for indicator in self.findChildren(PerFileToggleIndicator):
            indicator.set_manager(manager)

    def _register_perfile_indicators(self):
        mapping = {
            "ONSET_METHOD": self.onset_method,
            "MIN_INTER_ONSET_MS": self.min_ioi,
            "ONSET_DELTA": self.onset_delta,
            "ONSET_HOP_LENGTH": self.onset_hop,
            "ONSET_BACKTRACK": self.onset_backtrack,
            "APPLY_HIGHPASS_FILTER": self.apply_highpass,
            "HIGHPASS_CUTOFF_HZ": self.highpass_cutoff,
            "ONSET_AMPLITUDE_GATE": self.amplitude_gate,
            "ONSET_AMPLITUDE_WINDOW_MS": self.amplitude_window,
            "ONSET_SHARPNESS_GATE": self.sharpness_gate,
            "ONSET_SHARPNESS_WINDOW_MS": self.sharpness_window,
            "ONSET_REFINE_ENABLED": self.refine_enabled,
            "ONSET_REFINE_WINDOW_MS": self.refine_window,
            "ONSET_REFINE_ENERGY_GATE": self.refine_energy_gate,
            "TEMPO_ADAPTIVE_MIN_IOI": self.tempo_adaptive_enabled,
            "TEMPO_ADAPTIVE_FRACTION": self.tempo_adaptive_fraction,
            "PITCH_TRACKER": self.pitch_tracker,
        }
        for config_key, widget in mapping.items():
            _mark_perfile_setting(widget, "onset_recommendations", config_key)

    def get_values(self):
        preset = self.preset.currentText()
        freq_max_text = self.pb_freq_max.text().strip()
        if freq_max_text in ("", "None", "none"):
            freq_max = None
        else:
            freq_max = _to_int(freq_max_text, None)

        return {
            "EXTRACTOR_ENGINE": self.engine.currentText(),
            "audio_folder": self.audio_folder.text(),
            "EXTRACTOR_SPECIFY_FILES": self.specify_files_cb.isChecked(),
            "EXTRACTOR_SELECTED_FILES": self.selected_files_combo.selected_files(),
            "EXTRACTOR_SPECIFY_LAYERS": self.specify_layers_cb.isChecked(),
            "EXTRACTOR_SELECTED_LAYERS": self.selected_layers_combo.selected_layers(),
            "output_excel_path": self.output_excel.text(),
            "ACTIVE_PRESET": None if preset == "None" else preset,
            "CREATE_SPECTROGRAMS": self.create_spectrograms.isChecked(),
            "SPECTROGRAM_CHUNK_ENABLED": self.spectrogram_chunk_enabled.isChecked(),
            "SPECTROGRAM_CHUNK_SECONDS": _to_int(self.spectrogram_chunk_seconds.text(), 30),
            "CREATE_AUDACITY_LABELS": self.create_labels.isChecked(),
            "ADD_COLUMN_COMMENTS": self.add_column_comments.isChecked(),
            "ADD_FORMULA_SHEET": self.add_formula_sheet.isChecked(),
            "CLUSTER_OVERLAPPING_ONSETS": self.cluster_onsets.isChecked(),
            "ONSET_CLUSTER_WINDOW_MS": _to_int(self.cluster_window.text(), 25),
            "FILTER_STABLE_RHYTHMS": self.filter_stable.isChecked(),
            "STABLE_RHYTHM_TOLERANCE": _to_float(self.stable_tolerance.text(), 0.25),
            "APPLY_HIGHPASS_FILTER": self.apply_highpass.isChecked(),
            "HIGHPASS_CUTOFF_HZ": _to_int(self.highpass_cutoff.text(), 200),
            "ONSET_AMPLITUDE_GATE": _to_float(self.amplitude_gate.text(), 0.05),
            "ONSET_AMPLITUDE_WINDOW_MS": _to_int(self.amplitude_window.text(), 50),
            "ONSET_SHARPNESS_GATE": _to_float(self.sharpness_gate.text(), 0.0),
            "ONSET_SHARPNESS_WINDOW_MS": _to_int(self.sharpness_window.text(), 20),
            "ONSET_BROADBAND_MIN_BANDS": _to_int(self.broadband_min_bands.text(), 0),
            "ONSET_BROADBAND_N_BANDS": _to_int(self.broadband_n_bands.text(), 6),
            "ONSET_BROADBAND_THRESHOLD": _to_float(self.broadband_threshold.text(), 0.15),
            "MIN_INTER_ONSET_MS": _to_int(self.min_ioi.text(), 30),
            "ONSET_METHOD": self.onset_method.currentText(),
            "ONSET_DELTA": _to_float(self.onset_delta.text(), 0.10),
            "ONSET_HOP_LENGTH": _to_int(self.onset_hop.text(), 256),
            "ONSET_BACKTRACK": self.onset_backtrack.isChecked(),
            "ONSET_REFINE_ENABLED": self.refine_enabled.isChecked(),
            "ONSET_REFINE_WINDOW_MS": _to_float(self.refine_window.text(), 10),
            "ONSET_REFINE_ENERGY_GATE": _to_float(self.refine_energy_gate.text(), 0.0),
            "HP_SMOOTH_LAMBDA": _to_float(self.hp_smooth.text(), 50),
            "HP_THRESHOLD_LAMBDA": _to_float(self.hp_threshold.text(), 5e7),
            "HP_ENVELOPE_WINDOW_MS": _to_float(self.hp_env_window.text(), 10),
            "HP_ENVELOPE_HOP_MS": _to_float(self.hp_env_hop.text(), 1),
            "MEDIAN_WINDOW_MS": _to_float(self.median_window.text(), 200),
            "MEDIAN_THRESHOLD_SCALE": _to_float(self.median_scale.text(), 1.5),
            "SUPERFLUX_LAG": _to_int(self.sf_lag.text(), 2),
            "SUPERFLUX_MAX_SIZE": _to_int(self.sf_max_size.text(), 3),
            "CFAR_GUARD_MS": _to_float(self.cfar_guard.text(), 20),
            "CFAR_TRAINING_MS": _to_float(self.cfar_training.text(), 200),
            "CFAR_THRESHOLD_FACTOR": _to_float(self.cfar_factor.text(), 4.0),
            "PER_BAND_N_BANDS": _to_int(self.pb_n_bands.text(), 6),
            "PER_BAND_FREQ_MIN": _to_int(self.pb_freq_min.text(), 200),
            "PER_BAND_FREQ_MAX": freq_max,
            "PER_BAND_MEDIAN_MS": _to_float(self.pb_median.text(), 200),
            "PER_BAND_THRESHOLD_SCALE": _to_float(self.pb_thresh_scale.text(), 1.5),
            "PER_BAND_MIN_BANDS": _to_int(self.pb_min_bands.text(), 2),
            "SYLLABLE_INTENSITY_THRESHOLD": _to_float(self.syl_intensity_thresh.text(), -25.0),
            "SYLLABLE_MIN_DIP_DB": _to_float(self.syl_min_dip.text(), 2.0),
            "SYLLABLE_MIN_PAUSE_MS": _to_float(self.syl_min_pause.text(), 30.0),
            "SYLLABLE_VOICING_THRESHOLD": _to_float(self.syl_voicing_thresh.text(), 0.3),
            "SYLLABLE_TIME_STEP": _to_float(self.syl_time_step.text(), 0.01),
            "WHISPER_MODEL_SIZE": self.whisper_model_size.currentText(),
            "WHISPER_LANGUAGE": self.whisper_language.text().strip() or None,
            "WHISPER_WORD_TIMESTAMPS": self.whisper_word_ts.isChecked(),
            "WHISPERX_MODEL_SIZE": self.whisperx_model_size.currentText(),
            "WHISPERX_LANGUAGE": self.whisperx_language.text().strip() or None,
            "WHISPERX_DEVICE": self.whisperx_device.currentText(),
            "MADMOM_MIN_BPM": _to_float(self.madmom_min_bpm.text(), 40),
            "MADMOM_MAX_BPM": _to_float(self.madmom_max_bpm.text(), 240),
            "MADMOM_FPS": int(_to_float(self.madmom_fps.text(), 100)),
            "MADMOM_TRANSITION_LAMBDA": int(_to_float(self.madmom_transition_lambda.text(), 100)),
            "MADMOM_DOWNBEATS": self.madmom_downbeats.isChecked(),
            "PITCH_TRACKER": self.pitch_tracker.currentText(),
            "PITCH_FMIN": _to_float(self.pitch_fmin.text(), 65.0),
            "PITCH_FMAX": _to_float(self.pitch_fmax.text(), 1047.0),
            "TEMPO_ADAPTIVE_MIN_IOI": self.tempo_adaptive_enabled.isChecked(),
            "TEMPO_ADAPTIVE_FRACTION": _to_float(self.tempo_adaptive_fraction.text(), 0.5),
            "PAUSE_THRESHOLD_MS": _to_float(self.pause_threshold.text(), 250.0),
            "EXPORT_TEXTGRID": self.export_textgrid.isChecked(),
            "EXPORT_TRANSCRIPT": self.export_transcript.isChecked(),
        }

    def set_values(self, d):
        self.engine.setCurrentText(str(d.get("EXTRACTOR_ENGINE", "standard")))
        self.audio_folder.setText(str(d.get("audio_folder", self.audio_folder.text())))
        self.specify_files_cb.setChecked(bool(d.get("EXTRACTOR_SPECIFY_FILES", False)))
        self.selected_files_combo.set_selected_files(d.get("EXTRACTOR_SELECTED_FILES", []))
        if self.specify_files_cb.isChecked():
            self.selected_files_combo.ensure_first_selected()
        self.specify_layers_cb.setChecked(bool(d.get("EXTRACTOR_SPECIFY_LAYERS", False)))
        self.selected_layers_combo.set_selected_layers(d.get("EXTRACTOR_SELECTED_LAYERS", []))
        if self.specify_layers_cb.isChecked():
            self.selected_layers_combo.ensure_first_selected()
        if "output_excel_path" in d:
            self.output_excel.setText(str(d["output_excel_path"]))
        preset_val = d.get("ACTIVE_PRESET")
        self.preset.setCurrentText("None" if preset_val is None else str(preset_val))
        self.create_spectrograms.setChecked(bool(d.get("CREATE_SPECTROGRAMS", True)))
        self.spectrogram_chunk_enabled.setChecked(bool(d.get("SPECTROGRAM_CHUNK_ENABLED", False)))
        self.spectrogram_chunk_seconds.setText(str(d.get("SPECTROGRAM_CHUNK_SECONDS", 30)))
        self.create_labels.setChecked(bool(d.get("CREATE_AUDACITY_LABELS", True)))
        self.add_column_comments.setChecked(bool(d.get("ADD_COLUMN_COMMENTS", True)))
        self.add_formula_sheet.setChecked(bool(d.get("ADD_FORMULA_SHEET", True)))
        self.cluster_onsets.setChecked(bool(d.get("CLUSTER_OVERLAPPING_ONSETS", True)))
        self.cluster_window.setText(str(d.get("ONSET_CLUSTER_WINDOW_MS", 25)))
        self.filter_stable.setChecked(bool(d.get("FILTER_STABLE_RHYTHMS", True)))
        self.stable_tolerance.setText(str(d.get("STABLE_RHYTHM_TOLERANCE", 0.25)))
        self.apply_highpass.setChecked(bool(d.get("APPLY_HIGHPASS_FILTER", False)))
        self.highpass_cutoff.setText(str(d.get("HIGHPASS_CUTOFF_HZ", 200)))
        self.amplitude_gate.setText(str(d.get("ONSET_AMPLITUDE_GATE", 0.05)))
        self.amplitude_window.setText(str(d.get("ONSET_AMPLITUDE_WINDOW_MS", 50)))
        self.sharpness_gate.setText(str(d.get("ONSET_SHARPNESS_GATE", 0.0)))
        self.sharpness_window.setText(str(d.get("ONSET_SHARPNESS_WINDOW_MS", 20)))
        self.broadband_min_bands.setText(str(d.get("ONSET_BROADBAND_MIN_BANDS", 0)))
        self.broadband_n_bands.setText(str(d.get("ONSET_BROADBAND_N_BANDS", 6)))
        self.broadband_threshold.setText(str(d.get("ONSET_BROADBAND_THRESHOLD", 0.15)))
        self.min_ioi.setText(str(d.get("MIN_INTER_ONSET_MS", 30)))
        self.onset_method.setCurrentText(str(d.get("ONSET_METHOD", "adaptive_hp")))
        self.onset_delta.setText(str(d.get("ONSET_DELTA", 0.10)))
        self.onset_hop.setText(str(d.get("ONSET_HOP_LENGTH", 256)))
        self.onset_backtrack.setChecked(bool(d.get("ONSET_BACKTRACK", False)))
        self.refine_enabled.setChecked(bool(d.get("ONSET_REFINE_ENABLED", True)))
        self.refine_window.setText(str(d.get("ONSET_REFINE_WINDOW_MS", 10)))
        self.refine_energy_gate.setText(str(d.get("ONSET_REFINE_ENERGY_GATE", 0.0)))
        self.hp_smooth.setText(str(d.get("HP_SMOOTH_LAMBDA", 50)))
        self.hp_threshold.setText(str(d.get("HP_THRESHOLD_LAMBDA", 5e7)))
        self.hp_env_window.setText(str(d.get("HP_ENVELOPE_WINDOW_MS", 10)))
        self.hp_env_hop.setText(str(d.get("HP_ENVELOPE_HOP_MS", 1)))
        self.median_window.setText(str(d.get("MEDIAN_WINDOW_MS", 200)))
        self.median_scale.setText(str(d.get("MEDIAN_THRESHOLD_SCALE", 1.5)))
        self.sf_lag.setText(str(d.get("SUPERFLUX_LAG", 2)))
        self.sf_max_size.setText(str(d.get("SUPERFLUX_MAX_SIZE", 3)))
        self.cfar_guard.setText(str(d.get("CFAR_GUARD_MS", 20)))
        self.cfar_training.setText(str(d.get("CFAR_TRAINING_MS", 200)))
        self.cfar_factor.setText(str(d.get("CFAR_THRESHOLD_FACTOR", 4.0)))
        self.pb_n_bands.setText(str(d.get("PER_BAND_N_BANDS", 6)))
        self.pb_freq_min.setText(str(d.get("PER_BAND_FREQ_MIN", 200)))
        freq_max = d.get("PER_BAND_FREQ_MAX")
        self.pb_freq_max.setText("" if freq_max is None else str(freq_max))
        self.pb_median.setText(str(d.get("PER_BAND_MEDIAN_MS", 200)))
        self.pb_thresh_scale.setText(str(d.get("PER_BAND_THRESHOLD_SCALE", 1.5)))
        self.pb_min_bands.setText(str(d.get("PER_BAND_MIN_BANDS", 2)))
        self.syl_intensity_thresh.setText(str(d.get("SYLLABLE_INTENSITY_THRESHOLD", -25.0)))
        self.syl_min_dip.setText(str(d.get("SYLLABLE_MIN_DIP_DB", 2.0)))
        self.syl_min_pause.setText(str(d.get("SYLLABLE_MIN_PAUSE_MS", 30.0)))
        self.syl_voicing_thresh.setText(str(d.get("SYLLABLE_VOICING_THRESHOLD", 0.3)))
        self.syl_time_step.setText(str(d.get("SYLLABLE_TIME_STEP", 0.01)))
        self.whisper_model_size.setCurrentText(str(d.get("WHISPER_MODEL_SIZE", "base")))
        whisper_language = d.get("WHISPER_LANGUAGE")
        self.whisper_language.setText("" if whisper_language is None else str(whisper_language))
        self.whisper_word_ts.setChecked(bool(d.get("WHISPER_WORD_TIMESTAMPS", True)))
        self.whisperx_model_size.setCurrentText(str(d.get("WHISPERX_MODEL_SIZE", "base")))
        whisperx_language = d.get("WHISPERX_LANGUAGE")
        self.whisperx_language.setText("" if whisperx_language is None else str(whisperx_language))
        self.whisperx_device.setCurrentText(str(d.get("WHISPERX_DEVICE", "cpu")))
        self.madmom_min_bpm.setText(str(d.get("MADMOM_MIN_BPM", 40)))
        self.madmom_max_bpm.setText(str(d.get("MADMOM_MAX_BPM", 240)))
        self.madmom_fps.setText(str(d.get("MADMOM_FPS", 100)))
        self.madmom_transition_lambda.setText(str(d.get("MADMOM_TRANSITION_LAMBDA", 100)))
        self.madmom_downbeats.setChecked(bool(d.get("MADMOM_DOWNBEATS", False)))
        idx = self.pitch_tracker.findText(str(d.get("PITCH_TRACKER", "none")))
        self.pitch_tracker.setCurrentIndex(max(0, idx))
        self.pitch_fmin.setText(str(d.get("PITCH_FMIN", 65.0)))
        self.pitch_fmax.setText(str(d.get("PITCH_FMAX", 1047.0)))
        self.tempo_adaptive_enabled.setChecked(bool(d.get("TEMPO_ADAPTIVE_MIN_IOI", False)))
        self.tempo_adaptive_fraction.setText(str(d.get("TEMPO_ADAPTIVE_FRACTION", 0.5)))
        self.pause_threshold.setText(str(d.get("PAUSE_THRESHOLD_MS", 250.0)))
        self.export_textgrid.setChecked(bool(d.get("EXPORT_TEXTGRID", True)))
        self.export_transcript.setChecked(bool(d.get("EXPORT_TRANSCRIPT", True)))


__all__ = ["ExtractorPanel"]