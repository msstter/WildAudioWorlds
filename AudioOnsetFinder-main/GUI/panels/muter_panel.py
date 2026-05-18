from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

try:
    from form_widgets import (
        PresetReasonLabel,
        FolderPicker,
        _CheckableAudioFileCombo,
        _ALL_IO_SUMMARIES,
        _add_checkbox,
        _add_row,
        _make_auto_set,
        _resolve_auto_config,
        get_form_widget_palette,
    )
except ImportError:
    from GUI.form_widgets import (
        PresetReasonLabel,
        FolderPicker,
        _CheckableAudioFileCombo,
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
        _MUTER_KEY_ORDER,
        _MUTER_PREFIX,
        _mark_perfile_setting,
        PerFileOverridesBox,
        PerFileToggleIndicator,
    )
except ImportError:
    from GUI.per_file_settings_support import (
        _MUTER_KEY_ORDER,
        _MUTER_PREFIX,
        _mark_perfile_setting,
        PerFileOverridesBox,
        PerFileToggleIndicator,
    )

try:
    from panel_presets import MUTER_PRESETS, _MUTER_PRESET_REASONS
except ImportError:
    from GUI.panel_presets import MUTER_PRESETS, _MUTER_PRESET_REASONS


_ACCENT = "#4caf50"
_BG_WIDGET = "#2c2c3c"
_BORDER = "#3a3a50"
_TEXT = "#dcdcdc"
_TEXT_DIM = "#8888a0"


def _sync_theme_aliases() -> None:
    global _ACCENT, _BG_WIDGET, _BORDER, _TEXT, _TEXT_DIM
    palette = get_form_widget_palette()
    _ACCENT = palette.accent
    _BG_WIDGET = palette.bg_widget
    _BORDER = palette.border
    _TEXT = palette.text
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


class MuterPanel(QScrollArea):
    def __init__(self, parent=None):
        _sync_theme_aliases()
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._preset_reason_labels = {}
        self._muter_presets = MUTER_PRESETS
        self._muter_preset_reasons = _MUTER_PRESET_REASONS
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setSpacing(14)
        lay.setContentsMargins(16, 16, 16, 16)

        self._per_file_overrides = PerFileOverridesBox(
            section_key="settings",
            panel_label="Audio Editor",
            key_filter=lambda k: k.startswith(_MUTER_PREFIX),
            key_order_list=_MUTER_KEY_ORDER,
            parent=content,
        )
        lay.addWidget(self._per_file_overrides)

        grp = QGroupBox("Input / Output")
        g = QVBoxLayout(grp)
        self.input_folder = FolderPicker("")
        self.input_folder.line_edit.setPlaceholderText(
            "Select folder with raw audio files to clean")
        _add_row(g, "Input folder", self.input_folder,
                 "Folder containing raw audio files (.wav, .mp3, .flac, .ogg) to process.",
                 extended_desc="Point this at the folder of raw recordings you want to clean. Supported formats: .wav, .mp3, .flac, .ogg. Every file in the folder will be processed in alphabetical order.",
                 label_width=140)
        self._input_auto_cb, self._input_auto_desc = _make_auto_set(
            self.input_folder, g,
            "↳ Auto: Set to the <b>Input folder</b> from Pipeline Prep",
            checked=True,
            step_name="Audio Editor", io_type="input",
            auto_config={"source_step": "Pipeline Prep", "source_io": "input",
                         "suffix": "", "use_dirname": False,
                         "use_basename": False})
        self.specify_files_cb = QCheckBox("Specify files:")
        self.specify_files_cb.setChecked(False)
        self.specify_files_cb.setToolTip(
            "When off, all supported audio files in the input folder are processed. When on, only the checked files are included.")
        self.selected_files_combo = _CheckableAudioFileCombo()
        self.selected_files_combo.setEnabled(False)
        self.selected_files_combo.setToolTip(
            "Choose which audio files in the input folder should be processed.")
        files_row = QHBoxLayout()
        files_row.setSpacing(12)
        files_spacer = QLabel("")
        files_spacer.setFixedWidth(140)
        files_row.addWidget(files_spacer)
        files_row.addWidget(self.specify_files_cb)
        files_row.addWidget(self.selected_files_combo, stretch=1)
        g.addLayout(files_row)
        self.output_folder = FolderPicker("")
        self.output_folder.line_edit.setPlaceholderText(
            "Output folder for cleaned audio (auto-set from input)")
        _add_row(g, "Output folder", self.output_folder,
                 "Where cleaned audio and sidecar files are saved.",
                 extended_desc="Cleaned audio is saved here. Rejected-noise, HPSS harmonic, and HPSS percussive outputs go to sibling folders derived from this name (e.g. '..._rejected_noise', '..._hpss_harmonic').",
                 label_width=140)
        self._output_auto_cb, self._output_auto_desc = _make_auto_set(
            self.output_folder, g,
            "↳ Auto: Placed <b>inside</b> the Input folder as '<i>{basename}</i>_muted_clean'",
            step_name="Audio Editor", io_type="output",
            auto_config={"source_step": "(this step)", "source_io": "input",
                         "suffix": "_muted_clean", "use_dirname": False,
                         "use_basename": True})
        self._output_auto_cb.stateChanged.connect(self._on_output_auto_toggled)

        self._io_summary = QLabel()
        self._io_summary.setWordWrap(True)
        self._io_summary.setStyleSheet(
            f"color: {_TEXT_DIM}; background: transparent; font-size: 11px; padding: 4px 6px; border: 1px solid {_BORDER}; border-radius: 4px;"
        )
        g.addWidget(self._io_summary)
        _ALL_IO_SUMMARIES.append(self._io_summary)
        self._io_summary.hide()

        lay.addWidget(grp)

        _build_settings_preset_section(
            self, lay, "Audio Editor", self.input_folder,
            presets_dict=self._muter_presets, preset_combo_attr="muter_preset")
        self._import_settings_btn.clicked.connect(
            lambda: _import_settings_for(self, "Audio Editor"))
        self._export_settings_btn.clicked.connect(
            lambda: _export_settings_for(self, "Audio Editor"))
        self._saved_settings_combo.currentTextChanged.connect(
            lambda name: _on_saved_settings_selected(self, "Audio Editor", name))
        self._save_preset_btn.clicked.connect(self._save_as_preset)
        self.muter_preset.currentTextChanged.connect(self._on_muter_preset_changed)

        grp = QGroupBox("① Demucs Source Separation")
        grp.setStyleSheet(
            grp.styleSheet() + " QGroupBox { border: 2px solid #555; }")
        g = QVBoxLayout(grp)

        self.demucs_enabled = QCheckBox("Apply Demucs")
        self.demucs_enabled.setChecked(False)
        _add_checkbox(g, self.demucs_enabled,
            "Run Demucs deep-learning source separation on input audio before the Audio Editor processing chain. Splits each file into isolated stems (drums, bass, vocals, other).",
            "Demucs (Meta/Kyutai, MIT license) uses a Hybrid Transformer neural network to separate audio into independent stems. For bioacoustics, this can isolate percussion from singing, separate overlapping sound sources, or remove vocals from a recording. The separated stems are saved to a subfolder. When this is ON, the rest of the Audio Editor runs on the separated stems (unless 'ONLY Run Demucs' is also checked).\n\nNOTE: Requires 'pip install demucs'. The model (~200 MB) is downloaded automatically on first use. Processing time ~= 1.5x audio duration on CPU. Demucs runs 100 % locally - no data is sent anywhere.")

        self._demucs_details = QWidget()
        dg = QVBoxLayout(self._demucs_details)
        dg.setContentsMargins(0, 0, 0, 0)

        self.demucs_only = QCheckBox("ONLY Run Demucs")
        self.demucs_only.setChecked(False)
        _add_checkbox(dg, self.demucs_only,
            "When checked, ONLY run Demucs source separation - skip all Audio Editor processing steps (filters, HPSS, denoising, muting, etc.).",
            "Use this mode when you want to separate audio into stems without any further cleaning. The original Audio Editor pipeline (high-pass, HPSS, spectral denoising, amplitude muting, etc.) will be skipped entirely. Useful for testing Demucs separation quality on its own before deciding whether to run the full Audio Editor on the stems.")

        self.demucs_model = QComboBox()
        self.demucs_model.addItems([
            "htdemucs", "htdemucs_ft", "htdemucs_6s", "hdemucs_mmi",
            "mdx", "mdx_extra", "mdx_q", "mdx_extra_q"])
        _add_row(dg, "Model", self.demucs_model,
                 "Which pre-trained Demucs model to use for separation.",
                 extended_desc="- htdemucs - Hybrid Transformer Demucs v4 (default). Fast, good quality. Trained on MusDB + 800 songs. 4 stems.\n- htdemucs_ft - Fine-tuned version. 4x slower but slightly better separation quality. Same training data.\n- htdemucs_6s - 6-source model. Adds guitar and piano stems on top of the standard 4. Piano quality is limited.\n- hdemucs_mmi - Hybrid Demucs v3 retrained. Slightly older architecture.\n- mdx / mdx_extra - Contest-winning models trained on MusDB HQ. 'extra' includes additional training data.\n- mdx_q / mdx_extra_q - Quantized (smaller download, slightly lower quality).")

        self.demucs_two_stems = QComboBox()
        self.demucs_two_stems.addItems(["(full separation)", "vocals", "drums", "bass", "other"])
        _add_row(dg, "Two-stems mode", self.demucs_two_stems,
                 "Separate into only two stems: the selected source vs. everything else. Set to '(full separation)' for all stems.",
                 extended_desc="Instead of producing 4 (or 6) separate stems, this produces just two: the named stem isolated, and everything else mixed together. For example, 'drums' produces drums.wav and no_drums.wav. 'vocals' is useful for karaoke-style isolation. Set to '(full separation)' to get all individual stems.\n\nFor bioacoustics: 'drums' can isolate percussive sounds (hand drums, clapping) from singing and other instruments.")

        self.demucs_other_method = QComboBox()
        self.demucs_other_method.addItems(["add", "minus", "none"])
        _add_row(dg, "Other-stem method", self.demucs_other_method,
                 "How to compute the 'no_<stem>' track when two-stems mode is active. Only used when two-stems is not '(full separation)'.",
                 extended_desc="When two-stems mode is active, Demucs produces the selected stem and a complementary 'no_<stem>' track. This setting controls how that complement is built:\n- add - Sum all remaining stems together (default, clean).\n- minus - Subtract the selected stem from the original mix (preserves phase but can add artefacts).\n- none - Don't save the complementary track at all.")

        self.demucs_device = QComboBox()
        self.demucs_device.addItems(["auto", "cpu", "cuda", "mps"])
        _add_row(dg, "Device", self.demucs_device,
                 "Computation device. 'auto' uses GPU if available, else CPU. 'mps' = Apple Silicon GPU (M1/M2/M3/M4).",
                 extended_desc="- auto - Automatically detects GPU (CUDA or MPS) availability and uses it if found, otherwise falls back to CPU.\n- cpu - Force CPU processing. Slower (~1.5x audio duration) but works everywhere and uses system RAM.\n- cuda - Force NVIDIA GPU processing. Much faster but requires an NVIDIA GPU with >=3 GB VRAM (7 GB recommended for default settings).\n- mps - Apple Silicon GPU (Metal Performance Shaders). Uses the GPU on M1/M2/M3/M4 Macs. Faster than CPU with no extra hardware needed.")

        self.demucs_shifts = QLineEdit("1")
        _add_row(dg, "Shifts", self.demucs_shifts,
                 "Number of random-shift predictions to average (shift trick). 1 = off (default). Higher = better quality but N x slower.",
                 extended_desc="The 'shift trick': run separation multiple times with random offsets and average the results. Reduces artefacts at segment boundaries. 1 = disabled (default, fastest). 2-5 = noticeable quality improvement. Only worth using with a GPU - each shift multiplies processing time. For CPU processing, leave at 1.")

        self.demucs_overlap = QLineEdit("0.25")
        _add_row(dg, "Overlap", self.demucs_overlap,
                 "Overlap between prediction windows (0.0-1.0). Default 0.25 (25%). Reduce to 0.1 for faster processing.",
                 extended_desc="Controls how much adjacent processing windows overlap. More overlap = smoother transitions between segments but slower. 0.25 (25%) is the default and works well for most cases. 0.1 (10%) speeds things up with minimal quality loss. 0.5+ is rarely needed.")

        self.demucs_segment_enabled = QCheckBox("Custom segment length")
        self.demucs_segment_enabled.setChecked(False)
        _add_checkbox(dg, self.demucs_segment_enabled,
            "Override the default segment length for splitting long files. Reduce to lower GPU memory usage.",
            "When enabled, splits audio into chunks of the specified length for processing. Smaller segments use less memory but may slightly reduce quality. The Hybrid Transformer models support a maximum of ~7.8 seconds per segment. Minimum recommended: 8 seconds.")

        self.demucs_segment = QLineEdit("10")
        _add_row(dg, "Segment length (s)", self.demucs_segment,
                 "Segment length in seconds for splitting long files. Reduce to save GPU memory. Min ~8s recommended.",
                 extended_desc="How many seconds of audio to process at once. Smaller values reduce peak memory usage (useful for GPUs with limited VRAM) but may reduce separation quality. 10 seconds is a good compromise. Note: Hybrid Transformer models (htdemucs*) have a maximum of ~7.8s - values above this are automatically clamped.")

        self.demucs_output_format = QComboBox()
        self.demucs_output_format.addItems([
            "wav-int16", "wav-int24", "wav-float32", "flac", "mp3"])
        _add_row(dg, "Output format", self.demucs_output_format,
                 "File format and bit depth for separated stems. Default: WAV 16-bit integer.",
                 extended_desc="- wav-int16 - Standard 16-bit WAV (default). Compact, widely compatible.\n- wav-int24 - 24-bit WAV. Higher dynamic range, ~1.5x larger.\n- wav-float32 - 32-bit float WAV. Full neural-network precision, 2x larger. Best when stems will undergo further processing.\n- flac - Lossless compressed. Same quality as WAV but ~60 % the size.\n- mp3 - Lossy compressed. Much smaller files but some quality loss.")

        self.demucs_mp3_bitrate = QLineEdit("320")
        _add_row(dg, "MP3 bitrate (kbps)", self.demucs_mp3_bitrate,
                 "Bitrate for MP3 output. 320 = highest quality. Only used when output format is 'mp3'.",
                 extended_desc="MP3 bitrate in kilobits per second. 320 kbps is CD-like quality. 256 and 192 are good for most purposes. Lower values save space but reduce audio quality. Only relevant when output format is set to 'mp3'.")

        self.demucs_clip_mode = QComboBox()
        self.demucs_clip_mode.addItems(["rescale", "clamp", "none"])
        _add_row(dg, "Clip mode", self.demucs_clip_mode,
                 "How to handle output clipping. 'rescale' adjusts volume, 'clamp' hard-clips at +/-1.0, 'none' = no clipping strategy.",
                 extended_desc="Separation can produce samples that exceed +/-1.0 due to reconstruction artefacts. 'rescale' (default) scales each stem's volume down to prevent clipping - safe but may change relative volumes between stems. 'clamp' hard-clips at +/-1.0 - preserves relative volumes but introduces distortion on peaks. 'none' leaves the raw output as-is (may clip when saving to integer formats).")

        self.demucs_jobs = QLineEdit("1")
        _add_row(dg, "Parallel jobs", self.demucs_jobs,
                 "Number of parallel separation jobs. Each job multiplies RAM usage. Default 1.",
                 extended_desc="Run multiple files in parallel. Each additional job uses roughly the same amount of RAM as the first, so be careful with memory. 2-4 jobs can speed up batch processing significantly on machines with enough RAM (16+ GB for 2 jobs, 32+ GB for 4 jobs). Leave at 1 for safety.")

        g.addWidget(self._demucs_details)
        self._demucs_details.setVisible(False)

        lay.addWidget(grp)

        grp = QGroupBox("② Channel & Resampling")
        g = QVBoxLayout(grp)
        self.channel = QComboBox()
        self.channel.addItems(["mix", "left", "right"])
        _add_row(g, "Channel", self.channel,
                 "For stereo recordings: 'mix' = average to mono (default), 'left' = left channel only, 'right' = right channel only.",
                 extended_desc="For stereo input files, determines how channels are combined. 'mix' averages both channels to mono (recommended - preserves all energy). 'left' or 'right' discards one channel entirely, which can help when one microphone was closer to the target or had less noise.")

        self.resample_enabled = QCheckBox("Enable resampling")
        self.resample_enabled.setChecked(False)
        _add_checkbox(g, self.resample_enabled,
            "Toggle resampling on or off. When off, each file keeps its native sample rate.",
            "Enables or disables sample-rate conversion. Turn this on when your recordings come from different devices with different sample rates and you want uniform FFT bin widths and onset timing across all files.")
        self.resample_hz = QLineEdit("44100")
        _add_row(g, "Resample (Hz)", self.resample_hz,
                 "Resample all output to this sample rate (Hz). 44100 recommended for consistency.",
                 extended_desc="Force all output files to a uniform sample rate. Different recorders may capture at 22050, 44100, 48000 Hz etc. Resampling to a common rate (e.g. 44100) ensures consistent FFT bin widths and onset timing across files.")
        prl = PresetReasonLabel("MUTER_RESAMPLE_HZ")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_RESAMPLE_HZ"] = prl
        lay.addWidget(grp)

        grp = QGroupBox("③ Frequency Filters")
        g = QVBoxLayout(grp)

        self.highpass_enabled = QCheckBox("Enable high-pass filter")
        self.highpass_enabled.setChecked(True)
        _add_checkbox(g, self.highpass_enabled,
            "Toggle high-pass filtering on or off.",
            "Enables or disables the high-pass filter. When disabled, no low-frequency content is removed. Turn this off if your target species produces important low-frequency sounds (e.g. whale moans, elephant rumbles).")
        self.highpass_hz = QLineEdit("200")
        _add_row(g, "High-pass cutoff (Hz)", self.highpass_hz,
                 "High-pass filter cutoff (Hz). Removes low-frequency rumble. 80 = percussion, 200 = general, 500 = birdsong, 1000 = insects.",
                 extended_desc="Butterworth high-pass filter applied first, before all other processing. Removes energy below this frequency (wind noise, traffic rumble, microphone handling). 0 disables the filter entirely. 80 Hz preserves bass drum content; 200 Hz is safe for most animal vocalizations; 500 Hz targets birdsong specifically; 1000+ Hz isolates insect stridulations.")
        prl = PresetReasonLabel("MUTER_HIGHPASS_HZ")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_HIGHPASS_HZ"] = prl

        self.lowpass_enabled = QCheckBox("Enable low-pass filter")
        self.lowpass_enabled.setChecked(False)
        _add_checkbox(g, self.lowpass_enabled,
            "Toggle low-pass filtering on or off.",
            "Enables or disables the low-pass filter. When disabled, no high-frequency content is removed. Turn this on to suppress equipment hiss, ultrasonic artefacts, or high-pitched interference above your species' vocal range.")
        self.lowpass_hz = QLineEdit("8000")
        _add_row(g, "Low-pass cutoff (Hz)", self.lowpass_hz,
                 "Low-pass filter cutoff (Hz). Removes high-frequency noise. 2000 = whale/elephant, 8000 = birdsong, 10000 = general.",
                 extended_desc="Butterworth low-pass filter. Removes energy above this frequency - useful for suppressing equipment hiss, high-pitched insect interference, or ultrasonic artefacts. Set to 2000 Hz for low-frequency species (whales, elephants), 8000 Hz to bracket birdsong, or 10000 Hz for general cleanup.")
        prl = PresetReasonLabel("MUTER_LOWPASS_HZ")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_LOWPASS_HZ"] = prl

        self.notch_enabled = QCheckBox("Enable notch filter")
        self.notch_enabled.setChecked(False)
        _add_checkbox(g, self.notch_enabled,
            "Toggle notch filtering on or off.",
            "Enables or disables notch filtering. Turn this on when your recordings have a specific tonal interference (e.g. 50/60 Hz mains hum from power lines).")
        self.notch_freqs = QLineEdit("50 60")
        _add_row(g, "Notch filter (Hz)", self.notch_freqs,
                 "Notch filter: surgically remove specific interference frequencies (e.g. 50/60 Hz power hum). Enter one or more Hz values separated by spaces.",
                 extended_desc="Removes precise tonal interference at the specified frequencies. Enter one or more space-separated values (e.g. '50 60 120' to remove mains hum and its first harmonic). Leave blank to disable.")

        self.notch_q = QLineEdit("30")
        _add_row(g, "Notch Q factor", self.notch_q,
                 "Quality factor for notch filter(s). Higher = narrower notch. 30 = power hum, 10-15 = broader tonal interference.",
                 extended_desc="Controls the bandwidth of each notch. Q=30 produces a very narrow notch (~1-2 Hz wide at 50 Hz) - ideal for mains hum. Q=10-15 removes a wider band, useful when the interference frequency wobbles or has sidebands.")

        self.pre_emphasis_enabled = QCheckBox("Enable pre-emphasis")
        self.pre_emphasis_enabled.setChecked(False)
        _add_checkbox(g, self.pre_emphasis_enabled,
            "Toggle pre-emphasis filtering on or off.",
            "Enables or disables the pre-emphasis filter. Turn this on when distant or outdoor recordings sound muffled, to compensate for the natural high-frequency roll-off caused by distance between source and microphone.")
        self.pre_emphasis = QLineEdit("0.97")
        _add_row(g, "Pre-emphasis", self.pre_emphasis,
                 "Pre-emphasis coefficient (0.0-1.0). Boosts high frequencies to compensate for distance roll-off. 0.97 = standard.",
                 extended_desc="Applies a first-order pre-emphasis filter: y[n] = x[n] - coeff·x[n-1]. Tilts the spectrum toward higher frequencies to compensate for the natural high-frequency roll-off caused by distance between source and microphone. 0.97 is standard for speech/vocalization enhancement.")
        prl = PresetReasonLabel("MUTER_PRE_EMPHASIS")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_PRE_EMPHASIS"] = prl
        lay.addWidget(grp)

        grp = QGroupBox("④ Bandpass Boost")
        g = QVBoxLayout(grp)
        self.bandpass_boost = QCheckBox("Enable bandpass boost")
        self.bandpass_boost.setChecked(False)
        _add_checkbox(g, self.bandpass_boost,
            "Amplify a specific frequency band to make target species' calls more prominent. Positive counterpart to high-pass: boosts wanted frequencies instead of cutting unwanted ones.",
            "Instead of removing unwanted frequencies, this amplifies a specific band where your target species vocalizes. For example, boosting 1000-4000 Hz for birdsong makes calls louder relative to out-of-band noise without removing any audio content.")
        prl = PresetReasonLabel("MUTER_BANDPASS_BOOST")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_BANDPASS_BOOST"] = prl

        self.boost_low_hz = QLineEdit("300")
        _add_row(g, "Boost low (Hz)", self.boost_low_hz,
                 "Lower edge (Hz) of the frequency band to boost.",
                 extended_desc="The lower boundary of the band to amplify. Set this to just below the fundamental frequency of your target species' vocalisation.")
        prl = PresetReasonLabel("MUTER_BOOST_LOW_HZ")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_BOOST_LOW_HZ"] = prl

        self.boost_high_hz = QLineEdit("3000")
        _add_row(g, "Boost high (Hz)", self.boost_high_hz,
                 "Upper edge (Hz) of the frequency band to boost.",
                 extended_desc="The upper boundary of the band to amplify. Set this to just above the highest harmonic of your target vocalisation.")
        prl = PresetReasonLabel("MUTER_BOOST_HIGH_HZ")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_BOOST_HIGH_HZ"] = prl

        self.boost_gain_db = QLineEdit("6.0")
        _add_row(g, "Boost gain (dB)", self.boost_gain_db,
                 "How many dB to boost the target frequency band. 3 = subtle, 6 = moderate, 12 = strong.",
                 extended_desc="How much louder to make the target band. 3 dB ~= 'just noticeable', 6 dB ~= doubling perceived loudness, 12 dB is very strong. Higher values risk clipping - pair with normalization to prevent distortion.")
        prl = PresetReasonLabel("MUTER_BOOST_GAIN_DB")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_BOOST_GAIN_DB"] = prl
        lay.addWidget(grp)

        grp = QGroupBox("⑤ Harmonic-Percussive Source Separation (HPSS)")
        g = QVBoxLayout(grp)
        self.hpss_enabled = QCheckBox("Enable HPSS")
        self.hpss_enabled.setChecked(False)
        _add_checkbox(g, self.hpss_enabled,
            "Decompose audio into harmonic (sustained tones) and percussive (sharp transients) components before muting.",
            "Uses librosa HPSS to split the signal into two tracks based on spectral structure rather than volume. Harmonic = smooth, continuous sounds (bird calls, whale moans, wind). Percussive = sharp onsets (primate drumming, insect clicks, human clapping). Solves the problem where background noise is the same volume as the target call. Both component tracks are saved for auditing; the selected target component is passed through to later stages. Preserves the global timeline.")
        prl = PresetReasonLabel("MUTER_HPSS_ENABLED")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_HPSS_ENABLED"] = prl

        self.hpss_target = QComboBox()
        self.hpss_target.addItems(["percussive", "harmonic", "both"])
        _add_row(g, "HPSS target component", self.hpss_target,
                 "Which component to keep for onset extraction.",
                 extended_desc="'percussive' = sharp transients (primate drumming, insect clicks, human percussion). 'harmonic' = sustained tones (bird song, whale moans, tonal calls). 'both' = keep the full signal unchanged, just export the component tracks for manual auditing.")
        prl = PresetReasonLabel("MUTER_HPSS_TARGET")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_HPSS_TARGET"] = prl

        self.hpss_margin = QLineEdit("2.0")
        _add_row(g, "HPSS margin", self.hpss_margin,
                 "Separation softness. 1.0 = soft, 2.0 = moderate, 4.0 = hard.",
                 extended_desc="Controls how aggressively the harmonic and percussive components are separated. 1.0 = soft split (components overlap, preserves more signal). 2.0 = moderate (good default). 4.0+ = hard split (very clean separation but may lose quieter signal elements).")
        prl = PresetReasonLabel("MUTER_HPSS_MARGIN")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_HPSS_MARGIN"] = prl

        self.hpss_emphasis_db = QLineEdit("0")
        _add_row(g, "HPSS emphasis (dB)", self.hpss_emphasis_db,
                 "Boost the target HPSS component by this many dB instead of isolating it. 0 = isolate (default), 3-9 = emphasis mode.",
                 extended_desc="Instead of discarding the non-target component entirely (isolation mode), this option keeps the full signal and boosts the target component by the specified dB amount. Set to 0 for classic isolation. 3-6 dB is a gentle emphasis; 9+ dB strongly highlights the target while retaining natural context.")
        prl = PresetReasonLabel("MUTER_HPSS_EMPHASIS_DB")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_HPSS_EMPHASIS_DB"] = prl

        lay.addWidget(grp)

        grp = QGroupBox("⑥ Spectral Denoising")
        g = QVBoxLayout(grp)
        self.spectral_denoise = QCheckBox("Enable spectral denoising")
        self.spectral_denoise.setChecked(True)
        _add_checkbox(g, self.spectral_denoise,
            "Suppress persistent tonal background sounds (cicadas, hum, hiss) via spectral gating before amplitude muting.",
            "Applies spectral gating (noisereduce library) to subtract stationary noise before the amplitude-based muting step. Effective against constant tones like cicada chorus, electrical hum, or tape hiss. Strength is controlled by the Denoise strength slider below. Adds ~1-2 s per file.")
        prl = PresetReasonLabel("MUTER_SPECTRAL_DENOISE")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_SPECTRAL_DENOISE"] = prl

        self.denoise_strength = QLineEdit("1.5")
        _add_row(g, "Denoise strength", self.denoise_strength,
                 "Spectral denoise aggressiveness. 1.0 = conservative, 1.5 = moderate (default), 2.0 = very aggressive.",
                 extended_desc="Multiplier applied to the spectral gate threshold estimated from the noise profile. 1.0 removes only the most obvious stationary noise and preserves weak signals. 1.5 is a good all-around value. 2.0 or above removes more noise but may introduce musical artifacts (warbling). Values above 2.5 are not recommended.")
        prl = PresetReasonLabel("MUTER_DENOISE_STRENGTH")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_DENOISE_STRENGTH"] = prl
        lay.addWidget(grp)

        grp = QGroupBox("⑦ Spectral Enhancement")
        g = QVBoxLayout(grp)
        self.spectral_enhance = QCheckBox("Enable spectral enhancement")
        self.spectral_enhance.setChecked(False)
        _add_checkbox(g, self.spectral_enhance,
            "Amplify spectral peaks that deviate from the stationary background. Positive counterpart to spectral denoising: lifts signal up instead of pushing noise down.",
            "While spectral denoising subtracts the stationary noise floor, spectral enhancement takes the opposite approach: it amplifies parts of the spectrum that rise above the background. The effect is increased signal-to-noise ratio by making target sounds louder rather than making noise quieter.")
        prl = PresetReasonLabel("MUTER_SPECTRAL_ENHANCE")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_SPECTRAL_ENHANCE"] = prl

        self.enhance_factor = QLineEdit("2.0")
        _add_row(g, "Enhance factor", self.enhance_factor,
                 "How much to amplify spectral peaks above background. 1.0 = no change, 2.0 = double, 4.0 = aggressive.",
                 extended_desc="Multiplier applied to spectral energy that exceeds the estimated background level. 1.0 = no change. 2.0 doubles the signal's prominence above the noise floor. 4.0+ is very aggressive and may introduce artefacts - use with normalization.")
        prl = PresetReasonLabel("MUTER_ENHANCE_FACTOR")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_ENHANCE_FACTOR"] = prl
        lay.addWidget(grp)

        grp = QGroupBox("⑧ Dynamic Compression")
        g = QVBoxLayout(grp)
        self.compress = QCheckBox("Enable dynamic compression")
        self.compress.setChecked(False)
        _add_checkbox(g, self.compress,
            "Boost quiet audio toward a threshold. Positive counterpart to dB muting: amplifies quiet parts instead of silencing them.",
            "Applies upward compression: audio segments below the threshold are boosted toward it. This is the positive counterpart to amplitude muting - instead of silencing quiet regions, it makes them louder, bringing distant or faint vocalizations closer to the volume of nearby ones.")
        prl = PresetReasonLabel("MUTER_COMPRESS")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_COMPRESS"] = prl

        self.compress_ratio = QLineEdit("3.0")
        _add_row(g, "Compression ratio", self.compress_ratio,
                 "Compression ratio. Higher = more aggressive levelling. 2.0 = gentle, 3.0 = moderate, 6.0+ = heavy.",
                 extended_desc="Determines how aggressively quiet sounds are boosted. A 2:1 ratio means sounds 10 dB below threshold are boosted by 5 dB; 3:1 boosts them by ~6.7 dB; 6:1 brings them up by ~8.3 dB. Higher ratios produce a more uniform volume at the cost of naturalness.")
        prl = PresetReasonLabel("MUTER_COMPRESS_RATIO")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_COMPRESS_RATIO"] = prl

        self.compress_threshold_db = QLineEdit("-30")
        _add_row(g, "Threshold (dBFS)", self.compress_threshold_db,
                 "Threshold (dBFS) below which quiet audio is boosted. Default -30.",
                 extended_desc="Sounds quieter than this level (in dBFS) get boosted by the compressor. Sounds louder than this are left alone. -30 dBFS is a good starting point for field recordings. -20 dBFS is more conservative.")
        prl = PresetReasonLabel("MUTER_COMPRESS_THRESHOLD_DB")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_COMPRESS_THRESHOLD_DB"] = prl
        lay.addWidget(grp)

        grp = QGroupBox("⑨ Transient Sharpening")
        g = QVBoxLayout(grp)
        self.sharpen_transients = QCheckBox("Enable transient sharpening")
        self.sharpen_transients.setChecked(False)
        _add_checkbox(g, self.sharpen_transients,
            "Boost the attack portion of each detected onset. Positive counterpart to crossfade: emphasises edges instead of softening them.",
            "Detects onset events and boosts the first few milliseconds of each one, making attacks crisper and more detectible by the downstream onset finder. The positive counterpart to crossfade smoothing: it sharpens transient edges rather than softening them.")
        prl = PresetReasonLabel("MUTER_SHARPEN_TRANSIENTS")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_SHARPEN_TRANSIENTS"] = prl

        self.sharpen_gain_db = QLineEdit("6")
        _add_row(g, "Sharpen gain (dB)", self.sharpen_gain_db,
                 "How many dB to boost the attack of each onset. Default 6.",
                 extended_desc="How much extra dB each onset attack receives. 3 dB is subtle sharpening; 6 dB is a noticeable boost; 12+ dB makes onsets dramatically louder. Very high values may cause clipping - combine with normalization.")
        prl = PresetReasonLabel("MUTER_SHARPEN_GAIN_DB")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_SHARPEN_GAIN_DB"] = prl

        self.sharpen_attack_ms = QLineEdit("15")
        _add_row(g, "Attack window (ms)", self.sharpen_attack_ms,
                 "Duration (ms) of the attack window to boost at each onset. Default 15.",
                 extended_desc="How long the attack boost lasts, starting at each detected onset. 5 ms boosts only the very first crack of the transient. 15 ms (default) covers a natural attack envelope. 30+ ms extends into the sustain portion of each event.")
        prl = PresetReasonLabel("MUTER_SHARPEN_ATTACK_MS")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_SHARPEN_ATTACK_MS"] = prl
        lay.addWidget(grp)

        grp = QGroupBox("⑩ Amplitude Muting")
        g = QVBoxLayout(grp)

        self.auto_threshold = QCheckBox("Adaptive threshold")
        self.auto_threshold.setChecked(True)
        _add_checkbox(g, self.auto_threshold,
            "When enabled, estimates each file's noise floor and sets the muting threshold dynamically instead of using a fixed dB value.",
            "Analyses a quiet section of each audio file to estimate the noise floor, then sets the muting cutoff relative to that floor (controlled by Noise margin). Disable to use the Fixed dB threshold instead. Recommended ON for field recordings where noise levels vary between files.")
        prl = PresetReasonLabel("MUTER_AUTO_THRESHOLD")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_AUTO_THRESHOLD"] = prl

        self.db_threshold = QLineEdit("30")
        _add_row(g, "Fixed dB threshold", self.db_threshold,
                 "How far below peak volume (dB) is considered noise. 20-25 = clean studio, 30 = general, 35-40 = noisy field. Only used when Adaptive Threshold is off.",
                 extended_desc="Segments whose RMS amplitude is more than this many decibels below the file's peak are muted. Lower values = more aggressive (mutes more audio). 20-25 dB suits clean studio/lab recordings; 30 dB is a safe general-purpose value; 35-40 dB preserves quieter signals in very noisy field recordings. Ignored when Adaptive threshold is ON.")
        prl = PresetReasonLabel("MUTER_DB_THRESHOLD")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_DB_THRESHOLD"] = prl

        self.noise_margin = QLineEdit("6.0")
        _add_row(g, "Noise margin (dB)", self.noise_margin,
                 "dB above the estimated noise floor to set the muting cutoff. Only used when Adaptive Threshold is on. 4 = aggressive, 6 = moderate, 10 = permissive.",
                 extended_desc="After the adaptive algorithm estimates the noise floor, this margin is added to set the muting cutoff. A small margin (4 dB) aggressively mutes anything close to the noise floor; a large margin (10 dB) preserves quieter intentional sounds but may leave some noise. 6 dB is a safe default. Only used when Adaptive threshold is ON.")
        prl = PresetReasonLabel("MUTER_NOISE_MARGIN_DB")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_NOISE_MARGIN_DB"] = prl

        self.save_profile = QCheckBox("Save noise profile JSON")
        self.save_profile.setChecked(True)
        _add_checkbox(g, self.save_profile,
            "Save a JSON noise profile alongside each cleaned file. Useful for auditing the muter's decisions.",
            "Writes a JSON sidecar containing the estimated noise floor (dB), chosen muting threshold, and basic file statistics. Useful for debugging or comparing noise conditions across recordings. Has negligible performance cost.")

        lay.addWidget(grp)

        grp = QGroupBox("⑪ Crossfade")
        g = QVBoxLayout(grp)
        self.fade_enabled = QCheckBox("Enable crossfade")
        self.fade_enabled.setChecked(True)
        _add_checkbox(g, self.fade_enabled,
            "Toggle crossfade smoothing on or off.",
            "Enables or disables the crossfade at mute/unmute boundaries. When enabled, transitions are smoothed to prevent false onset detections. Recommended ON for most use cases.")
        self.fade_ms = QLineEdit("5.0")
        _add_row(g, "Fade duration (ms)", self.fade_ms,
                 "Crossfade duration (ms) at mute boundaries. Prevents false onset detections from hard silence edges. 5 ms recommended.",
                 extended_desc="Applies a linear crossfade at each mute/unmute boundary so that transitions are smooth. Without crossfade, the abrupt jump from silence to signal can itself be detected as a false onset. 5 ms is fast enough to be inaudible while preventing artifacts. Increase to 10 ms for very sensitive detectors.")
        prl = PresetReasonLabel("MUTER_FADE_MS")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_FADE_MS"] = prl
        lay.addWidget(grp)

        grp = QGroupBox("⑫ Normalization & Trimming")
        g = QVBoxLayout(grp)
        self.normalize = QComboBox()
        self.normalize.addItems(["None", "peak", "rms"])
        _add_row(g, "Normalize", self.normalize,
                 "Normalize audio levels after all processing. 'peak' = max sample to target. 'rms' = RMS energy to target. None = disabled.",
                 extended_desc="Standardises the output volume of every file so they can be compared fairly. 'peak' scales so the loudest sample hits the target level. 'rms' scales so the average energy matches the target - better for comparing perceived loudness. 'None' leaves levels as-is.")
        prl = PresetReasonLabel("MUTER_NORMALIZE")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_NORMALIZE"] = prl

        self.normalize_target_db = QLineEdit("-1.0")
        _add_row(g, "Target level (dBFS)", self.normalize_target_db,
                 "Target level in dBFS for normalization. -1.0 = near-max with headroom. -3.0 = conservative.",
                 extended_desc="The target dBFS for normalization. -1.0 leaves 1 dB of headroom below digital full scale (prevents clipping on lossy codecs). -3.0 is more conservative. Only used when Normalize is set to 'peak' or 'rms'.")
        prl = PresetReasonLabel("MUTER_NORMALIZE_TARGET_DB")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_NORMALIZE_TARGET_DB"] = prl

        self.trim_silence = QCheckBox("Trim leading/trailing silence")
        self.trim_silence.setChecked(False)
        _add_checkbox(g, self.trim_silence,
            "Trim leading and trailing silence from output. Internal timing preserved.",
            "Removes dead silence from the very start and end of each output file. This only affects edges - internal timing and event positions are preserved. Useful for recordings with long pre-roll or post-roll silence.")
        prl = PresetReasonLabel("MUTER_TRIM_SILENCE")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_TRIM_SILENCE"] = prl

        self.trim_threshold_db = QLineEdit("40")
        _add_row(g, "Trim threshold (dB)", self.trim_threshold_db,
                 "dB threshold for edge silence detection. Audio below this at edges is trimmed. Default 40.",
                 extended_desc="Samples quieter than this many dB below peak at the edges are considered silence and trimmed. 40 dB is conservative (only removes very quiet edges). Lower values (20-30 dB) trim more aggressively.")
        lay.addWidget(grp)

        grp = QGroupBox("⑬ MFCC Template Matching")
        g = QVBoxLayout(grp)

        self.mfcc_enabled = QCheckBox("Enable MFCC template matching")
        self.mfcc_enabled.setChecked(False)
        _add_checkbox(g, self.mfcc_enabled,
            "Apply MFCC sliding-window template matching to suppress non-target sounds.",
            "Uses MFCC fingerprints extracted from the Focus Signal (positive) regions you defined in the Onset Editor to build a template, then attenuates all sections of the recording that do not closely match that template. Effective for isolating a specific call type against broadband noise or other competing sounds.")
        prl = PresetReasonLabel("MUTER_MFCC_ENABLED")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_MFCC_ENABLED"] = prl

        self.mfcc_template_paths = QPlainTextEdit()
        self.mfcc_template_paths.setPlaceholderText(
            "One absolute file path per line (WAV/FLAC).\n"
            "Leave blank to pick up any *_focusSignal.wav files saved alongside the input audio."
        )
        self.mfcc_template_paths.setFixedHeight(72)
        _add_row(g, "Template file(s)", self.mfcc_template_paths,
                 "Path(s) to short audio excerpts that represent the target signal. One path per line. Leave blank to auto-detect *_focusSignal.wav files.",
                 extended_desc="Each file should contain a clean example of the sound you want to keep (e.g., a single drum beat, a clean call). The algorithm computes MFCCs for each template and retains only those frames of the recording that match at least one template within the chosen threshold.")
        prl = PresetReasonLabel("MUTER_MFCC_TEMPLATE_PATHS")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_MFCC_TEMPLATE_PATHS"] = prl

        self.mfcc_threshold = QLineEdit("15.0")
        _add_row(g, "Threshold percentile (%)", self.mfcc_threshold,
                 "Lower = more selective (keeps fewer frames). Higher = more permissive (keeps more frames). Default 15.",
                 extended_desc="Frames whose MFCC distance from all templates exceeds this percentile of all distances are set to zero. At 15 % only the 15 % of frames closest to a template are retained - good for sparse, clear signals. Raise towards 50 % if too much of the target is being removed.")
        prl = PresetReasonLabel("MUTER_MFCC_THRESHOLD_PERCENTILE")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_MFCC_THRESHOLD_PERCENTILE"] = prl

        self.mfcc_smooth_ms = QLineEdit("50.0")
        _add_row(g, "Mask smoothing (ms)", self.mfcc_smooth_ms,
                 "Gaussian smoothing applied to the binary keep/mute mask in milliseconds. Prevents abrupt cuts. Default 50 ms.",
                 extended_desc="A gaussian_filter1d kernel proportional to this duration is applied to the 0/1 mask before it is multiplied against the audio. Larger values produce longer fade-ins/outs around kept regions, reducing audible clicks but slightly blurring the mask edges.")
        prl = PresetReasonLabel("MUTER_MFCC_SMOOTH_MS")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_MFCC_SMOOTH_MS"] = prl

        self.mfcc_n_mfcc = QLineEdit("13")
        _add_row(g, "MFCC coefficients", self.mfcc_n_mfcc,
                 "Number of MFCC coefficients used to characterise each frame. 13 is standard. Increase (up to ~40) for more discriminative fingerprints.",
                 extended_desc="More coefficients capture finer spectral detail but increase computation time and risk over-fitting to the template. 13 is the conventional value for speaker/sound recognition tasks. Values in the range 13-20 are recommended for most bioacoustics use-cases.")
        prl = PresetReasonLabel("MUTER_MFCC_N_MFCC")
        g.addWidget(prl)
        self._preset_reason_labels["MUTER_MFCC_N_MFCC"] = prl

        lay.addWidget(grp)

        circ = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬"
        self._proc_grps = []
        self._proc_base_titles = []
        for i in range(lay.count()):
            item = lay.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, QGroupBox) and widget.title() and widget.title()[0] in circ:
                self._proc_grps.append(widget)
                self._proc_base_titles.append(widget.title()[2:].strip())

        self._n_proc = len(self._proc_grps)
        self._proc_order = list(range(self._n_proc))
        self._proc_spins = {}
        self._updating_proc_order = False

        for idx, proc_group in enumerate(self._proc_grps):
            proc_group._proc_idx = idx
            group_layout = proc_group.layout()
            if not group_layout:
                continue
            order_row = QHBoxLayout()
            order_row.setContentsMargins(0, 0, 0, 4)
            order_row.setSpacing(4)
            order_label = QLabel("Step order:")
            order_label.setStyleSheet(
                f"color: {_TEXT_DIM}; font-size: 10px; background: transparent;")
            order_spin = QSpinBox()
            order_spin.setRange(1, self._n_proc)
            order_spin.setValue(idx + 1)
            order_spin.setFixedWidth(40)
            order_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            order_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            order_spin.setToolTip("Processing step order - type to reorder")
            order_spin.setStyleSheet(
                f"QSpinBox {{ background: {_BG_WIDGET}; color: {_TEXT}; border: 1px solid {_BORDER}; border-radius: 3px; padding: 1px; font-size: 10px; font-weight: 600; }}"
                f"QSpinBox:focus {{ border-color: {_ACCENT}; }}")
            order_spin.valueChanged.connect(
                lambda value, i=idx: self._on_proc_order_changed(i, value))
            self._proc_spins[idx] = order_spin
            order_row.addWidget(order_label)
            order_row.addWidget(order_spin)
            order_row.addStretch()
            group_layout.insertLayout(0, order_row)

        self._reset_order_row = QHBoxLayout()
        self._reset_order_row.setContentsMargins(0, 0, 0, 0)
        self._reset_order_btn = QPushButton("Reset Step Order")
        self._reset_order_btn.setFixedHeight(28)
        self._reset_order_btn.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT_DIM}; border: 1px solid {_BORDER}; border-radius: 4px; padding: 2px 10px; font-size: 11px; }} "
            f"QPushButton:hover {{ border-color: {_ACCENT}; color: {_ACCENT}; }}")
        self._reset_order_btn.setToolTip("Restore default 1-12 processing order")
        self._reset_order_btn.clicked.connect(self._on_reset_proc_order)
        self._reset_order_row.addStretch()
        self._reset_order_row.addWidget(self._reset_order_btn)
        self._reset_order_row.addStretch()
        lay.addLayout(self._reset_order_row)

        lay.addStretch()
        self._content_layout = lay
        self.setWidget(content)

        self.demucs_enabled.stateChanged.connect(self._update_conditions)
        self.demucs_segment_enabled.stateChanged.connect(self._update_conditions)
        self.demucs_two_stems.currentTextChanged.connect(lambda _: self._update_conditions())
        self.demucs_output_format.currentTextChanged.connect(lambda _: self._update_conditions())
        self.resample_enabled.stateChanged.connect(self._update_conditions)
        self.highpass_enabled.stateChanged.connect(self._update_conditions)
        self.lowpass_enabled.stateChanged.connect(self._update_conditions)
        self.notch_enabled.stateChanged.connect(self._update_conditions)
        self.pre_emphasis_enabled.stateChanged.connect(self._update_conditions)
        self.auto_threshold.stateChanged.connect(self._update_conditions)
        self.spectral_denoise.stateChanged.connect(self._update_conditions)
        self.hpss_enabled.stateChanged.connect(self._update_conditions)
        self.bandpass_boost.stateChanged.connect(self._update_conditions)
        self.spectral_enhance.stateChanged.connect(self._update_conditions)
        self.compress.stateChanged.connect(self._update_conditions)
        self.sharpen_transients.stateChanged.connect(self._update_conditions)
        self.fade_enabled.stateChanged.connect(self._update_conditions)
        self.trim_silence.stateChanged.connect(self._update_conditions)
        self.normalize.currentTextChanged.connect(lambda _: self._update_conditions())
        self._update_conditions()

        self._register_perfile_indicators()

        self.input_folder.textChanged.connect(self._on_input_changed)
        self.specify_files_cb.stateChanged.connect(self._on_specify_files_toggled)
        self.output_folder.textChanged.connect(self._update_io_summary)

        self.demucs_enabled.stateChanged.connect(self._update_io_summary)
        self.demucs_model.currentTextChanged.connect(lambda _: self._update_io_summary())
        self.hpss_enabled.stateChanged.connect(self._update_io_summary)
        self.save_profile.stateChanged.connect(self._update_io_summary)
        self.spectral_denoise.stateChanged.connect(self._update_io_summary)
        self._update_io_summary()

    def _on_proc_order_changed(self, step_idx, new_val):
        if self._updating_proc_order:
            return
        old_pos = self._proc_order.index(step_idx)
        new_pos = max(0, min(new_val - 1, self._n_proc - 1))
        if new_pos == old_pos:
            return
        order = list(self._proc_order)
        order.pop(old_pos)
        order.insert(new_pos, step_idx)
        self._proc_order = order
        self._sync_proc_order()

    def _sync_proc_order(self):
        circ = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"
        self._updating_proc_order = True
        for vis_pos, step_idx in enumerate(self._proc_order):
            self._proc_spins[step_idx].setValue(vis_pos + 1)
            num = circ[vis_pos] if vis_pos < len(circ) else str(vis_pos + 1)
            self._proc_grps[step_idx].setTitle(
                f"{num} {self._proc_base_titles[step_idx]}")
        self._updating_proc_order = False
        self._relayout_proc_groups()

    def _relayout_proc_groups(self):
        layout = self._content_layout
        for proc_group in self._proc_grps:
            layout.removeWidget(proc_group)
        for insert_pos, step_idx in enumerate(self._proc_order):
            layout.insertWidget(2 + insert_pos, self._proc_grps[step_idx])

    def _on_reset_proc_order(self):
        self._proc_order = list(range(self._n_proc))
        self._sync_proc_order()

    def get_proc_order(self):
        return list(self._proc_order)

    def set_proc_order(self, order_list):
        if (len(order_list) == self._n_proc
                and sorted(order_list) == list(range(self._n_proc))):
            self._proc_order = list(order_list)
            self._sync_proc_order()

    def _save_as_preset(self):
        _export_settings_for(self, "Audio Editor")

    def save_settings_if_enabled(self):
        return _save_settings_if_enabled(self)

    def _on_muter_preset_changed(self, name):
        for label in self._preset_reason_labels.values():
            label.hide()
        self._preset_desc.hide()

        if name == "None" or name not in self._muter_presets:
            return

        preset = self._muter_presets[name]
        self._preset_desc.setText(preset.get("description", ""))
        self._preset_desc.show()

        self.channel.setCurrentText(str(preset.get("MUTER_CHANNEL", "mix")))
        resample_val = int(preset.get("MUTER_RESAMPLE_HZ", 0))
        self.resample_enabled.setChecked(resample_val > 0)
        if resample_val > 0:
            self.resample_hz.setText(str(resample_val))
        highpass_val = int(preset["MUTER_HIGHPASS_HZ"])
        self.highpass_enabled.setChecked(highpass_val > 0)
        if highpass_val > 0:
            self.highpass_hz.setText(str(highpass_val))
        lowpass_val = int(preset.get("MUTER_LOWPASS_HZ", 0))
        self.lowpass_enabled.setChecked(lowpass_val > 0)
        if lowpass_val > 0:
            self.lowpass_hz.setText(str(lowpass_val))
        notch = preset.get("MUTER_NOTCH_FREQS", [])
        self.notch_enabled.setChecked(bool(notch))
        if notch:
            self.notch_freqs.setText(" ".join(str(freq) for freq in notch))
        self.notch_q.setText(str(preset.get("MUTER_NOTCH_Q", 30)))
        pre_emphasis_val = float(preset.get("MUTER_PRE_EMPHASIS", 0.0))
        self.pre_emphasis_enabled.setChecked(pre_emphasis_val > 0)
        if pre_emphasis_val > 0:
            self.pre_emphasis.setText(str(pre_emphasis_val))
        self.bandpass_boost.setChecked(bool(preset.get("MUTER_BANDPASS_BOOST", False)))
        self.boost_low_hz.setText(str(preset.get("MUTER_BOOST_LOW_HZ", 300)))
        self.boost_high_hz.setText(str(preset.get("MUTER_BOOST_HIGH_HZ", 3000)))
        self.boost_gain_db.setText(str(preset.get("MUTER_BOOST_GAIN_DB", 6.0)))
        self.hpss_enabled.setChecked(preset["MUTER_HPSS_ENABLED"])
        self.hpss_target.setCurrentText(preset["MUTER_HPSS_TARGET"])
        self.hpss_margin.setText(str(preset["MUTER_HPSS_MARGIN"]))
        self.hpss_emphasis_db.setText(str(preset.get("MUTER_HPSS_EMPHASIS_DB", 0)))
        self.spectral_denoise.setChecked(preset["MUTER_SPECTRAL_DENOISE"])
        self.denoise_strength.setText(str(preset["MUTER_DENOISE_STRENGTH"]))
        self.spectral_enhance.setChecked(bool(preset.get("MUTER_SPECTRAL_ENHANCE", False)))
        self.enhance_factor.setText(str(preset.get("MUTER_ENHANCE_FACTOR", 2.0)))
        self.compress.setChecked(bool(preset.get("MUTER_COMPRESS", False)))
        self.compress_ratio.setText(str(preset.get("MUTER_COMPRESS_RATIO", 3.0)))
        self.compress_threshold_db.setText(str(preset.get("MUTER_COMPRESS_THRESHOLD_DB", -30)))
        self.sharpen_transients.setChecked(bool(preset.get("MUTER_SHARPEN_TRANSIENTS", False)))
        self.sharpen_gain_db.setText(str(preset.get("MUTER_SHARPEN_GAIN_DB", 6)))
        self.sharpen_attack_ms.setText(str(preset.get("MUTER_SHARPEN_ATTACK_MS", 15)))
        self.auto_threshold.setChecked(preset["MUTER_AUTO_THRESHOLD"])
        self.noise_margin.setText(str(preset["MUTER_NOISE_MARGIN_DB"]))
        self.db_threshold.setText(str(preset["MUTER_DB_THRESHOLD"]))
        fade_val = float(preset["MUTER_FADE_MS"])
        self.fade_enabled.setChecked(fade_val > 0)
        if fade_val > 0:
            self.fade_ms.setText(str(fade_val))
        normalize_val = preset.get("MUTER_NORMALIZE")
        self.normalize.setCurrentText("None" if normalize_val is None else str(normalize_val))
        self.normalize_target_db.setText(str(preset.get("MUTER_NORMALIZE_TARGET_DB", -1.0)))
        self.trim_silence.setChecked(bool(preset.get("MUTER_TRIM_SILENCE", False)))
        self.trim_threshold_db.setText(str(preset.get("MUTER_TRIM_THRESHOLD_DB", 40)))
        self.mfcc_enabled.setChecked(bool(preset.get("MUTER_MFCC_ENABLED", False)))
        mfcc_paths = preset.get("MUTER_MFCC_TEMPLATE_PATHS", [])
        self.mfcc_template_paths.setPlainText(
            "\n".join(mfcc_paths) if mfcc_paths else ""
        )
        self.mfcc_threshold.setText(str(preset.get("MUTER_MFCC_THRESHOLD_PERCENTILE", 15.0)))
        self.mfcc_smooth_ms.setText(str(preset.get("MUTER_MFCC_SMOOTH_MS", 50.0)))
        self.mfcc_n_mfcc.setText(str(preset.get("MUTER_MFCC_N_MFCC", 13)))

        reasons = self._muter_preset_reasons.get(name, {})
        for key, reason_text in reasons.items():
            preset_reason_label = self._preset_reason_labels.get(key)
            if preset_reason_label:
                preset_reason_label.setText(f"* Preset: {reason_text}")
                preset_reason_label.show()

        self._update_conditions()

    def _on_input_changed(self, text):
        self.selected_files_combo.set_folder(text)
        if self.specify_files_cb.isChecked():
            self.selected_files_combo.ensure_first_selected()
        if self._output_auto_cb.isChecked():
            cfg = self._output_auto_cb.auto_config
            src = cfg.get("source_step", "(this step)")
            if src in ("(this step)", "Audio Editor") and cfg.get("source_io") == "input":
                resolved = _resolve_auto_config(text, cfg)
                if resolved:
                    self.output_folder.setText(resolved)
        self._update_io_summary()

    def _on_specify_files_toggled(self, state):
        enabled = bool(state)
        self.selected_files_combo.setEnabled(enabled)
        if enabled:
            self.selected_files_combo.set_folder(self.input_folder.text())
            self.selected_files_combo.ensure_first_selected()

    def _on_output_auto_toggled(self, state):
        if bool(state):
            self._on_input_changed(self.input_folder.text())

    def _update_io_summary(self):
        lines = ["<b>Reads:</b> .wav, .mp3, .flac, .ogg audio files"]
        out = ["<b>Produces:</b>"]
        out.append("- Cleaned .wav files -> Output folder")
        out.append("- Rejected-noise .wav files -> ..._rejected_noise/")
        if self.hpss_enabled.isChecked():
            out.append("- HPSS harmonic .wav -> ..._hpss_harmonic/")
            out.append("- HPSS percussive .wav -> ..._hpss_percussive/")
        if self.demucs_enabled.isChecked():
            model = self.demucs_model.currentText()
            if "6s" in model:
                out.append("- Demucs stems (drums, bass, vocals, other, guitar, piano) -> ..._demucs_stems/")
            else:
                out.append("- Demucs stems (drums, bass, vocals, other) -> ..._demucs_stems/")
        if self.save_profile.isChecked():
            out.append("- Noise profile .json files -> Output folder")
        self._io_summary.setText("<br>".join(lines + out))

    def _update_conditions(self):
        demucs_on = self.demucs_enabled.isChecked()
        self._demucs_details.setVisible(demucs_on)
        self.demucs_segment.setEnabled(self.demucs_segment_enabled.isChecked())
        two_stem_active = self.demucs_two_stems.currentText() != "(full separation)"
        self.demucs_other_method.setEnabled(two_stem_active)
        self.demucs_mp3_bitrate.setEnabled(
            self.demucs_output_format.currentText() == "mp3")

        self.resample_hz.setEnabled(self.resample_enabled.isChecked())
        self.highpass_hz.setEnabled(self.highpass_enabled.isChecked())
        self.lowpass_hz.setEnabled(self.lowpass_enabled.isChecked())

        notch = self.notch_enabled.isChecked()
        self.notch_freqs.setEnabled(notch)
        self.notch_q.setEnabled(notch)

        self.pre_emphasis.setEnabled(self.pre_emphasis_enabled.isChecked())

        bandpass_boost = self.bandpass_boost.isChecked()
        self.boost_low_hz.setEnabled(bandpass_boost)
        self.boost_high_hz.setEnabled(bandpass_boost)
        self.boost_gain_db.setEnabled(bandpass_boost)

        hpss = self.hpss_enabled.isChecked()
        self.hpss_target.setEnabled(hpss)
        self.hpss_margin.setEnabled(hpss)
        self.hpss_emphasis_db.setEnabled(hpss)

        self.denoise_strength.setEnabled(self.spectral_denoise.isChecked())
        self.enhance_factor.setEnabled(self.spectral_enhance.isChecked())

        compress = self.compress.isChecked()
        self.compress_ratio.setEnabled(compress)
        self.compress_threshold_db.setEnabled(compress)

        sharpen = self.sharpen_transients.isChecked()
        self.sharpen_gain_db.setEnabled(sharpen)
        self.sharpen_attack_ms.setEnabled(sharpen)

        auto = self.auto_threshold.isChecked()
        self.db_threshold.setEnabled(not auto)
        self.noise_margin.setEnabled(auto)
        self.save_profile.setEnabled(auto)

        self.fade_ms.setEnabled(self.fade_enabled.isChecked())

        normalize = self.normalize.currentText() != "None"
        self.normalize_target_db.setEnabled(normalize)
        self.trim_threshold_db.setEnabled(self.trim_silence.isChecked())

    def attach_per_file_manager(self, manager, open_dialog_callback=None):
        self._per_file_overrides.set_manager(manager)
        if open_dialog_callback is not None:
            self._per_file_overrides._open_dialog_callback = open_dialog_callback
        for indicator in self.findChildren(PerFileToggleIndicator):
            indicator.set_manager(manager)

    def _register_perfile_indicators(self):
        mapping = {
            "MUTER_HIGHPASS_HZ": self.highpass_hz,
            "MUTER_LOWPASS_HZ": self.lowpass_hz,
            "MUTER_NOTCH_FREQS": self.notch_freqs,
            "MUTER_NOTCH_Q": self.notch_q,
            "MUTER_PRE_EMPHASIS": self.pre_emphasis,
            "MUTER_BANDPASS_BOOST": self.bandpass_boost,
            "MUTER_BOOST_LOW_HZ": self.boost_low_hz,
            "MUTER_BOOST_HIGH_HZ": self.boost_high_hz,
            "MUTER_BOOST_GAIN_DB": self.boost_gain_db,
            "MUTER_HPSS_ENABLED": self.hpss_enabled,
            "MUTER_HPSS_TARGET": self.hpss_target,
            "MUTER_HPSS_MARGIN": self.hpss_margin,
            "MUTER_SPECTRAL_DENOISE": self.spectral_denoise,
            "MUTER_DENOISE_STRENGTH": self.denoise_strength,
            "MUTER_COMPRESS": self.compress,
            "MUTER_COMPRESS_RATIO": self.compress_ratio,
            "MUTER_COMPRESS_THRESHOLD_DB": self.compress_threshold_db,
            "MUTER_SHARPEN_TRANSIENTS": self.sharpen_transients,
            "MUTER_SHARPEN_GAIN_DB": self.sharpen_gain_db,
            "MUTER_SHARPEN_ATTACK_MS": self.sharpen_attack_ms,
            "MUTER_DB_THRESHOLD": self.db_threshold,
            "MUTER_AUTO_THRESHOLD": self.auto_threshold,
            "MUTER_NOISE_MARGIN_DB": self.noise_margin,
            "MUTER_FADE_MS": self.fade_ms,
            "MUTER_NORMALIZE": self.normalize,
            "MUTER_NORMALIZE_TARGET_DB": self.normalize_target_db,
        }
        for config_key, widget in mapping.items():
            _mark_perfile_setting(widget, "settings", config_key)

    def get_values(self):
        preset = self.muter_preset.currentText()
        norm = self.normalize.currentText()
        notch_text = self.notch_freqs.text().strip()
        notch_list = [float(freq) for freq in notch_text.split() if freq] if notch_text else []
        two_stems = self.demucs_two_stems.currentText()
        return {
            "MUTER_INPUT_FOLDER": self.input_folder.text(),
            "MUTER_OUTPUT_FOLDER": self.output_folder.text(),
            "MUTER_SPECIFY_FILES": self.specify_files_cb.isChecked(),
            "MUTER_SELECTED_FILES": self.selected_files_combo.selected_files(),
            "MUTER_PRESET": None if preset == "None" else preset,
            "MUTER_DEMUCS_ENABLED": self.demucs_enabled.isChecked(),
            "MUTER_DEMUCS_ONLY": self.demucs_only.isChecked(),
            "MUTER_DEMUCS_MODEL": self.demucs_model.currentText(),
            "MUTER_DEMUCS_TWO_STEMS": None if two_stems == "(full separation)" else two_stems,
            "MUTER_DEMUCS_OTHER_METHOD": self.demucs_other_method.currentText(),
            "MUTER_DEMUCS_DEVICE": self.demucs_device.currentText(),
            "MUTER_DEMUCS_SHIFTS": _to_int(self.demucs_shifts.text(), 1),
            "MUTER_DEMUCS_OVERLAP": _to_float(self.demucs_overlap.text(), 0.25),
            "MUTER_DEMUCS_SEGMENT": _to_int(self.demucs_segment.text(), 10) if self.demucs_segment_enabled.isChecked() else None,
            "MUTER_DEMUCS_OUTPUT_FORMAT": self.demucs_output_format.currentText(),
            "MUTER_DEMUCS_MP3_BITRATE": _to_int(self.demucs_mp3_bitrate.text(), 320),
            "MUTER_DEMUCS_CLIP_MODE": self.demucs_clip_mode.currentText(),
            "MUTER_DEMUCS_JOBS": _to_int(self.demucs_jobs.text(), 1),
            "MUTER_CHANNEL": self.channel.currentText(),
            "MUTER_RESAMPLE_HZ": _to_int(self.resample_hz.text(), 0) if self.resample_enabled.isChecked() else 0,
            "MUTER_HIGHPASS_HZ": _to_int(self.highpass_hz.text(), 200) if self.highpass_enabled.isChecked() else 0,
            "MUTER_LOWPASS_HZ": _to_int(self.lowpass_hz.text(), 0) if self.lowpass_enabled.isChecked() else 0,
            "MUTER_NOTCH_FREQS": notch_list if self.notch_enabled.isChecked() else [],
            "MUTER_NOTCH_Q": _to_float(self.notch_q.text(), 30.0),
            "MUTER_PRE_EMPHASIS": _to_float(self.pre_emphasis.text(), 0.0) if self.pre_emphasis_enabled.isChecked() else 0.0,
            "MUTER_BANDPASS_BOOST": self.bandpass_boost.isChecked(),
            "MUTER_BOOST_LOW_HZ": _to_int(self.boost_low_hz.text(), 300),
            "MUTER_BOOST_HIGH_HZ": _to_int(self.boost_high_hz.text(), 3000),
            "MUTER_BOOST_GAIN_DB": _to_float(self.boost_gain_db.text(), 6.0),
            "MUTER_HPSS_ENABLED": self.hpss_enabled.isChecked(),
            "MUTER_HPSS_TARGET": self.hpss_target.currentText(),
            "MUTER_HPSS_MARGIN": _to_float(self.hpss_margin.text(), 2.0),
            "MUTER_HPSS_EMPHASIS_DB": _to_float(self.hpss_emphasis_db.text(), 0.0),
            "MUTER_SPECTRAL_DENOISE": self.spectral_denoise.isChecked(),
            "MUTER_DENOISE_STRENGTH": _to_float(self.denoise_strength.text(), 1.5),
            "MUTER_SPECTRAL_ENHANCE": self.spectral_enhance.isChecked(),
            "MUTER_ENHANCE_FACTOR": _to_float(self.enhance_factor.text(), 2.0),
            "MUTER_COMPRESS": self.compress.isChecked(),
            "MUTER_COMPRESS_RATIO": _to_float(self.compress_ratio.text(), 3.0),
            "MUTER_COMPRESS_THRESHOLD_DB": _to_float(self.compress_threshold_db.text(), -30.0),
            "MUTER_SHARPEN_TRANSIENTS": self.sharpen_transients.isChecked(),
            "MUTER_SHARPEN_GAIN_DB": _to_float(self.sharpen_gain_db.text(), 6.0),
            "MUTER_SHARPEN_ATTACK_MS": _to_float(self.sharpen_attack_ms.text(), 15.0),
            "MUTER_DB_THRESHOLD": _to_int(self.db_threshold.text(), 30),
            "MUTER_AUTO_THRESHOLD": self.auto_threshold.isChecked(),
            "MUTER_NOISE_MARGIN_DB": _to_float(self.noise_margin.text(), 6.0),
            "MUTER_SAVE_NOISE_PROFILE": self.save_profile.isChecked(),
            "MUTER_FADE_MS": _to_float(self.fade_ms.text(), 5.0) if self.fade_enabled.isChecked() else 0.0,
            "MUTER_NORMALIZE": None if norm == "None" else norm,
            "MUTER_NORMALIZE_TARGET_DB": _to_float(self.normalize_target_db.text(), -1.0),
            "MUTER_TRIM_SILENCE": self.trim_silence.isChecked(),
            "MUTER_TRIM_THRESHOLD_DB": _to_float(self.trim_threshold_db.text(), 40.0),
            "MUTER_MFCC_ENABLED": self.mfcc_enabled.isChecked(),
            "MUTER_MFCC_TEMPLATE_PATHS": [
                path.strip()
                for path in self.mfcc_template_paths.toPlainText().splitlines()
                if path.strip()
            ],
            "MUTER_MFCC_THRESHOLD_PERCENTILE": _to_float(self.mfcc_threshold.text(), 15.0),
            "MUTER_MFCC_SMOOTH_MS": _to_float(self.mfcc_smooth_ms.text(), 50.0),
            "MUTER_MFCC_N_MFCC": int(_to_float(self.mfcc_n_mfcc.text(), 13)),
            "MUTER_PROC_ORDER": list(self._proc_order),
        }

    def set_values(self, d):
        self.input_folder.setText(str(d.get("MUTER_INPUT_FOLDER", self.input_folder.text())))
        self.specify_files_cb.setChecked(bool(d.get("MUTER_SPECIFY_FILES", False)))
        self.selected_files_combo.set_selected_files(d.get("MUTER_SELECTED_FILES", []))
        if self.specify_files_cb.isChecked():
            self.selected_files_combo.ensure_first_selected()
        out = d.get("MUTER_OUTPUT_FOLDER")
        if out:
            self._output_auto = False
            self.output_folder.setText(str(out))
        self.demucs_enabled.setChecked(bool(d.get("MUTER_DEMUCS_ENABLED", False)))
        self.demucs_only.setChecked(bool(d.get("MUTER_DEMUCS_ONLY", False)))
        self.demucs_model.setCurrentText(str(d.get("MUTER_DEMUCS_MODEL", "htdemucs")))
        two_stems = d.get("MUTER_DEMUCS_TWO_STEMS")
        self.demucs_two_stems.setCurrentText("(full separation)" if two_stems is None else str(two_stems))
        self.demucs_other_method.setCurrentText(str(d.get("MUTER_DEMUCS_OTHER_METHOD", "add")))
        self.demucs_device.setCurrentText(str(d.get("MUTER_DEMUCS_DEVICE", "auto")))
        self.demucs_shifts.setText(str(d.get("MUTER_DEMUCS_SHIFTS", 1)))
        self.demucs_overlap.setText(str(d.get("MUTER_DEMUCS_OVERLAP", 0.25)))
        segment = d.get("MUTER_DEMUCS_SEGMENT")
        self.demucs_segment_enabled.setChecked(segment is not None)
        if segment is not None:
            self.demucs_segment.setText(str(segment))
        out_format = d.get("MUTER_DEMUCS_OUTPUT_FORMAT")
        if out_format is None:
            if d.get("MUTER_DEMUCS_FLOAT32", False):
                out_format = "wav-float32"
            else:
                out_format = "wav-int16"
        self.demucs_output_format.setCurrentText(str(out_format))
        self.demucs_mp3_bitrate.setText(str(d.get("MUTER_DEMUCS_MP3_BITRATE", 320)))
        self.demucs_clip_mode.setCurrentText(str(d.get("MUTER_DEMUCS_CLIP_MODE", "rescale")))
        self.demucs_jobs.setText(str(d.get("MUTER_DEMUCS_JOBS", 1)))
        self.channel.setCurrentText(str(d.get("MUTER_CHANNEL", "mix")))
        resample_val = int(d.get("MUTER_RESAMPLE_HZ", 0))
        self.resample_enabled.setChecked(resample_val > 0)
        if resample_val > 0:
            self.resample_hz.setText(str(resample_val))
        highpass_val = int(d.get("MUTER_HIGHPASS_HZ", 200))
        self.highpass_enabled.setChecked(highpass_val > 0)
        if highpass_val > 0:
            self.highpass_hz.setText(str(highpass_val))
        lowpass_val = int(d.get("MUTER_LOWPASS_HZ", 0))
        self.lowpass_enabled.setChecked(lowpass_val > 0)
        if lowpass_val > 0:
            self.lowpass_hz.setText(str(lowpass_val))
        notch = d.get("MUTER_NOTCH_FREQS", [])
        self.notch_enabled.setChecked(bool(notch))
        if notch:
            self.notch_freqs.setText(" ".join(str(freq) for freq in notch))
        self.notch_q.setText(str(d.get("MUTER_NOTCH_Q", 30)))
        pre_emphasis_val = float(d.get("MUTER_PRE_EMPHASIS", 0.0))
        self.pre_emphasis_enabled.setChecked(pre_emphasis_val > 0)
        if pre_emphasis_val > 0:
            self.pre_emphasis.setText(str(pre_emphasis_val))
        self.bandpass_boost.setChecked(bool(d.get("MUTER_BANDPASS_BOOST", False)))
        self.boost_low_hz.setText(str(d.get("MUTER_BOOST_LOW_HZ", 300)))
        self.boost_high_hz.setText(str(d.get("MUTER_BOOST_HIGH_HZ", 3000)))
        self.boost_gain_db.setText(str(d.get("MUTER_BOOST_GAIN_DB", 6.0)))
        self.hpss_enabled.setChecked(bool(d.get("MUTER_HPSS_ENABLED", False)))
        self.hpss_target.setCurrentText(str(d.get("MUTER_HPSS_TARGET", "percussive")))
        self.hpss_margin.setText(str(d.get("MUTER_HPSS_MARGIN", 2.0)))
        self.hpss_emphasis_db.setText(str(d.get("MUTER_HPSS_EMPHASIS_DB", 0)))
        self.spectral_denoise.setChecked(bool(d.get("MUTER_SPECTRAL_DENOISE", True)))
        self.denoise_strength.setText(str(d.get("MUTER_DENOISE_STRENGTH", 1.5)))
        self.spectral_enhance.setChecked(bool(d.get("MUTER_SPECTRAL_ENHANCE", False)))
        self.enhance_factor.setText(str(d.get("MUTER_ENHANCE_FACTOR", 2.0)))
        self.compress.setChecked(bool(d.get("MUTER_COMPRESS", False)))
        self.compress_ratio.setText(str(d.get("MUTER_COMPRESS_RATIO", 3.0)))
        self.compress_threshold_db.setText(str(d.get("MUTER_COMPRESS_THRESHOLD_DB", -30)))
        self.sharpen_transients.setChecked(bool(d.get("MUTER_SHARPEN_TRANSIENTS", False)))
        self.sharpen_gain_db.setText(str(d.get("MUTER_SHARPEN_GAIN_DB", 6)))
        self.sharpen_attack_ms.setText(str(d.get("MUTER_SHARPEN_ATTACK_MS", 15)))
        self.db_threshold.setText(str(d.get("MUTER_DB_THRESHOLD", 30)))
        self.auto_threshold.setChecked(bool(d.get("MUTER_AUTO_THRESHOLD", True)))
        self.noise_margin.setText(str(d.get("MUTER_NOISE_MARGIN_DB", 6.0)))
        self.save_profile.setChecked(bool(d.get("MUTER_SAVE_NOISE_PROFILE", True)))
        fade_val = float(d.get("MUTER_FADE_MS", 5.0))
        self.fade_enabled.setChecked(fade_val > 0)
        if fade_val > 0:
            self.fade_ms.setText(str(fade_val))
        normalize_val = d.get("MUTER_NORMALIZE")
        self.normalize.setCurrentText("None" if normalize_val is None else str(normalize_val))
        self.normalize_target_db.setText(str(d.get("MUTER_NORMALIZE_TARGET_DB", -1.0)))
        self.trim_silence.setChecked(bool(d.get("MUTER_TRIM_SILENCE", False)))
        self.trim_threshold_db.setText(str(d.get("MUTER_TRIM_THRESHOLD_DB", 40)))
        self.mfcc_enabled.setChecked(bool(d.get("MUTER_MFCC_ENABLED", False)))
        mfcc_paths = d.get("MUTER_MFCC_TEMPLATE_PATHS", [])
        self.mfcc_template_paths.setPlainText(
            "\n".join(mfcc_paths) if mfcc_paths else ""
        )
        self.mfcc_threshold.setText(str(d.get("MUTER_MFCC_THRESHOLD_PERCENTILE", 15.0)))
        self.mfcc_smooth_ms.setText(str(d.get("MUTER_MFCC_SMOOTH_MS", 50.0)))
        self.mfcc_n_mfcc.setText(str(d.get("MUTER_MFCC_N_MFCC", 13)))
        preset_val = d.get("MUTER_PRESET")
        self.muter_preset.setCurrentText("None" if preset_val is None else str(preset_val))
        self._update_conditions()
        proc_order = d.get("MUTER_PROC_ORDER")
        if proc_order:
            self.set_proc_order(proc_order)


__all__ = ["MuterPanel"]