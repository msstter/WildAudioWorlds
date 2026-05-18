from __future__ import annotations

import json
import os
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class FormWidgetPalette:
    accent: str
    accent_dim: str
    bg: str
    bg_mid: str
    bg_widget: str
    bg_input: str
    border: str
    text: str
    text_desc: str
    text_dim: str
    text_muted: str


_DEFAULT_PALETTE = FormWidgetPalette(
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

_PALETTE = _DEFAULT_PALETTE
_PROJECT_ROOT = "."
_SETTING_POLARITY: dict[str, str] = {}
_NOVICE_DESCRIPTIONS: dict[str, str] = {}
_FRIENDLY_NAMES: dict[str, tuple[str, str, str]] = {}
_AUTO_SET_STEPS = [
    "Audio Editor",
    "Onset Finder",
    "Flower Raster Plots",
    "Histogram Generator",
    "nPVI Group Plot",
    "Association Rule Learning",
]

_ALL_DESC_LABELS = []
_ALL_IO_SUMMARIES = []
_ALL_POLARITY_LABELS = []
_ALL_SETTING_LABELS = []

AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".mp4", ".m4a", ".aiff"}


def configure_form_widgets(*, palette: FormWidgetPalette, project_root: str,
                           setting_polarity: dict[str, str],
                           novice_descriptions: dict[str, str],
                           friendly_names: dict[str, tuple[str, str, str]],
                           auto_set_steps: list[str] | None = None) -> None:
    global _PALETTE, _PROJECT_ROOT, _SETTING_POLARITY
    global _NOVICE_DESCRIPTIONS, _FRIENDLY_NAMES, _AUTO_SET_STEPS
    _PALETTE = palette
    _PROJECT_ROOT = project_root
    _SETTING_POLARITY = setting_polarity
    _NOVICE_DESCRIPTIONS = novice_descriptions
    _FRIENDLY_NAMES = friendly_names
    if auto_set_steps is not None:
        _AUTO_SET_STEPS = list(auto_set_steps)


def get_form_widget_palette() -> FormWidgetPalette:
    return _PALETTE


def get_form_widget_project_root() -> str:
    return _PROJECT_ROOT


class DescriptionLabel(QLabel):
    """A small label displayed beneath a setting widget."""

    def __init__(self, brief_text, detailed_text=None, novice_text=None,
                 parent=None):
        super().__init__(parent)
        self._brief = brief_text
        self._detailed = detailed_text or brief_text
        self._novice = novice_text or brief_text
        self.setWordWrap(True)
        self.setStyleSheet(
            f"QLabel {{"
            f"  color: {_PALETTE.text_desc};"
            f"  font-size: 11px;"
            f"  background-color: transparent;"
            f"  border-left: 2px solid {_PALETTE.accent_dim};"
            f"  padding: 3px 8px 5px 10px;"
            f"  margin: 2px 0 6px 230px;"
            f"}}"
        )
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.hide()

    def apply_level(self, level):
        if level == 0:
            self.hide()
        elif level == 1:
            self.setText(self._brief)
            self.show()
        elif level == 2:
            self.setText(self._detailed)
            self.show()
        else:
            self.setText(self._novice)
            self.show()


class PresetReasonLabel(QLabel):
    """Small accent label shown below a setting when a preset is active."""

    def __init__(self, config_key, parent=None):
        super().__init__(parent)
        self._config_key = config_key
        self.setWordWrap(True)
        self.setStyleSheet(
            f"QLabel {{"
            f"  color: {_PALETTE.accent};"
            f"  font-size: 11px;"
            f"  font-style: italic;"
            f"  background-color: transparent;"
            f"  border-left: 2px solid {_PALETTE.accent};"
            f"  padding: 3px 8px 5px 10px;"
            f"  margin: 2px 0 6px 230px;"
            f"}}"
        )
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.hide()

    def show_reason(self, reason_text):
        self.setText(f"\u2731 Preset: {reason_text}")
        self.show()

    def clear_reason(self):
        self.setText("")
        self.hide()


def _add_row(layout, label_text, widget, tooltip=None, label_width=230,
             extended_desc=None, novice_desc=None):
    row = QHBoxLayout()
    row.setSpacing(12)
    lbl = QLabel(label_text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: {_PALETTE.text}; background: transparent; font-size: 13px;")
    lbl.setFixedWidth(label_width)
    _ALL_SETTING_LABELS.append((lbl, label_text, "label"))
    if tooltip:
        lbl.setToolTip(tooltip)
        widget.setToolTip(tooltip)
    row.addWidget(lbl)
    polarity = _SETTING_POLARITY.get(label_text)
    if polarity is not None:
        clr = "#4caf50" if polarity == "+" else "#f44336"
        pol = QLabel(f"({polarity})")
        pol.setStyleSheet(
            f"color: {clr}; font-weight: bold; font-size: 13px; background: transparent;")
        pol.setFixedWidth(24)
        pol.hide()
        row.addWidget(pol)
        _ALL_POLARITY_LABELS.append(pol)
    row.addWidget(widget, stretch=1)
    layout.addLayout(row)
    try:
        widget._perfile_row = row
    except AttributeError:
        pass

    if tooltip:
        nov = novice_desc or _NOVICE_DESCRIPTIONS.get(tooltip)
        desc_label = DescriptionLabel(tooltip, extended_desc or tooltip, nov)
        layout.addWidget(desc_label)
        _ALL_DESC_LABELS.append(desc_label)
    return row


def _add_checkbox(layout, checkbox, tooltip=None, extended_desc=None,
                  novice_desc=None):
    _ALL_SETTING_LABELS.append((checkbox, checkbox.text(), "checkbox"))
    if tooltip:
        checkbox.setToolTip(tooltip)
    polarity = _SETTING_POLARITY.get(checkbox.text())
    row = QHBoxLayout()
    row.setSpacing(4)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(checkbox)
    if polarity is not None:
        clr = "#4caf50" if polarity == "+" else "#f44336"
        pol = QLabel(f"({polarity})")
        pol.setStyleSheet(
            f"color: {clr}; font-weight: bold; font-size: 13px; background: transparent;")
        pol.setFixedWidth(24)
        pol.hide()
        row.addWidget(pol)
        _ALL_POLARITY_LABELS.append(pol)
    row.addStretch()
    layout.addLayout(row)
    try:
        checkbox._perfile_row = row
    except AttributeError:
        pass

    if tooltip:
        nov = novice_desc or _NOVICE_DESCRIPTIONS.get(tooltip)
        desc_label = DescriptionLabel(tooltip, extended_desc or tooltip, nov)
        layout.addWidget(desc_label)
        _ALL_DESC_LABELS.append(desc_label)


class ColorPickerEdit(QWidget):
    """Hex text field plus color swatch button."""

    def __init__(self, default="#000000", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.line_edit = QLineEdit(default)
        self.line_edit.setToolTip("Hex color code (e.g. #1f77b4) or named color")
        lay.addWidget(self.line_edit, stretch=1)
        self._swatch = QPushButton()
        self._swatch.setFixedSize(28, 28)
        self._swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        self._swatch.setToolTip("Pick a color")
        self._swatch.clicked.connect(self._open_picker)
        lay.addWidget(self._swatch)
        self._update_swatch(default)
        self.line_edit.textChanged.connect(self._update_swatch)

    def text(self):
        return self.line_edit.text()

    def setText(self, t):
        self.line_edit.setText(t)

    def setToolTip(self, t):
        self.line_edit.setToolTip(t)

    def _update_swatch(self, color_text=None):
        c = (color_text or self.line_edit.text()).strip() or "#000000"
        self._swatch.setStyleSheet(
            f"QPushButton {{ background-color: {c}; border: 1px solid {_PALETTE.border}; "
            f"border-radius: 4px; }} "
            f"QPushButton:hover {{ border-color: {_PALETTE.accent}; }}"
        )

    def _open_picker(self):
        current = QColor(self.line_edit.text().strip())
        if not current.isValid():
            current = QColor("#000000")
        chosen = QColorDialog.getColor(current, self, "Pick a Color")
        if chosen.isValid():
            self.line_edit.setText(chosen.name())


class AutoSetConfigDialog(QDialog):
    """Small dialog for configuring which path an Auto-Set derives from."""

    def __init__(self, current_config, own_step_name, own_io, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Auto-Set Configuration — {own_step_name} {own_io.title()}")
        self.setMinimumWidth(460)
        self.setStyleSheet(
            f"QDialog {{ background-color: {_PALETTE.bg}; color: {_PALETTE.text}; }}"
            f"QLabel {{ background: transparent; }}"
            f"QComboBox {{ background-color: {_PALETTE.bg_widget}; color: {_PALETTE.text}; "
            f"border: 1px solid {_PALETTE.border}; border-radius: 4px; padding: 4px 8px; }}"
            f"QLineEdit {{ background-color: {_PALETTE.bg_widget}; color: {_PALETTE.text}; "
            f"border: 1px solid {_PALETTE.border}; border-radius: 4px; padding: 4px 8px; }}"
            f"QCheckBox {{ color: {_PALETTE.text}; }}"
            f"QPushButton {{ background-color: {_PALETTE.bg_widget}; color: {_PALETTE.text}; "
            f"border: 1px solid {_PALETTE.border}; border-radius: 5px; padding: 6px 16px; }}"
            f"QPushButton:hover {{ background-color: {_PALETTE.bg_input}; border-color: {_PALETTE.accent}; }}"
        )
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        header = QLabel(
            f"Configure which path the <b>{own_io}</b> field of <b>{own_step_name}</b> is derived from.")
        header.setWordWrap(True)
        header.setStyleSheet(
            f"color: {_PALETTE.text}; font-size: 12px; padding: 4px;")
        lay.addWidget(header)

        row1 = QHBoxLayout()
        lbl1 = QLabel("Source step:")
        lbl1.setFixedWidth(130)
        self.step_combo = QComboBox()
        self.step_combo.addItems(["(this step)"] + _AUTO_SET_STEPS)
        row1.addWidget(lbl1)
        row1.addWidget(self.step_combo, stretch=1)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        lbl2 = QLabel("Source field:")
        lbl2.setFixedWidth(130)
        self.io_combo = QComboBox()
        self.io_combo.addItems(["Input", "Output"])
        row2.addWidget(lbl2)
        row2.addWidget(self.io_combo, stretch=1)
        lay.addLayout(row2)

        self.use_dirname_cb = QCheckBox(
            "Use parent directory of the source path (dirname)")
        lay.addWidget(self.use_dirname_cb)

        self.use_basename_cb = QCheckBox(
            "Insert source folder's basename into suffix (e.g. {basename}_clean)")
        lay.addWidget(self.use_basename_cb)

        row3 = QHBoxLayout()
        lbl3 = QLabel("Suffix / sub-path:")
        lbl3.setFixedWidth(130)
        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText(
            "e.g. _muted_clean  or  data/AudioData.xlsx  or  RasterPlots")
        row3.addWidget(lbl3)
        row3.addWidget(self.suffix_edit, stretch=1)
        lay.addLayout(row3)

        suffix_hint = QLabel(
            "<i>If blank, the source path is used as-is. Otherwise, the suffix is appended/joined to the source.</i>")
        suffix_hint.setWordWrap(True)
        suffix_hint.setStyleSheet(
            f"color: {_PALETTE.text_dim}; font-size: 10px; padding: 2px 8px;")
        lay.addWidget(suffix_hint)

        self.preview_label = QLabel("")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet(
            f"color: {_PALETTE.accent}; font-size: 11px; padding: 4px 8px; "
            f"border: 1px solid {_PALETTE.border}; border-radius: 4px;")
        lay.addWidget(self.preview_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("OK")
        ok_btn.setStyleSheet(
            f"QPushButton {{ background-color: {_PALETTE.accent_dim}; color: white; "
            f"border: 1px solid {_PALETTE.accent}; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {_PALETTE.accent}; }}")
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

        self._own_step = own_step_name
        cfg = current_config or {}
        src_step = cfg.get("source_step", "")
        src_io = cfg.get("source_io", "input")
        suffix = cfg.get("suffix", "")
        use_dirname = cfg.get("use_dirname", False)
        use_basename = cfg.get("use_basename", False)

        if src_step == own_step_name or src_step == "(this step)" or not src_step:
            self.step_combo.setCurrentIndex(0)
        else:
            idx = self.step_combo.findText(src_step)
            if idx >= 0:
                self.step_combo.setCurrentIndex(idx)

        self.io_combo.setCurrentText(src_io.title())
        self.suffix_edit.setText(suffix)
        self.use_dirname_cb.setChecked(use_dirname)
        self.use_basename_cb.setChecked(use_basename)

        self.step_combo.currentTextChanged.connect(self._update_preview)
        self.io_combo.currentTextChanged.connect(self._update_preview)
        self.suffix_edit.textChanged.connect(self._update_preview)
        self.use_dirname_cb.stateChanged.connect(self._update_preview)
        self.use_basename_cb.stateChanged.connect(self._update_preview)
        self._update_preview()

    def _update_preview(self):
        cfg = self.get_config()
        step = cfg["source_step"] if cfg["source_step"] != "(this step)" else self._own_step
        io_label = cfg["source_io"].title()
        parts = [f"<b>{step}</b> → {io_label}"]
        if cfg["use_dirname"]:
            parts.append("→ parent dir")
        if cfg["suffix"]:
            if cfg["use_basename"]:
                parts.append(f"/ {{basename}}{cfg['suffix']}")
            else:
                parts.append(f"/ {cfg['suffix']}")
        self.preview_label.setText("Path: " + " ".join(parts))

    def get_config(self):
        step = self.step_combo.currentText()
        return {
            "source_step": step,
            "source_io": self.io_combo.currentText().lower(),
            "suffix": self.suffix_edit.text(),
            "use_dirname": self.use_dirname_cb.isChecked(),
            "use_basename": self.use_basename_cb.isChecked(),
        }


def _make_auto_set(picker, group_layout, desc_html, checked=True,
                   step_name="", io_type="input", auto_config=None):
    cb = QCheckBox("Auto Set")
    cb.setChecked(checked)
    cb.setStyleSheet(f"QCheckBox {{ color: {_PALETTE.text_dim}; font-size: 11px; }}")
    cb.setFixedWidth(80)
    picker.layout().addWidget(cb)

    cb.auto_config = dict(auto_config) if auto_config else {
        "source_step": "(this step)",
        "source_io": "input",
        "suffix": "",
        "use_dirname": False,
        "use_basename": False,
    }
    cb._step_name = step_name
    cb._io_type = io_type

    config_btn = QPushButton("⚙")
    config_btn.setFixedSize(24, 24)
    config_btn.setToolTip("Configure Auto-Set path source")
    config_btn.setStyleSheet(
        f"QPushButton {{ background: transparent; color: {_PALETTE.text_dim}; "
        f"border: 1px solid {_PALETTE.border}; border-radius: 4px; font-size: 13px; padding: 0; }}"
        f"QPushButton:hover {{ color: {_PALETTE.accent}; border-color: {_PALETTE.accent}; }}")
    picker.layout().addWidget(config_btn)
    cb.auto_config_btn = config_btn

    desc = QLabel(desc_html)
    desc.setWordWrap(True)
    desc.setStyleSheet(
        f"color: {_PALETTE.text_dim}; font-size: 11px; font-style: italic; "
        f"background: transparent; padding: 2px 8px; margin-left: 142px;"
        f"margin-bottom: 4px;")
    group_layout.addWidget(desc)
    desc.setVisible(checked)

    def _on_toggle(state):
        on = bool(state)
        desc.setVisible(on)
        config_btn.setVisible(on)
        picker.line_edit.setReadOnly(on)
        picker._browse_btn.setEnabled(not on)
        picker.line_edit.setStyleSheet(
            f"color: {_PALETTE.text_muted};" if on else "")

    def _on_config_clicked():
        dlg = AutoSetConfigDialog(cb.auto_config, step_name, io_type,
                                  parent=picker.window())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cb.auto_config = dlg.get_config()
            _update_auto_desc(cb, desc)

    config_btn.clicked.connect(_on_config_clicked)
    cb.stateChanged.connect(_on_toggle)
    _on_toggle(cb.isChecked())
    return cb, desc


def _update_auto_desc(cb, desc):
    cfg = cb.auto_config
    step = cfg.get("source_step", "(this step)")
    if step == "(this step)":
        step = cb._step_name
    io_label = cfg.get("source_io", "input").title()
    suffix = cfg.get("suffix", "")
    use_dirname = cfg.get("use_dirname", False)
    use_basename = cfg.get("use_basename", False)

    parts = [f"↳ Auto: From <b>{step}</b> → {io_label}"]
    if use_dirname:
        parts.append("(parent dir)")
    if suffix:
        if use_basename:
            parts.append(f"/ <i>{{basename}}{suffix}</i>")
        else:
            parts.append(f"/ <i>{suffix}</i>")
    desc.setText(" ".join(parts))


def _resolve_auto_config(source_text, auto_config):
    if not source_text:
        return ""
    cfg = auto_config or {}
    base = source_text.rstrip("/\\")
    if cfg.get("use_dirname"):
        base = os.path.dirname(base)
    suffix = cfg.get("suffix", "")
    if not suffix:
        return base
    if cfg.get("use_basename"):
        basename = os.path.basename(source_text.rstrip("/\\"))
        return os.path.join(base, basename + suffix)
    return os.path.join(base, suffix)


class FolderPicker(QWidget):
    textChanged = pyqtSignal(str)

    def __init__(self, default="", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.line_edit = QLineEdit(default)
        self.line_edit.textChanged.connect(self.textChanged.emit)
        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.setFixedWidth(90)
        self._browse_btn.clicked.connect(self._browse)
        lay.addWidget(self.line_edit, stretch=1)
        lay.addWidget(self._browse_btn)

    def _browse(self):
        start = self.line_edit.text() or _PROJECT_ROOT
        path = QFileDialog.getExistingDirectory(self, "Select Folder", start)
        if path:
            self.line_edit.setText(path)

    def text(self):
        return self.line_edit.text()

    def setText(self, t):
        self.line_edit.setText(t)

    def setToolTip(self, tip):
        self.line_edit.setToolTip(tip)
        self._browse_btn.setToolTip(tip)


class ExcelDataUsedDialog(QDialog):
    """Dialog showing a 3-column table of Excel column mappings for a step."""

    def __init__(self, step_name, column_defs, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Excel Data Used — {step_name}")
        self.setMinimumSize(620, 300)
        self.setStyleSheet(
            f"QDialog {{ background-color: {_PALETTE.bg}; color: {_PALETTE.text}; }}"
            f"QTableWidget {{ background-color: {_PALETTE.bg_widget}; color: {_PALETTE.text}; "
            f"gridline-color: {_PALETTE.border}; font-size: 12px; }}"
            f"QTableWidget::item {{ padding: 4px; }}"
            f"QHeaderView::section {{ background-color: {_PALETTE.bg_mid}; color: {_PALETTE.text}; "
            f"border: 1px solid {_PALETTE.border}; padding: 4px; font-weight: bold; font-size: 12px; }}"
            f"QPushButton {{ background-color: {_PALETTE.bg_widget}; color: {_PALETTE.text}; "
            f"border: 1px solid {_PALETTE.border}; border-radius: 5px; padding: 6px 14px; font-size: 12px; }}"
            f"QPushButton:hover {{ background-color: {_PALETTE.bg_input}; border-color: {_PALETTE.accent}; }}"
        )

        self._column_defs = column_defs
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        lbl = QLabel(f"<b>{step_name}</b> — Excel columns read by this step")
        lbl.setStyleSheet(
            f"color: {_PALETTE.text}; font-size: 13px; background: transparent;")
        lay.addWidget(lbl)

        self._table = QTableWidget(len(column_defs), 3)
        self._table.setHorizontalHeaderLabels(
            ["Variable ID", "Excel Column Used", "Description"])
        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)
        header.setSectionResizeMode(2, header.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)

        for row, cd in enumerate(column_defs):
            item0 = QTableWidgetItem(cd["var_id"])
            item0.setFlags(item0.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item0.setForeground(QColor(_PALETTE.text_dim))
            self._table.setItem(row, 0, item0)

            item1 = QTableWidgetItem(cd["column"])
            self._table.setItem(row, 1, item1)

            item2 = QTableWidgetItem(cd["description"])
            item2.setFlags(item2.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item2.setForeground(QColor(_PALETTE.text_dim))
            self._table.setItem(row, 2, item2)

        lay.addWidget(self._table, stretch=1)

        btn_row = QHBoxLayout()
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        lay.addLayout(btn_row)

    def _reset(self):
        for row, cd in enumerate(self._column_defs):
            self._table.item(row, 1).setText(cd["default"])

    def get_columns(self):
        result = {}
        for row, cd in enumerate(self._column_defs):
            result[cd["var_id"]] = self._table.item(row, 1).text().strip()
        return result


class FilePicker(QWidget):
    textChanged = pyqtSignal(str)

    def __init__(self, default="", filter_str="Excel files (*.xlsx *.xls)", parent=None):
        super().__init__(parent)
        self._filter = filter_str
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.line_edit = QLineEdit(default)
        self.line_edit.textChanged.connect(self.textChanged.emit)
        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.setFixedWidth(90)
        self._browse_btn.clicked.connect(self._browse)
        lay.addWidget(self.line_edit, stretch=1)
        lay.addWidget(self._browse_btn)

    def _browse(self):
        start_dir = os.path.dirname(self.line_edit.text()) or _PROJECT_ROOT
        path, _ = QFileDialog.getOpenFileName(self, "Select File", start_dir,
                                              self._filter)
        if path:
            self.line_edit.setText(path)

    def text(self):
        return self.line_edit.text()

    def setText(self, t):
        self.line_edit.setText(t)

    def setToolTip(self, tip):
        self.line_edit.setToolTip(tip)
        self._browse_btn.setToolTip(tip)


def _list_audio_files_in_folder(folder_path: str) -> list[str]:
    folder_path = (folder_path or "").strip()
    if os.path.isfile(folder_path):
        folder_path = os.path.dirname(folder_path)
    if not os.path.isdir(folder_path):
        return []
    return sorted(
        f for f in os.listdir(folder_path)
        if os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS
    )


class _CheckableAudioFileCombo(QComboBox):
    """Combo box whose popup contains checkable audio filenames."""

    selectionChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._folder = ""
        self._files: list[str] = []
        self._pending_selection: list[str] = []
        self._skip_hide = False
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText("Select audio files")
        self.lineEdit().installEventFilter(self)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumWidth(260)

        model = QStandardItemModel(self)
        self.setModel(model)
        self.view().pressed.connect(self._on_item_pressed)
        self._refresh_display_text()

    def hidePopup(self):
        if self._skip_hide:
            return
        super().hidePopup()

    def eventFilter(self, obj, event):
        if obj is self.lineEdit() and event.type() == event.Type.MouseButtonPress:
            self.showPopup()
            return True
        return super().eventFilter(obj, event)

    def set_folder(self, folder_path: str):
        folder_path = (folder_path or "").strip()
        if os.path.isfile(folder_path):
            folder_path = os.path.dirname(folder_path)
        files = _list_audio_files_in_folder(folder_path)
        prior_selected = self.selected_files()
        requested = self._pending_selection or prior_selected

        self._folder = folder_path if os.path.isdir(folder_path) else ""
        self._files = files
        self.model().clear()
        for filename in files:
            item = QStandardItem(filename)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setData(Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
            self.model().appendRow(item)

        valid_requested = [f for f in requested if f in files]
        if valid_requested:
            self.set_selected_files(valid_requested)
        else:
            self._refresh_display_text()

    def selected_files(self) -> list[str]:
        selected = []
        for row in range(self.model().rowCount()):
            item = self.model().item(row)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected

    def set_selected_files(self, filenames):
        requested = [str(name) for name in (filenames or []) if str(name)]
        self._pending_selection = requested
        requested_set = set(requested)
        for row in range(self.model().rowCount()):
            item = self.model().item(row)
            if not item:
                continue
            state = (Qt.CheckState.Checked
                     if item.text() in requested_set
                     else Qt.CheckState.Unchecked)
            item.setCheckState(state)
        self._refresh_display_text()
        self.selectionChanged.emit(self.selected_files())

    def ensure_first_selected(self):
        if self.model().rowCount() == 0 or self.selected_files():
            return
        first = self.model().item(0)
        if first:
            first.setCheckState(Qt.CheckState.Checked)
            self._pending_selection = [first.text()]
            self._refresh_display_text()
            self.selectionChanged.emit(self.selected_files())

    def file_count(self) -> int:
        return len(self._files)

    def _on_item_pressed(self, index):
        item = self.model().itemFromIndex(index)
        if item is None:
            return
        new_state = (Qt.CheckState.Unchecked
                     if item.checkState() == Qt.CheckState.Checked
                     else Qt.CheckState.Checked)
        item.setCheckState(new_state)
        self._pending_selection = self.selected_files()
        self._refresh_display_text()
        self.selectionChanged.emit(self.selected_files())
        self._skip_hide = True
        QTimer.singleShot(0, self._clear_skip_hide)

    def _clear_skip_hide(self):
        self._skip_hide = False

    def _refresh_display_text(self):
        files = self.selected_files()
        total = self.model().rowCount()
        if total == 0:
            text = "No audio files found"
        elif not files:
            text = "No files selected"
        elif len(files) == 1:
            text = files[0]
        elif len(files) == total:
            text = f"All {total} files selected"
        else:
            text = f"{len(files)} files selected"
        self.lineEdit().setText(text)


class _CheckableLayerCombo(QComboBox):
    """Combo box whose popup contains checkable onset layer names."""

    selectionChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._folder = ""
        self._layers: list[str] = []
        self._pending_selection: list[str] = []
        self._skip_hide = False
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText("Select onset layers")
        self.lineEdit().installEventFilter(self)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumWidth(260)

        model = QStandardItemModel(self)
        self.setModel(model)
        self.view().pressed.connect(self._on_item_pressed)
        self._refresh_display_text()

    def hidePopup(self):
        if self._skip_hide:
            return
        super().hidePopup()

    def eventFilter(self, obj, event):
        if obj is self.lineEdit() and event.type() == event.Type.MouseButtonPress:
            self.showPopup()
            return True
        return super().eventFilter(obj, event)

    def set_folder(self, folder_path: str):
        folder_path = (folder_path or "").strip()
        if os.path.isfile(folder_path):
            folder_path = os.path.dirname(folder_path)
        layers = self._discover_layers(folder_path)
        prior_selected = self.selected_layers()
        requested = self._pending_selection or prior_selected

        self._folder = folder_path if os.path.isdir(folder_path) else ""
        self._layers = layers
        self.model().clear()
        for name in layers:
            item = QStandardItem(name)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setData(Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
            self.model().appendRow(item)

        valid_requested = [name for name in requested if name in layers]
        if valid_requested:
            self.set_selected_layers(valid_requested)
        else:
            self._refresh_display_text()

    def selected_layers(self) -> list[str]:
        selected = []
        for row in range(self.model().rowCount()):
            item = self.model().item(row)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected

    def set_selected_layers(self, names):
        requested = [str(name) for name in (names or []) if str(name)]
        self._pending_selection = requested
        requested_set = set(requested)
        for row in range(self.model().rowCount()):
            item = self.model().item(row)
            if not item:
                continue
            state = (Qt.CheckState.Checked
                     if item.text() in requested_set
                     else Qt.CheckState.Unchecked)
            item.setCheckState(state)
        self._refresh_display_text()
        self.selectionChanged.emit(self.selected_layers())

    def ensure_first_selected(self):
        if self.model().rowCount() == 0 or self.selected_layers():
            return
        first = self.model().item(0)
        if first:
            first.setCheckState(Qt.CheckState.Checked)
            self._pending_selection = [first.text()]
            self._refresh_display_text()
            self.selectionChanged.emit(self.selected_layers())

    def layer_count(self) -> int:
        return len(self._layers)

    def _on_item_pressed(self, index):
        item = self.model().itemFromIndex(index)
        if item is None:
            return
        new_state = (Qt.CheckState.Unchecked
                     if item.checkState() == Qt.CheckState.Checked
                     else Qt.CheckState.Checked)
        item.setCheckState(new_state)
        self._pending_selection = self.selected_layers()
        self._refresh_display_text()
        self.selectionChanged.emit(self.selected_layers())
        self._skip_hide = True
        QTimer.singleShot(0, self._clear_skip_hide)

    def _clear_skip_hide(self):
        self._skip_hide = False

    def _refresh_display_text(self):
        layers = self.selected_layers()
        total = self.model().rowCount()
        if total == 0:
            text = "No saved layers found"
        elif not layers:
            text = "No layers selected"
        elif len(layers) == 1:
            text = layers[0]
        elif len(layers) == total:
            text = f"All {total} layers selected"
        else:
            text = f"{len(layers)} layers selected"
        self.lineEdit().setText(text)

    @staticmethod
    def _discover_layers(folder_path: str) -> list[str]:
        if not os.path.isdir(folder_path):
            return []
        layer_names: set[str] = set()
        try:
            entries = os.listdir(folder_path)
        except OSError:
            return []
        for entry in entries:
            entry_path = os.path.join(folder_path, entry)
            if not (os.path.isdir(entry_path) and entry.endswith("_OnsetLayers")):
                continue
            try:
                jsons = [filename for filename in os.listdir(entry_path) if filename.endswith(".json")]
            except OSError:
                continue
            for filename in jsons:
                try:
                    with open(os.path.join(entry_path, filename), encoding="utf-8") as handle:
                        data = json.load(handle)
                    if isinstance(data, dict) and "name" in data:
                        layer_names.add(data["name"])
                except (json.JSONDecodeError, OSError, ValueError):
                    pass
        return sorted(layer_names)
