from __future__ import annotations

import json

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
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
        get_form_widget_project_root,
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
        get_form_widget_project_root,
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


class PlotPanel(QScrollArea):
    """Settings panel for the Flower Raster Plots step."""

    _EXCEL_COLUMNS = [
        {"var_id": "file_name", "column": "File Name", "default": "File Name",
         "description": "Identifies each recording / audio file"},
        {"var_id": "cycle_duration", "column": "Cycle Duration [cd] (ms)",
         "default": "Cycle Duration [cd] (ms)",
         "description": "Duration of each rhythmic cycle (y-axis sorting)"},
        {"var_id": "rhythm_ratio", "column": "Rhythm Ratio [r_k]",
         "default": "Rhythm Ratio [r_k]",
         "description": "Ratio used for inter-onset boundary calculation"},
        {"var_id": "short_interval", "column": "Short Interval [i_s] (ms)",
         "default": "Short Interval [i_s] (ms)",
         "description": "Shorter of the two intervals (left scatter)"},
        {"var_id": "long_interval", "column": "Long Interval [i_l] (ms)",
         "default": "Long Interval [i_l] (ms)",
         "description": "Longer of the two intervals (right scatter)"},
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
                 extended_desc="Path to the .xlsx file containing 'Dyadic Events (For Plots)' "
                 "and 'Dyadic Events (Stable Rhythms)' sheets.",
                 label_width=140)
        self._input_auto_cb, self._input_auto_desc = _make_auto_set(
            self.excel_path, g,
            "↳ Auto: Set to the <b>Output Excel</b> from Step 3 (Onset Finder)",
            step_name="Flower Raster Plots", io_type="input",
            auto_config={"source_step": "Onset Finder", "source_io": "output",
                         "suffix": "", "use_dirname": False,
                         "use_basename": False})

        self.output_folder = FolderPicker("")
        self.output_folder.line_edit.setPlaceholderText(
            "Output folder for raster plot images")
        _add_row(g, "Output folder", self.output_folder,
                 "Folder where raster plot PNGs are saved.",
                 extended_desc="Individual and combined raster plot images are saved here. "
                 "'raw/' and 'stable/' subdirectories are created automatically.",
                 label_width=140)
        self._output_auto_cb, self._output_auto_desc = _make_auto_set(
            self.output_folder, g,
            "↳ Auto: Plots saved in a '<i>RasterPlots</i>' folder alongside the Input Excel file",
            step_name="Flower Raster Plots", io_type="output",
            auto_config={"source_step": "(this step)", "source_io": "input",
                         "suffix": "RasterPlots", "use_dirname": True,
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
            self, lay, "Flower Raster Plots", self.excel_path,
            presets_dict=None)
        self._import_settings_btn.clicked.connect(
            lambda: _import_settings_for(self, "Flower Raster Plots"))
        self._export_settings_btn.clicked.connect(
            lambda: _export_settings_for(self, "Flower Raster Plots"))
        self._saved_settings_combo.currentTextChanged.connect(
            lambda name: _on_saved_settings_selected(self, "Flower Raster Plots", name))

        grp = QGroupBox("Data Source")
        g = QVBoxLayout(grp)
        self.plot_datasets = QComboBox()
        self.plot_datasets.addItems(["raw + stable", "raw only", "stable only"])
        _add_row(g, "Datasets to plot", self.plot_datasets,
                 "Which dyadic event sheets to generate raster plots for.",
                 extended_desc="'raw + stable' generates plots from both the full onset set "
                 "and the stable-rhythm subset. 'raw only' skips stable plots. "
                 "'stable only' plots only the filtered stable rhythms.")
        lay.addWidget(grp)

        grp = QGroupBox("Figure Dimensions")
        g = QVBoxLayout(grp)
        self.raster_width = QLineEdit("10")
        _add_row(g, "Width (inches)", self.raster_width,
                 "Figure width in inches. Default 10.",
                 extended_desc="Width of the exported PNG figure in inches. Increase for "
                 "wider aspect ratios when many dyads are present. Typical range: 8–16.")
        self.raster_height = QLineEdit("8")
        _add_row(g, "Height (inches)", self.raster_height,
                 "Figure height in inches. Default 8.",
                 extended_desc="Height of the exported PNG figure in inches. Increase for "
                 "recordings with a large number of dyadic events. Typical range: 6–14.")
        self.raster_dpi = QLineEdit("300")
        _add_row(g, "DPI", self.raster_dpi,
                 "Resolution (dots per inch). 150 = draft, 300 = publication.",
                 extended_desc="Output resolution. 150 DPI is suitable for on-screen review, "
                 "300 DPI is standard for publication-quality figures, 600 DPI for posters.")
        self.raster_tight_pad = QLineEdit("1.08")
        _add_row(g, "Tight-layout padding", self.raster_tight_pad,
                 "Extra padding around figure edges. Default 1.08.",
                 extended_desc="Passed to matplotlib tight_layout(pad=…). Increase to add "
                 "breathing room between axis labels and the figure border. 0 = no extra "
                 "padding, 2+ = generous margins.")
        self.raster_bg_color = ColorPickerEdit("#ffffff")
        _add_row(g, "Background color", self.raster_bg_color,
                 "Background color for the figure and axes. Default: white #ffffff.",
                 extended_desc="Sets the background color of both the figure canvas and the "
                 "plot axes area. White is standard for publication; use other colors "
                 "for presentations or stylistic purposes.")
        lay.addWidget(grp)

        grp = QGroupBox("Scatter Appearance")
        g = QVBoxLayout(grp)
        self.raster_dot_size = QLineEdit("3")
        _add_row(g, "Dot size (pt²)", self.raster_dot_size,
                 "Marker area in points². 1–3 = dense data, 5–10 = sparse data.",
                 extended_desc="Area of each scatter point in points². Smaller values prevent "
                 "overlap when many dyads are present. Increase for recordings with fewer events "
                 "so individual points remain visible.")
        self.raster_alpha = QLineEdit("0.6")
        _add_row(g, "Opacity (alpha)", self.raster_alpha,
                 "Point transparency. 0.3 = very faded, 0.6 = default, 1.0 = fully opaque.",
                 extended_desc="Alpha transparency for scatter points. Lower values reveal "
                 "density patterns when points overlap heavily. Higher values make sparse "
                 "datasets easier to see.")
        self.raster_color_short = ColorPickerEdit("#1f77b4")
        _add_row(g, "Short-interval color", self.raster_color_short,
                 "Color for the short interval (left side). Default: blue #1f77b4.",
                 extended_desc="Scatter points representing the shorter interval of each dyad "
                 "are drawn in this color. Choose a hue that contrasts clearly with the "
                 "long-interval color for easy visual separation.")
        self.raster_color_long = ColorPickerEdit("#ff7f0e")
        _add_row(g, "Long-interval color", self.raster_color_long,
                 "Color for the long interval (right side). Default: orange #ff7f0e.",
                 extended_desc="Scatter points representing the longer interval of each dyad "
                 "are drawn in this color. Choose a hue that contrasts clearly with the "
                 "short-interval color. Consider colour-blind-friendly palettes for "
                 "publication figures.")
        lay.addWidget(grp)

        grp = QGroupBox("Center Line")
        g = QVBoxLayout(grp)
        self.raster_center_color = ColorPickerEdit("#000000")
        _add_row(g, "Line color", self.raster_center_color,
                 "Color of the vertical center divider. Default black.",
                 extended_desc="The center line at x=0 separates short and long intervals. "
                 "Change this to match your figure background or align with a theme.")
        self.raster_center_width = QLineEdit("1.5")
        _add_row(g, "Line width", self.raster_center_width,
                 "Width of the center divider in points. Default 1.5.",
                 extended_desc="Thickness of the vertical line at x=0 that separates the short "
                 "and long interval sides. 0.5–1 = subtle, 1.5 = default, 2–3 = prominent.")
        self.raster_center_style = QComboBox()
        self.raster_center_style.addItems(["solid (—)", "dashed (--)", "dotted (···)", "dashdot (-·)"])
        _add_row(g, "Line style", self.raster_center_style,
                 "Style of the center divider line.",
                 extended_desc="'solid' = continuous line, 'dashed' = long dashes, "
                 "'dotted' = dots only, 'dashdot' = alternating dashes and dots.")
        lay.addWidget(grp)

        grp = QGroupBox("Labels & Text")
        g = QVBoxLayout(grp)
        self.raster_title_size = QLineEdit("14")
        _add_row(g, "Title font size", self.raster_title_size,
                 "Font size of the plot title. Default 14.",
                 extended_desc="Font size in points for the figure title. 12–14 for on-screen "
                 "review, 16–18 for presentation slides, 10–12 for multi-panel figures.")
        self.raster_title_pad = QLineEdit("12")
        _add_row(g, "Title padding", self.raster_title_pad,
                 "Distance (pt) between the title and the top of the axes. Default 12.",
                 extended_desc="Increase to push the title further from the plot area. "
                 "Useful if you have large tick labels that overlap the title.")
        self.raster_axis_size = QLineEdit("12")
        _add_row(g, "Axis label size", self.raster_axis_size,
                 "Font size for axis labels (x and y). Default 12.",
                 extended_desc="Font size in points for the x-axis ('Interval Duration') and "
                 "y-axis ('Dyadic Events') labels. Keep proportional to the title size.")
        self.raster_label_pad = QLineEdit("8")
        _add_row(g, "Axis label padding", self.raster_label_pad,
                 "Distance (pt) between axis labels and the axis line. Default 8.",
                 extended_desc="Increase to move 'Interval Duration' or 'Dyadic Events' "
                 "further from the tick marks. Useful for avoiding cramped layouts.")
        self.raster_tick_size = QLineEdit("10")
        _add_row(g, "Tick label size", self.raster_tick_size,
                 "Font size for the numeric tick labels on both axes. Default 10.",
                 extended_desc="Font size in points for the numbers along each axis. "
                 "Should be slightly smaller than the axis label size for visual hierarchy.")
        self.raster_title_color = ColorPickerEdit("#000000")
        _add_row(g, "Title color", self.raster_title_color,
                 "Color of the plot title text. Default black.",
                 extended_desc="Hex color for the plot title. Use black for print, or a "
                 "lighter shade if placing plots on dark backgrounds.")
        self.raster_axis_color = ColorPickerEdit("#000000")
        _add_row(g, "Axis label color", self.raster_axis_color,
                 "Color of axis label text (x and y). Default black.",
                 extended_desc="Hex color for the x/y axis labels. Typically matches the "
                 "title color for visual consistency.")
        self.raster_tick_color = ColorPickerEdit("#000000")
        _add_row(g, "Tick label color", self.raster_tick_color,
                 "Color of the numeric tick labels on both axes. Default black.",
                 extended_desc="Hex color for the numbers along each axis. Use a slightly "
                 "lighter shade than the axis labels if you want a visual hierarchy.")
        self.raster_title_prefix = QLineEdit("Rhythm Raster")
        _add_row(g, "Title prefix", self.raster_title_prefix,
                 "Text before the auto-generated dataset and filename. Default 'Rhythm Raster'.",
                 extended_desc="The full title is: PREFIX (Dataset): Filename SUFFIX. "
                 "Change the prefix to customise the leading text of every plot title.")
        self.raster_title_suffix = QLineEdit("")
        _add_row(g, "Title suffix", self.raster_title_suffix,
                 "Text appended after the filename in the title. Default empty.",
                 extended_desc="The full title is: PREFIX (Dataset): Filename SUFFIX. "
                 "Use this to add a trailing note, e.g. ' — Draft' or ' (v2)'.")
        self.raster_combined_title_prefix = QLineEdit("Combined Corpus Rhythm Raster")
        _add_row(g, "Combined title prefix", self.raster_combined_title_prefix,
                 "Title prefix for the combined corpus plot. Default 'Combined Corpus Rhythm Raster'.",
                 extended_desc="The combined plot title is: PREFIX (Dataset) SUFFIX. "
                 "Change this to customise the leading text of the combined plot's title.")
        self.raster_x_label = QLineEdit("Interval Duration (ms)")
        _add_row(g, "X-axis label", self.raster_x_label,
                 "Label for the horizontal axis. Default 'Interval Duration (ms)'.",
                 extended_desc="This label is the same across all raster plots. "
                 "Edit directly to change the x-axis text on every generated figure.")
        self.raster_y_label = QLineEdit("Dyadic Events (Sorted by Cycle Duration)")
        _add_row(g, "Y-axis label", self.raster_y_label,
                 "Label for the vertical axis. Default 'Dyadic Events (Sorted by Cycle Duration)'.",
                 extended_desc="This label is the same across all raster plots. "
                 "Edit directly to change the y-axis text on every generated figure.")
        lay.addWidget(grp)

        grp = QGroupBox("Grid")
        g = QVBoxLayout(grp)
        self.raster_grid = QCheckBox("Show grid")
        self.raster_grid.setChecked(True)
        _add_checkbox(g, self.raster_grid,
                      "Display dashed grid lines behind the scatter plot.",
                      "Overlays grid lines behind the data points to aid visual alignment "
                      "of intervals with axis values. Turn off for a cleaner appearance "
                      "in publication figures.")
        self.raster_grid_alpha = QLineEdit("0.5")
        _add_row(g, "Grid opacity", self.raster_grid_alpha,
                 "Grid line transparency. 0.2 = faint, 0.5 = default, 0.8 = prominent.",
                 extended_desc="Alpha transparency for grid lines. Lower values keep the grid "
                 "unobtrusive so data points remain the visual focus. Higher values make the "
                 "grid easier to read but risk obscuring sparse data.")
        self.raster_grid_color = ColorPickerEdit("#cccccc")
        _add_row(g, "Grid color", self.raster_grid_color,
                 "Color of the grid lines. Default light grey #cccccc.",
                 extended_desc="Light grey keeps the grid visible without competing with "
                 "data colors. Use a darker shade for high-contrast needs or match to your "
                 "figure's background color scheme.")
        self.raster_grid_style = QComboBox()
        self.raster_grid_style.addItems(["dashed (--)", "solid (—)", "dotted (···)", "dashdot (-·)"])
        _add_row(g, "Grid line style", self.raster_grid_style,
                 "Style of the grid lines. Default dashed.",
                 extended_desc="'dashed' (default) is the least visually intrusive. 'dotted' "
                 "is even subtler. 'solid' gives clear alignment guides but can look busy.")
        lay.addWidget(grp)

        grp = QGroupBox("Legend")
        g = QVBoxLayout(grp)
        self.raster_legend_show = QCheckBox("Show legend")
        self.raster_legend_show.setChecked(True)
        _add_checkbox(g, self.raster_legend_show,
                      "Display the color legend identifying short and long intervals.",
                      "Shows a small box labelling the short-interval and long-interval "
                      "colors. Turn off if the legend overlaps data or is not needed "
                      "(e.g. when colours are explained in a figure caption).")
        self.raster_legend_pos = QComboBox()
        self.raster_legend_pos.addItems([
            "upper left", "upper right", "lower left", "lower right",
            "center left", "center right", "upper center", "lower center", "center",
        ])
        _add_row(g, "Legend position", self.raster_legend_pos,
                 "Where to anchor the legend inside the axes. Default 'upper left'.",
                 extended_desc="Choose the corner or edge where the legend box is placed. "
                 "If it overlaps data, try a different position or turn it off.")
        self.raster_legend_size = QLineEdit("10")
        _add_row(g, "Legend font size", self.raster_legend_size,
                 "Font size inside the legend box. Default 10.",
                 extended_desc="Font size in points for the text labels inside the legend. "
                 "Reduce to 8 if the legend box is too large; increase for presentation slides.")
        lay.addWidget(grp)

        grp = QGroupBox("Rhythm Reference Lines")
        g = QVBoxLayout(grp)
        self.raster_ref_lines = QCheckBox("Show rhythm reference lines")
        self.raster_ref_lines.setChecked(False)
        _add_checkbox(g, self.raster_ref_lines,
                      "Draw horizontal lines at key rhythm-ratio cycle durations.",
                      "Overlays horizontal dashed lines at y-positions matching user-defined "
                      "cycle durations, helpful for visualising where particular rhythms sit "
                      "on the sorted raster.")
        self.raster_ref_values = QLineEdit("")
        _add_row(g, "Cycle durations (ms)", self.raster_ref_values,
                 "Comma-separated cycle durations for horizontal reference lines.",
                 extended_desc="Enter one or more cycle durations in milliseconds, separated "
                 "by commas (e.g. '500, 1000, 1500'). A horizontal dashed line will be drawn "
                 "at each of these values on the y-axis.")
        self.raster_ref_labels = QLineEdit("")
        _add_row(g, "Reference labels", self.raster_ref_labels,
                 "Comma-separated labels for each reference line (optional).",
                 extended_desc="Matching labels for the reference lines above (e.g. "
                 "'Fast, Medium, Slow'). If fewer labels than values, extras are unlabelled.")
        self.raster_ref_color = ColorPickerEdit("#e74c3c")
        _add_row(g, "Reference line color", self.raster_ref_color,
                 "Color for the rhythm reference lines. Default red #e74c3c.",
                 extended_desc="Color for all rhythm reference lines. Choose a hue that "
                 "stands out against both the scatter point colors and the background. "
                 "Red is a common choice for reference/annotation lines.")
        lay.addWidget(grp)

        grp = QGroupBox("Rhythm Boundary Line")
        g = QVBoxLayout(grp)

        self.raster_boundary_enabled = QCheckBox("Enable boundary line")
        self.raster_boundary_enabled.setChecked(False)
        _add_checkbox(g, self.raster_boundary_enabled,
                      "Draw a horizontal line where the rhythm distribution fans out.",
                      "Replicates the 'fanning out' boundary from Roeske et al. (2020). "
                      "Uses a moving-window dispersion calculation on rhythm ratios to find "
                      "the cycle duration where rhythms shift from isochronous to multimodal.")

        self.raster_boundary_method = QComboBox()
        self.raster_boundary_method.addItems(["Standard Deviation (σ_r)", "Shannon Entropy"])
        _add_row(g, "Dispersion method", self.raster_boundary_method,
                 "Which dispersion measure to use for detecting the boundary.",
                 extended_desc="Standard Deviation measures variability of rhythm ratios "
                 "within the sliding window. Shannon Entropy measures how spread-out "
                 "the distribution is across histogram bins. Entropy is more sensitive "
                 "to multi-modal distributions.")

        self.raster_boundary_threshold = QLineEdit("0.12")
        _add_row(g, "Boundary threshold", self.raster_boundary_threshold,
                 "Dispersion value that triggers the boundary (e.g. σ_r > 0.12 or Entropy > 1.5).",
                 extended_desc="The boundary line is placed where the dispersion first exceeds "
                 "this value. Lower threshold = earlier (shorter CDs) boundary. "
                 "For Std Dev, try 0.08–0.15. For Entropy, try 1.0–2.0.")

        self.raster_boundary_window = QLineEdit("50")
        _add_row(g, "Window size (dyads)", self.raster_boundary_window,
                 "Number of dyads in the sliding window for dispersion calculation.",
                 extended_desc="Larger windows smooth out noise but reduce sensitivity. "
                 "Smaller windows are more responsive but may produce false positives. "
                 "Try 30–100 depending on dataset size.")

        self.raster_boundary_color = ColorPickerEdit("#e74c3c")
        _add_row(g, "Line color", self.raster_boundary_color,
                 "Color for the rhythm boundary line. Default red #e74c3c.",
                 extended_desc="Choose a color that stands out against the data points "
                 "and background. Red is commonly used for boundary annotations.")

        self.raster_boundary_width = QLineEdit("2.0")
        _add_row(g, "Line thickness", self.raster_boundary_width,
                 "Width of the boundary line in points. Default 2.0.",
                 extended_desc="Thicker lines are more visible but may obscure nearby data. "
                 "Try 1.0–3.0.")

        self.raster_boundary_style = QComboBox()
        self.raster_boundary_style.addItems(["solid (—)", "dashed (--)", "dotted (···)", "dashdot (-·)"])
        self.raster_boundary_style.setCurrentText("dashed (--)")
        _add_row(g, "Line style", self.raster_boundary_style,
                 "Matplotlib line style for the boundary line. Default dashed.",
                 extended_desc="Dashed or dotted styles help distinguish the boundary "
                 "from the center line and grid lines.")

        self.raster_boundary_label = QLineEdit("Tempo Boundary")
        _add_row(g, "Label text", self.raster_boundary_label,
                 "Text label displayed next to the boundary line.",
                 extended_desc="Custom text for the annotation. Leave empty to show "
                 "no label. Common choices: 'Tempo Boundary', 'Rhythm Transition'.")

        self.raster_boundary_show_value = QCheckBox("Show tempo value")
        self.raster_boundary_show_value.setChecked(True)
        _add_checkbox(g, self.raster_boundary_show_value,
                      "Append the calculated cycle duration to the label (e.g. '= 135ms').",
                      "When enabled, the actual cycle duration at the boundary is appended "
                      "to the label text, showing exactly where the transition occurs.")

        self.raster_boundary_text_size = QLineEdit("11")
        _add_row(g, "Text size", self.raster_boundary_text_size,
                 "Font size for the boundary label in points. Default 11.",
                 extended_desc="Increase for presentations or posters. "
                 "Decrease if the label overwhelms the plot.")

        self.raster_boundary_text_color = ColorPickerEdit("#e74c3c")
        _add_row(g, "Text color", self.raster_boundary_text_color,
                 "Color for the boundary label text. Default red #e74c3c.",
                 extended_desc="Often matched to the line color for visual consistency, "
                 "but can be set to black or another color for contrast.")

        self.raster_boundary_text_va = QComboBox()
        self.raster_boundary_text_va.addItems(["Above", "Below"])
        _add_row(g, "Label vertical alignment", self.raster_boundary_text_va,
                 "Place the label text above or below the boundary line.",
                 extended_desc="'Above' places the label on the shorter-CD side of the line. "
                 "'Below' places it on the longer-CD side.")

        self.raster_boundary_text_ha = QComboBox()
        self.raster_boundary_text_ha.addItems(["Left", "Center", "Right"])
        self.raster_boundary_text_ha.setCurrentText("Right")
        _add_row(g, "Label horizontal alignment", self.raster_boundary_text_ha,
                 "Horizontal position of the label text along the boundary line.",
                 extended_desc="'Right' places the text near the right edge of the plot. "
                 "'Left' places it near the left edge. 'Center' centers it.")

        lay.addWidget(grp)

        grp = QGroupBox("Combined Corpus Plot")
        g = QVBoxLayout(grp)
        self.raster_combined = QCheckBox("Generate combined corpus plot")
        self.raster_combined.setChecked(True)
        _add_checkbox(g, self.raster_combined,
                      "Create an additional raster plot combining all files.",
                      "Generates one extra figure that overlays every dyadic event from all "
                      "recordings in a single raster. Useful for seeing corpus-level patterns.")
        lay.addWidget(grp)

        grp = QGroupBox("3D Flower Raster Plot")
        g = QVBoxLayout(grp)

        self.raster_3d_enabled = QCheckBox("Generate 3D flower raster")
        self.raster_3d_enabled.setChecked(False)
        _add_checkbox(g, self.raster_3d_enabled,
            "Arrange each recording's raster as a radial petal in 3D space.",
            "Creates a 3D flower where every file becomes a petal fanning out from a shared "
            "vertical axis. Short intervals extend inward and long intervals outward along "
            "each petal's radial plane. Requires at least 2 files. The interactive HTML "
            "output can be rotated and zoomed in any web browser.")

        self.raster_3d_format = QComboBox()
        self.raster_3d_format.addItems(["Interactive HTML", "Static PNG", "Both"])
        _add_row(g, "Output format", self.raster_3d_format,
                 "File format for the 3D flower plot.",
                 extended_desc="'Interactive HTML' (recommended) produces a self-contained HTML "
                 "file using Plotly that you can rotate, zoom, and hover over in any browser. "
                 "'Static PNG' renders a fixed-angle image via matplotlib. "
                 "'Both' generates both formats.")

        self.raster_3d_dot_size = QLineEdit("2.5")
        _add_row(g, "Dot size", self.raster_3d_dot_size,
                 "Marker size for scatter points. 1–2 = dense, 3–5 = sparse.",
                 extended_desc="Area of each point in the 3D scatter. Smaller values work "
                 "better when many recordings overlap; larger values for sparse datasets.")

        self.raster_3d_petal_opacity = QLineEdit("0.70")
        _add_row(g, "Petal opacity", self.raster_3d_petal_opacity,
                 "Transparency of each petal's points (0–1). Lower = see through petals.",
                 extended_desc="Controls how opaque each petal's scatter points are. Lower "
                 "values let petals behind show through, revealing the 3D structure. "
                 "0.5 = semi-transparent, 0.7 = default, 1.0 = fully opaque.")

        self.raster_3d_colormap = QComboBox()
        self.raster_3d_colormap.addItems(["rainbow", "cool", "warm", "pastel"])
        _add_row(g, "Color scheme", self.raster_3d_colormap,
                 "Palette used to assign a unique color to each petal (recording).",
                 extended_desc="'rainbow' = high-contrast maximally distinct colors. "
                 "'cool' = blue-green-purple tones. 'warm' = red-orange-yellow tones. "
                 "'pastel' = soft muted colors. Colors cycle if there are more files than "
                 "palette entries.")

        self.raster_3d_bg_color = ColorPickerEdit("#ffffff")
        _add_row(g, "Background color", self.raster_3d_bg_color,
                 "Background color of the 3D scene. Default white.",
                 extended_desc="The color behind the 3D scatter plot. White works for "
                 "publication; dark backgrounds (#1a1a2e) can make colors pop.")

        self.raster_3d_show_labels = QCheckBox("Show petal labels")
        self.raster_3d_show_labels.setChecked(True)
        _add_checkbox(g, self.raster_3d_show_labels,
            "Display the filename at the tip of each petal.",
            "Adds a text label at the outermost extent of each petal so you can "
            "identify which recording each petal represents.")

        self.raster_3d_show_stems = QCheckBox("Show petal mid-planes")
        self.raster_3d_show_stems.setChecked(True)
        _add_checkbox(g, self.raster_3d_show_stems,
            "Draw a faint translucent surface along each petal's radial plane.",
            "Adds a very low-opacity rectangular surface along each petal's angle, "
            "making the radial arrangement easier to see. Only visible in the HTML output.")

        self.raster_3d_elevation = QLineEdit("25")
        _add_row(g, "Camera elevation (°)", self.raster_3d_elevation,
                 "Vertical camera angle for the static PNG. 0 = side view, 90 = top-down.",
                 extended_desc="Elevation angle in degrees for the matplotlib static PNG "
                 "render. 20–30° gives a good oblique view. 0° looks at the flower from "
                 "the side; 90° looks straight down. Has no effect on HTML output.")

        self.raster_3d_azimuth = QLineEdit("-60")
        _add_row(g, "Camera azimuth (°)", self.raster_3d_azimuth,
                 "Horizontal camera rotation for the static PNG. -60° = default viewpoint.",
                 extended_desc="Azimuth angle in degrees for the matplotlib static PNG "
                 "render. Rotates the view horizontally around the flower. Has no effect "
                 "on HTML output (where you rotate interactively).")

        self.raster_3d_fig_width = QLineEdit("1200")
        _add_row(g, "Width (pixels)", self.raster_3d_fig_width,
                 "Output width in pixels. Default 1200.",
                 extended_desc="Width of the 3D figure in pixels. Used for both HTML canvas "
                 "size and static PNG dimensions. 1200 is a good default for most screens.")

        self.raster_3d_fig_height = QLineEdit("900")
        _add_row(g, "Height (pixels)", self.raster_3d_fig_height,
                 "Output height in pixels. Default 900.",
                 extended_desc="Height of the 3D figure in pixels. Increase for a taller "
                 "view when there are many dyadic events stacked vertically.")

        sep = QLabel("<b>Stage 2 — Volumetric Flower</b>")
        g.addWidget(sep)

        self.raster_3d_mesh_enabled = QCheckBox("Enable volumetric mesh (Mesh3d)")
        self.raster_3d_mesh_enabled.setChecked(True)
        _add_checkbox(g, self.raster_3d_mesh_enabled,
            "Wrap an alphahull surface around each petal's point cloud.",
            "Uses Plotly Mesh3d with alphahull to create a non-convex 'skin' around "
            "the scatter points, producing a solid 3D sculpture of the rhythm. "
            "The mesh is semi-transparent so skeleton dots remain visible underneath.")

        self.raster_3d_mesh_opacity = QLineEdit("0.6")
        _add_row(g, "Mesh opacity", self.raster_3d_mesh_opacity,
                 "Transparency of the volumetric skin (0–1). 0.6 = see-through.",
                 extended_desc="Controls how transparent the Mesh3d surface is. Lower "
                 "values let skeleton dots show through clearly. 0.3 = very transparent, "
                 "0.6 = default, 1.0 = fully opaque.")

        self.raster_3d_alphahull = QLineEdit("7")
        _add_row(g, "Alpha hull value", self.raster_3d_alphahull,
                 "Controls concavity of the mesh skin. Lower = tighter fit.",
                 extended_desc="The alphahull parameter for Mesh3d. Lower values produce "
                 "a tighter, more concave surface that follows the data closely. Higher "
                 "values produce a smoother, more convex hull. Try 5–7 for a good balance.")

        self.raster_3d_show_skeleton = QCheckBox("Show skeleton dots under mesh")
        self.raster_3d_show_skeleton.setChecked(True)
        _add_checkbox(g, self.raster_3d_show_skeleton,
            "Display the Stage 1 scatter points inside the mesh surface.",
            "When enabled, the original skeleton dots are drawn inside the semi-transparent "
            "mesh, allowing you to see both the raw data and the volumetric shape.")

        self.raster_3d_group_mode = QCheckBox("Group mode (cluster files into groups)")
        self.raster_3d_group_mode.setChecked(False)
        _add_checkbox(g, self.raster_3d_group_mode,
            "Divide 180° into equal sectors, one per group.",
            "When enabled, files are assigned to named groups via filename patterns. "
            "Each group's data is swept within its angular sector, making it "
            "easy to compare rhythmic volumes across groups. Define groups below.")

        groups_container = QWidget()
        groups_lay = QHBoxLayout(groups_container)
        groups_lay.setContentsMargins(0, 0, 0, 0)
        self.raster_3d_groups = QLineEdit("")
        groups_lay.addWidget(self.raster_3d_groups, stretch=1)
        groups_load_btn = QPushButton("Load…")
        groups_load_btn.setFixedWidth(90)
        groups_load_btn.clicked.connect(self._load_groups_json_file)
        groups_lay.addWidget(groups_load_btn)
        _add_row(g, "Groups (JSON)", groups_container,
                 'Group name → filename patterns, e.g. {"Woodlark": ["*Woodlark*"], "Coal Tit": ["*Coal Tit*"]}',
                 extended_desc="A JSON object mapping group names to lists of filename patterns "
                 "(fnmatch syntax: * ? []). Files not matching any pattern go into 'Ungrouped'. "
                 "Click Load… to import definitions from a .json file.")

        sources_container = QWidget()
        sources_lay = QHBoxLayout(sources_container)
        sources_lay.setContentsMargins(0, 0, 0, 0)
        self.raster_3d_extra_sources = QLineEdit("")
        sources_lay.addWidget(self.raster_3d_extra_sources, stretch=1)
        sources_browse_btn = QPushButton("Browse…")
        sources_browse_btn.setFixedWidth(90)
        sources_browse_btn.clicked.connect(self._browse_extra_sources)
        sources_lay.addWidget(sources_browse_btn)
        _add_row(g, "Extra workbook paths", sources_container,
                 "Paths to additional .xlsx workbooks to merge.",
                 extended_desc="Point to workbooks generated by other pipeline runs. "
                 "Their dyadic sheets are merged so all files appear in a single flower. "
                 "Useful for cross-species or cross-culture comparisons. "
                 "Click Browse… to select one or more .xlsx files.")

        self.raster_3d_lathe_steps = QLineEdit("32")
        _add_row(g, "Lathe angular steps", self.raster_3d_lathe_steps,
                 "Number of angular slices for the lathe/spin replication (default 32).",
                 extended_desc="For single-file Signature mode and Group mode, "
                 "each dyad is replicated across this many discrete angles. 32 gives a "
                 "smooth shape; reduce for a faceted look or increase for higher fidelity.")

        lay.addWidget(grp)

        lay.addStretch()
        self.setWidget(content)

        self.excel_path.textChanged.connect(self._on_excel_changed)
        self.plot_datasets.currentTextChanged.connect(self._update_io_summary)
        self.raster_combined.stateChanged.connect(self._update_io_summary)
        self.raster_3d_enabled.stateChanged.connect(self._update_io_summary)
        self.raster_3d_format.currentTextChanged.connect(self._update_io_summary)
        self._update_io_summary()

    def _on_excel_changed(self, text):
        if self._output_auto_cb.isChecked():
            cfg = self._output_auto_cb.auto_config
            src = cfg.get("source_step", "(this step)")
            if src in ("(this step)", "Flower Raster Plots") and cfg.get("source_io") == "input":
                resolved = _resolve_auto_config(text, cfg)
                if resolved:
                    self.output_folder.setText(resolved)

    def _on_output_auto_toggled(self, state):
        if bool(state):
            self._on_excel_changed(self.excel_path.text())

    def _update_io_summary(self):
        lines = ["<b>Reads:</b> Excel workbook (.xlsx) from Step 3"]
        out = ["<b>Produces:</b>"]
        ds = self.plot_datasets.currentText()
        if "raw" in ds:
            out.append("• Per-file raster .png → raw/ subfolder")
        if "stable" in ds:
            out.append("• Per-file raster .png → stable/ subfolder")
        if self.raster_combined.isChecked():
            out.append("• Combined corpus raster .png")
        if self.raster_3d_enabled.isChecked():
            fmt = self.raster_3d_format.currentText()
            if fmt in ("Interactive HTML", "Both"):
                out.append("• 3D flower raster .html (interactive)")
            if fmt in ("Static PNG", "Both"):
                out.append("• 3D flower raster .png (static)")
        self._io_summary.setText("<br>".join(lines + out))

    def _parse_groups_json(self):
        raw = self.raster_3d_groups.text().strip()
        if not raw:
            return {}
        try:
            val = json.loads(raw)
            if isinstance(val, dict):
                return val
        except json.JSONDecodeError:
            pass
        return {}

    def _parse_extra_sources(self):
        raw = self.raster_3d_extra_sources.text().strip()
        if not raw:
            return []
        return [path.strip() for path in raw.split(";") if path.strip()]

    def _load_groups_json_file(self):
        start = self.output_folder.text() or get_form_widget_project_root()
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Groups JSON", start, "JSON files (*.json)")
        if not path:
            return
        try:
            with open(path) as handle:
                data = json.load(handle)
            self.raster_3d_groups.setText(json.dumps(data))
        except Exception as exc:
            self.raster_3d_groups.setText(f"Error: {exc}")

    def _browse_extra_sources(self):
        start = self.output_folder.text() or get_form_widget_project_root()
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Workbook(s)", start, "Excel files (*.xlsx)")
        if paths:
            existing = self.raster_3d_extra_sources.text().strip()
            new_text = "; ".join(paths)
            if existing:
                new_text = existing + "; " + new_text
            self.raster_3d_extra_sources.setText(new_text)

    def _show_excel_data_used(self):
        import copy

        defs = copy.deepcopy(self._EXCEL_COLUMNS)
        overrides = getattr(self, "_excel_col_overrides", {})
        for column_def in defs:
            if column_def["var_id"] in overrides:
                column_def["column"] = overrides[column_def["var_id"]]
        dlg = ExcelDataUsedDialog("Flower Raster Plots", defs, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._excel_col_overrides = dlg.get_columns()

    def save_settings_if_enabled(self):
        return _save_settings_if_enabled(self)

    def get_values(self):
        ds_map = {"raw + stable": ("raw", "stable"), "raw only": ("raw",), "stable only": ("stable",)}
        style_map = {"solid (—)": "-", "dashed (--)": "--", "dotted (···)": ":", "dashdot (-·)": "-."}
        return {
            "excel_path": self.excel_path.text(),
            "output_folder": self.output_folder.text(),
            "PLOT_DATASETS": list(ds_map.get(self.plot_datasets.currentText(), ("raw", "stable"))),
            "RASTER_FIG_WIDTH": _to_float(self.raster_width.text(), 10),
            "RASTER_FIG_HEIGHT": _to_float(self.raster_height.text(), 8),
            "RASTER_DPI": _to_int(self.raster_dpi.text(), 300),
            "RASTER_TIGHT_PAD": _to_float(self.raster_tight_pad.text(), 1.08),
            "RASTER_DOT_SIZE": _to_float(self.raster_dot_size.text(), 3),
            "RASTER_ALPHA": _to_float(self.raster_alpha.text(), 0.6),
            "RASTER_BG_COLOR": self.raster_bg_color.text().strip() or "#ffffff",
            "RASTER_COLOR_SHORT": self.raster_color_short.text().strip() or "#1f77b4",
            "RASTER_COLOR_LONG": self.raster_color_long.text().strip() or "#ff7f0e",
            "RASTER_CENTER_COLOR": self.raster_center_color.text().strip() or "#000000",
            "RASTER_CENTER_WIDTH": _to_float(self.raster_center_width.text(), 1.5),
            "RASTER_CENTER_STYLE": style_map.get(self.raster_center_style.currentText(), "-"),
            "RASTER_TITLE_FONTSIZE": _to_int(self.raster_title_size.text(), 14),
            "RASTER_TITLE_PAD": _to_float(self.raster_title_pad.text(), 12),
            "RASTER_AXIS_FONTSIZE": _to_int(self.raster_axis_size.text(), 12),
            "RASTER_LABEL_PAD": _to_float(self.raster_label_pad.text(), 8),
            "RASTER_TICK_FONTSIZE": _to_int(self.raster_tick_size.text(), 10),
            "RASTER_TITLE_COLOR": self.raster_title_color.text().strip() or "#000000",
            "RASTER_AXIS_COLOR": self.raster_axis_color.text().strip() or "#000000",
            "RASTER_TICK_COLOR": self.raster_tick_color.text().strip() or "#000000",
            "RASTER_TITLE_PREFIX": self.raster_title_prefix.text(),
            "RASTER_TITLE_SUFFIX": self.raster_title_suffix.text(),
            "RASTER_COMBINED_TITLE_PREFIX": self.raster_combined_title_prefix.text(),
            "RASTER_X_LABEL": self.raster_x_label.text(),
            "RASTER_Y_LABEL": self.raster_y_label.text(),
            "RASTER_GRID": self.raster_grid.isChecked(),
            "RASTER_GRID_ALPHA": _to_float(self.raster_grid_alpha.text(), 0.5),
            "RASTER_GRID_COLOR": self.raster_grid_color.text().strip() or "#cccccc",
            "RASTER_GRID_STYLE": style_map.get(self.raster_grid_style.currentText(), "--"),
            "RASTER_LEGEND_SHOW": self.raster_legend_show.isChecked(),
            "RASTER_LEGEND_POS": self.raster_legend_pos.currentText(),
            "RASTER_LEGEND_FONTSIZE": _to_int(self.raster_legend_size.text(), 10),
            "RASTER_REF_LINES": self.raster_ref_lines.isChecked(),
            "RASTER_REF_VALUES": self.raster_ref_values.text().strip(),
            "RASTER_REF_LABELS": self.raster_ref_labels.text().strip(),
            "RASTER_REF_COLOR": self.raster_ref_color.text().strip() or "#e74c3c",
            "RASTER_COMBINED": self.raster_combined.isChecked(),
            "RASTER_BOUNDARY_ENABLED": self.raster_boundary_enabled.isChecked(),
            "RASTER_BOUNDARY_METHOD": {"Standard Deviation (σ_r)": "std",
                                       "Shannon Entropy": "entropy"}.get(
                self.raster_boundary_method.currentText(), "std"),
            "RASTER_BOUNDARY_THRESHOLD": _to_float(self.raster_boundary_threshold.text(), 0.12),
            "RASTER_BOUNDARY_WINDOW": _to_int(self.raster_boundary_window.text(), 50),
            "RASTER_BOUNDARY_COLOR": self.raster_boundary_color.text().strip() or "#e74c3c",
            "RASTER_BOUNDARY_WIDTH": _to_float(self.raster_boundary_width.text(), 2.0),
            "RASTER_BOUNDARY_STYLE": style_map.get(self.raster_boundary_style.currentText(), "--"),
            "RASTER_BOUNDARY_LABEL": self.raster_boundary_label.text(),
            "RASTER_BOUNDARY_SHOW_VALUE": self.raster_boundary_show_value.isChecked(),
            "RASTER_BOUNDARY_TEXT_SIZE": _to_int(self.raster_boundary_text_size.text(), 11),
            "RASTER_BOUNDARY_TEXT_COLOR": self.raster_boundary_text_color.text().strip() or "#e74c3c",
            "RASTER_BOUNDARY_TEXT_VA": self.raster_boundary_text_va.currentText().lower(),
            "RASTER_BOUNDARY_TEXT_HA": self.raster_boundary_text_ha.currentText().lower(),
            "RASTER_3D_ENABLED": self.raster_3d_enabled.isChecked(),
            "RASTER_3D_FORMAT": {"Interactive HTML": "html", "Static PNG": "png",
                                 "Both": "both"}.get(self.raster_3d_format.currentText(), "html"),
            "RASTER_3D_DOT_SIZE": _to_float(self.raster_3d_dot_size.text(), 2.5),
            "RASTER_3D_PETAL_OPACITY": _to_float(self.raster_3d_petal_opacity.text(), 0.70),
            "RASTER_3D_COLORMAP": self.raster_3d_colormap.currentText(),
            "RASTER_3D_BG_COLOR": self.raster_3d_bg_color.text().strip() or "#ffffff",
            "RASTER_3D_SHOW_LABELS": self.raster_3d_show_labels.isChecked(),
            "RASTER_3D_SHOW_STEMS": self.raster_3d_show_stems.isChecked(),
            "RASTER_3D_ELEVATION": _to_int(self.raster_3d_elevation.text(), 25),
            "RASTER_3D_AZIMUTH": _to_int(self.raster_3d_azimuth.text(), -60),
            "RASTER_3D_FIG_WIDTH": _to_int(self.raster_3d_fig_width.text(), 1200),
            "RASTER_3D_FIG_HEIGHT": _to_int(self.raster_3d_fig_height.text(), 900),
            "RASTER_3D_MESH_ENABLED": self.raster_3d_mesh_enabled.isChecked(),
            "RASTER_3D_MESH_OPACITY": _to_float(self.raster_3d_mesh_opacity.text(), 0.6),
            "RASTER_3D_ALPHAHULL": _to_int(self.raster_3d_alphahull.text(), 7),
            "RASTER_3D_SHOW_SKELETON": self.raster_3d_show_skeleton.isChecked(),
            "RASTER_3D_GROUP_MODE": self.raster_3d_group_mode.isChecked(),
            "RASTER_3D_GROUPS": self._parse_groups_json(),
            "RASTER_3D_EXTRA_SOURCES": self._parse_extra_sources(),
            "RASTER_3D_LATHE_STEPS": _to_int(self.raster_3d_lathe_steps.text(), 32),
        }

    def set_values(self, d):
        if "excel_path" in d:
            self.excel_path.setText(str(d["excel_path"]))
        if "output_folder" in d:
            self.output_folder.setText(str(d["output_folder"]))
        ds_rev = {"raw,stable": "raw + stable", "raw": "raw only", "stable": "stable only"}
        style_rev = {"-": "solid (—)", "--": "dashed (--)", ":": "dotted (···)", "-.": "dashdot (-·)"}
        ds_val = d.get("PLOT_DATASETS", ["raw", "stable"])
        ds_key = ",".join(ds_val) if isinstance(ds_val, list) else str(ds_val)
        self.plot_datasets.setCurrentText(ds_rev.get(ds_key, "raw + stable"))
        self.raster_width.setText(str(d.get("RASTER_FIG_WIDTH", 10)))
        self.raster_height.setText(str(d.get("RASTER_FIG_HEIGHT", 8)))
        self.raster_dpi.setText(str(d.get("RASTER_DPI", 300)))
        self.raster_tight_pad.setText(str(d.get("RASTER_TIGHT_PAD", 1.08)))
        self.raster_dot_size.setText(str(d.get("RASTER_DOT_SIZE", 3)))
        self.raster_alpha.setText(str(d.get("RASTER_ALPHA", 0.6)))
        self.raster_bg_color.setText(str(d.get("RASTER_BG_COLOR", "#ffffff")))
        self.raster_color_short.setText(str(d.get("RASTER_COLOR_SHORT", "#1f77b4")))
        self.raster_color_long.setText(str(d.get("RASTER_COLOR_LONG", "#ff7f0e")))
        self.raster_center_color.setText(str(d.get("RASTER_CENTER_COLOR", "#000000")))
        self.raster_center_width.setText(str(d.get("RASTER_CENTER_WIDTH", 1.5)))
        self.raster_center_style.setCurrentText(style_rev.get(d.get("RASTER_CENTER_STYLE", "-"), "solid (—)"))
        self.raster_title_size.setText(str(d.get("RASTER_TITLE_FONTSIZE", 14)))
        self.raster_title_pad.setText(str(d.get("RASTER_TITLE_PAD", 12)))
        self.raster_axis_size.setText(str(d.get("RASTER_AXIS_FONTSIZE", 12)))
        self.raster_label_pad.setText(str(d.get("RASTER_LABEL_PAD", 8)))
        self.raster_tick_size.setText(str(d.get("RASTER_TICK_FONTSIZE", 10)))
        self.raster_title_color.setText(str(d.get("RASTER_TITLE_COLOR", "#000000")))
        self.raster_axis_color.setText(str(d.get("RASTER_AXIS_COLOR", "#000000")))
        self.raster_tick_color.setText(str(d.get("RASTER_TICK_COLOR", "#000000")))
        self.raster_title_prefix.setText(str(d.get("RASTER_TITLE_PREFIX", "Rhythm Raster")))
        self.raster_title_suffix.setText(str(d.get("RASTER_TITLE_SUFFIX", "")))
        self.raster_combined_title_prefix.setText(str(d.get("RASTER_COMBINED_TITLE_PREFIX", "Combined Corpus Rhythm Raster")))
        self.raster_x_label.setText(str(d.get("RASTER_X_LABEL", "Interval Duration (ms)")))
        self.raster_y_label.setText(str(d.get("RASTER_Y_LABEL", "Dyadic Events (Sorted by Cycle Duration)")))
        self.raster_grid.setChecked(bool(d.get("RASTER_GRID", False)))
        self.raster_grid_alpha.setText(str(d.get("RASTER_GRID_ALPHA", 0.5)))
        self.raster_grid_color.setText(str(d.get("RASTER_GRID_COLOR", "#cccccc")))
        self.raster_grid_style.setCurrentText(style_rev.get(d.get("RASTER_GRID_STYLE", "--"), "dashed (--)"))
        self.raster_legend_show.setChecked(bool(d.get("RASTER_LEGEND_SHOW", True)))
        self.raster_legend_pos.setCurrentText(str(d.get("RASTER_LEGEND_POS", "upper left")))
        self.raster_legend_size.setText(str(d.get("RASTER_LEGEND_FONTSIZE", 10)))
        self.raster_ref_lines.setChecked(bool(d.get("RASTER_REF_LINES", False)))
        self.raster_ref_values.setText(str(d.get("RASTER_REF_VALUES", "")))
        self.raster_ref_labels.setText(str(d.get("RASTER_REF_LABELS", "")))
        self.raster_ref_color.setText(str(d.get("RASTER_REF_COLOR", "#e74c3c")))
        self.raster_combined.setChecked(bool(d.get("RASTER_COMBINED", False)))
        self.raster_boundary_enabled.setChecked(bool(d.get("RASTER_BOUNDARY_ENABLED", False)))
        bmethod_rev = {"std": "Standard Deviation (σ_r)", "entropy": "Shannon Entropy"}
        self.raster_boundary_method.setCurrentText(
            bmethod_rev.get(d.get("RASTER_BOUNDARY_METHOD", "std"),
                            "Standard Deviation (σ_r)"))
        self.raster_boundary_threshold.setText(str(d.get("RASTER_BOUNDARY_THRESHOLD", 0.12)))
        self.raster_boundary_window.setText(str(d.get("RASTER_BOUNDARY_WINDOW", 50)))
        self.raster_boundary_color.setText(str(d.get("RASTER_BOUNDARY_COLOR", "#e74c3c")))
        self.raster_boundary_width.setText(str(d.get("RASTER_BOUNDARY_WIDTH", 2.0)))
        self.raster_boundary_style.setCurrentText(
            style_rev.get(d.get("RASTER_BOUNDARY_STYLE", "--"), "dashed (--)"))
        self.raster_boundary_label.setText(str(d.get("RASTER_BOUNDARY_LABEL", "Tempo Boundary")))
        self.raster_boundary_show_value.setChecked(bool(d.get("RASTER_BOUNDARY_SHOW_VALUE", True)))
        self.raster_boundary_text_size.setText(str(d.get("RASTER_BOUNDARY_TEXT_SIZE", 11)))
        self.raster_boundary_text_color.setText(str(d.get("RASTER_BOUNDARY_TEXT_COLOR", "#e74c3c")))
        va_rev = {"above": "Above", "below": "Below"}
        self.raster_boundary_text_va.setCurrentText(
            va_rev.get(d.get("RASTER_BOUNDARY_TEXT_VA", "above"), "Above"))
        ha_rev = {"left": "Left", "center": "Center", "right": "Right"}
        self.raster_boundary_text_ha.setCurrentText(
            ha_rev.get(d.get("RASTER_BOUNDARY_TEXT_HA", "right"), "Right"))
        self.raster_3d_enabled.setChecked(bool(d.get("RASTER_3D_ENABLED", False)))
        fmt_rev = {"html": "Interactive HTML", "png": "Static PNG", "both": "Both"}
        self.raster_3d_format.setCurrentText(fmt_rev.get(d.get("RASTER_3D_FORMAT", "html"), "Interactive HTML"))
        self.raster_3d_dot_size.setText(str(d.get("RASTER_3D_DOT_SIZE", 2.5)))
        self.raster_3d_petal_opacity.setText(str(d.get("RASTER_3D_PETAL_OPACITY", 0.70)))
        self.raster_3d_colormap.setCurrentText(str(d.get("RASTER_3D_COLORMAP", "rainbow")))
        self.raster_3d_bg_color.setText(str(d.get("RASTER_3D_BG_COLOR", "#ffffff")))
        self.raster_3d_show_labels.setChecked(bool(d.get("RASTER_3D_SHOW_LABELS", True)))
        self.raster_3d_show_stems.setChecked(bool(d.get("RASTER_3D_SHOW_STEMS", True)))
        self.raster_3d_elevation.setText(str(d.get("RASTER_3D_ELEVATION", 25)))
        self.raster_3d_azimuth.setText(str(d.get("RASTER_3D_AZIMUTH", -60)))
        self.raster_3d_fig_width.setText(str(d.get("RASTER_3D_FIG_WIDTH", 1200)))
        self.raster_3d_fig_height.setText(str(d.get("RASTER_3D_FIG_HEIGHT", 900)))
        self.raster_3d_mesh_enabled.setChecked(bool(d.get("RASTER_3D_MESH_ENABLED", True)))
        self.raster_3d_mesh_opacity.setText(str(d.get("RASTER_3D_MESH_OPACITY", 0.6)))
        self.raster_3d_alphahull.setText(str(d.get("RASTER_3D_ALPHAHULL", 7)))
        self.raster_3d_show_skeleton.setChecked(bool(d.get("RASTER_3D_SHOW_SKELETON", True)))
        self.raster_3d_group_mode.setChecked(bool(d.get("RASTER_3D_GROUP_MODE", False)))
        groups_val = d.get("RASTER_3D_GROUPS", {})
        self.raster_3d_groups.setText(json.dumps(groups_val) if groups_val else "")
        extra_val = d.get("RASTER_3D_EXTRA_SOURCES", [])
        self.raster_3d_extra_sources.setText(";".join(extra_val) if extra_val else "")
        self.raster_3d_lathe_steps.setText(str(d.get("RASTER_3D_LATHE_STEPS", 32)))