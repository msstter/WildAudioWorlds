"""Shared I/O helpers for the onset editor workbench."""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Optional

import numpy as np

try:
    from onset_editor_state import build_loaded_onset_session as _build_loaded_onset_session
except ImportError:
    from GUI.onset_editor_state import build_loaded_onset_session as _build_loaded_onset_session

_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

try:
    import excel_onset_io as _eio

    _HAS_EXCEL_IO = True
except ImportError:
    _eio = None
    _HAS_EXCEL_IO = False


# Each entry: (action_id, default_key, description, category)
# category "viewer" entries are handled by audio_viewer's keyPressEvent and
# are shown as read-only in the settings dialog.
_HOTKEY_DEFS: list[tuple[str, str, str, str]] = [
    ("undo", "Ctrl+Z", "Undo", "General"),
    ("redo", "Ctrl+Shift+Z", "Redo", "General"),
    ("save", "Ctrl+S", "Save onsets", "General"),
    ("delete", "Delete", "Delete selected onset / region", "General"),
    ("escape", "Escape", "Cancel / clear selection", "General"),
    ("focus_mode", "F", "Toggle Focus Onsets mode", "Tools"),
    ("edit_onsets", "E", "Toggle Edit Onsets mode", "Tools"),
    ("detect_onsets", "D", "Open Quick Onset Finder", "Tools"),
    ("quick_audio_edit", "A", "Open Quick Audio Editor", "Tools"),
    ("manage_files", "G", "Open Manage Onset / Excel Files", "Tools"),
    ("prev_file", "Ctrl+Left", "Previous audio file", "Navigation"),
    ("next_file", "Ctrl+Right", "Next audio file", "Navigation"),
    ("cycle_fullscreen", "M", "Cycle fullscreen states", "Tools"),
    ("prev_layer", "[", "Previous layer", "Layers"),
    ("next_layer", "]", "Next layer", "Layers"),
    ("prev_onset", "Up", "Select previous onset", "Navigation"),
    ("next_onset", "Down", "Select next onset", "Navigation"),
    ("play_pause", "Space", "Play / Pause", "viewer"),
    ("prev_chunk", "Left", "Previous chunk", "viewer"),
    ("next_chunk", "Right", "Next chunk", "viewer"),
    ("seek_start", "Home", "Seek to start", "viewer"),
    ("seek_end", "End", "Seek to end", "viewer"),
    ("zoom_in", "+", "Zoom in", "viewer"),
    ("zoom_out", "-", "Zoom out", "viewer"),
]

_HOTKEY_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "onset_editor_hotkeys.json",
)


def _load_hotkey_overrides() -> dict[str, str]:
    """Load user-customised hotkey overrides from disk."""
    if os.path.isfile(_HOTKEY_CONFIG_FILE):
        try:
            with open(_HOTKEY_CONFIG_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _save_hotkey_overrides(overrides: dict[str, str]):
    """Persist hotkey overrides to disk."""
    try:
        with open(_HOTKEY_CONFIG_FILE, "w") as f:
            json.dump(overrides, f, indent=2)
    except Exception:
        pass


def _get_hotkey_map() -> dict[str, str]:
    """Return action_id → key_sequence merging defaults with overrides."""
    mapping = {aid: key for aid, key, _desc, _cat in _HOTKEY_DEFS}
    mapping.update(_load_hotkey_overrides())
    return mapping


def _load_muter_presets() -> dict:
    """Import MUTER_PRESETS from the shared presets module, or return empty dict."""
    try:
        from panel_presets import MUTER_PRESETS

        return MUTER_PRESETS
    except Exception:
        try:
            from GUI.panel_presets import MUTER_PRESETS

            return MUTER_PRESETS
        except Exception:
            return {}


def _load_labels(path: str) -> list[float]:
    """Load onset times from an Audacity-format label file."""
    times: list[float] = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 1:
                try:
                    times.append(float(parts[0]))
                except ValueError:
                    continue
    times.sort()
    return times


def _save_labels(path: str, times: list[float]):
    """Save onset times as an Audacity-format label file."""
    with open(path, "w") as f:
        for idx, t in enumerate(sorted(times)):
            f.write(f"{t:.6f}\t{t:.6f}\tOnsetR_{idx + 1}\n")


def _find_label_file(audio_path: str) -> Optional[str]:
    """Given an audio file path, find the corresponding _labels.txt file."""
    stem = os.path.splitext(os.path.basename(audio_path))[0]
    folder = os.path.dirname(audio_path)
    candidate = os.path.join(folder, f"{stem}_labels.txt")
    if os.path.isfile(candidate):
        return candidate
    return None


def _load_saved_onsets_for_audio(audio_path: str) -> tuple[Optional[str], list[float]]:
    """Return the saved label path and onset list for one audio file."""
    label_path = _find_label_file(audio_path)
    if not label_path:
        return None, []
    return label_path, _load_labels(label_path)


def _load_saved_onset_session_for_audio(audio_path: str) -> tuple[Optional[str], dict]:
    """Return the saved label path and a fresh live session for one audio file."""
    label_path, onset_times = _load_saved_onsets_for_audio(audio_path)
    return label_path, _build_loaded_onset_session(onset_times)


def _list_audio_files(folder: str) -> list[str]:
    """Return sorted audio filenames in one folder."""
    if not os.path.isdir(folder):
        return []

    audio_exts = {".wav", ".mp3", ".flac", ".ogg", ".aiff", ".aif", ".m4a"}
    return sorted(
        file_name
        for file_name in os.listdir(folder)
        if os.path.splitext(file_name)[1].lower() in audio_exts
        and os.path.isfile(os.path.join(folder, file_name))
    )


def _review_audio_paths(folder: str) -> list[str]:
    """Return absolute audio paths in one folder for review-mode iteration."""
    return [os.path.join(folder, file_name) for file_name in _list_audio_files(folder)]


def _resolve_restored_file_selection(
    folder: str,
    requested_file: str,
) -> tuple[bool, list[str], int]:
    """Return folder validity, available files, and the index to select on restore."""
    if not folder or not os.path.isdir(folder):
        return False, [], -1

    files = _list_audio_files(folder)
    if not files:
        return True, [], -1

    selected_index = files.index(requested_file) if requested_file in files else 0
    return True, files, selected_index


def _selection_manifest_filename(audio_path: str | None, polarity: str) -> str:
    """Return the saved-selection manifest filename for one polarity."""
    stem = os.path.splitext(os.path.basename(audio_path))[0] if audio_path else "selection"
    normalized = str(polarity).strip().lower()
    suffix = "PositiveSignals" if normalized == "positive" else "NegativeSignals"
    return f"{stem}_{suffix}.json"


def _read_selection_manifest(
    audio_path: str | None,
    directory: str,
    polarity: str,
) -> dict | None:
    """Read one polarity-specific saved-selection manifest if it exists."""
    if not directory:
        return None

    manifest_path = os.path.join(
        directory,
        _selection_manifest_filename(audio_path, polarity),
    )
    if not os.path.isfile(manifest_path):
        return None

    with open(manifest_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _regions_from_manifests(
    audio_path: str | None,
    manifests: list[dict | None],
) -> list[dict]:
    """Extract drawable focus regions from saved-selection manifests for one audio file."""
    if not audio_path:
        return []

    current_file = os.path.basename(audio_path)
    restored: list[dict] = []
    seen: set[tuple] = set()

    for manifest in manifests:
        if not manifest or manifest.get("source_file") != current_file:
            continue
        for region in manifest.get("regions", []):
            key = (
                round(float(region.get("t_start", 0.0)), 6),
                round(float(region.get("t_end", 0.0)), 6),
                round(float(region.get("f_low", 0.0)), 3),
                round(float(region.get("f_high", 0.0)), 3),
                region.get("polarity", manifest.get("polarity", "positive")),
                region.get("layer_name", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            restored.append(
                {
                    "t_start": float(region.get("t_start", 0.0)),
                    "t_end": float(region.get("t_end", 0.0)),
                    "f_low": float(region.get("f_low", 0.0)),
                    "f_high": float(region.get("f_high", 0.0)),
                    "polarity": region.get("polarity", manifest.get("polarity", "positive")),
                    "layer_name": region.get("layer_name"),
                }
            )

    restored.sort(
        key=lambda region: (
            region.get("layer_name") or "",
            region["t_start"],
            region["f_low"],
        )
    )
    return restored


def _write_selection_manifest(
    output_dir: str,
    audio_path: str | None,
    polarity: str,
    manifest: dict,
):
    """Write selection geometry metadata alongside exported signal clips."""
    os.makedirs(output_dir, exist_ok=True)
    manifest_path = os.path.join(
        output_dir,
        _selection_manifest_filename(audio_path, polarity),
    )
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)


def _build_load_selections_request(
    positive_input_dir: str,
    negative_input_dir: str,
) -> dict[str, str]:
    """Return the normalized directory payload for a load-selections request."""
    return {
        "positive_input_dir": positive_input_dir,
        "negative_input_dir": negative_input_dir,
    }


def _summarize_load_selections_error(exc: Exception) -> dict[str, str]:
    """Return the title and message for a load-selections failure dialog."""
    return {
        "title": "Load Selections Error",
        "message": f"Failed to load saved selections:\n{exc}",
    }


def _load_saved_selections(
    audio_path: str | None,
    positive_dir: str,
    negative_dir: str,
    build_profile_callback,
) -> dict:
    """Load saved selection geometry and optional clip-derived fallback profile."""
    pos_manifest = _read_selection_manifest(audio_path, positive_dir, "positive")
    neg_manifest = _read_selection_manifest(audio_path, negative_dir, "negative")

    restored_regions = _regions_from_manifests(audio_path, [pos_manifest, neg_manifest])
    geometry_restored = bool(restored_regions)
    loaded_profile = None
    if not geometry_restored:
        loaded_profile = build_profile_callback(
            positive_dir,
            negative_dir,
            pos_manifest,
            neg_manifest,
        )

    return {
        "regions": restored_regions,
        "geometry_restored": geometry_restored,
        "profile": loaded_profile,
    }


def _next_export_number(
    out_dir: str,
    stem: str,
    polarity: str,
    layer_suffix: str = "",
) -> int:
    """Return the next available clip number for one export stem and polarity."""
    pattern = re.compile(
        rf"^{re.escape(stem)}_{re.escape(polarity)}"
        rf"(\d+){re.escape(layer_suffix)}\.wav$",
        re.IGNORECASE,
    )
    max_n = 0
    if os.path.isdir(out_dir):
        for file_name in os.listdir(out_dir):
            match = pattern.match(file_name)
            if match:
                max_n = max(max_n, int(match.group(1)))
    return max_n + 1


def _extract_region_audio(
    y: np.ndarray,
    sr: int,
    region: dict,
    bandpass: bool,
) -> np.ndarray | None:
    """Extract one focus-region audio segment, optionally bandpass-filtered."""
    t_start = region["t_start"]
    t_end = region["t_end"]
    i_start = max(0, int(t_start * sr))
    i_end = min(len(y), int(t_end * sr))
    if i_end <= i_start:
        return None

    seg = y[i_start:i_end].copy()

    if bandpass:
        f_low = region.get("f_low", 0)
        f_high = region.get("f_high", sr // 2)
        nyquist = sr / 2.0
        f_low = max(1, min(f_low, nyquist - 1))
        f_high = max(f_low + 1, min(f_high, nyquist - 1))
        if f_low < f_high:
            try:
                from scipy.signal import butter, sosfilt

                sos = butter(4, [f_low, f_high], btype="band", fs=sr, output="sos")
                seg = sosfilt(sos, seg).astype(seg.dtype)
            except Exception:
                pass

    return seg


def _export_selections_audio(
    audio_path: str,
    audio_data: np.ndarray | None,
    sr: int,
    out_dir: str,
    layers_to_export: list[tuple[int, dict]],
    individual: bool,
    bandpass: bool,
    negative_out_dir: str | None = None,
) -> int:
    """Export focus-region selections as WAV clips and write selection manifests."""
    try:
        import soundfile as sf
    except ImportError as exc:
        raise ImportError(
            "soundfile is required for WAV export. Install it with: pip install soundfile"
        ) from exc

    if audio_data is None:
        raise ValueError("No audio data loaded.")

    negative_out_dir = negative_out_dir or out_dir
    stem = os.path.splitext(os.path.basename(audio_path))[0]
    file_name = os.path.basename(audio_path)
    total_files = 0
    manifests = {
        "Positive": {
            "version": 1,
            "source_audio": audio_path,
            "source_file": file_name,
            "polarity": "positive",
            "export_mode": "individual" if individual else "concatenated",
            "bandpass": bool(bandpass),
            "regions": [],
            "files": [],
        },
        "Negative": {
            "version": 1,
            "source_audio": audio_path,
            "source_file": file_name,
            "polarity": "negative",
            "export_mode": "individual" if individual else "concatenated",
            "bandpass": bool(bandpass),
            "regions": [],
            "files": [],
        },
    }
    dir_map = {"Positive": out_dir, "Negative": negative_out_dir}

    for _layer_idx, layer in layers_to_export:
        regions = layer["focus_regions"].get(file_name, [])
        if not regions:
            continue

        pos_regions = [region for region in regions if region["polarity"] == "positive"]
        neg_regions = [region for region in regions if region["polarity"] == "negative"]

        layer_suffix = ""
        if len(layers_to_export) > 1:
            layer_suffix = f"_{layer['name'].replace(' ', '_')}"

        for polarity, pol_regions in (("Positive", pos_regions), ("Negative", neg_regions)):
            if not pol_regions:
                continue

            target_dir = dir_map[polarity]
            os.makedirs(target_dir, exist_ok=True)

            segments = []
            for region_index, region in enumerate(pol_regions):
                seg = _extract_region_audio(audio_data, sr, region, bandpass)
                if seg is not None and len(seg) > 0:
                    segments.append((region_index, region, seg))

            if not segments:
                continue

            if individual:
                for _region_index, region, seg in segments:
                    number = _next_export_number(target_dir, stem, polarity, layer_suffix)
                    out_name = f"{stem}_{polarity}{number}{layer_suffix}.wav"
                    out_path = os.path.join(target_dir, out_name)
                    sf.write(out_path, seg, sr)
                    region_meta = dict(region)
                    region_meta["audio_file"] = out_name
                    region_meta["layer_name"] = layer["name"]
                    manifests[polarity]["regions"].append(region_meta)
                    manifests[polarity]["files"].append(
                        {
                            "audio_file": out_name,
                            "layer_name": layer["name"],
                            "region": dict(region),
                        }
                    )
                    total_files += 1
            else:
                concat = np.concatenate([seg for _, _, seg in segments])
                out_name = f"{stem}_{polarity}_all{layer_suffix}.wav"
                out_path = os.path.join(target_dir, out_name)
                sf.write(out_path, concat, sr)
                manifests[polarity]["files"].append(
                    {
                        "audio_file": out_name,
                        "layer_name": layer["name"],
                        "regions": [dict(region) for _, region, _seg in segments],
                    }
                )
                for _region_index, region, _seg in segments:
                    region_meta = dict(region)
                    region_meta["audio_file"] = out_name
                    region_meta["layer_name"] = layer["name"]
                    manifests[polarity]["regions"].append(region_meta)
                total_files += 1

    for polarity, manifest in manifests.items():
        if manifest["regions"]:
            _write_selection_manifest(dir_map[polarity], audio_path, polarity, manifest)

    return total_files


def _write_focus_regions_json(folder: str, stem: str, layers: list[dict]) -> Optional[str]:
    """Write merged per-file focus regions to a JSON file next to the audio."""
    all_regions: dict[str, list[dict]] = {}
    for layer in layers:
        for file_name, regions in layer.get("focus_regions", {}).items():
            if not regions:
                continue
            all_regions.setdefault(file_name, []).extend(regions)

    if not all_regions:
        return None

    out_path = os.path.join(folder, f"{stem}_focus_regions.json")
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(all_regions, handle, indent=2)
    return out_path


def _write_onset_layer_settings(audio_path: str, layers: list[dict]) -> Optional[str]:
    """Write per-layer onset settings JSON files alongside the audio file."""
    if not audio_path:
        return None

    audio_folder = os.path.dirname(audio_path)
    stem = os.path.splitext(os.path.basename(audio_path))[0]
    layers_dir = os.path.join(audio_folder, f"{stem}_OnsetLayers")
    os.makedirs(layers_dir, exist_ok=True)

    audio_filename = os.path.basename(audio_path)
    for index, layer in enumerate(layers, 1):
        layer_data = {
            "name": layer.get("name", f"Layer {index}"),
            "audio_filename": audio_filename,
            "focus_regions": layer.get("focus_regions", {}).get(audio_filename, []),
            "onset_times": [round(float(onset_time), 6) for onset_time in layer.get("onset_times", [])],
        }
        out_path = os.path.join(layers_dir, f"Layer_{index}.json")
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(layer_data, handle, indent=2)

    return layers_dir


__all__ = [
    "_HOTKEY_DEFS",
    "_HAS_EXCEL_IO",
    "_extract_region_audio",
    "_export_selections_audio",
    "_build_load_selections_request",
    "_eio",
    "_find_label_file",
    "_get_hotkey_map",
    "_list_audio_files",
    "_load_hotkey_overrides",
    "_load_labels",
    "_load_saved_selections",
    "_load_saved_onset_session_for_audio",
    "_load_saved_onsets_for_audio",
    "_load_muter_presets",
    "_next_export_number",
    "_save_hotkey_overrides",
    "_save_labels",
    "_resolve_restored_file_selection",
    "_selection_manifest_filename",
    "_summarize_load_selections_error",
    "_write_selection_manifest",
    "_write_focus_regions_json",
    "_write_onset_layer_settings",
]