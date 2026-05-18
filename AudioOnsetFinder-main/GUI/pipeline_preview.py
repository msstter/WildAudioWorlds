from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout


@dataclass(frozen=True)
class PreviewPalette:
	accent: str
	accent_dim: str


DEFAULT_PREVIEW_PALETTE = PreviewPalette(
	accent="#4caf50",
	accent_dim="#2e7d32",
)


@dataclass(frozen=True)
class PipelinePreviewDeps:
	accent: str
	accent_dim: str
	audio_preview_step_index: int
	npvi_group_step_index: int
	step_names: Sequence[str]


def _json_safe(value: Any) -> Any:
	if isinstance(value, (np.integer,)):
		return int(value)
	if isinstance(value, (np.floating,)):
		return float(value)
	if isinstance(value, np.ndarray):
		return value.tolist()
	if isinstance(value, dict):
		return {str(key): _json_safe(val) for key, val in value.items()}
	if isinstance(value, (list, tuple)):
		return [_json_safe(item) for item in value]
	if isinstance(value, set):
		return sorted(_json_safe(item) for item in value)
	return value


def _monospace_font() -> QFont:
	family = "Menlo" if platform.system() == "Darwin" else "Consolas"
	font = QFont(family, 10)
	if not font.exactMatch() and platform.system() != "Darwin":
		font = QFont("DejaVu Sans Mono", 10)
	return font


class PreviewWindow(QDialog):
	"""Lightweight preview dialog used by tests and by the shell preview button."""

	def __init__(self, parent=None, *, palette: PreviewPalette = DEFAULT_PREVIEW_PALETTE):
		super().__init__(parent)
		self._palette = palette
		self.setWindowTitle("Preview")
		self.resize(980, 700)

		layout = QVBoxLayout(self)
		layout.setContentsMargins(12, 12, 12, 12)
		layout.setSpacing(10)

		self._header = QLabel("Preview")
		self._header.setStyleSheet(
			f"color: {self._palette.accent}; font-size: 16px; font-weight: bold;"
		)
		layout.addWidget(self._header)

		self._figure = Figure(figsize=(8, 4), tight_layout=True)
		self._canvas = FigureCanvas(self._figure)
		self._ax = self._figure.add_subplot(111)
		layout.addWidget(self._canvas, stretch=3)

		self._summary = QPlainTextEdit()
		self._summary.setReadOnly(True)
		self._summary.setFont(_monospace_font())
		self._summary.setPlaceholderText("Nothing to preview yet.")
		layout.addWidget(self._summary, stretch=2)

	def _render_mapping(self, title: str, values: dict) -> None:
		self._header.setText(title)
		self.setWindowTitle(title)
		self._summary.setPlainText(
			json.dumps(_json_safe(values), indent=2, sort_keys=True, default=str)
		)

		self._ax.clear()
		numeric_items = [
			(str(key), float(value))
			for key, value in values.items()
			if isinstance(value, (int, float)) and not isinstance(value, bool)
		]
		if numeric_items:
			labels = [item[0] for item in numeric_items[:12]]
			values_only = [item[1] for item in numeric_items[:12]]
			self._ax.bar(range(len(values_only)), values_only, color=self._palette.accent_dim)
			self._ax.set_xticks(range(len(labels)))
			self._ax.set_xticklabels(labels, rotation=35, ha="right")
			self._ax.set_ylabel("Value")
			self._ax.set_title(title)
		else:
			self._ax.text(
				0.5,
				0.5,
				"No numeric preview data available for this step.",
				ha="center",
				va="center",
				transform=self._ax.transAxes,
			)
			self._ax.set_axis_off()
		self._canvas.draw_idle()

	def render_summary(self, title: str, values: dict) -> None:
		self._render_mapping(title, values)

	def render_npvi_group(self, values: dict) -> None:
		self._render_mapping("nPVI Group Preview", values or {})


class AudioPreviewWindow(QDialog):
	"""Small dual-waveform preview used by tests and by the Audio Editor preview."""

	def __init__(
		self,
		muter_panel=None,
		parent=None,
		*,
		palette: PreviewPalette = DEFAULT_PREVIEW_PALETTE,
	):
		super().__init__(parent)
		self._palette = palette
		self.muter_panel = muter_panel
		self._y_orig = None
		self._y_proc = None
		self._y_chunk = None
		self._sr = 22050
		self._bg_cache = None
		self._active_track = None
		self._positions = {"original": 0.0, "processed": 0.0}

		self.setWindowTitle("Audio Preview")
		self.resize(1100, 720)

		root = QVBoxLayout(self)
		root.setContentsMargins(12, 12, 12, 12)
		root.setSpacing(10)

		self._figure = Figure(figsize=(9, 5), tight_layout=True)
		self.canvas = FigureCanvas(self._figure)
		self._ax1 = self._figure.add_subplot(211)
		self._ax2 = self._figure.add_subplot(212, sharex=self._ax1)
		root.addWidget(self.canvas, stretch=1)

		self._play_orig_btn = self._make_transport_button(">")
		self._loop_orig_btn = self._make_transport_button("L", checkable=True)
		self._rewind_orig_btn = self._make_transport_button("|<")
		self._play_proc_btn = self._make_transport_button(">")
		self._loop_proc_btn = self._make_transport_button("L", checkable=True)
		self._rewind_proc_btn = self._make_transport_button("|<")

		orig_row = self._build_transport_row(
			"Original",
			self._play_orig_btn,
			self._loop_orig_btn,
			self._rewind_orig_btn,
		)
		proc_row = self._build_transport_row(
			"Processed",
			self._play_proc_btn,
			self._loop_proc_btn,
			self._rewind_proc_btn,
		)
		root.addLayout(orig_row)
		root.addLayout(proc_row)

		self._loop_proc_btn.setEnabled(False)
		self._rewind_proc_btn.setEnabled(False)
		self._play_proc_btn.setEnabled(False)

		self._play_orig_btn.clicked.connect(lambda: self._toggle_play("original"))
		self._loop_orig_btn.toggled.connect(lambda checked: self._set_loop("original", checked))
		self._rewind_orig_btn.clicked.connect(lambda: self._rewind("original"))
		self._play_proc_btn.clicked.connect(lambda: self._toggle_play("processed"))
		self._loop_proc_btn.toggled.connect(lambda checked: self._set_loop("processed", checked))
		self._rewind_proc_btn.clicked.connect(lambda: self._rewind("processed"))

		self._anim_timer = QTimer(self)
		self._anim_timer.setInterval(50)
		self._anim_timer.timeout.connect(self._advance_playhead)

		self._playhead1 = self._ax1.axvline(0.0, color=self._palette.accent, linewidth=1.4, visible=False)
		self._playhead2 = self._ax2.axvline(0.0, color="#f3c14b", linewidth=1.4, visible=False)
		self._draw()

	def _make_transport_button(self, text: str, checkable: bool = False) -> QPushButton:
		button = QPushButton(text)
		button.setCheckable(checkable)
		button.setFixedSize(38, 38)
		return button

	def _build_transport_row(self, label_text: str, play_btn, loop_btn, rewind_btn):
		row = QHBoxLayout()
		row.setSpacing(8)
		label = QLabel(label_text)
		label.setFixedWidth(80)
		row.addWidget(label)
		row.addWidget(play_btn)
		row.addWidget(loop_btn)
		row.addWidget(rewind_btn)
		row.addStretch(1)
		return row

	def _track_signal(self, track: str):
		if track == "original":
			return self._y_orig
		return self._y_proc if self._y_proc is not None else self._y_chunk

	def _track_duration(self, track: str) -> float:
		signal = self._track_signal(track)
		if signal is None:
			return 0.0
		data = np.asarray(signal)
		if data.size == 0 or not self._sr:
			return 0.0
		return float(data.size) / float(self._sr)

	def _set_loop(self, _track: str, _checked: bool) -> None:
		return None

	def _toggle_play(self, track: str) -> None:
		if self._track_signal(track) is None:
			return
		if self._active_track == track and self._anim_timer.isActive():
			self._anim_timer.stop()
			self._active_track = None
			return
		self._active_track = track
		self._anim_timer.start()

	def _advance_playhead(self) -> None:
		if not self._active_track:
			return
		duration = self._track_duration(self._active_track)
		if duration <= 0:
			self._anim_timer.stop()
			self._active_track = None
			return
		self._positions[self._active_track] += self._anim_timer.interval() / 1000.0
		if self._positions[self._active_track] >= duration:
			if self._is_loop_active(self._active_track):
				self._positions[self._active_track] = 0.0
			else:
				self._positions[self._active_track] = duration
				self._anim_timer.stop()
				self._active_track = None
		if self._active_track == "original":
			self._playhead1.set_xdata([self._positions["original"], self._positions["original"]])
			self._playhead1.set_visible(True)
		else:
			self._playhead2.set_xdata([self._positions["processed"], self._positions["processed"]])
			self._playhead2.set_visible(True)
		self.canvas.draw_idle()

	def _is_loop_active(self, track: str) -> bool:
		if track == "original":
			return self._loop_orig_btn.isChecked()
		return self._loop_proc_btn.isChecked()

	def _rewind(self, track: str) -> None:
		self._positions[track] = 0.0
		if track == "original":
			self._playhead1.set_xdata([0.0, 0.0])
			self._playhead1.set_visible(True)
			self._playhead2.set_visible(False)
		else:
			self._playhead2.set_xdata([0.0, 0.0])
			self._playhead2.set_visible(True)
			self._playhead1.set_visible(False)
		self.canvas.draw_idle()

	def _draw_signal(self, axis, signal, title: str) -> None:
		axis.clear()
		axis.set_title(title)
		axis.set_ylabel("Amplitude")
		if signal is None:
			axis.text(0.5, 0.5, "No audio loaded", ha="center", va="center", transform=axis.transAxes)
			axis.set_xticks([])
			axis.set_yticks([])
			return
		data = np.asarray(signal)
		if data.size == 0:
			axis.text(0.5, 0.5, "Empty audio buffer", ha="center", va="center", transform=axis.transAxes)
			axis.set_xticks([])
			axis.set_yticks([])
			return
		xs = np.arange(data.size, dtype=float) / float(self._sr or 1)
		axis.plot(xs, data, color=self._palette.accent_dim, linewidth=0.9)
		axis.set_xlim(0, xs[-1] if xs.size else 1.0)

	def _draw(self) -> None:
		processed_signal = self._track_signal("processed")
		self._draw_signal(self._ax1, self._y_orig, "Original")
		self._draw_signal(self._ax2, processed_signal, "Processed")
		self._ax2.set_xlabel("Time (s)")

		self._playhead1 = self._ax1.axvline(0.0, color=self._palette.accent, linewidth=1.4, visible=False)
		self._playhead2 = self._ax2.axvline(0.0, color="#f3c14b", linewidth=1.4, visible=False)

		has_processed = processed_signal is not None and np.asarray(processed_signal).size > 0
		self._play_proc_btn.setEnabled(has_processed)
		self._loop_proc_btn.setEnabled(has_processed)
		self._rewind_proc_btn.setEnabled(has_processed)

		self.canvas.draw()
		QTimer.singleShot(0, self._cache_background)

	def _cache_background(self) -> None:
		try:
			self.canvas.draw()
			self._bg_cache = self.canvas.copy_from_bbox(self._figure.bbox)
		except Exception:
			self._bg_cache = object()

	def _seek_to(self, sec: float) -> None:
		sec = max(0.0, float(sec))
		self._positions["original"] = sec
		self._positions["processed"] = sec
		self._playhead1.set_xdata([sec, sec])
		self._playhead2.set_xdata([sec, sec])
		self._playhead1.set_visible(True)
		self._playhead2.set_visible(True)
		self.canvas.draw_idle()


class PipelinePreviewController:
	def __init__(self, window, deps: PipelinePreviewDeps):
		self._window = window
		self._deps = deps
		self._palette = PreviewPalette(
			accent=deps.accent,
			accent_dim=deps.accent_dim,
		)

	def toggle_preview(self) -> None:
		current_idx = self._window.panels_stack.currentIndex()
		if current_idx == self._deps.audio_preview_step_index:
			audio_preview_window = getattr(self._window, "_audio_preview_window", None)
			if audio_preview_window is not None and audio_preview_window.isVisible():
				audio_preview_window.close()
				self._window._audio_preview_window = None
			else:
				self._window._audio_preview_window = AudioPreviewWindow(
					self._window.muter_panel,
					self._window,
					palette=self._palette,
				)
				self._window._audio_preview_window.show()
				if os.environ.get("QT_QPA_PLATFORM", "").strip().lower() != "offscreen":
					self._window._audio_preview_window.raise_()
		else:
			preview_window = getattr(self._window, "_preview_window", None)
			if preview_window is not None and preview_window.isVisible():
				preview_window.close()
				self._window._preview_window = None
			else:
				self._window._preview_window = PreviewWindow(
					self._window,
					palette=self._palette,
				)
				self.refresh_preview()
				self._window._preview_window.show()
				if os.environ.get("QT_QPA_PLATFORM", "").strip().lower() != "offscreen":
					self._window._preview_window.raise_()
		self.update_preview_button_text()

	def update_preview_button_text(self) -> None:
		preview_window = getattr(self._window, "_preview_window", None)
		audio_preview_window = getattr(self._window, "_audio_preview_window", None)
		preview_open = (
			(preview_window is not None and preview_window.isVisible())
			or (audio_preview_window is not None and audio_preview_window.isVisible())
		)
		self._window.preview_btn.setText("  Close Preview  " if preview_open else "  Open Preview  ")

	def refresh_preview(self) -> None:
		self.update_preview_button_text()
		preview_window = getattr(self._window, "_preview_window", None)
		if preview_window is None or not preview_window.isVisible():
			return
		current_idx = max(0, min(self._window.panels_stack.currentIndex(), len(self._deps.step_names) - 1))
		panel = self._window.panels_stack.currentWidget()
		if current_idx == self._deps.npvi_group_step_index and hasattr(self._window.npvi_group_panel, "get_values"):
			preview_window.render_npvi_group(self._window.npvi_group_panel.get_values())
			return
		values = {}
		if hasattr(panel, "get_values"):
			try:
				values = panel.get_values()
			except Exception as exc:
				values = {"error": str(exc)}
		preview_window.render_summary(self._deps.step_names[current_idx], values)


__all__ = [
	"AudioPreviewWindow",
	"PipelinePreviewController",
	"PipelinePreviewDeps",
	"PreviewPalette",
	"PreviewWindow",
]