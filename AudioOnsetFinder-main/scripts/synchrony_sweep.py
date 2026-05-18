"""Synchrony threshold sweep — assess temporal separability of group beats.

Detects onsets in one or more audio files with clustering disabled, then sweeps
a range of merge-window values to show how onset count changes as the tolerance
for "near-simultaneous" grows.  This directly answers: at what minimum spacing
can individual beats still be discriminated?

Usage examples:
    # Sweep a single file (uses ensemble preset defaults)
    python scripts/synchrony_sweep.py path/to/audio.ogg

    # Sweep all files in a folder
    python scripts/synchrony_sweep.py path/to/folder/

    # Custom sweep range (1–80 ms in 0.5 ms steps)
    python scripts/synchrony_sweep.py path/to/audio.ogg --min-ms 1 --max-ms 80 --step-ms 0.5

    # Use settings from pipeline_config.json (onset method, delta, etc.)
    python scripts/synchrony_sweep.py path/to/audio.ogg --use-config

Outputs:
    <audio_folder>/synchrony_sweep_results.csv   — per-file onset counts at each threshold
    <audio_folder>/synchrony_sweep_plot.png       — visual curve of onset count vs threshold
    <audio_folder>/synchrony_ioi_histogram.png    — histogram of raw inter-onset intervals
"""

import argparse
import json
import os
import sys

import librosa
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import butter, sosfilt

# Allow importing sibling modules when run from the project root.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from onset_detectors import detect_onsets, refine_onsets_to_sample

# ── Lightweight copies of the helper functions (avoid circular imports) ──────

def _apply_highpass(signal, sr, cutoff_hz):
    sos = butter(4, cutoff_hz, btype="high", fs=sr, output="sos")
    return sosfilt(sos, signal).astype(signal.dtype)


def _cluster_onsets(onset_times, cluster_window_ms):
    if len(onset_times) <= 1:
        return np.array(onset_times, dtype=float)
    window_s = cluster_window_ms / 1000.0
    kept = [float(onset_times[0])]
    for t in onset_times[1:]:
        if float(t) - kept[-1] >= window_s:
            kept.append(float(t))
    return np.array(kept, dtype=float)


def _enforce_min_interval(onset_times, min_interval_ms):
    if min_interval_ms <= 0 or len(onset_times) <= 1:
        return onset_times
    min_s = min_interval_ms / 1000.0
    kept = [onset_times[0]]
    for t in onset_times[1:]:
        if t - kept[-1] >= min_s:
            kept.append(t)
    return np.array(kept, dtype=float)


def _gate_by_amplitude(onset_times, y, sr, gate_frac, window_ms):
    if gate_frac <= 0 or len(onset_times) == 0:
        return onset_times
    win = int(sr * window_ms / 1000.0)
    rms = librosa.feature.rms(y=y, frame_length=win, hop_length=win // 2)[0]
    rms_t = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=win // 2)
    thresh = gate_frac * float(np.max(rms))
    return np.array([t for t in onset_times
                     if rms[int(np.argmin(np.abs(rms_t - t)))] >= thresh], dtype=float)


# ── Core analysis ────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac", ".wma", ".opus"}


def detect_raw_onsets(filepath, cfg):
    """Load audio, detect onsets with no clustering/min-IOI, return (onsets, sr, duration)."""
    y, sr = librosa.load(filepath, sr=cfg.get("sr", None), mono=True)

    hp_hz = cfg.get("HIGHPASS_CUTOFF_HZ", 60)
    if hp_hz > 0:
        y = _apply_highpass(y, sr, hp_hz)

    duration = librosa.get_duration(y=y, sr=sr)

    method = cfg.get("ONSET_METHOD", "adaptive_hp")
    kwargs = {}
    if method == "adaptive_hp":
        kwargs = dict(
            hp_smooth_lambda=cfg.get("HP_SMOOTH_LAMBDA", 50.0),
            hp_threshold_lambda=cfg.get("HP_THRESHOLD_LAMBDA", 5e7),
            envelope_window_ms=cfg.get("HP_ENVELOPE_WINDOW_MS", 10.0),
            envelope_hop_ms=cfg.get("HP_ENVELOPE_HOP_MS", 1.0),
        )
    elif method == "librosa":
        kwargs = dict(
            hop_length=cfg.get("ONSET_HOP_LENGTH", 128),
            delta=cfg.get("ONSET_DELTA", 0.04),
            backtrack=cfg.get("ONSET_BACKTRACK", False),
        )
    elif method == "superflux":
        kwargs = dict(
            hop_length=cfg.get("ONSET_HOP_LENGTH", 128),
            lag=cfg.get("SUPERFLUX_LAG", 2),
            max_size=cfg.get("SUPERFLUX_MAX_SIZE", 3),
            delta=cfg.get("ONSET_DELTA", 0.04),
        )
    elif method == "per_band":
        kwargs = dict(
            hop_length=cfg.get("ONSET_HOP_LENGTH", 128),
            n_bands=cfg.get("PER_BAND_N_BANDS", 6),
            freq_min=cfg.get("PER_BAND_FREQ_MIN", 200),
            freq_max=cfg.get("PER_BAND_FREQ_MAX", None),
            median_window_ms=cfg.get("PER_BAND_MEDIAN_MS", 200.0),
            threshold_scale=cfg.get("PER_BAND_THRESHOLD_SCALE", 1.5),
            min_bands=cfg.get("PER_BAND_MIN_BANDS", 2),
        )

    onsets = detect_onsets(method, y, sr, **kwargs)

    if cfg.get("ONSET_REFINE_ENABLED", True) and len(onsets) > 0:
        onsets = refine_onsets_to_sample(
            onsets, y, sr,
            window_ms=cfg.get("ONSET_REFINE_WINDOW_MS", 5),
            energy_gate=cfg.get("ONSET_REFINE_ENERGY_GATE", 0.0),
        )

    amp_gate = cfg.get("ONSET_AMPLITUDE_GATE", 0.02)
    if amp_gate > 0:
        onsets = _gate_by_amplitude(onsets, y, sr, amp_gate,
                                    cfg.get("ONSET_AMPLITUDE_WINDOW_MS", 30))

    return np.sort(onsets), sr, duration


def sweep_thresholds(raw_onsets, min_ms=0.0, max_ms=100.0, step_ms=1.0):
    """Return (thresholds_ms, onset_counts) for a range of cluster-window values."""
    thresholds = np.arange(min_ms, max_ms + step_ms / 2, step_ms)
    counts = []
    for t in thresholds:
        merged = _cluster_onsets(raw_onsets, t)
        counts.append(len(merged))
    return thresholds, np.array(counts)


def sweep_min_ioi(raw_onsets, min_ms=0.0, max_ms=100.0, step_ms=1.0):
    """Return (thresholds_ms, onset_counts) for a range of min-IOI values."""
    thresholds = np.arange(min_ms, max_ms + step_ms / 2, step_ms)
    counts = []
    for t in thresholds:
        kept = _enforce_min_interval(raw_onsets, t)
        counts.append(len(kept))
    return thresholds, np.array(counts)


# ── Plotting ─────────────────────────────────────────────────────────────────

def plot_sweep(sweep_data, output_path, title_prefix=""):
    """Plot onset-count vs merge-threshold curves for all files.

    sweep_data: list of (filename, thresholds, cluster_counts, ioi_counts)
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), sharey=True)

    for fname, thresholds, cluster_counts, ioi_counts in sweep_data:
        label = os.path.splitext(fname)[0]
        ax1.plot(thresholds, cluster_counts, label=label, linewidth=1.5)
        ax2.plot(thresholds, ioi_counts, label=label, linewidth=1.5)

    ax1.set_xlabel("Cluster window (ms)")
    ax1.set_ylabel("Onset count")
    ax1.set_title(f"{title_prefix}Onset clustering sweep")
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    ax2.set_xlabel("Min inter-onset interval (ms)")
    ax2.set_title(f"{title_prefix}Min-IOI sweep")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"  Sweep plot saved → {output_path}")


def plot_ioi_histogram(all_iois_ms, output_path, title_prefix=""):
    """Plot a histogram of raw inter-onset intervals (ms)."""
    if len(all_iois_ms) == 0:
        return

    fig, ax = plt.subplots(figsize=(10, 5))

    # Use fine bins up to 200 ms to see the close-together structure
    bins_fine = np.arange(0, min(200, np.max(all_iois_ms) + 2), 1)
    ax.hist(all_iois_ms[all_iois_ms < 200], bins=bins_fine, color="#4caf50",
            alpha=0.8, edgecolor="none")

    ax.set_xlabel("Inter-onset interval (ms)")
    ax.set_ylabel("Count")
    ax.set_title(f"{title_prefix}Raw IOI distribution (< 200 ms)")
    ax.axvline(5, color="red", linestyle="--", alpha=0.6, label="5 ms")
    ax.axvline(10, color="orange", linestyle="--", alpha=0.6, label="10 ms")
    ax.axvline(25, color="blue", linestyle="--", alpha=0.6, label="25 ms")
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"  IOI histogram saved → {output_path}")


# ── Main ─────────────────────────────────────────────────────────────────────

def build_config(args):
    """Build config dict from args, optionally merging pipeline_config.json."""
    cfg = {
        "HIGHPASS_CUTOFF_HZ": 60,
        "ONSET_METHOD": "adaptive_hp",
        "HP_SMOOTH_LAMBDA": 50.0,
        "HP_THRESHOLD_LAMBDA": 5e7,
        "HP_ENVELOPE_WINDOW_MS": 10.0,
        "HP_ENVELOPE_HOP_MS": 1.0,
        "ONSET_DELTA": 0.04,
        "ONSET_HOP_LENGTH": 128,
        "ONSET_BACKTRACK": False,
        "ONSET_REFINE_ENABLED": True,
        "ONSET_REFINE_WINDOW_MS": 5,
        "ONSET_REFINE_ENERGY_GATE": 0.0,
        "ONSET_AMPLITUDE_GATE": 0.02,
        "ONSET_AMPLITUDE_WINDOW_MS": 30,
    }

    if args.use_config:
        config_path = os.path.join(os.path.dirname(_SCRIPT_DIR), "pipeline_config.json")
        if os.path.isfile(config_path):
            with open(config_path) as f:
                pcfg = json.load(f)
            ext = pcfg.get("extractor", {})
            for k in cfg:
                if k in ext:
                    cfg[k] = ext[k]
            print(f"  Loaded overrides from {config_path}")

    return cfg


def main():
    parser = argparse.ArgumentParser(
        description="Synchrony threshold sweep — assess beat separability in group audio"
    )
    parser.add_argument("path", help="Audio file or folder of audio files")
    parser.add_argument("--min-ms", type=float, default=0.0,
                        help="Sweep start (ms). Default: 0")
    parser.add_argument("--max-ms", type=float, default=100.0,
                        help="Sweep end (ms). Default: 100")
    parser.add_argument("--step-ms", type=float, default=1.0,
                        help="Sweep step size (ms). Default: 1")
    parser.add_argument("--use-config", action="store_true",
                        help="Load onset detection settings from pipeline_config.json")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory for results (default: same as input)")
    args = parser.parse_args()

    cfg = build_config(args)

    # Resolve input files
    target = os.path.abspath(args.path)
    if os.path.isfile(target):
        audio_files = [target]
        audio_dir = os.path.dirname(target)
    elif os.path.isdir(target):
        audio_dir = target
        audio_files = sorted([
            os.path.join(target, f) for f in os.listdir(target)
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
        ])
    else:
        print(f"Error: path not found: {target}")
        sys.exit(1)

    if not audio_files:
        print(f"No audio files found in {target}")
        sys.exit(1)

    out_dir = args.output_dir or audio_dir
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n{'=' * 60}")
    print(f"  SYNCHRONY THRESHOLD SWEEP")
    print(f"  Files: {len(audio_files)}")
    print(f"  Sweep: {args.min_ms}–{args.max_ms} ms (step {args.step_ms} ms)")
    print(f"  Method: {cfg['ONSET_METHOD']}")
    print(f"{'=' * 60}\n")

    sweep_data = []
    all_raw_iois_ms = []
    summary_rows = []

    for fpath in audio_files:
        fname = os.path.basename(fpath)
        print(f"  Processing: {fname}")

        raw_onsets, sr, duration = detect_raw_onsets(fpath, cfg)
        n_raw = len(raw_onsets)

        if n_raw < 2:
            print(f"    Only {n_raw} onset(s) detected — skipping sweep")
            continue

        raw_iois_ms = np.diff(raw_onsets) * 1000.0
        all_raw_iois_ms.append(raw_iois_ms)

        thresholds, cluster_counts = sweep_thresholds(
            raw_onsets, args.min_ms, args.max_ms, args.step_ms
        )
        _, ioi_counts = sweep_min_ioi(
            raw_onsets, args.min_ms, args.max_ms, args.step_ms
        )

        sweep_data.append((fname, thresholds, cluster_counts, ioi_counts))

        # Summary statistics
        pct_below_5 = 100.0 * np.sum(raw_iois_ms < 5) / len(raw_iois_ms)
        pct_below_10 = 100.0 * np.sum(raw_iois_ms < 10) / len(raw_iois_ms)
        pct_below_25 = 100.0 * np.sum(raw_iois_ms < 25) / len(raw_iois_ms)

        # Find the steepest drop — where the most merging happens
        count_diffs = np.diff(cluster_counts)
        if len(count_diffs) > 0:
            steepest_idx = int(np.argmin(count_diffs))
            steepest_ms = thresholds[steepest_idx + 1]
            steepest_drop = int(-count_diffs[steepest_idx])
        else:
            steepest_ms = 0
            steepest_drop = 0

        summary_rows.append({
            "File": fname,
            "Duration (s)": round(duration, 2),
            "Raw onsets": n_raw,
            "Min IOI (ms)": round(float(np.min(raw_iois_ms)), 2),
            "Median IOI (ms)": round(float(np.median(raw_iois_ms)), 2),
            "Mean IOI (ms)": round(float(np.mean(raw_iois_ms)), 2),
            "IOIs < 5 ms (%)": round(pct_below_5, 1),
            "IOIs < 10 ms (%)": round(pct_below_10, 1),
            "IOIs < 25 ms (%)": round(pct_below_25, 1),
            "Steepest merge at (ms)": round(steepest_ms, 1),
            "Onsets lost at steepest": steepest_drop,
            "Onsets at 0 ms": int(cluster_counts[0]) if len(cluster_counts) > 0 else n_raw,
            "Onsets at 5 ms": int(cluster_counts[min(int(5 / args.step_ms), len(cluster_counts) - 1)]),
            "Onsets at 10 ms": int(cluster_counts[min(int(10 / args.step_ms), len(cluster_counts) - 1)]),
            "Onsets at 25 ms": int(cluster_counts[min(int(25 / args.step_ms), len(cluster_counts) - 1)]),
            "Onsets at 50 ms": int(cluster_counts[min(int(50 / args.step_ms), len(cluster_counts) - 1)]),
        })

        print(f"    {n_raw} raw onsets | min IOI = {np.min(raw_iois_ms):.1f} ms | "
              f"median = {np.median(raw_iois_ms):.1f} ms")
        print(f"    IOIs < 5 ms: {pct_below_5:.1f}% | < 10 ms: {pct_below_10:.1f}% | "
              f"< 25 ms: {pct_below_25:.1f}%")
        print(f"    Steepest drop at {steepest_ms:.1f} ms ({steepest_drop} onsets merged)")

    if not sweep_data:
        print("\nNo files had enough onsets for analysis.")
        sys.exit(0)

    # Build per-threshold CSV with all files
    csv_rows = []
    for fname, thresholds, cluster_counts, ioi_counts in sweep_data:
        for i, t in enumerate(thresholds):
            csv_rows.append({
                "File": fname,
                "Threshold (ms)": round(t, 2),
                "Onsets (cluster sweep)": int(cluster_counts[i]),
                "Onsets (min-IOI sweep)": int(ioi_counts[i]),
            })

    csv_path = os.path.join(out_dir, "synchrony_sweep_results.csv")
    pd.DataFrame(csv_rows).to_csv(csv_path, index=False)
    print(f"\n  Sweep data saved → {csv_path}")

    # Summary CSV
    summary_path = os.path.join(out_dir, "synchrony_sweep_summary.csv")
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False)
    print(f"  Summary saved   → {summary_path}")

    # Plots
    plot_sweep(sweep_data, os.path.join(out_dir, "synchrony_sweep_plot.png"))

    all_iois = np.concatenate(all_raw_iois_ms) if all_raw_iois_ms else np.array([])
    plot_ioi_histogram(all_iois, os.path.join(out_dir, "synchrony_ioi_histogram.png"))

    # Print summary table
    print(f"\n{'─' * 60}")
    print("  SUMMARY")
    print(f"{'─' * 60}")
    for row in summary_rows:
        print(f"\n  {row['File']}")
        print(f"    {row['Raw onsets']} onsets in {row['Duration (s)']}s")
        print(f"    Min IOI: {row['Min IOI (ms)']} ms | Median: {row['Median IOI (ms)']} ms")
        print(f"    Onsets surviving at  5 ms: {row['Onsets at 5 ms']}")
        print(f"    Onsets surviving at 10 ms: {row['Onsets at 10 ms']}")
        print(f"    Onsets surviving at 25 ms: {row['Onsets at 25 ms']}")
        print(f"    Onsets surviving at 50 ms: {row['Onsets at 50 ms']}")
    print()


if __name__ == "__main__":
    main()
