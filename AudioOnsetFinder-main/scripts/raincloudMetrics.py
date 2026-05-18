"""Raincloud plots for arbitrary rhythmic metrics (Category B2).

Generalises ``nPVI_byGroup.py`` to any set of per-file numeric columns
from the File Summaries sheet (nPVI, entropy, CV, mean IOI, …).
Per-metric raincloud = half-violin + boxplot + jittered points.

Supports optional pairwise across-group tests (Mann-Whitney, Wilcoxon,
or KS) with multiple-comparison correction and significance-bracket
overlays.

Outputs:
- ``raincloud_<metric>.<fmt>`` per metric (or a grid if requested)
- ``raincloud_stats.csv`` with per-pair p-values (if enabled)
"""

from __future__ import annotations

import json
import os
import sys
from itertools import combinations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, os.path.join(_PROJECT_DIR, "scripts"))

from group_assignment import (  # noqa: E402
    assign_groups, ensure_output_folder, get_palette, load_file_summaries,
    order_groups, pick_rhythm_column, save_figure,
)

# Defaults
excel_path = os.path.join(_PROJECT_DIR, "Cross_Species_Rhythm_Data.xlsx")
output_folder = os.path.join(_PROJECT_DIR, "Raincloud_Metrics")

RC_DATASET = "raw"
RC_GROUP_SOURCE = "filename_pattern"
RC_GROUP_PATTERN = r"(?P<group>[A-Za-z]+)_"
RC_GROUP_CSV_PATH = ""
RC_MANUAL_GROUPS: dict = {}
RC_GROUP_EXCEL_COLUMN = "Group"
RC_UNGROUPED_LABEL = "Ungrouped"
RC_GROUP_ORDER = ""

# Step-specific
RC_METRICS = [
    "nPVI (Isochrony)",
    "r_k Entropy (Categorical Measure)",
    "CV of Intervals",
    "Mean IOI (ms)",
]
RC_ONE_FIG_PER_METRIC = True
RC_ORIENTATION = "vertical"        # "vertical" | "horizontal"
RC_SHOW_N_PER_GROUP = True
RC_PAIRWISE_STATS = "none"        # "none" | "mannwhitney" | "wilcoxon" | "ks"
RC_STATS_CORRECTION = "none"      # "none" | "bonferroni" | "fdr_bh"
RC_STATS_ALPHA = 0.05

# Generic plot settings
RC_FIG_WIDTH = 12
RC_FIG_HEIGHT = 6
RC_DPI = 300
RC_PALETTE = "okabe-ito"
RC_BG_COLOR = "#ffffff"
RC_VIOLIN_ALPHA = 0.6
RC_BOX_WIDTH = 0.15
RC_BOX_ALPHA = 0.5
RC_JITTER_SIZE = 14
RC_JITTER_ALPHA = 0.7
RC_JITTER_WIDTH = 0.12
RC_OUTPUT_FORMAT = "png"

_cfg_path = os.path.join(_PROJECT_DIR, "pipeline_config.json")
if os.path.isfile(_cfg_path):
    with open(_cfg_path) as _f:
        _cfg = json.load(_f).get("raincloud_metrics", {})
    excel_path = _cfg.get("excel_path", excel_path)
    output_folder = _cfg.get("output_folder", output_folder)
    for _k in list(globals().keys()):
        if _k.startswith("RC_") and _k in _cfg:
            globals()[_k] = _cfg[_k]
    del _f, _cfg

ensure_output_folder(output_folder)

# Load & group
print(f"[raincloudMetrics] Loading {excel_path} ({RC_DATASET} dataset)...")
df_summary = load_file_summaries(excel_path)
df = df_summary.copy()
df = assign_groups(
    df, source=RC_GROUP_SOURCE, pattern=RC_GROUP_PATTERN,
    csv_path=RC_GROUP_CSV_PATH, manual_map=RC_MANUAL_GROUPS,
    ungrouped=RC_UNGROUPED_LABEL, excel_column=RC_GROUP_EXCEL_COLUMN,
    df_summary=df_summary)
groups = order_groups(df, RC_GROUP_ORDER)

# Swap metrics if stable
metrics = [pick_rhythm_column(m, RC_DATASET) for m in RC_METRICS]
metrics = [m for m in metrics if m in df.columns]
if not metrics:
    print("ERROR: No requested metrics found as columns in File Summaries.")
    sys.exit(1)

colors = get_palette(RC_PALETTE, len(groups))


def _half_violin(ax, data, position, color, width=0.6, alpha=0.6, orient="vertical"):
    if len(data) < 2 or np.nanstd(data) <= 0:
        return
    try:
        kde = stats.gaussian_kde(data)
    except (np.linalg.LinAlgError, ValueError):
        return
    lo, hi = float(np.min(data)), float(np.max(data))
    span = max(hi - lo, 1e-6)
    grid = np.linspace(lo - 0.05 * span, hi + 0.05 * span, 120)
    dens = kde(grid)
    dens /= dens.max()
    dens *= width
    if orient == "vertical":
        ax.fill_betweenx(grid, position, position + dens,
                         color=color, alpha=alpha, zorder=1)
    else:
        ax.fill_between(grid, position, position + dens,
                        color=color, alpha=alpha, zorder=1)


def _box(ax, data, position, color, width=0.15, alpha=0.5, orient="vertical"):
    vert = orient == "vertical"
    bp = ax.boxplot([data], positions=[position - width],
                    widths=width * 0.9, patch_artist=True,
                    vert=vert, showfliers=False)
    for patch in bp["boxes"]:
        patch.set_facecolor(color)
        patch.set_alpha(alpha)


def _jitter(ax, data, position, color, rng, orient="vertical"):
    if len(data) == 0:
        return
    jit = rng.normal(0, float(RC_JITTER_WIDTH), size=len(data))
    pos = np.full_like(data, position - 2 * float(RC_JITTER_WIDTH)) + jit
    if orient == "vertical":
        ax.scatter(pos, data, s=float(RC_JITTER_SIZE),
                   color=color, edgecolor="black",
                   alpha=float(RC_JITTER_ALPHA), zorder=3)
    else:
        ax.scatter(data, pos, s=float(RC_JITTER_SIZE),
                   color=color, edgecolor="black",
                   alpha=float(RC_JITTER_ALPHA), zorder=3)


def _sig_stars(p: float) -> str:
    if not np.isfinite(p):
        return "ns"
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


def _pairwise(ax, positions, per_g, groups, metric_name):
    rows = []
    if RC_PAIRWISE_STATS == "none":
        return rows
    pairs = list(combinations(range(len(groups)), 2))
    pvals = []
    for i, j in pairs:
        a, b = per_g[i], per_g[j]
        if len(a) < 2 or len(b) < 2:
            pvals.append(np.nan)
            continue
        if RC_PAIRWISE_STATS == "mannwhitney":
            p = stats.mannwhitneyu(a, b, alternative="two-sided").pvalue
        elif RC_PAIRWISE_STATS == "wilcoxon":
            # Paired Wilcoxon signed-rank requires matched pairs of equal length.
            # Across-group File Summaries are NOT paired, so the test is only
            # statistically meaningful when both groups have identical n AND a
            # genuine pairing exists. We refuse otherwise.
            if len(a) != len(b):
                print(f"[raincloudMetrics] WARNING: pairwise 'wilcoxon' requires equal-length"
                      f" matched groups; skipping {metric_name}: groups have n={len(a)} vs n={len(b)}."
                      " Use 'mannwhitney' for unpaired comparisons.")
                p = np.nan
            else:
                p = stats.wilcoxon(a, b).pvalue
        elif RC_PAIRWISE_STATS == "ks":
            p = stats.ks_2samp(a, b).pvalue
        else:
            p = np.nan
        pvals.append(float(p))

    # Correction
    pvals_arr = np.array(pvals)
    mask = ~np.isnan(pvals_arr)
    padj = pvals_arr.copy()
    m = int(mask.sum())
    if RC_STATS_CORRECTION == "bonferroni" and m > 0:
        padj[mask] = np.clip(pvals_arr[mask] * m, 0, 1)
    elif RC_STATS_CORRECTION == "fdr_bh" and m > 0:
        p_sub = pvals_arr[mask]
        order = np.argsort(p_sub)
        ranked = p_sub[order]
        adj = ranked * m / (np.arange(m) + 1)
        adj = np.minimum.accumulate(adj[::-1])[::-1]
        adj = np.clip(adj, 0, 1)
        out = np.empty_like(adj)
        out[order] = adj
        padj[mask] = out

    for (i, j), p, padj_ij in zip(pairs, pvals, padj):
        rows.append({
            "metric": metric_name,
            "group_a": groups[i],
            "group_b": groups[j],
            "test": RC_PAIRWISE_STATS,
            "p": p,
            "p_adj": float(padj_ij) if not np.isnan(padj_ij) else np.nan,
            "significant": (padj_ij if not np.isnan(padj_ij) else p) < float(RC_STATS_ALPHA)
            if not np.isnan(p) else False,
        })

    # Bracket overlay on the plot
    try:
        all_vals = np.concatenate([g for g in per_g if len(g) > 0])
        if len(all_vals) == 0:
            return rows
        y0 = all_vals.max()
        step = 0.05 * (all_vals.max() - all_vals.min() + 1e-6)
        counter = 0
        for (i, j), row in zip(pairs, rows[-len(pairs):]):
            if not row["significant"]:
                continue
            y = y0 + (counter + 1) * step
            counter += 1
            ax.plot([positions[i], positions[i], positions[j], positions[j]],
                    [y, y + step * 0.4, y + step * 0.4, y],
                    color="black", linewidth=0.7)
            p_use = row["p_adj"] if not np.isnan(row["p_adj"]) else row["p"]
            star = _sig_stars(p_use)
            ax.text((positions[i] + positions[j]) / 2, y + step * 0.4,
                    f"{star}\n(p={p_use:.2g})",
                    ha="center", va="bottom", fontsize=8, linespacing=0.9)
    except Exception:
        pass

    return rows


rng = np.random.default_rng(42)
stats_rows: list[dict] = []

for metric in metrics:
    per_g = [pd.to_numeric(df[df["Group"] == g][metric], errors="coerce")
             .dropna().values for g in groups]
    fig, ax = plt.subplots(figsize=(RC_FIG_WIDTH, RC_FIG_HEIGHT),
                           facecolor=RC_BG_COLOR, constrained_layout=True)
    positions = np.arange(1, len(groups) + 1, dtype=float)
    for pos, data, color in zip(positions, per_g, colors):
        if len(data) == 0:
            continue
        _half_violin(ax, data, pos, color,
                     width=0.6, alpha=float(RC_VIOLIN_ALPHA),
                     orient=RC_ORIENTATION)
        _box(ax, data, pos, color,
             width=float(RC_BOX_WIDTH),
             alpha=float(RC_BOX_ALPHA), orient=RC_ORIENTATION)
        _jitter(ax, data, pos, color, rng, orient=RC_ORIENTATION)
    # Axis formatting
    counts = [len(d) for d in per_g]
    if RC_SHOW_N_PER_GROUP:
        tick_labels = [f"{g}\n(n={n})" for g, n in zip(groups, counts)]
    else:
        tick_labels = list(groups)
    if RC_ORIENTATION == "vertical":
        ax.set_xticks(positions)
        ax.set_xticklabels(tick_labels, rotation=0)
        ax.set_ylabel(metric)
        ax.set_xlim(0.3, len(groups) + 0.7)
    else:
        ax.set_yticks(positions)
        ax.set_yticklabels(tick_labels)
        ax.set_xlabel(metric)
        ax.set_ylim(0.3, len(groups) + 0.7)
    ax.set_title(f"{metric} by Group ({RC_DATASET})")
    ax.grid(True, axis="y" if RC_ORIENTATION == "vertical" else "x",
            linestyle=":", alpha=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    stats_rows.extend(_pairwise(ax, positions, per_g, groups, metric))

    safe = "".join(ch if ch.isalnum() else "_" for ch in metric)
    save_figure(fig, output_folder, f"raincloud_{safe}",
                fmt=RC_OUTPUT_FORMAT, dpi=int(RC_DPI))
    plt.close(fig)

if stats_rows:
    pd.DataFrame(stats_rows).to_csv(
        os.path.join(output_folder, "raincloud_stats.csv"), index=False)

print(f"[raincloudMetrics] Done — wrote {len(metrics)} figure(s) to {output_folder}")
