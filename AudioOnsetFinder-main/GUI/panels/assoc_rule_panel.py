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


class AssocRulePanel(QScrollArea):
    """Settings panel for the experimental association-rule-learning step."""

    _EXCEL_COLUMNS = [
        {"var_id": "file_name", "column": "File Name", "default": "File Name",
         "description": "Identifies each recording / audio file"},
        {"var_id": "npvi", "column": "nPVI (Isochrony)",
         "default": "nPVI (Isochrony)",
         "description": "Normalised Pairwise Variability Index (raw)"},
        {"var_id": "npvi_stable", "column": "Stable Rhythm nPVI",
         "default": "Stable Rhythm nPVI",
         "description": "nPVI for the stable-rhythm subset"},
        {"var_id": "entropy", "column": "r_k Entropy (Categorical Measure)",
         "default": "r_k Entropy (Categorical Measure)",
         "description": "Shannon entropy of the rhythm-ratio distribution"},
        {"var_id": "cv", "column": "CV of Intervals",
         "default": "CV of Intervals",
         "description": "Coefficient of variation of inter-onset intervals"},
        {"var_id": "mean_ioi", "column": "Mean IOI (ms)",
         "default": "Mean IOI (ms)",
         "description": "Mean inter-onset interval (ms)"},
        {"var_id": "total_onsets", "column": "Total Onsets Used",
         "default": "Total Onsets Used",
         "description": "Onsets remaining after filtering"},
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._palette = get_form_widget_palette()
        self.setWidgetResizable(True)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setSpacing(14)
        lay.setContentsMargins(16, 16, 16, 16)

        banner = QLabel(
            "<b>Experimental — Association Rule Learning (Apriori)</b><br>"
            "<i>Discretises the per-file rhythm metrics already produced by "
            "the Onset Finder and mines co-occurrence rules. This is a "
            "descriptive / hypothesis-generating tool, not a timing analysis.</i>")
        banner.setWordWrap(True)
        banner.setStyleSheet(
            f"color: {self._palette.text}; background: {self._palette.bg_widget}; "
            f"border: 1px solid {self._palette.accent}; border-radius: 6px; "
            f"padding: 8px 10px; font-size: 12px;"
        )
        lay.addWidget(banner)

        grp = QGroupBox("Input / Output")
        g = QVBoxLayout(grp)

        self.excel_path = FilePicker("", "Excel files (*.xlsx *.xls)")
        self.excel_path.line_edit.setPlaceholderText(
            "Excel file from Onset Finder output")
        _add_row(g, "Input Excel file", self.excel_path,
                 "Excel workbook produced by Step 3 (Onset Finder).",
                 extended_desc="Path to the .xlsx file containing File Summaries "
                 "with numeric rhythm metrics.",
                 label_width=140)
        self._input_auto_cb, self._input_auto_desc = _make_auto_set(
            self.excel_path, g,
            "↳ Auto: Set to the <b>Output Excel</b> from Step 3 (Onset Finder)",
            step_name="Association Rule Learning", io_type="input",
            auto_config={"source_step": "Onset Finder", "source_io": "output",
                         "suffix": "", "use_dirname": False,
                         "use_basename": False})

        self.output_folder = FolderPicker("")
        self.output_folder.line_edit.setPlaceholderText(
            "Output folder for rule CSVs + plots")
        _add_row(g, "Output folder", self.output_folder,
                 "Folder where association-rule CSVs and plots are saved.",
                 extended_desc="Produces association_rules.csv, "
                 "frequent_itemsets.csv, top_rules_bar, support_vs_confidence "
                 "and (optionally) rules_network plots.",
                 label_width=140)
        self._output_auto_cb, self._output_auto_desc = _make_auto_set(
            self.output_folder, g,
            "↳ Auto: Plots + CSVs saved in an '<i>Association_Rules</i>' folder "
            "alongside the Input Excel file",
            step_name="Association Rule Learning", io_type="output",
            auto_config={"source_step": "(this step)", "source_io": "input",
                         "suffix": "Association_Rules", "use_dirname": True,
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
            self, lay, "Association Rule Learning", self.excel_path,
            presets_dict=None)
        self._import_settings_btn.clicked.connect(
            lambda: _import_settings_for(self, "Association Rule Learning"))
        self._export_settings_btn.clicked.connect(
            lambda: _export_settings_for(self, "Association Rule Learning"))
        self._saved_settings_combo.currentTextChanged.connect(
            lambda name: _on_saved_settings_selected(
                self, "Association Rule Learning", name))

        grp = QGroupBox("Data Source")
        g = QVBoxLayout(grp)
        self.arl_dataset = QComboBox()
        self.arl_dataset.addItems(["raw", "stable"])
        _add_row(g, "Rhythm dataset", self.arl_dataset,
                 "Which rhythm metrics to mine: full or stable-rhythm subset.",
                 extended_desc="'raw' uses the 'nPVI (Isochrony)' / "
                 "'r_k Entropy (Categorical Measure)' columns (full data). "
                 "'stable' swaps them for 'Stable Rhythm nPVI' / "
                 "'Stable Rhythm Entropy' (filtered subset).")

        self.arl_features = QLineEdit(
            "nPVI (Isochrony), r_k Entropy (Categorical Measure), "
            "CV of Intervals, Mean IOI (ms), Total Onsets Used")
        _add_row(g, "Features to mine", self.arl_features,
                 "Comma-separated Excel column names from the File Summaries "
                 "sheet that will be discretised into items.",
                 extended_desc="Each feature is binned and becomes one item per "
                 "file (e.g. 'nPVI=high'). Files with NaN in any selected "
                 "feature are dropped. The ‘Excel Data Used…’ button lists the "
                 "default column names this step reads.")
        lay.addWidget(grp)

        grp = QGroupBox("Binning (numeric → categorical)")
        g = QVBoxLayout(grp)
        self.arl_bin_method = QComboBox()
        self.arl_bin_method.addItems(["quantile", "equal_width"])
        _add_row(g, "Bin method", self.arl_bin_method,
                 "How each numeric feature is split into bins.",
                 extended_desc="'quantile' puts roughly equal numbers of files "
                 "in each bin — robust to outliers and usually preferred. "
                 "'equal_width' splits the min→max range into equal intervals "
                 "which can leave some bins nearly empty if the distribution is "
                 "skewed.")
        self.arl_n_bins = QLineEdit("3")
        _add_row(g, "Number of bins", self.arl_n_bins,
                 "How many bins per feature. Default 3.",
                 extended_desc="More bins = finer-grained rules but fewer "
                 "transactions per bin (lower support). 3–4 is usually a "
                 "good starting point for <100 files.")
        self.arl_bin_labels = QLineEdit("low, medium, high")
        _add_row(g, "Bin labels", self.arl_bin_labels,
                 "Comma-separated labels, one per bin (low → high).",
                 extended_desc="Examples: 'low, medium, high' for 3 bins; "
                 "'Q1, Q2, Q3, Q4' for 4 bins. If the count doesn't match "
                 "Number of bins, falls back to 'bin1, bin2, …'.")
        lay.addWidget(grp)

        grp = QGroupBox("Group Assignment (optional extra item)")
        g = QVBoxLayout(grp)
        self.arl_include_group = QCheckBox("Include a per-file Group item")
        self.arl_include_group.setChecked(True)
        _add_checkbox(g, self.arl_include_group,
                      "Add a Group=… item to every transaction so that rules "
                      "can predict (or use) group membership.",
                      "When on, each file gets an extra item such as "
                      "'Group=Chimp' determined by the source below. Rules "
                      "like {Entropy=low, CV=low} ⇒ {Group=Chimp} become "
                      "possible.")

        self.arl_group_source = QComboBox()
        self.arl_group_source.addItems(
            ["filename_pattern", "mapping_csv", "manual", "excel_column"])
        _add_row(g, "Group source", self.arl_group_source,
                 "How to derive each file's group label.",
                 extended_desc="'filename_pattern' extracts the group from each "
                 "file name using a regex (with a named capture group "
                 "'group'). 'mapping_csv' loads a CSV of File Name → Group. "
                 "'manual' uses comma-separated file=group pairs. "
                 "'excel_column' reads group labels from a named column in the "
                 "File Summaries sheet.")
        self.arl_group_source.currentTextChanged.connect(
            self._on_group_source_changed)

        self.arl_group_pattern = QLineEdit(r"(?P<group>[A-Za-z]+)_")
        _add_row(g, "Filename pattern (regex)", self.arl_group_pattern,
                 "Regex with a named capture (?P<group>…) to extract group "
                 "from filename.",
                 extended_desc="Example r'(?P<group>[A-Za-z]+)_' extracts the "
                 "leading alphabetic word before the first underscore.")
        self.arl_group_csv_path = FilePicker("", "CSV files (*.csv)")
        self.arl_group_csv_path.line_edit.setPlaceholderText(
            "CSV with 'File Name' and 'Group' columns")
        _add_row(g, "Mapping CSV file", self.arl_group_csv_path,
                 "External CSV mapping each file name to a group.",
                 extended_desc="Must have columns 'File Name' and 'Group'. "
                 "Files not listed become the ungrouped label.")
        self.arl_manual_groups = QLineEdit("")
        self.arl_manual_groups.setPlaceholderText(
            "file1.wav=GroupA, file2.wav=GroupB, …")
        _add_row(g, "Manual groups", self.arl_manual_groups,
                 "Comma-separated file=group pairs for manual assignment.",
                 extended_desc="Format: 'filename1.wav=Group A, "
                 "filename2.wav=Group B'. Files not listed are labeled with "
                 "the ungrouped label.")
        self.arl_group_excel_column = QLineEdit("Group")
        _add_row(g, "Excel column name", self.arl_group_excel_column,
                 "Column in File Summaries holding each file's group label.",
                 extended_desc="Used when Group source is 'excel_column'.")
        self.arl_ungrouped_label = QLineEdit("Ungrouped")
        _add_row(g, "Ungrouped label", self.arl_ungrouped_label,
                 "Label for files that can't be assigned to any group.",
                 extended_desc="Files that don't match any group are "
                 "labelled with this text.")
        lay.addWidget(grp)

        grp = QGroupBox("Apriori Thresholds")
        g = QVBoxLayout(grp)
        self.arl_min_support = QLineEdit("0.15")
        _add_row(g, "Min support", self.arl_min_support,
                 "Minimum fraction of files in which an itemset must occur "
                 "(0-1). Default 0.15.",
                 extended_desc="Lower values retain more — and rarer — "
                 "itemsets but slow mining and inflate false positives. "
                 "Rule of thumb: raise min_support until the result set is "
                 "manageable (dozens, not thousands).")
        self.arl_min_confidence = QLineEdit("0.60")
        _add_row(g, "Min confidence", self.arl_min_confidence,
                 "Minimum P(consequent | antecedent) (0-1). Default 0.60.",
                 extended_desc="Drops low-reliability rules. "
                 "0.6–0.8 is a typical exploratory range.")
        self.arl_min_lift = QLineEdit("1.10")
        _add_row(g, "Min lift", self.arl_min_lift,
                 "Minimum lift (>1 means the rule is better than chance). "
                 "Default 1.10.",
                 extended_desc="Lift = confidence / P(consequent). "
                 "Values at or below 1 are uninformative (the antecedent "
                 "doesn't help predict the consequent). Raising to 1.3–2.0 "
                 "gives more distinctive rules.")
        self.arl_max_itemset = QLineEdit("4")
        _add_row(g, "Max itemset size", self.arl_max_itemset,
                 "Maximum number of items in a frequent itemset. Default 4.",
                 extended_desc="Caps combinatorial explosion. "
                 "With ~5 features + 1 group, 3–4 is usually plenty.")
        self.arl_require_group = QCheckBox(
            "Only keep rules whose consequent contains a Group=… item")
        _add_checkbox(g, self.arl_require_group,
                      "Restrict the output to rules that predict group "
                      "membership.",
                      "Useful when the question is 'what rhythm-bin "
                      "combinations characterise each group?'.")
        self.arl_top_n = QLineEdit("15")
        _add_row(g, "Top-N for plots", self.arl_top_n,
                 "How many rules to plot in the bar + network plots. "
                 "Default 15.",
                 extended_desc="The CSV always contains every rule that "
                 "passes the thresholds — this only limits the plots.")
        lay.addWidget(grp)

        grp = QGroupBox("Plot Appearance")
        g = QVBoxLayout(grp)
        self.arl_width = QLineEdit("12")
        _add_row(g, "Width (inches)", self.arl_width,
                 "Figure width in inches.",
                 extended_desc="Wider figures suit many rules.")
        self.arl_height = QLineEdit("7")
        _add_row(g, "Height (inches)", self.arl_height,
                 "Figure height in inches.",
                 extended_desc="Increase for very long rule labels.")
        self.arl_dpi = QLineEdit("300")
        _add_row(g, "DPI", self.arl_dpi,
                 "Output resolution. 150 = draft, 300 = publication.",
                 extended_desc="Higher DPI produces larger, sharper files.")
        self.arl_bg_color = ColorPickerEdit("#ffffff")
        _add_row(g, "Background color", self.arl_bg_color,
                 "Figure background. Default white.",
                 extended_desc="Applied to both the figure and axes.")
        self.arl_palette = QComboBox()
        self.arl_palette.setEditable(True)
        self.arl_palette.addItems([
            "viridis", "plasma", "cividis", "coolwarm", "inferno",
            "magma", "tab10", "Set2", "Dark2",
        ])
        _add_row(g, "Color palette", self.arl_palette,
                 "Matplotlib colormap used for bar / scatter / network.",
                 extended_desc="A sequential map like 'viridis' works best "
                 "for the lift-colored network and scatter.")
        self.arl_title_fs = QLineEdit("15")
        _add_row(g, "Title font size", self.arl_title_fs,
                 "Font size for plot titles.",
                 extended_desc="In points.")
        self.arl_axis_fs = QLineEdit("12")
        _add_row(g, "Axis font size", self.arl_axis_fs,
                 "Font size for axis labels.",
                 extended_desc="In points.")
        self.arl_tick_fs = QLineEdit("10")
        _add_row(g, "Tick / label font size", self.arl_tick_fs,
                 "Font size for tick marks and rule labels.",
                 extended_desc="Shrink for very long rule labels.")
        self.arl_draw_network = QCheckBox("Draw rule network diagram")
        self.arl_draw_network.setChecked(True)
        _add_checkbox(g, self.arl_draw_network,
                      "Enable the optional circular network diagram of the "
                      "top-N rules.",
                      "Turn off to skip the network plot (e.g. if too many "
                      "items cause clutter).")
        lay.addWidget(grp)

        grp = QGroupBox("Output Format")
        g = QVBoxLayout(grp)
        self.arl_output_format = QComboBox()
        self.arl_output_format.addItems(["png", "svg", "pdf", "png+svg"])
        _add_row(g, "File format", self.arl_output_format,
                 "Output image format. Default PNG.",
                 extended_desc="'png' for raster images, 'svg' for scalable "
                 "vector, 'pdf' for print-ready, 'png+svg' saves both.")
        lay.addWidget(grp)

        lay.addStretch()
        self.setWidget(content)

        self.excel_path.textChanged.connect(self._on_excel_changed)
        self.arl_dataset.currentTextChanged.connect(self._update_io_summary)
        self.arl_output_format.currentTextChanged.connect(self._update_io_summary)
        self.arl_draw_network.stateChanged.connect(self._update_io_summary)
        self._update_io_summary()
        self._on_group_source_changed(self.arl_group_source.currentText())

    def _on_excel_changed(self, text):
        if self._output_auto_cb.isChecked():
            cfg = self._output_auto_cb.auto_config
            src = cfg.get("source_step", "(this step)")
            if src in ("(this step)", "Association Rule Learning") \
                    and cfg.get("source_io") == "input":
                resolved = _resolve_auto_config(text, cfg)
                if resolved:
                    self.output_folder.setText(resolved)

    def _on_output_auto_toggled(self, state):
        if bool(state):
            self._on_excel_changed(self.excel_path.text())

    def _on_group_source_changed(self, source):
        self.arl_group_pattern.setEnabled(source == "filename_pattern")
        self.arl_group_csv_path.setEnabled(source == "mapping_csv")
        self.arl_manual_groups.setEnabled(source == "manual")
        self.arl_group_excel_column.setEnabled(source == "excel_column")

    def _update_io_summary(self):
        lines = ["<b>Reads:</b> Excel workbook (.xlsx) from Step 3"]
        out = ["<b>Produces:</b>",
               "• association_rules.csv",
               "• frequent_itemsets.csv"]
        fmt = self.arl_output_format.currentText()
        if "png" in fmt:
            out.append("• top_rules_bar .png + support_vs_confidence .png")
        if "svg" in fmt:
            out.append("• top_rules_bar .svg + support_vs_confidence .svg")
        if "pdf" in fmt:
            out.append("• top_rules_bar .pdf + support_vs_confidence .pdf")
        if self.arl_draw_network.isChecked():
            out.append("• rules_network plot (same format)")
        self._io_summary.setText("<br>".join(lines + out))

    def _show_excel_data_used(self):
        import copy

        defs = copy.deepcopy(self._EXCEL_COLUMNS)
        overrides = getattr(self, "_excel_col_overrides", {})
        for column_def in defs:
            if column_def["var_id"] in overrides:
                column_def["column"] = overrides[column_def["var_id"]]
        dlg = ExcelDataUsedDialog(
            "Association Rule Learning", defs, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._excel_col_overrides = dlg.get_columns()

    def save_settings_if_enabled(self):
        return _save_settings_if_enabled(self)

    def get_values(self):
        manual_map = {}
        text = self.arl_manual_groups.text().strip()
        if text:
            for pair in text.split(","):
                pair = pair.strip()
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    manual_map[key.strip()] = value.strip()
        features = [feature.strip() for feature in self.arl_features.text().split(",")
                    if feature.strip()]
        return {
            "excel_path": self.excel_path.text(),
            "output_folder": self.output_folder.text(),
            "ARL_DATASET": self.arl_dataset.currentText(),
            "ARL_FEATURES": features,
            "ARL_BIN_METHOD": self.arl_bin_method.currentText(),
            "ARL_N_BINS": _to_int(self.arl_n_bins.text(), 3),
            "ARL_BIN_LABELS": self.arl_bin_labels.text(),
            "ARL_INCLUDE_GROUP": self.arl_include_group.isChecked(),
            "ARL_GROUP_SOURCE": self.arl_group_source.currentText(),
            "ARL_GROUP_PATTERN": self.arl_group_pattern.text(),
            "ARL_GROUP_CSV_PATH": self.arl_group_csv_path.text(),
            "ARL_MANUAL_GROUPS": manual_map,
            "ARL_GROUP_EXCEL_COLUMN":
                self.arl_group_excel_column.text().strip() or "Group",
            "ARL_UNGROUPED_LABEL": self.arl_ungrouped_label.text(),
            "ARL_MIN_SUPPORT": _to_float(self.arl_min_support.text(), 0.15),
            "ARL_MIN_CONFIDENCE":
                _to_float(self.arl_min_confidence.text(), 0.60),
            "ARL_MIN_LIFT": _to_float(self.arl_min_lift.text(), 1.10),
            "ARL_MAX_ITEMSET_SIZE": _to_int(self.arl_max_itemset.text(), 4),
            "ARL_REQUIRE_GROUP_IN_CONSEQUENT":
                self.arl_require_group.isChecked(),
            "ARL_TOP_N": _to_int(self.arl_top_n.text(), 15),
            "ARL_FIG_WIDTH": _to_float(self.arl_width.text(), 12),
            "ARL_FIG_HEIGHT": _to_float(self.arl_height.text(), 7),
            "ARL_DPI": _to_int(self.arl_dpi.text(), 300),
            "ARL_BG_COLOR": self.arl_bg_color.text().strip() or "#ffffff",
            "ARL_PALETTE":
                self.arl_palette.currentText().strip() or "viridis",
            "ARL_TITLE_FONTSIZE": _to_int(self.arl_title_fs.text(), 15),
            "ARL_AXIS_FONTSIZE": _to_int(self.arl_axis_fs.text(), 12),
            "ARL_TICK_FONTSIZE": _to_int(self.arl_tick_fs.text(), 10),
            "ARL_OUTPUT_FORMAT": self.arl_output_format.currentText(),
            "ARL_DRAW_NETWORK": self.arl_draw_network.isChecked(),
        }

    def set_values(self, d):
        if "excel_path" in d:
            self.excel_path.setText(str(d["excel_path"]))
        if "output_folder" in d:
            self.output_folder.setText(str(d["output_folder"]))
        self.arl_dataset.setCurrentText(str(d.get("ARL_DATASET", "raw")))
        features = d.get("ARL_FEATURES",
                         ["nPVI (Isochrony)",
                          "r_k Entropy (Categorical Measure)",
                          "CV of Intervals", "Mean IOI (ms)",
                          "Total Onsets Used"])
        if isinstance(features, list):
            self.arl_features.setText(", ".join(features))
        else:
            self.arl_features.setText(str(features))
        self.arl_bin_method.setCurrentText(
            str(d.get("ARL_BIN_METHOD", "quantile")))
        self.arl_n_bins.setText(str(d.get("ARL_N_BINS", 3)))
        self.arl_bin_labels.setText(
            str(d.get("ARL_BIN_LABELS", "low, medium, high")))
        self.arl_include_group.setChecked(
            bool(d.get("ARL_INCLUDE_GROUP", True)))
        self.arl_group_source.setCurrentText(
            str(d.get("ARL_GROUP_SOURCE", "filename_pattern")))
        self.arl_group_pattern.setText(
            str(d.get("ARL_GROUP_PATTERN", r"(?P<group>[A-Za-z]+)_")))
        self.arl_group_csv_path.setText(str(d.get("ARL_GROUP_CSV_PATH", "")))
        manual_groups = d.get("ARL_MANUAL_GROUPS", {})
        if isinstance(manual_groups, dict):
            self.arl_manual_groups.setText(
                ", ".join(f"{key}={value}" for key, value in manual_groups.items()))
        else:
            self.arl_manual_groups.setText(str(manual_groups))
        self.arl_group_excel_column.setText(
            str(d.get("ARL_GROUP_EXCEL_COLUMN", "Group")))
        self.arl_ungrouped_label.setText(
            str(d.get("ARL_UNGROUPED_LABEL", "Ungrouped")))
        self.arl_min_support.setText(str(d.get("ARL_MIN_SUPPORT", 0.15)))
        self.arl_min_confidence.setText(
            str(d.get("ARL_MIN_CONFIDENCE", 0.60)))
        self.arl_min_lift.setText(str(d.get("ARL_MIN_LIFT", 1.10)))
        self.arl_max_itemset.setText(
            str(d.get("ARL_MAX_ITEMSET_SIZE", 4)))
        self.arl_require_group.setChecked(
            bool(d.get("ARL_REQUIRE_GROUP_IN_CONSEQUENT", False)))
        self.arl_top_n.setText(str(d.get("ARL_TOP_N", 15)))
        self.arl_width.setText(str(d.get("ARL_FIG_WIDTH", 12)))
        self.arl_height.setText(str(d.get("ARL_FIG_HEIGHT", 7)))
        self.arl_dpi.setText(str(d.get("ARL_DPI", 300)))
        self.arl_bg_color.setText(str(d.get("ARL_BG_COLOR", "#ffffff")))
        palette = d.get("ARL_PALETTE", "viridis")
        idx = self.arl_palette.findText(str(palette))
        if idx >= 0:
            self.arl_palette.setCurrentIndex(idx)
        else:
            self.arl_palette.setEditText(str(palette))
        self.arl_title_fs.setText(str(d.get("ARL_TITLE_FONTSIZE", 15)))
        self.arl_axis_fs.setText(str(d.get("ARL_AXIS_FONTSIZE", 12)))
        self.arl_tick_fs.setText(str(d.get("ARL_TICK_FONTSIZE", 10)))
        fmt = d.get("ARL_OUTPUT_FORMAT", "png")
        idx = self.arl_output_format.findText(str(fmt))
        if idx >= 0:
            self.arl_output_format.setCurrentIndex(idx)
        self.arl_draw_network.setChecked(
            bool(d.get("ARL_DRAW_NETWORK", True)))