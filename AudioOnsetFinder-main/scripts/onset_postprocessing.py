"""Shared onset post-processing helpers for the rhythm pipeline.

This module contains pure onset filtering and spectral-matching helpers that
were previously bundled inside ``onset_finder.py``. Keeping them here makes the
post-detection pipeline reusable from the GUI workbench and analysis scripts
without importing the full batch-processing entrypoint.
"""

import os
import sys

import librosa
import numpy as np
from scipy.signal import butter, sosfilt

try:
    from analysis.spectral_profiles import (
        build_spectral_profile as _build_spectral_profile_impl,
        gate_onsets_by_spectral_match as _gate_onsets_by_spectral_match_impl,
    )
except ImportError:
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    from analysis.spectral_profiles import (
        build_spectral_profile as _build_spectral_profile_impl,
        gate_onsets_by_spectral_match as _gate_onsets_by_spectral_match_impl,
    )


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


def apply_focus_regions(onset_times, focus_regions, *,
                        y=None, sr=None,
                        use_frequency_bounds=False,
                        freq_energy_threshold=0.3,
                        freq_window_sec=0.05,
                        n_fft=2048):
    """Filter *onset_times* using focus regions."""
    if not focus_regions or len(onset_times) == 0:
        return np.array(onset_times, dtype=float)

    times = np.array(onset_times, dtype=float)
    pos_regions = [r for r in focus_regions if r.get("polarity") == "positive"]
    neg_regions = [r for r in focus_regions if r.get("polarity") == "negative"]

    if pos_regions:
        mask = np.zeros(len(times), dtype=bool)
        for r in pos_regions:
            mask |= (times >= r["t_start"]) & (times <= r["t_end"])
        times = times[mask]

    if neg_regions and len(times) > 0:
        mask = np.ones(len(times), dtype=bool)
        for r in neg_regions:
            mask &= ~((times >= r["t_start"]) & (times <= r["t_end"]))
        times = times[mask]

    if use_frequency_bounds and y is not None and sr is not None and len(times) > 0:
        freq_regions = [
            r for r in focus_regions
            if r.get("f_low") is not None and r.get("f_high") is not None
            and r["f_high"] > r.get("f_low", 0)
        ]
        if freq_regions:
            half_win = int(freq_window_sec * sr / 2)
            freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)
            keep = np.ones(len(times), dtype=bool)

            for i, t in enumerate(times):
                centre = int(t * sr)
                start = max(0, centre - half_win)
                end = min(len(y), centre + half_win)
                seg = y[start:end]
                if len(seg) < n_fft:
                    continue

                spectrum = np.abs(np.fft.rfft(seg, n=n_fft)) ** 2
                total_energy = spectrum.sum()
                if total_energy == 0:
                    keep[i] = False
                    continue

                onset_matched = False
                for r in freq_regions:
                    if r.get("polarity") != "positive":
                        continue
                    if t < r["t_start"] or t > r["t_end"]:
                        continue
                    f_low = r.get("f_low", 0)
                    f_high = r.get("f_high", sr / 2)
                    band_mask = (freqs >= f_low) & (freqs <= f_high)
                    band_energy = spectrum[band_mask].sum()
                    if band_energy / total_energy >= freq_energy_threshold:
                        onset_matched = True
                        break

                for r in freq_regions:
                    if r.get("polarity") != "negative":
                        continue
                    if t < r["t_start"] or t > r["t_end"]:
                        continue
                    f_low = r.get("f_low", 0)
                    f_high = r.get("f_high", sr / 2)
                    band_mask = (freqs >= f_low) & (freqs <= f_high)
                    band_energy = spectrum[band_mask].sum()
                    if band_energy / total_energy >= freq_energy_threshold:
                        keep[i] = False
                        onset_matched = True
                        break

                pos_freq = [r for r in freq_regions if r.get("polarity") == "positive"]
                if pos_freq and not onset_matched:
                    keep[i] = False

            times = times[keep]

    return times


def build_spectral_profile(y, sr, regions, n_fft=2048, hop_length=512):
    """Build a spectral template from positive focus regions."""
    return _build_spectral_profile_impl(
        y,
        sr,
        regions,
        n_fft=n_fft,
        hop_length=hop_length,
    )


def gate_onsets_by_spectral_match(onset_times, y, sr, profile,
                                  threshold=0.3,
                                  n_fft=2048, hop_length=512,
                                  window_sec=0.1):
    """Keep only onsets whose local spectrum matches the spectral profile."""
    return _gate_onsets_by_spectral_match_impl(
        onset_times,
        y,
        sr,
        profile,
        threshold=threshold,
        n_fft=n_fft,
        hop_length=hop_length,
        window_sec=window_sec,
    )


def gate_onsets_by_amplitude(onset_times, signal, sr, gate_fraction, window_ms):
    """Remove onsets whose local RMS energy falls below a peak-scaled threshold."""
    if gate_fraction <= 0 or len(onset_times) == 0:
        return onset_times

    window_samples = int(sr * window_ms / 1000.0)
    rms_values = librosa.feature.rms(
        y=signal,
        frame_length=window_samples,
        hop_length=window_samples // 2,
    )[0]
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
    """Remove onsets whose attack slope is below a peak-scaled sharpness threshold."""
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


def gate_onsets_by_variable_bounds(
    onset_times,
    y,
    sr,
    ref_analysis,
    per_var_config,
    ref_region,
    window_sec=0.1,
    analyze_region_fn=None,
):
    """Filter onsets by per-variable upper and lower bounds.

    ``analyze_region_fn`` is optional so callers can inject a shared analysis
    helper directly instead of forcing this module to import a broader script.
    """
    if len(onset_times) == 0:
        return np.array(onset_times, dtype=float)

    times = np.array(onset_times, dtype=float)
    skip_keys = {"duration_s"}
    checks = []
    for key, var_cfg in per_var_config.items():
        if key in skip_keys:
            continue
        if not isinstance(var_cfg, dict) or not var_cfg.get("enabled"):
            continue
        ref_value = ref_analysis.get(key)
        if ref_value is None:
            continue
        lower_pct = var_cfg.get("lower_pct", var_cfg.get("deviation_pct", 30))
        upper_pct = var_cfg.get("upper_pct", var_cfg.get("deviation_pct", 30))
        lower_bound = var_cfg.get(
            "lower_bound",
            float(ref_value) * (1 - lower_pct / 100.0),
        )
        upper_bound = var_cfg.get(
            "upper_bound",
            float(ref_value) * (1 + upper_pct / 100.0),
        )
        checks.append((key, lower_bound, upper_bound))

    if not checks:
        return times

    if analyze_region_fn is None:
        try:
            from signal_selector import analyze_region as analyze_region_fn
        except ImportError:
            return times

    f_low = ref_region.get("f_low", 0)
    f_high = ref_region.get("f_high", sr // 2)
    half_window = window_sec / 2.0
    keep = np.ones(len(times), dtype=bool)

    for index, onset_time in enumerate(times):
        start_time = max(0.0, onset_time - half_window)
        end_time = min(len(y) / sr, onset_time + half_window)
        if end_time - start_time < 0.005:
            continue
        try:
            candidate = analyze_region_fn(y, sr, start_time, end_time, f_low, f_high)
        except Exception:
            continue

        for key, lower_bound, upper_bound in checks:
            candidate_value = candidate.get(key)
            if candidate_value is None:
                keep[index] = False
                break
            if candidate_value < lower_bound or candidate_value > upper_bound:
                keep[index] = False
                break

    return times[keep]


def apply_highpass(signal, sr, cutoff_hz):
    """Apply a 4th-order Butterworth high-pass filter to the audio signal."""
    sos = butter(4, cutoff_hz, btype="high", fs=sr, output="sos")
    return sosfilt(sos, signal).astype(signal.dtype)


def gate_onsets_by_broadband(onset_times, signal, sr, min_bands, n_bands=6,
                             threshold=0.15):
    """Remove onsets that do not excite enough frequency bands simultaneously."""
    if min_bands <= 0 or len(onset_times) == 0:
        return onset_times

    n_fft = 2048
    hop_length = 512
    spectrogram = np.abs(librosa.stft(signal, n_fft=n_fft, hop_length=hop_length))
    n_freq_bins = spectrogram.shape[0]
    band_edges = np.linspace(0, n_freq_bins, n_bands + 1, dtype=int)

    band_energy = np.zeros((n_bands, spectrogram.shape[1]))
    for band_index in range(n_bands):
        lower, upper = band_edges[band_index], band_edges[band_index + 1]
        if upper > lower:
            band_energy[band_index] = np.sum(spectrogram[lower:upper] ** 2, axis=0)

    band_peaks = np.max(band_energy, axis=1)
    band_peaks[band_peaks == 0] = 1.0
    band_thresholds = threshold * band_peaks

    onset_frames = librosa.time_to_frames(
        onset_times,
        sr=sr,
        hop_length=hop_length,
        n_fft=n_fft,
    )
    onset_frames = np.clip(onset_frames, 0, spectrogram.shape[1] - 1)

    kept = []
    for onset_time, frame_index in zip(onset_times, onset_frames):
        active_bands = int(np.sum(band_energy[:, frame_index] >= band_thresholds))
        if active_bands >= min_bands:
            kept.append(onset_time)

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