from core.audio_processor import AudioProcessor
from core.dim_reduction import DimensionalityReducer
import numpy as np
import os
import json
import shutil
from pathlib import Path

from shared_graph_paths import resolve_graph_project_root
from wild_audio_worlds.data.audio_asset_store import (
    build_project_paths as _shared_build_project_paths,
    load_manifest_entries as _shared_load_manifest_entries,
)
from wild_audio_worlds.data.data_manager import DataManager


DEFAULT_TERRAIN_ENVELOPE_VERSION = 2
DEFAULT_TERRAIN_ENVELOPE_KIND = "terrain-envelope-v2"
DEFAULT_TERRAIN_ENVELOPE_BIN_COUNT = 128
DEFAULT_TERRAIN_ENVELOPE_SMOOTHING = 0.65
DEFAULT_TERRAIN_ENVELOPE_POWER = 0.45
DEFAULT_TERRAIN_ENVELOPE_AMP_PADDING_PERCENT = 5.0
DEFAULT_TERRAIN_ENVELOPE_INTENSITY_SCALE = 255
TIMING_COLUMN_NAMES = (
    "Frame_Index",
    "Time_Start_Sec",
    "Time_Center_Sec",
    "Time_End_Sec",
    "Sample_Start",
    "Sample_Center",
    "Sample_End",
)


def _build_timing_export_matrix(frame_metadata):
    return np.column_stack((
        frame_metadata["frame_indices"],
        frame_metadata["time_starts_sec"],
        frame_metadata["time_centers_sec"],
        frame_metadata["time_ends_sec"],
        frame_metadata["sample_starts"],
        frame_metadata["sample_centers"],
        frame_metadata["sample_ends"],
    ))


def _build_analysis_manifest_fields(frame_metadata):
    sample_rate = frame_metadata["sample_rate"]
    hop_length = frame_metadata["hop_length"]
    frame_length = frame_metadata["frame_length"]
    hop_duration_sec = float(hop_length / sample_rate) if sample_rate else 0.0
    window_duration_sec = float(frame_length / sample_rate) if sample_rate else 0.0

    return {
        "analysisSampleRate": int(sample_rate),
        "analysisHopLength": int(hop_length),
        "analysisFrameLength": int(frame_length),
        "analysisFrameCount": int(frame_metadata["frame_count"]),
        "analysisFrameDurationSec": hop_duration_sec,
        "analysisHopDurationSec": hop_duration_sec,
        "analysisWindowDurationSec": window_duration_sec,
        "analysisClipDurationSec": float(frame_metadata["clip_duration_sec"]),
        "analysisFftNfft": int(frame_metadata["fft_nfft"]),
        "analysisTimeColumns": {
            "frameIndex": TIMING_COLUMN_NAMES[0],
            "timeStartSec": TIMING_COLUMN_NAMES[1],
            "timeCenterSec": TIMING_COLUMN_NAMES[2],
            "timeEndSec": TIMING_COLUMN_NAMES[3],
            "sampleStart": TIMING_COLUMN_NAMES[4],
            "sampleCenter": TIMING_COLUMN_NAMES[5],
            "sampleEnd": TIMING_COLUMN_NAMES[6],
        },
    }


def _audio_display_name(path_obj, duplicate_count):
    stem = path_obj.stem
    if duplicate_count > 1:
        return f"{stem} ({path_obj.suffix.lstrip('.')})"
    return stem


def _resample_fft_frame(frame_row, target_bin_count):
    if frame_row.size == 0:
        return np.zeros(target_bin_count, dtype=np.float32)

    if frame_row.size == target_bin_count:
        return frame_row.astype(np.float32, copy=True)

    sample_positions = np.linspace(0, frame_row.size - 1, target_bin_count)
    sample_indices = np.rint(sample_positions).astype(np.int32)
    return frame_row[sample_indices].astype(np.float32, copy=False)


def _build_terrain_envelope_helper(
    fft_bins,
    target_bin_count=DEFAULT_TERRAIN_ENVELOPE_BIN_COUNT,
    smoothing=DEFAULT_TERRAIN_ENVELOPE_SMOOTHING,
    power=DEFAULT_TERRAIN_ENVELOPE_POWER,
    amplitude_padding_percent=DEFAULT_TERRAIN_ENVELOPE_AMP_PADDING_PERCENT,
):
    frame_count = int(fft_bins.shape[0]) if fft_bins.ndim == 2 else 0
    source_bin_count = int(fft_bins.shape[1]) if fft_bins.ndim == 2 and fft_bins.size > 0 else 0
    amplitude_max = float(np.max(fft_bins)) if fft_bins.size > 0 else 0.0
    padded_amplitude_max = amplitude_max * (1.0 + max(0.0, amplitude_padding_percent) / 100.0) if amplitude_max > 0 else 1.0

    smoothing_state = np.zeros(target_bin_count, dtype=np.float32)
    peak_smoothed_values = np.zeros(frame_count, dtype=np.float32)
    peak_display_bins = np.zeros(frame_count, dtype=np.int32)
    wall_spectrogram_display_bins = np.zeros((frame_count, target_bin_count), dtype=np.int32)
    wall_spectrogram_intensity_bytes = np.zeros((frame_count, target_bin_count), dtype=np.uint8)
    amplitude_levels = np.linspace(0.0, 1.0, target_bin_count, dtype=np.float32) if target_bin_count > 1 else np.zeros(1, dtype=np.float32)
    intensity_scale_factor = max(4.0, target_bin_count * 0.55)

    for frame_index in range(frame_count):
        frame_row = _resample_fft_frame(fft_bins[frame_index], target_bin_count)
        clamped = np.clip(frame_row, 0.0, padded_amplitude_max)
        normalized = clamped / padded_amplitude_max
        enhanced = np.power(normalized, power).astype(np.float32, copy=False)
        smoothing_state = (smoothing_state * smoothing) + (enhanced * (1.0 - smoothing))

        peak_value = float(np.max(smoothing_state)) if smoothing_state.size > 0 else 0.0
        peak_indices = np.flatnonzero(smoothing_state >= peak_value)
        peak_index = int(peak_indices[-1]) if peak_indices.size > 0 else 0

        peak_smoothed_values[frame_index] = peak_value
        peak_display_bins[frame_index] = peak_index

        distance_grid = np.abs(smoothing_state[:, np.newaxis] - amplitude_levels[np.newaxis, :])
        best_bin_indices = np.argmin(distance_grid, axis=0).astype(np.int32, copy=False)
        best_distances = distance_grid[best_bin_indices, np.arange(target_bin_count)]
        intensities = np.clip(1.0 - (best_distances * intensity_scale_factor), 0.0, 1.0)

        wall_spectrogram_display_bins[frame_index, :] = best_bin_indices
        wall_spectrogram_intensity_bytes[frame_index, :] = np.rint(intensities * DEFAULT_TERRAIN_ENVELOPE_INTENSITY_SCALE).astype(np.uint8, copy=False)

    return {
        "version": DEFAULT_TERRAIN_ENVELOPE_VERSION,
        "kind": DEFAULT_TERRAIN_ENVELOPE_KIND,
        "frameCount": frame_count,
        "sourceBinCount": source_bin_count,
        "displayBinCount": target_bin_count,
        "smoothing": smoothing,
        "powerExponent": power,
        "amplitudePaddingPercent": amplitude_padding_percent,
        "wallSpectrogramIntensityScale": DEFAULT_TERRAIN_ENVELOPE_INTENSITY_SCALE,
        "peakSmoothedValues": peak_smoothed_values.tolist(),
        "peakDisplayBins": peak_display_bins.tolist(),
        "wallSpectrogramDisplayBins": wall_spectrogram_display_bins.reshape(-1).tolist(),
        "wallSpectrogramIntensityBytes": wall_spectrogram_intensity_bytes.reshape(-1).tolist(),
    }


def _build_short_clip_coords(feature_matrix):
    frame_count = int(feature_matrix.shape[0]) if getattr(feature_matrix, "ndim", 0) == 2 else 0
    coords = np.zeros((frame_count, 3), dtype=np.float32)
    if frame_count <= 0:
        return coords

    if frame_count > 1:
        coords[:, 0] = np.linspace(-1.0, 1.0, frame_count, dtype=np.float32)

    for feature_index in range(min(2, feature_matrix.shape[1] if getattr(feature_matrix, "ndim", 0) == 2 else 0)):
        feature_values = feature_matrix[:, feature_index].astype(np.float32, copy=False)
        feature_min = float(np.min(feature_values))
        feature_range = float(np.max(feature_values) - feature_min) or 1.0
        coords[:, feature_index + 1] = ((feature_values - feature_min) / feature_range) - 0.5

    return coords


def _reduce_features_to_3d(feature_matrix, dim_reducer=None, logger=print):
    frame_count = int(feature_matrix.shape[0]) if getattr(feature_matrix, "ndim", 0) == 2 else 0
    if frame_count <= 0:
        raise ValueError("Audio analysis did not produce any MFCC frames for 3D export.")

    log = logger if callable(logger) else (lambda *_args, **_kwargs: None)
    if frame_count < 4:
        log("Using short-clip fallback coordinates instead of UMAP.")
        return _build_short_clip_coords(feature_matrix)

    dim_reducer = dim_reducer or DimensionalityReducer(n_neighbors=15, min_dist=0.1)
    log("Reducing dimensions to 3D...")
    try:
        return dim_reducer.reduce_to_3d(feature_matrix)
    except Exception as error:
        log(f"UMAP reduction failed; using short-clip fallback coordinates instead. ({error})")
        return _build_short_clip_coords(feature_matrix)


def _list_audio_files(sample_audio_dir):
    supported = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac"}
    return sorted(
        path for path in Path(sample_audio_dir).iterdir()
        if path.is_file() and path.suffix.lower() in supported
    )


def build_project_paths(project_root=None):
    resolved_project_root = resolve_graph_project_root(project_root, anchor_file=__file__)
    return _shared_build_project_paths(resolved_project_root)


def _build_data_manager(project_root=None):
    resolved_project_root = resolve_graph_project_root(project_root, anchor_file=__file__)
    return DataManager(resolved_project_root)


def _resolve_project_root_from_manifest_path(manifest_path):
    return DataManager.resolve_project_root_from_manifest_path(manifest_path)


def load_manifest_entries(manifest_path):
    project_root = _resolve_project_root_from_manifest_path(manifest_path)
    return _build_data_manager(project_root).load_manifest_entries()


def save_manifest_entries(manifest_path, manifest_entries):
    project_root = _resolve_project_root_from_manifest_path(manifest_path)
    _build_data_manager(project_root).save_manifest_entries(manifest_entries)


def upsert_manifest_entry(manifest_path, manifest_entry):
    project_root = _resolve_project_root_from_manifest_path(manifest_path)
    return _build_data_manager(project_root).upsert_manifest_entry(manifest_entry).get("assets", [])


def process_audio_file(audio_file, include_mfcc=True, display_name=None, project_root=None, logger=print, audio_proc=None, dim_reducer=None):
    audio_path = Path(audio_file).resolve()
    data_manager = _build_data_manager(project_root)
    log = logger if callable(logger) else (lambda *_args, **_kwargs: None)
    display_name = str(display_name or "").strip() or _audio_display_name(audio_path, 1)
    audio_proc = audio_proc or AudioProcessor()

    log(f"Processing {audio_path.name}...")
    features, volume_rms, pitch_f0, fft_bins, frame_metadata = audio_proc.extract_features(str(audio_path))
    log(f"Extracted feature shape: {features.shape}")

    mfcc_csv_name = None
    if include_mfcc:
        coords_3d = _reduce_features_to_3d(features, dim_reducer=dim_reducer, logger=log)
        log(f"Reduced coordinate shape: {coords_3d.shape}")

        export_matrix = np.column_stack((
            coords_3d,
            volume_rms,
            pitch_f0,
            _build_timing_export_matrix(frame_metadata),
        ))
        dynamic_labels = ",".join((
            "Audio_UMAP_X",
            "Audio_UMAP_Y",
            "Audio_UMAP_Z",
            "Volume",
            "Pitch",
            *TIMING_COLUMN_NAMES,
        ))
        mfcc_csv_name = f"{audio_path.stem}_MFCC.csv"
    else:
        log("Skipping MFCC / TimbreCube export for this asset.")
        export_matrix = None
        dynamic_labels = ""
        mfcc_csv_name = None

    fft_header = ",".join(f"FFT_Bin_{i}" for i in range(fft_bins.shape[1]))
    terrain_envelope = _build_terrain_envelope_helper(fft_bins)
    fft_csv_name = f"{audio_path.stem}_FFTs.csv"
    terrain_envelope_name = f"{audio_path.stem}_TerrainEnvelope.json"

    return data_manager.publish_graph_asset_artifacts(
        source_audio_path=audio_path,
        display_name=display_name,
        fft_export_matrix=fft_bins,
        fft_header=fft_header,
        fft_file_name=fft_csv_name,
        terrain_envelope=terrain_envelope,
        terrain_file_name=terrain_envelope_name,
        mfcc_export_matrix=export_matrix,
        mfcc_header=dynamic_labels,
        mfcc_file_name=mfcc_csv_name,
        manifest_fields=_build_analysis_manifest_fields(frame_metadata),
    )

def process_offline_audio():
    # 1. Define paths (relative to this script's location)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    paths = build_project_paths(project_root)
    sample_audio_dir = paths["sample_audio_dir"]
    manifest_path = paths["manifest_path"]

    audio_files = _list_audio_files(sample_audio_dir)
    if not audio_files:
        print(f"Error: No audio files found in {sample_audio_dir}")
        return

    duplicate_counts = {}
    for audio_file in audio_files:
        duplicate_counts[audio_file.stem] = duplicate_counts.get(audio_file.stem, 0) + 1

    manifest = []
    audio_proc = AudioProcessor()
    dim_reducer = DimensionalityReducer(n_neighbors=15, min_dist=0.1)

    for audio_file in audio_files:
        display_name = _audio_display_name(audio_file, duplicate_counts[audio_file.stem])
        manifest.append(process_audio_file(
            audio_file,
            include_mfcc=True,
            display_name=display_name,
            project_root=project_root,
            logger=print,
            audio_proc=audio_proc,
            dim_reducer=dim_reducer,
        ))

    save_manifest_entries(manifest_path, manifest)

    print(f"Saved manifest to {manifest_path}")
    print("Phase 1 Complete! You now have per-clip coordinate, timing-aware MFCC, FFT, audio, and optional terrain envelope exports.")

if __name__ == "__main__":
    process_offline_audio()