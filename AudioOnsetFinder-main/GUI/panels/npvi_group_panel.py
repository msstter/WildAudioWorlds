from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    from form_widgets import (
        ColorPickerEdit,
        ExcelDataUsedDialog,
        FilePicker,
        FolderPicker,
        _ALL_IO_SUMMARIES,
        _add_checkbox,
        _add_row,
        _make_auto_set,
        _resolve_auto_config,
        get_form_widget_palette,
    )
    from panel_settings_helpers import (
        _build_settings_preset_section,
        _export_settings_for,
        _import_settings_for,
        _on_saved_settings_selected,
        _save_settings_if_enabled,
    )
except ImportError:
    from GUI.form_widgets import (
        ColorPickerEdit,
        ExcelDataUsedDialog,
        FilePicker,
        FolderPicker,
        _ALL_IO_SUMMARIES,
        _add_checkbox,
        _add_row,
        _make_auto_set,
        _resolve_auto_config,
        get_form_widget_palette,
    )
    from GUI.panel_settings_helpers import (
        _build_settings_preset_section,
        _export_settings_for,
        _import_settings_for,
        _on_saved_settings_selected,
        _save_settings_if_enabled,
    )


def _to_int(text, default):
    try:
        return int(float(str(text).strip()))
    except Exception:
        return default


def _to_float(text, default):
    try:
        return float(str(text).strip())
    except Exception:
        return default


class nPVIGroupPanel(QScrollArea):
    """Settings panel for the nPVI-by-group raincloud plot step."""

    _EXCEL_COLUMNS = [
        {"var_id": "file_name", "column": "File Name", "default": "File Name",
         "description": "Identifies each recording / audio file"},
        {"var_id": "npvi_raw", "column": "nPVI (Isochrony)",
         "default": "nPVI (Isochrony)",
         "description": "Normalised Pairwise Variability Index (raw dataset)"},
        {"var_id": "npvi_stable", "column": "Stable Rhythm nPVI",
         "default": "Stable Rhythm nPVI",
         "description": "nPVI for stable-rhythm subset only"},
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._palette = get_form_widget_palette()
        self.setWidgetResizable(True)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setSpacing(14)
        lay.setContentsMargins(16, 16, 16, 16)

        grp = QGroupBox("Input / Output")
        g = QVBoxLayout(grp)

        self.excel_path = FilePicker("", "Excel files (*.xlsx *.xls)")
        self.excel_path.line_edit.setPlaceholderText(
            "Excel file from Onset Finder output")
        _add_row(g, "Input Excel file", self.excel_path,
                 "Excel workbook produced by Step 3 (Onset Finder).",
                 extended_desc="Path to the .xlsx file containing File Summaries "
                 "with nPVI values.",
                 label_width=140)
        self._input_auto_cb, self._input_auto_desc = _make_auto_set(
            self.excel_path, g,
            "↳ Auto: Set to the <b>Output Excel</b> from Step 3 (Onset Finder)",
            step_name="nPVI Group Plot", io_type="input",
            auto_config={"source_step": "Onset Finder", "source_io": "output",
                         "suffix": "", "use_dirname": False,
                         "use_basename": False})

        self.output_folder = FolderPicker("")
        self.output_folder.line_edit.setPlaceholderText(
            "Output folder for nPVI group plots")
        _add_row(g, "Output folder", self.output_folder,
                 "Folder where nPVI group plots are saved.",
                 extended_desc="Raincloud plots (half-violin + boxplot + jitter) "
                 "are saved here in the selected format(s).",
                 label_width=140)
        self._output_auto_cb, self._output_auto_desc = _make_auto_set(
            self.output_folder, g,
            "↳ Auto: Plots saved in a '<i>nPVI_Group_Plots</i>' folder alongside "
            "the Input Excel file",
            step_name="nPVI Group Plot", io_type="output",
            auto_config={"source_step": "(this step)", "source_io": "input",
                         "suffix": "nPVI_Group_Plots", "use_dirname": True,
                         "use_basename": False})
        self._output_auto_cb.stateChanged.connect(self._on_output_auto_toggled)

        self._io_summary = QLabel()
        self._io_summary.setWordWrap(True)
        self._io_summary.setStyleSheet(
            f"color: {self._palette.text_dim}; background: transparent; font-size: 11px; "
            f"padding: 4px 6px; border: 1px solid {self._palette.border}; border-radius: 4px;"
        )
        g.addWidget(self._io_summary)
        _ALL_IO_SUMMARIES.append(self._io_summary)
        self._io_summary.hide()

        self._excel_data_btn = QPushButton("  Excel Data Used…  ")
        self._excel_data_btn.setStyleSheet(
            f"QPushButton {{ background-color: {self._palette.bg_widget}; color: {self._palette.text_dim}; "
            f"border: 1px solid {self._palette.border}; border-radius: 5px; padding: 5px 12px; font-size: 11px; }}"
            f"QPushButton:hover {{ background-color: {self._palette.bg_input}; color: {self._palette.text}; border-color: {self._palette.accent}; }}"
        )
        self._excel_data_btn.clicked.connect(self._show_excel_data_used)
        g.addWidget(self._excel_data_btn)

        lay.addWidget(grp)

        _build_settings_preset_section(
            self, lay, "nPVI Group Plot", self.excel_path,
            presets_dict=None)
        self._import_settings_btn.clicked.connect(
            lambda: _import_settings_for(self, "nPVI Group Plot"))
        self._export_settings_btn.clicked.connect(
            lambda: _export_settings_for(self, "nPVI Group Plot"))
        self._saved_settings_combo.currentTextChanged.connect(
            lambda name: _on_saved_settings_selected(self, "nPVI Group Plot", name))

        grp = QGroupBox("Data Source")
        g = QVBoxLayout(grp)
        self.npvi_dataset = QComboBox()
        self.npvi_dataset.addItems(["raw", "stable"])
        _add_row(g, "nPVI dataset", self.npvi_dataset,
                 "Which nPVI values to plot: full data or stable-rhythm subset.",
                 extended_desc="'raw' uses the 'nPVI (Isochrony)' column from the "
                 "full onset set. 'stable' uses the 'Stable Rhythm nPVI' column "
                 "which only includes filtered stable rhythms.")
        lay.addWidget(grp)

        grp = QGroupBox("Group Assignment")
        g = QVBoxLayout(grp)

        self.group_source = QComboBox()
        self.group_source.addItems(["filename_pattern", "mapping_csv", "manual", "excel_column"])
        _add_row(g, "Group source", self.group_source,
                 "How to assign files to groups for the plot.",
                 extended_desc="'filename_pattern' extracts the group name from each "
                 "file name using a regex. 'mapping_csv' loads a CSV file mapping "
                 "file names to group labels. 'manual' uses the manual groups defined below. "
                 "'excel_column' reads group labels from a column in the Excel file.")
        self.group_source.currentTextChanged.connect(self._on_group_source_changed)

        self.group_pattern = QLineEdit(r"(?P<group>[A-Za-z]+)_")
        _add_row(g, "Filename pattern (regex)", self.group_pattern,
                 "Regex with a named capture (?P<group>…) to extract group from filename.",
                 extended_desc="The regex is searched against each file name. The named "
                 "capture group 'group' becomes the group label. Example: "
                 "r'(?P<group>[A-Za-z]+)_' extracts the leading word before underscore.")

        self.group_csv_path = FilePicker("", "CSV files (*.csv)")
        self.group_csv_path.line_edit.setPlaceholderText(
            "CSV with 'File Name' and 'Group' columns")
        _add_row(g, "Mapping CSV file", self.group_csv_path,
                 "External CSV mapping each file name to a group.",
                 extended_desc="Must have columns 'File Name' and 'Group'. Files not "
                 "found in the CSV are labeled with the ungrouped label.")

        self.manual_groups = QLineEdit("")
        self.manual_groups.setPlaceholderText(
            "file1.wav=GroupA, file2.wav=GroupB, ...")
        _add_row(g, "Manual groups", self.manual_groups,
                 "Comma-separated file=group pairs for manual assignment.",
                 extended_desc="Format: 'filename1.wav=Group A, filename2.wav=Group B'. "
                 "Files not listed are labeled with the ungrouped label.")

        self.group_excel_column = QLineEdit("Group")
        self.group_excel_column.setPlaceholderText("Column name in File Summaries sheet")
        _add_row(g, "Excel column name", self.group_excel_column,
                 "Name of the column in the File Summaries sheet containing group labels.",
                 extended_desc="The column must exist in the 'File Summaries' sheet of the "
                 "input Excel file. Each row's value becomes the group label for that file.")

        self.ungrouped_label = QLineEdit("Ungrouped")
        _add_row(g, "Ungrouped label", self.ungrouped_label,
                 "Label for files that don't match any group. Default 'Ungrouped'.",
                 extended_desc="Files that cannot be assigned to a group are placed "
                 "under this label.")

        self.group_order = QLineEdit("")
        self.group_order.setPlaceholderText("e.g. GroupA, GroupB, GroupC")
        _add_row(g, "Group display order", self.group_order,
                 "Comma-separated group names in desired display order. Empty = alphabetical.",
                 extended_desc="Controls the left-to-right order of groups on the x-axis. "
                 "Groups not listed are appended alphabetically. Leave empty to use "
                 "alphabetical order for all groups.")

        lay.addWidget(grp)

        grp = QGroupBox("Figure Dimensions")
        g = QVBoxLayout(grp)
        self.npvi_width = QLineEdit("14")
        _add_row(g, "Width (inches)", self.npvi_width,
                 "Figure width in inches. Default 14.",
                 extended_desc="Wider figures accommodate more groups. "
                 "14 is a good default for 3-6 groups; increase for more.")
        self.npvi_height = QLineEdit("8")
        _add_row(g, "Height (inches)", self.npvi_height,
                 "Figure height in inches. Default 8.",
                 extended_desc="Height of the exported figure. Increase if nPVI "
                 "values span a large range and the violin gets crowded.")
        self.npvi_dpi = QLineEdit("300")
        _add_row(g, "DPI", self.npvi_dpi,
                 "Resolution. 150 = draft, 300 = publication.",
                 extended_desc="Output resolution. 300 DPI is standard for "
                 "publication-quality figures.")
        self.npvi_tight_pad = QLineEdit("1.5")
        _add_row(g, "Tight-layout padding", self.npvi_tight_pad,
                 "Extra padding around figure edges. Default 1.5.",
                 extended_desc="Passed to matplotlib tight_layout(pad=…).")
        self.npvi_bg_color = ColorPickerEdit("#ffffff")
        _add_row(g, "Background color", self.npvi_bg_color,
                 "Background color for the figure. Default white.",
                 extended_desc="Sets background for both figure and axes.")
        lay.addWidget(grp)

        grp = QGroupBox("Raincloud Appearance")
        g = QVBoxLayout(grp)

        self.npvi_violin_alpha = QLineEdit("0.6")
        _add_row(g, "Violin opacity", self.npvi_violin_alpha,
                 "Alpha transparency for the half-violin. Default 0.6.",
                 extended_desc="Controls the transparency of the kernel density "
                 "half-violin shape. Lower values are more translucent.")
        self.npvi_violin_color = ColorPickerEdit("")
        _add_row(g, "Violin color (override)", self.npvi_violin_color,
                 "Single color for all violins. Leave empty to use the palette.",
                 extended_desc="If set, all violins use this color. If empty (default), "
                 "each group gets a distinct color from the palette.")
        self.npvi_violin_width = QLineEdit("0.6")
        _add_row(g, "Violin width", self.npvi_violin_width,
                 "Maximum width of the half-violin density. Default 0.6.",
                 extended_desc="Controls how wide the densest part of the violin "
                 "extends. Increase for more prominent violins.")
        self.npvi_violin_bw = QLineEdit("0.7")
        _add_row(g, "Violin bandwidth", self.npvi_violin_bw,
                 "Kernel density bandwidth adjustment. Default 0.7.",
                 extended_desc="Lower = tighter fit to data (more detail, may be noisy). "
                 "Higher = smoother density estimate.")
        self.npvi_box_width = QLineEdit("0.15")
        _add_row(g, "Box width", self.npvi_box_width,
                 "Width of the boxplot component. Default 0.15.",
                 extended_desc="Width of the boxplot that sits next to the violin. "
                 "Keep smaller than the violin width.")
        self.npvi_box_alpha = QLineEdit("0.5")
        _add_row(g, "Box opacity", self.npvi_box_alpha,
                 "Alpha transparency for boxplot fill. Default 0.5.",
                 extended_desc="Transparency of the boxplot fill color.")
        self.npvi_jitter_size = QLineEdit("12")
        _add_row(g, "Jitter point size", self.npvi_jitter_size,
                 "Size of individual data points. Default 12.",
                 extended_desc="Matplotlib scatter 's' parameter for jittered points.")
        self.npvi_jitter_alpha = QLineEdit("0.7")
        _add_row(g, "Jitter point opacity", self.npvi_jitter_alpha,
                 "Alpha transparency for data points. Default 0.7.",
                 extended_desc="Transparency of the jittered data points.")
        self.npvi_jitter_width = QLineEdit("0.12")
        _add_row(g, "Jitter spread", self.npvi_jitter_width,
                 "Horizontal spread of jittered points. Default 0.12.",
                 extended_desc="Controls how much the points are randomly spread "
                 "horizontally. Increase if points overlap too much.")
        self.npvi_jitter_color = ColorPickerEdit("#333333")
        _add_row(g, "Jitter point color", self.npvi_jitter_color,
                 "Color of data points. Default dark grey #333333.",
                 extended_desc="Color for all jittered data points. Use a dark "
                 "neutral color for visibility against colored violins.")
        self.npvi_palette = QComboBox()
        self.npvi_palette.setEditable(True)
        self.npvi_palette.addItems([
            "Set2", "Set1", "Set3", "Pastel1", "Pastel2",
            "tab10", "tab20", "Paired", "Accent",
            "Dark2", "viridis", "plasma", "coolwarm",
        ])
        _add_row(g, "Color palette", self.npvi_palette,
                 "Matplotlib colormap name or comma-separated hex colors.",
                 extended_desc="Names a matplotlib colormap (e.g. Set2, tab10, viridis) "
                 "or provide comma-separated hex colors (#ff0000, #00ff00, …). "
                 "Each group gets a distinct color from the palette.")
        lay.addWidget(grp)

        grp = QGroupBox("Labels & Text")
        g = QVBoxLayout(grp)
        self.npvi_title = QLineEdit("nPVI by Group")
        _add_row(g, "Plot title", self.npvi_title,
                 "Title displayed above the plot. Default 'nPVI by Group'.",
                 extended_desc="The main title for the figure. Include descriptive "
                 "text about your dataset or analysis.")
        self.npvi_title_fontsize = QLineEdit("16")
        _add_row(g, "Title font size", self.npvi_title_fontsize,
                 "Font size for the title. Default 16.",
                 extended_desc="Font size in points for the figure title.")
        self.npvi_title_pad = QLineEdit("14")
        _add_row(g, "Title padding", self.npvi_title_pad,
                 "Distance (pt) between title and axes. Default 14.",
                 extended_desc="Increase to push the title further from the plot.")
        self.npvi_title_color = ColorPickerEdit("#000000")
        _add_row(g, "Title color", self.npvi_title_color,
                 "Color of the title text. Default black.",
                 extended_desc="Hex color for the figure title.")
        self.npvi_x_label = QLineEdit("")
        _add_row(g, "X-axis label", self.npvi_x_label,
                 "Label for the x-axis. Default empty (groups are self-explanatory).",
                 extended_desc="Optional x-axis label. Leave empty if group names "
                 "on the tick labels are sufficient.")
        self.npvi_y_label = QLineEdit("nPVI")
        _add_row(g, "Y-axis label", self.npvi_y_label,
                 "Label for the y-axis. Default 'nPVI'.",
                 extended_desc="Y-axis label. 'nPVI' is the standard abbreviation.")
        self.npvi_axis_fontsize = QLineEdit("13")
        _add_row(g, "Axis label size", self.npvi_axis_fontsize,
                 "Font size for axis labels. Default 13.",
                 extended_desc="Font size in points for x/y axis labels.")
        self.npvi_label_pad = QLineEdit("10")
        _add_row(g, "Axis label padding", self.npvi_label_pad,
                 "Distance (pt) between axis labels and the axis. Default 10.",
                 extended_desc="Increase to move labels further from tick marks.")
        self.npvi_tick_fontsize = QLineEdit("11")
        _add_row(g, "Tick label size", self.npvi_tick_fontsize,
                 "Font size for tick labels. Default 11.",
                 extended_desc="Font size for group names and numeric ticks.")
        self.npvi_axis_color = ColorPickerEdit("#000000")
        _add_row(g, "Axis label color", self.npvi_axis_color,
                 "Color of axis label text. Default black.",
                 extended_desc="Hex color for x/y axis labels.")
        self.npvi_tick_color = ColorPickerEdit("#000000")
        _add_row(g, "Tick label color", self.npvi_tick_color,
                 "Color of tick label text. Default black.",
                 extended_desc="Hex color for tick labels on both axes.")
        lay.addWidget(grp)

        grp = QGroupBox("Statistics Annotation")
        g = QVBoxLayout(grp)
        self.npvi_show_stats = QCheckBox("Show per-group stats (n, mean, median)")
        self.npvi_show_stats.setChecked(True)
        _add_checkbox(g, self.npvi_show_stats,
                      "Display n, mean, and median below each group.",
                      "Shows a text annotation for each group with the sample "
                      "size, mean, and median nPVI values.")
        self.npvi_stats_fontsize = QLineEdit("9")
        _add_row(g, "Stats font size", self.npvi_stats_fontsize,
                 "Font size for the per-group stats text. Default 9.",
                 extended_desc="Smaller sizes work well to avoid cluttering the plot.")
        lay.addWidget(grp)

        grp = QGroupBox("Reference Lines")
        g = QVBoxLayout(grp)
        self.npvi_ref_lines = QCheckBox("Show horizontal reference lines")
        self.npvi_ref_lines.setChecked(False)
        _add_checkbox(g, self.npvi_ref_lines,
                      "Draw horizontal reference lines at specified nPVI values.",
                      "Overlays horizontal lines at key nPVI thresholds to help "
                      "interpret the rhythmicity of different groups.")
        self.npvi_ref_values = QLineEdit("30, 50")
        _add_row(g, "Reference values", self.npvi_ref_values,
                 "Comma-separated nPVI values for reference lines.",
                 extended_desc="e.g. '30, 50' — 30 nPVI is considered regular/isochronous, "
                 "50+ is considered irregular.")
        self.npvi_ref_labels = QLineEdit("Regular, Irregular")
        _add_row(g, "Reference labels", self.npvi_ref_labels,
                 "Comma-separated labels for each reference line.",
                 extended_desc="Displayed next to the reference lines.")
        self.npvi_ref_color = ColorPickerEdit("#ff0000")
        _add_row(g, "Reference line color", self.npvi_ref_color,
                 "Color for reference lines. Default red.",
                 extended_desc="Color for horizontal reference lines.")
        self.npvi_ref_style = QComboBox()
        self.npvi_ref_style.addItems([
            "dashed (--)", "solid (—)", "dotted (···)", "dashdot (-·)"])
        _add_row(g, "Reference line style", self.npvi_ref_style,
                 "Line style for reference lines. Default dashed.",
                 extended_desc="Visual style of the reference lines.")
        self.npvi_ref_width = QLineEdit("0.9")
        _add_row(g, "Reference line width", self.npvi_ref_width,
                 "Width of reference lines. Default 0.9.",
                 extended_desc="Thickness of the horizontal reference lines.")
        self.npvi_ref_alpha = QLineEdit("0.5")
        _add_row(g, "Reference line opacity", self.npvi_ref_alpha,
                 "Opacity for reference lines. Default 0.5.",
                 extended_desc="Alpha transparency for reference lines.")
        lay.addWidget(grp)

        grp = QGroupBox("Output Format")
        g = QVBoxLayout(grp)
        self.npvi_output_format = QComboBox()
        self.npvi_output_format.addItems(["png", "svg", "pdf", "png+svg"])
        _add_row(g, "File format", self.npvi_output_format,
                 "Output image format. Default PNG.",
                 extended_desc="'png' for raster images, 'svg' for scalable vector, "
                 "'pdf' for print-ready, 'png+svg' for both raster and vector.")
        lay.addWidget(grp)

        lay.addStretch()
        self.setWidget(content)

        self.excel_path.textChanged.connect(self._on_excel_changed)
        self.npvi_dataset.currentTextChanged.connect(self._update_io_summary)
        self.npvi_output_format.currentTextChanged.connect(self._update_io_summary)
        self._update_io_summary()
        self._on_group_source_changed(self.group_source.currentText())

    def _on_excel_changed(self, text):
        if self._output_auto_cb.isChecked():
            cfg = self._output_auto_cb.auto_config
            src = cfg.get("source_step", "(this step)")
            if src in ("(this step)", "nPVI Group Plot") and cfg.get("source_io") == "input":
                resolved = _resolve_auto_config(text, cfg)
                if resolved:
                    self.output_folder.setText(resolved)

    def _on_output_auto_toggled(self, state):
        if bool(state):
            self._on_excel_changed(self.excel_path.text())

    def _on_group_source_changed(self, source):
        self.group_pattern.setEnabled(source == "filename_pattern")
        self.group_csv_path.setEnabled(source == "mapping_csv")
        self.manual_groups.setEnabled(source == "manual")
        self.group_excel_column.setEnabled(source == "excel_column")

    def _update_io_summary(self):
        lines = ["<b>Reads:</b> Excel workbook (.xlsx) from Step 3"]
        out = ["<b>Produces:</b>"]
        fmt = self.npvi_output_format.currentText()
        ds = self.npvi_dataset.currentText()
        desc = f"nPVI by Group raincloud plot ({ds} dataset)"
        if "png" in fmt:
            out.append(f"• {desc} .png")
        if "svg" in fmt:
            out.append(f"• {desc} .svg")
        if "pdf" in fmt:
            out.append(f"• {desc} .pdf")
        self._io_summary.setText("<br>".join(lines + out))

    def _show_excel_data_used(self):
        import copy

        defs = copy.deepcopy(self._EXCEL_COLUMNS)
        overrides = getattr(self, "_excel_col_overrides", {})
        for column_def in defs:
            if column_def["var_id"] in overrides:
                column_def["column"] = overrides[column_def["var_id"]]
        dlg = ExcelDataUsedDialog("nPVI Group Plot", defs, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._excel_col_overrides = dlg.get_columns()

    def save_settings_if_enabled(self):
        return _save_settings_if_enabled(self)

    def get_values(self):
        style_map = {
            "solid (—)": "-",
            "dashed (--)": "--",
            "dotted (···)": ":",
            "dashdot (-·)": "-.",
        }
        manual_map = {}
        text = self.manual_groups.text().strip()
        if text:
            for pair in text.split(","):
                pair = pair.strip()
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    manual_map[key.strip()] = value.strip()
        return {
            "excel_path": self.excel_path.text(),
            "output_folder": self.output_folder.text(),
            "NPVI_GROUP_SOURCE": self.group_source.currentText(),
            "NPVI_GROUP_PATTERN": self.group_pattern.text(),
            "NPVI_GROUP_CSV_PATH": self.group_csv_path.text(),
            "NPVI_MANUAL_GROUPS": manual_map,
            "NPVI_GROUP_EXCEL_COLUMN": self.group_excel_column.text().strip() or "Group",
            "NPVI_UNGROUPED_LABEL": self.ungrouped_label.text(),
            "NPVI_GROUP_ORDER": self.group_order.text().strip(),
            "NPVI_DATASET": self.npvi_dataset.currentText(),
            "NPVI_FIG_WIDTH": _to_float(self.npvi_width.text(), 14),
            "NPVI_FIG_HEIGHT": _to_float(self.npvi_height.text(), 8),
            "NPVI_DPI": _to_int(self.npvi_dpi.text(), 300),
            "NPVI_TIGHT_PAD": _to_float(self.npvi_tight_pad.text(), 1.5),
            "NPVI_BG_COLOR": self.npvi_bg_color.text().strip() or "#ffffff",
            "NPVI_VIOLIN_ALPHA": _to_float(self.npvi_violin_alpha.text(), 0.6),
            "NPVI_VIOLIN_COLOR": self.npvi_violin_color.text().strip(),
            "NPVI_VIOLIN_WIDTH": _to_float(self.npvi_violin_width.text(), 0.6),
            "NPVI_VIOLIN_BANDWIDTH": _to_float(self.npvi_violin_bw.text(), 0.7),
            "NPVI_BOX_WIDTH": _to_float(self.npvi_box_width.text(), 0.15),
            "NPVI_BOX_ALPHA": _to_float(self.npvi_box_alpha.text(), 0.5),
            "NPVI_JITTER_SIZE": _to_float(self.npvi_jitter_size.text(), 12),
            "NPVI_JITTER_ALPHA": _to_float(self.npvi_jitter_alpha.text(), 0.7),
            "NPVI_JITTER_WIDTH": _to_float(self.npvi_jitter_width.text(), 0.12),
            "NPVI_JITTER_COLOR": self.npvi_jitter_color.text().strip() or "#333333",
            "NPVI_PALETTE": self.npvi_palette.currentText().strip() or "Set2",
            "NPVI_TITLE": self.npvi_title.text(),
            "NPVI_TITLE_FONTSIZE": _to_int(self.npvi_title_fontsize.text(), 16),
            "NPVI_TITLE_PAD": _to_float(self.npvi_title_pad.text(), 14),
            "NPVI_TITLE_COLOR": self.npvi_title_color.text().strip() or "#000000",
            "NPVI_X_LABEL": self.npvi_x_label.text(),
            "NPVI_Y_LABEL": self.npvi_y_label.text(),
            "NPVI_AXIS_FONTSIZE": _to_int(self.npvi_axis_fontsize.text(), 13),
            "NPVI_LABEL_PAD": _to_float(self.npvi_label_pad.text(), 10),
            "NPVI_TICK_FONTSIZE": _to_int(self.npvi_tick_fontsize.text(), 11),
            "NPVI_AXIS_COLOR": self.npvi_axis_color.text().strip() or "#000000",
            "NPVI_TICK_COLOR": self.npvi_tick_color.text().strip() or "#000000",
            "NPVI_SHOW_STATS": self.npvi_show_stats.isChecked(),
            "NPVI_STATS_FONTSIZE": _to_int(self.npvi_stats_fontsize.text(), 9),
            "NPVI_REF_LINES": self.npvi_ref_lines.isChecked(),
            "NPVI_REF_VALUES": self.npvi_ref_values.text().strip(),
            "NPVI_REF_LABELS": self.npvi_ref_labels.text().strip(),
            "NPVI_REF_COLOR": self.npvi_ref_color.text().strip() or "#ff0000",
            "NPVI_REF_STYLE": style_map.get(self.npvi_ref_style.currentText(), "--"),
            "NPVI_REF_WIDTH": _to_float(self.npvi_ref_width.text(), 0.9),
            "NPVI_REF_ALPHA": _to_float(self.npvi_ref_alpha.text(), 0.5),
            "NPVI_OUTPUT_FORMAT": self.npvi_output_format.currentText(),
        }

    def set_values(self, d):
        style_rev = {
            "-": "solid (—)",
            "--": "dashed (--)",
            ":": "dotted (···)",
            "-.": "dashdot (-·)",
        }
        if "excel_path" in d:
            self.excel_path.setText(str(d["excel_path"]))
        if "output_folder" in d:
            self.output_folder.setText(str(d["output_folder"]))
        self.group_source.setCurrentText(
            str(d.get("NPVI_GROUP_SOURCE", "filename_pattern")))
        self.group_pattern.setText(
            str(d.get("NPVI_GROUP_PATTERN", r"(?P<group>[A-Za-z]+)_")))
        self.group_csv_path.setText(
            str(d.get("NPVI_GROUP_CSV_PATH", "")))
        manual_groups = d.get("NPVI_MANUAL_GROUPS", {})
        if isinstance(manual_groups, dict):
            self.manual_groups.setText(
                ", ".join(f"{key}={value}" for key, value in manual_groups.items()))
        else:
            self.manual_groups.setText(str(manual_groups))
        self.group_excel_column.setText(
            str(d.get("NPVI_GROUP_EXCEL_COLUMN", "Group")))
        self.ungrouped_label.setText(
            str(d.get("NPVI_UNGROUPED_LABEL", "Ungrouped")))
        self.group_order.setText(str(d.get("NPVI_GROUP_ORDER", "")))
        self.npvi_dataset.setCurrentText(
            str(d.get("NPVI_DATASET", "raw")))
        self.npvi_width.setText(str(d.get("NPVI_FIG_WIDTH", 14)))
        self.npvi_height.setText(str(d.get("NPVI_FIG_HEIGHT", 8)))
        self.npvi_dpi.setText(str(d.get("NPVI_DPI", 300)))
        self.npvi_tight_pad.setText(str(d.get("NPVI_TIGHT_PAD", 1.5)))
        self.npvi_bg_color.setText(
            str(d.get("NPVI_BG_COLOR", "#ffffff")))
        self.npvi_violin_alpha.setText(
            str(d.get("NPVI_VIOLIN_ALPHA", 0.6)))
        self.npvi_violin_color.setText(
            str(d.get("NPVI_VIOLIN_COLOR", "")))
        self.npvi_violin_width.setText(
            str(d.get("NPVI_VIOLIN_WIDTH", 0.6)))
        self.npvi_violin_bw.setText(
            str(d.get("NPVI_VIOLIN_BANDWIDTH", 0.7)))
        self.npvi_box_width.setText(str(d.get("NPVI_BOX_WIDTH", 0.15)))
        self.npvi_box_alpha.setText(str(d.get("NPVI_BOX_ALPHA", 0.5)))
        self.npvi_jitter_size.setText(
            str(d.get("NPVI_JITTER_SIZE", 12)))
        self.npvi_jitter_alpha.setText(
            str(d.get("NPVI_JITTER_ALPHA", 0.7)))
        self.npvi_jitter_width.setText(
            str(d.get("NPVI_JITTER_WIDTH", 0.12)))
        self.npvi_jitter_color.setText(
            str(d.get("NPVI_JITTER_COLOR", "#333333")))
        palette = d.get("NPVI_PALETTE", "Set2")
        idx = self.npvi_palette.findText(str(palette))
        if idx >= 0:
            self.npvi_palette.setCurrentIndex(idx)
        else:
            self.npvi_palette.setEditText(str(palette))
        self.npvi_title.setText(
            str(d.get("NPVI_TITLE", "nPVI by Group")))
        self.npvi_title_fontsize.setText(
            str(d.get("NPVI_TITLE_FONTSIZE", 16)))
        self.npvi_title_pad.setText(
            str(d.get("NPVI_TITLE_PAD", 14)))
        self.npvi_title_color.setText(
            str(d.get("NPVI_TITLE_COLOR", "#000000")))
        self.npvi_x_label.setText(str(d.get("NPVI_X_LABEL", "")))
        self.npvi_y_label.setText(
            str(d.get("NPVI_Y_LABEL", "nPVI")))
        self.npvi_axis_fontsize.setText(
            str(d.get("NPVI_AXIS_FONTSIZE", 13)))
        self.npvi_label_pad.setText(
            str(d.get("NPVI_LABEL_PAD", 10)))
        self.npvi_tick_fontsize.setText(
            str(d.get("NPVI_TICK_FONTSIZE", 11)))
        self.npvi_axis_color.setText(
            str(d.get("NPVI_AXIS_COLOR", "#000000")))
        self.npvi_tick_color.setText(
            str(d.get("NPVI_TICK_COLOR", "#000000")))
        self.npvi_show_stats.setChecked(
            bool(d.get("NPVI_SHOW_STATS", True)))
        self.npvi_stats_fontsize.setText(
            str(d.get("NPVI_STATS_FONTSIZE", 9)))
        self.npvi_ref_lines.setChecked(
            bool(d.get("NPVI_REF_LINES", False)))
        self.npvi_ref_values.setText(
            str(d.get("NPVI_REF_VALUES", "30, 50")))
        self.npvi_ref_labels.setText(
            str(d.get("NPVI_REF_LABELS", "Regular, Irregular")))
        self.npvi_ref_color.setText(
            str(d.get("NPVI_REF_COLOR", "#ff0000")))
        self.npvi_ref_style.setCurrentText(
            style_rev.get(d.get("NPVI_REF_STYLE", "--"), "dashed (--)"))
        self.npvi_ref_width.setText(
            str(d.get("NPVI_REF_WIDTH", 0.9)))
        self.npvi_ref_alpha.setText(
            str(d.get("NPVI_REF_ALPHA", 0.5)))
        fmt = d.get("NPVI_OUTPUT_FORMAT", "png")
        idx = self.npvi_output_format.findText(str(fmt))
        if idx >= 0:
            self.npvi_output_format.setCurrentIndex(idx)