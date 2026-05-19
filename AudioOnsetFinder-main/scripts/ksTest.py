"""Kolmogorov-Smirnov test (Category A2).

For each group, compare the empirical distribution of rhythm ratios r_k
against a simulated null distribution (Uniform(0,1) by default),
reporting the D statistic and a permutation / analytic p-value.

Writes a CSV of per-group results plus overlayed ECDF plots.
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
    load_file_summaries, order_groups, save_figure, write_csv_dataframe,
)

# Defaults
excel_path = os.path.join(_PROJECT_DIR, "Cross_Species_Rhythm_Data.xlsx")
output_folder = os.path.join(_PROJECT_DIR, "KS_Test")

KS_DATASET = "raw"
KS_GROUP_SOURCE = "filename_pattern"
KS_GROUP_PATTERN = r"(?P<group>[A-Za-z]+)_"
KS_GROUP_CSV_PATH = ""
KS_MANUAL_GROUPS: dict = {}
KS_GROUP_EXCEL_COLUMN = "Group"
KS_UNGROUPED_LABEL = "Ungrouped"
KS_GROUP_ORDER = ""

# Step-specific
KS_NULL_DISTRIBUTION = "uniform"   # "uniform" | "bootstrap_shuffle" | "custom_csv"
KS_NULL_CSV_PATH = ""
KS_N_NULL_SAMPLES = 10000
KS_RANDOM_SEED = 42
KS_ALTERNATIVE = "two-sided"       # "two-sided" | "less" | "greater"
KS_MULTIPLE_COMPARISONS = "none"    # "none" | "bonferroni" | "fdr_bh"
KS_ALPHA = 0.05

# Generic plot settings
KS_FIG_WIDTH = 10
KS_FIG_HEIGHT = 6
KS_DPI = 300
KS_PALETTE = "Set2"
KS_TITLE = "Rhythm-Ratio ECDF vs Uniform Null"
KS_BG_COLOR = "#ffffff"
KS_OUTPUT_FORMAT = "png"

# Config override
_cfg_path = os.path.join(_PROJECT_DIR, "pipeline_config.json")
if os.path.isfile(_cfg_path):
    with open(_cfg_path) as _f:
        _cfg = json.load(_f).get("ks_test", {})
    excel_path = _cfg.get("excel_path", excel_path)
    output_folder = _cfg.get("output_folder", output_folder)
    for _k in list(globals().keys()):
        if _k.startswith("KS_") and _k in _cfg:
            globals()[_k] = _cfg[_k]
    del _f, _cfg

ensure_output_folder(output_folder)

# Load data
print(f"[ksTest] Loading {excel_path} ({KS_DATASET} dataset)...")
df_summary = load_file_summaries(excel_path)
df_events = load_dyadic_events(excel_path, dataset=KS_DATASET)

# Locate the r_k column. The Onset Finder writes "Rhythm Ratio [r_k]";
# fall back to legacy spellings or any column whose name contains "r_k".
r_col = None
_EXACT_CANDIDATES = (
    "Rhythm Ratio [r_k]",
    "Rhythm Ratio (r_k)",
    "r_k",
    "r (Rhythm Ratio)",
    "Rhythm Ratio",
    "r",
)
for candidate in _EXACT_CANDIDATES:
    if candidate in df_events.columns:
        r_col = candidate
        break
if r_col is None:
    for col in df_events.columns:
        if "r_k" in str(col).lower():
            r_col = col
            break
if r_col is None:
    print("ERROR: r_k column not found in Dyadic Events.")
    print("Available columns:", list(df_events.columns))
    sys.exit(1)
print(f"[ksTest] using column '{r_col}' for r_k.")

df = df_events[["File Name", r_col]].copy()
df[r_col] = pd.to_numeric(df[r_col], errors="coerce")
_n_raw = len(df)
df = df.dropna(subset=[r_col])
# r_k is bounded on the open interval (0, 1); discard out-of-range rows
# so the ECDFs line up with the Uniform(0,1) support.
df = df[(df[r_col] > 0.0) & (df[r_col] < 1.0)]
_n_dropped = _n_raw - len(df)
if _n_dropped:
    print(f"[ksTest] dropped {_n_dropped} NaN / out-of-range r_k rows "
          f"(kept {len(df)}).")

df = assign_groups(
    df, source=KS_GROUP_SOURCE, pattern=KS_GROUP_PATTERN,
    csv_path=KS_GROUP_CSV_PATH, manual_map=KS_MANUAL_GROUPS,
    ungrouped=KS_UNGROUPED_LABEL, excel_column=KS_GROUP_EXCEL_COLUMN,
    df_summary=df_summary)
groups = order_groups(df, KS_GROUP_ORDER)
print(f"[ksTest] groups: {groups}")

# Cache per-group arrays once (avoid repeated boolean scans).
_grouped = {g: np.asarray(sub[r_col].values, dtype=float)
            for g, sub in df.groupby("Group", sort=False)}

# ----------------------------------------------------------------------
# Null construction
# ----------------------------------------------------------------------
# Three modes:
#   - "uniform": compare each group to the analytic Uniform(0,1) CDF
#     using ks_1samp. No Monte-Carlo draw is needed; this is the most
#     powerful test for the isochrony-neutral null.
#   - "bootstrap_shuffle": for each group g, resample from the pooled
#     r_k of the OTHER groups (excluding g itself) so the null is not
#     contaminated with the target's own distribution.
#   - "custom_csv": user-supplied null; compared with ks_2samp.
# A shared "reference null" sample is also drawn once (from all data
# for bootstrap, or from Uniform(0,1) for uniform) purely for plotting
# the null ECDF curve.
# ----------------------------------------------------------------------
rng = np.random.default_rng(int(KS_RANDOM_SEED))
_n_null = int(KS_N_NULL_SAMPLES)
_null_mode = str(KS_NULL_DISTRIBUTION).strip().lower()

if _null_mode == "uniform":
    null_sample_for_plot = np.sort(rng.uniform(0, 1, size=_n_null))
    custom_null_sample = None
elif _null_mode in ("bootstrap_shuffle", "bootstrap"):
    pool_all = df[r_col].to_numpy()
    if len(pool_all) == 0:
        print("ERROR: bootstrap_shuffle null requested but data pool is empty.")
        sys.exit(1)
    null_sample_for_plot = np.sort(
        rng.choice(pool_all, size=_n_null, replace=True))
    custom_null_sample = None  # per-group null is built inside the loop
elif _null_mode in ("custom_csv", "custom"):
    if not KS_NULL_CSV_PATH or not os.path.isfile(KS_NULL_CSV_PATH):
        print(f"ERROR: Custom null CSV not found: {KS_NULL_CSV_PATH}")
        sys.exit(1)
    null_df = pd.read_csv(KS_NULL_CSV_PATH)
    col = null_df.columns[0]
    custom_null_sample = pd.to_numeric(null_df[col], errors="coerce") \
        .dropna().to_numpy()
    if len(custom_null_sample) < 2:
        print(f"ERROR: Custom null CSV '{KS_NULL_CSV_PATH}' has < 2 values.")
        sys.exit(1)
    null_sample_for_plot = np.sort(custom_null_sample)
else:
    print(f"ERROR: Unknown KS_NULL_DISTRIBUTION '{KS_NULL_DISTRIBUTION}'.")
    sys.exit(1)


def _ks_max_deviation_point(sample_vals, null_sorted):
    """Return (x, F_group(x), F_null(x)) where |F_group - F_null| is maximal.

    Used purely for plotting — highlights where the KS D statistic is
    realised. Works for any null passed as a sorted array.
    """
    s = np.sort(sample_vals)
    n = len(s)
    # Evaluate both ECDFs on the union of breakpoints.
    grid = np.union1d(s, null_sorted)
    f_group = np.searchsorted(s, grid, side="right") / n
    f_null = np.searchsorted(null_sorted, grid, side="right") / len(null_sorted)
    idx = int(np.argmax(np.abs(f_group - f_null)))
    return float(grid[idx]), float(f_group[idx]), float(f_null[idx])


# Run KS per group
rows = []
max_dev_points = {}  # group -> (x, y_group, y_null) for annotation
for g in groups:
    vals = _grouped.get(g, np.array([], dtype=float))
    n = len(vals)
    if n < 2:
        rows.append({"Group": g, "n": n, "D": np.nan, "p": np.nan,
                     "test": "insufficient_n"})
        continue

    if _null_mode == "uniform":
        # Analytic one-sample test against Uniform(0,1) CDF.
        res = stats.ks_1samp(vals, stats.uniform.cdf,
                             alternative=KS_ALTERNATIVE)
        test_name = "ks_1samp vs Uniform(0,1)"
        null_for_point = null_sample_for_plot  # for plotting only
    elif _null_mode in ("bootstrap_shuffle", "bootstrap"):
        # Null = resample from OTHER groups (exclude g itself).
        pool_others = np.concatenate(
            [arr for gg, arr in _grouped.items() if gg != g]
        ) if len(_grouped) > 1 else _grouped[g]  # degenerate single-group case
        if len(pool_others) < 2:
            rows.append({"Group": g, "n": n, "D": np.nan, "p": np.nan,
                         "test": "insufficient_null_pool"})
            continue
        null_g = rng.choice(pool_others, size=_n_null, replace=True)
        res = stats.ks_2samp(vals, null_g, alternative=KS_ALTERNATIVE)
        test_name = "ks_2samp vs leave-one-group-out bootstrap"
        null_for_point = np.sort(null_g)
    else:  # custom_csv
        res = stats.ks_2samp(vals, custom_null_sample,
                             alternative=KS_ALTERNATIVE)
        test_name = "ks_2samp vs custom null"
        null_for_point = null_sample_for_plot

    rows.append({
        "Group": g, "n": int(n),
        "D": float(res.statistic), "p": float(res.pvalue),
        "test": test_name,
    })
    try:
        max_dev_points[g] = _ks_max_deviation_point(vals, null_for_point)
    except Exception:
        pass

res_df = pd.DataFrame(rows)

# Multiple-comparisons correction
if KS_MULTIPLE_COMPARISONS != "none":
    pvals = res_df["p"].values
    mask = ~np.isnan(pvals)
    m = int(mask.sum())
    padj = np.full_like(pvals, np.nan, dtype=float)
    if m > 0:
        if KS_MULTIPLE_COMPARISONS == "bonferroni":
            padj[mask] = np.clip(pvals[mask] * m, 0, 1)
        elif KS_MULTIPLE_COMPARISONS == "fdr_bh":
            p_sub = pvals[mask]
            order = np.argsort(p_sub)
            ranked = p_sub[order]
            adj = ranked * m / (np.arange(m) + 1)
            # enforce monotonicity
            adj = np.minimum.accumulate(adj[::-1])[::-1]
            adj = np.clip(adj, 0, 1)
            out = np.empty_like(adj)
            out[order] = adj
            padj[mask] = out
    res_df["p_adj"] = padj
    # significant: only mark True when the adjusted p-value is below alpha
    # AND is not NaN (untested groups stay NaN, not False).
    _alpha = float(KS_ALPHA)
    res_df["significant"] = np.where(
        np.isnan(res_df["p_adj"].values), pd.NA,
        res_df["p_adj"].values < _alpha,
    )
else:
    _alpha = float(KS_ALPHA)
    res_df["significant"] = np.where(
        np.isnan(res_df["p"].values), pd.NA,
        res_df["p"].values < _alpha,
    )

csv_path = os.path.join(output_folder, "ks_results.csv")
write_csv_dataframe(csv_path, res_df, index=False)
print(f"[ksTest] wrote {csv_path}")
print(res_df.to_string(index=False))

# ----------------------------------------------------------------------
# ECDF plot
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


_plot_groups = [g for g in groups if len(_grouped.get(g, [])) > 0]
colors = _resolve_palette(KS_PALETTE, max(len(_plot_groups), 1))

fig, ax = plt.subplots(figsize=(float(KS_FIG_WIDTH), float(KS_FIG_HEIGHT)),
                       facecolor=KS_BG_COLOR, constrained_layout=True)

# Reference null ECDF — drawn as a light dashed step curve behind the data.
if _null_mode == "uniform":
    # Exact analytic CDF for Uniform(0,1): y = x.
    ax.plot([0.0, 1.0], [0.0, 1.0],
            color="#555555", linestyle="--", linewidth=1.2,
            label="Null: Uniform(0,1) CDF", zorder=1)
else:
    xs = null_sample_for_plot  # already sorted
    ys = np.arange(1, len(xs) + 1) / len(xs)
    ax.plot(xs, ys, color="#555555", linestyle="--", linewidth=1.2,
            drawstyle="steps-post",
            label=f"Null ({_null_mode}, n={len(xs)})", zorder=1)

# Per-group step ECDFs + max-D markers.
_p_lookup = dict(zip(res_df["Group"], res_df["p"]))
_d_lookup = dict(zip(res_df["Group"], res_df["D"]))

for g, c in zip(_plot_groups, colors):
    vals = np.sort(_grouped[g])
    n = len(vals)
    y = np.arange(1, n + 1) / n
    D = _d_lookup.get(g, np.nan)
    p = _p_lookup.get(g, np.nan)
    lbl = f"{g}  (n={n}, D={D:.3f}, p={p:.3g})" if not np.isnan(D) \
        else f"{g}  (n={n})"
    ax.plot(vals, y, color=c, linewidth=1.8, drawstyle="steps-post",
            label=lbl, zorder=3)

    # Mark the point of maximum deviation.
    pt = max_dev_points.get(g)
    if pt is not None:
        x_d, y_grp, y_null = pt
        ax.vlines(x_d, min(y_grp, y_null), max(y_grp, y_null),
                  color=c, linewidth=1.2, alpha=0.9, zorder=4)
        ax.plot([x_d], [y_grp], marker="o", markersize=5,
                color=c, markeredgecolor="black", markeredgewidth=0.6,
                zorder=5)

ax.set_xlim(0.0, 1.0)
ax.set_ylim(0.0, 1.0)
ax.set_xlabel(r"Rhythm ratio $r_k$", fontsize=11)
ax.set_ylabel("Empirical CDF", fontsize=11)
ax.set_title(KS_TITLE, fontsize=13)
ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.5)
ax.set_axisbelow(True)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)
ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0),
          frameon=False, fontsize=9, borderaxespad=0.0)

save_figure(fig, output_folder, "ks_ecdf_per_group",
            fmt=KS_OUTPUT_FORMAT, dpi=int(KS_DPI))
plt.close(fig)
print("[ksTest] done.")
