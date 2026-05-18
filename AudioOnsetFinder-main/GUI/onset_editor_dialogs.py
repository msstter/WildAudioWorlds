"""Standalone dialog classes used by the onset editor workbench."""

from __future__ import annotations

import os
import platform
import sys
from collections import OrderedDict

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
)

try:
    from onset_editor_io import _HOTKEY_DEFS, _HAS_EXCEL_IO, _eio
except ImportError:
    from GUI.onset_editor_io import _HOTKEY_DEFS, _HAS_EXCEL_IO, _eio


def _monospace_css_family() -> str:
    system = platform.system()
    if system == "Darwin":
        return "Menlo"
    if system == "Windows":
        return "Consolas"
    return "DejaVu Sans Mono"


_ACCENT = "#4caf50"
_BG = "#1e1e2e"
_BG_MID = "#262636"
_BG_WIDGET = "#2c2c3c"
_BG_INPUT = "#323248"
_BORDER = "#3a3a50"
_TEXT = "#dcdcdc"
_TEXT_DIM = "#8888a0"
_TEXT_MUTED = "#6a6a82"


def _fallback_detect_recommendations(profile: dict | None, result: dict | None) -> str:
    """Return a compact recommendation summary when the richer formatter is unavailable."""
    lines = ["Derived From Focus Signals", "=" * 28]

    if profile:
        summary = profile.get("summary", {}) or {}
        negative_summary = profile.get("negative_summary", {}) or {}
        if summary:
            lines.append(f"Positive regions: {summary.get('n_regions', 0)}")
        if negative_summary:
            lines.append(f"Negative regions: {negative_summary.get('n_regions', 0)}")

    if not result:
        lines.append("")
        lines.append("No analyzer recommendations are available for this file yet.")
        return "\n".join(lines)

    analysis = result.get("analysis", {}) or {}
    if analysis:
        lines.append("")
        lines.append("Analysis")
        lines.append(
            f"  Best method: {analysis.get('best_method', result.get('settings', {}).get('ONSET_METHOD', '?'))}"
        )
        if "best_delta" in analysis:
            lines.append(f"  Best delta: {analysis.get('best_delta', 0):.2f}")

    lines.append("")
    lines.append("Recommended settings")
    for key, value in (result.get("settings", {}) or {}).items():
        lines.append(f"  {key}: {value}")

    return "\n".join(lines)


class _OnsetEditorSettingsDialog(QDialog):
    """Settings dialog with hitbox size and editable hotkeys."""

    def __init__(self, current_hitbox_px: int, hotkey_map: dict[str, str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Onset Editor Settings")
        self.setMinimumWidth(420)
        self.setStyleSheet(
            f"QDialog {{ background: {_BG_MID}; color: {_TEXT}; }}"
            f"QLabel {{ color: {_TEXT}; font-size: 13px; }}"
            f"QSpinBox {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 4px 8px; font-size: 13px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        hitbox_group = QGroupBox("Onset Click Detection")
        hitbox_group.setStyleSheet(
            f"QGroupBox {{ color: {_TEXT}; font-weight: bold; font-size: 13px; "
            f"border: 1px solid {_BORDER}; border-radius: 6px; "
            f"margin-top: 8px; padding: 12px 10px 10px 10px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; "
            f"padding: 0 4px; }}"
        )
        hb_layout = QVBoxLayout(hitbox_group)

        desc = QLabel(
            "Controls how close (in pixels) you must click to an onset line "
            "to select or drag it. Lower values require more precise clicks."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        hb_layout.addWidget(desc)

        spin_row = QHBoxLayout()
        spin_row.addWidget(QLabel("Onset Hitbox Size (px):"))
        self._hitbox_spin = QSpinBox()
        self._hitbox_spin.setRange(1, 50)
        self._hitbox_spin.setValue(current_hitbox_px)
        self._hitbox_spin.setToolTip("Pixel distance threshold for clicking on onset lines")
        spin_row.addWidget(self._hitbox_spin)
        spin_row.addStretch()
        hb_layout.addLayout(spin_row)

        layout.addWidget(hitbox_group)

        hotkey_group = QGroupBox("Keyboard Shortcuts")
        hotkey_group.setStyleSheet(
            f"QGroupBox {{ color: {_TEXT}; font-weight: bold; font-size: 13px; "
            f"border: 1px solid {_BORDER}; border-radius: 6px; "
            f"margin-top: 8px; padding: 12px 10px 10px 10px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; "
            f"padding: 0 4px; }}"
        )
        hk_layout = QVBoxLayout(hotkey_group)

        hk_desc = QLabel(
            "Click a key box to change its shortcut. "
            "Viewer keys (greyed out) are not editable."
        )
        hk_desc.setWordWrap(True)
        hk_desc.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        hk_layout.addWidget(hk_desc)

        section_style = (
            f"color: {_TEXT_DIM}; font-size: 11px; font-weight: bold; "
            f"margin-top: 4px;"
        )
        desc_style = f"color: {_TEXT}; font-size: 12px;"
        ro_key_style = (
            f"color: {_TEXT_MUTED}; font-family: '{_monospace_css_family()}'; font-size: 12px; "
            f"background: {_BG_WIDGET}; "
            f"border: 1px solid {_BORDER}; border-radius: 3px; padding: 2px 6px;"
        )
        edit_style = (
            f"QKeySequenceEdit {{ "
            f"  color: {_ACCENT}; font-family: '{_monospace_css_family()}'; font-size: 12px; "
            f"  font-weight: bold; background: {_BG_WIDGET}; "
            f"  border: 1px solid {_BORDER}; border-radius: 3px; "
            f"  padding: 2px 6px; "
            f"}} "
            f"QKeySequenceEdit:focus {{ border-color: {_ACCENT}; }}"
        )

        self._hotkey_edits: dict[str, QKeySequenceEdit] = {}

        categories: OrderedDict[str, list] = OrderedDict()
        for action_id, _default_key, desc_text, cat in _HOTKEY_DEFS:
            categories.setdefault(cat, []).append((action_id, desc_text))

        cat_labels = {
            "General": "General",
            "Tools": "Tools",
            "Layers": "Layers",
            "Navigation": "Navigation",
            "viewer": "Viewer  (read-only)",
        }

        for cat, entries in categories.items():
            sec_label = QLabel(cat_labels.get(cat, cat))
            sec_label.setStyleSheet(section_style)
            hk_layout.addWidget(sec_label)

            is_viewer = cat == "viewer"
            for action_id, desc_text in entries:
                row = QHBoxLayout()
                row.setSpacing(8)

                current_key = hotkey_map.get(action_id, "")

                if is_viewer:
                    key_label = QLabel(current_key)
                    key_label.setStyleSheet(ro_key_style)
                    key_label.setFixedWidth(160)
                    key_label.setFixedHeight(26)
                    row.addWidget(key_label)
                else:
                    key_edit = QKeySequenceEdit(QKeySequence(current_key))
                    key_edit.setStyleSheet(edit_style)
                    key_edit.setFixedWidth(160)
                    key_edit.setFixedHeight(26)
                    key_edit.setToolTip(f"Click to change shortcut for: {desc_text}")
                    self._hotkey_edits[action_id] = key_edit
                    row.addWidget(key_edit)

                desc_label = QLabel(desc_text)
                desc_label.setStyleSheet(desc_style)
                row.addWidget(desc_label)
                row.addStretch()
                hk_layout.addLayout(row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(hotkey_group)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {_BG_MID}; }}")
        scroll.setMinimumHeight(200)
        layout.addWidget(scroll, stretch=1)

        reset_btn = QPushButton("Reset Hotkeys to Defaults")
        reset_btn.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT_DIM}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 4px 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; color: {_TEXT}; }}"
        )
        reset_btn.clicked.connect(self._reset_hotkeys)
        layout.addWidget(reset_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 6px 18px; font-size: 13px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; color: white; }}"
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _reset_hotkeys(self):
        defaults = {action_id: key for action_id, key, _desc, _cat in _HOTKEY_DEFS}
        for action_id, key_edit in self._hotkey_edits.items():
            key_edit.setKeySequence(QKeySequence(defaults.get(action_id, "")))

    def hitbox_px(self) -> int:
        return self._hitbox_spin.value()

    def hotkey_map(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for action_id, key_edit in self._hotkey_edits.items():
            result[action_id] = key_edit.keySequence().toString()
        return result


class _ExcelColumnDialog(QDialog):
    """Dialog to select which columns in an Excel/CSV contain filename and onset data."""

    def __init__(
        self,
        file_path: str,
        *,
        initial_filename_col: str = "File Name",
        initial_onset_col: str = "Exact Onset Times Used (s)",
        initial_sheet: str | int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Select Excel Columns")
        self.setMinimumWidth(480)
        self.setStyleSheet(
            f"QDialog {{ background: {_BG}; color: {_TEXT}; }}"
            f"QLabel {{ color: {_TEXT}; background: transparent; }}"
            f"QComboBox {{ background: {_BG_INPUT}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 4px 8px; }}"
            f"QGroupBox {{ background: {_BG_MID}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 6px; "
            f"margin-top: 14px; padding: 16px 10px 10px 10px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 12px; "
            f"padding: 0 6px; color: {_ACCENT}; }}"
        )
        self._file_path = file_path
        self._columns: list[str] = []
        self._sheets: list[str] = []

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        file_lbl = QLabel(f"<b>File:</b> {os.path.basename(file_path)}")
        file_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        lay.addWidget(file_lbl)

        ext = os.path.splitext(file_path)[1].lower()
        if ext != ".csv" and _HAS_EXCEL_IO:
            try:
                self._sheets = _eio.get_sheet_names(file_path)
            except Exception:
                self._sheets = ["File Summaries"]
            if len(self._sheets) > 1:
                grp_sheet = QGroupBox("Sheet")
                g_sheet = QVBoxLayout(grp_sheet)
                self._sheet_combo = QComboBox()
                self._sheet_combo.addItems(self._sheets)
                if isinstance(initial_sheet, str) and initial_sheet in self._sheets:
                    self._sheet_combo.setCurrentText(initial_sheet)
                elif isinstance(initial_sheet, int) and initial_sheet < len(self._sheets):
                    self._sheet_combo.setCurrentIndex(initial_sheet)
                self._sheet_combo.currentTextChanged.connect(self._on_sheet_changed)
                g_sheet.addWidget(self._sheet_combo)
                lay.addWidget(grp_sheet)
            else:
                self._sheet_combo = None
        else:
            self._sheet_combo = None
            self._sheets = ["Sheet1"]

        grp = QGroupBox("Column Mapping")
        g = QVBoxLayout(grp)

        g.addWidget(QLabel("Which column contains the <b>audio filenames</b>?"))
        self._filename_combo = QComboBox()
        g.addWidget(self._filename_combo)

        g.addSpacing(8)
        g.addWidget(QLabel("Which column contains the <b>onset times</b>?"))
        self._onset_combo = QComboBox()
        g.addWidget(self._onset_combo)

        self._preview_label = QLabel("")
        self._preview_label.setWordWrap(True)
        self._preview_label.setStyleSheet(
            f"color: {_TEXT_DIM}; font-size: 11px; font-style: italic; "
            f"padding: 6px; border: 1px solid {_BORDER}; border-radius: 4px;"
        )
        g.addWidget(self._preview_label)

        lay.addWidget(grp)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 5px 20px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        lay.addWidget(btn_box)

        self._load_columns(initial_filename_col, initial_onset_col)
        self._onset_combo.currentTextChanged.connect(self._update_preview)
        self._filename_combo.currentTextChanged.connect(self._update_preview)
        self._update_preview()

    def _load_columns(self, initial_filename_col: str, initial_onset_col: str):
        if not _HAS_EXCEL_IO:
            return
        sheet = self.sheet_name()
        try:
            self._columns = _eio.get_columns(self._file_path, sheet)
        except Exception as exc:
            self._columns = []
            self._preview_label.setText(f"Error reading columns: {exc}")
            return

        self._filename_combo.blockSignals(True)
        self._onset_combo.blockSignals(True)
        self._filename_combo.clear()
        self._onset_combo.clear()
        self._filename_combo.addItems(self._columns)
        self._onset_combo.addItems(self._columns)

        if initial_filename_col in self._columns:
            self._filename_combo.setCurrentText(initial_filename_col)
        else:
            for column in self._columns:
                if "file" in column.lower() and "name" in column.lower():
                    self._filename_combo.setCurrentText(column)
                    break

        if initial_onset_col in self._columns:
            self._onset_combo.setCurrentText(initial_onset_col)
        else:
            for column in self._columns:
                if "onset" in column.lower() and "time" in column.lower():
                    self._onset_combo.setCurrentText(column)
                    break

        self._filename_combo.blockSignals(False)
        self._onset_combo.blockSignals(False)

    def _on_sheet_changed(self, sheet_name: str):
        self._load_columns("File Name", "Exact Onset Times Used (s)")
        self._update_preview()

    def _update_preview(self):
        if not _HAS_EXCEL_IO or not self._columns:
            return
        try:
            import pandas as pd

            sheet = self.sheet_name()
            ext = os.path.splitext(self._file_path)[1].lower()
            if ext == ".csv":
                df = pd.read_csv(self._file_path, nrows=3)
            else:
                df = pd.read_excel(self._file_path, sheet_name=sheet, nrows=3, engine="openpyxl")

            fn_col = self._filename_combo.currentText()
            on_col = self._onset_combo.currentText()
            lines = []
            if fn_col in df.columns and on_col in df.columns:
                for _, row in df.iterrows():
                    fname = str(row.get(fn_col, ""))[:30]
                    onsets_raw = str(row.get(on_col, ""))[:60]
                    parsed = _eio.parse_onset_string(onsets_raw)
                    lines.append(f"  {fname} → {len(parsed)} onsets")
                self._preview_label.setText(
                    f"Preview (first {len(lines)} rows):\n" + "\n".join(lines)
                )
            else:
                self._preview_label.setText("Select valid columns")
        except Exception as exc:
            self._preview_label.setText(f"Preview error: {exc}")

    def sheet_name(self) -> str | int:
        if self._sheet_combo is not None:
            return self._sheet_combo.currentText()
        return self._sheets[0] if self._sheets else 0

    def filename_column(self) -> str:
        return self._filename_combo.currentText()

    def onset_column(self) -> str:
        return self._onset_combo.currentText()


class _ExcelSaveDialog(QDialog):
    """Dialog for saving onsets to Excel with overwrite protection and new-column options."""

    def __init__(
        self,
        *,
        excel_path: str,
        audio_filename: str,
        onset_col: str,
        onset_times: list[float],
        filename_col: str,
        sheet_name: str | int,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Save Onsets to Excel")
        self.setMinimumWidth(560)
        self.setStyleSheet(
            f"QDialog {{ background: {_BG}; color: {_TEXT}; }}"
            f"QLabel {{ color: {_TEXT}; background: transparent; }}"
            f"QGroupBox {{ background: {_BG_MID}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 6px; "
            f"margin-top: 14px; padding: 16px 10px 10px 10px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 12px; "
            f"padding: 0 6px; color: {_ACCENT}; }}"
            f"QLineEdit {{ background: {_BG_INPUT}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 4px 8px; }}"
            f"QCheckBox {{ color: {_TEXT}; }}"
        )

        self._excel_path = excel_path
        self._audio_filename = audio_filename
        self._onset_col = onset_col
        self._onset_times = onset_times
        self._filename_col = filename_col
        self._sheet_name = sheet_name
        self._output_path = excel_path

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        info = QLabel(
            f"<b>Excel:</b> {os.path.basename(excel_path)}<br>"
            f"<b>Audio:</b> {audio_filename}<br>"
            f"<b>Onsets:</b> {len(onset_times)}"
        )
        info.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        lay.addWidget(info)

        grp_target = QGroupBox("Save Target")
        g_target = QVBoxLayout(grp_target)

        self._overwrite_rb = QCheckBox("Update original Excel file")
        self._overwrite_rb.setChecked(True)
        self._overwrite_rb.toggled.connect(self._on_target_toggled)
        g_target.addWidget(self._overwrite_rb)

        dup_row = QHBoxLayout()
        self._duplicate_rb = QCheckBox("Save to new file:")
        self._duplicate_rb.toggled.connect(self._on_target_toggled)
        dup_row.addWidget(self._duplicate_rb)
        self._dup_path_edit = QLineEdit()
        self._dup_path_edit.setEnabled(False)
        stem = os.path.splitext(excel_path)[0]
        ext = os.path.splitext(excel_path)[1]
        self._dup_path_edit.setText(f"{stem}_edited{ext}")
        dup_row.addWidget(self._dup_path_edit, stretch=1)
        self._dup_browse_btn = QPushButton("Browse…")
        self._dup_browse_btn.setEnabled(False)
        self._dup_browse_btn.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 3px 10px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
        )
        self._dup_browse_btn.clicked.connect(self._browse_dup_path)
        dup_row.addWidget(self._dup_browse_btn)
        g_target.addLayout(dup_row)

        lay.addWidget(grp_target)

        grp_col = QGroupBox("Column Settings")
        g_col = QVBoxLayout(grp_col)

        self._new_col_cb = QCheckBox("Save onsets in a new column")
        self._new_col_cb.setToolTip(
            "Instead of overwriting the original onset column, save to a new column with a custom name."
        )
        self._new_col_cb.toggled.connect(self._on_new_col_toggled)
        g_col.addWidget(self._new_col_cb)

        col_name_row = QHBoxLayout()
        col_name_row.addWidget(QLabel("New column name:"))
        self._new_col_edit = QLineEdit()
        self._new_col_edit.setText(f"{onset_col}_OnsetEdits")
        self._new_col_edit.setEnabled(False)
        col_name_row.addWidget(self._new_col_edit, stretch=1)
        g_col.addLayout(col_name_row)

        self._overwrite_warning = QLabel("")
        self._overwrite_warning.setWordWrap(True)
        self._overwrite_warning.setStyleSheet(
            "color: #ff9800; font-size: 11px; padding: 6px; "
            "border: 1px solid #ff9800; border-radius: 4px;"
        )
        self._overwrite_warning.hide()
        g_col.addWidget(self._overwrite_warning)

        lay.addWidget(grp_col)

        self._check_overwrite_warning()

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 5px 20px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        lay.addWidget(btn_box)

    def _on_target_toggled(self, checked: bool):
        sender = self.sender()
        if sender is self._overwrite_rb and checked:
            self._duplicate_rb.setChecked(False)
            self._dup_path_edit.setEnabled(False)
            self._dup_browse_btn.setEnabled(False)
        elif sender is self._duplicate_rb and checked:
            self._overwrite_rb.setChecked(False)
            self._dup_path_edit.setEnabled(True)
            self._dup_browse_btn.setEnabled(True)
        elif sender is self._duplicate_rb and not checked:
            self._overwrite_rb.setChecked(True)
        elif sender is self._overwrite_rb and not checked:
            self._duplicate_rb.setChecked(True)
        self._check_overwrite_warning()

    def _on_new_col_toggled(self, checked: bool):
        self._new_col_edit.setEnabled(checked)
        self._check_overwrite_warning()

    def _browse_dup_path(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Excel As",
            self._dup_path_edit.text(),
            "Excel Files (*.xlsx);;CSV Files (*.csv)",
        )
        if path:
            self._dup_path_edit.setText(path)

    def _check_overwrite_warning(self):
        if not _HAS_EXCEL_IO or not os.path.isfile(self._excel_path):
            self._overwrite_warning.hide()
            return

        target_col = self.target_column()
        try:
            import pandas as pd

            ext = os.path.splitext(self._excel_path)[1].lower()
            if ext == ".csv":
                df = pd.read_csv(self._excel_path)
            else:
                df = pd.read_excel(self._excel_path, sheet_name=self._sheet_name, engine="openpyxl")

            if target_col in df.columns:
                mask = df[self._filename_col].astype(str).str.strip().str.lower() == self._audio_filename.strip().lower()
                matches = df.loc[mask, target_col]
                if not matches.empty:
                    old_val = matches.iloc[0]
                    if not pd.isna(old_val) and str(old_val).strip():
                        old_str = str(old_val)
                        if len(old_str) > 80:
                            old_str = old_str[:80] + "..."
                        self._overwrite_warning.setText(
                            f"Warning: {target_col} already contains data for this file:\n{old_str}"
                        )
                        self._overwrite_warning.show()
                        return
        except Exception:
            pass
        self._overwrite_warning.hide()

    def _on_accept(self):
        if self._duplicate_rb.isChecked():
            self._output_path = self._dup_path_edit.text().strip()
            if not self._output_path:
                return
        else:
            self._output_path = self._excel_path
        self.accept()

    def output_path(self) -> str:
        return self._output_path

    def target_column(self) -> str:
        if self._new_col_cb.isChecked():
            return self._new_col_edit.text().strip() or self._onset_col
        return self._onset_col

    def create_new_column(self) -> bool:
        return self._new_col_cb.isChecked()


class _AnalyzeSignalsDialog(QDialog):
    """Dialog for analyzing focus signals and reviewing derived settings."""

    def __init__(
        self,
        *,
        parent=None,
        recommendation_result: dict | None = None,
        signal_profile: dict | None = None,
        apply_callback=None,
        analyze_callback=None,
        format_recommendations=None,
    ):
        super().__init__(parent)
        self._recommendation_result = recommendation_result or {}
        self._signal_profile = signal_profile
        self._apply_callback = apply_callback
        self._analyze_callback = analyze_callback
        self._format_recommendations = format_recommendations or _fallback_detect_recommendations
        self._cluster_result: dict | None = None
        self.setWindowTitle("Analyze Selected Signals")
        self.setMinimumWidth(580)
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

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        info = QLabel("<b>Analyze Selected +/- Signals</b>")
        info.setWordWrap(True)
        layout.addWidget(info)

        intro_desc = QLabel(
            "<i>Use this to run spectral analysis on the current positive and negative "
            "focus regions. The analysis generates recommended onset detection settings "
            "based on the spectral characteristics of your selected signals.</i>"
        )
        intro_desc.setWordWrap(True)
        intro_desc.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        layout.addWidget(intro_desc)

        self._analyze_btn = QPushButton("Analyze Selected +/- Signals")
        self._analyze_btn.setToolTip(
            "Run spectral analysis on the current positive/negative focus regions.\n"
            "This populates the Recommended settings below."
        )
        self._analyze_btn.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_ACCENT}; "
            f"border: 1px solid {_ACCENT}; border-radius: 4px; padding: 6px 16px; }}"
            f"QPushButton:hover {{ background: {_BG_MID}; }}"
        )
        self._analyze_btn.setEnabled(self._analyze_callback is not None)
        self._analyze_btn.clicked.connect(self._run_analysis)
        layout.addWidget(self._analyze_btn)

        self._auto_layers_cb = QCheckBox("Add Onset Layer Detection")
        self._auto_layers_cb.setToolTip(
            "When checked, the analysis will also cluster positive signals\n"
            "by spectral similarity and suggest separate onset layers."
        )
        self._auto_layers_cb.setChecked(False)
        layout.addWidget(self._auto_layers_cb)

        self._recommended_toggle = QPushButton("▶ Recommended From Focus Signals")
        self._recommended_toggle.setFlat(True)
        self._recommended_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._recommended_toggle.setStyleSheet(
            f"QPushButton {{ color: {_ACCENT}; font-size: 12px; "
            f"text-align: left; padding: 4px 0; background: transparent; }}"
            f"QPushButton:hover {{ color: white; }}"
        )
        self._recommended_toggle.clicked.connect(self._toggle_recommended)
        layout.addWidget(self._recommended_toggle)

        self._recommended_frame = QFrame()
        self._recommended_frame.setStyleSheet(
            f"QFrame {{ background: {_BG_MID}; border: 1px solid {_BORDER}; "
            f"border-radius: 6px; }}"
        )
        self._recommended_frame.setVisible(bool(self._recommendation_result))
        rec_layout = QVBoxLayout(self._recommended_frame)
        rec_layout.setContentsMargins(10, 8, 10, 8)
        rec_layout.setSpacing(6)

        rec_desc = QLabel(
            "<i>This section shows how the current positive/negative focus signals "
            "influenced the onset settings, then lets you use or override those values.</i>"
        )
        rec_desc.setWordWrap(True)
        rec_desc.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px; background: transparent;")
        rec_layout.addWidget(rec_desc)

        self._recommended_text = QPlainTextEdit()
        self._recommended_text.setReadOnly(True)
        self._recommended_text.setMinimumHeight(220)
        self._recommended_text.setStyleSheet(
            f"QPlainTextEdit {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 6px; }}"
        )
        self._recommended_text.setPlainText(
            self._format_recommendations(self._signal_profile, self._recommendation_result)
            if self._recommendation_result
            else "(Click 'Analyze Selected +/- Signals' above to populate recommendations.)"
        )
        rec_layout.addWidget(self._recommended_text)

        rec_btns = QHBoxLayout()
        rec_btns.setSpacing(6)
        self._apply_pipeline_btn = QPushButton("Apply to Onset Finder")
        self._apply_pipeline_btn.setEnabled(bool(self._recommendation_result))
        self._apply_pipeline_btn.setToolTip(
            "Copy these recommended settings to the main Onset Finder pipeline panel."
        )
        self._apply_pipeline_btn.clicked.connect(self._apply_to_onset_finder)
        self._apply_pipeline_btn.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 4px 12px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
        )
        rec_btns.addWidget(self._apply_pipeline_btn)
        rec_btns.addStretch()
        rec_layout.addLayout(rec_btns)

        layout.addWidget(self._recommended_frame)
        self._recommended_toggle.setText(
            "▼ Recommended From Focus Signals" if self._recommended_frame.isVisible()
            else "▶ Recommended From Focus Signals"
        )

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        btns.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 5px 14px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
        )
        layout.addWidget(btns)

    def _toggle_recommended(self):
        visible = not self._recommended_frame.isVisible()
        self._recommended_frame.setVisible(visible)
        self._recommended_toggle.setText(
            "▼ Recommended From Focus Signals" if visible else "▶ Recommended From Focus Signals"
        )
        self.adjustSize()

    def _run_analysis(self):
        if not self._analyze_callback:
            return
        self._analyze_btn.setEnabled(False)
        self._analyze_btn.setText("Analyzing...")
        QApplication.processEvents()
        try:
            profile, result = self._analyze_callback()
            self._signal_profile = profile
            self._recommendation_result = result or {}

            self._cluster_result = None
            if self._auto_layers_cb.isChecked() and profile:
                pos_regions = profile.get("regions") or []
                if len(pos_regions) >= 2:
                    try:
                        from analysis.signal_profiles import cluster_signal_regions
                    except ImportError:
                        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        if project_root not in sys.path:
                            sys.path.insert(0, project_root)
                        from analysis.signal_profiles import cluster_signal_regions
                    try:
                        self._cluster_result = cluster_signal_regions(pos_regions)
                    except Exception:
                        pass

            text = self._format_recommendations(profile, result)
            if self._cluster_result and self._cluster_result["n_clusters"] > 1:
                text += "\n\n"
                text += "Onset Layer Detection\n"
                text += "=" * 22 + "\n"
                cluster_result = self._cluster_result
                text += f"Suggested layers: {cluster_result['n_clusters']}\n"
                for description in cluster_result["descriptions"]:
                    text += f"  {description}\n"
                text += "\nClose this dialog to auto-create these layers."
            elif self._auto_layers_cb.isChecked():
                text += "\n\n"
                text += "Onset Layer Detection\n"
                text += "=" * 22 + "\n"
                n_pos = len((profile or {}).get("regions") or [])
                if n_pos < 2:
                    text += "Need at least 2 positive regions to cluster.\n"
                else:
                    text += "All positive regions are spectrally similar - 1 layer is sufficient.\n"

            self._recommended_text.setPlainText(text)
            self._apply_pipeline_btn.setEnabled(bool(result))
            self._recommended_frame.setVisible(True)
            self._recommended_toggle.setText("▼ Recommended From Focus Signals")
        finally:
            self._analyze_btn.setText("Analyze Selected +/- Signals")
            self._analyze_btn.setEnabled(True)

    def _apply_to_onset_finder(self):
        if not callable(self._apply_callback):
            QMessageBox.information(
                self,
                "Unavailable",
                "This window is not connected to the main Onset Finder panel.",
            )
            return
        settings = self._recommendation_result.get("settings", {})
        if not settings:
            QMessageBox.information(
                self,
                "No Recommendations",
                "Run the analysis first to generate recommended settings.",
            )
            return
        self._apply_callback(settings)

    def layer_cluster_result(self) -> dict | None:
        return self._cluster_result

    def recommendation_result(self) -> dict:
        return self._recommendation_result

    def signal_profile(self) -> dict | None:
        return self._signal_profile


__all__ = [
    "_AnalyzeSignalsDialog",
    "_ExcelColumnDialog",
    "_ExcelSaveDialog",
    "_OnsetEditorSettingsDialog",
]