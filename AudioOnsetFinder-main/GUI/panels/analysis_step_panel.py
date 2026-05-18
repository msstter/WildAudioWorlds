from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

try:
    from form_widgets import (
        ExcelDataUsedDialog,
        FilePicker,
        FolderPicker,
        _ALL_IO_SUMMARIES,
        _add_row,
        _make_auto_set,
        _resolve_auto_config,
        _update_auto_desc,
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
        ExcelDataUsedDialog,
        FilePicker,
        FolderPicker,
        _ALL_IO_SUMMARIES,
        _add_row,
        _make_auto_set,
        _resolve_auto_config,
        _update_auto_desc,
        get_form_widget_palette,
    )
    from GUI.panel_settings_helpers import (
        _build_settings_preset_section,
        _export_settings_for,
        _import_settings_for,
        _on_saved_settings_selected,
        _save_settings_if_enabled,
    )


class AnalysisStepPanel(QScrollArea):
    """Data-driven panel used for the multi-species rhythmic analyses."""

    def __init__(self, spec: dict, parent=None):
        super().__init__(parent)
        self._spec = spec
        self._widgets: dict = {}
        self._excel_col_overrides: dict = {}
        self._palette = get_form_widget_palette()
        self.setWidgetResizable(True)

        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setSpacing(12)
        lay.setContentsMargins(16, 16, 16, 16)

        hdr = QLabel(f"<b>{spec['title']}</b>")
        hdr.setStyleSheet(
            f"color: {self._palette.accent}; font-size: 16px; background: transparent;")
        lay.addWidget(hdr)
        subtitle = spec.get("subtitle", "")
        if subtitle:
            sl = QLabel(subtitle)
            sl.setWordWrap(True)
            sl.setStyleSheet(
                f"color: {self._palette.text_dim}; background: transparent; font-size: 12px;")
            lay.addWidget(sl)

        grp = QGroupBox("Input / Output")
        g = QVBoxLayout(grp)

        self.excel_path = FilePicker("", "Excel files (*.xlsx *.xls)")
        self.excel_path.line_edit.setPlaceholderText(
            "Excel file from Onset Finder output")
        _add_row(g, "Input Excel file", self.excel_path,
                 "Excel workbook produced by Step 3 (Onset Finder).",
                 extended_desc=(
                     "Path to the .xlsx file containing the per-file rhythm "
                     "metrics and dyadic events this step consumes. This is "
                     "the workbook written by the Onset Finder (Step 3) — it "
                     "has sheets like 'File Summaries' and 'Dyadic Events'."),
                 novice_desc=(
                     "This is the spreadsheet full of rhythm numbers the "
                     "program made for you in an earlier step. Think of it "
                     "as the ingredient list the analysis will cook with."),
                 label_width=160)
        self._input_auto_cb, self._input_auto_desc = _make_auto_set(
            self.excel_path, g,
            "↳ Auto: Set to the <b>Output Excel</b> from Step 3 (Onset Finder)",
            step_name=spec["title"], io_type="input",
            auto_config={"source_step": "Onset Finder", "source_io": "output",
                         "suffix": "", "use_dirname": False,
                         "use_basename": False})

        self.output_folder = FolderPicker("")
        default_out = spec.get("output_folder", "Output")
        self.output_folder.line_edit.setPlaceholderText(
            f"Output folder (default: {default_out})")
        _add_row(g, "Output folder", self.output_folder,
                 "Folder where outputs are saved (CSV + plots).",
                 extended_desc=(
                     "All CSV summaries and plots produced by this step are "
                     "written into this folder. If it does not exist, the "
                     f"pipeline will create it. Default name: '{default_out}'."),
                 novice_desc=(
                     "Pick the folder where you want the program to put the "
                     "results. If you leave the checkbox on, it will just "
                     "drop a results folder next to your input file — like "
                     "saving homework next to the assignment sheet."),
                 label_width=160)
        self._output_auto_cb, self._output_auto_desc = _make_auto_set(
            self.output_folder, g,
            f"↳ Auto: Saved in a '<i>{default_out}</i>' folder alongside "
            f"the Input Excel file",
            step_name=spec["title"], io_type="output",
            auto_config={"source_step": "(this step)", "source_io": "input",
                         "suffix": default_out, "use_dirname": True,
                         "use_basename": False})
        self._output_auto_cb.stateChanged.connect(self._on_output_auto_toggled)
        self.excel_path.line_edit.textChanged.connect(self._on_excel_changed)

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

        self._excel_scan_warning = QLabel()
        self._excel_scan_warning.setWordWrap(True)
        self._excel_scan_warning.setStyleSheet(
            "color: #c76b2a; background: rgba(199, 107, 42, 0.08); "
            "font-size: 11px; padding: 6px 8px; "
            "border: 1px solid #c76b2a; border-radius: 4px;"
        )
        self._excel_scan_warning.hide()
        g.addWidget(self._excel_scan_warning)

        lay.addWidget(grp)

        sgrp = QGroupBox(f"{spec['title']} — Settings")
        sg = QVBoxLayout(sgrp)

        for setting in spec.get("settings", []):
            widget = self._build_widget(setting)
            if widget is None:
                continue
            self._widgets[setting["key"]] = (widget, setting)
            _add_row(sg, setting["label"], widget,
                     setting.get("help", ""),
                     extended_desc=setting.get("help_detailed") or setting.get("help", ""),
                     novice_desc=setting.get("help_novice"),
                     label_width=220)

        lay.addWidget(sgrp)

        pgrp = QGroupBox("General plot settings")
        pg = QVBoxLayout(pgrp)
        self.plot_title = QLineEdit("")
        _add_row(pg, "Plot title (optional)", self.plot_title,
                 "Override the default figure title.",
                 extended_desc=(
                     "If filled in, this text replaces the automatic title "
                     "on the main figure. Leave blank to use the step's "
                     "default title."),
                 novice_desc=(
                     "The big caption at the top of the chart. Leave empty "
                     "to let the program pick one; type your own if you "
                     "want a custom headline."),
                 label_width=220)
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(50, 1200)
        self.dpi_spin.setValue(300)
        _add_row(pg, "DPI", self.dpi_spin,
                 "Resolution of saved figures.",
                 extended_desc=(
                     "Dots per inch for saved raster images (PNG/JPG). "
                     "300 is journal-quality; 150 is fine for slides; "
                     "72 is screen-resolution."),
                 novice_desc=(
                     "How sharp the picture is. Bigger number = crisper "
                     "image but larger file — like choosing 'HD' vs 'SD' "
                     "on a video."),
                 label_width=220)
        self.fig_w = QDoubleSpinBox()
        self.fig_w.setRange(1.0, 40.0)
        self.fig_w.setValue(10.0)
        _add_row(pg, "Figure width (in)", self.fig_w,
                 "Width of the saved figure in inches.",
                 extended_desc=(
                     "Canvas width in inches. Wider figures give more room "
                     "for long x-axis labels or many groups."),
                 novice_desc=(
                     "How wide the picture is, measured in inches. Think "
                     "of the size of a printed photo."),
                 label_width=220)
        self.fig_h = QDoubleSpinBox()
        self.fig_h.setRange(1.0, 40.0)
        self.fig_h.setValue(6.0)
        _add_row(pg, "Figure height (in)", self.fig_h,
                 "Height of the saved figure in inches.",
                 extended_desc=(
                     "Canvas height in inches. Taller figures help when "
                     "stacking many rows or showing very wide y-axis ranges."),
                 novice_desc=(
                     "How tall the picture is, in inches. Pair it with the "
                     "width to control the overall shape."),
                 label_width=220)
        self.out_format = QComboBox()
        self.out_format.addItems(["png", "pdf", "svg", "jpg"])
        _add_row(pg, "Output format", self.out_format,
                 "Image format for saved plots.",
                 extended_desc=(
                     "File format for saved figures: PNG (raster, small, "
                     "universal), PDF / SVG (vector, infinitely scalable, "
                     "best for publications), JPG (raster, lossy)."),
                 novice_desc=(
                     "What kind of image file to save. PNG is the normal "
                     "web picture; PDF and SVG can be zoomed in forever "
                     "without getting blurry — great for printing."),
                 label_width=220)
        self.bg_color = QLineEdit("#ffffff")
        _add_row(pg, "Background color", self.bg_color,
                 "Hex color for figure background.",
                 extended_desc=(
                     "Six-digit hex code (e.g. #ffffff for white, #000000 "
                     "for black) used as the figure background. Accepts any "
                     "valid matplotlib colour string."),
                 novice_desc=(
                     "The paper colour behind the chart. Type a colour code "
                     "like #ffffff for white or #000000 for black — like "
                     "choosing the colour of construction paper."),
                 label_width=220)
        lay.addWidget(pgrp)

        step_name = self._spec["title"]
        _build_settings_preset_section(
            self, lay, step_name, self.excel_path, presets_dict=None)
        self._import_settings_btn.clicked.connect(
            lambda _checked=False, sn=step_name: _import_settings_for(self, sn))
        self._export_settings_btn.clicked.connect(
            lambda _checked=False, sn=step_name: _export_settings_for(self, sn))
        self._saved_settings_combo.currentTextChanged.connect(
            lambda name, sn=step_name: _on_saved_settings_selected(
                self, sn, name))

        lay.addStretch()
        self.setWidget(content)

    def _build_widget(self, spec: dict):
        widget_type = spec.get("type", "str")
        default = spec.get("default")
        if widget_type == "int":
            widget = QSpinBox()
            widget.setRange(spec.get("min", -10 ** 9), spec.get("max", 10 ** 9))
            widget.setValue(int(default) if default is not None else 0)
            return widget
        if widget_type == "float":
            widget = QDoubleSpinBox()
            widget.setDecimals(spec.get("decimals", 4))
            widget.setRange(spec.get("min", -1e9), spec.get("max", 1e9))
            widget.setSingleStep(spec.get("step", 0.01))
            widget.setValue(float(default) if default is not None else 0.0)
            return widget
        if widget_type == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(default))
            return widget
        if widget_type == "choice":
            widget = QComboBox()
            for choice in spec.get("choices", []):
                widget.addItem(str(choice))
            if default is not None and str(default) in [widget.itemText(i)
                                                        for i in range(widget.count())]:
                widget.setCurrentText(str(default))
            return widget
        if widget_type == "list":
            return QLineEdit(", ".join(str(x) for x in (default or [])))
        return QLineEdit("" if default is None else str(default))

    def _widget_value(self, widget, spec):
        widget_type = spec.get("type", "str")
        if widget_type == "int":
            return int(widget.value())
        if widget_type == "float":
            return float(widget.value())
        if widget_type == "bool":
            return bool(widget.isChecked())
        if widget_type == "choice":
            return widget.currentText()
        if widget_type == "list":
            text = widget.text().strip()
            if not text:
                return []
            return [part.strip() for part in text.split(",") if part.strip()]
        return widget.text()

    def _set_widget_value(self, widget, spec, value):
        widget_type = spec.get("type", "str")
        try:
            if widget_type == "int":
                widget.setValue(int(value))
            elif widget_type == "float":
                widget.setValue(float(value))
            elif widget_type == "bool":
                widget.setChecked(bool(value))
            elif widget_type == "choice":
                widget.setCurrentText(str(value))
            elif widget_type == "list":
                if isinstance(value, list):
                    widget.setText(", ".join(str(x) for x in value))
                else:
                    widget.setText(str(value))
            else:
                widget.setText(str(value))
        except Exception:
            pass

    def _on_excel_changed(self, text):
        if self._output_auto_cb.isChecked():
            cfg = self._output_auto_cb.auto_config
            resolved = _resolve_auto_config(text, cfg)
            if resolved:
                self.output_folder.line_edit.setText(resolved)
        self._scan_excel_columns()

    def _scan_excel_columns(self):
        path = self.excel_path.line_edit.text().strip()
        warn = self._excel_scan_warning
        if not path or not os.path.isfile(path):
            warn.hide()
            return

        import copy
        defs = copy.deepcopy(self._default_excel_columns())
        for cd in defs:
            if cd["var_id"] in self._excel_col_overrides:
                cd["column"] = self._excel_col_overrides[cd["var_id"]]
        required = [cd["column"] for cd in defs
                    if cd.get("column", "").strip()]
        seen_cols: set[str] = set()
        required = [c for c in required
                    if not (c in seen_cols or seen_cols.add(c))]
        if not required:
            warn.hide()
            return

        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            headers = set()
            for ws in wb.worksheets:
                row = next(ws.iter_rows(min_row=1, max_row=1,
                                        values_only=True), None)
                if row:
                    for cell in row:
                        if cell is not None:
                            headers.add(str(cell).strip())
            wb.close()
        except Exception as exc:
            warn.setText(
                f"⚠ Could not read Excel file ({type(exc).__name__}): {exc}")
            warn.show()
            return

        missing = [c for c in required if c not in headers]
        if not missing:
            warn.hide()
            return

        desc_by_col = {cd["column"]: cd.get("description", "")
                       for cd in defs}
        lines = ["⚠ Input Excel is missing columns required by this test:"]
        for col in missing:
            desc = desc_by_col.get(col, "")
            if desc:
                lines.append(f"   • <b>{col}</b> — {desc}")
            else:
                lines.append(f"   • <b>{col}</b>")
        lines.append(
            "<i>Click 'Excel Data Used…' to rename the expected columns, "
            "or re-run the Onset Finder to regenerate this workbook.</i>")
        warn.setText("<br>".join(lines))
        warn.show()

    def _on_output_auto_toggled(self, state):
        if bool(state):
            self._on_excel_changed(self.excel_path.line_edit.text())

    def _default_excel_columns(self):
        rows = [
            {"var_id": "file_name", "column": "File Name",
             "default": "File Name",
             "description": "Identifies each recording / audio file"},
            {"var_id": "group", "column": "Group", "default": "Group",
             "description": "Grouping label used for per-group analyses"},
        ]
        spec = self._spec
        for extra in spec.get("excel_columns", []):
            rows.append(dict(extra))
        prefix = spec["prefix"]
        inferred: list[tuple[str, str, str]] = []
        for key, (widget, widget_spec) in self._widgets.items():
            full = prefix + key
            val = self._widget_value(widget, widget_spec)
            if key == "CLASS_COLUMN" and isinstance(val, str) and val:
                inferred.append(("class_column", val,
                                 "Class column for pDFA"))
            elif key == "UNIT_COLUMN" and isinstance(val, str) and val:
                inferred.append(("unit_column", val,
                                 "Unit column (species / group / individual)"))
            elif key == "RESPONSE" and isinstance(val, str) and val:
                inferred.append(("response", val, "Response variable"))
            elif key == "PREDICTORS" and isinstance(val, list):
                for i, p in enumerate(val):
                    inferred.append((f"predictor_{i+1}", str(p),
                                     "Predictor / covariate"))
            elif key == "FIXED_EFFECTS" and isinstance(val, list):
                for i, p in enumerate(val):
                    inferred.append((f"fixed_{i+1}", str(p),
                                     "GLMM fixed effect"))
            elif key == "RANDOM_EFFECTS" and isinstance(val, list):
                for i, p in enumerate(val):
                    inferred.append((f"random_{i+1}", str(p),
                                     "GLMM random effect"))
            elif key == "METRICS" and isinstance(val, list):
                for i, p in enumerate(val):
                    inferred.append((f"metric_{i+1}", str(p),
                                     "Metric to plot"))
            elif key in ("GEO_LAT_COLUMN", "GEO_LON_COLUMN") and val:
                inferred.append((key.lower(), val,
                                 "Geographic coordinate column"))
        seen = {r["var_id"] for r in rows}
        for var_id, col, desc in inferred:
            if var_id in seen:
                continue
            rows.append({"var_id": var_id, "column": col,
                         "default": col, "description": desc})
            seen.add(var_id)
        return rows

    def _show_excel_data_used(self):
        import copy
        defs = copy.deepcopy(self._default_excel_columns())
        for cd in defs:
            if cd["var_id"] in self._excel_col_overrides:
                cd["column"] = self._excel_col_overrides[cd["var_id"]]
        dlg = ExcelDataUsedDialog(self._spec["title"], defs, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._excel_col_overrides = dlg.get_columns()
            self._scan_excel_columns()

    def get_values(self) -> dict:
        out = {
            "excel_path": self.excel_path.text(),
            "output_folder": self.output_folder.text(),
            "_input_auto_set": bool(self._input_auto_cb.isChecked()),
            "_input_auto_config": dict(getattr(self._input_auto_cb, "auto_config", {}) or {}),
            "_output_auto_set": bool(self._output_auto_cb.isChecked()),
            "_output_auto_config": dict(getattr(self._output_auto_cb, "auto_config", {}) or {}),
            "_PLOT_TITLE": self.plot_title.text(),
            "_FIG_WIDTH": float(self.fig_w.value()),
            "_FIG_HEIGHT": float(self.fig_h.value()),
            "_DPI": int(self.dpi_spin.value()),
            "_OUTPUT_FORMAT": self.out_format.currentText(),
            "_BG_COLOR": self.bg_color.text(),
            "_excel_col_overrides": dict(self._excel_col_overrides),
        }
        prefix = self._spec["prefix"]
        for key, (widget, widget_spec) in self._widgets.items():
            out[prefix + key] = self._widget_value(widget, widget_spec)
        out[prefix + "TITLE"] = out["_PLOT_TITLE"] or self._spec["title"]
        out[prefix + "FIG_WIDTH"] = out["_FIG_WIDTH"]
        out[prefix + "FIG_HEIGHT"] = out["_FIG_HEIGHT"]
        out[prefix + "DPI"] = out["_DPI"]
        out[prefix + "OUTPUT_FORMAT"] = out["_OUTPUT_FORMAT"]
        out[prefix + "BG_COLOR"] = out["_BG_COLOR"]
        return out

    def set_values(self, vals: dict):
        if "excel_path" in vals:
            self.excel_path.line_edit.setText(str(vals["excel_path"]))
        if "output_folder" in vals:
            self.output_folder.line_edit.setText(str(vals["output_folder"]))
        if "_input_auto_set" in vals:
            try:
                self._input_auto_cb.setChecked(bool(vals["_input_auto_set"]))
            except Exception:
                pass
        if "_input_auto_config" in vals and isinstance(
                vals["_input_auto_config"], dict):
            self._input_auto_cb.auto_config = dict(vals["_input_auto_config"])
            _update_auto_desc(self._input_auto_cb, self._input_auto_desc)
        if "_output_auto_set" in vals:
            try:
                self._output_auto_cb.setChecked(bool(vals["_output_auto_set"]))
            except Exception:
                pass
        if "_output_auto_config" in vals and isinstance(
                vals["_output_auto_config"], dict):
            self._output_auto_cb.auto_config = dict(vals["_output_auto_config"])
            _update_auto_desc(self._output_auto_cb, self._output_auto_desc)
        if "_excel_col_overrides" in vals and isinstance(
                vals["_excel_col_overrides"], dict):
            self._excel_col_overrides = dict(vals["_excel_col_overrides"])
        prefix = self._spec["prefix"]
        for key, (widget, widget_spec) in self._widgets.items():
            if prefix + key in vals:
                self._set_widget_value(widget, widget_spec, vals[prefix + key])
        if prefix + "TITLE" in vals:
            self.plot_title.setText(str(vals.get(prefix + "TITLE", "")))
        if prefix + "DPI" in vals:
            try:
                self.dpi_spin.setValue(int(vals[prefix + "DPI"]))
            except Exception:
                pass
        if prefix + "FIG_WIDTH" in vals:
            try:
                self.fig_w.setValue(float(vals[prefix + "FIG_WIDTH"]))
            except Exception:
                pass
        if prefix + "FIG_HEIGHT" in vals:
            try:
                self.fig_h.setValue(float(vals[prefix + "FIG_HEIGHT"]))
            except Exception:
                pass
        if prefix + "OUTPUT_FORMAT" in vals:
            self.out_format.setCurrentText(str(vals[prefix + "OUTPUT_FORMAT"]))
        if prefix + "BG_COLOR" in vals:
            self.bg_color.setText(str(vals[prefix + "BG_COLOR"]))

    def save_settings_if_enabled(self):
        return _save_settings_if_enabled(self)


__all__ = ["AnalysisStepPanel"]