"""Shared signal-profile analysis helpers.

These helpers are used by the interactive signal selector, the Audio
Workbench, and downstream analyzers. Keeping them here separates the pure
feature-extraction logic from the selector UI and compatibility scripts.
"""

from __future__ import annotations

import librosa
import numpy as np


def compute_spectrogram(y, sr, n_fft=2048, hop_length=512):
    """Return log-power spectrogram, frequencies, and times arrays."""
    spectra = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop_length))
    spectra_db = librosa.amplitude_to_db(spectra, ref=np.max)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    times = librosa.frames_to_time(
        np.arange(spectra.shape[1]),
        sr=sr,
        hop_length=hop_length,
    )
    return spectra_db, freqs, times


def analyze_region(y, sr, t_start, t_end, f_low, f_high, n_fft=2048, hop_length=512):
    """Extract spectral and temporal features from a selected region."""
    sample_start = max(0, int(t_start * sr))
    sample_end = min(len(y), int(t_end * sr))
    segment = y[sample_start:sample_end]

    if len(segment) < n_fft:
        segment = np.pad(segment, (0, n_fft - len(segment)))

    spectra = np.abs(librosa.stft(segment, n_fft=n_fft, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    freq_mask = (freqs >= f_low) & (freqs <= f_high)
    region_spectra = spectra[freq_mask, :]

    mean_spectrum = np.mean(region_spectra, axis=1) if region_spectra.size > 0 else np.array([0.0])
    peak_freq_idx = int(np.argmax(mean_spectrum)) if mean_spectrum.size > 0 else 0
    region_freqs = freqs[freq_mask]
    peak_freq = (
        float(region_freqs[peak_freq_idx])
        if len(region_freqs) > 0
        else float(f_low + f_high) / 2.0
    )

    total_energy = float(np.sum(spectra ** 2))
    region_energy = float(np.sum(region_spectra ** 2))
    energy_ratio = region_energy / max(total_energy, 1e-10)

    region_envelope = np.sum(region_spectra ** 2, axis=0)
    if len(region_envelope) > 1:
        env_diff = np.diff(region_envelope)
        attack_sharpness = float(np.max(env_diff) / (np.max(region_envelope) + 1e-10))
    else:
        attack_sharpness = 0.0

    try:
        harmonic, percussive = librosa.decompose.hpss(spectra)
        harmonic_energy = float(np.sum(harmonic[freq_mask, :] ** 2))
        percussive_energy = float(np.sum(percussive[freq_mask, :] ** 2))
        harmonicity = harmonic_energy / max(harmonic_energy + percussive_energy, 1e-10)
    except Exception:
        harmonicity = 0.5

    if region_spectra.size > 0 and region_freqs.size > 0:
        weighted = mean_spectrum * region_freqs
        centroid = float(np.sum(weighted) / max(np.sum(mean_spectrum), 1e-10))
        variance = np.sum(mean_spectrum * (region_freqs - centroid) ** 2) / max(np.sum(mean_spectrum), 1e-10)
        bandwidth = float(np.sqrt(max(variance, 0.0)))
    else:
        centroid = peak_freq
        bandwidth = (f_high - f_low) / 2.0

    return {
        "t_start": round(t_start, 4),
        "t_end": round(t_end, 4),
        "f_low": round(f_low, 1),
        "f_high": round(f_high, 1),
        "duration_s": round(t_end - t_start, 4),
        "peak_frequency_hz": round(peak_freq, 1),
        "spectral_centroid_hz": round(centroid, 1),
        "spectral_bandwidth_hz": round(bandwidth, 1),
        "energy_ratio": round(energy_ratio, 4),
        "attack_sharpness": round(attack_sharpness, 4),
        "harmonicity": round(harmonicity, 4),
    }


def summarize_signal_region_analyses(analyses: list[dict]) -> dict:
    """Build a compact signal-profile summary from per-region analyses."""
    if not analyses:
        return {}

    all_f_low = min(analysis["f_low"] for analysis in analyses)
    all_f_high = max(analysis["f_high"] for analysis in analyses)
    avg_centroid = float(np.mean([analysis["spectral_centroid_hz"] for analysis in analyses]))
    avg_bandwidth = float(np.mean([analysis["spectral_bandwidth_hz"] for analysis in analyses]))
    avg_harmonicity = float(np.mean([analysis["harmonicity"] for analysis in analyses]))
    avg_sharpness = float(np.mean([analysis["attack_sharpness"] for analysis in analyses]))
    avg_energy_ratio = float(np.mean([analysis["energy_ratio"] for analysis in analyses]))
    avg_duration = float(np.mean([analysis["duration_s"] for analysis in analyses]))

    if avg_harmonicity > 0.65:
        character = "harmonic"
    elif avg_harmonicity < 0.35:
        character = "percussive"
    else:
        character = "mixed"

    return {
        "freq_range_hz": [round(all_f_low, 1), round(all_f_high, 1)],
        "spectral_centroid_hz": round(avg_centroid, 1),
        "spectral_bandwidth_hz": round(avg_bandwidth, 1),
        "harmonicity": round(avg_harmonicity, 4),
        "attack_sharpness": round(avg_sharpness, 4),
        "energy_ratio": round(avg_energy_ratio, 4),
        "avg_signal_duration_s": round(avg_duration, 4),
        "signal_character": character,
        "n_regions": len(analyses),
    }


def build_signal_profile(y, sr, regions):
    """Build a complete signal profile from a list of selected regions."""
    analyses = []
    for region in regions:
        analysis = analyze_region(
            y,
            sr,
            region["t_start"],
            region["t_end"],
            region["f_low"],
            region["f_high"],
        )
        if "polarity" in region:
            analysis["polarity"] = region["polarity"]
        analyses.append(analysis)

    if not analyses:
        return {"regions": [], "summary": {}, "sr": sr}

    return {
        "sr": sr,
        "regions": analyses,
        "summary": summarize_signal_region_analyses(analyses),
    }


def build_per_signal_profiles(y, sr, regions):
    """Build one signal-profile payload per selected region."""
    profiles = []
    for index, region in enumerate(regions):
        analysis = analyze_region(
            y,
            sr,
            region["t_start"],
            region["t_end"],
            region.get("f_low", 0),
            region.get("f_high", sr / 2),
        )
        profiles.append(
            {
                "index": index,
                "region": dict(region),
                "analysis": analysis,
            }
        )
    return profiles


def cluster_signal_regions(region_analyses: list[dict], max_clusters: int = 6) -> dict:
    """Cluster analysed positive regions by spectral similarity."""
    n_regions = len(region_analyses)
    if n_regions <= 1:
        return {
            "n_clusters": 1,
            "labels": [0] * n_regions,
            "descriptions": ["All regions — single group"],
        }

    features = np.array(
        [
            [
                region.get("spectral_centroid_hz", 0),
                region.get("spectral_bandwidth_hz", 0),
                region.get("harmonicity", 0),
                region.get("attack_sharpness", 0),
            ]
            for region in region_analyses
        ],
        dtype=float,
    )

    stds = features.std(axis=0)
    means = features.mean(axis=0)
    meaningful = stds > 1e-6
    stds_safe = np.where(meaningful, stds, 1.0)
    features_norm = (features - means) / stds_safe
    features_norm[:, ~meaningful] = 0.0

    centroid_cv = stds[0] / max(abs(means[0]), 1.0)
    bandwidth_cv = stds[1] / max(abs(means[1]), 1.0)
    harmonicity_std = stds[2]
    sharpness_std = stds[3]
    if centroid_cv < 0.15 and bandwidth_cv < 0.15 and harmonicity_std < 0.15 and sharpness_std < 0.15:
        return {
            "n_clusters": 1,
            "labels": [0] * n_regions,
            "descriptions": ["All regions — spectrally similar"],
        }

    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import pdist

    dists = pdist(features_norm, metric="euclidean")
    linkage_matrix = linkage(dists, method="ward")

    max_k = min(max_clusters, n_regions)
    merge_dists = linkage_matrix[:, 2]
    if len(merge_dists) >= 2:
        gaps = np.diff(merge_dists)
        candidate_indices = list(range(max(0, len(gaps) - max_k + 1), len(gaps)))
        if candidate_indices:
            best_gap_idx = candidate_indices[int(np.argmax(gaps[candidate_indices]))]
            n_clusters = len(merge_dists) - best_gap_idx
            n_clusters = max(1, min(n_clusters, max_k))
        else:
            n_clusters = 1
    else:
        n_clusters = 1

    if n_clusters > 1:
        total_range = merge_dists[-1] - merge_dists[0] if len(merge_dists) > 1 else 1.0
        best_gap = float(np.max(np.diff(merge_dists))) if len(merge_dists) > 1 else 0.0
        if total_range > 0 and best_gap / total_range < 0.15:
            n_clusters = 1
        elif merge_dists[-1] < 1.0:
            n_clusters = 1

    labels = [label - 1 for label in fcluster(linkage_matrix, t=n_clusters, criterion="maxclust").tolist()]

    descriptions = []
    for cluster_id in range(n_clusters):
        members = [region_analyses[i] for i, label in enumerate(labels) if label == cluster_id]
        if not members:
            descriptions.append(f"Cluster {cluster_id + 1}: (empty)")
            continue

        avg_cent = float(np.mean([member["spectral_centroid_hz"] for member in members]))
        avg_harm = float(np.mean([member["harmonicity"] for member in members]))
        f_lows = [member["f_low"] for member in members]
        f_highs = [member["f_high"] for member in members]
        character = "harmonic" if avg_harm > 0.65 else ("percussive" if avg_harm < 0.35 else "mixed")
        descriptions.append(
            f"Cluster {cluster_id + 1}: {len(members)} region(s), "
            f"{min(f_lows):.0f}-{max(f_highs):.0f} Hz, "
            f"centroid {avg_cent:.0f} Hz, {character}"
        )

    return {
        "n_clusters": n_clusters,
        "labels": labels,
        "descriptions": descriptions,
    }


__all__ = [
    "analyze_region",
    "build_per_signal_profiles",
    "build_signal_profile",
    "cluster_signal_regions",
    "compute_spectrogram",
    "summarize_signal_region_analyses",
]