"""Lag-one autocorrelation on inter-hit intervals (Category A4).

Per recording (or pooled by group), compute Pearson autocorrelation of
consecutive inter-hit intervals at lag 1. A negative lag-1 r indicates
the classic "short-long-short-long" alternation pattern.

Outputs:
- ``autocorr_lag1.csv`` (file, group, r_lag1, CI_low, CI_high, n)
- violin plot of r_lag1 by group with 0-reference line.
"""

from __future__ import annotations

import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, os.path.join(_PROJECT_DIR, "scripts"))

from group_assignment import (  # noqa: E402
    assign_groups, ensure_output_folder, get_palette, load_dyadic_events,
    load_file_summaries, order_groups, save_figure,
)

# Defaults
excel_path = os.path.join(_PROJECT_DIR, "Cross_Species_Rhythm_Data.xlsx")
output_folder = os.path.join(_PROJECT_DIR, "Lag1_Autocorrelation")

AC_DATASET = "raw"
AC_GROUP_SOURCE = "filename_pattern"
AC_GROUP_PATTERN = r"(?P<group>[A-Za-z]+)_"
AC_GROUP_CSV_PATH = ""
AC_MANUAL_GROUPS: dict = {}
AC_GROUP_EXCEL_COLUMN = "Group"
AC_UNGROUPED_LABEL = "Ungrouped"
AC_GROUP_ORDER = ""

# Step-specific
AC_INTERVAL_SOURCE = "auto"        # "auto" | column name like "IOI (ms)"
AC_MIN_INTERVALS_PER_BOUT = 5
AC_DETREND = "mean"                # "none" | "mean" | "linear"
AC_CONFIDENCE_METHOD = "fisher_z"  # "fisher_z" | "bootstrap"
AC_N_BOOTSTRAP = 1000
AC_CONFIDENCE_LEVEL = 0.95
AC_RANDOM_SEED = 42
AC_GROUP_AGGREGATION = "per_file"  # "per_file" | "pooled_by_group"

# Generic plot settings
AC_FIG_WIDTH = 10
AC_FIG_HEIGHT = 6
AC_DPI = 300
AC_PALETTE = "Set2"
AC_TITLE = "Lag-1 Autocorrelation of Inter-Hit Intervals"
AC_BG_COLOR = "#ffffff"
AC_OUTPUT_FORMAT = "png"

_cfg_path = os.path.join(_PROJECT_DIR, "pipeline_config.json")
if os.path.isfile(_cfg_path):
    with open(_cfg_path) as _f:
        _cfg = json.load(_f).get("lag_one_autocorrelation", {})
    excel_path = _cfg.get("excel_path", excel_path)
    output_folder = _cfg.get("output_folder", output_folder)
    for _k in list(globals().keys()):
        if _k.startswith("AC_") and _k in _cfg:
            globals()[_k] = _cfg[_k]
    del _f, _cfg

ensure_output_folder(output_folder)

# Load data
print(f"[lagOneAutocorrelation] Loading {excel_path} ({AC_DATASET} dataset)...")
df_summary = load_file_summaries(excel_path)
df_events = load_dyadic_events(excel_path, dataset=AC_DATASET)

# ----------------------------------------------------------------------
# Interval column resolution.
# ----------------------------------------------------------------------
# The Onset Finder produces OVERLAPPING dyads: each row k carries
# (Interval 1, Interval 2) = (I_k, I_{k+1}). The original IOI sequence
# for a file is therefore Interval1[0..N-1] + [Interval2[N-1]], NOT
# Interval1 ++ Interval2 (which would double-count every IOI).
#
# AC_INTERVAL_SOURCE:
#   "auto"            -> reconstruct the per-file IOI sequence from
#                        Interval 1 + Interval 2.
#   "Interval 1 (ms)" / "Interval 2 (ms)" / other column name
#                     -> use that single column directly (legacy /
#                        for single-IOI exports).
# ----------------------------------------------------------------------
_I1, _I2 = "Interval 1 (ms)", "Interval 2 (ms)"
_AUTO_SINGLE_COL = ("IOI (ms)", "IHI (ms)", "IOI", "IHI",
                    "Interval (ms)", "Interval", "i1 (ms)", "i1")

_use_dyadic_reconstruction = False
iv_col = None
if AC_INTERVAL_SOURCE == "auto":
    if _I1 in df_events.columns and _I2 in df_events.columns:
        _use_dyadic_reconstruction = True
        iv_col = _I1  # reported as the "base" column
        print("[lagOneAutocorrelation] reconstructing IOI sequence from "
              f"'{_I1}' + '{_I2}' (correct handling of overlapping dyads).")
    else:
        for candidate in _AUTO_SINGLE_COL:
            if candidate in df_events.columns:
                iv_col = candidate
                break
        if iv_col is None:
            print("ERROR: No interval column found in Dyadic Events. "
                  "Set AC_INTERVAL_SOURCE explicitly.")
            print("Available columns:", list(df_events.columns))
            sys.exit(1)
        print(f"[lagOneAutocorrelation] Using single interval column: {iv_col}")
else:
    iv_col = AC_INTERVAL_SOURCE
    if iv_col not in df_events.columns:
        print(f"ERROR: Column '{iv_col}' not in Dyadic Events sheet.")
        print("Available columns:", list(df_events.columns))
        sys.exit(1)
    print(f"[lagOneAutocorrelation] Using interval column: {iv_col}")

# Build the working frame. Keep Dyad Index (if present) so we can sort
# rows within each file rather than trusting pandas ingestion order.
_keep_cols = ["File Name"]
if "Dyad Index" in df_events.columns:
    _keep_cols.append("Dyad Index")
if _use_dyadic_reconstruction:
    _keep_cols += [_I1, _I2]
else:
    _keep_cols.append(iv_col)
df = df_events[_keep_cols].copy()

# Coerce numerics.
for c in [c for c in (_I1, _I2, iv_col) if c in df.columns]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

if "Dyad Index" in df.columns:
    df["Dyad Index"] = pd.to_numeric(df["Dyad Index"], errors="coerce")

df = assign_groups(
    df, source=AC_GROUP_SOURCE, pattern=AC_GROUP_PATTERN,
    csv_path=AC_GROUP_CSV_PATH, manual_map=AC_MANUAL_GROUPS,
    ungrouped=AC_UNGROUPED_LABEL, excel_column=AC_GROUP_EXCEL_COLUMN,
    df_summary=df_summary)
groups = order_groups(df, AC_GROUP_ORDER)
print(f"[lagOneAutocorrelation] groups: {groups}")


def _ioi_sequence_for_file(sub: pd.DataFrame) -> np.ndarray:
    """Reconstruct the contiguous IOI sequence for one file.

    Handles the overlapping-dyad convention used by the Onset Finder:
        dyad k -> (I_k, I_{k+1})
    So the original IOI sequence is Interval1[0..N-1] + [Interval2[N-1]].
    """
    if "Dyad Index" in sub.columns:
        sub = sub.sort_values("Dyad Index", kind="stable")
    if _use_dyadic_reconstruction:
        i1 = sub[_I1].to_numpy(dtype=float)
        i2 = sub[_I2].to_numpy(dtype=float)
        # Drop rows where either is NaN to keep the sequence contiguous.
        mask = np.isfinite(i1) & np.isfinite(i2)
        i1, i2 = i1[mask], i2[mask]
        if len(i1) == 0:
            return np.array([], dtype=float)
        return np.concatenate([i1, i2[-1:]])
    vals = sub[iv_col].to_numpy(dtype=float)
    return vals[np.isfinite(vals)]


def _detrend(x: np.ndarray, mode: str) -> np.ndarray:
    if mode == "none":
        return x
    if mode == "mean":
        return x - np.mean(x)
    if mode == "linear":
        t = np.arange(len(x))
        slope, intercept = np.polyfit(t, x, 1)
        return x - (slope * t + intercept)
    return x


def _fisher_ci(r: float, n: int, conf: float):
    """Fisher z-transform CI for a Pearson correlation.

    Note: n is the number of *pairs* used to compute r, not the number
    of IOIs. For lag-1 autocorrelation of an IOI sequence of length L
    we have n = L - 1 pairs.
    """
    if n < 4 or np.isnan(r) or abs(r) >= 1:
        return (np.nan, np.nan)
    z = np.arctanh(r)
    se = 1 / np.sqrt(n - 3)
    q = stats.norm.ppf(1 - (1 - conf) / 2)
    lo = np.tanh(z - q * se)
    hi = np.tanh(z + q * se)
    return float(lo), float(hi)


def _bootstrap_ci_pairs(x: np.ndarray, n_boot: int, conf: float, rng):
    """Pair-preserving bootstrap CI for lag-1 autocorrelation.

    We resample WITH REPLACEMENT from the set of consecutive lag-1 pairs
    (a_i, b_i) = (x_i, x_{i+1}), then recompute Pearson r each time.
    Resampling pairs (rather than individual x values) preserves the
    lag-1 structure we are trying to estimate.
    """
    n = len(x)
    if n < 4:
        return (np.nan, np.nan)
    a = x[:-1]
    b = x[1:]
    m = len(a)
    rs = np.empty(int(n_boot), dtype=float)
    # Vectorised: draw one n_boot x m matrix of indices, compute r per row.
    idx = rng.integers(0, m, size=(int(n_boot), m))
    A = a[idx]
    B = b[idx]
    a_mean = A.mean(axis=1, keepdims=True)
    b_mean = B.mean(axis=1, keepdims=True)
    A0, B0 = A - a_mean, B - b_mean
    num = (A0 * B0).sum(axis=1)
    den = np.sqrt((A0 ** 2).sum(axis=1) * (B0 ** 2).sum(axis=1))
    with np.errstate(invalid="ignore", divide="ignore"):
        rs = np.where(den > 0, num / den, np.nan)
    rs = rs[np.isfinite(rs)]
    if len(rs) == 0:
        return (np.nan, np.nan)
    lo = float(np.quantile(rs, (1 - conf) / 2))
    hi = float(np.quantile(rs, 1 - (1 - conf) / 2))
    return lo, hi


def _lag1_r(x: np.ndarray):
    if len(x) < 3:
        return np.nan
    a = x[:-1]
    b = x[1:]
    if np.std(a) == 0 or np.std(b) == 0:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


rng = np.random.default_rng(int(AC_RANDOM_SEED))
rows = []
_min_iv = int(AC_MIN_INTERVALS_PER_BOUT)

# Compute per-file first — always. If AC_GROUP_AGGREGATION == "pooled_by_group"
# we additionally emit a Fisher-z-averaged group summary in a second pass,
# but we never concatenate IOIs across files (that would introduce spurious
# seam pairs).
for (fname, group), sub in df.groupby(["File Name", "Group"], observed=False):
    intervals = _ioi_sequence_for_file(sub)
    if len(intervals) < _min_iv:
        continue
    intervals = _detrend(intervals, AC_DETREND)
    r = _lag1_r(intervals)
    n_pairs = max(len(intervals) - 1, 0)
    if AC_CONFIDENCE_METHOD == "bootstrap":
        lo, hi = _bootstrap_ci_pairs(intervals, AC_N_BOOTSTRAP,
                                     AC_CONFIDENCE_LEVEL, rng)
    else:
        lo, hi = _fisher_ci(r, n_pairs, AC_CONFIDENCE_LEVEL)
    rows.append({
        "File Name": fname, "Group": str(group),
        "n_intervals": int(len(intervals)),
        "n_pairs": int(n_pairs),
        "r_lag1": r, "CI_low": lo, "CI_high": hi,
    })

res_df = pd.DataFrame(rows)

# Optional group-level summary via Fisher-z averaging (concatenation across
# files is mathematically incorrect; z-averaging is the right way to pool).
if AC_GROUP_AGGREGATION == "pooled_by_group" and not res_df.empty:
    group_rows = []
    for g in groups:
        sub = res_df[(res_df["Group"] == g) & res_df["r_lag1"].notna()]
        rs = sub["r_lag1"].to_numpy(dtype=float)
        n_pairs = sub["n_pairs"].to_numpy(dtype=float)
        # Guard |r|<1 for atanh.
        rs_safe = np.clip(rs, -0.9999999, 0.9999999)
        weights = np.maximum(n_pairs - 3.0, 1.0)  # Fisher-z IV weight
        if rs_safe.size == 0 or weights.sum() == 0:
            continue
        z_mean = float(np.sum(np.arctanh(rs_safe) * weights) / weights.sum())
        se = float(1.0 / np.sqrt(weights.sum()))
        q = float(stats.norm.ppf(1 - (1 - AC_CONFIDENCE_LEVEL) / 2))
        r_mean = float(np.tanh(z_mean))
        ci_lo = float(np.tanh(z_mean - q * se))
        ci_hi = float(np.tanh(z_mean + q * se))
        group_rows.append({
            "Group": g, "n_files": int(len(rs)),
            "r_lag1_zmean": r_mean, "CI_low": ci_lo, "CI_high": ci_hi,
        })
    if group_rows:
        pd.DataFrame(group_rows).to_csv(
            os.path.join(output_folder, "autocorr_lag1_group_summary.csv"),
            index=False)
        print("[lagOneAutocorrelation] wrote autocorr_lag1_group_summary.csv")

csv_path = os.path.join(output_folder, "autocorr_lag1.csv")
res_df.to_csv(csv_path, index=False)
print(f"[lagOneAutocorrelation] wrote {csv_path}")
if not res_df.empty:
    print(res_df.groupby("Group")["r_lag1"].describe().to_string())

# ----------------------------------------------------------------------
# Plot: per-file lag-1 r values as violin + box + jittered points,
# with the group Fisher-z mean and its 95% CI overlaid as a diamond.
# ----------------------------------------------------------------------
_OKABE_ITO = ["#0072B2", "#D55E00", "#009E73", "#CC79A7",
              "#F0E442", "#56B4E9", "#E69F00", "#000000"]


def _resolve_palette(palette_str, n):
    key = str(palette_str).strip().lower()
    if key in {"okabe", "okabe-ito", "okabe_ito", "colorblind", "cb"}:
        pal = list(_OKABE_ITO)
        while len(pal) < n:
            pal.extend(_OKABE_ITO)
        return pal[:n]
    return get_palette(palette_str, n)


if not res_df.empty:
    colors = _resolve_palette(AC_PALETTE, len(groups))
    fig, ax = plt.subplots(figsize=(float(AC_FIG_WIDTH), float(AC_FIG_HEIGHT)),
                           facecolor=AC_BG_COLOR, constrained_layout=True)
    per_g = [res_df[res_df["Group"] == g]["r_lag1"].dropna().to_numpy(dtype=float)
             for g in groups]
    positions = np.arange(1, len(groups) + 1)

    jitter_rng = np.random.default_rng(0)
    for pos, vals, c in zip(positions, per_g, colors):
        if len(vals) == 0:
            continue

        # Violin — only if we have at least 2 points.
        if len(vals) >= 2:
            parts = ax.violinplot(
                [vals], positions=[pos], widths=0.75,
                showmeans=False, showmedians=False, showextrema=False,
            )
            for body in parts["bodies"]:
                body.set_facecolor(c)
                body.set_edgecolor(c)
                body.set_alpha(0.35)

            # Boxplot overlay (median, IQR, whiskers) for stats clarity.
            bp = ax.boxplot(
                [vals], positions=[pos], widths=0.18,
                patch_artist=True, showfliers=False,
                medianprops=dict(color="black", linewidth=1.4),
                whiskerprops=dict(color="#333333", linewidth=1.0),
                capprops=dict(color="#333333", linewidth=1.0),
                boxprops=dict(facecolor="white", edgecolor="#333333",
                              linewidth=1.0),
                zorder=4,
            )

        # Jittered raw points.
        jitter = jitter_rng.uniform(-0.15, 0.15, size=len(vals))
        ax.scatter(np.full_like(vals, pos, dtype=float) + jitter, vals,
                   color=c, edgecolor="black", linewidth=0.4,
                   s=24, alpha=0.85, zorder=5)

        # Fisher-z group mean ± CI as a diamond marker.
        rs_safe = np.clip(vals, -0.9999999, 0.9999999)
        # Use per-file n_pairs for weights.
        nps = res_df.loc[res_df["Group"] == groups[pos - 1], "n_pairs"] \
            .to_numpy(dtype=float)
        w = np.maximum(nps - 3.0, 1.0)
        if w.sum() > 0 and len(rs_safe) > 0:
            z_mean = float(np.sum(np.arctanh(rs_safe) * w) / w.sum())
            se = float(1.0 / np.sqrt(w.sum()))
            q = float(stats.norm.ppf(1 - (1 - float(AC_CONFIDENCE_LEVEL)) / 2))
            r_mean = float(np.tanh(z_mean))
            ci_lo = float(np.tanh(z_mean - q * se))
            ci_hi = float(np.tanh(z_mean + q * se))
            ax.errorbar([pos + 0.33], [r_mean],
                        yerr=[[r_mean - ci_lo], [ci_hi - r_mean]],
                        fmt="D", color="black", markerfacecolor=c,
                        markeredgecolor="black", markersize=8,
                        capsize=4, linewidth=1.2, zorder=6,
                        label=("Fisher-z group mean ± 95% CI"
                               if pos == positions[0] else None))

    # Reference lines: r=0 (no autocorrelation) and r=-0.5 (alternation).
    ax.axhline(0.0, color="#555555", linestyle="--", linewidth=1.0,
               zorder=1, label="r = 0 (no autocorr.)")
    ax.axhline(-0.5, color="#D55E00", linestyle=":", linewidth=1.0,
               zorder=1, label="r = −0.5 (short-long alternation)")

    ax.set_xticks(positions)
    xtick_labels = []
    for g, vals in zip(groups, per_g):
        xtick_labels.append(f"{g}\n(n_files={len(vals)})")
    ax.set_xticklabels(xtick_labels, rotation=0)
    ax.set_ylabel(r"Lag-1 autocorrelation of IOIs  ($r_1$)", fontsize=11)
    ax.set_title(AC_TITLE, fontsize=13)
    ax.set_ylim(-1.05, 1.05)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # Deduplicate legend entries (violin/box repeated per group).
    handles, labels = ax.get_legend_handles_labels()
    seen = set()
    uniq = [(h, l) for h, l in zip(handles, labels) if not (l in seen or seen.add(l))]
    if uniq:
        ax.legend([h for h, _ in uniq], [l for _, l in uniq],
                  loc="upper left", bbox_to_anchor=(1.01, 1.0),
                  frameon=False, fontsize=9, borderaxespad=0.0)

    save_figure(fig, output_folder, "autocorr_lag1_by_group",
                fmt=AC_OUTPUT_FORMAT, dpi=int(AC_DPI))
    plt.close(fig)

print("[lagOneAutocorrelation] done.")
