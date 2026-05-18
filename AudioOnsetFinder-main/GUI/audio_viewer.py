"""
AudioViewerWidget — GPU-accelerated audio viewer for the Bioacoustics Rhythm Pipeline.

Provides waveform + spectrogram display using pyqtgraph, with audio playback,
onset marker overlays, region selection, and chunk navigation.  Designed to
replace the slow matplotlib-based viewers (AudioPreviewWindow, SpectrogramSelector,
OnsetSelector) with a single high-performance, reusable component.

Dependencies: PyQt6, pyqtgraph, numpy, librosa.
Optional: sounddevice (for playback).
"""

from __future__ import annotations

import platform
import threading
import time
from typing import Any, List, Optional, Tuple

import numpy as np

from PyQt6.QtCore import (
    QObject,
    QTimer,
    Qt,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QAction
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import pyqtgraph as pg

# ---------------------------------------------------------------------------
# Optional: sounddevice for playback
# ---------------------------------------------------------------------------
try:
    import sounddevice as sd
    _HAS_SOUNDDEVICE = True
except (ImportError, OSError):
    _HAS_SOUNDDEVICE = False

# ---------------------------------------------------------------------------
# Optional: librosa for audio loading and STFT
# ---------------------------------------------------------------------------
try:
    import librosa
    _HAS_LIBROSA = True
except ImportError:
    _HAS_LIBROSA = False

# ---------------------------------------------------------------------------
# Theme constants (duplicated from pipeline_gui to keep self-contained)
# ---------------------------------------------------------------------------
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


def _monospace_css_family() -> str:
    system = platform.system()
    if system == "Darwin":
        return "Menlo"
    if system == "Windows":
        return "Consolas"
    return "DejaVu Sans Mono"

# Waveform / spectrogram colours
_WAVEFORM_COLOR = (76, 175, 80, 200)   # accent green, semi-transparent
_PLAYHEAD_COLOR = (255, 255, 255, 220) # bright white
_ONSET_DEFAULT_COLOR = (255, 80, 80, 220)     # red
_ONSET_SELECTED_COLOR = (255, 215, 0, 255)    # gold
_REGION_DEFAULT_COLOR = (76, 175, 80, 40)      # translucent green

# Focus region colours
_FOCUS_POSITIVE_COLOR = (33, 150, 243, 50)     # semi-transparent blue
_FOCUS_NEGATIVE_COLOR = (229, 57, 53, 50)      # semi-transparent red
_FOCUS_POSITIVE_BORDER = (33, 150, 243, 180)   # blue border
_FOCUS_NEGATIVE_BORDER = (229, 57, 53, 180)    # red border
_FOCUS_SELECTED_FILL_ALPHA = 95
_FOCUS_SELECTED_BORDER_ALPHA = 255

# Spectrogram colormap (magma-like warm colormap)
_SPEC_CMAP = pg.colormap.get("magma", source="matplotlib")


class _FocusRectROI(pg.RectROI):
    """RectROI variant with fill-brush support across pyqtgraph versions."""

    def __init__(self, *args, brush=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._brush = pg.mkBrush(brush) if brush is not None else pg.mkBrush((0, 0, 0, 0))

    def setBrush(self, brush):
        self._brush = pg.mkBrush(brush)
        self.update()

    def paint(self, painter, option, widget):
        painter.setBrush(self._brush)
        super().paint(painter, option, widget)


# ═══════════════════════════════════════════════════════════════════════════
# Background workers
# ═══════════════════════════════════════════════════════════════════════════

class _AudioLoadWorker(QObject):
    """Loads an audio file in a background thread via librosa."""
    finished = pyqtSignal(np.ndarray, int, str)   # (y, sr, file_path)
    error = pyqtSignal(str)

    def __init__(self, file_path: str, sr: int | None = None):
        super().__init__()
        self._path = file_path
        self._sr = sr

    @pyqtSlot()
    def run(self):
        try:
            y, sr = librosa.load(self._path, sr=self._sr, mono=True)
            self.finished.emit(y.astype(np.float32), int(sr), self._path)
        except Exception as exc:
            self.error.emit(f"Failed to load audio: {exc}")


class _STFTWorker(QObject):
    """Computes the full STFT spectrogram in a background thread."""
    finished = pyqtSignal(np.ndarray, np.ndarray, np.ndarray)  # (spec_db, freqs, times)
    error = pyqtSignal(str)

    def __init__(self, y: np.ndarray, sr: int, n_fft: int = 2048,
                 hop_length: int = 512):
        super().__init__()
        self._y = y
        self._sr = sr
        self._n_fft = n_fft
        self._hop = hop_length

    @pyqtSlot()
    def run(self):
        try:
            S = np.abs(librosa.stft(self._y, n_fft=self._n_fft,
                                     hop_length=self._hop))
            S_db = librosa.amplitude_to_db(S, ref=np.max)
            freqs = librosa.fft_frequencies(sr=self._sr, n_fft=self._n_fft)
            times = librosa.frames_to_time(
                np.arange(S_db.shape[1]), sr=self._sr, hop_length=self._hop)
            self.finished.emit(S_db.astype(np.float32), freqs.astype(np.float32),
                               times.astype(np.float32))
        except Exception as exc:
            self.error.emit(f"STFT failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# AudioViewerWidget
# ═══════════════════════════════════════════════════════════════════════════

class AudioViewerWidget(QWidget):
    """High-performance audio viewer with waveform + spectrogram + playback.

    Signals
    -------
    audioLoaded(str)          – emitted when an audio file has been loaded
    onsetAdded(float)         – emitted when a new onset is added (time_sec)
    onsetRemoved(int)         – emitted when an onset is removed (index)
    onsetMoved(int, float)    – emitted when an onset marker is dragged (index, new_time)
    onsetClicked(int, float)  – emitted when an onset marker is clicked (index, time)
    regionSelected(float, float)  – emitted when a region is selected
    viewClicked(float)        – emitted when the view is clicked (time_sec)
    viewShiftClicked(float)   – emitted when shift+click on view (time_sec)
    viewCtrlClicked(float)    – emitted when ctrl+click on view (time_sec)
    playbackPositionChanged(float)  – emitted during playback (current_time)
    """

    audioLoaded = pyqtSignal(str)
    onsetAdded = pyqtSignal(float)
    onsetRemoved = pyqtSignal(int)
    onsetMoved = pyqtSignal(int, float)
    onsetClicked = pyqtSignal(int, float)
    regionSelected = pyqtSignal(float, float)
    regionCleared = pyqtSignal()
    viewClicked = pyqtSignal(float)
    viewShiftClicked = pyqtSignal(float)
    viewCtrlClicked = pyqtSignal(float)
    playbackPositionChanged = pyqtSignal(float)
    maximizeRequested = pyqtSignal(int)  # 0=default, 1=fullscreen, 2=fullscreen-2
    # Focus region signals (dict carries t_start, t_end, f_low, f_high, polarity)
    focusRegionAdded = pyqtSignal(dict)
    focusRegionRemoved = pyqtSignal(int)
    focusRegionModified = pyqtSignal(int, dict)
    focusRegionExportRequested = pyqtSignal(int)  # region index
    focusRegionMoveRequested = pyqtSignal(int, int)   # (region_idx, target_layer_idx) -1=new
    focusRegionCopyRequested = pyqtSignal(int, int)   # (region_idx, target_layer_idx) -1=new

    def __init__(self, parent: QWidget | None = None, *,
                 show_waveform: bool = True,
                 show_spectrogram: bool = True,
                 show_transport: bool = True,
                 show_chunk_nav: bool = True,
                 chunk_duration: float = 10.0,
                 n_fft: int = 2048,
                 hop_length: int = 512):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {_BG}; color: {_TEXT};")

        # ---- configuration ----
        self._show_waveform = show_waveform
        self._show_spectrogram = show_spectrogram
        self._chunk_sec = chunk_duration
        self._n_fft = n_fft
        self._hop_length = hop_length

        # ---- audio data ----
        self._y: np.ndarray | None = None
        self._sr: int = 22050
        self._duration: float = 0.0
        self._time_offset: float = 0.0
        self._file_path: str = ""

        # ---- spectrogram cache ----
        self._spec_db: np.ndarray | None = None
        self._spec_freqs: np.ndarray | None = None
        self._spec_times: np.ndarray | None = None
        self._waveform_y_abs_max: float = 1.0
        self._spec_f_min: float = 0.0
        self._spec_f_max: float = 1.0

        # ---- overlay state ----
        self._onset_lines: list[pg.InfiniteLine] = []
        self._onset_times: np.ndarray = np.array([], dtype=np.float64)
        self._onset_draggable: bool = False
        self._selected_onset: int = -1
        self._region_items: list[pg.LinearRegionItem] = []
        self._comparison_lines: list[tuple[pg.InfiniteLine, pg.InfiniteLine]] = []

        # ---- region-selection drag state ----
        self._region_dragging: bool = False
        self._region_drag_start: float = 0.0
        self._region_drag_did_move: bool = False
        self._region_drag_is_shift: bool = False
        self._region_select_item_w: pg.LinearRegionItem | None = None
        self._region_select_item_s: pg.LinearRegionItem | None = None

        # ---- onset click/drag settings ----
        self._onset_hitbox_px: int = 5  # pixel radius for onset click detection

        # ---- onset-drag state (left-click+drag on an onset line) ----
        self._onset_dragging: bool = False
        self._onset_drag_index: int = -1
        self._onset_drag_start_time: float = 0.0

        # ---- two-click select-range mode ----
        self._select_range_mode: bool = False
        self._select_range_start: float | None = None
        self._range_start_line_w: pg.InfiniteLine | None = None
        self._range_start_line_s: pg.InfiniteLine | None = None

        # ---- focus-region mode state ----
        self._focus_mode: bool = False
        self._focus_polarity: str = "positive"     # "positive" or "negative"
        self._focus_regions: list[dict] = []       # current file's regions
        self._focus_rect_items: list[pg.RectROI] = []  # pyqtgraph ROI items on spec
        self._selected_focus_region_index: int = -1
        self._focus_dragging: bool = False
        self._focus_drag_start_t: float = 0.0
        self._focus_drag_start_f: float = 0.0
        self._focus_drag_rect: pg.RectROI | None = None
        self._focus_drag_did_move: bool = False

        # ---- layer info for context menus ----
        self._layer_names: list[str] = ["Layer 1"]
        self._active_layer_idx: int = 0

        # ---- playback state ----
        self._playing: bool = False
        self._last_playback_error: str | None = None
        self._play_offset: float = 0.0
        self._play_start_wall: float = 0.0
        self._stream: Any = None
        self._stream_frame_idx: int = 0
        self._clip_data: np.ndarray | None = None
        self._clip_frame_idx: int = 0
        self._clip_start_time: float = 0.0
        self._clip_loop: bool = False
        self._loop_region: tuple[float, float] | None = None
        self._volume: float = 1.0

        # ---- background threads ----
        self._load_thread: threading.Thread | None = None
        self._stft_thread: threading.Thread | None = None
        self._last_spectrogram_error: str | None = None

        # ---- build UI ----
        self._build_ui(show_transport, show_chunk_nav)

        # ---- playhead animation timer (60 fps) ----
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)   # ~60fps
        self._anim_timer.timeout.connect(self._animate_playhead)

        # Enable keyboard focus
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def audioData(self) -> np.ndarray | None:
        return self._y

    @audioData.setter
    def audioData(self, value: np.ndarray) -> None:
        """Replace the in-memory audio data without reloading from disk.

        Called by the Onset Editor after applying in-place edits (Quick Audio
        Editor, MFCC cleaning, etc.) so that subsequent calls to
        ``_plot_waveform`` / ``_plot_spectrogram`` operate on the edited data.
        """
        if value is None:
            self._y = None
        else:
            self._y = np.asarray(value, dtype=np.float32)

    @property
    def sampleRate(self) -> int:
        return self._sr

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def filePath(self) -> str:
        return self._file_path

    @property
    def onsetTimes(self) -> np.ndarray:
        return self._onset_times.copy()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self, show_transport: bool, show_chunk_nav: bool):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Loading indicator
        self._loading_label = QLabel("Loading…")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setStyleSheet(
            f"color: {_ACCENT}; font-size: 14px; padding: 20px;")
        self._loading_label.hide()
        layout.addWidget(self._loading_label)

        # ---- pyqtgraph setup ----
        pg.setConfigOption("background", _BG_MID)
        pg.setConfigOption("foreground", _TEXT)

        # Shared tick font – use QFont() (application default) instead of
        # QFont("", 9) to avoid a null-family crash on macOS Qt6.
        _tick_font = QFont()
        _tick_font.setPointSize(9)

        # Waveform plot
        self._waveform_plot = pg.PlotWidget()
        self._waveform_plot.setLabel("left", "Amplitude")
        self._waveform_plot.setLabel("bottom", "Time", units="s")
        self._waveform_plot.showGrid(x=True, y=False, alpha=0.15)
        self._waveform_plot.setMouseEnabled(x=False, y=False)
        self._waveform_plot.getAxis("left").setStyle(tickFont=_tick_font)
        self._waveform_plot.getAxis("bottom").setStyle(tickFont=_tick_font)
        self._waveform_curve = self._waveform_plot.plot(
            pen=pg.mkPen(color=_WAVEFORM_COLOR, width=1))
        self._waveform_curve.setDownsampling(auto=True, method="peak")
        self._waveform_curve.setClipToView(True)
        if not self._show_waveform:
            self._waveform_plot.hide()
        layout.addWidget(self._waveform_plot, stretch=2)

        # Spectrogram plot
        self._spec_plot = pg.PlotWidget()
        self._spec_plot.setLabel("left", "Frequency", units="Hz")
        self._spec_plot.setLabel("bottom", "Time", units="s")
        self._spec_plot.showGrid(x=True, y=False, alpha=0.15)
        self._spec_plot.setMouseEnabled(x=False, y=False)
        self._spec_plot.getAxis("left").setStyle(tickFont=_tick_font)
        self._spec_plot.getAxis("bottom").setStyle(tickFont=_tick_font)

        # Ensure graphics scenes have a valid default font (macOS Qt6 workaround:
        # without this the first QGraphicsWidget paint can SIGSEGV when
        # Qt tries to serialise a null QFont).
        _scene_font = QFont()
        for _pw in (self._waveform_plot, self._spec_plot):
            _sc = _pw.scene()
            if _sc is not None:
                _sc.setFont(_scene_font)
        self._spec_image = pg.ImageItem()
        self._spec_plot.addItem(self._spec_image)
        if _SPEC_CMAP is not None:
            self._spec_image.setLookupTable(_SPEC_CMAP.getLookupTable(nPts=256))
        if not self._show_spectrogram:
            self._spec_plot.hide()
        layout.addWidget(self._spec_plot, stretch=3)

        # Link x-axes
        self._spec_plot.setXLink(self._waveform_plot)

        # Playhead lines
        self._playhead_wave = pg.InfiniteLine(
            pos=0, angle=90, pen=pg.mkPen(color=_PLAYHEAD_COLOR, width=2))
        self._playhead_wave.setZValue(100)
        self._waveform_plot.addItem(self._playhead_wave)

        self._playhead_spec = pg.InfiniteLine(
            pos=0, angle=90, pen=pg.mkPen(color=_PLAYHEAD_COLOR, width=2))
        self._playhead_spec.setZValue(100)
        self._spec_plot.addItem(self._playhead_spec)

        # Click handlers on plots
        self._waveform_plot.scene().sigMouseClicked.connect(
            lambda evt: self._on_plot_clicked(evt, self._waveform_plot))
        self._spec_plot.scene().sigMouseClicked.connect(
            lambda evt: self._on_plot_clicked(evt, self._spec_plot))

        # Ctrl+drag region-selection: install event filter on both viewports
        self._waveform_plot.viewport().installEventFilter(self)
        self._spec_plot.viewport().installEventFilter(self)
        self._waveform_plot.scene().installEventFilter(self)
        self._spec_plot.scene().installEventFilter(self)

        # ---- Transport controls ----
        self._transport = QWidget()
        transport_layout = QHBoxLayout(self._transport)
        transport_layout.setContentsMargins(4, 2, 4, 2)
        transport_layout.setSpacing(8)

        btn_style = (
            f"QPushButton {{ background-color: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 5px; "
            f"padding: 4px 8px; font-size: 16px; min-width: 36px; }} "
            f"QPushButton:hover {{ background-color: {_BG_MID}; "
            f"border-color: {_ACCENT}; }} "
            f"QPushButton:disabled {{ color: {_TEXT_MUTED}; }}")

        self._play_btn = QPushButton("▶")
        self._play_btn.setToolTip("Play / Pause (Space)")
        self._play_btn.setStyleSheet(btn_style)
        self._play_btn.setFixedSize(38, 32)
        self._play_btn.clicked.connect(self._toggle_play)
        self._play_btn.setEnabled(_HAS_SOUNDDEVICE)
        transport_layout.addWidget(self._play_btn)

        self._stop_btn = QPushButton("⏹")
        self._stop_btn.setToolTip("Stop")
        self._stop_btn.setStyleSheet(btn_style)
        self._stop_btn.setFixedSize(38, 32)
        self._stop_btn.clicked.connect(self.stop)
        self._stop_btn.setEnabled(False)
        transport_layout.addWidget(self._stop_btn)

        self._restart_btn = QPushButton("⏮")
        self._restart_btn.setToolTip("Play from beginning")
        self._restart_btn.setStyleSheet(btn_style)
        self._restart_btn.setFixedSize(38, 32)
        self._restart_btn.clicked.connect(self._play_from_beginning)
        self._restart_btn.setEnabled(_HAS_SOUNDDEVICE)
        transport_layout.addWidget(self._restart_btn)

        # Volume slider
        transport_layout.addWidget(QLabel("🔊"))
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(100)
        self._volume_slider.setFixedWidth(80)
        self._volume_slider.setStyleSheet(
            f"QSlider::groove:horizontal {{ background: {_BG_WIDGET}; "
            f"height: 6px; border-radius: 3px; }} "
            f"QSlider::handle:horizontal {{ background: {_ACCENT}; "
            f"width: 14px; margin: -4px 0; border-radius: 7px; }}")
        self._volume_slider.valueChanged.connect(
            lambda v: setattr(self, '_volume', v / 100.0))
        transport_layout.addWidget(self._volume_slider)

        # Time display
        self._time_label = QLabel("0:00.000 / 0:00.000")
        self._time_label.setStyleSheet(
            f"color: {_TEXT_DIM}; font-size: 12px; font-family: '{_monospace_css_family()}';")
        transport_layout.addWidget(self._time_label)

        # ── Vertical separator before chunk controls ──
        _chunk_sep = QFrame()
        _chunk_sep.setFrameShape(QFrame.Shape.VLine)
        _chunk_sep.setStyleSheet(f"color: {_BORDER};")
        _chunk_sep.setFixedHeight(24)
        transport_layout.addSpacing(10)
        transport_layout.addWidget(_chunk_sep)
        transport_layout.addSpacing(6)

        # ── Chunk navigation (inline with transport) ──
        small_btn_style = (
            f"QPushButton {{ background-color: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 2px 6px; font-size: 11px; }} "
            f"QPushButton:hover {{ background-color: {_BG_MID}; "
            f"border-color: {_ACCENT}; }} "
            f"QPushButton:disabled {{ color: {_TEXT_MUTED}; }}")
        small_spin_style = (
            f"QDoubleSpinBox, QSpinBox {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 3px; "
            f"padding: 1px 4px; font-size: 11px; }}")
        small_label_style = f"color: {_TEXT_DIM}; font-size: 11px;"

        dur_label = QLabel("Duration:")
        dur_label.setStyleSheet(small_label_style)
        transport_layout.addWidget(dur_label)
        self._chunk_dur_spin = QDoubleSpinBox()
        self._chunk_dur_spin.setRange(1.0, 600.0)
        self._chunk_dur_spin.setValue(self._chunk_sec)
        self._chunk_dur_spin.setSuffix(" s")
        self._chunk_dur_spin.setDecimals(1)
        self._chunk_dur_spin.setSingleStep(1.0)
        self._chunk_dur_spin.setFixedHeight(24)
        self._chunk_dur_spin.setStyleSheet(small_spin_style)
        self._chunk_dur_spin.valueChanged.connect(self._on_chunk_duration_changed)
        transport_layout.addWidget(self._chunk_dur_spin)

        transport_layout.addSpacing(6)
        chunk_label = QLabel("Chunk:")
        chunk_label.setStyleSheet(small_label_style)
        transport_layout.addWidget(chunk_label)
        self._chunk_spin = QSpinBox()
        self._chunk_spin.setMinimum(1)
        self._chunk_spin.setMaximum(1)
        self._chunk_spin.setValue(1)
        self._chunk_spin.setFixedHeight(24)
        self._chunk_spin.setStyleSheet(small_spin_style)
        self._chunk_spin.valueChanged.connect(self._on_chunk_changed)
        transport_layout.addWidget(self._chunk_spin)

        self._chunk_info_label = QLabel("/ 1")
        self._chunk_info_label.setStyleSheet(small_label_style)
        transport_layout.addWidget(self._chunk_info_label)

        self._prev_chunk_btn = QPushButton("\u2190 Prev")
        self._prev_chunk_btn.setStyleSheet(small_btn_style)
        self._prev_chunk_btn.setFixedHeight(24)
        self._prev_chunk_btn.clicked.connect(self._prev_chunk)
        transport_layout.addWidget(self._prev_chunk_btn)

        self._next_chunk_btn = QPushButton("Next \u2192")
        self._next_chunk_btn.setStyleSheet(small_btn_style)
        self._next_chunk_btn.setFixedHeight(24)
        self._next_chunk_btn.clicked.connect(self._next_chunk)
        transport_layout.addWidget(self._next_chunk_btn)

        transport_layout.addStretch()

        if not show_transport:
            self._transport.hide()
        layout.addWidget(self._transport)

        # ---- Chunk navigation bar (view toggles & external buttons) ----
        self._chunk_bar = QWidget()
        chunk_layout = QHBoxLayout(self._chunk_bar)
        self._chunk_layout = chunk_layout  # expose for external widget insertion
        chunk_layout.setContentsMargins(4, 2, 4, 2)
        chunk_layout.setSpacing(6)

        chunk_layout.addStretch()

        # ── View toggles (stacked vertically) ──
        cb_style = (f"QCheckBox {{ color: {_TEXT_DIM}; font-size: 12px; spacing: 4px; }}"
                    f"QCheckBox::indicator {{ width: 14px; height: 14px; }}")
        _cb_col = QVBoxLayout()
        _cb_col.setContentsMargins(0, 0, 0, 0)
        _cb_col.setSpacing(1)
        self._wave_cb = QCheckBox("Waveform")
        self._wave_cb.setChecked(self._show_waveform)
        self._wave_cb.setStyleSheet(cb_style)
        self._wave_cb.toggled.connect(self.show_waveform)
        _cb_col.addWidget(self._wave_cb)

        self._spec_cb = QCheckBox("Spectrogram")
        self._spec_cb.setChecked(self._show_spectrogram)
        self._spec_cb.setStyleSheet(cb_style)
        self._spec_cb.toggled.connect(self.show_spectrogram)
        _cb_col.addWidget(self._spec_cb)
        chunk_layout.addLayout(_cb_col)

        chunk_layout.addSpacing(6)

        # ── Maximize / Restore button ──
        self._maximize_state = 0  # 0=default, 1=fullscreen, 2=fullscreen-2
        self._maximize_btn = QPushButton("⛶")
        self._maximize_btn.setToolTip("Cycle: Default → Fullscreen → Fullscreen-2 → Default")
        self._maximize_btn.setStyleSheet(
            f"QPushButton {{ background-color: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 5px; "
            f"padding: 4px 8px; font-size: 15px; min-width: 30px; }} "
            f"QPushButton:hover {{ background-color: {_BG_MID}; "
            f"border-color: {_ACCENT}; }}")
        self._maximize_btn.setFixedSize(34, 28)
        self._maximize_btn.clicked.connect(self._toggle_maximize)
        chunk_layout.addWidget(self._maximize_btn)

        if not show_chunk_nav:
            self._chunk_bar.hide()
        layout.addWidget(self._chunk_bar)

    # ------------------------------------------------------------------
    # Audio loading
    # ------------------------------------------------------------------

    def load_audio(self, file_path: str, sr: int | None = None):
        """Load an audio file. Runs in a background thread, emits audioLoaded when done."""
        if not _HAS_LIBROSA:
            self._loading_label.setText("librosa not installed")
            self._loading_label.show()
            return

        self.stop()
        self._loading_label.setText("Loading…")
        self._loading_label.show()

        worker = _AudioLoadWorker(file_path, sr)
        worker.finished.connect(self._on_audio_loaded)
        worker.error.connect(self._on_load_error)

        self._load_thread = threading.Thread(
            target=self._run_worker, args=(worker,), daemon=True)
        self._load_thread.start()

    def load_audio_array(self, y: np.ndarray, sr: int,
                         file_path: str = "<array>",
                         time_offset: float = 0.0):
        """Load audio directly from a numpy array (no file I/O).

        Parameters
        ----------
        time_offset : float
            Time in seconds to add to the x-axis origin (for chunk display).
        """
        self.stop()
        self._y = y.astype(np.float32) if y.dtype != np.float32 else y
        self._sr = sr
        self._duration = len(self._y) / sr + time_offset
        self._time_offset = time_offset
        self._file_path = file_path
        self._spec_db = None
        self._spec_freqs = None
        self._spec_times = None
        self._last_spectrogram_error = None
        self._display_waveform()
        self._compute_spectrogram()
        self._update_chunk_controls()
        self._apply_view_limits()
        self._loading_label.hide()
        self.audioLoaded.emit(file_path)

    @staticmethod
    def _run_worker(worker: QObject):
        """Execute a worker's run() method (call from thread)."""
        worker.run()

    @pyqtSlot(np.ndarray, int, str)
    def _on_audio_loaded(self, y: np.ndarray, sr: int, path: str):
        self._y = y
        self._sr = sr
        self._duration = len(y) / sr
        self._time_offset = 0.0
        self._file_path = path
        self._spec_db = None
        self._spec_freqs = None
        self._spec_times = None
        self._last_spectrogram_error = None
        self._loading_label.hide()
        self._display_waveform()
        self._compute_spectrogram()
        self._update_chunk_controls()
        self._apply_view_limits()
        self._update_time_label(0.0)
        self.audioLoaded.emit(path)

    @pyqtSlot(str)
    def _on_load_error(self, msg: str):
        self._loading_label.setText(msg)

    # ------------------------------------------------------------------
    # Waveform rendering
    # ------------------------------------------------------------------

    def _display_waveform(self):
        if self._y is None:
            return
        t = np.arange(len(self._y)) / self._sr + self._time_offset
        self._waveform_curve.setData(t, self._y)
        try:
            peak = float(np.nanmax(np.abs(self._y))) if self._y.size else 1.0
        except Exception:
            peak = 1.0
        self._waveform_y_abs_max = max(1.0, peak * 1.05)
        t_start = self._time_offset
        t_end = min(t_start + self._chunk_sec, self._duration)
        self._waveform_plot.setXRange(t_start, t_end, padding=0)
        self._waveform_plot.setYRange(
            -self._waveform_y_abs_max,
            self._waveform_y_abs_max,
            padding=0.02)

    # ------------------------------------------------------------------
    # Spectrogram rendering
    # ------------------------------------------------------------------

    def _compute_spectrogram(self):
        if self._y is None or not _HAS_LIBROSA:
            return

        self._last_spectrogram_error = None
        worker = _STFTWorker(self._y, self._sr, self._n_fft, self._hop_length)
        worker.finished.connect(self._on_stft_done)
        worker.error.connect(self._on_stft_error)

        self._stft_thread = threading.Thread(
            target=self._run_worker, args=(worker,), daemon=True)
        self._stft_thread.start()

    @pyqtSlot(np.ndarray, np.ndarray, np.ndarray)
    def _on_stft_done(self, spec_db: np.ndarray, freqs: np.ndarray,
                      times: np.ndarray):
        self._last_spectrogram_error = None
        self._spec_db = spec_db
        self._spec_freqs = freqs
        self._spec_times = times
        self._display_spectrogram()

    @pyqtSlot(str)
    def _on_stft_error(self, msg: str):
        self._last_spectrogram_error = msg
        print(f"[AudioViewer] {msg}")

    def _display_spectrogram(self):
        if self._spec_db is None:
            return
        # ImageItem expects (width, height) = (time_bins, freq_bins)
        img = self._spec_db.T   # shape: (time, freq) → display as image
        self._spec_image.setImage(img, autoLevels=True)

        # Scale so axes show time (s) and frequency (Hz)
        dt = self._spec_times[1] - self._spec_times[0] if len(self._spec_times) > 1 else 1.0
        df = self._spec_freqs[1] - self._spec_freqs[0] if len(self._spec_freqs) > 1 else 1.0
        t0 = (self._spec_times[0] if len(self._spec_times) > 0 else 0.0) + self._time_offset
        f0 = self._spec_freqs[0] if len(self._spec_freqs) > 0 else 0.0

        from pyqtgraph import QtGui
        tr = QtGui.QTransform()
        tr.translate(t0, f0)
        tr.scale(dt, df)
        self._spec_image.setTransform(tr)

        # x-range is controlled by the waveform plot via setXLink — do not
        # call self._spec_plot.setXRange() here; it would fight the link and
        # could cause sub-sample x-axis misalignment during pan/zoom.
        self._spec_f_min = float(self._spec_freqs[0])
        self._spec_f_max = float(self._spec_freqs[-1])
        self._spec_plot.setYRange(self._spec_f_min, self._spec_f_max, padding=0)

    # ------------------------------------------------------------------
    # Visibility controls
    # ------------------------------------------------------------------

    def show_waveform(self, visible: bool):
        self._show_waveform = visible
        self._waveform_plot.setVisible(visible)

    def show_spectrogram(self, visible: bool):
        self._show_spectrogram = visible
        self._spec_plot.setVisible(visible)

    def _toggle_maximize(self):
        """Cycle through 3 view states and emit signal for parent to act on.

        States: 0 = Default (all panels), 1 = Fullscreen (collapse outer panels),
                2 = Fullscreen-2 (also collapse top controls + onset table).
        """
        self._maximize_state = (self._maximize_state + 1) % 3
        icons = {
            0: "⛶",   # default
            1: "⊖",   # fullscreen
            2: "⬜",  # fullscreen-2
        }
        tips = {
            0: "Cycle: Default → Fullscreen → Fullscreen-2 → Default",
            1: "Fullscreen — click to enter Fullscreen-2",
            2: "Fullscreen-2 — click to restore Default",
        }
        self._maximize_btn.setText(icons[self._maximize_state])
        self._maximize_btn.setToolTip(tips[self._maximize_state])
        self.maximizeRequested.emit(self._maximize_state)

    # ------------------------------------------------------------------
    # Chunk navigation
    # ------------------------------------------------------------------

    def _total_chunks(self) -> int:
        if self._duration <= 0:
            return 1
        return max(1, int(np.ceil(self._duration / self._chunk_sec)))

    def _update_chunk_controls(self):
        n = self._total_chunks()
        self._chunk_spin.setMaximum(n)
        self._chunk_info_label.setText(f"/ {n}")
        # Show chunk bar whenever audio is loaded (so duration is always editable)
        has_audio = self._duration > 0
        self._chunk_bar.setVisible(has_audio and self._chunk_bar.parent() is not None)
        self._chunk_spin.setEnabled(n > 1)
        self._prev_chunk_btn.setEnabled(n > 1)
        self._next_chunk_btn.setEnabled(n > 1)

    def _on_chunk_changed(self, value: int):
        t0 = (value - 1) * self._chunk_sec
        t1 = min(t0 + self._chunk_sec, self._duration)
        self._waveform_plot.setXRange(t0, t1, padding=0)
        # spec plot follows via x-link

    def _on_chunk_duration_changed(self, value: float):
        """Handle chunk duration spinbox change."""
        self._chunk_sec = value
        self._update_chunk_controls()
        self._chunk_spin.setValue(1)
        self._on_chunk_changed(1)

    def _prev_chunk(self):
        v = self._chunk_spin.value()
        if v > 1:
            self._chunk_spin.setValue(v - 1)

    def _next_chunk(self):
        v = self._chunk_spin.value()
        if v < self._chunk_spin.maximum():
            self._chunk_spin.setValue(v + 1)

    # ------------------------------------------------------------------
    # Mouse interaction: onset dragging, region selection, click
    # ------------------------------------------------------------------

    def _is_near_onset(self, t: float, plot_widget) -> int:
        """Return the onset index if *t* is close to an onset line, else -1.

        Uses a fixed pixel-distance threshold so the hit region matches
        the visual width of the onset line regardless of zoom level.
        """
        if len(self._onset_times) == 0:
            return -1
        diffs = np.abs(self._onset_times - t)
        nearest_idx = int(np.argmin(diffs))
        # Convert the hitbox pixel count to data-coordinate distance
        vb = plot_widget.plotItem.vb
        px_width = vb.viewPixelSize()[0]  # data-coord width of one pixel
        threshold = self._onset_hitbox_px * px_width
        if diffs[nearest_idx] <= threshold:
            return nearest_idx
        return -1

    def _plot_for_event_target(self, obj) -> Optional['pg.PlotWidget']:
        """Map a viewport or scene object back to its plot widget."""
        if obj in (self._waveform_plot.viewport(), self._waveform_plot.scene()):
            return self._waveform_plot
        if obj in (self._spec_plot.viewport(), self._spec_plot.scene()):
            return self._spec_plot
        return None

    def _is_spec_event_target(self, obj) -> bool:
        """Return True when an event target belongs to the spectrogram."""
        return obj in (self._spec_plot.viewport(), self._spec_plot.scene())

    def _event_pos_to_time(self, plot_widget: 'pg.PlotWidget', obj, event) -> Optional[float]:
        """Convert a viewport or scene mouse event into a time coordinate."""
        if obj is plot_widget.scene():
            vb = plot_widget.plotItem.vb
            view_pos = vb.mapSceneToView(event.scenePos())
            t = view_pos.x()
            if t < 0:
                t = 0.0
            elif t > self._duration:
                t = self._duration
            return t
        return self._viewport_pos_to_time(plot_widget, event.position())

    def _event_pos_to_time_freq(self, plot_widget: 'pg.PlotWidget', obj, event) -> Optional[Tuple[float, float]]:
        """Convert a viewport or scene mouse event into (time, frequency)."""
        if obj is plot_widget.scene():
            vb = plot_widget.plotItem.vb
            view_pos = vb.mapSceneToView(event.scenePos())
            t = view_pos.x()
            f = view_pos.y()
            if t < 0:
                t = 0.0
            elif t > self._duration:
                t = self._duration
            if f < 0:
                f = 0.0
            return (t, f)
        return self._viewport_pos_to_time_freq(plot_widget, event.position())

    def _sync_onset_line_movable_state(self):
        """Keep onset lines non-movable; dragging is handled by eventFilter.

        We never set InfiniteLine.movable=True because pyqtgraph's built-in
        hover/click detection uses a wide bounding rect that intercepts
        mouse events far from the visible line.  Our eventFilter handles
        onset dragging with a precise pixel-based hit test instead.
        """
        for line_w, line_s in self._onset_lines:
            line_w.setMovable(False)
            line_s.setMovable(False)

    def eventFilter(self, obj, event):
        """Intercept mouse/wheel events on the plot viewports.

        Controls:
        - Plain left-click + drag: create region selection (unless on onset)
        - Left-click + drag on onset line: drag onset to new position
        - Shift + click: extend selection (two-click range)
        - Ctrl + click: add a new onset
        - Scroll-wheel: pan / zoom
        - Trackpad pinch: zoom
        """
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QMouseEvent, QNativeGestureEvent

        if self._y is None:
            return super().eventFilter(obj, event)

        etype = event.type()
        plot_widget = self._plot_for_event_target(obj)

        # ---- Scroll-wheel: pan (plain) / zoom (Shift) ----
        if etype == QEvent.Type.Wheel:
            return self._handle_wheel(obj, event)

        # ---- Trackpad pinch-to-zoom (macOS native gesture) ----
        if etype == QEvent.Type.NativeGesture and isinstance(event, QNativeGestureEvent):
            if event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                return self._handle_pinch_zoom(obj, event)

        mouse_press_types = (QEvent.Type.MouseButtonPress, QEvent.Type.GraphicsSceneMousePress)
        mouse_move_types = (QEvent.Type.MouseMove, QEvent.Type.GraphicsSceneMouseMove)
        mouse_release_types = (QEvent.Type.MouseButtonRelease, QEvent.Type.GraphicsSceneMouseRelease)

        if etype in mouse_press_types and plot_widget is not None:
            if event.button() == Qt.MouseButton.LeftButton:
                pw = plot_widget
                t = self._event_pos_to_time(pw, obj, event)
                if t is None:
                    return super().eventFilter(obj, event)

                mods = event.modifiers()

                # Ctrl+click → add onset (emit signal for onset editor)
                if mods & Qt.KeyboardModifier.ControlModifier:
                    self.viewCtrlClicked.emit(t)
                    return True

                # Shift+click → two-click range selection
                if mods & Qt.KeyboardModifier.ShiftModifier:
                    self._handle_range_click(t)
                    return True

                # Focus mode: draw rectangle on spectrogram (priority
                # over onset drag so left-click always draws a region)
                if self._focus_mode and self._is_spec_event_target(obj):
                    scene_pos = self._event_scene_pos(pw, obj, event)
                    hit_roi = self._focus_rect_item_at_scene_pos(scene_pos)
                    if hit_roi is not None:
                        hit_idx = getattr(hit_roi, '_focus_index', -1)
                        if hit_idx >= 0:
                            self._select_focus_region(hit_idx)
                        return False

                    self.clear_focus_region_selection()
                    tf = self._event_pos_to_time_freq(pw, obj, event)
                    if tf is not None:
                        self._start_focus_drag(tf[0], tf[1])
                        return True

                # Plain left-click: check if we're clicking on an onset
                onset_idx = self._is_near_onset(t, pw)
                allow_onset_drag = self._onset_draggable and not (
                    self._focus_mode and pw is self._spec_plot
                )
                if onset_idx >= 0 and allow_onset_drag:
                    # Start dragging the onset
                    self._onset_dragging = True
                    self._onset_drag_index = onset_idx
                    self._onset_drag_start_time = self._onset_times[onset_idx]
                    self._region_drag_did_move = False
                    self._select_onset(onset_idx)
                    self.onsetClicked.emit(onset_idx, self._onset_times[onset_idx])
                    return True

                # Plain left-click on empty space → start region drag
                self._region_drag_did_move = False
                self._region_drag_is_shift = False
                self._start_region_drag(t)
                return True

            # Right-click on spectrogram in focus mode → show context menu
            if (event.button() == Qt.MouseButton.RightButton
                    and self._focus_mode
                    and self._is_spec_event_target(obj)):
                pw = self._spec_plot
                tf = self._event_pos_to_time_freq(pw, obj, event)
                if tf is not None:
                    hit_idx = self._focus_region_hit_test(tf[0], tf[1])
                    if hit_idx >= 0 and hit_idx < len(self._focus_rect_items):
                        screen_pos = (event.globalPosition().toPoint()
                                      if hasattr(event, 'globalPosition')
                                      else event.screenPos())
                        self._show_focus_context_menu(
                            self._focus_rect_items[hit_idx],
                            screen_pos)
                        return True

        elif etype in mouse_move_types and plot_widget is not None:
            # Focus-region dragging (drawing new rectangle)
            if self._focus_dragging:
                pw = self._spec_plot
                tf = self._event_pos_to_time_freq(pw, obj, event)
                if tf is not None:
                    dist = abs(tf[0] - self._focus_drag_start_t) + abs(tf[1] - self._focus_drag_start_f)
                    if dist > 0.005:
                        self._focus_drag_did_move = True
                    self._update_focus_drag(tf[0], tf[1])
                return True

            # Onset dragging
            if self._onset_dragging:
                pw = plot_widget
                t = self._event_pos_to_time(pw, obj, event)
                if t is not None:
                    if abs(t - self._onset_drag_start_time) > 0.002:
                        self._region_drag_did_move = True
                    self._update_onset_drag(t)
                return True

            # Region dragging
            if self._region_dragging:
                pw = plot_widget
                t = self._event_pos_to_time(pw, obj, event)
                if t is not None:
                    if abs(t - self._region_drag_start) > 0.005:
                        self._region_drag_did_move = True
                    self._update_region_drag(t)
                return True

        elif etype in mouse_release_types and plot_widget is not None:
            # Focus-region drag release (finalize new rectangle)
            if self._focus_dragging:
                pw = self._spec_plot
                tf = self._event_pos_to_time_freq(pw, obj, event)
                self._focus_dragging = False
                if tf is not None and self._focus_drag_did_move:
                    self._end_focus_drag(tf[0], tf[1])
                elif self._focus_drag_rect is not None:
                    # Too small or no move — remove preview rect
                    try:
                        self._spec_plot.removeItem(self._focus_drag_rect)
                    except Exception:
                        pass
                    self._focus_drag_rect = None
                return True

            # Onset drag release
            if self._onset_dragging:
                pw = plot_widget
                t = self._event_pos_to_time(pw, obj, event)
                self._onset_dragging = False
                if t is not None and self._region_drag_did_move:
                    self._finish_onset_drag(t)
                # If no move, it was just a click on the onset (already handled)
                return True

            # Region drag release
            if self._region_dragging:
                pw = plot_widget
                t = self._event_pos_to_time(pw, obj, event)
                if t is not None:
                    if not self._region_drag_did_move:
                        # Click without dragging → normal click
                        self.clear_selection_region()
                        self._region_dragging = False
                        self._on_click_no_drag(t, pw)
                    else:
                        self._end_region_drag(t)
                else:
                    self._region_dragging = False
                    self.clear_selection_region()
                return True

        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Onset dragging helpers
    # ------------------------------------------------------------------

    def _update_onset_drag(self, t: float):
        """Move the onset line visually while dragging."""
        idx = self._onset_drag_index
        if idx < 0 or idx >= len(self._onset_lines):
            return
        # Clamp to valid range
        t = max(0.0, min(t, self._duration))
        pair = self._onset_lines[idx]
        for line in pair:
            line.setValue(t)

    def _finish_onset_drag(self, t: float):
        """Finalize onset drag — update internal data and emit signal."""
        idx = self._onset_drag_index
        if idx < 0 or idx >= len(self._onset_times):
            return
        t = max(0.0, min(t, self._duration))
        self._onset_times[idx] = t
        # Re-sort and rebuild if order changed
        order = np.argsort(self._onset_times)
        if not np.all(order == np.arange(len(order))):
            self._onset_times = self._onset_times[order]
            new_idx = int(np.where(order == idx)[0][0])
            self.set_onset_markers(self._onset_times,
                                   draggable=self._onset_draggable)
            self.onsetMoved.emit(new_idx, t)
        else:
            self.onsetMoved.emit(idx, t)

    def _handle_wheel(self, obj, event) -> bool:
        """Handle wheel gestures for x-pan and y-zoom controls."""
        angle_delta = event.angleDelta()
        pixel_delta = event.pixelDelta()
        mods = event.modifiers()
        pw = self._plot_for_event_target(obj)
        if pw is None:
            return True

        is_trackpad = (pixel_delta.x() != 0 or pixel_delta.y() != 0)
        pos = self._event_pos_to_view_pos(pw, obj, event)
        zoom_delta = self._dominant_wheel_delta(pixel_delta, angle_delta, is_trackpad)

        # Shift+scroll always controls Y-axis zoom on the hovered plot.
        if (mods & Qt.KeyboardModifier.ShiftModifier) and zoom_delta != 0:
            y_center = self._y_zoom_anchor(pw, pos)
            factor = pow(2.0, -zoom_delta / 600.0)
            self._zoom_y_axis(pw, y_center, factor)
            return True

        # Cmd/Ctrl + scroll controls X-axis zoom for both mouse and trackpad.
        if ((mods & Qt.KeyboardModifier.ControlModifier)
                or (mods & Qt.KeyboardModifier.MetaModifier)):
            if zoom_delta != 0:
                x_center = self._current_view_x_center() if pos is None else pos.x()
                factor = pow(2.0, -zoom_delta / 600.0)
                self._zoom_x_axis(x_center, factor)
            return True

        # Plain scroll pans x-axis; trackpad path prefers pixel deltas to keep
        # smooth momentum and avoid axis-jitter from mixed deltas.
        if is_trackpad:
            if abs(pixel_delta.y()) >= abs(pixel_delta.x()):
                scroll_amount = -pixel_delta.y()
            else:
                scroll_amount = -pixel_delta.x()
        else:
            scroll_amount = angle_delta.y() if angle_delta.y() != 0 else angle_delta.x()

        if scroll_amount != 0:
            self._pan_x_axis(scroll_amount)
            return True

        return True  # consume unknown wheel variants

    def _handle_pinch_zoom(self, obj, event) -> bool:
        """Handle trackpad pinch-to-zoom gesture (macOS)."""
        pw = self._plot_for_event_target(obj)
        if pw is None:
            return True
        # event.value() is the incremental scale factor (e.g. 0.02 = 2% zoom)
        scale_delta = event.value()
        factor = 1.0 / (1.0 + scale_delta)

        pos = self._event_pos_to_view_pos(pw, obj, event)
        mods = event.modifiers()

        # Shift+pinch controls y-axis zoom; plain pinch keeps x-axis zoom.
        if mods & Qt.KeyboardModifier.ShiftModifier:
            y_center = self._y_zoom_anchor(pw, pos)
            self._zoom_y_axis(pw, y_center, factor)
            return True

        t_center = self._current_view_x_center() if pos is None else pos.x()
        self._zoom_x_axis(t_center, factor)
        return True

    def _current_view_x_center(self) -> float:
        vr = self._waveform_plot.viewRange()[0]
        return (vr[0] + vr[1]) / 2.0

    def _current_view_y_center(self, plot_widget: 'pg.PlotWidget') -> float:
        vr = plot_widget.viewRange()[1]
        return (vr[0] + vr[1]) / 2.0

    def _event_pos_to_view_pos(self, plot_widget: 'pg.PlotWidget', obj, event):
        """Map an input-event position to plot view coordinates."""
        vb = plot_widget.plotItem.vb

        if obj is plot_widget.scene() and hasattr(event, 'scenePos'):
            return vb.mapSceneToView(event.scenePos())

        if hasattr(event, 'position'):
            pos = event.position()
            scene_pos = plot_widget.mapToScene(int(pos.x()), int(pos.y()))
            return vb.mapSceneToView(scene_pos)

        return None

    def _dominant_wheel_delta(self, pixel_delta, angle_delta, is_trackpad: bool) -> float:
        """Return the dominant wheel component across x/y for robust modifier zoom."""
        if is_trackpad:
            delta = pixel_delta.y() if abs(pixel_delta.y()) >= abs(pixel_delta.x()) else pixel_delta.x()
            return -delta
        return angle_delta.y() if abs(angle_delta.y()) >= abs(angle_delta.x()) else angle_delta.x()

    def _y_zoom_anchor(self, plot_widget: 'pg.PlotWidget', view_pos) -> float:
        """Return y-anchor for zoom: centered on waveform, cursor on spectrogram."""
        if plot_widget is self._waveform_plot or view_pos is None:
            return self._current_view_y_center(plot_widget)
        return float(view_pos.y())

    def _pan_x_axis(self, scroll_amount: float):
        """Pan along time axis; positive scroll moves right."""
        vr = self._waveform_plot.viewRange()[0]
        span = vr[1] - vr[0]
        shift = scroll_amount / 600.0 * span
        lo = vr[0] + shift
        hi = vr[1] + shift

        margin = self._duration * 0.025 if self._duration > 0 else 0.0
        if lo < -margin:
            lo = -margin
            hi = lo + span
        if hi > self._duration + margin:
            hi = self._duration + margin
            lo = hi - span
        self._waveform_plot.setXRange(lo, hi, padding=0)

    def _zoom_x_axis(self, x_center: float, factor: float):
        """Zoom x-axis around *x_center* using multiplicative *factor*."""
        vr = self._waveform_plot.viewRange()[0]
        span = vr[1] - vr[0]
        if span <= 0:
            return

        new_span = span * factor
        max_span = self._duration * 1.1 if self._duration > 0 else new_span
        min_span = max(0.01, self._duration * 0.001) if self._duration > 0 else 0.01
        new_span = max(min_span, min(new_span, max_span))

        frac = (x_center - vr[0]) / span
        lo = x_center - frac * new_span
        hi = x_center + (1.0 - frac) * new_span

        margin = self._duration * 0.025 if self._duration > 0 else 0.0
        if lo < -margin:
            lo = -margin
            hi = lo + new_span
        if hi > self._duration + margin:
            hi = self._duration + margin
            lo = hi - new_span

        self._waveform_plot.setXRange(lo, hi, padding=0)

    def _zoom_y_axis(self, plot_widget: 'pg.PlotWidget', y_center: float, factor: float):
        """Zoom y-axis for waveform amplitude or spectrogram frequency."""
        vr = plot_widget.viewRange()[1]
        span = vr[1] - vr[0]
        if span <= 0:
            return

        if plot_widget is self._waveform_plot:
            y_abs = max(0.1, self._waveform_y_abs_max)
            y_min = -y_abs
            y_max = y_abs
            min_span = max(0.02, y_abs * 0.02)
            max_span = y_max - y_min
        else:
            y_min = min(self._spec_f_min, self._spec_f_max)
            y_max = max(self._spec_f_min, self._spec_f_max)
            total = y_max - y_min
            if total <= 0:
                return
            min_span = max(10.0, total * 0.01)
            max_span = total

        new_span = span * factor
        new_span = max(min_span, min(new_span, max_span))

        y_center = max(y_min, min(y_center, y_max))
        frac = (y_center - vr[0]) / span
        lo = y_center - frac * new_span
        hi = y_center + (1.0 - frac) * new_span

        if lo < y_min:
            lo = y_min
            hi = lo + new_span
        if hi > y_max:
            hi = y_max
            lo = hi - new_span

        plot_widget.setYRange(lo, hi, padding=0)

    def _viewport_pos_to_time(self, plot_widget: 'pg.PlotWidget',
                               pos) -> Optional[float]:
        """Convert a viewport-local position to a time coordinate."""
        scene_pos = plot_widget.mapToScene(int(pos.x()), int(pos.y()))
        vb = plot_widget.plotItem.vb
        view_pos = vb.mapSceneToView(scene_pos)
        t = view_pos.x()
        if t < 0:
            t = 0.0
        elif t > self._duration:
            t = self._duration
        return t

    def _viewport_pos_to_time_freq(self, plot_widget: 'pg.PlotWidget',
                                    pos) -> Optional[Tuple[float, float]]:
        """Convert a viewport-local position to (time, frequency) on the spectrogram."""
        scene_pos = plot_widget.mapToScene(int(pos.x()), int(pos.y()))
        vb = plot_widget.plotItem.vb
        view_pos = vb.mapSceneToView(scene_pos)
        t = view_pos.x()
        f = view_pos.y()
        if t < 0:
            t = 0.0
        elif t > self._duration:
            t = self._duration
        if f < 0:
            f = 0.0
        return (t, f)

    # ------------------------------------------------------------------
    # Focus-region drawing helpers
    # ------------------------------------------------------------------

    def _start_focus_drag(self, t: float, f: float):
        """Begin drawing a new focus region rectangle on the spectrogram."""
        self._focus_dragging = True
        self._focus_drag_start_t = t
        self._focus_drag_start_f = f
        self._focus_drag_did_move = False

        # Determine colour from current polarity
        if self._focus_polarity == "positive":
            border_color = _FOCUS_POSITIVE_BORDER
            fill_color = _FOCUS_POSITIVE_COLOR
        else:
            border_color = _FOCUS_NEGATIVE_BORDER
            fill_color = _FOCUS_NEGATIVE_COLOR

        pen = pg.mkPen(color=border_color, width=2, style=Qt.PenStyle.DashLine)
        brush = pg.mkBrush(color=fill_color)

        # Create a temporary RectROI for visual feedback while dragging
        self._focus_drag_rect = _FocusRectROI(
            pos=(t, f), size=(0.001, 1.0),
            pen=pen,
            brush=brush,
            movable=False,
            resizable=False,
            rotatable=False,
        )
        self._focus_drag_rect.setZValue(55)
        self._spec_plot.addItem(self._focus_drag_rect)

    def _update_focus_drag(self, t: float, f: float):
        """Update the preview rectangle while user is dragging."""
        if self._focus_drag_rect is None:
            return
        t0 = self._focus_drag_start_t
        f0 = self._focus_drag_start_f
        x = min(t0, t)
        y = min(f0, f)
        w = abs(t - t0)
        h = abs(f - f0)
        self._focus_drag_rect.setPos(x, y)
        self._focus_drag_rect.setSize((max(w, 0.001), max(h, 1.0)))

    def _end_focus_drag(self, t: float, f: float):
        """Finalize the focus region rectangle."""
        # Remove the temporary preview rect
        if self._focus_drag_rect is not None:
            try:
                self._spec_plot.removeItem(self._focus_drag_rect)
            except Exception:
                pass
            self._focus_drag_rect = None

        t0 = self._focus_drag_start_t
        f0 = self._focus_drag_start_f
        t_start = min(t0, t)
        t_end = max(t0, t)
        f_low = min(f0, f)
        f_high = max(f0, f)

        # Require minimum size
        if (t_end - t_start) < 0.01 or (f_high - f_low) < 5.0:
            return

        region = {
            "t_start": t_start,
            "t_end": t_end,
            "f_low": f_low,
            "f_high": f_high,
            "polarity": self._focus_polarity,
        }
        idx = len(self._focus_regions)
        self._focus_regions.append(region)
        self._add_focus_rect_item(idx, region)
        self._select_focus_region(idx)
        self.focusRegionAdded.emit(region)

    def _focus_region_hit_test(self, t: float, f: float) -> int:
        """Return the index of the focus region under (t, f), or -1."""
        for i, region in enumerate(self._focus_regions):
            if (region["t_start"] <= t <= region["t_end"]
                    and region["f_low"] <= f <= region["f_high"]):
                return i
        return -1

    def _event_scene_pos(self, plot_widget: 'pg.PlotWidget', obj, event):
        """Convert a viewport or scene mouse event into a scene position."""
        if obj is plot_widget.scene():
            return event.scenePos()
        pos = event.position()
        return plot_widget.mapToScene(int(pos.x()), int(pos.y()))

    def _focus_rect_item_at_scene_pos(self, scene_pos) -> Optional[_FocusRectROI]:
        """Return the focus ROI or handle under the given scene position."""
        scene = self._spec_plot.scene()
        if scene is None:
            return None
        for item in scene.items(scene_pos):
            current = item
            while current is not None:
                if current in self._focus_rect_items:
                    return current
                current = current.parentItem()
        return None

    def _focus_region_style(self, polarity: str, selected: bool = False):
        """Return pen/brush colours for a focus ROI."""
        if polarity == "positive":
            border = _FOCUS_POSITIVE_BORDER
            fill = _FOCUS_POSITIVE_COLOR
        else:
            border = _FOCUS_NEGATIVE_BORDER
            fill = _FOCUS_NEGATIVE_COLOR

        if selected:
            border = (border[0], border[1], border[2], _FOCUS_SELECTED_BORDER_ALPHA)
            fill = (fill[0], fill[1], fill[2], _FOCUS_SELECTED_FILL_ALPHA)
            width = 3
            z_value = 47
        else:
            width = 2
            z_value = 45
        return border, fill, width, z_value

    def _apply_focus_rect_style(self, rect: _FocusRectROI, polarity: str, selected: bool = False):
        """Update one focus ROI's visuals to reflect its polarity and selection."""
        border, fill, width, z_value = self._focus_region_style(polarity, selected=selected)
        rect.setPen(pg.mkPen(color=border, width=width))
        rect.setBrush(pg.mkBrush(color=fill))
        rect.setZValue(z_value)

    def _get_active_play_region(self) -> Optional[Tuple[float, float]]:
        """Return the currently active time-only playback region, if any."""
        if self._region_select_item_w is not None:
            lo, hi = self._region_select_item_w.getRegion()
            return (lo, hi)
        idx = self._selected_focus_region_index
        if 0 <= idx < len(self._focus_regions):
            region = self._focus_regions[idx]
            return (region["t_start"], region["t_end"])
        return None

    def _select_focus_region(self, index: int, emit_signal: bool = True):
        """Select a focus ROI and use its time range for playback actions."""
        if index < 0 or index >= len(self._focus_regions):
            self.clear_focus_region_selection(emit_signal=emit_signal)
            return

        self.clear_selection_region()
        previous = self._selected_focus_region_index
        if previous == index and emit_signal:
            region = self._focus_regions[index]
            self.regionSelected.emit(region["t_start"], region["t_end"])
            return

        self._selected_focus_region_index = index
        for rect in self._focus_rect_items:
            rect_idx = getattr(rect, '_focus_index', -1)
            polarity = getattr(rect, '_focus_polarity', 'positive')
            self._apply_focus_rect_style(rect, polarity, selected=(rect_idx == index))

        if emit_signal:
            region = self._focus_regions[index]
            self.regionSelected.emit(region["t_start"], region["t_end"])

    def clear_focus_region_selection(self, emit_signal: bool = True):
        """Clear the selected focus ROI, if any."""
        had_selection = self._selected_focus_region_index >= 0
        self._selected_focus_region_index = -1
        for rect in self._focus_rect_items:
            polarity = getattr(rect, '_focus_polarity', 'positive')
            self._apply_focus_rect_style(rect, polarity, selected=False)
        if had_selection and emit_signal:
            self.regionCleared.emit()

    def get_selected_focus_region(self) -> Optional[dict]:
        """Return the currently selected focus ROI dict, if any."""
        idx = self._selected_focus_region_index
        if 0 <= idx < len(self._focus_regions):
            return dict(self._focus_regions[idx])
        return None

    def has_selected_focus_region(self) -> bool:
        """Return whether a focus ROI is currently selected."""
        return self.get_selected_focus_region() is not None

    def remove_selected_focus_region(self) -> bool:
        """Delete the selected focus ROI, if any. Returns True if removed."""
        idx = self._selected_focus_region_index
        if idx < 0:
            return False
        self._remove_focus_region(idx)
        return True

    def _on_focus_rect_clicked(self, roi: _FocusRectROI, event):
        """Select a focus ROI when the user left-clicks it."""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        idx = getattr(roi, '_focus_index', -1)
        if idx >= 0:
            self._select_focus_region(idx)

    # ------------------------------------------------------------------
    # Region-selection drag helpers
    # ------------------------------------------------------------------

    def _start_region_drag(self, t: float):
        self._region_dragging = True
        self._region_drag_start = t
        self.clear_focus_region_selection()
        # Remove previous selection region
        self.clear_selection_region()
        # Create new selection overlays
        color = (76, 175, 80, 50)  # semi-transparent green
        self._region_select_item_w = pg.LinearRegionItem(
            values=[t, t], brush=pg.mkBrush(color), movable=False)
        self._region_select_item_w.setZValue(50)
        self._waveform_plot.addItem(self._region_select_item_w)
        self._region_select_item_s = pg.LinearRegionItem(
            values=[t, t], brush=pg.mkBrush(color), movable=False)
        self._region_select_item_s.setZValue(50)
        self._spec_plot.addItem(self._region_select_item_s)

    def _update_region_drag(self, t: float):
        lo = min(self._region_drag_start, t)
        hi = max(self._region_drag_start, t)
        if self._region_select_item_w:
            self._region_select_item_w.setRegion([lo, hi])
        if self._region_select_item_s:
            self._region_select_item_s.setRegion([lo, hi])

    def _end_region_drag(self, t: float):
        self._region_dragging = False
        lo = min(self._region_drag_start, t)
        hi = max(self._region_drag_start, t)
        if hi - lo < 0.01:
            # Too small — treat as a click, clear selection
            self.clear_selection_region()
            return
        if self._region_select_item_w:
            self._region_select_item_w.setRegion([lo, hi])
        if self._region_select_item_s:
            self._region_select_item_s.setRegion([lo, hi])
        self.regionSelected.emit(lo, hi)

    def clear_selection_region(self):
        """Remove the Shift+drag selection region overlay."""
        if self._region_select_item_w is not None:
            self._waveform_plot.removeItem(self._region_select_item_w)
            self._region_select_item_w = None
        if self._region_select_item_s is not None:
            self._spec_plot.removeItem(self._region_select_item_s)
            self._region_select_item_s = None
        # Also clear any two-click start marker
        self._clear_range_start_marker()

    def _clear_range_start_marker(self):
        """Remove the temporary start-point marker used in Select Range mode."""
        if self._range_start_line_w is not None:
            self._waveform_plot.removeItem(self._range_start_line_w)
            self._range_start_line_w = None
        if self._range_start_line_s is not None:
            self._spec_plot.removeItem(self._range_start_line_s)
            self._range_start_line_s = None
        self._select_range_start = None

    def set_select_range_mode(self, enabled: bool):
        """Enable or disable the two-click Select Range mode."""
        self._select_range_mode = enabled
        if not enabled:
            self._clear_range_start_marker()

    def _handle_range_click(self, t: float):
        """Process a click in Select Range mode.

        First click: set the range start and show a vertical marker.
        Second click: create a region from start to this click and emit regionSelected.
        """
        if self._select_range_start is None:
            # --- First click: mark the start ---
            self._select_range_start = t
            pen = pg.mkPen(color='#00ff00', width=2, style=Qt.PenStyle.DashLine)
            self._range_start_line_w = pg.InfiniteLine(pos=t, angle=90, pen=pen)
            self._range_start_line_s = pg.InfiniteLine(pos=t, angle=90, pen=pen)
            self._waveform_plot.addItem(self._range_start_line_w)
            self._spec_plot.addItem(self._range_start_line_s)
        else:
            # --- Second click: create the region ---
            start = min(self._select_range_start, t)
            end = max(self._select_range_start, t)
            self._clear_range_start_marker()
            if end - start < 0.01:
                return  # too small
            # Remove any existing region overlay first
            self.clear_selection_region()
            # Create region overlay directly
            color = (76, 175, 80, 50)
            self._region_select_item_w = pg.LinearRegionItem(
                values=[start, end], brush=pg.mkBrush(color), movable=False)
            self._region_select_item_w.setZValue(50)
            self._waveform_plot.addItem(self._region_select_item_w)
            self._region_select_item_s = pg.LinearRegionItem(
                values=[start, end], brush=pg.mkBrush(color), movable=False)
            self._region_select_item_s.setZValue(50)
            self._spec_plot.addItem(self._region_select_item_s)
            self.regionSelected.emit(start, end)

    # ------------------------------------------------------------------
    # Click handling
    # ------------------------------------------------------------------

    def _on_click_no_drag(self, t: float, plot_widget: pg.PlotWidget):
        """Handle a plain left-click that did NOT become a drag.

        Called from eventFilter when the user presses and releases
        without moving beyond the drag threshold.
        """
        if self._focus_mode and plot_widget is self._spec_plot:
            return

        if t < 0 or t > self._duration:
            return

        # Check if click is near an existing onset marker
        if self._onset_draggable and len(self._onset_times) > 0:
            diffs = np.abs(self._onset_times - t)
            nearest_idx = int(np.argmin(diffs))
            vb = plot_widget.plotItem.vb
            px_width = vb.viewPixelSize()[0]
            threshold = self._onset_hitbox_px * px_width
            if diffs[nearest_idx] < threshold:
                self._select_onset(nearest_idx)
                self.onsetClicked.emit(nearest_idx, self._onset_times[nearest_idx])
                return

        # If a selection region exists, clear it on click outside the region
        if self._region_select_item_w is not None:
            rgn = self._region_select_item_w.getRegion()
            if t < rgn[0] or t > rgn[1]:
                self.clear_selection_region()
                self.regionCleared.emit()

        # Plain click → seek + emit viewClicked
        self.seek(t)
        self.viewClicked.emit(t)

    def _on_plot_clicked(self, evt, plot_widget: pg.PlotWidget):
        """Handle mouse click on waveform or spectrogram (fallback for sigMouseClicked)."""
        if self._y is None:
            return
        if self._focus_mode and plot_widget is self._spec_plot:
            return
        pos = evt.scenePos()
        vb = plot_widget.plotItem.vb
        mouse_point = vb.mapSceneToView(pos)
        t = mouse_point.x()

        if t < 0 or t > self._duration:
            return

        modifiers = evt.modifiers()

        # Ctrl+click → add onset
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self.viewCtrlClicked.emit(t)
            return

        # Shift+click → two-click range selection
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            self._handle_range_click(t)
            return

        # Check if click is near an existing onset marker
        if self._onset_draggable and len(self._onset_times) > 0:
            diffs = np.abs(self._onset_times - t)
            nearest_idx = int(np.argmin(diffs))
            # Pixel-based threshold using configurable hitbox
            pixel_width = vb.viewPixelSize()[0]  # data-units per pixel
            threshold = pixel_width * self._onset_hitbox_px
            if diffs[nearest_idx] < threshold:
                self._select_onset(nearest_idx)
                self.onsetClicked.emit(nearest_idx, self._onset_times[nearest_idx])
                return

        # If a selection region exists, clear it on click outside the region
        if self._region_select_item_w is not None:
            rgn = self._region_select_item_w.getRegion()
            if t < rgn[0] or t > rgn[1]:
                self.clear_selection_region()
                self.regionCleared.emit()

        # Plain click → seek + emit viewClicked
        self.seek(t)
        self.viewClicked.emit(t)

    def _select_onset(self, idx: int):
        """Highlight the selected onset marker."""
        # Deselect previous
        if 0 <= self._selected_onset < len(self._onset_lines):
            pair = self._onset_lines[self._selected_onset]
            for line in pair:
                line.setPen(pg.mkPen(color=_ONSET_DEFAULT_COLOR, width=2))
        # Select new
        self._selected_onset = idx
        if 0 <= idx < len(self._onset_lines):
            pair = self._onset_lines[idx]
            for line in pair:
                line.setPen(pg.mkPen(color=_ONSET_SELECTED_COLOR, width=3))

    def center_on_time(self, time_sec: float):
        """Center the current visible time span on ``time_sec``."""
        if self._duration <= 0:
            return
        vr = self._waveform_plot.viewRange()[0]
        span = max(vr[1] - vr[0], 0.01)
        half_span = span / 2.0
        lo = max(0.0, float(time_sec) - half_span)
        hi = lo + span
        if hi > self._duration:
            hi = self._duration
            lo = max(0.0, hi - span)
        self._waveform_plot.setXRange(lo, hi, padding=0)

    def select_onset(self, idx: int, *, center: bool = False, seek_playhead: bool = False):
        """Select an onset marker, optionally centering the view on it."""
        if idx < 0 or idx >= len(self._onset_times):
            return
        self._select_onset(idx)
        onset_time = float(self._onset_times[idx])
        if center:
            self.center_on_time(onset_time)
        else:
            self.scroll_to_time(onset_time)
        if seek_playhead:
            self.seek(onset_time)

    # ------------------------------------------------------------------
    # Onset marker overlay API
    # ------------------------------------------------------------------

    def set_onset_markers(self, times_sec: np.ndarray,
                          colors: list | None = None,
                          draggable: bool = False) -> list:
        """Display vertical onset markers at the given times.

        Parameters
        ----------
        times_sec : array of onset times in seconds
        colors : optional list of (r,g,b,a) tuples per marker
        draggable : if True, markers can be dragged to reposition

        Returns
        -------
        List of (waveform_line, spec_line) tuples for each marker.
        """
        self.clear_onset_markers()
        times = np.asarray(times_sec, dtype=np.float64)
        self._onset_times = times.copy()
        self._onset_draggable = draggable

        result = []
        for i, t in enumerate(times):
            color = colors[i] if colors and i < len(colors) else _ONSET_DEFAULT_COLOR
            pen = pg.mkPen(color=color, width=2)

            line_w = pg.InfiniteLine(
                pos=t, angle=90, pen=pen, movable=False)
            line_w.setZValue(50)
            self._waveform_plot.addItem(line_w)

            line_s = pg.InfiniteLine(
                pos=t, angle=90, pen=pen, movable=False)
            line_s.setZValue(50)
            self._spec_plot.addItem(line_s)

            if draggable:
                # Capture index by default arg
                line_w.sigPositionChangeFinished.connect(
                    lambda ln, idx=i: self._on_marker_dragged(idx, ln))
                line_s.sigPositionChangeFinished.connect(
                    lambda ln, idx=i: self._on_marker_dragged(idx, ln))
                # Keep both lines synced
                line_w.sigPositionChanged.connect(
                    lambda ln, ls=line_s: ls.setValue(ln.value()))
                line_s.sigPositionChanged.connect(
                    lambda ln, lw=line_w: lw.setValue(ln.value()))

            pair = (line_w, line_s)
            self._onset_lines.append(pair)
            result.append(pair)

        self._sync_onset_line_movable_state()
        return result

    def set_onset_draggable(self, enabled: bool):
        """Enable or disable onset marker dragging at runtime."""
        self._onset_draggable = enabled
        self._sync_onset_line_movable_state()

    def clear_onset_markers(self):
        """Remove all onset markers."""
        for pair in self._onset_lines:
            for line in pair:
                try:
                    self._waveform_plot.removeItem(line)
                except Exception:
                    pass
                try:
                    self._spec_plot.removeItem(line)
                except Exception:
                    pass
        self._onset_lines.clear()
        self._onset_times = np.array([], dtype=np.float64)
        self._selected_onset = -1

    # ------------------------------------------------------------------
    # Comparison onset markers (read-only overlays)
    # ------------------------------------------------------------------

    def set_comparison_markers(self, layers: list[dict]):
        """Display comparison onset layers as non-draggable vertical lines.

        Parameters
        ----------
        layers : list of dicts, each with keys:
            ``times`` – array of onset times (seconds)
            ``color`` – (r, g, b, a) tuple
            ``style`` – optional Qt.PenStyle (default DashLine)
        """
        self.clear_comparison_markers()
        for layer in layers:
            times = np.asarray(layer["times"], dtype=np.float64)
            color = layer.get("color", (255, 165, 0, 180))
            style = layer.get("style", Qt.PenStyle.DashLine)
            for t in times:
                pen = pg.mkPen(color=color, width=1.5, style=style)
                lw = pg.InfiniteLine(pos=t, angle=90, pen=pen, movable=False)
                lw.setZValue(40)
                self._waveform_plot.addItem(lw)
                ls = pg.InfiniteLine(pos=t, angle=90, pen=pen, movable=False)
                ls.setZValue(40)
                self._spec_plot.addItem(ls)
                self._comparison_lines.append((lw, ls))

    def clear_comparison_markers(self):
        """Remove all comparison onset overlay markers."""
        for lw, ls in self._comparison_lines:
            try:
                self._waveform_plot.removeItem(lw)
            except Exception:
                pass
            try:
                self._spec_plot.removeItem(ls)
            except Exception:
                pass
        self._comparison_lines.clear()

    def add_onset_marker(self, time_sec: float, color=None,
                         draggable: bool | None = None) -> int:
        """Add a single onset marker. Returns the index of the new marker."""
        if draggable is None:
            draggable = self._onset_draggable

        # Find insertion position to keep sorted
        idx = int(np.searchsorted(self._onset_times, time_sec))
        self._onset_times = np.insert(self._onset_times, idx, time_sec)

        # Recreate all markers to maintain correct indices
        self.set_onset_markers(self._onset_times, draggable=draggable)
        self.onsetAdded.emit(time_sec)
        return idx

    def remove_onset_marker(self, index: int):
        """Remove the onset marker at the given index."""
        if index < 0 or index >= len(self._onset_times):
            return
        self._onset_times = np.delete(self._onset_times, index)
        self.set_onset_markers(self._onset_times,
                               draggable=self._onset_draggable)
        self.onsetRemoved.emit(index)

    def remove_selected_onset(self):
        """Remove the currently selected onset marker."""
        if self._selected_onset >= 0:
            idx = self._selected_onset
            self._selected_onset = -1
            self.remove_onset_marker(idx)

    def _on_marker_dragged(self, index: int, line: pg.InfiniteLine):
        """Called when a draggable onset marker is released."""
        new_t = line.value()
        if 0 <= index < len(self._onset_times):
            old_t = self._onset_times[index]
            self._onset_times[index] = new_t
            # Re-sort and rebuild if order changed
            order = np.argsort(self._onset_times)
            if not np.all(order == np.arange(len(order))):
                self._onset_times = self._onset_times[order]
                new_idx = int(np.where(order == index)[0][0])
                self.set_onset_markers(self._onset_times,
                                       draggable=self._onset_draggable)
                self.onsetMoved.emit(new_idx, new_t)
            else:
                self.onsetMoved.emit(index, new_t)

    # ------------------------------------------------------------------
    # Region overlay API
    # ------------------------------------------------------------------

    def add_region(self, start_sec: float, end_sec: float,
                   color=None, label: str | None = None,
                   movable: bool = False) -> pg.LinearRegionItem:
        """Add a colored region overlay to both plots."""
        if color is None:
            color = _REGION_DEFAULT_COLOR
        brush = pg.mkBrush(color)

        region = pg.LinearRegionItem(
            values=[start_sec, end_sec],
            brush=brush,
            movable=movable)
        region.setZValue(10)
        self._waveform_plot.addItem(region)

        region_s = pg.LinearRegionItem(
            values=[start_sec, end_sec],
            brush=brush,
            movable=movable)
        region_s.setZValue(10)
        self._spec_plot.addItem(region_s)

        # Sync region movements
        if movable:
            region.sigRegionChanged.connect(
                lambda: region_s.setRegion(region.getRegion()))
            region_s.sigRegionChanged.connect(
                lambda: region.setRegion(region_s.getRegion()))

        self._region_items.append(region)
        self._region_items.append(region_s)
        return region

    def clear_regions(self):
        """Remove all region overlays."""
        for item in self._region_items:
            try:
                self._waveform_plot.removeItem(item)
            except Exception:
                pass
            try:
                self._spec_plot.removeItem(item)
            except Exception:
                pass
        self._region_items.clear()

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play(self):
        """Start audio playback from the current playhead position."""
        if not _HAS_SOUNDDEVICE or self._y is None:
            return
        if self._playing:
            return
        self._last_playback_error = None
        self._clip_data = None
        self._clip_frame_idx = 0
        self._clip_start_time = 0.0
        self._clip_loop = False

        start_sample = int(self._play_offset * self._sr)
        if start_sample >= len(self._y):
            start_sample = 0
            self._play_offset = 0.0

        # Determine end sample (loop region or end of file)
        if self._loop_region:
            end_sample = min(int(self._loop_region[1] * self._sr), len(self._y))
            start_sample = max(int(self._loop_region[0] * self._sr), 0)
            if self._play_offset < self._loop_region[0]:
                self._play_offset = self._loop_region[0]
                start_sample = int(self._play_offset * self._sr)
        else:
            end_sample = len(self._y)

        self._stream_frame_idx = start_sample
        self._play_end_sample = end_sample
        self._play_start_wall = time.monotonic()
        self._play_start_sample = start_sample

        def callback(outdata, frames, time_info, status):
            idx = self._stream_frame_idx
            end = self._play_end_sample
            remaining = end - idx
            if remaining <= 0:
                if self._loop_region:
                    # Loop back
                    loop_start = int(self._loop_region[0] * self._sr)
                    self._stream_frame_idx = loop_start
                    self._play_start_wall = time.monotonic()
                    self._play_start_sample = loop_start
                    idx = loop_start
                    remaining = end - idx
                else:
                    outdata[:] = 0
                    raise sd.CallbackStop()

            chunk_len = min(frames, remaining)
            data = self._y[idx:idx + chunk_len] * self._volume
            outdata[:chunk_len, 0] = data
            if chunk_len < frames:
                outdata[chunk_len:] = 0
            self._stream_frame_idx = idx + chunk_len

        try:
            self._stream = sd.OutputStream(
                samplerate=self._sr,
                channels=1,
                dtype="float32",
                callback=callback,
                finished_callback=self._on_playback_finished,
                blocksize=1024)
            self._stream.start()
            self._playing = True
            self._play_btn.setText("⏸")
            self._stop_btn.setEnabled(True)
            self._anim_timer.start()
        except Exception as exc:
            print(f"[AudioViewer] Playback error: {exc}")
            self._last_playback_error = str(exc)
            if self._stream is not None:
                try:
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            self._playing = False

    def stop(self):
        """Stop playback and reset playhead."""
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.abort()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass
        self._playing = False
        self._clip_data = None
        self._clip_frame_idx = 0
        self._clip_start_time = 0.0
        self._clip_loop = False
        self._anim_timer.stop()
        self._play_btn.setText("▶")
        self._stop_btn.setEnabled(False)

    def _play_from_beginning(self):
        """Stop any current playback, seek to start, and play."""
        self.stop()
        self.seek(0)
        self.play()

    def _toggle_play(self):
        if self._playing:
            self.stop()
        else:
            selected_focus = self.get_selected_focus_region()
            if selected_focus is not None:
                start = selected_focus["t_start"]
                end = selected_focus["t_end"]
                if end - start >= 0.01:
                    self.play_focus_region(selected_focus, loop=bool(self._loop_region))
                    return
            # If a time region is selected, play just that region
            active_region = self._get_active_play_region()
            if active_region is not None:
                start, end = active_region
                if end - start >= 0.01:
                    if self._loop_region:
                        # Loop mode active → use normal play with loop
                        self.set_loop_region(start, end)
                        self.seek(start)
                        self.play()
                    else:
                        self.play_region(start, end)
                    return
            self.play()

    def play_region(self, start: float, end: float):
        """Play a specific region once (no looping) and stop."""
        if not _HAS_SOUNDDEVICE or self._y is None:
            return
        if self._playing:
            return
        self._last_playback_error = None
        self._clip_data = None
        self._clip_frame_idx = 0
        self._clip_start_time = 0.0
        self._clip_loop = False
        start_sample = max(int(start * self._sr), 0)
        end_sample = min(int(end * self._sr), len(self._y))
        if start_sample >= end_sample:
            return

        self._stream_frame_idx = start_sample
        self._play_end_sample = end_sample
        self._play_start_wall = time.monotonic()
        self._play_start_sample = start_sample
        self._play_offset = start

        def callback(outdata, frames, time_info, status):
            idx = self._stream_frame_idx
            remaining = self._play_end_sample - idx
            if remaining <= 0:
                outdata[:] = 0
                raise sd.CallbackStop()
            chunk_len = min(frames, remaining)
            data = self._y[idx:idx + chunk_len] * self._volume
            outdata[:chunk_len, 0] = data
            if chunk_len < frames:
                outdata[chunk_len:] = 0
            self._stream_frame_idx = idx + chunk_len

        try:
            self._stream = sd.OutputStream(
                samplerate=self._sr,
                channels=1,
                dtype="float32",
                callback=callback,
                finished_callback=self._on_playback_finished,
                blocksize=1024)
            self._stream.start()
            self._playing = True
            self._play_btn.setText("⏸")
            self._stop_btn.setEnabled(True)
            self._anim_timer.start()
        except Exception as exc:
            print(f"[AudioViewer] Playback error: {exc}")
            self._last_playback_error = str(exc)
            if self._stream is not None:
                try:
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            self._playing = False

    @staticmethod
    def _bandpass_clip(y: np.ndarray, sr: int, f_low: float, f_high: float) -> np.ndarray:
        """Return a bandpassed copy of *y* clamped to a valid frequency span."""
        nyquist = sr / 2.0
        lo = max(1.0, min(float(f_low), nyquist - 1.0))
        hi = max(lo + 1.0, min(float(f_high), nyquist - 1.0))
        if lo >= hi:
            return y.copy()
        try:
            from scipy.signal import butter, sosfilt
            sos = butter(4, [lo, hi], btype="band", fs=sr, output="sos")
            return sosfilt(sos, y).astype(y.dtype, copy=False)
        except Exception:
            return y.copy()

    def play_focus_region(self, region: dict, loop: bool = False):
        """Play a focus ROI as a time-limited, band-limited clip."""
        if not _HAS_SOUNDDEVICE or self._y is None:
            return
        if self._playing:
            return
        self._last_playback_error = None

        start = float(region.get("t_start", 0.0))
        end = float(region.get("t_end", 0.0))
        start_sample = max(int(start * self._sr), 0)
        end_sample = min(int(end * self._sr), len(self._y))
        if start_sample >= end_sample:
            return

        clip = self._y[start_sample:end_sample].copy()
        clip = self._bandpass_clip(
            clip,
            self._sr,
            region.get("f_low", 0.0),
            region.get("f_high", self._sr / 2.0),
        )
        if len(clip) == 0:
            return

        self._clip_data = clip
        self._clip_frame_idx = 0
        self._clip_start_time = start
        self._clip_loop = loop
        self._stream_frame_idx = start_sample
        self._play_end_sample = end_sample
        self._play_start_wall = time.monotonic()
        self._play_start_sample = start_sample
        self._play_offset = start

        def callback(outdata, frames, time_info, status):
            idx = self._clip_frame_idx
            clip_data = self._clip_data
            if clip_data is None:
                outdata[:] = 0
                raise sd.CallbackStop()
            remaining = len(clip_data) - idx
            if remaining <= 0:
                if self._clip_loop:
                    self._clip_frame_idx = 0
                    idx = 0
                    remaining = len(clip_data)
                else:
                    outdata[:] = 0
                    raise sd.CallbackStop()
            chunk_len = min(frames, remaining)
            data = clip_data[idx:idx + chunk_len] * self._volume
            outdata[:chunk_len, 0] = data
            if chunk_len < frames:
                outdata[chunk_len:] = 0
            self._clip_frame_idx = idx + chunk_len
            self._stream_frame_idx = start_sample + self._clip_frame_idx

        try:
            self._stream = sd.OutputStream(
                samplerate=self._sr,
                channels=1,
                dtype="float32",
                callback=callback,
                finished_callback=self._on_playback_finished,
                blocksize=1024)
            self._stream.start()
            self._playing = True
            self._play_btn.setText("⏸")
            self._stop_btn.setEnabled(True)
            self._anim_timer.start()
        except Exception as exc:
            print(f"[AudioViewer] Playback error: {exc}")
            self._last_playback_error = str(exc)
            if self._stream is not None:
                try:
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            self._playing = False
            self._clip_data = None
            self._clip_frame_idx = 0
            self._clip_loop = False

    def seek(self, time_sec: float):
        """Move the playhead to the given time."""
        time_sec = max(0.0, min(time_sec, self._duration))
        self._play_offset = time_sec
        self._playhead_wave.setValue(time_sec)
        self._playhead_spec.setValue(time_sec)
        self._update_time_label(time_sec)

        if self._playing:
            # Restart playback from new position
            self.stop()
            self.play()

    def set_loop_region(self, start: float, end: float):
        """Set a loop region for playback."""
        self._loop_region = (start, end)

    def clear_loop(self):
        """Clear the loop region."""
        self._loop_region = None

    def setPlaybackPosition(self, time_sec: float):
        """Alias for seek()."""
        self.seek(time_sec)

    def _on_playback_finished(self):
        """Called from sounddevice thread when playback ends."""
        # Schedule GUI update on main thread
        QTimer.singleShot(0, self._playback_stopped)

    def _playback_stopped(self):
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass
        self._playing = False
        self._clip_data = None
        self._clip_frame_idx = 0
        self._clip_loop = False
        self._anim_timer.stop()
        self._play_btn.setText("▶")
        self._stop_btn.setEnabled(False)

    def _animate_playhead(self):
        """Update playhead position during playback (called at ~60fps)."""
        if not self._playing:
            return
        if self._clip_data is not None:
            t = self._clip_start_time + (self._clip_frame_idx / self._sr)
            if self._clip_loop and self._clip_data is not None and self._clip_frame_idx >= len(self._clip_data):
                t = self._clip_start_time
        else:
            current_sample = self._stream_frame_idx
            t = current_sample / self._sr
        self._playhead_wave.setValue(t)
        self._playhead_spec.setValue(t)
        self._play_offset = t
        self._update_time_label(t)
        self.playbackPositionChanged.emit(t)

    def _update_time_label(self, t: float):
        def fmt(s):
            m = int(s) // 60
            sec = s - m * 60
            return f"{m}:{sec:06.3f}"
        self._time_label.setText(f"{fmt(t)} / {fmt(self._duration)}")

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Space:
            self._toggle_play()
        elif key == Qt.Key.Key_Left:
            self._prev_chunk()
        elif key == Qt.Key.Key_Right:
            self._next_chunk()
        elif key == Qt.Key.Key_Home:
            self.seek(0)
        elif key == Qt.Key.Key_End:
            self.seek(self._duration)
        elif key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal:
            self._zoom_in()
        elif key == Qt.Key.Key_Minus:
            self._zoom_out()
        elif key == Qt.Key.Key_Escape:
            self.stop()
            self.clear_regions()
        elif key == Qt.Key.Key_Delete or key == Qt.Key.Key_Backspace:
            if self.remove_selected_focus_region():
                event.accept()
                return
            if self._onset_draggable:
                self.remove_selected_onset()
                event.accept()
                return
        else:
            super().keyPressEvent(event)

    def _zoom_in(self):
        vr = self._waveform_plot.viewRange()[0]
        center = (vr[0] + vr[1]) / 2
        span = (vr[1] - vr[0]) * 0.5
        min_span = max(0.01, self._duration * 0.001) if self._duration > 0 else 0.01
        span = max(span, min_span)
        self._waveform_plot.setXRange(center - span / 2, center + span / 2,
                                       padding=0)

    def _zoom_out(self):
        vr = self._waveform_plot.viewRange()[0]
        center = (vr[0] + vr[1]) / 2
        span = (vr[1] - vr[0]) * 2.0
        max_span = self._duration * 1.1 if self._duration > 0 else span
        span = min(span, max_span)
        lo = max(0, center - span / 2)
        hi = min(self._duration, center + span / 2)
        self._waveform_plot.setXRange(lo, hi, padding=0)

    def _apply_view_limits(self):
        """Set x-axis limits to prevent zooming/panning far beyond the recording."""
        if self._duration <= 0:
            return
        margin = self._duration * 0.025
        min_span = max(0.01, self._duration * 0.001)
        max_span = self._duration * 1.1
        for pw in (self._waveform_plot, self._spec_plot):
            pw.setLimits(xMin=-margin, xMax=self._duration + margin,
                         minXRange=min_span, maxXRange=max_span)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_visible_range(self) -> Tuple[float, float]:
        """Return the currently visible time range (start, end) in seconds."""
        vr = self._waveform_plot.viewRange()[0]
        return (max(0, vr[0]), min(self._duration, vr[1]))

    def get_playhead_position(self) -> float:
        """Return the current playhead time in seconds."""
        return self._play_offset

    def scroll_to_time(self, time_sec: float, margin: float = 0.5):
        """Scroll the view so the given time is visible, with margin in seconds."""
        vr = self._waveform_plot.viewRange()[0]
        span = vr[1] - vr[0]
        if time_sec < vr[0] or time_sec > vr[1]:
            lo = max(0, time_sec - margin)
            hi = lo + span
            if hi > self._duration:
                hi = self._duration
                lo = max(0, hi - span)
            self._waveform_plot.setXRange(lo, hi, padding=0)

    def addMarker(self, time_sec: float, color=None, label: str = ""):
        """Convenience alias used by external code."""
        return self.add_onset_marker(time_sec, color=color)

    # ------------------------------------------------------------------
    # Focus region overlay API
    # ------------------------------------------------------------------

    def set_focus_mode(self, enabled: bool, polarity: str = "positive"):
        """Enable or disable focus-region drawing mode."""
        self._focus_mode = enabled
        self._focus_polarity = polarity
        self._sync_onset_line_movable_state()
        if not enabled:
            # Cancel any in-progress focus drag
            self._focus_dragging = False
            self._focus_drag_rect = None
            self.clear_focus_region_selection(emit_signal=False)

    def set_focus_polarity(self, polarity: str):
        """Set the drawing polarity to 'positive' or 'negative'."""
        self._focus_polarity = polarity

    def set_focus_regions(self, regions: list[dict]):
        """Replace all focus regions with the given list and redraw."""
        self.clear_focus_regions()
        self._focus_regions = list(regions)
        for i, region in enumerate(self._focus_regions):
            self._add_focus_rect_item(i, region)

    def set_layer_info(self, layer_names: list[str], active_layer_idx: int):
        """Update the layer names and active index for context-menu submenus."""
        self._layer_names = list(layer_names)
        self._active_layer_idx = active_layer_idx

    def clear_focus_regions(self):
        """Remove all focus region overlays from the spectrogram."""
        self.clear_focus_region_selection(emit_signal=False)
        for rect in self._focus_rect_items:
            try:
                self._spec_plot.removeItem(rect)
            except Exception:
                pass
        self._focus_rect_items.clear()
        self._focus_regions.clear()

    def _add_focus_rect_item(self, index: int, region: dict):
        """Create a pyqtgraph RectROI on the spectrogram for one focus region."""
        t_start = region["t_start"]
        t_end = region["t_end"]
        f_low = region["f_low"]
        f_high = region["f_high"]
        polarity = region.get("polarity", "positive")

        pos = (t_start, f_low)
        size = (t_end - t_start, f_high - f_low)

        border_color, fill_color, _, _ = self._focus_region_style(polarity)

        pen = pg.mkPen(color=border_color, width=2)
        brush = pg.mkBrush(color=fill_color)

        rect = _FocusRectROI(
            pos=pos, size=size,
            pen=pen,
            brush=brush,
            movable=True,
            resizable=True,
            rotatable=False,
        )
        rect.setZValue(45)
        # Remove default corner handles, add cleaner ones
        while rect.handles:
            rect.removeHandle(rect.handles[0]['item'])
        # Add 4-corner resize handles
        for handle_pos in ([0, 0], [1, 0], [0, 1], [1, 1]):
            rect.addScaleHandle(handle_pos, [1 - handle_pos[0], 1 - handle_pos[1]])

        # Store metadata on the ROI for identification
        rect._focus_index = index
        rect._focus_polarity = polarity
        self._apply_focus_rect_style(
            rect, polarity, selected=(index == self._selected_focus_region_index)
        )

        # Connect signals for when user moves/resizes the ROI
        rect.sigRegionChangeFinished.connect(
            lambda roi=rect: self._on_focus_rect_changed(roi))
        rect.sigClicked.connect(
            lambda roi, ev, item=rect: self._on_focus_rect_clicked(item, ev))

        self._spec_plot.addItem(rect)
        self._focus_rect_items.append(rect)

        # Install context menu via right-click
        rect.contextMenuEnabled = lambda: False  # disable default pg menu
        return rect

    def _on_focus_rect_changed(self, roi: pg.RectROI):
        """Handle user move/resize of a focus region ROI."""
        idx = getattr(roi, '_focus_index', -1)
        if idx < 0 or idx >= len(self._focus_regions):
            return
        pos = roi.pos()
        size = roi.size()
        t_start = pos.x()
        f_low = pos.y()
        t_end = t_start + size.x()
        f_high = f_low + size.y()
        # Ensure correct ordering
        if t_end < t_start:
            t_start, t_end = t_end, t_start
        if f_high < f_low:
            f_low, f_high = f_high, f_low
        updated = {
            "t_start": t_start, "t_end": t_end,
            "f_low": f_low, "f_high": f_high,
            "polarity": self._focus_regions[idx].get("polarity", "positive"),
        }
        self._focus_regions[idx] = updated
        self.focusRegionModified.emit(idx, updated)
        if idx == self._selected_focus_region_index:
            self.regionSelected.emit(updated["t_start"], updated["t_end"])

    def _remove_focus_region(self, index: int):
        """Remove a focus region by index."""
        if index < 0 or index >= len(self._focus_regions):
            return
        was_selected = index == self._selected_focus_region_index
        if was_selected:
            self._selected_focus_region_index = -1
        elif index < self._selected_focus_region_index:
            self._selected_focus_region_index -= 1
        # Remove the ROI item
        if index < len(self._focus_rect_items):
            rect = self._focus_rect_items.pop(index)
            try:
                self._spec_plot.removeItem(rect)
            except Exception:
                pass
        self._focus_regions.pop(index)
        # Re-index remaining ROIs
        for i, rect in enumerate(self._focus_rect_items):
            rect._focus_index = i
            self._apply_focus_rect_style(
                rect,
                getattr(rect, '_focus_polarity', 'positive'),
                selected=(i == self._selected_focus_region_index),
            )
        if was_selected:
            self.regionCleared.emit()
        self.focusRegionRemoved.emit(index)

    def _toggle_focus_region_polarity(self, index: int):
        """Toggle a focus region between positive and negative."""
        if index < 0 or index >= len(self._focus_regions):
            return
        region = self._focus_regions[index]
        new_pol = "negative" if region["polarity"] == "positive" else "positive"
        region["polarity"] = new_pol
        # Update visual
        if index < len(self._focus_rect_items):
            rect = self._focus_rect_items[index]
            rect._focus_polarity = new_pol
            self._apply_focus_rect_style(
                rect, new_pol, selected=(index == self._selected_focus_region_index)
            )
        self.focusRegionModified.emit(index, region)

    def _show_focus_context_menu(self, roi: pg.RectROI, screen_pos):
        """Show context menu for a focus region ROI."""
        idx = getattr(roi, '_focus_index', -1)
        if idx < 0:
            return
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; }}"
            f"QMenu::item:selected {{ background: {_ACCENT_DIM}; }}"
        )
        polarity = self._focus_regions[idx].get("polarity", "positive")
        toggle_label = "Switch to Negative" if polarity == "positive" else "Switch to Positive"
        toggle_action = QAction(toggle_label, menu)
        toggle_action.triggered.connect(lambda: self._toggle_focus_region_polarity(idx))
        menu.addAction(toggle_action)

        export_action = QAction("Export Region as WAV", menu)
        export_action.triggered.connect(lambda: self.focusRegionExportRequested.emit(idx))
        menu.addAction(export_action)

        # ── Move to Layer / Copy to Layer submenus ──
        if len(self._layer_names) >= 1:
            menu.addSeparator()
            move_menu = QMenu("Move to Layer", menu)
            move_menu.setStyleSheet(menu.styleSheet())
            copy_menu = QMenu("Copy to Layer", menu)
            copy_menu.setStyleSheet(menu.styleSheet())

            for li, lname in enumerate(self._layer_names):
                if li == self._active_layer_idx:
                    continue  # skip the current layer
                m_action = QAction(lname, move_menu)
                m_action.triggered.connect(
                    lambda checked=False, _li=li: self.focusRegionMoveRequested.emit(idx, _li))
                move_menu.addAction(m_action)

                c_action = QAction(lname, copy_menu)
                c_action.triggered.connect(
                    lambda checked=False, _li=li: self.focusRegionCopyRequested.emit(idx, _li))
                copy_menu.addAction(c_action)

            # Separator + Add to New Layer
            move_menu.addSeparator()
            move_new = QAction("Add to New Layer", move_menu)
            move_new.triggered.connect(
                lambda: self.focusRegionMoveRequested.emit(idx, -1))
            move_menu.addAction(move_new)

            copy_menu.addSeparator()
            copy_new = QAction("Add to New Layer", copy_menu)
            copy_new.triggered.connect(
                lambda: self.focusRegionCopyRequested.emit(idx, -1))
            copy_menu.addAction(copy_new)

            menu.addMenu(move_menu)
            menu.addMenu(copy_menu)

        menu.addSeparator()
        delete_action = QAction("Delete Region", menu)
        delete_action.triggered.connect(lambda: self._remove_focus_region(idx))
        menu.addAction(delete_action)

        menu.exec(screen_pos)

    def removeMarker(self, time_sec: float):
        """Remove the marker closest to the given time."""
        if len(self._onset_times) == 0:
            return
        idx = int(np.argmin(np.abs(self._onset_times - time_sec)))
        self.remove_onset_marker(idx)

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)


# ═══════════════════════════════════════════════════════════════════════════
# Standalone demo / test
# ═══════════════════════════════════════════════════════════════════════════

def _demo():
    """Run a standalone demo of AudioViewerWidget."""
    import sys
    from PyQt6.QtWidgets import QApplication, QFileDialog

    app = QApplication(sys.argv)

    viewer = AudioViewerWidget(
        show_waveform=True,
        show_spectrogram=True,
        show_transport=True,
        show_chunk_nav=True)
    viewer.setWindowTitle("AudioViewerWidget — Demo")
    viewer.resize(1000, 700)
    viewer.show()

    # Load a file from dialog or command-line arg
    path = None
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path, _ = QFileDialog.getOpenFileName(
            viewer, "Select Audio File", "",
            "Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)")

    if path:
        viewer.load_audio(path)

        # When loaded, add some demo onset markers
        def on_loaded(fp):
            print(f"Loaded: {fp}")
            print(f"  Duration: {viewer.duration:.2f}s")
            print(f"  Sample rate: {viewer.sampleRate}")
            # Add a few demo markers
            dur = viewer.duration
            if dur > 0.5:
                demo_times = np.linspace(0.5, min(dur - 0.1, 5.0), 5)
                viewer.set_onset_markers(demo_times, draggable=True)
                print(f"  Added {len(demo_times)} demo markers")

        viewer.audioLoaded.connect(on_loaded)

    sys.exit(app.exec())


if __name__ == "__main__":
    _demo()
