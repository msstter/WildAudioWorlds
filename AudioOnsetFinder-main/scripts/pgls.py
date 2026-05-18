"""Phylogenetic Generalized Least Squares (Category D1).

Regresses a species-mean rhythmic trait on ecological / allometric
predictors while accounting for phylogenetic non-independence via a
user-supplied variance-covariance matrix.

Construction:
- Per-unit (default "Species") aggregation of the response column.
- Optional standardization of continuous predictors.
- Variance-covariance matrix V built from:
    * a precomputed CSV matrix (``PGLS_TREE_SOURCE = "vcv_matrix_csv"``), OR
    * a Newick tree (``PGLS_TREE_SOURCE = "newick_file"``) using dendropy's
      phylogenetic distance matrix → V constructed as shared branch length
      under Brownian motion; Pagel's λ rescales off-diagonals.
- Generalized least squares with the chosen V: β = (X' V⁻¹ X)⁻¹ X' V⁻¹ y.
- Pagel's λ either fixed or grid-searched by profile likelihood.

Requires at least one of: ``dendropy``, ``ete3``, or a precomputed CSV.
Falls back to OLS with a warning if nothing is available.

Outputs:
- ``pgls_summary.txt``
- ``pgls_coefficients.csv``
- ``pgls_lambda.csv``
- ``pgls_residuals.png``
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

from group_assignment import ensure_output_folder, get_palette, load_file_summaries, save_figure  # noqa: E402

excel_path = os.path.join(_PROJECT_DIR, "Cross_Species_Rhythm_Data.xlsx")
output_folder = os.path.join(_PROJECT_DIR, "PGLS")

PGLS_RESPONSE = "nPVI (Isochrony)"
PGLS_PREDICTORS = ["BodyMass_kg", "Tempo_BPM"]
PGLS_UNIT_COLUMN = "Species"
PGLS_TREE_SOURCE = "vcv_matrix_csv"   # "vcv_matrix_csv" | "newick_file"
PGLS_TREE_PATH = ""
PGLS_CORRELATION_MODEL = "pagel_lambda"  # "brownian" | "pagel_lambda" | "ornstein_uhlenbeck"
PGLS_ESTIMATE_LAMBDA = True
PGLS_FIXED_LAMBDA = 1.0
PGLS_STANDARDIZE_CONTINUOUS = True
PGLS_ENGINE = "numpy_gls"             # "numpy_gls" | "rpy2_caper"
PGLS_CONFIDENCE_LEVEL = 0.95
PGLS_DROP_MISSING_TIPS = True

# Plot
PGLS_FIG_WIDTH = 9
PGLS_FIG_HEIGHT = 6
PGLS_DPI = 300
PGLS_TITLE = "PGLS — phylogenetically-corrected regression"
PGLS_BG_COLOR = "#ffffff"
PGLS_OUTPUT_FORMAT = "png"
PGLS_PALETTE = "okabe-ito"

_cfg_path = os.path.join(_PROJECT_DIR, "pipeline_config.json")
if os.path.isfile(_cfg_path):
    with open(_cfg_path) as _f:
        _cfg = json.load(_f).get("pgls", {})
    excel_path = _cfg.get("excel_path", excel_path)
    output_folder = _cfg.get("output_folder", output_folder)
    for _k in list(globals().keys()):
        if _k.startswith("PGLS_") and _k in _cfg:
            globals()[_k] = _cfg[_k]
    del _f, _cfg

ensure_output_folder(output_folder)

print(f"[pgls] Loading {excel_path}...")
df = load_file_summaries(excel_path)

if PGLS_UNIT_COLUMN not in df.columns:
    print(f"ERROR: Unit column '{PGLS_UNIT_COLUMN}' missing.")
    sys.exit(1)
if PGLS_RESPONSE not in df.columns:
    print(f"ERROR: Response column '{PGLS_RESPONSE}' missing.")
    sys.exit(1)

predictors = [c for c in PGLS_PREDICTORS if c in df.columns]
missing = [c for c in PGLS_PREDICTORS if c not in df.columns]
if missing:
    print(f"WARNING: Missing predictors (dropped): {missing}")
if not predictors:
    print("ERROR: No usable predictors.")
    sys.exit(1)

# Aggregate per unit
for c in [PGLS_RESPONSE] + predictors:
    df[c] = pd.to_numeric(df[c], errors="coerce")
agg = df.groupby(PGLS_UNIT_COLUMN)[[PGLS_RESPONSE] + predictors].mean()
agg = agg.dropna()
units = agg.index.tolist()
print(f"[pgls] n_units={len(units)}")
if len(units) < 3:
    print("ERROR: Need at least 3 units.")
    sys.exit(1)

if PGLS_STANDARDIZE_CONTINUOUS:
    for c in predictors:
        sd = agg[c].std(ddof=0)
        if sd > 0:
            agg[c] = (agg[c] - agg[c].mean()) / sd


# ------------------------------------------------------------------
# Build VCV matrix V
# ------------------------------------------------------------------
def _vcv_from_csv(path, units):
    if not os.path.isfile(path):
        return None
    m = pd.read_csv(path, index_col=0)
    inter = [u for u in units if u in m.index and u in m.columns]
    if len(inter) < 3:
        return None
    return m.reindex(index=inter, columns=inter).values, inter


def _vcv_from_newick(path, units):
    try:
        import dendropy
    except ImportError:
        print("WARNING: dendropy not installed; cannot parse newick_file.")
        return None
    if not os.path.isfile(path):
        return None
    tree = dendropy.Tree.get(path=path, schema="newick")
    pdm = tree.phylogenetic_distance_matrix()
    taxa = {t.label: t for t in tree.taxon_namespace}
    avail = [u for u in units if u in taxa]
    n = len(avail)
    if n < 3:
        return None
    # Brownian VCV: V[i,j] = shared branch length from root to MRCA(i,j).
    # Approximated as (total_height - 0.5 * distance(i,j)) assuming ultrametric.
    root_dist = np.array([tree.max_distance_from_root() for _ in avail])
    D = np.zeros((n, n))
    for i, ti in enumerate(avail):
        for j, tj in enumerate(avail):
            D[i, j] = pdm.distance(taxa[ti], taxa[tj])
    V = root_dist[:, None] - 0.5 * D
    return V, avail


V = None
used_units = units
if PGLS_TREE_SOURCE == "vcv_matrix_csv":
    out = _vcv_from_csv(PGLS_TREE_PATH, units)
elif PGLS_TREE_SOURCE == "newick_file":
    out = _vcv_from_newick(PGLS_TREE_PATH, units)
else:
    out = None

if out is not None:
    V, used_units = out
else:
    print("WARNING: No phylogenetic VCV available; PGLS will degenerate to OLS.")
    V = np.eye(len(units))
    used_units = units

# Drop agg rows not in used_units
agg = agg.loc[used_units]
y = agg[PGLS_RESPONSE].values
X = np.column_stack([np.ones(len(agg)), agg[predictors].values])
n, p = X.shape

# ------------------------------------------------------------------
# Pagel's lambda transformation
# ------------------------------------------------------------------
def _apply_lambda(V, lam):
    V_lam = V.copy().astype(float)
    diag = np.diag(V_lam).copy()
    V_lam *= lam
    np.fill_diagonal(V_lam, diag)
    return V_lam


def _gls_fit(X, y, V):
    # Regularise
    V_reg = V + 1e-8 * np.eye(V.shape[0])
    try:
        Vinv = np.linalg.pinv(V_reg)
    except np.linalg.LinAlgError:
        Vinv = np.linalg.pinv(V_reg + 1e-4 * np.eye(V_reg.shape[0]))
    XtVinv = X.T @ Vinv
    cov_beta = np.linalg.pinv(XtVinv @ X)
    beta = cov_beta @ XtVinv @ y
    resid = y - X @ beta
    n_obs = len(y)
    p_pred = X.shape[1]
    # Unbiased σ² (for inference); ML σ² = r'V⁻¹r / n (for profile likelihood)
    rVr = float(resid @ Vinv @ resid)
    sigma2 = rVr / max(n_obs - p_pred, 1)
    sigma2_ml = rVr / n_obs
    cov_beta = cov_beta * sigma2
    # Profile log-likelihood for MVN with covariance σ²·V; σ² profiled out at ML.
    # ll(λ) = -0.5 [ n·log(2π) + n·log(σ²_ML) + log|V| + n ]
    sign, logdet = np.linalg.slogdet(V_reg)
    if sign <= 0:
        logdet = float(np.log(np.abs(np.linalg.det(V_reg)) + 1e-300))
    ll = -0.5 * (n_obs * np.log(2 * np.pi)
                 + n_obs * np.log(max(sigma2_ml, 1e-300))
                 + logdet
                 + n_obs)
    return beta, cov_beta, sigma2, ll


if PGLS_CORRELATION_MODEL == "pagel_lambda" and PGLS_ESTIMATE_LAMBDA:
    # 1D grid search
    lams = np.linspace(0.0, 1.0, 21)
    best = (-np.inf, 0.0, None)
    for lam in lams:
        V_lam = _apply_lambda(V, lam)
        try:
            beta, cov, sig2, ll = _gls_fit(X, y, V_lam)
        except Exception:
            continue
        if ll > best[0]:
            best = (ll, lam, (beta, cov, sig2))
    best_lam = best[1]
    beta, cov_beta, sigma2 = best[2]
    print(f"[pgls] Estimated Pagel's λ = {best_lam:.3f}")
elif PGLS_CORRELATION_MODEL == "brownian":
    best_lam = 1.0
    beta, cov_beta, sigma2, _ = _gls_fit(X, y, V)
else:
    best_lam = float(PGLS_FIXED_LAMBDA)
    beta, cov_beta, sigma2, _ = _gls_fit(X, y, _apply_lambda(V, best_lam))

se = np.sqrt(np.diag(cov_beta))
# t-ratio with n-p df
from scipy.stats import t as student_t
dof = max(len(y) - p, 1)
tvals = beta / (se + 1e-12)
pvals = 2.0 * student_t.sf(np.abs(tvals), dof)  # sf avoids underflow for large |t|
conf_z = student_t.ppf(1 - (1 - float(PGLS_CONFIDENCE_LEVEL)) / 2, dof)
ci_low = beta - conf_z * se
ci_high = beta + conf_z * se

term_names = ["Intercept"] + predictors
coef_df = pd.DataFrame({
    "term": term_names,
    "estimate": beta,
    "std_err": se,
    "t": tvals,
    "p_value": pvals,
    "ci_low": ci_low,
    "ci_high": ci_high,
})
coef_df.to_csv(os.path.join(output_folder, "pgls_coefficients.csv"), index=False)
pd.DataFrame([{"correlation_model": PGLS_CORRELATION_MODEL,
               "lambda": best_lam,
               "sigma2": float(sigma2),
               "n_units": len(used_units),
               "units_used": ", ".join(map(str, used_units))}]).to_csv(
    os.path.join(output_folder, "pgls_lambda.csv"), index=False)

with open(os.path.join(output_folder, "pgls_summary.txt"), "w") as fh:
    fh.write("=== PGLS summary ===\n")
    fh.write(f"Response: {PGLS_RESPONSE}\n")
    fh.write(f"Predictors: {predictors}\n")
    fh.write(f"Unit: {PGLS_UNIT_COLUMN}; n={len(used_units)}\n")
    fh.write(f"Correlation: {PGLS_CORRELATION_MODEL}, lambda={best_lam:.4f}\n")
    fh.write(f"sigma^2 = {sigma2:.4f}\n\n")
    fh.write(coef_df.to_string(index=False))
    fh.write("\n")

# ---- Figures ----
_pal = get_palette(PGLS_PALETTE, 3)
_blue, _vermillion = _pal[0], _pal[1]


def _sig_stars(p):
    if p is None or np.isnan(p):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "n.s."


# Forest plot of fixed effects (dropping intercept)
cdf_plot = coef_df[coef_df["term"] != "Intercept"].reset_index(drop=True)
if len(cdf_plot):
    fig, ax = plt.subplots(figsize=(PGLS_FIG_WIDTH, max(2.8, 0.55 * len(cdf_plot) + 1.0)),
                           facecolor=PGLS_BG_COLOR, constrained_layout=True)
    yloc = np.arange(len(cdf_plot))
    colors = [_vermillion if (pd.notna(pv) and pv < 0.05) else _blue
              for pv in cdf_plot["p_value"]]
    for yi, row, col in zip(yloc, cdf_plot.itertuples(index=False), colors):
        ax.plot([row.ci_low, row.ci_high], [yi, yi], color=col,
                linewidth=2.2, solid_capstyle="round", zorder=2)
        ax.plot([row.estimate], [yi], marker="o", color=col,
                markersize=9, markeredgecolor="black", markeredgewidth=0.6, zorder=3)
    ax.axvline(0, color="#555555", linestyle="--", linewidth=1.2, zorder=1)
    xmax = ax.get_xlim()[1]
    for yi, row in zip(yloc, cdf_plot.itertuples(index=False)):
        txt = f"{_sig_stars(row.p_value)}  p={row.p_value:.3g}"
        ax.text(xmax, yi, "  " + txt, va="center", ha="left", fontsize=9, color="#333333")
    ax.set_yticks(yloc)
    ax.set_yticklabels(cdf_plot["term"])
    ax.invert_yaxis()
    ax.set_xlabel(f"Coefficient estimate ({int(round(PGLS_CONFIDENCE_LEVEL*100))}% CI)")
    ax.set_title(f"{PGLS_TITLE}\nλ={best_lam:.3f}, σ²={sigma2:.3g}, n units={len(used_units)}")
    ax.grid(True, axis="x", linestyle=":", alpha=0.55)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save_figure(fig, output_folder, "pgls_forest",
                fmt=PGLS_OUTPUT_FORMAT, dpi=int(PGLS_DPI))
    plt.close(fig)

# Residual diagnostic (fitted-vs-residual + QQ)
fitted = X @ beta
resid = y - fitted
fig, axes = plt.subplots(1, 2, figsize=(PGLS_FIG_WIDTH, 4.2),
                          facecolor=PGLS_BG_COLOR, constrained_layout=True)
ax = axes[0]
ax.scatter(fitted, resid, color=_blue, edgecolor="black", linewidth=0.5, s=55, alpha=0.85)
ax.axhline(0, color="#555555", linestyle="--", linewidth=1.0)
ax.set_xlabel("Fitted")
ax.set_ylabel("Residual")
ax.set_title("Residual vs fitted")
ax.grid(True, linestyle=":", alpha=0.55)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

ax = axes[1]
if len(resid) >= 3:
    from scipy.stats import probplot
    probplot(resid, dist="norm", plot=ax)
    ax.get_lines()[0].set_markerfacecolor(_blue)
    ax.get_lines()[0].set_markeredgecolor("black")
    ax.get_lines()[0].set_markersize(5)
    ax.get_lines()[1].set_color("#555555")
    ax.get_lines()[1].set_linestyle("--")
ax.set_title("Normal QQ of residuals")
ax.grid(True, linestyle=":", alpha=0.55)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
fig.suptitle(f"PGLS diagnostics (λ={best_lam:.3f})")
save_figure(fig, output_folder, "pgls_residuals",
            fmt=PGLS_OUTPUT_FORMAT, dpi=int(PGLS_DPI))
plt.close(fig)

# Pagel's lambda profile plot (if estimated)
if PGLS_CORRELATION_MODEL == "pagel_lambda" and PGLS_ESTIMATE_LAMBDA:
    try:
        prof_lams = np.linspace(0.0, 1.0, 41)
        prof_lls = []
        for lam in prof_lams:
            try:
                _, _, _, ll = _gls_fit(X, y, _apply_lambda(V, lam))
                prof_lls.append(ll)
            except Exception:
                prof_lls.append(np.nan)
        fig, ax = plt.subplots(figsize=(PGLS_FIG_WIDTH, 4.0),
                               facecolor=PGLS_BG_COLOR, constrained_layout=True)
        ax.plot(prof_lams, prof_lls, color=_blue, linewidth=1.8, zorder=2)
        ax.axvline(best_lam, color=_vermillion, linestyle="--", linewidth=1.5,
                   label=f"λ̂ = {best_lam:.3f}", zorder=3)
        ax.set_xlabel("Pagel's λ")
        ax.set_ylabel("Profile log-likelihood")
        ax.set_title("λ profile likelihood")
        ax.grid(True, linestyle=":", alpha=0.55)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.legend(loc="lower right", frameon=False)
        save_figure(fig, output_folder, "pgls_lambda_profile",
                    fmt=PGLS_OUTPUT_FORMAT, dpi=int(PGLS_DPI))
        plt.close(fig)
    except Exception as _le:
        print(f"[pgls] lambda profile plot skipped: {_le}")

print(f"[pgls] done. Results in {output_folder}")
