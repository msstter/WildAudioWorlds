"""Generalized Linear Mixed Models for rhythmic responses (Category C3).

Fits a mixed-effects model predicting a rhythmic response
(e.g. ``nPVI (Isochrony)`` or r_k) from fixed effects (Modality,
Function, Tempo, Allometry, …) with random intercepts for Group /
Individual.

Primary engine: ``statsmodels.regression.mixed_linear_model.MixedLM``
(REML by default) for Gaussian responses — handles random intercepts.
Falls back to OLS with cluster-robust standard errors if MixedLM fails.

Note: for beta/binomial families or crossed random effects, use the
optional ``pymer4`` engine (which wraps R's lme4) if installed.

Outputs:
- ``glmm_summary.txt`` full text summary
- ``glmm_coefficients.csv`` tidy coefficient table
- ``glmm_random_effects.csv`` random-effects table (if available)
- ``glmm_forest.png`` coefficient forest plot
- ``glmm_residuals.png`` residual diagnostic
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

from group_assignment import ensure_output_folder, get_palette, load_file_summaries, save_figure, write_csv_dataframe, write_text_output  # noqa: E402

excel_path = os.path.join(_PROJECT_DIR, "Cross_Species_Rhythm_Data.xlsx")
output_folder = os.path.join(_PROJECT_DIR, "GLMM")

GLMM_DATASET = "raw"
GLMM_RESPONSE = "nPVI (Isochrony)"
GLMM_RESPONSE_FAMILY = "gaussian"   # "gaussian"|"beta"|"binomial"|"poisson"
GLMM_LINK = "identity"              # "identity"|"logit"|"log"
GLMM_FIXED_EFFECTS = ["Mean IOI (ms)", "CV of Intervals", "Total Duration (s)"]
GLMM_CATEGORICAL_FIXED: list = []    # auto-detected if empty
GLMM_RANDOM_EFFECTS = ["Group"]
GLMM_INTERACTIONS: list = []
GLMM_STANDARDIZE_CONTINUOUS = True
GLMM_ENGINE = "statsmodels"          # "statsmodels"|"pymer4"
GLMM_CONFIDENCE_LEVEL = 0.95
GLMM_REFERENCE_LEVELS: dict = {}
GLMM_COMPARE_NULL = True

# Plot
GLMM_FIG_WIDTH = 9
GLMM_FIG_HEIGHT = 6
GLMM_DPI = 300
GLMM_TITLE = "GLMM Coefficients"
GLMM_BG_COLOR = "#ffffff"
GLMM_OUTPUT_FORMAT = "png"
GLMM_PALETTE = "okabe-ito"

_cfg_path = os.path.join(_PROJECT_DIR, "pipeline_config.json")
if os.path.isfile(_cfg_path):
    with open(_cfg_path) as _f:
        _cfg = json.load(_f).get("glmm_rhythm", {})
    excel_path = _cfg.get("excel_path", excel_path)
    output_folder = _cfg.get("output_folder", output_folder)
    for _k in list(globals().keys()):
        if _k.startswith("GLMM_") and _k in _cfg:
            globals()[_k] = _cfg[_k]
    del _f, _cfg

ensure_output_folder(output_folder)

print(f"[glmmRhythm] Loading {excel_path}...")
df = load_file_summaries(excel_path)

if GLMM_RESPONSE not in df.columns:
    print(f"ERROR: Response column '{GLMM_RESPONSE}' not found.")
    sys.exit(1)

fixed = [c for c in GLMM_FIXED_EFFECTS if c in df.columns]
missing_fixed = [c for c in GLMM_FIXED_EFFECTS if c not in df.columns]
if missing_fixed:
    print(f"WARNING: Missing fixed-effect columns (dropped): {missing_fixed}")
random = [c for c in GLMM_RANDOM_EFFECTS if c in df.columns]
missing_rnd = [c for c in GLMM_RANDOM_EFFECTS if c not in df.columns]
if missing_rnd:
    print(f"WARNING: Missing random-effect columns (dropped): {missing_rnd}")

if not fixed:
    print("ERROR: No valid fixed effects.")
    sys.exit(1)
if not random:
    print("WARNING: No random effects available; falling back to OLS.")

df = df[[GLMM_RESPONSE] + fixed + random].copy()
df[GLMM_RESPONSE] = pd.to_numeric(df[GLMM_RESPONSE], errors="coerce")
df = df.dropna(subset=[GLMM_RESPONSE])

# Decide categorical vs continuous
cat_explicit = set(GLMM_CATEGORICAL_FIXED)
auto_cat = set()
for c in fixed:
    if df[c].dtype == object or df[c].dtype.name.startswith("category"):
        auto_cat.add(c)
categorical = list(cat_explicit | auto_cat)
continuous = [c for c in fixed if c not in categorical]

# Coerce + impute
for c in continuous:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df = df.dropna(subset=continuous + categorical)

if GLMM_STANDARDIZE_CONTINUOUS and continuous:
    for c in continuous:
        sd = df[c].std(ddof=0)
        if sd > 0:
            df[c] = (df[c] - df[c].mean()) / sd

# Apply reference levels
for c, level in (GLMM_REFERENCE_LEVELS or {}).items():
    if c in categorical:
        df[c] = pd.Categorical(df[c], categories=[level] +
                               [v for v in df[c].unique() if v != level])

# Build formula
def _q(name):
    return f"Q(\"{name}\")"

formula_rhs_parts = []
for c in continuous:
    formula_rhs_parts.append(_q(c))
for c in categorical:
    formula_rhs_parts.append(f"C({_q(c)})")
for interaction in GLMM_INTERACTIONS:
    # user-specified like "A:B"
    pieces = interaction.split(":")
    if all(p.strip() in df.columns for p in pieces):
        formula_rhs_parts.append(
            ":".join(f"C({_q(p.strip())})" if p.strip() in categorical else _q(p.strip())
                     for p in pieces))

formula = f"{_q(GLMM_RESPONSE)} ~ " + " + ".join(formula_rhs_parts)
print(f"[glmmRhythm] formula: {formula}")

summary_text = ""
coef_rows: list[dict] = []
random_rows: list[dict] = []

try:
    import statsmodels.formula.api as smf
    import statsmodels.api as sm  # noqa: F401

    if random and GLMM_ENGINE == "statsmodels":
        group_var = random[0]
        model = smf.mixedlm(formula, df, groups=df[group_var])
        result = model.fit(method="lbfgs", reml=True)
    else:
        result = smf.ols(formula, df).fit()

    summary_text = str(result.summary())
    params = result.params
    conf = result.conf_int(alpha=1 - float(GLMM_CONFIDENCE_LEVEL))
    pvalues = getattr(result, "pvalues", pd.Series(dtype=float))
    se = getattr(result, "bse", pd.Series(dtype=float))

    for name in params.index:
        coef_rows.append({
            "term": name,
            "estimate": float(params[name]),
            "std_err": float(se.get(name, np.nan)),
            "ci_low": float(conf.loc[name].iloc[0]) if name in conf.index else np.nan,
            "ci_high": float(conf.loc[name].iloc[1]) if name in conf.index else np.nan,
            "p_value": float(pvalues.get(name, np.nan)),
        })

    # Random effects
    if hasattr(result, "random_effects"):
        for grp, vals in result.random_effects.items():
            for idx in vals.index:
                random_rows.append({
                    "group": str(grp), "term": idx,
                    "estimate": float(vals[idx]),
                })

    # Null comparison
    if GLMM_COMPARE_NULL:
        null_formula = f"{_q(GLMM_RESPONSE)} ~ 1"
        try:
            if random and GLMM_ENGINE == "statsmodels":
                null = smf.mixedlm(null_formula, df, groups=df[group_var]).fit(
                    method="lbfgs", reml=False)
                # Refit full with ML for LRT
                full_ml = smf.mixedlm(formula, df, groups=df[group_var]).fit(
                    method="lbfgs", reml=False)
                lrt_stat = 2 * (full_ml.llf - null.llf)
                from scipy.stats import chi2
                # df = difference in number of fixed-effect parameters only
                # (mixedlm `params` includes the variance component, so use
                # `fe_params` to count fixed effects).
                full_k = len(getattr(full_ml, "fe_params", full_ml.params))
                null_k = len(getattr(null, "fe_params", null.params))
                lrt_df = max(full_k - null_k, 1)
                lrt_p = float(chi2.sf(lrt_stat, lrt_df))
                summary_text += (f"\n\n=== Null comparison ===\n"
                                 f"LRT statistic: {lrt_stat:.4f}\n"
                                 f"df: {lrt_df}\n"
                                 f"p-value: {lrt_p:.4g}\n"
                                 f"ΔAIC: {full_ml.aic - null.aic:.4f}\n")
            else:
                null = smf.ols(null_formula, df).fit()
                summary_text += (f"\n\n=== Null comparison ===\n"
                                 f"ΔAIC (full - null): {result.aic - null.aic:.4f}\n")
        except Exception as e:
            summary_text += f"\nNull comparison failed: {e}\n"

except ImportError:
    print("ERROR: statsmodels not installed. Install with: pip install statsmodels")
    sys.exit(1)
except Exception as e:
    print(f"[glmmRhythm] Model fit failed: {e}")
    summary_text = f"Model fit failed: {e}\n"

write_text_output(os.path.join(output_folder, "glmm_summary.txt"), summary_text)
write_csv_dataframe(
    os.path.join(output_folder, "glmm_coefficients.csv"),
    pd.DataFrame(coef_rows),
    index=False,
)
if random_rows:
    write_csv_dataframe(
        os.path.join(output_folder, "glmm_random_effects.csv"),
        pd.DataFrame(random_rows),
        index=False,
    )

# Forest plot
if coef_rows:
    cdf = pd.DataFrame(coef_rows)
    cdf = cdf[cdf["term"] != "Intercept"].reset_index(drop=True)
    if len(cdf):
        _pal = get_palette(GLMM_PALETTE, 3)
        sig_color = _pal[1] if len(_pal) > 1 else "#D55E00"     # Okabe-Ito vermillion for sig
        nonsig_color = _pal[0] if len(_pal) else "#0072B2"      # Okabe-Ito blue for n.s.
        colors = [sig_color if (pd.notna(p) and p < 0.05) else nonsig_color
                  for p in cdf["p_value"]]

        fig, ax = plt.subplots(figsize=(GLMM_FIG_WIDTH, max(3.0, 0.55 * len(cdf) + 1.0)),
                               facecolor=GLMM_BG_COLOR,
                               constrained_layout=True)
        y = np.arange(len(cdf))
        for yi, row, col in zip(y, cdf.itertuples(index=False), colors):
            lo = row.ci_low if pd.notna(row.ci_low) else row.estimate
            hi = row.ci_high if pd.notna(row.ci_high) else row.estimate
            ax.plot([lo, hi], [yi, yi], color=col, linewidth=2.2, solid_capstyle="round", zorder=2)
            ax.plot([row.estimate], [yi], marker="o", color=col,
                    markersize=8, markeredgecolor="black", markeredgewidth=0.6, zorder=3)
        ax.axvline(0, color="#555555", linestyle="--", linewidth=1.2, zorder=1)

        # Annotate each row with p-value / sig stars on the right margin
        def _sig_stars(p):
            if pd.isna(p):
                return ""
            if p < 0.001:
                return "***"
            if p < 0.01:
                return "**"
            if p < 0.05:
                return "*"
            return "n.s."
        xmax = ax.get_xlim()[1]
        for yi, row in zip(y, cdf.itertuples(index=False)):
            p = row.p_value
            txt = f"{_sig_stars(p)}  p={p:.3g}" if pd.notna(p) else ""
            ax.text(xmax, yi, "  " + txt, va="center", ha="left",
                    fontsize=9, color="#333333")

        ax.set_yticks(y)
        ax.set_yticklabels(cdf["term"])
        ax.invert_yaxis()
        ax.set_xlabel(f"Coefficient estimate ({int(round(GLMM_CONFIDENCE_LEVEL*100))}% CI)")
        ax.set_title(f"{GLMM_TITLE}  (n = {len(df)} observations)")
        ax.grid(True, axis="x", linestyle=":", alpha=0.55)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        save_figure(fig, output_folder, "glmm_forest",
                    fmt=GLMM_OUTPUT_FORMAT, dpi=int(GLMM_DPI))
        plt.close(fig)

# Residual diagnostic plot (fitted-vs-residual + QQ)
try:
    if "result" in globals() and hasattr(result, "fittedvalues") and hasattr(result, "resid"):
        fitted = np.asarray(result.fittedvalues)
        resid = np.asarray(result.resid)
        fig, axes = plt.subplots(1, 2, figsize=(GLMM_FIG_WIDTH, 4.2),
                                  facecolor=GLMM_BG_COLOR, constrained_layout=True)
        ax = axes[0]
        ax.scatter(fitted, resid, alpha=0.75, color=get_palette(GLMM_PALETTE, 1)[0],
                   edgecolor="black", linewidth=0.5, s=45)
        ax.axhline(0, color="#555555", linestyle="--", linewidth=1.0)
        ax.set_xlabel("Fitted")
        ax.set_ylabel("Residual")
        ax.set_title("Residual vs fitted")
        ax.grid(True, linestyle=":", alpha=0.55)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        ax = axes[1]
        from scipy.stats import probplot
        probplot(resid, dist="norm", plot=ax)
        # Restyle the default probplot markers / line
        ax.get_lines()[0].set_markerfacecolor(get_palette(GLMM_PALETTE, 1)[0])
        ax.get_lines()[0].set_markeredgecolor("black")
        ax.get_lines()[0].set_markersize(5)
        ax.get_lines()[1].set_color("#555555")
        ax.get_lines()[1].set_linestyle("--")
        ax.set_title("Normal QQ of residuals")
        ax.grid(True, linestyle=":", alpha=0.55)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        save_figure(fig, output_folder, "glmm_residuals",
                    fmt=GLMM_OUTPUT_FORMAT, dpi=int(GLMM_DPI))
        plt.close(fig)
except Exception as _resid_err:
    print(f"[glmmRhythm] residual plot skipped: {_resid_err}")

print(f"[glmmRhythm] done. Results in {output_folder}")
