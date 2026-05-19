"""Mantel tests (Category C2).

Compares pairwise distance matrices derived from per-group (or per-file)
rhythmic, geographic, and linguistic/phylogenetic data using:

- Two-matrix Mantel test (r_M, permutation p).
- Partial Mantel test holding a third matrix constant.

Geographic distance can be computed from lat/lon columns (haversine) or
supplied as a precomputed CSV. Phylogenetic distance comes from a
precomputed matrix CSV or (optionally) a Newick tree via ``dendropy`` /
``ete3`` if available.

Outputs:
- ``mantel_results.csv``: each pair of matrices, r, p, n.
- ``distance_matrices/*.csv``: the actual matrices used.
- ``mantel_scatter_<pair>.png`` for each pair of matrices compared.
"""

from __future__ import annotations

import json
import math
import os
import sys
from itertools import combinations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, os.path.join(_PROJECT_DIR, "scripts"))

from group_assignment import ensure_output_folder, get_palette, load_file_summaries, save_figure, write_csv_dataframe  # noqa: E402

excel_path = os.path.join(_PROJECT_DIR, "Cross_Species_Rhythm_Data.xlsx")
output_folder = os.path.join(_PROJECT_DIR, "Mantel_Test")

MANTEL_DATASET = "raw"
MANTEL_UNIT_COLUMN = "Group"
MANTEL_RHYTHM_METRIC = "nPVI"        # "nPVI"|"entropy"|"CV"|"mean_IOI"|"euclidean_multivar"
MANTEL_RHYTHM_MULTIVAR_COLS = [
    "nPVI (Isochrony)", "CV of Intervals",
    "r_k Entropy (Categorical Measure)", "Mean IOI (ms)",
]
MANTEL_AGGREGATE_BY_UNIT = "mean"    # "mean" | "median"

MANTEL_GEOGRAPHIC_SOURCE = "lat_lon_columns"  # "lat_lon_columns" | "precomputed_matrix_csv"
MANTEL_GEO_LAT_COLUMN = "Latitude"
MANTEL_GEO_LON_COLUMN = "Longitude"
MANTEL_GEO_DISTANCE = "haversine_km"   # "haversine_km" | "euclidean"
MANTEL_GEO_MATRIX_CSV = ""

MANTEL_PHYLO_SOURCE = "precomputed_matrix_csv"  # "precomputed_matrix_csv" | "newick_tree" | "skip"
MANTEL_PHYLO_PATH = ""

MANTEL_TEST_MODE = "two_matrix"       # "two_matrix" | "partial"
MANTEL_CORRELATION = "pearson"        # "pearson" | "spearman"
MANTEL_N_PERMUTATIONS = 999
MANTEL_RANDOM_SEED = 42
MANTEL_ALTERNATIVE = "greater"        # "greater" | "two-sided"

# Plot
MANTEL_FIG_WIDTH = 7.5
MANTEL_FIG_HEIGHT = 6
MANTEL_DPI = 300
MANTEL_TITLE = "Mantel Scatter"
MANTEL_BG_COLOR = "#ffffff"
MANTEL_OUTPUT_FORMAT = "png"
MANTEL_PALETTE = "okabe-ito"  # colorblind-friendly default
MANTEL_MIN_UNITS = 4          # Minimum units required for a meaningful Mantel test
MANTEL_SHOW_FIT_LINE = True   # Overlay OLS regression on scatter

_cfg_path = os.path.join(_PROJECT_DIR, "pipeline_config.json")
if os.path.isfile(_cfg_path):
    with open(_cfg_path) as _f:
        _cfg = json.load(_f).get("mantel_test", {})
    excel_path = _cfg.get("excel_path", excel_path)
    output_folder = _cfg.get("output_folder", output_folder)
    for _k in list(globals().keys()):
        if _k.startswith("MANTEL_") and _k in _cfg:
            globals()[_k] = _cfg[_k]
    del _f, _cfg

ensure_output_folder(output_folder)
ensure_output_folder(os.path.join(output_folder, "distance_matrices"))

print(f"[mantelTest] Loading {excel_path}...")
df_summary = load_file_summaries(excel_path)

if MANTEL_UNIT_COLUMN not in df_summary.columns:
    print(f"ERROR: Unit column '{MANTEL_UNIT_COLUMN}' missing.")
    sys.exit(1)

# Drop rows with missing unit labels
_before = len(df_summary)
df_summary = df_summary.dropna(subset=[MANTEL_UNIT_COLUMN]).copy()
df_summary[MANTEL_UNIT_COLUMN] = df_summary[MANTEL_UNIT_COLUMN].astype(str)
if len(df_summary) < _before:
    print(f"[mantelTest] dropped {_before - len(df_summary)} rows with missing '{MANTEL_UNIT_COLUMN}'.")

_n_units_total = df_summary[MANTEL_UNIT_COLUMN].nunique()
if _n_units_total < MANTEL_MIN_UNITS:
    print(f"ERROR: only {_n_units_total} unique unit(s) in '{MANTEL_UNIT_COLUMN}'; "
          f"need ≥ {MANTEL_MIN_UNITS} for a Mantel test. "
          f"Aggregate onset data with more than one group before running.")
    sys.exit(1)

# ------------------------------------------------------------------
# Aggregate rhythmic data per unit
# ------------------------------------------------------------------
metric_map = {
    "nPVI": "nPVI (Isochrony)",
    "entropy": "r_k Entropy (Categorical Measure)",
    "CV": "CV of Intervals",
    "mean_IOI": "Mean IOI (ms)",
}

agg_fn = np.nanmean if MANTEL_AGGREGATE_BY_UNIT == "mean" else np.nanmedian

if MANTEL_RHYTHM_METRIC == "euclidean_multivar":
    cols = [c for c in MANTEL_RHYTHM_MULTIVAR_COLS if c in df_summary.columns]
    if len(cols) < 2:
        print("ERROR: Need at least 2 multivar columns present.")
        sys.exit(1)
    agg = df_summary.groupby(MANTEL_UNIT_COLUMN)[cols].agg(agg_fn)
    # standardize each col
    agg = (agg - agg.mean(axis=0)) / (agg.std(axis=0, ddof=0) + 1e-12)
    units = agg.index.tolist()
    # Euclidean between rows
    rhy_d = np.sqrt(((agg.values[:, None, :] - agg.values[None, :, :]) ** 2).sum(axis=2))
else:
    col = metric_map.get(MANTEL_RHYTHM_METRIC)
    if col is None or col not in df_summary.columns:
        print(f"ERROR: Rhythm metric column '{col}' not found.")
        sys.exit(1)
    agg = df_summary.groupby(MANTEL_UNIT_COLUMN)[col].agg(agg_fn)
    units = agg.index.tolist()
    vals = agg.values
    rhy_d = np.abs(vals[:, None] - vals[None, :])

rhy_df = pd.DataFrame(rhy_d, index=units, columns=units)
write_csv_dataframe(os.path.join(output_folder, "distance_matrices", "rhythmic.csv"), rhy_df, index=True)


# ------------------------------------------------------------------
# Geographic distance
# ------------------------------------------------------------------
def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _build_geo_matrix(df_summary, units):
    if MANTEL_GEOGRAPHIC_SOURCE == "precomputed_matrix_csv":
        if not MANTEL_GEO_MATRIX_CSV or not os.path.isfile(MANTEL_GEO_MATRIX_CSV):
            print("WARNING: Geo matrix CSV missing; skipping geographic matrix.")
            return None
        m = pd.read_csv(MANTEL_GEO_MATRIX_CSV, index_col=0)
        m = m.reindex(index=units, columns=units)
        return m.values
    lat_col = MANTEL_GEO_LAT_COLUMN
    lon_col = MANTEL_GEO_LON_COLUMN
    if lat_col not in df_summary.columns or lon_col not in df_summary.columns:
        print(f"WARNING: lat/lon columns ({lat_col},{lon_col}) missing; skipping geographic matrix.")
        return None
    latlon = df_summary.groupby(MANTEL_UNIT_COLUMN)[[lat_col, lon_col]].agg("mean")
    latlon = latlon.reindex(units)
    if latlon.isna().any().any():
        print("WARNING: Some units lack lat/lon; skipping geographic matrix.")
        return None
    n = len(units)
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            if MANTEL_GEO_DISTANCE == "haversine_km":
                d = _haversine_km(latlon.iloc[i, 0], latlon.iloc[i, 1],
                                  latlon.iloc[j, 0], latlon.iloc[j, 1])
            else:
                d = np.sqrt((latlon.iloc[i, 0] - latlon.iloc[j, 0]) ** 2 +
                            (latlon.iloc[i, 1] - latlon.iloc[j, 1]) ** 2)
            D[i, j] = D[j, i] = d
    return D


geo_d = _build_geo_matrix(df_summary, units)
if geo_d is not None:
    write_csv_dataframe(
        os.path.join(output_folder, "distance_matrices", "geographic.csv"),
        pd.DataFrame(geo_d, index=units, columns=units),
        index=True,
    )


# ------------------------------------------------------------------
# Phylogenetic / linguistic distance
# ------------------------------------------------------------------
def _build_phylo_matrix(units):
    src = MANTEL_PHYLO_SOURCE
    if src == "skip" or not MANTEL_PHYLO_PATH:
        return None
    if src == "precomputed_matrix_csv":
        if not os.path.isfile(MANTEL_PHYLO_PATH):
            print(f"WARNING: phylo matrix CSV not found: {MANTEL_PHYLO_PATH}")
            return None
        m = pd.read_csv(MANTEL_PHYLO_PATH, index_col=0)
        m = m.reindex(index=units, columns=units)
        return m.values
    if src == "newick_tree":
        try:
            import dendropy
        except ImportError:
            print("WARNING: dendropy not installed; skipping newick_tree source.")
            return None
        if not os.path.isfile(MANTEL_PHYLO_PATH):
            print(f"WARNING: newick tree not found: {MANTEL_PHYLO_PATH}")
            return None
        tree = dendropy.Tree.get(path=MANTEL_PHYLO_PATH, schema="newick")
        pdm = tree.phylogenetic_distance_matrix()
        taxa = {t.label: t for t in tree.taxon_namespace}
        D = np.full((len(units), len(units)), np.nan)
        for i, u in enumerate(units):
            for j, v in enumerate(units):
                if u in taxa and v in taxa:
                    D[i, j] = pdm.distance(taxa[u], taxa[v])
        return D
    print(f"WARNING: Unknown MANTEL_PHYLO_SOURCE '{src}'.")
    return None


phylo_d = _build_phylo_matrix(units)
if phylo_d is not None:
    write_csv_dataframe(
        os.path.join(output_folder, "distance_matrices", "phylogenetic.csv"),
        pd.DataFrame(phylo_d, index=units, columns=units),
        index=True,
    )


# ------------------------------------------------------------------
# Mantel helpers
# ------------------------------------------------------------------
def _upper_tri(D):
    iu = np.triu_indices_from(D, k=1)
    return D[iu]


def _corr(a, b, method):
    # drop NaNs pairwise
    mask = ~(np.isnan(a) | np.isnan(b))
    if mask.sum() < 3:
        return np.nan
    if method == "spearman":
        from scipy.stats import spearmanr
        return float(spearmanr(a[mask], b[mask]).correlation)
    return float(np.corrcoef(a[mask], b[mask])[0, 1])


def _mantel(A, B, n_perm, alt, method, seed):
    n = A.shape[0]
    a = _upper_tri(A)
    b = _upper_tri(B)
    r_obs = _corr(a, b, method)
    rng = np.random.default_rng(int(seed))
    perm_r = np.zeros(int(n_perm))
    for k in range(int(n_perm)):
        idx = rng.permutation(n)
        Bp = B[np.ix_(idx, idx)]
        perm_r[k] = _corr(a, _upper_tri(Bp), method)
    if alt == "two-sided":
        p = (np.sum(np.abs(perm_r) >= abs(r_obs)) + 1) / (len(perm_r) + 1)
    else:
        p = (np.sum(perm_r >= r_obs) + 1) / (len(perm_r) + 1)
    return r_obs, float(p)


def _partial_mantel(A, B, C, n_perm, alt, method, seed):
    """Partial Mantel of A & B controlling for C."""
    a = _upper_tri(A); b = _upper_tri(B); c = _upper_tri(C)
    mask = ~(np.isnan(a) | np.isnan(b) | np.isnan(c))
    a, b, c = a[mask], b[mask], c[mask]
    if len(a) < 5:
        return np.nan, np.nan
    # residualize a and b on c
    def _resid(x, z):
        slope = np.cov(x, z, ddof=0)[0, 1] / (np.var(z) + 1e-12)
        intercept = x.mean() - slope * z.mean()
        return x - (slope * z + intercept)
    a_r = _resid(a, c)
    b_r = _resid(b, c)
    r_obs = _corr(a_r, b_r, method)

    n = A.shape[0]
    rng = np.random.default_rng(int(seed))
    perm_r = np.zeros(int(n_perm))
    for k in range(int(n_perm)):
        idx = rng.permutation(n)
        Bp = B[np.ix_(idx, idx)]
        b_p = _upper_tri(Bp)[mask]
        b_pr = _resid(b_p, c)
        perm_r[k] = _corr(a_r, b_pr, method)
    if alt == "two-sided":
        p = (np.sum(np.abs(perm_r) >= abs(r_obs)) + 1) / (len(perm_r) + 1)
    else:
        p = (np.sum(perm_r >= r_obs) + 1) / (len(perm_r) + 1)
    return r_obs, float(p)


matrices = {"rhythmic": rhy_d}
if geo_d is not None:
    matrices["geographic"] = geo_d
if phylo_d is not None:
    matrices["phylogenetic"] = phylo_d

if len(matrices) < 2:
    print("ERROR: Need at least 2 distance matrices (rhythmic + one of geo/phylo). "
          "Provide geographic and/or phylogenetic inputs.")
    sys.exit(1)

rows = []
for (n1, M1), (n2, M2) in combinations(matrices.items(), 2):
    r, p = _mantel(M1, M2, MANTEL_N_PERMUTATIONS, MANTEL_ALTERNATIVE,
                   MANTEL_CORRELATION, MANTEL_RANDOM_SEED)
    rows.append({"test": "mantel", "matrix_a": n1, "matrix_b": n2,
                 "controlling_for": "", "r": r, "p": p,
                 "n_units": len(units),
                 "n_permutations": int(MANTEL_N_PERMUTATIONS)})

if MANTEL_TEST_MODE == "partial" and len(matrices) >= 3:
    mat_items = list(matrices.items())
    names = [n for n, _ in mat_items]
    for (i, j) in combinations(range(len(mat_items)), 2):
        for k in range(len(mat_items)):
            if k == i or k == j:
                continue
            n1, M1 = mat_items[i]
            n2, M2 = mat_items[j]
            n3, M3 = mat_items[k]
            r, p = _partial_mantel(M1, M2, M3, MANTEL_N_PERMUTATIONS,
                                   MANTEL_ALTERNATIVE, MANTEL_CORRELATION,
                                   MANTEL_RANDOM_SEED)
            rows.append({"test": "partial_mantel",
                         "matrix_a": n1, "matrix_b": n2,
                         "controlling_for": n3,
                         "r": r, "p": p,
                         "n_units": len(units),
                         "n_permutations": int(MANTEL_N_PERMUTATIONS)})

res_df = pd.DataFrame(rows)
write_csv_dataframe(os.path.join(output_folder, "mantel_results.csv"), res_df, index=False)
print(res_df.to_string(index=False))

# Scatter plots for each pair (two-matrix only)
_palette = get_palette(MANTEL_PALETTE, max(3, len(matrices)))
_pair_results = {(r["matrix_a"], r["matrix_b"]): (r["r"], r["p"])
                 for r in rows if r["test"] == "mantel"}

for idx, ((n1, M1), (n2, M2)) in enumerate(combinations(matrices.items(), 2)):
    fig, ax = plt.subplots(figsize=(MANTEL_FIG_WIDTH, MANTEL_FIG_HEIGHT),
                           facecolor=MANTEL_BG_COLOR,
                           constrained_layout=True)
    a = _upper_tri(M1); b = _upper_tri(M2)
    mask = ~(np.isnan(a) | np.isnan(b))
    a_v, b_v = a[mask], b[mask]
    color = _palette[idx % len(_palette)]
    ax.scatter(a_v, b_v, alpha=0.75, edgecolor="black", linewidth=0.6,
               color=color, s=55, zorder=3)
    if MANTEL_SHOW_FIT_LINE and len(a_v) >= 3 and np.std(a_v) > 0:
        slope, intercept = np.polyfit(a_v, b_v, 1)
        xline = np.linspace(a_v.min(), a_v.max(), 100)
        ax.plot(xline, slope * xline + intercept, color="#333333",
                linestyle="--", linewidth=1.4, zorder=2, label="OLS fit")
    r, p = _pair_results.get((n1, n2), (_corr(a, b, MANTEL_CORRELATION), np.nan))
    ax.set_xlabel(f"{n1} distance")
    ax.set_ylabel(f"{n2} distance")
    ax.set_title(f"{MANTEL_TITLE}: {n1} vs {n2}")
    annot = (f"Mantel $r$ = {r:.3f}\n"
             f"$p$ = {p:.3g}  ({int(MANTEL_N_PERMUTATIONS)} perms)\n"
             f"$n$ units = {len(units)},  pairs = {len(a_v)}")
    ax.text(0.02, 0.98, annot, transform=ax.transAxes,
            ha="left", va="top", fontsize=10,
            bbox=dict(boxstyle="round,pad=0.4",
                      facecolor="white", edgecolor="#cccccc", alpha=0.9))
    ax.grid(True, linestyle=":", alpha=0.55)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save_figure(fig, output_folder, f"mantel_scatter_{n1}_vs_{n2}",
                fmt=MANTEL_OUTPUT_FORMAT, dpi=int(MANTEL_DPI))
    plt.close(fig)

print(f"[mantelTest] done. Results in {output_folder}")
