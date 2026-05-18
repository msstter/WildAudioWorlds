"""Layer/session state helpers for the onset editor workbench."""

from __future__ import annotations

import os

from typing import Optional, TypedDict


class _UndoStack:
    """Simple undo/redo stack storing snapshots of onset time lists."""

    def __init__(self, max_depth: int = 50):
        self._stack: list[list[float]] = []
        self._redo: list[list[float]] = []
        self._max = max_depth

    def push(self, state: list[float]):
        self._stack.append(list(state))
        if len(self._stack) > self._max:
            self._stack.pop(0)
        self._redo.clear()

    def undo(self) -> Optional[list[float]]:
        if len(self._stack) < 2:
            return None
        self._redo.append(self._stack.pop())
        return list(self._stack[-1])

    def redo(self) -> Optional[list[float]]:
        if not self._redo:
            return None
        state = self._redo.pop()
        self._stack.append(state)
        return list(state)

    def can_undo(self) -> bool:
        return len(self._stack) >= 2

    def can_redo(self) -> bool:
        return len(self._redo) > 0

    def clear(self):
        self._stack.clear()
        self._redo.clear()


class OnsetLayerState(TypedDict):
    name: str
    onset_times: list[float]
    focus_regions: dict[str, list[dict]]
    undo_stack: _UndoStack
    dirty: bool


class FocusRegionTransferResult(TypedDict):
    target_layer_idx: int
    target_name: str
    polarity: str
    created_layer: bool
    removed_from_source: bool

class LayerRemovalResult(TypedDict):
    removed_name: str
    active_layer_idx: int
    checked_layer_indices: set[int]

class FileLayerResetResult(TypedDict):
    layers: list[OnsetLayerState]
    active_layer_idx: int
    checked_layer_indices: set[int]


class LoadedOnsetSessionResult(TypedDict):
    onset_times: list[float]
    undo_stack: _UndoStack
    dirty: bool


class SaveSelectionsExportPlanResult(TypedDict):
    positive_output_dir: str
    negative_output_dir: str
    individual_mode: bool
    bandpass_enabled: bool
    layers_to_export: list[tuple[int, OnsetLayerState]]


class RestoredLoadedFocusRegionsResult(TypedDict):
    created_layer_names: list[str]
    focus_regions: dict[str, list[dict]]


class RestoredLayerConfigResult(TypedDict):
    layers: list[OnsetLayerState]
    active_layer_idx: int


class ScalarConfigRestoreResult(TypedDict):
    folder_auto: bool | None
    onset_auto: bool | None
    onset_source: str | None
    excel_onset_path: str | None
    excel_onset_col: object | None
    excel_filename_col: object | None
    excel_sheet_name: object | None
    folder: str
    file_name: str
    focus_polarity: str | None


class FocusRestoreStateResult(TypedDict):
    focus_polarity: str | None
    positive_checked: bool | None
    negative_checked: bool | None
    focus_mode_enabled: bool


class LayerSwitchResult(TypedDict):
    active_layer_idx: int
    onset_times: list[float]
    focus_regions: dict[str, list[dict]]
    undo_stack: _UndoStack
    dirty: bool


class LayerSelectionChangeResult(TypedDict):
    checked_layer_indices: set[int]
    primary_layer_idx: int | None
    merge_enabled: bool


class LayerRangeActivationResult(TypedDict):
    active_layer_idx: int
    checked_layer_indices: set[int]


class ComparisonClassificationResult(TypedDict):
    main_only: set[int]
    shared_main: set[int]
    comp_only_per_file: list[list[float]]


class ComparisonDisplayState(TypedDict):
    visible_main_times: list[float]
    visible_main_colors: list[object]
    comparison_layers: list[dict]
    status_text: str


class ReviewNavigationStateResult(TypedDict):
    counter_text: str
    prev_enabled: bool
    next_enabled: bool
    save_next_enabled: bool


class ReviewFinishStateResult(TypedDict):
    require_save_prompt: bool
    prompt_text: str | None
    review_mode: bool
    review_files: list[str]
    review_index: int
    status_text: str


class FocusRegionStatusResult(TypedDict):
    positive_count: int
    negative_count: int
    status_text: str


class SaveSelectionsPreflightResult(TypedDict):
    can_open: bool
    regions: list[dict]
    info_title: str | None
    info_message: str | None


class LoadedSelectionsFeedbackResult(TypedDict):
    restored_regions: list[dict]
    geometry_restored: bool
    loaded_profile: dict | None
    status_text: str | None
    info_title: str | None
    info_message: str | None


def _copy_focus_regions(focus_regions: dict[str, list[dict]] | None) -> dict[str, list[dict]]:
    if not focus_regions:
        return {}
    return {
        file_name: [dict(region) for region in regions]
        for file_name, regions in focus_regions.items()
    }


def _build_undo_stack(initial_onsets: list[float] | None = None) -> _UndoStack:
    undo_stack = _UndoStack()
    undo_stack.push(list(initial_onsets or []))
    return undo_stack


def make_default_layer(name: str = "Layer 1") -> OnsetLayerState:
    """Return a fresh layer dict with empty state."""
    return {
        "name": name,
        "onset_times": [],
        "focus_regions": {},
        "undo_stack": _build_undo_stack(),
        "dirty": False,
    }


def hydrate_layer_state(
    name: str,
    *,
    onset_times: list[float] | None = None,
    focus_regions: dict[str, list[dict]] | None = None,
    undo_stack: _UndoStack | None = None,
    dirty: bool = False,
) -> OnsetLayerState:
    """Return a layer dict populated from persisted or live runtime state."""
    normalized_onsets = list(onset_times or [])
    return {
        "name": name,
        "onset_times": normalized_onsets,
        "focus_regions": _copy_focus_regions(focus_regions),
        "undo_stack": undo_stack if undo_stack is not None else _build_undo_stack(normalized_onsets),
        "dirty": bool(dirty),
    }


def save_layer_state(
    layers: list[OnsetLayerState],
    active_layer_idx: int,
    onset_times: list[float],
    focus_regions: dict[str, list[dict]],
    undo_stack: _UndoStack,
    dirty: bool,
):
    """Persist live onset-editor attributes back into the active layer dict."""
    layer = layers[active_layer_idx]
    layer["onset_times"] = onset_times
    layer["focus_regions"] = focus_regions
    layer["undo_stack"] = undo_stack
    layer["dirty"] = dirty


def load_layer_state(
    layers: list[OnsetLayerState],
    active_layer_idx: int,
) -> tuple[list[float], dict[str, list[dict]], _UndoStack, bool]:
    """Load the active layer dict into the panel's live attribute set."""
    layer = layers[active_layer_idx]
    return (
        layer["onset_times"],
        layer["focus_regions"],
        layer["undo_stack"],
        layer["dirty"],
    )


def build_loaded_onset_session(onset_times: list[float]) -> LoadedOnsetSessionResult:
    """Return fresh live session state for a newly loaded onset list."""
    normalized_onsets = [float(onset_time) for onset_time in onset_times]
    return {
        "onset_times": normalized_onsets,
        "undo_stack": _build_undo_stack(normalized_onsets),
        "dirty": False,
    }


def summarize_review_navigation_state(
    review_file_count: int,
    review_index: int,
) -> ReviewNavigationStateResult:
    """Return counter text and button enablement for review navigation."""
    count = max(int(review_file_count), 0)
    index = max(int(review_index), 0)
    counter_index = min(index + 1, count) if count else 0
    return {
        "counter_text": f"File {counter_index} / {count}",
        "prev_enabled": count > 0 and index > 0,
        "next_enabled": count > 0 and index < count - 1,
        "save_next_enabled": count > 0 and index < count - 1,
    }


def summarize_review_finish_state(
    dirty: bool,
    audio_path: str | None,
) -> ReviewFinishStateResult:
    """Return prompt metadata and reset state for finishing review mode."""
    normalized_path = str(audio_path) if audio_path else ""
    require_save_prompt = bool(dirty and normalized_path)
    prompt_text = None
    if require_save_prompt:
        prompt_text = (
            f"Save changes to {os.path.basename(normalized_path)} before finishing?"
        )
    return {
        "require_save_prompt": require_save_prompt,
        "prompt_text": prompt_text,
        "review_mode": False,
        "review_files": [],
        "review_index": 0,
        "status_text": "Review complete.",
    }


def summarize_focus_region_status(regions: list[dict]) -> FocusRegionStatusResult:
    """Return focus-region counts and the matching status-label text."""
    positive_count = sum(1 for region in regions if region.get("polarity") == "positive")
    negative_count = sum(1 for region in regions if region.get("polarity") == "negative")
    return {
        "positive_count": positive_count,
        "negative_count": negative_count,
        "status_text": (
            f"Focus regions: {positive_count} positive, {negative_count} negative"
        ),
    }


def summarize_save_selections_preflight(
    *,
    audio_path: str | None,
    viewer_available: bool,
    focus_regions: dict[str, list[dict]],
) -> SaveSelectionsPreflightResult:
    """Return whether the save-selections dialog can open and any user-facing feedback."""
    if not audio_path or not viewer_available:
        return {
            "can_open": False,
            "regions": [],
            "info_title": None,
            "info_message": None,
        }

    file_name = os.path.basename(audio_path)
    regions = list(focus_regions.get(file_name, []))
    if regions:
        return {
            "can_open": True,
            "regions": regions,
            "info_title": None,
            "info_message": None,
        }

    return {
        "can_open": False,
        "regions": [],
        "info_title": "No Regions",
        "info_message": "Draw positive/negative regions on the spectrogram first.",
    }


def summarize_loaded_selections_feedback(result: dict) -> LoadedSelectionsFeedbackResult:
    """Normalize loaded-selection restore results into one feedback payload."""
    restored_regions = list(result.get("regions", []))
    geometry_restored = bool(result.get("geometry_restored"))
    loaded_profile = result.get("profile")

    if geometry_restored:
        return {
            "restored_regions": restored_regions,
            "geometry_restored": True,
            "loaded_profile": loaded_profile,
            "status_text": (
                f"Loaded {len(restored_regions)} saved selection(s) onto the spectrogram"
            ),
            "info_title": None,
            "info_message": None,
        }

    if loaded_profile:
        return {
            "restored_regions": restored_regions,
            "geometry_restored": False,
            "loaded_profile": loaded_profile,
            "status_text": (
                "Loaded saved signal clips for settings recommendations; geometry metadata missing"
            ),
            "info_title": "Geometry Metadata Missing",
            "info_message": (
                "Cannot place selected signals back to Spectrogram due to missing .json file. "
                "The saved signal clips were still loaded and will be used for settings recommendations."
            ),
        }

    return {
        "restored_regions": restored_regions,
        "geometry_restored": False,
        "loaded_profile": loaded_profile,
        "status_text": None,
        "info_title": "No Saved Selections Found",
        "info_message": "No usable saved selections or metadata were found in the chosen folders.",
    }


def build_save_selections_export_plan(
    request: dict,
    *,
    layers: list[OnsetLayerState],
    active_layer_idx: int,
) -> SaveSelectionsExportPlanResult:
    """Return the normalized export plan for an accepted save-selections request."""
    export_all_layers = bool(request.get("export_all_layers"))
    if export_all_layers and len(layers) > 1:
        layers_to_export = list(enumerate(layers))
    else:
        layers_to_export = [(active_layer_idx, layers[active_layer_idx])]

    return {
        "positive_output_dir": request["positive_output_dir"],
        "negative_output_dir": request["negative_output_dir"],
        "individual_mode": bool(request["individual_mode"]),
        "bandpass_enabled": bool(request["bandpass_enabled"]),
        "layers_to_export": layers_to_export,
    }


def build_panel_config_snapshot(
    *,
    folder: str,
    file_name: str,
    folder_auto: bool,
    onset_auto: bool,
    onset_source: str,
    excel_onset_path: str | None,
    excel_onset_col,
    excel_filename_col,
    excel_sheet_name,
    focus_mode: bool,
    focus_polarity: str,
    active_layer_idx: int,
    layers: list[OnsetLayerState],
) -> dict:
    """Return the panel config payload used for persistence."""
    return {
        "folder": folder,
        "file": file_name,
        "folder_auto": bool(folder_auto),
        "onset_auto": bool(onset_auto),
        "onset_source": onset_source,
        "excel_onset_path": excel_onset_path or "",
        "excel_onset_col": excel_onset_col,
        "excel_filename_col": excel_filename_col,
        "excel_sheet_name": excel_sheet_name,
        "focus_mode": bool(focus_mode),
        "focus_polarity": focus_polarity,
        "active_layer_idx": int(active_layer_idx),
        "layers": serialize_layers(layers),
    }


def extract_scalar_config_restore_values(vals: dict) -> ScalarConfigRestoreResult:
    """Return the scalar config values that `set_values` restores."""
    focus_polarity = vals.get("focus_polarity")
    return {
        "folder_auto": vals["folder_auto"] if "folder_auto" in vals else None,
        "onset_auto": vals["onset_auto"] if "onset_auto" in vals else None,
        "onset_source": vals.get("onset_source") or None,
        "excel_onset_path": vals.get("excel_onset_path") or None,
        "excel_onset_col": vals.get("excel_onset_col") or None,
        "excel_filename_col": vals.get("excel_filename_col") or None,
        "excel_sheet_name": vals.get("excel_sheet_name") or None,
        "folder": vals.get("folder", ""),
        "file_name": vals.get("file", ""),
        "focus_polarity": (
            focus_polarity if focus_polarity in ("positive", "negative") else None
        ),
    }


def summarize_focus_restore_state(
    focus_polarity: str | None,
) -> FocusRestoreStateResult:
    """Describe the focus-control state to restore after loading config."""
    if focus_polarity not in ("positive", "negative"):
        return {
            "focus_polarity": None,
            "positive_checked": None,
            "negative_checked": None,
            "focus_mode_enabled": False,
        }
    return {
        "focus_polarity": focus_polarity,
        "positive_checked": focus_polarity == "positive",
        "negative_checked": focus_polarity == "negative",
        "focus_mode_enabled": False,
    }


def serialize_layers(layers: list[OnsetLayerState]) -> list[dict]:
    """Return a JSON-friendly snapshot of the current layer list."""
    return [
        {
            "name": layer["name"],
            "onset_times": list(layer["onset_times"]),
            "focus_regions": _copy_focus_regions(layer["focus_regions"]),
            "dirty": layer["dirty"],
        }
        for layer in layers
    ]


def deserialize_layers(layer_dicts: list[dict]) -> list[OnsetLayerState]:
    """Restore layer state dictionaries from config/persistence payloads."""
    return [
        hydrate_layer_state(
            layer_dict.get("name", f"Layer {index + 1}"),
            onset_times=layer_dict.get("onset_times", []),
            focus_regions=layer_dict.get("focus_regions", {}),
            dirty=layer_dict.get("dirty", False),
        )
        for index, layer_dict in enumerate(layer_dicts)
    ]


def restore_configured_layers(
    layer_dicts: list[dict],
    requested_active_layer_idx: int,
) -> RestoredLayerConfigResult | None:
    """Return restored layers and a clamped active index from config data."""
    if not layer_dicts:
        return None
    layers = deserialize_layers(layer_dicts)
    return {
        "layers": layers,
        "active_layer_idx": max(0, min(int(requested_active_layer_idx), len(layers) - 1)),
    }


def append_layer_state(
    layers: list[OnsetLayerState],
    *,
    layer_name: str,
    onset_times: list[float] | None = None,
    focus_regions: dict[str, list[dict]] | None = None,
    dirty: bool = False,
) -> int:
    """Append a new layer initialised from the provided state and return its index."""
    layers.append(
        hydrate_layer_state(
            layer_name,
            onset_times=onset_times,
            focus_regions=focus_regions,
            dirty=dirty,
        )
    )
    return len(layers) - 1

def append_empty_layer(layers: list[OnsetLayerState]) -> tuple[int, str]:
    """Append a default-named empty layer and return its index and name."""
    layer_name = f"Layer {len(layers) + 1}"
    return append_layer_state(layers, layer_name=layer_name), layer_name

def remove_active_layer(
    layers: list[OnsetLayerState],
    active_layer_idx: int,
    checked_layer_indices: set[int],
) -> LayerRemovalResult | None:
    """Remove the active layer and return the updated lifecycle state."""
    if len(layers) <= 1:
        return None

    removed_name = layers[active_layer_idx]["name"]
    layers.pop(active_layer_idx)

    new_checked: set[int] = set()
    for checked_idx in checked_layer_indices:
        if checked_idx == active_layer_idx:
            continue
        new_checked.add(checked_idx - 1 if checked_idx > active_layer_idx else checked_idx)

    new_active_idx = active_layer_idx
    if new_active_idx >= len(layers):
        new_active_idx = len(layers) - 1
    if not new_checked:
        new_checked.add(new_active_idx)

    return {
        "removed_name": removed_name,
        "active_layer_idx": new_active_idx,
        "checked_layer_indices": new_checked,
    }

def reset_layers_for_loaded_file(
    onset_times: list[float],
    focus_regions: dict[str, list[dict]],
    undo_stack: _UndoStack,
    dirty: bool,
) -> FileLayerResetResult:
    """Return the default layer/session state for a newly loaded file."""
    return {
        "layers": [
            hydrate_layer_state(
                "Layer 1",
                onset_times=onset_times,
                focus_regions=focus_regions,
                undo_stack=undo_stack,
                dirty=dirty,
            )
        ],
        "active_layer_idx": 0,
        "checked_layer_indices": {0},
    }


def switch_active_layer(
    layers: list[OnsetLayerState],
    active_layer_idx: int,
    new_idx: int,
    onset_times: list[float],
    focus_regions: dict[str, list[dict]],
    undo_stack: _UndoStack,
    dirty: bool,
) -> LayerSwitchResult | None:
    """Persist the current live layer state and load a new active layer."""
    if new_idx == active_layer_idx:
        return None
    if new_idx < 0 or new_idx >= len(layers):
        return None

    save_layer_state(
        layers,
        active_layer_idx,
        onset_times,
        focus_regions,
        undo_stack,
        dirty,
    )
    loaded_onsets, loaded_regions, loaded_undo, loaded_dirty = load_layer_state(layers, new_idx)
    return {
        "active_layer_idx": new_idx,
        "onset_times": loaded_onsets,
        "focus_regions": loaded_regions,
        "undo_stack": loaded_undo,
        "dirty": loaded_dirty,
    }


def summarize_layer_selection_change(
    checked_indices: list[int],
) -> LayerSelectionChangeResult:
    """Summarize the current layer-menu selection for the panel shell."""
    normalized_checked = [int(layer_idx) for layer_idx in checked_indices]
    return {
        "checked_layer_indices": set(normalized_checked),
        "primary_layer_idx": normalized_checked[0] if normalized_checked else None,
        "merge_enabled": len(normalized_checked) >= 2,
    }


def select_exclusive_layer(
    layer_idx: int,
    layer_count: int,
) -> LayerSelectionChangeResult | None:
    """Return a single-layer checked selection for combo or shortcut navigation."""
    if layer_idx < 0 or layer_idx >= layer_count:
        return None
    return summarize_layer_selection_change([layer_idx])


def classify_comparison_onsets(
    onset_times: list[float],
    comp_files: list[dict],
    tolerance_ms: float,
) -> ComparisonClassificationResult:
    """Classify main and comparison onsets as shared or unique."""
    tolerance_sec = float(tolerance_ms) / 1000.0
    matched_main: set[int] = set()
    comp_only_per_file: list[list[float]] = []

    for comp_file in comp_files:
        unique_comp: list[float] = []
        comp_times = [float(comp_time) for comp_time in comp_file.get("times", [])]
        for comp_time in comp_times:
            if onset_times:
                best_idx = min(
                    range(len(onset_times)),
                    key=lambda onset_idx: abs(float(onset_times[onset_idx]) - comp_time),
                )
                if abs(float(onset_times[best_idx]) - comp_time) <= tolerance_sec:
                    matched_main.add(best_idx)
                    continue
            unique_comp.append(comp_time)
        comp_only_per_file.append(unique_comp)

    return {
        "main_only": set(range(len(onset_times))) - matched_main,
        "shared_main": matched_main,
        "comp_only_per_file": comp_only_per_file,
    }


def add_shared_comparison_onsets(
    onset_times: list[float],
    comp_files: list[dict],
    tolerance_ms: float,
    *,
    duplicate_tolerance_sec: float = 0.001,
) -> tuple[list[float], int]:
    """Return main onsets after appending shared comparison matches."""
    updated_onsets = [float(onset_time) for onset_time in onset_times]
    if not updated_onsets:
        return updated_onsets, 0

    tolerance_sec = float(tolerance_ms) / 1000.0
    added = 0
    for comp_file in comp_files:
        for comp_time in comp_file.get("times", []):
            normalized_time = float(comp_time)
            nearest_distance = min(
                abs(existing_time - normalized_time) for existing_time in updated_onsets
            )
            if nearest_distance <= tolerance_sec and nearest_distance > duplicate_tolerance_sec:
                updated_onsets.append(normalized_time)
                added += 1

    if added:
        updated_onsets.sort()
    return updated_onsets, added


def add_unique_comparison_onsets(
    onset_times: list[float],
    comp_only_per_file: list[list[float]],
    *,
    duplicate_tolerance_sec: float = 0.001,
) -> tuple[list[float], int]:
    """Return main onsets after appending comparison-only onsets."""
    updated_onsets = [float(onset_time) for onset_time in onset_times]
    added = 0
    for unique_times in comp_only_per_file:
        updated_onsets, newly_added = merge_onsets(
            updated_onsets,
            [float(onset_time) for onset_time in unique_times],
            tolerance_sec=duplicate_tolerance_sec,
        )
        added += newly_added
    return updated_onsets, added


def remove_main_only_onsets(
    onset_times: list[float],
    main_only_indices: set[int] | list[int],
) -> tuple[list[float], int]:
    """Return main onsets after removing indices unique to the main file."""
    removal_indices = {
        int(index)
        for index in main_only_indices
        if 0 <= int(index) < len(onset_times)
    }
    kept = [
        float(onset_time)
        for index, onset_time in enumerate(onset_times)
        if index not in removal_indices
    ]
    return kept, len(removal_indices)


def build_comparison_display_state(
    onset_times: list[float],
    comp_files: list[dict],
    filter_idx: int,
    *,
    main_only: set[int],
    shared_main: set[int],
    comp_only_per_file: list[list[float]],
    main_only_color: object,
    shared_color: object,
    comparison_style: object,
) -> ComparisonDisplayState:
    """Build comparison marker payloads and status text for the panel shell."""
    visible_main_times: list[float] = []
    visible_main_colors: list[object] = []
    for index, onset_time in enumerate(onset_times):
        is_shared = index in shared_main
        show = (
            filter_idx == 0
            or (filter_idx == 1 and index in main_only)
            or (filter_idx == 2 and is_shared)
        )
        if not show:
            continue
        visible_main_times.append(float(onset_time))
        visible_main_colors.append(shared_color if is_shared else main_only_color)

    comparison_layers: list[dict] = []
    if filter_idx in (0, 3):
        for index, comp_file in enumerate(comp_files):
            unique_times = [
                float(comp_time)
                for comp_time in (comp_only_per_file[index] if index < len(comp_only_per_file) else [])
            ]
            if not unique_times:
                continue
            comparison_layers.append(
                {
                    "times": unique_times,
                    "color": comp_file["color"],
                    "style": comparison_style,
                }
            )

    total_comp_unique = sum(len(unique_times) for unique_times in comp_only_per_file)
    return {
        "visible_main_times": visible_main_times,
        "visible_main_colors": visible_main_colors,
        "comparison_layers": comparison_layers,
        "status_text": (
            f"Main: {len(main_only)} unique, {len(shared_main)} shared  |  "
            f"Comparison: {total_comp_unique} unique"
        ),
    }


def activate_layer_range(
    checked_layer_indices: set[int],
    first_layer_idx: int,
    layer_count: int,
) -> LayerRangeActivationResult | None:
    """Activate the first layer in a new range and mark that range as checked."""
    if first_layer_idx < 0 or first_layer_idx >= layer_count:
        return None
    new_checked = set(checked_layer_indices)
    new_checked.update(range(first_layer_idx, layer_count))
    return {
        "active_layer_idx": first_layer_idx,
        "checked_layer_indices": new_checked,
    }


def format_checked_layer_label(
    layers: list[OnsetLayerState],
    checked_indices: list[int],
) -> str:
    """Return the layer-menu button label for the current checked selection."""
    if not checked_indices:
        return "(none) ▾"
    primary_name = layers[checked_indices[0]]["name"]
    n_extra = len(checked_indices) - 1
    suffix = f" +{n_extra}" if n_extra > 0 else ""
    return f"{primary_name}{suffix} ▾"


def build_layer_overlay_markers(
    layers: list[OnsetLayerState],
    checked_indices: list[int],
    overlay_colors: list[object],
    shared_color: object,
    *,
    unique_style: object,
    shared_style: object,
    round_digits: int = 4,
) -> list[dict]:
    """Build comparison-marker payloads for checked layers beyond the primary."""
    if len(checked_indices) <= 1:
        return []

    primary_idx = checked_indices[0]
    primary_times = {
        round(float(onset_time), round_digits)
        for onset_time in layers[primary_idx].get("onset_times", [])
    }

    overlay_layers: list[dict] = []
    overlay_idx = 0
    for layer_idx in checked_indices[1:]:
        times = layers[layer_idx].get("onset_times", [])
        if not times:
            overlay_idx += 1
            continue

        color = overlay_colors[overlay_idx % len(overlay_colors)]
        shared_times: list[float] = []
        unique_times: list[float] = []
        for onset_time in times:
            if round(float(onset_time), round_digits) in primary_times:
                shared_times.append(onset_time)
            else:
                unique_times.append(onset_time)

        if unique_times:
            overlay_layers.append({
                "times": unique_times,
                "color": color,
                "style": unique_style,
            })
        if shared_times:
            overlay_layers.append({
                "times": shared_times,
                "color": shared_color,
                "style": shared_style,
            })

        overlay_idx += 1

    return overlay_layers


def append_merged_layer(
    layers: list[OnsetLayerState],
    source_indices: list[int],
    *,
    layer_name: str,
    tolerance_sec: float = 0.001,
) -> tuple[int, list[float]]:
    """Append a new layer containing deduplicated onsets from source layers."""
    merged_onsets: list[float] = []
    for layer_idx in source_indices:
        if layer_idx < 0 or layer_idx >= len(layers):
            continue
        merged_onsets, _ = merge_onsets(
            merged_onsets,
            layers[layer_idx]["onset_times"],
            tolerance_sec=tolerance_sec,
        )

    new_idx = append_layer_state(
        layers,
        layer_name=layer_name,
        onset_times=merged_onsets,
        dirty=True,
    )
    return new_idx, merged_onsets


def restore_loaded_focus_regions(
    layers: list[OnsetLayerState],
    active_layer_idx: int,
    audio_path: str | None,
    restored_regions: list[dict],
) -> RestoredLoadedFocusRegionsResult:
    """Restore saved focus regions into matching layers for the current file."""
    file_name = os.path.basename(audio_path) if audio_path else ""
    if not file_name or not layers:
        return {
            "created_layer_names": [],
            "focus_regions": {},
        }

    default_layer_name = layers[active_layer_idx]["name"]
    by_layer: dict[str, list[dict]] = {}
    for region in restored_regions:
        region_copy = dict(region)
        layer_name = region_copy.pop("layer_name", None) or default_layer_name
        by_layer.setdefault(layer_name, []).append(region_copy)

    existing = {layer["name"]: idx for idx, layer in enumerate(layers)}
    created_layer_names: list[str] = []
    for layer_name, layer_regions in by_layer.items():
        if layer_name not in existing:
            existing[layer_name] = append_layer_state(layers, layer_name=layer_name)
            created_layer_names.append(layer_name)
        layer = layers[existing[layer_name]]
        layer.setdefault("focus_regions", {})[file_name] = [
            dict(region) for region in layer_regions
        ]

    return {
        "created_layer_names": created_layer_names,
        "focus_regions": layers[active_layer_idx]["focus_regions"],
    }


def transfer_focus_region(
    layers: list[OnsetLayerState],
    active_layer_idx: int,
    focus_regions: dict[str, list[dict]],
    audio_path: str | None,
    region_idx: int,
    target_layer_idx: int,
    remove_from_source: bool,
) -> FocusRegionTransferResult | None:
    """Move or copy a focus region between layers for the current audio file."""
    file_name = os.path.basename(audio_path) if audio_path else ""
    if not file_name:
        return None

    regions = focus_regions.get(file_name, [])
    if region_idx < 0 or region_idx >= len(regions):
        return None

    region_copy = dict(regions[region_idx])
    created_layer = False

    if target_layer_idx == -1:
        target_layer_idx, target_layer_name = append_empty_layer(layers)
        created_layer = True

    if target_layer_idx < 0 or target_layer_idx >= len(layers):
        return None
    if target_layer_idx == active_layer_idx:
        return None

    target_layer = layers[target_layer_idx]
    target_layer.setdefault("focus_regions", {})
    target_layer["focus_regions"].setdefault(file_name, []).append(region_copy)

    if remove_from_source:
        regions.pop(region_idx)

    return {
        "target_layer_idx": target_layer_idx,
        "target_name": target_layer["name"],
        "polarity": region_copy.get("polarity", "positive"),
        "created_layer": created_layer,
        "removed_from_source": remove_from_source,
    }


def compute_ioi(times: list[float]) -> list[Optional[float]]:
    """Return per-onset inter-onset intervals in milliseconds."""
    if len(times) < 2:
        return [None] * len(times)

    iois: list[Optional[float]] = [None]
    for index in range(1, len(times)):
        iois.append((times[index] - times[index - 1]) * 1000.0)
    return iois


def compute_rk(times: list[float]) -> list[Optional[float]]:
    """Return the dyadic rhythm ratio per onset index."""
    if len(times) < 3:
        return [None] * len(times)

    result: list[Optional[float]] = [None, None]
    for index in range(2, len(times)):
        interval_1 = times[index - 1] - times[index - 2]
        interval_2 = times[index] - times[index - 1]
        cycle_duration = interval_1 + interval_2
        result.append(interval_1 / cycle_duration if cycle_duration > 0 else None)
    return result


def compute_stable(times: list[float], tolerance: float) -> list[Optional[bool]]:
    """Return stable-rhythm flags per dyad using a repeating-interval check."""
    n_times = len(times)
    if n_times < 3:
        return [None] * n_times

    intervals = [times[index] - times[index - 1] for index in range(1, n_times)]
    result: list[Optional[bool]] = [None, None]

    def _match(interval_a: float, interval_b: float) -> bool:
        max_interval = max(interval_a, interval_b)
        if max_interval <= 0:
            return False
        return abs(interval_a - interval_b) / max_interval <= tolerance

    for dyad_index in range(len(intervals) - 1):
        comparisons = []
        if dyad_index + 2 < len(intervals):
            comparisons.append(_match(intervals[dyad_index], intervals[dyad_index + 2]))
        if dyad_index + 3 < len(intervals):
            comparisons.append(_match(intervals[dyad_index + 1], intervals[dyad_index + 3]))
        result.append(bool(comparisons) and all(comparisons))
    return result


def remove_onsets_in_range(
    onset_times: list[float],
    start: float,
    end: float,
    *,
    tolerance_sec: float = 0.0,
) -> tuple[list[float], int]:
    """Return onsets outside the given range and how many were removed."""
    lower = min(float(start), float(end)) - float(tolerance_sec)
    upper = max(float(start), float(end)) + float(tolerance_sec)
    kept = []
    removed = 0
    for onset_time in onset_times:
        if lower <= float(onset_time) <= upper:
            removed += 1
        else:
            kept.append(float(onset_time))
    return kept, removed


def merge_onsets(
    existing_onsets: list[float],
    new_onsets: list[float],
    *,
    offset: float = 0.0,
    tolerance_sec: float = 0.001,
) -> tuple[list[float], int]:
    """Merge new onset times into an existing list with duplicate suppression."""
    merged = [float(onset_time) for onset_time in existing_onsets]
    added = 0
    for onset_time in new_onsets:
        absolute_time = float(onset_time) + float(offset)
        if any(abs(absolute_time - existing) < tolerance_sec for existing in merged):
            continue
        merged.append(absolute_time)
        added += 1
    if added:
        merged.sort()
    return merged, added


def filter_removed_onsets(
    onset_times: list[float],
    removed_times,
    *,
    tolerance_sec: float = 0.001,
) -> list[float]:
    """Return onsets that do not match any removed time within tolerance."""
    removed_list = [float(onset_time) for onset_time in removed_times]
    kept = []
    for onset_time in onset_times:
        if any(abs(float(onset_time) - removed) < tolerance_sec for removed in removed_list):
            continue
        kept.append(float(onset_time))
    return sorted(kept)


__all__ = [
    "ComparisonClassificationResult",
    "ComparisonDisplayState",
    "FileLayerResetResult",
    "FocusRegionStatusResult",
    "FocusRestoreStateResult",
    "FocusRegionTransferResult",
    "LayerRangeActivationResult",
    "LayerRemovalResult",
    "LayerSelectionChangeResult",
    "LayerSwitchResult",
    "LoadedSelectionsFeedbackResult",
    "LoadedOnsetSessionResult",
    "OnsetLayerState",
    "RestoredLoadedFocusRegionsResult",
    "RestoredLayerConfigResult",
    "ReviewFinishStateResult",
    "ReviewNavigationStateResult",
    "SaveSelectionsExportPlanResult",
    "SaveSelectionsPreflightResult",
    "ScalarConfigRestoreResult",
    "_UndoStack",
    "add_shared_comparison_onsets",
    "add_unique_comparison_onsets",
    "activate_layer_range",
    "append_empty_layer",
    "append_layer_state",
    "append_merged_layer",
    "build_panel_config_snapshot",
    "build_loaded_onset_session",
    "build_save_selections_export_plan",
    "build_comparison_display_state",
    "compute_ioi",
    "compute_rk",
    "compute_stable",
    "classify_comparison_onsets",
    "deserialize_layers",
    "extract_scalar_config_restore_values",
    "filter_removed_onsets",
    "format_checked_layer_label",
    "hydrate_layer_state",
    "load_layer_state",
    "make_default_layer",
    "merge_onsets",
    "build_layer_overlay_markers",
    "remove_active_layer",
    "remove_main_only_onsets",
    "remove_onsets_in_range",
    "restore_configured_layers",
    "reset_layers_for_loaded_file",
    "restore_loaded_focus_regions",
    "serialize_layers",
    "save_layer_state",
    "select_exclusive_layer",
    "summarize_loaded_selections_feedback",
    "summarize_save_selections_preflight",
    "summarize_focus_restore_state",
    "summarize_focus_region_status",
    "summarize_review_finish_state",
    "summarize_review_navigation_state",
    "summarize_layer_selection_change",
    "switch_active_layer",
    "transfer_focus_region",
]