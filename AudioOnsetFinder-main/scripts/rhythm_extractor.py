"""Extract rhythmic timing features from audio files and export analysis artifacts.

This is the core pipeline script. It scans the ``audioFiles/`` directory, detects
onsets in each recording, computes interval-based rhythm metrics, writes Audacity
label tracks and spectrogram review images, and exports both file-level summaries
and dyadic event tables to a multi-sheet Excel workbook.

Current role in the pipeline:
- Input: audio recordings in ``audioFiles/``
- Output: ``Cross_Species_Rhythm_Data.xlsx`` plus optional labels and spectrograms

Implemented next-step goals from ``docs/ReadMe.md`` and ``docs/nextSteps.md``:
- Cluster onsets that occur within 25 ms to reduce false dyads from overlapping signals.
- Export a stable-rhythm subset alongside the full dyadic dataset.
- Pre-filter audio with a high-pass filter and gate onsets by local amplitude to reduce
  false positives from background noise (configurable toggles in section 1).
- Preserve manual-review artifacts so noisy files can still be checked visually.
"""

import os  # directory listing and file path joining

import librosa  # core audio analysis (onsets, RMS, beat tracking)
import librosa.display  # spectrogram plotting utilities for QA images
import matplotlib.pyplot as plt  # generating plots for visual outputs
import numpy as np  # array math for intervals, normalization, stats
import pandas as pd  # dataframes for summaries and Excel export
from scipy.signal import butter, sosfilt  # filter implementation used for high-pass pre-filter
from scipy.stats import entropy  # rhythm entropy calculation for nPVI-like metrics

from onset_detectors import detect_onsets, refine_onsets_to_sample, available_methods

# ==========================================
# 1. MAIN CONFIGURATION & TOGGLES
# ==========================================
# --- Named Presets ---
# Choose a preset to load tuned defaults for a particular dataset type, or set
# ACTIVE_PRESET to None to use the manual values below. Each preset overrides
# only the onset-detection and noise-filter parameters; paths and output toggles
# are always controlled by the manual values below the preset dictionary.
PRESETS = {
    "birdsong": {
        "description": "Small passerines with rapid, high-frequency calls",
        "HIGHPASS_CUTOFF_HZ": 500,
        "ONSET_AMPLITUDE_GATE": 0.08,
        "ONSET_AMPLITUDE_WINDOW_MS": 30,
        "ONSET_SHARPNESS_GATE": 0.0,
        "ONSET_SHARPNESS_WINDOW_MS": 20,
        "MIN_INTER_ONSET_MS": 12,
        "ONSET_CLUSTER_WINDOW_MS": 15,
        "STABLE_RHYTHM_TOLERANCE": 0.25,
        "ONSET_DELTA": 0.05,
        "ONSET_HOP_LENGTH": 256,
        "ONSET_BACKTRACK": False,
        "ONSET_REFINE_ENABLED": True,
        "ONSET_REFINE_WINDOW_MS": 10,
        "ONSET_REFINE_ENERGY_GATE": 0.0,
        "ONSET_METHOD": "adaptive_hp",
    },
    "percussion_clean": {
        "description": "Clean percussion recordings — sensitive to quiet hits and rapid sequences",
        "HIGHPASS_CUTOFF_HZ": 80,
        "ONSET_AMPLITUDE_GATE": 0.005,
        "ONSET_AMPLITUDE_WINDOW_MS": 50,
        "ONSET_SHARPNESS_GATE": 0.0,
        "ONSET_SHARPNESS_WINDOW_MS": 20,
        "ONSET_BROADBAND_MIN_BANDS": 3,
        "ONSET_BROADBAND_N_BANDS": 6,
        "ONSET_BROADBAND_THRESHOLD": 0.15,
        "MIN_INTER_ONSET_MS": 15,
        "ONSET_CLUSTER_WINDOW_MS": 12,
        "STABLE_RHYTHM_TOLERANCE": 0.25,
        "ONSET_DELTA": 0.04,
        "ONSET_HOP_LENGTH": 128,
        "ONSET_BACKTRACK": False,
        "ONSET_REFINE_ENABLED": True,
        "ONSET_REFINE_WINDOW_MS": 8,
        "ONSET_REFINE_ENERGY_GATE": 0.005,
        "ONSET_METHOD": "adaptive_hp",
    },
    "percussion_messy": {
        "description": "Noisy percussion and drumming with sharp transient attacks",
        "HIGHPASS_CUTOFF_HZ": 80,
        "ONSET_AMPLITUDE_GATE": 0.03,
        "ONSET_AMPLITUDE_WINDOW_MS": 50,
        "ONSET_SHARPNESS_GATE": 0.10,
        "ONSET_SHARPNESS_WINDOW_MS": 20,
        "MIN_INTER_ONSET_MS": 30,
        "ONSET_CLUSTER_WINDOW_MS": 25,
        "STABLE_RHYTHM_TOLERANCE": 0.25,
        "ONSET_DELTA": 0.07,
        "ONSET_HOP_LENGTH": 256,
        "ONSET_BACKTRACK": False,
        "ONSET_REFINE_ENABLED": True,
        "ONSET_REFINE_WINDOW_MS": 10,
        "ONSET_REFINE_ENERGY_GATE": 0.0,
        "ONSET_METHOD": "adaptive_hp",
    },
    "primate": {
        "description": "Primate calls and drumming — mid-frequency with moderate attack",
        "HIGHPASS_CUTOFF_HZ": 150,
        "ONSET_AMPLITUDE_GATE": 0.06,
        "ONSET_AMPLITUDE_WINDOW_MS": 60,
        "ONSET_SHARPNESS_GATE": 0.15,
        "ONSET_SHARPNESS_WINDOW_MS": 25,
        "MIN_INTER_ONSET_MS": 40,
        "ONSET_CLUSTER_WINDOW_MS": 30,
        "STABLE_RHYTHM_TOLERANCE": 0.30,
        "ONSET_DELTA": 0.06,
        "ONSET_HOP_LENGTH": 256,
        "ONSET_BACKTRACK": False,
        "ONSET_REFINE_ENABLED": True,
        "ONSET_REFINE_WINDOW_MS": 10,
        "ONSET_REFINE_ENERGY_GATE": 0.0,
        "ONSET_METHOD": "adaptive_hp",
    },
    "insect": {
        "description": "High-frequency percussive clicks (e.g. crickets, cicadas)",
        "HIGHPASS_CUTOFF_HZ": 1000,
        "ONSET_AMPLITUDE_GATE": 0.10,
        "ONSET_AMPLITUDE_WINDOW_MS": 20,
        "ONSET_SHARPNESS_GATE": 0.0,
        "ONSET_SHARPNESS_WINDOW_MS": 15,
        "MIN_INTER_ONSET_MS": 10,
        "ONSET_CLUSTER_WINDOW_MS": 10,
        "STABLE_RHYTHM_TOLERANCE": 0.20,
        "ONSET_DELTA": 0.04,
        "ONSET_HOP_LENGTH": 128,
        "ONSET_BACKTRACK": False,
        "ONSET_REFINE_ENABLED": True,
        "ONSET_REFINE_WINDOW_MS": 10,
        "ONSET_REFINE_ENERGY_GATE": 0.0,
        "ONSET_METHOD": "adaptive_hp",
    },
}

# Set this to a preset name (e.g. "birdsong") or None to use manual values.
ACTIVE_PRESET = None

# These toggles control which review artifacts and filtered exports are created.
CREATE_SPECTROGRAMS = True
SPECTROGRAM_CHUNK_ENABLED = False
SPECTROGRAM_CHUNK_SECONDS = 30
CREATE_AUDACITY_LABELS = True
CLUSTER_OVERLAPPING_ONSETS = True
ONSET_CLUSTER_WINDOW_MS = 25
FILTER_STABLE_RHYTHMS = True
STABLE_RHYTHM_TOLERANCE = 0.25

# --- Noise-Handling Pre-Filters (nextSteps.md item 2) ---
# NOTE: High-pass filtering and dB-based noise muting are now handled by
# audio_muter.py as a pre-processing step. These toggles are kept here as a
# fallback but are DISABLED by default to avoid double-filtering, which can
# over-aggressively remove quiet but legitimate animal calls.
#
# Only re-enable these if you are running the extractor on raw (un-muted) audio.
APPLY_HIGHPASS_FILTER = False
HIGHPASS_CUTOFF_HZ = 200

# Onset amplitude gate: discard onsets whose local RMS energy is below a fraction
# of the file's peak RMS. Set to a positive value to filter out weak onsets that
# may be residual noise (e.g. cicada remnants after spectral denoising).
# Recommended: 0.05-0.10 for field recordings, 0.0 to disable.
ONSET_AMPLITUDE_GATE = 0.05
ONSET_AMPLITUDE_WINDOW_MS = 50

# Minimum inter-onset interval: any onset that follows the previous one by fewer
# than this many milliseconds is dropped (applied after clustering). Guards against
# impossibly fast detections caused by transient noise.
MIN_INTER_ONSET_MS = 30

# Onset detection sensitivity (passed to librosa as the `delta` parameter).
# Higher values = fewer, more prominent onsets detected. Lower = more sensitive.
# Recommended: 0.07 (general), 0.10-0.15 (noisy field recordings with cicadas).
ONSET_DELTA = 0.10

# Hop length for onset detection (samples). Controls temporal resolution:
#   512 → ~11.6 ms (librosa default — coarse, onsets can be off by up to ~6 ms)
#   256 → ~5.8 ms  (recommended — good balance of precision and speed)
#   128 → ~2.9 ms  (very fine — slower, may add noise-triggered false onsets)
# Reducing hop_length lets onsets snap to a finer time grid.
ONSET_HOP_LENGTH = 256

# Backtracking: when True, librosa rolls each detected onset *backward* to the
# nearest preceding local energy minimum. Intended to find the true attack start,
# but on noisy field recordings it often overshoots, placing onsets too early.
# Set False to keep onsets at the energy *peak* instead.
ONSET_BACKTRACK = False

# --- Sample-Level Onset Refinement ---
# When enabled, each coarse frame-level onset is refined to the nearest sample
# that shows the steepest energy rise (via the Hilbert amplitude envelope
# derivative) within a ±ONSET_REFINE_WINDOW_MS search window. This achieves
# sub-millisecond precision (~0.023 ms at 44.1 kHz) while keeping the coarse
# detector's robustness against cicada and other broadband noise.
#
# ONSET_REFINE_ENABLED  — True to activate sample-level refinement.
# ONSET_REFINE_WINDOW_MS — half-width of the search window around each coarse
#                          onset (±ms). 10 ms is a safe default; increase if the
#                          coarse detector systematically lands far from the true
#                          attack. Larger windows cost more CPU but stay fast.
# ONSET_REFINE_ENERGY_GATE — optional local energy ratio threshold (0.0–1.0).
#                            If the peak envelope in the refinement window is
#                            below this fraction of the file's peak envelope,
#                            the coarse time is kept unchanged (avoids snapping
#                            to noise). Set 0.0 to disable.
ONSET_REFINE_ENABLED = True
ONSET_REFINE_WINDOW_MS = 10
ONSET_REFINE_ENERGY_GATE = 0.0

# --- Onset Detection Method ---
# Controls which algorithm finds onset candidates before refinement/clustering.
# See onset_detectors.py for full documentation of each method.
#
# "adaptive_hp" (default) — HP adaptive baseline (Roeske et al. 2020).
# "librosa"      — Standard spectral-flux onset detection.
# "moving_median" — Moving-median adaptive baseline (simpler/faster than HP).
# "superflux"    — Spectral flux with vibrato suppression (Böck & Widmer 2013).
# "cfar"         — Constant False Alarm Rate detector.
# "per_band"     — Per-frequency-band adaptive threshold.
ONSET_METHOD = "adaptive_hp"

# HP filter parameters (used when ONSET_METHOD == "adaptive_hp"):
HP_SMOOTH_LAMBDA = 50
HP_THRESHOLD_LAMBDA = 5e7
HP_ENVELOPE_WINDOW_MS = 10
HP_ENVELOPE_HOP_MS = 1

# Moving-median parameters (used when ONSET_METHOD == "moving_median"):
MEDIAN_WINDOW_MS = 200
MEDIAN_THRESHOLD_SCALE = 1.5

# Superflux parameters (used when ONSET_METHOD == "superflux"):
SUPERFLUX_LAG = 2
SUPERFLUX_MAX_SIZE = 3

# CFAR parameters (used when ONSET_METHOD == "cfar"):
CFAR_GUARD_MS = 20
CFAR_TRAINING_MS = 200
CFAR_THRESHOLD_FACTOR = 4.0

# Per-band parameters (used when ONSET_METHOD == "per_band"):
PER_BAND_N_BANDS = 6
PER_BAND_FREQ_MIN = 200
PER_BAND_FREQ_MAX = None   # None = sr/2
PER_BAND_MEDIAN_MS = 200
PER_BAND_THRESHOLD_SCALE = 1.5
PER_BAND_MIN_BANDS = 2

# --- Apply preset overrides ---
if ACTIVE_PRESET is not None:
    if ACTIVE_PRESET not in PRESETS:
        raise ValueError(f"Unknown preset '{ACTIVE_PRESET}'. Choose from: {list(PRESETS.keys())}")
    _preset = PRESETS[ACTIVE_PRESET]
    print(f"Using preset '{ACTIVE_PRESET}': {_preset['description']}")
    HIGHPASS_CUTOFF_HZ = _preset["HIGHPASS_CUTOFF_HZ"]
    ONSET_AMPLITUDE_GATE = _preset["ONSET_AMPLITUDE_GATE"]
    ONSET_AMPLITUDE_WINDOW_MS = _preset["ONSET_AMPLITUDE_WINDOW_MS"]
    ONSET_SHARPNESS_GATE = _preset["ONSET_SHARPNESS_GATE"]
    ONSET_SHARPNESS_WINDOW_MS = _preset["ONSET_SHARPNESS_WINDOW_MS"]
    MIN_INTER_ONSET_MS = _preset["MIN_INTER_ONSET_MS"]
    ONSET_CLUSTER_WINDOW_MS = _preset["ONSET_CLUSTER_WINDOW_MS"]
    STABLE_RHYTHM_TOLERANCE = _preset["STABLE_RHYTHM_TOLERANCE"]
    ONSET_DELTA = _preset["ONSET_DELTA"]
    ONSET_HOP_LENGTH = _preset["ONSET_HOP_LENGTH"]
    ONSET_BACKTRACK = _preset["ONSET_BACKTRACK"]
    ONSET_REFINE_ENABLED = _preset["ONSET_REFINE_ENABLED"]
    ONSET_REFINE_WINDOW_MS = _preset["ONSET_REFINE_WINDOW_MS"]
    ONSET_REFINE_ENERGY_GATE = _preset["ONSET_REFINE_ENERGY_GATE"]
    ONSET_METHOD = _preset["ONSET_METHOD"]

# --- Default paths (relative to the project root, portable across machines) ---
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
audio_folder = os.path.join(_PROJECT_DIR, "audioFiles_muted_clean")
output_excel_path = os.path.join(_PROJECT_DIR, "Cross_Species_Rhythm_Data.xlsx")

# ------------------------------------------------------------------
# GUI CONFIG OVERRIDE — Read settings from pipeline_config.json if present.
# ------------------------------------------------------------------
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_config_path = os.path.join(_PROJECT_DIR, "pipeline_config.json")
if os.path.isfile(_config_path):
    import json as _json
    with open(_config_path) as _f:
        _cfg = _json.load(_f).get("extractor", {})
    audio_folder = _cfg.get("audio_folder", audio_folder)
    ACTIVE_PRESET = _cfg.get("ACTIVE_PRESET", ACTIVE_PRESET)
    CREATE_SPECTROGRAMS = _cfg.get("CREATE_SPECTROGRAMS", CREATE_SPECTROGRAMS)
    SPECTROGRAM_CHUNK_ENABLED = _cfg.get("SPECTROGRAM_CHUNK_ENABLED", SPECTROGRAM_CHUNK_ENABLED)
    SPECTROGRAM_CHUNK_SECONDS = _cfg.get("SPECTROGRAM_CHUNK_SECONDS", SPECTROGRAM_CHUNK_SECONDS)
    CREATE_AUDACITY_LABELS = _cfg.get("CREATE_AUDACITY_LABELS", CREATE_AUDACITY_LABELS)
    CLUSTER_OVERLAPPING_ONSETS = _cfg.get("CLUSTER_OVERLAPPING_ONSETS", CLUSTER_OVERLAPPING_ONSETS)
    ONSET_CLUSTER_WINDOW_MS = _cfg.get("ONSET_CLUSTER_WINDOW_MS", ONSET_CLUSTER_WINDOW_MS)
    FILTER_STABLE_RHYTHMS = _cfg.get("FILTER_STABLE_RHYTHMS", FILTER_STABLE_RHYTHMS)
    STABLE_RHYTHM_TOLERANCE = _cfg.get("STABLE_RHYTHM_TOLERANCE", STABLE_RHYTHM_TOLERANCE)
    APPLY_HIGHPASS_FILTER = _cfg.get("APPLY_HIGHPASS_FILTER", APPLY_HIGHPASS_FILTER)
    HIGHPASS_CUTOFF_HZ = _cfg.get("HIGHPASS_CUTOFF_HZ", HIGHPASS_CUTOFF_HZ)
    ONSET_AMPLITUDE_GATE = _cfg.get("ONSET_AMPLITUDE_GATE", ONSET_AMPLITUDE_GATE)
    ONSET_AMPLITUDE_WINDOW_MS = _cfg.get("ONSET_AMPLITUDE_WINDOW_MS", ONSET_AMPLITUDE_WINDOW_MS)
    ONSET_SHARPNESS_GATE = _cfg.get("ONSET_SHARPNESS_GATE", ONSET_SHARPNESS_GATE)
    ONSET_SHARPNESS_WINDOW_MS = _cfg.get("ONSET_SHARPNESS_WINDOW_MS", ONSET_SHARPNESS_WINDOW_MS)
    MIN_INTER_ONSET_MS = _cfg.get("MIN_INTER_ONSET_MS", MIN_INTER_ONSET_MS)
    ONSET_METHOD = _cfg.get("ONSET_METHOD", ONSET_METHOD)
    ONSET_DELTA = _cfg.get("ONSET_DELTA", ONSET_DELTA)
    ONSET_HOP_LENGTH = _cfg.get("ONSET_HOP_LENGTH", ONSET_HOP_LENGTH)
    ONSET_BACKTRACK = _cfg.get("ONSET_BACKTRACK", ONSET_BACKTRACK)
    ONSET_REFINE_ENABLED = _cfg.get("ONSET_REFINE_ENABLED", ONSET_REFINE_ENABLED)
    ONSET_REFINE_WINDOW_MS = _cfg.get("ONSET_REFINE_WINDOW_MS", ONSET_REFINE_WINDOW_MS)
    ONSET_REFINE_ENERGY_GATE = _cfg.get("ONSET_REFINE_ENERGY_GATE", ONSET_REFINE_ENERGY_GATE)
    HP_SMOOTH_LAMBDA = _cfg.get("HP_SMOOTH_LAMBDA", HP_SMOOTH_LAMBDA)
    HP_THRESHOLD_LAMBDA = _cfg.get("HP_THRESHOLD_LAMBDA", HP_THRESHOLD_LAMBDA)
    HP_ENVELOPE_WINDOW_MS = _cfg.get("HP_ENVELOPE_WINDOW_MS", HP_ENVELOPE_WINDOW_MS)
    HP_ENVELOPE_HOP_MS = _cfg.get("HP_ENVELOPE_HOP_MS", HP_ENVELOPE_HOP_MS)
    MEDIAN_WINDOW_MS = _cfg.get("MEDIAN_WINDOW_MS", MEDIAN_WINDOW_MS)
    MEDIAN_THRESHOLD_SCALE = _cfg.get("MEDIAN_THRESHOLD_SCALE", MEDIAN_THRESHOLD_SCALE)
    SUPERFLUX_LAG = _cfg.get("SUPERFLUX_LAG", SUPERFLUX_LAG)
    SUPERFLUX_MAX_SIZE = _cfg.get("SUPERFLUX_MAX_SIZE", SUPERFLUX_MAX_SIZE)
    CFAR_GUARD_MS = _cfg.get("CFAR_GUARD_MS", CFAR_GUARD_MS)
    CFAR_TRAINING_MS = _cfg.get("CFAR_TRAINING_MS", CFAR_TRAINING_MS)
    CFAR_THRESHOLD_FACTOR = _cfg.get("CFAR_THRESHOLD_FACTOR", CFAR_THRESHOLD_FACTOR)
    PER_BAND_N_BANDS = _cfg.get("PER_BAND_N_BANDS", PER_BAND_N_BANDS)
    PER_BAND_FREQ_MIN = _cfg.get("PER_BAND_FREQ_MIN", PER_BAND_FREQ_MIN)
    PER_BAND_FREQ_MAX = _cfg.get("PER_BAND_FREQ_MAX", PER_BAND_FREQ_MAX)
    PER_BAND_MEDIAN_MS = _cfg.get("PER_BAND_MEDIAN_MS", PER_BAND_MEDIAN_MS)
    PER_BAND_THRESHOLD_SCALE = _cfg.get("PER_BAND_THRESHOLD_SCALE", PER_BAND_THRESHOLD_SCALE)
    PER_BAND_MIN_BANDS = _cfg.get("PER_BAND_MIN_BANDS", PER_BAND_MIN_BANDS)
    # Re-apply preset if config specifies one (GUI handles preset field population,
    # so individual values from config take precedence above).
    del _json, _f, _cfg
del _PROJECT_DIR, _config_path

# These lists accumulate rows before they are written to separate Excel sheets.
file_summary_data = []
dyadic_events_data = []
stable_dyadic_events_data = []


def cluster_onsets(onset_times, cluster_window_ms):
    """Merge near-simultaneous onsets into a single onset at the cluster start."""
    if len(onset_times) <= 1:
        return np.array(onset_times, dtype=float)

    cluster_window_seconds = cluster_window_ms / 1000.0
    clustered_onsets = [float(onset_times[0])]

    for onset_time in onset_times[1:]:
        if float(onset_time) - clustered_onsets[-1] < cluster_window_seconds:
            continue
        clustered_onsets.append(float(onset_time))

    return np.array(clustered_onsets, dtype=float)


def apply_highpass(signal, sr, cutoff_hz):
    """Apply a 4th-order Butterworth high-pass filter to the audio signal."""
    sos = butter(4, cutoff_hz, btype="high", fs=sr, output="sos")
    return sosfilt(sos, signal).astype(signal.dtype)


def gate_onsets_by_amplitude(onset_times, signal, sr, gate_fraction, window_ms):
    """Remove onsets whose local RMS energy falls below *gate_fraction* of the peak RMS."""
    if gate_fraction <= 0 or len(onset_times) == 0:
        return onset_times

    window_samples = int(sr * window_ms / 1000.0)
    rms_values = librosa.feature.rms(y=signal, frame_length=window_samples, hop_length=window_samples // 2)[0]
    rms_times = librosa.frames_to_time(
        np.arange(len(rms_values)), sr=sr, hop_length=window_samples // 2
    )
    peak_rms = float(np.max(rms_values))
    threshold = gate_fraction * peak_rms

    kept = []
    for onset_time in onset_times:
        closest_idx = int(np.argmin(np.abs(rms_times - onset_time)))
        if rms_values[closest_idx] >= threshold:
            kept.append(onset_time)

    return np.array(kept, dtype=float)


def gate_onsets_by_sharpness(onset_times, signal, sr, gate_fraction, window_ms):
    """Remove onsets whose attack slope is below *gate_fraction* of the steepest attack.

    Attack slope is measured as the maximum positive derivative of the Hilbert
    amplitude envelope within a ±window_ms region around each onset.  Onsets
    with a slope below ``gate_fraction * peak_slope`` are discarded.
    """
    if gate_fraction <= 0 or len(onset_times) == 0:
        return onset_times

    from scipy.signal import hilbert as scipy_hilbert

    analytic = scipy_hilbert(signal)
    envelope = np.abs(analytic).astype(np.float64)
    envelope_diff = np.diff(envelope)

    window_samples = int(sr * window_ms / 1000.0)
    half_window = window_samples // 2

    slopes = []
    for onset_time in onset_times:
        center = int(onset_time * sr)
        start = max(center - half_window, 0)
        end = min(center + half_window, len(envelope_diff))
        if start < end:
            slopes.append(float(np.max(envelope_diff[start:end])))
        else:
            slopes.append(0.0)

    peak_slope = max(slopes) if slopes else 1.0
    if peak_slope <= 0:
        return onset_times

    threshold = gate_fraction * peak_slope
    kept = [t for t, s in zip(onset_times, slopes) if s >= threshold]
    return np.array(kept, dtype=float)


def enforce_min_interval(onset_times, min_interval_ms):
    """Drop onsets that follow the previous one by fewer than *min_interval_ms*."""
    if min_interval_ms <= 0 or len(onset_times) <= 1:
        return onset_times

    min_interval_s = min_interval_ms / 1000.0
    kept = [onset_times[0]]
    for t in onset_times[1:]:
        if t - kept[-1] >= min_interval_s:
            kept.append(t)
    return np.array(kept, dtype=float)


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


# ==========================================
# 2. AUDIO PROCESSING LOOP
# ==========================================
print("Starting extraction process... This might take a moment depending on file sizes.")

for filename in sorted(os.listdir(audio_folder)):
    if filename.endswith(".wav") or filename.endswith(".mp3") or filename.endswith(".mp4"):
        file_path = os.path.join(audio_folder, filename)
        print(f"Processing: {filename}...")

        # Load the original sample rate so timing values stay faithful to the recording.
        y, sr = librosa.load(file_path, sr=None)

        # Apply high-pass filter to remove low-frequency rumble before onset detection.
        if APPLY_HIGHPASS_FILTER and HIGHPASS_CUTOFF_HZ > 0:
            y = apply_highpass(y, sr, HIGHPASS_CUTOFF_HZ)

        total_duration = librosa.get_duration(y=y, sr=sr)

        # These coarse acoustic summaries provide quick descriptive context per file.
        tempo_bpm, _ = librosa.beat.beat_track(y=y, sr=sr)
        estimated_bpm = float(tempo_bpm[0]) if isinstance(tempo_bpm, np.ndarray) else float(tempo_bpm)

        rms = librosa.feature.rms(y=y)
        avg_loudness = np.mean(rms)

        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        avg_brightness = np.mean(centroid)

        # Onset detection is the core dependency for all downstream rhythm metrics.
        # Build keyword arguments for the selected method.
        if ONSET_METHOD == "adaptive_hp":
            _onset_kwargs = dict(
                hp_smooth_lambda=HP_SMOOTH_LAMBDA,
                hp_threshold_lambda=HP_THRESHOLD_LAMBDA,
                envelope_window_ms=HP_ENVELOPE_WINDOW_MS,
                envelope_hop_ms=HP_ENVELOPE_HOP_MS,
            )
        elif ONSET_METHOD == "librosa":
            _onset_kwargs = dict(
                hop_length=ONSET_HOP_LENGTH,
                delta=ONSET_DELTA,
                backtrack=ONSET_BACKTRACK,
            )
        elif ONSET_METHOD == "moving_median":
            _onset_kwargs = dict(
                envelope_window_ms=HP_ENVELOPE_WINDOW_MS,
                envelope_hop_ms=HP_ENVELOPE_HOP_MS,
                median_window_ms=MEDIAN_WINDOW_MS,
                threshold_scale=MEDIAN_THRESHOLD_SCALE,
            )
        elif ONSET_METHOD == "superflux":
            _onset_kwargs = dict(
                hop_length=ONSET_HOP_LENGTH,
                lag=SUPERFLUX_LAG,
                max_size=SUPERFLUX_MAX_SIZE,
                delta=ONSET_DELTA,
            )
        elif ONSET_METHOD == "cfar":
            _onset_kwargs = dict(
                envelope_window_ms=HP_ENVELOPE_WINDOW_MS,
                envelope_hop_ms=HP_ENVELOPE_HOP_MS,
                guard_ms=CFAR_GUARD_MS,
                training_ms=CFAR_TRAINING_MS,
                threshold_factor=CFAR_THRESHOLD_FACTOR,
            )
        elif ONSET_METHOD == "per_band":
            _onset_kwargs = dict(
                hop_length=ONSET_HOP_LENGTH,
                n_bands=PER_BAND_N_BANDS,
                freq_min=PER_BAND_FREQ_MIN,
                freq_max=PER_BAND_FREQ_MAX,
                median_window_ms=PER_BAND_MEDIAN_MS,
                threshold_scale=PER_BAND_THRESHOLD_SCALE,
                min_bands=PER_BAND_MIN_BANDS,
            )
        else:
            _onset_kwargs = {}

        onset_times = detect_onsets(ONSET_METHOD, y, sr, **_onset_kwargs)

        # Sample-level refinement: snap each coarse onset to the steepest
        # energy rise in a ±ONSET_REFINE_WINDOW_MS neighbourhood, giving
        # ~0.023 ms precision at 44.1 kHz instead of the ~5.8 ms frame grid.
        if ONSET_REFINE_ENABLED and len(onset_times) > 0:
            onset_times = refine_onsets_to_sample(
                onset_times, y, sr,
                window_ms=ONSET_REFINE_WINDOW_MS,
                energy_gate=ONSET_REFINE_ENERGY_GATE,
            )

        # Merge near-simultaneous onsets before the interval and dyad calculations.
        clustered_onset_times = (
            cluster_onsets(onset_times, ONSET_CLUSTER_WINDOW_MS)
            if CLUSTER_OVERLAPPING_ONSETS
            else np.array(onset_times, dtype=float)
        )

        # Amplitude gate: reject onsets in quiet regions that are likely noise artifacts.
        if ONSET_AMPLITUDE_GATE > 0:
            clustered_onset_times = gate_onsets_by_amplitude(
                clustered_onset_times, y, sr, ONSET_AMPLITUDE_GATE, ONSET_AMPLITUDE_WINDOW_MS
            )

        # Sharpness gate
        if ONSET_SHARPNESS_GATE > 0:
            clustered_onset_times = gate_onsets_by_sharpness(
                clustered_onset_times, y, sr, ONSET_SHARPNESS_GATE, ONSET_SHARPNESS_WINDOW_MS
            )

        # Minimum inter-onset spacing: drop impossibly fast repeated detections.
        if MIN_INTER_ONSET_MS > 0:
            clustered_onset_times = enforce_min_interval(clustered_onset_times, MIN_INTER_ONSET_MS)

        intervals_seconds = np.diff(clustered_onset_times)
        intervals_ms = intervals_seconds * 1000
        stable_dyad_flags = get_stable_dyad_flags(intervals_ms, STABLE_RHYTHM_TOLERANCE)

        file_dyad_records = build_dyad_records(filename, intervals_ms, stable_dyad_flags)
        file_stable_dyad_records = [record for record in file_dyad_records if record["Stable Rhythm"]]

        dyadic_events_data.extend(file_dyad_records)
        if FILTER_STABLE_RHYTHMS:
            stable_dyadic_events_data.extend(file_stable_dyad_records)

        metrics = calculate_rhythm_metrics(intervals_seconds, file_dyad_records)
        stable_metrics = calculate_stable_subset_metrics(file_stable_dyad_records)

        # --- AUDACITY LABEL EXPORT ---
        # These labels support the manual verification step recommended for noisy recordings.
        if CREATE_AUDACITY_LABELS and len(clustered_onset_times) > 0:
            label_filename = f"{os.path.splitext(filename)[0]}_labels.txt"
            label_path = os.path.join(audio_folder, label_filename)
            precision = 6 if ONSET_REFINE_ENABLED else 4
            with open(label_path, "w") as file_handle:
                for idx, onset_time in enumerate(clustered_onset_times):
                    tag = "Onset" if not ONSET_REFINE_ENABLED else "OnsetR"
                    file_handle.write(f"{onset_time:.{precision}f}\t{onset_time:.{precision}f}\t{tag}_{idx + 1}\n")

        # --- SPECTROGRAM VISUALIZER ---
        # The spectrogram overlay is intended for visual QA, not for downstream computation.
        if CREATE_SPECTROGRAMS and len(clustered_onset_times) > 0:
            base_stem = os.path.splitext(filename)[0]
            onset_arr = np.array(clustered_onset_times)

            if SPECTROGRAM_CHUNK_ENABLED and SPECTROGRAM_CHUNK_SECONDS > 0:
                chunk_dur = float(SPECTROGRAM_CHUNK_SECONDS)
                n_chunks = max(1, int(np.ceil(total_duration / chunk_dur)))
            else:
                chunk_dur = total_duration
                n_chunks = 1

            for chunk_idx in range(n_chunks):
                t_start = chunk_idx * chunk_dur
                t_end = min(t_start + chunk_dur, total_duration)
                s_start = int(t_start * sr)
                s_end = int(t_end * sr)
                y_chunk = y[s_start:s_end]

                chunk_onsets = onset_arr[(onset_arr >= t_start) & (onset_arr < t_end)]

                spectrogram = librosa.amplitude_to_db(np.abs(librosa.stft(y_chunk)), ref=np.max)
                plt.figure(figsize=(10, 4))
                librosa.display.specshow(spectrogram, x_axis="time", y_axis="log",
                                         sr=sr, x_coords=np.linspace(t_start, t_end,
                                         spectrogram.shape[1]))
                plt.colorbar(format="%+2.0f dB")
                if n_chunks == 1:
                    plt.title(f"Detected Onsets: {filename}")
                    image_filename = f"{base_stem}_plot.png"
                else:
                    plt.title(f"Detected Onsets: {filename}  [{t_start:.1f}\u2013{t_end:.1f} s]")
                    image_filename = f"{base_stem}_{chunk_idx + 1}.png"
                plt.vlines(
                    chunk_onsets,
                    ymin=0,
                    ymax=sr / 2,
                    color="r",
                    alpha=0.8,
                    linestyle="--",
                    label="Onsets",
                )
                image_path = os.path.join(audio_folder, image_filename)
                plt.savefig(image_path)
                plt.close()

        # --- SAVE FILE SUMMARY DATA ---
        # The summary sheet is the bridge between raw extraction and quick exploratory review.
        file_summary_data.append(
            {
                "File Name": filename,
                "Total Duration (s)": round(total_duration, 3),
                "Estimated Overall BPM": round(estimated_bpm, 1),
                "Average Cycle Duration (ms)": round(metrics["Average Cycle Duration (ms)"], 2)
                if metrics["Average Cycle Duration (ms)"] is not None
                else "N/A",
                "Avg Loudness (Energy)": round(avg_loudness, 4),
                "Avg Brightness (Centroid Hz)": round(avg_brightness, 2),
                "Total Onsets Found (Raw)": len(onset_times),
                "Total Onsets Used": len(clustered_onset_times),
                "Onsets Merged by Clustering": max(len(onset_times) - len(clustered_onset_times), 0),
                "High-Pass Filter Hz": HIGHPASS_CUTOFF_HZ if APPLY_HIGHPASS_FILTER else "Off",
                "Amplitude Gate Threshold": ONSET_AMPLITUDE_GATE if ONSET_AMPLITUDE_GATE > 0 else "Off",
                "Sharpness Gate Threshold": ONSET_SHARPNESS_GATE if ONSET_SHARPNESS_GATE > 0 else "Off",
                "Min Inter-Onset (ms)": MIN_INTER_ONSET_MS if MIN_INTER_ONSET_MS > 0 else "Off",
                "Onset Delta": ONSET_DELTA if ONSET_METHOD in ("librosa", "superflux") else "N/A",
                "Onset Method": ONSET_METHOD,
                "Active Preset": ACTIVE_PRESET if ACTIVE_PRESET else "None",
                "Onset Refinement": f"±{ONSET_REFINE_WINDOW_MS}ms (sample-level)" if ONSET_REFINE_ENABLED else "Off",
                "Stable Dyads Retained": len(file_stable_dyad_records),
                "Stable Rhythm Filter Enabled": FILTER_STABLE_RHYTHMS,
                "nPVI (Isochrony)": round(metrics["nPVI (Isochrony)"], 2)
                if metrics["nPVI (Isochrony)"] is not None
                else "N/A",
                "CV of Intervals": round(metrics["CV of Intervals"], 4)
                if metrics["CV of Intervals"] is not None
                else "N/A",
                "r_k Std Dev": round(metrics["r_k Std Dev"], 4)
                if metrics["r_k Std Dev"] is not None
                else "N/A",
                "r_k Entropy (Categorical Measure)": round(metrics["r_k Entropy (Categorical Measure)"], 4)
                if metrics["r_k Entropy (Categorical Measure)"] is not None
                else "N/A",
                "Stable Rhythm nPVI": round(stable_metrics["Stable Rhythm nPVI"], 2)
                if stable_metrics["Stable Rhythm nPVI"] is not None
                else "N/A",
                "Stable Rhythm CV": round(stable_metrics["Stable Rhythm CV"], 4)
                if stable_metrics["Stable Rhythm CV"] is not None
                else "N/A",
                "Stable Rhythm r_k Std Dev": round(stable_metrics["Stable Rhythm r_k Std Dev"], 4)
                if stable_metrics["Stable Rhythm r_k Std Dev"] is not None
                else "N/A",
                "Stable Rhythm Entropy": round(stable_metrics["Stable Rhythm Entropy"], 4)
                if stable_metrics["Stable Rhythm Entropy"] is not None
                else "N/A",
                "Exact Onset Times Used (s)": ", ".join(
                    [str(round(onset_time, 6 if ONSET_REFINE_ENABLED else 3)) for onset_time in clustered_onset_times]
                ),
            }
        )

# ==========================================
# 3. EXPORT EXCEL FILE WITH MULTIPLE TABS
# ==========================================
# Keeping summaries and dyads on separate sheets makes the plotting scripts simpler.
df_summary = pd.DataFrame(file_summary_data)
df_dyads = pd.DataFrame(dyadic_events_data)
df_stable_dyads = pd.DataFrame(stable_dyadic_events_data)

with pd.ExcelWriter(output_excel_path) as writer:
    df_summary.to_excel(writer, sheet_name="File Summaries", index=False)
    df_dyads.to_excel(writer, sheet_name="Dyadic Events (For Plots)", index=False)
    if FILTER_STABLE_RHYTHMS:
        df_stable_dyads.to_excel(writer, sheet_name="Dyadic Events (Stable Rhythms)", index=False)

print(f"\nSUCCESS! Processed {len(file_summary_data)} files.")
print(f"Extracted {len(dyadic_events_data)} total dyadic rhythms.")
if FILTER_STABLE_RHYTHMS:
    print(f"Retained {len(stable_dyadic_events_data)} dyadic rhythms in the stable-rhythm sheet.")
print(f"Spreadsheet saved to: {output_excel_path}")