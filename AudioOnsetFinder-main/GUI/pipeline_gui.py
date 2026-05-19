from __future__ import annotations

import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMainWindow


try:
	from local_integration_session import (
		attach_to_local_integration_session,
		consume_local_integration_launch_args,
	)
except ImportError:
	from GUI.local_integration_session import (
		attach_to_local_integration_session,
		consume_local_integration_launch_args,
	)


try:
	from pipeline_bootstrap import (
		CONFIG_PATH,
		DEFAULT_PYTHON,
		ExcelDataUsedDialog,
		FolderPicker,
		ICON_PATH,
		PROJECT_ROOT,
		SCRIPTS_DIR,
		THEME,
		apply_qt_application_theme,
		bootstrap_pipeline_ui,
		ensure_qt_application_font,
		set_description_level as _set_description_level,
	)
except ImportError:
	from GUI.pipeline_bootstrap import (
		CONFIG_PATH,
		DEFAULT_PYTHON,
		ExcelDataUsedDialog,
		FolderPicker,
		ICON_PATH,
		PROJECT_ROOT,
		SCRIPTS_DIR,
		THEME,
		apply_qt_application_theme,
		bootstrap_pipeline_ui,
		ensure_qt_application_font,
		set_description_level as _set_description_level,
	)

try:
	from step_sidebar import SidebarPalette, StepSidebar
except ImportError:
	from GUI.step_sidebar import SidebarPalette, StepSidebar

try:
	from main_window_shell import MainWindowShellDeps, build_main_window_shell
except ImportError:
	from GUI.main_window_shell import MainWindowShellDeps, build_main_window_shell

try:
	from pipeline_preview import (
		AudioPreviewWindow,
		PipelinePreviewController,
		PipelinePreviewDeps,
		PreviewWindow,
	)
except ImportError:
	from GUI.pipeline_preview import (
		AudioPreviewWindow,
		PipelinePreviewController,
		PipelinePreviewDeps,
		PreviewWindow,
	)

try:
	from pipeline_runtime import PipelineRuntimeController, PipelineRuntimeDeps
except ImportError:
	from GUI.pipeline_runtime import PipelineRuntimeController, PipelineRuntimeDeps

try:
	from analysis_specs import (
		ANALYSIS_RUN_KEYS,
		NEW_ANALYSIS_SPECS,
		SIDEBAR_ANALYSIS_OFFSET,
		STEP_SETTINGS_PREFIX,
	)
except ImportError:
	from GUI.analysis_specs import (
		ANALYSIS_RUN_KEYS,
		NEW_ANALYSIS_SPECS,
		SIDEBAR_ANALYSIS_OFFSET,
		STEP_SETTINGS_PREFIX,
	)

try:
	from per_file_settings_support import PerFileSettingsManager
except ImportError:
	from GUI.per_file_settings_support import PerFileSettingsManager

try:
	from panels.analysis_step_panel import AnalysisStepPanel
	from panels.assoc_rule_panel import AssocRulePanel
	from panels.beat_tempo_panel import BeatTempoPanel
	from panels.extractor_panel import ExtractorPanel
	from panels.histogram_panel import HistogramPanel
	from panels.muter_panel import MuterPanel
	from panels.npvi_group_panel import nPVIGroupPanel
	from panels.pipeline_prep_panel import PipelinePrepPanel
	from panels.plot_panel import PlotPanel
except ImportError:
	from GUI.panels.analysis_step_panel import AnalysisStepPanel
	from GUI.panels.assoc_rule_panel import AssocRulePanel
	from GUI.panels.beat_tempo_panel import BeatTempoPanel
	from GUI.panels.extractor_panel import ExtractorPanel
	from GUI.panels.histogram_panel import HistogramPanel
	from GUI.panels.muter_panel import MuterPanel
	from GUI.panels.npvi_group_panel import nPVIGroupPanel
	from GUI.panels.pipeline_prep_panel import PipelinePrepPanel
	from GUI.panels.plot_panel import PlotPanel

try:
	from onset_editor import OnsetEditorPanel, apply_onset_editor_desc_level

	HAS_ONSET_EDITOR = True
except ImportError:
	try:
		from GUI.onset_editor import OnsetEditorPanel, apply_onset_editor_desc_level

		HAS_ONSET_EDITOR = True
	except ImportError:
		OnsetEditorPanel = None
		HAS_ONSET_EDITOR = False

		def apply_onset_editor_desc_level(_level: int) -> None:
			return None

from scripts import preset_manager


bootstrap_pipeline_ui(
	step_settings_prefix=STEP_SETTINGS_PREFIX,
	auto_set_steps=StepSidebar.STEP_NAMES[2:],
)


def set_description_level(level: int) -> None:
	_set_description_level(level, apply_onset_editor_desc_level)


class MainWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		ensure_qt_application_font()
		self._process = None
		self._editor_max_state = 0
		self.setWindowTitle("Bioacoustics Rhythm Pipeline")
		self.resize(1540, 980)
		if ICON_PATH:
			self.setWindowIcon(QIcon(ICON_PATH))
		self._preview = PipelinePreviewController(self, self._build_preview_deps())
		self._runtime = PipelineRuntimeController(self, self._build_runtime_deps())

		build_main_window_shell(self, self._build_shell_deps())
		self._apply_window_style()
		set_description_level(0)

	def _build_preview_deps(self) -> PipelinePreviewDeps:
		return PipelinePreviewDeps(
			accent=THEME.accent,
			accent_dim=THEME.accent_dim,
			audio_preview_step_index=2,
			npvi_group_step_index=7,
			step_names=StepSidebar.STEP_NAMES,
		)

	def _build_runtime_deps(self) -> PipelineRuntimeDeps:
		return PipelineRuntimeDeps(
			analysis_run_keys=ANALYSIS_RUN_KEYS,
			config_path=CONFIG_PATH,
			default_python=DEFAULT_PYTHON,
			has_onset_editor=HAS_ONSET_EDITOR,
			new_analysis_specs=NEW_ANALYSIS_SPECS,
			preset_manager=preset_manager,
			project_root=PROJECT_ROOT,
			scripts_dir=SCRIPTS_DIR,
			sidebar_analysis_offset=SIDEBAR_ANALYSIS_OFFSET,
			step_defaults_on=StepSidebar.STEP_DEFAULTS_ON,
			step_names=StepSidebar.STEP_NAMES,
		)

	def _build_shell_deps(self) -> MainWindowShellDeps:
		return MainWindowShellDeps(
			accent=THEME.accent,
			accent_dim=THEME.accent_dim,
			bg=THEME.bg,
			bg_mid=THEME.bg_mid,
			bg_widget=THEME.bg_widget,
			bg_input=THEME.bg_input,
			border=THEME.border,
			text=THEME.text,
			text_dim=THEME.text_dim,
			text_muted=THEME.text_muted,
			has_onset_editor=HAS_ONSET_EDITOR,
			onset_editor_panel_cls=OnsetEditorPanel,
			create_sidebar=self._create_sidebar,
			pipeline_prep_panel_cls=PipelinePrepPanel,
			muter_panel_cls=MuterPanel,
			extractor_panel_cls=ExtractorPanel,
			beat_tempo_panel_cls=BeatTempoPanel,
			plot_panel_cls=PlotPanel,
			histogram_panel_cls=HistogramPanel,
			npvi_group_panel_cls=nPVIGroupPanel,
			analysis_step_panel_cls=AnalysisStepPanel,
			new_analysis_specs=NEW_ANALYSIS_SPECS,
			assoc_rule_panel_cls=AssocRulePanel,
			per_file_settings_manager_cls=PerFileSettingsManager,
			preset_manager=preset_manager,
		)

	def _create_sidebar(self) -> StepSidebar:
		palette = SidebarPalette(
			accent=THEME.accent,
			accent_hover="#7ad27e",
			accent_dim=THEME.accent_dim,
			bg_mid=THEME.bg_mid,
			bg_widget=THEME.bg_widget,
			border=THEME.border,
			text=THEME.text,
			text_dim=THEME.text_dim,
		)
		return StepSidebar(FolderPicker, DEFAULT_PYTHON, palette, self)

	def _apply_window_style(self) -> None:
		self.setStyleSheet(
			f"QMainWindow {{ background-color: {THEME.bg}; color: {THEME.text}; }}"
			f"QWidget {{ color: {THEME.text}; }}"
			f"QWidget#PipelineCentral {{ background-color: {THEME.bg}; }}"
			f"QSplitter#PipelineBodySplitter, QSplitter#PipelineVerticalSplitter {{ background-color: {THEME.bg}; }}"
			f"QStackedWidget#PipelinePanelsStack {{ background-color: {THEME.bg}; }}"
			f"QStackedWidget#PipelinePanelsStack QScrollArea {{ background-color: {THEME.bg}; border: none; }}"
			f"QStackedWidget#PipelinePanelsStack QAbstractScrollArea::viewport {{ background-color: {THEME.bg}; }}"
			f"QPlainTextEdit {{ background-color: {THEME.bg_widget}; color: {THEME.text}; border: 1px solid {THEME.border}; border-radius: 6px; }}"
			f"QStatusBar {{ background-color: {THEME.bg_mid}; color: {THEME.text_dim}; }}"
		)

	def _show_step(self, index: int) -> None:
		index = max(0, min(int(index), self.panels_stack.count() - 1))
		self.panels_stack.setCurrentIndex(index)
		self.status.showMessage(f"Viewing {StepSidebar.STEP_NAMES[index]}")
		self._refresh_preview()

	def _on_editor_maximize(self, state: int) -> None:
		state = int(state)
		if state == self._editor_max_state:
			return
		if state == 0:
			if self._saved_body_sizes:
				self.body_splitter.setSizes(self._saved_body_sizes)
			if self._saved_v_sizes:
				self.v_splitter.setSizes(self._saved_v_sizes)
		else:
			if not self._saved_body_sizes:
				self._saved_body_sizes = self.body_splitter.sizes()
			if not self._saved_v_sizes:
				self._saved_v_sizes = self.v_splitter.sizes()
			self.body_splitter.setSizes([0, 1])
			if state >= 2:
				self.v_splitter.setSizes([1, 0])
		self._editor_max_state = state

	def _toggle_preview(self) -> None:
		self._preview.toggle_preview()

	def _update_preview_button_text(self) -> None:
		self._preview.update_preview_button_text()

	def _open_presets_dialog(self) -> None:
		self._runtime.open_presets_dialog()

	def _on_desc_changed(self, idx: int) -> None:
		set_description_level(idx)
		self._prev_desc_idx = idx
		if idx == 5:
			self.status.showMessage("Walkthrough mode uses the novice description layer plus the docs walkthrough guide.")
		elif idx == 4:
			self.status.showMessage("Common audio terms enabled.")
		else:
			self.status.showMessage("Description level updated.")

	def _refresh_preview(self) -> None:
		self._preview.refresh_preview()

	def _build_config(self) -> dict:
		return self._runtime.build_config()

	def _refresh_config_preview(self) -> None:
		self._runtime.refresh_config_preview()

	def _run_pipeline(self) -> None:
		self._runtime.run_pipeline()

	def _append_process_output(self) -> None:
		self._runtime.append_process_output()

	def _on_pipeline_finished(self, exit_code: int, _status) -> None:
		self._runtime.on_pipeline_finished(exit_code, _status)

	def _on_pipeline_error(self, error) -> None:
		self._runtime.on_pipeline_error(error)

	def _open_per_file_settings_dialog(self) -> None:
		self._runtime.open_per_file_settings_dialog()

	def _refresh_per_file_manager(self, json_path: str) -> None:
		self._runtime.refresh_per_file_manager(json_path)

	def _auto_set_muter_input(self, path: str) -> None:
		self._runtime.auto_set_muter_input(path)

	def _auto_set_step2_input(self, path: str) -> None:
		self._runtime.auto_set_step2_input(path)

	def _auto_set_step3_input(self, path: str) -> None:
		self._runtime.auto_set_step3_input(path)

	def _auto_set_step4_input(self, path: str) -> None:
		self._runtime.auto_set_step4_input(path)

	def _auto_set_step5_input(self, path: str) -> None:
		self._runtime.auto_set_step5_input(path)

	def _auto_set_step6_input(self, path: str) -> None:
		self._runtime.auto_set_step6_input(path)

	def _auto_set_new_analyses_input(self, path: str) -> None:
		self._runtime.auto_set_new_analyses_input(path)

	def _auto_set_beat_tempo_input(self, path: str) -> None:
		self._runtime.auto_set_beat_tempo_input(path)

	def _auto_set_beat_tempo_output(self, path: str) -> None:
		self._runtime.auto_set_beat_tempo_output(path)

	def _auto_set_prep_excel(self, path: str) -> None:
		self._runtime.auto_set_prep_excel(path)

	def _auto_set_onset_editor_input(self, path: str) -> None:
		self._runtime.auto_set_onset_editor_input(path)

	def _auto_set_onset_editor_excel(self, path: str) -> None:
		self._runtime.auto_set_onset_editor_excel(path)

	def _on_muter_input_auto_toggled(self, state: int) -> None:
		self._runtime.on_muter_input_auto_toggled(state)

	def _on_extractor_input_auto_toggled(self, state: int) -> None:
		self._runtime.on_extractor_input_auto_toggled(state)

	def _on_plot_input_auto_toggled(self, state: int) -> None:
		self._runtime.on_plot_input_auto_toggled(state)

	def _on_histogram_input_auto_toggled(self, state: int) -> None:
		self._runtime.on_histogram_input_auto_toggled(state)

	def _on_npvi_input_auto_toggled(self, state: int) -> None:
		self._runtime.on_npvi_input_auto_toggled(state)

	def _on_assoc_input_auto_toggled(self, state: int) -> None:
		self._runtime.on_assoc_input_auto_toggled(state)

	def _on_new_analysis_input_auto_toggled(self, panel) -> None:
		self._runtime.on_new_analysis_input_auto_toggled(panel)

	def _on_beat_tempo_input_auto_toggled(self, state: int) -> None:
		self._runtime.on_beat_tempo_input_auto_toggled(state)

	def _on_beat_tempo_output_auto_toggled(self, state: int) -> None:
		self._runtime.on_beat_tempo_output_auto_toggled(state)

	def _load_last_config(self) -> None:
		self._runtime.load_last_config()

	def _config_run_flags(self, config: dict) -> list[bool]:
		return self._runtime.config_run_flags(config)

	def _apply_config(self, config: dict) -> None:
		self._runtime.apply_config(config)

	def _sync_autoset_from_current_values(self) -> None:
		self._runtime.sync_autoset_from_current_values()


def main(argv: list[str] | None = None) -> int:
	argv_values = list(sys.argv if argv is None else argv)
	attach_request, qt_argv = consume_local_integration_launch_args(argv_values)
	if argv is None:
		sys.argv[:] = qt_argv

	if attach_request:
		try:
			attach_to_local_integration_session(attach_request)
		except Exception as error:
			print(f"Warning: failed to attach AudioOnsetFinder to the shared WildAudioWorlds session. {error}", file=sys.stderr)

	app = QApplication.instance() or QApplication(qt_argv)
	apply_qt_application_theme(app)
	ensure_qt_application_font()
	if ICON_PATH:
		app.setWindowIcon(QIcon(ICON_PATH))
	window = MainWindow()
	window.show()
	return app.exec()


__all__ = [
	"AudioPreviewWindow",
	"PreviewWindow",
	"MuterPanel",
	"ExtractorPanel",
	"PlotPanel",
	"HistogramPanel",
	"nPVIGroupPanel",
	"ExcelDataUsedDialog",
	"StepSidebar",
	"MainWindow",
	"NEW_ANALYSIS_SPECS",
	"main",
	"set_description_level",
]


if __name__ == "__main__":
	raise SystemExit(main())
