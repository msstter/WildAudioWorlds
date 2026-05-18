"""One-sample Wilcoxon signed-rank test for isochrony preference (Category A3).

For each group (or per-file), test whether the proportion of rhythm ratios
r_k falling inside the isochronous band differs from mathematical chance
(= band width under a Uniform null). Uses scipy.stats.wilcoxon with a
per-file paired-difference formulation when ``WIL_UNIT="per_file"``.

Outputs:
- ``wilcoxon_isochrony_results.csv``
- bar plot of per-group isochrony proportion with chance line
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
output_folder = os.path.join(_PROJECT_DIR, "Wilcoxon_Isochrony")

WIL_DATASET = "raw"
WIL_GROUP_SOURCE = "filename_pattern"
WIL_GROUP_PATTERN = r"(?P<group>[A-Za-z]+)_"
WIL_GROUP_CSV_PATH = ""
WIL_MANUAL_GROUPS: dict = {}
WIL_GROUP_EXCEL_COLUMN = "Group"
WIL_UNGROUPED_LABEL = "Ungrouped"
WIL_GROUP_ORDER = ""

# Step-specific
WIL_ISOCHRONOUS_BAND_LOW = 0.45
WIL_ISOCHRONOUS_BAND_HIGH = 0.55
WIL_CHANCE_LEVEL = -1.0       # -1.0 → derive from band width
WIL_UNIT = "per_file"          # "per_file" | "per_bout"
WIL_ALTERNATIVE = "greater"    # "greater" | "two-sided" | "less"
WIL_MULTIPLE_COMPARISONS = "none"
WIL_ALPHA = 0.05
WIL_MIN_EVENTS_PER_UNIT = 5

# Generic plot settings
WIL_FIG_WIDTH = 10
WIL_FIG_HEIGHT = 6
WIL_DPI = 300
WIL_PALETTE = "Set2"
WIL_TITLE = "Isochrony Preference per Group"
WIL_BG_COLOR = "#ffffff"
WIL_OUTPUT_FORMAT = "png"

_cfg_path = os.path.join(_PROJECT_DIR, "pipeline_config.json")
if os.path.isfile(_cfg_path):
    with open(_cfg_path) as _f:
        _cfg = json.load(_f).get("wilcoxon_isochrony", {})
    excel_path = _cfg.get("excel_path", excel_path)
    output_folder = _cfg.get("output_folder", output_folder)
    for _k in list(globals().keys()):
        if _k.startswith("WIL_") and _k in _cfg:
            globals()[_k] = _cfg[_k]
    del _f, _cfg

ensure_output_folder(output_folder)

# Load data
print(f"[wilcoxonIsochrony] Loading {excel_path} ({WIL_DATASET} dataset)...")
df_summary = load_file_summaries(excel_path)
df_events = load_dyadic_events(excel_path, dataset=WIL_DATASET)

# Locate the r_k column (accepts Onset Finder's "Rhythm Ratio [r_k]" plus
# legacy / abbreviated spellings).
_R_CANDIDATES = (
    "Rhythm Ratio [r_k]", "Rhythm Ratio (r_k)",
    "r_k", "r (Rhythm Ratio)", "Rhythm Ratio", "r",
)
r_col = next((c for c in _R_CANDIDATES if c in df_events.columns), None)
if r_col is None:
    r_col = next((c for c in df_events.columns if "r_k" in str(c).lower()), None)
if r_col is None:
    print("ERROR: r_k column not found.")
    print("Available columns:", list(df_events.columns))
    sys.exit(1)
print(f"[wilcoxonIsochrony] using column '{r_col}' for r_k.")

df = df_events[["File Name", r_col]].copy()
df[r_col] = pd.to_numeric(df[r_col], errors="coerce")
_n_raw = len(df)
df = df.dropna(subset=[r_col])
# r_k is bounded on the open interval (0, 1); exclude anything outside
# so the "chance = band_width" derivation from the Uniform null holds.
df = df[(df[r_col] > 0.0) & (df[r_col] < 1.0)]
_n_dropped = _n_raw - len(df)
if _n_dropped:
    print(f"[wilcoxonIsochrony] dropped {_n_dropped} NaN / out-of-range rows "
          f"(kept {len(df)}).")
df = assign_groups(
    df, source=WIL_GROUP_SOURCE, pattern=WIL_GROUP_PATTERN,
    csv_path=WIL_GROUP_CSV_PATH, manual_map=WIL_MANUAL_GROUPS,
    ungrouped=WIL_UNGROUPED_LABEL, excel_column=WIL_GROUP_EXCEL_COLUMN,
    df_summary=df_summary)
groups = order_groups(df, WIL_GROUP_ORDER)

band_low = float(WIL_ISOCHRONOUS_BAND_LOW)
band_high = float(WIL_ISOCHRONOUS_BAND_HIGH)
chance = float(WIL_CHANCE_LEVEL)
if chance < 0:
    chance = band_high - band_low   # uniform-null expectation

# Compute per-unit isochronous proportions. Only per_file aggregation
# is currently supported; per_bout / per_individual would require extra
# columns that the Onset Finder doesn't yet export.
if WIL_UNIT != "per_file":
    print(f"[wilcoxonIsochrony] WARNING: WIL_UNIT='{WIL_UNIT}' not implemented; "
          "falling back to per_file aggregation.")
unit_col = "File Name"
df["_iso"] = ((df[r_col] >= band_low) & (df[r_col] <= band_high)).astype(int)

_min_ev = int(WIL_MIN_EVENTS_PER_UNIT)
_rng = np.random.default_rng(42)

rows = []
per_file_props = {}  # group -> np.ndarray of per-file proportions (for plot)
for g in groups:
    sub = df[df["Group"] == g]
    per_unit = sub.groupby(unit_col).agg(
        n_events=(r_col, "size"),
        prop_iso=("_iso", "mean"))
    per_unit = per_unit[per_unit["n_events"] >= _min_ev]
    props = per_unit["prop_iso"].to_numpy(dtype=float)
    per_file_props[g] = props

    if len(props) < 1:
        rows.append({"Group": g, "n_units": 0, "mean_prop": np.nan,
                     "sd_prop": np.nan, "ci_lo": np.nan, "ci_hi": np.nan,
                     "chance": chance, "V": np.nan, "p": np.nan})
        continue

    # Wilcoxon signed-rank on (prop_iso - chance)
    diffs = props - chance
    if np.all(diffs == 0) or len(diffs) < 2:
        V, p = np.nan, np.nan
    else:
        try:
            res = stats.wilcoxon(diffs, alternative=WIL_ALTERNATIVE,
                                 zero_method="wilcox")
            V, p = float(res.statistic), float(res.pvalue)
        except ValueError as e:
            print(f"[wilcoxonIsochrony] {g}: wilcoxon error: {e}")
            V, p = np.nan, np.nan

    # 95% bootstrap CI of the mean (percentile method, 2000 resamples).
    if len(props) >= 2:
        boot_means = _rng.choice(props, size=(2000, len(props)),
                                 replace=True).mean(axis=1)
        ci_lo = float(np.percentile(boot_means, 2.5))
        ci_hi = float(np.percentile(boot_means, 97.5))
    else:
        ci_lo = ci_hi = float(props[0])

    rows.append({
        "Group": g, "n_units": int(len(props)),
        "mean_prop": float(np.mean(props)),
        "sd_prop": float(np.std(props, ddof=1)) if len(props) > 1 else np.nan,
        "ci_lo": ci_lo, "ci_hi": ci_hi,
        "chance": chance, "V": V, "p": p,
    })

res_df = pd.DataFrame(rows)

# Multiple-comparisons correction (re-use ksTest pattern)
if WIL_MULTIPLE_COMPARISONS != "none":
    pvals = res_df["p"].values
    mask = ~np.isnan(pvals)
    m = int(mask.sum())
    padj = np.full_like(pvals, np.nan, dtype=float)
    if m > 0:
        if WIL_MULTIPLE_COMPARISONS == "bonferroni":
            padj[mask] = np.clip(pvals[mask] * m, 0, 1)
        elif WIL_MULTIPLE_COMPARISONS == "fdr_bh":
            p_sub = pvals[mask]
            order = np.argsort(p_sub)
            ranked = p_sub[order]
            adj = ranked * m / (np.arange(m) + 1)
            adj = np.minimum.accumulate(adj[::-1])[::-1]
            adj = np.clip(adj, 0, 1)
            out = np.empty_like(adj)
            out[order] = adj
            padj[mask] = out
    res_df["p_adj"] = padj
    _pcol = "p_adj"
else:
    _pcol = "p"

_alpha = float(WIL_ALPHA)
_pvals = res_df[_pcol].to_numpy(dtype=float)
res_df["significant"] = np.where(
    np.isnan(_pvals), pd.NA, _pvals < _alpha,
)

csv_path = os.path.join(output_folder, "wilcoxon_isochrony_results.csv")
res_df.to_csv(csv_path, index=False)
print(f"[wilcoxonIsochrony] wrote {csv_path}")
print(res_df.to_string(index=False))

# ----------------------------------------------------------------------
# Plot: per-group bar of mean isochronous proportion, with
#   - 95% bootstrap CI as error bars (not SD — matches CSV)
#   - per-file points jittered behind bars (shows the raw distribution
#     the Wilcoxon test actually consumed)
#   - chance line with axis-side label
#   - significance tiers (*, **, ***) above each bar
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


def _sig_stars(p):
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


colors = _resolve_palette(WIL_PALETTE, len(groups))
fig, ax = plt.subplots(figsize=(float(WIL_FIG_WIDTH), float(WIL_FIG_HEIGHT)),
                       facecolor=WIL_BG_COLOR, constrained_layout=True)
x = np.arange(len(groups))

means = res_df.set_index("Group").loc[groups, "mean_prop"].to_numpy(dtype=float)
ci_lo = res_df.set_index("Group").loc[groups, "ci_lo"].to_numpy(dtype=float)
ci_hi = res_df.set_index("Group").loc[groups, "ci_hi"].to_numpy(dtype=float)
# Asymmetric error bars: [mean - ci_lo, ci_hi - mean].
err_lo = np.where(np.isnan(means), 0.0, means - ci_lo)
err_hi = np.where(np.isnan(means), 0.0, ci_hi - means)
err = np.vstack([np.nan_to_num(err_lo, nan=0.0),
                 np.nan_to_num(err_hi, nan=0.0)])

safe_means = np.nan_to_num(means, nan=0.0)
bars = ax.bar(x, safe_means, yerr=err,
              color=colors, alpha=0.85,
              edgecolor="black", linewidth=0.8, capsize=4,
              error_kw=dict(ecolor="#333333", lw=1.2),
              zorder=2)

# Per-file jittered points.
jitter_rng = np.random.default_rng(0)
for xi, g in enumerate(groups):
    pts = per_file_props.get(g, np.array([]))
    if len(pts) == 0:
        continue
    jitter = jitter_rng.uniform(-0.12, 0.12, size=len(pts))
    ax.scatter(np.full_like(pts, xi, dtype=float) + jitter, pts,
               s=16, color="#1a1a1a", alpha=0.45,
               edgecolor="white", linewidth=0.3, zorder=3)

# Chance reference line with axis-side label.
ax.axhline(chance, color="#D55E00", linestyle="--", linewidth=1.2,
           zorder=1, label=f"Chance = {chance:.3f} (Uniform null)")

# X-tick labels including per-group n_units.
xtick_labels = []
for g in groups:
    row = res_df.set_index("Group").loc[g]
    n_u = int(row["n_units"]) if not pd.isna(row["n_units"]) else 0
    xtick_labels.append(f"{g}\n(n={n_u})")
ax.set_xticks(x)
ax.set_xticklabels(xtick_labels, rotation=0)

ax.set_ylabel("Per-file proportion in isochronous band "
              rf"$[{band_low:g}, {band_high:g}]$", fontsize=11)
ax.set_title(WIL_TITLE, fontsize=13)
ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5)
ax.set_axisbelow(True)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)

# Y-axis: span 0 to the higher of 1 or the top CI.
top_data = np.nanmax(np.concatenate([safe_means + err_hi,
                                     np.concatenate(list(per_file_props.values()))
                                     if per_file_props else np.array([0.0])]))
ax.set_ylim(0.0, min(1.05, max(1.0, float(top_data) * 1.12)))

# Significance annotations above the upper CI.
pcol_vals = res_df.set_index("Group").loc[groups, _pcol].to_numpy(dtype=float)
for xi, (mean_val, hi_err, p_val) in enumerate(
        zip(safe_means, err_hi, pcol_vals)):
    stars = _sig_stars(p_val)
    if stars:
        y = min(1.02, mean_val + (hi_err if not np.isnan(hi_err) else 0) + 0.03)
        ax.text(xi, y, stars, ha="center", va="bottom",
                fontsize=14, fontweight="bold", color="#000000")

ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0),
          frameon=False, fontsize=9, borderaxespad=0.0)

save_figure(fig, output_folder, "wilcoxon_isochrony_bar",
            fmt=WIL_OUTPUT_FORMAT, dpi=int(WIL_DPI))
plt.close(fig)
print("[wilcoxonIsochrony] done.")
