"""Generate per-file and combined rhythm-ratio histograms from the extractor output.

This script reads the Excel workbook created by ``onset_finder.py`` and builds
histograms of the dyadic rhythm ratio ``r_k`` for each recording plus the full corpus.
It also overlays summary metrics from the workbook so each figure can be inspected
without reopening the spreadsheet.

Current role in the pipeline:
- Input: ``Cross_Species_Rhythm_Data.xlsx``
- Output: PNG histograms in ``Histogram_Plots/``

Useful expansion points from ``docs/ReadMe.md`` and ``docs/nextSteps.md``:
- Add species-level or corpus-level summary plots once the dataset grows.
- Add validation around missing Excel sheets or columns for smoother handoff to other users.
"""

import os  # filesystem checks and path operations
import sys  # exit with status code on fatal errors

import matplotlib.pyplot as plt  # histogram generation and annotation
import pandas as pd  # read the Excel workbook and manipulate imported data

# ==========================================
# 1. CONFIGURATION
# ==========================================
# Default paths are derived from the project root so the script is portable.
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, os.path.join(_PROJECT_DIR, "scripts"))
try:
    from group_assignment import merge_file_demographics as _ga_merge_demographics  # noqa: E402
except Exception:
    _ga_merge_demographics = None
excel_path = os.path.join(_PROJECT_DIR, "Cross_Species_Rhythm_Data.xlsx")
PLOT_DATASETS = ("raw", "stable")
output_folder = os.path.join(_PROJECT_DIR, "Histogram_Plots")

# Figure & appearance defaults (can be overridden via pipeline_config.json)
HIST_FIG_WIDTH = 10
HIST_FIG_HEIGHT = 6
HIST_DPI = 300
HIST_TIGHT_PAD = 1.08
HIST_BINS = 30
HIST_COLOR = "#2ca02c"
HIST_ALPHA = 0.7
HIST_EDGE_COLOR = "black"
HIST_EDGE_WIDTH = 0.8
HIST_TITLE_FONTSIZE = 14
HIST_TITLE_PAD = 12
HIST_AXIS_FONTSIZE = 12
HIST_LABEL_PAD = 8
HIST_TICK_FONTSIZE = 10
HIST_REF_LINES = True
HIST_REF_RATIOS = "0.25, 0.333, 0.5, 0.666, 0.75"
HIST_REF_LABELS = "1:3, 1:2, 1:1, 2:1, 3:1"
HIST_REF_COLOR = "#ff0000"
HIST_REF_STYLE = "--"
HIST_REF_WIDTH = 0.9
HIST_REF_ALPHA = 0.5
HIST_ISO_BAND = True
HIST_ISO_LOW = 0.45
HIST_ISO_HIGH = 0.55
HIST_ISO_COLOR = "#808080"
HIST_ISO_ALPHA = 0.15
HIST_SHOW_STATS = True
HIST_STATS_X = 0.97
HIST_STATS_Y = 0.95
HIST_STATS_HA = "right"
HIST_STATS_VA = "top"
HIST_STATS_FONTSIZE = 11
HIST_STATS_BG = "#ffffff"
HIST_STATS_ALPHA = 0.9
HIST_STATS_TEXT_COLOR = "#000000"
HIST_TITLE_COLOR = "#000000"
HIST_AXIS_COLOR = "#000000"
HIST_TICK_COLOR = "#000000"
HIST_TITLE_PREFIX = "r_k Distribution"
HIST_TITLE_SUFFIX = ""
HIST_COMBINED_TITLE_PREFIX = "Combined Corpus r_k Distribution"
HIST_X_LABEL = "Rhythm Ratio (r_k)"
HIST_Y_LABEL = "Frequency (Number of Dyads)"
HIST_BG_COLOR = "#ffffff"
HIST_COMBINED = True

# ------------------------------------------------------------------
# GUI CONFIG OVERRIDE
# ------------------------------------------------------------------
_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "pipeline_config.json")
if os.path.isfile(_config_path):
    import json as _json
    with open(_config_path) as _f:
        _cfg = _json.load(_f).get("histogram_generator", {})
    excel_path = _cfg.get("excel_path", excel_path)
    output_folder = _cfg.get("output_folder", output_folder)
    PLOT_DATASETS = tuple(_cfg.get("HIST_DATASETS", list(PLOT_DATASETS)))
    HIST_FIG_WIDTH = _cfg.get("HIST_FIG_WIDTH", HIST_FIG_WIDTH)
    HIST_FIG_HEIGHT = _cfg.get("HIST_FIG_HEIGHT", HIST_FIG_HEIGHT)
    HIST_DPI = _cfg.get("HIST_DPI", HIST_DPI)
    HIST_TIGHT_PAD = _cfg.get("HIST_TIGHT_PAD", HIST_TIGHT_PAD)
    HIST_BINS = _cfg.get("HIST_BINS", HIST_BINS)
    HIST_COLOR = _cfg.get("HIST_COLOR", HIST_COLOR)
    HIST_ALPHA = _cfg.get("HIST_ALPHA", HIST_ALPHA)
    HIST_EDGE_COLOR = _cfg.get("HIST_EDGE_COLOR", HIST_EDGE_COLOR)
    HIST_EDGE_WIDTH = _cfg.get("HIST_EDGE_WIDTH", HIST_EDGE_WIDTH)
    HIST_TITLE_FONTSIZE = _cfg.get("HIST_TITLE_FONTSIZE", HIST_TITLE_FONTSIZE)
    HIST_TITLE_PAD = _cfg.get("HIST_TITLE_PAD", HIST_TITLE_PAD)
    HIST_AXIS_FONTSIZE = _cfg.get("HIST_AXIS_FONTSIZE", HIST_AXIS_FONTSIZE)
    HIST_LABEL_PAD = _cfg.get("HIST_LABEL_PAD", HIST_LABEL_PAD)
    HIST_TICK_FONTSIZE = _cfg.get("HIST_TICK_FONTSIZE", HIST_TICK_FONTSIZE)
    HIST_REF_LINES = _cfg.get("HIST_REF_LINES", HIST_REF_LINES)
    HIST_REF_RATIOS = _cfg.get("HIST_REF_RATIOS", HIST_REF_RATIOS)
    HIST_REF_LABELS = _cfg.get("HIST_REF_LABELS", HIST_REF_LABELS)
    HIST_REF_COLOR = _cfg.get("HIST_REF_COLOR", HIST_REF_COLOR)
    HIST_REF_STYLE = _cfg.get("HIST_REF_STYLE", HIST_REF_STYLE)
    HIST_REF_WIDTH = _cfg.get("HIST_REF_WIDTH", HIST_REF_WIDTH)
    HIST_REF_ALPHA = _cfg.get("HIST_REF_ALPHA", HIST_REF_ALPHA)
    HIST_ISO_BAND = _cfg.get("HIST_ISO_BAND", HIST_ISO_BAND)
    HIST_ISO_LOW = _cfg.get("HIST_ISO_LOW", HIST_ISO_LOW)
    HIST_ISO_HIGH = _cfg.get("HIST_ISO_HIGH", HIST_ISO_HIGH)
    HIST_ISO_COLOR = _cfg.get("HIST_ISO_COLOR", HIST_ISO_COLOR)
    HIST_ISO_ALPHA = _cfg.get("HIST_ISO_ALPHA", HIST_ISO_ALPHA)
    HIST_SHOW_STATS = _cfg.get("HIST_SHOW_STATS", HIST_SHOW_STATS)
    HIST_STATS_X = _cfg.get("HIST_STATS_X", HIST_STATS_X)
    HIST_STATS_Y = _cfg.get("HIST_STATS_Y", HIST_STATS_Y)
    HIST_STATS_HA = _cfg.get("HIST_STATS_HA", HIST_STATS_HA)
    HIST_STATS_VA = _cfg.get("HIST_STATS_VA", HIST_STATS_VA)
    HIST_STATS_FONTSIZE = _cfg.get("HIST_STATS_FONTSIZE", HIST_STATS_FONTSIZE)
    HIST_STATS_BG = _cfg.get("HIST_STATS_BG", HIST_STATS_BG)
    HIST_STATS_ALPHA = _cfg.get("HIST_STATS_ALPHA", HIST_STATS_ALPHA)
    HIST_STATS_TEXT_COLOR = _cfg.get("HIST_STATS_TEXT_COLOR", HIST_STATS_TEXT_COLOR)
    HIST_TITLE_COLOR = _cfg.get("HIST_TITLE_COLOR", HIST_TITLE_COLOR)
    HIST_AXIS_COLOR = _cfg.get("HIST_AXIS_COLOR", HIST_AXIS_COLOR)
    HIST_TICK_COLOR = _cfg.get("HIST_TICK_COLOR", HIST_TICK_COLOR)
    HIST_TITLE_PREFIX = _cfg.get("HIST_TITLE_PREFIX", HIST_TITLE_PREFIX)
    HIST_TITLE_SUFFIX = _cfg.get("HIST_TITLE_SUFFIX", HIST_TITLE_SUFFIX)
    HIST_COMBINED_TITLE_PREFIX = _cfg.get("HIST_COMBINED_TITLE_PREFIX", HIST_COMBINED_TITLE_PREFIX)
    HIST_X_LABEL = _cfg.get("HIST_X_LABEL", HIST_X_LABEL)
    HIST_Y_LABEL = _cfg.get("HIST_Y_LABEL", HIST_Y_LABEL)
    HIST_BG_COLOR = _cfg.get("HIST_BG_COLOR", HIST_BG_COLOR)
    HIST_COMBINED = _cfg.get("HIST_COMBINED", HIST_COMBINED)
    del _json, _f, _cfg

if not os.path.exists(output_folder):
    os.makedirs(output_folder)


def load_plot_datasets(workbook_path, selected_datasets):
    """Load whichever dyadic sheets are available for histogram generation."""
    dataset_sheets = {
        "raw": "Dyadic Events (For Plots)",
        "stable": "Dyadic Events (Stable Rhythms)",
    }
    loaded_datasets = []
    workbook = pd.ExcelFile(workbook_path)

    for dataset_name in selected_datasets:
        sheet_name = dataset_sheets[dataset_name]
        if sheet_name not in workbook.sheet_names:
            print(f"Skipping {dataset_name} histograms because '{sheet_name}' is not present.")
            continue

        dataframe = pd.read_excel(workbook_path, sheet_name=sheet_name)
        if dataframe.empty:
            print(f"Skipping {dataset_name} histograms because '{sheet_name}' is empty.")
            continue

        loaded_datasets.append((dataset_name, dataframe))

    return loaded_datasets


def get_summary_columns(dataset_name):
    """Return the summary columns that match the requested plotting dataset."""
    if dataset_name == "stable":
        return {
            "npvi": "Stable Rhythm nPVI",
            "entropy": "Stable Rhythm Entropy",
            "cv": "Stable Rhythm CV",
        }

    return {
        "npvi": "nPVI (Isochrony)",
        "entropy": "r_k Entropy (Categorical Measure)",
        "cv": "CV of Intervals",
    }

# The histogram view needs both the dyadic event table and the per-file summary table.
print("Loading data from Excel...")
if not os.path.isfile(excel_path):
    print(f"ERROR: Excel workbook not found: {excel_path}")
    print("Run the Onset Finder (Step 2) first to generate the workbook.")
    sys.exit(1)
df_summary = pd.read_excel(excel_path, sheet_name="File Summaries")
if _ga_merge_demographics is not None:
    df_summary = _ga_merge_demographics(df_summary, excel_path)
plot_datasets = load_plot_datasets(excel_path, PLOT_DATASETS)

# ==========================================
# 2. PLOTTING FUNCTION
# ==========================================
def create_histogram(rk_data, summary_row, summary_columns, title, save_path):
    """Create a single r_k histogram and optionally annotate it with file metrics."""
    plt.figure(figsize=(HIST_FIG_WIDTH, HIST_FIG_HEIGHT), facecolor=HIST_BG_COLOR)
    plt.gca().set_facecolor(HIST_BG_COLOR)
    
    # Plot the observed rhythm ratios on a fixed 0-1 scale so files stay comparable.
    plt.hist(rk_data, bins=HIST_BINS, range=(0, 1), color=HIST_COLOR,
             alpha=HIST_ALPHA, edgecolor=HIST_EDGE_COLOR, linewidth=HIST_EDGE_WIDTH)
    
    # Reference lines highlight simple small-integer timing relationships.
    if HIST_REF_LINES and HIST_REF_RATIOS:
        try:
            ratios = [float(v.strip()) for v in HIST_REF_RATIOS.split(",") if v.strip()]
        except ValueError:
            ratios = []
        labels = ([s.strip() for s in HIST_REF_LABELS.split(",") if s.strip()]
                  if HIST_REF_LABELS else [])
        for i, ratio_val in enumerate(ratios):
            plt.axvline(x=ratio_val, color=HIST_REF_COLOR, linestyle=HIST_REF_STYLE,
                        linewidth=HIST_REF_WIDTH, alpha=HIST_REF_ALPHA)
            lbl = labels[i] if i < len(labels) else ""
            if lbl:
                plt.text(ratio_val, plt.ylim()[1]*0.95, lbl, color=HIST_REF_COLOR,
                         ha='center',
                         bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1))
        
    # The summary table provides quick context for how regular or variable the file is.
    if HIST_SHOW_STATS and summary_row is not None and not summary_row.empty:
        npvi = summary_row[summary_columns["npvi"]].values[0]
        entropy = summary_row[summary_columns["entropy"]].values[0]
        cv = summary_row[summary_columns["cv"]].values[0]
        
        # Preserve 'N/A' strings but round numeric metrics for figure readability.
        stats_text = (
            f"Summary Statistics:\n"
            f"nPVI: {npvi if isinstance(npvi, str) else round(npvi, 1)}\n"
            f"Entropy: {entropy if isinstance(entropy, str) else round(entropy, 2)}\n"
            f"Interval CV: {cv if isinstance(cv, str) else round(cv, 2)}"
        )
        
        # Keep the annotation inside the axes so exported figures remain self-contained.
        plt.text(HIST_STATS_X, HIST_STATS_Y, stats_text, transform=plt.gca().transAxes,
                 fontsize=HIST_STATS_FONTSIZE, color=HIST_STATS_TEXT_COLOR,
                 verticalalignment=HIST_STATS_VA, horizontalalignment=HIST_STATS_HA,
                 bbox=dict(boxstyle='round', facecolor=HIST_STATS_BG, alpha=HIST_STATS_ALPHA))

    # Visual framing mirrors the methodology notes in the project docs.
    plt.title(title, fontsize=HIST_TITLE_FONTSIZE, fontweight='bold', pad=HIST_TITLE_PAD,
              color=HIST_TITLE_COLOR)
    plt.xlabel(HIST_X_LABEL, fontsize=HIST_AXIS_FONTSIZE, labelpad=HIST_LABEL_PAD,
               color=HIST_AXIS_COLOR)
    plt.ylabel(HIST_Y_LABEL, fontsize=HIST_AXIS_FONTSIZE, labelpad=HIST_LABEL_PAD,
               color=HIST_AXIS_COLOR)
    plt.tick_params(labelsize=HIST_TICK_FONTSIZE, labelcolor=HIST_TICK_COLOR)
    plt.xlim(0, 1)
    
    # A narrow shaded band around 0.5 marks the isochronous region.
    if HIST_ISO_BAND:
        plt.axvspan(HIST_ISO_LOW, HIST_ISO_HIGH, color=HIST_ISO_COLOR, alpha=HIST_ISO_ALPHA,
                    label='Isochronous Range')
    
    plt.tight_layout(pad=HIST_TIGHT_PAD)
    plt.savefig(save_path, dpi=HIST_DPI, facecolor=HIST_BG_COLOR)
    plt.close()

# ==========================================
# 3. GENERATE INDIVIDUAL PLOTS
# ==========================================
for dataset_name, df_dyads in plot_datasets:
    dataset_output_folder = os.path.join(output_folder, dataset_name)
    if not os.path.exists(dataset_output_folder):
        os.makedirs(dataset_output_folder)
    summary_columns = get_summary_columns(dataset_name)

    files = df_dyads["File Name"].unique()
    print(f"Found data for {len(files)} files in the {dataset_name} sheet. Generating individual histograms...")

    for filename in files:
        # Each output figure is generated from the dyads and summary row for one recording.
        file_rk_data = df_dyads[df_dyads["File Name"] == filename]["Rhythm Ratio [r_k]"].dropna()
        file_summary = df_summary[df_summary["File Name"] == filename]

        # Skip files that did not yield enough onsets to form dyadic events.
        if len(file_rk_data) > 0:
            plot_name = f"{os.path.splitext(filename)[0]}_Hist.png"
            save_location = os.path.join(dataset_output_folder, plot_name)
            create_histogram(
                file_rk_data,
                file_summary,
                summary_columns,
                f"{HIST_TITLE_PREFIX} ({dataset_name.title()}): {filename}{HIST_TITLE_SUFFIX}",
                save_location,
            )

    # ==========================================
    # 4. GENERATE THE "COMBINED CORPUS" PLOT
    # ==========================================
    if HIST_COMBINED:
        print(f"Generating Combined Corpus master histogram for the {dataset_name} sheet...")
        all_rk_data = df_dyads["Rhythm Ratio [r_k]"].dropna()

        if len(all_rk_data) > 0:
            combined_save_path = os.path.join(dataset_output_folder, "ALL_FILES_COMBINED_Hist.png")
            create_histogram(
                all_rk_data,
                None,
                summary_columns,
                f"{HIST_COMBINED_TITLE_PREFIX} ({dataset_name.title()}){HIST_TITLE_SUFFIX}",
                combined_save_path,
            )

print(f"\nSUCCESS! All histograms saved to: {output_folder}")