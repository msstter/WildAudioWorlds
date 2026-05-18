"""Shared MFCC-template cleaning helpers."""

from __future__ import annotations

import numpy as np


def clean_audio_with_mfcc_template(
    y_raw: np.ndarray,
    sr: int,
    templates: list[np.ndarray],
    *,
    threshold_percentile: float = 15.0,
    n_mfcc: int = 13,
    hop_length: int = 512,
    smooth_ms: float = 50.0,
) -> np.ndarray:
    """Isolate sections of ``y_raw`` that acoustically resemble the given templates."""
    try:
        import librosa
    except ImportError as exc:
        raise ImportError(
            "librosa is required for MFCC audio cleaning. Install it with: pip install librosa"
        ) from exc
    try:
        from scipy.ndimage import gaussian_filter1d
    except ImportError as exc:
        raise ImportError(
            "scipy is required for MFCC audio cleaning. Install it with: pip install scipy"
        ) from exc

    if not templates:
        raise ValueError("At least one template must be provided.")

    y_raw = np.asarray(y_raw, dtype=np.float32)
    if y_raw.ndim != 1:
        raise ValueError("y_raw must be a 1-D (mono) array.")
    if len(y_raw) == 0:
        return y_raw.copy()

    mfcc_raw = librosa.feature.mfcc(
        y=y_raw,
        sr=sr,
        n_mfcc=n_mfcc,
        hop_length=hop_length,
    )
    raw_frames = mfcc_raw.shape[1]

    all_dist_arrays: list[np.ndarray] = []
    for y_temp in templates:
        y_temp = np.asarray(y_temp, dtype=np.float32)
        if y_temp.ndim != 1 or len(y_temp) == 0:
            continue

        mfcc_temp = librosa.feature.mfcc(
            y=y_temp,
            sr=sr,
            n_mfcc=n_mfcc,
            hop_length=hop_length,
        )
        temp_frames = mfcc_temp.shape[1]
        if temp_frames < 1:
            continue

        dist_arr = np.zeros(raw_frames, dtype=np.float64)
        if temp_frames >= raw_frames:
            overlap = min(temp_frames, raw_frames)
            global_dist = float(np.linalg.norm(mfcc_raw - mfcc_temp[:, :overlap]))
            dist_arr[:] = global_dist
        else:
            half = temp_frames // 2
            for frame_index in range(raw_frames - temp_frames):
                window = mfcc_raw[:, frame_index : frame_index + temp_frames]
                dist_arr[frame_index + half] = float(np.linalg.norm(window - mfcc_temp))

            interior = dist_arr[half : raw_frames - half]
            interior_max = float(interior.max()) if len(interior) else float(dist_arr.max())
            if interior_max == 0.0:
                interior_max = 1.0
            dist_arr[:half] = interior_max
            dist_arr[raw_frames - half :] = interior_max

        d_min, d_max = dist_arr.min(), dist_arr.max()
        if d_max > d_min:
            dist_arr = (dist_arr - d_min) / (d_max - d_min)
        else:
            dist_arr[:] = 0.5

        all_dist_arrays.append(dist_arr)

    if not all_dist_arrays:
        return y_raw.copy()

    distances = np.min(np.stack(all_dist_arrays, axis=0), axis=0)
    cutoff = float(np.percentile(distances, float(threshold_percentile)))
    mask_frames = (distances <= cutoff).astype(np.float32)

    if smooth_ms > 0.0:
        frames_per_ms = sr / hop_length / 1000.0
        smooth_frames = smooth_ms * frames_per_ms
        sigma = max(smooth_frames / 3.0, 0.5)
        mask_frames = gaussian_filter1d(mask_frames, sigma=sigma)
        mask_frames = np.clip(mask_frames, 0.0, 1.0)

    raw_frame_indices = np.arange(raw_frames, dtype=np.float64)
    sample_centers = librosa.frames_to_samples(raw_frame_indices.astype(int), hop_length=hop_length).astype(np.float64)
    sample_centers = np.clip(sample_centers, 0, len(y_raw) - 1)
    sample_positions = np.arange(len(y_raw), dtype=np.float64)
    mask_audio = np.interp(sample_positions, sample_centers, mask_frames.astype(np.float64))
    mask_audio = np.asarray(mask_audio, dtype=np.float32)

    return y_raw * mask_audio


__all__ = ["clean_audio_with_mfcc_template"]