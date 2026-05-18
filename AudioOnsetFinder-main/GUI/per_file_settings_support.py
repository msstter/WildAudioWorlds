from __future__ import annotations

import json
import os
from copy import deepcopy

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from form_widgets import get_form_widget_palette
except ImportError:
    from GUI.form_widgets import get_form_widget_palette


_MUTER_PREFIX = "MUTER_"

_ONSET_KEY_ORDER = [
    "ONSET_METHOD",
    "MIN_INTER_ONSET_MS",
    "ONSET_DELTA",
    "ONSET_HOP_LENGTH",
    "ONSET_BACKTRACK",
    "APPLY_HIGHPASS_FILTER",
    "HIGHPASS_CUTOFF_HZ",
    "ONSET_AMPLITUDE_GATE",
    "ONSET_AMPLITUDE_WINDOW_MS",
    "ONSET_SHARPNESS_GATE",
    "ONSET_SHARPNESS_WINDOW_MS",
    "ONSET_REFINE_ENABLED",
    "ONSET_REFINE_WINDOW_MS",
    "ONSET_REFINE_ENERGY_GATE",
    "TEMPO_ADAPTIVE_MIN_IOI",
    "TEMPO_ADAPTIVE_FRACTION",
    "PITCH_TRACKER",
]

_MUTER_KEY_ORDER = [
    "MUTER_HIGHPASS_HZ",
    "MUTER_LOWPASS_HZ",
    "MUTER_DB_THRESHOLD",
    "MUTER_AUTO_THRESHOLD",
    "MUTER_NOISE_MARGIN_DB",
    "MUTER_HPSS_ENABLED",
    "MUTER_HPSS_TARGET",
    "MUTER_HPSS_MARGIN",
    "MUTER_SPECTRAL_DENOISE",
    "MUTER_DENOISE_STRENGTH",
    "MUTER_BANDPASS_BOOST",
    "MUTER_BOOST_LOW_HZ",
    "MUTER_BOOST_HIGH_HZ",
    "MUTER_BOOST_GAIN_DB",
    "MUTER_NOTCH_FREQS",
    "MUTER_NOTCH_Q",
    "MUTER_COMPRESS",
    "MUTER_COMPRESS_RATIO",
    "MUTER_COMPRESS_THRESHOLD_DB",
    "MUTER_SHARPEN_TRANSIENTS",
    "MUTER_SHARPEN_GAIN_DB",
    "MUTER_SHARPEN_ATTACK_MS",
    "MUTER_PRE_EMPHASIS",
    "MUTER_NORMALIZE",
    "MUTER_NORMALIZE_TARGET_DB",
    "MUTER_FADE_MS",
]


def _perfile_format_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if abs(value) >= 1000 or (abs(value) < 0.001 and value != 0):
            return f"{value:g}"
        return f"{value:.4f}".rstrip("0").rstrip(".") or "0"
    return str(value)


def _perfile_coerce_value(text: str, template):
    if text is None:
        return None
    stripped = str(text).strip()
    if stripped == "" or stripped.lower() in ("none", "null"):
        return None
    if isinstance(template, bool):
        return stripped.lower() in ("true", "1", "yes", "on")
    if isinstance(template, int) and not isinstance(template, bool):
        try:
            return int(float(stripped))
        except ValueError:
            return stripped
    if isinstance(template, float):
        try:
            return float(stripped)
        except ValueError:
            return stripped
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        pass
    if stripped.lower() in ("true", "false"):
        return stripped.lower() == "true"
    return stripped


class PerFileToggleIndicator(QCheckBox):
    _COLOR_GENERAL = "#3B82F6"
    _COLOR_SPECIFIC = "#F97316"

    def __init__(self, section_key: str, config_key: str, parent=None):
        super().__init__(parent)
        self.section_key = section_key
        self.config_key = config_key
        self._manager: PerFileSettingsManager | None = None

        self.setFixedSize(22, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setText("")
        self.setToolTip(
            f"Per-file override toggle for {config_key}.\n"
            "Blue (General): every file uses the value in this panel.\n"
            "Orange (Specific): every file uses the per-file value "
            "suggested by Pre-Analyze.\n"
            "This toggle is in sync with the 'View / Edit Per-File "
            "Settings' dialog and the summary strip at the top of the "
            "panel - they all edit the same file."
        )

        self._apply_style(False)
        self.toggled.connect(self._on_toggled)
        self.hide()

    def set_manager(self, manager: PerFileSettingsManager | None):
        if self._manager is manager:
            self._refresh_from_manager()
            return
        if self._manager is not None:
            try:
                self._manager.changed.disconnect(self._refresh_from_manager)
            except (TypeError, RuntimeError):
                pass
        self._manager = manager
        if manager is not None:
            manager.changed.connect(self._refresh_from_manager)
        self._refresh_from_manager()

    def _refresh_from_manager(self):
        manager = self._manager
        relevant = False
        overridden = False
        if manager is not None and manager.has_data():
            for _filename, file_dict in manager.files().items():
                section = file_dict.get(self.section_key)
                if isinstance(section, dict) and self.config_key in section:
                    relevant = True
                    overridden = True
                    break
            if not relevant:
                for _filename, file_dict in manager.original().items():
                    section = file_dict.get(self.section_key)
                    if isinstance(section, dict) and self.config_key in section:
                        relevant = True
                        break
        if not relevant:
            self.hide()
            return
        self.show()
        self.blockSignals(True)
        self.setChecked(overridden)
        self.blockSignals(False)
        self._apply_style(overridden)

    def _apply_style(self, specific: bool):
        color = self._COLOR_SPECIFIC if specific else self._COLOR_GENERAL
        label = "Specific" if specific else "General"
        self.setStyleSheet(
            f"QCheckBox {{ spacing: 0; }}"
            f"QCheckBox::indicator {{"
            f" width: 18px; height: 18px;"
            f" border: 2px solid {color};"
            f" border-radius: 9px;"
            f" background-color: {'rgba(249,115,22,0.35)' if specific else 'rgba(59,130,246,0.18)'};"
            f"}} "
            f"QCheckBox::indicator:hover {{"
            f" background-color: {'rgba(249,115,22,0.55)' if specific else 'rgba(59,130,246,0.35)'};"
            f"}}"
        )
        self.setAccessibleName(f"{self.config_key}: {label}")

    def _on_toggled(self, checked: bool):
        if self._manager is None:
            return
        new_source = (
            PerFileSettingsDialog.SRC_SPECIFIC
            if checked else PerFileSettingsDialog.SRC_GENERAL
        )
        self._manager.set_source(self.section_key, self.config_key, new_source)


def _mark_perfile_setting(widget, section_key: str,
                          config_key: str) -> PerFileToggleIndicator | None:
    row = getattr(widget, "_perfile_row", None)
    if row is None:
        return None
    indicator = PerFileToggleIndicator(section_key, config_key)
    row.insertWidget(0, indicator)
    widget._perfile_indicator = indicator
    return indicator


class PerFileSettingsManager(QObject):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._path: str = ""
        self._files: dict[str, dict] = {}
        self._original: dict[str, dict] = {}
        self._meta: dict[str, dict] = {}

    def path(self) -> str:
        return self._path

    def load(self, json_path: str) -> bool:
        if not json_path or not os.path.isfile(json_path):
            self._path = json_path or ""
            self._files = {}
            self._original = {}
            self._meta = {}
            self.changed.emit()
            return False
        with open(json_path, encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        if not isinstance(data, dict):
            return False
        self._path = json_path
        self._meta = {key: value for key, value in data.items() if key.startswith("__")}
        self._files = {
            key: (value if isinstance(value, dict) else {})
            for key, value in data.items()
            if not key.startswith("__")
        }
        self._original = self._meta.get("__pre_analysis_original__") or deepcopy(self._files)
        self.changed.emit()
        return True

    def reload(self) -> bool:
        return self.load(self._path) if self._path else False

    def save(self) -> bool:
        if not self._path:
            return False
        self._meta["__pre_analysis_original__"] = self._original
        out = dict(self._files)
        out.update(self._meta)
        with open(self._path, "w", encoding="utf-8") as file_obj:
            json.dump(out, file_obj, indent=2)
        return True

    def has_data(self) -> bool:
        return bool(self._files)

    def general_metadata(self) -> dict:
        general_metadata = self._meta.get("__general_metadata__")
        return general_metadata if isinstance(general_metadata, dict) else {}

    def set_general_metadata(self, values: dict, autosave: bool = True) -> None:
        clean = {
            key: value
            for key, value in (values or {}).items()
            if value is not None and str(value).strip() != ""
        }
        if clean:
            self._meta["__general_metadata__"] = clean
        else:
            self._meta.pop("__general_metadata__", None)
        if autosave and self._path:
            self.save()
        self.changed.emit()

    def filenames(self) -> list[str]:
        return sorted(self._files.keys())

    def files(self) -> dict:
        return self._files

    def original(self) -> dict:
        return self._original

    def section(self, section_key: str, filename: str) -> dict:
        file_dict = self._files.get(filename, {})
        section = file_dict.get(section_key)
        return section if isinstance(section, dict) else {}

    def original_section(self, section_key: str, filename: str) -> dict:
        file_dict = self._original.get(filename, {})
        section = file_dict.get(section_key)
        return section if isinstance(section, dict) else {}

    def is_overridden(self, section_key: str, key: str) -> bool:
        for filename in self._files:
            if key in self.section(section_key, filename):
                return True
        return False

    def overridden_keys(self, section_key: str, key_filter=None) -> list[str]:
        keys: set[str] = set()
        for filename in self._files:
            for key in self.section(section_key, filename):
                if key_filter is None or key_filter(key):
                    keys.add(key)
        return sorted(keys)

    def values_for_key(self, section_key: str, key: str) -> list:
        return [self.section(section_key, filename).get(key)
                for filename in self.filenames()]

    def original_values_for_key(self, section_key: str, key: str) -> list:
        return [self.original_section(section_key, filename).get(key)
                for filename in self.filenames()]

    def set_source(self, section_key: str, key: str, source: str,
                   autosave: bool = True) -> None:
        if source == PerFileSettingsDialog.SRC_GENERAL:
            for filename in self._files:
                section = self._files[filename].setdefault(section_key, {})
                section.pop(key, None)
        else:
            for filename in self._files:
                original = self.original_section(section_key, filename)
                if key in original:
                    section = self._files[filename].setdefault(section_key, {})
                    section[key] = deepcopy(original[key])
        if autosave:
            self.save()
        self.changed.emit()

    def set_all_sources(self, section_key: str, source: str, key_filter=None,
                        autosave: bool = True) -> None:
        keys: set[str] = set()
        for filename in self._files:
            keys.update(self.section(section_key, filename).keys())
            keys.update(self.original_section(section_key, filename).keys())
        if key_filter is not None:
            keys = {key for key in keys if key_filter(key)}
        for key in keys:
            self.set_source(section_key, key, source, autosave=False)
        if autosave:
            self.save()
        self.changed.emit()

    def set_value(self, section_key: str, key: str, filename: str, value,
                  autosave: bool = True) -> None:
        section = self._files.setdefault(filename, {}).setdefault(section_key, {})
        if value is None:
            section.pop(key, None)
        else:
            section[key] = value
        if autosave:
            self.save()
        self.changed.emit()

    def bulk_set_files(self, new_files: dict, autosave: bool = True) -> None:
        self._files = new_files
        if autosave:
            self.save()
        self.changed.emit()


class PerFileSettingsDialog(QDialog):
    SRC_GENERAL = "General"
    SRC_SPECIFIC = "Specific"

    def __init__(self, json_path: str = "", muter_panel=None,
                 extractor_panel=None, manager: PerFileSettingsManager | None = None,
                 parent=None):
        super().__init__(parent)
        self.muter_panel = muter_panel
        self.extractor_panel = extractor_panel

        if manager is not None:
            self._manager = manager
            self.json_path = manager.path()
        else:
            self._manager = PerFileSettingsManager(self)
            if json_path:
                self._manager.load(json_path)
            self.json_path = json_path

        self._muter_panel_values = (
            muter_panel.get_values() if muter_panel is not None else {}
        )
        self._extractor_panel_values = (
            extractor_panel.get_values() if extractor_panel is not None else {}
        )

        palette = get_form_widget_palette()
        self.setWindowTitle("Per-File Settings - Audio Editor & Onset Finder")
        self.setMinimumSize(1080, 680)
        self.setStyleSheet(
            f"QDialog {{ background-color: {palette.bg_mid}; color: {palette.text}; }}"
        )

        self._build_ui()
        self._manager.changed.connect(self._on_manager_changed)

    def _on_manager_changed(self):
        if hasattr(self, "_tabs") and self._tabs is not None:
            index = self._tabs.currentIndex()
            self._tabs.clear()
            self._muter_tab = _PerFileSectionTable(
                manager=self._manager,
                panel_values=self._muter_panel_values,
                section_key="settings",
                key_filter=lambda key: key.startswith(_MUTER_PREFIX),
                key_order_fn=_PerFileSectionTable.order_by_list_then_alpha(
                    _MUTER_KEY_ORDER
                ),
                parent=self,
            )
            self._tabs.addTab(self._muter_tab, "Audio Editor  (MUTER_*)")
            self._onset_tab = _PerFileSectionTable(
                manager=self._manager,
                panel_values=self._extractor_panel_values,
                section_key="onset_recommendations",
                key_filter=lambda key: not key.startswith(_MUTER_PREFIX),
                key_order_fn=_PerFileSectionTable.order_by_list_then_alpha(
                    _ONSET_KEY_ORDER
                ),
                parent=self,
            )
            self._tabs.addTab(self._onset_tab, "Onset Finder")
            if 0 <= index < self._tabs.count():
                self._tabs.setCurrentIndex(index)

    def _build_ui(self):
        palette = get_form_widget_palette()
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QLabel(
            "<b>What each row means.</b> For every setting below, choose "
            "<b>General</b> to let all files use the value currently in the "
            "Audio Editor / Onset Finder panel, or <b>Specific</b> to use "
            "(and optionally edit) the per-file value that Pre-Analyze "
            "chose. &nbsp;"
            "<span style='color:" + palette.text_dim + "'>"
            "The JSON on disk is the source of truth: at pipeline run time "
            "keys present per file override the panel; keys removed "
            "(General) fall back to the panel. "
            "This dialog and the per-setting General/Specific toggles "
            "inside the Audio Editor and Onset Finder panels read and "
            "write the same file - changes here are reflected there "
            "automatically, and vice versa."
            "</span>"
        )
        header.setWordWrap(True)
        header.setStyleSheet(
            f"color: {palette.text}; font-size: 12px; background: transparent;"
        )
        root.addWidget(header)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabBar::tab {{ background: {palette.bg_widget}; color: {palette.text}; "
            f"padding: 6px 14px; border: 1px solid {palette.border}; "
            f"border-bottom: none; border-top-left-radius: 4px; "
            f"border-top-right-radius: 4px; }} "
            f"QTabBar::tab:selected {{ background: {palette.bg_mid}; "
            f"color: {palette.accent}; font-weight: 700; }} "
            f"QTabWidget::pane {{ border: 1px solid {palette.border}; "
            f"background: {palette.bg_mid}; }}"
        )

        self._muter_tab = _PerFileSectionTable(
            manager=self._manager,
            panel_values=self._muter_panel_values,
            section_key="settings",
            key_filter=lambda key: key.startswith(_MUTER_PREFIX),
            key_order_fn=_PerFileSectionTable.order_by_list_then_alpha(
                _MUTER_KEY_ORDER
            ),
            parent=self,
        )
        self._tabs.addTab(self._muter_tab, "Audio Editor  (MUTER_*)")

        self._onset_tab = _PerFileSectionTable(
            manager=self._manager,
            panel_values=self._extractor_panel_values,
            section_key="onset_recommendations",
            key_filter=lambda key: not key.startswith(_MUTER_PREFIX),
            key_order_fn=_PerFileSectionTable.order_by_list_then_alpha(
                _ONSET_KEY_ORDER
            ),
            parent=self,
        )
        self._tabs.addTab(self._onset_tab, "Onset Finder")
        root.addWidget(self._tabs, stretch=1)

        button_row = QHBoxLayout()
        info = QLabel(f"Editing: <code>{os.path.basename(self._manager.path())}</code>")
        info.setStyleSheet(
            f"color: {palette.text_dim}; font-size: 11px; background: transparent;"
        )
        button_row.addWidget(info)
        button_row.addStretch(1)

        cancel_button = QPushButton("  Cancel  ")
        cancel_button.setStyleSheet(
            f"QPushButton {{ background-color: {palette.bg_widget}; color: {palette.text}; "
            f"border: 1px solid {palette.border}; border-radius: 5px; "
            f"padding: 5px 14px; font-size: 12px; }} "
            f"QPushButton:hover {{ border-color: {palette.accent}; }}"
        )
        cancel_button.clicked.connect(self.reject)
        button_row.addWidget(cancel_button)

        save_button = QPushButton("  Save Changes  ")
        save_button.setStyleSheet(
            f"QPushButton {{ background-color: {palette.accent_dim}; color: white; "
            f"border-radius: 5px; padding: 5px 14px; font-size: 12px; "
            f"border: none; }} "
            f"QPushButton:hover {{ background-color: {palette.accent}; }}"
        )
        save_button.clicked.connect(self._on_save)
        button_row.addWidget(save_button)

        root.addLayout(button_row)

    def _on_save(self):
        try:
            self._muter_tab.apply_to_files()
            self._onset_tab.apply_to_files()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Could Not Save",
                f"Failed to build the updated per-file payload:\n{exc}",
            )
            return

        try:
            self._manager.save()
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Could Not Write File",
                f"Failed to write {self._manager.path()}:\n{exc}",
            )
            return

        self._manager.changed.emit()
        self.accept()


class _PerFileSectionTable(QWidget):
    def __init__(self, manager: PerFileSettingsManager, panel_values: dict,
                 section_key: str, key_filter, key_order_fn, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._panel_values = panel_values
        self._section_key = section_key

        files = manager.files()
        original = manager.original()

        all_keys: set[str] = set()
        for file_dict in files.values():
            section = file_dict.get(section_key) if isinstance(file_dict, dict) else None
            if isinstance(section, dict):
                all_keys.update(key for key in section.keys() if key_filter(key))
        for file_dict in original.values():
            section = file_dict.get(section_key) if isinstance(file_dict, dict) else None
            if isinstance(section, dict):
                all_keys.update(key for key in section.keys() if key_filter(key))
        for key in panel_values.keys():
            if key_filter(key) and key not in ("audio_folder", "output_excel_path"):
                all_keys.add(key)

        self._ordered_keys: list[str] = list(key_order_fn(all_keys))
        self._filenames: list[str] = sorted(files.keys())
        self._row_source: dict[str, str] = {}
        for key in self._ordered_keys:
            present = any(
                isinstance(files.get(filename, {}).get(section_key), dict)
                and key in files[filename][section_key]
                for filename in self._filenames
            )
            self._row_source[key] = (
                PerFileSettingsDialog.SRC_SPECIFIC
                if present else PerFileSettingsDialog.SRC_GENERAL
            )

        self._build_table()

    @property
    def _files(self):
        return self._manager.files()

    @property
    def _original(self):
        return self._manager.original()

    @staticmethod
    def order_by_list_then_alpha(priority_list: list[str]):
        def _sort(keys):
            priority_set = set(priority_list)
            in_list = [key for key in priority_list if key in keys]
            rest = sorted(key for key in keys if key not in priority_set)
            return in_list + rest

        return _sort

    def _build_table(self):
        palette = get_form_widget_palette()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(6)

        tools = QHBoxLayout()
        tools.setSpacing(6)
        all_general_button = QPushButton("All rows -> General")
        all_general_button.setToolTip(
            "Set every setting in this tab to use the panel value "
            "(equivalent to clearing every file's override)."
        )
        all_general_button.clicked.connect(
            lambda: self._set_all_sources(PerFileSettingsDialog.SRC_GENERAL)
        )
        tools.addWidget(all_general_button)

        all_specific_button = QPushButton("All rows -> Specific")
        all_specific_button.setToolTip(
            "Restore every setting in this tab to the per-file value "
            "Pre-Analyze originally chose."
        )
        all_specific_button.clicked.connect(
            lambda: self._set_all_sources(PerFileSettingsDialog.SRC_SPECIFIC)
        )
        tools.addWidget(all_specific_button)

        tools.addStretch(1)
        count_label = QLabel(
            f"{len(self._filenames)} file(s) x {len(self._ordered_keys)} setting(s)"
        )
        count_label.setStyleSheet(
            f"color: {palette.text_dim}; font-size: 11px; background: transparent;"
        )
        tools.addWidget(count_label)
        layout.addLayout(tools)

        columns = ["Setting", "Source", "Panel (General)"] + self._filenames
        self._table = QTableWidget(len(self._ordered_keys), len(columns))
        self._table.setHorizontalHeaderLabels(columns)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setStyleSheet(
            f"QTableWidget {{ background-color: {palette.bg_widget}; color: {palette.text}; "
            f"gridline-color: {palette.border}; font-size: 11px; "
            f"alternate-background-color: {palette.bg_input}; }}"
            f"QHeaderView::section {{ background-color: {palette.bg_mid}; "
            f"color: {palette.text}; border: 1px solid {palette.border}; padding: 4px; "
            f"font-weight: bold; font-size: 11px; }}"
        )

        self._source_combos: dict[str, QComboBox] = {}

        for row, key in enumerate(self._ordered_keys):
            name_item = QTableWidgetItem(key)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name_item.setToolTip(key)
            self._table.setItem(row, 0, name_item)

            combo = QComboBox()
            combo.addItems([
                PerFileSettingsDialog.SRC_GENERAL,
                PerFileSettingsDialog.SRC_SPECIFIC,
            ])
            combo.setCurrentText(self._row_source[key])
            combo.currentTextChanged.connect(
                lambda text, config_key=key: self._on_source_changed(config_key, text)
            )
            self._source_combos[key] = combo
            self._table.setCellWidget(row, 1, combo)

            panel_value = self._panel_values.get(key)
            panel_item = QTableWidgetItem(_perfile_format_value(panel_value))
            panel_item.setFlags(panel_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if panel_value is None:
                panel_item.setForeground(QColor(palette.text_dim))
                panel_item.setToolTip("No value found in the panel for this key.")
            else:
                panel_item.setToolTip(f"Current panel value for {key}: {panel_value!r}")
            self._table.setItem(row, 2, panel_item)

            for column_index, filename in enumerate(self._filenames, start=3):
                self._populate_file_cell(row, column_index, filename, key)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, header.ResizeMode.ResizeToContents)
        for column_index in range(3, len(columns)):
            header.setSectionResizeMode(column_index, header.ResizeMode.Interactive)
            self._table.setColumnWidth(column_index, 130)

        layout.addWidget(self._table, stretch=1)

    def _populate_file_cell(self, row: int, col: int, filename: str, key: str):
        palette = get_form_widget_palette()
        source = self._row_source[key]
        live_section = self._files.get(filename, {}).get(self._section_key, {})
        original_section = self._original.get(filename, {}).get(self._section_key, {})

        if source == PerFileSettingsDialog.SRC_GENERAL:
            item = QTableWidgetItem("- uses general -")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable & ~Qt.ItemFlag.ItemIsSelectable)
            item.setForeground(QColor(palette.text_dim))
            if key in original_section:
                item.setToolTip(
                    "Pre-Analysis originally suggested: "
                    f"{original_section[key]!r}. Switch Source to 'Specific' to "
                    "restore / edit it."
                )
        else:
            if isinstance(live_section, dict) and key in live_section:
                value = live_section[key]
            elif isinstance(original_section, dict) and key in original_section:
                value = original_section[key]
            else:
                value = None
            item = QTableWidgetItem(_perfile_format_value(value))
            item.setToolTip(
                f"Per-file value for {filename} / {key}. Edit to override "
                "the Pre-Analysis suggestion."
            )

        self._table.setItem(row, col, item)

    def _on_source_changed(self, key: str, new_source: str):
        self._row_source[key] = new_source
        row = self._ordered_keys.index(key)
        for column_index, filename in enumerate(self._filenames, start=3):
            self._populate_file_cell(row, column_index, filename, key)

    def _set_all_sources(self, new_source: str):
        for _key, combo in self._source_combos.items():
            combo.setCurrentText(new_source)

    def apply_to_files(self):
        for row, key in enumerate(self._ordered_keys):
            source = self._row_source[key]
            for column_index, filename in enumerate(self._filenames, start=3):
                file_entry = self._files.setdefault(filename, {})
                section = file_entry.setdefault(self._section_key, {})

                if source == PerFileSettingsDialog.SRC_GENERAL:
                    section.pop(key, None)
                    continue

                item = self._table.item(row, column_index)
                text = item.text() if item is not None else ""
                original_section = self._original.get(filename, {}).get(self._section_key, {})
                template = original_section.get(key) if isinstance(original_section, dict) else None
                if template is None:
                    template = self._panel_values.get(key)

                coerced = _perfile_coerce_value(text, template)
                if coerced is None and text.strip() == "":
                    section.pop(key, None)
                else:
                    section[key] = coerced


class PerFileOverridesBox(QGroupBox):
    def __init__(self, section_key: str, panel_label: str, key_filter,
                 key_order_list: list[str], parent=None,
                 open_dialog_callback=None):
        super().__init__("Per-File Overrides (from Pre-Analyze)", parent)
        self._manager: PerFileSettingsManager | None = None
        self._section_key = section_key
        self._panel_label = panel_label
        self._key_filter = key_filter
        self._key_order_list = key_order_list
        self._open_dialog_callback = open_dialog_callback
        self._row_widgets: dict[str, QComboBox] = {}

        palette = get_form_widget_palette()
        self.setStyleSheet(
            f"QGroupBox {{ border: 1px solid {palette.accent_dim}; "
            f"border-radius: 6px; margin-top: 10px; padding-top: 8px; "
            f"color: {palette.text}; background-color: {palette.bg_mid}; font-weight: 700; }} "
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; "
            f"padding: 0 6px; color: {palette.accent}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 8)
        outer.setSpacing(6)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color: {palette.text}; font-size: 11px; background: transparent; "
            f"font-weight: 600;"
        )
        self._status_lbl.setWordWrap(True)
        outer.addWidget(self._status_lbl)

        note = QLabel(
            "<span style='color:" + palette.text_dim + "'>"
            "Each row below lets you choose <b>General</b> (this "
            f"{panel_label} panel's value is used for that file) or "
            "<b>Specific</b> (the per-file value Pre-Analyze suggested is "
            "used instead). "
            "This strip and the full "
            "<i>View / Edit Per-File Settings</i> dialog share the same "
            "JSON on disk, so changes here appear there automatically "
            "and vice versa. "
            "Per-file overrides apply to whichever audio files are in "
            f"the {panel_label} input folder at pipeline run time - if "
            "you point the folder elsewhere, the overrides simply don't "
            "match anything and the panel values are used for every file."
            "</span>"
        )
        note.setWordWrap(True)
        note.setStyleSheet("background: transparent; font-size: 11px; font-weight: 400;")
        outer.addWidget(note)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self._open_btn = QPushButton("Open full editor...")
        self._open_btn.setToolTip(
            "Open the tabbed View / Edit Per-File Settings dialog "
            "(shows every file, every setting, with editable values)."
        )
        self._open_btn.clicked.connect(self._on_open_full_editor)
        buttons.addWidget(self._open_btn)

        self._all_general_btn = QPushButton("Revert all to General")
        self._all_general_btn.setToolTip(
            f"Remove every per-file override for the {panel_label} "
            "section - every file will use this panel's value at run "
            "time."
        )
        self._all_general_btn.clicked.connect(
            lambda: self._set_all(PerFileSettingsDialog.SRC_GENERAL)
        )
        buttons.addWidget(self._all_general_btn)

        self._all_specific_btn = QPushButton("Restore all Specific")
        self._all_specific_btn.setToolTip(
            f"Restore every setting Pre-Analyze suggested for the "
            f"{panel_label} section to its per-file value."
        )
        self._all_specific_btn.clicked.connect(
            lambda: self._set_all(PerFileSettingsDialog.SRC_SPECIFIC)
        )
        buttons.addWidget(self._all_specific_btn)

        buttons.addStretch(1)
        outer.addLayout(buttons)

        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(2)

        self._body_scroll = QScrollArea()
        self._body_scroll.setWidgetResizable(True)
        self._body_scroll.setWidget(self._body)
        self._body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._body_scroll.setMaximumHeight(180)
        self._body_scroll.setStyleSheet("background: transparent;")
        outer.addWidget(self._body_scroll)

        self.hide()

    def set_manager(self, manager: PerFileSettingsManager | None):
        if self._manager is manager:
            return
        if self._manager is not None:
            try:
                self._manager.changed.disconnect(self._on_manager_changed)
            except (TypeError, RuntimeError):
                pass
        self._manager = manager
        if manager is not None:
            manager.changed.connect(self._on_manager_changed)
        self._on_manager_changed()

    def manager(self) -> PerFileSettingsManager | None:
        return self._manager

    def _on_manager_changed(self):
        palette = get_form_widget_palette()
        manager = self._manager
        if manager is None or not manager.has_data():
            self.hide()
            return

        keys: set[str] = set()
        for _filename, file_dict in manager.files().items():
            section = file_dict.get(self._section_key)
            if isinstance(section, dict):
                keys.update(key for key in section if self._key_filter(key))
        for _filename, file_dict in manager.original().items():
            section = file_dict.get(self._section_key)
            if isinstance(section, dict):
                keys.update(key for key in section if self._key_filter(key))

        priority_set = set(self._key_order_list)
        ordered = [key for key in self._key_order_list if key in keys] + sorted(
            key for key in keys if key not in priority_set
        )

        while self._body_layout.count():
            child = self._body_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._row_widgets = {}

        if not ordered:
            label = QLabel(
                "<i>Pre-Analyze didn't record any per-file suggestions for "
                f"this {self._panel_label} section - nothing to override.</i>"
            )
            label.setStyleSheet(
                f"color: {palette.text_dim}; background: transparent; "
                f"font-size: 11px; font-weight: 400;"
            )
            label.setWordWrap(True)
            self._body_layout.addWidget(label)
        else:
            for key in ordered:
                self._body_layout.addWidget(self._make_row(key))
            self._body_layout.addStretch(1)

        n_files = len(manager.filenames())
        n_overridden = sum(
            1 for key in ordered if manager.is_overridden(self._section_key, key)
        )
        self._status_lbl.setText(
            f"{n_overridden} of {len(ordered)} setting(s) using Specific "
            f"per-file values · {n_files} file(s) analysed · "
            f"source: {os.path.basename(manager.path())}"
        )
        self.show()

    def _make_row(self, key: str) -> QWidget:
        palette = get_form_widget_palette()
        manager = self._manager
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 1, 4, 1)
        row_layout.setSpacing(8)

        name = QLabel(key)
        name.setStyleSheet(
            f"color: {palette.text}; background: transparent; font-size: 11px; "
            f"font-weight: 500; min-width: 210px;"
        )
        name.setMinimumWidth(210)
        row_layout.addWidget(name)

        combo = QComboBox()
        combo.addItems([
            PerFileSettingsDialog.SRC_GENERAL,
            PerFileSettingsDialog.SRC_SPECIFIC,
        ])
        current = (
            PerFileSettingsDialog.SRC_SPECIFIC
            if manager.is_overridden(self._section_key, key)
            else PerFileSettingsDialog.SRC_GENERAL
        )
        combo.setCurrentText(current)
        combo.setStyleSheet(
            f"QComboBox {{ background: {palette.bg_widget}; color: {palette.text}; "
            f"border: 1px solid {palette.border}; border-radius: 3px; "
            f"padding: 1px 4px; font-size: 11px; font-weight: 400; }}"
        )
        combo.setMinimumWidth(100)
        combo.currentTextChanged.connect(
            lambda text, config_key=key: self._on_row_changed(config_key, text)
        )
        self._row_widgets[key] = combo
        row_layout.addWidget(combo)

        values = manager.values_for_key(self._section_key, key)
        original_values = manager.original_values_for_key(self._section_key, key)
        summary_text = self._summarise_values(
            values if current == PerFileSettingsDialog.SRC_SPECIFIC else original_values
        )
        summary = QLabel(summary_text)
        summary.setStyleSheet(
            f"color: {palette.text_dim}; background: transparent; font-size: 11px; "
            f"font-weight: 400;"
        )
        summary.setToolTip(
            "Per-file values (Specific) or Pre-Analyze suggestions "
            "(when currently General)."
        )
        row_layout.addWidget(summary)
        row_layout.addStretch(1)

        return row

    @staticmethod
    def _summarise_values(values: list) -> str:
        present = [value for value in values if value is not None]
        if not present:
            return "- no value -"
        unique = []
        for value in present:
            if value not in unique:
                unique.append(value)
        if len(unique) == 1:
            return f"all files: {_perfile_format_value(unique[0])}"
        if len(unique) <= 3:
            return " · ".join(_perfile_format_value(value) for value in unique)
        try:
            numbers = [float(value) for value in unique]
            return f"{len(unique)} distinct values ({min(numbers):g}-{max(numbers):g})"
        except (TypeError, ValueError):
            return f"{len(unique)} distinct values"

    def _on_row_changed(self, key: str, new_source: str):
        if self._manager is None:
            return
        self._manager.set_source(self._section_key, key, new_source)

    def _set_all(self, new_source: str):
        if self._manager is None:
            return
        self._manager.set_all_sources(
            self._section_key,
            new_source,
            key_filter=self._key_filter,
        )

    def _on_open_full_editor(self):
        if self._open_dialog_callback is not None:
            self._open_dialog_callback()


__all__ = [
    "_MUTER_PREFIX",
    "_MUTER_KEY_ORDER",
    "_ONSET_KEY_ORDER",
    "_mark_perfile_setting",
    "PerFileOverridesBox",
    "PerFileSettingsDialog",
    "PerFileSettingsManager",
    "PerFileToggleIndicator",
]