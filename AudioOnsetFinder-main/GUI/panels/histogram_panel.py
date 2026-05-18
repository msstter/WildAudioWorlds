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


class HistogramPanel(QScrollArea):
    """Settings panel for the Histogram Generator step."""

    _EXCEL_COLUMNS = [
        {"var_id": "file_name", "column": "File Name", "default": "File Name",
         "description": "Identifies each recording / audio file"},
        {"var_id": "rhythm_ratio", "column": "Rhythm Ratio [r_k]",
         "default": "Rhythm Ratio [r_k]",
         "description": "Rhythm ratio values plotted in the histogram"},
        {"var_id": "npvi_raw", "column": "nPVI (Isochrony)",
         "default": "nPVI (Isochrony)",
         "description": "Normalised Pairwise Variability Index (raw dataset)"},
        {"var_id": "entropy_raw", "column": "r_k Entropy (Categorical Measure)",
         "default": "r_k Entropy (Categorical Measure)",
         "description": "Categorical entropy of rhythm ratios (raw dataset)"},
        {"var_id": "cv_raw", "column": "CV of Intervals",
         "default": "CV of Intervals",
         "description": "Coefficient of Variation of inter-onset intervals (raw)"},
        {"var_id": "npvi_stable", "column": "Stable Rhythm nPVI",
         "default": "Stable Rhythm nPVI",
         "description": "nPVI for stable-rhythm subset only"},
        {"var_id": "entropy_stable", "column": "Stable Rhythm Entropy",
         "default": "Stable Rhythm Entropy",
         "description": "Entropy for stable-rhythm subset only"},
        {"var_id": "cv_stable", "column": "Stable Rhythm CV",
         "default": "Stable Rhythm CV",
         "description": "CV of intervals for stable-rhythm subset only"},
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

        self.excel_path = FilePicker(
            "", "Excel files (*.xlsx *.xls)")
        self.excel_path.line_edit.setPlaceholderText(
            "Excel file from Onset Finder output")
        _add_row(g, "Input Excel file", self.excel_path,
                 "Excel workbook produced by Step 3 (Onset Finder).",
                 extended_desc="Path to the .xlsx file containing dyadic event sheets.",
                 label_width=140)
        self._input_auto_cb, self._input_auto_desc = _make_auto_set(
            self.excel_path, g,
            "↳ Auto: Set to the <b>Output Excel</b> from Step 3 (Onset Finder)",
            step_name="Histogram Generator", io_type="input",
            auto_config={"source_step": "Onset Finder", "source_io": "output",
                         "suffix": "", "use_dirname": False,
                         "use_basename": False})

        self.output_folder = FolderPicker("")
        self.output_folder.line_edit.setPlaceholderText(
            "Output folder for histogram images")
        _add_row(g, "Output folder", self.output_folder,
                 "Folder where histogram PNGs are saved.",
                 extended_desc="Individual and combined histogram images are saved here. "
                 "'raw/' and 'stable/' subdirectories are created automatically.",
                 label_width=140)
        self._output_auto_cb, self._output_auto_desc = _make_auto_set(
            self.output_folder, g,
            "↳ Auto: Plots saved in a '<i>HistogramPlots</i>' folder alongside the Input Excel file",
            step_name="Histogram Generator", io_type="output",
            auto_config={"source_step": "(this step)", "source_io": "input",
                         "suffix": "HistogramPlots", "use_dirname": True,
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
            self, lay, "Histogram Generator", self.excel_path,
            presets_dict=None)
        self._import_settings_btn.clicked.connect(
            lambda: _import_settings_for(self, "Histogram Generator"))
        self._export_settings_btn.clicked.connect(
            lambda: _export_settings_for(self, "Histogram Generator"))
        self._saved_settings_combo.currentTextChanged.connect(
            lambda name: _on_saved_settings_selected(self, "Histogram Generator", name))

        grp = QGroupBox("Data Source")
        g = QVBoxLayout(grp)
        self.hist_datasets = QComboBox()
        self.hist_datasets.addItems(["raw + stable", "raw only", "stable only"])
        _add_row(g, "Datasets to plot", self.hist_datasets,
                 "Which dyadic event sheets to generate histograms for.",
                 extended_desc="'raw + stable' generates histograms from both the full onset set "
                 "and the stable-rhythm subset. 'raw only' skips stable plots. "
                 "'stable only' plots only the filtered stable rhythms.")
        lay.addWidget(grp)

        grp = QGroupBox("Figure Dimensions")
        g = QVBoxLayout(grp)
        self.hist_width = QLineEdit("10")
        _add_row(g, "Width (inches)", self.hist_width,
                 "Figure width in inches. Default 10.",
                 extended_desc="Width of the exported PNG figure in inches. Wider figures "
                 "spread bars out, making individual bins easier to read. Typical range: 8–16.")
        self.hist_height = QLineEdit("6")
        _add_row(g, "Height (inches)", self.hist_height,
                 "Figure height in inches. Default 6.",
                 extended_desc="Height of the exported PNG figure in inches. Increase for "
                 "datasets with tall frequency counts so bars are not clipped. Typical range: 5–10.")
        self.hist_dpi = QLineEdit("300")
        _add_row(g, "DPI", self.hist_dpi,
                 "Resolution (dots per inch). 150 = draft, 300 = publication.",
                 extended_desc="Output resolution. 150 DPI is suitable for on-screen review, "
                 "300 DPI is standard for publication-quality figures, 600 DPI for posters.")
        self.hist_tight_pad = QLineEdit("1.08")
        _add_row(g, "Tight-layout padding", self.hist_tight_pad,
                 "Extra padding around figure edges. Default 1.08.",
                 extended_desc="Passed to matplotlib tight_layout(pad=…). Increase to add "
                 "breathing room between axis labels and the figure border.")
        self.hist_bg_color = ColorPickerEdit("#ffffff")
        _add_row(g, "Background color", self.hist_bg_color,
                 "Background color for the figure and axes. Default: white #ffffff.",
                 extended_desc="Sets the background color of both the figure canvas and the "
                 "plot axes area. White is standard for publication; use other colors "
                 "for presentations or stylistic purposes.")
        lay.addWidget(grp)

        grp = QGroupBox("Histogram Appearance")
        g = QVBoxLayout(grp)
        self.hist_bins = QLineEdit("30")
        _add_row(g, "Number of bins", self.hist_bins,
                 "How many bins to split the 0–1 r_k range into. Default 30.",
                 extended_desc="Number of equal-width bins across the 0–1 rhythm ratio range. "
                 "More bins reveal fine structure but can look noisy with small samples. "
                 "15–20 for small datasets, 30 for medium, 50+ for large corpora.")
        self.hist_color = ColorPickerEdit("#2ca02c")
        _add_row(g, "Bar color", self.hist_color,
                 "Color for histogram bars. Default: green #2ca02c.",
                 extended_desc="Fill color for the histogram bars. Choose a hue that contrasts "
                 "with the reference line and isochronous band colors for clarity.")
        self.hist_alpha = QLineEdit("0.7")
        _add_row(g, "Bar opacity (alpha)", self.hist_alpha,
                 "Bar transparency. 0.4 = faded, 0.7 = default, 1.0 = solid.",
                 extended_desc="Alpha transparency for bar fill. Lower values let reference "
                 "lines and the isochronous band show through the bars. 0.7 balances "
                 "bar visibility with background element legibility.")
        self.hist_edge_color = ColorPickerEdit("#000000")
        _add_row(g, "Bar edge color", self.hist_edge_color,
                 "Color of bar outlines. Default black. Type 'none' to remove outlines.",
                 extended_desc="Outline color for each bar. Black provides clear separation "
                 "between adjacent bins. Type 'none' (case-insensitive) to remove outlines "
                 "entirely for a smoother appearance.")
        self.hist_edge_width = QLineEdit("0.8")
        _add_row(g, "Bar edge width", self.hist_edge_width,
                 "Width of bar outlines in points. Default 0.8. Use 0 for no outlines.",
                 extended_desc="Thicker edges make individual bins more distinct but can "
                 "overwhelm plots with many narrow bins. Try 0.5–1.0 for most cases.")
        lay.addWidget(grp)

        grp = QGroupBox("Labels & Text")
        g = QVBoxLayout(grp)
        self.hist_title_size = QLineEdit("14")
        _add_row(g, "Title font size", self.hist_title_size,
                 "Font size of the plot title. Default 14.",
                 extended_desc="Font size in points for the figure title. 12–14 for on-screen "
                 "review, 16–18 for presentation slides, 10–12 for multi-panel figures.")
        self.hist_title_pad = QLineEdit("12")
        _add_row(g, "Title padding", self.hist_title_pad,
                 "Distance (pt) between the title and the top of the axes. Default 12.",
                 extended_desc="Increase to push the title further from the plot area. "
                 "Useful if you have large tick labels that overlap the title.")
        self.hist_axis_size = QLineEdit("12")
        _add_row(g, "Axis label size", self.hist_axis_size,
                 "Font size for axis labels (x and y). Default 12.",
                 extended_desc="Font size in points for the x-axis ('Rhythm Ratio') and "
                 "y-axis ('Frequency') labels. Keep proportional to the title size.")
        self.hist_label_pad = QLineEdit("8")
        _add_row(g, "Axis label padding", self.hist_label_pad,
                 "Distance (pt) between axis labels and the axis line. Default 8.",
                 extended_desc="Increase to move 'Rhythm Ratio' or 'Frequency' further "
                 "from the tick marks.")
        self.hist_tick_size = QLineEdit("10")
        _add_row(g, "Tick label size", self.hist_tick_size,
                 "Font size for the numeric tick labels on both axes. Default 10.",
                 extended_desc="Font size in points for the numbers along each axis. "
                 "Should be slightly smaller than the axis label size for visual hierarchy.")
        self.hist_title_color = ColorPickerEdit("#000000")
        _add_row(g, "Title color", self.hist_title_color,
                 "Color of the plot title text. Default black.",
                 extended_desc="Hex color for the histogram title. Use black for print, or a "
                 "lighter shade if placing plots on dark backgrounds.")
        self.hist_axis_color = ColorPickerEdit("#000000")
        _add_row(g, "Axis label color", self.hist_axis_color,
                 "Color of axis label text (x and y). Default black.",
                 extended_desc="Hex color for the x/y axis labels. Typically matches the "
                 "title color for visual consistency.")
        self.hist_tick_color = ColorPickerEdit("#000000")
        _add_row(g, "Tick label color", self.hist_tick_color,
                 "Color of the numeric tick labels on both axes. Default black.",
                 extended_desc="Hex color for the numbers along each axis. Use a slightly "
                 "lighter shade than the axis labels if you want a visual hierarchy.")
        self.hist_title_prefix = QLineEdit("r_k Distribution")
        _add_row(g, "Title prefix", self.hist_title_prefix,
                 "Text before the auto-generated dataset and filename. Default 'r_k Distribution'.",
                 extended_desc="The full title is: PREFIX (Dataset): Filename SUFFIX. "
                 "Change the prefix to customise the leading text of every histogram title.")
        self.hist_title_suffix = QLineEdit("")
        _add_row(g, "Title suffix", self.hist_title_suffix,
                 "Text appended after the filename in the title. Default empty.",
                 extended_desc="The full title is: PREFIX (Dataset): Filename SUFFIX. "
                 "Use this to add a trailing note, e.g. ' — Draft' or ' (v2)'.")
        self.hist_combined_title_prefix = QLineEdit("Combined Corpus r_k Distribution")
        _add_row(g, "Combined title prefix", self.hist_combined_title_prefix,
                 "Title prefix for the combined corpus histogram. Default 'Combined Corpus r_k Distribution'.",
                 extended_desc="The combined histogram title is: PREFIX (Dataset) SUFFIX. "
                 "Change this to customise the leading text of the combined histogram's title.")
        self.hist_x_label = QLineEdit("Rhythm Ratio (r_k)")
        _add_row(g, "X-axis label", self.hist_x_label,
                 "Label for the horizontal axis. Default 'Rhythm Ratio (r_k)'.",
                 extended_desc="This label is the same across all histograms. "
                 "Edit directly to change the x-axis text on every generated figure.")
        self.hist_y_label = QLineEdit("Frequency (Number of Dyads)")
        _add_row(g, "Y-axis label", self.hist_y_label,
                 "Label for the vertical axis. Default 'Frequency (Number of Dyads)'.",
                 extended_desc="This label is the same across all histograms. "
                 "Edit directly to change the y-axis text on every generated figure.")
        lay.addWidget(grp)

        grp = QGroupBox("Reference Lines")
        g = QVBoxLayout(grp)
        self.hist_ref_lines = QCheckBox("Show ratio reference lines")
        self.hist_ref_lines.setChecked(True)
        _add_checkbox(g, self.hist_ref_lines,
                      "Draw vertical lines at key rhythm ratios.",
                      "Overlays dashed lines at r_k values to highlight simple small-integer "
                      "timing ratios. Useful for spotting whether rhythms cluster near "
                      "isochronous or other canonical patterns.")
        self.hist_ref_ratios = QLineEdit("0.25, 0.333, 0.5, 0.666, 0.75")
        _add_row(g, "Reference ratios", self.hist_ref_ratios,
                 "Comma-separated r_k values where vertical lines are drawn.",
                 extended_desc="Default: 0.25 (1:3), 0.333 (1:2), 0.5 (1:1), "
                 "0.666 (2:1), 0.75 (3:1). Add or remove ratios to match "
                 "your analysis — e.g. add 0.4 or 0.6 for swing-like rhythms.")
        self.hist_ref_labels = QLineEdit("1:3, 1:2, 1:1, 2:1, 3:1")
        _add_row(g, "Reference labels", self.hist_ref_labels,
                 "Comma-separated labels for each reference line.",
                 extended_desc="Matching labels displayed at the top of each reference line. "
                 "Must have the same number of entries as Reference ratios.")
        self.hist_ref_color = ColorPickerEdit("#ff0000")
        _add_row(g, "Reference line color", self.hist_ref_color,
                 "Color for the ratio reference lines. Default: red.",
                 extended_desc="Color for all vertical ratio reference lines. Choose a hue that "
                 "stands out against the bar color. Red is a common choice for annotations.")
        self.hist_ref_style = QComboBox()
        self.hist_ref_style.addItems(["dashed (--)", "solid (—)", "dotted (···)", "dashdot (-·)"])
        _add_row(g, "Reference line style", self.hist_ref_style,
                 "Style for the ratio reference lines. Default dashed.",
                 extended_desc="'dashed' (default) is visually distinct from bar edges. "
                 "'dotted' is subtler for dense plots. 'solid' for maximum emphasis.")
        self.hist_ref_width = QLineEdit("0.9")
        _add_row(g, "Reference line width", self.hist_ref_width,
                 "Width of the reference lines in points. Default 0.9.",
                 extended_desc="Thickness of the vertical reference lines. 0.5–1 = subtle, "
                 "1.5–2 = prominent. Keep thinner than bar edge width to avoid visual clutter.")
        self.hist_ref_alpha = QLineEdit("0.5")
        _add_row(g, "Reference line opacity", self.hist_ref_alpha,
                 "Opacity for reference lines. Default 0.5.",
                 extended_desc="Alpha transparency for reference lines. 0.3 = faint background "
                 "guides, 0.5 = balanced default, 0.8–1.0 = bold emphasis.")
        lay.addWidget(grp)

        grp = QGroupBox("Isochronous Band")
        g = QVBoxLayout(grp)
        self.hist_iso_band = QCheckBox("Show isochronous band")
        self.hist_iso_band.setChecked(True)
        _add_checkbox(g, self.hist_iso_band,
                      "Shade the isochronous region (r_k ≈ 0.5) with a translucent band.",
                      "Shades the region between the low/high bounds to visually mark the "
                      "isochronous zone. Helps quickly assess how much of the distribution "
                      "falls near 1:1 timing.")
        self.hist_iso_low = QLineEdit("0.45")
        _add_row(g, "Band lower bound", self.hist_iso_low,
                 "Lower bound of the isochronous shaded region. Default 0.45.",
                 extended_desc="r_k values at or above this threshold fall within the isochronous "
                 "band. 0.45 (default) captures ratios close to 1:1. Widen to 0.40 for a more "
                 "permissive isochrony definition; narrow to 0.48 for a stricter one.")
        self.hist_iso_high = QLineEdit("0.55")
        _add_row(g, "Band upper bound", self.hist_iso_high,
                 "Upper bound of the isochronous shaded region. Default 0.55.",
                 extended_desc="r_k values at or below this threshold fall within the isochronous "
                 "band. 0.55 (default) with a lower bound of 0.45 gives a 10-percentage-point "
                 "window around perfect isochrony (r_k = 0.5).")
        self.hist_iso_color = ColorPickerEdit("#808080")
        _add_row(g, "Band color", self.hist_iso_color,
                 "Fill color for the isochronous band. Default grey #808080.",
                 extended_desc="A neutral grey keeps the band unobtrusive. Use a warm or cool "
                 "tint if you want to draw more attention to the isochronous zone.")
        self.hist_iso_alpha = QLineEdit("0.15")
        _add_row(g, "Band opacity", self.hist_iso_alpha,
                 "Opacity of the isochronous band. Default 0.15.",
                 extended_desc="Low opacity ensures the band is a subtle background highlight "
                 "rather than obscuring the histogram bars. Increase to 0.25–0.35 if you want "
                 "the isochronous zone to stand out more.")
        lay.addWidget(grp)

        grp = QGroupBox("Statistics Annotation")
        g = QVBoxLayout(grp)
        self.hist_show_stats = QCheckBox("Show summary statistics box")
        self.hist_show_stats.setChecked(True)
        _add_checkbox(g, self.hist_show_stats,
                      "Overlay the nPVI, Entropy, and CV stats in the corner of each plot.",
                      "Displays a text box with summary metrics from the File Summaries sheet "
                      "so each histogram is self-contained. Disable for cleaner figures.")
        self.hist_stats_pos = QComboBox()
        self.hist_stats_pos.addItems([
            "upper right", "upper left", "lower right", "lower left",
        ])
        _add_row(g, "Stats box position", self.hist_stats_pos,
                 "Corner where the statistics box is anchored. Default 'upper right'.",
                 extended_desc="If the box overlaps bars, move it to a different corner. "
                 "'lower right' or 'lower left' work well when most counts are high.")
        self.hist_stats_fontsize = QLineEdit("11")
        _add_row(g, "Stats font size", self.hist_stats_fontsize,
                 "Font size inside the statistics box. Default 11.",
                 extended_desc="Font size for the nPVI, Entropy, and CV values displayed in "
                 "the stats box. Reduce to 9–10 if the box is too large; increase for slides.")
        self.hist_stats_bg = ColorPickerEdit("#ffffff")
        _add_row(g, "Stats box background", self.hist_stats_bg,
                 "Background color of the stats box. Default white.",
                 extended_desc="Fill color behind the statistics text. White provides maximum "
                 "contrast. Use a light tint to match your figure's colour scheme.")
        self.hist_stats_text_color = ColorPickerEdit("#000000")
        _add_row(g, "Stats text color", self.hist_stats_text_color,
                 "Color of the text inside the statistics box. Default black.",
                 extended_desc="Hex color for the nPVI, Entropy, and CV text. Use black "
                 "on a white/light background for maximum readability.")
        self.hist_stats_alpha = QLineEdit("0.9")
        _add_row(g, "Stats box opacity", self.hist_stats_alpha,
                 "Background opacity of the stats box. Default 0.9.",
                 extended_desc="Transparency of the stats box background. 0.9 = nearly opaque "
                 "(default), ensuring text is readable over bars. Reduce to 0.6–0.7 if you "
                 "want to see histogram bars through the box.")
        lay.addWidget(grp)

        grp = QGroupBox("Combined Corpus Plot")
        g = QVBoxLayout(grp)
        self.hist_combined = QCheckBox("Generate combined corpus histogram")
        self.hist_combined.setChecked(True)
        _add_checkbox(g, self.hist_combined,
                      "Create an additional histogram combining all files.",
                      "Generates one extra figure that pools every r_k value from all "
                      "recordings into a single histogram. Useful for seeing overall "
                      "corpus-level rhythm ratio distributions.")
        lay.addWidget(grp)

        lay.addStretch()
        self.setWidget(content)

        self.excel_path.textChanged.connect(self._on_excel_changed)
        self.hist_datasets.currentTextChanged.connect(self._update_io_summary)
        self.hist_combined.stateChanged.connect(self._update_io_summary)
        self._update_io_summary()

    def _on_excel_changed(self, text):
        if self._output_auto_cb.isChecked():
            cfg = self._output_auto_cb.auto_config
            src = cfg.get("source_step", "(this step)")
            if src in ("(this step)", "Histogram Generator") and cfg.get("source_io") == "input":
                resolved = _resolve_auto_config(text, cfg)
                if resolved:
                    self.output_folder.setText(resolved)

    def _on_output_auto_toggled(self, state):
        if bool(state):
            self._on_excel_changed(self.excel_path.text())

    def _update_io_summary(self):
        lines = ["<b>Reads:</b> Excel workbook (.xlsx) from Step 3"]
        out = ["<b>Produces:</b>"]
        ds = self.hist_datasets.currentText()
        if "raw" in ds:
            out.append("• Per-file histogram .png → raw/ subfolder")
        if "stable" in ds:
            out.append("• Per-file histogram .png → stable/ subfolder")
        if self.hist_combined.isChecked():
            out.append("• Combined corpus histogram .png")
        self._io_summary.setText("<br>".join(lines + out))

    def _show_excel_data_used(self):
        import copy

        defs = copy.deepcopy(self._EXCEL_COLUMNS)
        overrides = getattr(self, "_excel_col_overrides", {})
        for column_def in defs:
            if column_def["var_id"] in overrides:
                column_def["column"] = overrides[column_def["var_id"]]
        dlg = ExcelDataUsedDialog("Histogram Generator", defs, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._excel_col_overrides = dlg.get_columns()

    def save_settings_if_enabled(self):
        """Called by MainWindow._run_pipeline to auto-save settings."""
        return _save_settings_if_enabled(self)

    def get_values(self):
        ds_map = {"raw + stable": ("raw", "stable"), "raw only": ("raw",), "stable only": ("stable",)}
        style_map = {"solid (—)": "-", "dashed (--)": "--", "dotted (···)": ":", "dashdot (-·)": "-."}
        stats_anchor = {
            "upper right": (0.97, 0.95, "right", "top"),
            "upper left": (0.03, 0.95, "left", "top"),
            "lower right": (0.97, 0.05, "right", "bottom"),
            "lower left": (0.03, 0.05, "left", "bottom"),
        }
        pos_key = self.hist_stats_pos.currentText()
        sx, sy, sha, sva = stats_anchor.get(pos_key, (0.97, 0.95, "right", "top"))
        edge_text = self.hist_edge_color.text().strip()
        return {
            "excel_path": self.excel_path.text(),
            "output_folder": self.output_folder.text(),
            "HIST_DATASETS": list(ds_map.get(self.hist_datasets.currentText(), ("raw", "stable"))),
            "HIST_FIG_WIDTH": _to_float(self.hist_width.text(), 10),
            "HIST_FIG_HEIGHT": _to_float(self.hist_height.text(), 6),
            "HIST_DPI": _to_int(self.hist_dpi.text(), 300),
            "HIST_TIGHT_PAD": _to_float(self.hist_tight_pad.text(), 1.08),
            "HIST_BG_COLOR": self.hist_bg_color.text().strip() or "#ffffff",
            "HIST_BINS": _to_int(self.hist_bins.text(), 30),
            "HIST_COLOR": self.hist_color.text().strip() or "#2ca02c",
            "HIST_ALPHA": _to_float(self.hist_alpha.text(), 0.7),
            "HIST_EDGE_COLOR": edge_text if edge_text else "black",
            "HIST_EDGE_WIDTH": _to_float(self.hist_edge_width.text(), 0.8),
            "HIST_TITLE_FONTSIZE": _to_int(self.hist_title_size.text(), 14),
            "HIST_TITLE_PAD": _to_float(self.hist_title_pad.text(), 12),
            "HIST_AXIS_FONTSIZE": _to_int(self.hist_axis_size.text(), 12),
            "HIST_LABEL_PAD": _to_float(self.hist_label_pad.text(), 8),
            "HIST_TICK_FONTSIZE": _to_int(self.hist_tick_size.text(), 10),
            "HIST_TITLE_COLOR": self.hist_title_color.text().strip() or "#000000",
            "HIST_AXIS_COLOR": self.hist_axis_color.text().strip() or "#000000",
            "HIST_TICK_COLOR": self.hist_tick_color.text().strip() or "#000000",
            "HIST_TITLE_PREFIX": self.hist_title_prefix.text(),
            "HIST_TITLE_SUFFIX": self.hist_title_suffix.text(),
            "HIST_COMBINED_TITLE_PREFIX": self.hist_combined_title_prefix.text(),
            "HIST_X_LABEL": self.hist_x_label.text(),
            "HIST_Y_LABEL": self.hist_y_label.text(),
            "HIST_REF_LINES": self.hist_ref_lines.isChecked(),
            "HIST_REF_RATIOS": self.hist_ref_ratios.text().strip(),
            "HIST_REF_LABELS": self.hist_ref_labels.text().strip(),
            "HIST_REF_COLOR": self.hist_ref_color.text().strip() or "#ff0000",
            "HIST_REF_STYLE": style_map.get(self.hist_ref_style.currentText(), "--"),
            "HIST_REF_WIDTH": _to_float(self.hist_ref_width.text(), 0.9),
            "HIST_REF_ALPHA": _to_float(self.hist_ref_alpha.text(), 0.5),
            "HIST_ISO_BAND": self.hist_iso_band.isChecked(),
            "HIST_ISO_LOW": _to_float(self.hist_iso_low.text(), 0.45),
            "HIST_ISO_HIGH": _to_float(self.hist_iso_high.text(), 0.55),
            "HIST_ISO_COLOR": self.hist_iso_color.text().strip() or "#808080",
            "HIST_ISO_ALPHA": _to_float(self.hist_iso_alpha.text(), 0.15),
            "HIST_SHOW_STATS": self.hist_show_stats.isChecked(),
            "HIST_STATS_POS": pos_key,
            "HIST_STATS_X": sx,
            "HIST_STATS_Y": sy,
            "HIST_STATS_HA": sha,
            "HIST_STATS_VA": sva,
            "HIST_STATS_FONTSIZE": _to_int(self.hist_stats_fontsize.text(), 11),
            "HIST_STATS_BG": self.hist_stats_bg.text().strip() or "#ffffff",
            "HIST_STATS_TEXT_COLOR": self.hist_stats_text_color.text().strip() or "#000000",
            "HIST_STATS_ALPHA": _to_float(self.hist_stats_alpha.text(), 0.9),
            "HIST_COMBINED": self.hist_combined.isChecked(),
        }

    def set_values(self, d):
        if "excel_path" in d:
            self.excel_path.setText(str(d["excel_path"]))
        if "output_folder" in d:
            self.output_folder.setText(str(d["output_folder"]))
        ds_rev = {"raw,stable": "raw + stable", "raw": "raw only", "stable": "stable only"}
        style_rev = {"-": "solid (—)", "--": "dashed (--)", ":": "dotted (···)", "-.": "dashdot (-·)"}
        ds_val = d.get("HIST_DATASETS", ["raw", "stable"])
        ds_key = ",".join(ds_val) if isinstance(ds_val, list) else str(ds_val)
        self.hist_datasets.setCurrentText(ds_rev.get(ds_key, "raw + stable"))
        self.hist_width.setText(str(d.get("HIST_FIG_WIDTH", 10)))
        self.hist_height.setText(str(d.get("HIST_FIG_HEIGHT", 6)))
        self.hist_dpi.setText(str(d.get("HIST_DPI", 300)))
        self.hist_tight_pad.setText(str(d.get("HIST_TIGHT_PAD", 1.08)))
        self.hist_bg_color.setText(str(d.get("HIST_BG_COLOR", "#ffffff")))
        self.hist_bins.setText(str(d.get("HIST_BINS", 30)))
        self.hist_color.setText(str(d.get("HIST_COLOR", "#2ca02c")))
        self.hist_alpha.setText(str(d.get("HIST_ALPHA", 0.7)))
        self.hist_edge_color.setText(str(d.get("HIST_EDGE_COLOR", "black")))
        self.hist_edge_width.setText(str(d.get("HIST_EDGE_WIDTH", 0.8)))
        self.hist_title_size.setText(str(d.get("HIST_TITLE_FONTSIZE", 14)))
        self.hist_title_pad.setText(str(d.get("HIST_TITLE_PAD", 12)))
        self.hist_axis_size.setText(str(d.get("HIST_AXIS_FONTSIZE", 12)))
        self.hist_label_pad.setText(str(d.get("HIST_LABEL_PAD", 8)))
        self.hist_tick_size.setText(str(d.get("HIST_TICK_FONTSIZE", 10)))
        self.hist_title_color.setText(str(d.get("HIST_TITLE_COLOR", "#000000")))
        self.hist_axis_color.setText(str(d.get("HIST_AXIS_COLOR", "#000000")))
        self.hist_tick_color.setText(str(d.get("HIST_TICK_COLOR", "#000000")))
        self.hist_title_prefix.setText(str(d.get("HIST_TITLE_PREFIX", "r_k Distribution")))
        self.hist_title_suffix.setText(str(d.get("HIST_TITLE_SUFFIX", "")))
        self.hist_combined_title_prefix.setText(str(d.get("HIST_COMBINED_TITLE_PREFIX", "Combined Corpus r_k Distribution")))
        self.hist_x_label.setText(str(d.get("HIST_X_LABEL", "Rhythm Ratio (r_k)")))
        self.hist_y_label.setText(str(d.get("HIST_Y_LABEL", "Frequency (Number of Dyads)")))
        self.hist_ref_lines.setChecked(bool(d.get("HIST_REF_LINES", False)))
        self.hist_ref_ratios.setText(str(d.get("HIST_REF_RATIOS", "")))
        self.hist_ref_labels.setText(str(d.get("HIST_REF_LABELS", "")))
        self.hist_ref_color.setText(str(d.get("HIST_REF_COLOR", "#ff0000")))
        self.hist_ref_style.setCurrentText(style_rev.get(d.get("HIST_REF_STYLE", "--"), "dashed (--)"))
        self.hist_ref_width.setText(str(d.get("HIST_REF_WIDTH", 0.9)))
        self.hist_ref_alpha.setText(str(d.get("HIST_REF_ALPHA", 0.5)))
        self.hist_iso_band.setChecked(bool(d.get("HIST_ISO_BAND", False)))
        self.hist_iso_low.setText(str(d.get("HIST_ISO_LOW", 0.45)))
        self.hist_iso_high.setText(str(d.get("HIST_ISO_HIGH", 0.55)))
        self.hist_iso_color.setText(str(d.get("HIST_ISO_COLOR", "#808080")))
        self.hist_iso_alpha.setText(str(d.get("HIST_ISO_ALPHA", 0.15)))
        self.hist_show_stats.setChecked(bool(d.get("HIST_SHOW_STATS", True)))
        self.hist_stats_pos.setCurrentText(str(d.get("HIST_STATS_POS", "upper right")))
        self.hist_stats_fontsize.setText(str(d.get("HIST_STATS_FONTSIZE", 11)))
        self.hist_stats_bg.setText(str(d.get("HIST_STATS_BG", "#ffffff")))
        self.hist_stats_text_color.setText(str(d.get("HIST_STATS_TEXT_COLOR", "#000000")))
        self.hist_stats_alpha.setText(str(d.get("HIST_STATS_ALPHA", 0.9)))
        self.hist_combined.setChecked(bool(d.get("HIST_COMBINED", False)))