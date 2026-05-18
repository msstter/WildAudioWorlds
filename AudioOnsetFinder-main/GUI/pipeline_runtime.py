from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
from PyQt6.QtCore import QProcess, QProcessEnvironment
from PyQt6.QtWidgets import QInputDialog, QMessageBox

try:
    from per_file_settings_support import PerFileSettingsDialog
except ImportError:
    from GUI.per_file_settings_support import PerFileSettingsDialog


@dataclass(frozen=True)
class PipelineRuntimeDeps:
    analysis_run_keys: Mapping[str, str]
    config_path: str
    default_python: str
    has_onset_editor: bool
    new_analysis_specs: Sequence[dict]
    preset_manager: Any
    project_root: str
    scripts_dir: str
    sidebar_analysis_offset: int
    step_defaults_on: Sequence[bool]
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


def _load_json(path: str) -> dict:
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as file_obj:
        json.dump(_json_safe(data), file_obj, indent=2, sort_keys=True)


def _set_picker_text(widget, text: str) -> None:
    if widget is None:
        return
    try:
        widget.setText(text)
    except Exception:
        try:
            widget.line_edit.setText(text)
        except Exception:
            pass


def _picker_text(widget) -> str:
    if widget is None:
        return ""
    try:
        return widget.text().strip()
    except Exception:
        try:
            return widget.line_edit.text().strip()
        except Exception:
            return ""


def _normalize_python_path(path: str) -> str:
    candidate = (path or "").strip()
    if not candidate:
        return ""

    normalized = candidate
    if candidate.lower().endswith("pythonw.exe"):
        python_candidate = candidate[: -len("pythonw.exe")] + "python.exe"
        if os.path.isfile(python_candidate):
            normalized = python_candidate

    if os.path.isfile(normalized):
        return normalized

    resolved = shutil.which(normalized)
    return resolved or ""


class PipelineRuntimeController:
    def __init__(self, window, deps: PipelineRuntimeDeps):
        self._window = window
        self._deps = deps

    def _analysis_panel_pairs(self):
        return zip(self._deps.new_analysis_specs, self._window.new_analysis_panels)

    def build_config(self) -> dict:
        run_flags = self._window.sidebar.run_flags()
        prep_values = self._window.prep_panel.get_values()
        beat_tempo_values = self._window.beat_tempo_panel.get_values()
        if (
            not beat_tempo_values.get("output_excel_path")
            and self._window.beat_tempo_panel._output_auto_cb.isChecked()
        ):
            beat_tempo_values["output_excel_path"] = _picker_text(
                self._window.extractor_panel.output_excel
            )
        config = {
            "pipeline_prep": prep_values,
            "audio_analyzer": self._window.prep_panel.get_audio_analyzer_values(),
            "muter": {
                "RUN_MUTER": bool(run_flags[2]),
                **self._window.muter_panel.get_values(),
            },
            "extractor": {
                "RUN_EXTRACTOR": bool(run_flags[3]),
                **self._window.extractor_panel.get_values(),
            },
            "beat_tempo": {
                "RUN_BEAT_TEMPO": bool(run_flags[4]),
                **beat_tempo_values,
            },
            "plot_generator": {
                "RUN_PLOT_GENERATOR": bool(run_flags[5]),
                **self._window.plot_panel.get_values(),
            },
            "histogram_generator": {
                "RUN_HISTOGRAM_GENERATOR": bool(run_flags[6]),
                **self._window.histogram_panel.get_values(),
            },
            "npvi_group_generator": {
                "RUN_NPVI_GROUP_GENERATOR": bool(run_flags[7]),
                **self._window.npvi_group_panel.get_values(),
            },
            "assoc_rule_learning": {
                "RUN_ASSOC_RULE_LEARNING": bool(run_flags[18]),
                **self._window.assoc_rule_panel.get_values(),
            },
            "app_state": {
                "run_flags": list(run_flags),
                "python_path": self._window.sidebar.python_path(),
                "description_level": self._window.desc_combo.currentIndex(),
                "experimental_collapsed": bool(
                    getattr(self._window.sidebar, "_experimental_collapsed", True)
                ),
                "selected_step": self._window.panels_stack.currentIndex(),
            },
        }

        if self._deps.has_onset_editor and hasattr(self._window.onset_editor_panel, "get_values"):
            config["onset_editor_ui"] = self._window.onset_editor_panel.get_values()

        for offset, (spec, panel) in enumerate(self._analysis_panel_pairs()):
            run_flag = bool(run_flags[self._deps.sidebar_analysis_offset + offset])
            run_key = self._deps.analysis_run_keys[spec["config_key"]]
            config[spec["config_key"]] = {
                run_key: run_flag,
                "enabled": run_flag,
                **panel.get_values(),
            }

        return config

    def refresh_config_preview(self) -> None:
        try:
            preview_text = json.dumps(
                _json_safe(self.build_config()),
                indent=2,
                sort_keys=True,
            )
        except Exception as exc:
            preview_text = f"Could not build config preview:\n{exc}"
        self._window.config_preview.setPlainText(preview_text)

    def open_presets_dialog(self) -> None:
        actions = ["Load preset", "Save current as preset"]
        action, ok = QInputDialog.getItem(
            self._window,
            "Presets",
            "Choose an action:",
            actions,
            editable=False,
        )
        if not ok:
            return
        if action == "Load preset":
            presets = self._deps.preset_manager.list_presets()
            if not presets:
                QMessageBox.information(
                    self._window,
                    "Presets",
                    "No presets are available yet.",
                )
                return
            name, ok = QInputDialog.getItem(
                self._window,
                "Load Preset",
                "Preset:",
                presets,
                editable=False,
            )
            if not ok or not name:
                return
            try:
                config = self._deps.preset_manager.load_preset(name)
            except Exception as exc:
                QMessageBox.critical(self._window, "Preset Error", str(exc))
                return
            self.apply_config(config)
            self._window.status.showMessage(f"Loaded preset: {name}")
            return

        suggested = self._deps.preset_manager._next_default_name()
        name, ok = QInputDialog.getText(
            self._window,
            "Save Preset",
            "Preset name:",
            text=suggested,
        )
        if not ok:
            return
        final_name = self._deps.preset_manager.save_preset(self.build_config(), name or None)
        self._window.status.showMessage(f"Saved preset: {final_name}")

    def run_pipeline(self) -> None:
        process = getattr(self._window, "_process", None)
        if process is not None and process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(
                self._window,
                "Pipeline Running",
                "The pipeline is already running.",
            )
            return

        config = self.build_config()
        _write_json(self._deps.config_path, config)

        python_path = _normalize_python_path(self._window.sidebar.python_path())
        if not python_path:
            python_path = _normalize_python_path(self._deps.default_python)
        if not python_path:
            QMessageBox.critical(
                self._window,
                "Python Not Found",
                "Could not find a valid Python interpreter for the pipeline. "
                "Use the Python path field in the sidebar to choose rhythm_env\\python.exe.",
            )
            self._window.status.showMessage(
                "Pipeline launch failed: no valid Python interpreter."
            )
            return

        self._window.sidebar.python_picker.setText(python_path)
        self._window.terminal_output.clear()
        self._window.terminal_output.appendPlainText(f"Using Python: {python_path}")
        self._window.terminal_output.appendPlainText(
            f"Writing config: {self._deps.config_path}\n"
        )

        process = QProcess(self._window)
        process_env = QProcessEnvironment()
        for key, value in os.environ.items():
            process_env.insert(key, value)
        process.setProcessEnvironment(process_env)
        process.setWorkingDirectory(self._deps.project_root)
        process.setProgram(python_path)
        process.setArguments([os.path.join(self._deps.scripts_dir, "main.py")])
        process.readyReadStandardOutput.connect(self._window._append_process_output)
        process.readyReadStandardError.connect(self._window._append_process_output)
        process.finished.connect(self._window._on_pipeline_finished)
        process.errorOccurred.connect(self._window._on_pipeline_error)
        self._window._process = process

        self._window._pipeline_progress.show()
        self._window._pipeline_progress.setRange(0, 0)
        self._window._pipeline_progress_label.setText("Running pipeline...")
        self._window.run_btn.setEnabled(False)
        self._window.status.showMessage("Pipeline running...")
        process.start()

    def append_process_output(self) -> None:
        process = getattr(self._window, "_process", None)
        if process is None:
            return
        out = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        err = bytes(process.readAllStandardError()).decode("utf-8", errors="replace")
        text = (out + err).rstrip()
        if text:
            self._window.terminal_output.appendPlainText(text)

    def on_pipeline_finished(self, exit_code: int, _status) -> None:
        self.append_process_output()
        self._window._pipeline_progress.setRange(0, 100)
        self._window._pipeline_progress.setValue(100 if exit_code == 0 else 0)
        self._window._pipeline_progress_label.setText(
            "Pipeline finished."
            if exit_code == 0
            else f"Pipeline failed (exit code {exit_code})."
        )
        self._window.run_btn.setEnabled(True)
        self._window.status.showMessage(self._window._pipeline_progress_label.text())
        self._window._process = None

    def on_pipeline_error(self, error) -> None:
        self.append_process_output()
        self._window._pipeline_progress.show()
        self._window._pipeline_progress.setRange(0, 100)
        self._window._pipeline_progress.setValue(0)
        self._window._pipeline_progress_label.setText(f"Pipeline launch failed: {error}")
        self._window.run_btn.setEnabled(True)
        self._window.status.showMessage(self._window._pipeline_progress_label.text())

    def open_per_file_settings_dialog(self) -> None:
        dialog = PerFileSettingsDialog(
            manager=self._window.per_file_mgr,
            muter_panel=self._window.muter_panel,
            extractor_panel=self._window.extractor_panel,
            parent=self._window,
        )
        dialog.exec()

    def refresh_per_file_manager(self, json_path: str) -> None:
        if hasattr(self._window, "per_file_mgr"):
            self._window.per_file_mgr.load((json_path or "").strip())

    def auto_set_muter_input(self, path: str) -> None:
        if self._window.muter_panel._input_auto_cb.isChecked():
            _set_picker_text(self._window.muter_panel.input_folder, path)

    def auto_set_step2_input(self, path: str) -> None:
        if self._window.extractor_panel._input_auto_cb.isChecked():
            _set_picker_text(self._window.extractor_panel.audio_folder, path)

    def auto_set_step3_input(self, path: str) -> None:
        if self._window.plot_panel._input_auto_cb.isChecked():
            _set_picker_text(self._window.plot_panel.excel_path, path)

    def auto_set_step4_input(self, path: str) -> None:
        if self._window.histogram_panel._input_auto_cb.isChecked():
            _set_picker_text(self._window.histogram_panel.excel_path, path)

    def auto_set_step5_input(self, path: str) -> None:
        if self._window.npvi_group_panel._input_auto_cb.isChecked():
            _set_picker_text(self._window.npvi_group_panel.excel_path, path)

    def auto_set_step6_input(self, path: str) -> None:
        if self._window.assoc_rule_panel._input_auto_cb.isChecked():
            _set_picker_text(self._window.assoc_rule_panel.excel_path, path)

    def auto_set_new_analyses_input(self, path: str) -> None:
        for panel in self._window.new_analysis_panels:
            if panel._input_auto_cb.isChecked():
                _set_picker_text(panel.excel_path, path)

    def auto_set_beat_tempo_input(self, path: str) -> None:
        if self._window.beat_tempo_panel._input_auto_cb.isChecked():
            _set_picker_text(self._window.beat_tempo_panel.audio_folder, path)

    def auto_set_beat_tempo_output(self, path: str) -> None:
        if self._window.beat_tempo_panel._output_auto_cb.isChecked():
            _set_picker_text(self._window.beat_tempo_panel.output_excel, path)

    def auto_set_prep_excel(self, path: str) -> None:
        if path:
            _set_picker_text(self._window.prep_panel.excel_path, path)

    def auto_set_onset_editor_input(self, path: str) -> None:
        if self._deps.has_onset_editor and hasattr(self._window.onset_editor_panel, "set_folder"):
            self._window.onset_editor_panel.set_folder(path)

    def auto_set_onset_editor_excel(self, path: str) -> None:
        if self._deps.has_onset_editor and hasattr(
            self._window.onset_editor_panel,
            "set_pipeline_excel_path",
        ):
            self._window.onset_editor_panel.set_pipeline_excel_path(path)

    def on_muter_input_auto_toggled(self, state: int) -> None:
        if bool(state):
            self.auto_set_muter_input(_picker_text(self._window.prep_panel.input_folder))

    def on_extractor_input_auto_toggled(self, state: int) -> None:
        if bool(state):
            self.auto_set_step2_input(_picker_text(self._window.muter_panel.output_folder))

    def on_plot_input_auto_toggled(self, state: int) -> None:
        if bool(state):
            self.auto_set_step3_input(_picker_text(self._window.extractor_panel.output_excel))

    def on_histogram_input_auto_toggled(self, state: int) -> None:
        if bool(state):
            self.auto_set_step4_input(_picker_text(self._window.extractor_panel.output_excel))

    def on_npvi_input_auto_toggled(self, state: int) -> None:
        if bool(state):
            self.auto_set_step5_input(_picker_text(self._window.extractor_panel.output_excel))

    def on_assoc_input_auto_toggled(self, state: int) -> None:
        if bool(state):
            self.auto_set_step6_input(_picker_text(self._window.extractor_panel.output_excel))

    def on_new_analysis_input_auto_toggled(self, panel) -> None:
        if panel._input_auto_cb.isChecked():
            _set_picker_text(panel.excel_path, _picker_text(self._window.extractor_panel.output_excel))

    def on_beat_tempo_input_auto_toggled(self, state: int) -> None:
        if bool(state):
            self.auto_set_beat_tempo_input(_picker_text(self._window.extractor_panel.audio_folder))

    def on_beat_tempo_output_auto_toggled(self, state: int) -> None:
        if bool(state):
            self.auto_set_beat_tempo_output(_picker_text(self._window.extractor_panel.output_excel))

    def load_last_config(self) -> None:
        config = _load_json(self._deps.config_path)
        if not config:
            self.sync_autoset_from_current_values()
            return
        self.apply_config(config)

    def config_run_flags(self, config: dict) -> list[bool]:
        app_state = config.get("app_state", {})
        run_flags = app_state.get("run_flags")
        if isinstance(run_flags, list) and len(run_flags) == len(self._deps.step_names):
            return [bool(item) for item in run_flags]

        flags = list(self._deps.step_defaults_on)
        flags[2] = bool(config.get("muter", {}).get("RUN_MUTER", flags[2]))
        flags[3] = bool(config.get("extractor", {}).get("RUN_EXTRACTOR", flags[3]))
        flags[4] = bool(config.get("beat_tempo", {}).get("RUN_BEAT_TEMPO", flags[4]))
        flags[5] = bool(config.get("plot_generator", {}).get("RUN_PLOT_GENERATOR", flags[5]))
        flags[6] = bool(config.get("histogram_generator", {}).get("RUN_HISTOGRAM_GENERATOR", flags[6]))
        flags[7] = bool(config.get("npvi_group_generator", {}).get("RUN_NPVI_GROUP_GENERATOR", flags[7]))
        flags[18] = bool(config.get("assoc_rule_learning", {}).get("RUN_ASSOC_RULE_LEARNING", flags[18]))
        for idx, spec in enumerate(
            self._deps.new_analysis_specs,
            start=self._deps.sidebar_analysis_offset,
        ):
            section = config.get(spec["config_key"], {})
            run_key = self._deps.analysis_run_keys[spec["config_key"]]
            flags[idx] = bool(section.get(run_key, section.get("enabled", flags[idx])))
        return flags

    def apply_config(self, config: dict) -> None:
        prep_values = config.get("pipeline_prep", {})
        if prep_values:
            self._window.prep_panel.set_values(prep_values)
        if self._deps.has_onset_editor and hasattr(self._window.onset_editor_panel, "set_values"):
            onset_editor_state = config.get("onset_editor_ui", {})
            if onset_editor_state:
                self._window.onset_editor_panel.set_values(onset_editor_state)
        self._window.muter_panel.set_values(config.get("muter", {}))
        self._window.extractor_panel.set_values(config.get("extractor", {}))
        self._window.beat_tempo_panel.set_values(config.get("beat_tempo", {}))
        self._window.plot_panel.set_values(config.get("plot_generator", {}))
        self._window.histogram_panel.set_values(config.get("histogram_generator", {}))
        self._window.npvi_group_panel.set_values(config.get("npvi_group_generator", {}))
        self._window.assoc_rule_panel.set_values(config.get("assoc_rule_learning", {}))
        for spec, panel in self._analysis_panel_pairs():
            panel.set_values(config.get(spec["config_key"], {}))

        run_flags = self.config_run_flags(config)
        for idx, value in enumerate(run_flags):
            self._window.sidebar._set_run_flag(idx, value)

        app_state = config.get("app_state", {})
        python_path = _normalize_python_path(str(app_state.get("python_path") or ""))
        if python_path:
            self._window.sidebar.python_picker.setText(python_path)
        else:
            self._window.sidebar.python_picker.setText(self._deps.default_python)
        self._window.sidebar.set_experimental_collapsed(
            app_state.get("experimental_collapsed", True)
        )

        desc_level = int(app_state.get("description_level", 0) or 0)
        self._window.desc_combo.blockSignals(True)
        self._window.desc_combo.setCurrentIndex(
            max(0, min(desc_level, self._window.desc_combo.count() - 1))
        )
        self._window.desc_combo.blockSignals(False)
        self._window._on_desc_changed(self._window.desc_combo.currentIndex())

        selected_step = int(app_state.get("selected_step", 0) or 0)
        self._window.sidebar._select_step(
            max(0, min(selected_step, self._window.panels_stack.count() - 1))
        )
        self.sync_autoset_from_current_values()

    def sync_autoset_from_current_values(self) -> None:
        self.auto_set_muter_input(_picker_text(self._window.prep_panel.input_folder))
        self.auto_set_step2_input(_picker_text(self._window.muter_panel.output_folder))
        self.auto_set_onset_editor_input(_picker_text(self._window.muter_panel.output_folder))
        self.auto_set_beat_tempo_input(_picker_text(self._window.extractor_panel.audio_folder))
        excel_path = _picker_text(self._window.extractor_panel.output_excel)
        self.auto_set_beat_tempo_output(excel_path)
        self.auto_set_step3_input(excel_path)
        self.auto_set_step4_input(excel_path)
        self.auto_set_step5_input(excel_path)
        self.auto_set_step6_input(excel_path)
        self.auto_set_new_analyses_input(excel_path)
        self.auto_set_onset_editor_excel(excel_path or _picker_text(self._window.prep_panel.excel_path))
        self.auto_set_prep_excel(excel_path or _picker_text(self._window.prep_panel.excel_path))


__all__ = ["PipelineRuntimeController", "PipelineRuntimeDeps"]