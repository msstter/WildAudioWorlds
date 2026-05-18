"""Shared helpers for Bioacoustics Pipeline analysis steps.

Extracts the common "data source" logic used by many analysis steps
(nPVI Group Plot, Association Rule Learning, and the new Category A/B/C/D
steps). Keeps behaviour identical to the inlined implementation inside
``scripts/nPVI_byGroup.py`` so existing pipelines are unaffected.

Responsibilities:

1. ``assign_groups(...)``  — 4-mode group assignment
   (``filename_pattern``, ``mapping_csv``, ``manual``, ``excel_column``).

2. ``pick_rhythm_column(...)`` — swap Excel column name for the
   "raw" vs "stable" dataset toggle (e.g. ``nPVI (Isochrony)`` ↔
   ``Stable Rhythm nPVI``).

3. ``load_summary_and_groups(...)`` — convenience wrapper that loads
   the File Summaries sheet, assigns groups, and returns a DataFrame
   ready for downstream analysis.

4. ``order_groups(...)`` — honour a user-supplied display order while
   appending any missing groups alphabetically.

5. ``get_palette(...)`` — colour palette resolution shared with
   ``nPVI_byGroup.py``.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Iterable

import numpy as np
import pandas as pd


# ------------------------------------------------------------------
# Raw vs stable dataset column mapping
# ------------------------------------------------------------------
# Columns whose values differ between the raw onset set and the
# stable-rhythm subset. Keys are the "raw" column names used in
# File Summaries; values are the stable-rhythm equivalents.
RAW_TO_STABLE_COLUMNS = {
    "nPVI (Isochrony)": "Stable Rhythm nPVI",
    "r_k Entropy (Categorical Measure)": "Stable Rhythm Entropy",
    "CV of Intervals": "Stable Rhythm CV",
    "Mean IOI (ms)": "Stable Rhythm Mean IOI (ms)",
    "Total Onsets Used": "Stable Rhythm Onsets Used",
}


def pick_rhythm_column(raw_name: str, dataset: str) -> str:
    """Return the correct column name for the selected dataset.

    Parameters
    ----------
    raw_name : str
        The "raw" column name (e.g. ``"nPVI (Isochrony)"``).
    dataset : str
        Either ``"raw"`` (return name unchanged) or ``"stable"``
        (return the Stable Rhythm equivalent if one exists; otherwise
        the original name).
    """
    if dataset == "stable":
        return RAW_TO_STABLE_COLUMNS.get(raw_name, raw_name)
    return raw_name


# ------------------------------------------------------------------
# Group assignment
# ------------------------------------------------------------------
def assign_groups(
    df: pd.DataFrame,
    source: str,
    pattern: str = r"(?P<group>[A-Za-z]+)_",
    csv_path: str = "",
    manual_map: dict | None = None,
    ungrouped: str = "Ungrouped",
    excel_column: str | None = None,
    df_summary: pd.DataFrame | None = None,
    *,
    filename_col: str = "File Name",
) -> pd.DataFrame:
    """Add a ``Group`` column to *df* based on the selected source method.

    The four supported modes mirror those in ``nPVI_byGroup.py``:

    - ``filename_pattern``: regex with named capture ``(?P<group>…)``
      searched against each file name.
    - ``mapping_csv``: external CSV with ``File Name`` / ``Group``
      columns.
    - ``manual``: dict mapping file name → group.
    - ``excel_column``: read a column from ``df_summary``.

    Returns the same DataFrame with an added ``Group`` column.
    Raises ``SystemExit`` on user-facing errors so CLI scripts exit
    cleanly with a readable message (matching existing step behaviour).
    """
    manual_map = manual_map or {}

    if source == "filename_pattern":
        try:
            compiled = re.compile(pattern)
        except re.error as e:
            print(f"ERROR: Invalid group pattern: {e}")
            sys.exit(1)
        groups = []
        for fname in df[filename_col]:
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
        df["Group"] = df[filename_col].map(mapping).fillna(ungrouped)

    elif source == "manual":
        df["Group"] = df[filename_col].map(manual_map).fillna(ungrouped)

    elif source == "excel_column":
        col = excel_column or "Group"
        if df_summary is not None and col in df_summary.columns:
            mapping = dict(zip(df_summary[filename_col], df_summary[col].astype(str)))
            df["Group"] = df[filename_col].map(mapping).fillna(ungrouped)
        else:
            print(f"ERROR: Column '{col}' not found in File Summaries sheet.")
            print("Available columns:",
                  list(df_summary.columns) if df_summary is not None else "N/A")
            sys.exit(1)
    else:
        print(f"ERROR: Unknown group source '{source}'. "
              "Use 'filename_pattern', 'mapping_csv', 'manual', or 'excel_column'.")
        sys.exit(1)

    return df


def order_groups(df: pd.DataFrame, order_str: str) -> list:
    """Return the final ordered list of group labels present in *df*.

    ``order_str`` is a comma-separated list of group names (empty = alphabetical).
    Unknown names are appended alphabetically to the end.
    """
    if order_str and order_str.strip():
        order = [g.strip() for g in order_str.split(",") if g.strip()]
        for g in sorted(df["Group"].unique()):
            if g not in order:
                order.append(g)
    else:
        order = sorted(df["Group"].unique())
    return [g for g in order if g in df["Group"].values]


# ------------------------------------------------------------------
# Palette
# ------------------------------------------------------------------
_OKABE_ITO = [
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#009E73",  # bluish green
    "#CC79A7",  # reddish purple
    "#F0E442",  # yellow
    "#56B4E9",  # sky blue
    "#E69F00",  # orange
    "#000000",  # black
]

_NAMED_HEX_PALETTES = {
    "okabe-ito": _OKABE_ITO,
    "okabe_ito": _OKABE_ITO,
    "okabeito":  _OKABE_ITO,
    "cb":        _OKABE_ITO,
    "colorblind": _OKABE_ITO,
}


def get_palette(palette_str: str, n: int):
    """Return a list of *n* colours from a named colormap, named hex palette,
    or comma-separated hex list. Recognises 'okabe-ito' / 'cb' as the
    Okabe-Ito colour-blind-friendly 8-colour palette."""
    import matplotlib.pyplot as plt
    if palette_str is None:
        palette_str = "okabe-ito"
    key = str(palette_str).strip().lower()
    if key in _NAMED_HEX_PALETTES:
        pal = list(_NAMED_HEX_PALETTES[key])
        while len(pal) < n:
            pal.extend(_NAMED_HEX_PALETTES[key])
        return pal[:n]
    if "," in palette_str:
        colors = [c.strip() for c in palette_str.split(",")]
        while len(colors) < n:
            colors.extend(colors)
        return colors[:n]
    try:
        cmap = plt.get_cmap(palette_str)
    except ValueError:
        cmap = plt.get_cmap("Set2")
    return [cmap(i / max(n - 1, 1)) for i in range(n)]


# ------------------------------------------------------------------
# Convenience loader
# ------------------------------------------------------------------
def load_file_summaries(excel_path: str) -> pd.DataFrame:
    """Read the File Summaries sheet from the extractor output. Exits on error.

    If the workbook also contains a ``File Demographics`` sheet (written by
    the Onset Finder from the user-supplied per-file metadata), its
    columns are merged into the returned DataFrame on ``File Name``.
    Existing File Summaries columns are preserved — demographics only
    contributes columns that are missing.
    """
    if not os.path.isfile(excel_path):
        print(f"ERROR: Excel workbook not found: {excel_path}")
        print("Run the Onset Finder (Step 2) first to generate the workbook.")
        sys.exit(1)
    try:
        df = pd.read_excel(excel_path, sheet_name="File Summaries")
    except Exception as e:
        print(f"ERROR: Could not read 'File Summaries' sheet from {excel_path}: {e}")
        sys.exit(1)
    return merge_file_demographics(df, excel_path)


def merge_file_demographics(df: pd.DataFrame, excel_path: str) -> pd.DataFrame:
    """Merge the workbook's ``File Demographics`` sheet into *df* on
    ``File Name`` and return the merged DataFrame.

    No-op (returns *df* unchanged) if the sheet is absent, the
    DataFrame lacks a ``File Name`` column, or the merge fails.
    Columns already present in *df* are preserved — demographics values
    fill only missing columns.
    """
    if df is None or "File Name" not in df.columns:
        return df
    try:
        demo = pd.read_excel(excel_path, sheet_name="File Demographics")
    except Exception:
        return df
    if demo is None or demo.empty or "File Name" not in demo.columns:
        return df
    # Keep only demographic columns that aren't already in df.
    new_cols = [c for c in demo.columns
                if c != "File Name" and c not in df.columns]
    if not new_cols:
        return df
    demo_slim = demo[["File Name"] + new_cols].copy()
    # Treat the literal "NA" placeholder as a missing value so downstream
    # scripts can drop it rather than compare on the string.
    for c in new_cols:
        demo_slim[c] = demo_slim[c].replace({"NA": pd.NA})
    try:
        merged = df.merge(demo_slim, on="File Name", how="left")
    except Exception:
        return df
    return merged


def load_dyadic_events(excel_path: str, dataset: str = "raw") -> pd.DataFrame:
    """Read the Dyadic Events sheet (raw or stable)."""
    sheet = "Dyadic Events (For Plots)" if dataset == "raw" \
        else "Dyadic Events (Stable Rhythms)"
    try:
        return pd.read_excel(excel_path, sheet_name=sheet)
    except Exception as e:
        print(f"ERROR: Could not read '{sheet}' from {excel_path}: {e}")
        sys.exit(1)


def group_assignment_config_from(cfg: dict, prefix: str = "") -> dict:
    """Pull the common group-assignment keys from a step config dict.

    Scripts typically store keys with a prefix (e.g. ``NPVI_``, ``RR_``).
    This helper first looks for the prefixed key, then for the bare key,
    then falls back to the documented default.
    """
    def _get(key, default):
        return cfg.get(prefix + key, cfg.get(key, default))

    return {
        "source":        _get("GROUP_SOURCE", "filename_pattern"),
        "pattern":       _get("GROUP_PATTERN", r"(?P<group>[A-Za-z]+)_"),
        "csv_path":      _get("GROUP_CSV_PATH", ""),
        "manual_map":    _get("MANUAL_GROUPS", {}),
        "excel_column":  _get("GROUP_EXCEL_COLUMN", "Group"),
        "ungrouped":     _get("UNGROUPED_LABEL", "Ungrouped"),
        "order_str":     _get("GROUP_ORDER", ""),
        "dataset":       _get("DATASET", "raw"),
    }


# ------------------------------------------------------------------
# Output helpers
# ------------------------------------------------------------------
def ensure_output_folder(path: str) -> str:
    """Create *path* if it doesn't exist and return it."""
    if path and not os.path.exists(path):
        os.makedirs(path)
    return path


def save_figure(fig, folder: str, stem: str, fmt: str = "png", dpi: int = 300):
    """Save *fig* under ``folder/stem.ext`` for each format in *fmt*.

    *fmt* may be ``"png"``, ``"svg"``, ``"pdf"``, or combinations like
    ``"png+svg"`` matching the conventions used elsewhere in the pipeline.
    """
    formats = []
    for token in fmt.split("+"):
        token = token.strip().lower()
        if token in {"png", "svg", "pdf"}:
            formats.append(token)
    if not formats:
        formats = ["png"]
    out_paths = []
    for f in formats:
        path = os.path.join(folder, f"{stem}.{f}")
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
        out_paths.append(path)
    return out_paths


__all__ = [
    "RAW_TO_STABLE_COLUMNS",
    "assign_groups",
    "ensure_output_folder",
    "get_palette",
    "group_assignment_config_from",
    "load_dyadic_events",
    "load_file_summaries",
    "merge_file_demographics",
    "order_groups",
    "pick_rhythm_column",
    "save_figure",
]
