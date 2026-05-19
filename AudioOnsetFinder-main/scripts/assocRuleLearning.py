"""Association Rule Learning (Apriori) on the extractor's rhythm-metrics workbook.

This is an **experimental** analysis step.  It is *not* trying to re-derive
onset timing — instead it treats the per-file rhythm metrics already
produced by the Onset Finder (nPVI, entropy, CV, mean IOI, onset count,
…) as categorical "items" and asks:

    "Which combinations of rhythm-metric bins reliably co-occur across
     recordings, and — when a group label is also attached — which bins
     are predictive of which group?"

Relevance to bioacoustics
-------------------------
Association rule mining is a descriptive data-mining technique
(Agrawal & Srikant 1994).  In a bioacoustics context the *items* are
discretised rhythm metrics (e.g. ``nPVI=high``) and per-file group
labels (e.g. ``Group=Chimp``).  The Apriori algorithm then discovers
*rules* of the form

    {Entropy=low, CV=low}  →  {Group=Chimp}

with three classical interest measures:

* **support**      P(X ∪ Y)  — how frequent the joint pattern is
* **confidence**   P(Y | X)  — how reliable the rule is
* **lift**         P(Y | X) / P(Y) — how much X boosts Y above baseline

It will not invent onsets; it is a lightweight exploratory summary of
the extractor's existing output.  Results are best used to generate
hypotheses ("groups differ mostly on entropy + CV") that can then be
tested with proper statistics.

Inputs
------
``Cross_Species_Rhythm_Data.xlsx`` — ``File Summaries`` sheet (produced
by Step 2, Onset Finder).

Outputs (written to ``Association_Rules/``)
-------------------------------------------
* ``README.txt``               — plain-English guide to every file
* ``summary.txt``              — plain-English top-N rules
* ``association_rules.csv``    — all rules passing the thresholds
* ``frequent_itemsets.csv``    — all frequent itemsets with support
* ``top_rules_bar.png``        — bar plot of the top-N rules by lift
* ``support_vs_confidence.png``— scatter plot (size = lift)
* ``rules_network.png``        — (optional) network diagram of top rules
"""

from __future__ import annotations

import json
import os
import re
import sys
from itertools import combinations, chain

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, os.path.join(_PROJECT_DIR, "scripts"))

try:
    from group_assignment import get_palette as _ga_get_palette  # noqa: E402
except Exception:
    _ga_get_palette = None

try:
    from group_assignment import merge_file_demographics as _ga_merge_demographics  # noqa: E402
except Exception:
    _ga_merge_demographics = None

try:
    from .shared_output_writers import save_matplotlib_figure, write_csv_dataframe, write_text_output
except ImportError:
    from shared_output_writers import save_matplotlib_figure, write_csv_dataframe, write_text_output


# ==========================================================================
# 1. CONFIGURATION (defaults — overridden by pipeline_config.json)
# ==========================================================================
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
excel_path = os.path.join(_PROJECT_DIR, "Cross_Species_Rhythm_Data.xlsx")
output_folder = os.path.join(_PROJECT_DIR, "Association_Rules")

# --- Data source ---
ARL_DATASET = "raw"  # "raw" or "stable"

# --- Feature selection (columns in the File Summaries sheet) ---
# Empty / missing values in any selected feature are dropped per file.
ARL_FEATURES = [
    "nPVI (Isochrony)",
    "r_k Entropy (Categorical Measure)",
    "CV of Intervals",
    "Mean IOI (ms)",
    "Total Onsets Used",
]

# --- Binning (how to turn numeric features into items) ---
ARL_BIN_METHOD = "quantile"   # "quantile" or "equal_width"
ARL_N_BINS = 3
ARL_BIN_LABELS = "low, medium, high"

# --- Group label (optional — also becomes an item) ---
ARL_INCLUDE_GROUP = True
ARL_GROUP_SOURCE = "filename_pattern"  # filename_pattern, mapping_csv, manual, excel_column
ARL_GROUP_PATTERN = r"(?P<group>[A-Za-z]+)_"
ARL_GROUP_CSV_PATH = ""
ARL_MANUAL_GROUPS = {}
ARL_GROUP_EXCEL_COLUMN = "Group"
ARL_UNGROUPED_LABEL = "Ungrouped"

# --- Apriori thresholds ---
ARL_MIN_SUPPORT = 0.15
ARL_MIN_CONFIDENCE = 0.60
ARL_MIN_LIFT = 1.10
ARL_MAX_ITEMSET_SIZE = 4

# --- Rule filtering ---
ARL_REQUIRE_GROUP_IN_CONSEQUENT = False  # if True, only rules predicting a Group=… item
ARL_TOP_N = 15  # used for plots

# --- Plot appearance ---
ARL_FIG_WIDTH = 12
ARL_FIG_HEIGHT = 7
ARL_DPI = 300
ARL_BG_COLOR = "#ffffff"
ARL_PALETTE = "viridis"              # sequential colormap for lift scale
ARL_BAR_PALETTE = "okabe-ito"        # categorical palette for top-N bars
ARL_TITLE_FONTSIZE = 15
ARL_AXIS_FONTSIZE = 12
ARL_TICK_FONTSIZE = 10

# --- Output format ---
ARL_OUTPUT_FORMAT = "png"     # png, svg, pdf, or png+svg
ARL_DRAW_NETWORK = True       # extra optional plot


# ==========================================================================
# 2. GUI CONFIG OVERRIDE
# ==========================================================================
_config_path = os.path.join(_PROJECT_DIR, "pipeline_config.json")
if os.path.isfile(_config_path):
    with open(_config_path) as _f:
        _cfg = json.load(_f).get("assoc_rule_learning", {})
    excel_path = _cfg.get("excel_path", excel_path)
    output_folder = _cfg.get("output_folder", output_folder)
    ARL_DATASET = _cfg.get("ARL_DATASET", ARL_DATASET)
    ARL_FEATURES = _cfg.get("ARL_FEATURES", ARL_FEATURES)
    ARL_BIN_METHOD = _cfg.get("ARL_BIN_METHOD", ARL_BIN_METHOD)
    ARL_N_BINS = _cfg.get("ARL_N_BINS", ARL_N_BINS)
    ARL_BIN_LABELS = _cfg.get("ARL_BIN_LABELS", ARL_BIN_LABELS)
    ARL_INCLUDE_GROUP = _cfg.get("ARL_INCLUDE_GROUP", ARL_INCLUDE_GROUP)
    ARL_GROUP_SOURCE = _cfg.get("ARL_GROUP_SOURCE", ARL_GROUP_SOURCE)
    ARL_GROUP_PATTERN = _cfg.get("ARL_GROUP_PATTERN", ARL_GROUP_PATTERN)
    ARL_GROUP_CSV_PATH = _cfg.get("ARL_GROUP_CSV_PATH", ARL_GROUP_CSV_PATH)
    ARL_MANUAL_GROUPS = _cfg.get("ARL_MANUAL_GROUPS", ARL_MANUAL_GROUPS)
    ARL_GROUP_EXCEL_COLUMN = _cfg.get("ARL_GROUP_EXCEL_COLUMN", ARL_GROUP_EXCEL_COLUMN)
    ARL_UNGROUPED_LABEL = _cfg.get("ARL_UNGROUPED_LABEL", ARL_UNGROUPED_LABEL)
    ARL_MIN_SUPPORT = _cfg.get("ARL_MIN_SUPPORT", ARL_MIN_SUPPORT)
    ARL_MIN_CONFIDENCE = _cfg.get("ARL_MIN_CONFIDENCE", ARL_MIN_CONFIDENCE)
    ARL_MIN_LIFT = _cfg.get("ARL_MIN_LIFT", ARL_MIN_LIFT)
    ARL_MAX_ITEMSET_SIZE = _cfg.get("ARL_MAX_ITEMSET_SIZE", ARL_MAX_ITEMSET_SIZE)
    ARL_REQUIRE_GROUP_IN_CONSEQUENT = _cfg.get(
        "ARL_REQUIRE_GROUP_IN_CONSEQUENT", ARL_REQUIRE_GROUP_IN_CONSEQUENT)
    ARL_TOP_N = _cfg.get("ARL_TOP_N", ARL_TOP_N)
    ARL_FIG_WIDTH = _cfg.get("ARL_FIG_WIDTH", ARL_FIG_WIDTH)
    ARL_FIG_HEIGHT = _cfg.get("ARL_FIG_HEIGHT", ARL_FIG_HEIGHT)
    ARL_DPI = _cfg.get("ARL_DPI", ARL_DPI)
    ARL_BG_COLOR = _cfg.get("ARL_BG_COLOR", ARL_BG_COLOR)
    ARL_PALETTE = _cfg.get("ARL_PALETTE", ARL_PALETTE)
    ARL_BAR_PALETTE = _cfg.get("ARL_BAR_PALETTE", ARL_BAR_PALETTE)
    ARL_TITLE_FONTSIZE = _cfg.get("ARL_TITLE_FONTSIZE", ARL_TITLE_FONTSIZE)
    ARL_AXIS_FONTSIZE = _cfg.get("ARL_AXIS_FONTSIZE", ARL_AXIS_FONTSIZE)
    ARL_TICK_FONTSIZE = _cfg.get("ARL_TICK_FONTSIZE", ARL_TICK_FONTSIZE)
    ARL_OUTPUT_FORMAT = _cfg.get("ARL_OUTPUT_FORMAT", ARL_OUTPUT_FORMAT)
    ARL_DRAW_NETWORK = _cfg.get("ARL_DRAW_NETWORK", ARL_DRAW_NETWORK)
    del _f, _cfg

os.makedirs(output_folder, exist_ok=True)


# ==========================================================================
# 3. LOAD DATA
# ==========================================================================
print("=" * 60)
print("  Association Rule Learning (Apriori)")
print("=" * 60)
print(f"Excel:  {excel_path}")
print(f"Output: {output_folder}")

if not os.path.isfile(excel_path):
    print(f"\nERROR: Excel workbook not found: {excel_path}")
    print("Run the Onset Finder (Step 2) first to generate the workbook.")
    sys.exit(1)

df_summary = pd.read_excel(excel_path, sheet_name="File Summaries")
if _ga_merge_demographics is not None:
    df_summary = _ga_merge_demographics(df_summary, excel_path)

# Swap nPVI / Entropy column according to dataset selection
if ARL_DATASET == "stable":
    _swap = {"nPVI (Isochrony)": "Stable Rhythm nPVI",
             "r_k Entropy (Categorical Measure)": "Stable Rhythm Entropy"}
    for i, col in enumerate(list(ARL_FEATURES)):
        if col in _swap and _swap[col] in df_summary.columns:
            ARL_FEATURES[i] = _swap[col]

missing = [c for c in ARL_FEATURES if c not in df_summary.columns]
if missing:
    print(f"\nERROR: Column(s) not found in File Summaries sheet: {missing}")
    print("Available columns:", list(df_summary.columns))
    sys.exit(1)

cols = ["File Name"] + [c for c in ARL_FEATURES if c in df_summary.columns]
df = df_summary[cols].copy()
for c in ARL_FEATURES:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df = df.dropna(subset=list(ARL_FEATURES))

if df.empty:
    print("\nERROR: No rows with valid values for all selected features.")
    sys.exit(1)

print(f"\nFiles with valid values: {len(df)}")
print(f"Features used: {ARL_FEATURES}")


# ==========================================================================
# 4. GROUP ASSIGNMENT (same 4 sources as nPVI_byGroup.py)
# ==========================================================================
def _assign_groups(df, source, pattern, csv_path, manual_map, ungrouped,
                   excel_column=None, df_summary=None):
    if source == "filename_pattern":
        try:
            rx = re.compile(pattern)
        except re.error as e:
            print(f"ERROR: Invalid group pattern: {e}")
            sys.exit(1)
        out = []
        for fname in df["File Name"]:
            m = rx.search(str(fname))
            out.append(m.group("group") if m and "group" in m.groupdict()
                       else ungrouped)
        df["Group"] = out
    elif source == "mapping_csv":
        if not csv_path or not os.path.isfile(csv_path):
            print(f"ERROR: Group mapping CSV not found: {csv_path}")
            sys.exit(1)
        m_df = pd.read_csv(csv_path)
        if "File Name" not in m_df or "Group" not in m_df:
            print("ERROR: Mapping CSV must have 'File Name' and 'Group' columns.")
            sys.exit(1)
        df["Group"] = df["File Name"].map(
            dict(zip(m_df["File Name"], m_df["Group"]))).fillna(ungrouped)
    elif source == "manual":
        df["Group"] = df["File Name"].map(manual_map).fillna(ungrouped)
    elif source == "excel_column":
        col = excel_column or "Group"
        if df_summary is not None and col in df_summary.columns:
            df["Group"] = df["File Name"].map(
                dict(zip(df_summary["File Name"],
                         df_summary[col].astype(str)))).fillna(ungrouped)
        else:
            print(f"ERROR: Column '{col}' not found in File Summaries sheet.")
            sys.exit(1)
    else:
        print(f"ERROR: Unknown ARL_GROUP_SOURCE '{source}'.")
        sys.exit(1)
    return df


if ARL_INCLUDE_GROUP:
    df = _assign_groups(df, ARL_GROUP_SOURCE, ARL_GROUP_PATTERN,
                        ARL_GROUP_CSV_PATH, ARL_MANUAL_GROUPS,
                        ARL_UNGROUPED_LABEL,
                        excel_column=ARL_GROUP_EXCEL_COLUMN,
                        df_summary=df_summary)
    print(f"Groups: {sorted(df['Group'].unique())}")


# ==========================================================================
# 5. DISCRETISATION → transactions
# ==========================================================================
labels = [s.strip() for s in ARL_BIN_LABELS.split(",") if s.strip()]
if len(labels) != ARL_N_BINS:
    # fall back to default labels
    labels = [f"bin{i + 1}" for i in range(ARL_N_BINS)]

transactions: list[set[str]] = []
# Short human-friendly feature names for items
_short_name = {
    "nPVI (Isochrony)": "nPVI",
    "Stable Rhythm nPVI": "nPVI",
    "r_k Entropy (Categorical Measure)": "Entropy",
    "Stable Rhythm Entropy": "Entropy",
    "CV of Intervals": "CV",
    "Mean IOI (ms)": "MeanIOI",
    "Total Onsets Used": "Onsets",
}

bin_edges_used: dict[str, np.ndarray] = {}
for feat in ARL_FEATURES:
    values = df[feat].to_numpy(dtype=float)
    if ARL_BIN_METHOD == "equal_width":
        edges = np.linspace(values.min(), values.max(), ARL_N_BINS + 1)
    else:
        qs = np.linspace(0.0, 1.0, ARL_N_BINS + 1)
        edges = np.quantile(values, qs)
    edges[0] -= 1e-9
    edges[-1] += 1e-9
    bin_edges_used[feat] = edges
    idx = np.clip(np.digitize(values, edges[1:-1], right=False),
                  0, ARL_N_BINS - 1)
    short = _short_name.get(feat, feat.split("(")[0].strip().replace(" ", ""))
    df[f"__item_{feat}"] = [f"{short}={labels[i]}" for i in idx]

for i, row in df.iterrows():
    t = {row[f"__item_{feat}"] for feat in ARL_FEATURES}
    if ARL_INCLUDE_GROUP:
        t.add(f"Group={row['Group']}")
    transactions.append(t)

n_tx = len(transactions)
print(f"\nTransactions: {n_tx}")
print("Sample items:", sorted(set().union(*transactions))[:10], "…")


# ==========================================================================
# 6. APRIORI — frequent itemset mining
# ==========================================================================
def _support(itemset, tx_list):
    s = frozenset(itemset)
    return sum(1 for t in tx_list if s.issubset(t)) / len(tx_list)


def apriori(tx_list, min_support, max_size):
    """Classic Apriori.  Returns dict(frozenset -> support)."""
    # 1-itemsets
    item_counts: dict[str, int] = {}
    for t in tx_list:
        for item in t:
            item_counts[item] = item_counts.get(item, 0) + 1
    L = {}
    freq_k = []
    for item, c in item_counts.items():
        sup = c / len(tx_list)
        if sup >= min_support:
            fs = frozenset([item])
            L[fs] = sup
            freq_k.append(fs)

    k = 2
    while freq_k and k <= max_size:
        # Generate candidates via k-1 prefix join
        candidates: set[frozenset] = set()
        freq_sorted = [tuple(sorted(s)) for s in freq_k]
        for i in range(len(freq_sorted)):
            for j in range(i + 1, len(freq_sorted)):
                a, b = freq_sorted[i], freq_sorted[j]
                if a[:-1] == b[:-1]:
                    cand = frozenset(a) | frozenset(b)
                    if len(cand) == k:
                        # Prune: all (k-1)-subsets must be frequent
                        if all(frozenset(sub) in L
                               for sub in combinations(cand, k - 1)):
                            candidates.add(cand)
        new_freq = []
        for c in candidates:
            sup = _support(c, tx_list)
            if sup >= min_support:
                L[c] = sup
                new_freq.append(c)
        freq_k = new_freq
        k += 1
    return L


print("\nRunning Apriori…")
itemsets = apriori(transactions, ARL_MIN_SUPPORT, ARL_MAX_ITEMSET_SIZE)
print(f"  frequent itemsets: {len(itemsets)} "
      f"(min_support={ARL_MIN_SUPPORT})")


# ==========================================================================
# 7. RULE GENERATION
# ==========================================================================
def _non_empty_proper_subsets(s):
    s = list(s)
    for r in range(1, len(s)):
        for combo in combinations(s, r):
            yield frozenset(combo)


def generate_rules(itemsets, min_confidence, min_lift,
                   require_group_consequent=False):
    rules = []
    for itemset, sup_xy in itemsets.items():
        if len(itemset) < 2:
            continue
        for ant in _non_empty_proper_subsets(itemset):
            cons = itemset - ant
            sup_x = itemsets.get(ant)
            sup_y = itemsets.get(cons)
            if sup_x is None or sup_y is None:
                continue
            conf = sup_xy / sup_x
            lift = conf / sup_y
            if conf < min_confidence or lift < min_lift:
                continue
            if require_group_consequent and not any(
                    i.startswith("Group=") for i in cons):
                continue
            rules.append({
                "antecedent": " & ".join(sorted(ant)),
                "consequent": " & ".join(sorted(cons)),
                "support": sup_xy,
                "confidence": conf,
                "lift": lift,
                "antecedent_support": sup_x,
                "consequent_support": sup_y,
                "size": len(itemset),
            })
    return rules


rules = generate_rules(itemsets, ARL_MIN_CONFIDENCE, ARL_MIN_LIFT,
                       ARL_REQUIRE_GROUP_IN_CONSEQUENT)
rules.sort(key=lambda r: (r["lift"], r["confidence"], r["support"]),
           reverse=True)
print(f"  rules: {len(rules)} "
      f"(min_confidence={ARL_MIN_CONFIDENCE}, min_lift={ARL_MIN_LIFT})")

rules_df = pd.DataFrame(rules)
items_df = pd.DataFrame([
    {"itemset": " & ".join(sorted(k)), "size": len(k), "support": v}
    for k, v in itemsets.items()
]).sort_values(["size", "support"], ascending=[True, False])

rules_csv = os.path.join(output_folder, "association_rules.csv")
items_csv = os.path.join(output_folder, "frequent_itemsets.csv")
write_csv_dataframe(rules_csv, rules_df, index=False)
write_csv_dataframe(items_csv, items_df, index=False)
print(f"  → {rules_csv}")
print(f"  → {items_csv}")

if rules_df.empty:
    print("\nNo rules passed the thresholds — try lowering min_support / "
          "min_confidence / min_lift.  Still wrote the frequent-itemsets CSV.")
    _empty_readme = (
        "ASSOCIATION RULE LEARNING — no rules passed the thresholds.\n\n"
        f"Tried {len(itemsets)} frequent itemsets across {n_tx} files.\n"
        f"Thresholds:  min_support ≥ {ARL_MIN_SUPPORT}, "
        f"min_confidence ≥ {ARL_MIN_CONFIDENCE}, min_lift ≥ {ARL_MIN_LIFT}.\n\n"
        "Try lowering them, adding more features, or using fewer bins.\n"
    )
    write_text_output(os.path.join(output_folder, "README.txt"), _empty_readme)
    sys.exit(0)


# ==========================================================================
# 8. PLOTS
# ==========================================================================
def _save(fig, stem):
    fmt = ARL_OUTPUT_FORMAT.lower()
    exts = []
    if "png" in fmt:
        exts.append("png")
    if "svg" in fmt:
        exts.append("svg")
    if "pdf" in fmt:
        exts.append("pdf")
    if not exts:
        exts = ["png"]
    for ext in exts:
        p = os.path.join(output_folder, f"{stem}.{ext}")
        save_matplotlib_figure(fig, p, dpi=ARL_DPI, facecolor=ARL_BG_COLOR, bbox_inches="tight")
        print(f"  → {p}")
    plt.close(fig)


def _palette(n):
    try:
        cmap = plt.get_cmap(ARL_PALETTE)
    except ValueError:
        cmap = plt.get_cmap("viridis")
    return [cmap(i / max(n - 1, 1)) for i in range(n)]


def _bar_palette(n):
    """Categorical palette for the top-N bar plot.

    Uses the shared Okabe-Ito-aware get_palette when available,
    falls back to recycling viridis-equivalent spread otherwise."""
    if _ga_get_palette is not None:
        return _ga_get_palette(ARL_BAR_PALETTE, n)
    return _palette(n)


# -- 8a. Top-N bar plot (by lift) --
top = rules_df.head(ARL_TOP_N)
fig, ax = plt.subplots(figsize=(ARL_FIG_WIDTH, ARL_FIG_HEIGHT),
                       facecolor=ARL_BG_COLOR,
                       constrained_layout=True)
ax.set_facecolor(ARL_BG_COLOR)
y = np.arange(len(top))
ax.barh(y, top["lift"].values, color=_bar_palette(len(top)), edgecolor="black",
        linewidth=0.5)
for i, (_, row) in enumerate(top.iterrows()):
    ax.text(row["lift"] + 0.02, i,
            f"conf={row['confidence']:.2f}  sup={row['support']:.2f}",
            va="center", fontsize=ARL_TICK_FONTSIZE - 1)
labels_y = [f"{r['antecedent']}  ⇒  {r['consequent']}"
            for _, r in top.iterrows()]
ax.set_yticks(y)
ax.set_yticklabels(labels_y, fontsize=ARL_TICK_FONTSIZE)
ax.invert_yaxis()
ax.axvline(1.0, color="#888", lw=0.8, ls="--", label="lift = 1 (chance)")
ax.set_xlabel("Lift  (how many times more often the rule appears than chance)",
              fontsize=ARL_AXIS_FONTSIZE)
ax.set_title(f"Top {len(top)} Association Rules (by Lift)",
             fontsize=ARL_TITLE_FONTSIZE, pad=10)
ax.tick_params(axis="x", labelsize=ARL_TICK_FONTSIZE)
ax.grid(True, axis="x", linestyle=":", alpha=0.5)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

# Caption / legend box beneath the plot
_caption = (
    "How to read this plot:\n"
    "  • Each row is one rule in the form  IF (antecedent)  ⇒  THEN (consequent).\n"
    "  • Bar length = LIFT — how many times more often the pattern occurs than if the two sides\n"
    "    were unrelated. Dashed vertical line at lift = 1 marks the 'no better than chance' baseline.\n"
    "  • Numbers next to each bar: conf = confidence (reliability, 0–1), sup = support (frequency, 0–1)."
)
fig.text(0.01, -0.02, _caption, ha="left", va="top",
         fontsize=ARL_TICK_FONTSIZE - 1, family="monospace",
         bbox=dict(boxstyle="round,pad=0.5", facecolor="#f5f5f0",
                   edgecolor="#999999", linewidth=0.6))
_save(fig, "top_rules_bar")


# -- 8b. Support vs Confidence scatter, coloured by lift --
fig, ax = plt.subplots(figsize=(ARL_FIG_WIDTH, ARL_FIG_HEIGHT),
                       facecolor=ARL_BG_COLOR,
                       constrained_layout=True)
ax.set_facecolor(ARL_BG_COLOR)
sc = ax.scatter(rules_df["support"], rules_df["confidence"],
                c=rules_df["lift"], cmap=ARL_PALETTE,
                s=40 + 30 * (rules_df["size"] - 1),
                edgecolors="black", linewidths=0.4, alpha=0.85)
cb = fig.colorbar(sc, ax=ax)
cb.set_label("Lift (higher = more informative)", fontsize=ARL_AXIS_FONTSIZE)
ax.set_xlabel("Support  (fraction of files showing this pattern)",
              fontsize=ARL_AXIS_FONTSIZE)
ax.set_ylabel("Confidence  (P(THEN | IF) — reliability of the rule)",
              fontsize=ARL_AXIS_FONTSIZE)
ax.set_title("Association Rules — Support vs Confidence (size = rule size)",
             fontsize=ARL_TITLE_FONTSIZE, pad=10)
ax.tick_params(labelsize=ARL_TICK_FONTSIZE)
ax.grid(True, alpha=0.35, linestyle=":")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

_caption = (
    "How to read this plot:\n"
    "  • Every dot is one association rule.\n"
    "  • X-axis (support): how often the full pattern appears in your data (0 = never, 1 = every file).\n"
    "  • Y-axis (confidence): if the IF-side is present, how often does the THEN-side follow? (0–1)\n"
    "  • Colour (lift): how much the rule beats random chance. Bright = highly informative.\n"
    "  • Marker size: total items in the rule (bigger = more complex combination).\n"
    "  • Rules in the upper-right corner are both frequent AND reliable — the most trustworthy ones."
)
fig.text(0.01, -0.02, _caption, ha="left", va="top",
         fontsize=ARL_TICK_FONTSIZE - 1, family="monospace",
         bbox=dict(boxstyle="round,pad=0.5", facecolor="#f5f5f0",
                   edgecolor="#999999", linewidth=0.6))
_save(fig, "support_vs_confidence")


# -- 8c. Simple network diagram of top rules (no networkx dependency) --
if ARL_DRAW_NETWORK:
    top = rules_df.head(ARL_TOP_N)
    # Collect unique nodes
    nodes = set()
    for _, r in top.iterrows():
        for item in chain(r["antecedent"].split(" & "),
                          r["consequent"].split(" & ")):
            nodes.add(item.strip())
    nodes = sorted(nodes)
    # Circular layout
    theta = np.linspace(0, 2 * np.pi, len(nodes), endpoint=False)
    pos = {n: (np.cos(t), np.sin(t)) for n, t in zip(nodes, theta)}

    fig, ax = plt.subplots(figsize=(ARL_FIG_WIDTH, ARL_FIG_WIDTH),
                           facecolor=ARL_BG_COLOR)
    ax.set_facecolor(ARL_BG_COLOR)
    ax.set_aspect("equal")
    ax.axis("off")

    # Draw edges
    lifts = top["lift"].to_numpy()
    lift_range = float(lifts.max() - lifts.min())
    lift_norm = (lifts - lifts.min()) / max(lift_range, 1e-9)
    cmap = plt.get_cmap(ARL_PALETTE)
    for (_, r), ln in zip(top.iterrows(), lift_norm):
        ants = [a.strip() for a in r["antecedent"].split(" & ")]
        cons = [c.strip() for c in r["consequent"].split(" & ")]
        for a in ants:
            for c in cons:
                x0, y0 = pos[a]
                x1, y1 = pos[c]
                ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                            arrowprops=dict(arrowstyle="->",
                                            color=cmap(float(ln)),
                                            lw=0.6 + 2.2 * float(ln),
                                            alpha=0.75))

    # Draw nodes
    for n, (x, y) in pos.items():
        is_group = n.startswith("Group=")
        ax.scatter([x], [y], s=280 if is_group else 180,
                   color="#ffcc66" if is_group else "#cce5ff",
                   edgecolors="black", linewidths=0.7, zorder=3)
        ax.text(x * 1.12, y * 1.12, n, ha="center", va="center",
                fontsize=ARL_TICK_FONTSIZE,
                fontweight="bold" if is_group else "normal",
                zorder=4)

    ax.set_title(f"Rule Network (Top {len(top)} rules)",
                 fontsize=ARL_TITLE_FONTSIZE, pad=10)
    ax.set_xlim(-1.4, 1.4)
    ax.set_ylim(-1.4, 1.4)

    # On-plot legend (inside figure — network plot has no spare axes)
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    legend_handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#cce5ff",
               markeredgecolor="black", markersize=10,
               label="Rhythm-metric item (e.g. nPVI=high)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#ffcc66",
               markeredgecolor="black", markersize=12,
               label="Group label (e.g. Group=Chimp)"),
        Line2D([0], [0], color=cmap(0.9), lw=2.6,
               label="Arrow IF → THEN  (thicker / brighter = higher lift)"),
    ]
    ax.legend(handles=legend_handles, loc="lower center",
              bbox_to_anchor=(0.5, -0.05), ncol=1, frameon=True,
              fontsize=ARL_TICK_FONTSIZE)

    _caption = (
        "How to read this plot:\n"
        "  • Dots are items; arrows point from an IF-item to a THEN-item in a rule.\n"
        "  • Thick bright arrows = rules with the highest lift (most informative).\n"
        "  • Hubs with many incoming arrows are strongly predicted items (often Group labels)."
    )
    fig.text(0.01, -0.02, _caption, ha="left", va="top",
             fontsize=ARL_TICK_FONTSIZE - 1, family="monospace",
             bbox=dict(boxstyle="round,pad=0.5", facecolor="#f5f5f0",
                       edgecolor="#999999", linewidth=0.6))
    _save(fig, "rules_network")


print("\nSUCCESS — Association rule learning complete.")
print(f"All outputs in: {output_folder}")


# ==========================================================================
# 9. PLAIN-ENGLISH README + SUMMARY
# ==========================================================================
def _rule_to_english(r):
    """Translate one rule row into a plain-English sentence."""
    ant = r["antecedent"].replace(" & ", " and ")
    cons = r["consequent"].replace(" & ", " and ")
    sup = r["support"] * 100
    conf = r["confidence"] * 100
    lift = r["lift"]
    # Friendlier wording when the consequent is a single Group=… item
    cons_items = r["consequent"].split(" & ")
    if len(cons_items) == 1 and cons_items[0].startswith("Group="):
        grp = cons_items[0].split("=", 1)[1]
        return (f"When files show  {ant}, they are "
                f"{grp} recordings "
                f"{conf:.0f}% of the time "
                f"(seen in {sup:.0f}% of the corpus; "
                f"lift = {lift:.2f}× vs. chance).")
    return (f"When files show  {ant}, they also show  {cons} "
            f"{conf:.0f}% of the time "
            f"(seen in {sup:.0f}% of the corpus; "
            f"lift = {lift:.2f}× vs. chance).")


# ---- README ----
_readme = f"""\
================================================================
  ASSOCIATION RULE LEARNING  —  Output Guide
================================================================

WHAT IS THIS?
-------------
Association Rule Learning (the "Apriori" algorithm) looks at the
rhythm metrics of every recording you processed and asks:

    "Which combinations of metric bins tend to show up together?"

Every file is first described as a small list of "items", for
example:  nPVI=high, Entropy=low, CV=medium, Group=Chimp.
Apriori then hunts for rules of the form

    IF {{Entropy=low, CV=low}}   THEN  {{Group=Chimp}}

and scores each rule with three classic numbers.


THE THREE NUMBERS YOU NEED TO KNOW
----------------------------------
  SUPPORT     — how OFTEN the rule appears in your data.
                 0.30 = the full pattern was present in 30 % of files.
                 Higher = more common.  Low support = rare pattern.

  CONFIDENCE  — how RELIABLE the rule is (a probability).
                 0.80 = "when the IF-part is true, the THEN-part is
                 also true 80 % of the time."
                 Higher = more dependable.

  LIFT        — how much the rule beats CHANCE.
                  = 1.0   no better than random
                  > 1.0   informative (above baseline)
                  > 2.0   strongly informative
                  < 1.0   the two sides actually AVOID each other


FILES IN THIS FOLDER
--------------------
  README.txt                 This guide.

  summary.txt                Top-{ARL_TOP_N} rules translated into
                             plain English sentences, so you can
                             read them without opening the CSV.

  association_rules.csv      Every rule that passed your thresholds,
                             sorted by lift (highest first).
                             Columns:
                               antecedent           IF-side items
                               consequent           THEN-side items
                               support              frequency of full pattern
                               confidence           P(THEN | IF)
                               lift                 confidence / baseline
                               antecedent_support   frequency of IF-side alone
                               consequent_support   frequency of THEN-side alone
                               size                 total items in rule

  frequent_itemsets.csv      Every item COMBINATION that met
                             min_support — raw building blocks for
                             the rules.  Columns: itemset, size, support.

  top_rules_bar.png          Horizontal bar chart of the top-{ARL_TOP_N}
                             rules ranked by LIFT.  Dashed vertical
                             line at lift = 1 is the "chance" baseline.
                             Numbers beside each bar are the rule's
                             confidence and support.

  support_vs_confidence.png  Scatter of EVERY rule.  X = support,
                             Y = confidence, colour = lift, marker
                             size grows with rule complexity.
                             Upper-right corner = frequent AND reliable.

  rules_network.png          (optional) Circular diagram of the
                             top-{ARL_TOP_N} rules.  Blue dots are rhythm-
                             metric items, yellow dots are Group
                             labels, arrows point IF → THEN.  Arrow
                             thickness and colour encode lift.


HOW THIS RUN WAS CONFIGURED
---------------------------
  Dataset                : {ARL_DATASET}
  Features              : {', '.join(ARL_FEATURES)}
  Binning method         : {ARL_BIN_METHOD}  ({ARL_N_BINS} bins: {ARL_BIN_LABELS})
  Group item included    : {ARL_INCLUDE_GROUP}
  Group source           : {ARL_GROUP_SOURCE}
  min_support            : {ARL_MIN_SUPPORT}
  min_confidence         : {ARL_MIN_CONFIDENCE}
  min_lift               : {ARL_MIN_LIFT}
  max_itemset_size       : {ARL_MAX_ITEMSET_SIZE}
  require_group_consequent : {ARL_REQUIRE_GROUP_IN_CONSEQUENT}

  Files mined            : {n_tx}
  Frequent itemsets      : {len(itemsets)}
  Rules kept             : {len(rules)}


HOW TO READ A RULE IN PLAIN ENGLISH
-----------------------------------
  "Group=Whale  ⇒  CV=high & Entropy=high   (sup=0.29, conf=1.00, lift=3.5)"

  ➜  "When a file is a Whale recording (29 % of the corpus), it
       ALWAYS ends up with high CV AND high entropy.  That joint
       pattern is 3.5× more common in whales than would be expected
       if the two were unrelated."


TROUBLESHOOTING
---------------
  • Too many rules?       Raise min_support, min_confidence, or min_lift.
  • Too few rules?        Lower them — or add more features / bins.
  • Rules all look same?  Two features may be perfectly correlated
                          in your data; try dropping one.
  • Nothing interesting?  Check that the Group source produced more
                          than one group label (see "Groups: …" in
                          the run log).
"""

write_text_output(os.path.join(output_folder, "README.txt"), _readme)
print(f"  → {os.path.join(output_folder, 'README.txt')}")


# ---- summary.txt ----
_summary_lines = [
    "================================================================",
    "  ASSOCIATION RULE LEARNING  —  Plain-English Summary",
    "================================================================",
    "",
    f"Files mined:          {n_tx}",
    f"Frequent itemsets:    {len(itemsets)}",
    f"Rules kept:           {len(rules)}",
    "",
    "Thresholds used:",
    f"    support    ≥ {ARL_MIN_SUPPORT}",
    f"    confidence ≥ {ARL_MIN_CONFIDENCE}",
    f"    lift       ≥ {ARL_MIN_LIFT}",
    "",
    f"TOP {min(ARL_TOP_N, len(rules))} RULES (by lift):",
    "----------------------------------------------------------------",
    "",
]
for i, (_, r) in enumerate(rules_df.head(ARL_TOP_N).iterrows(), start=1):
    _summary_lines.append(f"{i:>2}. {_rule_to_english(r)}")
    _summary_lines.append("")
_summary_lines += [
    "----------------------------------------------------------------",
    "See README.txt for a full explanation of support / confidence /",
    "lift and a guide to every file in this folder.",
]
write_text_output(os.path.join(output_folder, "summary.txt"), "\n".join(_summary_lines))
print(f"  → {os.path.join(output_folder, 'summary.txt')}")
