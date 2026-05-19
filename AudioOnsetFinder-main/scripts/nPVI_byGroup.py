"""Generate nPVI-by-group raincloud plots from the extractor output.

This script reads the Excel workbook created by ``onset_finder.py`` and builds
per-group raincloud plots (half-violin + boxplot + jitter) of the normalised
Pairwise Variability Index (nPVI), inspired by Eleuteri et al. (2025).

Groups can be defined in four ways (selected via ``GROUP_SOURCE``):

1. **"filename_pattern"** — derive the group label from each file name using
   a regex with a named capture group ``(?P<group>…)``.  E.g.
   ``r"(?P<group>[A-Za-z]+)_"`` pulls the leading word before the first
   underscore.

2. **"mapping_csv"** — load an external CSV that maps ``File Name`` → ``Group``.

3. **"manual"** — use the ``MANUAL_GROUPS`` dict (file name → group string).

4. **"excel_column"** — read group labels directly from a column in the
   ``File Summaries`` sheet of the input Excel workbook.

Current role in the pipeline:
- Input:  ``Cross_Species_Rhythm_Data.xlsx``
- Output: PNG/SVG/PDF plots in ``nPVI_Group_Plots/``
"""

import json
import os
import re
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ==========================================
# 1. CONFIGURATION
# ==========================================
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, os.path.join(_PROJECT_DIR, "scripts"))
try:
    from group_assignment import merge_file_demographics as _ga_merge_demographics  # noqa: E402
except Exception:
    _ga_merge_demographics = None
try:
    from .shared_output_writers import save_matplotlib_figure
except ImportError:
    from shared_output_writers import save_matplotlib_figure
excel_path = os.path.join(_PROJECT_DIR, "Cross_Species_Rhythm_Data.xlsx")
output_folder = os.path.join(_PROJECT_DIR, "nPVI_Group_Plots")

# --- Group assignment ---
GROUP_SOURCE = "filename_pattern"  # "filename_pattern", "mapping_csv", "manual", or "excel_column"
GROUP_PATTERN = r"(?P<group>[A-Za-z]+)_"  # used when GROUP_SOURCE == "filename_pattern"
GROUP_CSV_PATH = ""  # CSV with 'File Name' and 'Group' columns
MANUAL_GROUPS = {}  # {"file1.wav": "Group A", ...}
GROUP_EXCEL_COLUMN = "Group"  # column name in File Summaries when GROUP_SOURCE == "excel_column"
UNGROUPED_LABEL = "Ungrouped"  # label for files that don't match

# --- Dataset selection ---
NPVI_DATASET = "raw"  # "raw" or "stable"

# --- Figure dimensions ---
NPVI_FIG_WIDTH = 14
NPVI_FIG_HEIGHT = 8
NPVI_DPI = 300
NPVI_TIGHT_PAD = 1.5
NPVI_BG_COLOR = "#ffffff"

# --- Raincloud appearance ---
NPVI_VIOLIN_ALPHA = 0.6
NPVI_VIOLIN_COLOR = ""  # empty = auto per group
NPVI_VIOLIN_WIDTH = 0.6
NPVI_VIOLIN_BANDWIDTH = 0.7
NPVI_BOX_WIDTH = 0.15
NPVI_BOX_ALPHA = 0.5
NPVI_JITTER_SIZE = 12
NPVI_JITTER_ALPHA = 0.7
NPVI_JITTER_WIDTH = 0.12
NPVI_JITTER_COLOR = "#333333"
NPVI_PALETTE = "Set2"  # matplotlib colormap or comma-separated hex

# --- Labels & text ---
NPVI_TITLE = "nPVI by Group"
NPVI_TITLE_FONTSIZE = 16
NPVI_TITLE_PAD = 14
NPVI_TITLE_COLOR = "#000000"
NPVI_X_LABEL = ""
NPVI_Y_LABEL = "nPVI"
NPVI_AXIS_FONTSIZE = 13
NPVI_LABEL_PAD = 10
NPVI_TICK_FONTSIZE = 11
NPVI_AXIS_COLOR = "#000000"
NPVI_TICK_COLOR = "#000000"

# --- Stats overlay ---
NPVI_SHOW_STATS = True
NPVI_STATS_FONTSIZE = 9

# --- Group ordering ---
NPVI_GROUP_ORDER = ""  # comma-separated group names in display order; empty = alphabetical

# --- Reference lines ---
NPVI_REF_LINES = False
NPVI_REF_VALUES = "30, 50"
NPVI_REF_LABELS = "Regular, Irregular"
NPVI_REF_COLOR = "#ff0000"
NPVI_REF_STYLE = "--"
NPVI_REF_WIDTH = 0.9
NPVI_REF_ALPHA = 0.5

# --- Output format ---
NPVI_OUTPUT_FORMAT = "png"  # "png", "svg", "pdf", or "png+svg"

# ------------------------------------------------------------------
# GUI CONFIG OVERRIDE
# ------------------------------------------------------------------
_config_path = os.path.join(_PROJECT_DIR, "pipeline_config.json")
if os.path.isfile(_config_path):
    with open(_config_path) as _f:
        _cfg = json.load(_f).get("npvi_group_generator", {})
    excel_path = _cfg.get("excel_path", excel_path)
    output_folder = _cfg.get("output_folder", output_folder)
    GROUP_SOURCE = _cfg.get("NPVI_GROUP_SOURCE", GROUP_SOURCE)
    GROUP_PATTERN = _cfg.get("NPVI_GROUP_PATTERN", GROUP_PATTERN)
    GROUP_CSV_PATH = _cfg.get("NPVI_GROUP_CSV_PATH", GROUP_CSV_PATH)
    MANUAL_GROUPS = _cfg.get("NPVI_MANUAL_GROUPS", MANUAL_GROUPS)
    GROUP_EXCEL_COLUMN = _cfg.get("NPVI_GROUP_EXCEL_COLUMN", GROUP_EXCEL_COLUMN)
    UNGROUPED_LABEL = _cfg.get("NPVI_UNGROUPED_LABEL", UNGROUPED_LABEL)
    NPVI_DATASET = _cfg.get("NPVI_DATASET", NPVI_DATASET)
    NPVI_FIG_WIDTH = _cfg.get("NPVI_FIG_WIDTH", NPVI_FIG_WIDTH)
    NPVI_FIG_HEIGHT = _cfg.get("NPVI_FIG_HEIGHT", NPVI_FIG_HEIGHT)
    NPVI_DPI = _cfg.get("NPVI_DPI", NPVI_DPI)
    NPVI_TIGHT_PAD = _cfg.get("NPVI_TIGHT_PAD", NPVI_TIGHT_PAD)
    NPVI_BG_COLOR = _cfg.get("NPVI_BG_COLOR", NPVI_BG_COLOR)
    NPVI_VIOLIN_ALPHA = _cfg.get("NPVI_VIOLIN_ALPHA", NPVI_VIOLIN_ALPHA)
    NPVI_VIOLIN_COLOR = _cfg.get("NPVI_VIOLIN_COLOR", NPVI_VIOLIN_COLOR)
    NPVI_VIOLIN_WIDTH = _cfg.get("NPVI_VIOLIN_WIDTH", NPVI_VIOLIN_WIDTH)
    NPVI_VIOLIN_BANDWIDTH = _cfg.get("NPVI_VIOLIN_BANDWIDTH", NPVI_VIOLIN_BANDWIDTH)
    NPVI_BOX_WIDTH = _cfg.get("NPVI_BOX_WIDTH", NPVI_BOX_WIDTH)
    NPVI_BOX_ALPHA = _cfg.get("NPVI_BOX_ALPHA", NPVI_BOX_ALPHA)
    NPVI_JITTER_SIZE = _cfg.get("NPVI_JITTER_SIZE", NPVI_JITTER_SIZE)
    NPVI_JITTER_ALPHA = _cfg.get("NPVI_JITTER_ALPHA", NPVI_JITTER_ALPHA)
    NPVI_JITTER_WIDTH = _cfg.get("NPVI_JITTER_WIDTH", NPVI_JITTER_WIDTH)
    NPVI_JITTER_COLOR = _cfg.get("NPVI_JITTER_COLOR", NPVI_JITTER_COLOR)
    NPVI_PALETTE = _cfg.get("NPVI_PALETTE", NPVI_PALETTE)
    NPVI_TITLE = _cfg.get("NPVI_TITLE", NPVI_TITLE)
    NPVI_TITLE_FONTSIZE = _cfg.get("NPVI_TITLE_FONTSIZE", NPVI_TITLE_FONTSIZE)
    NPVI_TITLE_PAD = _cfg.get("NPVI_TITLE_PAD", NPVI_TITLE_PAD)
    NPVI_TITLE_COLOR = _cfg.get("NPVI_TITLE_COLOR", NPVI_TITLE_COLOR)
    NPVI_X_LABEL = _cfg.get("NPVI_X_LABEL", NPVI_X_LABEL)
    NPVI_Y_LABEL = _cfg.get("NPVI_Y_LABEL", NPVI_Y_LABEL)
    NPVI_AXIS_FONTSIZE = _cfg.get("NPVI_AXIS_FONTSIZE", NPVI_AXIS_FONTSIZE)
    NPVI_LABEL_PAD = _cfg.get("NPVI_LABEL_PAD", NPVI_LABEL_PAD)
    NPVI_TICK_FONTSIZE = _cfg.get("NPVI_TICK_FONTSIZE", NPVI_TICK_FONTSIZE)
    NPVI_AXIS_COLOR = _cfg.get("NPVI_AXIS_COLOR", NPVI_AXIS_COLOR)
    NPVI_TICK_COLOR = _cfg.get("NPVI_TICK_COLOR", NPVI_TICK_COLOR)
    NPVI_SHOW_STATS = _cfg.get("NPVI_SHOW_STATS", NPVI_SHOW_STATS)
    NPVI_STATS_FONTSIZE = _cfg.get("NPVI_STATS_FONTSIZE", NPVI_STATS_FONTSIZE)
    NPVI_GROUP_ORDER = _cfg.get("NPVI_GROUP_ORDER", NPVI_GROUP_ORDER)
    NPVI_REF_LINES = _cfg.get("NPVI_REF_LINES", NPVI_REF_LINES)
    NPVI_REF_VALUES = _cfg.get("NPVI_REF_VALUES", NPVI_REF_VALUES)
    NPVI_REF_LABELS = _cfg.get("NPVI_REF_LABELS", NPVI_REF_LABELS)
    NPVI_REF_COLOR = _cfg.get("NPVI_REF_COLOR", NPVI_REF_COLOR)
    NPVI_REF_STYLE = _cfg.get("NPVI_REF_STYLE", NPVI_REF_STYLE)
    NPVI_REF_WIDTH = _cfg.get("NPVI_REF_WIDTH", NPVI_REF_WIDTH)
    NPVI_REF_ALPHA = _cfg.get("NPVI_REF_ALPHA", NPVI_REF_ALPHA)
    NPVI_OUTPUT_FORMAT = _cfg.get("NPVI_OUTPUT_FORMAT", NPVI_OUTPUT_FORMAT)
    del _f, _cfg

if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# ==========================================
# 2. LOAD DATA
# ==========================================
print("Loading data from Excel...")
if not os.path.isfile(excel_path):
    print(f"ERROR: Excel workbook not found: {excel_path}")
    print("Run the Onset Finder (Step 2) first to generate the workbook.")
    sys.exit(1)

df_summary = pd.read_excel(excel_path, sheet_name="File Summaries")
if _ga_merge_demographics is not None:
    df_summary = _ga_merge_demographics(df_summary, excel_path)

# Pick the correct nPVI column
npvi_col = "nPVI (Isochrony)" if NPVI_DATASET == "raw" else "Stable Rhythm nPVI"
if npvi_col not in df_summary.columns:
    print(f"ERROR: Column '{npvi_col}' not found in File Summaries sheet.")
    print("Available columns:", list(df_summary.columns))
    sys.exit(1)

# Filter to rows with valid numeric nPVI
df = df_summary[["File Name", npvi_col]].copy()
df[npvi_col] = pd.to_numeric(df[npvi_col], errors="coerce")
df = df.dropna(subset=[npvi_col])

if df.empty:
    print("ERROR: No valid nPVI values found. Cannot generate plots.")
    sys.exit(1)

print(f"Found {len(df)} files with valid {npvi_col} values.")


# ==========================================
# 3. ASSIGN GROUPS
# ==========================================
def assign_groups(df, source, pattern, csv_path, manual_map, ungrouped,
                  excel_column=None, df_summary=None):
    """Add a 'Group' column based on the selected source method."""
    if source == "filename_pattern":
        try:
            compiled = re.compile(pattern)
        except re.error as e:
            print(f"ERROR: Invalid group pattern: {e}")
            sys.exit(1)
        groups = []
        for fname in df["File Name"]:
            m = compiled.search(str(fname))
            if m and "group" in m.groupdict():
                groups.append(m.group("group"))
            else:
                groups.append(ungrouped)
        df["Group"] = groups

    elif source == "mapping_csv":
        if not csv_path or not os.path.isfile(csv_path):
            print(f"ERROR: Group mapping CSV not found: {csv_path}")
            sys.exit(1)
        map_df = pd.read_csv(csv_path)
        if "File Name" not in map_df.columns or "Group" not in map_df.columns:
            print("ERROR: Mapping CSV must have 'File Name' and 'Group' columns.")
            sys.exit(1)
        mapping = dict(zip(map_df["File Name"], map_df["Group"]))
        df["Group"] = df["File Name"].map(mapping).fillna(ungrouped)

    elif source == "manual":
        df["Group"] = df["File Name"].map(manual_map).fillna(ungrouped)

    elif source == "excel_column":
        col = excel_column or "Group"
        if df_summary is not None and col in df_summary.columns:
            mapping = dict(zip(df_summary["File Name"], df_summary[col].astype(str)))
            df["Group"] = df["File Name"].map(mapping).fillna(ungrouped)
        else:
            print(f"ERROR: Column '{col}' not found in File Summaries sheet.")
            print("Available columns:", list(df_summary.columns) if df_summary is not None else "N/A")
            sys.exit(1)

    else:
        print(f"ERROR: Unknown GROUP_SOURCE '{source}'. "
              "Use 'filename_pattern', 'mapping_csv', 'manual', or 'excel_column'.")
        sys.exit(1)

    return df


df = assign_groups(df, GROUP_SOURCE, GROUP_PATTERN, GROUP_CSV_PATH,
                   MANUAL_GROUPS, UNGROUPED_LABEL,
                   excel_column=GROUP_EXCEL_COLUMN, df_summary=df_summary)

# Determine group order
if NPVI_GROUP_ORDER and NPVI_GROUP_ORDER.strip():
    group_order = [g.strip() for g in NPVI_GROUP_ORDER.split(",") if g.strip()]
    # Add any groups not specified to the end
    for g in sorted(df["Group"].unique()):
        if g not in group_order:
            group_order.append(g)
else:
    group_order = sorted(df["Group"].unique())

# Filter and reorder
df["Group"] = pd.Categorical(df["Group"], categories=group_order, ordered=True)
df = df.sort_values("Group")

groups = [g for g in group_order if g in df["Group"].values]
group_data = [df[df["Group"] == g][npvi_col].values for g in groups]

print(f"Groups found: {groups}")
for g, gd in zip(groups, group_data):
    print(f"  {g}: n={len(gd)}, mean={np.mean(gd):.1f}, median={np.median(gd):.1f}")


# ==========================================
# 4. COLOUR PALETTE
# ==========================================
def get_palette(palette_str, n):
    """Return a list of n colours from a named colormap or comma-separated hex list."""
    if "," in palette_str:
        colors = [c.strip() for c in palette_str.split(",")]
        while len(colors) < n:
            colors.extend(colors)
        return colors[:n]
    try:
        cmap = plt.get_cmap(palette_str)
        return [cmap(i / max(n - 1, 1)) for i in range(n)]
    except ValueError:
        cmap = plt.get_cmap("Set2")
        return [cmap(i / max(n - 1, 1)) for i in range(n)]


colors = get_palette(NPVI_PALETTE, len(groups))


# ==========================================
# 5. RAINCLOUD PLOT
# ==========================================
def draw_half_violin(ax, data, position, color, width=0.6, alpha=0.6, bw_adjust=0.7):
    """Draw a half-violin (kernel density) to the right of the given position."""
    if len(data) < 2:
        return
    from scipy.stats import gaussian_kde
    try:
        kde = gaussian_kde(data, bw_method=bw_adjust)
    except np.linalg.LinAlgError:
        return
    y_range = np.linspace(data.min() - 0.1 * np.ptp(data),
                          data.max() + 0.1 * np.ptp(data), 200)
    density = kde(y_range)
    # Normalise density to desired visual width
    density = density / density.max() * width
    # Draw to the right of the position
    ax.fill_betweenx(y_range, position, position + density,
                     alpha=alpha, color=color, edgecolor="none")


def create_raincloud_plot(groups, group_data, colors, save_paths):
    """Create the raincloud (half-violin + box + jitter) plot."""
    fig, ax = plt.subplots(figsize=(NPVI_FIG_WIDTH, NPVI_FIG_HEIGHT),
                           facecolor=NPVI_BG_COLOR)
    ax.set_facecolor(NPVI_BG_COLOR)

    positions = np.arange(len(groups))

    for i, (gname, gdata, col) in enumerate(zip(groups, group_data, colors)):
        pos = positions[i]
        fill_color = NPVI_VIOLIN_COLOR if NPVI_VIOLIN_COLOR else col

        # Half-violin (kernel density) to the right
        draw_half_violin(ax, gdata, pos + 0.05, fill_color,
                         width=NPVI_VIOLIN_WIDTH, alpha=NPVI_VIOLIN_ALPHA,
                         bw_adjust=NPVI_VIOLIN_BANDWIDTH)

        # Boxplot (slightly left of centre)
        bp = ax.boxplot([gdata], positions=[pos - 0.12], widths=NPVI_BOX_WIDTH,
                        vert=True, patch_artist=True,
                        showfliers=False, manage_ticks=False)
        for patch in bp["boxes"]:
            patch.set_facecolor(fill_color)
            patch.set_alpha(NPVI_BOX_ALPHA)
            patch.set_edgecolor("black")
        for element in ("whiskers", "caps", "medians"):
            for line in bp[element]:
                line.set_color("black")
                line.set_linewidth(0.8)

        # Jitter points (left side)
        jitter_x = pos - 0.25 + np.random.default_rng(42 + i).uniform(
            -NPVI_JITTER_WIDTH, NPVI_JITTER_WIDTH, len(gdata))
        ax.scatter(jitter_x, gdata, s=NPVI_JITTER_SIZE,
                   alpha=NPVI_JITTER_ALPHA, color=NPVI_JITTER_COLOR,
                   edgecolors="none", zorder=3)

        # Per-group stats annotation
        if NPVI_SHOW_STATS and len(gdata) > 0:
            mean_val = np.mean(gdata)
            median_val = np.median(gdata)
            n_val = len(gdata)
            stat_text = f"n={n_val}\nM={mean_val:.1f}\nMd={median_val:.1f}"
            ax.text(pos, ax.get_ylim()[0] if ax.get_ylim()[0] != 0 else min(gdata) * 0.85,
                    stat_text, ha="center", va="top",
                    fontsize=NPVI_STATS_FONTSIZE, color=NPVI_AXIS_COLOR,
                    alpha=0.7)

    # Reference lines
    if NPVI_REF_LINES and NPVI_REF_VALUES:
        try:
            ref_vals = [float(v.strip()) for v in NPVI_REF_VALUES.split(",") if v.strip()]
        except ValueError:
            ref_vals = []
        ref_labels = ([s.strip() for s in NPVI_REF_LABELS.split(",") if s.strip()]
                      if NPVI_REF_LABELS else [])
        for j, rv in enumerate(ref_vals):
            ax.axhline(y=rv, color=NPVI_REF_COLOR, linestyle=NPVI_REF_STYLE,
                       linewidth=NPVI_REF_WIDTH, alpha=NPVI_REF_ALPHA)
            if j < len(ref_labels):
                ax.text(len(groups) - 0.5, rv, f" {ref_labels[j]}",
                        va="bottom", ha="right", fontsize=NPVI_TICK_FONTSIZE - 1,
                        color=NPVI_REF_COLOR, alpha=0.8)

    # Fix the stats text position after axes limits are set
    if NPVI_SHOW_STATS:
        y_min = ax.get_ylim()[0]
        for i, (gname, gdata) in enumerate(zip(groups, group_data)):
            if len(gdata) > 0:
                mean_val = np.mean(gdata)
                median_val = np.median(gdata)
                n_val = len(gdata)
                stat_text = f"n={n_val}\nM={mean_val:.1f}\nMd={median_val:.1f}"
                # Clear and redraw at bottom
                ax.text(positions[i], y_min + 0.02 * (ax.get_ylim()[1] - y_min),
                        stat_text, ha="center", va="bottom",
                        fontsize=NPVI_STATS_FONTSIZE, color=NPVI_AXIS_COLOR,
                        alpha=0.7,
                        bbox=dict(boxstyle="round,pad=0.2", facecolor=NPVI_BG_COLOR,
                                  edgecolor="none", alpha=0.8))

    # Formatting
    ax.set_xticks(positions)
    ax.set_xticklabels(groups, fontsize=NPVI_TICK_FONTSIZE, color=NPVI_TICK_COLOR)
    ax.set_title(NPVI_TITLE, fontsize=NPVI_TITLE_FONTSIZE, fontweight="bold",
                 pad=NPVI_TITLE_PAD, color=NPVI_TITLE_COLOR)
    if NPVI_X_LABEL:
        ax.set_xlabel(NPVI_X_LABEL, fontsize=NPVI_AXIS_FONTSIZE,
                      labelpad=NPVI_LABEL_PAD, color=NPVI_AXIS_COLOR)
    ax.set_ylabel(NPVI_Y_LABEL, fontsize=NPVI_AXIS_FONTSIZE,
                  labelpad=NPVI_LABEL_PAD, color=NPVI_AXIS_COLOR)
    ax.tick_params(labelsize=NPVI_TICK_FONTSIZE, labelcolor=NPVI_TICK_COLOR)

    plt.tight_layout(pad=NPVI_TIGHT_PAD)

    for sp in save_paths:
        save_matplotlib_figure(fig, sp, dpi=NPVI_DPI, facecolor=NPVI_BG_COLOR,
                               bbox_inches="tight")
        print(f"  Saved: {sp}")
    plt.close(fig)


# ==========================================
# 6. GENERATE THE PLOT
# ==========================================
print("\nGenerating nPVI by Group raincloud plot...")

base_name = "nPVI_by_Group"
if NPVI_DATASET == "stable":
    base_name = "nPVI_by_Group_Stable"

save_paths = []
fmt = NPVI_OUTPUT_FORMAT.lower().strip()
if "png" in fmt:
    save_paths.append(os.path.join(output_folder, f"{base_name}.png"))
if "svg" in fmt:
    save_paths.append(os.path.join(output_folder, f"{base_name}.svg"))
if "pdf" in fmt:
    save_paths.append(os.path.join(output_folder, f"{base_name}.pdf"))
if not save_paths:
    save_paths.append(os.path.join(output_folder, f"{base_name}.png"))

create_raincloud_plot(groups, group_data, colors, save_paths)

print(f"\nSUCCESS! nPVI group plots saved to: {output_folder}")
