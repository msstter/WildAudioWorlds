"""Rhythm Ratios Extractor & Distribution Plot (Category A1).

For each recording in the File Summaries sheet, the Onset Finder has
already computed per-cycle rhythm ratios r_k = i_k / (i_k + i_{k+1})
and exported them into the ``Dyadic Events`` sheet. This script:

1. Loads those r_k values (raw or stable dataset).
2. Assigns each event to a group using the shared 4-mode source.
3. Writes a tidy per-group CSV summary of r_k counts, mean, isochronous
   proportion, etc.
4. Plots per-group + combined histograms of r_k with reference lines at
   standard musical ratios (1:3, 1:2, 1:1, 2:1, 3:1) and a highlighted
   isochronous band.

Outputs land in ``RR_OUTPUT_FOLDER``:
- ``rhythm_ratios_per_group.csv``
- ``rhythm_ratios_hist_<group>.<fmt>`` per group
- ``rhythm_ratios_hist_combined.<fmt>``
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
    assign_groups, ensure_output_folder, get_palette,
    group_assignment_config_from, load_dyadic_events, load_file_summaries,
    order_groups, save_figure, write_csv_dataframe,
)

# ==========================================
# 1. DEFAULT CONFIGURATION
# ==========================================
excel_path = os.path.join(_PROJECT_DIR, "Cross_Species_Rhythm_Data.xlsx")
output_folder = os.path.join(_PROJECT_DIR, "Rhythm_Ratios")

RR_DATASET = "raw"
RR_GROUP_SOURCE = "filename_pattern"
RR_GROUP_PATTERN = r"(?P<group>[A-Za-z]+)_"
RR_GROUP_CSV_PATH = ""
RR_MANUAL_GROUPS: dict = {}
RR_GROUP_EXCEL_COLUMN = "Group"
RR_UNGROUPED_LABEL = "Ungrouped"
RR_GROUP_ORDER = ""

# Step-specific
RR_BIN_COUNT = 40
RR_ISOCHRONOUS_BAND_LOW = 0.45
RR_ISOCHRONOUS_BAND_HIGH = 0.55
RR_REFERENCE_RATIOS = "0.25, 0.333, 0.5, 0.667, 0.75"  # 1:3,1:2,1:1,2:1,3:1
RR_REFERENCE_LABELS = "1:3, 1:2, 1:1, 2:1, 3:1"
RR_OVERLAY_GROUPS = True     # plot all groups on one axes
RR_FACET_PER_GROUP = True    # also save per-group files
RR_NORMALIZE = True          # density vs counts

# Generic plot settings
RR_FIG_WIDTH = 12
RR_FIG_HEIGHT = 6
RR_DPI = 300
RR_PALETTE = "Set2"
RR_TITLE = "Rhythm Ratio (r) Distribution by Group"
RR_X_LABEL = "Rhythm Ratio r = i_k / (i_k + i_{k+1})"
RR_Y_LABEL = "Density"
RR_BG_COLOR = "#ffffff"
RR_HIST_ALPHA = 0.55
RR_REF_COLOR = "#666666"
RR_REF_STYLE = "--"
RR_REF_ALPHA = 0.7
RR_BAND_COLOR = "#ffd54f"
RR_BAND_ALPHA = 0.25
RR_OUTPUT_FORMAT = "png"

# ==========================================
# 2. CONFIG OVERRIDE
# ==========================================
_cfg_path = os.path.join(_PROJECT_DIR, "pipeline_config.json")
if os.path.isfile(_cfg_path):
    with open(_cfg_path) as _f:
        _cfg = json.load(_f).get("rhythm_ratios", {})
    excel_path = _cfg.get("excel_path", excel_path)
    output_folder = _cfg.get("output_folder", output_folder)
    for _k in list(globals().keys()):
        if _k.startswith("RR_") and _k in _cfg:
            globals()[_k] = _cfg[_k]
    del _f, _cfg

ensure_output_folder(output_folder)

# ==========================================
# 3. LOAD DATA
# ==========================================
print(f"[rhythmRatios] Loading {excel_path} ({RR_DATASET} dataset)...")
df_summary = load_file_summaries(excel_path)
df_events = load_dyadic_events(excel_path, dataset=RR_DATASET)

if "File Name" not in df_events.columns:
    print("ERROR: Dyadic Events sheet missing 'File Name' column.")
    sys.exit(1)

# Find the r_k column. The Onset Finder writes "Rhythm Ratio [r_k]";
# older / alternate exports may use other spellings. Exact names first,
# then a substring fallback so future renames don't silently break.
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
    # Substring fallback: first column whose lower-cased name contains "r_k".
    for col in df_events.columns:
        if "r_k" in str(col).lower():
            r_col = col
            break
if r_col is None:
    print("ERROR: Could not locate an r_k column in Dyadic Events sheet.")
    print("Available columns:", list(df_events.columns))
    sys.exit(1)
print(f"[rhythmRatios] using column '{r_col}' for r_k.")

df = df_events[["File Name", r_col]].copy()
df[r_col] = pd.to_numeric(df[r_col], errors="coerce")
# r_k is mathematically bounded on (0, 1). Drop NaN and out-of-range rows
# so both the summary stats and the histograms reflect the same data.
_n_raw = len(df)
df = df.dropna(subset=[r_col])
df = df[(df[r_col] > 0.0) & (df[r_col] < 1.0)]
_n_dropped = _n_raw - len(df)
if _n_dropped:
    print(f"[rhythmRatios] dropped {_n_dropped} NaN / out-of-range r_k rows "
          f"(kept {len(df)}).")
else:
    print(f"[rhythmRatios] {len(df)} rhythm-ratio events loaded.")

# Assign groups (against dyadic events; may reuse summary for excel_column)
_ga = {
    "source": RR_GROUP_SOURCE,
    "pattern": RR_GROUP_PATTERN,
    "csv_path": RR_GROUP_CSV_PATH,
    "manual_map": RR_MANUAL_GROUPS,
    "excel_column": RR_GROUP_EXCEL_COLUMN,
    "ungrouped": RR_UNGROUPED_LABEL,
}
df = assign_groups(df, df_summary=df_summary, **_ga)
groups = order_groups(df, RR_GROUP_ORDER)
print(f"[rhythmRatios] groups: {groups}")

# ==========================================
# 4. PER-GROUP SUMMARY
# ==========================================
_iso_lo = float(RR_ISOCHRONOUS_BAND_LOW)
_iso_hi = float(RR_ISOCHRONOUS_BAND_HIGH)
rows = []
_grouped = {g: sub[r_col].to_numpy() for g, sub in df.groupby("Group", sort=False)}
for g in groups:
    vals = _grouped.get(g, np.array([], dtype=float))
    n = len(vals)
    if n:
        iso_mask = (vals >= _iso_lo) & (vals <= _iso_hi)
        rows.append({
            "Group": g,
            "n_events": n,
            "mean_r": float(np.mean(vals)),
            "median_r": float(np.median(vals)),
            "std_r": float(np.std(vals, ddof=1)) if n > 1 else np.nan,
            "prop_isochronous": float(iso_mask.mean()),
            "isochronous_band": f"[{_iso_lo}, {_iso_hi}]",
        })
    else:
        rows.append({
            "Group": g, "n_events": 0, "mean_r": np.nan, "median_r": np.nan,
            "std_r": np.nan, "prop_isochronous": np.nan,
            "isochronous_band": f"[{_iso_lo}, {_iso_hi}]",
        })
summary_df = pd.DataFrame(rows)
summary_csv = os.path.join(output_folder, "rhythm_ratios_per_group.csv")
write_csv_dataframe(summary_csv, summary_df, index=False)
print(f"[rhythmRatios] wrote {summary_csv}")
print(summary_df.to_string(index=False))

# Groups that actually have data (used below for plotting)
_plot_groups = [g for g in groups if len(_grouped.get(g, [])) > 0]
if not _plot_groups:
    print("[rhythmRatios] no groups contained any r_k events; skipping plots.")
    print("[rhythmRatios] done.")
    sys.exit(0)


# ==========================================
# 5. PLOTS
# ==========================================
def _parse_floats(s):
    # Accept either a Python list (from the GUI) or a comma-separated string.
    if isinstance(s, (list, tuple)):
        out = []
        for tok in s:
            try:
                out.append(float(tok))
            except (ValueError, TypeError):
                pass
        return out
    out = []
    for tok in str(s).split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(float(tok))
        except ValueError:
            pass
    return out


def _parse_strings(s):
    if isinstance(s, (list, tuple)):
        return [str(t).strip() for t in s if str(t).strip()]
    return [t.strip() for t in str(s).split(",") if t.strip()]


# Okabe–Ito colorblind-safe palette — the de-facto standard for
# bioacoustic / behavioral publications.
_OKABE_ITO = ["#0072B2", "#D55E00", "#009E73", "#CC79A7",
              "#F0E442", "#56B4E9", "#E69F00", "#000000"]


def _resolve_palette(palette_str: str, n: int):
    key = str(palette_str).strip().lower()
    if key in {"okabe", "okabe-ito", "okabe_ito", "colorblind", "cb"}:
        pal = list(_OKABE_ITO)
        while len(pal) < n:
            pal.extend(_OKABE_ITO)
        return pal[:n]
    return get_palette(palette_str, n)


ref_vals = _parse_floats(RR_REFERENCE_RATIOS)
ref_labels = _parse_strings(RR_REFERENCE_LABELS)
# Pad labels if caller supplied fewer labels than ratios.
if len(ref_labels) < len(ref_vals):
    ref_labels = ref_labels + [f"{v:.3g}" for v in ref_vals[len(ref_labels):]]

colors = _resolve_palette(RR_PALETTE, len(_plot_groups))

# Shared mathtext x-label.
_X_LABEL_TEX = r"Rhythm ratio $r_k = i_k / (i_k + i_{k+1})$"


def _plot_histogram(ax, vals, color, label, *, filled=True):
    """Draw one group's histogram: soft fill plus a crisp step outline.

    The step outline ensures overlapping distributions remain readable
    even when fills pile up in the overlay plot.
    """
    bins = int(RR_BIN_COUNT)
    rng = (0.0, 1.0)
    if filled:
        ax.hist(vals, bins=bins, range=rng,
                density=bool(RR_NORMALIZE), histtype="stepfilled",
                alpha=float(RR_HIST_ALPHA), color=color,
                edgecolor="none", label=None)
    ax.hist(vals, bins=bins, range=rng,
            density=bool(RR_NORMALIZE), histtype="step",
            color=color, linewidth=1.8, label=label)


def _decorate(ax, title, *, group_means=None):
    # Isochronous band (behind data).
    ax.axvspan(_iso_lo, _iso_hi,
               color=RR_BAND_COLOR, alpha=float(RR_BAND_ALPHA),
               zorder=0, label=f"Isochronous band [{_iso_lo:g}, {_iso_hi:g}]")

    # Reference lines.
    for v in ref_vals:
        ax.axvline(v, color=RR_REF_COLOR, linestyle=RR_REF_STYLE,
                   alpha=float(RR_REF_ALPHA), linewidth=1, zorder=1)

    ax.set_xlim(0.0, 1.0)
    ax.set_xlabel(_X_LABEL_TEX, fontsize=11)
    ax.set_ylabel(RR_Y_LABEL, fontsize=11)
    ax.set_title(title, fontsize=13, pad=18)  # pad leaves room for top labels
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # Place reference-ratio labels ABOVE the axes so they never collide
    # with histogram bars. xycoords=('data','axes fraction') locks x to
    # the reference value and y to a constant fraction above the frame.
    for v, lab in zip(ref_vals, ref_labels):
        ax.annotate(
            lab, xy=(v, 1.0), xycoords=("data", "axes fraction"),
            xytext=(0, 3), textcoords="offset points",
            ha="center", va="bottom",
            fontsize=8, color=RR_REF_COLOR,
        )

    # Optional mean-rug at the bottom of the axes.
    if group_means:
        for mean_val, c in group_means:
            ax.annotate(
                "", xy=(mean_val, 0.0), xycoords=("data", "axes fraction"),
                xytext=(0, -2), textcoords="offset points",
                arrowprops=dict(arrowstyle="-", color=c, lw=2),
            )

    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0),
              frameon=False, fontsize=9, borderaxespad=0.0)


# ---- Combined overlay ------------------------------------------------
if RR_OVERLAY_GROUPS:
    fig, ax = plt.subplots(figsize=(float(RR_FIG_WIDTH), float(RR_FIG_HEIGHT)),
                           facecolor=RR_BG_COLOR, constrained_layout=True)
    means_for_rug = []
    for g, c in zip(_plot_groups, colors):
        vals = _grouped[g]
        mean_r = float(np.mean(vals))
        _plot_histogram(ax, vals, c,
                        f"{g}  (n={len(vals)}, mean r={mean_r:.3f})")
        means_for_rug.append((mean_r, c))
    _decorate(ax, RR_TITLE, group_means=means_for_rug)
    save_figure(fig, output_folder, "rhythm_ratios_hist_combined",
                fmt=RR_OUTPUT_FORMAT, dpi=int(RR_DPI))
    plt.close(fig)

# ---- Per-group facets ------------------------------------------------
if RR_FACET_PER_GROUP:
    # Per-group figures are single-panel — use a modestly smaller width.
    per_w = max(float(RR_FIG_WIDTH) * 0.8, 7.0)
    for g, c in zip(_plot_groups, colors):
        vals = _grouped[g]
        mean_r = float(np.mean(vals))
        fig, ax = plt.subplots(figsize=(per_w, float(RR_FIG_HEIGHT)),
                               facecolor=RR_BG_COLOR,
                               constrained_layout=True)
        _plot_histogram(ax, vals, c,
                        f"{g}  (n={len(vals)}, mean r={mean_r:.3f})")
        _decorate(ax, f"{RR_TITLE} — {g}",
                  group_means=[(mean_r, c)])
        safe = "".join(ch if ch.isalnum() else "_" for ch in g)
        save_figure(fig, output_folder, f"rhythm_ratios_hist_{safe}",
                    fmt=RR_OUTPUT_FORMAT, dpi=int(RR_DPI))
        plt.close(fig)

print("[rhythmRatios] done.")
