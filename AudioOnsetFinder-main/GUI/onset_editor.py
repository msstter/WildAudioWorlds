"""
OnsetEditorPanel — Interactive onset editing panel for the Bioacoustics Rhythm Pipeline.

Provides a full onset editing workflow:
- File browser (folder picker + file combo)
- AudioViewerWidget (waveform + spectrogram with draggable onset markers)
- Editable QTableWidget showing onset times, IOIs, r_k, stable flag
- Toolbar with Add/Remove/Save, Undo/Redo
- Load/Save Audacity label files and Excel

Dependencies: PyQt6, numpy, audio_viewer (AudioViewerWidget).
Optional: openpyxl (for Excel I/O), librosa (for audio loading).
"""

from __future__ import annotations

import copy
import json
import os
import platform
import re
import sys
from typing import List, Optional

import librosa
import numpy as np
import pandas as pd

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

try:
    from onset_editor_analysis import (
        _analyze_focus_region_settings as _analyze_focus_region_settings_impl,
        _build_per_signal_variable_checks as _build_per_signal_variable_checks_impl,
        _build_focus_signal_profile as _build_focus_signal_profile_impl,
        _build_signal_profile_from_saved_dirs as _build_signal_profile_from_saved_dirs_impl,
        _build_region_detector_kwargs as _build_region_detector_kwargs_impl,
        _build_uniform_probe_times as _build_uniform_probe_times_impl,
        _candidate_peak_times_for_region as _candidate_peak_times_for_region_impl,
        _compute_per_signal_spectral_threshold as _compute_per_signal_spectral_threshold_impl,
        _compute_per_signal_variable_score_threshold as _compute_per_signal_variable_score_threshold_impl,
        _compute_spectral_similarity_at_time as _compute_spectral_similarity_at_time_impl,
        _diagnose_candidate_matches as _diagnose_candidate_matches_impl,
        _evaluate_exemplar_self_check as _evaluate_exemplar_self_check_impl,
        _extract_recommended_detect_settings as _extract_recommended_detect_settings_impl,
        _format_match_miss_reason as _format_match_miss_reason_impl,
        _merge_negative_detection_hits as _merge_negative_detection_hits_impl,
        _recover_focus_region_onset as _recover_focus_region_onset_impl,
        _region_contains_onset as _region_contains_onset_impl,
        _score_onsets_by_variable_match as _score_onsets_by_variable_match_impl,
        _summarize_signal_region_analyses as _summarize_signal_region_analyses_impl,
    )
    from onset_editor_detection import _DetectOnsetsWorker as _ExtractedDetectOnsetsWorker
    from onset_editor_dialogs import (
        _AnalyzeSignalsDialog as _ExtractedAnalyzeSignalsDialog,
        _ExcelColumnDialog as _ExtractedExcelColumnDialog,
        _ExcelSaveDialog as _ExtractedExcelSaveDialog,
        _OnsetEditorSettingsDialog,
    )
    from onset_editor_io import (
        _HOTKEY_DEFS,
        _HAS_EXCEL_IO,
        _build_load_selections_request as _build_load_selections_request_impl,
        _extract_region_audio as _extract_region_audio_impl,
        _export_selections_audio as _export_selections_audio_impl,
        _eio,
        _find_label_file,
        _get_hotkey_map,
        _list_audio_files,
        _load_hotkey_overrides,
        _load_labels,
        _load_muter_presets,
        _load_saved_selections as _load_saved_selections_impl,
        _next_export_number as _next_export_number_impl,
        _read_selection_manifest,
        _review_audio_paths,
        _regions_from_manifests,
        _resolve_restored_file_selection,
        _load_saved_onset_session_for_audio,
        _save_hotkey_overrides,
        _save_labels,
        _selection_manifest_filename,
        _summarize_load_selections_error as _summarize_load_selections_error_impl,
        _write_audio_file,
        _write_selection_manifest,
        _write_focus_regions_json as _write_focus_regions_json_impl,
        _write_onset_layer_settings as _write_onset_layer_settings_impl,
    )
    from onset_editor_state import (
        OnsetLayerState as _OnsetLayerState,
        _UndoStack,
        add_shared_comparison_onsets as _add_shared_comparison_onsets_impl,
        add_unique_comparison_onsets as _add_unique_comparison_onsets_impl,
        activate_layer_range as _activate_layer_range_impl,
        append_empty_layer as _append_empty_layer_impl,
        append_layer_state as _append_layer_state_impl,
        append_merged_layer as _append_merged_layer_impl,
        build_panel_config_snapshot as _build_panel_config_snapshot_impl,
        build_loaded_onset_session as _build_loaded_onset_session_impl,
        build_save_selections_export_plan as _build_save_selections_export_plan_impl,
        build_comparison_display_state as _build_comparison_display_state_impl,
        classify_comparison_onsets as _classify_comparison_onsets_impl,
        compute_ioi as _compute_ioi_impl,
        compute_rk as _compute_rk_impl,
        compute_stable as _compute_stable_impl,
        deserialize_layers as _deserialize_layer_states,
        extract_scalar_config_restore_values as _extract_scalar_config_restore_values_impl,
        format_checked_layer_label as _format_checked_layer_label_impl,
        filter_removed_onsets as _filter_removed_onsets_impl,
        hydrate_layer_state as _hydrate_layer_state,
        load_layer_state as _load_active_layer_state,
        make_default_layer as _make_default_layer_state,
        merge_onsets as _merge_onsets_impl,
        build_layer_overlay_markers as _build_layer_overlay_markers_impl,
        remove_active_layer as _remove_active_layer_impl,
        remove_main_only_onsets as _remove_main_only_onsets_impl,
        remove_onsets_in_range as _remove_onsets_in_range_impl,
        restore_configured_layers as _restore_configured_layers_impl,
        reset_layers_for_loaded_file as _reset_layers_for_loaded_file_impl,
        restore_loaded_focus_regions as _restore_loaded_focus_regions_impl,
        serialize_layers as _serialize_layer_states,
        save_layer_state as _save_active_layer_state,
        select_exclusive_layer as _select_exclusive_layer_impl,
        summarize_loaded_selections_feedback as _summarize_loaded_selections_feedback_impl,
        summarize_save_selections_preflight as _summarize_save_selections_preflight_impl,
        summarize_focus_region_status as _summarize_focus_region_status_impl,
        summarize_focus_restore_state as _summarize_focus_restore_state_impl,
        summarize_review_finish_state as _summarize_review_finish_state_impl,
        summarize_review_navigation_state as _summarize_review_navigation_state_impl,
        summarize_layer_selection_change as _summarize_layer_selection_change_impl,
        switch_active_layer as _switch_active_layer_impl,
        transfer_focus_region as _transfer_focus_region_impl,
    )
    from onset_editor_workbench_dialogs import (
        OnsetManagerDialog as _ExtractedOnsetManagerDialog,
        _DetectOnsetsDialog as _ExtractedDetectOnsetsDialog,
        _LayerCheckboxMenu as _ExtractedLayerCheckboxMenu,
        _LoadSelectionsDialog as _ExtractedLoadSelectionsDialog,
        _MfccAudioEditDialog as _ExtractedMfccAudioEditDialog,
        _NegativeSubtractionDialog as _ExtractedNegativeSubtractionDialog,
        _PerSignalConfigDialog as _ExtractedPerSignalConfigDialog,
        _SaveSelectionsDialog as _ExtractedSaveSelectionsDialog,
        _default_signal_export_dirs as _default_signal_export_dirs_impl,
    )
except ImportError:
    from GUI.onset_editor_analysis import (
        _analyze_focus_region_settings as _analyze_focus_region_settings_impl,
        _build_per_signal_variable_checks as _build_per_signal_variable_checks_impl,
        _build_focus_signal_profile as _build_focus_signal_profile_impl,
        _build_signal_profile_from_saved_dirs as _build_signal_profile_from_saved_dirs_impl,
        _build_region_detector_kwargs as _build_region_detector_kwargs_impl,
        _build_uniform_probe_times as _build_uniform_probe_times_impl,
        _candidate_peak_times_for_region as _candidate_peak_times_for_region_impl,
        _compute_per_signal_spectral_threshold as _compute_per_signal_spectral_threshold_impl,
        _compute_per_signal_variable_score_threshold as _compute_per_signal_variable_score_threshold_impl,
        _compute_spectral_similarity_at_time as _compute_spectral_similarity_at_time_impl,
        _diagnose_candidate_matches as _diagnose_candidate_matches_impl,
        _evaluate_exemplar_self_check as _evaluate_exemplar_self_check_impl,
        _extract_recommended_detect_settings as _extract_recommended_detect_settings_impl,
        _format_match_miss_reason as _format_match_miss_reason_impl,
        _merge_negative_detection_hits as _merge_negative_detection_hits_impl,
        _recover_focus_region_onset as _recover_focus_region_onset_impl,
        _region_contains_onset as _region_contains_onset_impl,
        _score_onsets_by_variable_match as _score_onsets_by_variable_match_impl,
        _summarize_signal_region_analyses as _summarize_signal_region_analyses_impl,
    )
    from GUI.onset_editor_detection import _DetectOnsetsWorker as _ExtractedDetectOnsetsWorker
    from GUI.onset_editor_dialogs import (
        _AnalyzeSignalsDialog as _ExtractedAnalyzeSignalsDialog,
        _ExcelColumnDialog as _ExtractedExcelColumnDialog,
        _ExcelSaveDialog as _ExtractedExcelSaveDialog,
        _OnsetEditorSettingsDialog,
    )
    from GUI.onset_editor_io import (
        _HOTKEY_DEFS,
        _HAS_EXCEL_IO,
        _build_load_selections_request as _build_load_selections_request_impl,
        _extract_region_audio as _extract_region_audio_impl,
        _export_selections_audio as _export_selections_audio_impl,
        _eio,
        _find_label_file,
        _get_hotkey_map,
        _list_audio_files,
        _load_hotkey_overrides,
        _load_labels,
        _load_muter_presets,
        _load_saved_selections as _load_saved_selections_impl,
        _next_export_number as _next_export_number_impl,
        _read_selection_manifest,
        _review_audio_paths,
        _regions_from_manifests,
        _resolve_restored_file_selection,
        _load_saved_onset_session_for_audio,
        _save_hotkey_overrides,
        _save_labels,
        _selection_manifest_filename,
        _summarize_load_selections_error as _summarize_load_selections_error_impl,
        _write_selection_manifest,
        _write_focus_regions_json as _write_focus_regions_json_impl,
        _write_onset_layer_settings as _write_onset_layer_settings_impl,
    )
    from GUI.onset_editor_state import (
        OnsetLayerState as _OnsetLayerState,
        _UndoStack,
        add_shared_comparison_onsets as _add_shared_comparison_onsets_impl,
        add_unique_comparison_onsets as _add_unique_comparison_onsets_impl,
        activate_layer_range as _activate_layer_range_impl,
        append_empty_layer as _append_empty_layer_impl,
        append_layer_state as _append_layer_state_impl,
        append_merged_layer as _append_merged_layer_impl,
        build_panel_config_snapshot as _build_panel_config_snapshot_impl,
        build_loaded_onset_session as _build_loaded_onset_session_impl,
        build_save_selections_export_plan as _build_save_selections_export_plan_impl,
        build_comparison_display_state as _build_comparison_display_state_impl,
        classify_comparison_onsets as _classify_comparison_onsets_impl,
        compute_ioi as _compute_ioi_impl,
        compute_rk as _compute_rk_impl,
        compute_stable as _compute_stable_impl,
        deserialize_layers as _deserialize_layer_states,
        extract_scalar_config_restore_values as _extract_scalar_config_restore_values_impl,
        format_checked_layer_label as _format_checked_layer_label_impl,
        filter_removed_onsets as _filter_removed_onsets_impl,
        hydrate_layer_state as _hydrate_layer_state,
        load_layer_state as _load_active_layer_state,
        make_default_layer as _make_default_layer_state,
        merge_onsets as _merge_onsets_impl,
        build_layer_overlay_markers as _build_layer_overlay_markers_impl,
        remove_active_layer as _remove_active_layer_impl,
        remove_main_only_onsets as _remove_main_only_onsets_impl,
        remove_onsets_in_range as _remove_onsets_in_range_impl,
        restore_configured_layers as _restore_configured_layers_impl,
        reset_layers_for_loaded_file as _reset_layers_for_loaded_file_impl,
        restore_loaded_focus_regions as _restore_loaded_focus_regions_impl,
        serialize_layers as _serialize_layer_states,
        save_layer_state as _save_active_layer_state,
        select_exclusive_layer as _select_exclusive_layer_impl,
        summarize_loaded_selections_feedback as _summarize_loaded_selections_feedback_impl,
        summarize_save_selections_preflight as _summarize_save_selections_preflight_impl,
        summarize_focus_region_status as _summarize_focus_region_status_impl,
        summarize_focus_restore_state as _summarize_focus_restore_state_impl,
        summarize_review_finish_state as _summarize_review_finish_state_impl,
        summarize_review_navigation_state as _summarize_review_navigation_state_impl,
        summarize_layer_selection_change as _summarize_layer_selection_change_impl,
        switch_active_layer as _switch_active_layer_impl,
        transfer_focus_region as _transfer_focus_region_impl,
    )
    from GUI.onset_editor_workbench_dialogs import (
        OnsetManagerDialog as _ExtractedOnsetManagerDialog,
        _DetectOnsetsDialog as _ExtractedDetectOnsetsDialog,
        _LayerCheckboxMenu as _ExtractedLayerCheckboxMenu,
        _LoadSelectionsDialog as _ExtractedLoadSelectionsDialog,
        _MfccAudioEditDialog as _ExtractedMfccAudioEditDialog,
        _NegativeSubtractionDialog as _ExtractedNegativeSubtractionDialog,
        _PerSignalConfigDialog as _ExtractedPerSignalConfigDialog,
        _SaveSelectionsDialog as _ExtractedSaveSelectionsDialog,
        _default_signal_export_dirs as _default_signal_export_dirs_impl,
    )


def _monospace_css_family() -> str:
    system = platform.system()
    if system == "Darwin":
        return "Menlo"
    if system == "Windows":
        return "Consolas"
    return "DejaVu Sans Mono"

# ---------------------------------------------------------------------------
# AudioViewerWidget import (same approach as pipeline_gui.py)
# ---------------------------------------------------------------------------
try:
    from audio_viewer import AudioViewerWidget as _AudioViewerWidget
except ImportError:
    try:
        from GUI.audio_viewer import AudioViewerWidget as _AudioViewerWidget
        _AUDIO_VIEWER_IMPORT_ERROR = None
    except ImportError as exc:
        _AudioViewerWidget = None
        _AUDIO_VIEWER_IMPORT_ERROR = exc
else:
    _AUDIO_VIEWER_IMPORT_ERROR = None


def _noop_local_integration_publish(*_args, **_kwargs):
    return None


try:
    from local_integration_session import (
        clear_audio_onset_selection as _clear_audio_onset_selection_impl,
        publish_audio_onset_asset_state as _publish_audio_onset_asset_state_impl,
        publish_audio_onset_playhead as _publish_audio_onset_playhead_impl,
        publish_audio_onset_selection as _publish_audio_onset_selection_impl,
    )
except Exception:
    try:
        from GUI.local_integration_session import (
            clear_audio_onset_selection as _clear_audio_onset_selection_impl,
            publish_audio_onset_asset_state as _publish_audio_onset_asset_state_impl,
            publish_audio_onset_playhead as _publish_audio_onset_playhead_impl,
            publish_audio_onset_selection as _publish_audio_onset_selection_impl,
        )
    except Exception:
        _clear_audio_onset_selection_impl = _noop_local_integration_publish
        _publish_audio_onset_asset_state_impl = _noop_local_integration_publish
        _publish_audio_onset_playhead_impl = _noop_local_integration_publish
        _publish_audio_onset_selection_impl = _noop_local_integration_publish


def _require_audio_viewer() -> None:
    if _AudioViewerWidget is not None:
        return
    raise ImportError(
        "OnsetEditorPanel requires the optional 'pyqtgraph' viewer stack via audio_viewer.py. "
        "Install the viewer dependencies to enable the full onset editor UI."
    ) from _AUDIO_VIEWER_IMPORT_ERROR

# ---------------------------------------------------------------------------
# Theme constants (match pipeline_gui.py)
# ---------------------------------------------------------------------------
_ACCENT = "#4caf50"
_BG = "#1e1e2e"
_BG_MID = "#262636"
_BG_WIDGET = "#2c2c3c"
_BG_INPUT = "#323248"
_BORDER = "#3a3a50"
_TEXT = "#dcdcdc"
_TEXT_DIM = "#8888a0"
_TEXT_MUTED = "#6a6a82"
_ACCENT_DIM = "#2e7d32"

# Focus Onsets mode colours
_FOCUS_BLUE = "#1565c0"
_FOCUS_BLUE_BRIGHT = "#5cacff"
_FOCUS_BLUE_DARK = "#0d47a1"
_FOCUS_BLUE_DIM = "#1a3a5c"
_FOCUS_BLUE_BORDER = "#2a5a8c"
_POSITIVE_BLUE = "#2196F3"
_POSITIVE_BLUE_BORDER = "#1976D2"
_NEGATIVE_RED = "#e53935"
_NEGATIVE_RED_BORDER = "#c62828"
_STABLE_BG = QColor(76, 175, 80, 80)
_POSITIVE_REGION_COLOR = (33, 150, 243, 50)   # semi-transparent blue
_NEGATIVE_REGION_COLOR = (229, 57, 53, 50)    # semi-transparent red
_DEFAULT_STABLE_TOLERANCE = 0.25

# Layer overlay colours — each additional checked layer uses next colour
_LAYER_OVERLAY_COLORS = [
    (0, 200, 255, 200),     # cyan
    (255, 165, 0, 200),     # orange
    (180, 100, 255, 200),   # purple
    (50, 255, 150, 200),    # mint
    (255, 220, 50, 200),    # yellow
    (255, 105, 180, 200),   # pink
    (100, 200, 200, 200),   # teal
    (200, 150, 100, 200),   # tan
]
# Shared onset colour — onsets that appear in 2+ checked layers
_SHARED_ONSET_COLOR = (255, 255, 255, 240)    # white

# Negative subtraction overlay colours (changed exact from red→blue)
_NEG_EXACT_COLOR = (80, 140, 255, 220)        # blue (not red — onset lines are already red)
_NEG_CLOSE_COLOR = (255, 183, 77, 220)        # orange

_ONSET_EDITOR_TOOLTIP_REGISTRY: list[tuple[QWidget, str, str, str]] = []
_ONSET_EDITOR_DESCRIPTION_LEVEL = 0


def _tooltip_text_for_level(level: int, brief: str, detailed: str, novice: str) -> str:
    if level >= 3:
        return novice
    if level == 2:
        return detailed
    return brief


def _capture_onset_editor_tooltips(root: QWidget) -> None:
    seen_ids = {id(widget) for widget, *_ in _ONSET_EDITOR_TOOLTIP_REGISTRY}
    widgets = [root, *root.findChildren(QWidget)]
    for widget in widgets:
        brief = widget.toolTip()
        if not brief or id(widget) in seen_ids:
            continue
        detailed = widget.property("tooltip_detailed") or widget.property("detailed_tooltip") or brief
        novice = widget.property("tooltip_novice") or widget.property("novice_tooltip") or detailed
        entry = (widget, str(brief), str(detailed), str(novice))
        _ONSET_EDITOR_TOOLTIP_REGISTRY.append(entry)
        widget.setToolTip(
            _tooltip_text_for_level(
                _ONSET_EDITOR_DESCRIPTION_LEVEL,
                entry[1],
                entry[2],
                entry[3],
            )
        )


def apply_onset_editor_desc_level(level: int) -> None:
    global _ONSET_EDITOR_DESCRIPTION_LEVEL

    _ONSET_EDITOR_DESCRIPTION_LEVEL = max(0, min(int(level), 3))
    active_entries: list[tuple[QWidget, str, str, str]] = []
    for widget, brief, detailed, novice in _ONSET_EDITOR_TOOLTIP_REGISTRY:
        try:
            widget.setToolTip(
                _tooltip_text_for_level(
                    _ONSET_EDITOR_DESCRIPTION_LEVEL,
                    brief,
                    detailed,
                    novice,
                )
            )
        except RuntimeError:
            continue
        active_entries.append((widget, brief, detailed, novice))
    _ONSET_EDITOR_TOOLTIP_REGISTRY[:] = active_entries

'''
        btns.rejected.connect(self.reject)
        btns.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 5px 14px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
        )
        layout.addWidget(btns)

    def _toggle_recommended(self):
        vis = not self._recommended_frame.isVisible()
        self._recommended_frame.setVisible(vis)
        self._recommended_toggle.setText(
            "\u25bc Recommended From Focus Signals" if vis else "\u25b6 Recommended From Focus Signals"
        )
        self.adjustSize()

    def _run_analysis(self):
        """Run the focus-signal analysis and populate recommendations."""
        if not self._analyze_callback:
            return
        self._analyze_btn.setEnabled(False)
        self._analyze_btn.setText("Analyzing\u2026")
        QApplication.processEvents()
        try:
            profile, result = self._analyze_callback()
            self._signal_profile = profile
            self._recommendation_result = result or {}

            # Clustering when checkbox is checked
            self._cluster_result = None
            if self._auto_layers_cb.isChecked() and profile:
                pos_regions = profile.get("regions") or []
                if len(pos_regions) >= 2:
                    try:
                        from analysis.signal_profiles import cluster_signal_regions
                    except ImportError:
                        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        if project_root not in sys.path:
                            sys.path.insert(0, project_root)
                        from analysis.signal_profiles import cluster_signal_regions
                    try:
                        self._cluster_result = cluster_signal_regions(pos_regions)
                    except Exception:
                        pass

            text = _format_detect_recommendations(profile, result)
            if self._cluster_result and self._cluster_result["n_clusters"] > 1:
                text += "\n\n"
                text += "Onset Layer Detection\n"
                text += "=" * 22 + "\n"
                cr = self._cluster_result
                text += f"Suggested layers: {cr['n_clusters']}\n"
                for desc in cr["descriptions"]:
                    text += f"  {desc}\n"
                text += "\nClose this dialog to auto-create these layers."
            elif self._auto_layers_cb.isChecked():
                text += "\n\n"
                text += "Onset Layer Detection\n"
                text += "=" * 22 + "\n"
                n_pos = len((profile or {}).get("regions") or [])
                if n_pos < 2:
                    text += "Need at least 2 positive regions to cluster.\n"
                else:
                    text += "All positive regions are spectrally similar \u2014 1 layer is sufficient.\n"

            self._recommended_text.setPlainText(text)
            self._apply_pipeline_btn.setEnabled(bool(result))
            self._recommended_frame.setVisible(True)
            self._recommended_toggle.setText("\u25bc Recommended From Focus Signals")
        finally:
            self._analyze_btn.setText("Analyze Selected +/\u2212 Signals")
            self._analyze_btn.setEnabled(True)

    def _apply_to_onset_finder(self):
        """Apply recommended settings to the main Onset Finder pipeline panel."""
        if not callable(self._apply_callback):
            QMessageBox.information(
                self,
                "Unavailable",
                "This window is not connected to the main Onset Finder panel.",
            )
            return
        settings = self._recommendation_result.get("settings", {})
        if not settings:
            QMessageBox.information(
                self,
                "No Recommendations",
                "Run the analysis first to generate recommended settings.",
            )
            return
        self._apply_callback(settings)

    def layer_cluster_result(self) -> dict | None:
        """Return the clustering result if auto-layer detection was performed."""
        return self._cluster_result

    def recommendation_result(self) -> dict:
        """Return the current recommendation result dict."""
        return self._recommendation_result

    def signal_profile(self) -> dict | None:
        """Return the current signal profile."""
        return self._signal_profile

'''


_DetectOnsetsWorker = _ExtractedDetectOnsetsWorker
_AnalyzeSignalsDialog = _ExtractedAnalyzeSignalsDialog

_DetectOnsetsWorker = _ExtractedDetectOnsetsWorker
_AnalyzeSignalsDialog = _ExtractedAnalyzeSignalsDialog
_DetectOnsetsDialog = _ExtractedDetectOnsetsDialog
_MfccAudioEditDialog = _ExtractedMfccAudioEditDialog
_NegativeSubtractionDialog = _ExtractedNegativeSubtractionDialog


class _EditAudioDialog(QDialog):
    """Dialog for applying Audio Editor processing to a chosen time range."""

    _GROUP_NAMES = [
        "② Frequency Filters",
        "③ Bandpass Boost",
        "④ Source Separation && Denoising",
        "⑤ Enhancement && Dynamics",
        "⑥ Muting && Finalisation",
    ]

    def __init__(
        self,
        start: float,
        end: float,
        duration: float = 0.0,
        *,
        selection_available: bool = True,
        locked_range: tuple[float, float] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._selection_start = float(start)
        self._selection_end = float(end)
        self._duration = max(float(duration), 0.0)
        self._selection_available = bool(selection_available)
        self._locked_range = tuple(locked_range) if locked_range is not None else None

        self.setWindowTitle("Quick Audio Editor")
        self.setMinimumWidth(440)

        input_style = (
            f"background: {_BG_INPUT}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 4px;"
        )
        self.setStyleSheet(
            f"QDialog {{ background: {_BG}; color: {_TEXT}; }}"
            f"QLabel {{ background: transparent; color: {_TEXT}; }}"
            f"QSpinBox, QDoubleSpinBox, QComboBox {{ {input_style} }}"
            f"QCheckBox {{ background: transparent; color: {_TEXT}; }}"
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSpacing(8)

        range_row = QHBoxLayout()
        range_row.setSpacing(6)
        range_row.addWidget(QLabel("Start (s):"))
        self._start_spin = QDoubleSpinBox()
        self._start_spin.setRange(0.0, self._duration)
        self._start_spin.setDecimals(3)
        self._start_spin.setSingleStep(0.05)
        self._start_spin.setValue(self._selection_start)
        range_row.addWidget(self._start_spin)
        range_row.addWidget(QLabel("End (s):"))
        self._end_spin = QDoubleSpinBox()
        self._end_spin.setRange(0.0, self._duration)
        self._end_spin.setDecimals(3)
        self._end_spin.setSingleStep(0.05)
        self._end_spin.setValue(self._selection_end)
        range_row.addWidget(self._end_spin)
        layout.addLayout(range_row)

        scope_btn_row = QHBoxLayout()
        scope_btn_row.setSpacing(6)
        self._use_selection_btn = QPushButton("Use Selection")
        self._use_selection_btn.setEnabled(self._selection_available)
        self._use_selection_btn.clicked.connect(self._apply_selection_range)
        scope_btn_row.addWidget(self._use_selection_btn)
        self._use_full_btn = QPushButton("Use Full Clip")
        self._use_full_btn.clicked.connect(self._apply_full_clip_range)
        scope_btn_row.addWidget(self._use_full_btn)
        scope_btn_row.addStretch()
        layout.addLayout(scope_btn_row)

        self._scope_note = QLabel("")
        self._scope_note.setWordWrap(True)
        self._scope_note.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        layout.addWidget(self._scope_note)

        if self._locked_range is not None:
            lock_start, lock_end = self._locked_range
            self._start_spin.setRange(lock_start, lock_end)
            self._end_spin.setRange(lock_start, lock_end)
            self._start_spin.setValue(lock_start)
            self._end_spin.setValue(lock_end)
            self._start_spin.setEnabled(False)
            self._end_spin.setEnabled(False)
            self._use_selection_btn.setEnabled(False)
            self._use_full_btn.setEnabled(False)

        self._start_spin.valueChanged.connect(self._on_range_changed)
        self._end_spin.valueChanged.connect(self._on_range_changed)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        preset_row.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        self._preset_combo.addItem("None")
        for name in sorted(_load_muter_presets().keys()):
            self._preset_combo.addItem(name)
        preset_row.addWidget(self._preset_combo, 1)
        layout.addLayout(preset_row)

        self._preset_desc = QLabel("")
        self._preset_desc.setWordWrap(True)
        self._preset_desc.setStyleSheet(f"color: {_ACCENT}; font-size: 11px; font-style: italic;")
        self._preset_desc.hide()
        layout.addWidget(self._preset_desc)

        self._section_toggles: list[QPushButton] = []
        self._section_frames: list[QFrame] = []
        self._build_settings(layout)
        self._preset_combo.currentTextChanged.connect(self._on_preset_changed)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root_layout.addWidget(btns)
        self._on_range_changed()

    def _build_settings(self, layout: QVBoxLayout):
        def _make_section(title: str):
            toggle = QPushButton(f"▶ {title}")
            toggle.setFlat(True)
            frame = QFrame()
            frame.setVisible(False)
            frame_layout = QVBoxLayout(frame)
            index = len(self._section_toggles)
            self._section_toggles.append(toggle)
            self._section_frames.append(frame)
            toggle.clicked.connect(lambda _=None, i=index: self._toggle_section(i))
            layout.addWidget(toggle)
            layout.addWidget(frame)
            return frame_layout

        fl = _make_section("② Frequency Filters")
        self._hp_cb = QCheckBox("High-pass filter")
        self._hp_spin = QSpinBox(); self._hp_spin.setRange(0, 5000)
        self._lp_cb = QCheckBox("Low-pass filter")
        self._lp_spin = QSpinBox(); self._lp_spin.setRange(0, 22050)
        self._pe_cb = QCheckBox("Pre-emphasis")
        self._pe_spin = QDoubleSpinBox(); self._pe_spin.setRange(0.0, 1.0); self._pe_spin.setDecimals(2)
        for checkbox, widget, label in [
            (self._hp_cb, self._hp_spin, "Cutoff (Hz):"),
            (self._lp_cb, self._lp_spin, "Cutoff (Hz):"),
            (self._pe_cb, self._pe_spin, "Coefficient:"),
        ]:
            fl.addWidget(checkbox)
            row = QHBoxLayout(); row.addWidget(QLabel(label)); row.addWidget(widget)
            fl.addLayout(row)
            checkbox.toggled.connect(widget.setEnabled)
            widget.setEnabled(False)

        fl = _make_section("③ Bandpass Boost")
        self._bb_cb = QCheckBox("Enable bandpass boost")
        self._bb_low = QSpinBox(); self._bb_low.setRange(20, 22050); self._bb_low.setValue(300)
        self._bb_high = QSpinBox(); self._bb_high.setRange(20, 22050); self._bb_high.setValue(3000)
        self._bb_gain = QDoubleSpinBox(); self._bb_gain.setRange(0.0, 18.0); self._bb_gain.setValue(6.0)
        fl.addWidget(self._bb_cb)
        for widget, label in [(self._bb_low, "Low (Hz):"), (self._bb_high, "High (Hz):"), (self._bb_gain, "Gain (dB):")]:
            row = QHBoxLayout(); row.addWidget(QLabel(label)); row.addWidget(widget); fl.addLayout(row)
            self._bb_cb.toggled.connect(widget.setEnabled)
            widget.setEnabled(False)

        fl = _make_section("④ Source Separation && Denoising")
        self._hpss_cb = QCheckBox("Enable HPSS")
        self._hpss_target_combo = QComboBox(); self._hpss_target_combo.addItems(["percussive", "harmonic"])
        self._hpss_margin_spin = QDoubleSpinBox(); self._hpss_margin_spin.setRange(0.5, 10.0); self._hpss_margin_spin.setValue(2.0)
        self._hpss_emphasis_spin = QDoubleSpinBox(); self._hpss_emphasis_spin.setRange(0.0, 18.0)
        self._spectral_denoise_cb = QCheckBox("Enable spectral denoising")
        self._denoise_strength_spin = QDoubleSpinBox(); self._denoise_strength_spin.setRange(0.5, 4.0); self._denoise_strength_spin.setValue(1.5)
        fl.addWidget(self._hpss_cb)
        for widget, label in [(self._hpss_target_combo, "Target:"), (self._hpss_margin_spin, "Margin:"), (self._hpss_emphasis_spin, "Emphasis (dB):")]:
            row = QHBoxLayout(); row.addWidget(QLabel(label)); row.addWidget(widget); fl.addLayout(row)
        fl.addWidget(self._spectral_denoise_cb)
        row = QHBoxLayout(); row.addWidget(QLabel("Strength:")); row.addWidget(self._denoise_strength_spin); fl.addLayout(row)
        self._spectral_denoise_cb.toggled.connect(self._denoise_strength_spin.setEnabled)
        self._denoise_strength_spin.setEnabled(False)

        fl = _make_section("⑤ Enhancement && Dynamics")
        self._spectral_enhance_cb = QCheckBox("Enable spectral enhancement")
        self._enhance_factor_spin = QDoubleSpinBox(); self._enhance_factor_spin.setRange(1.0, 6.0); self._enhance_factor_spin.setValue(2.0)
        self._compress_cb = QCheckBox("Enable compression")
        self._compress_ratio_spin = QDoubleSpinBox(); self._compress_ratio_spin.setRange(1.0, 10.0); self._compress_ratio_spin.setValue(3.0)
        self._compress_threshold_spin = QDoubleSpinBox(); self._compress_threshold_spin.setRange(-60.0, 0.0); self._compress_threshold_spin.setValue(-30.0)
        self._sharpen_cb = QCheckBox("Sharpen transients")
        self._sharpen_gain_spin = QDoubleSpinBox(); self._sharpen_gain_spin.setRange(0.0, 18.0); self._sharpen_gain_spin.setValue(6.0)
        self._sharpen_attack_spin = QDoubleSpinBox(); self._sharpen_attack_spin.setRange(1.0, 50.0); self._sharpen_attack_spin.setValue(15.0)
        for checkbox, controls in [
            (self._spectral_enhance_cb, [(self._enhance_factor_spin, "Factor:")]),
            (self._compress_cb, [(self._compress_ratio_spin, "Ratio:"), (self._compress_threshold_spin, "Threshold (dB):")]),
            (self._sharpen_cb, [(self._sharpen_gain_spin, "Gain (dB):"), (self._sharpen_attack_spin, "Attack (ms):")]),
        ]:
            fl.addWidget(checkbox)
            for widget, label in controls:
                row = QHBoxLayout(); row.addWidget(QLabel(label)); row.addWidget(widget); fl.addLayout(row)
                checkbox.toggled.connect(widget.setEnabled)
                widget.setEnabled(False)

        fl = _make_section("⑥ Muting && Finalisation")
        self._auto_threshold_cb = QCheckBox("Use adaptive threshold")
        self._auto_threshold_cb.setChecked(True)
        self._db_threshold_spin = QSpinBox(); self._db_threshold_spin.setRange(0, 80); self._db_threshold_spin.setValue(30)
        self._noise_margin_spin = QDoubleSpinBox(); self._noise_margin_spin.setRange(0.0, 30.0); self._noise_margin_spin.setValue(6.0)
        self._fade_ms_spin = QDoubleSpinBox(); self._fade_ms_spin.setRange(0.0, 100.0); self._fade_ms_spin.setValue(5.0)
        self._normalize_combo = QComboBox(); self._normalize_combo.addItems(["None", "peak", "rms"])
        self._normalize_target_spin = QDoubleSpinBox(); self._normalize_target_spin.setRange(-60.0, 0.0); self._normalize_target_spin.setValue(-1.0)
        self._trim_silence_cb = QCheckBox("Trim leading/trailing silence")
        self._trim_threshold_spin = QDoubleSpinBox(); self._trim_threshold_spin.setRange(0.0, 80.0); self._trim_threshold_spin.setValue(40.0)
        fl.addWidget(self._auto_threshold_cb)
        for widget, label in [
            (self._db_threshold_spin, "dB threshold:"),
            (self._noise_margin_spin, "Noise margin (dB):"),
            (self._fade_ms_spin, "Crossfade (ms):"),
            (self._normalize_combo, "Normalize:"),
            (self._normalize_target_spin, "Target (dB):"),
        ]:
            row = QHBoxLayout(); row.addWidget(QLabel(label)); row.addWidget(widget); fl.addLayout(row)
        fl.addWidget(self._trim_silence_cb)
        row = QHBoxLayout(); row.addWidget(QLabel("Trim threshold (dB):")); row.addWidget(self._trim_threshold_spin); fl.addLayout(row)
        self._trim_silence_cb.toggled.connect(self._trim_threshold_spin.setEnabled)
        self._trim_threshold_spin.setEnabled(False)

    @staticmethod
    def _default_config() -> dict:
        return {
            "MUTER_CHANNEL": "mix",
            "MUTER_RESAMPLE_HZ": 0,
            "MUTER_RESAMPLE_SR": 0,
            "MUTER_HIGHPASS_HZ": 0,
            "MUTER_LOWPASS_HZ": 0,
            "MUTER_NOTCH_FREQS": [],
            "MUTER_NOTCH_Q": 30.0,
            "MUTER_PRE_EMPHASIS": 0.0,
            "MUTER_BANDPASS_BOOST": False,
            "MUTER_BOOST_LOW_HZ": 300,
            "MUTER_BOOST_HIGH_HZ": 3000,
            "MUTER_BOOST_GAIN_DB": 6.0,
            "MUTER_HPSS_ENABLED": False,
            "MUTER_HPSS_TARGET": "percussive",
            "MUTER_HPSS_MARGIN": 2.0,
            "MUTER_HPSS_EMPHASIS_DB": 0.0,
            "MUTER_SPECTRAL_DENOISE": False,
            "MUTER_DENOISE_STRENGTH": 1.5,
            "MUTER_SPECTRAL_ENHANCE": False,
            "MUTER_ENHANCE_FACTOR": 2.0,
            "MUTER_COMPRESS": False,
            "MUTER_COMPRESS_RATIO": 3.0,
            "MUTER_COMPRESS_THRESHOLD_DB": -30.0,
            "MUTER_SHARPEN_TRANSIENTS": False,
            "MUTER_SHARPEN_GAIN_DB": 6.0,
            "MUTER_SHARPEN_ATTACK_MS": 15.0,
            "MUTER_AUTO_THRESHOLD": True,
            "MUTER_DB_THRESHOLD": 30,
            "MUTER_NOISE_MARGIN_DB": 6.0,
            "MUTER_FADE_MS": 5.0,
            "MUTER_NORMALIZE": None,
            "MUTER_NORMALIZE_TARGET_DB": -1.0,
            "MUTER_TRIM_SILENCE": False,
            "MUTER_TRIM_THRESHOLD_DB": 40.0,
            "MUTER_MFCC_ENABLED": False,
            "MUTER_MFCC_TEMPLATE_PATHS": [],
            "MUTER_MFCC_THRESHOLD_PERCENTILE": 15.0,
            "MUTER_MFCC_SMOOTH_MS": 50.0,
            "MUTER_MFCC_N_MFCC": 13,
            "MUTER_PROC_ORDER": list(range(12)),
        }

    def _apply_config(self, cfg: dict):
        hp = int(cfg.get("MUTER_HIGHPASS_HZ", 0))
        lp = int(cfg.get("MUTER_LOWPASS_HZ", 0))
        self._hp_cb.setChecked(hp > 0)
        self._hp_spin.setValue(hp)
        self._lp_cb.setChecked(lp > 0)
        self._lp_spin.setValue(lp)
        pre_emphasis = float(cfg.get("MUTER_PRE_EMPHASIS", 0.0))
        self._pe_cb.setChecked(pre_emphasis > 0.0)
        self._pe_spin.setValue(pre_emphasis)
        self._bb_cb.setChecked(bool(cfg.get("MUTER_BANDPASS_BOOST", False)))
        self._bb_low.setValue(int(cfg.get("MUTER_BOOST_LOW_HZ", 300)))
        self._bb_high.setValue(int(cfg.get("MUTER_BOOST_HIGH_HZ", 3000)))
        self._bb_gain.setValue(float(cfg.get("MUTER_BOOST_GAIN_DB", 6.0)))
        self._hpss_cb.setChecked(bool(cfg.get("MUTER_HPSS_ENABLED", False)))
        self._hpss_target_combo.setCurrentText(str(cfg.get("MUTER_HPSS_TARGET", "percussive")))
        self._hpss_margin_spin.setValue(float(cfg.get("MUTER_HPSS_MARGIN", 2.0)))
        self._hpss_emphasis_spin.setValue(float(cfg.get("MUTER_HPSS_EMPHASIS_DB", 0.0)))
        self._spectral_denoise_cb.setChecked(bool(cfg.get("MUTER_SPECTRAL_DENOISE", False)))
        self._denoise_strength_spin.setValue(float(cfg.get("MUTER_DENOISE_STRENGTH", 1.5)))
        self._spectral_enhance_cb.setChecked(bool(cfg.get("MUTER_SPECTRAL_ENHANCE", False)))
        self._enhance_factor_spin.setValue(float(cfg.get("MUTER_ENHANCE_FACTOR", 2.0)))
        self._compress_cb.setChecked(bool(cfg.get("MUTER_COMPRESS", False)))
        self._compress_ratio_spin.setValue(float(cfg.get("MUTER_COMPRESS_RATIO", 3.0)))
        self._compress_threshold_spin.setValue(float(cfg.get("MUTER_COMPRESS_THRESHOLD_DB", -30.0)))
        self._sharpen_cb.setChecked(bool(cfg.get("MUTER_SHARPEN_TRANSIENTS", False)))
        self._sharpen_gain_spin.setValue(float(cfg.get("MUTER_SHARPEN_GAIN_DB", 6.0)))
        self._sharpen_attack_spin.setValue(float(cfg.get("MUTER_SHARPEN_ATTACK_MS", 15.0)))
        self._auto_threshold_cb.setChecked(bool(cfg.get("MUTER_AUTO_THRESHOLD", True)))
        self._db_threshold_spin.setValue(int(cfg.get("MUTER_DB_THRESHOLD", 30)))
        self._noise_margin_spin.setValue(float(cfg.get("MUTER_NOISE_MARGIN_DB", 6.0)))
        self._fade_ms_spin.setValue(float(cfg.get("MUTER_FADE_MS", 5.0)))
        normalize_mode = cfg.get("MUTER_NORMALIZE")
        self._normalize_combo.setCurrentText("None" if normalize_mode in (None, "") else str(normalize_mode))
        self._normalize_target_spin.setValue(float(cfg.get("MUTER_NORMALIZE_TARGET_DB", -1.0)))
        self._trim_silence_cb.setChecked(bool(cfg.get("MUTER_TRIM_SILENCE", False)))
        self._trim_threshold_spin.setValue(float(cfg.get("MUTER_TRIM_THRESHOLD_DB", 40.0)))

    def _on_preset_changed(self, preset_name: str):
        cfg = self._default_config()
        presets = _load_muter_presets()
        if preset_name != "None" and preset_name in presets:
            cfg.update({key: value for key, value in presets[preset_name].items() if key != "description"})
            description = presets[preset_name].get("description", "")
            self._preset_desc.setText(description)
            self._preset_desc.setVisible(bool(description))
        else:
            self._preset_desc.hide()
        self._apply_config(cfg)

    def _toggle_section(self, index: int):
        frame = self._section_frames[index]
        visible = not frame.isVisible()
        frame.setVisible(visible)
        title = self._section_toggles[index].text()[2:]
        self._section_toggles[index].setText(("▼ " if visible else "▶ ") + title)

    def _apply_selection_range(self):
        if self._locked_range is not None:
            return
        self._start_spin.setValue(self._selection_start)
        self._end_spin.setValue(self._selection_end)

    def _apply_full_clip_range(self):
        if self._locked_range is not None:
            return
        self._start_spin.setValue(0.0)
        self._end_spin.setValue(self._duration)

    def _on_range_changed(self):
        start, end = self.selected_range()
        length = max(end - start, 0.0)
        if self.using_full_clip():
            self._scope_note.setText(f"Full clip selected: 0.000s – {self._duration:.3f}s ({self._duration:.3f}s).")
        else:
            self._scope_note.setText(f"Current range: {start:.3f}s – {end:.3f}s ({length:.3f}s).")

    def selected_range(self) -> tuple[float, float]:
        if self._locked_range is not None:
            return self._locked_range
        start = min(self._start_spin.value(), self._end_spin.value())
        end = max(self._start_spin.value(), self._end_spin.value())
        return float(start), float(end)

    def using_full_clip(self) -> bool:
        start, end = self.selected_range()
        return abs(start) < 1e-9 and abs(end - self._duration) < 1e-9

    def get_config(self) -> dict:
        cfg = self._default_config()
        cfg.update({
            "MUTER_HIGHPASS_HZ": int(self._hp_spin.value()) if self._hp_cb.isChecked() else 0,
            "MUTER_LOWPASS_HZ": int(self._lp_spin.value()) if self._lp_cb.isChecked() else 0,
            "MUTER_PRE_EMPHASIS": float(self._pe_spin.value()) if self._pe_cb.isChecked() else 0.0,
            "MUTER_BANDPASS_BOOST": bool(self._bb_cb.isChecked()),
            "MUTER_BOOST_LOW_HZ": int(self._bb_low.value()),
            "MUTER_BOOST_HIGH_HZ": int(self._bb_high.value()),
            "MUTER_BOOST_GAIN_DB": float(self._bb_gain.value()),
            "MUTER_HPSS_ENABLED": bool(self._hpss_cb.isChecked()),
            "MUTER_HPSS_TARGET": self._hpss_target_combo.currentText(),
            "MUTER_HPSS_MARGIN": float(self._hpss_margin_spin.value()),
            "MUTER_HPSS_EMPHASIS_DB": float(self._hpss_emphasis_spin.value()),
            "MUTER_SPECTRAL_DENOISE": bool(self._spectral_denoise_cb.isChecked()),
            "MUTER_DENOISE_STRENGTH": float(self._denoise_strength_spin.value()),
            "MUTER_SPECTRAL_ENHANCE": bool(self._spectral_enhance_cb.isChecked()),
            "MUTER_ENHANCE_FACTOR": float(self._enhance_factor_spin.value()),
            "MUTER_COMPRESS": bool(self._compress_cb.isChecked()),
            "MUTER_COMPRESS_RATIO": float(self._compress_ratio_spin.value()),
            "MUTER_COMPRESS_THRESHOLD_DB": float(self._compress_threshold_spin.value()),
            "MUTER_SHARPEN_TRANSIENTS": bool(self._sharpen_cb.isChecked()),
            "MUTER_SHARPEN_GAIN_DB": float(self._sharpen_gain_spin.value()),
            "MUTER_SHARPEN_ATTACK_MS": float(self._sharpen_attack_spin.value()),
            "MUTER_AUTO_THRESHOLD": bool(self._auto_threshold_cb.isChecked()),
            "MUTER_DB_THRESHOLD": int(self._db_threshold_spin.value()),
            "MUTER_NOISE_MARGIN_DB": float(self._noise_margin_spin.value()),
            "MUTER_FADE_MS": float(self._fade_ms_spin.value()),
            "MUTER_NORMALIZE": None if self._normalize_combo.currentText() == "None" else self._normalize_combo.currentText(),
            "MUTER_NORMALIZE_TARGET_DB": float(self._normalize_target_spin.value()),
            "MUTER_TRIM_SILENCE": bool(self._trim_silence_cb.isChecked()),
            "MUTER_TRIM_THRESHOLD_DB": float(self._trim_threshold_spin.value()),
        })
        return cfg

# ═══════════════════════════════════════════════════════════════════════════
# Onset data model
# ═══════════════════════════════════════════════════════════════════════════

def _compute_ioi(times: list[float]) -> list[Optional[float]]:
    """Compute inter-onset intervals (ms). First IOI is None."""
    return _compute_ioi_impl(times)


def _compute_rk(times: list[float]) -> list[Optional[float]]:
    """Compute rhythm ratio r_k for each consecutive pair of intervals.
    r_k[i] is defined for onset i where intervals i-1 and i exist,
    i.e. for i >= 2.  r_k = interval_1 / (interval_1 + interval_2).
    Returns list of same length as times, with None where undefined.
    """
    return _compute_rk_impl(times)


def _compute_stable(times: list[float],
                    tolerance: float = _DEFAULT_STABLE_TOLERANCE
                    ) -> list[Optional[bool]]:
    """Compute stable-rhythm flag per dyad (onset index >= 2).

    A dyad at position k (intervals k-1, k) is stable if:
    - interval k-1 ≈ interval k+1  (same-position, 2 beats later)
    - interval k ≈ interval k+2    (next-position, 2 beats later)
    where ≈ means |a-b|/max(a,b) <= tolerance.
    """
    return _compute_stable_impl(times, tolerance)


def _extract_recommended_detect_settings(result: dict | None) -> dict:
    return _extract_recommended_detect_settings_impl(result)


def _compute_per_signal_spectral_threshold(cfg: dict) -> float:
    return _compute_per_signal_spectral_threshold_impl(cfg)


def _compute_per_signal_variable_score_threshold(cfg: dict) -> float:
    return _compute_per_signal_variable_score_threshold_impl(cfg)


def _score_onsets_by_variable_match(*args, **kwargs):
    return _score_onsets_by_variable_match_impl(*args, **kwargs)


def _build_uniform_probe_times(*args, **kwargs):
    return _build_uniform_probe_times_impl(*args, **kwargs)


def _region_contains_onset(*args, **kwargs):
    return _region_contains_onset_impl(*args, **kwargs)


def _candidate_peak_times_for_region(*args, **kwargs):
    return _candidate_peak_times_for_region_impl(*args, **kwargs)


def _compute_spectral_similarity_at_time(
    candidate_time: float,
    y: np.ndarray,
    sr: int,
    profile: dict | None,
    window_sec: float = 0.1,
) -> float | None:
    return _compute_spectral_similarity_at_time_impl(
        candidate_time,
        y,
        sr,
        profile,
        window_sec,
    )


def _diagnose_candidate_matches(
    candidate_times: list[float],
    y: np.ndarray,
    sr: int,
    signal_profile: dict,
    cfg: dict,
    effective_settings: dict,
) -> dict:
    return _diagnose_candidate_matches_impl(
        candidate_times,
        y,
        sr,
        signal_profile,
        cfg,
        effective_settings,
        compute_per_signal_variable_score_threshold=_compute_per_signal_variable_score_threshold,
        score_onsets_by_variable_match=_score_onsets_by_variable_match,
        compute_spectral_similarity_at_time=_compute_spectral_similarity_at_time,
    )


def _evaluate_exemplar_self_check(
    y: np.ndarray,
    sr: int,
    signal_profile: dict,
    cfg: dict,
    effective_settings: dict,
) -> dict:
    return _evaluate_exemplar_self_check_impl(
        y,
        sr,
        signal_profile,
        cfg,
        effective_settings,
        build_uniform_probe_times=_build_uniform_probe_times,
        diagnose_candidate_matches=_diagnose_candidate_matches,
    )


def _recover_focus_region_onset(
    y: np.ndarray,
    sr: int,
    region: dict,
    signal_profile: dict,
    cfg: dict,
    effective_settings: dict,
) -> dict:
    return _recover_focus_region_onset_impl(
        y,
        sr,
        region,
        signal_profile,
        cfg,
        effective_settings,
        build_uniform_probe_times=_build_uniform_probe_times,
        candidate_peak_times_for_region=_candidate_peak_times_for_region,
        diagnose_candidate_matches=_diagnose_candidate_matches,
    )


def _format_match_miss_reason(result: dict | None) -> str:
    return _format_match_miss_reason_impl(result)


def _merge_negative_detection_hits(*args, **kwargs):
    return _merge_negative_detection_hits_impl(*args, **kwargs)


def _build_region_detector_kwargs(settings: dict):
    return _build_region_detector_kwargs_impl(settings)


# ═══════════════════════════════════════════════════════════════════════════
# OnsetManagerDialog — Manage onset files, comparison, colors and Excel
# ═══════════════════════════════════════════════════════════════════════════

OnsetManagerDialog = _ExtractedOnsetManagerDialog


# ═══════════════════════════════════════════════════════════════════════════
# _LayerCheckboxMenu — multi-select checkbox popup for onset layers
# ═══════════════════════════════════════════════════════════════════════════

_LayerCheckboxMenu = _ExtractedLayerCheckboxMenu


# ═══════════════════════════════════════════════════════════════════════════
# _PerSignalConfigDialog — per-signal deviation config wizard
# ═══════════════════════════════════════════════════════════════════════════

"""Legacy full-size per-signal dialog retained below as inert reference text."""

'''

        main_layout.addWidget(self._splitter, stretch=1)

        # ── Navigation buttons ───────────────────────────────────────
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 6, 0, 0)

        self._prev_btn = QPushButton("◀ Previous")
        self._prev_btn.setStyleSheet(
            "QPushButton { background: #2a2a3e; color: #90caf9; "
            "border: 1px solid #3a3a5a; border-radius: 4px; "
            "padding: 8px 18px; font-size: 13px; }"
            "QPushButton:hover { border-color: #5c7cfa; }"
            "QPushButton:disabled { color: #555; }")
        self._prev_btn.clicked.connect(self._go_prev)

        self._next_btn = QPushButton("Next ▶")
        self._next_btn.setStyleSheet(
            "QPushButton { background: #1b5e20; color: white; "
            "border: 1px solid #2e7d32; border-radius: 4px; "
            "padding: 8px 18px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #2e7d32; }")
        self._next_btn.clicked.connect(self._go_next)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            "QPushButton { background: #3a1a1a; color: #ef9a9a; "
            "border: 1px solid #5a2020; border-radius: 4px; "
            "padding: 8px 18px; font-size: 13px; }"
            "QPushButton:hover { border-color: #cc4444; }")
        cancel_btn.clicked.connect(self.reject)

        self._page_label = QLabel()
        self._page_label.setStyleSheet("color: #888; font-size: 12px;")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        nav_layout.addWidget(self._prev_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self._page_label)
        nav_layout.addStretch()
        nav_layout.addWidget(cancel_btn)
        nav_layout.addWidget(self._next_btn)
        main_layout.addWidget(nav_widget)

        self._show_page(0)

    # ── descriptions ─────────────────────────────────────────────────

    def _on_desc_level_changed(self, idx: int):
        """Update description level and refresh variable labels."""
        self._desc_level = idx
        self._apply_descriptions()

    def _apply_descriptions(self):
        """Apply current description level to all variable rows."""
        level = self._desc_level
        for row in self._var_rows:
            key = row["key"]
            label_text = row["label_text"]
            cb = row["checkbox"]
            desc_lbl = row["desc_label"]

            # Update checkbox label with friendly name
            names = _SIGNAL_VAR_FRIENDLY_NAMES.get(label_text)
            if level == 0 or names is None:
                cb.setText(label_text)
            else:
                idx = min(level - 1, 2)
                friendly = names[idx]
                cb.setText(f"{friendly} / ({label_text})")

            # Update description text
            descs = _SIGNAL_VAR_DESCRIPTIONS.get(key)
            if level == 0 or descs is None:
                desc_lbl.hide()
            else:
                idx = min(level - 1, 2)
                desc_lbl.setText(descs[idx])
                desc_lbl.show()

    # ── signal preview ───────────────────────────────────────────────

    def _update_preview(self, region: dict, analysis: dict):
        """Render waveform + spectrogram for the current signal region."""
        if self._wave_plot is None or self._y is None:
            return

        t_start = region.get("t_start", 0)
        t_end = region.get("t_end", 0)
        f_low = region.get("f_low", 0)
        f_high = region.get("f_high", self._sr // 2)

        s0 = max(int(t_start * self._sr), 0)
        s1 = min(int(t_end * self._sr), len(self._y))
        if s1 <= s0:
            return
        y_seg = self._y[s0:s1]
        t_axis = np.linspace(t_start, t_end, len(y_seg))

        # Waveform (downsample for performance)
        if len(y_seg) > 5000:
            step = len(y_seg) // 2500
            t_ds = t_axis[::step]
            y_ds = y_seg[::step]
        else:
            t_ds, y_ds = t_axis, y_seg
        self._wave_curve.setData(t_ds, y_ds)
        self._wave_plot.setXRange(t_start, t_end, padding=0.02)
        self._wave_plot.setYRange(float(y_seg.min()), float(y_seg.max()), padding=0.05)

        # Spectrogram
        try:
            import librosa
            n_fft = min(1024, len(y_seg))
            hop = max(n_fft // 4, 1)
            S = np.abs(librosa.stft(y_seg, n_fft=n_fft, hop_length=hop))
            S_db = librosa.amplitude_to_db(S, ref=np.max)
            freqs = librosa.fft_frequencies(sr=self._sr, n_fft=n_fft)
            times = librosa.frames_to_time(
                np.arange(S_db.shape[1]), sr=self._sr, hop_length=hop) + t_start

            self._spec_image_preview.setImage(S_db.T, autoLevels=True)
            dt = times[1] - times[0] if len(times) > 1 else 1.0
            df = freqs[1] - freqs[0] if len(freqs) > 1 else 1.0
            from pyqtgraph import QtGui
            tr = QtGui.QTransform()
            tr.translate(float(times[0]), float(freqs[0]))
            tr.scale(dt, df)
            self._spec_image_preview.setTransform(tr)

            self._spec_plot_preview.setXRange(t_start, t_end, padding=0.02)
            self._spec_plot_preview.setYRange(
                max(float(f_low) - 50, 0),
                float(f_high) + 50, padding=0)
        except Exception:
            pass

        self._draw_annotations_with_ranges(region, analysis)

    def _clear_annotations(self):
        """Remove all variable annotation items from the spectrogram."""
        if self._spec_plot_preview is None:
            return
        for item in self._ann_items:
            try:
                self._spec_plot_preview.removeItem(item)
            except Exception:
                pass
        self._ann_items.clear()

    def _update_value_display(self, analysis: dict):
        """Update lower/value/upper labels and range info for each variable row.

        Sides that have a manual override in ``_manual_bounds`` are left
        unchanged — the user's typed value is preserved.
        """
        for row in self._var_rows:
            key = row["key"]
            unit = row.get("unit", "")
            value = analysis.get(key)
            lower_pct = row["lower_spin"].value()
            upper_pct = row["upper_spin"].value()
            enabled = row["checkbox"].isChecked()
            lo_manual = (key, "lower") in self._manual_bounds
            hi_manual = (key, "upper") in self._manual_bounds

            if value is None:
                row["value_edit"].setText("—")
                if not lo_manual:
                    row["lower_label"].setText("—")
                if not hi_manual:
                    row["upper_label"].setText("—")
                continue

            # Format value
            def _fmt(v):
                if isinstance(v, float):
                    return f"{v:.4f}" if v < 1 else f"{v:.1f}"
                return str(v)

            unit_suffix = f" {unit}" if unit else ""
            row["value_edit"].setText(f"{_fmt(value)}{unit_suffix}")

            ll = row["lower_label"]
            ul = row["upper_label"]
            ll.blockSignals(True)
            ul.blockSignals(True)
            ann_color = self._ANN_COLORS.get(key, "#888")
            if not enabled:
                if not lo_manual:
                    ll.setText("—")
                    ll.setStyleSheet(
                        "QLineEdit { color: #444; font-size: 13px; min-width: 70px;"
                        " background: #2a2a3e; border: 1px solid #3a3a5a;"
                        " border-radius: 3px; padding: 2px 4px; }")
                if not hi_manual:
                    ul.setText("—")
                    ul.setStyleSheet(
                        "QLineEdit { color: #444; font-size: 13px; min-width: 70px;"
                        " background: #2a2a3e; border: 1px solid #3a3a5a;"
                        " border-radius: 3px; padding: 2px 4px; }")
            else:
                _active_ss = (
                    f"QLineEdit {{ color: {ann_color}; font-size: 13px; min-width: 70px;"
                    f" background: #2a2a3e; border: 1px solid #3a3a5a;"
                    f" border-radius: 3px; padding: 2px 4px; }}"
                    f"QLineEdit:focus {{ border-color: #5c7cfa; }}")
                if not lo_manual:
                    lo = value * (1 - lower_pct / 100)
                    ll.setText(f"{_fmt(lo)}{unit_suffix}")
                    ll.setStyleSheet(_active_ss)
                if not hi_manual:
                    hi = value * (1 + upper_pct / 100)
                    ul.setText(f"{_fmt(hi)}{unit_suffix}")
                    ul.setStyleSheet(_active_ss)
            ll.blockSignals(False)
            ul.blockSignals(False)

    def _on_deviation_changed(self):
        """Called when any deviation spinbox/slider or checkbox changes."""
        if self._current_idx >= len(self._profiles):
            return
        # Identify which spinbox triggered the change and clear its
        # manual override so slider mode takes over.
        sender = self.sender()
        if sender is not None:
            for row in self._var_rows:
                key = row["key"]
                if sender is row["lower_spin"]:
                    self._manual_bounds.pop((key, "lower"), None)
                    row["lower_slider"].setStyleSheet(self._slider_ss)
                    row["lower_spin"].setStyleSheet(self._spin_ss)
                    break
                if sender is row["upper_spin"]:
                    self._manual_bounds.pop((key, "upper"), None)
                    row["upper_slider"].setStyleSheet(self._slider_ss)
                    row["upper_spin"].setStyleSheet(self._spin_ss)
                    break
        analysis = self._profiles[self._current_idx]["analysis"]
        self._update_value_display(analysis)
        if self._spec_plot_preview is not None:
            region = self._profiles[self._current_idx]["region"]
            self._draw_annotations_with_ranges(region, analysis)

    def _on_actual_value_edited(self):
        """Called when the user finishes editing an actual-value QLineEdit.

        Parses the text (stripping any unit suffix), updates the
        analysis dict, and refreshes the display + annotations.
        """
        if self._current_idx >= len(self._profiles):
            return
        analysis = self._profiles[self._current_idx]["analysis"]
        for row in self._var_rows:
            text = row["value_edit"].text().strip()
            unit = row.get("unit", "")
            # Strip unit suffix if present
            if unit and text.endswith(unit):
                text = text[: -len(unit)].strip()
            try:
                new_val = float(text)
            except (ValueError, TypeError):
                continue
            key = row["key"]
            analysis[key] = new_val
        self._update_value_display(analysis)
        if self._spec_plot_preview is not None:
            region = self._profiles[self._current_idx]["region"]
            self._update_preview(region, analysis)

    def _on_boundary_value_edited(self):
        """Called when the user finishes editing a lower/upper boundary QLineEdit.

        Stores the typed value as a manual override and greys out the
        corresponding slider+spinbox.  The slider remains functional:
        if the user later interacts with it, `_on_deviation_changed`
        clears the manual override and restores slider mode.
        """
        if self._current_idx >= len(self._profiles):
            return
        analysis = self._profiles[self._current_idx]["analysis"]
        for row in self._var_rows:
            key = row["key"]
            unit = row.get("unit", "")

            for side, lbl_key, slider_key, spin_key in [
                ("lower", "lower_label", "lower_slider", "lower_spin"),
                ("upper", "upper_label", "upper_slider", "upper_spin"),
            ]:
                text = row[lbl_key].text().strip()
                if unit and text.endswith(unit):
                    text = text[: -len(unit)].strip()
                try:
                    typed_val = float(text)
                except (ValueError, TypeError):
                    continue
                # Check if the typed value matches what the slider would
                # produce — if so, no need to enter manual mode.
                value = analysis.get(key)
                if value is not None and value != 0:
                    pct = row[spin_key].value()
                    if side == "lower":
                        slider_val = value * (1 - pct / 100.0)
                    else:
                        slider_val = value * (1 + pct / 100.0)
                    # Tolerance check (format-level precision)
                    if abs(typed_val - slider_val) < 0.05:
                        continue
                # Enter manual mode for this side
                self._manual_bounds[(key, side)] = typed_val
                row[slider_key].setStyleSheet(self._slider_ss_grey)
                row[spin_key].setStyleSheet(self._spin_ss_grey)

        # Refresh spectrogram with the manual boundary values
        if self._spec_plot_preview is not None:
            region = self._profiles[self._current_idx]["region"]
            self._draw_annotations_with_ranges(region, analysis)

    def _draw_annotations_with_ranges(self, region: dict, analysis: dict):
        """Draw annotations including upper/lower deviation shaded regions.

        Notes on per-variable visualisation:
        - Peak Frequency / Spectral Centroid: horizontal line + single
          asymmetric shaded band  [value*(1-lower%), value*(1+upper%)].
        - Spectral Bandwidth: solid band at centroid ± bandwidth, plus
          a lower-boundary line at centroid ± bw*(1-lower%) and an
          upper-boundary line at centroid ± bw*(1+upper%).  Each line
          is drawn independently so that dragging one slider only moves
          the corresponding pair of lines.
        - Duration: two independent marker lines — one for the shortest
          acceptable duration, one for the longest — each moves with
          only its own slider.
        - Attack Sharpness: solid attack region plus independent
          inner/outer boundary lines.
        - Harmonicity / Energy Ratio: these are scalar ratios (0–1)
          with no natural mapping to spectrogram axes, so they are
          shown only in the Detection Variables list below — no
          spectrogram overlay.
        """
        self._clear_annotations()
        if self._spec_plot_preview is None:
            return

        import pyqtgraph as pg
        from pyqtgraph import LinearRegionItem
        t_start = region.get("t_start", 0)
        t_end = region.get("t_end", 0)

        centroid = analysis.get("spectral_centroid_hz")
        bandwidth = analysis.get("spectral_bandwidth_hz")
        peak_freq = analysis.get("peak_frequency_hz")

        def _devs(key):
            """Return (lower_frac, upper_frac) or None if disabled."""
            for row in self._var_rows:
                if row["key"] == key:
                    if row["checkbox"].isChecked():
                        return (row["lower_spin"].value() / 100.0,
                                row["upper_spin"].value() / 100.0)
                    return None
            return None

        def _effective_bounds(key, ref_value):
            """Return (lo_bound, hi_bound) or None if disabled.

            Uses manual overrides from ``_manual_bounds`` when present,
            otherwise computes from slider percentage.
            """
            for row in self._var_rows:
                if row["key"] == key:
                    if not row["checkbox"].isChecked():
                        return None
                    lo_frac = row["lower_spin"].value() / 100.0
                    hi_frac = row["upper_spin"].value() / 100.0
                    lo = self._manual_bounds.get(
                        (key, "lower"), ref_value * (1 - lo_frac))
                    hi = self._manual_bounds.get(
                        (key, "upper"), ref_value * (1 + hi_frac))
                    return (lo, hi)
            return None

        # Peak frequency
        if peak_freq is not None:
            line = pg.InfiniteLine(
                pos=peak_freq, angle=0,
                pen=pg.mkPen(self._ANN_COLORS["peak_frequency_hz"], width=2,
                             style=Qt.PenStyle.SolidLine))
            self._spec_plot_preview.addItem(line)
            self._ann_items.append(line)
            bounds = _effective_bounds("peak_frequency_hz", peak_freq)
            if bounds is not None:
                lo_b, hi_b = bounds
                band = LinearRegionItem(
                    values=[lo_b, hi_b],
                    orientation="horizontal", movable=False,
                    brush=pg.mkBrush(102, 187, 106, 25),
                    pen=pg.mkPen("#66bb6a", width=1, style=Qt.PenStyle.DotLine))
                self._spec_plot_preview.addItem(band)
                self._ann_items.append(band)

        # Spectral centroid
        if centroid is not None:
            line = pg.InfiniteLine(
                pos=centroid, angle=0,
                pen=pg.mkPen(self._ANN_COLORS["spectral_centroid_hz"], width=2,
                             style=Qt.PenStyle.DashLine))
            self._spec_plot_preview.addItem(line)
            self._ann_items.append(line)
            bounds = _effective_bounds("spectral_centroid_hz", centroid)
            if bounds is not None:
                lo_b, hi_b = bounds
                band = LinearRegionItem(
                    values=[lo_b, hi_b],
                    orientation="horizontal", movable=False,
                    brush=pg.mkBrush(255, 107, 107, 20),
                    pen=pg.mkPen("#ff6b6b", width=1, style=Qt.PenStyle.DotLine))
                self._spec_plot_preview.addItem(band)
                self._ann_items.append(band)

        # Spectral bandwidth: solid band at actual value; independent
        # lower/upper boundary lines so each slider moves only its own.
        if centroid is not None and bandwidth is not None:
            bw_region = LinearRegionItem(
                values=[centroid - bandwidth, centroid + bandwidth],
                orientation="horizontal", movable=False,
                brush=pg.mkBrush(255, 167, 38, 30),
                pen=pg.mkPen(self._ANN_COLORS["spectral_bandwidth_hz"],
                             width=1, style=Qt.PenStyle.SolidLine))
            self._spec_plot_preview.addItem(bw_region)
            self._ann_items.append(bw_region)
            bounds = _effective_bounds("spectral_bandwidth_hz", bandwidth)
            if bounds is not None:
                bw_lo, bw_hi = bounds   # narrowest / widest acceptable
                # Upper boundary lines (dashed) — widest acceptable
                for pos in [centroid - bw_hi, centroid + bw_hi]:
                    ul = pg.InfiniteLine(
                        pos=pos, angle=0,
                        pen=pg.mkPen("#ffa726", width=1,
                                     style=Qt.PenStyle.DashLine))
                    self._spec_plot_preview.addItem(ul)
                    self._ann_items.append(ul)
                # Lower boundary lines (dash-dot) — narrowest acceptable
                if bw_lo > 0:
                    for pos in [centroid - bw_lo, centroid + bw_lo]:
                        ll = pg.InfiniteLine(
                            pos=pos, angle=0,
                            pen=pg.mkPen("#ffa726", width=1,
                                         style=Qt.PenStyle.DashDotLine))
                        self._spec_plot_preview.addItem(ll)
                        self._ann_items.append(ll)

        # Duration: independent lower/upper boundary lines
        for t_val in (t_start, t_end):
            line = pg.InfiniteLine(
                pos=t_val, angle=90,
                pen=pg.mkPen(self._ANN_COLORS["duration_s"], width=1,
                             style=Qt.PenStyle.DashDotLine))
            self._spec_plot_preview.addItem(line)
            self._ann_items.append(line)
        dur = analysis.get("duration_s")
        dur_bounds = _effective_bounds("duration_s", dur) if dur is not None else None
        if dur is not None and dur_bounds is not None:
            dur_lo, dur_hi = dur_bounds  # shortest / longest acceptable
            # Shortest acceptable duration → lower boundary line
            dur_lo_end = t_start + dur_lo
            lo_line = pg.InfiniteLine(
                pos=dur_lo_end, angle=90,
                pen=pg.mkPen("#90caf9", width=1,
                             style=Qt.PenStyle.DashDotLine))
            self._spec_plot_preview.addItem(lo_line)
            self._ann_items.append(lo_line)
            # Longest acceptable duration → upper boundary line
            dur_hi_end = t_start + dur_hi
            hi_line = pg.InfiniteLine(
                pos=dur_hi_end, angle=90,
                pen=pg.mkPen("#90caf9", width=1,
                             style=Qt.PenStyle.DashLine))
            self._spec_plot_preview.addItem(hi_line)
            self._ann_items.append(hi_line)
            # Shaded band between the two boundaries
            band = LinearRegionItem(
                values=[dur_lo_end, dur_hi_end],
                orientation="vertical", movable=False,
                brush=pg.mkBrush(144, 202, 249, 15),
                pen=pg.mkPen(None))
            self._spec_plot_preview.addItem(band)
            self._ann_items.append(band)

        # Attack sharpness: solid attack region + independent boundary lines
        attack = analysis.get("attack_sharpness")
        if attack is not None:
            attack_dur = (t_end - t_start) * 0.15
            attack_end = t_start + attack_dur
            atk_region = LinearRegionItem(
                values=[t_start, attack_end],
                orientation="vertical", movable=False,
                brush=pg.mkBrush(77, 208, 225, 35),
                pen=pg.mkPen(self._ANN_COLORS["attack_sharpness"],
                             width=1, style=Qt.PenStyle.DotLine))
            self._spec_plot_preview.addItem(atk_region)
            self._ann_items.append(atk_region)
            atk_bounds = _effective_bounds("attack_sharpness", attack)
            if atk_bounds is not None:
                atk_lo_val, atk_hi_val = atk_bounds
                # Upper boundary (wider attack accepted)
                atk_hi_end = t_start + attack_dur * (atk_hi_val / attack) if attack else attack_end
                hi_atk = pg.InfiniteLine(
                    pos=atk_hi_end, angle=90,
                    pen=pg.mkPen("#4dd0e1", width=1,
                                 style=Qt.PenStyle.DashLine))
                self._spec_plot_preview.addItem(hi_atk)
                self._ann_items.append(hi_atk)
                # Lower boundary (narrower attack accepted)
                atk_lo_end = t_start + attack_dur * (atk_lo_val / attack) if attack else t_start
                if atk_lo_end > t_start:
                    lo_atk = pg.InfiniteLine(
                        pos=atk_lo_end, angle=90,
                        pen=pg.mkPen("#4dd0e1", width=1,
                                     style=Qt.PenStyle.DashDotLine))
                    self._spec_plot_preview.addItem(lo_atk)
                    self._ann_items.append(lo_atk)

        # Harmonicity & Energy Ratio: no spectrogram overlay — these are
        # scalar ratios (0–1) with no natural mapping to the frequency or
        # time axes.  Their values + bounds are visible in the Detection
        # Variables list below.

    def _play_signal(self):
        """Play the current signal region using sounddevice."""
        if self._y is None:
            return
        self._stop_playback()

        prof = self._profiles[self._current_idx]
        region = prof["region"]
        t_start = region.get("t_start", 0)
        t_end = region.get("t_end", 0)
        s0 = max(int(t_start * self._sr), 0)
        s1 = min(int(t_end * self._sr), len(self._y))
        if s1 <= s0:
            return
        clip = self._y[s0:s1].astype(np.float32)

        try:
            import sounddevice as sd
            sd.play(clip, samplerate=self._sr)
        except Exception:
            pass

    def _stop_playback(self):
        """Stop any active sounddevice playback."""
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass

    def _reset_current_settings(self):
        """Reset the current signal's config back to default values."""
        cfg = self._configs[self._current_idx]
        for key, _label, _unit, default_dev in _SIGNAL_VARIABLES:
            cfg[key] = {"enabled": True, "lower_pct": default_dev, "upper_pct": default_dev}
        # Clear any manual boundary overrides for the current signal
        self._manual_bounds.clear()
        # Reload the page to reflect reset values
        self._show_page(self._current_idx)

    def reject(self):
        self._stop_playback()
        self._persist_splitter_sizes()
        super().reject()

    def accept(self):
        self._stop_playback()
        self._persist_splitter_sizes()
        super().accept()

    def _persist_splitter_sizes(self):
        """Save splitter sizes to QSettings for next dialog open."""
        from PyQt6.QtCore import QSettings
        settings = QSettings("BioacousticsRhythmPipeline", "PerSignalConfig")
        settings.setValue(self._SETTINGS_SPLITTER_KEY, self._splitter.sizes())

    # ── page navigation ──────────────────────────────────────────────

    def _save_current_page(self):
        """Persist widget states into self._configs for the current signal."""
        cfg = self._configs[self._current_idx]
        for row in self._var_rows:
            key = row["key"]
            cfg[key]["enabled"] = row["checkbox"].isChecked()
            cfg[key]["lower_pct"] = row["lower_spin"].value()
            cfg[key]["upper_pct"] = row["upper_spin"].value()
            # Persist manual boundary overrides
            if (key, "lower") in self._manual_bounds:
                cfg[key]["lower_bound"] = self._manual_bounds[(key, "lower")]
            else:
                cfg[key].pop("lower_bound", None)
            if (key, "upper") in self._manual_bounds:
                cfg[key]["upper_bound"] = self._manual_bounds[(key, "upper")]
            else:
                cfg[key].pop("upper_bound", None)
        # Remember splitter position for this signal
        self._splitter_sizes_per_signal[self._current_idx] = self._splitter.sizes()

    def _show_page(self, idx: int):
        """Display signal page *idx*."""
        self._stop_playback()
        self._current_idx = idx
        n = len(self._profiles)
        prof = self._profiles[idx]
        analysis = prof["analysis"]
        region = prof["region"]
        cfg = self._configs[idx]

        polarity = region.get("polarity", "positive")
        color = "#90caf9" if polarity == "positive" else "#ef9a9a"
        kind = "Positive" if polarity == "positive" else "Negative"
        self._header_label.setText(
            f"<span style='color:{color}'>{kind} Signal {idx + 1} of {n}</span>")

        self._info_label.setText(
            f"Time: {region.get('t_start', 0):.3f} – {region.get('t_end', 0):.3f} s  |  "
            f"Freq: {region.get('f_low', 0):.0f} – {region.get('f_high', 0):.0f} Hz  |  "
            f"Character: {analysis.get('harmonicity', 0):.2f} harmonicity"
        )

        self._update_preview(region, analysis)

        # Populate variable rows (block signals to avoid cascading updates)
        # First, restore manual bounds for this page from saved config
        self._manual_bounds.clear()
        for row in self._var_rows:
            key = row["key"]
            row["checkbox"].setChecked(cfg[key]["enabled"])
            row["lower_spin"].blockSignals(True)
            row["lower_slider"].blockSignals(True)
            row["upper_spin"].blockSignals(True)
            row["upper_slider"].blockSignals(True)
            row["lower_spin"].setValue(cfg[key]["lower_pct"])
            row["lower_slider"].setValue(cfg[key]["lower_pct"])
            row["upper_spin"].setValue(cfg[key]["upper_pct"])
            row["upper_slider"].setValue(cfg[key]["upper_pct"])
            row["lower_spin"].blockSignals(False)
            row["lower_slider"].blockSignals(False)
            row["upper_spin"].blockSignals(False)
            row["upper_slider"].blockSignals(False)
            # Restore manual overrides and slider styling
            if "lower_bound" in cfg[key]:
                self._manual_bounds[(key, "lower")] = cfg[key]["lower_bound"]
                row["lower_slider"].setStyleSheet(self._slider_ss_grey)
                row["lower_spin"].setStyleSheet(self._spin_ss_grey)
            else:
                row["lower_slider"].setStyleSheet(self._slider_ss)
                row["lower_spin"].setStyleSheet(self._spin_ss)
            if "upper_bound" in cfg[key]:
                self._manual_bounds[(key, "upper")] = cfg[key]["upper_bound"]
                row["upper_slider"].setStyleSheet(self._slider_ss_grey)
                row["upper_spin"].setStyleSheet(self._spin_ss_grey)
            else:
                row["upper_slider"].setStyleSheet(self._slider_ss)
                row["upper_spin"].setStyleSheet(self._spin_ss)

        self._update_value_display(analysis)
        self._apply_descriptions()

        # Restore per-signal splitter sizes if remembered
        if idx in self._splitter_sizes_per_signal:
            self._splitter.setSizes(self._splitter_sizes_per_signal[idx])

        self._prev_btn.setEnabled(idx > 0)
        is_last = (idx == n - 1)
        self._next_btn.setText("✅ Confirm && Run" if is_last else "Next ▶")
        self._page_label.setText(f"Signal {idx + 1} / {n}")

    def _go_prev(self):
        self._save_current_page()
        if self._current_idx > 0:
            self._show_page(self._current_idx - 1)

    def _go_next(self):
        self._save_current_page()
        if self._current_idx < len(self._profiles) - 1:
            self._show_page(self._current_idx + 1)
        else:
            self.accept()

    # ── public API ───────────────────────────────────────────────────

    def get_configs(self) -> list[dict]:
        self._save_current_page()
        return self._configs

    def get_profiles(self) -> list[dict]:
        return self._profiles


'''

_PerSignalConfigDialog = _ExtractedPerSignalConfigDialog


_NegativeSubtractionDialog = _ExtractedNegativeSubtractionDialog


# ═══════════════════════════════════════════════════════════════════════════
# _ExcelColumnDialog — select filename and onset columns from Excel/CSV
# ═══════════════════════════════════════════════════════════════════════════

_ExcelColumnDialog = _ExtractedExcelColumnDialog
_ExcelSaveDialog = _ExtractedExcelSaveDialog


# ═══════════════════════════════════════════════════════════════════════════
# Save Selections Dialog
# ═══════════════════════════════════════════════════════════════════════════

_SaveSelectionsDialog = _ExtractedSaveSelectionsDialog
_LoadSelectionsDialog = _ExtractedLoadSelectionsDialog


# ═══════════════════════════════════════════════════════════════════════════
# OnsetEditorPanel
# ═══════════════════════════════════════════════════════════════════════════

class OnsetEditorPanel(QWidget):
    """Interactive onset editing panel with waveform viewer and data table.

    Integrates into the pipeline GUI as an additional step panel.
    """

    # Emitted when onsets are saved (file_path, onset_count)
    onsetsSaved = pyqtSignal(str, int)
    # Emitted when the viewer's maximize button is toggled
    maximizeRequested = pyqtSignal(int)  # 0=default, 1=fullscreen, 2=fullscreen-2

    _COL_HEADERS = ["#", "Time (s)", "IOI (ms)", "r_k", "Stable"]
    _COL_IDX = 0
    _COL_TIME = 1
    _COL_IOI = 2
    _COL_RK = 3
    _COL_STABLE = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._onset_times: list[float] = []
        self._undo_stack = _UndoStack()
        self._undo_stack.push([])  # initial empty state
        self._audio_path: Optional[str] = None
        self._loaded_file_index: int = -1
        self._label_path: Optional[str] = None
        self._dirty = False
        self._suppress_file_selection_handler: bool = False
        self._updating_table = False
        self._updating_viewer = False
        self._viewer: Optional[_AudioViewerWidget] = None
        self._viewer_initialized = False
        self._onset_hitbox_px: int = 5  # pixel radius for onset click detection
        self._saved_outer_sizes: list[int] = []
        self._saved_inner_sizes: list[int] = []
        self._selected_region: Optional[tuple] = None
        self._loaded_signal_profile: dict | None = None

        # ── Excel/CSV onset source state ──
        self._excel_onset_path: Optional[str] = None  # path to Excel/CSV used for onset loading
        self._excel_onset_col: str = "Exact Onset Times Used (s)"  # column with onset data
        self._excel_filename_col: str = "File Name"  # column with audio filenames
        self._excel_sheet_name: str | int = "File Summaries"  # sheet name
        self._onset_source: str = "txt"  # "txt" or "excel"
        self._pipeline_excel_path: Optional[str] = None  # path from Onset Finder output

        # Refresh timers for performance (defer expensive updates)
        self._table_refresh_timer = QTimer(self)
        self._table_refresh_timer.setSingleShot(True)
        self._table_refresh_timer.timeout.connect(self._refresh_table_now)
        self._viewer_refresh_timer = QTimer(self)
        self._viewer_refresh_timer.setSingleShot(True)
        self._viewer_refresh_timer.timeout.connect(self._refresh_viewer_markers_now)

        # ── Focus Onsets mode state ──
        self._focus_mode = False
        self._focus_polarity: str = "positive"  # "positive" or "negative"
        # Per-file focus regions: {filename: [{"t_start", "t_end", "f_low", "f_high", "polarity"}]}
        self._focus_regions: dict[str, list[dict]] = {}

        # ── Onset Layers state ──
        # Each layer is a dict: {"name": str, "onset_times": list[float],
        #   "focus_regions": dict[str, list[dict]], "undo_stack": _UndoStack, "dirty": bool}
        # _onset_times, _focus_regions, _undo_stack, _dirty are "live" refs to the active layer.
        self._layers: list[_OnsetLayerState] = [self._make_default_layer("Layer 1")]
        self._active_layer_idx: int = 0
        # Sync the live attributes with Layer 1 (they were already initialised above)
        _save_active_layer_state(
            self._layers,
            self._active_layer_idx,
            self._onset_times,
            self._focus_regions,
            self._undo_stack,
            self._dirty,
        )

        # ── Review mode state ──
        self._review_mode = False
        self._review_files: list[str] = []
        self._review_index: int = 0
        self._review_folder: str = ""

        # ── Comparison mode state ──
        # Each entry: {"path": str, "label": str, "times": list[float],
        #              "color": (r,g,b,a)}
        self._comp_files: list[dict] = []
        self._comp_palette = [
            (255, 165, 0, 200),   # orange
            (170, 100, 255, 200), # purple
            (0, 200, 200, 200),   # cyan
            (255, 100, 180, 200), # pink
            (180, 180, 0, 200),   # yellow-olive
            (100, 200, 100, 200), # lime
        ]
        self._comp_tolerance_ms = 1.0
        self._comp_filter_idx = 0
        self._manage_btn = None  # will be created in _build_ui toolbar section

        self._build_ui()
        self._connect_signals()
        self._update_button_states()
        # Register all tooltipped widgets with the description-level system so
        # they swap brief/detailed/novice text when the app-wide Descriptions
        # combo changes.
        _capture_onset_editor_tooltips(self)

    # ──────────────────────────────────────────────────────────────────────
    # UI Construction
    # ──────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        # ── Top controls container (will go into _outer_splitter) ──
        self._top_controls = QWidget()
        self._top_controls.setStyleSheet(f"background: transparent;")
        _top_layout = QVBoxLayout(self._top_controls)
        _top_layout.setContentsMargins(0, 0, 0, 0)
        _top_layout.setSpacing(6)

        # ── Row 1: Header + Input folder ──
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        # Title block (fixed width)
        title_block = QVBoxLayout()
        title_block.setSpacing(0)
        header = QLabel("Onset Editor")
        header.setFont(QFont("", 13, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {_ACCENT}; background: transparent;")
        title_block.addWidget(header)
        desc = QLabel(
            "Load audio files, view and edit onset markers interactively. "
            "Changes are saved to Audacity label files."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {_TEXT_DIM}; font-size: 11px; background: transparent;")
        desc.setMaximumWidth(320)
        title_block.addWidget(desc)
        row1.addLayout(title_block)

        _row_sep = QFrame()
        _row_sep.setFrameShape(QFrame.Shape.VLine)
        _row_sep.setStyleSheet(f"background-color: {_BORDER}; max-width: 1px;")
        row1.addWidget(_row_sep)

        # Input folder
        folder_label = QLabel("Input folder:")
        folder_label.setStyleSheet(
            f"color: {_TEXT_DIM}; font-size: 11px; background: transparent;")
        row1.addWidget(folder_label)

        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("Select audio folder…")
        self._folder_edit.setReadOnly(True)
        self._folder_edit.setStyleSheet(
            f"QLineEdit {{ background: {_BG_INPUT}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; padding: 3px 6px; "
            f"font-size: 11px; }}"
        )
        row1.addWidget(self._folder_edit, stretch=1)

        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 3px 10px; font-size: 11px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
        )
        row1.addWidget(self._browse_btn)

        self._folder_auto_cb = QCheckBox("Auto-set")
        self._folder_auto_cb.setChecked(True)
        self._folder_auto_cb.setToolTip(
            "Automatically set from the Onset Finder's input audio folder")
        self._folder_auto_cb.setStyleSheet(
            f"QCheckBox {{ color: {_TEXT_DIM}; font-size: 11px; }}")
        self._folder_auto_cb.toggled.connect(self._on_folder_auto_toggled)
        row1.addWidget(self._folder_auto_cb)

        _top_layout.addLayout(row1)

        # ── Row 2: Audio File + Main Onset File + Save Onsets ──
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        _lbl_style = f"color: {_TEXT_DIM}; font-size: 11px; background: transparent;"
        _input_style = (
            f"QLineEdit {{ background: {_BG_INPUT}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 3px 6px; font-size: 11px; }}")
        _combo_style = (
            f"QComboBox {{ background: {_BG_INPUT}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 3px 6px; font-size: 11px; }}")
        _small_btn_style = (
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 3px 10px; font-size: 11px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
            f"QPushButton:disabled {{ color: {_TEXT_MUTED}; border-color: {_BG_MID}; }}"
        )

        af_label = QLabel("Audio File:")
        af_label.setStyleSheet(_lbl_style)
        row2.addWidget(af_label)

        self._file_combo = QComboBox()
        self._file_combo.setMinimumWidth(180)
        self._file_combo.setStyleSheet(_combo_style)
        row2.addWidget(self._file_combo, stretch=1)

        _row2_sep = QFrame()
        _row2_sep.setFrameShape(QFrame.Shape.VLine)
        _row2_sep.setStyleSheet(f"background-color: {_BORDER}; max-width: 1px;")
        row2.addWidget(_row2_sep)

        ol_label = QLabel("Main Onset File:")
        ol_label.setStyleSheet(_lbl_style)
        row2.addWidget(ol_label)

        self._onset_file_edit = QLineEdit()
        self._onset_file_edit.setPlaceholderText("(auto: Onset Finder Excel)")
        self._onset_file_edit.setReadOnly(True)
        self._onset_file_edit.setStyleSheet(_input_style)
        row2.addWidget(self._onset_file_edit, stretch=1)

        self._onset_browse_btn = QPushButton("Browse…")
        self._onset_browse_btn.setStyleSheet(_small_btn_style)
        row2.addWidget(self._onset_browse_btn)

        self._onset_auto_cb = QCheckBox("Auto-set")
        self._onset_auto_cb.setChecked(True)
        self._onset_auto_cb.setToolTip(
            "Automatically use the Onset Finder's output Excel file.\n"
            "Uncheck to browse for a different Excel/CSV or .txt file.")
        self._onset_auto_cb.setStyleSheet(
            f"QCheckBox {{ color: {_TEXT_DIM}; font-size: 11px; }}")
        self._onset_auto_cb.toggled.connect(self._on_onset_auto_toggled)
        row2.addWidget(self._onset_auto_cb)

        _top_layout.addLayout(row2)

        # ── Create Manage / Undo / Redo buttons early so they can go in row 2b ──
        self._undo_btn = QPushButton("↩ Undo")
        self._redo_btn = QPushButton("↪ Redo")
        self._manage_btn = QPushButton("📋 Manage Onset / Excel Files")
        self._manage_btn.setToolTip("Open the Onset & Excel Manager dialog")
        self._manage_btn.setStyleSheet(
            f"QPushButton {{ background: {_ACCENT_DIM}; color: white; "
            f"border: none; border-radius: 5px; "
            f"padding: 6px 14px; font-size: 13px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {_ACCENT}; }}"
        )
        self._manage_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._manage_btn.clicked.connect(self._open_onset_manager)

        # ── Row 2b: Manage / Excel column controls / Undo-Redo ──
        self._excel_info_row = QHBoxLayout()
        self._excel_info_row.setSpacing(8)

        # Excel-specific widgets (shown/hidden based on onset source)
        self._excel_col_label = QLabel("Onset Column:")
        self._excel_col_label.setStyleSheet(_lbl_style)
        self._excel_col_label.hide()
        self._excel_info_row.addWidget(self._excel_col_label)

        self._excel_col_edit = QLineEdit()
        self._excel_col_edit.setReadOnly(True)
        self._excel_col_edit.setPlaceholderText("(select column)")
        self._excel_col_edit.setStyleSheet(_input_style)
        self._excel_col_edit.setMaximumWidth(280)
        self._excel_col_edit.hide()
        self._excel_info_row.addWidget(self._excel_col_edit)

        self._excel_col_btn = QPushButton("Choose Column…")
        self._excel_col_btn.setStyleSheet(_small_btn_style)
        self._excel_col_btn.clicked.connect(self._choose_excel_column)
        self._excel_col_btn.hide()
        self._excel_info_row.addWidget(self._excel_col_btn)

        self._excel_info_row.addSpacing(8)
        self._excel_info_row.addWidget(self._manage_btn)

        # Prev / Next file navigation buttons
        _file_nav_style = (
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 5px; "
            f"padding: 5px 10px; font-size: 12px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; color: white; }}"
            f"QPushButton:disabled {{ color: {_TEXT_MUTED}; border-color: {_BG_WIDGET}; }}"
        )
        self._excel_info_row.addSpacing(6)
        self._prev_file_btn = QPushButton("⏮ Prev")
        self._prev_file_btn.setToolTip("Load previous audio file")
        self._prev_file_btn.setStyleSheet(_file_nav_style)
        self._prev_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prev_file_btn.clicked.connect(self._navigate_prev_file)
        self._excel_info_row.addWidget(self._prev_file_btn)

        self._next_file_btn = QPushButton("Next ⏭")
        self._next_file_btn.setToolTip("Load next audio file")
        self._next_file_btn.setStyleSheet(_file_nav_style)
        self._next_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_file_btn.clicked.connect(self._navigate_next_file)
        self._excel_info_row.addWidget(self._next_file_btn)

        self._excel_info_row.addStretch()

        # Settings button (opens onset editor settings dialog)
        self._settings_btn = QPushButton("⚙ Settings")
        self._settings_btn.setToolTip("Open Onset Editor settings")
        self._settings_btn.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 5px; "
            f"padding: 6px 14px; font-size: 13px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; color: white; }}"
        )
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.clicked.connect(self._open_settings_dialog)
        self._excel_info_row.addWidget(self._settings_btn)
        self._excel_info_row.addSpacing(4)

        self._excel_info_row.addWidget(self._undo_btn)
        self._excel_info_row.addWidget(self._redo_btn)

        # Wrap in a widget (always visible — Excel parts shown/hidden individually)
        self._excel_info_widget = QWidget()
        self._excel_info_widget.setLayout(self._excel_info_row)
        self._excel_info_widget.setStyleSheet(f"background: transparent;")
        _top_layout.addWidget(self._excel_info_widget)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {_BORDER}; max-height: 1px;")
        _top_layout.addWidget(sep)

        # ── Review-mode navigation bar (hidden by default) ──
        self._review_bar = QWidget()
        rb_layout = QHBoxLayout(self._review_bar)
        rb_layout.setContentsMargins(6, 4, 6, 4)
        rb_layout.setSpacing(8)

        _rb_btn_style = (
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 5px 14px; font-size: 12px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; color: white; }}"
            f"QPushButton:disabled {{ color: {_TEXT_MUTED}; border-color: {_BG_MID}; }}"
        )
        _rb_accent_style = (
            f"QPushButton {{ background: {_ACCENT_DIM}; color: white; "
            f"border: none; border-radius: 4px; "
            f"padding: 5px 14px; font-size: 12px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {_ACCENT}; }}"
            f"QPushButton:disabled {{ background: {_BORDER}; color: {_TEXT_MUTED}; }}"
        )

        self._review_prev_btn = QPushButton("← Previous")
        self._review_prev_btn.setStyleSheet(_rb_btn_style)
        self._review_prev_btn.clicked.connect(self._review_prev)
        rb_layout.addWidget(self._review_prev_btn)

        self._review_counter = QLabel("File 1 / 1")
        self._review_counter.setStyleSheet(
            f"color: {_TEXT}; font-size: 13px; font-weight: bold; padding: 0 8px;"
        )
        rb_layout.addWidget(self._review_counter)

        self._review_next_btn = QPushButton("Next →")
        self._review_next_btn.setStyleSheet(_rb_btn_style)
        self._review_next_btn.clicked.connect(self._review_next)
        rb_layout.addWidget(self._review_next_btn)

        rb_layout.addStretch()

        self._review_revert_btn = QPushButton("↩ Revert")
        self._review_revert_btn.setToolTip("Discard edits and reload original onsets")
        self._review_revert_btn.setStyleSheet(_rb_btn_style)
        self._review_revert_btn.clicked.connect(self._review_revert)
        rb_layout.addWidget(self._review_revert_btn)

        self._review_save_btn = QPushButton("💾 Save Both")
        self._review_save_btn.setToolTip("Save onsets to label file and Excel")
        self._review_save_btn.setStyleSheet(_rb_accent_style)
        self._review_save_btn.clicked.connect(self._review_save_current)
        rb_layout.addWidget(self._review_save_btn)

        self._review_save_next_btn = QPushButton("✓ Save & Next")
        self._review_save_next_btn.setToolTip("Save onsets and advance to the next file")
        self._review_save_next_btn.setStyleSheet(_rb_accent_style)
        self._review_save_next_btn.clicked.connect(self._review_save_and_next)
        rb_layout.addWidget(self._review_save_next_btn)

        rb_layout.addSpacing(12)

        self._review_finish_btn = QPushButton("✓ Finish Review")
        self._review_finish_btn.setToolTip("Exit review mode")
        self._review_finish_btn.setStyleSheet(
            f"QPushButton {{ background: #b71c1c; color: white; "
            f"border: none; border-radius: 4px; "
            f"padding: 5px 14px; font-size: 12px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #c62828; }}"
        )
        self._review_finish_btn.clicked.connect(self._review_finish)
        rb_layout.addWidget(self._review_finish_btn)

        self._review_bar.setStyleSheet(
            f"background: {_BG_MID}; border: 1px solid {_ACCENT}; border-radius: 6px;"
        )
        self._review_bar.hide()
        _top_layout.addWidget(self._review_bar)

        # ── Outer splitter: top controls + (viewer / table) ──
        self._outer_splitter = QSplitter(Qt.Orientation.Vertical)
        self._outer_splitter.setHandleWidth(5)
        self._outer_splitter.setStyleSheet(
            f"QSplitter::handle {{ background-color: {_BORDER}; }}"
            f"QSplitter::handle:hover {{ background-color: {_ACCENT}; }}"
            f"QSplitter::handle:vertical {{ height: 5px; }}"
        )
        self._outer_splitter.addWidget(self._top_controls)

        # ── Main splitter: viewer (top) + table (bottom) ──
        self._splitter = QSplitter(Qt.Orientation.Vertical)

        # Viewer placeholder — actual AudioViewerWidget is created lazily
        # on first showEvent to avoid pyqtgraph segfault on macOS when the
        # widget is painted inside a QStackedWidget before the graphics
        # scene is fully initialised.
        self._viewer_placeholder = QWidget()
        self._viewer_placeholder.setMinimumHeight(120)
        self._viewer_placeholder.setStyleSheet(f"background: {_BG};")
        _ph_lay = QVBoxLayout(self._viewer_placeholder)
        _ph_lbl = QLabel("Loading viewer…")
        _ph_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _ph_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 13px;")
        _ph_lay.addWidget(_ph_lbl)
        self._splitter.addWidget(self._viewer_placeholder)

        # Bottom section: toolbar + table
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(4)

        # Toolbar buttons (will be placed below the viewer in _init_viewer)
        self._toolbar_buttons_layout = QHBoxLayout()
        self._toolbar_buttons_layout.setSpacing(6)

        self._add_btn = QPushButton("+ Add Onset")
        self._add_btn.setToolTip(
            "Click to add an onset at the current playhead position, "
            "or Ctrl+click on the waveform"
        )
        self._remove_btn = QPushButton("− Remove Selected")
        self._remove_btn.setToolTip("Remove the selected onset from the table and viewer")
        self._detect_region_btn = QPushButton("🔍 Quick Onset Finder")
        self._detect_region_btn.setToolTip(
            "Open Quick Onset Finder for the current normal selection, or the full clip if no normal selection is active. "
            "When Focus Onsets mode is active, this is locked to the selected focus region."
        )
        self._detect_region_btn.setEnabled(False)

        self._detect_all_layers_btn = QPushButton("🔍 Auto-Detect All Layers")
        self._detect_all_layers_btn.setToolTip(
            "Run onset detection for every layer using each layer's focus regions "
            "and recommended settings"
        )
        self._detect_all_layers_btn.setEnabled(False)

        # ── Per-signal detection buttons ──
        self._analyze_signals_btn = QPushButton("📊 Analyze Signals")
        self._analyze_signals_btn.setToolTip(
            "Open dialog to analyze the current positive/negative focus signals.\n"
            "Shows spectral analysis, recommended onset detection settings,\n"
            "and optional onset layer clustering."
        )
        self._analyze_signals_btn.setEnabled(False)

        self._per_signal_btn = QPushButton("🎯 Per-Signal Detect")
        self._per_signal_btn.setToolTip(
            "Run separate onset detection for each positive focus signal.\n"
            "Creates one layer per signal with customisable deviation ranges.\n"
            "Draw positive focus regions first, then click this button."
        )
        self._per_signal_btn.setEnabled(False)

        self._neg_subtract_btn = QPushButton("🚫 Neg. Subtract")
        self._neg_subtract_btn.setToolTip(
            "Run detection for negative signals and remove matching onsets.\n"
            "Requires existing onsets and negative focus regions."
        )
        self._neg_subtract_btn.setEnabled(False)

        self._merge_layers_btn = QPushButton("🔗 Merge Layers")
        self._merge_layers_btn.setToolTip(
            "Merge all per-signal layer onsets into a single FinalMergedOnsets layer.\n"
            "Deduplicates within 1 ms tolerance."
        )
        self._merge_layers_btn.setEnabled(False)

        self._edit_audio_btn = QPushButton("🎛 Quick Audio Editor")
        self._edit_audio_btn.setToolTip(
            "Open Quick Audio Editor for the current normal selection, or the full clip if no normal selection is active. "
            "When Focus Onsets mode is active, this is locked to the selected focus region."
        )
        self._edit_audio_btn.setEnabled(False)

        self._mfcc_audio_btn = QPushButton("🧹 Audio Edits-MFCC")
        self._mfcc_audio_btn.setToolTip(
            "Clean audio by MFCC template matching: uses your positive focus-onset regions "
            "as signal templates, then mutes sections of the recording that don't resemble "
            "those templates.  Requires at least one positive focus region to be defined."
        )
        self._mfcc_audio_btn.setEnabled(False)

        self._play_sel_btn = QPushButton("▶ Play Selection")
        self._play_sel_btn.setToolTip(
            "Play the selected region once (click+drag to select a region first)"
        )
        self._play_sel_btn.setEnabled(False)

        self._loop_sel_btn = QPushButton("🔁 Loop Selection")
        self._loop_sel_btn.setToolTip(
            "Toggle looping playback of the selected region"
        )
        self._loop_sel_btn.setCheckable(True)
        self._loop_sel_btn.setEnabled(False)

        self._edit_onsets_btn = QPushButton("✏ Edit Onsets")
        self._edit_onsets_btn.setToolTip(
            "Toggle ability to drag existing onset markers to new positions"
        )
        self._edit_onsets_btn.setCheckable(True)
        self._edit_onsets_btn.setChecked(False)
        self._edit_onsets_btn.setStyleSheet(
            "QPushButton {"
            "  background: #5c2020; color: #ffaaaa;"
            "  border: 1px solid #8b3030; border-radius: 4px;"
            "  padding: 5px 12px; font-size: 12px;"
            "}"
            "QPushButton:hover {"
            "  border-color: #cc4444; color: white;"
            "}"
            "QPushButton:checked {"
            "  background: qradialgradient("
            "    cx:0.5, cy:0.5, radius:0.8,"
            "    fx:0.5, fy:0.5,"
            "    stop:0 #5cff5c, stop:0.5 #2e7d32, stop:1 #1b5e20);"
            "  color: white; border: 1px solid #66bb6a;"
            "}"
            "QPushButton:checked:hover {"
            "  border-color: #81c784;"
            "}"
        )
        self._edit_onsets_btn.toggled.connect(self._on_edit_onsets_toggled)

        # ── Focus Onsets button (blue glow when active) ──
        self._focus_onsets_btn = QPushButton("🔎 Focus Onsets")
        self._focus_onsets_btn.setToolTip(
            "Toggle Focus Onsets mode: draw positive/negative regions on the "
            "spectrogram to guide onset detection"
        )
        self._focus_onsets_btn.setCheckable(True)
        self._focus_onsets_btn.setChecked(False)
        self._focus_onsets_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {_FOCUS_BLUE_DIM}; color: #aaccff;"
            f"  border: 1px solid {_FOCUS_BLUE_BORDER}; border-radius: 4px;"
            f"  padding: 5px 12px; font-size: 12px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  border-color: {_FOCUS_BLUE_BRIGHT}; color: white;"
            f"}}"
            f"QPushButton:checked {{"
            f"  background: qradialgradient("
            f"    cx:0.5, cy:0.5, radius:0.8,"
            f"    fx:0.5, fy:0.5,"
            f"    stop:0 {_FOCUS_BLUE_BRIGHT}, stop:0.5 {_FOCUS_BLUE}, stop:1 {_FOCUS_BLUE_DARK});"
            f"  color: white; border: 1px solid {_FOCUS_BLUE_BRIGHT};"
            f"}}"
            f"QPushButton:checked:hover {{"
            f"  border-color: #90caf9;"
            f"}}"
        )
        self._focus_onsets_btn.toggled.connect(self._on_focus_onsets_toggled)

        # ── Positive / Negative polarity toggle buttons ──
        # These sit in a small container that is only visible when Focus mode is on.
        self._pos_neg_widget = QWidget()
        self._pos_neg_widget.setStyleSheet(f"background: transparent;")
        pos_neg_layout = QHBoxLayout(self._pos_neg_widget)
        pos_neg_layout.setContentsMargins(0, 0, 0, 2)
        pos_neg_layout.setSpacing(4)

        self._positive_btn = QPushButton("+ Positive")
        self._positive_btn.setCheckable(True)
        self._positive_btn.setChecked(True)  # positive is default
        self._positive_btn.setToolTip("Draw regions marking the signal of interest (positive)")
        self._positive_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {_FOCUS_BLUE_DIM}; color: #90caf9;"
            f"  border: 1px solid {_POSITIVE_BLUE_BORDER}; border-radius: 4px;"
            f"  padding: 4px 10px; font-size: 11px; font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{ border-color: {_POSITIVE_BLUE}; color: white; }}"
            f"QPushButton:checked {{"
            f"  background: {_POSITIVE_BLUE}; color: white;"
            f"  border: 1px solid {_POSITIVE_BLUE_BORDER};"
            f"}}"
        )

        self._negative_btn = QPushButton("− Negative")
        self._negative_btn.setCheckable(True)
        self._negative_btn.setChecked(False)
        self._negative_btn.setToolTip("Draw regions marking noise/background to ignore (negative)")
        self._negative_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {_FOCUS_BLUE_DIM}; color: #ef9a9a;"
            f"  border: 1px solid {_NEGATIVE_RED_BORDER}; border-radius: 4px;"
            f"  padding: 4px 10px; font-size: 11px; font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{ border-color: {_NEGATIVE_RED}; color: white; }}"
            f"QPushButton:checked {{"
            f"  background: {_NEGATIVE_RED}; color: white;"
            f"  border: 1px solid {_NEGATIVE_RED_BORDER};"
            f"}}"
        )

        self._positive_btn.toggled.connect(self._on_positive_toggled)
        self._negative_btn.toggled.connect(self._on_negative_toggled)

        # ── Layer selector controls (inside Focus Onsets bar) ──
        _layer_lbl_style = (
            f"color: {_TEXT_DIM}; font-size: 11px; background: transparent; "
            f"padding: 0 2px;"
        )
        _layer_btn_style = (
            f"QPushButton {{ background: {_FOCUS_BLUE_DIM}; color: #aaccff; "
            f"border: 1px solid {_FOCUS_BLUE_BORDER}; border-radius: 4px; "
            f"padding: 3px 8px; font-size: 11px; }}"
            f"QPushButton:hover {{ border-color: {_FOCUS_BLUE_BRIGHT}; color: white; }}"
            f"QPushButton:disabled {{ color: {_TEXT_MUTED}; border-color: {_BG_MID}; }}"
        )

        self._layer_label = QLabel("Layers:")
        self._layer_label.setStyleSheet(_layer_lbl_style)

        # Layer dropdown button (replaces old QComboBox with checkbox popup)
        self._checked_layer_indices: set[int] = {0}  # initially Layer 1 checked
        self._layer_menu = _LayerCheckboxMenu(self)
        self._layer_menu.layerSelectionChanged.connect(self._on_layer_selection_changed)

        self._layer_combo_btn = QToolButton()
        self._layer_combo_btn.setText("Layer 1 ▾")
        self._layer_combo_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._layer_combo_btn.setMenu(self._layer_menu)
        self._layer_combo_btn.setStyleSheet(
            f"QToolButton {{ background: {_BG_INPUT}; color: {_TEXT}; "
            f"border: 1px solid {_FOCUS_BLUE_BORDER}; border-radius: 4px; "
            f"padding: 3px 8px; font-size: 11px; min-width: 100px; }}"
            f"QToolButton:hover {{ border-color: {_FOCUS_BLUE_BRIGHT}; }}"
            f"QToolButton::menu-indicator {{ image: none; }}"
        )

        # Keep backward-compat: _layer_combo is now an alias property.
        # Code that calls _layer_combo.addItem / .setCurrentIndex etc.
        # will be updated to use the new helper methods.
        self._layer_combo = QComboBox()  # hidden; used only for legacy compat
        self._layer_combo.addItem("Layer 1")
        self._layer_combo.hide()
        self._layer_combo.currentIndexChanged.connect(self._on_layer_combo_changed)

        self._merge_sel_btn = QPushButton("⊕ Merge Sel.")
        self._merge_sel_btn.setToolTip(
            "Merge only the checked layers into one\n"
            "(check 2+ layers in the Layers dropdown first)")
        self._merge_sel_btn.setStyleSheet(_layer_btn_style)
        self._merge_sel_btn.setEnabled(False)
        self._merge_sel_btn.clicked.connect(self._merge_selected_layers)

        self._add_layer_btn = QPushButton("+ Layer")
        self._add_layer_btn.setToolTip("Add a new onset layer")
        self._add_layer_btn.setStyleSheet(_layer_btn_style)
        self._add_layer_btn.clicked.connect(self._add_layer)

        self._remove_layer_btn = QPushButton("− Layer")
        self._remove_layer_btn.setToolTip("Remove the current onset layer")
        self._remove_layer_btn.setStyleSheet(_layer_btn_style)
        self._remove_layer_btn.clicked.connect(self._remove_layer)

        # ── Signal browser dropdown ──
        _signal_browser_lbl_style = (
            f"color: {_TEXT_DIM}; font-size: 11px; background: transparent; "
            f"padding: 0 2px;"
        )
        _signal_browser_combo_style = (
            f"QComboBox {{ background: {_BG_INPUT}; color: {_TEXT}; "
            f"border: 1px solid {_FOCUS_BLUE_BORDER}; border-radius: 4px; "
            f"padding: 3px 6px; font-size: 11px; min-width: 160px; }}"
            f"QComboBox:focus {{ border-color: {_FOCUS_BLUE_BRIGHT}; }}"
            f"QComboBox::drop-down {{ border: none; }}"
        )
        self._signal_browser_label = QLabel("Signals:")
        self._signal_browser_label.setStyleSheet(_signal_browser_lbl_style)
        self._signal_browser_combo = QComboBox()
        self._signal_browser_combo.setStyleSheet(_signal_browser_combo_style)
        self._signal_browser_combo.setToolTip(
            "Browse and select focus regions (positive/negative signals) for this layer"
        )
        self._signal_browser_combo.currentIndexChanged.connect(
            self._on_signal_browser_selected
        )
        self._refresh_signal_browser_combo()

        self._save_selections_btn = QPushButton("💾 Save Selections")
        self._save_selections_btn.setToolTip(
            "Export positive/negative audio regions as separate WAV files"
        )
        self._save_selections_btn.setStyleSheet(
            f"QPushButton {{ background: {_FOCUS_BLUE_DIM}; color: #aaccff; "
            f"border: 1px solid {_FOCUS_BLUE_BORDER}; border-radius: 4px; "
            f"padding: 3px 8px; font-size: 11px; font-weight: bold; }}"
            f"QPushButton:hover {{ border-color: {_FOCUS_BLUE_BRIGHT}; color: white; }}"
            f"QPushButton:disabled {{ color: {_TEXT_MUTED}; border-color: {_BG_MID}; }}"
        )
        self._save_selections_btn.setEnabled(False)
        self._save_selections_btn.clicked.connect(self._open_save_selections_dialog)

        self._load_selections_btn = QPushButton("📂 Load Selections")
        self._load_selections_btn.setToolTip(
            "Load saved positive/negative signal examples and restore their spectrogram regions when metadata is available"
        )
        self._load_selections_btn.setStyleSheet(
            f"QPushButton {{ background: {_FOCUS_BLUE_DIM}; color: #aaccff; "
            f"border: 1px solid {_FOCUS_BLUE_BORDER}; border-radius: 4px; "
            f"padding: 3px 8px; font-size: 11px; font-weight: bold; }}"
            f"QPushButton:hover {{ border-color: {_FOCUS_BLUE_BRIGHT}; color: white; }}"
            f"QPushButton:disabled {{ color: {_TEXT_MUTED}; border-color: {_BG_MID}; }}"
        )
        self._load_selections_btn.setEnabled(False)
        self._load_selections_btn.clicked.connect(self._open_load_selections_dialog)

        pos_neg_layout.addStretch()
        pos_neg_layout.addWidget(self._positive_btn)
        pos_neg_layout.addWidget(self._negative_btn)
        pos_neg_layout.addSpacing(16)
        pos_neg_layout.addWidget(self._layer_label)
        pos_neg_layout.addWidget(self._layer_combo_btn)
        pos_neg_layout.addWidget(self._merge_sel_btn)
        pos_neg_layout.addWidget(self._add_layer_btn)
        pos_neg_layout.addWidget(self._remove_layer_btn)
        pos_neg_layout.addSpacing(12)
        pos_neg_layout.addWidget(self._signal_browser_label)
        pos_neg_layout.addWidget(self._signal_browser_combo)
        pos_neg_layout.addSpacing(16)
        pos_neg_layout.addWidget(self._save_selections_btn)
        pos_neg_layout.addWidget(self._load_selections_btn)
        pos_neg_layout.addStretch()
        self._pos_neg_widget.hide()  # hidden until Focus Onsets is checked

        _region_btn_style = (
            f"QPushButton {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 5px 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; color: white; }}"
            f"QPushButton:disabled {{ color: {_TEXT_MUTED}; border-color: {_BG_MID}; }}"
            f"QPushButton:checked {{ background: {_ACCENT_DIM}; border-color: {_ACCENT}; color: white; }}"
        )
        for btn in (self._add_btn, self._remove_btn, self._undo_btn,
                     self._redo_btn, self._detect_region_btn,
                     self._detect_all_layers_btn,
                     self._edit_audio_btn,
                     self._play_sel_btn, self._loop_sel_btn):
            btn.setStyleSheet(_region_btn_style)

        # MFCC audio cleaning button gets a purple-tinted style to distinguish it
        self._mfcc_audio_btn.setStyleSheet(
            f"QPushButton {{ background: {_BG_WIDGET}; color: #ce93d8; "
            f"border: 1px solid #6a1b9a; border-radius: 4px; "
            f"padding: 5px 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ border-color: #ba68c8; color: white; "
            f"background: #2a1a2e; }}"
            f"QPushButton:disabled {{ color: {_TEXT_MUTED}; border-color: {_BG_MID}; "
            f"background: {_BG_WIDGET}; }}"
        )

        # Per-signal group gets a distinct teal accent
        _per_signal_btn_style = (
            f"QPushButton {{ background: {_BG_WIDGET}; color: #80cbc4; "
            f"border: 1px solid #26635b; border-radius: 4px; "
            f"padding: 5px 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ border-color: #4db6ac; color: white; "
            f"background: #1a3a36; }}"
            f"QPushButton:disabled {{ color: {_TEXT_MUTED}; border-color: {_BG_MID}; }}"
        )
        for btn in (self._analyze_signals_btn, self._per_signal_btn,
                     self._neg_subtract_btn,
                     self._merge_layers_btn):
            btn.setStyleSheet(_per_signal_btn_style)

        self._toolbar_buttons_layout.addStretch()
        self._toolbar_buttons_layout.addWidget(self._add_btn)
        self._toolbar_buttons_layout.addWidget(self._remove_btn)
        self._toolbar_buttons_layout.addWidget(self._detect_all_layers_btn)
        self._toolbar_buttons_layout.addSpacing(4)
        self._sig_sep = QFrame()
        self._sig_sep.setFrameShape(QFrame.Shape.VLine)
        self._sig_sep.setStyleSheet(f"color: {_BORDER};")
        self._toolbar_buttons_layout.addWidget(self._sig_sep)
        self._toolbar_buttons_layout.addSpacing(4)
        self._toolbar_buttons_layout.addWidget(self._analyze_signals_btn)
        self._toolbar_buttons_layout.addWidget(self._per_signal_btn)
        self._toolbar_buttons_layout.addWidget(self._neg_subtract_btn)
        self._toolbar_buttons_layout.addWidget(self._merge_layers_btn)
        self._toolbar_buttons_layout.addSpacing(4)
        self._util_sep = QFrame()
        self._util_sep.setFrameShape(QFrame.Shape.VLine)
        self._util_sep.setStyleSheet(f"color: {_BORDER};")
        self._toolbar_buttons_layout.addWidget(self._util_sep)
        self._toolbar_buttons_layout.addSpacing(4)
        self._toolbar_buttons_layout.addWidget(self._play_sel_btn)
        self._toolbar_buttons_layout.addWidget(self._loop_sel_btn)
        self._toolbar_buttons_layout.addStretch()

        # Wrap toolbar buttons + pos/neg toggles into a vertical container
        self._toolbar_container = QWidget()
        _toolbar_container_layout = QVBoxLayout(self._toolbar_container)
        _toolbar_container_layout.setContentsMargins(0, 0, 0, 0)
        _toolbar_container_layout.setSpacing(0)
        _toolbar_container_layout.addWidget(self._pos_neg_widget)

        # Store toolbar as a widget so we can insert it into the viewer later
        self._toolbar_widget = QWidget()
        self._toolbar_widget.setLayout(self._toolbar_buttons_layout)
        self._toolbar_widget.setStyleSheet(f"background: {_BG};")

        _toolbar_container_layout.addWidget(self._toolbar_widget)
        self._toolbar_container.setStyleSheet(f"background: {_BG};")
        # Don't add to table_layout — it will be placed below the viewer in _init_viewer

        # Status line
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            f"color: {_TEXT_DIM}; font-size: 11px; background: transparent; padding: 0 4px;"
        )
        table_layout.addWidget(self._status_label)

        # Onset table
        self._table = QTableWidget(0, len(self._COL_HEADERS))
        self._table.setHorizontalHeaderLabels(self._COL_HEADERS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet(
            f"QTableWidget {{ background: {_BG_WIDGET}; color: {_TEXT}; "
            f"gridline-color: {_BORDER}; border: 1px solid {_BORDER}; "
            f"border-radius: 4px; font-size: 12px; }}"
            f"QTableWidget::item {{ padding: 3px 6px; }}"
            f"QTableWidget::item:selected {{ background: {_ACCENT_DIM}; color: white; }}"
            f"QHeaderView::section {{ background: {_BG_MID}; color: {_TEXT_DIM}; "
            f"border: 1px solid {_BORDER}; padding: 4px 6px; font-weight: bold; }}"
        )
        # Column sizing
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(self._COL_IDX, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self._COL_TIME, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(self._COL_IOI, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(self._COL_RK, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(self._COL_STABLE, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self._COL_IDX, 50)
        self._table.setColumnWidth(self._COL_STABLE, 70)

        table_layout.addWidget(self._table, stretch=1)
        self._splitter.addWidget(table_container)

        self._splitter.setSizes([500, 300])
        self._outer_splitter.addWidget(self._splitter)

        # Set initial outer splitter proportions (controls : viewer+table)
        self._outer_splitter.setCollapsible(0, True)
        self._outer_splitter.setCollapsible(1, False)
        self._outer_splitter.setSizes([120, 700])
        root.addWidget(self._outer_splitter, stretch=1)

    # ──────────────────────────────────────────────────────────────────────
    # Signal wiring
    # ──────────────────────────────────────────────────────────────────────

    def _connect_signals(self):
        # File browser
        self._browse_btn.clicked.connect(self._browse_folder)
        self._file_combo.currentIndexChanged.connect(self._on_file_selected)
        self._onset_browse_btn.clicked.connect(self._browse_onset_file)

        # Toolbar buttons
        self._add_btn.clicked.connect(self._add_onset_at_playhead)
        self._remove_btn.clicked.connect(self._remove_selected_onset)
        self._undo_btn.clicked.connect(self._undo)
        self._redo_btn.clicked.connect(self._redo)
        self._detect_region_btn.clicked.connect(self._detect_onsets_in_region)
        self._detect_all_layers_btn.clicked.connect(self._detect_all_layers)
        self._analyze_signals_btn.clicked.connect(self._open_analyze_signals_dialog)
        self._per_signal_btn.clicked.connect(self._run_per_signal_detection)
        self._neg_subtract_btn.clicked.connect(self._run_negative_subtraction)
        self._merge_layers_btn.clicked.connect(self._confirm_and_merge_layers)
        self._edit_audio_btn.clicked.connect(self._edit_audio_in_region)
        self._mfcc_audio_btn.clicked.connect(self._run_mfcc_audio_cleaning)
        self._play_sel_btn.clicked.connect(self._play_selection)
        self._loop_sel_btn.toggled.connect(self._toggle_loop_selection)

        # Viewer signals are connected in _init_viewer() (deferred)

        # Table selection → viewer highlight
        self._table.currentCellChanged.connect(self._on_table_selection_changed)
        self._table.cellClicked.connect(self._on_table_cell_clicked)
        self._table.cellChanged.connect(self._on_table_cell_edited)

        # Keyboard shortcuts — built from hotkey map
        self._shortcut_actions: dict[str, callable] = {
            "undo":             self._undo,
            "redo":             self._redo,
            "save":             self._save_labels,
            "delete":           self._delete_current_selection,
            "escape":           self._on_escape_pressed,
            "focus_mode":       self._toggle_focus_mode_shortcut,
            "edit_onsets":      self._toggle_edit_onsets_shortcut,
            "detect_onsets":    self._detect_onsets_in_region,
            "quick_audio_edit": self._edit_audio_in_region,
            "manage_files":     self._open_onset_manager,
            "cycle_fullscreen": self._cycle_maximize,
            "prev_layer":       self._prev_layer_shortcut,
            "next_layer":       self._next_layer_shortcut,
            "prev_onset":       self._select_prev_onset,
            "next_onset":       self._select_next_onset,
            "prev_file":        self._navigate_prev_file,
            "next_file":        self._navigate_next_file,
        }
        self._hotkey_map = _get_hotkey_map()
        self._shortcuts: dict[str, QShortcut] = {}
        self._apply_hotkeys()

        # Worker thread reference (onset detection)
        self._detect_worker: Optional[_DetectOnsetsWorker] = None

    # ──────────────────────────────────────────────────────────────────────
    # Onset Layers helpers
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _make_default_layer(name: str = "Layer 1") -> dict:
        """Return a fresh layer dict with empty state."""
        return _make_default_layer_state(name)

    def _save_layer_state(self):
        """Persist live attributes back into the active layer dict."""
        _save_active_layer_state(
            self._layers,
            self._active_layer_idx,
            self._onset_times,
            self._focus_regions,
            self._undo_stack,
            self._dirty,
        )

    def _load_layer_state(self):
        """Load attributes from the active layer dict into live attributes."""
        (
            self._onset_times,
            self._focus_regions,
            self._undo_stack,
            self._dirty,
        ) = _load_active_layer_state(self._layers, self._active_layer_idx)

    def _switch_layer(self, new_idx: int):
        """Save current layer, switch to *new_idx*, refresh display."""
        result = _switch_active_layer_impl(
            self._layers,
            self._active_layer_idx,
            new_idx,
            self._onset_times,
            self._focus_regions,
            self._undo_stack,
            self._dirty,
        )
        if result is None:
            return
        self._active_layer_idx = result["active_layer_idx"]
        self._onset_times = result["onset_times"]
        self._focus_regions = result["focus_regions"]
        self._undo_stack = result["undo_stack"]
        self._dirty = result["dirty"]
        if hasattr(self, '_layer_combo') and self._layer_combo.currentIndex() != new_idx:
            self._set_layer_combo_index(new_idx)
        # Refresh viewer/table for new layer
        self._refresh_layer_data_views()
        self._refresh_active_layer_focus_widgets(
            refresh_signal_browser=True,
            push_layer_info=True,
        )

    def _add_layer(self):
        """Append a new layer and switch to it."""
        self._save_layer_state()
        new_idx, name = _append_empty_layer_impl(self._layers)
        self._active_layer_idx = new_idx
        self._load_layer_state()
        # Update layer combo
        if hasattr(self, '_layer_combo'):
            self._layer_combo.blockSignals(True)
            self._layer_combo.addItem(name)
            self._layer_combo.setCurrentIndex(new_idx)
            self._layer_combo.blockSignals(False)
        # Auto-check the new layer
        self._checked_layer_indices.add(new_idx)
        self._refresh_structural_layer_mutation_widgets(refresh_signal_browser=True)
        self._status_label.setText(f"Added {name}")

    def _remove_layer(self):
        """Remove the active layer (cannot remove the last layer)."""
        result = _remove_active_layer_impl(
            self._layers,
            self._active_layer_idx,
            self._checked_layer_indices,
        )
        if result is None:
            return
        removed_name = result["removed_name"]
        self._active_layer_idx = result["active_layer_idx"]
        self._checked_layer_indices = result["checked_layer_indices"]
        self._load_layer_state()
        self._refresh_restored_layer_widgets()
        self._refresh_structural_layer_mutation_widgets()
        self._status_label.setText(f"Removed {removed_name}")

    # ──────────────────────────────────────────────────────────────────────
    # Lazy viewer initialisation (avoids pyqtgraph crash on macOS)
    # ──────────────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if not self._viewer_initialized:
            # Use a single-shot timer so the widget is fully
            # laid-out / parented before pyqtgraph paints.
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._init_viewer)
            self._viewer_initialized = True

    def _init_viewer(self):
        """Create the AudioViewerWidget and swap it in for the placeholder.

        The viewer is inserted *hidden* and made visible on the next event-loop
        cycle so that Qt's paint engine has time to fully initialise the
        QGraphicsScene font caches (avoids SIGSEGV on macOS Qt6).
        """
        _require_audio_viewer()
        self._viewer = _AudioViewerWidget()
        self._viewer.setVisible(False)  # keep hidden during insertion
        self._viewer._onset_hitbox_px = self._onset_hitbox_px

        # Replace placeholder in the splitter
        idx = self._splitter.indexOf(self._viewer_placeholder)
        self._splitter.replaceWidget(idx, self._viewer)
        self._viewer_placeholder.setParent(None)
        self._viewer_placeholder.deleteLater()
        self._viewer_placeholder = None

        # Connect viewer signals
        self._viewer.onsetAdded.connect(self._on_viewer_onset_added)
        self._viewer.onsetRemoved.connect(self._on_viewer_onset_removed)
        self._viewer.onsetMoved.connect(self._on_viewer_onset_moved)
        self._viewer.viewCtrlClicked.connect(self._on_viewer_ctrl_click)
        self._viewer.viewClicked.connect(self._on_viewer_view_clicked)
        self._viewer.onsetClicked.connect(self._on_viewer_onset_clicked)
        self._viewer.audioLoaded.connect(self._on_viewer_audio_loaded)
        self._viewer.playbackPositionChanged.connect(self._on_viewer_playback_position_changed)
        self._viewer.regionSelected.connect(self._on_viewer_region_selected)
        self._viewer.regionCleared.connect(self._clear_selection_state)
        self._viewer.maximizeRequested.connect(self._on_maximize_state_changed)

        # Insert Edit/Focus + Manage + Undo/Redo into the viewer's chunk nav bar
        if hasattr(self._viewer, '_chunk_layout'):
            cl = self._viewer._chunk_layout
            # Replace the leading spacer with a mirrored left balance block,
            # then center the three action buttons between equal stretches.
            # This compensates for the Waveform/Spectrogram + maximize cluster
            # on the right so Focus Onsets sits on the true visual center.
            _lead_item = cl.takeAt(0)
            if _lead_item is not None:
                del _lead_item
            _toggle_w = max(
                self._viewer._wave_cb.sizeHint().width(),
                self._viewer._spec_cb.sizeHint().width(),
            )
            _right_cluster_w = _toggle_w + cl.spacing() + self._viewer._maximize_btn.sizeHint().width()
            self._chunk_left_balance = QWidget()
            self._chunk_left_balance.setFixedWidth(_right_cluster_w)
            self._chunk_action_row = QWidget()
            _action_layout = QHBoxLayout(self._chunk_action_row)
            _action_layout.setContentsMargins(0, 0, 0, 0)
            _action_layout.setSpacing(6)
            _action_layout.addWidget(self._edit_onsets_btn)
            _action_layout.addWidget(self._focus_onsets_btn)
            _action_layout.addWidget(self._detect_region_btn)
            _action_layout.addWidget(self._edit_audio_btn)
            _action_layout.addWidget(self._mfcc_audio_btn)
            cl.insertWidget(0, self._chunk_left_balance)
            cl.insertStretch(1, 1)
            cl.insertWidget(2, self._chunk_action_row)
            cl.insertStretch(3, 1)

        # Insert the editing toolbar (with pos/neg toggles) below the viewer's chunk bar
        if self._toolbar_container is not None:
            self._viewer.layout().addWidget(self._toolbar_container)

        # Connect viewer focus-region signals
        self._viewer.focusRegionAdded.connect(self._on_viewer_focus_region_added)
        self._viewer.focusRegionRemoved.connect(self._on_viewer_focus_region_removed)
        self._viewer.focusRegionModified.connect(self._on_viewer_focus_region_modified)
        self._viewer.focusRegionExportRequested.connect(self._on_quick_export_region)
        self._viewer.focusRegionMoveRequested.connect(self._on_viewer_focus_region_move)
        self._viewer.focusRegionCopyRequested.connect(self._on_viewer_focus_region_copy)

        # Push initial layer info to the viewer
        self._push_layer_info_to_viewer()

        # Defer showing to the next event-loop cycle so that Qt finishes
        # internal setup before the first paint.
        QTimer.singleShot(0, self._show_viewer)

    def _show_viewer(self):
        """Make the viewer visible and load any pending audio."""
        if self._viewer is None:
            return
        self._viewer.setVisible(True)
        self._splitter.setSizes([500, 300])

        # If audio was already selected before viewer was ready, load it now
        if self._audio_path and os.path.isfile(self._audio_path):
            self._viewer.load_audio(self._audio_path)
            self._refresh_viewer_markers()

    def _current_viewer_playhead(self) -> float | None:
        if self._viewer is None or not hasattr(self._viewer, "get_playhead_position"):
            return None
        try:
            return float(self._viewer.get_playhead_position())
        except Exception:
            return None

    def _publish_local_integration_asset_state(self, audio_path: str | None = None) -> None:
        target_audio_path = audio_path or self._audio_path
        if not target_audio_path:
            return
        try:
            _publish_audio_onset_asset_state_impl(
                target_audio_path,
                asset_label=os.path.basename(target_audio_path),
            )
        except Exception as exc:
            print(f"[local-integration] Failed to publish onset-editor asset state: {exc}", file=sys.stderr)

    def _publish_local_integration_playhead(self, time_sec: float | None, *, force: bool = False) -> None:
        if time_sec is None:
            return
        try:
            _publish_audio_onset_playhead_impl(time_sec, force=force)
        except Exception as exc:
            print(f"[local-integration] Failed to publish onset-editor playhead: {exc}", file=sys.stderr)

    def _publish_local_integration_selection(self, start: float, end: float) -> None:
        try:
            _publish_audio_onset_selection_impl(
                start,
                end,
                playhead_sec=self._current_viewer_playhead(),
            )
        except Exception as exc:
            print(f"[local-integration] Failed to publish onset-editor selection: {exc}", file=sys.stderr)

    def _clear_local_integration_selection(self) -> None:
        try:
            _clear_audio_onset_selection_impl(playhead_sec=self._current_viewer_playhead())
        except Exception as exc:
            print(f"[local-integration] Failed to clear onset-editor selection: {exc}", file=sys.stderr)

    # ──────────────────────────────────────────────────────────────────────
    # File browser
    # ──────────────────────────────────────────────────────────────────────

    def _browse_folder(self):
        start = self._folder_edit.text() or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self, "Select Audio Folder", start)
        if not folder:
            return
        self._folder_edit.setText(folder)
        self._populate_files(folder)

    def _on_folder_auto_toggled(self, checked: bool):
        """Toggle Input folder auto-set state."""
        self._browse_btn.setEnabled(not checked)
        self._folder_edit.setStyleSheet(
            f"QLineEdit {{ background: {_BG_INPUT}; "
            f"color: {_TEXT_MUTED if checked else _TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 3px 6px; font-size: 11px; }}"
        )

    def _on_onset_auto_toggled(self, checked: bool):
        """Toggle onset file auto-set state."""
        self._onset_browse_btn.setEnabled(not checked)
        self._onset_file_edit.setStyleSheet(
            f"QLineEdit {{ background: {_BG_INPUT}; "
            f"color: {_TEXT_MUTED if checked else _TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 4px; "
            f"padding: 3px 6px; font-size: 11px; }}"
        )
        if checked and self._audio_path:
            # Auto-set: prefer Excel from pipeline, fall back to .txt
            self._auto_detect_onset_source()

    def _browse_onset_file(self):
        """Manually browse for an onset file (Excel/CSV or Audacity .txt)."""
        start = os.path.dirname(self._audio_path) if self._audio_path else os.path.expanduser("~")
        path, selected_filter = QFileDialog.getOpenFileName(
            self, "Load Onset File", start,
            "Excel/CSV Files (*.xlsx *.xls *.csv);;Label Files (*.txt);;All Files (*)"
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        if ext in (".xlsx", ".xls", ".csv"):
            self._load_onsets_from_excel_file(path)
        else:
            # Traditional .txt label file
            self._onset_source = "txt"
            self._excel_onset_path = None
            self._label_path = path
            self._onset_file_edit.setText(os.path.basename(path))
            self._update_excel_info_display()
            self._onset_times = _load_labels(path)
            self._undo_stack.clear()
            self._undo_stack.push(list(self._onset_times))
            self._dirty = False
            self._refresh_viewer_markers()
            self._refresh_table()
            self._update_button_states()
            self._status_label.setText(
                f"Loaded {len(self._onset_times)} onsets from {os.path.basename(path)}"
            )

    # ──────────────────────────────────────────────────────────────────────
    # Excel / CSV onset loading
    # ──────────────────────────────────────────────────────────────────────

    def _auto_detect_onset_source(self):
        """Auto-detect the best onset source: pipeline Excel or .txt labels.

        Called when auto-set is checked and an audio file is loaded.
        Priority: (1) pipeline Excel path set by Onset Finder,
                  (2) auto-detected Excel in data/ subfolder,
                  (3) _labels.txt file next to audio.
        """
        audio_filename = os.path.basename(self._audio_path) if self._audio_path else ""
        audio_folder = os.path.normpath(os.path.dirname(self._audio_path)) if self._audio_path else ""

        # Try pipeline Excel first — but only if it is adjacent to the current
        # audio folder (i.e. inside it or in its data/ subfolder).  Without this
        # check, switching between folders that share the same filenames (e.g.
        # the original folder and the _muted_clean output) would keep loading
        # onset data from the previous folder's Excel because the filename lookup
        # uses only the basename.
        def _pipeline_excel_is_adjacent():
            if not self._pipeline_excel_path:
                return False
            excel_dir = os.path.normpath(os.path.dirname(self._pipeline_excel_path))
            return (excel_dir == audio_folder or
                    excel_dir == os.path.normpath(os.path.join(audio_folder, "data")))

        if self._pipeline_excel_path and os.path.isfile(self._pipeline_excel_path) and _pipeline_excel_is_adjacent():
            if _HAS_EXCEL_IO and audio_filename:
                try:
                    times = _eio.load_onsets_for_file(
                        self._pipeline_excel_path, audio_filename,
                        self._excel_filename_col, self._excel_onset_col,
                        self._excel_sheet_name)
                    if times:
                        self._excel_onset_path = self._pipeline_excel_path
                        self._onset_source = "excel"
                        self._onset_times = times
                        self._onset_file_edit.setText(
                            os.path.basename(self._pipeline_excel_path))
                        self._update_excel_info_display()
                        self._undo_stack.clear()
                        self._undo_stack.push(list(self._onset_times))
                        self._dirty = False
                        self._refresh_viewer_markers()
                        self._refresh_table()
                        self._update_button_states()
                        self._status_label.setText(
                            f"Loaded {len(times)} onsets from Excel "
                            f"({os.path.basename(self._pipeline_excel_path)})")
                        return
                except Exception:
                    pass

        # Try auto-detected Excel in audio folder
        if _HAS_EXCEL_IO and self._audio_path:
            audio_folder = os.path.dirname(self._audio_path)
            candidates = [
                os.path.join(audio_folder, "data", "AudioData_OnsetFinder.xlsx"),
                os.path.join(audio_folder, "AudioData_OnsetFinder.xlsx"),
                os.path.join(audio_folder, "Cross_Species_Rhythm_Data.xlsx"),
                os.path.join(audio_folder, "data", "Cross_Species_Rhythm_Data.xlsx"),
            ]
            for excel_path in candidates:
                if os.path.isfile(excel_path):
                    try:
                        times = _eio.load_onsets_for_file(
                            excel_path, audio_filename,
                            self._excel_filename_col, self._excel_onset_col,
                            self._excel_sheet_name)
                        if times:
                            self._excel_onset_path = excel_path
                            self._onset_source = "excel"
                            self._onset_times = times
                            self._onset_file_edit.setText(
                                os.path.basename(excel_path))
                            self._update_excel_info_display()
                            self._undo_stack.clear()
                            self._undo_stack.push(list(self._onset_times))
                            self._dirty = False
                            self._refresh_viewer_markers()
                            self._refresh_table()
                            self._update_button_states()
                            self._status_label.setText(
                                f"Loaded {len(times)} onsets from Excel "
                                f"({os.path.basename(excel_path)})")
                            return
                    except Exception:
                        continue

        # Fall back to .txt labels
        self._onset_source = "txt"
        self._excel_onset_path = None
        self._update_excel_info_display()
        self._label_path = _find_label_file(self._audio_path)
        if self._label_path and os.path.isfile(self._label_path):
            self._onset_file_edit.setText(os.path.basename(self._label_path))
            self._onset_times = _load_labels(self._label_path)
            self._undo_stack.clear()
            self._undo_stack.push(list(self._onset_times))
            self._dirty = False
            self._refresh_viewer_markers()
            self._refresh_table()
            self._update_button_states()
            self._status_label.setText(
                f"Loaded {len(self._onset_times)} onsets from "
                f"{os.path.basename(self._label_path)}")
        else:
            self._onset_file_edit.setText("")
            self._onset_times = []
            self._undo_stack.clear()
            self._undo_stack.push([])
            self._dirty = False
            self._refresh_viewer_markers()
            self._refresh_table()
            self._update_button_states()
            self._status_label.setText("No onset file found — start adding onsets")

    def _load_onsets_from_excel_file(self, path: str):
        """Load onsets from a user-selected Excel/CSV file.

        Shows a column selection dialog, then loads onsets for the current
        audio file.
        """
        if not _HAS_EXCEL_IO:
            QMessageBox.warning(
                self, "Missing Module",
                "Excel onset I/O module not available.\n"
                "Ensure scripts/excel_onset_io.py exists.")
            return

        # Show column selection dialog
        dlg = _ExcelColumnDialog(path, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        self._excel_onset_path = path
        self._excel_filename_col = dlg.filename_column()
        self._excel_onset_col = dlg.onset_column()
        self._excel_sheet_name = dlg.sheet_name()
        self._onset_source = "excel"
        self._label_path = None

        self._load_onsets_from_excel_current()

    def _load_onsets_from_excel_current(self):
        """Load onsets for the current audio file from the configured Excel."""
        if not _HAS_EXCEL_IO or not self._excel_onset_path:
            return
        if not self._audio_path:
            return

        audio_filename = os.path.basename(self._audio_path)
        try:
            times = _eio.load_onsets_for_file(
                self._excel_onset_path, audio_filename,
                self._excel_filename_col, self._excel_onset_col,
                self._excel_sheet_name)
        except Exception as exc:
            self._status_label.setText(f"Excel load error: {exc}")
            self._onset_times = []
            times = []

        self._onset_times = times
        self._onset_file_edit.setText(os.path.basename(self._excel_onset_path))
        self._update_excel_info_display()
        loaded_session = _build_loaded_onset_session_impl(self._onset_times)
        self._onset_times = loaded_session["onset_times"]
        self._undo_stack = loaded_session["undo_stack"]
        self._dirty = loaded_session["dirty"]
        self._refresh_viewer_markers()
        self._refresh_table()
        self._update_button_states()

        if times:
            self._status_label.setText(
                f"Loaded {len(times)} onsets from Excel for {audio_filename}")
        else:
            self._status_label.setText(
                f"No onsets found in Excel for {audio_filename}")

    def _update_excel_info_display(self):
        """Update the Excel info bar visibility and content."""
        if self._onset_source == "excel" and self._excel_onset_path:
            self._excel_col_edit.setText(self._excel_onset_col)
            self._excel_col_label.show()
            self._excel_col_edit.show()
            self._excel_col_btn.show()
        else:
            self._excel_col_label.hide()
            self._excel_col_edit.hide()
            self._excel_col_btn.hide()

    def _choose_excel_column(self):
        """Open column selection dialog for the current Excel file."""
        if not self._excel_onset_path or not _HAS_EXCEL_IO:
            return
        dlg = _ExcelColumnDialog(
            self._excel_onset_path,
            initial_filename_col=self._excel_filename_col,
            initial_onset_col=self._excel_onset_col,
            initial_sheet=self._excel_sheet_name,
            parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._excel_filename_col = dlg.filename_column()
        self._excel_onset_col = dlg.onset_column()
        self._excel_sheet_name = dlg.sheet_name()
        self._load_onsets_from_excel_current()

    # ──────────────────────────────────────────────────────────────────────
    # Excel / CSV onset saving
    # ──────────────────────────────────────────────────────────────────────

    def _save_to_excel_column(self):
        """Save onsets back to the Excel file's onset column (or new column).

        Shows a save dialog with overwrite protection and new-column options.
        """
        if not _HAS_EXCEL_IO:
            QMessageBox.warning(
                self, "Missing Module",
                "Excel onset I/O module not available.")
            return
        if not self._audio_path:
            QMessageBox.warning(self, "No File", "No audio file is loaded.")
            return

        excel_path = self._excel_onset_path
        if not excel_path or not os.path.isfile(excel_path):
            # Fall back to auto-detect or let user browse
            start = os.path.dirname(self._audio_path)
            excel_path, _ = QFileDialog.getSaveFileName(
                self, "Save to Excel/CSV", start,
                "Excel Files (*.xlsx);;CSV Files (*.csv)")
            if not excel_path:
                return

        audio_filename = os.path.basename(self._audio_path)

        # Show save options dialog
        dlg = _ExcelSaveDialog(
            excel_path=excel_path,
            audio_filename=audio_filename,
            onset_col=self._excel_onset_col,
            onset_times=self._onset_times,
            filename_col=self._excel_filename_col,
            sheet_name=self._excel_sheet_name,
            parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        target_col = dlg.target_column()
        output_path = dlg.output_path()

        try:
            result = _eio.save_onsets_to_excel(
                file_path=excel_path,
                audio_filename=audio_filename,
                onset_times=self._onset_times,
                filename_col=self._excel_filename_col,
                onset_col=self._excel_onset_col,
                sheet_name=self._excel_sheet_name,
                new_col_name=target_col if target_col != self._excel_onset_col else None,
                output_path=output_path if output_path != excel_path else None,
            )
            self._status_label.setText(
                f"Saved {len(self._onset_times)} onsets → "
                f"{os.path.basename(result['path'])} [{result['column']}]")
            self._dirty = False
        except Exception as exc:
            QMessageBox.critical(self, "Excel Save Error", str(exc))

    def set_pipeline_excel_path(self, path: str):
        """Set the Onset Finder's output Excel path (called by pipeline_gui)."""
        self._pipeline_excel_path = path
        # If auto-set is on, update the onset source
        if self._onset_auto_cb.isChecked() and self._audio_path:
            self._auto_detect_onset_source()

    def _open_onset_manager(self):
        """Open the Onset & Excel Manager dialog."""
        changes = self._prompt_onset_manager_changes()
        if changes is not None:
            self._apply_onset_manager_changes(changes)

    def _prompt_onset_manager_changes(self) -> dict | None:
        """Run the onset-manager dialog and return accepted changes, if any."""
        dlg = OnsetManagerDialog(
            parent=self,
            audio_path=self._audio_path,
            label_path=self._label_path,
            onset_times=self._onset_times,
            comp_files=self._comp_files,
            comp_palette=list(self._comp_palette),
            tolerance_ms=self._comp_tolerance_ms,
            filter_idx=self._comp_filter_idx,
            color_main_only=self._COLOR_MAIN_ONLY,
            color_shared=self._COLOR_SHARED,
            onset_source=self._onset_source,
            excel_onset_path=self._excel_onset_path,
            excel_onset_col=self._excel_onset_col,
            excel_filename_col=self._excel_filename_col,
            excel_sheet_name=self._excel_sheet_name,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg.get_changes()

    def _apply_onset_manager_changes(self, changes: dict):
        """Apply saved main/comparison state returned by the onset manager."""
        if changes.get("main_label_path"):
            self._label_path = changes["main_label_path"]
            self._onset_file_edit.setText(os.path.basename(self._label_path))

        if changes.get("comp_files") is not None:
            self._comp_files = changes["comp_files"]
        if "tolerance_ms" in changes:
            self._comp_tolerance_ms = changes["tolerance_ms"]
        if "filter_idx" in changes:
            self._comp_filter_idx = changes["filter_idx"]
        if "color_main_only" in changes:
            self._COLOR_MAIN_ONLY = changes["color_main_only"]
        if "color_shared" in changes:
            self._COLOR_SHARED = changes["color_shared"]
        if "comp_palette" in changes:
            self._comp_palette = changes["comp_palette"]

        self._refresh_comparison_display()

    def _populate_files(self, folder: str):
        """Scan folder for audio files and populate the combo box."""
        self._file_combo.blockSignals(True)
        self._file_combo.clear()
        if not os.path.isdir(folder):
            self._file_combo.blockSignals(False)
            return
        files = _list_audio_files(folder)
        if files:
            self._file_combo.addItems(files)
        self._file_combo.blockSignals(False)
        if files:
            self._file_combo.setCurrentIndex(0)
            self._on_file_selected(0)

    def _navigate_prev_file(self):
        """Navigate to the previous audio file in the combo box."""
        idx = self._file_combo.currentIndex()
        if idx <= 0:
            return
        self._file_combo.setCurrentIndex(idx - 1)

    def _navigate_next_file(self):
        """Navigate to the next audio file in the combo box."""
        idx = self._file_combo.currentIndex()
        if idx >= self._file_combo.count() - 1:
            return
        self._file_combo.setCurrentIndex(idx + 1)

    def _on_file_selected(self, index: int):
        """Load the selected audio file and its onset data (Excel or .txt)."""
        if index < 0:
            return
        if self._suppress_file_selection_handler:
            return

        # For true file switches, allow user to save/discard/cancel unsaved edits.
        if self._loaded_file_index >= 0 and index != self._loaded_file_index:
            self._save_layer_state()
            any_dirty = any(l["dirty"] for l in self._layers)
            if any_dirty and self._audio_path:
                reply = self._prompt_save()
                if reply == QMessageBox.StandardButton.Cancel:
                    # Revert combo selection and keep in-memory edits untouched.
                    self._suppress_file_selection_handler = True
                    self._file_combo.blockSignals(True)
                    self._file_combo.setCurrentIndex(self._loaded_file_index)
                    self._file_combo.blockSignals(False)
                    self._suppress_file_selection_handler = False
                    return

        filename = self._file_combo.currentText()
        folder = self._folder_edit.text()
        if not filename or not folder:
            return
        audio_path = os.path.join(folder, filename)
        self._audio_path = audio_path

        # Auto-set onset source if checkbox is checked
        if self._onset_auto_cb.isChecked():
            self._auto_detect_onset_source()
        else:
            # Manual mode: if using Excel, reload for new audio file
            if self._onset_source == "excel" and self._excel_onset_path:
                self._load_onsets_from_excel_current()
            else:
                # Keep existing manual label path or try to find one
                if not self._label_path or not os.path.isfile(self._label_path):
                    self._label_path = _find_label_file(audio_path)

        # Update the onset file display
        if self._onset_source == "excel" and self._excel_onset_path:
            self._onset_file_edit.setText(os.path.basename(self._excel_onset_path))
            self._update_excel_info_display()
        elif self._label_path and os.path.isfile(self._label_path):
            self._onset_file_edit.setText(os.path.basename(self._label_path))
            self._update_excel_info_display()
        else:
            self._onset_file_edit.setText("")
            self._update_excel_info_display()

        # Load audio into viewer (if ready; otherwise _init_viewer handles it)
        if self._viewer is not None:
            self._viewer.load_audio(audio_path)

        # Clear comparison files on audio change
        self._comp_files.clear()
        self._loaded_signal_profile = None

        # Load onsets (if not already loaded by _auto_detect_onset_source)
        if self._onset_source != "excel":
            if self._label_path and os.path.isfile(self._label_path):
                self._onset_times = _load_labels(self._label_path)
                self._status_label.setText(
                    f"Loaded {len(self._onset_times)} onsets from {os.path.basename(self._label_path)}"
                )
            else:
                self._onset_times = []
                self._status_label.setText("No onset file found — start adding onsets")

        self._undo_stack.clear()
        self._undo_stack.push(list(self._onset_times))
        self._dirty = False

        # Reset layers: Layer 1 gets the loaded onsets, extra layers are cleared
        # Reset layers: Layer 1 gets the loaded onsets, extra layers are cleared
        reset_result = _reset_layers_for_loaded_file_impl(
            self._onset_times,
            self._focus_regions,
            self._undo_stack,
            self._dirty,
        )
        self._layers = reset_result["layers"]
        self._active_layer_idx = reset_result["active_layer_idx"]
        self._refresh_restored_layer_widgets()
        self._checked_layer_indices = reset_result["checked_layer_indices"]
        self._refresh_layer_structure_widgets()
        self._refresh_active_layer_focus_widgets()
        self._loaded_file_index = index

    def _prompt_save(self, *, prompt_text: str | None = None) -> QMessageBox.StandardButton:
        """Ask user whether to save unsaved changes.

        Returns the button the user clicked (Save, Discard, or Cancel).
        """
        reply = QMessageBox.question(
            self, "Unsaved Changes",
            prompt_text or f"Save changes to {os.path.basename(self._audio_path or '')}?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if reply == QMessageBox.StandardButton.Save:
            self._save_labels()
        return reply

    # ──────────────────────────────────────────────────────────────────────
    # Onset manipulation
    # ──────────────────────────────────────────────────────────────────────

    def _push_undo(self):
        """Snapshot current onsets to undo stack (call after mutation)."""
        self._undo_stack.push(list(self._onset_times))
        self._dirty = True
        self._update_button_states()

    def _add_onset(self, time_sec: float):
        """Add an onset at the specified time, maintaining sorted order."""
        if time_sec < 0:
            return
        # Avoid duplicates (within 1 ms)
        for t in self._onset_times:
            if abs(t - time_sec) < 0.001:
                return
        self._onset_times.append(time_sec)
        self._onset_times.sort()
        self._push_undo()
        self._refresh_viewer_markers()
        self._refresh_table()
        self._status_label.setText(f"Added onset at {time_sec:.4f}s")

    def _remove_onset(self, index: int):
        """Remove onset at given index."""
        if 0 <= index < len(self._onset_times):
            t = self._onset_times[index]
            self._onset_times.pop(index)
            self._push_undo()
            self._refresh_viewer_markers()
            self._refresh_table()
            self._status_label.setText(f"Removed onset at {t:.4f}s")

    def _move_onset(self, index: int, new_time: float):
        """Move onset at given index to a new time."""
        if 0 <= index < len(self._onset_times) and new_time >= 0:
            self._onset_times[index] = new_time
            self._onset_times.sort()
            self._push_undo()
            self._refresh_viewer_markers()
            self._refresh_table()
            self._status_label.setText(f"Moved onset to {new_time:.4f}s")

    # ──────────────────────────────────────────────────────────────────────
    # Viewer ↔ table sync
    # ──────────────────────────────────────────────────────────────────────

    def _refresh_viewer_markers(self):
        """Update the viewer's onset markers from the current onset list."""
        # Cancel any pending refresh and do it now
        self._viewer_refresh_timer.stop()
        self._refresh_viewer_markers_now()
        # Start a timer in case more changes come quickly
        self._viewer_refresh_timer.start(50)

    def _refresh_viewer_markers_now(self):
        """Actually perform the viewer marker refresh."""
        if self._viewer is None:
            return
        # If comparison files are loaded, delegate to comparison display
        if self._comp_files:
            self._refresh_comparison_display()
            return
        self._updating_viewer = True
        self._viewer.clear_onset_markers()
        self._clear_comparison_markers()
        if self._onset_times:
            self._viewer.set_onset_markers(self._onset_times, draggable=self._edit_onsets_btn.isChecked())
        # Overlay checked layers beyond the primary
        if hasattr(self, '_layer_menu'):
            self._refresh_layer_overlays()
        self._updating_viewer = False

    def _refresh_table(self):
        """Rebuild the table from the current onset list."""
        # Cancel any pending refresh and do it now
        self._table_refresh_timer.stop()
        self._refresh_table_now()
        # Start a timer in case more changes come quickly
        self._table_refresh_timer.start(50)

    def _refresh_table_now(self):
        """Actually rebuild the table from the current onset list."""
        self._updating_table = True
        iois = _compute_ioi(self._onset_times)
        rks = _compute_rk(self._onset_times)
        stables = _compute_stable(self._onset_times)

        self._table.setRowCount(len(self._onset_times))
        for row, t in enumerate(self._onset_times):
            # Index (read-only)
            idx_item = QTableWidgetItem(str(row + 1))
            idx_item.setFlags(idx_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, self._COL_IDX, idx_item)

            # Time (editable)
            time_item = QTableWidgetItem(f"{t:.6f}")
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, self._COL_TIME, time_item)

            # IOI (read-only)
            ioi_val = iois[row]
            ioi_text = f"{ioi_val:.2f}" if ioi_val is not None else "—"
            ioi_item = QTableWidgetItem(ioi_text)
            ioi_item.setFlags(ioi_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            ioi_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, self._COL_IOI, ioi_item)

            # r_k (read-only)
            rk_val = rks[row]
            rk_text = f"{rk_val:.4f}" if rk_val is not None else "—"
            rk_item = QTableWidgetItem(rk_text)
            rk_item.setFlags(rk_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            rk_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, self._COL_RK, rk_item)

            # Stable (read-only)
            stable_val = stables[row]
            if stable_val is None:
                stable_text = "—"
            else:
                stable_text = "✓" if stable_val else "✗"
            stable_item = QTableWidgetItem(stable_text)
            stable_item.setFlags(stable_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            stable_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if stable_val is True:
                stable_item.setBackground(_STABLE_BG)
            self._table.setItem(row, self._COL_STABLE, stable_item)

        self._updating_table = False
        self._update_status_summary()

    def _update_status_summary(self):
        """Update the status label with summary statistics."""
        n = len(self._onset_times)
        if n == 0:
            self._status_label.setText("No onsets")
            return
        stables = _compute_stable(self._onset_times)
        n_stable = sum(1 for s in stables if s is True)
        dirty_mark = " (unsaved)" if self._dirty else ""
        self._status_label.setText(
            f"{n} onsets | {n_stable} stable dyads{dirty_mark}"
        )

    # ──────────────────────────────────────────────────────────────────────
    # Viewer signal handlers
    # ──────────────────────────────────────────────────────────────────────

    def _on_edit_onsets_toggled(self, checked: bool):
        """Enable or disable onset marker editing (dragging)."""
        if self._viewer is not None:
            self._viewer.set_onset_draggable(checked)
        self._update_button_states()

    # ── Focus Onsets mode handlers ──

    def _on_focus_onsets_toggled(self, checked: bool):
        """Enable or disable Focus Onsets mode."""
        self._focus_mode = checked
        self._pos_neg_widget.setVisible(checked)
        if self._viewer is not None:
            self._viewer.set_focus_mode(checked, self._focus_polarity)
            if checked:
                # Show existing focus regions for this file
                self._refresh_focus_regions_in_viewer()
            else:
                self._clear_selection_state()
                self._viewer.clear_focus_regions()
        self._update_button_states()

    def _on_positive_toggled(self, checked: bool):
        """Toggle positive polarity (radio-style with negative)."""
        if checked:
            self._negative_btn.setChecked(False)
            self._focus_polarity = "positive"
            if self._viewer is not None:
                self._viewer.set_focus_polarity("positive")
        elif not self._negative_btn.isChecked():
            # Don't allow both to be unchecked — re-check this one
            self._positive_btn.setChecked(True)

    def _on_negative_toggled(self, checked: bool):
        """Toggle negative polarity (radio-style with positive)."""
        if checked:
            self._positive_btn.setChecked(False)
            self._focus_polarity = "negative"
            if self._viewer is not None:
                self._viewer.set_focus_polarity("negative")
        elif not self._positive_btn.isChecked():
            self._negative_btn.setChecked(True)

    def _on_viewer_focus_region_added(self, region: dict):
        """Viewer reports a new focus region was drawn."""
        fname = os.path.basename(self._audio_path) if self._audio_path else ""
        if fname not in self._focus_regions:
            self._focus_regions[fname] = []
        self._focus_regions[fname].append(region)
        status = _summarize_focus_region_status_impl(self._focus_regions[fname])
        self._apply_focus_region_status_widgets(status["status_text"])

    def _on_viewer_focus_region_removed(self, index: int):
        """Viewer reports a focus region was deleted."""
        fname = os.path.basename(self._audio_path) if self._audio_path else ""
        regions = self._focus_regions.get(fname, [])
        if 0 <= index < len(regions):
            regions.pop(index)
        status = _summarize_focus_region_status_impl(regions)
        self._apply_focus_region_status_widgets(status["status_text"])

    def _on_viewer_focus_region_modified(self, index: int, region: dict):
        """Viewer reports a focus region was moved/resized."""
        fname = os.path.basename(self._audio_path) if self._audio_path else ""
        regions = self._focus_regions.get(fname, [])
        if 0 <= index < len(regions):
            regions[index] = region

    def _on_quick_export_region(self, index: int):
        """Export a single focus region as a WAV file (right-click menu)."""
        if not self._audio_path or self._viewer is None:
            return
        fname = os.path.basename(self._audio_path)
        regions = self._focus_regions.get(fname, [])
        if index < 0 or index >= len(regions):
            return

        region = regions[index]
        y = self._viewer.audioData
        sr = self._viewer.sampleRate
        if y is None:
            return

        seg = self._extract_region_audio(y, sr, region, bandpass=False)
        if seg is None or len(seg) == 0:
            return

        stem = os.path.splitext(fname)[0]
        polarity = region.get("polarity", "positive").capitalize()
        out_dir = os.path.dirname(self._audio_path)
        n = self._next_export_number(out_dir, stem, polarity)
        out_name = f"{stem}_{polarity}{n}.wav"
        out_path = os.path.join(out_dir, out_name)

        try:
            _write_audio_file(out_path, seg, sr)
            self._status_label.setText(f"Exported: {out_name}")
        except ImportError:
            QMessageBox.critical(
                self, "Missing Library",
                "soundfile is required. Install it with: pip install soundfile")
        except Exception as exc:
            QMessageBox.critical(
                self, "Export Error",
                f"Failed to export region:\n{exc}")

    # ──────────────────────────────────────────────────────────────────────
    # Move / Copy focus regions between layers
    # ──────────────────────────────────────────────────────────────────────

    def _push_layer_info_to_viewer(self):
        """Send current layer names and active index to the viewer."""
        if self._viewer is None:
            return
        names = [layer["name"] for layer in self._layers]
        self._viewer.set_layer_info(names, self._active_layer_idx)

    def _on_viewer_focus_region_move(self, region_idx: int, target_layer_idx: int):
        """Move a focus region from the active layer to another layer."""
        self._transfer_focus_region(region_idx, target_layer_idx, remove_from_source=True)

    def _on_viewer_focus_region_copy(self, region_idx: int, target_layer_idx: int):
        """Copy a focus region from the active layer to another layer."""
        self._transfer_focus_region(region_idx, target_layer_idx, remove_from_source=False)

    def _transfer_focus_region(self, region_idx: int, target_layer_idx: int,
                               remove_from_source: bool):
        """Move or copy a focus region to the target layer.

        Parameters
        ----------
        region_idx : int
            Index of the focus region inside the current file's list.
        target_layer_idx : int
            Index into ``self._layers``. ``-1`` means create a new layer.
        remove_from_source : bool
            If True the region is removed from the active layer (move);
            if False it is kept (copy).
        """
        if target_layer_idx == -1:
            self._save_layer_state()
        result = _transfer_focus_region_impl(
            self._layers,
            self._active_layer_idx,
            self._focus_regions,
            self._audio_path,
            region_idx,
            target_layer_idx,
            remove_from_source,
        )
        if result is None:
            return

        if result["created_layer"]:
            self._append_layer_names_to_combo(
                [self._layers[result["target_layer_idx"]]["name"]],
                block_signals=True,
            )
            self._load_layer_state()  # reload current (we didn't switch)
            self._push_layer_info_to_viewer()

        if result["removed_from_source"]:
            self._refresh_focus_regions_in_viewer()

        action = "Moved" if result["removed_from_source"] else "Copied"
        self._apply_focus_region_status_widgets(
            f"{action} {result['polarity']} region to {result['target_name']}"
        )

    # ──────────────────────────────────────────────────────────────────────
    # Onset Layer switching
    # ──────────────────────────────────────────────────────────────────────

    def _on_layer_combo_changed(self, index: int):
        """User selected a different layer from the combo box."""
        self._activate_exclusive_layer(index, update_buttons=True)

    # ── Checkbox layer menu handlers ──

    def _rebuild_layer_menu(self):
        """Rebuild the checkbox popup from current _layers list."""
        self._save_layer_state()
        self._layer_menu.rebuild(self._layers, self._checked_layer_indices)
        checked = self._get_checked_layer_indices()
        self._layer_combo_btn.setText(
            _format_checked_layer_label_impl(self._layers, checked)
        )

    def _on_layer_selection_changed(self):
        """Respond to checkbox changes in the layer popup menu."""
        selection = _summarize_layer_selection_change_impl(
            self._get_checked_layer_indices()
        )
        self._checked_layer_indices = selection["checked_layer_indices"]

        # If a re-sort was triggered, rebuild the menu with new order
        # (the signal fires for sort changes too)
        self._rebuild_layer_menu()
        self._apply_checked_layer_selection(selection)

    def _refresh_layer_overlays(self):
        """Draw comparison markers for all checked layers beyond the primary."""
        if self._viewer is None:
            return

        self._save_layer_state()  # ensure _layers is up to date
        checked = self._get_checked_layer_indices()
        overlay_layers = _build_layer_overlay_markers_impl(
            self._layers,
            checked,
            list(_LAYER_OVERLAY_COLORS),
            _SHARED_ONSET_COLOR,
            unique_style=Qt.PenStyle.SolidLine,
            shared_style=Qt.PenStyle.DashLine,
        )
        if not overlay_layers:
            self._clear_comparison_markers()
            return

        self._viewer.set_comparison_markers(overlay_layers)

    def _merge_selected_layers(self):
        """Merge only the currently checked layers into a single new layer."""
        checked = self._get_checked_layer_indices()
        if len(checked) < 2:
            QMessageBox.information(
                self, "Select Layers",
                "Check at least 2 layers in the Layers dropdown to merge.")
            return

        self._save_layer_state()

        # Show confirmation
        info_lines = []
        for idx in checked:
            layer = self._layers[idx]
            n = len(layer.get("onset_times", []))
            info_lines.append(f"  {layer['name']}: {n} onset(s)")
        info_text = "\n".join(info_lines)

        reply = QMessageBox.question(
            self, "Merge Selected Layers",
            f"Merge {len(checked)} checked layer(s) into one?\n\n"
            f"{info_text}\n\n"
            f"Creates a new 'Merged' layer (duplicates within 1 ms removed).\n"
            f"Original layers are preserved.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if reply != QMessageBox.StandardButton.Yes:
            return

        new_idx, deduped = _append_merged_layer_impl(
            self._layers,
            checked,
            layer_name="Merged (selected)",
        )

        # Update hidden combo (for backward compat)
        self._append_layer_names_to_combo([self._layers[new_idx]["name"]], block_signals=True)

        # Switch to merged layer and check only it
        if not self._activate_exclusive_layer(new_idx):
            return

        self._status_label.setText(
            f"Merged {len(checked)} layers → {len(deduped)} unique onset(s)")

    def _on_layer_name_changed(self, text: str):
        """User edited the layer name text box (legacy — kept for compatibility)."""
        idx = self._active_layer_idx
        if idx < 0 or idx >= len(self._layers):
            return
        self._layers[idx]["name"] = text or f"Layer {idx + 1}"
        # Update combo item text to reflect the name
        if hasattr(self, '_layer_combo'):
            self._layer_combo.blockSignals(True)
            self._layer_combo.setItemText(idx, self._layers[idx]["name"])
            self._layer_combo.blockSignals(False)
        self._push_layer_info_to_viewer()

    # ──────────────────────────────────────────────────────────────────────
    # Signal Browser dropdown
    # ──────────────────────────────────────────────────────────────────────

    def _refresh_signal_browser_combo(self):
        """Clear and repopulate the signal browser dropdown with current focus regions."""
        combo = self._signal_browser_combo
        combo.blockSignals(True)
        combo.clear()

        fname = os.path.basename(self._audio_path) if self._audio_path else ""
        regions = self._focus_regions.get(fname, [])

        if not regions:
            combo.addItem("(no signals defined)")
            combo.model().item(0).setEnabled(False)
            combo.blockSignals(False)
            return

        pos_count = 0
        neg_count = 0
        for i, region in enumerate(regions):
            polarity = region.get("polarity", "positive")
            if polarity == "positive":
                pos_count += 1
                label = f"+ Positive {pos_count}"
                color = QColor(_FOCUS_BLUE_BRIGHT)
            else:
                neg_count += 1
                label = f"- Negative {neg_count}"
                color = QColor(_NEGATIVE_RED_BORDER)
            combo.addItem(label)
            combo.setItemData(combo.count() - 1, i, Qt.ItemDataRole.UserRole)
            combo.setItemData(combo.count() - 1, color, Qt.ItemDataRole.ForegroundRole)

        combo.blockSignals(False)

    def _on_signal_browser_selected(self, combo_idx: int):
        """User selected a focus region from the signal browser dropdown."""
        if combo_idx < 0:
            return
        region_index = self._signal_browser_combo.itemData(
            combo_idx, Qt.ItemDataRole.UserRole
        )
        if region_index is None:
            return

        fname = os.path.basename(self._audio_path) if self._audio_path else ""
        regions = self._focus_regions.get(fname, [])
        if region_index < 0 or region_index >= len(regions):
            return

        # Select and highlight in viewer
        if self._viewer is not None:
            self._viewer._select_focus_region(region_index)
            region = regions[region_index]
            mid = (region["t_start"] + region["t_end"]) / 2.0
            span = region["t_end"] - region["t_start"]
            margin = max(span * 0.5, 0.2)
            self._viewer.scroll_to_time(mid, margin=margin)

    # ──────────────────────────────────────────────────────────────────────
    # Save Selections (export positive/negative regions as WAV files)
    # ──────────────────────────────────────────────────────────────────────

    def _open_save_selections_dialog(self):
        """Show the Save Selections dialog and run the export."""
        preflight = _summarize_save_selections_preflight_impl(
            audio_path=self._audio_path,
            viewer_available=self._viewer is not None,
            focus_regions=self._focus_regions,
        )
        if not preflight["can_open"]:
            if preflight["info_title"]:
                QMessageBox.information(
                    self,
                    preflight["info_title"],
                    preflight["info_message"],
                )
            return

        request = self._prompt_save_selections_request(preflight["regions"])
        if request is None:
            return

        self._apply_save_selections_request(request)

    def _apply_save_selections_request(self, request: dict) -> None:
        """Apply an accepted save-selections request and run the export."""
        plan = _build_save_selections_export_plan_impl(
            request,
            layers=self._layers,
            active_layer_idx=self._active_layer_idx,
        )

        try:
            total_files = self._export_selections(
                plan["positive_output_dir"],
                plan["layers_to_export"],
                plan["individual_mode"],
                plan["bandpass_enabled"],
                negative_out_dir=plan["negative_output_dir"],
            )
            self._status_label.setText(
                f"Exported {total_files} WAV file(s) to positive/negative signal folders")
        except Exception as exc:
            QMessageBox.critical(
                self, "Export Error",
                f"Failed to export selections:\n{exc}")

    def _prompt_save_selections_request(self, regions: list[dict]) -> dict | None:
        """Run the save-selections dialog and return the accepted export request, if any."""
        self._save_layer_state()
        dlg = _SaveSelectionsDialog(
            self._audio_path, regions,
            layers=self._layers,
            active_layer_idx=self._active_layer_idx,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None

        return {
            "positive_output_dir": dlg.positive_output_dir(),
            "negative_output_dir": dlg.negative_output_dir(),
            "individual_mode": dlg.individual_mode(),
            "bandpass_enabled": dlg.bandpass_enabled(),
            "export_all_layers": dlg.export_all_layers(),
        }

    def _open_load_selections_dialog(self):
        """Load saved positive/negative signal examples and optional geometry metadata."""
        if not self._audio_path or self._viewer is None:
            return

        result = self._prompt_load_selections_result()
        if result is None:
            return

        self._apply_loaded_selections_result(result)

    def _prompt_load_selections_result(self) -> dict | None:
        """Run the load-selections dialog and return the loaded result, if any."""
        dlg = _LoadSelectionsDialog(self._audio_path, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        request = _build_load_selections_request_impl(
            dlg.positive_input_dir(),
            dlg.negative_input_dir(),
        )

        try:
            return self._load_saved_selections(
                request["positive_input_dir"],
                request["negative_input_dir"],
            )
        except Exception as exc:
            error = _summarize_load_selections_error_impl(exc)
            QMessageBox.critical(
                self,
                error["title"],
                error["message"],
            )
            return

    def _apply_loaded_selections_result(self, result: dict) -> None:
        """Apply loaded selection geometry/profile results to panel state and feedback."""
        feedback = _summarize_loaded_selections_feedback_impl(result)
        self._loaded_signal_profile = feedback["loaded_profile"]
        self._apply_loaded_selections_feedback(feedback)

    def _apply_loaded_selections_feedback(
        self,
        feedback: dict,
    ) -> None:
        """Apply saved-selection restore feedback to panel state and messaging."""

        if feedback["geometry_restored"]:
            self._restore_loaded_focus_regions(feedback["restored_regions"])

        if feedback["info_title"]:
            QMessageBox.information(
                self,
                feedback["info_title"],
                feedback["info_message"],
            )

        if feedback["status_text"]:
            self._status_label.setText(feedback["status_text"])

    def _export_selections(self, out_dir: str,
                           layers_to_export: list[tuple[int, dict]],
                           individual: bool, bandpass: bool,
                           negative_out_dir: str | None = None) -> int:
        """Export focus regions as WAV files via the shared onset-editor I/O helper."""
        return _export_selections_audio_impl(
            self._audio_path,
            self._viewer.audioData,
            self._viewer.sampleRate,
            out_dir,
            layers_to_export,
            individual,
            bandpass,
            negative_out_dir,
        )

    def _load_saved_selections(self, positive_dir: str, negative_dir: str) -> dict:
        """Load saved selection metadata and/or audio examples from disk."""
        return _load_saved_selections_impl(
            self._audio_path,
            positive_dir,
            negative_dir,
            self._build_signal_profile_from_saved_dirs,
        )

    def _restore_loaded_focus_regions(self, restored_regions: list[dict]):
        """Restore loaded focus regions into matching layers for the current file."""
        restore_result = _restore_loaded_focus_regions_impl(
            self._layers,
            self._active_layer_idx,
            self._audio_path,
            restored_regions,
        )
        self._apply_restored_focus_regions_result(restore_result)

    def _apply_restored_focus_regions_result(self, restore_result: dict):
        """Apply restored focus-region layer state and refresh dependent widgets."""
        self._append_layer_names_to_combo(restore_result["created_layer_names"])

        self._focus_regions = restore_result["focus_regions"]
        self._refresh_active_layer_focus_widgets()

    def _build_signal_profile_from_saved_dirs(self, positive_dir: str, negative_dir: str,
                                              pos_manifest: dict | None,
                                              neg_manifest: dict | None) -> dict | None:
        """Build a signal-profile fallback from saved WAV clips when geometry metadata is absent."""
        return _build_signal_profile_from_saved_dirs_impl(
            self._audio_path,
            positive_dir,
            negative_dir,
            pos_manifest,
            neg_manifest,
        )

    @staticmethod
    def _next_export_number(out_dir: str, stem: str, polarity: str,
                            layer_suffix: str = "") -> int:
        """Compatibility wrapper around the shared selection-export numbering helper."""
        return _next_export_number_impl(out_dir, stem, polarity, layer_suffix)

    @staticmethod
    def _extract_region_audio(y: np.ndarray, sr: int, region: dict,
                              bandpass: bool) -> np.ndarray | None:
        """Compatibility wrapper around the shared selection-export audio helper."""
        return _extract_region_audio_impl(y, sr, region, bandpass)

    def _refresh_focus_regions_in_viewer(self):
        """Push current file's focus regions to the viewer for display."""
        if self._viewer is None:
            return
        self._clear_selection_state()
        fname = os.path.basename(self._audio_path) if self._audio_path else ""
        regions = self._focus_regions.get(fname, [])
        self._viewer.set_focus_regions(regions)
        if regions:
            status = _summarize_focus_region_status_impl(regions)
            self._status_label.setText(status["status_text"])

    def _on_viewer_onset_added(self, time_sec: float):
        """Viewer reports a new onset was added (e.g., via keybind)."""
        if self._updating_viewer:
            return
        self._add_onset(time_sec)

    def _on_viewer_onset_removed(self, index: int):
        """Viewer reports an onset was removed."""
        if self._updating_viewer:
            return
        self._remove_onset(index)

    def _on_viewer_onset_moved(self, index: int, new_time: float):
        """Viewer reports an onset marker was dragged to a new position."""
        if self._updating_viewer:
            return
        self._move_onset(index, new_time)

    def _on_viewer_ctrl_click(self, time_sec: float):
        """Ctrl+click on viewer adds an onset at that time."""
        if not self._edit_onsets_btn.isChecked():
            return
        self._add_onset(time_sec)

    def _on_viewer_view_clicked(self, time_sec: float):
        """Publish manual seek updates that do not ride playback callbacks."""
        self._publish_local_integration_playhead(time_sec, force=True)

    def _on_viewer_audio_loaded(self, audio_path: str):
        """Publish the active asset after the viewer finishes loading it."""
        self._publish_local_integration_asset_state(audio_path)

    def _on_viewer_playback_position_changed(self, time_sec: float):
        """Publish playback-driven transport updates to the shared session."""
        self._publish_local_integration_playhead(time_sec)

    def _on_viewer_onset_clicked(self, index: int, time_sec: float):
        """When an onset marker is clicked in the viewer, select the
        corresponding row in the table."""
        if 0 <= index < self._table.rowCount():
            self._table.setCurrentCell(index, self._COL_TIME)

    def _on_viewer_region_selected(self, start: float, end: float):
        """A region was selected in the viewer — store it for potential
        onset detection."""
        self._selected_region = (start, end)
        self._publish_local_integration_selection(start, end)
        if self._viewer is not None and self._loop_sel_btn.isChecked():
            self._viewer.set_loop_region(start, end)
        self._detect_region_btn.setEnabled(self._audio_path is not None)
        self._edit_audio_btn.setEnabled(self._audio_path is not None)
        self._mfcc_audio_btn.setEnabled(self._audio_path is not None)
        self._play_sel_btn.setEnabled(True)
        self._loop_sel_btn.setEnabled(True)
        self._status_label.setText(
            f"Region selected: {start:.3f}s – {end:.3f}s  "
            f"({end - start:.3f}s)"
        )

    def _play_selection(self):
        """Play the selected region once from start to end."""
        if self._viewer is None or self._selected_region is None:
            return
        start, end = self._selected_region
        self._viewer.stop()
        selected_focus = self._viewer.get_selected_focus_region()
        if selected_focus is not None:
            self._viewer.play_focus_region(selected_focus, loop=self._loop_sel_btn.isChecked())
            return
        if self._loop_sel_btn.isChecked():
            # Loop mode: use loop region + normal play
            self._viewer.set_loop_region(start, end)
            self._viewer.seek(start)
            self._viewer.play()
        else:
            # Single play: use play_region (no looping)
            self._viewer.play_region(start, end)

    def _toggle_loop_selection(self, checked: bool):
        """Toggle continuous looping of the selected region."""
        if self._viewer is None:
            return
        if checked and self._selected_region is not None:
            start, end = self._selected_region
            self._viewer.set_loop_region(start, end)
            selected_focus = self._viewer.get_selected_focus_region()
            if selected_focus is not None:
                self._viewer.stop()
                self._viewer.play_focus_region(selected_focus, loop=True)
            elif not self._viewer._playing:
                self._viewer.seek(start)
                self._viewer.play()
            self._status_label.setText(
                f"Looping region: {start:.3f}s – {end:.3f}s"
            )
        else:
            self._viewer.clear_loop()
            if self._viewer.get_selected_focus_region() is not None and self._viewer._playing:
                self._viewer.stop()
            self._loop_sel_btn.setChecked(False)
            if self._selected_region:
                start, end = self._selected_region
                self._status_label.setText(
                    f"Region selected: {start:.3f}s – {end:.3f}s  "
                    f"({end - start:.3f}s)"
                )

    def _clear_selection_state(self):
        """Clear region selection state and disable selection-related buttons."""
        if self._viewer is not None:
            self._viewer.clear_selection_region()
            self._viewer.clear_focus_region_selection(emit_signal=False)
            self._viewer.clear_loop()
        self._clear_local_integration_selection()
        self._selected_region = None
        has_audio = self._audio_path is not None
        self._detect_region_btn.setEnabled(has_audio)
        self._edit_audio_btn.setEnabled(has_audio)
        self._mfcc_audio_btn.setEnabled(has_audio)
        self._play_sel_btn.setEnabled(False)
        self._loop_sel_btn.setChecked(False)
        self._loop_sel_btn.setEnabled(False)

    # ──────────────────────────────────────────────────────────────────────
    # Table signal handlers
    # ──────────────────────────────────────────────────────────────────────

    def _on_table_selection_changed(self, row: int, col: int, prev_row: int, prev_col: int):
        """When a row is selected in the table, highlight the corresponding onset in the viewer."""
        self._focus_table_onset(row)

    def _on_table_cell_clicked(self, row: int, col: int):
        """Re-focus the clicked onset even when the current row does not change."""
        self._focus_table_onset(row)

    def _focus_table_onset(self, row: int):
        """Highlight and center the onset corresponding to the selected table row."""
        if row < 0 or row >= len(self._onset_times):
            return
        if self._viewer is not None:
            if hasattr(self._viewer, "select_onset"):
                self._viewer.select_onset(row, center=True)
            else:
                t = self._onset_times[row]
                self._viewer.scroll_to_time(t)

    def _select_prev_onset(self):
        """Select the previous onset (Up arrow)."""
        if len(self._onset_times) == 0:
            return
        row = self._table.currentRow()
        new_row = max(row - 1, 0) if row >= 0 else 0
        self._table.setCurrentCell(new_row, self._COL_TIME)

    def _select_next_onset(self):
        """Select the next onset (Down arrow)."""
        if len(self._onset_times) == 0:
            return
        row = self._table.currentRow()
        last = len(self._onset_times) - 1
        new_row = min(row + 1, last) if row >= 0 else 0
        self._table.setCurrentCell(new_row, self._COL_TIME)

    def _on_table_cell_edited(self, row: int, col: int):
        """Handle user editing the Time column in the table."""
        if self._updating_table:
            return
        if col != self._COL_TIME:
            return
        item = self._table.item(row, col)
        if item is None:
            return
        try:
            new_time = float(item.text())
        except ValueError:
            # Revert to original value
            self._updating_table = True
            item.setText(f"{self._onset_times[row]:.6f}")
            self._updating_table = False
            return
        if new_time < 0:
            self._updating_table = True
            item.setText(f"{self._onset_times[row]:.6f}")
            self._updating_table = False
            return
        # Apply the edit
        self._move_onset(row, new_time)

    # ──────────────────────────────────────────────────────────────────────
    # Toolbar actions
    # ──────────────────────────────────────────────────────────────────────

    def _add_onset_at_playhead(self):
        """Add an onset at the current playhead position."""
        if self._viewer is not None:
            pos = self._viewer.get_playhead_position()
        else:
            pos = 0.0
        self._add_onset(pos)

    def _remove_selected_onset(self):
        """Remove the currently selected onset, or all onsets inside the
        active selection region if no specific onset is selected."""
        if not self._edit_onsets_btn.isChecked():
            return

        # Prefer deleting the individually selected onset (table row)
        row = self._table.currentRow()
        if 0 <= row < len(self._onset_times):
            self._remove_onset(row)
            return

        # Fall back: if a region is selected, remove all onsets within it
        if self._selected_region is not None:
            start, end = self._selected_region
            remaining_onsets, count = _remove_onsets_in_range_impl(
                self._onset_times,
                start,
                end,
            )
            if count:
                self._onset_times = remaining_onsets
                self._push_undo()
                self._refresh_viewer_markers()
                self._refresh_table()
                self._status_label.setText(
                    f"Removed {count} onset(s) in selection "
                    f"({start:.3f}s \u2013 {end:.3f}s)")
                return

    def _delete_current_selection(self):
        """Delete the selected focus ROI or, if none, the selected onset."""
        if self._viewer is not None and self._viewer.remove_selected_focus_region():
            if self._audio_path:
                fname = os.path.basename(self._audio_path)
                regions = self._focus_regions.get(fname, [])
                n_pos = sum(1 for r in regions if r["polarity"] == "positive")
                n_neg = sum(1 for r in regions if r["polarity"] == "negative")
                self._status_label.setText(
                    f"Focus region deleted. Remaining: {n_pos} positive, {n_neg} negative"
                )
            self._update_button_states()
            return
        self._remove_selected_onset()

    # ------------------------------------------------------------------
    # Settings dialog
    # ------------------------------------------------------------------

    def _open_settings_dialog(self):
        dlg = _OnsetEditorSettingsDialog(
            self._onset_hitbox_px, self._hotkey_map, parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._onset_hitbox_px = dlg.hitbox_px()
            if self._viewer is not None:
                self._viewer._onset_hitbox_px = self._onset_hitbox_px

            # Apply new hotkeys
            new_map = dlg.hotkey_map()
            # Merge viewer keys back (they aren't in the edit widgets)
            for aid, key, _d, cat in _HOTKEY_DEFS:
                if cat == "viewer":
                    new_map[aid] = key
            self._hotkey_map = new_map
            self._apply_hotkeys()

            # Persist overrides (only store diffs from defaults)
            defaults = {aid: k for aid, k, _d, _c in _HOTKEY_DEFS}
            overrides = {
                aid: new_map[aid]
                for aid in new_map
                if new_map[aid] != defaults.get(aid, "")
            }
            _save_hotkey_overrides(overrides)

    # ------------------------------------------------------------------
    # 3-way fullscreen toggle
    # ------------------------------------------------------------------

    def _on_maximize_state_changed(self, state: int):
        """Handle the 3-state maximize cycle from the viewer button.

        0 = Default (all sections visible)
        1 = Fullscreen (collapse outer pipeline panels only)
        2 = Fullscreen-2 (also collapse top controls + onset table)
        """
        if state == 0:
            # Restore everything
            self._top_controls.setVisible(True)
            if hasattr(self, '_saved_inner_sizes') and self._saved_inner_sizes:
                self._splitter.setSizes(self._saved_inner_sizes)
            if hasattr(self, '_saved_outer_sizes') and self._saved_outer_sizes:
                self._outer_splitter.setSizes(self._saved_outer_sizes)
        elif state == 1:
            # Save sizes for later restore, but keep inner panels visible
            self._saved_outer_sizes = self._outer_splitter.sizes()
            self._saved_inner_sizes = self._splitter.sizes()
            self._top_controls.setVisible(True)
            self._splitter.widget(1).setVisible(True)
        elif state == 2:
            # Collapse top controls and onset table
            self._top_controls.setVisible(False)
            total_inner = sum(self._splitter.sizes())
            self._splitter.setSizes([total_inner, 0])

        # Forward to pipeline GUI for outer panel collapse/restore
        self.maximizeRequested.emit(state)

    def _undo(self):
        state = self._undo_stack.undo()
        if state is not None:
            self._onset_times = state
            self._dirty = True
            self._save_layer_state()
            self._refresh_viewer_markers()
            self._refresh_table()
            self._update_button_states()
            self._status_label.setText("Undo")

    def _redo(self):
        state = self._undo_stack.redo()
        if state is not None:
            self._onset_times = state
            self._dirty = True
            self._save_layer_state()
            self._refresh_viewer_markers()
            self._refresh_table()
            self._update_button_states()
            self._status_label.setText("Redo")

    def _update_button_states(self):
        can_edit = self._edit_onsets_btn.isChecked()
        self._undo_btn.setEnabled(self._undo_stack.can_undo())
        self._redo_btn.setEnabled(self._undo_stack.can_redo())
        self._manage_btn.setEnabled(self._audio_path is not None)
        has_audio = self._audio_path is not None
        has_selection = self._table.currentRow() >= 0
        self._remove_btn.setEnabled(can_edit and has_selection and len(self._onset_times) > 0)
        self._add_btn.setEnabled(can_edit)
        self._detect_region_btn.setEnabled(has_audio)
        self._detect_all_layers_btn.setEnabled(
            has_audio and len(self._layers) > 1
        )
        self._edit_audio_btn.setEnabled(has_audio)
        self._mfcc_audio_btn.setEnabled(has_audio)
        # Per-signal detection buttons
        if hasattr(self, '_analyze_signals_btn'):
            has_any_focus = False
            if has_audio and self._audio_path:
                fname = os.path.basename(self._audio_path)
                rgns = self._focus_regions.get(fname, [])
                has_any_focus = len(rgns) > 0
            self._analyze_signals_btn.setEnabled(has_audio and has_any_focus)
        if hasattr(self, '_per_signal_btn'):
            has_pos = False
            if has_audio and self._audio_path:
                fname = os.path.basename(self._audio_path)
                rgns = self._focus_regions.get(fname, [])
                has_pos = any(r.get("polarity") == "positive" for r in rgns)
            self._per_signal_btn.setEnabled(has_audio and has_pos)
        if hasattr(self, '_neg_subtract_btn'):
            has_neg = False
            if has_audio and self._audio_path:
                fname = os.path.basename(self._audio_path)
                rgns = self._focus_regions.get(fname, [])
                has_neg = any(r.get("polarity") == "negative" for r in rgns)
            self._neg_subtract_btn.setEnabled(
                has_audio and has_neg and len(self._onset_times) > 0)
        if hasattr(self, '_merge_layers_btn'):
            self._merge_layers_btn.setEnabled(
                has_audio and len(self._layers) > 1)
        # Layer remove button: disabled when only 1 layer
        if hasattr(self, '_remove_layer_btn'):
            self._remove_layer_btn.setEnabled(len(self._layers) > 1)
        # Merge Sel. button: enabled when 2+ layers checked
        checked = self._get_checked_layer_indices()
        self._set_merge_selection_enabled(len(checked) >= 2)
        # Save Selections: enabled when focus mode is on and regions exist
        if hasattr(self, '_save_selections_btn'):
            has_regions = False
            if self._focus_mode and self._audio_path:
                fname = os.path.basename(self._audio_path)
                has_regions = bool(self._focus_regions.get(fname, []))
            self._save_selections_btn.setEnabled(has_regions)
        if hasattr(self, '_load_selections_btn'):
            self._load_selections_btn.setEnabled(self._focus_mode and self._audio_path is not None)
        # Prev / Next file buttons
        if hasattr(self, '_prev_file_btn'):
            idx = self._file_combo.currentIndex()
            self._prev_file_btn.setEnabled(idx > 0)
        if hasattr(self, '_next_file_btn'):
            idx = self._file_combo.currentIndex()
            self._next_file_btn.setEnabled(idx < self._file_combo.count() - 1)

    # ──────────────────────────────────────────────────────────────────────
    # Save / Load
    # ──────────────────────────────────────────────────────────────────────

    def _save_labels(self):
        """Save current onsets to the appropriate file (Excel or .txt).

        When multiple layers exist, each layer is saved to a separate label
        file (``*_labels_1.txt``, ``*_labels_2.txt``, …) and, if using Excel,
        to separate columns (``Onset_Times_1``, ``Onset_Times_2``, …).
        The active layer is also saved to the "main" label path for
        backward compatibility.
        """
        if not self._audio_path:
            return

        stem = os.path.splitext(os.path.basename(self._audio_path))[0]
        folder = os.path.dirname(self._audio_path)

        # Always save to .txt label file (backward compatibility)
        if self._label_path is None:
            self._label_path = os.path.join(folder, f"{stem}_labels.txt")

        # Persist current layer so _layers list is up-to-date
        self._save_layer_state()

        n_layers = len(self._layers)
        saved_layer_paths: list[str] = []

        if n_layers == 1:
            # Single layer: save to main label path only
            _save_labels(self._label_path, self._onset_times)
            saved_layer_paths.append(self._label_path)
        else:
            # Multiple layers: save each to a numbered file
            for li, layer in enumerate(self._layers):
                layer_path = os.path.join(
                    folder, f"{stem}_labels_{li + 1}.txt")
                _save_labels(layer_path, layer["onset_times"])
                saved_layer_paths.append(layer_path)
            # Also save active layer to the main path for compat
            _save_labels(self._label_path, self._onset_times)

        self._dirty = False
        # Mark all layers as clean
        for layer in self._layers:
            layer["dirty"] = False

        if self._onset_source != "excel":
            self._onset_file_edit.setText(os.path.basename(self._label_path))
        self._update_button_states()
        self._update_status_summary()

        if n_layers == 1:
            self._status_label.setText(
                f"Saved {len(self._onset_times)} onsets → {os.path.basename(self._label_path)}"
            )
        else:
            total = sum(len(l["onset_times"]) for l in self._layers)
            self._status_label.setText(
                f"Saved {total} onsets across {n_layers} layers → {stem}_labels_*.txt"
            )
        self.onsetsSaved.emit(self._label_path, len(self._onset_times))

        # Also save to Excel if using Excel source
        if self._onset_source == "excel" and self._excel_onset_path and _HAS_EXCEL_IO:
            audio_filename = os.path.basename(self._audio_path)
            try:
                if n_layers == 1:
                    # Use custom layer name if user provided one
                    lyr_name = self._layers[0]["name"]
                    default_name = "Layer 1"
                    _eio.save_onsets_to_excel(
                        file_path=self._excel_onset_path,
                        audio_filename=audio_filename,
                        onset_times=self._onset_times,
                        filename_col=self._excel_filename_col,
                        onset_col=self._excel_onset_col,
                        sheet_name=self._excel_sheet_name,
                        layer_name=lyr_name if lyr_name != default_name else None,
                    )
                else:
                    # Save each layer to its own column
                    for li, layer in enumerate(self._layers):
                        col_name = f"Onset_Times_{li + 1}"
                        lyr_name = layer["name"]
                        default_name = f"Layer {li + 1}"
                        _eio.save_onsets_to_excel(
                            file_path=self._excel_onset_path,
                            audio_filename=audio_filename,
                            onset_times=layer["onset_times"],
                            filename_col=self._excel_filename_col,
                            onset_col=self._excel_onset_col,
                            new_col_name=col_name,
                            sheet_name=self._excel_sheet_name,
                            layer_name=lyr_name if lyr_name != default_name else None,
                            layer_col_name=f"Onset_Layer_{li + 1}",
                        )
                xl_base = os.path.basename(self._excel_onset_path)
                if n_layers == 1:
                    self._status_label.setText(
                        f"Saved {len(self._onset_times)} onsets → "
                        f"{os.path.basename(self._label_path)} + {xl_base}")
                else:
                    self._status_label.setText(
                        f"Saved {n_layers} layers → {stem}_labels_*.txt + {xl_base}")
            except Exception as exc:
                self._status_label.setText(
                    f"Saved .txt OK but Excel error: {exc}")

        # Export focus regions JSON (used by onset_finder for spectral matching)
        self._save_focus_regions_json(folder, stem)

        # Export per-layer settings (used by pipeline's "Specify Layers")
        self._save_onset_layer_settings()

    def _save_focus_regions_json(self, folder: str, stem: str):
        """Write per-file focus regions to a JSON file next to the audio.

        The JSON maps filename → list of region dicts (with t_start,
        t_end, f_low, f_high, polarity).  onset_finder.py reads
        this via the ``focus_regions_path`` config key.
        """
        _write_focus_regions_json_impl(folder, stem, self._layers)

    def _save_onset_layer_settings(self):
        """Save each layer's config to ``{stem}_OnsetLayers/`` alongside the audio.

        Each layer is written as ``Layer_{N}.json`` containing:
            name, focus_regions (for this file), settings (detection overrides).
        The pipeline's ``_CheckableLayerCombo`` discovers layers from these files.
        """
        if not self._audio_path:
            return

        # Persist current layer before iterating
        self._save_layer_state()
        _write_onset_layer_settings_impl(self._audio_path, self._layers)

    def _load_labels_dialog(self):
        """Open a file dialog to load a label file."""
        start = os.path.dirname(self._audio_path) if self._audio_path else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Audacity Labels", start,
            "Label Files (*.txt);;All Files (*)"
        )
        if not path:
            return
        self._label_path = path
        self._onset_times = _load_labels(path)
        self._undo_stack.clear()
        self._undo_stack.push(list(self._onset_times))
        self._dirty = False
        self._refresh_viewer_markers()
        self._refresh_table()
        self._update_button_states()
        self._status_label.setText(
            f"Loaded {len(self._onset_times)} onsets from {os.path.basename(path)}"
        )

    # ──────────────────────────────────────────────────────────────────────
    # Excel save (per-recording)
    # ──────────────────────────────────────────────────────────────────────

    def _save_to_excel(self):
        """Save current onsets to the pipeline Excel file, updating only
        the rows that belong to the current recording."""
        if not self._audio_path:
            QMessageBox.warning(self, "No File", "No audio file is loaded.")
            return

        try:
            import pandas as pd
        except ImportError:
            QMessageBox.warning(
                self, "Missing Dependency",
                "pandas is required for Excel export. "
                "Install it with: pip install pandas openpyxl")
            return

        # Locate the Excel file — look in a 'data' subfolder first, then
        # the same folder as the audio file.
        audio_folder = os.path.dirname(self._audio_path)
        fname = os.path.basename(self._audio_path)

        candidates = [
            os.path.join(audio_folder, "data", "AudioData_OnsetFinder.xlsx"),
            os.path.join(audio_folder, "AudioData_OnsetFinder.xlsx"),
            os.path.join(audio_folder, "Cross_Species_Rhythm_Data.xlsx"),
            os.path.join(audio_folder, "data", "Cross_Species_Rhythm_Data.xlsx"),
        ]
        excel_path = None
        for c in candidates:
            if os.path.isfile(c):
                excel_path = c
                break

        if excel_path is None:
            # Let user pick / create one
            start = os.path.join(audio_folder, "data") if os.path.isdir(
                os.path.join(audio_folder, "data")) else audio_folder
            excel_path, _ = QFileDialog.getSaveFileName(
                self, "Save to Excel", start,
                "Excel Files (*.xlsx)")
            if not excel_path:
                return

        source = getattr(self, '_excel_onset_path', None)
        self._write_recording_to_excel(excel_path, fname, self._onset_times,
                                       source_excel=source)

    def _write_recording_to_excel(self, excel_path: str, file_name: str,
                                   onsets: list[float],
                                   source_excel: str | None = None):
        try:
            result = _eio.write_recording_to_workbook(
                excel_path,
                file_name,
                onsets,
                source_excel=source_excel,
            )
            self._status_label.setText(
                f"Saved {file_name} ({result['onset_count']} onsets) → {os.path.basename(result['path'])}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Excel Save Error", str(exc))

    # ──────────────────────────────────────────────────────────────────────
    # Region-based onset detection
    # ──────────────────────────────────────────────────────────────────────

    def _build_focus_signal_profile(self) -> dict | None:
        """Build a signal profile from the current file's positive/negative focus regions."""
        if self._viewer is None or self._viewer.audioData is None or self._audio_path is None:
            return None

        return _build_focus_signal_profile_impl(
            os.path.basename(self._audio_path),
            self._focus_regions,
            self._viewer.audioData,
            self._viewer.sampleRate,
            loaded_signal_profile=self._loaded_signal_profile,
        )

    def _analyze_focus_region_settings(self) -> tuple[dict | None, dict | None]:
        """Return (signal_profile, recommendation_result) for the current file."""
        profile = self._build_focus_signal_profile()
        return _analyze_focus_region_settings_impl(self._audio_path, profile)

    def _get_processable_time_range(self) -> tuple[float, float]:
        """Return the default process range: selection if present, else full clip."""
        if self._viewer is None or self._viewer.audioData is None:
            return 0.0, 0.0
        duration = float(self._viewer.duration)
        if self._selected_region is not None:
            start, end = self._selected_region
            return float(start), float(end)
        return 0.0, duration

    def _get_focus_locked_time_range(self) -> tuple[float, float] | None:
        """Return selected focus-region range when Focus mode is active."""
        if not self._focus_mode or self._viewer is None:
            return None
        if not hasattr(self._viewer, "get_selected_focus_region"):
            return None
        selected_focus = self._viewer.get_selected_focus_region()
        if selected_focus is None:
            return None

        duration = self._get_audio_duration()
        start = float(selected_focus.get("t_start", 0.0))
        end = float(selected_focus.get("t_end", 0.0))
        if end < start:
            start, end = end, start
        start = max(0.0, min(start, duration))
        end = max(start, min(end, duration))
        if end - start < 1e-9:
            return None
        return start, end

    def _get_audio_duration(self) -> float:
        """Return the loaded audio duration in seconds."""
        if self._viewer is None or self._viewer.audioData is None:
            return 0.0
        return float(self._viewer.duration)

    def _apply_detect_settings_to_onset_finder(self, settings: dict):
        """Apply current effective region-detection settings to the main Onset Finder panel."""
        main = self.window()
        if not (hasattr(main, "extractor_panel") and hasattr(main, "sidebar")):
            QMessageBox.information(
                self,
                "Unavailable",
                "The main Onset Finder panel is not available in this window.",
            )
            return

        main.extractor_panel.set_values(settings)
        main.sidebar._select(3)
        QMessageBox.information(
            self,
            "Applied",
            "These effective settings have been applied to the Onset Finder panel."
            "\nSwitch to Step 3 to review and run.",
        )

    def _detect_onsets_in_region(self):
        """Open Onset Finder for the current selection or the full clip."""
        if self._viewer is None or self._viewer.audioData is None:
            QMessageBox.warning(self, "No Audio", "Load an audio file first.")
            return

        locked_range = self._get_focus_locked_time_range()
        if self._focus_mode and locked_range is None:
            QMessageBox.information(
                self,
                "Select Focus Region",
                "Focus Onsets mode is active. Select a focus region first to run Quick Onset Finder within that region.",
            )
            return

        default_start, default_end = locked_range or self._get_processable_time_range()
        duration = self._get_audio_duration()

        dlg = _DetectOnsetsDialog(
            default_start,
            default_end,
            duration,
            parent=self,
            selection_available=self._selected_region is not None,
            locked_range=locked_range,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        n_onsets = dlg.num_onsets()
        effective_settings = dlg.effective_settings()
        start, end = dlg.selected_range()
        if end - start < 0.01:
            QMessageBox.warning(
                self,
                "Range Too Small",
                "The chosen time range is too short.",
            )
            return

        # Extract the audio slice
        y = self._viewer.audioData
        sr = self._viewer.sampleRate
        i_start = max(0, int(start * sr))
        i_end = min(len(y), int(end * sr))
        y_slice = y[i_start:i_end]

        if len(y_slice) < sr * 0.01:
            QMessageBox.warning(self, "Too Short",
                                "The selected audio region is too short for detection.")
            return

        # Create and configure the worker thread
        self._detect_worker = _DetectOnsetsWorker(
            y_slice,
            sr,
            n_onsets,
            settings=effective_settings,
            run_detection=OnsetEditorPanel._run_simple_detection,
        )

        # Store region info for when the worker finishes
        self._detect_region_start = start
        self._detect_region_end = end

        # Progress dialog (Esc or Cancel button to abort)
        self._detect_progress = QProgressDialog(
            "Detecting onsets… Press Esc to cancel.", "Cancel", 0, 0, self)
        self._detect_progress.setWindowTitle("Finding Onsets")
        self._detect_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._detect_progress.setMinimumDuration(0)
        self._detect_progress.canceled.connect(self._cancel_detect_worker)

        # Connect worker signals
        self._detect_worker.finished.connect(self._on_detect_finished)
        self._detect_worker.error.connect(self._on_detect_error)
        self._detect_worker.finished.connect(self._detect_progress.close)
        self._detect_worker.error.connect(self._detect_progress.close)

        self._detect_region_btn.setEnabled(False)
        self._detect_worker.start()

    def _cancel_detect_worker(self):
        """Cancel the running onset detection worker."""
        if hasattr(self, '_detect_worker') and self._detect_worker is not None:
            self._detect_worker.cancel()
            self._detect_worker.quit()
            self._detect_worker.wait(2000)
            self._detect_worker = None
        self._update_button_states()
        self._status_label.setText("Onset detection cancelled.")

    def _open_analyze_signals_dialog(self):
        """Open the Analyze Selected Signals dialog."""
        if self._viewer is None or self._viewer.audioData is None:
            QMessageBox.warning(self, "No Audio", "Load an audio file first.")
            return

        dlg = _AnalyzeSignalsDialog(
            parent=self,
            apply_callback=self._apply_detect_settings_to_onset_finder,
            analyze_callback=self._analyze_focus_region_settings,
            format_recommendations=_format_detect_recommendations,
        )
        dlg.exec()

        # Apply cluster layers if the analysis produced them
        cluster_result = dlg.layer_cluster_result()
        if (cluster_result and cluster_result.get("n_clusters", 1) > 1
                and self._audio_path):
            self._apply_cluster_layers(cluster_result)

    def _apply_cluster_layers(self, cluster_result: dict):
        """Create onset layers from a clustering result and distribute focus regions.

        Always creates *new* layers — existing layers are never overwritten.
        Negative regions are copied to every new layer so that suppression
        info is always available.
        """
        n_clusters = cluster_result.get("n_clusters", 1)
        labels = cluster_result.get("labels", [])
        descriptions = cluster_result.get("descriptions", [])
        if n_clusters <= 1 or not labels:
            return

        fname = os.path.basename(self._audio_path) if self._audio_path else ""
        if not fname:
            return

        # Gather current layer's focus regions for this file
        current_regions = list(self._focus_regions.get(fname, []))
        pos_regions = [r for r in current_regions if r.get("polarity") == "positive"]
        neg_regions = [r for r in current_regions if r.get("polarity") == "negative"]

        if len(pos_regions) != len(labels):
            return

        # Save current layer state first
        self._save_layer_state()

        # Partition positive regions by cluster label
        clustered: dict[int, list[dict]] = {}
        for region, lab in zip(pos_regions, labels):
            clustered.setdefault(lab, []).append(region)

        # Create new layers for every cluster (preserving existing layers)
        sorted_cluster_ids = sorted(clustered.keys())
        first_new_idx = len(self._layers)
        created_layer_names: list[str] = []

        for cid in sorted_cluster_ids:
            desc_idx = min(cid, len(descriptions) - 1)
            cdesc = descriptions[desc_idx] if desc_idx >= 0 else f"Cluster {cid + 1}"
            layer_name = f"Layer {len(self._layers) + 1} — {cdesc}"
            created_layer_names.append(layer_name)
            _append_layer_state_impl(
                self._layers,
                layer_name=layer_name,
                focus_regions={fname: list(clustered[cid]) + list(neg_regions)},
            )

        self._append_layer_names_to_combo(created_layer_names, block_signals=True)

        activation = _activate_layer_range_impl(
            self._checked_layer_indices,
            first_new_idx,
            len(self._layers),
        )
        if activation is None:
            return
        self._apply_new_layer_range_activation(activation, first_new_idx)

        self._refresh_layer_data_views()
        self._refresh_post_layer_change_widgets(refresh_signal_browser=True)
        self._status_label.setText(
            f"Created {n_clusters} new onset layers from signal clustering."
        )

    def _on_escape_pressed(self):
        """Handle Escape key — cancel any active background process."""
        if hasattr(self, '_detect_worker') and self._detect_worker is not None:
            self._cancel_detect_worker()
            if hasattr(self, '_detect_progress') and self._detect_progress is not None:
                self._detect_progress.close()

    def _toggle_focus_mode_shortcut(self):
        """Toggle focus mode via F key."""
        if hasattr(self, '_focus_onsets_btn'):
            self._focus_onsets_btn.setChecked(not self._focus_onsets_btn.isChecked())

    def _toggle_edit_onsets_shortcut(self):
        """Toggle edit-onsets mode via E key."""
        if hasattr(self, '_edit_onsets_btn'):
            self._edit_onsets_btn.setChecked(not self._edit_onsets_btn.isChecked())

    def _cycle_maximize(self):
        """Cycle through fullscreen states via M key."""
        if self._viewer is not None and hasattr(self._viewer, '_toggle_maximize'):
            self._viewer._toggle_maximize()

    def _apply_hotkeys(self):
        """Create or rebind all QShortcuts from self._hotkey_map."""
        # Remove old shortcuts
        for sc in self._shortcuts.values():
            sc.setEnabled(False)
            sc.setParent(None)
            sc.deleteLater()
        self._shortcuts.clear()

        for action_id, callback in self._shortcut_actions.items():
            key_str = self._hotkey_map.get(action_id, "")
            if not key_str:
                continue
            sc = QShortcut(QKeySequence(key_str), self, callback)
            self._shortcuts[action_id] = sc

    def _prev_layer_shortcut(self):
        """Switch to previous layer via [ key."""
        if hasattr(self, '_layer_combo') and self._layer_combo.count() > 1:
            idx = self._layer_combo.currentIndex()
            if idx > 0:
                self._layer_combo.setCurrentIndex(idx - 1)

    def _next_layer_shortcut(self):
        """Switch to next layer via ] key."""
        if hasattr(self, '_layer_combo') and self._layer_combo.count() > 1:
            idx = self._layer_combo.currentIndex()
            if idx < self._layer_combo.count() - 1:
                self._layer_combo.setCurrentIndex(idx + 1)

    def _on_detect_error(self, msg: str):
        """Handle an error from the detection worker."""
        self._detect_worker = None
        self._update_button_states()
        QMessageBox.critical(self, "Detection Error",
                             f"Onset detection failed:\n{msg}")

    def _on_detect_finished(self, detected: list):
        """Handle results from the detection worker thread."""
        self._detect_worker = None
        self._update_button_states()

        start = self._detect_region_start
        end = self._detect_region_end

        if not detected:
            QMessageBox.information(
                self, "No Onsets Found",
                "No onsets were detected in the selected region. "
                "Try selecting a larger region or increasing the count.")
            return

        merged_onsets, added = _merge_onsets_impl(
            self._onset_times,
            detected,
            offset=start,
        )

        if added > 0:
            self._onset_times = merged_onsets
            self._push_undo()
            self._refresh_viewer_markers()
            self._refresh_table()
            scope = "full clip" if abs(start) < 1e-9 and abs(end - self._get_audio_duration()) < 1e-9 else f"{start:.3f}s–{end:.3f}s"
            self._status_label.setText(f"Added {added} onset(s) from {scope}")
        else:
            self._status_label.setText(
                "All detected onsets already exist (duplicates skipped)")

        # Clear the selection region
        self._clear_selection_state()

    # ──────────────────────────────────────────────────────────────────────
    # Per-layer batch detection
    # ──────────────────────────────────────────────────────────────────────

    def _detect_all_layers(self):
        """Run onset detection for every layer using each layer's focus regions."""
        if self._viewer is None or self._viewer.audioData is None:
            QMessageBox.warning(self, "No Audio", "Load an audio file first.")
            return

        n_layers = len(self._layers)
        if n_layers < 2:
            QMessageBox.information(
                self, "Single Layer",
                "Auto-Detect All Layers requires multiple layers.\n"
                "Add more layers first, each with their own focus regions.")
            return

        reply = QMessageBox.question(
            self, "Auto-Detect All Layers",
            f"This will run onset detection for all {n_layers} layers "
            f"using each layer's focus regions and recommended settings.\n\n"
            f"Detected onsets will be added to each layer (existing onsets are preserved).\n\n"
            f"Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Save current layer state before iterating
        self._save_layer_state()
        original_layer_idx = self._active_layer_idx

        y = self._viewer.audioData
        sr = self._viewer.sampleRate
        duration = self._get_audio_duration()
        fname = os.path.basename(self._audio_path) if self._audio_path else ""

        progress = QProgressDialog(
            "Detecting onsets for all layers\u2026", "Cancel", 0, n_layers, self)
        progress.setWindowTitle("Auto-Detect All Layers")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        total_added = 0
        layers_processed = 0

        for li in range(n_layers):
            if progress.wasCanceled():
                break

            layer = self._layers[li]
            layer_name = layer["name"]
            progress.setLabelText(
                f"Processing {layer_name} ({li + 1}/{n_layers})\u2026")
            progress.setValue(li)
            QApplication.processEvents()

            # Get this layer's focus regions for the current file
            layer_regions = layer.get("focus_regions", {}).get(fname, [])
            if not layer_regions:
                continue

            # Build signal profile from this layer's regions
            pos_regions = [r for r in layer_regions if r.get("polarity") == "positive"]
            neg_regions = [r for r in layer_regions if r.get("polarity") == "negative"]
            if not pos_regions and not neg_regions:
                continue

            signal_profile = None
            recommendation = None
            try:
                # Temporarily switch live state to this layer for analysis
                self._active_layer_idx = li
                self._load_layer_state()
                signal_profile, recommendation = self._analyze_focus_region_settings()
            except Exception:
                pass
            finally:
                # Restore — we'll write results directly to layer dict
                pass

            # Build effective settings from recommendation
            effective = None
            if recommendation:
                effective = dict(recommendation)

            # Determine time range from positive regions
            if pos_regions:
                t_start = min(r["t_start"] for r in pos_regions)
                t_end = max(r["t_end"] for r in pos_regions)
            else:
                t_start, t_end = 0.0, duration

            i_start = max(0, int(t_start * sr))
            i_end = min(len(y), int(t_end * sr))
            y_slice = y[i_start:i_end]

            if len(y_slice) < sr * 0.01:
                continue

            try:
                detected = self._run_simple_detection(
                    y_slice, sr, 0,  # 0 = auto-detect as many as possible
                    settings=effective,
                    signal_profile=signal_profile,
                )
            except Exception:
                continue

            if not detected:
                continue

            # Convert to absolute times and add to this layer
            layer_onsets = list(layer["onset_times"])
            added = 0
            for t_rel in detected:
                t_abs = t_rel + t_start
                if any(abs(t_abs - ex) < 0.001 for ex in layer_onsets):
                    continue
                layer_onsets.append(t_abs)
                added += 1

            if added > 0:
                layer_onsets.sort()
                layer["onset_times"] = layer_onsets
                layer["undo_stack"].push(list(layer_onsets))
                layer["dirty"] = True
                total_added += added

            layers_processed += 1

        progress.setValue(n_layers)

        # Restore original active layer
        self._active_layer_idx = original_layer_idx
        self._load_layer_state()
        self._refresh_viewer_markers()
        self._refresh_table()
        self._update_button_states()

        if total_added > 0:
            self._status_label.setText(
                f"Auto-detect: added {total_added} onset(s) across {layers_processed} layer(s)")
        else:
            self._status_label.setText(
                "Auto-detect: no new onsets found (layers may need focus regions)")

    # ──────────────────────────────────────────────────────────────────────
    # Per-signal detection ("Onset Finder / Sel. Signal")
    # ──────────────────────────────────────────────────────────────────────

    def _run_per_signal_detection(self):
        """Positive-signal per-signal detection workflow.

        1. Build per-signal profiles from current layer's positive focus regions.
        2. Open the PerSignalConfigDialog wizard.
        3. Create one temporary layer per positive signal.
        4. Run detection per layer with per-signal settings.
        5. Show results in the layer combo for review.
        """
        if self._viewer is None or self._viewer.audioData is None:
            QMessageBox.warning(self, "No Audio", "Load an audio file first.")
            return

        fname = os.path.basename(self._audio_path) if self._audio_path else ""
        regions = list(self._focus_regions.get(fname, []))
        pos_regions = [r for r in regions if r.get("polarity") == "positive"]

        if not pos_regions:
            QMessageBox.information(
                self, "No Positive Signals",
                "Draw at least one positive focus region first.\n"
                "Use Focus Onsets → + Positive to mark example signals.")
            return

        y = self._viewer.audioData
        sr = self._viewer.sampleRate

        # Build per-signal profiles
        try:
            from analysis.signal_profiles import (
                build_per_signal_profiles,
                build_signal_profile,
            )
        except ImportError:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            try:
                from analysis.signal_profiles import (
                    build_per_signal_profiles,
                    build_signal_profile,
                )
            except Exception:
                QMessageBox.warning(self, "Import Error",
                                    "Could not import analysis.signal_profiles.")
                return

        per_profiles = build_per_signal_profiles(y, sr, pos_regions)
        if not per_profiles:
            QMessageBox.information(self, "No Profiles",
                                    "Could not build profiles from the selected signals.")
            return

        # Open the config wizard
        dlg = _PerSignalConfigDialog(per_profiles, parent=self, mode="positive",
                                      y=y, sr=sr)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        configs = dlg.get_configs()
        profiles = dlg.get_profiles()

        exemplar_failures = []
        preflight_reports: dict[int, dict] = {}
        for si, prof in enumerate(profiles):
            region = prof["region"]
            cfg = configs[si]
            single_profile = build_signal_profile(y, sr, [region])
            effective = {
                "_spectral_match_threshold": _compute_per_signal_spectral_threshold(cfg),
                "_per_signal_variable_score_threshold": _compute_per_signal_variable_score_threshold(cfg),
            }
            report = _evaluate_exemplar_self_check(y, sr, single_profile, cfg, effective)
            preflight_reports[si] = report
            if not report.get("passed"):
                exemplar_failures.append((si, region, report))

        if exemplar_failures:
            lines = [
                "Some positive exemplars do not satisfy their current match settings.",
                "The run can continue, but these signals may be over-constrained.",
                "",
            ]
            for si, region, report in exemplar_failures[:4]:
                best = report.get("best_result") or {}
                failed = ", ".join(best.get("failed_keys", [])[:3]) or "spectral match"
                spec_text = (f"{best.get('spectral_similarity', 0):.2f}"
                             if best.get("spectral_similarity") is not None else "n/a")
                lines.append(
                    f"Signal {si + 1} ({region.get('f_low', 0):.0f}-{region.get('f_high', 0):.0f} Hz): "
                    f"spectral {spec_text}/{report.get('spectral_threshold', 0):.2f}, "
                    f"variable {best.get('score', 0):.2f}/{report.get('variable_threshold', 0):.2f}; "
                    f"weakest: {failed}"
                )
            if len(exemplar_failures) > 4:
                lines.append(f"... and {len(exemplar_failures) - 4} more signal(s)")
            lines.append("")
            lines.append("Continue anyway?")
            reply = QMessageBox.warning(
                self,
                "Positive Self-Check Warning",
                "\n".join(lines),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Confirmation
        reply = QMessageBox.question(
            self, "Run Per-Signal Detection",
            f"This will create {len(profiles)} new layer(s) — one per positive signal — "
            f"and run onset detection for each.\n\n"
            f"Existing layers are preserved. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Save current layer state
        self._save_layer_state()

        progress = QProgressDialog(
            "Finding onsets\u2026", "Cancel",
            0, len(profiles), self)
        progress.setWindowTitle("Per-Signal Onset Detection")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        total_added = 0
        layers_created = 0
        exemplar_recoveries = 0
        exemplar_misses: list[str] = []
        created_layer_names: list[str] = []

        for si, prof in enumerate(profiles):
            if progress.wasCanceled():
                break
            progress.setLabelText(
                f"Finding onsets for signal {si + 1}/{len(profiles)}\u2026")
            progress.setValue(si)
            QApplication.processEvents()

            region = prof["region"]
            analysis = prof["analysis"]
            cfg = configs[si]

            # Create a new layer for this signal
            layer_name = f"Signal {si + 1} ({region.get('f_low', 0):.0f}-{region.get('f_high', 0):.0f} Hz)"
            neg_regions = [r for r in regions if r.get("polarity") == "negative"]
            new_idx = _append_layer_state_impl(
                self._layers,
                layer_name=layer_name,
                focus_regions={
                    fname: [dict(region)] + [dict(nr) for nr in neg_regions]
                },
            )
            new_layer = self._layers[new_idx]
            created_layer_names.append(layer_name)
            layers_created += 1

            # Build a single-signal profile for detection
            single_profile = build_signal_profile(y, sr, [region])
            if neg_regions:
                neg_profile = build_signal_profile(y, sr, neg_regions)
                single_profile["negative_regions"] = neg_profile.get("regions", [])
                single_profile["negative_summary"] = neg_profile.get("summary", {})

            # Get recommendations from the analyzer
            recommendation = None
            try:
                from analysis.onset_recommendations import analyze_for_onsets
            except ImportError:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if project_root not in sys.path:
                    sys.path.insert(0, project_root)
                from analysis.onset_recommendations import analyze_for_onsets
            try:
                result = analyze_for_onsets(self._audio_path, signal_profile=single_profile)
                if result:
                    recommendation = dict(result)
            except Exception:
                pass

            effective = _extract_recommended_detect_settings(recommendation)

            # Apply per-variable deviation constraints:
            # Adjust the spectral match threshold based on how tight the
            # user wants matching to be.
            spectral_threshold = _compute_per_signal_spectral_threshold(cfg)
            effective["_spectral_match_threshold"] = spectral_threshold
            effective["_per_signal_config"] = cfg
            effective["_per_signal_variable_score_threshold"] = (
                _compute_per_signal_variable_score_threshold(cfg)
            )

            # Detect across the full file (not just the region)
            try:
                detected = self._run_simple_detection(
                    y, sr, 0,
                    settings=effective,
                    signal_profile=single_profile,
                )
            except Exception:
                detected = []

            if not _region_contains_onset(detected, region):
                recovery = _recover_focus_region_onset(
                    y, sr, region, single_profile, cfg, effective)
                recovered_time = recovery.get("recovered_time")
                if recovered_time is not None and not any(abs(recovered_time - ex) < 0.001 for ex in detected):
                    detected.append(recovered_time)
                    exemplar_recoveries += 1
                elif recovered_time is None:
                    exemplar_misses.append(
                        f"Signal {si + 1}: {_format_match_miss_reason(recovery.get('best_result'))}"
                    )

            if not detected:
                exemplar_misses.append(
                    f"Signal {si + 1}: no onset survived detection or local exemplar recovery"
                )
                continue

            # Add detected onsets to the new layer
            layer_onsets = list(new_layer["onset_times"])
            added = 0
            for t in detected:
                if any(abs(t - ex) < 0.001 for ex in layer_onsets):
                    continue
                layer_onsets.append(t)
                added += 1

            if added > 0:
                layer_onsets.sort()
                new_layer["onset_times"] = layer_onsets
                new_layer["undo_stack"].push(list(layer_onsets))
                new_layer["dirty"] = True
                total_added += added

        progress.setValue(len(profiles))
        self._append_layer_names_to_combo(created_layer_names)

        # Switch to the first new layer for review
        if layers_created > 0:
            first_new_idx = len(self._layers) - layers_created
            activation = _activate_layer_range_impl(
                self._checked_layer_indices,
                first_new_idx,
                len(self._layers),
            )
            if activation is None:
                return
            self._apply_new_layer_range_activation(activation, first_new_idx)
            self._refresh_viewer_markers()
            self._refresh_table()
            self._refresh_layer_selection_widgets()

        self._update_button_states()

        if exemplar_misses:
            lines = [
                "Some selected positive signals still ended without a matching onset in their own region.",
                "",
            ]
            lines.extend(exemplar_misses[:6])
            if len(exemplar_misses) > 6:
                lines.append(f"... and {len(exemplar_misses) - 6} more")
            QMessageBox.information(self, "Per-Signal Miss Diagnostics", "\n".join(lines))

        if total_added > 0:
            recovery_text = (f", recovered {exemplar_recoveries} exemplar onset(s)"
                             if exemplar_recoveries > 0 else "")
            miss_text = (f", {len(exemplar_misses)} exemplar miss(es) remain"
                         if exemplar_misses else "")
            self._status_label.setText(
                f"Per-signal: created {layers_created} layer(s), "
                f"added {total_added} onset(s) total{recovery_text}{miss_text}")
        else:
            self._status_label.setText(
                "Per-signal: no new onsets found — try adjusting deviation ranges")

    @staticmethod
    def _compute_avg_deviation(cfg: dict) -> float:
        """Compute the average enabled deviation % from a per-signal config.

        For each enabled variable, averages (lower_pct + upper_pct) / 2,
        then returns the mean across all enabled variables.
        Falls back to legacy ``deviation_pct`` if present.
        """
        vals = []
        for v in cfg.values():
            if not isinstance(v, dict) or not v.get("enabled"):
                continue
            if "lower_pct" in v and "upper_pct" in v:
                vals.append((v["lower_pct"] + v["upper_pct"]) / 2.0)
            elif "deviation_pct" in v:
                vals.append(v["deviation_pct"])
        return float(np.mean(vals)) if vals else 30.0

    # ──────────────────────────────────────────────────────────────────────
    # Negative signal subtraction
    # ──────────────────────────────────────────────────────────────────────

    def _run_negative_subtraction(self):
        """Negative-signal subtraction workflow.

        1. Build per-signal profiles from negative focus regions.
        2. Open the PerSignalConfigDialog wizard (negative mode).
        3. Run detection for each negative signal.
        4. Match detected negative onsets against existing onsets.
        5. Open the NegativeSubtractionDialog for review.
        6. Apply removals.
        """
        if self._viewer is None or self._viewer.audioData is None:
            QMessageBox.warning(self, "No Audio", "Load an audio file first.")
            return

        if not self._onset_times and not any(
                layer.get("onset_times") for layer in self._layers):
            QMessageBox.information(
                self, "No Existing Onsets",
                "The negative subtraction pass removes onsets that match "
                "negative signals.\nYou need existing onsets first — run "
                "the positive detection or Onset Finder first.")
            return

        fname = os.path.basename(self._audio_path) if self._audio_path else ""
        regions = list(self._focus_regions.get(fname, []))
        neg_regions = [r for r in regions if r.get("polarity") == "negative"]

        if not neg_regions:
            QMessageBox.information(
                self, "No Negative Signals",
                "Draw at least one negative focus region first.\n"
                "Use Focus Onsets → − Negative to mark unwanted signals.")
            return

        y = self._viewer.audioData
        sr = self._viewer.sampleRate

        try:
            from analysis.signal_profiles import (
                build_per_signal_profiles,
                build_signal_profile,
            )
        except ImportError:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            try:
                from analysis.signal_profiles import (
                    build_per_signal_profiles,
                    build_signal_profile,
                )
            except Exception:
                QMessageBox.warning(self, "Import Error",
                                    "Could not import analysis.signal_profiles.")
                return

        per_profiles = build_per_signal_profiles(y, sr, neg_regions)
        if not per_profiles:
            return

        # Open config wizard for negative signals
        dlg = _PerSignalConfigDialog(per_profiles, parent=self, mode="negative",
                                      y=y, sr=sr)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        configs = dlg.get_configs()
        profiles = dlg.get_profiles()

        exemplar_failures = []
        for si, prof in enumerate(profiles):
            region = prof["region"]
            cfg = configs[si]
            neg_single_profile = build_signal_profile(y, sr, [region])
            neg_single_profile["regions"] = neg_single_profile.get("regions", [])
            for r_entry in neg_single_profile.get("regions", []):
                r_entry["polarity"] = "positive"
            effective = {
                "_spectral_match_threshold": _compute_per_signal_spectral_threshold(cfg),
                "_per_signal_variable_score_threshold": _compute_per_signal_variable_score_threshold(cfg),
            }
            report = _evaluate_exemplar_self_check(y, sr, neg_single_profile, cfg, effective)
            if not report.get("passed"):
                exemplar_failures.append((si, region, report))

        if exemplar_failures:
            lines = [
                "Some negative exemplars do not satisfy their current match settings.",
                "This can make subtraction miss unwanted events.",
                "",
            ]
            for si, region, report in exemplar_failures[:4]:
                best = report.get("best_result") or {}
                failed = ", ".join(best.get("failed_keys", [])[:3]) or "spectral match"
                spec_text = (f"{best.get('spectral_similarity', 0):.2f}"
                             if best.get("spectral_similarity") is not None else "n/a")
                lines.append(
                    f"Signal {si + 1} ({region.get('f_low', 0):.0f}-{region.get('f_high', 0):.0f} Hz): "
                    f"spectral {spec_text}/{report.get('spectral_threshold', 0):.2f}, "
                    f"variable {best.get('score', 0):.2f}/{report.get('variable_threshold', 0):.2f}; "
                    f"weakest: {failed}"
                )
            if len(exemplar_failures) > 4:
                lines.append(f"... and {len(exemplar_failures) - 4} more signal(s)")
            lines.append("")
            lines.append("Continue anyway?")
            reply = QMessageBox.warning(
                self,
                "Negative Self-Check Warning",
                "\n".join(lines),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        progress = QProgressDialog(
            "Finding onsets\u2026", "Cancel",
            0, len(profiles), self)
        progress.setWindowTitle("Negative Signal Detection")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        merged_neg_hits: list[dict] = []

        for si, prof in enumerate(profiles):
            if progress.wasCanceled():
                break
            progress.setLabelText(
                f"Finding onsets for negative signal {si + 1}/{len(profiles)}\u2026")
            progress.setValue(si)
            QApplication.processEvents()

            region = prof["region"]
            cfg = configs[si]

            # Build spectral profile for this negative signal
            neg_single_profile = build_signal_profile(y, sr, [region])
            # Treat the negative region as the "positive" target for detection
            # (we're looking for sounds that match the negative signal)
            neg_single_profile["regions"] = neg_single_profile.get("regions", [])
            for r_entry in neg_single_profile.get("regions", []):
                r_entry["polarity"] = "positive"

            recommendation = None
            try:
                from analysis.onset_recommendations import analyze_for_onsets
            except ImportError:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if project_root not in sys.path:
                    sys.path.insert(0, project_root)
                from analysis.onset_recommendations import analyze_for_onsets
            try:
                result = analyze_for_onsets(
                    self._audio_path,
                    signal_profile=neg_single_profile,
                )
                if result:
                    recommendation = dict(result)
            except Exception:
                pass

            effective = _extract_recommended_detect_settings(recommendation)
            spectral_threshold = _compute_per_signal_spectral_threshold(cfg)
            effective["_spectral_match_threshold"] = spectral_threshold
            effective["_per_signal_variable_score_threshold"] = (
                _compute_per_signal_variable_score_threshold(cfg)
            )

            try:
                detected = self._run_simple_detection(
                    y, sr, 0,
                    settings=effective,
                    signal_profile=neg_single_profile,
                )
            except Exception:
                continue

            if detected:
                # Compute similarity of each detected negative onset to the
                # spectral template (using cosine similarity)
                sig_num = si + 1  # 1-based signal number
                try:
                    from onset_postprocessing import build_spectral_profile as _build_spectral_profile
                    spect_prof = _build_spectral_profile(y, sr, [region])
                    if spect_prof is not None:
                        for t in detected:
                            centre = int(t * sr)
                            half_win = int(0.05 * sr)
                            start = max(0, centre - half_win)
                            end = min(len(y), centre + half_win)
                            if end - start >= 2048:
                                import librosa
                                seg = y[start:end]
                                S_seg = np.abs(librosa.stft(seg, n_fft=2048, hop_length=512))
                                seg_spectrum = S_seg.mean(axis=1)
                                ref = spect_prof["mean_spectrum"]
                                norm_seg = np.linalg.norm(seg_spectrum)
                                norm_ref = np.linalg.norm(ref)
                                if norm_seg > 0 and norm_ref > 0:
                                    sim = float(np.dot(seg_spectrum, ref) / (norm_seg * norm_ref))
                                else:
                                    sim = 0.0
                                sim = max(0.0, sim)
                            else:
                                sim = 0.5
                            _merge_negative_detection_hits(
                                merged_neg_hits, t, sim, sig_num)
                    else:
                        for t in detected:
                            _merge_negative_detection_hits(
                                merged_neg_hits, t, 0.5, sig_num)
                except Exception:
                    for t in detected:
                        _merge_negative_detection_hits(
                            merged_neg_hits, t, 0.5, sig_num)

        progress.setValue(len(profiles))

        all_neg_onsets = [hit["time"] for hit in merged_neg_hits]
        all_similarities = [hit["similarity"] for hit in merged_neg_hits]
        all_signal_indices = [hit["signal_nums"] for hit in merged_neg_hits]

        if not all_neg_onsets:
            QMessageBox.information(
                self, "No Negative Onsets Found",
                "No onsets matching the negative signal profiles were found.")
            return

        # Open the subtraction review dialog
        self._save_layer_state()
        sub_dlg = _NegativeSubtractionDialog(
            all_neg_onsets, all_similarities,
            layers=self._layers,
            active_layer_idx=self._active_layer_idx,
            checked_layer_indices=self._checked_layer_indices,
            neg_signal_indices=all_signal_indices,
            parent=self, viewer=self._viewer)

        if sub_dlg.exec() == QDialog.DialogCode.Accepted:
            removed = sub_dlg.get_removed_indices()
            if not removed:
                self._status_label.setText(
                    "Negative subtraction: no onsets removed")
                return

            remaining = sub_dlg.get_remaining_onsets()
            save_mode = sub_dlg.get_save_mode()
            sel_layers = sub_dlg.get_selected_layer_indices()

            if save_mode == _NegativeSubtractionDialog.SAVE_NEW_LAYER:
                # Create a new layer with the remaining onsets
                new_name = f"NegSub ({len(remaining)} onsets)"
                new_idx = _append_layer_state_impl(
                    self._layers,
                    layer_name=new_name,
                    onset_times=sorted(remaining),
                    dirty=True,
                )
                self._save_layer_state()
                self._active_layer_idx = new_idx
                self._load_layer_state()
                self._refresh_layer_menu_widgets()
                self._status_label.setText(
                    f"Negative subtraction: created new layer "
                    f"'{new_name}' with {len(remaining)} onset(s)")
            else:
                # Overwrite: apply remaining onsets to each selected layer
                # by removing the same onset times
                removed_times = set()
                combined = sub_dlg._combined_onsets
                for ri in removed:
                    if ri < len(combined):
                        removed_times.add(combined[ri])

                for li in sel_layers:
                    if li >= len(self._layers):
                        continue
                    old_times = self._layers[li].get("onset_times", [])
                    self._layers[li]["onset_times"] = _filter_removed_onsets_impl(
                        old_times,
                        removed_times,
                    )

                # Reload active layer
                self._load_layer_state()
                self._push_undo()
                self._refresh_viewer_markers()
                self._refresh_table()
                self._refresh_layer_menu_widgets()
                self._status_label.setText(
                    f"Negative subtraction: removed {len(removed)} onset(s) "
                    f"from {len(sel_layers)} layer(s)")

    # ──────────────────────────────────────────────────────────────────────
    # Confirm & Merge per-signal layers → FinalMergedOnsets
    # ──────────────────────────────────────────────────────────────────────

    def _confirm_and_merge_layers(self):
        """Merge all per-signal layers into a single FinalMergedOnsets result.

        Collects onset times from all layers, deduplicates (1ms tolerance),
        writes the merged set to the active layer, and optionally saves
        to a ``_FinalMergedOnsets`` column in the Excel file.
        """
        if len(self._layers) < 2:
            QMessageBox.information(
                self, "Single Layer",
                "Need at least 2 layers to merge.\n"
                "Run per-signal detection first to create per-signal layers.")
            return

        self._save_layer_state()

        # Gather layer names and onset counts for the confirmation dialog
        info_lines = []
        for i, layer in enumerate(self._layers):
            n = len(layer.get("onset_times", []))
            info_lines.append(f"  {layer['name']}: {n} onset(s)")
        info_text = "\n".join(info_lines)

        reply = QMessageBox.question(
            self, "Confirm & Merge All Layers",
            f"Merge onsets from all {len(self._layers)} layer(s) into one?\n\n"
            f"{info_text}\n\n"
            f"A merged onset set will be created (duplicates within 1 ms removed).\n"
            f"The result will be saved as a new 'Merged' layer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if reply != QMessageBox.StandardButton.Yes:
            return

        merged_idx, deduped = _append_merged_layer_impl(
            self._layers,
            list(range(len(self._layers))),
            layer_name="FinalMergedOnsets",
        )
        self._append_layer_names_to_combo([self._layers[merged_idx]["name"]])

        # Switch to the merged layer and check only it
        if not self._activate_exclusive_layer(merged_idx):
            return

        # Also try to save to Excel if available
        self._try_save_merged_to_excel(deduped)

        self._status_label.setText(
            f"Merged {len(self._layers) - 1} layer(s) → {len(deduped)} unique onset(s)")

    def _try_save_merged_to_excel(self, merged_onsets: list[float]):
        """Attempt to save merged onsets to a _FinalMergedOnsets column."""
        if not _HAS_EXCEL_IO or not self._audio_path:
            return

        # Try to find the existing Excel file
        audio_dir = os.path.dirname(self._audio_path)
        data_dir = os.path.join(audio_dir, "data")
        candidates = [
            os.path.join(data_dir, "AudioData_OnsetFinder.xlsx"),
            os.path.join(audio_dir, "AudioData_OnsetFinder.xlsx"),
        ]
        excel_path = None
        for c in candidates:
            if os.path.isfile(c):
                excel_path = c
                break

        if not excel_path:
            return

        try:
            stem = os.path.splitext(os.path.basename(self._audio_path))[0]
            col_name = f"{stem}_FinalMergedOnsets"
            _eio.save_onsets_to_excel(
                excel_path,
                os.path.basename(self._audio_path),
                merged_onsets,
                onset_col=col_name,
            )
        except Exception:
            pass  # Non-critical — user can always save manually later

    @staticmethod
    def _run_simple_detection(y_slice: np.ndarray, sr: int,
                               n_requested: int, *,
                               settings: dict | None = None,
                               signal_profile: dict | None = None,
                               hop_length: int = 256,
                               initial_delta: float = 0.3,
                               backtrack: bool = True,
                               min_ioi_ms: int = 30,
                               amplitude_gate: float = 0.0,
                               sharpness_gate: float = 0.0,
                               cluster_enabled: bool = True,
                               cluster_window_ms: int = 25,
                               refine_enabled: bool = True,
                               refine_window_ms: float = 10.0,
                               _cancel_flag=None) -> list[float]:
        """Run onset detection on an audio slice with post-processing.

        Uses the same onset-detector vocabulary as the main Onset Finder for
        the coarse pass, then applies the same post-processing order used in
        the main pipeline.
        """
        def _is_cancelled():
            return _cancel_flag is not None and getattr(_cancel_flag, '_cancelled', False)

        try:
            import librosa
        except ImportError:
            return []

        # Import post-processing functions from the main pipeline
        import sys, os
        _scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
        if _scripts_dir not in sys.path:
            sys.path.insert(0, _scripts_dir)
        from onset_postprocessing import (
            cluster_onsets, gate_onsets_by_amplitude,
            gate_onsets_by_sharpness, enforce_min_interval,
            build_spectral_profile, gate_onsets_by_spectral_match)
        from onset_detectors import detect_onsets, refine_onsets_to_sample

        effective = dict(settings or {
            "ONSET_METHOD": "librosa",
            "ONSET_HOP_LENGTH": hop_length,
            "ONSET_DELTA": initial_delta,
            "ONSET_BACKTRACK": backtrack,
            "MIN_INTER_ONSET_MS": min_ioi_ms,
            "ONSET_AMPLITUDE_GATE": amplitude_gate,
            "ONSET_SHARPNESS_GATE": sharpness_gate,
            "CLUSTER_OVERLAPPING_ONSETS": cluster_enabled,
            "ONSET_CLUSTER_WINDOW_MS": cluster_window_ms,
            "ONSET_REFINE_ENABLED": refine_enabled,
            "ONSET_REFINE_WINDOW_MS": refine_window_ms,
        })

        method, detector_kwargs = _build_region_detector_kwargs(effective)
        best_times: np.ndarray = np.array([], dtype=float)
        methods_with_delta = {"librosa", "superflux"}

        if method in methods_with_delta and n_requested > 0:
            delta = float(effective.get("ONSET_DELTA", initial_delta))
            for _ in range(12):
                if _is_cancelled():
                    return []
                detector_kwargs["delta"] = delta
                times = np.array(detect_onsets(method, y_slice, sr, **detector_kwargs), dtype=float)
                if len(times) >= n_requested:
                    best_times = times
                    break
                if len(times) > len(best_times):
                    best_times = times
                delta *= 0.65
        else:
            if _is_cancelled():
                return []
            best_times = np.array(detect_onsets(method, y_slice, sr, **detector_kwargs), dtype=float)

        if _is_cancelled() or len(best_times) == 0:
            return []

        if n_requested > 0 and len(best_times) > n_requested:
            # Pick the N with the strongest onset strengths
            env = librosa.onset.onset_strength(
                y=y_slice,
                sr=sr,
                hop_length=int(effective.get("ONSET_HOP_LENGTH", hop_length)),
            )
            hop = int(effective.get("ONSET_HOP_LENGTH", hop_length))
            strengths = []
            for t in best_times:
                frame_idx = int(t * sr / hop)
                frame_idx = min(frame_idx, len(env) - 1)
                strengths.append(env[frame_idx])
            strengths = np.array(strengths)
            top_indices = np.argsort(strengths)[-n_requested:]
            top_indices.sort()
            best_times = best_times[top_indices]

        if _is_cancelled():
            return []

        # ── Post-processing (same order as main Onset Finder pipeline) ──

        # 1. Refinement to sample accuracy
        if effective.get("ONSET_REFINE_ENABLED", refine_enabled) and len(best_times) > 0:
            best_times = refine_onsets_to_sample(
                best_times,
                y_slice,
                sr,
                window_ms=float(effective.get("ONSET_REFINE_WINDOW_MS", refine_window_ms)),
                energy_gate=float(effective.get("ONSET_REFINE_ENERGY_GATE", 0.0)),
            )

        # 2. Clustering
        if effective.get("CLUSTER_OVERLAPPING_ONSETS", cluster_enabled) and len(best_times) > 0:
            best_times = cluster_onsets(
                best_times,
                int(effective.get("ONSET_CLUSTER_WINDOW_MS", cluster_window_ms)),
            )

        # 3. Min inter-onset interval
        if int(effective.get("MIN_INTER_ONSET_MS", min_ioi_ms)) > 0 and len(best_times) > 0:
            best_times = enforce_min_interval(
                best_times,
                int(effective.get("MIN_INTER_ONSET_MS", min_ioi_ms)),
            )

        # 4. Amplitude gate
        if float(effective.get("ONSET_AMPLITUDE_GATE", amplitude_gate)) > 0 and len(best_times) > 0:
            best_times = gate_onsets_by_amplitude(
                best_times,
                y_slice,
                sr,
                float(effective.get("ONSET_AMPLITUDE_GATE", amplitude_gate)),
                window_ms=float(effective.get("ONSET_AMPLITUDE_WINDOW_MS", 50)),
            )

        # 5. Sharpness gate
        if float(effective.get("ONSET_SHARPNESS_GATE", sharpness_gate)) > 0 and len(best_times) > 0:
            best_times = gate_onsets_by_sharpness(
                best_times,
                y_slice,
                sr,
                float(effective.get("ONSET_SHARPNESS_GATE", sharpness_gate)),
                window_ms=float(effective.get("ONSET_SHARPNESS_WINDOW_MS", 20)),
            )

        # 6. Spectral matching (when focus-signal profile is available)
        if signal_profile is not None and len(best_times) > 0:
            focus_regions = signal_profile.get("regions", [])
            if not focus_regions:
                focus_regions = signal_profile.get("positive_regions", [])
            # Ensure every region has a polarity key so that
            # build_spectral_profile (which filters for "positive") works.
            for _r in focus_regions:
                _r.setdefault("polarity", "positive")
            # Build a spectral template from the positive region data
            spect_profile = build_spectral_profile(
                y_slice, sr, focus_regions) if focus_regions else None
            if spect_profile is not None:
                # Use per-signal threshold if provided, else default 0.3
                spect_threshold = float(
                    effective.get("_spectral_match_threshold", 0.3))
                best_times = gate_onsets_by_spectral_match(
                    best_times, y_slice, sr, spect_profile,
                    threshold=spect_threshold,
                )

        # 7. Per-variable upper/lower bound gating
        per_var_cfg = effective.get("_per_signal_config")
        if per_var_cfg is not None and signal_profile is not None and len(best_times) > 0:
            focus_regions = signal_profile.get("regions", [])
            if not focus_regions:
                focus_regions = signal_profile.get("positive_regions", [])
            if focus_regions:
                # Use the first region's analysis dict — it has all variable
                # keys (peak_frequency_hz, duration_s, etc.) unlike the
                # summary which may rename or omit some.
                ref_region = focus_regions[0]
                ref_analysis = ref_region  # analyze_region output IS the region dict
                if ref_analysis:
                    score_threshold = float(
                        effective.get(
                            "_per_signal_variable_score_threshold",
                            _compute_per_signal_variable_score_threshold(per_var_cfg),
                        )
                    )
                    scored = _score_onsets_by_variable_match(
                        best_times, y_slice, sr,
                        ref_analysis, per_var_cfg, ref_region,
                    )
                    best_times = np.array(
                        [item["time"] for item in scored if item["score"] >= score_threshold],
                        dtype=float,
                    )

        return best_times.tolist() if len(best_times) > 0 else []

    # ──────────────────────────────────────────────────────────────────────
    # Edit audio in region
    # ──────────────────────────────────────────────────────────────────────

    def _edit_audio_in_region(self):
        """Open Quick Audio Editor and apply processing to a range or full clip."""
        if self._viewer is None or self._viewer.audioData is None:
            QMessageBox.warning(self, "No Audio", "Load an audio file first.")
            return

        locked_range = self._get_focus_locked_time_range()
        if self._focus_mode and locked_range is None:
            QMessageBox.information(
                self,
                "Select Focus Region",
                "Focus Onsets mode is active. Select a focus region first to run Quick Audio Editor within that region.",
            )
            return

        default_start, default_end = locked_range or self._get_processable_time_range()
        duration = self._get_audio_duration()

        dlg = _EditAudioDialog(
            default_start,
            default_end,
            duration,
            selection_available=self._selected_region is not None,
            locked_range=locked_range,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        cfg = dlg.get_config()
        start, end = dlg.selected_range()
        if end - start < 0.01:
            QMessageBox.warning(
                self,
                "Range Too Small",
                "The chosen time range is too short.",
            )
            return

        y = self._viewer.audioData
        sr = self._viewer.sampleRate
        i_start = max(0, int(start * sr))
        i_end = min(len(y), int(end * sr))
        y_slice = y[i_start:i_end].copy()

        if len(y_slice) < sr * 0.01:
            QMessageBox.warning(
                self,
                "Too Short",
                "The chosen audio range is too short for editing.",
            )
            return

        # Import and run the Audio Editor processing chain
        try:
            import sys, os as _os
            _scripts_dir = _os.path.join(
                _os.path.dirname(_os.path.dirname(__file__)), "scripts")
            if _scripts_dir not in sys.path:
                sys.path.insert(0, _scripts_dir)
            from audio_editor import process_signal
        except ImportError:
            QMessageBox.critical(
                self, "Import Error",
                "Could not import audio_editor.process_signal.\n"
                "Make sure the scripts/ folder is accessible.")
            return

        try:
            y_edited = process_signal(y_slice, sr, cfg)
        except Exception as exc:
            QMessageBox.critical(
                self, "Processing Error",
                f"Audio editing failed:\n{exc}")
            return

        # Replace the region in the full audio array
        y_new = y.copy()
        # process_signal may trim or change length; fit edited into region
        edit_len = len(y_edited)
        region_len = i_end - i_start
        if edit_len >= region_len:
            y_new[i_start:i_end] = y_edited[:region_len]
        else:
            # If trimmed shorter, paste what we have and zero-pad
            y_new[i_start:i_start + edit_len] = y_edited
            y_new[i_start + edit_len:i_end] = 0.0

        # Crossfade at boundaries to avoid clicks (2 ms fade)
        fade_samples = min(int(sr * 0.002), region_len // 4)
        if fade_samples > 1:
            fade_in = np.linspace(0, 1, fade_samples, dtype=np.float32)
            fade_out = np.linspace(1, 0, fade_samples, dtype=np.float32)
            # Blend original → edited at start boundary
            y_new[i_start:i_start + fade_samples] = (
                y[i_start:i_start + fade_samples] * fade_out
                + y_new[i_start:i_start + fade_samples] * fade_in)
            # Blend edited → original at end boundary
            blend_start = i_end - fade_samples
            y_new[blend_start:i_end] = (
                y_new[blend_start:i_end] * fade_out
                + y[blend_start:i_end] * fade_in)

        # Update the viewer's audio data and refresh display
        self._viewer.audioData = y_new
        self._viewer._plot_waveform()
        self._viewer._plot_spectrogram()
        self._refresh_viewer_markers()

        scope = "full clip" if dlg.using_full_clip() else f"{start:.3f}s – {end:.3f}s"
        self._status_label.setText(f"Audio edited: {scope}")

        # Don't clear the selection so user can audition the result
        self._play_sel_btn.setEnabled(True)
        self._loop_sel_btn.setEnabled(True)

    # ──────────────────────────────────────────────────────────────────────
    # MFCC audio cleaning
    # ──────────────────────────────────────────────────────────────────────

    def _run_mfcc_audio_cleaning(self):
        """Open the MFCC Audio Edit dialog and apply template-matching cleaning."""
        if self._viewer is None or self._viewer.audioData is None:
            QMessageBox.warning(self, "No Audio", "Load an audio file first.")
            return

        # Gather positive focus regions for the current file
        fname = os.path.basename(self._audio_path) if self._audio_path else ""
        all_regions = list(self._focus_regions.get(fname, []))
        positive_regions = [r for r in all_regions if r.get("polarity") == "positive"]

        sel_range = self._selected_region  # None or (start, end) in seconds
        duration = self._get_audio_duration()

        dlg = _MfccAudioEditDialog(
            positive_regions,
            selection_range=sel_range,
            duration=duration,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected_indices = dlg.selected_region_indices()
        if not selected_indices:
            QMessageBox.information(
                self,
                "No Templates Selected",
                "Select at least one positive focus region to use as a template.",
            )
            return

        threshold_pct = dlg.threshold_percentile()
        smooth_ms = dlg.smooth_ms()
        n_mfcc = dlg.n_mfcc()
        use_full = dlg.use_full_clip()

        y = self._viewer.audioData
        sr = self._viewer.sampleRate

        # Determine the audio range to process
        if use_full or sel_range is None:
            proc_start, proc_end = 0.0, duration
        else:
            proc_start, proc_end = float(sel_range[0]), float(sel_range[1])

        i_start = max(0, int(proc_start * sr))
        i_end = min(len(y), int(proc_end * sr))
        y_slice = y[i_start:i_end].copy()

        if len(y_slice) < sr * 0.05:
            QMessageBox.warning(
                self,
                "Range Too Short",
                "The chosen audio range is too short for MFCC analysis.",
            )
            return

        # Extract template audio from the selected positive regions
        templates: list[np.ndarray] = []
        for idx in selected_indices:
            r = positive_regions[idx]
            t0 = float(r.get("t_start", 0.0))
            t1 = float(r.get("t_end", t0))
            s0 = max(0, int(t0 * sr))
            s1 = min(len(y), int(t1 * sr))
            if s1 > s0:
                templates.append(y[s0:s1].copy())

        if not templates:
            QMessageBox.warning(
                self,
                "Empty Templates",
                "The selected focus regions contain no audio samples.  "
                "Make sure the regions overlap the loaded audio.",
            )
            return

        # Import the cleaner script
        try:
            import sys as _sys
            _project_root = os.path.dirname(os.path.dirname(__file__))
            if _project_root not in _sys.path:
                _sys.path.insert(0, _project_root)
            from analysis.mfcc_template import clean_audio_with_mfcc_template
        except ImportError as exc:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Could not import shared MFCC analysis module:\n{exc}\n\n"
                "Make sure analysis/mfcc_template.py exists and "
                "librosa + scipy are installed.",
            )
            return

        # Show progress before the computation (MFCC can take several seconds
        # on long clips).  Force a repaint so the label is visible immediately.
        scope_str = "full clip" if use_full else f"{proc_start:.3f}s – {proc_end:.3f}s"
        n_templates = len(templates)
        self._status_label.setText(
            f"⏳  Running MFCC cleaning ({scope_str}, "
            f"{n_templates} template(s), threshold {threshold_pct:.0f}%) …"
        )
        self._mfcc_audio_btn.setEnabled(False)
        QApplication.processEvents()

        # Run the cleaning synchronously (usually < 5 s for typical field recordings)
        try:
            y_cleaned_slice = clean_audio_with_mfcc_template(
                y_slice,
                sr,
                templates,
                threshold_percentile=threshold_pct,
                smooth_ms=smooth_ms,
                n_mfcc=n_mfcc,
            )
        except Exception as exc:
            self._mfcc_audio_btn.setEnabled(True)
            self._status_label.setText("MFCC cleaning failed — see error dialog.")
            QMessageBox.critical(
                self,
                "MFCC Cleaning Error",
                f"MFCC audio cleaning failed:\n{exc}",
            )
            return
        finally:
            self._mfcc_audio_btn.setEnabled(self._audio_path is not None)

        # Splice the cleaned slice back into the full audio array
        y_new = y.copy()
        cleaned_len = len(y_cleaned_slice)
        region_len = i_end - i_start
        if cleaned_len >= region_len:
            y_new[i_start:i_end] = y_cleaned_slice[:region_len]
        else:
            y_new[i_start:i_start + cleaned_len] = y_cleaned_slice
            y_new[i_start + cleaned_len:i_end] = 0.0

        # Update viewer audio and refresh waveform + spectrogram
        # (audioData has a setter that writes directly to _y, so the plots
        # will now reflect the cleaned data)
        self._viewer.audioData = y_new
        self._viewer._plot_waveform()
        self._viewer._plot_spectrogram()
        self._refresh_viewer_markers()

        self._status_label.setText(
            f"✅  MFCC cleaning applied — {scope_str}, "
            f"{n_templates} template(s), threshold {threshold_pct:.0f}%"
        )
        self._play_sel_btn.setEnabled(True)
        self._loop_sel_btn.setEnabled(True)

    # ──────────────────────────────────────────────────────────────────────
    # Label comparison
    # ──────────────────────────────────────────────────────────────────────

    _COLOR_MAIN_ONLY = (100, 181, 246, 220)     # blue
    _COLOR_SHARED = (102, 187, 106, 220)        # green
    # comparison-only colors use the per-file palette

    def _classify_onsets(self):
        """Classify main + comparison onsets as shared / unique.

        Returns (main_only, shared_main, comp_only_per_file) where:
            main_only: set of indices into self._onset_times
            shared_main: set of indices into self._onset_times
            comp_only_per_file: list of lists of float (times unique to each comp file)
        """
        result = _classify_comparison_onsets_impl(
            self._onset_times,
            self._comp_files,
            self._comp_tolerance_ms,
        )
        return (
            result["main_only"],
            result["shared_main"],
            result["comp_only_per_file"],
        )

    def _refresh_comparison_display(self):
        """Recolor main markers and show/hide comparison overlays based on
        the current filter and tolerance settings."""
        if self._viewer is None:
            return

        # Clear comparison overlay
        self._clear_comparison_markers()

        if not self._comp_files:
            # No comparison files — reset main markers to default color
            self._refresh_viewer_markers()
            return

        main_only, shared_main, comp_only_per_file = self._classify_onsets()
        filt = self._comp_filter_idx
        display_state = _build_comparison_display_state_impl(
            self._onset_times,
            self._comp_files,
            filt,
            main_only=main_only,
            shared_main=shared_main,
            comp_only_per_file=comp_only_per_file,
            main_only_color=self._COLOR_MAIN_ONLY,
            shared_color=self._COLOR_SHARED,
            comparison_style=Qt.PenStyle.DashLine,
        )

        # Update main onset markers with colors
        self._updating_viewer = True
        self._viewer.clear_onset_markers()
        if display_state["visible_main_times"]:
            self._viewer.set_onset_markers(
                display_state["visible_main_times"],
                colors=display_state["visible_main_colors"],
                draggable=self._edit_onsets_btn.isChecked(),
            )
        self._updating_viewer = False

        # Show comparison-only overlays
        if display_state["comparison_layers"]:
            self._viewer.set_comparison_markers(display_state["comparison_layers"])

        # Update stats in status label
        self._status_label.setText(display_state["status_text"])

    def _comp_add_shared_to_main(self):
        """Add comparison onsets that match within tolerance to the main list
        (skips those already present within 1ms)."""
        if not self._comp_files:
            return
        updated_onsets, added = _add_shared_comparison_onsets_impl(
            self._onset_times,
            self._comp_files,
            self._comp_tolerance_ms,
        )
        if added:
            self._onset_times[:] = updated_onsets
            self._push_undo()
            self._refresh_table()
            self._refresh_comparison_display()
            self._status_label.setText(f"Added {added} shared onset(s) to Main")
        else:
            self._status_label.setText("No new shared onsets to add")

    def _comp_add_unique_to_main(self):
        """Add comparison-only onsets (unique to comparison files) to Main."""
        if not self._comp_files:
            return
        _, _, comp_only_per_file = self._classify_onsets()
        updated_onsets, added = _add_unique_comparison_onsets_impl(
            self._onset_times,
            comp_only_per_file,
        )
        if added:
            self._onset_times[:] = updated_onsets
            self._push_undo()
            self._refresh_table()
            self._refresh_comparison_display()
            self._status_label.setText(
                f"Added {added} comparison-unique onset(s) to Main")
        else:
            self._status_label.setText("No new unique onsets to add")

    def _comp_remove_main_only(self):
        """Remove onsets unique to Main (not confirmed by any comparison file)."""
        if not self._comp_files:
            return
        main_only, _, _ = self._classify_onsets()
        if not main_only:
            self._status_label.setText("No main-only onsets to remove")
            return
        reply = QMessageBox.question(
            self, "Remove Main-Only Onsets",
            f"Remove {len(main_only)} onset(s) that are NOT confirmed "
            f"by any comparison file?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        updated_onsets, removed = _remove_main_only_onsets_impl(
            self._onset_times,
            main_only,
        )
        self._onset_times[:] = updated_onsets
        self._push_undo()
        self._refresh_table()
        self._refresh_comparison_display()
        self._status_label.setText(
            f"Removed {removed} main-only onset(s)")

    # ──────────────────────────────────────────────────────────────────────
    # Review mode (post-pipeline batch confirmation)
    # ──────────────────────────────────────────────────────────────────────

    def start_review(self, folder: str):
        """Enter review mode — load all audio files in *folder* for sequential
        confirmation.  Called automatically by the pipeline GUI after the
        Onset Finder finishes when the Onset Editor step is enabled."""
        if not os.path.isdir(folder):
            return
        self._review_folder = folder
        self._folder_edit.setText(folder)
        self._populate_files(folder)

        # Include all audio files (those without labels will show empty table).
        self._review_files = _review_audio_paths(folder)
        if not self._review_files:
            QMessageBox.information(
                self, "No Files",
                f"No audio files found in:\n{folder}")
            return

        self._apply_review_start_state(self._review_files)

    def _apply_review_start_state(self, review_files: list[str]):
        """Apply review-mode state and load the first file in sequence."""
        self._review_files = list(review_files)
        self._review_mode = True
        self._review_index = 0
        self._review_bar.show()
        self._load_review_file(0)

    def _apply_loaded_review_session(
        self,
        audio_path: str,
        label_path: str | None,
        loaded_session: dict,
        *,
        refresh_review_ui: bool = False,
        refresh_button_states: bool = False,
        status_text: str | None = None,
    ):
        """Apply a loaded review-label session and refresh the requested UI state."""
        self._audio_path = audio_path
        self._label_path = label_path
        self._onset_times = loaded_session["onset_times"]
        self._undo_stack = loaded_session["undo_stack"]
        self._dirty = loaded_session["dirty"]

        if self._viewer is not None:
            self._viewer.load_audio(audio_path)
        self._refresh_viewer_markers()
        self._refresh_table()

        if refresh_review_ui:
            self._update_review_ui()
        if refresh_button_states:
            self._update_button_states()
        if status_text:
            self._status_label.setText(status_text)

    def _sync_review_file_combo(self, file_name: str):
        """Sync the file selector to the current review-mode file."""
        combo_idx = self._file_combo.findText(file_name)
        if combo_idx < 0:
            return
        self._file_combo.blockSignals(True)
        self._file_combo.setCurrentIndex(combo_idx)
        self._file_combo.blockSignals(False)

    def _load_review_file(self, index: int):
        """Load the review file at the given index."""
        if index < 0 or index >= len(self._review_files):
            return
        # Prompt save if dirty
        if self._dirty and self._audio_path:
            reply = self._prompt_save()
            if reply == QMessageBox.StandardButton.Cancel:
                return

        self._review_index = index
        audio_path = self._review_files[index]
        fname = os.path.basename(audio_path)

        self._sync_review_file_combo(fname)

        label_path, loaded_session = _load_saved_onset_session_for_audio(audio_path)
        self._apply_loaded_review_session(
            audio_path,
            label_path,
            loaded_session,
            refresh_review_ui=True,
            status_text=f"Review {index + 1}/{len(self._review_files)}: {fname}",
        )

    def _update_review_ui(self):
        """Update review bar button states and counter."""
        navigation_state = _summarize_review_navigation_state_impl(
            len(self._review_files),
            self._review_index,
        )
        self._review_counter.setText(navigation_state["counter_text"])
        self._review_prev_btn.setEnabled(navigation_state["prev_enabled"])
        self._review_next_btn.setEnabled(navigation_state["next_enabled"])
        self._review_save_next_btn.setEnabled(navigation_state["save_next_enabled"])

    def _review_prev(self):
        """Go to the previous file in review mode."""
        if self._review_index > 0:
            self._load_review_file(self._review_index - 1)

    def _review_next(self):
        """Go to the next file in review mode."""
        if self._review_index < len(self._review_files) - 1:
            self._load_review_file(self._review_index + 1)

    def _review_save_current(self):
        """Save both label file and Excel for the current file."""
        self._save_labels()
        self._save_to_excel()

    def _review_save_and_next(self):
        """Save both, then advance to the next file."""
        self._review_save_current()
        self._review_next()

    def _review_revert(self):
        """Reload the original label file, discarding any edits."""
        if not self._audio_path:
            return
        label_path, loaded_session = _load_saved_onset_session_for_audio(self._audio_path)
        self._apply_loaded_review_session(
            self._audio_path,
            label_path,
            loaded_session,
            refresh_button_states=True,
            status_text=f"Reverted to saved labels for {os.path.basename(self._audio_path)}",
        )

    def _apply_review_finish_state(self, finish_state: dict):
        """Apply the finalized review-mode reset state to the panel widgets."""
        self._review_mode = finish_state["review_mode"]
        self._review_files = finish_state["review_files"]
        self._review_index = finish_state["review_index"]
        self._review_bar.hide()
        self._status_label.setText(finish_state["status_text"])

    def _review_finish(self):
        """Exit review mode."""
        finish_state = _summarize_review_finish_state_impl(self._dirty, self._audio_path)
        if finish_state["require_save_prompt"]:
            reply = self._prompt_save(prompt_text=finish_state["prompt_text"])
            if reply == QMessageBox.StandardButton.Cancel:
                return

        self._apply_review_finish_state(finish_state)

    # ──────────────────────────────────────────────────────────────────────
    # Public API (for integration with pipeline_gui.py)
    # ──────────────────────────────────────────────────────────────────────

    def set_folder(self, folder: str):
        """Programmatically set the audio folder (respects auto-set checkbox)."""
        if not self._folder_auto_cb.isChecked():
            return
        self._folder_edit.setText(folder)
        self._populate_files(folder)

    def get_values(self) -> dict:
        """Return current state as a dict (for config persistence)."""
        self._save_layer_state()
        return _build_panel_config_snapshot_impl(
            folder=self._folder_edit.text(),
            file_name=self._file_combo.currentText(),
            folder_auto=self._folder_auto_cb.isChecked(),
            onset_auto=self._onset_auto_cb.isChecked(),
            onset_source=self._onset_source,
            excel_onset_path=self._excel_onset_path,
            excel_onset_col=self._excel_onset_col,
            excel_filename_col=self._excel_filename_col,
            excel_sheet_name=self._excel_sheet_name,
            focus_mode=self._focus_mode,
            focus_polarity=self._focus_polarity,
            active_layer_idx=self._active_layer_idx,
            layers=self._layers,
        )

    def _refresh_restored_layer_widgets(self):
        """Rebuild layer combo state and signal browser after layer restores."""
        if hasattr(self, '_layer_combo'):
            self._layer_combo.blockSignals(True)
            self._layer_combo.clear()
            for lyr in self._layers:
                self._layer_combo.addItem(lyr["name"])
            self._layer_combo.setCurrentIndex(self._active_layer_idx)
            self._layer_combo.blockSignals(False)
        if hasattr(self, '_signal_browser_combo'):
            self._refresh_signal_browser_combo()

    def _append_layer_names_to_combo(
        self,
        layer_names: list[str],
        *,
        block_signals: bool = False,
    ):
        """Append one or more layer names to the hidden compatibility combo."""
        if not hasattr(self, '_layer_combo') or not layer_names:
            return
        if block_signals:
            self._layer_combo.blockSignals(True)
        for layer_name in layer_names:
            self._layer_combo.addItem(layer_name)
        if block_signals:
            self._layer_combo.blockSignals(False)

    def _apply_active_focus_region_widgets(self, *, refresh_signal_browser: bool = False):
        """Refresh focus-region dependent widgets for the current active layer."""
        if self._focus_mode:
            self._refresh_focus_regions_in_viewer()
        self._update_button_states()
        if refresh_signal_browser and hasattr(self, '_signal_browser_combo'):
            self._refresh_signal_browser_combo()

    def _apply_focus_region_status_widgets(
        self,
        status_text: str,
        *,
        refresh_signal_browser: bool = True,
    ):
        """Update status text and dependent widgets after focus-region edits."""
        self._status_label.setText(status_text)
        self._update_button_states()
        if refresh_signal_browser and hasattr(self, '_signal_browser_combo'):
            self._refresh_signal_browser_combo()

    def _apply_new_layer_range_activation(self, activation: dict, first_new_idx: int):
        """Apply a checked-layer activation result and sync the compatibility combo."""
        self._checked_layer_indices = activation["checked_layer_indices"]
        self._active_layer_idx = activation["active_layer_idx"]
        self._load_layer_state()
        self._set_layer_combo_index(first_new_idx)
        self._refresh_layer_menu_widgets()

    def _set_layer_combo_index(self, index: int):
        """Update the hidden compatibility combo without firing its change handler."""
        if not hasattr(self, '_layer_combo'):
            return
        self._layer_combo.blockSignals(True)
        self._layer_combo.setCurrentIndex(index)
        self._layer_combo.blockSignals(False)

    def _refresh_layer_structure_widgets(self):
        """Refresh shared layer-structure UI after layer add/remove/reset changes."""
        self._refresh_layer_menu_widgets()
        self._refresh_layer_data_views()

    def _refresh_layer_data_views(self):
        """Refresh the shared viewer markers and onset table for layer data changes."""
        self._refresh_viewer_markers()
        self._refresh_table()

    def _refresh_layer_overlay_widgets(self):
        """Refresh derived layer overlays after layer-state mutations."""
        self._push_layer_info_to_viewer()
        self._refresh_layer_overlays()

    def _clear_comparison_markers(self):
        """Clear comparison markers when the viewer is available."""
        if self._viewer is None:
            return
        self._viewer.clear_comparison_markers()

    def _get_checked_layer_indices(self) -> list[int]:
        """Return the currently checked layer indices when the layer menu exists."""
        if not hasattr(self, '_layer_menu') or self._layer_menu is None:
            return []
        return self._layer_menu.get_checked_indices()

    def _refresh_layer_menu_widgets(self):
        """Rebuild the layer menu when the layer-menu widget exists."""
        if hasattr(self, '_layer_menu') and self._layer_menu is not None:
            self._rebuild_layer_menu()

    def _apply_scalar_restore_values(self, restore_values: dict):
        """Apply scalar config values restored from persisted panel state."""
        if restore_values["folder_auto"] is not None:
            self._folder_auto_cb.setChecked(restore_values["folder_auto"])
        if restore_values["onset_auto"] is not None:
            self._onset_auto_cb.setChecked(restore_values["onset_auto"])
        if restore_values["onset_source"] is not None:
            self._onset_source = restore_values["onset_source"]
        if restore_values["excel_onset_path"] is not None:
            self._excel_onset_path = restore_values["excel_onset_path"]
        if restore_values["excel_onset_col"] is not None:
            self._excel_onset_col = restore_values["excel_onset_col"]
        if restore_values["excel_filename_col"] is not None:
            self._excel_filename_col = restore_values["excel_filename_col"]
        if restore_values["excel_sheet_name"] is not None:
            self._excel_sheet_name = restore_values["excel_sheet_name"]

    def _apply_restored_file_selection_widgets(
        self,
        folder: str,
        restored_files: list[str],
        restored_idx: int,
    ):
        """Apply restored folder and file combo state for config reloads."""
        self._folder_edit.setText(folder)
        self._file_combo.blockSignals(True)
        self._file_combo.clear()
        if restored_files:
            self._file_combo.addItems(restored_files)
        self._file_combo.blockSignals(False)
        if restored_idx >= 0:
            self._file_combo.setCurrentIndex(restored_idx)
            self._on_file_selected(restored_idx)

    def _apply_restored_layer_state(self, restored_layers: dict):
        """Apply restored layer data and reload the active live layer state."""
        self._layers = restored_layers["layers"]
        self._active_layer_idx = restored_layers["active_layer_idx"]
        self._load_layer_state()
        self._refresh_restored_layer_widgets()

    def _apply_focus_restore_widgets(self, focus_restore_state: dict):
        """Apply restored focus polarity and focus-mode widget state."""
        if focus_restore_state["focus_polarity"] is not None:
            self._focus_polarity = focus_restore_state["focus_polarity"]
            if hasattr(self, '_positive_btn'):
                self._positive_btn.blockSignals(True)
                self._negative_btn.blockSignals(True)
                self._positive_btn.setChecked(focus_restore_state["positive_checked"])
                self._negative_btn.setChecked(focus_restore_state["negative_checked"])
                self._positive_btn.blockSignals(False)
                self._negative_btn.blockSignals(False)
        # Focus mode always starts OFF to avoid stale controls state.
        if hasattr(self, '_focus_onsets_btn'):
            self._focus_onsets_btn.setChecked(focus_restore_state["focus_mode_enabled"])

    def _refresh_active_layer_focus_widgets(
        self,
        *,
        refresh_signal_browser: bool = False,
        push_layer_info: bool = False,
    ):
        """Refresh focus-driven widgets for the current active layer."""
        self._apply_active_focus_region_widgets(
            refresh_signal_browser=refresh_signal_browser
        )
        if push_layer_info:
            self._push_layer_info_to_viewer()

    def _refresh_post_layer_change_widgets(self, refresh_signal_browser: bool = False):
        """Refresh focus-driven and overlay-driven UI after a layer mutation."""
        self._refresh_active_layer_focus_widgets(
            refresh_signal_browser=refresh_signal_browser
        )
        self._refresh_layer_overlay_widgets()

    def _refresh_structural_layer_mutation_widgets(
        self,
        refresh_signal_browser: bool = False,
    ):
        """Refresh UI after a layer add/remove style structural mutation."""
        self._refresh_layer_structure_widgets()
        self._refresh_post_layer_change_widgets(
            refresh_signal_browser=refresh_signal_browser
        )

    def _refresh_layer_selection_widgets(self, *, update_buttons: bool = False):
        """Refresh layer-selection overlays and optionally button state."""
        self._refresh_layer_overlays()
        if update_buttons:
            self._update_button_states()

    def _set_merge_selection_enabled(self, enabled: bool):
        """Sync the merge-selected button state when the widget exists."""
        if hasattr(self, '_merge_sel_btn'):
            self._merge_sel_btn.setEnabled(enabled)

    def _apply_checked_layer_selection(self, selection: dict):
        """Apply a checked-layer selection summary to the current panel UI."""
        primary_idx = selection["primary_layer_idx"]
        if primary_idx is None:
            self._clear_comparison_markers()
            self._set_merge_selection_enabled(selection["merge_enabled"])
            return

        if primary_idx != self._active_layer_idx:
            self._switch_layer(primary_idx)

        self._refresh_layer_selection_widgets()
        self._set_merge_selection_enabled(selection["merge_enabled"])

    def _activate_exclusive_layer(
        self,
        index: int,
        *,
        update_buttons: bool = False,
    ) -> bool:
        """Switch to a single checked layer and refresh merge-related layer UI."""
        selection = _select_exclusive_layer_impl(index, len(self._layers))
        if selection is None:
            return False
        self._checked_layer_indices = selection["checked_layer_indices"]
        primary_idx = selection["primary_layer_idx"]
        if primary_idx is None:
            return False
        switched = primary_idx != self._active_layer_idx
        if switched:
            self._switch_layer(primary_idx)
        self._refresh_layer_menu_widgets()
        self._refresh_layer_selection_widgets(update_buttons=update_buttons)
        return True

    def set_values(self, vals: dict):
        """Restore state from a config dict."""
        restore_values = _extract_scalar_config_restore_values_impl(vals)
        focus_restore_state = _summarize_focus_restore_state_impl(
            restore_values["focus_polarity"]
        )
        self._apply_scalar_restore_values(restore_values)
        folder_exists, restored_files, restored_idx = _resolve_restored_file_selection(
            restore_values["folder"],
            restore_values["file_name"],
        )
        if folder_exists:
            self._apply_restored_file_selection_widgets(
                restore_values["folder"],
                restored_files,
                restored_idx,
            )
        # Restore layers
        layers_data = vals.get("layers", [])
        restored_layers = _restore_configured_layers_impl(
            layers_data,
            vals.get("active_layer_idx", 0),
        )
        if restored_layers is not None:
            self._apply_restored_layer_state(restored_layers)
        self._apply_focus_restore_widgets(focus_restore_state)
