from __future__ import annotations

import platform
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class MainWindowShellDeps:
    accent: str
    accent_dim: str
    bg: str
    bg_mid: str
    bg_widget: str
    bg_input: str
    border: str
    text: str
    text_dim: str
    text_muted: str
    has_onset_editor: bool
    onset_editor_panel_cls: type | None
    create_sidebar: Callable[[], QWidget]
    pipeline_prep_panel_cls: type
    muter_panel_cls: type
    extractor_panel_cls: type
    beat_tempo_panel_cls: type
    plot_panel_cls: type
    histogram_panel_cls: type
    npvi_group_panel_cls: type
    analysis_step_panel_cls: type
    new_analysis_specs: Sequence[dict]
    assoc_rule_panel_cls: type
    per_file_settings_manager_cls: type
    preset_manager: Any


def _monospace_font() -> QFont:
    return QFont("Menlo" if platform.system() == "Darwin" else "Consolas", 10)


def _apply_step_panel_surface(panel: QWidget, bg: str) -> None:
    if not isinstance(panel, QScrollArea):
        return

    panel.setFrameShape(QFrame.Shape.NoFrame)
    panel.setStyleSheet(
        f"QScrollArea {{ background-color: {bg}; border: none; }}"
        f"QAbstractScrollArea::viewport {{ background-color: {bg}; }}"
    )

    viewport = panel.viewport()
    viewport.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    viewport.setAutoFillBackground(True)
    viewport_palette = viewport.palette()
    viewport_palette.setColor(viewport.backgroundRole(), QColor(bg))
    viewport.setPalette(viewport_palette)

    content = panel.widget()
    if content is None:
        return
    content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    content.setAutoFillBackground(True)
    content.setStyleSheet(f"background-color: {bg};")
    content_palette = content.palette()
    content_palette.setColor(content.backgroundRole(), QColor(bg))
    content.setPalette(content_palette)


def build_main_window_shell(window, deps: MainWindowShellDeps) -> None:
    central = QWidget()
    central.setObjectName("PipelineCentral")
    central.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    window.setCentralWidget(central)
    root_layout = QVBoxLayout(central)
    root_layout.setContentsMargins(10, 8, 10, 6)
    root_layout.setSpacing(8)

    top_bar = QHBoxLayout()
    top_bar.setContentsMargins(8, 6, 8, 6)
    title = QLabel("Bioacoustics Rhythm Pipeline")
    title.setFont(QFont("", 16, QFont.Weight.Bold))
    title.setStyleSheet(f"color: {deps.text}; background: transparent;")
    top_bar.addWidget(title)
    top_bar.addStretch()

    window.preview_btn = QPushButton("  Open Preview  ")
    window.preview_btn.setFont(QFont("", 12, QFont.Weight.Bold))
    window.preview_btn.setMinimumHeight(34)
    window.preview_btn.setStyleSheet(
        f"QPushButton {{ background-color: {deps.bg_widget}; color: {deps.text_dim}; border-radius: 7px; "
        f"padding: 5px 16px; border: 1px solid {deps.border}; font-size: 13px; }} "
        f"QPushButton:hover {{ background-color: {deps.bg_input}; color: {deps.text}; border-color: {deps.accent}; }} "
        f"QPushButton:disabled {{ background-color: {deps.bg}; color: {deps.text_muted}; border-color: {deps.bg_mid}; }}"
    )
    window.preview_btn.clicked.connect(window._toggle_preview)
    top_bar.addWidget(window.preview_btn)
    top_bar.addSpacing(8)

    window.audio_graphs_btn = QPushButton("  3D Graphs  ")
    window.audio_graphs_btn.setFont(QFont("", 12, QFont.Weight.Bold))
    window.audio_graphs_btn.setMinimumHeight(34)
    window.audio_graphs_btn.setStyleSheet(
        f"QPushButton {{ background-color: {deps.bg_widget}; color: {deps.text_dim}; border-radius: 7px; "
        f"padding: 5px 16px; border: 1px solid {deps.border}; font-size: 13px; }} "
        f"QPushButton:hover {{ background-color: {deps.bg_input}; color: {deps.text}; border-color: {deps.accent}; }} "
    )
    window.audio_graphs_btn.clicked.connect(window._open_audio_graphs_companion)
    top_bar.addWidget(window.audio_graphs_btn)
    top_bar.addSpacing(8)

    window.presets_btn = QPushButton("  Presets  ")
    window.presets_btn.setFont(QFont("", 12, QFont.Weight.Bold))
    window.presets_btn.setMinimumHeight(34)
    window.presets_btn.setStyleSheet(
        f"QPushButton {{ background-color: {deps.bg_widget}; color: {deps.text_dim}; border-radius: 7px; "
        f"padding: 5px 16px; border: 1px solid {deps.border}; font-size: 13px; }} "
        f"QPushButton:hover {{ background-color: {deps.bg_input}; color: {deps.text}; border-color: {deps.accent}; }} "
    )
    window.presets_btn.clicked.connect(window._open_presets_dialog)
    top_bar.addWidget(window.presets_btn)
    top_bar.addSpacing(10)

    window.desc_combo = QComboBox()
    window.desc_combo.addItems([
        "Descriptions: Off", "Descriptions: Brief",
        "Descriptions: Detailed", "Descriptions: Novice",
        "Common Audio Terms", "Walkthrough Guide",
    ])
    window.desc_combo.setFixedWidth(210)
    window.desc_combo.setMinimumHeight(34)
    window.desc_combo.setStyleSheet(
        "QComboBox { font-size: 12px; padding: 4px 8px; }"
    )
    window._prev_desc_idx = 0
    window.desc_combo.currentIndexChanged.connect(window._on_desc_changed)
    top_bar.addWidget(window.desc_combo)
    top_bar.addSpacing(10)

    window.run_btn = QPushButton("  Run ▶  ")
    window.run_btn.setFont(QFont("", 13, QFont.Weight.Bold))
    window.run_btn.setMinimumHeight(38)
    window.run_btn.setStyleSheet(
        f"QPushButton {{ background-color: {deps.accent_dim}; color: white; border-radius: 7px; "
        f"padding: 5px 22px; border: none; font-size: 14px; }} "
        f"QPushButton:hover {{ background-color: {deps.accent}; }} "
        f"QPushButton:disabled {{ background-color: {deps.border}; color: {deps.text_muted}; }}"
    )
    window.run_btn.clicked.connect(window._run_pipeline)
    top_bar.addWidget(window.run_btn)
    root_layout.addLayout(top_bar)

    top_sep = QFrame()
    top_sep.setFrameShape(QFrame.Shape.HLine)
    top_sep.setStyleSheet(f"background-color: {deps.border}; max-height: 1px;")
    root_layout.addWidget(top_sep)

    prog_row = QHBoxLayout()
    prog_row.setContentsMargins(16, 4, 16, 4)
    prog_row.addStretch(1)
    window._pipeline_progress_label = QLabel("")
    window._pipeline_progress_label.setStyleSheet(
        f"color: {deps.text_dim}; font-size: 11px; background: transparent;")
    window._pipeline_progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    prog_row.addWidget(window._pipeline_progress_label)
    window._pipeline_progress = QProgressBar()
    window._pipeline_progress.setMinimum(0)
    window._pipeline_progress.setMaximum(100)
    window._pipeline_progress.setValue(0)
    window._pipeline_progress.setTextVisible(True)
    window._pipeline_progress.setFormat("Pipeline: %p%")
    window._pipeline_progress.setFixedHeight(20)
    window._pipeline_progress.setMinimumWidth(420)
    window._pipeline_progress.setMaximumWidth(640)
    window._pipeline_progress.setStyleSheet(
        f"QProgressBar {{ border: 1px solid {deps.border}; border-radius: 5px; "
        f"background-color: {deps.bg_widget}; color: {deps.text}; font-size: 11px; "
        f"text-align: center; padding: 1px; }}"
        f"QProgressBar::chunk {{ background-color: {deps.accent}; border-radius: 4px; }}"
    )
    window._pipeline_progress.hide()
    prog_row.addWidget(window._pipeline_progress, stretch=2)
    prog_row.addStretch(1)
    root_layout.addLayout(prog_row)

    window.body_splitter = QSplitter(Qt.Orientation.Horizontal)
    window.body_splitter.setObjectName("PipelineBodySplitter")
    window.body_splitter.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    window.body_splitter.setHandleWidth(5)

    window.sidebar = deps.create_sidebar()
    window.sidebar.stepSelected.connect(window._show_step)
    window.sidebar_scroll = QScrollArea()
    window.sidebar_scroll.setObjectName("PipelineSidebarScroll")
    window.sidebar_scroll.setWidget(window.sidebar)
    window.sidebar_scroll.setWidgetResizable(False)
    window.sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
    window.sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    window.sidebar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    window.sidebar_scroll.setMinimumWidth(window.sidebar.width() + 20)
    window.sidebar_scroll.setStyleSheet(
        f"QScrollArea {{ background-color: {deps.bg_mid}; border: none; }}"
        f"QAbstractScrollArea::viewport {{ background-color: {deps.bg_mid}; }}"
    )
    window.body_splitter.addWidget(window.sidebar_scroll)

    window.v_splitter = QSplitter(Qt.Orientation.Vertical)
    window.v_splitter.setObjectName("PipelineVerticalSplitter")
    window.v_splitter.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    window.panels_stack = QStackedWidget()
    window.panels_stack.setObjectName("PipelinePanelsStack")
    window.panels_stack.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    if deps.has_onset_editor and deps.onset_editor_panel_cls is not None:
        window.onset_editor_panel = deps.onset_editor_panel_cls()
        window.onset_editor_panel.maximizeRequested.connect(
            window._on_editor_maximize)
    else:
        window.onset_editor_panel = QWidget()
    _apply_step_panel_surface(window.onset_editor_panel, deps.bg)
    window.panels_stack.addWidget(window.onset_editor_panel)

    window.prep_panel = deps.pipeline_prep_panel_cls()
    _apply_step_panel_surface(window.prep_panel, deps.bg)
    window.panels_stack.addWidget(window.prep_panel)
    window.muter_panel = deps.muter_panel_cls()
    _apply_step_panel_surface(window.muter_panel, deps.bg)
    window.panels_stack.addWidget(window.muter_panel)
    window.extractor_panel = deps.extractor_panel_cls()
    _apply_step_panel_surface(window.extractor_panel, deps.bg)
    window.panels_stack.addWidget(window.extractor_panel)
    window.beat_tempo_panel = deps.beat_tempo_panel_cls()
    _apply_step_panel_surface(window.beat_tempo_panel, deps.bg)
    window.panels_stack.addWidget(window.beat_tempo_panel)
    window.plot_panel = deps.plot_panel_cls()
    _apply_step_panel_surface(window.plot_panel, deps.bg)
    window.panels_stack.addWidget(window.plot_panel)
    window.histogram_panel = deps.histogram_panel_cls()
    _apply_step_panel_surface(window.histogram_panel, deps.bg)
    window.panels_stack.addWidget(window.histogram_panel)
    window.npvi_group_panel = deps.npvi_group_panel_cls()
    _apply_step_panel_surface(window.npvi_group_panel, deps.bg)
    window.panels_stack.addWidget(window.npvi_group_panel)

    window.new_analysis_panels = []
    for spec in deps.new_analysis_specs:
        panel = deps.analysis_step_panel_cls(spec)
        _apply_step_panel_surface(panel, deps.bg)
        window.new_analysis_panels.append(panel)
        window.panels_stack.addWidget(panel)

    window.assoc_rule_panel = deps.assoc_rule_panel_cls()
    _apply_step_panel_surface(window.assoc_rule_panel, deps.bg)
    window.panels_stack.addWidget(window.assoc_rule_panel)

    window.per_file_mgr = deps.per_file_settings_manager_cls(window)
    window.muter_panel.attach_per_file_manager(
        window.per_file_mgr,
        open_dialog_callback=window._open_per_file_settings_dialog,
    )
    window.extractor_panel.attach_per_file_manager(
        window.per_file_mgr,
        open_dialog_callback=window._open_per_file_settings_dialog,
    )
    window.prep_panel.per_file_settings_path.line_edit.textChanged.connect(
        window._refresh_per_file_manager)
    window._refresh_per_file_manager(
        window.prep_panel.per_file_settings_path.text())

    window.prep_panel.input_folder.textChanged.connect(window._auto_set_muter_input)
    window.prep_panel.excel_path.textChanged.connect(window._auto_set_onset_editor_excel)
    window.muter_panel.output_folder.textChanged.connect(window._auto_set_step2_input)
    window.muter_panel.output_folder.textChanged.connect(window._auto_set_onset_editor_input)
    window.extractor_panel.audio_folder.textChanged.connect(window._auto_set_beat_tempo_input)
    window.beat_tempo_panel._input_auto_cb.stateChanged.connect(
        window._on_beat_tempo_input_auto_toggled)
    window.extractor_panel.output_excel.textChanged.connect(window._auto_set_beat_tempo_output)
    window.beat_tempo_panel._output_auto_cb.stateChanged.connect(
        window._on_beat_tempo_output_auto_toggled)
    window.extractor_panel.output_excel.textChanged.connect(window._auto_set_step3_input)
    window.extractor_panel.output_excel.textChanged.connect(window._auto_set_step4_input)
    window.extractor_panel.output_excel.textChanged.connect(window._auto_set_step5_input)
    window.extractor_panel.output_excel.textChanged.connect(window._auto_set_onset_editor_excel)
    window.extractor_panel.output_excel.textChanged.connect(window._auto_set_prep_excel)

    window.muter_panel._input_auto_cb.stateChanged.connect(
        window._on_muter_input_auto_toggled)
    window.extractor_panel._input_auto_cb.stateChanged.connect(
        window._on_extractor_input_auto_toggled)
    window.plot_panel._input_auto_cb.stateChanged.connect(
        window._on_plot_input_auto_toggled)
    window.histogram_panel._input_auto_cb.stateChanged.connect(
        window._on_histogram_input_auto_toggled)
    window.npvi_group_panel._input_auto_cb.stateChanged.connect(
        window._on_npvi_input_auto_toggled)
    window.extractor_panel.output_excel.textChanged.connect(
        window._auto_set_step6_input)
    window.assoc_rule_panel._input_auto_cb.stateChanged.connect(
        window._on_assoc_input_auto_toggled)

    window.extractor_panel.output_excel.textChanged.connect(
        window._auto_set_new_analyses_input)
    for panel in window.new_analysis_panels:
        panel._input_auto_cb.stateChanged.connect(
            lambda _state, _panel=panel: window._on_new_analysis_input_auto_toggled(_panel))
    window._auto_set_new_analyses_input(window.extractor_panel.output_excel.text())

    deps.preset_manager.ensure_default_preset(window._build_config())

    window.v_splitter.addWidget(window.panels_stack)
    window.h_splitter = QSplitter(Qt.Orientation.Horizontal)

    config_container = QWidget()
    config_lay = QVBoxLayout(config_container)
    config_lay.setContentsMargins(6, 6, 6, 6)
    config_lay.setSpacing(6)
    config_header = QLabel("  Config Preview")
    config_header.setFont(QFont("", 12, QFont.Weight.Bold))
    config_header.setStyleSheet(
        f"color: {deps.accent}; background: transparent; padding: 4px 0 6px 0;"
    )
    config_lay.addWidget(config_header)
    window.config_preview = QPlainTextEdit()
    window.config_preview.setReadOnly(True)
    window.config_preview.setFont(_monospace_font())
    config_lay.addWidget(window.config_preview)
    window.h_splitter.addWidget(config_container)

    term_container = QWidget()
    term_lay = QVBoxLayout(term_container)
    term_lay.setContentsMargins(6, 6, 6, 6)
    term_lay.setSpacing(6)
    term_header_row = QHBoxLayout()
    term_header = QLabel("  Terminal Output")
    term_header.setFont(QFont("", 12, QFont.Weight.Bold))
    term_header.setStyleSheet(
        f"color: {deps.accent}; background: transparent; padding: 4px 0 6px 0;"
    )
    term_header_row.addWidget(term_header)
    term_header_row.addStretch()
    clear_btn = QPushButton("Clear")
    clear_btn.setFixedWidth(64)
    clear_btn.setStyleSheet(
        "QPushButton { font-size: 11px; padding: 3px 10px; border-radius: 4px; }"
    )
    clear_btn.clicked.connect(lambda: window.terminal_output.clear())
    term_header_row.addWidget(clear_btn)
    term_lay.addLayout(term_header_row)
    window.terminal_output = QPlainTextEdit()
    window.terminal_output.setReadOnly(True)
    window.terminal_output.setFont(_monospace_font())
    term_lay.addWidget(window.terminal_output)
    window.h_splitter.addWidget(term_container)

    window.h_splitter.setSizes([500, 500])
    window.v_splitter.addWidget(window.h_splitter)
    window.v_splitter.setSizes([500, 250])

    window.body_splitter.addWidget(window.v_splitter)
    window.body_splitter.setSizes([280, 800])
    window.body_splitter.setStretchFactor(0, 0)
    window.body_splitter.setStretchFactor(1, 1)
    root_layout.addWidget(window.body_splitter, stretch=1)

    window._editor_maximized = False
    window._saved_body_sizes = []
    window._saved_v_sizes = []

    window.status = window.statusBar()
    window.status.showMessage("Ready")

    window._preview_timer = QTimer(window)
    window._preview_timer.timeout.connect(window._refresh_config_preview)
    window._preview_timer.start(400)

    window._preview_window = None
    window._audio_preview_window = None

    window._preview_refresh_timer = QTimer(window)
    window._preview_refresh_timer.timeout.connect(window._refresh_preview)
    window._preview_refresh_timer.start(500)

    window._load_last_config()
    window.sidebar._select_step(0)
    window.panels_stack.setCurrentIndex(0)
