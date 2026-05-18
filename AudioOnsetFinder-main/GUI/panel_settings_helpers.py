from __future__ import annotations

import datetime
import glob
import json
import os

import numpy as np
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

try:
    from form_widgets import DescriptionLabel, _ALL_DESC_LABELS, get_form_widget_palette
except ImportError:
    from GUI.form_widgets import DescriptionLabel, _ALL_DESC_LABELS, get_form_widget_palette


_PROJECT_ROOT = "."
_STEP_SETTINGS_PREFIX: dict[str, str] = {}


def configure_panel_settings_helpers(*, project_root: str,
                                     step_settings_prefix: dict[str, str]) -> None:
    global _PROJECT_ROOT, _STEP_SETTINGS_PREFIX
    _PROJECT_ROOT = project_root
    _STEP_SETTINGS_PREFIX = dict(step_settings_prefix)


def _json_safe_value(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def _settings_folder_for(audio_folder):
    """Return the PipelinePresets subfolder adjacent to *audio_folder*."""
    if not audio_folder:
        return ""
    parent = os.path.dirname(os.path.normpath(audio_folder))
    return os.path.join(parent, "PipelinePresets")


def _save_step_settings(step_name, values_dict, audio_folder):
    """Save *values_dict* as a timestamped JSON file next to *audio_folder*."""
    folder = _settings_folder_for(audio_folder)
    if not folder:
        return ""
    os.makedirs(folder, exist_ok=True)
    prefix = _STEP_SETTINGS_PREFIX.get(step_name, step_name.replace(" ", ""))
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{prefix}_{stamp}.json"
    path = os.path.join(folder, filename)
    clean = {k: _json_safe_value(v) for k, v in values_dict.items()}
    with open(path, "w") as f:
        json.dump(clean, f, indent=2)
    return path


def _scan_saved_settings(audio_folder, step_name):
    """Return display-name/path pairs for saved settings JSON files."""
    folder = _settings_folder_for(audio_folder)
    if not folder or not os.path.isdir(folder):
        return []
    prefix = _STEP_SETTINGS_PREFIX.get(step_name, step_name.replace(" ", ""))
    pattern = os.path.join(folder, f"{prefix}_*.json")
    files = sorted(glob.glob(pattern), reverse=True)
    return [
        (os.path.splitext(os.path.basename(fp))[0], fp)
        for fp in files
    ]


def _build_settings_preset_section(
    panel, lay, step_name, input_picker,
    presets_dict=None, preset_combo_attr="preset",
    auto_desc_text=None,
):
    """Build a shared Settings / Presets section for a step panel."""
    palette = get_form_widget_palette()
    has_presets = presets_dict is not None

    title = "Settings & Presets" if has_presets else "Settings"
    grp = QGroupBox(title)
    g = QVBoxLayout(grp)

    columns = QHBoxLayout()
    columns.setSpacing(16)

    left = QVBoxLayout()
    left_lbl = QLabel("Saved Settings")
    left_lbl.setStyleSheet(
        f"color: {palette.text}; font-size: 12px; font-weight: bold;")
    left.addWidget(left_lbl)

    panel._saved_settings_combo = QComboBox()
    panel._saved_settings_combo.addItem("None")
    panel._saved_settings_combo.setToolTip(
        "Load settings from a previously saved run.\n"
        "Files are found in the PipelinePresets folder next to the input audio.")
    left.addWidget(panel._saved_settings_combo)

    saved_combo_desc = DescriptionLabel(
        "Load settings from a previously saved run.",
        "Lists JSON settings files found in the PipelinePresets/ folder next to "
        "your input audio. Selecting one applies all saved values to this panel, "
        "replacing the current settings. Files are auto-detected when Auto Set "
        "is enabled, or you can Import a file from any location.",
        "Pick a settings file you saved before to set everything back the way "
        "it was. The list fills up automatically when you point to a folder "
        "you have worked with before."
    )
    saved_combo_desc.setStyleSheet(
        saved_combo_desc.styleSheet().replace("margin: 2px 0 6px 230px;",
                                              "margin: 2px 0 4px 0px;"))
    left.addWidget(saved_combo_desc)
    _ALL_DESC_LABELS.append(saved_combo_desc)

    left_btns = QHBoxLayout()
    left_btns.setSpacing(6)
    panel._import_settings_btn = QPushButton("Import…")
    panel._import_settings_btn.setToolTip("Load a saved settings JSON file from disk")
    panel._export_settings_btn = QPushButton("Export…")
    panel._export_settings_btn.setToolTip("Save current settings to a JSON file")
    btn_ss = (
        f"QPushButton {{ background: {palette.bg_widget}; color: {palette.text}; "
        f"border: 1px solid {palette.border}; border-radius: 4px; "
        f"padding: 3px 10px; font-size: 11px; }}"
        f"QPushButton:hover {{ border-color: {palette.accent}; }}")
    for button in (panel._import_settings_btn, panel._export_settings_btn):
        button.setFixedHeight(28)
        button.setStyleSheet(btn_ss)
    left_btns.addWidget(panel._import_settings_btn)
    left_btns.addWidget(panel._export_settings_btn)
    left.addLayout(left_btns)

    import_export_desc = DescriptionLabel(
        "Import loads a JSON settings file; Export saves one.",
        "Import opens a file dialog so you can pick any settings JSON from "
        "disk — useful for restoring a configuration from a collaborator or a "
        "different project folder. Export writes all current panel settings to "
        "a JSON file you choose, defaulting to the PipelinePresets/ folder.",
        "Import lets you load settings someone else saved (or that you saved "
        "somewhere special). Export lets you save your current settings to a "
        "file so you can share them or keep a backup."
    )
    import_export_desc.setStyleSheet(
        import_export_desc.styleSheet().replace("margin: 2px 0 6px 230px;",
                                                "margin: 2px 0 4px 0px;"))
    left.addWidget(import_export_desc)
    _ALL_DESC_LABELS.append(import_export_desc)

    columns.addLayout(left, stretch=1)

    if has_presets:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {palette.border};")
        columns.addWidget(sep)

        right = QVBoxLayout()
        right_lbl = QLabel("Presets")
        right_lbl.setStyleSheet(
            f"color: {palette.text}; font-size: 12px; font-weight: bold;")
        right.addWidget(right_lbl)

        preset_combo = QComboBox()
        preset_combo.addItems(["None"] + list(presets_dict.keys()))
        preset_combo.setToolTip(
            "Load tuned defaults for a specific data type.\n"
            "Set to None for full manual control.")
        setattr(panel, preset_combo_attr, preset_combo)
        right.addWidget(preset_combo)

        preset_combo_desc = DescriptionLabel(
            "Load tuned defaults for a specific data type.",
            "Built-in presets override multiple settings at once with values "
            "optimised for a particular use case (e.g. birdsong, percussion). "
            "Selecting a preset resets the Saved Settings dropdown to None. "
            "Set to None for full manual control of every parameter.",
            "Presets are like ready-made recipes — pick one that matches your "
            "type of recording and it fills in good starting settings for you. "
            "You can always tweak individual settings afterwards."
        )
        preset_combo_desc.setStyleSheet(
            preset_combo_desc.styleSheet().replace("margin: 2px 0 6px 230px;",
                                                   "margin: 2px 0 4px 0px;"))
        right.addWidget(preset_combo_desc)
        _ALL_DESC_LABELS.append(preset_combo_desc)

        panel._save_preset_btn = QPushButton("Save as Preset…")
        panel._save_preset_btn.setToolTip(
            "Save current settings as a new built-in preset")
        panel._save_preset_btn.setFixedHeight(28)
        panel._save_preset_btn.setStyleSheet(btn_ss)
        right.addWidget(panel._save_preset_btn)

        columns.addLayout(right, stretch=1)

    g.addLayout(columns)

    panel._preset_desc = QLabel()
    panel._preset_desc.setWordWrap(True)
    panel._preset_desc.setStyleSheet(
        f"color: {palette.text_dim}; font-style: italic; font-size: 11px; "
        f"background: transparent; padding: 2px 8px;")
    panel._preset_desc.hide()
    g.addWidget(panel._preset_desc)

    cb_row = QHBoxLayout()
    cb_row.setSpacing(16)

    panel._save_settings_on_run = QCheckBox("Save settings on Run")
    panel._save_settings_on_run.setChecked(True)
    panel._save_settings_on_run.setToolTip(
        "Automatically save a timestamped copy of these settings to "
        "the PipelinePresets folder each time the pipeline runs.")
    panel._save_settings_on_run.setStyleSheet(
        f"QCheckBox {{ color: {palette.text_dim}; font-size: 11px; }}")
    cb_row.addWidget(panel._save_settings_on_run)

    panel._settings_auto_set = QCheckBox("Auto Set")
    panel._settings_auto_set.setChecked(True)
    panel._settings_auto_set.setToolTip(
        "Automatically scan PipelinePresets folder for saved settings")
    panel._settings_auto_set.setStyleSheet(
        f"QCheckBox {{ color: {palette.text_dim}; font-size: 11px; }}")
    cb_row.addWidget(panel._settings_auto_set)
    cb_row.addStretch()
    g.addLayout(cb_row)

    save_desc = DescriptionLabel(
        "Auto-saves a timestamped copy of settings each time you Run.",
        "When checked, clicking Run automatically writes a JSON snapshot of all "
        "current panel settings to the PipelinePresets/ folder next to your input "
        "audio. Each snapshot gets a unique timestamp so you never overwrite a "
        "previous configuration. This lets you trace exactly which settings "
        "produced which results.",
        "Every time you click the Run button, the app saves a little file that "
        "remembers all the settings you used. That way, if you get great results "
        "and want to do the exact same thing again later, you can!"
    )
    g.addWidget(save_desc)
    _ALL_DESC_LABELS.append(save_desc)

    auto_desc = DescriptionLabel(
        "Scans the PipelinePresets folder for previously saved settings.",
        "When checked, changing the input folder triggers an automatic scan of "
        "the PipelinePresets/ subfolder. Any saved settings files found are "
        "listed in the Saved Settings dropdown so you can restore them with one "
        "click. Disable this if you want to ignore prior runs.",
        "When this is on, the app automatically looks for settings you saved "
        "before for this folder and shows them in the dropdown list. Turn it "
        "off if you want to start completely fresh."
    )
    g.addWidget(auto_desc)
    _ALL_DESC_LABELS.append(auto_desc)

    if auto_desc_text is None:
        auto_desc_text = (
            f"↳ Auto: Scans <i>PipelinePresets/</i> folder next to input "
            f"for previously saved {step_name} settings")
    panel._settings_auto_desc = QLabel(auto_desc_text)
    panel._settings_auto_desc.setWordWrap(True)
    panel._settings_auto_desc.setStyleSheet(
        f"color: {palette.text_dim}; font-size: 11px; font-style: italic; "
        f"background: transparent; padding: 2px 8px;")
    g.addWidget(panel._settings_auto_desc)

    panel._preset_lock = False

    if has_presets:
        preset_combo = getattr(panel, preset_combo_attr)

        def _on_preset_sel(name, _panel=panel, _attr=preset_combo_attr):
            if _panel._preset_lock:
                return
            _panel._preset_lock = True
            if name != "None":
                _panel._saved_settings_combo.setCurrentText("None")
            _panel._preset_lock = False

        def _on_saved_sel(name, _panel=panel, _attr=preset_combo_attr):
            if _panel._preset_lock:
                return
            _panel._preset_lock = True
            if name != "None":
                getattr(_panel, _attr).setCurrentText("None")
            _panel._preset_lock = False

        preset_combo.currentTextChanged.connect(_on_preset_sel)
        panel._saved_settings_combo.currentTextChanged.connect(_on_saved_sel)

    input_picker.textChanged.connect(
        lambda _text, _panel=panel, _step=step_name: _rescan_saved_settings_for(
            _panel, _step, _text))

    lay.addWidget(grp)
    panel._settings_step_name = step_name
    panel._settings_input_picker = input_picker


def _rescan_saved_settings_for(panel, step_name, _text=None):
    """Re-populate a panel's saved-settings dropdown."""
    if not panel._settings_auto_set.isChecked():
        return
    panel._preset_lock = True
    panel._saved_settings_combo.clear()
    panel._saved_settings_combo.addItem("None")
    folder = panel._settings_input_picker.text()
    entries = _scan_saved_settings(folder, step_name)
    for display_name, _fp in entries:
        panel._saved_settings_combo.addItem(display_name)
    panel._preset_lock = False


def _on_saved_settings_selected(panel, step_name, name):
    """Load a saved-settings JSON file when selected from the dropdown."""
    if name == "None" or not name:
        return
    folder = panel._settings_input_picker.text()
    entries = _scan_saved_settings(folder, step_name)
    path = None
    for display_name, fp in entries:
        if display_name == name:
            path = fp
            break
    if not path or not os.path.isfile(path):
        return
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return
    panel.set_values(data)
    panel._preset_desc.setText(
        f"Loaded saved settings: {os.path.basename(path)}")
    panel._preset_desc.show()


def _import_settings_for(panel, step_name):
    """Manually import a settings JSON file via file dialog."""
    start = _settings_folder_for(
        panel._settings_input_picker.text()) or _PROJECT_ROOT
    path, _ = QFileDialog.getOpenFileName(
        panel, f"Import {step_name} Settings", start,
        "JSON files (*.json)")
    if not path:
        return
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        QMessageBox.warning(panel, "Import Error",
                            f"Could not read file:\n{exc}")
        return
    panel.set_values(data)
    panel._preset_desc.setText(f"Imported: {os.path.basename(path)}")
    panel._preset_desc.show()


def _export_settings_for(panel, step_name):
    """Export current settings to a JSON file via file dialog."""
    folder = _settings_folder_for(
        panel._settings_input_picker.text()) or _PROJECT_ROOT
    os.makedirs(folder, exist_ok=True)
    prefix = _STEP_SETTINGS_PREFIX.get(step_name, step_name.replace(" ", ""))
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    default_name = os.path.join(folder, f"{prefix}_{stamp}.json")
    path, _ = QFileDialog.getSaveFileName(
        panel, f"Export {step_name} Settings", default_name,
        "JSON files (*.json)")
    if not path:
        return
    clean = {k: _json_safe_value(v) for k, v in panel.get_values().items()}
    try:
        with open(path, "w") as f:
            json.dump(clean, f, indent=2)
    except OSError as exc:
        QMessageBox.warning(panel, "Export Error",
                            f"Could not write file:\n{exc}")
        return
    panel._preset_desc.setText(f"Exported: {os.path.basename(path)}")
    panel._preset_desc.show()
    _rescan_saved_settings_for(panel, step_name)


def _save_settings_if_enabled(panel):
    """Auto-save settings on Run. Returns the path or an empty string."""
    if not panel._save_settings_on_run.isChecked():
        return ""
    return _save_step_settings(
        panel._settings_step_name, panel.get_values(),
        panel._settings_input_picker.text())


__all__ = [
    "configure_panel_settings_helpers",
    "_build_settings_preset_section",
    "_export_settings_for",
    "_import_settings_for",
    "_on_saved_settings_selected",
    "_rescan_saved_settings_for",
    "_save_settings_if_enabled",
    "_scan_saved_settings",
    "_settings_folder_for",
]