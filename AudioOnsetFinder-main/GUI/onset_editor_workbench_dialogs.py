"""Large workbench-specific dialog classes extracted from onset_editor."""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

try:
    from onset_editor_io import _HAS_EXCEL_IO, _eio, _load_labels, _save_labels
except ImportError:
    from GUI.onset_editor_io import _HAS_EXCEL_IO, _eio, _load_labels, _save_labels


_ACCENT = "#4caf50"
_BG = "#1e1e2e"
_BG_MID = "#262636"
_BG_WIDGET = "#2c2c3c"
_BG_INPUT = "#323248"
_BORDER = "#3a3a50"
_TEXT = "#dcdcdc"
_TEXT_DIM = "#8888a0"
_TEXT_MUTED = "#6a6a82"
_ACCENT_DIM = "#2e7d32"
_POSITIVE_BLUE = "#2196F3"
_NEGATIVE_RED = "#e53935"
_FOCUS_BLUE = "#1565c0"
_FOCUS_BLUE_BRIGHT = "#5cacff"
_FOCUS_BLUE_BORDER = "#2a5a8c"
_NEG_EXACT_COLOR = (80, 140, 255, 220)
_NEG_CLOSE_COLOR = (255, 183, 77, 220)
_LAYER_OVERLAY_COLORS = [
    (0, 200, 255, 200),
    (255, 165, 0, 200),
    (180, 100, 255, 200),
    (50, 255, 150, 200),
    (255, 220, 50, 200),
    (255, 105, 180, 200),
    (100, 200, 200, 200),
    (200, 150, 100, 200),
]

_REGION_DETECTOR_METHODS = [
    "adaptive_hp",
    "librosa",
    "moving_median",
    "superflux",
    "cfar",
    "per_band",
]

_SIGNAL_VARIABLES = [
    ("spectral_centroid_hz", "Spectral Centroid", "Hz", 20),
    ("spectral_bandwidth_hz", "Spectral Bandwidth", "Hz", 30),
    ("peak_frequency_hz", "Peak Frequency", "Hz", 20),
    ("harmonicity", "Harmonicity", "", 25),
    ("attack_sharpness", "Attack Sharpness", "", 30),
    ("energy_ratio", "Energy Ratio", "", 40),
    ("duration_s", "Duration", "s", 50),
]

_SIGNAL_VAR_DESCRIPTIONS: dict[str, tuple[str, str, str]] = {
    "spectral_centroid_hz": (
        "The weighted average frequency of the signal — higher values mean a brighter sound.",
        "The spectral centroid is the 'centre of mass' of the frequency spectrum. "
        "A bright cymbal crash has a high centroid (~5 kHz); a bass drum has a low one (~100 Hz). "
        "The ±% range sets how far from this measured value a candidate onset can differ and still match.",
        "Imagine all the sound's frequencies sitting on a see-saw. The centroid is the balance point. "
        "Bright, shimmery sounds balance high up; deep, boomy sounds balance low down. "
        "The slider says how far off-balance you'll still accept as a match.",
    ),
    "spectral_bandwidth_hz": (
        "How spread out the signal's energy is across frequencies.",
        "Spectral bandwidth measures whether the sound is narrowly concentrated around one pitch or spread across many frequencies. "
        "Tighter bandwidths fit whistle-like sounds; wider bandwidths fit noisy or broadband hits.",
        "A narrow sound is focused like a whistle. A wide sound is smeared across lots of pitches like a clap or crash. "
        "This setting controls how wide that spread can be and still count as a match.",
    ),
    "peak_frequency_hz": (
        "The single strongest frequency in the signal.",
        "Peak frequency tracks the loudest spectral bin in the region. It is useful when your target sound has a very stable main pitch or resonant band.",
        "This is the note or pitch that stands out the most. Matching it helps keep only sounds that hit the same main pitch area.",
    ),
    "harmonicity": (
        "How tonal versus noisy the signal is.",
        "Harmonicity distinguishes stable tonal sounds from noisy or broadband events. Higher values suggest clearer harmonic structure; lower values suggest noisier hits.",
        "This tells you whether the sound feels musical and tone-like, or rough and noisy. It helps separate clean notes from scratchy or bursty sounds.",
    ),
    "attack_sharpness": (
        "How abruptly the sound begins.",
        "Attack sharpness measures how quickly energy rises at onset. Percussive events usually have sharper attacks than soft or gradual entries.",
        "A sharp attack feels like a sudden hit. A soft attack fades in more gently. This helps match crisp impacts versus smoother starts.",
    ),
    "energy_ratio": (
        "How much energy is concentrated inside the selected band.",
        "Energy ratio compares in-band energy to the surrounding spectrum. It helps prefer signals whose energy sits in the same focused band as the exemplar.",
        "This says how strongly the sound lives inside the frequency band you selected, instead of spilling everywhere else.",
    ),
    "duration_s": (
        "How long the signal lasts.",
        "Duration helps distinguish short impulse-like events from longer sustained sounds. Use a wider range if the target varies naturally in length.",
        "This is simply how long the sound lasts from start to end. It helps keep short hits separate from longer calls or notes.",
    ),
}


def _normalize_ui_path(path: str) -> str:
    """Return a stable forward-slash path for dialog display and tests."""
    return str(path).replace("\\", "/")


def _default_signal_export_dirs(audio_path: str) -> tuple[str, str]:
    """Return default positive/negative signal export folders for an audio file."""
    stem = os.path.splitext(os.path.basename(audio_path))[0]
    folder = os.path.dirname(audio_path)
    return (
        _normalize_ui_path(os.path.join(folder, f"{stem}_PositiveSignals")),
        _normalize_ui_path(os.path.join(folder, f"{stem}_NegativeSignals")),
    )


class _MfccAudioEditDialog(QDialog):
    """Dialog for MFCC template-matching audio cleaning."""

    def __init__(
        self,
        positive_regions: list[dict],
        *,
        selection_range: tuple[float, float] | None = None,
        duration: float = 0.0,
        parent=None,
    ):
        super().__init__(parent)
        self._positive_regions = positive_regions
        self._selection_range = selection_range
        self._duration = max(float(duration), 0.0)

        self.setWindowTitle("Audio Edits - MFCC Template Matching")
        self.setMinimumWidth(480)
        self.resize(540, 600)
        self.setStyleSheet(
            f"QDialog {{ background: {_BG}; color: {_TEXT}; }}"
            f"QLabel {{ background: transparent; color: {_TEXT}; }}"
            f"QGroupBox {{ color: {_TEXT}; border: 1px solid {_BORDER}; "
            f"border-radius: 4px; margin-top: 6px; padding-top: 6px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; "
            f"padding: 0 4px; color: {_TEXT_DIM}; }}"
            f"QSpinBox, QDoubleSpinBox {{ background: {_BG_INPUT}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 4px; }}"
            f"QCheckBox {{ background: transparent; color: {_TEXT}; }}"
            f"QListWidget {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; }}"
            f"QListWidget::item:selected {{ background: #1565c0; color: white; }}"
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 4px 10px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; color: white; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        desc = QLabel(
            "<b>MFCC Template Matching</b><br>"
            "Computes an MFCC fingerprint for each selected <i>positive</i> focus signal "
            "and slides it across the recording. Sections of the recording that closely "
            "match any template are preserved; non-matching sections are muted. "
            "The cleaned audio is displayed in the viewer - it is not saved to disk "
            "unless you use <i>File > Save a Copy</i>."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        root.addWidget(desc)

        tmpl_group = QGroupBox("Focus Signals to use as Templates")
        tmpl_layout = QVBoxLayout(tmpl_group)
        tmpl_layout.setSpacing(4)

        if not positive_regions:
            no_sig_lbl = QLabel(
                "No positive focus regions are defined for this file.\n"
                "Switch on Focus Onsets mode, draw one or more positive regions on\n"
                "the spectrogram, then re-open this dialog."
            )
            no_sig_lbl.setStyleSheet("color: #ffb74d; font-size: 11px;")
            no_sig_lbl.setWordWrap(True)
            tmpl_layout.addWidget(no_sig_lbl)
            self._region_list = None
        else:
            tmpl_hint = QLabel(
                "Select one or more positive regions below. The MFCC fingerprint of "
                "each selected region is used as a template. A recording frame is "
                "kept if it matches <i>any</i> selected template."
            )
            tmpl_hint.setWordWrap(True)
            tmpl_hint.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
            tmpl_layout.addWidget(tmpl_hint)

            self._region_list = QListWidget()
            self._region_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
            for index, region in enumerate(positive_regions):
                t0 = float(region.get("t_start", 0.0))
                t1 = float(region.get("t_end", 0.0))
                f_low = region.get("f_low", region.get("f_min", 0))
                f_high = region.get("f_high", region.get("f_max", 0))
                label = f"Signal {index + 1}:  {t0:.3f}s - {t1:.3f}s"
                if f_low or f_high:
                    label += f"  ({int(f_low)}-{int(f_high)} Hz)"
                self._region_list.addItem(label)
            for row in range(self._region_list.count()):
                self._region_list.item(row).setSelected(True)
            self._region_list.setMaximumHeight(120)
            tmpl_layout.addWidget(self._region_list)

            sel_row = QHBoxLayout()
            sel_all_btn = QPushButton("Select All")
            sel_all_btn.clicked.connect(self._region_list.selectAll)
            sel_none_btn = QPushButton("Deselect All")
            sel_none_btn.clicked.connect(self._region_list.clearSelection)
            sel_row.addWidget(sel_all_btn)
            sel_row.addWidget(sel_none_btn)
            sel_row.addStretch()
            tmpl_layout.addLayout(sel_row)

        root.addWidget(tmpl_group)

        param_group = QGroupBox("Cleaning Parameters")
        param_layout = QVBoxLayout(param_group)
        param_layout.setSpacing(6)

        thresh_row = QHBoxLayout()
        thresh_lbl = QLabel("Keep threshold (%):")
        thresh_lbl.setToolTip(
            "Keep only the top X% of recording frames that are most similar "
            "to the template(s). Lower = stricter (fewer frames kept). "
            "Raise this if your target animal calls frequently; lower it if "
            "calls are sparse."
        )
        thresh_row.addWidget(thresh_lbl)
        self._thresh_spin = QDoubleSpinBox()
        self._thresh_spin.setRange(1.0, 99.0)
        self._thresh_spin.setDecimals(1)
        self._thresh_spin.setSingleStep(5.0)
        self._thresh_spin.setValue(15.0)
        self._thresh_spin.setToolTip(thresh_lbl.toolTip())
        thresh_row.addWidget(self._thresh_spin)
        thresh_row.addStretch()
        param_layout.addLayout(thresh_row)

        thresh_hint = QLabel(
            "Example: 15% keeps the 15% of the file that sounds most like "
            "the template and mutes the rest. Try 10-20 for sparse calls, "
            "30-60 for dense call bouts."
        )
        thresh_hint.setWordWrap(True)
        thresh_hint.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        param_layout.addWidget(thresh_hint)

        smooth_row = QHBoxLayout()
        smooth_lbl = QLabel("Mask smoothing (ms):")
        smooth_lbl.setToolTip(
            "Gaussian smoothing applied to the keep/mute mask. Higher values "
            "produce softer fade transitions at the boundary between kept and "
            "muted sections, preventing click artefacts. Set to 0 to disable."
        )
        smooth_row.addWidget(smooth_lbl)
        self._smooth_spin = QDoubleSpinBox()
        self._smooth_spin.setRange(0.0, 500.0)
        self._smooth_spin.setDecimals(0)
        self._smooth_spin.setSingleStep(10.0)
        self._smooth_spin.setValue(50.0)
        self._smooth_spin.setToolTip(smooth_lbl.toolTip())
        smooth_row.addWidget(self._smooth_spin)
        smooth_row.addStretch()
        param_layout.addLayout(smooth_row)

        mfcc_row = QHBoxLayout()
        mfcc_lbl = QLabel("MFCC coefficients:")
        mfcc_lbl.setToolTip(
            "Number of MFCC coefficients used to represent each frame. "
            "13 is the standard for speech and bioacoustics. Increase to "
            "20-40 for finer timbral discrimination; decrease to 6-8 for "
            "coarser, more robust matching."
        )
        mfcc_row.addWidget(mfcc_lbl)
        self._mfcc_spin = QSpinBox()
        self._mfcc_spin.setRange(4, 40)
        self._mfcc_spin.setValue(13)
        self._mfcc_spin.setToolTip(mfcc_lbl.toolTip())
        mfcc_row.addWidget(self._mfcc_spin)
        mfcc_row.addStretch()
        param_layout.addLayout(mfcc_row)

        root.addWidget(param_group)

        range_group = QGroupBox("Apply To")
        range_layout = QVBoxLayout(range_group)
        range_layout.setSpacing(4)

        self._range_sel_rb = QRadioButton("Current selection only")
        self._range_full_rb = QRadioButton("Full audio clip")

        if selection_range is not None:
            t0, t1 = selection_range
            self._range_sel_rb.setText(f"Current selection only  ({t0:.3f}s - {t1:.3f}s)")
            self._range_sel_rb.setChecked(True)
        else:
            self._range_sel_rb.setEnabled(False)
            self._range_full_rb.setChecked(True)

        range_layout.addWidget(self._range_sel_rb)
        range_layout.addWidget(self._range_full_rb)
        root.addWidget(range_group)

        btn_row = QHBoxLayout()
        self._run_btn = QPushButton("Run Cleaning")
        self._run_btn.setStyleSheet(
            f"QPushButton {{ background: #2e7d32; color: white; "
            f"border: 1px solid {_ACCENT}; border-radius: 4px; "
            f"padding: 6px 16px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {_ACCENT}; }}"
            f"QPushButton:disabled {{ background: {_BG_MID}; color: #6a6a82; "
            f"border-color: {_BG_MID}; }}"
        )
        if not positive_regions:
            self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._run_btn)
        root.addLayout(btn_row)

    def selected_region_indices(self) -> list[int]:
        if self._region_list is None:
            return []
        return [index.row() for index in self._region_list.selectedIndexes()]

    def threshold_percentile(self) -> float:
        return float(self._thresh_spin.value())

    def smooth_ms(self) -> float:
        return float(self._smooth_spin.value())

    def n_mfcc(self) -> int:
        return int(self._mfcc_spin.value())

    def use_full_clip(self) -> bool:
        return self._range_full_rb.isChecked()


class _DetectOnsetsDialog(QDialog):
    """Dialog for running onset detection on a selected region or full clip."""

    def __init__(
        self,
        start: float,
        end: float,
        duration: float,
        *,
        parent=None,
        selection_available: bool,
        locked_range: tuple[float, float] | None = None,
    ):
        super().__init__(parent)
        self._selection_start = float(start)
        self._selection_end = float(end)
        self._duration = max(float(duration), 0.0)
        self._selection_available = bool(selection_available)
        self._locked_range = tuple(locked_range) if locked_range is not None else None
        self.setWindowTitle("Quick Onset Finder")
        self.setMinimumWidth(620)
        self.resize(760, 760)
        input_style = (
            f"background: {_BG_INPUT}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 4px;"
        )
        self.setStyleSheet(
            f"QDialog {{ background: {_BG}; color: {_TEXT}; }}"
            f"QLabel {{ color: {_TEXT}; background: transparent; }}"
            f"QSpinBox {{ {input_style} }}"
            f"QDoubleSpinBox {{ {input_style} }}"
            f"QComboBox {{ {input_style} }}"
            f"QCheckBox {{ color: {_TEXT}; }}"
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setSpacing(10)

        info = QLabel("<b>Timing Scope</b>")
        info.setWordWrap(True)
        layout.addWidget(info)

        scope_desc = QLabel(
            "<i>These times control which part of the recording will be analyzed. "
            "If a normal waveform/spectrogram selection is active, it is loaded here by default. "
            "You can edit the times manually or switch to the full clip.</i>"
        )
        scope_desc.setWordWrap(True)
        scope_desc.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        layout.addWidget(scope_desc)

        range_row = QHBoxLayout()
        range_row.setSpacing(6)
        range_row.addWidget(QLabel("Start (s):"))
        self._start_spin = QDoubleSpinBox()
        self._start_spin.setRange(0.0, self._duration)
        self._start_spin.setDecimals(3)
        self._start_spin.setSingleStep(0.05)
        self._start_spin.setValue(self._selection_start)
        range_row.addWidget(self._start_spin)
        range_row.addWidget(QLabel("End (s):"))
        self._end_spin = QDoubleSpinBox()
        self._end_spin.setRange(0.0, self._duration)
        self._end_spin.setDecimals(3)
        self._end_spin.setSingleStep(0.05)
        self._end_spin.setValue(self._selection_end)
        range_row.addWidget(self._end_spin)
        layout.addLayout(range_row)

        scope_btn_row = QHBoxLayout()
        scope_btn_row.setSpacing(6)
        self._use_selection_btn = QPushButton("Use Selection")
        self._use_selection_btn.setEnabled(self._selection_available)
        self._use_selection_btn.clicked.connect(self._apply_selection_range)
        scope_btn_row.addWidget(self._use_selection_btn)
        self._use_full_btn = QPushButton("Use Full Clip")
        self._use_full_btn.clicked.connect(self._apply_full_clip_range)
        scope_btn_row.addWidget(self._use_full_btn)
        scope_btn_row.addStretch()
        layout.addLayout(scope_btn_row)

        self._scope_note = QLabel("")
        self._scope_note.setWordWrap(True)
        self._scope_note.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        layout.addWidget(self._scope_note)

        self._focus_lock_note = QLabel("")
        self._focus_lock_note.setWordWrap(True)
        self._focus_lock_note.setStyleSheet(f"color: {_ACCENT}; font-size: 11px;")
        self._focus_lock_note.hide()
        layout.addWidget(self._focus_lock_note)

        if self._locked_range is not None:
            lock_start, lock_end = self._locked_range
            self._start_spin.setRange(lock_start, lock_end)
            self._end_spin.setRange(lock_start, lock_end)
            self._start_spin.setValue(lock_start)
            self._end_spin.setValue(lock_end)
            self._start_spin.setEnabled(False)
            self._end_spin.setEnabled(False)
            self._use_selection_btn.setEnabled(False)
            self._use_full_btn.setEnabled(False)
            self._focus_lock_note.setText(
                "Focus Onsets mode is active: detection is locked to the selected focus region."
            )
            self._focus_lock_note.show()

        q_label = QLabel("How many onsets should be detected in this region?")
        q_label.setWordWrap(True)
        layout.addWidget(q_label)

        hint = QLabel("<i>Hint: set to 0 or leave blank to auto-detect as many as possible.</i>")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        layout.addWidget(hint)

        existing_note = QLabel(
            "<i>Detected onsets are added to the current layer. Existing onset values are preserved, "
            "and near-duplicates are skipped automatically.</i>"
        )
        existing_note.setWordWrap(True)
        existing_note.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        layout.addWidget(existing_note)

        self._spin = QSpinBox()
        self._spin.setRange(0, 200)
        self._spin.setValue(1)
        self._spin.setSpecialValueText("Auto (as many as possible)")
        layout.addWidget(self._spin)

        self._settings_toggle = QPushButton("▶ Detection Settings")
        self._settings_toggle.setFlat(True)
        self._settings_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_toggle.setStyleSheet(
            f"QPushButton {{ color: {_ACCENT}; font-size: 12px; "
            f"text-align: left; padding: 4px 0; background: transparent; }}"
            f"QPushButton:hover {{ color: white; }}"
        )
        self._settings_toggle.clicked.connect(self._toggle_settings)
        layout.addWidget(self._settings_toggle)

        self._settings_frame = QFrame()
        self._settings_frame.setStyleSheet(
            f"QFrame {{ background: {_BG_MID}; border: 1px solid {_BORDER}; "
            f"border-radius: 6px; }}"
        )
        self._settings_frame.setVisible(False)
        s_layout = QVBoxLayout(self._settings_frame)
        s_layout.setContentsMargins(10, 8, 10, 8)
        s_layout.setSpacing(6)

        desc = QLabel(
            "<i>These are the settings used for onset detection in the selected region. "
            "Adjust them to tune detection sensitivity, method, and post-processing.</i>"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px; background: transparent;")
        s_layout.addWidget(desc)

        method_row = QHBoxLayout()
        method_row.setSpacing(6)
        method_label = QLabel("Detection method:")
        method_label.setToolTip(
            "Coarse onset detector to use before post-processing and sample refinement."
        )
        method_row.addWidget(method_label)
        self._method_combo = QComboBox()
        self._method_combo.addItems(_REGION_DETECTOR_METHODS)
        self._method_combo.setCurrentText("librosa")
        method_row.addWidget(self._method_combo)
        s_layout.addLayout(method_row)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        hop_label = QLabel("Hop length (samples):")
        hop_label.setToolTip(
            "Number of audio samples between analysis frames. "
            "Smaller = finer time resolution but slower."
        )
        row1.addWidget(hop_label)
        self._hop_spin = QSpinBox()
        self._hop_spin.setRange(64, 2048)
        self._hop_spin.setSingleStep(64)
        self._hop_spin.setValue(256)
        self._hop_spin.setToolTip("Default: 256")
        row1.addWidget(self._hop_spin)
        s_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        delta_label = QLabel("Initial sensitivity (delta):")
        delta_label.setToolTip(
            "Starting onset detection threshold. Higher = fewer, more prominent onsets. "
            "The detector progressively lowers this to find the requested count."
        )
        row2.addWidget(delta_label)
        self._delta_spin = QDoubleSpinBox()
        self._delta_spin.setRange(0.01, 2.0)
        self._delta_spin.setSingleStep(0.05)
        self._delta_spin.setDecimals(2)
        self._delta_spin.setValue(0.30)
        self._delta_spin.setToolTip("Default: 0.30")
        row2.addWidget(self._delta_spin)
        s_layout.addLayout(row2)

        self._backtrack_cb = QCheckBox("Backtrack to nearest energy minimum")
        self._backtrack_cb.setChecked(True)
        self._backtrack_cb.setToolTip(
            "When enabled, detected onsets are moved back to the nearest "
            "local energy minimum for more accurate timing."
        )
        s_layout.addWidget(self._backtrack_cb)

        method_desc = QLabel(
            "<i>Advanced controls below apply only to the currently selected method.</i>"
        )
        method_desc.setWordWrap(True)
        method_desc.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px; background: transparent;")
        s_layout.addWidget(method_desc)

        self._method_control_rows: dict[str, list[QWidget]] = {
            "adaptive_hp": [],
            "moving_median": [],
            "superflux": [],
            "cfar": [],
            "per_band": [],
            "librosa": [],
        }

        def _add_method_row(methods, label_text, widget, tooltip=""):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            label = QLabel(label_text)
            if tooltip:
                label.setToolTip(tooltip)
                widget.setToolTip(tooltip)
            row_layout.addWidget(label)
            row_layout.addWidget(widget)
            s_layout.addWidget(row_widget)
            for method in methods:
                self._method_control_rows[method].append(row_widget)
            return row_widget

        self._env_window_spin = QDoubleSpinBox()
        self._env_window_spin.setRange(1.0, 200.0)
        self._env_window_spin.setValue(10.0)
        self._env_window_spin.setSuffix(" ms")
        _add_method_row(
            ["adaptive_hp", "moving_median", "cfar"],
            "Envelope window:",
            self._env_window_spin,
            "Window size used when building the RMS envelope.",
        )

        self._env_hop_spin = QDoubleSpinBox()
        self._env_hop_spin.setRange(0.5, 50.0)
        self._env_hop_spin.setDecimals(1)
        self._env_hop_spin.setValue(1.0)
        self._env_hop_spin.setSuffix(" ms")
        _add_method_row(
            ["adaptive_hp", "moving_median", "cfar"],
            "Envelope hop:",
            self._env_hop_spin,
            "Hop between consecutive RMS envelope frames.",
        )

        self._hp_smooth_spin = QDoubleSpinBox()
        self._hp_smooth_spin.setRange(1.0, 5000.0)
        self._hp_smooth_spin.setValue(50.0)
        self._hp_smooth_spin.setDecimals(1)
        _add_method_row(
            ["adaptive_hp"],
            "HP smooth lambda:",
            self._hp_smooth_spin,
            "Envelope smoothing strength for adaptive HP detection.",
        )

        self._hp_threshold_spin = QDoubleSpinBox()
        self._hp_threshold_spin.setRange(1.0, 1e9)
        self._hp_threshold_spin.setDecimals(1)
        self._hp_threshold_spin.setValue(5e7)
        self._hp_threshold_spin.setSingleStep(1000.0)
        _add_method_row(
            ["adaptive_hp"],
            "HP threshold lambda:",
            self._hp_threshold_spin,
            "Baseline stiffness for adaptive HP detection.",
        )

        self._median_window_spin = QDoubleSpinBox()
        self._median_window_spin.setRange(1.0, 2000.0)
        self._median_window_spin.setValue(200.0)
        self._median_window_spin.setSuffix(" ms")
        _add_method_row(
            ["moving_median", "per_band"],
            "Median window:",
            self._median_window_spin,
            "Width of the moving-median baseline window.",
        )

        self._median_thresh_spin = QDoubleSpinBox()
        self._median_thresh_spin.setRange(0.1, 10.0)
        self._median_thresh_spin.setDecimals(2)
        self._median_thresh_spin.setValue(1.5)
        _add_method_row(
            ["moving_median", "per_band"],
            "Threshold scale:",
            self._median_thresh_spin,
            "Sensitivity relative to the moving-median baseline.",
        )

        self._superflux_nfft_spin = QSpinBox()
        self._superflux_nfft_spin.setRange(256, 8192)
        self._superflux_nfft_spin.setSingleStep(256)
        self._superflux_nfft_spin.setValue(2048)
        _add_method_row(["superflux"], "FFT size:", self._superflux_nfft_spin)

        self._superflux_lag_spin = QSpinBox()
        self._superflux_lag_spin.setRange(1, 16)
        self._superflux_lag_spin.setValue(2)
        _add_method_row(["superflux"], "Lag:", self._superflux_lag_spin)

        self._superflux_max_spin = QSpinBox()
        self._superflux_max_spin.setRange(1, 16)
        self._superflux_max_spin.setValue(3)
        _add_method_row(["superflux"], "Max size:", self._superflux_max_spin)

        self._cfar_guard_spin = QDoubleSpinBox()
        self._cfar_guard_spin.setRange(1.0, 500.0)
        self._cfar_guard_spin.setValue(20.0)
        self._cfar_guard_spin.setSuffix(" ms")
        _add_method_row(["cfar"], "Guard window:", self._cfar_guard_spin)

        self._cfar_train_spin = QDoubleSpinBox()
        self._cfar_train_spin.setRange(1.0, 5000.0)
        self._cfar_train_spin.setValue(200.0)
        self._cfar_train_spin.setSuffix(" ms")
        _add_method_row(["cfar"], "Training window:", self._cfar_train_spin)

        self._cfar_thresh_spin = QDoubleSpinBox()
        self._cfar_thresh_spin.setRange(0.1, 20.0)
        self._cfar_thresh_spin.setDecimals(2)
        self._cfar_thresh_spin.setValue(4.0)
        _add_method_row(["cfar"], "Threshold factor:", self._cfar_thresh_spin)

        self._perband_nfft_spin = QSpinBox()
        self._perband_nfft_spin.setRange(256, 8192)
        self._perband_nfft_spin.setSingleStep(256)
        self._perband_nfft_spin.setValue(2048)
        _add_method_row(["per_band"], "FFT size:", self._perband_nfft_spin)

        self._perband_bands_spin = QSpinBox()
        self._perband_bands_spin.setRange(1, 32)
        self._perband_bands_spin.setValue(6)
        _add_method_row(["per_band"], "Number of bands:", self._perband_bands_spin)

        self._perband_fmin_spin = QSpinBox()
        self._perband_fmin_spin.setRange(0, 50000)
        self._perband_fmin_spin.setValue(200)
        self._perband_fmin_spin.setSuffix(" Hz")
        _add_method_row(["per_band"], "Min frequency:", self._perband_fmin_spin)

        self._perband_fmax_spin = QSpinBox()
        self._perband_fmax_spin.setRange(0, 50000)
        self._perband_fmax_spin.setValue(0)
        self._perband_fmax_spin.setSpecialValueText("Nyquist")
        self._perband_fmax_spin.setSuffix(" Hz")
        _add_method_row(["per_band"], "Max frequency:", self._perband_fmax_spin)

        self._perband_minbands_spin = QSpinBox()
        self._perband_minbands_spin.setRange(1, 32)
        self._perband_minbands_spin.setValue(2)
        _add_method_row(["per_band"], "Min bands voting:", self._perband_minbands_spin)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT_DIM}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 3px 10px; font-size: 11px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; color: {_TEXT}; }}"
        )
        reset_btn.clicked.connect(self._reset_defaults)
        s_layout.addWidget(reset_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._update_method_controls_visibility(self._method_combo.currentText())

        layout.addWidget(self._settings_frame)

        post_header = QHBoxLayout()
        post_header.setContentsMargins(0, 0, 0, 0)
        post_header.setSpacing(6)

        self._post_enabled_cb = QCheckBox()
        self._post_enabled_cb.setChecked(True)
        self._post_enabled_cb.setToolTip(
            "Master switch: enable or disable all post-processing.\n"
            "When unchecked, raw detection results are returned as-is."
        )
        self._post_enabled_cb.setStyleSheet(
            "QCheckBox { background: transparent; }"
            "QCheckBox::indicator { width: 14px; height: 14px; }"
        )
        post_header.addWidget(self._post_enabled_cb)

        self._post_toggle = QPushButton("▶ Post-Processing")
        self._post_toggle.setFlat(True)
        self._post_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._post_toggle.setStyleSheet(
            f"QPushButton {{ color: {_ACCENT}; font-size: 12px; "
            f"text-align: left; padding: 4px 0; background: transparent; }}"
            f"QPushButton:hover {{ color: white; }}"
        )
        self._post_toggle.clicked.connect(self._toggle_post)
        post_header.addWidget(self._post_toggle)
        post_header.addStretch()
        layout.addLayout(post_header)

        self._post_enabled_cb.toggled.connect(self._on_post_enabled_toggled)

        self._post_frame = QFrame()
        self._post_frame.setStyleSheet(
            f"QFrame {{ background: {_BG_MID}; border: 1px solid {_BORDER}; "
            f"border-radius: 6px; }}"
        )
        self._post_frame.setVisible(False)
        p_layout = QVBoxLayout(self._post_frame)
        p_layout.setContentsMargins(10, 8, 10, 8)
        p_layout.setSpacing(6)

        post_desc = QLabel(
            "<i>These filters run after detection to clean up results. "
            "They are the same filters used in the main Onset Finder pipeline step.</i>"
        )
        post_desc.setWordWrap(True)
        post_desc.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px; background: transparent;")
        p_layout.addWidget(post_desc)

        r_min = QHBoxLayout()
        r_min.setSpacing(6)
        min_lbl = QLabel("Min inter-onset interval (ms):")
        min_lbl.setToolTip(
            "Drop onsets that follow the previous one by fewer than this many ms. "
            "Prevents double-triggers on a single event."
        )
        r_min.addWidget(min_lbl)
        self._min_ioi_spin = QSpinBox()
        self._min_ioi_spin.setRange(0, 500)
        self._min_ioi_spin.setValue(30)
        self._min_ioi_spin.setSuffix(" ms")
        self._min_ioi_spin.setSpecialValueText("Off")
        self._min_ioi_spin.setToolTip("Default: 30 ms  (0 = disabled)")
        r_min.addWidget(self._min_ioi_spin)
        p_layout.addLayout(r_min)

        r_amp = QHBoxLayout()
        r_amp.setSpacing(6)
        amp_lbl = QLabel("Amplitude gate:")
        amp_lbl.setToolTip(
            "Discard onsets whose local RMS energy is below this fraction "
            "of the region's peak RMS. Higher = keep only louder onsets."
        )
        r_amp.addWidget(amp_lbl)
        self._amp_gate_spin = QDoubleSpinBox()
        self._amp_gate_spin.setRange(0.0, 1.0)
        self._amp_gate_spin.setSingleStep(0.01)
        self._amp_gate_spin.setDecimals(2)
        self._amp_gate_spin.setValue(0.0)
        self._amp_gate_spin.setSpecialValueText("Off")
        self._amp_gate_spin.setToolTip("Default: 0.00 (disabled). Try 0.05–0.10.")
        r_amp.addWidget(self._amp_gate_spin)
        p_layout.addLayout(r_amp)

        r_sharp = QHBoxLayout()
        r_sharp.setSpacing(6)
        sharp_lbl = QLabel("Sharpness gate:")
        sharp_lbl.setToolTip(
            "Discard onsets whose attack slope (how fast energy rises) "
            "is below this fraction of the steepest attack in the region. "
            "Filters out gradual transients, keeps sharp percussive hits."
        )
        r_sharp.addWidget(sharp_lbl)
        self._sharp_gate_spin = QDoubleSpinBox()
        self._sharp_gate_spin.setRange(0.0, 1.0)
        self._sharp_gate_spin.setSingleStep(0.01)
        self._sharp_gate_spin.setDecimals(2)
        self._sharp_gate_spin.setValue(0.0)
        self._sharp_gate_spin.setSpecialValueText("Off")
        self._sharp_gate_spin.setToolTip("Default: 0.00 (disabled). Try 0.10–0.20.")
        r_sharp.addWidget(self._sharp_gate_spin)
        p_layout.addLayout(r_sharp)

        self._cluster_cb = QCheckBox("Cluster nearby onsets")
        self._cluster_cb.setChecked(True)
        self._cluster_cb.setToolTip(
            "Merge onsets that occur within the cluster window into a single onset."
        )
        p_layout.addWidget(self._cluster_cb)

        r_clust = QHBoxLayout()
        r_clust.setSpacing(6)
        clust_lbl = QLabel("    Cluster window (ms):")
        clust_lbl.setToolTip("Onsets within this window are merged into one.")
        r_clust.addWidget(clust_lbl)
        self._cluster_spin = QSpinBox()
        self._cluster_spin.setRange(1, 200)
        self._cluster_spin.setValue(25)
        self._cluster_spin.setSuffix(" ms")
        self._cluster_spin.setToolTip("Default: 25 ms")
        r_clust.addWidget(self._cluster_spin)
        p_layout.addLayout(r_clust)
        self._cluster_cb.toggled.connect(self._cluster_spin.setEnabled)

        self._refine_cb = QCheckBox("Refine onsets to sample accuracy (Hilbert envelope)")
        self._refine_cb.setChecked(True)
        self._refine_cb.setToolTip(
            "Snap each detected onset to the nearest steep energy rise "
            "using the Hilbert analytic envelope. Gives ~0.023 ms precision at 44.1 kHz."
        )
        p_layout.addWidget(self._refine_cb)

        r_ref = QHBoxLayout()
        r_ref.setSpacing(6)
        ref_lbl = QLabel("    Refinement window (ms):")
        ref_lbl.setToolTip(
            "Half-width of the search window around each coarse onset.\n"
            "• 5 ms — narrow, use when coarse detector is already accurate\n"
            "• 10 ms — safe default\n"
            "• 20 ms — wide, use if coarse detector has poor resolution"
        )
        r_ref.addWidget(ref_lbl)
        self._refine_window_spin = QDoubleSpinBox()
        self._refine_window_spin.setRange(1.0, 50.0)
        self._refine_window_spin.setSingleStep(1.0)
        self._refine_window_spin.setDecimals(1)
        self._refine_window_spin.setValue(10.0)
        self._refine_window_spin.setSuffix(" ms")
        self._refine_window_spin.setToolTip("Default: 10 ms")
        r_ref.addWidget(self._refine_window_spin)
        p_layout.addLayout(r_ref)
        self._refine_cb.toggled.connect(self._refine_window_spin.setEnabled)

        reset_post_btn = QPushButton("Reset to Defaults")
        reset_post_btn.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT_DIM}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 3px 10px; font-size: 11px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; color: {_TEXT}; }}"
        )
        reset_post_btn.clicked.connect(self._reset_post_defaults)
        p_layout.addWidget(reset_post_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(self._post_frame)

        eff_label = QLabel("Effective settings for this run")
        eff_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(eff_label)

        self._effective_text = QPlainTextEdit()
        self._effective_text.setReadOnly(True)
        self._effective_text.setMinimumHeight(140)
        self._effective_text.setStyleSheet(
            f"QPlainTextEdit {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 6px; }}"
        )
        layout.addWidget(self._effective_text)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Run Quick Onset Finder")
        btns.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 5px 14px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
        )
        layout.addWidget(btns)

        self._connect_effective_preview_signals()
        self._start_spin.valueChanged.connect(self._on_range_changed)
        self._end_spin.valueChanged.connect(self._on_range_changed)
        self._update_effective_settings_preview()
        self._on_range_changed()

    def _apply_selection_range(self):
        if self._locked_range is not None:
            return
        self._start_spin.setValue(self._selection_start)
        self._end_spin.setValue(self._selection_end)

    def _apply_full_clip_range(self):
        if self._locked_range is not None:
            return
        self._start_spin.setValue(0.0)
        self._end_spin.setValue(self._duration)

    def _on_range_changed(self):
        start, end = self.selected_range()
        length = end - start
        if self.using_full_clip():
            self._scope_note.setText(
                f"Full clip selected: 0.000s – {self._duration:.3f}s ({self._duration:.3f}s)."
            )
        else:
            self._scope_note.setText(
                f"Current range: {start:.3f}s – {end:.3f}s ({length:.3f}s)."
            )
        self._update_effective_settings_preview()

    def _update_method_controls_visibility(self, method: str):
        for method_name, rows in self._method_control_rows.items():
            visible = method_name == method
            for row in rows:
                row.setVisible(visible)
        self.updateGeometry()

    def _toggle_settings(self):
        visible = not self._settings_frame.isVisible()
        self._settings_frame.setVisible(visible)
        self._settings_toggle.setText(
            "▼ Detection Settings" if visible else "▶ Detection Settings"
        )
        self.updateGeometry()

    def _toggle_post(self):
        visible = not self._post_frame.isVisible()
        self._post_frame.setVisible(visible)
        self._post_toggle.setText(
            "▼ Post-Processing" if visible else "▶ Post-Processing"
        )
        self.updateGeometry()

    def _on_post_enabled_toggled(self, enabled: bool):
        for child in self._post_frame.findChildren(QWidget):
            child.setEnabled(enabled)
        self._post_frame.setEnabled(enabled)
        self._update_effective_settings_preview()

    def _connect_effective_preview_signals(self):
        self._spin.valueChanged.connect(self._update_effective_settings_preview)
        self._method_combo.currentTextChanged.connect(self._update_method_controls_visibility)
        self._method_combo.currentTextChanged.connect(self._update_effective_settings_preview)
        self._hop_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._delta_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._backtrack_cb.toggled.connect(self._update_effective_settings_preview)
        self._post_enabled_cb.toggled.connect(self._update_effective_settings_preview)
        self._min_ioi_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._amp_gate_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._sharp_gate_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._cluster_cb.toggled.connect(self._update_effective_settings_preview)
        self._cluster_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._refine_cb.toggled.connect(self._update_effective_settings_preview)
        self._refine_window_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._env_window_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._env_hop_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._hp_smooth_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._hp_threshold_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._median_window_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._median_thresh_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._superflux_nfft_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._superflux_lag_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._superflux_max_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._cfar_guard_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._cfar_train_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._cfar_thresh_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._perband_nfft_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._perband_bands_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._perband_fmin_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._perband_fmax_spin.valueChanged.connect(self._update_effective_settings_preview)
        self._perband_minbands_spin.valueChanged.connect(self._update_effective_settings_preview)

    def _reset_defaults(self):
        self._method_combo.setCurrentText("librosa")
        self._hop_spin.setValue(256)
        self._delta_spin.setValue(0.30)
        self._backtrack_cb.setChecked(True)
        self._env_window_spin.setValue(10.0)
        self._env_hop_spin.setValue(1.0)
        self._hp_smooth_spin.setValue(50.0)
        self._hp_threshold_spin.setValue(5e7)
        self._median_window_spin.setValue(200.0)
        self._median_thresh_spin.setValue(1.5)
        self._superflux_nfft_spin.setValue(2048)
        self._superflux_lag_spin.setValue(2)
        self._superflux_max_spin.setValue(3)
        self._cfar_guard_spin.setValue(20.0)
        self._cfar_train_spin.setValue(200.0)
        self._cfar_thresh_spin.setValue(4.0)
        self._perband_nfft_spin.setValue(2048)
        self._perband_bands_spin.setValue(6)
        self._perband_fmin_spin.setValue(200)
        self._perband_fmax_spin.setValue(0)
        self._perband_minbands_spin.setValue(2)
        self._update_effective_settings_preview()

    def _reset_post_defaults(self):
        self._post_enabled_cb.setChecked(True)
        self._min_ioi_spin.setValue(30)
        self._amp_gate_spin.setValue(0.0)
        self._sharp_gate_spin.setValue(0.0)
        self._cluster_cb.setChecked(True)
        self._cluster_spin.setValue(25)
        self._refine_cb.setChecked(True)
        self._refine_window_spin.setValue(10.0)
        self._update_effective_settings_preview()

    def effective_settings(self) -> dict:
        settings = {
            "ONSET_METHOD": self._method_combo.currentText(),
            "ONSET_HOP_LENGTH": self._hop_spin.value(),
            "ONSET_DELTA": self._delta_spin.value(),
            "ONSET_BACKTRACK": self._backtrack_cb.isChecked(),
        }
        method = settings["ONSET_METHOD"]
        if method == "adaptive_hp":
            settings.update(
                {
                    "HP_SMOOTH_LAMBDA": self._hp_smooth_spin.value(),
                    "HP_THRESHOLD_LAMBDA": self._hp_threshold_spin.value(),
                    "HP_ENVELOPE_WINDOW_MS": self._env_window_spin.value(),
                    "HP_ENVELOPE_HOP_MS": self._env_hop_spin.value(),
                }
            )
        elif method == "moving_median":
            settings.update(
                {
                    "HP_ENVELOPE_WINDOW_MS": self._env_window_spin.value(),
                    "HP_ENVELOPE_HOP_MS": self._env_hop_spin.value(),
                    "MEDIAN_WINDOW_MS": self._median_window_spin.value(),
                    "MEDIAN_THRESHOLD_SCALE": self._median_thresh_spin.value(),
                }
            )
        elif method == "superflux":
            settings.update(
                {
                    "SUPERFLUX_N_FFT": self._superflux_nfft_spin.value(),
                    "SUPERFLUX_LAG": self._superflux_lag_spin.value(),
                    "SUPERFLUX_MAX_SIZE": self._superflux_max_spin.value(),
                }
            )
        elif method == "cfar":
            settings.update(
                {
                    "HP_ENVELOPE_WINDOW_MS": self._env_window_spin.value(),
                    "HP_ENVELOPE_HOP_MS": self._env_hop_spin.value(),
                    "CFAR_GUARD_MS": self._cfar_guard_spin.value(),
                    "CFAR_TRAINING_MS": self._cfar_train_spin.value(),
                    "CFAR_THRESHOLD_FACTOR": self._cfar_thresh_spin.value(),
                }
            )
        elif method == "per_band":
            settings.update(
                {
                    "PER_BAND_N_FFT": self._perband_nfft_spin.value(),
                    "PER_BAND_N_BANDS": self._perband_bands_spin.value(),
                    "PER_BAND_FREQ_MIN": self._perband_fmin_spin.value(),
                    "PER_BAND_FREQ_MAX": self._perband_fmax_spin.value() or None,
                    "PER_BAND_MEDIAN_MS": self._median_window_spin.value(),
                    "PER_BAND_THRESHOLD_SCALE": self._median_thresh_spin.value(),
                    "PER_BAND_MIN_BANDS": self._perband_minbands_spin.value(),
                }
            )
        if self._post_enabled_cb.isChecked():
            settings.update(
                {
                    "MIN_INTER_ONSET_MS": self._min_ioi_spin.value(),
                    "ONSET_AMPLITUDE_GATE": self._amp_gate_spin.value(),
                    "ONSET_SHARPNESS_GATE": self._sharp_gate_spin.value(),
                    "CLUSTER_OVERLAPPING_ONSETS": self._cluster_cb.isChecked(),
                    "ONSET_CLUSTER_WINDOW_MS": self._cluster_spin.value(),
                    "ONSET_REFINE_ENABLED": self._refine_cb.isChecked(),
                    "ONSET_REFINE_WINDOW_MS": self._refine_window_spin.value(),
                }
            )
        else:
            settings.update(
                {
                    "MIN_INTER_ONSET_MS": 0,
                    "ONSET_AMPLITUDE_GATE": 0.0,
                    "ONSET_SHARPNESS_GATE": 0.0,
                    "CLUSTER_OVERLAPPING_ONSETS": False,
                    "ONSET_CLUSTER_WINDOW_MS": self._cluster_spin.value(),
                    "ONSET_REFINE_ENABLED": False,
                    "ONSET_REFINE_WINDOW_MS": self._refine_window_spin.value(),
                }
            )
        return settings

    def _update_effective_settings_preview(self):
        effective = self.effective_settings()
        lines = []
        lines.append(f"Requested onsets: {'Auto' if self._spin.value() == 0 else self._spin.value()}")
        lines.append("")
        for key, value in effective.items():
            lines.append(f"{key}: {value}")
        self._effective_text.setPlainText("\n".join(lines))

    def num_onsets(self) -> int:
        value = self._spin.value()
        return value if value > 0 else 999

    def selected_range(self) -> tuple[float, float]:
        if self._locked_range is not None:
            return self._locked_range
        start = min(self._start_spin.value(), self._end_spin.value())
        end = max(self._start_spin.value(), self._end_spin.value())
        return start, end

    def using_full_clip(self) -> bool:
        start, end = self.selected_range()
        return abs(start) < 1e-9 and abs(end - self._duration) < 1e-9

    def onset_method(self) -> str:
        return self._method_combo.currentText()

    def hop_length(self) -> int:
        return self._hop_spin.value()

    def initial_delta(self) -> float:
        return self._delta_spin.value()

    def backtrack(self) -> bool:
        return self._backtrack_cb.isChecked()

    def min_ioi_ms(self) -> int:
        return self._min_ioi_spin.value()

    def amplitude_gate(self) -> float:
        return self._amp_gate_spin.value()

    def sharpness_gate(self) -> float:
        return self._sharp_gate_spin.value()

    def cluster_enabled(self) -> bool:
        return self._cluster_cb.isChecked()

    def cluster_window_ms(self) -> int:
        return self._cluster_spin.value()

    def refine_enabled(self) -> bool:
        return self._refine_cb.isChecked()

    def post_processing_enabled(self) -> bool:
        return self._post_enabled_cb.isChecked()

    def refine_window_ms(self) -> float:
        return self._refine_window_spin.value()


class _NegativeSubtractionDialog(QDialog):
    """Dialog to review and remove onsets that match negative signal profiles."""

    SAVE_OVERWRITE = "overwrite"
    SAVE_NEW_LAYER = "new_layer"

    def __init__(
        self,
        neg_onset_times: list[float],
        neg_similarities: list[float],
        *,
        layers: list[dict],
        active_layer_idx: int = 0,
        checked_layer_indices: set[int] | None = None,
        neg_signal_indices: list[list[int]] | None = None,
        parent=None,
        viewer=None,
    ):
        super().__init__(parent)
        self._viewer = viewer
        self._editor_parent = parent
        self.setWindowTitle("Negative Signal Subtraction")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        self.setStyleSheet(
            "QDialog { background: #1e1e2e; color: #e0e0e0; }"
            "QLabel { color: #e0e0e0; }"
        )

        self._layers = layers
        self._neg_onset_times = list(neg_onset_times)
        self._neg_similarities = list(neg_similarities)
        self._neg_signal_indices = neg_signal_indices or []
        self._tolerance_ms = 10.0
        self._removed_indices: set[int] = set()

        if checked_layer_indices is None:
            self._selected_layer_indices: list[int] = [active_layer_idx]
        else:
            self._selected_layer_indices = sorted(checked_layer_indices)
        if not self._selected_layer_indices:
            self._selected_layer_indices = [active_layer_idx]

        self._combined_onsets: list[float] = []
        self._onset_layer_map: list[list[int]] = []
        self._rebuild_combined_onsets()
        self._matches = self._compute_matches()

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        layer_row = QHBoxLayout()
        layer_row.addWidget(QLabel("Onset Layer(s):"))
        self._layer_list_widget = QListWidget()
        self._layer_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._layer_list_widget.setMaximumHeight(min(28 * len(layers) + 6, 120))
        self._layer_list_widget.setStyleSheet(
            "QListWidget { background: #252538; color: #e0e0e0; "
            "border: 1px solid #3a3a5a; border-radius: 4px; font-size: 12px; }"
            "QListWidget::item { padding: 2px 6px; }"
            "QListWidget::item:selected { background: #3a4a6a; color: #81d4fa; }"
        )
        for layer_index, layer in enumerate(layers):
            name = layer.get("name", f"Layer {layer_index + 1}")
            count = len(layer.get("onset_times", []))
            self._layer_list_widget.addItem(f"{name}  ({count} onsets)")
        for layer_index in self._selected_layer_indices:
            if layer_index < self._layer_list_widget.count():
                self._layer_list_widget.item(layer_index).setSelected(True)
        self._layer_list_widget.itemSelectionChanged.connect(self._on_layer_selection_changed)
        layer_row.addWidget(self._layer_list_widget, stretch=1)
        main_layout.addLayout(layer_row)

        self._header_label = QLabel()
        self._header_label.setWordWrap(True)
        self._header_label.setStyleSheet("font-size: 13px; padding: 6px; color: #b0b0cc;")
        main_layout.addWidget(self._header_label)

        slider_group = QGroupBox("Match Tolerance")
        slider_group.setStyleSheet(
            "QGroupBox { border: 1px solid #3a3a5a; border-radius: 6px;"
            "  margin-top: 10px; padding-top: 14px; color: #b0b0cc; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; }"
        )
        slider_layout = QHBoxLayout(slider_group)

        self._tolerance_slider = QSlider(Qt.Orientation.Horizontal)
        self._tolerance_slider.setRange(1, 100)
        self._tolerance_slider.setValue(10)
        self._tolerance_slider.setStyleSheet(
            "QSlider::groove:horizontal { background: #2a2a3e; height: 6px; "
            "border-radius: 3px; }"
            "QSlider::handle:horizontal { background: #5c7cfa; width: 16px; "
            "margin: -5px 0; border-radius: 8px; }"
            "QSlider::sub-page:horizontal { background: #3a5afa; border-radius: 3px; }"
        )
        self._tolerance_slider.valueChanged.connect(self._on_tolerance_changed)
        slider_layout.addWidget(QLabel("Tight"))
        slider_layout.addWidget(self._tolerance_slider, stretch=1)
        slider_layout.addWidget(QLabel("Loose"))

        self._tolerance_value_label = QLabel("10 ms")
        self._tolerance_value_label.setStyleSheet(
            "font-weight: bold; color: #81d4fa; min-width: 60px;"
        )
        slider_layout.addWidget(self._tolerance_value_label)
        main_layout.addWidget(slider_group)

        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        self._summary_label.setStyleSheet(
            "font-size: 12px; padding: 6px; background: #252538; "
            "border-radius: 4px;"
        )
        main_layout.addWidget(self._summary_label)

        self._match_table = QTableWidget()
        self._match_table.setColumnCount(6)
        self._match_table.setHorizontalHeaderLabels(
            [
                "Neg. Sig #",
                "Existing Onset (s)",
                "Neg. Onset (s)",
                "Δ (ms)",
                "Match Type",
                "Status",
            ]
        )
        header = self._match_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._match_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._match_table.setStyleSheet(
            "QTableWidget { background: #1a1a2e; color: #e0e0e0; "
            "gridline-color: #2a2a4a; border: 1px solid #3a3a5a; }"
            "QHeaderView::section { background: #252540; color: #b0b0cc; "
            "border: 1px solid #2a2a4a; padding: 4px; }"
        )
        self._match_table.currentCellChanged.connect(self._on_match_table_row_changed)
        main_layout.addWidget(self._match_table, stretch=1)

        save_group = QGroupBox("Save Result As")
        save_group.setStyleSheet(
            "QGroupBox { border: 1px solid #3a3a5a; border-radius: 6px;"
            "  margin-top: 10px; padding-top: 14px; color: #b0b0cc; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; }"
            "QRadioButton { color: #e0e0e0; font-size: 12px; }"
        )
        save_layout = QHBoxLayout(save_group)
        self._save_btn_group = QButtonGroup(self)
        self._radio_overwrite = QRadioButton("Overwrite selected layer(s)")
        self._radio_new_layer = QRadioButton("Save as new layer")
        self._radio_overwrite.setChecked(True)
        self._save_btn_group.addButton(self._radio_overwrite, 0)
        self._save_btn_group.addButton(self._radio_new_layer, 1)
        save_layout.addWidget(self._radio_overwrite)
        save_layout.addWidget(self._radio_new_layer)
        save_layout.addStretch()
        main_layout.addWidget(save_group)

        btn_layout = QHBoxLayout()

        self._remove_exact_btn = QPushButton("🔵 Remove Exact Matches")
        self._remove_exact_btn.setStyleSheet(
            "QPushButton { background: #1a2a5a; color: #508cff; "
            "border: 1px solid #304a8b; border-radius: 4px; "
            "padding: 8px 16px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #2a3a7a; }"
        )
        self._remove_exact_btn.clicked.connect(self._remove_exact)

        self._remove_close_btn = QPushButton("🟠 Remove Close Matches")
        self._remove_close_btn.setStyleSheet(
            "QPushButton { background: #5a3a00; color: #ffb74d; "
            "border: 1px solid #8b6a15; border-radius: 4px; "
            "padding: 8px 16px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #7a4a00; }"
        )
        self._remove_close_btn.clicked.connect(self._remove_close)

        self._undo_btn = QPushButton("↩ Undo Removals")
        self._undo_btn.setStyleSheet(
            "QPushButton { background: #2a2a3e; color: #b0b0cc; "
            "border: 1px solid #3a3a5a; border-radius: 4px; "
            "padding: 8px 12px; font-size: 12px; }"
            "QPushButton:hover { background: #3a3a5a; }"
            "QPushButton:disabled { color: #444; }"
        )
        self._undo_btn.setEnabled(False)
        self._undo_btn.clicked.connect(self._undo_removals)

        self._confirm_btn = QPushButton("✅ Confirm & Keep Remaining")
        self._confirm_btn.setStyleSheet(
            "QPushButton { background: #1b5e20; color: white; "
            "border: 1px solid #2e7d32; border-radius: 4px; "
            "padding: 8px 16px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #2e7d32; }"
        )
        self._confirm_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            "QPushButton { background: #3a1a1a; color: #ef9a9a; "
            "border: 1px solid #5a2020; border-radius: 4px; "
            "padding: 8px 16px; font-size: 13px; }"
            "QPushButton:hover { border-color: #cc4444; }"
        )
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self._remove_exact_btn)
        btn_layout.addWidget(self._remove_close_btn)
        btn_layout.addWidget(self._undo_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self._confirm_btn)
        main_layout.addLayout(btn_layout)

        self._update_header()
        self._refresh_table()

    def _rebuild_combined_onsets(self):
        combined: dict[float, list[int]] = {}
        for layer_index in self._selected_layer_indices:
            if layer_index >= len(self._layers):
                continue
            for onset_time in self._layers[layer_index].get("onset_times", []):
                found = False
                for existing_time in list(combined.keys()):
                    if abs(onset_time - existing_time) < 0.001:
                        combined[existing_time].append(layer_index)
                        found = True
                        break
                if not found:
                    combined[onset_time] = [layer_index]
        sorted_times = sorted(combined.keys())
        self._combined_onsets = sorted_times
        self._onset_layer_map = [combined[onset_time] for onset_time in sorted_times]

    def _compute_matches(self) -> list[dict]:
        matches = []
        for neg_index, neg_time in enumerate(self._neg_onset_times):
            best_idx = -1
            best_delta = float("inf")
            for existing_idx, existing_time in enumerate(self._combined_onsets):
                delta = abs(neg_time - existing_time) * 1000
                if delta < best_delta:
                    best_delta = delta
                    best_idx = existing_idx
            similarity = self._neg_similarities[neg_index] if neg_index < len(self._neg_similarities) else 0.0
            signal_nums = self._neg_signal_indices[neg_index] if neg_index < len(self._neg_signal_indices) else []
            matches.append(
                {
                    "neg_time": neg_time,
                    "existing_idx": best_idx,
                    "existing_time": self._combined_onsets[best_idx] if best_idx >= 0 else None,
                    "delta_ms": best_delta,
                    "similarity": similarity,
                    "signal_nums": signal_nums,
                }
            )
        return matches

    def _update_header(self):
        names = []
        for layer_index in self._selected_layer_indices:
            if layer_index < len(self._layers):
                names.append(self._layers[layer_index].get("name", f"Layer {layer_index + 1}"))
        layer_text = ", ".join(names) if names else "none"
        self._header_label.setText(
            f"Found <b>{len(self._neg_onset_times)}</b> negative-signal onset(s) "
            f"to compare against <b>{len(self._combined_onsets)}</b> onset(s) "
            f"from: <i>{layer_text}</i>"
        )

    def _on_layer_selection_changed(self):
        selected = [
            index
            for index in range(self._layer_list_widget.count())
            if self._layer_list_widget.item(index).isSelected()
        ]
        if not selected:
            return
        self._selected_layer_indices = selected
        self._removed_indices.clear()
        self._undo_btn.setEnabled(False)
        self._rebuild_combined_onsets()
        self._matches = self._compute_matches()
        self._update_header()
        self._refresh_table()

    def _on_tolerance_changed(self, value: int):
        self._tolerance_ms = float(value)
        self._tolerance_value_label.setText(f"{value} ms")
        self._refresh_table()

    def _on_match_table_row_changed(self, row: int, col: int, prev_row: int, prev_col: int):
        if row < 0 or row >= len(self._rows_data):
            return
        match = self._rows_data[row]
        existing_time = match.get("existing_time")
        if existing_time is None:
            return

        if self._viewer is not None:
            self._viewer.scroll_to_time(existing_time)
            onset_arr = getattr(self._viewer, "_onset_times", None)
            if onset_arr is not None and len(onset_arr) > 0:
                diffs = [abs(onset_time - existing_time) for onset_time in onset_arr]
                best_idx = int(min(range(len(diffs)), key=lambda index: diffs[index]))
                if diffs[best_idx] < 0.001:
                    self._viewer._select_onset(best_idx)

        editor = self._editor_parent
        if editor is not None and hasattr(editor, "_onset_times"):
            for index, onset_time in enumerate(editor._onset_times):
                if abs(onset_time - existing_time) < 0.001:
                    editor._table.blockSignals(True)
                    editor._table.setCurrentCell(index, 0)
                    editor._table.blockSignals(False)
                    break

    def _refresh_table(self):
        tolerance = self._tolerance_ms
        exact_count = 0
        close_count = 0
        removed_count = len(self._removed_indices)
        exact_times: list[float] = []
        close_times: list[float] = []
        rows = []
        for match in self._matches:
            if match["existing_idx"] < 0:
                continue
            is_removed = match["existing_idx"] in self._removed_indices
            delta = match["delta_ms"]
            if is_removed:
                match_type = "Removed"
                color = "#555"
                status = "✗ Removed"
            elif delta <= 1.0:
                match_type = "Exact"
                color = "#508cff"
                exact_count += 1
                exact_times.append(match["existing_time"])
                status = "Remove?"
            elif delta <= tolerance:
                match_type = "Close"
                color = "#ffb74d"
                close_count += 1
                close_times.append(match["existing_time"])
                status = "Remove?"
            else:
                match_type = "-"
                color = "#666"
                status = "Keep"
            rows.append((match, match_type, color, status))

        self._rows_data = [match for match, _, _, _ in rows]

        self._match_table.setRowCount(len(rows))
        for row_index, (match, match_type, color, status) in enumerate(rows):
            signal_nums = match.get("signal_nums", [])
            signal_text = ", ".join(str(signal_num) for signal_num in signal_nums) if signal_nums else "-"
            items_text = [
                signal_text,
                f"{match['existing_time']:.4f}" if match["existing_time"] is not None else "-",
                f"{match['neg_time']:.4f}",
                f"{match['delta_ms']:.1f}",
                match_type,
                status,
            ]
            for column_index, text in enumerate(items_text):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(color))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._match_table.setItem(row_index, column_index, item)

        removed_text = ""
        if removed_count:
            removed_text = f"  |  <b style='color:#ef5350'>Removed: {removed_count}</b>"
        self._summary_label.setText(
            f"<b style='color:#508cff'>Exact matches: {exact_count}</b> "
            f"(within 1 ms)  |  "
            f"<b style='color:#ffb74d'>Close matches: {close_count}</b> "
            f"(within {tolerance:.0f} ms)  |  "
            f"Unmatched: {len(self._neg_onset_times) - exact_count - close_count - removed_count}"
            + removed_text
        )
        self._remove_exact_btn.setEnabled(exact_count > 0)
        self._remove_close_btn.setEnabled(close_count > 0)

        self._update_viewer_overlay(exact_times, close_times)

    def _remove_exact(self):
        added = 0
        for match in self._matches:
            if match["existing_idx"] >= 0 and match["delta_ms"] <= 1.0:
                if match["existing_idx"] not in self._removed_indices:
                    self._removed_indices.add(match["existing_idx"])
                    added += 1
        if added:
            self._undo_btn.setEnabled(True)
        self._refresh_table()

    def _remove_close(self):
        tolerance = self._tolerance_ms
        added = 0
        for match in self._matches:
            if match["existing_idx"] >= 0 and match["delta_ms"] <= tolerance:
                if match["existing_idx"] not in self._removed_indices:
                    self._removed_indices.add(match["existing_idx"])
                    added += 1
        if added:
            self._undo_btn.setEnabled(True)
        self._refresh_table()

    def _undo_removals(self):
        self._removed_indices.clear()
        self._undo_btn.setEnabled(False)
        self._refresh_table()

    def get_remaining_onsets(self) -> list[float]:
        return [
            onset_time
            for index, onset_time in enumerate(self._combined_onsets)
            if index not in self._removed_indices
        ]

    def get_removed_indices(self) -> set[int]:
        return set(self._removed_indices)

    def get_selected_layer_indices(self) -> list[int]:
        return list(self._selected_layer_indices)

    def get_save_mode(self) -> str:
        if self._radio_new_layer.isChecked():
            return self.SAVE_NEW_LAYER
        return self.SAVE_OVERWRITE

    def _update_viewer_overlay(self, exact_times: list[float], close_times: list[float]):
        if self._viewer is None:
            return
        self._viewer.clear_comparison_markers()
        overlay_layers = []
        if exact_times:
            overlay_layers.append(
                {
                    "times": exact_times,
                    "color": _NEG_EXACT_COLOR,
                    "style": Qt.PenStyle.SolidLine,
                }
            )
        if close_times:
            overlay_layers.append(
                {
                    "times": close_times,
                    "color": _NEG_CLOSE_COLOR,
                    "style": Qt.PenStyle.SolidLine,
                }
            )
        if overlay_layers:
            self._viewer.set_comparison_markers(overlay_layers)

    def _cleanup_viewer_overlay(self):
        if self._viewer is not None:
            self._viewer.clear_comparison_markers()

    def reject(self):
        self._cleanup_viewer_overlay()
        super().reject()

    def accept(self):
        self._cleanup_viewer_overlay()
        super().accept()


class _LayerCheckboxMenu(QMenu):
    """A QMenu-based popup showing a checkbox per onset layer."""

    layerSelectionChanged = pyqtSignal()

    SORT_CREATED = 0
    SORT_COUNT = 1
    SORT_ALPHA = 2
    _SORT_LABELS = ["⏱ Created", "🔢 Count", "🔤 A–Z"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QMenu {{ background: {_BG_WIDGET}; border: 1px solid {_BORDER}; "
            f"border-radius: 6px; padding: 4px; }}"
        )
        self._sort_mode = self.SORT_CREATED
        self._all_checked = True

        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(6, 4, 6, 2)
        top_layout.setSpacing(6)

        self._select_all_btn = QPushButton("☑ All")
        self._select_all_btn.setStyleSheet(
            f"QPushButton {{ background: {_BG_INPUT}; color: #aaccff; "
            f"border: 1px solid {_FOCUS_BLUE_BORDER}; border-radius: 3px; "
            f"padding: 2px 8px; font-size: 10px; }}"
            f"QPushButton:hover {{ border-color: {_FOCUS_BLUE_BRIGHT}; color: white; }}"
        )
        self._select_all_btn.clicked.connect(self._toggle_select_all)
        top_layout.addWidget(self._select_all_btn)

        self._sort_btn = QPushButton(self._SORT_LABELS[0])
        self._sort_btn.setStyleSheet(
            f"QPushButton {{ background: {_BG_INPUT}; color: #aaccff; "
            f"border: 1px solid {_FOCUS_BLUE_BORDER}; border-radius: 3px; "
            f"padding: 2px 8px; font-size: 10px; }}"
            f"QPushButton:hover {{ border-color: {_FOCUS_BLUE_BRIGHT}; color: white; }}"
        )
        self._sort_btn.clicked.connect(self._cycle_sort)
        top_layout.addWidget(self._sort_btn)

        top_layout.addStretch()

        top_action = QWidgetAction(self)
        top_action.setDefaultWidget(top_widget)
        self.addAction(top_action)

        self.addSeparator()

        self._cb_actions: list[tuple[QWidgetAction, QCheckBox, int]] = []

    def rebuild(self, layers: list[dict], checked_indices: set[int]):
        for action, _cb, _idx in self._cb_actions:
            self.removeAction(action)
        self._cb_actions.clear()

        indices = list(range(len(layers)))
        if self._sort_mode == self.SORT_COUNT:
            indices.sort(key=lambda i: -len(layers[i].get("onset_times", [])))
        elif self._sort_mode == self.SORT_ALPHA:
            indices.sort(key=lambda i: layers[i]["name"].lower())

        for idx in indices:
            layer = layers[idx]
            n = len(layer.get("onset_times", []))
            label = f"{layer['name']}  ({n})"

            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.setContentsMargins(8, 2, 8, 2)

            cb = QCheckBox(label)
            cb.blockSignals(True)
            cb.setChecked(idx in checked_indices)
            cb.blockSignals(False)
            cb.setStyleSheet(
                f"QCheckBox {{ color: {_TEXT}; font-size: 11px; spacing: 6px; }}"
                f"QCheckBox::indicator {{ width: 14px; height: 14px; "
                f"border: 1px solid {_BORDER}; border-radius: 3px; "
                f"background: {_BG_INPUT}; }}"
                f"QCheckBox::indicator:checked {{ background: {_FOCUS_BLUE}; "
                f"border-color: {_FOCUS_BLUE_BRIGHT}; }}"
            )
            cb.toggled.connect(self._on_checkbox_toggled)
            cb_layout.addWidget(cb)
            cb_layout.addStretch()

            swatch = QLabel()
            swatch.setFixedSize(12, 12)
            swatch.setStyleSheet("background: transparent; border: none;")
            cb_layout.addWidget(swatch)

            action = QWidgetAction(self)
            action.setDefaultWidget(cb_widget)
            self.addAction(action)
            self._cb_actions.append((action, cb, idx))

        self._update_swatches(checked_indices)

    def _update_swatches(self, checked: set[int]):
        ordered_checked = self.get_checked_indices()
        for _action, cb, layer_idx in self._cb_actions:
            swatch = cb.parent().findChildren(QLabel)
            if not swatch:
                continue
            sw = swatch[-1]
            if layer_idx in ordered_checked:
                pos = ordered_checked.index(layer_idx)
                if pos == 0:
                    sw.setStyleSheet(
                        "background: rgba(255, 80, 80, 220); "
                        "border: 1px solid #aa3333; border-radius: 2px;"
                    )
                else:
                    c = _LAYER_OVERLAY_COLORS[(pos - 1) % len(_LAYER_OVERLAY_COLORS)]
                    sw.setStyleSheet(
                        f"background: rgba({c[0]},{c[1]},{c[2]},{c[3]}); "
                        f"border: 1px solid rgba({c[0]},{c[1]},{c[2]},255); "
                        f"border-radius: 2px;"
                    )
            else:
                sw.setStyleSheet("background: transparent; border: none;")

    def get_checked_indices(self) -> list[int]:
        return [idx for _action, cb, idx in self._cb_actions if cb.isChecked()]

    def get_sort_mode(self) -> int:
        return self._sort_mode

    def _on_checkbox_toggled(self, _checked: bool):
        checked = set(self.get_checked_indices())
        self._update_swatches(checked)
        self.layerSelectionChanged.emit()

    def _toggle_select_all(self):
        self._all_checked = not self._all_checked
        for _action, cb, _idx in self._cb_actions:
            cb.blockSignals(True)
            cb.setChecked(self._all_checked)
            cb.blockSignals(False)
        self._select_all_btn.setText("☑ All" if self._all_checked else "☐ None")
        checked = set(self.get_checked_indices())
        self._update_swatches(checked)
        self.layerSelectionChanged.emit()

    def _cycle_sort(self):
        self._sort_mode = (self._sort_mode + 1) % 3
        self._sort_btn.setText(self._SORT_LABELS[self._sort_mode])
        self.layerSelectionChanged.emit()


class OnsetManagerDialog(QDialog):
    """Dialog for managing onset label files, comparison settings, colors, and Excel data export."""

    def __init__(
        self,
        parent=None,
        *,
        audio_path: str | None,
        label_path: str | None,
        onset_times: list[float],
        comp_files: list[dict],
        comp_palette: list[tuple],
        tolerance_ms: float,
        filter_idx: int,
        color_main_only: tuple,
        color_shared: tuple,
        onset_source: str = "txt",
        excel_onset_path: str | None = None,
        excel_onset_col: str = "Exact Onset Times Used (s)",
        excel_filename_col: str = "File Name",
        excel_sheet_name: str | int = "File Summaries",
    ):
        super().__init__(parent)
        self.setWindowTitle("Manage Onset / Excel Files")
        self.setMinimumWidth(720)
        self.setMinimumHeight(560)
        self.setStyleSheet(
            f"QDialog {{ background: {_BG}; color: {_TEXT}; }}"
            f"QGroupBox {{ background: {_BG_MID}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 6px; "
            f"margin-top: 14px; padding: 16px 10px 10px 10px; "
            f"font-weight: bold; font-size: 12px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 12px; "
            f"padding: 0 6px; color: {_ACCENT}; }}"
        )

        self._audio_path = audio_path
        self._label_path = label_path
        self._onset_times = onset_times
        self._onset_source = onset_source
        self._excel_onset_path = excel_onset_path
        self._excel_onset_col = excel_onset_col
        self._excel_filename_col = excel_filename_col
        self._excel_sheet_name = excel_sheet_name
        self._comp_files = [dict(cf) for cf in comp_files]
        self._comp_palette = list(comp_palette)
        self._tolerance_ms = tolerance_ms
        self._filter_idx = filter_idx
        self._color_main_only = tuple(color_main_only)
        self._color_shared = tuple(color_shared)
        self._changes: dict = {}

        self._build_ui()

    _BTN_STYLE = (
        f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
        f"border: 1px solid {_BORDER}; border-radius: 4px; "
        f"padding: 5px 14px; font-size: 12px; }}"
        f"QPushButton:hover {{ border-color: {_ACCENT}; color: white; }}"
        f"QPushButton:disabled {{ color: {_TEXT_MUTED}; border-color: {_BG_MID}; }}"
    )
    _ACCENT_BTN = (
        f"QPushButton {{ background: {_ACCENT_DIM}; color: white; "
        f"border: none; border-radius: 4px; "
        f"padding: 5px 14px; font-size: 12px; font-weight: bold; }}"
        f"QPushButton:hover {{ background: {_ACCENT}; }}"
        f"QPushButton:disabled {{ background: {_BORDER}; color: {_TEXT_MUTED}; }}"
    )
    _SMALL_BTN = (
        f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
        f"border: 1px solid {_BORDER}; border-radius: 4px; "
        f"padding: 3px 10px; font-size: 11px; }}"
        f"QPushButton:hover {{ border-color: {_ACCENT}; color: white; }}"
        f"QPushButton:disabled {{ color: {_TEXT_MUTED}; border-color: {_BG_MID}; }}"
    )
    _INPUT_STYLE = (
        f"QLineEdit {{ background: {_BG_INPUT}; color: {_TEXT}; "
        f"border: 1px solid {_BORDER}; border-radius: 4px; "
        f"padding: 3px 6px; font-size: 11px; }}"
    )
    _LBL_STYLE = f"color: {_TEXT_DIM}; font-size: 11px; background: transparent;"
    _CB_STYLE = f"QCheckBox {{ color: {_TEXT_DIM}; font-size: 11px; }}"

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {_BG}; }}")
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setSpacing(12)
        lay.setContentsMargins(8, 8, 8, 8)

        grp1 = QGroupBox("Manage Onset Files")
        g1 = QVBoxLayout(grp1)
        g1.setSpacing(6)

        self._build_main_row(g1)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet(f"background-color: {_BORDER}; max-height: 1px;")
        g1.addWidget(sep1)

        cmp_hdr = QLabel("Compare Labels")
        cmp_hdr.setStyleSheet(
            f"color: {_ACCENT}; font-size: 11px; font-weight: bold; "
            f"background: transparent; padding: 2px 0;"
        )
        g1.addWidget(cmp_hdr)

        cmp_row = QHBoxLayout()
        cmp_row.setSpacing(6)

        tol_label = QLabel("Tolerance:")
        tol_label.setStyleSheet(self._LBL_STYLE)
        cmp_row.addWidget(tol_label)

        self._tol_spin = QDoubleSpinBox()
        self._tol_spin.setRange(0.1, 100.0)
        self._tol_spin.setValue(self._tolerance_ms)
        self._tol_spin.setSuffix(" ms")
        self._tol_spin.setDecimals(1)
        self._tol_spin.setSingleStep(0.5)
        self._tol_spin.setStyleSheet(
            f"QDoubleSpinBox {{ background: {_BG_INPUT}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 2px 4px; font-size: 11px; }}"
        )
        cmp_row.addWidget(self._tol_spin)

        cmp_row.addSpacing(12)
        filter_label = QLabel("Show:")
        filter_label.setStyleSheet(self._LBL_STYLE)
        cmp_row.addWidget(filter_label)

        self._filter_combo = QComboBox()
        self._filter_combo.addItems([
            "All Onsets",
            "Main Only (unique)",
            "Shared (within tolerance)",
            "Comparison Only (unique)",
        ])
        self._filter_combo.setCurrentIndex(self._filter_idx)
        self._filter_combo.setStyleSheet(
            f"QComboBox {{ background: {_BG_INPUT}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 2px 6px; font-size: 11px; }}"
        )
        cmp_row.addWidget(self._filter_combo)

        cmp_row.addStretch()
        g1.addLayout(cmp_row)

        merge_row = QHBoxLayout()
        merge_row.setSpacing(6)
        merge_row.addStretch()

        self._add_shared_btn = QPushButton("+ Add Shared to Main")
        self._add_shared_btn.setToolTip(
            "Add comparison onsets that match within tolerance to the Main onset list"
        )
        self._add_shared_btn.setStyleSheet(self._SMALL_BTN)
        self._add_shared_btn.setEnabled(len(self._comp_files) > 0)
        self._add_shared_btn.clicked.connect(self._do_add_shared)
        merge_row.addWidget(self._add_shared_btn)

        self._add_unique_btn = QPushButton("+ Add Unique to Main")
        self._add_unique_btn.setToolTip(
            "Add comparison onsets NOT found in Main (unique to comparison files)"
        )
        self._add_unique_btn.setStyleSheet(self._SMALL_BTN)
        self._add_unique_btn.setEnabled(len(self._comp_files) > 0)
        self._add_unique_btn.clicked.connect(self._do_add_unique)
        merge_row.addWidget(self._add_unique_btn)

        self._remove_main_only_btn = QPushButton("− Remove Main-Only")
        self._remove_main_only_btn.setToolTip(
            "Remove onsets unique to Main (not confirmed by any comparison file)"
        )
        self._remove_main_only_btn.setStyleSheet(self._SMALL_BTN)
        self._remove_main_only_btn.setEnabled(len(self._comp_files) > 0)
        self._remove_main_only_btn.clicked.connect(self._do_remove_main_only)
        merge_row.addWidget(self._remove_main_only_btn)

        merge_row.addStretch()
        g1.addLayout(merge_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"background-color: {_BORDER}; max-height: 1px;")
        g1.addWidget(sep2)

        add_hdr = QLabel("Additional Onset Files")
        add_hdr.setStyleSheet(
            f"color: {_ACCENT}; font-size: 11px; font-weight: bold; "
            f"background: transparent; padding: 2px 0;"
        )
        g1.addWidget(add_hdr)

        self._comp_container = QVBoxLayout()
        self._comp_container.setSpacing(4)
        self._comp_widgets: list[dict] = []
        for i, cf in enumerate(self._comp_files):
            self._add_comp_row(cf, i)
        g1.addLayout(self._comp_container)

        self._comp_empty_label = QLabel("No comparison files loaded. Use 'Add Onset File…' below.")
        self._comp_empty_label.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: 11px; font-style: italic; padding: 4px;"
        )
        self._comp_empty_label.setVisible(len(self._comp_files) == 0)
        g1.addWidget(self._comp_empty_label)

        add_btn_row = QHBoxLayout()
        add_btn_row.addStretch()
        self._add_comp_btn = QPushButton("📂 Add Onset File…")
        self._add_comp_btn.setStyleSheet(self._BTN_STYLE)
        self._add_comp_btn.clicked.connect(self._add_comparison_file)
        add_btn_row.addWidget(self._add_comp_btn)

        self._add_excel_layers_btn = QPushButton("📊 Compare Excel Onset Layers…")
        self._add_excel_layers_btn.setStyleSheet(self._BTN_STYLE)
        self._add_excel_layers_btn.setToolTip(
            "Load onset times from Excel layer columns and add as comparison files"
        )
        self._add_excel_layers_btn.clicked.connect(self._add_excel_layer_comparisons)
        add_btn_row.addWidget(self._add_excel_layers_btn)

        add_btn_row.addStretch()
        g1.addLayout(add_btn_row)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet(f"background-color: {_BORDER}; max-height: 1px;")
        g1.addWidget(sep3)

        color_hdr = QLabel("Onset Comparison Colors")
        color_hdr.setStyleSheet(
            f"color: {_ACCENT}; font-size: 11px; font-weight: bold; "
            f"background: transparent; padding: 2px 0;"
        )
        g1.addWidget(color_hdr)
        self._build_color_section(g1)

        grp2 = QGroupBox("Excel Manager")
        g2 = QVBoxLayout(grp2)
        g2.setSpacing(6)
        self._build_excel_section(g2)
        lay.addWidget(grp2)
        lay.addWidget(grp1)

        lay.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 5px 20px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
        )
        btn_box.rejected.connect(self.accept)
        root.addWidget(btn_box)

    def _build_main_row(self, parent_layout):
        row_w = QWidget()
        row_lay = QHBoxLayout(row_w)
        row_lay.setContentsMargins(4, 2, 4, 2)
        row_lay.setSpacing(6)

        r, g, b, a = (255, 80, 80, 220)
        color_dot = QLabel(f'<span style="color:rgba({r},{g},{b},{a / 255:.1f});">●</span>')
        color_dot.setStyleSheet("font-size: 14px; background: transparent;")
        row_lay.addWidget(color_dot)

        name = os.path.basename(self._label_path) if self._label_path else "(none)"
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"color: {_TEXT}; font-size: 11px; background: transparent;")
        name_lbl.setToolTip(self._label_path or "")
        name_lbl.setMinimumWidth(40)
        row_lay.addWidget(name_lbl, stretch=1)

        n = len(self._onset_times)
        count_lbl = QLabel(f"({n} onset{'s' if n != 1 else ''})")
        count_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px; background: transparent;")
        row_lay.addWidget(count_lbl)

        save_btn = QPushButton("💾 Overwrite")
        save_btn.setStyleSheet(self._ACCENT_BTN)
        save_btn.setToolTip("Overwrite the current onset label file with edited onsets")
        save_btn.setEnabled(self._label_path is not None)
        save_btn.setMinimumWidth(90)
        save_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        save_btn.clicked.connect(self._save_main_overwrite)
        row_lay.addWidget(save_btn)

        save_new_btn = QPushButton("📄 Save New")
        save_new_btn.setStyleSheet(self._BTN_STYLE)
        save_new_btn.setToolTip("Save onsets to a new file alongside the original")
        save_new_btn.setMinimumWidth(80)
        save_new_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        save_new_btn.clicked.connect(self._save_main_new)
        row_lay.addWidget(save_new_btn)

        row_w.setStyleSheet(f"background: {_BG_WIDGET}; border-radius: 4px;")
        parent_layout.addWidget(row_w)

        self._auto_detect_excel()

        ex_btn_row = QHBoxLayout()
        ex_btn_row.setSpacing(8)
        ex_btn_row.addStretch()
        self._excel_overwrite_btn = QPushButton("📊 Excel: Update Onset Data (Overwrite)")
        self._excel_overwrite_btn.setStyleSheet(self._ACCENT_BTN)
        self._excel_overwrite_btn.setToolTip(
            "Update this recording's onset data in the existing Excel file"
        )
        self._excel_overwrite_btn.clicked.connect(self._excel_save_overwrite)
        ex_btn_row.addWidget(self._excel_overwrite_btn)

        self._excel_new_btn = QPushButton("📄 Excel: Save Onset Data (New file)")
        self._excel_new_btn.setStyleSheet(self._BTN_STYLE)
        self._excel_new_btn.setToolTip("Save this recording's onset data to a new Excel file")
        self._excel_new_btn.clicked.connect(self._excel_save_new)
        ex_btn_row.addWidget(self._excel_new_btn)
        ex_btn_row.addStretch()
        parent_layout.addLayout(ex_btn_row)

        combine_row = QHBoxLayout()
        combine_row.addStretch()
        self._combine_layers_btn = QPushButton("🔗 Combine Onset Layer Columns")
        self._combine_layers_btn.setStyleSheet(self._BTN_STYLE)
        self._combine_layers_btn.setToolTip(
            "Create a combined column merging all layer onset times in the Excel file"
        )
        self._combine_layers_btn.clicked.connect(self._combine_excel_layers)
        combine_row.addWidget(self._combine_layers_btn)
        combine_row.addStretch()
        parent_layout.addLayout(combine_row)

    def _add_comp_row(self, cf: dict, index: int):
        row_w = QWidget()
        row_lay = QHBoxLayout(row_w)
        row_lay.setContentsMargins(4, 2, 4, 2)
        row_lay.setSpacing(6)

        remove_btn = QPushButton("−")
        remove_btn.setFixedSize(22, 22)
        remove_btn.setStyleSheet(
            "QPushButton { background: #c62828; color: white; "
            "border: none; border-radius: 11px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background: #e53935; }"
        )
        remove_btn.setToolTip(f"Remove {cf['label']} from comparison")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(lambda _, i=index: self._remove_comp(i))
        row_lay.addWidget(remove_btn)

        r, g, b, a = cf["color"]
        color_dot = QLabel(f'<span style="color:rgba({r},{g},{b},{a / 255:.1f});">●</span>')
        color_dot.setStyleSheet("font-size: 14px; background: transparent;")
        row_lay.addWidget(color_dot)

        name_lbl = QLabel(cf["label"])
        name_lbl.setStyleSheet(f"color: {_TEXT}; font-size: 11px; background: transparent;")
        name_lbl.setToolTip(cf["path"])
        name_lbl.setMinimumWidth(40)
        row_lay.addWidget(name_lbl, stretch=1)

        count_lbl = QLabel(f"({len(cf['times'])} onsets)")
        count_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px; background: transparent;")
        row_lay.addWidget(count_lbl)

        save_btn = QPushButton("💾 Overwrite")
        save_btn.setStyleSheet(self._BTN_STYLE)
        save_btn.setToolTip(f"Overwrite {cf['label']} with current edits")
        save_btn.setMinimumWidth(90)
        save_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        save_btn.clicked.connect(lambda _, i=index: self._save_comp_overwrite(i))
        row_lay.addWidget(save_btn)

        save_new_btn = QPushButton("📄 Save New")
        save_new_btn.setStyleSheet(self._BTN_STYLE)
        save_new_btn.setToolTip(f"Save edits for {cf['label']} as a new file")
        save_new_btn.setMinimumWidth(80)
        save_new_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        save_new_btn.clicked.connect(lambda _, i=index: self._save_comp_new(i))
        row_lay.addWidget(save_new_btn)

        row_w.setStyleSheet(f"background: {_BG_WIDGET}; border-radius: 4px;")
        self._comp_container.addWidget(row_w)
        self._comp_widgets.append({"widget": row_w, "name": name_lbl, "count": count_lbl})

    def _build_color_section(self, parent_layout):
        self._color_btns: dict[str, QPushButton] = {}

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(self._make_color_swatch("Main Only", "main_only", self._color_main_only))
        row1.addSpacing(16)
        row1.addWidget(self._make_color_swatch("Shared", "shared", self._color_shared))
        row1.addStretch()
        parent_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        for i, color in enumerate(self._comp_palette):
            row2.addWidget(self._make_color_swatch(f"Comp {i + 1}", f"comp_{i}", color))
        row2.addStretch()
        parent_layout.addLayout(row2)

    def _make_color_swatch(self, label_text: str, key: str, color: tuple) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        lbl = QLabel(f"{label_text}:")
        lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px; background: transparent;")
        lay.addWidget(lbl)

        btn = QPushButton()
        btn.setFixedSize(24, 24)
        r, g, b, a = color
        btn.setStyleSheet(
            f"QPushButton {{ background: rgba({r},{g},{b},{a / 255:.1f}); "
            f"border: 1px solid {_BORDER}; border-radius: 4px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
        )
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(f"Click to change {label_text} color")
        btn.clicked.connect(lambda _, k=key: self._pick_color(k))
        lay.addWidget(btn)

        self._color_btns[key] = btn
        return container

    def _pick_color(self, key: str):
        if key == "main_only":
            current = self._color_main_only
        elif key == "shared":
            current = self._color_shared
        elif key.startswith("comp_"):
            idx = int(key.split("_")[1])
            current = self._comp_palette[idx]
        else:
            return

        r, g, b, a = current
        initial = QColor(r, g, b, a)
        color = QColorDialog.getColor(
            initial,
            self,
            "Choose color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if not color.isValid():
            return

        new_rgba = (color.red(), color.green(), color.blue(), color.alpha())
        if key == "main_only":
            self._color_main_only = new_rgba
        elif key == "shared":
            self._color_shared = new_rgba
        elif key.startswith("comp_"):
            idx = int(key.split("_")[1])
            self._comp_palette[idx] = new_rgba
            if idx < len(self._comp_files):
                self._comp_files[idx]["color"] = new_rgba

        r, g, b, a = new_rgba
        self._color_btns[key].setStyleSheet(
            f"QPushButton {{ background: rgba({r},{g},{b},{a / 255:.1f}); "
            f"border: 1px solid {_BORDER}; border-radius: 4px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
        )

    def _build_excel_section(self, parent_layout):
        ex_in_row = QHBoxLayout()
        ex_in_row.setSpacing(6)
        ex_in_lbl = QLabel("Input Excel:")
        ex_in_lbl.setStyleSheet(self._LBL_STYLE)
        ex_in_row.addWidget(ex_in_lbl)
        self._excel_input_edit = QLineEdit()
        self._excel_input_edit.setPlaceholderText("(auto-detected from audio folder)")
        self._excel_input_edit.setReadOnly(True)
        self._excel_input_edit.setStyleSheet(self._INPUT_STYLE)
        ex_in_row.addWidget(self._excel_input_edit, stretch=1)
        self._excel_input_browse = QPushButton("Browse…")
        self._excel_input_browse.setStyleSheet(self._BTN_STYLE)
        self._excel_input_browse.clicked.connect(self._browse_excel_input)
        ex_in_row.addWidget(self._excel_input_browse)
        self._excel_input_auto = QCheckBox("Auto-set")
        self._excel_input_auto.setChecked(True)
        self._excel_input_auto.setStyleSheet(self._CB_STYLE)
        self._excel_input_auto.setToolTip("Auto-detect Excel from the audio folder")
        self._excel_input_auto.toggled.connect(self._on_excel_input_auto)
        ex_in_row.addWidget(self._excel_input_auto)
        parent_layout.addLayout(ex_in_row)

        ex_out_row = QHBoxLayout()
        ex_out_row.setSpacing(6)
        ex_out_lbl = QLabel("Output Excel:")
        ex_out_lbl.setStyleSheet(self._LBL_STYLE)
        ex_out_row.addWidget(ex_out_lbl)
        self._excel_output_edit = QLineEdit()
        self._excel_output_edit.setPlaceholderText("(same as input by default)")
        self._excel_output_edit.setReadOnly(True)
        self._excel_output_edit.setStyleSheet(self._INPUT_STYLE)
        ex_out_row.addWidget(self._excel_output_edit, stretch=1)
        self._excel_output_browse = QPushButton("Browse…")
        self._excel_output_browse.setStyleSheet(self._BTN_STYLE)
        self._excel_output_browse.clicked.connect(self._browse_excel_output)
        ex_out_row.addWidget(self._excel_output_browse)
        self._excel_output_auto = QCheckBox("Auto-set")
        self._excel_output_auto.setChecked(True)
        self._excel_output_auto.setStyleSheet(self._CB_STYLE)
        self._excel_output_auto.setToolTip("Use the same path as the input Excel file")
        self._excel_output_auto.toggled.connect(self._on_excel_output_auto)
        ex_out_row.addWidget(self._excel_output_auto)
        parent_layout.addLayout(ex_out_row)

        self._auto_detect_excel()

        ex_btn_row = QHBoxLayout()
        ex_btn_row.setSpacing(8)
        ex_btn_row.addStretch()
        self._excel_overwrite_btn = QPushButton("📊 Excel: Update Onset Data (Overwrite)")
        self._excel_overwrite_btn.setStyleSheet(self._ACCENT_BTN)
        self._excel_overwrite_btn.setToolTip(
            "Update this recording's onset data in the existing Excel file"
        )
        self._excel_overwrite_btn.clicked.connect(self._excel_save_overwrite)
        ex_btn_row.addWidget(self._excel_overwrite_btn)

        self._excel_new_btn = QPushButton("📄 Excel: Save Onset Data (New file)")
        self._excel_new_btn.setStyleSheet(self._BTN_STYLE)
        self._excel_new_btn.setToolTip("Save this recording's onset data to a new Excel file")
        self._excel_new_btn.clicked.connect(self._excel_save_new)
        ex_btn_row.addWidget(self._excel_new_btn)
        ex_btn_row.addStretch()
        parent_layout.addLayout(ex_btn_row)

    def _save_main_overwrite(self):
        if self._onset_source == "excel" and self._excel_onset_path:
            if not self._audio_path:
                QMessageBox.warning(self, "No Audio", "No audio file loaded.")
                return
            fname = os.path.basename(self._audio_path)
            parent = self.parent()
            if parent and hasattr(parent, "_write_recording_to_excel"):
                parent._write_recording_to_excel(self._excel_onset_path, fname, self._onset_times)
                QMessageBox.information(
                    self,
                    "Saved",
                    f"Updated onset data for {fname} in {os.path.basename(self._excel_onset_path)}",
                )
            else:
                QMessageBox.warning(self, "Error", "Could not access Excel writer.")
            return
        if not self._label_path:
            QMessageBox.warning(self, "No File", "No onset file is set. Use 'Save New' instead.")
            return
        _save_labels(self._label_path, self._onset_times)
        self._changes["main_label_path"] = self._label_path
        QMessageBox.information(
            self,
            "Saved",
            f"Saved {len(self._onset_times)} onsets → {os.path.basename(self._label_path)}",
        )

    def _save_main_new(self):
        start = os.path.dirname(self._label_path or self._excel_onset_path or self._audio_path or "")
        if self._audio_path:
            stem = os.path.splitext(os.path.basename(self._audio_path))[0]
            default_name = os.path.join(start, f"{stem}_labels_edited.txt")
        else:
            default_name = start
        path, _filt = QFileDialog.getSaveFileName(
            self,
            "Save Onset File As",
            default_name,
            "Label Files (*.txt);;Excel Files (*.xlsx);;All Files (*)",
        )
        if not path:
            return
        if path.lower().endswith(".xlsx"):
            if not self._audio_path:
                QMessageBox.warning(self, "No Audio", "No audio file loaded.")
                return
            fname = os.path.basename(self._audio_path)
            source = self._excel_onset_path or None
            parent = self.parent()
            if parent and hasattr(parent, "_write_recording_to_excel"):
                parent._write_recording_to_excel(path, fname, self._onset_times, source_excel=source)
                QMessageBox.information(
                    self,
                    "Saved",
                    f"Saved onset data for {fname} → {os.path.basename(path)}",
                )
            else:
                QMessageBox.warning(self, "Error", "Could not access Excel writer.")
        else:
            _save_labels(path, self._onset_times)
            self._label_path = path
            self._changes["main_label_path"] = path
            QMessageBox.information(
                self,
                "Saved",
                f"Saved {len(self._onset_times)} onsets → {os.path.basename(path)}",
            )

    def _add_comparison_file(self):
        start = os.path.dirname(self._audio_path or "")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Add Comparison Onset File",
            start,
            "Label Files (*.txt);;All Files (*)",
        )
        if not path:
            return
        for cf in self._comp_files:
            if os.path.abspath(cf["path"]) == os.path.abspath(path):
                QMessageBox.information(self, "Already Loaded", f"{os.path.basename(path)} is already loaded.")
                return
        times = _load_labels(path)
        if not times:
            QMessageBox.warning(self, "Empty File", f"No onset times found in:\n{os.path.basename(path)}")
            return
        idx = len(self._comp_files)
        color = self._comp_palette[idx % len(self._comp_palette)]
        entry = {"path": path, "label": os.path.basename(path), "times": times, "color": color}
        self._comp_files.append(entry)
        self._add_comp_row(entry, idx)
        self._comp_empty_label.hide()
        self._changes["comp_files"] = self._comp_files
        self._update_merge_button_states()

    def _add_excel_layer_comparisons(self):
        excel_path = getattr(self, "_excel_input_edit", None)
        if excel_path is not None:
            excel_path = excel_path.text().strip()
        if not excel_path:
            parent = self.parent()
            if parent and hasattr(parent, "_excel_onset_path"):
                excel_path = parent._excel_onset_path
        if not excel_path or not os.path.isfile(excel_path):
            QMessageBox.warning(
                self,
                "No Excel File",
                "No Excel file found. Set one in the Excel Manager section or ensure one exists in the audio folder.",
            )
            return

        try:
            import pandas as pd

            df = pd.read_excel(excel_path, sheet_name=0, engine="openpyxl")
        except Exception as exc:
            QMessageBox.warning(self, "Excel Error", str(exc))
            return

        onset_cols = []
        for col in df.columns:
            col_str = str(col)
            if any(pat in col_str.lower() for pat in ("onset_times_", "onset times", "exact onset")):
                onset_cols.append(col_str)
        if not onset_cols:
            QMessageBox.information(
                self,
                "No Layer Columns",
                "No onset layer columns found in the Excel file.\nExpected columns like 'Onset_Times_1', 'Onset_Times_2', or 'Onset Times — Layer N (s)'.",
            )
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Select Excel Onset Columns")
        dlg.setMinimumWidth(400)
        dlg_lay = QVBoxLayout(dlg)
        dlg_lay.addWidget(QLabel("Select columns to compare:"))
        lw = QListWidget()
        lw.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for item in onset_cols:
            lw.addItem(item)
        for i in range(lw.count()):
            lw.item(i).setSelected(True)
        dlg_lay.addWidget(lw)
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        dlg_lay.addWidget(btn_box)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected = [lw.item(i).text() for i in range(lw.count()) if lw.item(i).isSelected()]
        if not selected:
            return

        audio_name = os.path.basename(self._audio_path) if self._audio_path else ""
        fname_col = None
        for c in df.columns:
            if "file" in str(c).lower() and "name" in str(c).lower():
                fname_col = str(c)
                break
        if fname_col is None:
            fname_col = str(df.columns[0])

        added = 0
        for col_name in selected:
            label = f"Excel: {col_name}"
            if any(cf.get("label") == label for cf in self._comp_files):
                continue
            if _HAS_EXCEL_IO:
                times = _eio.load_onsets_for_file(excel_path, audio_name, fname_col, col_name)
            else:
                mask = df[fname_col].astype(str).str.strip().str.lower() == audio_name.strip().lower()
                matches = df.loc[mask, col_name]
                if matches.empty:
                    continue
                cell = matches.iloc[0]
                if pd.isna(cell):
                    continue
                import re

                times = sorted(float(x) for x in re.findall(r"[\d.]+", str(cell)) if x)
            if not times:
                continue
            idx = len(self._comp_files)
            color = self._comp_palette[idx % len(self._comp_palette)]
            entry = {"path": excel_path, "label": label, "times": times, "color": color}
            self._comp_files.append(entry)
            self._add_comp_row(entry, idx)
            added += 1

        if added:
            self._comp_empty_label.hide()
            self._changes["comp_files"] = self._comp_files
            self._update_merge_button_states()
            QMessageBox.information(self, "Layers Loaded", f"Added {added} Excel onset layer(s) for comparison.")
        else:
            QMessageBox.information(
                self,
                "No New Layers",
                "No new onset data found in the selected columns for this audio file.",
            )

    def _remove_comp(self, index: int):
        if index < 0 or index >= len(self._comp_files):
            return
        self._comp_files.pop(index)
        for w in self._comp_widgets:
            w["widget"].setParent(None)
        self._comp_widgets.clear()
        for i, cf in enumerate(self._comp_files):
            self._add_comp_row(cf, i)
        self._comp_empty_label.setVisible(len(self._comp_files) == 0)
        self._changes["comp_files"] = self._comp_files
        self._update_merge_button_states()

    def _update_merge_button_states(self):
        has_comp = len(self._comp_files) > 0
        self._add_shared_btn.setEnabled(has_comp)
        self._add_unique_btn.setEnabled(has_comp)
        self._remove_main_only_btn.setEnabled(has_comp)

    def _save_comp_overwrite(self, index: int):
        if index < 0 or index >= len(self._comp_files):
            return
        cf = self._comp_files[index]
        _save_labels(cf["path"], cf["times"])
        QMessageBox.information(self, "Saved", f"Saved {len(cf['times'])} onsets → {os.path.basename(cf['path'])}")

    def _save_comp_new(self, index: int):
        if index < 0 or index >= len(self._comp_files):
            return
        cf = self._comp_files[index]
        start = os.path.dirname(cf["path"])
        stem = os.path.splitext(cf["label"])[0]
        default_name = os.path.join(start, f"{stem}_edited.txt")
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save {cf['label']} As",
            default_name,
            "Label Files (*.txt);;All Files (*)",
        )
        if not path:
            return
        _save_labels(path, cf["times"])
        QMessageBox.information(self, "Saved", f"Saved {len(cf['times'])} onsets → {os.path.basename(path)}")

    def _do_add_shared(self):
        parent = self.parent()
        if parent:
            parent._comp_tolerance_ms = self._tol_spin.value()
            parent._comp_add_shared_to_main()

    def _do_add_unique(self):
        parent = self.parent()
        if parent:
            parent._comp_tolerance_ms = self._tol_spin.value()
            parent._comp_add_unique_to_main()

    def _do_remove_main_only(self):
        parent = self.parent()
        if parent:
            parent._comp_tolerance_ms = self._tol_spin.value()
            parent._comp_remove_main_only()

    def _auto_detect_excel(self):
        if not self._audio_path:
            return
        audio_folder = os.path.dirname(self._audio_path)
        candidates = [
            os.path.join(audio_folder, "data", "AudioData_OnsetFinder.xlsx"),
            os.path.join(audio_folder, "AudioData_OnsetFinder.xlsx"),
            os.path.join(audio_folder, "Cross_Species_Rhythm_Data.xlsx"),
            os.path.join(audio_folder, "data", "Cross_Species_Rhythm_Data.xlsx"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                self._excel_input_edit.setText(c)
                if self._excel_output_auto.isChecked():
                    self._excel_output_edit.setText(c)
                return

    def _browse_excel_input(self):
        start = os.path.dirname(self._audio_path or "")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Input Excel",
            start,
            "Excel Files (*.xlsx *.xls);;All Files (*)",
        )
        if path:
            self._excel_input_edit.setText(path)
            if self._excel_output_auto.isChecked():
                self._excel_output_edit.setText(path)

    def _browse_excel_output(self):
        start = os.path.dirname(self._excel_input_edit.text() or self._audio_path or "")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Output Excel",
            start,
            "Excel Files (*.xlsx);;All Files (*)",
        )
        if path:
            self._excel_output_edit.setText(path)

    def _on_excel_input_auto(self, checked: bool):
        self._excel_input_browse.setEnabled(not checked)
        if checked:
            self._auto_detect_excel()

    def _on_excel_output_auto(self, checked: bool):
        self._excel_output_browse.setEnabled(not checked)
        if checked and self._excel_input_edit.text():
            self._excel_output_edit.setText(self._excel_input_edit.text())

    def _excel_save_overwrite(self):
        excel_path = self._excel_output_edit.text() or self._excel_input_edit.text()
        if not excel_path:
            QMessageBox.warning(self, "No Excel File", "Set an Excel file path first.")
            return
        if not self._audio_path:
            QMessageBox.warning(self, "No Audio", "No audio file loaded.")
            return
        fname = os.path.basename(self._audio_path)
        parent = self.parent()
        if parent and hasattr(parent, "_write_recording_to_excel"):
            parent._write_recording_to_excel(excel_path, fname, self._onset_times)
            QMessageBox.information(
                self,
                "Saved",
                f"Updated onset data for {fname} in {os.path.basename(excel_path)}",
            )
        else:
            QMessageBox.warning(self, "Error", "Could not access Excel writer.")

    def _excel_save_new(self):
        start = os.path.dirname(self._excel_input_edit.text() or self._audio_path or "")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Excel As",
            start,
            "Excel Files (*.xlsx);;All Files (*)",
        )
        if not path:
            return
        if not self._audio_path:
            QMessageBox.warning(self, "No Audio", "No audio file loaded.")
            return
        fname = os.path.basename(self._audio_path)
        source = self._excel_input_edit.text() or None
        parent = self.parent()
        if parent and hasattr(parent, "_write_recording_to_excel"):
            parent._write_recording_to_excel(path, fname, self._onset_times, source_excel=source)
            QMessageBox.information(
                self,
                "Saved",
                f"Saved onset data for {fname} → {os.path.basename(path)}",
            )
        else:
            QMessageBox.warning(self, "Error", "Could not access Excel writer.")

    def _combine_excel_layers(self):
        excel_path = self._excel_input_edit.text().strip()
        if not excel_path or not os.path.isfile(excel_path):
            QMessageBox.warning(
                self,
                "No Excel File",
                "Set an Excel file in the Excel Manager section first.",
            )
            return

        try:
            import pandas as pd

            df = pd.read_excel(excel_path, sheet_name=0, engine="openpyxl")
        except Exception as exc:
            QMessageBox.warning(self, "Excel Error", str(exc))
            return

        layer_cols = []
        for col in df.columns:
            col_str = str(col)
            if any(pat in col_str.lower() for pat in ("onset_times_", "onset times —")):
                layer_cols.append(col_str)
        if not layer_cols:
            QMessageBox.information(
                self,
                "No Layer Columns",
                "No onset layer columns (e.g. 'Onset_Times_1', 'Onset Times — Layer N (s)') found in the Excel file.",
            )
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Combine Onset Layer Columns")
        dlg.setMinimumWidth(400)
        dlg_lay = QVBoxLayout(dlg)
        dlg_lay.addWidget(QLabel("Select columns to combine:"))
        lw = QListWidget()
        lw.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for item in layer_cols:
            lw.addItem(item)
        for i in range(lw.count()):
            lw.item(i).setSelected(True)
        dlg_lay.addWidget(lw)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Combined column name:"))
        name_edit = QLineEdit("Onset Times Used (s)_Combined")
        name_row.addWidget(name_edit)
        dlg_lay.addLayout(name_row)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        dlg_lay.addWidget(btn_box)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected = [lw.item(i).text() for i in range(lw.count()) if lw.item(i).isSelected()]
        if not selected:
            return

        combined_name = name_edit.text().strip() or "Onset Times Used (s)_Combined"

        insert_before = None
        for col in df.columns:
            if "exact onset" in str(col).lower():
                insert_before = str(col)
                break

        fname_col = None
        for c in df.columns:
            if "file" in str(c).lower() and "name" in str(c).lower():
                fname_col = str(c)
                break
        if not fname_col:
            fname_col = str(df.columns[0])

        try:
            if _HAS_EXCEL_IO:
                result = _eio.combine_onset_columns(
                    file_path=excel_path,
                    filename_col=fname_col,
                    source_columns=selected,
                    combined_col_name=combined_name,
                    insert_before=insert_before,
                )
                QMessageBox.information(
                    self,
                    "Combined Column Created",
                    f"Column '{result['column']}' created with {result['rows_updated']} row(s) updated.\nSaved to: {os.path.basename(result['path'])}",
                )
            else:
                QMessageBox.warning(self, "Missing Module", "excel_onset_io module not available.")
        except Exception as exc:
            QMessageBox.warning(self, "Error Creating Combined Column", str(exc))

    def get_changes(self) -> dict:
        self._changes["tolerance_ms"] = self._tol_spin.value()
        self._changes["filter_idx"] = self._filter_combo.currentIndex()
        self._changes["color_main_only"] = self._color_main_only
        self._changes["color_shared"] = self._color_shared
        self._changes["comp_palette"] = list(self._comp_palette)
        self._changes["comp_files"] = self._comp_files
        return self._changes


class _PerSignalConfigDialog(QDialog):
    """Compact dialog for configuring per-signal match tolerances."""

    def __init__(self, profiles: list[dict], *, parent=None, mode: str = "positive", y=None, sr: int | None = None):
        super().__init__(parent)
        self._profiles = list(profiles)
        self._mode = mode
        self._y = y
        self._sr = sr
        self._var_rows: list[dict] = []

        title = "Per-Signal Match Settings"
        if mode == "negative":
            title = "Negative Signal Match Settings"
        self.setWindowTitle(title)
        self.setMinimumWidth(680)
        self.resize(760, 620)
        self.setStyleSheet(
            f"QDialog {{ background: {_BG}; color: {_TEXT}; }}"
            f"QLabel {{ color: {_TEXT}; background: transparent; }}"
            f"QGroupBox {{ background: {_BG_MID}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 6px; "
            f"margin-top: 10px; padding-top: 14px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {_ACCENT}; }}"
            f"QCheckBox {{ color: {_TEXT}; }}"
            f"QDoubleSpinBox {{ background: {_BG_INPUT}; color: {_TEXT}; border: 1px solid {_BORDER}; border-radius: 4px; padding: 4px; }}"
            f"QPlainTextEdit {{ background: {_BG_WIDGET}; color: {_TEXT}; border: 1px solid {_BORDER}; border-radius: 4px; padding: 6px; }}"
        )

        root = QVBoxLayout(self)
        root.setSpacing(8)

        intro = QLabel(
            "Configure how strictly candidate onsets should match the selected exemplar signals. "
            "This compact version applies one shared tolerance per variable across all selected signals."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        root.addWidget(intro)

        summary_group = QGroupBox("Selected Signals")
        summary_layout = QVBoxLayout(summary_group)
        self._summary_text = QPlainTextEdit()
        self._summary_text.setReadOnly(True)
        self._summary_text.setMinimumHeight(220)
        self._summary_text.setPlainText(self._build_profile_summary())
        summary_layout.addWidget(self._summary_text)
        root.addWidget(summary_group)

        cfg_group = QGroupBox("Shared Variable Tolerances")
        cfg_layout = QVBoxLayout(cfg_group)
        cfg_layout.setSpacing(6)

        for key, label_text, unit, default_pct in _SIGNAL_VARIABLES:
            row = QHBoxLayout()
            row.setSpacing(6)
            cb = QCheckBox(label_text)
            cb.setChecked(True)
            descs = _SIGNAL_VAR_DESCRIPTIONS.get(key)
            if descs:
                cb.setToolTip(descs[0])
            row.addWidget(cb)
            row.addStretch()
            row.addWidget(QLabel("±"))
            spin = QDoubleSpinBox()
            spin.setRange(1.0, 200.0)
            spin.setDecimals(1)
            spin.setSingleStep(1.0)
            spin.setValue(float(default_pct))
            spin.setSuffix(" %")
            row.addWidget(spin)
            cfg_layout.addLayout(row)

            if descs:
                desc_label = QLabel(descs[0])
                desc_label.setWordWrap(True)
                desc_label.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px; padding-left: 24px;")
                cfg_layout.addWidget(desc_label)

            self._var_rows.append({
                "key": key,
                "checkbox": cb,
                "spin": spin,
            })

        root.addWidget(cfg_group)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; border: 1px solid {_BORDER}; border-radius: 4px; padding: 5px 14px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
        )
        root.addWidget(btns)

    def _build_profile_summary(self) -> str:
        lines = []
        for index, profile in enumerate(self._profiles):
            region = profile.get("region", {})
            analysis = profile.get("analysis", {})
            lines.append(
                f"Signal {index + 1}: {region.get('t_start', 0.0):.3f}s–{region.get('t_end', 0.0):.3f}s, "
                f"{region.get('f_low', 0):.0f}–{region.get('f_high', 0):.0f} Hz"
            )
            for key, label_text, unit, _default_pct in _SIGNAL_VARIABLES:
                value = analysis.get(key)
                if value is None:
                    continue
                if unit:
                    lines.append(f"  {label_text}: {float(value):.3f} {unit}")
                else:
                    lines.append(f"  {label_text}: {float(value):.3f}")
            lines.append("")
        return "\n".join(lines).strip()

    def get_configs(self) -> list[dict]:
        configs = []
        for profile in self._profiles:
            analysis = profile.get("analysis", {})
            config: dict[str, dict] = {}
            for row in self._var_rows:
                key = row["key"]
                enabled = bool(row["checkbox"].isChecked()) and analysis.get(key) is not None
                pct = float(row["spin"].value())
                entry = {
                    "enabled": enabled,
                    "deviation_pct": pct,
                    "lower_pct": pct,
                    "upper_pct": pct,
                }
                ref_val = analysis.get(key)
                if ref_val is not None:
                    lower = max(float(ref_val) * (1.0 - pct / 100.0), 0.0)
                    upper = float(ref_val) * (1.0 + pct / 100.0)
                    entry["lower_bound"] = lower
                    entry["upper_bound"] = upper
                config[key] = entry
            configs.append(config)
        return configs

    def get_profiles(self) -> list[dict]:
        return self._profiles


class _SaveSelectionsDialog(QDialog):
    """Dialog for exporting positive/negative focus regions as WAV files."""

    def __init__(
        self,
        audio_path: str,
        regions: list[dict],
        layers: list[dict] | None = None,
        active_layer_idx: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Save Selections")
        self.setMinimumWidth(480)

        self._audio_path = audio_path
        self._regions = regions
        self._layers = layers or []
        self._active_layer_idx = active_layer_idx

        input_style = (
            f"background: {_BG_INPUT}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 4px;"
        )
        self.setStyleSheet(
            f"QDialog {{ background: {_BG}; color: {_TEXT}; }}"
            f"QLabel {{ color: {_TEXT}; background: transparent; }}"
            f"QCheckBox {{ color: {_TEXT}; }}"
            f"QRadioButton {{ color: {_TEXT}; }}"
            f"QLineEdit {{ {input_style} }}"
            f"QComboBox {{ {input_style} }}"
        )

        stem = os.path.splitext(os.path.basename(audio_path))[0]
        default_pos_dir, default_neg_dir = _default_signal_export_dirs(audio_path)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        n_pos = sum(1 for region in regions if region["polarity"] == "positive")
        n_neg = sum(1 for region in regions if region["polarity"] == "negative")
        info = QLabel(
            f"Export focus regions from <b>{os.path.basename(audio_path)}</b><br>"
            f"<span style='color: {_POSITIVE_BLUE}'>● {n_pos} positive</span>"
            f"&nbsp;&nbsp;"
            f"<span style='color: {_NEGATIVE_RED}'>● {n_neg} negative</span>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        dir_group = QGroupBox("Output Directories")
        dir_group.setStyleSheet(
            f"QGroupBox {{ color: {_TEXT_DIM}; border: 1px solid {_BORDER}; "
            f"border-radius: 6px; margin-top: 8px; padding-top: 14px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}"
        )
        dir_layout = QVBoxLayout(dir_group)

        btn_style = (
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 4px 10px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
        )

        pos_row = QHBoxLayout()
        pos_row.addWidget(QLabel("Positive:"))
        self._pos_dir_edit = QLineEdit(default_pos_dir)
        self._pos_dir_edit.setReadOnly(True)
        pos_row.addWidget(self._pos_dir_edit, stretch=1)
        pos_browse_btn = QPushButton("Browse…")
        pos_browse_btn.setStyleSheet(btn_style)
        pos_browse_btn.clicked.connect(self._browse_positive_dir)
        pos_row.addWidget(pos_browse_btn)
        dir_layout.addLayout(pos_row)

        neg_row = QHBoxLayout()
        neg_row.addWidget(QLabel("Negative:"))
        self._neg_dir_edit = QLineEdit(default_neg_dir)
        self._neg_dir_edit.setReadOnly(True)
        neg_row.addWidget(self._neg_dir_edit, stretch=1)
        neg_browse_btn = QPushButton("Browse…")
        neg_browse_btn.setStyleSheet(btn_style)
        neg_browse_btn.clicked.connect(self._browse_negative_dir)
        neg_row.addWidget(neg_browse_btn)
        dir_layout.addLayout(neg_row)
        layout.addWidget(dir_group)

        folder_info = QLabel(
            f"<i>Defaults: <b>{stem}_PositiveSignals</b> and <b>{stem}_NegativeSignals</b> "
            f"inside the source audio folder. Each folder also gets a JSON metadata file so saved "
            f"selections can be restored to the spectrogram later.</i>"
        )
        folder_info.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        folder_info.setWordWrap(True)
        layout.addWidget(folder_info)

        mode_group = QGroupBox("Export Mode")
        mode_group.setStyleSheet(
            f"QGroupBox {{ color: {_TEXT_DIM}; border: 1px solid {_BORDER}; "
            f"border-radius: 6px; margin-top: 8px; padding-top: 14px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}"
        )
        mode_layout = QVBoxLayout(mode_group)

        self._individual_rb = QRadioButton("Individual segments (one WAV per region)")
        self._individual_rb.setChecked(True)
        self._individual_rb.setToolTip(
            "Each region is saved as a separate WAV file, named by region index and time range"
        )
        mode_layout.addWidget(self._individual_rb)

        self._concat_rb = QRadioButton(
            "Concatenated (all positive in one file, all negative in one file)"
        )
        self._concat_rb.setToolTip(
            "All positive regions are joined into a single WAV, same for negative"
        )
        mode_layout.addWidget(self._concat_rb)
        layout.addWidget(mode_group)

        filter_group = QGroupBox("Frequency Filtering")
        filter_group.setStyleSheet(
            f"QGroupBox {{ color: {_TEXT_DIM}; border: 1px solid {_BORDER}; "
            f"border-radius: 6px; margin-top: 8px; padding-top: 14px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}"
        )
        filter_layout = QVBoxLayout(filter_group)

        self._bandpass_cb = QCheckBox("Apply bandpass filter to selected frequency range")
        self._bandpass_cb.setChecked(False)
        self._bandpass_cb.setToolTip(
            "When checked, each exported segment is bandpass-filtered to the "
            "frequency range drawn in the region rectangle"
        )
        filter_layout.addWidget(self._bandpass_cb)

        bp_hint = QLabel(
            "<i>Uses a 4th-order Butterworth filter to isolate frequencies "
            "within each region's f_low-f_high range.</i>"
        )
        bp_hint.setWordWrap(True)
        bp_hint.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        filter_layout.addWidget(bp_hint)
        layout.addWidget(filter_group)

        if len(self._layers) > 1:
            layer_group = QGroupBox("Layer Export")
            layer_group.setStyleSheet(
                f"QGroupBox {{ color: {_TEXT_DIM}; border: 1px solid {_BORDER}; "
                f"border-radius: 6px; margin-top: 8px; padding-top: 14px; }}"
                f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}"
            )
            layer_layout = QVBoxLayout(layer_group)

            self._active_layer_rb = QRadioButton(
                f"Active layer only ({self._layers[active_layer_idx]['name']})"
            )
            self._active_layer_rb.setChecked(True)
            layer_layout.addWidget(self._active_layer_rb)

            self._all_layers_rb = QRadioButton("All layers (separate folders per layer)")
            layer_layout.addWidget(self._all_layers_rb)
            layout.addWidget(layer_group)
        else:
            self._active_layer_rb = None
            self._all_layers_rb = None

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("Export")
        btn_box.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 6px 16px; font-size: 12px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; color: white; }}"
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def output_dir(self) -> str:
        return _normalize_ui_path(self._pos_dir_edit.text())

    def positive_output_dir(self) -> str:
        return _normalize_ui_path(self._pos_dir_edit.text())

    def negative_output_dir(self) -> str:
        return _normalize_ui_path(self._neg_dir_edit.text())

    def individual_mode(self) -> bool:
        return self._individual_rb.isChecked()

    def bandpass_enabled(self) -> bool:
        return self._bandpass_cb.isChecked()

    def export_all_layers(self) -> bool:
        if self._all_layers_rb is not None:
            return self._all_layers_rb.isChecked()
        return False

    def _browse_positive_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Positive Signals Directory",
            self._pos_dir_edit.text(),
        )
        if directory:
            self._pos_dir_edit.setText(_normalize_ui_path(directory))

    def _browse_negative_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Negative Signals Directory",
            self._neg_dir_edit.text(),
        )
        if directory:
            self._neg_dir_edit.setText(_normalize_ui_path(directory))


class _LoadSelectionsDialog(QDialog):
    """Dialog for restoring saved positive/negative selection examples."""

    def __init__(self, audio_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load Selections")
        self.setMinimumWidth(500)

        default_pos_dir, default_neg_dir = _default_signal_export_dirs(audio_path)
        stem = os.path.splitext(os.path.basename(audio_path))[0]

        input_style = (
            f"background: {_BG_INPUT}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 4px;"
        )
        self.setStyleSheet(
            f"QDialog {{ background: {_BG}; color: {_TEXT}; }}"
            f"QLabel {{ color: {_TEXT}; background: transparent; }}"
            f"QLineEdit {{ {input_style} }}"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        info = QLabel(
            f"Load saved positive/negative selections for <b>{os.path.basename(audio_path)}</b>."
            f"<br><span style='color: {_TEXT_DIM}'>If geometry metadata JSON files are found, the "
            f"regions will be restored to the spectrogram. Otherwise the saved WAV files can still be "
            f"used as signal examples for settings recommendations.</span>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        dir_group = QGroupBox("Saved Selection Folders")
        dir_group.setStyleSheet(
            f"QGroupBox {{ color: {_TEXT_DIM}; border: 1px solid {_BORDER}; "
            f"border-radius: 6px; margin-top: 8px; padding-top: 14px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}"
        )
        dir_layout = QVBoxLayout(dir_group)

        btn_style = (
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 4px 10px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
        )

        pos_row = QHBoxLayout()
        pos_row.addWidget(QLabel("Positive:"))
        self._pos_dir_edit = QLineEdit(default_pos_dir)
        self._pos_dir_edit.setReadOnly(True)
        pos_row.addWidget(self._pos_dir_edit, stretch=1)
        pos_browse_btn = QPushButton("Browse…")
        pos_browse_btn.setStyleSheet(btn_style)
        pos_browse_btn.clicked.connect(self._browse_positive_dir)
        pos_row.addWidget(pos_browse_btn)
        dir_layout.addLayout(pos_row)

        neg_row = QHBoxLayout()
        neg_row.addWidget(QLabel("Negative:"))
        self._neg_dir_edit = QLineEdit(default_neg_dir)
        self._neg_dir_edit.setReadOnly(True)
        neg_row.addWidget(self._neg_dir_edit, stretch=1)
        neg_browse_btn = QPushButton("Browse…")
        neg_browse_btn.setStyleSheet(btn_style)
        neg_browse_btn.clicked.connect(self._browse_negative_dir)
        neg_row.addWidget(neg_browse_btn)
        dir_layout.addLayout(neg_row)
        layout.addWidget(dir_group)

        note = QLabel(
            f"<i>Expected metadata files: <b>{stem}_PositiveSignals.json</b> and "
            f"<b>{stem}_NegativeSignals.json</b>.</i>"
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        layout.addWidget(note)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("Load")
        btn_box.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 6px 16px; font-size: 12px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; color: white; }}"
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def positive_input_dir(self) -> str:
        return _normalize_ui_path(self._pos_dir_edit.text())

    def negative_input_dir(self) -> str:
        return _normalize_ui_path(self._neg_dir_edit.text())

    def _browse_positive_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Positive Signals Directory",
            self._pos_dir_edit.text(),
        )
        if directory:
            self._pos_dir_edit.setText(_normalize_ui_path(directory))

    def _browse_negative_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Negative Signals Directory",
            self._neg_dir_edit.text(),
        )
        if directory:
            self._neg_dir_edit.setText(_normalize_ui_path(directory))


__all__ = [
    "_DetectOnsetsDialog",
    "_LayerCheckboxMenu",
    "_LoadSelectionsDialog",
    "_MfccAudioEditDialog",
    "_NegativeSubtractionDialog",
    "OnsetManagerDialog",
    "_PerSignalConfigDialog",
    "_SaveSelectionsDialog",
    "_default_signal_export_dirs",
]