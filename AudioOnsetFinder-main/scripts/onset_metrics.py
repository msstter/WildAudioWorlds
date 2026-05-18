"""Shared dyad and rhythm-metric helpers for onset extraction pipelines."""

from __future__ import annotations

import numpy as np
from scipy.stats import entropy


def is_stable_match(interval_a_ms, interval_b_ms, tolerance):
    """Return True when two alternating intervals differ by no more than the tolerance."""
    largest_interval = max(interval_a_ms, interval_b_ms)
    if largest_interval <= 0:
        return False
    return abs(interval_a_ms - interval_b_ms) / largest_interval <= tolerance


def get_stable_dyad_flags(intervals_ms, tolerance):
    """Flag dyads that belong to locally stable alternating interval patterns."""
    dyad_count = max(len(intervals_ms) - 1, 0)
    stable_flags = []

    for index in range(dyad_count):
        comparisons = []

        if index + 2 < len(intervals_ms):
            comparisons.append(is_stable_match(intervals_ms[index], intervals_ms[index + 2], tolerance))

        if index + 3 < len(intervals_ms):
            comparisons.append(is_stable_match(intervals_ms[index + 1], intervals_ms[index + 3], tolerance))

        stable_flags.append(bool(comparisons) and all(comparisons))

    return stable_flags


def build_dyad_records(filename, intervals_ms, stable_flags):
    """Convert an interval sequence into dyadic-event rows for export and plotting."""
    records = []

    for index in range(len(intervals_ms) - 1):
        interval_1 = float(intervals_ms[index])
        interval_2 = float(intervals_ms[index + 1])
        cycle_duration = interval_1 + interval_2
        short_interval = min(interval_1, interval_2)
        long_interval = max(interval_1, interval_2)
        rhythm_ratio = interval_1 / cycle_duration if cycle_duration > 0 else 0

        records.append(
            {
                "File Name": filename,
                "Dyad Index": index + 1,
                "Interval 1 (ms)": round(interval_1, 2),
                "Interval 2 (ms)": round(interval_2, 2),
                "Cycle Duration [cd] (ms)": round(cycle_duration, 2),
                "Short Interval [i_s] (ms)": round(short_interval, 2),
                "Long Interval [i_l] (ms)": round(long_interval, 2),
                "Rhythm Ratio [r_k]": round(rhythm_ratio, 4),
                "Stable Rhythm": stable_flags[index],
            }
        )

    return records


def calculate_rhythm_metrics(intervals_seconds, dyad_records):
    """Calculate file-level rhythm summary statistics from intervals and dyads."""
    if len(intervals_seconds) < 2 or not dyad_records:
        return {
            "Average Cycle Duration (ms)": None,
            "nPVI (Isochrony)": None,
            "CV of Intervals": None,
            "r_k Std Dev": None,
            "r_k Entropy (Categorical Measure)": None,
        }

    cycle_durations = np.array([record["Cycle Duration [cd] (ms)"] for record in dyad_records], dtype=float)
    rk_values = np.array([record["Rhythm Ratio [r_k]"] for record in dyad_records], dtype=float)

    average_cycle_duration = float(np.mean(cycle_durations))
    rk_count = len(rk_values)
    npvi = (400 / rk_count) * np.sum(np.abs(rk_values - 0.5)) if rk_count > 0 else 0

    mean_interval = float(np.mean(intervals_seconds))
    interval_cv = float(np.std(intervals_seconds) / mean_interval) if mean_interval > 0 else 0
    rk_std_dev = float(np.std(rk_values)) if rk_count > 0 else 0

    counts, _ = np.histogram(rk_values, bins=10, range=(0, 1))
    rk_entropy = float(entropy(counts))

    return {
        "Average Cycle Duration (ms)": average_cycle_duration,
        "nPVI (Isochrony)": npvi,
        "CV of Intervals": interval_cv,
        "r_k Std Dev": rk_std_dev,
        "r_k Entropy (Categorical Measure)": rk_entropy,
    }


def calculate_stable_subset_metrics(stable_dyad_records):
    """Calculate summary statistics for the stable-rhythm dyads only."""
    if not stable_dyad_records:
        return {
            "Stable Rhythm nPVI": None,
            "Stable Rhythm CV": None,
            "Stable Rhythm r_k Std Dev": None,
            "Stable Rhythm Entropy": None,
        }

    rk_values = np.array([record["Rhythm Ratio [r_k]"] for record in stable_dyad_records], dtype=float)
    interval_values = np.array(
        [
            value
            for record in stable_dyad_records
            for value in (record["Interval 1 (ms)"], record["Interval 2 (ms)"])
        ],
        dtype=float,
    )

    mean_interval = float(np.mean(interval_values)) if len(interval_values) > 0 else 0
    stable_cv = float(np.std(interval_values) / mean_interval) if mean_interval > 0 else 0
    rk_count = len(rk_values)
    stable_npvi = (400 / rk_count) * np.sum(np.abs(rk_values - 0.5)) if rk_count > 0 else 0
    stable_std_dev = float(np.std(rk_values)) if rk_count > 0 else 0

    counts, _ = np.histogram(rk_values, bins=10, range=(0, 1))
    stable_entropy = float(entropy(counts))

    return {
        "Stable Rhythm nPVI": stable_npvi,
        "Stable Rhythm CV": stable_cv,
        "Stable Rhythm r_k Std Dev": stable_std_dev,
        "Stable Rhythm Entropy": stable_entropy,
    }


def calculate_speech_rhythm_metrics(intervals_ms, pause_threshold_ms=250.0):
    """Calculate speech-specific rhythm metrics from inter-onset intervals."""
    intervals = np.asarray(intervals_ms, dtype=float)
    if len(intervals) < 2:
        return {
            "Speech Rate (onsets/sec)": None,
            "Mean IOI (ms)": None,
            "Std IOI (ms)": None,
            "PVI-raw (ms)": None,
            "nPVI (%)": None,
            "VarcoIOI (%)": None,
            "Articulation Rate (onsets/sec)": None,
            "Pause Count": None,
            "Mean Pause Duration (ms)": None,
            "Phonation Time Ratio": None,
        }

    mean_ioi = float(np.mean(intervals))
    std_ioi = float(np.std(intervals))

    speech_rate = 1000.0 / mean_ioi if mean_ioi > 0 else 0.0

    diffs = np.abs(np.diff(intervals))
    pvi_raw = float(np.mean(diffs)) if len(diffs) > 0 else 0.0

    pairs_sum = np.array([intervals[i] + intervals[i + 1] for i in range(len(intervals) - 1)], dtype=float)
    norms = np.where(pairs_sum > 0, np.abs(np.diff(intervals)) / (pairs_sum / 2.0), 0.0)
    npvi = float(100.0 * np.mean(norms)) if len(norms) > 0 else 0.0

    varco = float(100.0 * std_ioi / mean_ioi) if mean_ioi > 0 else 0.0

    pause_mask = intervals > pause_threshold_ms
    speech_intervals = intervals[~pause_mask]
    pause_intervals = intervals[pause_mask]

    pause_count = int(np.sum(pause_mask))
    mean_pause = float(np.mean(pause_intervals)) if pause_count > 0 else 0.0

    if len(speech_intervals) > 0:
        art_rate = 1000.0 / float(np.mean(speech_intervals))
    else:
        art_rate = speech_rate

    total_duration = float(np.sum(intervals))
    speech_duration = float(np.sum(speech_intervals))
    phonation_ratio = speech_duration / total_duration if total_duration > 0 else 0.0

    return {
        "Speech Rate (onsets/sec)": round(speech_rate, 3),
        "Mean IOI (ms)": round(mean_ioi, 2),
        "Std IOI (ms)": round(std_ioi, 2),
        "PVI-raw (ms)": round(pvi_raw, 2),
        "nPVI (%)": round(npvi, 2),
        "VarcoIOI (%)": round(varco, 2),
        "Articulation Rate (onsets/sec)": round(art_rate, 3),
        "Pause Count": pause_count,
        "Mean Pause Duration (ms)": round(mean_pause, 2),
        "Phonation Time Ratio": round(phonation_ratio, 4),
    }


__all__ = [
    "build_dyad_records",
    "calculate_rhythm_metrics",
    "calculate_speech_rhythm_metrics",
    "calculate_stable_subset_metrics",
    "get_stable_dyad_flags",
    "is_stable_match",
]