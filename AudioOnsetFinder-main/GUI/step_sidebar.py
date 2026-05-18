from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class SidebarPalette:
    accent: str
    accent_hover: str
    accent_dim: str
    bg_mid: str
    bg_widget: str
    border: str
    text: str
    text_dim: str


class StepSidebar(QFrame):
    """Left sidebar with fixed-order step buttons and run-include checkboxes."""

    stepSelected = pyqtSignal(int)

    STEP_NAMES = [
        "Onset Editor",
        "Pipeline Prep",
        "Audio Editor",
        "Onset Finder",
        "Beat & Tempo",
        "Flower Raster Plots",
        "Histogram Generator",
        "nPVI Group Plot",
        "Rhythm Ratio Distributions",
        "KS Test vs. Uniform",
        "Wilcoxon Isochrony",
        "Lag-1 Autocorrelation",
        "Tempo × Ratio Heatmap",
        "Raincloud Metrics",
        "pDFA",
        "Mantel Test",
        "GLMM for Rhythm",
        "PGLS",
        "Association Rule Learning",
    ]

    STEP_DEFAULTS_ON = [
        False, False, True, True, False, True, True, True,
        False, False, False, False, False, False,
        False, False, False, False, False,
    ]

    RUN_TOOLTIPS = [
        "Enable/disable the interactive onset editor.",
        "Pipeline Prep is an overview step — it does not run a script.",
        "Enable/disable the audio editor (noise muting) step.",
        "Enable/disable the rhythm extraction step.",
        "Enable/disable beat tracking and PLP tempo estimation (beat_tempo_step.py).",
        "Enable/disable raster plot generation.",
        "Enable/disable histogram generation.",
        "Enable/disable nPVI raincloud plot by group.",
        "Plot r_k distributions per group (see rhythmRatios.py).",
        "KS test of r_k against a null distribution (see ksTest.py).",
        "Wilcoxon test of isochrony preference (see wilcoxonIsochrony.py).",
        "Lag-1 autocorrelation of IOIs (see lagOneAutocorrelation.py).",
        "2-D density of tempo × r_k (see tempoRatioHeatmap.py).",
        "Raincloud plots for rhythm metrics (see raincloudMetrics.py).",
        "Permuted Discriminant Function Analysis (see pDFA.py).",
        "Mantel / partial Mantel tests (see mantelTest.py).",
        "Generalized Linear Mixed Model for rhythmic responses (see glmmRhythm.py).",
        "Phylogenetic Generalized Least Squares (see pgls.py).",
        "Enable/disable experimental Apriori association-rule mining on the rhythm metrics.",
    ]

    _SECTION_HEADERS = {
        0: "Setup",
        2: "Processing",
        5: "Analyses / Figures",
        8: "Experimental Analyses / Figures",
    }
    _COLLAPSIBLE_SECTION_START = 8

    def __init__(self, folder_picker_cls, default_python: str,
                 palette: SidebarPalette, parent=None):
        super().__init__(parent)
        self._folder_picker_cls = folder_picker_cls
        self._default_python = default_python
        self._palette = palette

        self.setStyleSheet(
            f"StepSidebar {{"
            f"  background-color: {palette.bg_mid};"
            f"  border: 1px solid {palette.border};"
            f"  border-radius: 8px;"
            f"}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(2)

        header = QLabel("Pipeline Steps")
        header.setFont(QFont("", 13, QFont.Weight.Bold))
        header.setStyleSheet(
            f"color: {palette.accent}; background: transparent; padding-bottom: 4px;")
        layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(
            f"background-color: {palette.border}; max-height: 1px;")
        layout.addWidget(sep)
        layout.addSpacing(10)

        self._n_steps = len(self.STEP_NAMES)
        self.checks = [None] * self._n_steps
        self.buttons = [None] * self._n_steps
        self._number_labels = [None] * self._n_steps
        self._exp_container = None
        self._exp_toggle_btn = None
        self._exp_rows = []
        self._experimental_collapsed = True

        exp_lay = None
        for i in range(self._n_steps):
            if i in self._SECTION_HEADERS:
                if i == self._COLLAPSIBLE_SECTION_START:
                    layout.addSpacing(4)
                    toggle, container = self._make_collapsible_header(
                        self._SECTION_HEADERS[i])
                    layout.addWidget(toggle)
                    layout.addWidget(container)
                    self._exp_toggle_btn = toggle
                    self._exp_container = container
                    exp_lay = container.layout()
                else:
                    self._add_section_header(layout, self._SECTION_HEADERS[i])
                    exp_lay = None

            row = self._make_row(i)
            target_lay = exp_lay if exp_lay is not None else layout
            target_lay.addWidget(row)
            if exp_lay is not None:
                self._exp_rows.append(row)

        if self._exp_container is not None:
            self._exp_container.setVisible(False)
            self._update_exp_toggle_caption()

        layout.addStretch()

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(
            f"background-color: {palette.border}; max-height: 1px;")
        layout.addWidget(sep2)
        layout.addSpacing(8)

        py_label = QLabel("Python executable:")
        py_label.setStyleSheet(
            f"color: {palette.text_dim}; font-size: 11px; background: transparent; "
            f"padding-bottom: 2px;")
        layout.addWidget(py_label)
        self.python_picker = folder_picker_cls(default_python)
        self.python_picker.line_edit.setToolTip(
            "Path to the conda environment Python executable used to "
            "run the pipeline."
        )
        self.python_picker._browse_btn.clicked.disconnect()
        self.python_picker._browse_btn.clicked.connect(self._browse_python)
        layout.addWidget(self.python_picker)

        self.setFixedWidth(250)
        self._select_step(0)

    def _add_section_header(self, parent_lay, title):
        parent_lay.addSpacing(6)
        rule = QFrame()
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setFixedHeight(1)
        rule.setStyleSheet(f"background-color: {self._palette.border};")
        parent_lay.addWidget(rule)
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(
            f"color: {self._palette.accent}; background: transparent;"
            f"  font-size: 10px; font-weight: bold;"
            f"  letter-spacing: 0.6px; padding: 4px 2px 2px 2px;"
        )
        parent_lay.addWidget(lbl)

    def _make_collapsible_header(self, title):
        toggle = QPushButton()
        toggle.setCheckable(False)
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.setStyleSheet(
            f"QPushButton {{"
            f"  text-align: left;"
            f"  color: {self._palette.accent}; background: transparent;"
            f"  border: none; border-top: 1px solid {self._palette.border};"
            f"  font-size: 10px; font-weight: bold;"
            f"  letter-spacing: 0.6px;"
            f"  padding: 8px 2px 4px 2px;"
            f"}}"
            f"QPushButton:hover {{ color: {self._palette.accent_hover}; }}"
        )
        toggle.setToolTip(
            "Click to show or hide the experimental analyses. "
            "These are optional, more advanced cross-group analyses."
        )
        toggle._title = title.upper()
        toggle.clicked.connect(self._toggle_experimental)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        c_lay = QVBoxLayout(container)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(2)
        return toggle, container

    def _toggle_experimental(self):
        if self._exp_container is None:
            return
        self._experimental_collapsed = not self._experimental_collapsed
        self._exp_container.setVisible(not self._experimental_collapsed)
        self._update_exp_toggle_caption()

    def _update_exp_toggle_caption(self):
        if self._exp_toggle_btn is None:
            return
        arrow = "▸" if self._experimental_collapsed else "▾"
        self._exp_toggle_btn.setText(
            f"  {arrow}  {self._exp_toggle_btn._title}"
        )

    def set_experimental_collapsed(self, collapsed):
        if self._exp_container is None:
            return
        self._experimental_collapsed = bool(collapsed)
        self._exp_container.setVisible(not self._experimental_collapsed)
        self._update_exp_toggle_caption()

    def _make_row(self, step_idx):
        row = QFrame()
        row.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(2, 5, 2, 5)
        lay.setSpacing(5)

        num_label = QLabel(str(step_idx))
        num_label.setFixedWidth(24)
        num_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num_label.setStyleSheet(
            f"color: {self._palette.text_dim}; background: {self._palette.bg_widget}; "
            f"border: 1px solid {self._palette.border}; border-radius: 4px; "
            f"padding: 2px; font-size: 12px; font-weight: 600;"
        )
        self._number_labels[step_idx] = num_label
        lay.addWidget(num_label)

        cb = QCheckBox()
        cb.setChecked(self.STEP_DEFAULTS_ON[step_idx])
        cb.setToolTip(self.RUN_TOOLTIPS[step_idx])
        self.checks[step_idx] = cb
        lay.addWidget(cb)

        btn = QPushButton(self.STEP_NAMES[step_idx])
        btn.setFlat(True)
        btn.setCheckable(True)
        btn.setStyleSheet(
            f"QPushButton {{ text-align: left; padding: 8px 10px; "
            f"border-radius: 5px; color: {self._palette.text}; font-size: 13px; }}"
            f"QPushButton:checked {{ background-color: {self._palette.accent_dim}; "
            f"color: white; font-weight: 600; }}"
            f"QPushButton:hover:!checked {{ background-color: "
            f"{self._palette.bg_widget}; }}"
        )
        btn.clicked.connect(
            lambda _, idx=step_idx: self._select_step(idx))
        self.buttons[step_idx] = btn
        lay.addWidget(btn, stretch=1)

        return row

    def _browse_python(self):
        start = self.python_picker.text() or "/"
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Python Executable", start)
        if path:
            self.python_picker.setText(path)

    def _select(self, idx):
        self._select_step(idx)

    def _select_step(self, step_idx):
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == step_idx)
        self.stepSelected.emit(step_idx)

    def run_flags(self):
        return [cb.isChecked() for cb in self.checks]

    def _set_run_flag(self, index, value):
        if 0 <= index < len(self.checks):
            self.checks[index].setChecked(bool(value))

    def python_path(self):
        return self.python_picker.text() or self._default_python

    def get_order(self):
        return list(range(self._n_steps))

    def set_order(self, order_list):
        pass
