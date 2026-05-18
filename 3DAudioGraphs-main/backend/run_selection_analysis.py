import json
import sys
import traceback
import wave
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import uuid4

import librosa
import numpy as np

from shared_graph_paths import resolve_graph_project_root
from wild_audio_worlds.session.analysis_types import (
    BACKEND_ANALYSIS_TYPE_CONFIGS,
    DEFAULT_BACKEND_ANALYSIS_TYPE,
    normalize_backend_analysis_type,
)
from wild_audio_worlds.session.command_contracts import (
    parse_backend_analysis_request_json,
)
from wild_audio_worlds.session.selection_contracts import (
    normalize_selection_amplitude_pct_range,
    normalize_selection_frequency_window,
    normalize_selection_time_window,
)

try:
    from bioacoustics_workbook import load_onsets_for_audio, sync_workbook_onsets
except ModuleNotFoundError:
    from backend.bioacoustics_workbook import load_onsets_for_audio, sync_workbook_onsets


DEFAULT_SAMPLE_RATE = 22050
DEFAULT_HOP_LENGTH = 512
DEFAULT_FRAME_LENGTH = 2048
DEFAULT_FFT_NFFT = 1024
DEFAULT_DISPLAY_BIN_COUNT = 512
DEFAULT_BIO_OUTPUT_MODE = "duplicate"
AUTO_DISCOVER_BIO_WORKBOOK_GLOB = "AudioData_OnsetFinder*.xlsx"
AUTO_DISCOVER_BIO_SEARCH_ROOTS = ("data", "backend/data")


def _project_root():
    return resolve_graph_project_root(anchor_file=__file__)


def _slugify(value):
    value = str(value or "selection-analysis").strip().lower()
    cleaned = []
    for char in value:
        cleaned.append(char if char.isalnum() else "-")
    slug = "".join(cleaned).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "selection-analysis"


def _read_payload():
    return parse_backend_analysis_request_json(sys.stdin.read())


def _coerce_float(value, fallback=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(fallback)
    return number if np.isfinite(number) else float(fallback)


def _coerce_int(value, fallback=0):
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return int(fallback)
    return number


def _clamp(value, lower, upper):
    return max(lower, min(upper, value))


def _resolve_audio_path(asset_payload):
    audio_url = str((asset_payload or {}).get("audioUrl") or "").strip()
    if not audio_url:
        raise ValueError("Selection analysis payload is missing asset.audioUrl.")

    clean_audio_url = audio_url.split("?", 1)[0].split("#", 1)[0]
    parsed_url = urlparse(clean_audio_url)

    if parsed_url.scheme.lower() == "file":
        file_path = unquote(parsed_url.path or "")
        if sys.platform.startswith("win") and file_path.startswith("/") and len(file_path) > 2 and file_path[2] == ":":
            file_path = file_path[1:]
        absolute_path = Path(file_path).resolve()
    else:
        relative_path = clean_audio_url
        if relative_path.startswith("./"):
            relative_path = relative_path[2:]
        relative_path = relative_path.lstrip("/")
        absolute_path = (_project_root() / "frontend" / "public" / relative_path).resolve()

    if not absolute_path.exists():
        raise FileNotFoundError(f"Audio asset not found on disk: {absolute_path}")
    return absolute_path


def _resolve_optional_path(path_value):
    text = str(path_value or "").strip()
    if not text:
        return None

    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = (_project_root() / candidate).resolve()
    return candidate


def _iter_bioacoustics_workbook_candidates(root_path):
    root_path = Path(root_path).resolve()
    seen_paths = set()

    if root_path.is_file():
        yield root_path
        return

    if not root_path.exists() or not root_path.is_dir():
        return

    preferred_search_roots = []
    if root_path.name.lower() == "data":
        preferred_search_roots.append(root_path)
    else:
        preferred_search_roots.append(root_path / "data")
        preferred_search_roots.append(root_path)

    for search_root in preferred_search_roots:
        if not search_root.exists() or not search_root.is_dir():
            continue
        for candidate in sorted(search_root.glob(AUTO_DISCOVER_BIO_WORKBOOK_GLOB)):
            if candidate.name.startswith("~$") or not candidate.is_file():
                continue
            resolved_candidate = candidate.resolve()
            if resolved_candidate in seen_paths:
                continue
            seen_paths.add(resolved_candidate)
            yield resolved_candidate

    for candidate in sorted(root_path.rglob(AUTO_DISCOVER_BIO_WORKBOOK_GLOB)):
        if candidate.name.startswith("~$") or not candidate.is_file():
            continue
        resolved_candidate = candidate.resolve()
        if resolved_candidate in seen_paths:
            continue
        seen_paths.add(resolved_candidate)
        yield resolved_candidate


def _resolve_bioacoustics_workbook_path(path_value, audio_filename=None):
    candidate_path = _resolve_optional_path(path_value)
    if not candidate_path or not candidate_path.exists():
        return None, None

    if candidate_path.is_file():
        return candidate_path.resolve(), None

    for workbook_path in _iter_bioacoustics_workbook_candidates(candidate_path):
        if not audio_filename:
            return workbook_path, None
        try:
            imported = load_onsets_for_audio(
                workbook_path,
                audio_filename,
            )
        except Exception:
            continue
        imported["workbookPath"] = str(workbook_path.resolve())
        return workbook_path, imported

    return None, None


def _resolve_bioacoustics_output_directory(path_value):
    candidate_path = _resolve_optional_path(path_value)
    if not candidate_path or not candidate_path.exists() or not candidate_path.is_dir():
        return None

    if candidate_path.name.lower() == "data":
        return candidate_path.resolve()
    return (candidate_path / "data").resolve()


def _resolve_asset_audio_filename(asset_payload, bio_payload=None):
    bio_payload = bio_payload or {}
    explicit_name = str(bio_payload.get("assetAudioFileName") or "").strip()
    if explicit_name:
        return Path(explicit_name).name

    audio_url = str((asset_payload or {}).get("audioUrl") or "").strip()
    if audio_url:
        return Path(audio_url.split("?", 1)[0].split("#", 1)[0]).name

    asset_label = str((asset_payload or {}).get("label") or "").strip()
    if asset_label:
        return asset_label

    asset_id = str((asset_payload or {}).get("id") or "").strip()
    if asset_id:
        return asset_id

    raise ValueError("Bioacoustics handler could not resolve the selected asset audio filename.")


def _relative_output_path(path_value):
    path_obj = Path(path_value)
    try:
        return str(path_obj.resolve().relative_to(_project_root()))
    except ValueError:
        return str(path_obj.resolve())


def _normalize_onset_times(onset_times):
    normalized = []
    for onset_time in onset_times or []:
        coerced = _coerce_float(onset_time, None)
        if coerced is None:
            continue
        normalized.append(coerced)
    return sorted(normalized)


def _resolve_bio_sync_output_path(payload, audio_filename):
    bio_payload = payload.get("bioacoustics") or {}
    explicit_output_path = _resolve_optional_path(bio_payload.get("outputPath"))
    if explicit_output_path:
        return explicit_output_path

    output_mode = str(bio_payload.get("outputMode") or DEFAULT_BIO_OUTPUT_MODE).strip().lower()
    requested_workbook_path = _resolve_optional_path(bio_payload.get("workbookPath"))
    workbook_path, _ = _resolve_bioacoustics_workbook_path(bio_payload.get("workbookPath"), audio_filename)
    save_options = payload.get("saveOptions") or {}
    save_label = str(save_options.get("label") or "").strip()
    asset_stem = Path(audio_filename).stem if audio_filename else "bioacoustics"
    label_stem = _slugify(save_label or asset_stem or "bioacoustics")

    if output_mode == "overwrite":
        if not workbook_path:
            raise ValueError("Overwrite mode requires an existing workbook path.")
        return workbook_path

    if output_mode == "duplicate":
        if not workbook_path:
            raise ValueError("Duplicate mode requires an existing workbook path.")
        suffix = _slugify(save_label or "3daudiograph")
        return workbook_path.with_name(f"{workbook_path.stem}_{suffix}.xlsx")

    if requested_workbook_path and requested_workbook_path.exists() and requested_workbook_path.is_dir():
        output_dir = _resolve_bioacoustics_output_directory(requested_workbook_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / f"AudioData_OnsetFinder_{label_stem}.xlsx"

    export_dir = _project_root() / "data" / "exports" / "backend_calls"
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir / f"{label_stem}_bioacoustics.xlsx"


def _iter_auto_discovery_workbook_paths():
    seen_paths = set()
    for relative_root in AUTO_DISCOVER_BIO_SEARCH_ROOTS:
        search_root = (_project_root() / relative_root).resolve()
        if not search_root.exists() or not search_root.is_dir():
            continue
        for candidate in sorted(search_root.rglob(AUTO_DISCOVER_BIO_WORKBOOK_GLOB)):
            if candidate.name.startswith("~$") or not candidate.is_file():
                continue
            resolved_candidate = candidate.resolve()
            if resolved_candidate in seen_paths:
                continue
            seen_paths.add(resolved_candidate)
            yield resolved_candidate


def _auto_discover_bioacoustics_workbook(audio_filename):
    for workbook_path in _iter_auto_discovery_workbook_paths():
        try:
            imported = load_onsets_for_audio(
                workbook_path,
                audio_filename,
            )
        except Exception:
            continue
        imported["workbookPath"] = str(workbook_path.resolve())
        return workbook_path, imported

    return None, {
        "workbookPath": None,
        "matchedFileName": None,
        "onsetTimes": [],
    }


def _run_bioacoustics_import_workbook(payload):
    asset = payload.get("asset") or {}
    bio_payload = payload.get("bioacoustics") or {}
    requested_workbook_path = _resolve_optional_path(bio_payload.get("workbookPath"))
    auto_discover = bool(bio_payload.get("autoDiscover"))
    audio_filename = _resolve_asset_audio_filename(asset, bio_payload)

    if requested_workbook_path and requested_workbook_path.exists():
        workbook_path, imported = _resolve_bioacoustics_workbook_path(requested_workbook_path, audio_filename)
        if not workbook_path or not imported:
            raise FileNotFoundError(
                f"Bioacoustics import could not resolve a matching AudioData_OnsetFinder workbook from: {requested_workbook_path.resolve()}"
            )
    elif auto_discover:
        workbook_path, imported = _auto_discover_bioacoustics_workbook(audio_filename)
        if not workbook_path:
            return {
                "summary": {
                    "targetLabel": str(bio_payload.get("targetLabel") or "Current Selection"),
                    "assetAudioFileName": audio_filename,
                    "matchedFileName": None,
                    "onsetCount": 0,
                    "workbookPath": None,
                    "autoDiscoveryAttempted": True,
                    "autoDiscoveryMatched": False,
                },
                "importedWorkbook": imported,
            }
    else:
        raise FileNotFoundError("Bioacoustics import requires a readable workbook path.")

    return {
        "summary": {
            "targetLabel": str(bio_payload.get("targetLabel") or "Current Selection"),
            "assetAudioFileName": audio_filename,
            "matchedFileName": imported.get("matchedFileName"),
            "onsetCount": len(imported.get("onsetTimes") or []),
            "workbookPath": str(workbook_path.resolve()),
            "autoDiscoveryAttempted": auto_discover,
            "autoDiscoveryMatched": auto_discover and workbook_path is not None,
        },
        "importedWorkbook": imported,
    }


def _run_bioacoustics_sync_workbook(payload):
    asset = payload.get("asset") or {}
    bio_payload = payload.get("bioacoustics") or {}
    onset_times = _normalize_onset_times(bio_payload.get("onsetTimes"))
    if not onset_times:
        raise ValueError("Bioacoustics workbook sync requires onset times from the active Timbre target.")

    audio_filename = _resolve_asset_audio_filename(asset, bio_payload)
    output_mode = str(bio_payload.get("outputMode") or DEFAULT_BIO_OUTPUT_MODE).strip().lower()
    workbook_path, _ = _resolve_bioacoustics_workbook_path(bio_payload.get("workbookPath"), audio_filename)
    output_path = _resolve_bio_sync_output_path(payload, audio_filename)
    source_or_template_path = workbook_path or output_path

    sync_result = sync_workbook_onsets(
        source_or_template_path,
        audio_filename,
        onset_times,
        output_path=output_path,
    )

    return {
        "summary": {
            "targetLabel": str(bio_payload.get("targetLabel") or "Current Selection"),
            "targetKind": str(bio_payload.get("targetKind") or "current"),
            "assetAudioFileName": audio_filename,
            "onsetCount": len(onset_times),
            "outputMode": output_mode,
            "workbookPath": str(workbook_path.resolve()) if workbook_path else None,
            "outputWorkbookPath": str(output_path.resolve()),
        },
        "workbookSync": sync_result,
        "saveResult": {
            "mode": "xlsx",
            "saved": True,
            "path": _relative_output_path(output_path),
        },
    }


def _resolve_selection_window(asset_payload, selection_payload):
    clip_duration_sec = _coerce_float((asset_payload or {}).get("analysisClipDurationSec"), 0.0)
    return normalize_selection_time_window(selection_payload, clip_duration_sec)


def _resolve_frequency_window(asset_payload, selection_payload, available_bin_count):
    preferred_total_bins = _coerce_int(
        max(1, min(available_bin_count, (asset_payload or {}).get("analysisFftNfft") or DEFAULT_DISPLAY_BIN_COUNT)),
    )
    return normalize_selection_frequency_window(selection_payload, available_bin_count, preferred_total_bins)


def _stats(values):
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        return {
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0,
            "std": 0.0,
        }

    return {
        "mean": float(np.mean(array)),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
        "std": float(np.std(array)),
    }


def _rounded(value, digits=6):
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        return {key: _rounded(entry, digits) for key, entry in value.items()}
    if isinstance(value, list):
        return [_rounded(entry, digits) for entry in value]
    if isinstance(value, tuple):
        return [_rounded(entry, digits) for entry in value]
    if isinstance(value, np.ndarray):
        return [_rounded(entry, digits) for entry in value.tolist()]
    if isinstance(value, (np.floating, float)):
        if not np.isfinite(value):
            return None
        return round(float(value), digits)
    if isinstance(value, (np.integer, int)):
        return int(value)
    return value


def _build_common_metrics(y, sr, asset_payload, selection_payload):
    hop_length = max(1, _coerce_int((asset_payload or {}).get("analysisHopLength"), DEFAULT_HOP_LENGTH))
    frame_length = max(64, _coerce_int((asset_payload or {}).get("analysisFrameLength"), DEFAULT_FRAME_LENGTH))
    fft_nfft = max(128, _coerce_int((asset_payload or {}).get("analysisFftNfft"), DEFAULT_FFT_NFFT))

    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length).flatten()
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length, n_fft=frame_length).flatten()
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, hop_length=hop_length, n_fft=frame_length).flatten()
    zcr = librosa.feature.zero_crossing_rate(y=y, frame_length=frame_length, hop_length=hop_length).flatten()
    onset_strength = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length, n_fft=frame_length)

    stft = np.abs(librosa.stft(y, n_fft=fft_nfft, hop_length=hop_length))
    usable_spectrum = stft[: min(max(1, stft.shape[0]), DEFAULT_DISPLAY_BIN_COUNT), :] if stft.size > 0 else np.zeros((1, 1), dtype=np.float32)
    frequency_window = _resolve_frequency_window(asset_payload, selection_payload, usable_spectrum.shape[0])
    selected_band = usable_spectrum[
        frequency_window["startBin"]:frequency_window["endBin"] + 1,
        :,
    ]

    total_energy = float(np.sum(usable_spectrum)) if usable_spectrum.size > 0 else 0.0
    selected_energy = float(np.sum(selected_band)) if selected_band.size > 0 else 0.0
    energy_ratio = (selected_energy / total_energy) if total_energy > 0 else 0.0

    frequency_axis = librosa.fft_frequencies(sr=sr, n_fft=fft_nfft)
    frequency_axis = frequency_axis[: usable_spectrum.shape[0]] if usable_spectrum.shape[0] > 0 else np.zeros(1, dtype=np.float64)
    min_bin = min(frequency_window["startBin"], max(0, frequency_axis.size - 1))
    max_bin = min(frequency_window["endBin"], max(0, frequency_axis.size - 1))

    return {
        "common": {
            "sampleRate": int(sr),
            "sampleCount": int(y.shape[0]),
            "durationSec": float(y.shape[0] / sr) if sr else 0.0,
            "hopLength": hop_length,
            "frameLength": frame_length,
            "fftNfft": fft_nfft,
            "frameCount": int(rms.shape[0]),
            "rms": _stats(rms),
            "spectralCentroidHz": _stats(centroid),
            "spectralBandwidthHz": _stats(bandwidth),
            "zeroCrossingRate": _stats(zcr),
            "onsetStrength": _stats(onset_strength),
        },
        "frequencyWindow": {
            **frequency_window,
            "startHz": float(frequency_axis[min_bin]) if frequency_axis.size > 0 else 0.0,
            "endHz": float(frequency_axis[max_bin]) if frequency_axis.size > 0 else 0.0,
            "selectedEnergyRatio": energy_ratio,
            "selectedBandMeanMagnitude": float(np.mean(selected_band)) if selected_band.size > 0 else 0.0,
            "selectedBandPeakMagnitude": float(np.max(selected_band)) if selected_band.size > 0 else 0.0,
        },
        "spectrum": usable_spectrum,
        "selectedBand": selected_band,
        "hopLength": hop_length,
        "frameLength": frame_length,
    }


def _run_slice_summary(y, sr, asset_payload, selection_payload):
    metrics = _build_common_metrics(y, sr, asset_payload, selection_payload)
    amplitude_range = normalize_selection_amplitude_pct_range(selection_payload)

    return {
        "summary": {
            **metrics["common"],
            "selectionFrequencyWindow": metrics["frequencyWindow"],
            "selectionAmplitudePctRange": amplitude_range,
        },
    }


def _run_mfcc_profile(y, sr, asset_payload, selection_payload):
    metrics = _build_common_metrics(y, sr, asset_payload, selection_payload)
    mfcc = librosa.feature.mfcc(
        y=y,
        sr=sr,
        n_mfcc=13,
        hop_length=metrics["hopLength"],
        n_fft=metrics["frameLength"],
    )

    return {
        "summary": {
            **metrics["common"],
            "selectionFrequencyWindow": metrics["frequencyWindow"],
            "coefficientCount": int(mfcc.shape[0]),
            "mfccMean": np.mean(mfcc, axis=1).tolist() if mfcc.size > 0 else [],
            "mfccStd": np.std(mfcc, axis=1).tolist() if mfcc.size > 0 else [],
        },
    }


def _run_spectral_shape(y, sr, asset_payload, selection_payload):
    metrics = _build_common_metrics(y, sr, asset_payload, selection_payload)
    hop_length = metrics["hopLength"]
    frame_length = metrics["frameLength"]

    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, hop_length=hop_length, n_fft=frame_length).flatten()
    flatness = librosa.feature.spectral_flatness(y=y, hop_length=hop_length, n_fft=frame_length).flatten()
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr, hop_length=hop_length, n_fft=frame_length)

    return {
        "summary": {
            **metrics["common"],
            "selectionFrequencyWindow": metrics["frequencyWindow"],
            "spectralRolloffHz": _stats(rolloff),
            "spectralFlatness": _stats(flatness),
            "spectralContrastMean": np.mean(contrast, axis=1).tolist() if contrast.size > 0 else [],
            "spectralContrastStd": np.std(contrast, axis=1).tolist() if contrast.size > 0 else [],
        },
    }


def _run_export_time_slice_audio(y, sr, asset_payload, selection_payload):
    del asset_payload
    amplitude_range = normalize_selection_amplitude_pct_range(selection_payload)
    frequency_range = (selection_payload or {}).get("frequencyBinRange") or {}
    peak_abs = float(np.max(np.abs(y))) if y.size > 0 else 0.0
    rms_value = float(np.sqrt(np.mean(np.square(y)))) if y.size > 0 else 0.0

    return {
        "summary": {
            "exportType": "time-slice-audio",
            "sampleRate": int(sr),
            "sampleCount": int(y.shape[0]),
            "durationSec": float(y.shape[0] / sr) if sr else 0.0,
            "peakAbs": peak_abs,
            "rms": rms_value,
            "selectionFrequencyWindow": frequency_range,
            "selectionAmplitudePctRange": amplitude_range,
            "notes": [
                "This export uses the shared full-clip time slice.",
                "Frequency and amplitude sculpt masking are not yet applied in this export path.",
            ],
        },
        "saveArtifact": {
            "type": "wav",
            "audio": np.asarray(y, dtype=np.float32),
            "sampleRate": int(sr),
        },
    }


def _run_export_spectral_mask_audio(y, sr, asset_payload, selection_payload):
    hop_length = max(1, _coerce_int((asset_payload or {}).get("analysisHopLength"), DEFAULT_HOP_LENGTH))
    fft_nfft = max(128, _coerce_int((asset_payload or {}).get("analysisFftNfft"), DEFAULT_FFT_NFFT))
    stft = librosa.stft(y, n_fft=fft_nfft, hop_length=hop_length)
    magnitudes = np.abs(stft)

    available_bin_count = magnitudes.shape[0] if magnitudes.ndim == 2 else 0
    if available_bin_count <= 0:
        raise ValueError("Unable to build an STFT for the requested selection.")

    frequency_window = _resolve_frequency_window(asset_payload, selection_payload, available_bin_count)
    amplitude_range = normalize_selection_amplitude_pct_range(selection_payload, clamp_values=True)
    amplitude_min_pct = amplitude_range["min"]
    amplitude_max_pct = amplitude_range["max"]

    combined_mask = np.zeros_like(magnitudes, dtype=bool)
    selected_frequency_band = magnitudes[
        frequency_window["startBin"]:frequency_window["endBin"] + 1,
        :,
    ]
    selected_band_peak = float(np.max(selected_frequency_band)) if selected_frequency_band.size > 0 else 0.0
    amplitude_min_value = (amplitude_min_pct / 100.0) * selected_band_peak
    amplitude_max_value = (amplitude_max_pct / 100.0) * selected_band_peak

    if selected_frequency_band.size > 0:
        band_mask = np.logical_and(
            selected_frequency_band >= amplitude_min_value,
            selected_frequency_band <= amplitude_max_value,
        )
        combined_mask[
            frequency_window["startBin"]:frequency_window["endBin"] + 1,
            :,
        ] = band_mask

    masked_stft = np.where(combined_mask, stft, 0.0j)
    masked_audio = librosa.istft(masked_stft, hop_length=hop_length, length=y.shape[0])

    original_energy = float(np.sum(magnitudes)) if magnitudes.size > 0 else 0.0
    masked_energy = float(np.sum(np.abs(masked_stft))) if masked_stft.size > 0 else 0.0
    kept_energy_ratio = (masked_energy / original_energy) if original_energy > 0 else 0.0
    peak_abs = float(np.max(np.abs(masked_audio))) if masked_audio.size > 0 else 0.0
    rms_value = float(np.sqrt(np.mean(np.square(masked_audio)))) if masked_audio.size > 0 else 0.0
    frequency_axis = librosa.fft_frequencies(sr=sr, n_fft=fft_nfft)
    max_frequency_index = max(0, min(frequency_window["endBin"], frequency_axis.size - 1))
    min_frequency_index = max(0, min(frequency_window["startBin"], frequency_axis.size - 1))

    return {
        "summary": {
            "exportType": "spectral-mask-audio",
            "sampleRate": int(sr),
            "sampleCount": int(masked_audio.shape[0]),
            "durationSec": float(masked_audio.shape[0] / sr) if sr else 0.0,
            "peakAbs": peak_abs,
            "rms": rms_value,
            "hopLength": hop_length,
            "fftNfft": fft_nfft,
            "selectionFrequencyWindow": {
                **frequency_window,
                "startHz": float(frequency_axis[min_frequency_index]) if frequency_axis.size > 0 else 0.0,
                "endHz": float(frequency_axis[max_frequency_index]) if frequency_axis.size > 0 else 0.0,
            },
            "selectionAmplitudePctRange": {
                "min": amplitude_min_pct,
                "max": amplitude_max_pct,
                "resolvedMinMagnitude": amplitude_min_value,
                "resolvedMaxMagnitude": amplitude_max_value,
                "selectedBandPeakMagnitude": selected_band_peak,
            },
            "maskStats": {
                "keptCellCount": int(np.count_nonzero(combined_mask)),
                "totalCellCount": int(combined_mask.size),
                "keptEnergyRatio": kept_energy_ratio,
            },
            "notes": [
                "This export uses the shared full-clip time slice.",
                "The STFT is masked by the selected frequency band and by the selected amplitude range within that band before inverse reconstruction.",
            ],
        },
        "saveArtifact": {
            "type": "wav",
            "audio": np.asarray(masked_audio, dtype=np.float32),
            "sampleRate": int(sr),
        },
    }


RUNNER_FUNCTIONS = {
    "slice_summary": _run_slice_summary,
    "mfcc_profile": _run_mfcc_profile,
    "spectral_shape": _run_spectral_shape,
    "export_time_slice_audio": _run_export_time_slice_audio,
    "export_spectral_mask_audio": _run_export_spectral_mask_audio,
    "bioacoustics_import_workbook": _run_bioacoustics_import_workbook,
    "bioacoustics_sync_workbook": _run_bioacoustics_sync_workbook,
}


def _build_runner_registry(group):
    registry = {}
    for analysis_type, config in BACKEND_ANALYSIS_TYPE_CONFIGS.items():
        if config.get("group") != group:
            continue

        runner_key = str(config.get("runner") or "").strip()
        if not runner_key:
            raise KeyError(f"Backend analysis type '{analysis_type}' is missing a runner mapping.")
        if runner_key not in RUNNER_FUNCTIONS:
            raise KeyError(f"Backend runner function is not defined for key: {runner_key}")

        registry[analysis_type] = RUNNER_FUNCTIONS[runner_key]
    return registry


ANALYSIS_RUNNERS = _build_runner_registry("analysis")
BIOACOUSTICS_RUNNERS = _build_runner_registry("bioacoustics")


def _write_wav_pcm16(export_path, y, sr):
    audio = np.asarray(y, dtype=np.float32)
    if audio.ndim != 1:
        audio = np.reshape(audio, (-1,))
    clipped = np.clip(audio, -1.0, 1.0)
    pcm16 = np.asarray(np.round(clipped * 32767.0), dtype=np.int16)

    with wave.open(str(export_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(max(1, _coerce_int(sr, DEFAULT_SAMPLE_RATE)))
        wav_file.writeframes(pcm16.tobytes())


def _save_result(payload, save_artifact=None):
    save_options = payload.get("saveOptions") or {}
    save_mode = str(save_options.get("mode") or "json").strip().lower()
    if save_mode == "none":
        return {
            "mode": "none",
            "saved": False,
            "path": None,
        }

    export_dir = _project_root() / "data" / "exports" / "backend_calls"
    export_dir.mkdir(parents=True, exist_ok=True)

    asset = payload.get("asset") or {}
    call_meta = payload.get("callMeta") or {}
    label = save_options.get("label") or asset.get("label") or asset.get("id") or "selection-analysis"
    request_id = str(call_meta.get("requestId") or uuid4())[:8]

    if save_mode == "wav":
        if not isinstance(save_artifact, dict) or save_artifact.get("type") != "wav":
            raise ValueError("This backend action does not provide WAV export data.")

        filename = f"{_slugify(label)}_{_slugify(payload.get('analysisType'))}_{request_id}.wav"
        export_path = export_dir / filename
        audio_data = save_artifact.get("audio")
        if audio_data is None:
            audio_data = np.zeros(0, dtype=np.float32)
        _write_wav_pcm16(export_path, audio_data, save_artifact.get("sampleRate"))
        sample_rate = max(1, _coerce_int(save_artifact.get("sampleRate"), DEFAULT_SAMPLE_RATE))
        sample_count = int(np.asarray(audio_data, dtype=np.float32).size)
        return {
            "mode": "wav",
            "saved": True,
            "path": str(export_path.relative_to(_project_root())),
            "sampleRate": sample_rate,
            "sampleCount": sample_count,
            "durationSec": float(sample_count / sample_rate) if sample_rate else 0.0,
        }

    filename = f"{_slugify(label)}_{_slugify(payload.get('analysisType'))}_{request_id}.json"
    export_path = export_dir / filename

    with export_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    return {
        "mode": "json",
        "saved": True,
        "path": str(export_path.relative_to(_project_root())),
    }


def run():
    payload = _read_payload()
    analysis_type = normalize_backend_analysis_type(payload.get("analysisType") or DEFAULT_BACKEND_ANALYSIS_TYPE)
    if analysis_type not in ANALYSIS_RUNNERS and analysis_type not in BIOACOUSTICS_RUNNERS:
        raise ValueError(f"Unsupported analysis type: {analysis_type}")

    asset = payload.get("asset") or {}
    selection = payload.get("selection") or {}
    audio_path = None
    selection_window = None

    if analysis_type in BIOACOUSTICS_RUNNERS:
        runner_result = BIOACOUSTICS_RUNNERS[analysis_type](payload)
    else:
        if not selection.get("isReady"):
            raise ValueError("No ready SpectroTerrain selection was provided for backend analysis.")

        audio_path = _resolve_audio_path(asset)
        selection_window = _resolve_selection_window(asset, selection)

        target_sr = max(1, _coerce_int(asset.get("analysisSampleRate"), DEFAULT_SAMPLE_RATE))
        y, sr = librosa.load(
            str(audio_path),
            sr=target_sr,
            offset=selection_window["startSec"],
            duration=selection_window["durationSec"],
        )
        if y.size == 0:
            raise ValueError("The requested selection produced an empty audio slice.")

        runner_result = ANALYSIS_RUNNERS[analysis_type](y, sr, asset, selection)

    save_artifact = None
    save_result_override = None
    if isinstance(runner_result, dict) and isinstance(runner_result.get("saveArtifact"), dict):
        save_artifact = runner_result.get("saveArtifact")
        result = {
            key: value
            for key, value in runner_result.items()
            if key != "saveArtifact"
        }
    else:
        result = runner_result

    if isinstance(result, dict) and isinstance(result.get("saveResult"), dict):
        save_result_override = result.get("saveResult")
        result = {
            key: value
            for key, value in result.items()
            if key != "saveResult"
        }

    response = {
        "ok": True,
        "analysisType": analysis_type,
        "callMeta": {
            "requestId": str((payload.get("callMeta") or {}).get("requestId") or uuid4()),
            "requestedAt": (payload.get("callMeta") or {}).get("requestedAt"),
            "completedAt": datetime.now(timezone.utc).isoformat(),
        },
        "asset": {
            "id": asset.get("id"),
            "label": asset.get("label"),
            "audioUrl": asset.get("audioUrl"),
            "audioPath": str(audio_path.relative_to(_project_root())) if isinstance(audio_path, Path) else None,
        },
        "selection": {
            **selection,
            "resolvedTimeWindow": selection_window,
        },
        "bioacoustics": payload.get("bioacoustics") or {},
        "saveOptions": payload.get("saveOptions") or {},
        "result": result,
    }
    response["saveResult"] = save_result_override or _save_result(response, save_artifact=save_artifact)
    return _rounded(response)


def main():
    try:
        response = run()
        sys.stdout.write(json.dumps(response))
        sys.stdout.flush()
        return 0
    except Exception as error:
        failure = {
            "ok": False,
            "error": str(error),
            "traceback": traceback.format_exc(),
        }
        sys.stdout.write(json.dumps(failure))
        sys.stdout.flush()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())