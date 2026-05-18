"""Tempo × Rhythm-Ratio heatmap (Category B1).

Builds a 2D density map of (tempo, rhythm ratio r) events. Either
computes tempo per-event from cycle duration or uses a pre-computed
BPM column from the File Summaries sheet.

Outputs:
- Pooled heatmap across all groups.
- Faceted heatmap per group (if ``TRH_FACET_BY_GROUP``).
- ``tempo_ratio_density.csv`` dumping the binned 2D density.
"""

from __future__ import annotations

import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, os.path.join(_PROJECT_DIR, "scripts"))

from group_assignment import (  # noqa: E402
    assign_groups, ensure_output_folder, load_dyadic_events,
    load_file_summaries, order_groups, save_figure,
)

# Defaults
excel_path = os.path.join(_PROJECT_DIR, "Cross_Species_Rhythm_Data.xlsx")
output_folder = os.path.join(_PROJECT_DIR, "Tempo_Ratio_Heatmap")

TRH_DATASET = "raw"
TRH_GROUP_SOURCE = "filename_pattern"
TRH_GROUP_PATTERN = r"(?P<group>[A-Za-z]+)_"
TRH_GROUP_CSV_PATH = ""
TRH_MANUAL_GROUPS: dict = {}
TRH_GROUP_EXCEL_COLUMN = "Group"
TRH_UNGROUPED_LABEL = "Ungrouped"
TRH_GROUP_ORDER = ""

# Step-specific
TRH_X_AXIS = "BPM"                # "BPM" | "cycle_duration_ms"
TRH_TEMPO_FROM = "ioi"             # "ioi" => BPM = 60000 / mean_IOI
                                    #        = 120000 / cycle_duration_ms
                                    # "cycle" => BPM = 60000 / cycle_duration_ms
                                    #        (legacy; half the Roeske tempo)
TRH_X_BINS = 40
TRH_Y_BINS = 40
TRH_X_RANGE_MIN = 40.0
TRH_X_RANGE_MAX = 240.0
TRH_KDE_MODE = "2d_histogram"     # "2d_histogram" | "gaussian_kde"
TRH_KDE_BANDWIDTH = 0.3
TRH_LOG_X = False
TRH_NORMALIZE = "per_group"        # "per_group" | "joint" | "none"
TRH_COLORMAP = "magma"
TRH_REFERENCE_RATIOS = "0.25, 0.333, 0.5, 0.667, 0.75"
TRH_REFERENCE_LABELS = "1:3, 1:2, 1:1, 2:1, 3:1"
TRH_FACET_BY_GROUP = True
TRH_MIN_EVENTS_PER_PANEL = 10      # min points required for a panel

# Generic plot settings
TRH_FIG_WIDTH = 10
TRH_FIG_HEIGHT = 6
TRH_DPI = 300
TRH_TITLE = "Tempo × Rhythm-Ratio Density"
TRH_BG_COLOR = "#ffffff"
TRH_OUTPUT_FORMAT = "png"

_cfg_path = os.path.join(_PROJECT_DIR, "pipeline_config.json")
if os.path.isfile(_cfg_path):
    with open(_cfg_path) as _f:
        _cfg = json.load(_f).get("tempo_ratio_heatmap", {})
    excel_path = _cfg.get("excel_path", excel_path)
    output_folder = _cfg.get("output_folder", output_folder)
    for _k in list(globals().keys()):
        if _k.startswith("TRH_") and _k in _cfg:
            globals()[_k] = _cfg[_k]
    del _f, _cfg

ensure_output_folder(output_folder)

# Load data
print(f"[tempoRatioHeatmap] Loading {excel_path} ({TRH_DATASET} dataset)...")
df_summary = load_file_summaries(excel_path)
df_events = load_dyadic_events(excel_path, dataset=TRH_DATASET)

r_col = next((c for c in ("Rhythm Ratio [r_k]", "Rhythm Ratio (r_k)",
                          "r_k", "r (Rhythm Ratio)", "Rhythm Ratio", "r")
              if c in df_events.columns), None)
if r_col is None:
    r_col = next((c for c in df_events.columns
                  if "r_k" in str(c).lower()), None)
if r_col is None:
    print("ERROR: r_k column not found.")
    print("Available columns:", list(df_events.columns))
    sys.exit(1)
print(f"[tempoRatioHeatmap] using r_k column: '{r_col}'")

# Get cycle duration (Onset Finder writes "Cycle Duration [cd] (ms)").
cycle_col = next((c for c in ("Cycle Duration [cd] (ms)",
                              "Cycle Duration (ms)", "Cycle Duration",
                              "cycle_duration", "cycle_duration_ms")
                  if c in df_events.columns), None)
if cycle_col is None:
    cycle_col = next((c for c in df_events.columns
                      if "cycle duration" in str(c).lower()), None)
if cycle_col is None:
    print("ERROR: Cycle duration column not found in Dyadic Events sheet.")
    print("Available columns:", list(df_events.columns))
    sys.exit(1)
print(f"[tempoRatioHeatmap] using cycle-duration column: '{cycle_col}'")

df = df_events[["File Name", r_col, cycle_col]].copy()
df[r_col] = pd.to_numeric(df[r_col], errors="coerce")
df[cycle_col] = pd.to_numeric(df[cycle_col], errors="coerce")
df = df.dropna(subset=[r_col, cycle_col])
# r_k is bounded (0, 1).
df = df[(df[r_col] > 0.0) & (df[r_col] < 1.0)]

# Build X axis.
# A "cycle" in the Onset Finder spans TWO IOIs (cd = i_k + i_{k+1}),
# so the instantaneous beat period is cd / 2, i.e.
#     BPM_pulse = 60000 / (cd/2) = 120000 / cd
# (TRH_TEMPO_FROM="ioi", matches Roeske 2020 and follow-ups).
# TRH_TEMPO_FROM="cycle" is the legacy formula = half the pulse tempo.
if TRH_X_AXIS == "BPM":
    cd = df[cycle_col].replace(0, np.nan)
    if str(TRH_TEMPO_FROM).strip().lower() == "cycle":
        df["_x"] = 60000.0 / cd
        print("[tempoRatioHeatmap] BPM = 60000 / cycle_duration "
              "(legacy 'cycle' mode — half the pulse tempo).")
    else:
        df["_x"] = 120000.0 / cd
        print("[tempoRatioHeatmap] BPM = 120000 / cycle_duration "
              "(Roeske convention: pulse tempo from mean IOI).")
    x_label = "Tempo (BPM)"
else:
    df["_x"] = df[cycle_col]
    x_label = "Cycle duration (ms)"

df = df.dropna(subset=["_x"])
df = df[(df["_x"] >= float(TRH_X_RANGE_MIN)) & (df["_x"] <= float(TRH_X_RANGE_MAX))]

df = assign_groups(
    df, source=TRH_GROUP_SOURCE, pattern=TRH_GROUP_PATTERN,
    csv_path=TRH_GROUP_CSV_PATH, manual_map=TRH_MANUAL_GROUPS,
    ungrouped=TRH_UNGROUPED_LABEL, excel_column=TRH_GROUP_EXCEL_COLUMN,
    df_summary=df_summary)
groups = order_groups(df, TRH_GROUP_ORDER)


def _build_density(xs, ys, x_range, y_range, xbins, ybins, mode, bw):
    """Return (xi, yi, Z, used_mode).

    Always falls back to 2d_histogram when gaussian_kde would be ill-defined
    (too few points, collinear data, etc.).
    """
    n = len(xs)
    if mode == "gaussian_kde" and n >= max(10, int(TRH_MIN_EVENTS_PER_PANEL)):
        try:
            from scipy.stats import gaussian_kde
            xy = np.vstack([xs, ys])
            kde = gaussian_kde(xy, bw_method=bw)
            xi = np.linspace(*x_range, xbins)
            yi = np.linspace(*y_range, ybins)
            XI, YI = np.meshgrid(xi, yi)
            Z = kde(np.vstack([XI.ravel(), YI.ravel()])).reshape(XI.shape)
            return xi, yi, Z, "gaussian_kde"
        except (np.linalg.LinAlgError, ValueError):
            pass  # fall through to histogram
    H, xe, ye = np.histogram2d(
        xs, ys, bins=[xbins, ybins], range=[x_range, y_range])
    xi = (xe[:-1] + xe[1:]) / 2
    yi = (ye[:-1] + ye[1:]) / 2
    return xi, yi, H.T, "2d_histogram"


def _plot_density(xi, yi, Z, title, outstem, ref_ratios, ref_labels,
                  used_mode, n_events, vmax=None):
    fig, ax = plt.subplots(figsize=(TRH_FIG_WIDTH, TRH_FIG_HEIGHT),
                           facecolor=TRH_BG_COLOR, constrained_layout=True)
    extent = [xi.min(), xi.max(), yi.min(), yi.max()]
    # Normalize:
    #   "per_group": each panel scaled so its own values sum to 1
    #   "joint":     no per-panel rescaling (caller passes shared vmax)
    #   "none":      raw counts/density
    if TRH_NORMALIZE == "per_group" and Z.sum() > 0:
        Z = Z / Z.sum()
    interp = "bilinear" if used_mode == "gaussian_kde" else "nearest"
    im = ax.imshow(Z, extent=extent, origin="lower", aspect="auto",
                   cmap=TRH_COLORMAP, interpolation=interp,
                   vmin=0, vmax=vmax)
    cb_label = ("Relative density" if TRH_NORMALIZE == "per_group"
                else ("Density" if used_mode == "gaussian_kde" else "Count"))
    fig.colorbar(im, ax=ax, label=cb_label)
    for v, lab in zip(ref_ratios, ref_labels):
        ax.axhline(v, color="#ffffff", linestyle="--",
                   alpha=0.75, linewidth=1.0)
        ax.text(1.005, v, lab, transform=ax.get_yaxis_transform(),
                va="center", ha="left", fontsize=8, color="#333333",
                clip_on=False)
    if TRH_LOG_X:
        ax.set_xscale("log")
    ax.set_xlabel(x_label)
    ax.set_ylabel(r"Rhythm ratio  $r_k$")
    ax.set_title(f"{title}\nn = {n_events} events  ·  {used_mode}",
                 fontsize=11)
    ax.set_ylim(0.0, 1.0)
    save_figure(fig, output_folder, outstem,
                fmt=TRH_OUTPUT_FORMAT, dpi=int(TRH_DPI))
    plt.close(fig)


def _parse_ref_ratios(val):
    """Accept list (from GUI) or comma-separated string."""
    if isinstance(val, (list, tuple)):
        out = []
        for t in val:
            try:
                out.append(float(t))
            except (ValueError, TypeError):
                pass
        return out
    return [float(t) for t in str(val).split(",") if t.strip()]


def _parse_ref_labels(val, ratios):
    if isinstance(val, (list, tuple)):
        labels = [str(t) for t in val]
    else:
        labels = [t.strip() for t in str(val).split(",") if t.strip()]
    # Pad / truncate to match ratio count.
    if len(labels) < len(ratios):
        labels = labels + [f"{r:.3f}" for r in ratios[len(labels):]]
    return labels[: len(ratios)]


ref = _parse_ref_ratios(TRH_REFERENCE_RATIOS)
ref_lab = _parse_ref_labels(TRH_REFERENCE_LABELS, ref)

x_range = (float(TRH_X_RANGE_MIN), float(TRH_X_RANGE_MAX))
y_range = (0.0, 1.0)

# Pooled density
xi, yi, Z_pool, pool_mode = _build_density(
    df["_x"].to_numpy(), df[r_col].to_numpy(),
    x_range, y_range,
    int(TRH_X_BINS), int(TRH_Y_BINS), TRH_KDE_MODE, float(TRH_KDE_BANDWIDTH))

# Per-group densities (for faceting + joint vmax)
group_densities = {}
if TRH_FACET_BY_GROUP:
    for g in groups:
        sub = df[df["Group"] == g]
        if len(sub) < int(TRH_MIN_EVENTS_PER_PANEL):
            print(f"[tempoRatioHeatmap] skipping group '{g}' "
                  f"(n={len(sub)} < {TRH_MIN_EVENTS_PER_PANEL}).")
            continue
        xi_g, yi_g, Z_g, mode_g = _build_density(
            sub["_x"].to_numpy(), sub[r_col].to_numpy(),
            x_range, y_range,
            int(TRH_X_BINS), int(TRH_Y_BINS),
            TRH_KDE_MODE, float(TRH_KDE_BANDWIDTH))
        group_densities[g] = (xi_g, yi_g, Z_g, mode_g, len(sub))

joint_vmax = None
if TRH_NORMALIZE == "joint":
    all_max = [Z_pool.max()] + [Z.max() for (_, _, Z, _, _) in group_densities.values()]
    joint_vmax = max(all_max) if all_max else None

_plot_density(xi, yi, Z_pool, f"{TRH_TITLE} — all groups",
              "tempo_ratio_heatmap_pooled", ref, ref_lab,
              pool_mode, len(df), vmax=joint_vmax)

# Dump the pooled density CSV
pool_out = pd.DataFrame(Z_pool, index=[f"r_bin_{v:.3f}" for v in yi],
                         columns=[f"x_bin_{v:.2f}" for v in xi])
pool_out.to_csv(os.path.join(output_folder, "tempo_ratio_density.csv"))

if TRH_FACET_BY_GROUP:
    for g, (xi_g, yi_g, Z_g, mode_g, n_g) in group_densities.items():
        safe = "".join(ch if ch.isalnum() else "_" for ch in g)
        _plot_density(xi_g, yi_g, Z_g, f"{TRH_TITLE} — {g}",
                      f"tempo_ratio_heatmap_{safe}", ref, ref_lab,
                      mode_g, n_g, vmax=joint_vmax)

print("[tempoRatioHeatmap] done.")
