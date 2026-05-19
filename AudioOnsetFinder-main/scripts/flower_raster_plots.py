"""Generate dyadic rhythm raster plots from the extractor workbook.

This script recreates the left/right interval visualization style described in the
project notes, using the dyadic event sheets produced by ``onset_finder.py``.
Each figure sorts events by cycle duration and plots the short interval to the left
of zero and the long interval to the right, making cross-file rhythmic structure
easy to compare at a glance.

Current role in the pipeline:
- Input: ``Cross_Species_Rhythm_Data.xlsx``
- Output: PNG raster plots in ``Raster_Plots/``

Useful expansion points from ``docs/ReadMe.md`` and ``docs/nextSteps.md``:
- Add metadata-driven grouping (species, call type, recording context) for larger corpora.
- Add safeguards for missing or empty sheets before plot generation starts.
"""

import os  # filesystem checks and path operations
import sys  # exit with status code on fatal errors

import numpy as np  # numerical operations for boundary dispersion calculation
import matplotlib.pyplot as plt  # raster plot generation
import matplotlib.ticker as ticker  # custom axis formatting for mirrored plot labels
import pandas as pd  # read the Excel workbook and manipulate imported data

try:
    from .shared_output_writers import save_matplotlib_figure
except ImportError:
    from shared_output_writers import save_matplotlib_figure

# ==========================================
# 1. CONFIGURATION
# ==========================================
# Default paths are derived from the project root so the script is portable.
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
excel_path = os.path.join(_PROJECT_DIR, "Cross_Species_Rhythm_Data.xlsx")
PLOT_DATASETS = ("raw", "stable")

# The raster plots are exported to their own folder so they remain separate from histograms.
output_folder = os.path.join(_PROJECT_DIR, "Raster_Plots")

# Figure & appearance defaults (can be overridden via pipeline_config.json)
RASTER_FIG_WIDTH = 10
RASTER_FIG_HEIGHT = 8
RASTER_DPI = 300
RASTER_TIGHT_PAD = 1.08
RASTER_DOT_SIZE = 3
RASTER_ALPHA = 0.6
RASTER_COLOR_SHORT = "#1f77b4"
RASTER_COLOR_LONG = "#ff7f0e"
RASTER_CENTER_COLOR = "#000000"
RASTER_CENTER_WIDTH = 1.5
RASTER_CENTER_STYLE = "-"
RASTER_TITLE_FONTSIZE = 14
RASTER_TITLE_PAD = 12
RASTER_AXIS_FONTSIZE = 12
RASTER_LABEL_PAD = 8
RASTER_TICK_FONTSIZE = 10
RASTER_GRID = True
RASTER_GRID_ALPHA = 0.5
RASTER_GRID_COLOR = "#cccccc"
RASTER_GRID_STYLE = "--"
RASTER_LEGEND_SHOW = True
RASTER_LEGEND_POS = "upper left"
RASTER_LEGEND_FONTSIZE = 10
RASTER_REF_LINES = False
RASTER_REF_VALUES = ""
RASTER_REF_LABELS = ""
RASTER_REF_COLOR = "#e74c3c"
RASTER_COMBINED = True
RASTER_TITLE_COLOR = "#000000"
RASTER_AXIS_COLOR = "#000000"
RASTER_TICK_COLOR = "#000000"
RASTER_TITLE_PREFIX = "Rhythm Raster"
RASTER_TITLE_SUFFIX = ""
RASTER_COMBINED_TITLE_PREFIX = "Combined Corpus Rhythm Raster"
RASTER_X_LABEL = "Interval Duration (ms)"
RASTER_Y_LABEL = "Dyadic Events (Sorted by Cycle Duration)"
RASTER_BG_COLOR = "#ffffff"

# Rhythm boundary line defaults (Roeske et al. 2020 "fanning out" boundary)
RASTER_BOUNDARY_ENABLED = False
RASTER_BOUNDARY_METHOD = "std"          # "std" or "entropy"
RASTER_BOUNDARY_THRESHOLD = 0.12       # σ_r threshold (std) or entropy threshold
RASTER_BOUNDARY_WINDOW = 50            # sliding window size in number of dyads
RASTER_BOUNDARY_COLOR = "#e74c3c"
RASTER_BOUNDARY_WIDTH = 2.0
RASTER_BOUNDARY_STYLE = "--"
RASTER_BOUNDARY_LABEL = "Tempo Boundary"
RASTER_BOUNDARY_SHOW_VALUE = True
RASTER_BOUNDARY_TEXT_SIZE = 11
RASTER_BOUNDARY_TEXT_COLOR = "#e74c3c"
RASTER_BOUNDARY_TEXT_VA = "above"       # "above" or "below"
RASTER_BOUNDARY_TEXT_HA = "right"       # "left", "center", or "right"

# ------------------------------------------------------------------
# GUI CONFIG OVERRIDE
# ------------------------------------------------------------------
_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "pipeline_config.json")
if os.path.isfile(_config_path):
    import json as _json
    with open(_config_path) as _f:
        _cfg = _json.load(_f).get("plot_generator", {})
    excel_path = _cfg.get("excel_path", excel_path)
    output_folder = _cfg.get("output_folder", output_folder)
    PLOT_DATASETS = tuple(_cfg.get("PLOT_DATASETS", list(PLOT_DATASETS)))
    RASTER_FIG_WIDTH = _cfg.get("RASTER_FIG_WIDTH", RASTER_FIG_WIDTH)
    RASTER_FIG_HEIGHT = _cfg.get("RASTER_FIG_HEIGHT", RASTER_FIG_HEIGHT)
    RASTER_DPI = _cfg.get("RASTER_DPI", RASTER_DPI)
    RASTER_TIGHT_PAD = _cfg.get("RASTER_TIGHT_PAD", RASTER_TIGHT_PAD)
    RASTER_DOT_SIZE = _cfg.get("RASTER_DOT_SIZE", RASTER_DOT_SIZE)
    RASTER_ALPHA = _cfg.get("RASTER_ALPHA", RASTER_ALPHA)
    RASTER_COLOR_SHORT = _cfg.get("RASTER_COLOR_SHORT", RASTER_COLOR_SHORT)
    RASTER_COLOR_LONG = _cfg.get("RASTER_COLOR_LONG", RASTER_COLOR_LONG)
    RASTER_CENTER_COLOR = _cfg.get("RASTER_CENTER_COLOR", RASTER_CENTER_COLOR)
    RASTER_CENTER_WIDTH = _cfg.get("RASTER_CENTER_WIDTH", RASTER_CENTER_WIDTH)
    RASTER_CENTER_STYLE = _cfg.get("RASTER_CENTER_STYLE", RASTER_CENTER_STYLE)
    RASTER_TITLE_FONTSIZE = _cfg.get("RASTER_TITLE_FONTSIZE", RASTER_TITLE_FONTSIZE)
    RASTER_TITLE_PAD = _cfg.get("RASTER_TITLE_PAD", RASTER_TITLE_PAD)
    RASTER_AXIS_FONTSIZE = _cfg.get("RASTER_AXIS_FONTSIZE", RASTER_AXIS_FONTSIZE)
    RASTER_LABEL_PAD = _cfg.get("RASTER_LABEL_PAD", RASTER_LABEL_PAD)
    RASTER_TICK_FONTSIZE = _cfg.get("RASTER_TICK_FONTSIZE", RASTER_TICK_FONTSIZE)
    RASTER_GRID = _cfg.get("RASTER_GRID", RASTER_GRID)
    RASTER_GRID_ALPHA = _cfg.get("RASTER_GRID_ALPHA", RASTER_GRID_ALPHA)
    RASTER_GRID_COLOR = _cfg.get("RASTER_GRID_COLOR", RASTER_GRID_COLOR)
    RASTER_GRID_STYLE = _cfg.get("RASTER_GRID_STYLE", RASTER_GRID_STYLE)
    RASTER_LEGEND_SHOW = _cfg.get("RASTER_LEGEND_SHOW", RASTER_LEGEND_SHOW)
    RASTER_LEGEND_POS = _cfg.get("RASTER_LEGEND_POS", RASTER_LEGEND_POS)
    RASTER_LEGEND_FONTSIZE = _cfg.get("RASTER_LEGEND_FONTSIZE", RASTER_LEGEND_FONTSIZE)
    RASTER_REF_LINES = _cfg.get("RASTER_REF_LINES", RASTER_REF_LINES)
    RASTER_REF_VALUES = _cfg.get("RASTER_REF_VALUES", RASTER_REF_VALUES)
    RASTER_REF_LABELS = _cfg.get("RASTER_REF_LABELS", RASTER_REF_LABELS)
    RASTER_REF_COLOR = _cfg.get("RASTER_REF_COLOR", RASTER_REF_COLOR)
    RASTER_COMBINED = _cfg.get("RASTER_COMBINED", RASTER_COMBINED)
    RASTER_TITLE_COLOR = _cfg.get("RASTER_TITLE_COLOR", RASTER_TITLE_COLOR)
    RASTER_AXIS_COLOR = _cfg.get("RASTER_AXIS_COLOR", RASTER_AXIS_COLOR)
    RASTER_TICK_COLOR = _cfg.get("RASTER_TICK_COLOR", RASTER_TICK_COLOR)
    RASTER_TITLE_PREFIX = _cfg.get("RASTER_TITLE_PREFIX", RASTER_TITLE_PREFIX)
    RASTER_TITLE_SUFFIX = _cfg.get("RASTER_TITLE_SUFFIX", RASTER_TITLE_SUFFIX)
    RASTER_COMBINED_TITLE_PREFIX = _cfg.get("RASTER_COMBINED_TITLE_PREFIX", RASTER_COMBINED_TITLE_PREFIX)
    RASTER_X_LABEL = _cfg.get("RASTER_X_LABEL", RASTER_X_LABEL)
    RASTER_Y_LABEL = _cfg.get("RASTER_Y_LABEL", RASTER_Y_LABEL)
    RASTER_BG_COLOR = _cfg.get("RASTER_BG_COLOR", RASTER_BG_COLOR)
    RASTER_BOUNDARY_ENABLED = _cfg.get("RASTER_BOUNDARY_ENABLED", RASTER_BOUNDARY_ENABLED)
    RASTER_BOUNDARY_METHOD = _cfg.get("RASTER_BOUNDARY_METHOD", RASTER_BOUNDARY_METHOD)
    RASTER_BOUNDARY_THRESHOLD = _cfg.get("RASTER_BOUNDARY_THRESHOLD", RASTER_BOUNDARY_THRESHOLD)
    RASTER_BOUNDARY_WINDOW = _cfg.get("RASTER_BOUNDARY_WINDOW", RASTER_BOUNDARY_WINDOW)
    RASTER_BOUNDARY_COLOR = _cfg.get("RASTER_BOUNDARY_COLOR", RASTER_BOUNDARY_COLOR)
    RASTER_BOUNDARY_WIDTH = _cfg.get("RASTER_BOUNDARY_WIDTH", RASTER_BOUNDARY_WIDTH)
    RASTER_BOUNDARY_STYLE = _cfg.get("RASTER_BOUNDARY_STYLE", RASTER_BOUNDARY_STYLE)
    RASTER_BOUNDARY_LABEL = _cfg.get("RASTER_BOUNDARY_LABEL", RASTER_BOUNDARY_LABEL)
    RASTER_BOUNDARY_SHOW_VALUE = _cfg.get("RASTER_BOUNDARY_SHOW_VALUE", RASTER_BOUNDARY_SHOW_VALUE)
    RASTER_BOUNDARY_TEXT_SIZE = _cfg.get("RASTER_BOUNDARY_TEXT_SIZE", RASTER_BOUNDARY_TEXT_SIZE)
    RASTER_BOUNDARY_TEXT_COLOR = _cfg.get("RASTER_BOUNDARY_TEXT_COLOR", RASTER_BOUNDARY_TEXT_COLOR)
    RASTER_BOUNDARY_TEXT_VA = _cfg.get("RASTER_BOUNDARY_TEXT_VA", RASTER_BOUNDARY_TEXT_VA)
    RASTER_BOUNDARY_TEXT_HA = _cfg.get("RASTER_BOUNDARY_TEXT_HA", RASTER_BOUNDARY_TEXT_HA)
    del _json, _f, _cfg
if not os.path.exists(output_folder):
    os.makedirs(output_folder)


def load_plot_datasets(workbook_path, selected_datasets):
    """Load whichever dyadic sheets are available for raster plotting."""
    dataset_sheets = {
        "raw": "Dyadic Events (For Plots)",
        "stable": "Dyadic Events (Stable Rhythms)",
    }
    loaded_datasets = []
    workbook = pd.ExcelFile(workbook_path)

    for dataset_name in selected_datasets:
        sheet_name = dataset_sheets[dataset_name]
        if sheet_name not in workbook.sheet_names:
            print(f"Skipping {dataset_name} raster plots because '{sheet_name}' is not present.")
            continue

        dataframe = pd.read_excel(workbook_path, sheet_name=sheet_name)
        if dataframe.empty:
            print(f"Skipping {dataset_name} raster plots because '{sheet_name}' is empty.")
            continue

        loaded_datasets.append((dataset_name, dataframe))

    return loaded_datasets

print("Loading data from Excel...")
if not os.path.isfile(excel_path):
    print(f"ERROR: Excel workbook not found: {excel_path}")
    print("Run the Onset Finder (Step 2) first to generate the workbook.")
    sys.exit(1)
plot_datasets = load_plot_datasets(excel_path, PLOT_DATASETS)


# ==========================================
# 2. BOUNDARY CALCULATION
# ==========================================
def find_rhythm_boundary(data, method, threshold, window):
    """Find the Cycle Duration where rhythm dispersion first exceeds *threshold*.

    Implements the 'Moving Window Dispersion' approach inspired by
    Roeske et al. (2020) and the Jadoul & Eleuteri (2025) mathematical framework.

    1. Sort all dyads by Cycle Duration.
    2. Slide a window of *window* dyads and compute a dispersion measure
       of the Rhythm Ratio (r_k) values inside the window.
    3. Return the Cycle Duration at the centre of the first window where the
       dispersion exceeds *threshold*.

    Parameters
    ----------
    data : pd.DataFrame
        Must contain 'Cycle Duration [cd] (ms)' and 'Rhythm Ratio [r_k]'.
    method : str
        'std' — dispersion = standard deviation of r_k in the window.
        'entropy' — dispersion = Shannon entropy of r_k histogram (10 bins).
    threshold : float
        The dispersion value that triggers the boundary.
    window : int
        Number of dyads in the sliding window.

    Returns
    -------
    boundary_cd : float or None
        The Cycle Duration (ms) at the boundary, or None if never exceeded.
    boundary_idx : int or None
        The y-axis index position (in the sorted data) of the boundary.
    """
    sorted_data = data.sort_values(by="Cycle Duration [cd] (ms)").reset_index(drop=True)
    cd_vals = sorted_data["Cycle Duration [cd] (ms)"].values
    rk_vals = sorted_data["Rhythm Ratio [r_k]"].values

    n = len(rk_vals)
    if n < window or window < 2:
        return None, None

    for i in range(n - window + 1):
        rk_window = rk_vals[i : i + window]

        if method == "entropy":
            # Shannon entropy of r_k histogram (10 equal-width bins over [0, 1])
            counts, _ = np.histogram(rk_window, bins=10, range=(0.0, 1.0))
            probs = counts / counts.sum()
            probs = probs[probs > 0]
            dispersion = -np.sum(probs * np.log2(probs))
        else:
            # Standard deviation of r_k values
            dispersion = np.std(rk_window, ddof=1) if len(rk_window) > 1 else 0.0

        if dispersion > threshold:
            centre_idx = i + window // 2
            return float(cd_vals[centre_idx]), int(centre_idx)

    return None, None


# ==========================================
# 3. PLOTTING FUNCTION
# ==========================================
def create_raster_plot(data, title, save_path):
    """Create one raster plot from a dyadic event table."""
    # Sorting by cycle duration reproduces the structured sweep seen in the reference plots.
    sorted_data = data.sort_values(by="Cycle Duration [cd] (ms)").reset_index(drop=True)
    y_axis = sorted_data.index
    
    plt.figure(figsize=(RASTER_FIG_WIDTH, RASTER_FIG_HEIGHT), facecolor=RASTER_BG_COLOR)
    plt.gca().set_facecolor(RASTER_BG_COLOR)
    
    # Short intervals are mirrored to the left of zero to create the "flower" layout.
    plt.scatter(-sorted_data["Short Interval [i_s] (ms)"], y_axis, 
                color=RASTER_COLOR_SHORT, s=RASTER_DOT_SIZE, alpha=RASTER_ALPHA,
                label="Short Interval (i_s)")
    
    # Long intervals remain positive on the right-hand side of the center line.
    plt.scatter(sorted_data["Long Interval [i_l] (ms)"], y_axis, 
                color=RASTER_COLOR_LONG, s=RASTER_DOT_SIZE, alpha=RASTER_ALPHA,
                label="Long Interval (i_l)")
    
    # The center line separates the short and long interval halves of each dyad.
    plt.axvline(x=0, color=RASTER_CENTER_COLOR, linewidth=RASTER_CENTER_WIDTH,
                linestyle=RASTER_CENTER_STYLE, zorder=0)
    
    plt.title(title, fontsize=RASTER_TITLE_FONTSIZE, fontweight='bold', pad=RASTER_TITLE_PAD,
              color=RASTER_TITLE_COLOR)
    plt.xlabel(RASTER_X_LABEL, fontsize=RASTER_AXIS_FONTSIZE, labelpad=RASTER_LABEL_PAD,
               color=RASTER_AXIS_COLOR)
    plt.ylabel(RASTER_Y_LABEL, fontsize=RASTER_AXIS_FONTSIZE,
               labelpad=RASTER_LABEL_PAD, color=RASTER_AXIS_COLOR)
    plt.tick_params(labelsize=RASTER_TICK_FONTSIZE, labelcolor=RASTER_TICK_COLOR)

    if RASTER_LEGEND_SHOW:
        plt.legend(loc=RASTER_LEGEND_POS, fontsize=RASTER_LEGEND_FONTSIZE)

    if RASTER_GRID:
        plt.grid(True, linestyle=RASTER_GRID_STYLE, alpha=RASTER_GRID_ALPHA,
                 color=RASTER_GRID_COLOR)

    # Rhythm reference lines (horizontal, keyed to cycle-duration y-axis)
    if RASTER_REF_LINES and RASTER_REF_VALUES:
        try:
            ref_vals = [float(v.strip()) for v in RASTER_REF_VALUES.split(",") if v.strip()]
        except ValueError:
            ref_vals = []
        ref_lbls = ([s.strip() for s in RASTER_REF_LABELS.split(",") if s.strip()]
                     if RASTER_REF_LABELS else [])
        for i, rv in enumerate(ref_vals):
            lbl = ref_lbls[i] if i < len(ref_lbls) else None
            plt.axhline(rv, color=RASTER_REF_COLOR, linewidth=0.9, linestyle="--", alpha=0.6)
            if lbl:
                plt.text(plt.xlim()[1] * 0.95, rv, f" {lbl}",
                         va="center", ha="right", fontsize=max(RASTER_TICK_FONTSIZE - 1, 6),
                         color=RASTER_REF_COLOR, alpha=0.8)

    # Rhythm boundary line — marks the CD where rhythm distribution fans out.
    if RASTER_BOUNDARY_ENABLED:
        boundary_cd, boundary_idx = find_rhythm_boundary(
            data, RASTER_BOUNDARY_METHOD, RASTER_BOUNDARY_THRESHOLD,
            RASTER_BOUNDARY_WINDOW)
        if boundary_idx is not None:
            ax = plt.gca()
            xlims = ax.get_xlim()
            ax.axhline(boundary_idx, color=RASTER_BOUNDARY_COLOR,
                       linewidth=RASTER_BOUNDARY_WIDTH,
                       linestyle=RASTER_BOUNDARY_STYLE, zorder=2)
            # Build label text
            label_text = RASTER_BOUNDARY_LABEL
            if RASTER_BOUNDARY_SHOW_VALUE and boundary_cd is not None:
                label_text += f" = {boundary_cd:.0f}ms"
            # Horizontal position
            ha_map = {"left": "left", "center": "center", "right": "right"}
            ha = ha_map.get(RASTER_BOUNDARY_TEXT_HA, "right")
            if RASTER_BOUNDARY_TEXT_HA == "left":
                x_pos = xlims[0] + (xlims[1] - xlims[0]) * 0.05
            elif RASTER_BOUNDARY_TEXT_HA == "center":
                x_pos = (xlims[0] + xlims[1]) / 2
            else:
                x_pos = xlims[1] - (xlims[1] - xlims[0]) * 0.05
            # Vertical offset above or below the line
            y_offset = len(sorted_data) * 0.02
            if RASTER_BOUNDARY_TEXT_VA == "below":
                y_pos = boundary_idx + y_offset
                va = "top"
            else:
                y_pos = boundary_idx - y_offset
                va = "bottom"
            ax.text(x_pos, y_pos, label_text, fontsize=RASTER_BOUNDARY_TEXT_SIZE,
                    color=RASTER_BOUNDARY_TEXT_COLOR, ha=ha, va=va, zorder=3)
    
    # Format the mirrored left axis as positive values to match the reference figure style.
    plt.gca().xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f"{abs(int(x))}"))
    
    plt.tight_layout(pad=RASTER_TIGHT_PAD)
    save_matplotlib_figure(plt, save_path, dpi=RASTER_DPI, facecolor=RASTER_BG_COLOR)
    plt.close()

# ==========================================
# 4. GENERATE INDIVIDUAL PLOTS
# ==========================================
for dataset_name, df in plot_datasets:
    dataset_output_folder = os.path.join(output_folder, dataset_name)
    if not os.path.exists(dataset_output_folder):
        os.makedirs(dataset_output_folder)

    files = df["File Name"].unique()
    print(f"Found data for {len(files)} files in the {dataset_name} sheet. Generating individual plots...")

    for filename in files:
        # Each file gets its own panel so individual rhythmic structure can be inspected.
        file_data = df[df["File Name"] == filename]
        if file_data.empty:
            continue

        plot_name = f"{os.path.splitext(filename)[0]}_Raster.png"
        save_location = os.path.join(dataset_output_folder, plot_name)

        create_raster_plot(file_data, f"{RASTER_TITLE_PREFIX} ({dataset_name.title()}): {filename}{RASTER_TITLE_SUFFIX}", save_location)

    # ==========================================
    # 5. GENERATE THE "COMBINED CORPUS" PLOT
    # ==========================================
    if RASTER_COMBINED:
        print(f"Generating Combined Corpus master plot for the {dataset_name} sheet...")
        combined_save_path = os.path.join(dataset_output_folder, "ALL_FILES_COMBINED_Raster.png")
        create_raster_plot(df, f"{RASTER_COMBINED_TITLE_PREFIX} ({dataset_name.title()}){RASTER_TITLE_SUFFIX}", combined_save_path)

print(f"\nSUCCESS! All plots saved to: {output_folder}")