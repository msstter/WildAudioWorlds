"""Shared spectral profile and cosine-similarity helpers.

These functions form the first dedicated analysis-layer slice so the workbench
and onset-finder can reuse the same spectral-template logic without housing the
algorithms inside GUI or pipeline entrypoint modules.
"""

from __future__ import annotations

import librosa
import numpy as np


def build_spectral_profile(y, sr, regions, n_fft=2048, hop_length=512):
    """Build a spectral template from positive focus regions."""
    pos = [r for r in regions if r.get("polarity") == "positive"]
    if not pos or len(y) == 0:
        return None

    spectra = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    times_arr = librosa.frames_to_time(
        np.arange(spectra.shape[1]),
        sr=sr,
        hop_length=hop_length,
    )

    weighted_sum = np.zeros(len(freqs), dtype=float)
    total_weight = 0.0

    for region in pos:
        time_mask = (times_arr >= region["t_start"]) & (times_arr <= region["t_end"])
        freq_mask = (freqs >= region.get("f_low", 0)) & (freqs <= region.get("f_high", sr / 2))
        if not np.any(time_mask) or not np.any(freq_mask):
            continue

        sub_spectra = spectra[:, time_mask]
        region_mean = sub_spectra.mean(axis=1)
        region_mean[~freq_mask] = 0.0
        n_frames = int(time_mask.sum())
        weighted_sum += region_mean * n_frames
        total_weight += n_frames

    if total_weight == 0:
        return None

    mean_spectrum = weighted_sum / total_weight
    norm = np.linalg.norm(mean_spectrum)
    if norm > 0:
        mean_spectrum = mean_spectrum / norm

    f_low = min(region.get("f_low", 0) for region in pos)
    f_high = max(region.get("f_high", sr / 2) for region in pos)
    return {
        "mean_spectrum": mean_spectrum,
        "freqs": freqs,
        "f_low": f_low,
        "f_high": f_high,
    }


def compute_spectral_similarity_at_time(
    candidate_time: float,
    y: np.ndarray,
    sr: int,
    profile: dict | None,
    *,
    window_sec: float = 0.1,
    n_fft: int = 2048,
    hop_length: int = 512,
) -> float | None:
    """Return cosine similarity between a candidate window and a spectral template."""
    if profile is None:
        return None

    ref = profile.get("mean_spectrum")
    if ref is None:
        return None

    ref = np.asarray(ref, dtype=float)
    ref_norm = np.linalg.norm(ref)
    if ref_norm == 0:
        return None

    half_win = int(window_sec * sr / 2)
    centre = int(candidate_time * sr)
    start = max(0, centre - half_win)
    end = min(len(y), centre + half_win)
    if end - start < n_fft:
        return None

    segment = y[start:end]
    spectra = np.abs(librosa.stft(segment, n_fft=n_fft, hop_length=hop_length))
    seg_spectrum = spectra.mean(axis=1)
    seg_norm = np.linalg.norm(seg_spectrum)
    if seg_norm == 0:
        return 0.0

    return float(np.dot(ref, seg_spectrum / seg_norm))


def gate_onsets_by_spectral_match(
    onset_times,
    y,
    sr,
    profile,
    threshold=0.3,
    n_fft=2048,
    hop_length=512,
    window_sec=0.1,
):
    """Keep only onsets whose local spectrum matches the spectral profile."""
    if profile is None or len(onset_times) == 0:
        return np.array(onset_times, dtype=float)

    times = np.array(onset_times, dtype=float)
    ref = profile["mean_spectrum"]
    ref_norm = np.linalg.norm(ref)
    if ref_norm == 0:
        return times

    keep = np.ones(len(times), dtype=bool)
    for index, onset_time in enumerate(times):
        similarity = compute_spectral_similarity_at_time(
            float(onset_time),
            y,
            sr,
            profile,
            window_sec=window_sec,
            n_fft=n_fft,
            hop_length=hop_length,
        )
        if similarity is None:
            continue
        if similarity < threshold:
            keep[index] = False

    return times[keep]