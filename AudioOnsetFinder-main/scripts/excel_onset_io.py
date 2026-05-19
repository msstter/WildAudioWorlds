"""Excel / CSV onset I/O utilities for the Bioacoustics Rhythm Pipeline.

Provides functions to:
- Parse onset-time strings from Excel cells (various formats)
- Load onset data from Excel/CSV files, matching by audio filename
- Save onset data back to Excel/CSV (overwrite or new column)
- Query available columns and filenames in a spreadsheet

Dependencies: pandas, openpyxl (for .xlsx)
"""

from __future__ import annotations

import os
import re
from typing import Optional

try:
    from .shared_data_manager import SharedDataManager as _SharedDataManager
except ImportError:
    from shared_data_manager import SharedDataManager as _SharedDataManager


_DEFAULT_STABLE_TOLERANCE = 0.25
_SUMMARY_SHEET = "File Summaries"
_DYADS_SHEET = "Dyadic Events (For Plots)"
_STABLE_DYADS_SHEET = "Dyadic Events (Stable Rhythms)"
_TARGET_FILENAME_COLUMN = "File Name"
_TARGET_ONSET_COLUMN = "Exact Onset Times Used (s)"
_DYAD_COLUMNS = [
    "File Name",
    "Dyad Index",
    "Interval 1 (ms)",
    "Interval 2 (ms)",
    "Cycle Duration [cd] (ms)",
    "Short Interval [i_s] (ms)",
    "Long Interval [i_l] (ms)",
    "Rhythm Ratio [r_k]",
    "Stable Rhythm",
]


def _write_csv_dataframe(output_path: str, dataframe) -> None:
    if _SharedDataManager is not None:
        _SharedDataManager.write_csv_dataframe(output_path, dataframe)
        return

    dataframe.to_csv(output_path, index=False)


def _write_workbook_sheets(output_path: str, workbook_sheets: dict[str, object]) -> None:
    import pandas as pd

    if _SharedDataManager is not None:
        _SharedDataManager.write_workbook_sheets(output_path, workbook_sheets)
        return

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for sheet_name, sheet_df in workbook_sheets.items():
            sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)


def parse_onset_string(s: str) -> list[float]:
    """Parse an onset-time string into a sorted list of floats.

    Handles formats:
      - "0.5, 1.2, 2.1"
      - "[0.5, 1.2, 2.1]"
      - "0.5;1.2;2.1"
      - "0.5 1.2 2.1"
    """
    if not s or not isinstance(s, str):
        return []
    # Strip brackets, parentheses, whitespace edges
    s = s.strip().strip("[](){}")
    if not s:
        return []
    # Split on comma, semicolon, or whitespace
    parts = re.split(r"[,;\s]+", s)
    times: list[float] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        try:
            times.append(float(p))
        except ValueError:
            continue
    times.sort()
    return times


def format_onset_string(times: list[float], precision: int = 6) -> str:
    """Convert a list of onset times to a comma-separated string."""
    return ", ".join(f"{t:.{precision}f}" for t in sorted(times))


def get_sheet_names(file_path: str) -> list[str]:
    """Return sheet names for an Excel file, or ['Sheet1'] for CSV."""
    import pandas as pd
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        return ["Sheet1"]
    xls = pd.ExcelFile(file_path, engine="openpyxl")
    return xls.sheet_names


def get_columns(file_path: str, sheet_name: str | int = 0) -> list[str]:
    """Return column names from a sheet in an Excel/CSV file."""
    import pandas as pd
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(file_path, nrows=0)
    else:
        df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=0,
                           engine="openpyxl")
    return list(df.columns)


def get_filenames(file_path: str, filename_col: str,
                  sheet_name: str | int = 0) -> list[str]:
    """Return unique filenames from the specified column."""
    import pandas as pd
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(file_path, usecols=[filename_col])
    else:
        df = pd.read_excel(file_path, sheet_name=sheet_name,
                           usecols=[filename_col], engine="openpyxl")
    if filename_col not in df.columns:
        return []
    return list(df[filename_col].dropna().unique())


def load_onsets_for_file(file_path: str, audio_filename: str,
                         filename_col: str, onset_col: str,
                         sheet_name: str | int = 0) -> list[float]:
    """Load onset times for a specific audio file from an Excel/CSV.

    Returns a sorted list of onset times (float seconds), or empty list
    if the audio file is not found or the onset cell is empty.
    """
    import pandas as pd
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path, sheet_name=sheet_name,
                           engine="openpyxl")

    if filename_col not in df.columns or onset_col not in df.columns:
        return []

    # Match by filename (case-insensitive, strip whitespace)
    mask = df[filename_col].astype(str).str.strip().str.lower() == \
        audio_filename.strip().lower()
    matches = df.loc[mask, onset_col]
    if matches.empty:
        return []

    # Take the first match
    cell_value = matches.iloc[0]
    if pd.isna(cell_value):
        return []
    return parse_onset_string(str(cell_value))


def load_all_onsets(file_path: str, filename_col: str, onset_col: str,
                    sheet_name: str | int = 0) -> dict[str, list[float]]:
    """Load onset times for all audio files in the Excel/CSV.

    Returns {audio_filename: [onset_times]} dict.
    """
    import pandas as pd
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path, sheet_name=sheet_name,
                           engine="openpyxl")

    if filename_col not in df.columns or onset_col not in df.columns:
        return {}

    result: dict[str, list[float]] = {}
    for _, row in df.iterrows():
        fname = row.get(filename_col)
        onset_str = row.get(onset_col)
        if pd.isna(fname) or pd.isna(onset_str):
            continue
        result[str(fname)] = parse_onset_string(str(onset_str))
    return result


def _normalized_audio_name(value: str | os.PathLike | None) -> str:
    """Return a lowercase basename for filename matching."""
    if value is None:
        return ""
    return os.path.basename(str(value)).strip().lower()


def _build_audio_name_lookup(audio_filenames: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """Build exact-name and unique-stem lookup tables for audio filenames."""
    exact_lookup: dict[str, str] = {}
    stem_buckets: dict[str, list[str]] = {}

    for audio_filename in audio_filenames:
        normalized = _normalized_audio_name(audio_filename)
        if not normalized:
            continue
        exact_lookup[normalized] = audio_filename
        stem = os.path.splitext(normalized)[0]
        stem_buckets.setdefault(stem, []).append(audio_filename)

    unique_stem_lookup = {
        stem: matches[0]
        for stem, matches in stem_buckets.items()
        if len(matches) == 1
    }
    return exact_lookup, unique_stem_lookup


def resolve_audio_filename_match(
    candidate_name: str,
    audio_filenames: list[str],
    *,
    _lookup: tuple[dict[str, str], dict[str, str]] | None = None,
) -> str | None:
    """Resolve one outside row name to an audio filename from the current folder."""
    exact_lookup, stem_lookup = _lookup or _build_audio_name_lookup(audio_filenames)
    normalized = _normalized_audio_name(candidate_name)
    if not normalized:
        return None

    exact_match = exact_lookup.get(normalized)
    if exact_match:
        return exact_match
    return stem_lookup.get(os.path.splitext(normalized)[0])


def scan_matching_onset_rows(
    file_path: str,
    available_audio_filenames: list[str],
    filename_col: str,
    onset_col: str,
    sheet_name: str | int = 0,
) -> dict:
    """Return source rows whose filenames match the current audio folder."""
    import pandas as pd

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")

    if filename_col not in df.columns:
        raise ValueError(f"Column '{filename_col}' not found in {file_path}")
    if onset_col not in df.columns:
        raise ValueError(f"Column '{onset_col}' not found in {file_path}")

    lookup = _build_audio_name_lookup(available_audio_filenames)
    matched_rows: dict[str, dict] = {}
    unmatched_source_names: list[str] = []
    duplicate_targets: list[dict] = []

    for row_index, row in df.iterrows():
        source_name = row.get(filename_col)
        onset_value = row.get(onset_col)
        if pd.isna(source_name):
            continue

        onset_times = [] if pd.isna(onset_value) else parse_onset_string(str(onset_value))
        if not onset_times:
            continue

        resolved_name = resolve_audio_filename_match(str(source_name), available_audio_filenames, _lookup=lookup)
        if not resolved_name:
            unmatched_source_names.append(str(source_name))
            continue

        if resolved_name in matched_rows:
            duplicate_targets.append(
                {
                    "source_name": str(source_name),
                    "audio_filename": resolved_name,
                    "row_index": int(row_index),
                    "onset_count": len(onset_times),
                }
            )
            continue

        matched_rows[resolved_name] = {
            "source_name": str(source_name),
            "audio_filename": resolved_name,
            "row_index": int(row_index),
            "onset_times": onset_times,
            "onset_count": len(onset_times),
        }

    return {
        "matches": sorted(matched_rows.values(), key=lambda row: _normalized_audio_name(row["audio_filename"])),
        "unmatched_source_names": unmatched_source_names,
        "duplicate_targets": duplicate_targets,
        "available_audio_count": len(available_audio_filenames),
    }


def _format_metric_value(value, digits: int) -> float | str:
    """Round numeric workbook metrics or emit the extractor-style N/A marker."""
    if value is None:
        return "N/A"
    return round(float(value), digits)


def _estimated_bpm_from_onsets(onsets: list[float]) -> float | None:
    """Estimate BPM from the median inter-onset interval when possible."""
    if len(onsets) < 2:
        return None

    intervals = [onsets[index] - onsets[index - 1] for index in range(1, len(onsets))]
    positive = [interval for interval in intervals if interval > 0]
    if not positive:
        return None

    import numpy as np

    return 60.0 / float(np.median(positive))


def _build_recording_workbook_payload(
    file_name: str,
    onset_times: list[float],
    *,
    stable_tolerance: float = _DEFAULT_STABLE_TOLERANCE,
) -> dict:
    """Build summary and dyad payloads for one recording's onset list."""
    try:
        from .onset_metrics import (
            build_dyad_records,
            calculate_rhythm_metrics,
            calculate_stable_subset_metrics,
            get_stable_dyad_flags,
        )
    except ImportError:
        from onset_metrics import (
            build_dyad_records,
            calculate_rhythm_metrics,
            calculate_stable_subset_metrics,
            get_stable_dyad_flags,
        )

    sorted_onsets = sorted(float(t) for t in onset_times)
    intervals_seconds = [
        sorted_onsets[index] - sorted_onsets[index - 1]
        for index in range(1, len(sorted_onsets))
    ]
    intervals_ms = [interval * 1000.0 for interval in intervals_seconds]
    stable_flags = get_stable_dyad_flags(intervals_ms, float(stable_tolerance))
    dyad_records = build_dyad_records(file_name, intervals_ms, stable_flags)
    stable_dyad_records = [record for record in dyad_records if record.get("Stable Rhythm")]
    metrics = calculate_rhythm_metrics(intervals_seconds, dyad_records)
    stable_metrics = calculate_stable_subset_metrics(stable_dyad_records)

    onset_updates = {
        "Estimated Overall BPM": _format_metric_value(_estimated_bpm_from_onsets(sorted_onsets), 1),
        "Total Onsets Used": len(sorted_onsets),
        "Average Cycle Duration (ms)": _format_metric_value(metrics.get("Average Cycle Duration (ms)"), 2),
        "Stable Dyads Retained": len(stable_dyad_records),
        "nPVI (Isochrony)": _format_metric_value(metrics.get("nPVI (Isochrony)"), 2),
        "CV of Intervals": _format_metric_value(metrics.get("CV of Intervals"), 4),
        "r_k Std Dev": _format_metric_value(metrics.get("r_k Std Dev"), 4),
        "r_k Entropy (Categorical Measure)": _format_metric_value(
            metrics.get("r_k Entropy (Categorical Measure)"),
            4,
        ),
        "Stable Rhythm nPVI": _format_metric_value(stable_metrics.get("Stable Rhythm nPVI"), 2),
        "Stable Rhythm CV": _format_metric_value(stable_metrics.get("Stable Rhythm CV"), 4),
        "Stable Rhythm r_k Std Dev": _format_metric_value(
            stable_metrics.get("Stable Rhythm r_k Std Dev"),
            4,
        ),
        "Stable Rhythm Entropy": _format_metric_value(stable_metrics.get("Stable Rhythm Entropy"), 4),
        "Exact Onset Times Used (s)": format_onset_string(sorted_onsets),
    }

    return {
        "file_name": file_name,
        "summary_updates": onset_updates,
        "dyad_records": dyad_records,
        "stable_dyad_records": stable_dyad_records,
    }


def _read_workbook_sheets(source_path: str | None) -> dict[str, object]:
    """Read all workbook sheets from one Excel file when present."""
    import pandas as pd

    if not source_path or not os.path.isfile(source_path):
        return {}
    return pd.read_excel(source_path, sheet_name=None, engine="openpyxl")


def _drop_rows_for_files(df, file_names: set[str]):
    """Return the sheet with any rows for the updated recordings removed."""
    if df is None or _TARGET_FILENAME_COLUMN not in df.columns:
        return df
    normalized_targets = {_normalized_audio_name(file_name) for file_name in file_names}
    mask = ~df[_TARGET_FILENAME_COLUMN].astype(str).map(_normalized_audio_name).isin(normalized_targets)
    return df.loc[mask].copy()


def _ensure_dyad_dataframe(df, columns: list[str]):
    """Return a dyad sheet DataFrame with the expected columns available."""
    import pandas as pd

    if df is None:
        return pd.DataFrame(columns=columns)
    working = df.copy()
    for column in columns:
        if column not in working.columns:
            working[column] = pd.Series(dtype="object")
    return working[columns]


def write_recordings_to_workbook(
    excel_path: str,
    recordings: dict[str, list[float]],
    *,
    source_excel: Optional[str] = None,
    stable_tolerance: float = _DEFAULT_STABLE_TOLERANCE,
) -> dict:
    """Write multiple recordings into one pipeline workbook in a single pass."""
    import pandas as pd

    cleaned_recordings = {
        str(file_name): sorted(float(t) for t in onset_times)
        for file_name, onset_times in recordings.items()
    }
    if not cleaned_recordings:
        return {"path": excel_path, "imported_files": [], "updated": 0}

    payloads = {
        file_name: _build_recording_workbook_payload(
            file_name,
            onset_times,
            stable_tolerance=stable_tolerance,
        )
        for file_name, onset_times in cleaned_recordings.items()
    }

    read_path = excel_path if os.path.isfile(excel_path) else source_excel
    all_sheets = _read_workbook_sheets(read_path)
    existing_summary = all_sheets.get(_SUMMARY_SHEET)
    existing_dyads = all_sheets.get(_DYADS_SHEET)
    existing_stable_dyads = all_sheets.get(_STABLE_DYADS_SHEET)

    if existing_summary is not None and _TARGET_FILENAME_COLUMN in existing_summary.columns:
        new_summary = existing_summary.copy()
        for file_name, payload in payloads.items():
            mask = new_summary[_TARGET_FILENAME_COLUMN].astype(str).map(_normalized_audio_name) == _normalized_audio_name(file_name)
            matched = new_summary.index[mask].tolist()
            if matched:
                row_index = matched[0]
                for column_name, value in payload["summary_updates"].items():
                    if column_name not in new_summary.columns:
                        continue
                    if new_summary[column_name].dtype != object:
                        new_summary[column_name] = new_summary[column_name].astype(object)
                    new_summary.at[row_index, column_name] = value
            else:
                append_row = {_TARGET_FILENAME_COLUMN: file_name, **payload["summary_updates"]}
                new_summary = pd.concat([new_summary, pd.DataFrame([append_row])], ignore_index=True)
    else:
        new_summary = pd.DataFrame(
            [{_TARGET_FILENAME_COLUMN: file_name, **payload["summary_updates"]} for file_name, payload in payloads.items()]
        )

    file_names = set(payloads.keys())
    raw_records = [
        record
        for payload in payloads.values()
        for record in payload["dyad_records"]
    ]
    stable_records = [
        record
        for payload in payloads.values()
        for record in payload["stable_dyad_records"]
    ]

    new_dyads = _drop_rows_for_files(existing_dyads, file_names)
    new_dyads = _ensure_dyad_dataframe(new_dyads, _DYAD_COLUMNS)
    if raw_records:
        new_dyads = pd.concat([new_dyads, pd.DataFrame(raw_records)], ignore_index=True)

    new_stable_dyads = _drop_rows_for_files(existing_stable_dyads, file_names)
    new_stable_dyads = _ensure_dyad_dataframe(new_stable_dyads, _DYAD_COLUMNS)
    if stable_records:
        new_stable_dyads = pd.concat([new_stable_dyads, pd.DataFrame(stable_records)], ignore_index=True)

    workbook_sheets = {
        _SUMMARY_SHEET: new_summary,
    }
    if len(new_dyads) > 0 or existing_dyads is not None or raw_records:
        workbook_sheets[_DYADS_SHEET] = new_dyads
    if len(new_stable_dyads) > 0 or existing_stable_dyads is not None or stable_records:
        workbook_sheets[_STABLE_DYADS_SHEET] = new_stable_dyads
    for sheet_name, sheet_df in all_sheets.items():
        if sheet_name in (_SUMMARY_SHEET, _DYADS_SHEET, _STABLE_DYADS_SHEET):
            continue
        workbook_sheets[sheet_name] = sheet_df

    _write_workbook_sheets(excel_path, workbook_sheets)

    return {
        "path": excel_path,
        "imported_files": sorted(payloads.keys(), key=_normalized_audio_name),
        "updated": len(payloads),
        "stable_tolerance": float(stable_tolerance),
    }


def write_recording_to_workbook(
    excel_path: str,
    file_name: str,
    onset_times: list[float],
    *,
    source_excel: Optional[str] = None,
    stable_tolerance: float = _DEFAULT_STABLE_TOLERANCE,
) -> dict:
    """Compatibility wrapper for updating one recording in a workbook."""
    result = write_recordings_to_workbook(
        excel_path,
        {file_name: onset_times},
        source_excel=source_excel,
        stable_tolerance=stable_tolerance,
    )
    result["file_name"] = file_name
    result["onset_count"] = len(onset_times)
    return result


def import_matching_onsets_to_workbook(
    source_path: str,
    target_excel_path: str,
    available_audio_filenames: list[str],
    *,
    source_filename_col: str,
    source_onset_col: str,
    source_sheet: str | int = 0,
    overwrite_existing: bool = True,
    target_filename_col: str = _TARGET_FILENAME_COLUMN,
    target_onset_col: str = _TARGET_ONSET_COLUMN,
    target_sheet: str | int = _SUMMARY_SHEET,
    stable_tolerance: float = _DEFAULT_STABLE_TOLERANCE,
) -> dict:
    """Import onset rows from one outside spreadsheet into the pipeline workbook."""
    matches = scan_matching_onset_rows(
        source_path,
        available_audio_filenames,
        source_filename_col,
        source_onset_col,
        source_sheet,
    )

    existing_target_onsets: dict[str, list[float]] = {}
    if os.path.isfile(target_excel_path):
        try:
            existing_target_onsets = {
                _normalized_audio_name(file_name): onset_times
                for file_name, onset_times in load_all_onsets(
                    target_excel_path,
                    target_filename_col,
                    target_onset_col,
                    target_sheet,
                ).items()
            }
        except Exception:
            existing_target_onsets = {}

    recordings_to_write: dict[str, list[float]] = {}
    skipped_existing: list[str] = []
    overwritten_files: list[str] = []

    for match in matches["matches"]:
        audio_filename = match["audio_filename"]
        existing_onsets = existing_target_onsets.get(_normalized_audio_name(audio_filename), [])
        if existing_onsets and not overwrite_existing:
            skipped_existing.append(audio_filename)
            continue
        if existing_onsets:
            overwritten_files.append(audio_filename)
        recordings_to_write[audio_filename] = list(match["onset_times"])

    write_result = write_recordings_to_workbook(
        target_excel_path,
        recordings_to_write,
        stable_tolerance=stable_tolerance,
    )
    return {
        "path": write_result["path"],
        "matched": len(matches["matches"]),
        "imported": len(recordings_to_write),
        "imported_files": write_result["imported_files"],
        "overwritten_files": sorted(overwritten_files, key=_normalized_audio_name),
        "skipped_existing": sorted(skipped_existing, key=_normalized_audio_name),
        "unmatched_source_names": matches["unmatched_source_names"],
        "duplicate_targets": matches["duplicate_targets"],
        "stable_tolerance": write_result["stable_tolerance"],
    }


def save_onsets_to_excel(
    file_path: str,
    audio_filename: str,
    onset_times: list[float],
    filename_col: str,
    onset_col: str,
    sheet_name: str | int = 0,
    new_col_name: Optional[str] = None,
    output_path: Optional[str] = None,
    layer_name: Optional[str] = None,
    layer_col_name: str = "Onset_Layer",
) -> dict:
    """Save onset times back to an Excel/CSV file.

    Args:
        file_path: Path to the source Excel/CSV file.
        audio_filename: Name of the audio file (used to match rows).
        onset_times: List of onset times to save.
        filename_col: Column name containing audio filenames.
        onset_col: Column name containing onset data (for reference).
        sheet_name: Sheet name or index (only for Excel).
        new_col_name: If provided, save to this new column instead of
            overwriting onset_col. If None, overwrites onset_col.
        output_path: If provided, write to this path instead of file_path.
            If None, overwrites the original file.
        layer_name: If provided, write this string to the *layer_col_name*
            column at the same row.  Used to record the onset-layer label
            (e.g. "Drums", "Vocalisation") alongside onsets.
        layer_col_name: Column name for the layer label (default
            ``"Onset_Layer"``).  Only used when *layer_name* is set.

    Returns:
        dict with keys:
          'path': output file path
          'column': column name that was written
          'row_index': pandas row index of the matched row
          'old_value': previous cell value (str or None)
          'new_value': the value written
          'column_existed': whether new_col_name already existed
    """
    import pandas as pd

    ext = os.path.splitext(file_path)[1].lower()
    is_csv = ext == ".csv"

    if is_csv:
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path, sheet_name=sheet_name,
                           engine="openpyxl")

    if filename_col not in df.columns:
        raise ValueError(f"Column '{filename_col}' not found in {file_path}")

    # Match row
    mask = df[filename_col].astype(str).str.strip().str.lower() == \
        audio_filename.strip().lower()
    matched_indices = df.index[mask].tolist()

    if not matched_indices:
        raise ValueError(
            f"Audio file '{audio_filename}' not found in column "
            f"'{filename_col}' of {os.path.basename(file_path)}")

    row_idx = matched_indices[0]
    new_value = format_onset_string(onset_times)

    # Determine target column
    target_col = new_col_name if new_col_name else onset_col
    column_existed = target_col in df.columns

    # Get old value
    old_value = None
    if column_existed:
        old_val = df.at[row_idx, target_col]
        old_value = str(old_val) if not pd.isna(old_val) else None

    # Ensure target column is string-typed so onset strings can be stored
    if not column_existed:
        df[target_col] = pd.Series(dtype="object")
    elif df[target_col].dtype != object:
        df[target_col] = df[target_col].astype("object")

    # Write
    df.at[row_idx, target_col] = new_value

    # Write layer name if provided
    if layer_name:
        if layer_col_name not in df.columns:
            df[layer_col_name] = pd.Series(dtype="object")
        elif df[layer_col_name].dtype != object:
            df[layer_col_name] = df[layer_col_name].astype("object")
        df.at[row_idx, layer_col_name] = layer_name

    # Determine output path
    out = output_path or file_path

    if is_csv or os.path.splitext(out)[1].lower() == ".csv":
        _write_csv_dataframe(out, df)
    else:
        # For Excel, we need to preserve other sheets
        if os.path.isfile(file_path) and not is_csv:
            _write_excel_preserving_sheets(
                file_path, out, sheet_name, df)
        else:
            _write_workbook_sheets(out, {
                sheet_name if isinstance(sheet_name, str) else "File Summaries": df,
            })

    return {
        "path": out,
        "column": target_col,
        "row_index": int(row_idx),
        "old_value": old_value,
        "new_value": new_value,
        "column_existed": column_existed,
    }


def _write_excel_preserving_sheets(
    source_path: str, output_path: str,
    target_sheet: str | int, updated_df
):
    """Write updated_df to target_sheet while preserving all other sheets."""
    import pandas as pd

    # Read all sheets from source
    all_sheets = pd.read_excel(source_path, sheet_name=None, engine="openpyxl")

    # Resolve sheet name if given as int
    if isinstance(target_sheet, int):
        sheet_names = list(all_sheets.keys())
        if target_sheet < len(sheet_names):
            target_sheet = sheet_names[target_sheet]
        else:
            target_sheet = "File Summaries"

    # Replace the target sheet
    all_sheets[target_sheet] = updated_df

    # Write all sheets to output
    _write_workbook_sheets(output_path, all_sheets)


def combine_onset_columns(
    file_path: str,
    filename_col: str,
    source_columns: list[str],
    combined_col_name: str = "Onset Times Used (s)_Combined",
    sheet_name: str | int = 0,
    output_path: Optional[str] = None,
    insert_before: Optional[str] = None,
) -> dict:
    """Combine multiple onset columns into a single union column.

    For each row, onset times from all *source_columns* are merged into a
    deduplicated, sorted union and written to *combined_col_name*.

    Args:
        file_path: Source Excel/CSV file.
        filename_col: Column with audio filenames (for logging only).
        source_columns: Column names whose onsets should be combined.
        combined_col_name: Name for the combined column.
        sheet_name: Sheet name or index.
        output_path: If given, write here instead of overwriting.
        insert_before: If given, place the combined column just before
            this column name; otherwise append at the end.

    Returns:
        dict with 'path', 'column', 'rows_updated'.
    """
    import pandas as pd

    ext = os.path.splitext(file_path)[1].lower()
    is_csv = ext == ".csv"

    if is_csv:
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path, sheet_name=sheet_name,
                           engine="openpyxl")

    missing = [c for c in source_columns if c not in df.columns]
    if missing:
        raise ValueError(
            f"Column(s) not found: {', '.join(missing)}")

    # Build the combined column values
    combined_values = []
    for _, row in df.iterrows():
        all_times: list[float] = []
        for col in source_columns:
            cell = row.get(col)
            if pd.isna(cell):
                continue
            all_times.extend(parse_onset_string(str(cell)))
        # Deduplicate within 0.001 s tolerance, keep sorted
        if all_times:
            all_times.sort()
            deduped = [all_times[0]]
            for t in all_times[1:]:
                if t - deduped[-1] > 0.001:
                    deduped.append(t)
            combined_values.append(format_onset_string(deduped))
        else:
            combined_values.append("")
    rows_updated = sum(1 for v in combined_values if v)

    # Insert at the right position
    if insert_before and insert_before in df.columns:
        pos = df.columns.get_loc(insert_before)
        if combined_col_name in df.columns:
            df[combined_col_name] = combined_values
        else:
            df.insert(int(pos), combined_col_name, combined_values)
    else:
        df[combined_col_name] = combined_values

    out = output_path or file_path
    if is_csv or os.path.splitext(out)[1].lower() == ".csv":
        _write_csv_dataframe(out, df)
    else:
        if os.path.isfile(file_path) and not is_csv:
            _write_excel_preserving_sheets(
                file_path, out, sheet_name, df)
        else:
            _write_workbook_sheets(out, {
                sheet_name if isinstance(sheet_name, str) else "File Summaries": df,
            })

    return {
        "path": out,
        "column": combined_col_name,
        "rows_updated": rows_updated,
    }
