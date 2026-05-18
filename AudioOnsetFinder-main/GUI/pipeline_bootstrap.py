from __future__ import annotations

import os
import shutil
import sys
from typing import Callable, Sequence

from PyQt6.QtGui import QColor, QFontDatabase, QPalette
from PyQt6.QtWidgets import QApplication


GUI_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(GUI_DIR)
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "pipeline_config.json")

if PROJECT_ROOT not in sys.path:
	sys.path.insert(0, PROJECT_ROOT)
if GUI_DIR not in sys.path:
	sys.path.insert(0, GUI_DIR)


try:
	from form_widgets import (
		ExcelDataUsedDialog,
		FolderPicker,
		FormWidgetPalette,
		_ALL_DESC_LABELS,
		configure_form_widgets,
	)
except ImportError:
	from GUI.form_widgets import (
		ExcelDataUsedDialog,
		FolderPicker,
		FormWidgetPalette,
		_ALL_DESC_LABELS,
		configure_form_widgets,
	)

try:
	from panel_settings_helpers import configure_panel_settings_helpers
except ImportError:
	from GUI.panel_settings_helpers import configure_panel_settings_helpers


def _default_python() -> str:
	python_executable = sys.executable
	if python_executable.lower().endswith("pythonw.exe"):
		python_candidate = python_executable[:-len("pythonw.exe")] + "python.exe"
		if os.path.exists(python_candidate):
			python_executable = python_candidate
	candidates = [
		"/opt/anaconda3/envs/rhythm_env/bin/python",
		python_executable,
		shutil.which("python3") or "",
		shutil.which("python") or "",
	]
	for candidate in candidates:
		if candidate and os.path.exists(candidate):
			return candidate
	return python_executable


DEFAULT_PYTHON = _default_python()


def _first_existing_path(*candidates: str) -> str:
	for candidate in candidates:
		if candidate and os.path.exists(candidate):
			return candidate
	return ""


ICON_PATH = _first_existing_path(
	os.path.join(
		PROJECT_ROOT,
		"GUI",
		"Bioacoustics Rhythm Pipeline.app",
		"Contents",
		"Resources",
		"BioacousticsRhythmPipeline.icns",
	),
	os.path.join(PROJECT_ROOT, "GUI", "BioacousticsRhythmPipeline.icns"),
)


THEME = FormWidgetPalette(
	accent="#4caf50",
	accent_dim="#2e7d32",
	bg="#1e1e2e",
	bg_mid="#262636",
	bg_widget="#2c2c3c",
	bg_input="#323248",
	border="#3a3a50",
	text="#dcdcdc",
	text_desc="#a8a8c0",
	text_dim="#8888a0",
	text_muted="#6a6a82",
)


_BOOTSTRAPPED = False


def _build_application_palette() -> QPalette:
	palette = QPalette()
	window = QColor(THEME.bg)
	window_text = QColor(THEME.text)
	base = QColor(THEME.bg_input)
	alternate_base = QColor(THEME.bg_widget)
	button = QColor(THEME.bg_widget)
	highlight = QColor(THEME.accent_dim)
	highlighted_text = QColor("#ffffff")
	muted_text = QColor(THEME.text_muted)
	border = QColor(THEME.border)

	palette.setColor(QPalette.ColorRole.Window, window)
	palette.setColor(QPalette.ColorRole.WindowText, window_text)
	palette.setColor(QPalette.ColorRole.Base, base)
	palette.setColor(QPalette.ColorRole.AlternateBase, alternate_base)
	palette.setColor(QPalette.ColorRole.Text, window_text)
	palette.setColor(QPalette.ColorRole.Button, button)
	palette.setColor(QPalette.ColorRole.ButtonText, window_text)
	palette.setColor(QPalette.ColorRole.ToolTipBase, button)
	palette.setColor(QPalette.ColorRole.ToolTipText, window_text)
	palette.setColor(QPalette.ColorRole.Highlight, highlight)
	palette.setColor(QPalette.ColorRole.HighlightedText, highlighted_text)
	palette.setColor(QPalette.ColorRole.BrightText, highlighted_text)
	palette.setColor(QPalette.ColorRole.Light, alternate_base)
	palette.setColor(QPalette.ColorRole.Midlight, border)
	palette.setColor(QPalette.ColorRole.Mid, border)
	palette.setColor(QPalette.ColorRole.Dark, window)
	palette.setColor(QPalette.ColorRole.PlaceholderText, muted_text)

	for role in (
		QPalette.ColorRole.WindowText,
		QPalette.ColorRole.Text,
		QPalette.ColorRole.ButtonText,
		QPalette.ColorRole.PlaceholderText,
	):
		palette.setColor(QPalette.ColorGroup.Disabled, role, muted_text)

	palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, alternate_base)
	palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, alternate_base)
	palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Window, window)
	palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, border)
	palette.setColor(
		QPalette.ColorGroup.Disabled,
		QPalette.ColorRole.HighlightedText,
		muted_text,
	)
	return palette


def _application_stylesheet() -> str:
	return (
		f"QToolTip {{ background-color: {THEME.bg_widget}; color: {THEME.text}; "
		f"border: 1px solid {THEME.border}; padding: 4px 6px; }}"
		f"QDialog, QMessageBox {{ background-color: {THEME.bg}; color: {THEME.text}; }}"
		f"QDialog QPushButton, QMessageBox QPushButton, QDialog QToolButton {{ "
		f"background-color: {THEME.bg_widget}; color: {THEME.text}; "
		f"border: 1px solid {THEME.border}; border-radius: 5px; padding: 5px 14px; }}"
		f"QDialog QPushButton:hover, QMessageBox QPushButton:hover, QDialog QToolButton:hover {{ "
		f"background-color: {THEME.bg_input}; border-color: {THEME.accent}; color: #ffffff; }}"
		f"QDialog QPushButton:disabled, QMessageBox QPushButton:disabled, QDialog QToolButton:disabled {{ "
		f"background-color: {THEME.bg_mid}; color: {THEME.text_muted}; border-color: {THEME.border}; }}"
		f"QDialog QDialogButtonBox QPushButton {{ min-width: 88px; }}"
		f"QMenu {{ background-color: {THEME.bg_widget}; color: {THEME.text}; "
		f"border: 1px solid {THEME.border}; }}"
		f"QMenu::item {{ background-color: transparent; color: {THEME.text}; "
		f"padding: 5px 24px 5px 10px; }}"
		f"QMenu::item:selected {{ background-color: {THEME.accent_dim}; color: #ffffff; }}"
		f"QMenu::separator {{ height: 1px; background: {THEME.border}; margin: 4px 8px; }}"
		f"QComboBox QAbstractItemView, QListView, QListWidget, QTreeView, QTreeWidget {{ "
		f"background-color: {THEME.bg_input}; color: {THEME.text}; "
		f"alternate-background-color: {THEME.bg_widget}; border: 1px solid {THEME.border}; "
		f"selection-background-color: {THEME.accent_dim}; selection-color: #ffffff; }}"
		f"QTableView {{ background-color: {THEME.bg_widget}; color: {THEME.text}; "
		f"gridline-color: {THEME.border}; selection-background-color: {THEME.accent_dim}; "
		f"selection-color: #ffffff; }}"
		f"QHeaderView::section {{ background-color: {THEME.bg_mid}; color: {THEME.text}; "
		f"border: 1px solid {THEME.border}; padding: 4px; }}"
	)


def apply_qt_application_theme(app: QApplication | None = None) -> None:
	app = app or QApplication.instance()
	if app is None:
		return
	app.setPalette(_build_application_palette())
	app.setStyleSheet(_application_stylesheet())


def ensure_qt_application_font() -> None:
	app = QApplication.instance()
	if app is None:
		return
	font = app.font()
	family = (font.family() or "").strip()
	if family and family.lower() != "sans serif":
		return
	try:
		available_families = set(QFontDatabase().families())
	except Exception:
		available_families = set()
	for candidate in (
		"Helvetica",
		"Arial",
		"Segoe UI",
		"DejaVu Sans",
		"Noto Sans",
		"Liberation Sans",
	):
		if available_families and candidate not in available_families:
			continue
		font.setFamily(candidate)
		app.setFont(font)
		return


def bootstrap_pipeline_ui(*, step_settings_prefix: str, auto_set_steps: Sequence[str]) -> None:
	global _BOOTSTRAPPED
	ensure_qt_application_font()
	if _BOOTSTRAPPED:
		return
	configure_form_widgets(
		palette=THEME,
		project_root=PROJECT_ROOT,
		setting_polarity={},
		novice_descriptions={},
		friendly_names={},
		auto_set_steps=list(auto_set_steps),
	)
	configure_panel_settings_helpers(
		project_root=PROJECT_ROOT,
		step_settings_prefix=step_settings_prefix,
	)
	_BOOTSTRAPPED = True


def _noop_apply_onset_editor_desc_level(_level: int) -> None:
	return None


def set_description_level(
	level: int,
	apply_onset_editor_desc_level: Callable[[int], None] = _noop_apply_onset_editor_desc_level,
) -> None:
	for label in list(_ALL_DESC_LABELS):
		try:
			label.apply_level(level)
		except RuntimeError:
			pass
	apply_onset_editor_desc_level(min(int(level), 3))


__all__ = [
	"CONFIG_PATH",
	"DEFAULT_PYTHON",
	"ExcelDataUsedDialog",
	"FolderPicker",
	"GUI_DIR",
	"ICON_PATH",
	"PROJECT_ROOT",
	"SCRIPTS_DIR",
	"THEME",
	"bootstrap_pipeline_ui",
	"apply_qt_application_theme",
	"ensure_qt_application_font",
	"set_description_level",
]