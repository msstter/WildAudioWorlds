"""Permuted Discriminant Function Analysis (Category C1).

Classifies per-file rhythmic predictors into a user-specified class
column (e.g. Region: East/West Africa) and computes a permutation
p-value by shuffling class labels while respecting repeated measures
(shuffling within individuals / sites when
``PDFA_REPEATED_MEASURES_COLUMN`` is set).

Engine: scipy/numpy LDA implementation — computes the correct
classification rate (CCR) from leave-one-out or k-fold cross-validation.
Compared against the same metric computed on permuted labels.

Outputs:
- ``pdfa_results.csv``: observed CCR, permutation p, n_permutations.
- ``pdfa_confusion_matrix.png``
- ``pdfa_scatter_LD1_LD2.png`` (first two discriminant axes)
- ``pdfa_loadings.csv``
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
    ensure_output_folder, get_palette, load_file_summaries, save_figure, write_csv_dataframe,
)

excel_path = os.path.join(_PROJECT_DIR, "Cross_Species_Rhythm_Data.xlsx")
output_folder = os.path.join(_PROJECT_DIR, "pDFA")

PDFA_DATASET = "raw"
PDFA_PREDICTORS = [
    "Total Onsets Used", "Total Duration (s)",
    "nPVI (Isochrony)", "CV of Intervals",
    "r_k Entropy (Categorical Measure)", "Mean IOI (ms)",
]
PDFA_CLASS_COLUMN = "Group"
PDFA_REPEATED_MEASURES_COLUMN = ""   # e.g. "Individual_ID"; empty = none
PDFA_N_PERMUTATIONS = 999
PDFA_RANDOM_SEED = 42
PDFA_STANDARDIZE = True
PDFA_CROSSVALIDATION = "leave_one_out"  # "none" | "leave_one_out" | "kfold" | "leave_one_group_out"
PDFA_N_FOLDS = 5
PDFA_PRIOR = "equal"             # "equal" | "empirical"
PDFA_MIN_OBS_PER_CLASS = 3

# Plot
PDFA_FIG_WIDTH = 10
PDFA_FIG_HEIGHT = 6
PDFA_DPI = 300
PDFA_PALETTE = "okabe-ito"
PDFA_TITLE = "Permuted DFA"
PDFA_BG_COLOR = "#ffffff"
PDFA_OUTPUT_FORMAT = "png"

_cfg_path = os.path.join(_PROJECT_DIR, "pipeline_config.json")
if os.path.isfile(_cfg_path):
    with open(_cfg_path) as _f:
        _cfg = json.load(_f).get("pdfa", {})
    excel_path = _cfg.get("excel_path", excel_path)
    output_folder = _cfg.get("output_folder", output_folder)
    for _k in list(globals().keys()):
        if _k.startswith("PDFA_") and _k in _cfg:
            globals()[_k] = _cfg[_k]
    del _f, _cfg

ensure_output_folder(output_folder)

print(f"[pDFA] Loading {excel_path}...")
df_summary = load_file_summaries(excel_path)

missing = [c for c in PDFA_PREDICTORS if c not in df_summary.columns]
if missing:
    print(f"WARNING: predictor columns missing and will be dropped: {missing}")
predictors = [c for c in PDFA_PREDICTORS if c in df_summary.columns]
if not predictors:
    print("ERROR: No valid predictor columns.")
    sys.exit(1)

if PDFA_CLASS_COLUMN not in df_summary.columns:
    print(f"ERROR: Class column '{PDFA_CLASS_COLUMN}' not in File Summaries.")
    sys.exit(1)

df = df_summary[["File Name", PDFA_CLASS_COLUMN] + predictors].copy()
for c in predictors:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df = df.dropna(subset=predictors + [PDFA_CLASS_COLUMN])

# Drop sparse classes
counts = df[PDFA_CLASS_COLUMN].value_counts()
keep = counts[counts >= int(PDFA_MIN_OBS_PER_CLASS)].index.tolist()
df = df[df[PDFA_CLASS_COLUMN].isin(keep)]
if df[PDFA_CLASS_COLUMN].nunique() < 2:
    print("ERROR: Need at least 2 classes with PDFA_MIN_OBS_PER_CLASS samples.")
    sys.exit(1)

print(f"[pDFA] n={len(df)}, classes={sorted(df[PDFA_CLASS_COLUMN].unique())}")

X = df[predictors].to_numpy(dtype=float)
# Drop constant predictors (would blow up standardisation / be useless to LDA).
col_std = X.std(axis=0, ddof=0)
keep_cols = col_std > 1e-12
if not keep_cols.all():
    dropped = [predictors[i] for i, k in enumerate(keep_cols) if not k]
    print(f"[pDFA] dropping constant predictors: {dropped}")
    X = X[:, keep_cols]
    predictors = [p for p, k in zip(predictors, keep_cols) if k]
if X.shape[1] == 0:
    print("ERROR: No non-constant predictors remain.")
    sys.exit(1)
if PDFA_STANDARDIZE:
    X = (X - X.mean(axis=0)) / X.std(axis=0, ddof=0)

y = df[PDFA_CLASS_COLUMN].astype(str).values
classes = sorted(np.unique(y))
class_to_idx = {c: i for i, c in enumerate(classes)}
y_idx = np.array([class_to_idx[c] for c in y])

rm_col = PDFA_REPEATED_MEASURES_COLUMN.strip()
if rm_col and rm_col in df.columns:
    rm = df[rm_col].astype(str).values
else:
    rm = None


def _lda_fit(Xtr, ytr, n_classes, prior="equal"):
    """Fit simple LDA: compute class means, pooled covariance, prior."""
    d = Xtr.shape[1]
    means = np.zeros((n_classes, d))
    Sw = np.zeros((d, d))
    counts = np.zeros(n_classes)
    for c in range(n_classes):
        mask = ytr == c
        counts[c] = mask.sum()
        if counts[c] == 0:
            continue
        means[c] = Xtr[mask].mean(axis=0)
        diff = Xtr[mask] - means[c]
        Sw += diff.T @ diff
    # pool
    n = Xtr.shape[0]
    if n - n_classes > 0:
        Sw /= max(n - n_classes, 1)
    # regularize
    Sw += 1e-8 * np.eye(d)
    inv = np.linalg.pinv(Sw)
    if prior == "equal":
        priors = np.full(n_classes, 1.0 / n_classes)
    else:
        priors = counts / counts.sum() if counts.sum() else np.full(n_classes, 1.0 / n_classes)
    return means, inv, priors


def _lda_predict(Xte, means, inv, priors):
    # Linear discriminant function: mu_k^T Σ^-1 x - 0.5 mu_k^T Σ^-1 mu_k + log π_k
    scores = Xte @ inv @ means.T \
        - 0.5 * np.einsum("kd,de,ke->k", means, inv, means)[None, :] \
        + np.log(priors + 1e-12)[None, :]
    return np.argmax(scores, axis=1)


def _ccr(X, y_idx, n_classes, mode, n_folds, prior):
    n = len(y_idx)
    if mode == "none":
        means, inv, priors = _lda_fit(X, y_idx, n_classes, prior)
        pred = _lda_predict(X, means, inv, priors)
        return float((pred == y_idx).mean()), pred
    if mode == "leave_one_out":
        pred = np.empty(n, dtype=int)
        for i in range(n):
            mask = np.ones(n, dtype=bool)
            mask[i] = False
            means, inv, priors = _lda_fit(X[mask], y_idx[mask], n_classes, prior)
            pred[i] = _lda_predict(X[i:i + 1], means, inv, priors)[0]
        return float((pred == y_idx).mean()), pred
    if mode == "kfold":
        rng = np.random.default_rng(int(PDFA_RANDOM_SEED))
        idx = rng.permutation(n)
        folds = np.array_split(idx, int(n_folds))
        pred = np.empty(n, dtype=int)
        for fold in folds:
            train_mask = np.ones(n, dtype=bool)
            train_mask[fold] = False
            means, inv, priors = _lda_fit(X[train_mask], y_idx[train_mask],
                                          n_classes, prior)
            pred[fold] = _lda_predict(X[fold], means, inv, priors)
        return float((pred == y_idx).mean()), pred
    # Fallback = resubstitution
    means, inv, priors = _lda_fit(X, y_idx, n_classes, prior)
    pred = _lda_predict(X, means, inv, priors)
    return float((pred == y_idx).mean()), pred


observed_ccr, pred = _ccr(X, y_idx, len(classes),
                          PDFA_CROSSVALIDATION, PDFA_N_FOLDS, PDFA_PRIOR)
print(f"[pDFA] Observed CCR: {observed_ccr:.4f}")

# Permutation
rng = np.random.default_rng(int(PDFA_RANDOM_SEED))
perm_ccrs = np.zeros(int(PDFA_N_PERMUTATIONS))
for i in range(int(PDFA_N_PERMUTATIONS)):
    if rm is not None:
        # Restricted shuffle (Mundry & Sommer 2007): permute class labels at the
        # UNIT level, so all observations from the same individual receive the
        # same permuted label. This breaks the predictor↔class mapping while
        # preserving within-unit pseudo-replication structure.
        units_arr = np.unique(rm)
        # one label per unit (must be consistent within unit; if not, take mode)
        unit_labels = np.array([
            np.bincount(y_idx[rm == u]).argmax()
            for u in units_arr
        ])
        permuted_unit_labels = rng.permutation(unit_labels)
        unit_to_label = dict(zip(units_arr, permuted_unit_labels))
        yp = np.array([unit_to_label[u] for u in rm])
    else:
        yp = rng.permutation(y_idx)
    perm_ccrs[i], _ = _ccr(X, yp, len(classes),
                           PDFA_CROSSVALIDATION, PDFA_N_FOLDS, PDFA_PRIOR)

p_val = (np.sum(perm_ccrs >= observed_ccr) + 1) / (len(perm_ccrs) + 1)
print(f"[pDFA] Permutation p = {p_val:.4f}")

res = pd.DataFrame([{
    "n": len(df),
    "n_classes": len(classes),
    "observed_CCR": observed_ccr,
    "chance_CCR_equal": 1.0 / len(classes),
    "n_permutations": int(PDFA_N_PERMUTATIONS),
    "p_value": float(p_val),
    "crossval": PDFA_CROSSVALIDATION,
    "repeated_measures": rm_col or "none",
}])
write_csv_dataframe(os.path.join(output_folder, "pdfa_results.csv"), res, index=False)

# Confusion matrix
cm = np.zeros((len(classes), len(classes)), dtype=int)
for actual, predicted in zip(y_idx, pred):
    cm[actual, predicted] += 1
cm_df = pd.DataFrame(cm, index=classes, columns=classes)
write_csv_dataframe(os.path.join(output_folder, "pdfa_confusion_matrix.csv"), cm_df, index=True)

fig, ax = plt.subplots(figsize=(PDFA_FIG_WIDTH, PDFA_FIG_HEIGHT),
                       facecolor=PDFA_BG_COLOR, constrained_layout=True)
# Row-normalise for colour; annotate with count (proportion%).
cm_row = cm.astype(float)
row_sums = cm_row.sum(axis=1, keepdims=True)
cm_norm = np.divide(cm_row, row_sums, out=np.zeros_like(cm_row),
                    where=row_sums > 0)
im = ax.imshow(cm_norm, cmap="Blues", aspect="auto", vmin=0.0, vmax=1.0)
ax.set_xticks(range(len(classes)))
ax.set_xticklabels(classes, rotation=25, ha="right")
ax.set_yticks(range(len(classes)))
ax.set_yticklabels(classes)
for i in range(len(classes)):
    for j in range(len(classes)):
        count = cm[i, j]
        pct = cm_norm[i, j] * 100.0
        ax.text(j, i, f"{count}\n({pct:.0f}%)", ha="center", va="center",
                color="white" if cm_norm[i, j] > 0.5 else "black",
                fontsize=9, linespacing=0.9)
ax.set_xlabel("Predicted class")
ax.set_ylabel("Actual class")
chance = 1.0 / len(classes)
ax.set_title(f"{PDFA_TITLE} — CCR = {observed_ccr:.3f}  "
             f"(chance = {chance:.3f})   p = {p_val:.3f}   "
             f"n_perm = {int(PDFA_N_PERMUTATIONS)}",
             fontsize=11)
fig.colorbar(im, ax=ax, label="Row-normalised rate")
save_figure(fig, output_folder, "pdfa_confusion_matrix",
            fmt=PDFA_OUTPUT_FORMAT, dpi=int(PDFA_DPI))
plt.close(fig)

# Permutation null histogram — the canonical pDFA figure.
fig, ax = plt.subplots(figsize=(PDFA_FIG_WIDTH, PDFA_FIG_HEIGHT * 0.75),
                       facecolor=PDFA_BG_COLOR, constrained_layout=True)
ax.hist(perm_ccrs, bins=30, color="#56B4E9", edgecolor="#0072B2",
        alpha=0.85, label=f"Permutation null (n = {len(perm_ccrs)})")
ax.axvline(observed_ccr, color="#D55E00", linestyle="-", linewidth=2.0,
           label=f"Observed CCR = {observed_ccr:.3f}")
ax.axvline(chance, color="#333333", linestyle=":", linewidth=1.2,
           label=f"Chance = {chance:.3f}")
ax.set_xlabel("Correct Classification Rate (CCR)")
ax.set_ylabel("Number of permutations")
ax.set_title(f"{PDFA_TITLE} — permutation null distribution   p = {p_val:.3f}")
ax.grid(True, axis="y", linestyle=":", alpha=0.5)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.legend(loc="upper right", frameon=False, fontsize=9)
save_figure(fig, output_folder, "pdfa_permutation_null",
            fmt=PDFA_OUTPUT_FORMAT, dpi=int(PDFA_DPI))
plt.close(fig)

# Discriminant projection: use between/within eigen decomposition
def _lda_project(X, y_idx, n_classes):
    d = X.shape[1]
    overall_mean = X.mean(axis=0)
    Sw = np.zeros((d, d))
    Sb = np.zeros((d, d))
    for c in range(n_classes):
        mask = y_idx == c
        nc = mask.sum()
        if nc == 0:
            continue
        mu_c = X[mask].mean(axis=0)
        diff = X[mask] - mu_c
        Sw += diff.T @ diff
        diff_b = (mu_c - overall_mean).reshape(-1, 1)
        Sb += nc * diff_b @ diff_b.T
    Sw += 1e-8 * np.eye(d)
    eigvals, eigvecs = np.linalg.eig(np.linalg.pinv(Sw) @ Sb)
    # Sort by eigenvalue
    order = np.argsort(-eigvals.real)
    return eigvecs.real[:, order], eigvals.real[order]


W, eigvals = _lda_project(X, y_idx, len(classes))
proj = X @ W[:, :2]

loadings = pd.DataFrame(W[:, :min(2, W.shape[1])],
                        index=predictors,
                        columns=[f"LD{i+1}" for i in range(min(2, W.shape[1]))])
write_csv_dataframe(os.path.join(output_folder, "pdfa_loadings.csv"), loadings, index=True)

fig, ax = plt.subplots(figsize=(PDFA_FIG_WIDTH, PDFA_FIG_HEIGHT),
                       facecolor=PDFA_BG_COLOR, constrained_layout=True)
colors = get_palette(PDFA_PALETTE, len(classes))
for i, c in enumerate(classes):
    mask = y_idx == i
    color = colors[i]
    if proj.shape[1] >= 2:
        ax.scatter(proj[mask, 0], proj[mask, 1], label=f"{c} (n={int(mask.sum())})",
                   color=color, edgecolor="black", s=55, alpha=0.85, zorder=2)
        # Class centroid
        ax.scatter(proj[mask, 0].mean(), proj[mask, 1].mean(),
                   marker="X", s=180, color=color, edgecolor="black",
                   linewidth=1.5, zorder=3)
    else:
        ax.scatter(proj[mask, 0], np.zeros(mask.sum()),
                   label=f"{c} (n={int(mask.sum())})",
                   color=color, edgecolor="black", s=55, alpha=0.85)
ax.axhline(0, color="#cccccc", linewidth=0.6, zorder=0)
ax.axvline(0, color="#cccccc", linewidth=0.6, zorder=0)
ax.set_xlabel("LD1")
ax.set_ylabel("LD2" if proj.shape[1] >= 2 else "")
ax.set_title(f"{PDFA_TITLE} — linear discriminants   "
             f"(X = class centroid)", fontsize=11)
ax.grid(True, linestyle=":", alpha=0.4)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0),
          frameon=False, fontsize=9)
save_figure(fig, output_folder, "pdfa_scatter_LD1_LD2",
            fmt=PDFA_OUTPUT_FORMAT, dpi=int(PDFA_DPI))
plt.close(fig)

print(f"[pDFA] done. Results in {output_folder}")
