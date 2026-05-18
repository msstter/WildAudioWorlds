from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import math
import re

import numpy as np
import pandas as pd
from scipy.stats import entropy as scipy_entropy


SUMMARY_SHEET_NAME = 'File Summaries'
DYADS_SHEET_NAME = 'Dyadic Events (For Plots)'
STABLE_DYADS_SHEET_NAME = 'Dyadic Events (Stable Rhythms)'
DEFAULT_FILENAME_COLUMN = 'File Name'
DEFAULT_ONSET_COLUMN = 'Exact Onset Times Used (s)'
DEFAULT_STABLE_TOLERANCE = 0.25

SUMMARY_EXPORT_COLUMNS = [
    DEFAULT_FILENAME_COLUMN,
    'Total Onsets Used',
    'Average Cycle Duration (ms)',
    'Stable Dyads Retained',
    'nPVI (Isochrony)',
    'CV of Intervals',
    'r_k Std Dev',
    'r_k Entropy (Categorical Measure)',
    'Stable Rhythm nPVI',
    'Stable Rhythm CV',
    'Stable Rhythm r_k Std Dev',
    'Stable Rhythm Entropy',
    DEFAULT_ONSET_COLUMN,
]

DYAD_EXPORT_COLUMNS = [
    DEFAULT_FILENAME_COLUMN,
    'Dyad Index',
    'Interval 1 (ms)',
    'Interval 2 (ms)',
    'Cycle Duration [cd] (ms)',
    'Short Interval [i_s] (ms)',
    'Long Interval [i_l] (ms)',
    'Rhythm Ratio [r_k]',
    'Stable Rhythm',
]


@dataclass(slots=True)
class WorkbookMatch:
    row_index: int
    matched_value: str


def _normalize_filename(value: Any) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    return Path(text).name.strip().lower()


def parse_onset_string(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, float) and math.isnan(value):
        return []

    text = str(value).strip().strip('[](){}')
    if not text:
        return []

    onset_times: list[float] = []
    for token in re.split(r'[,;\s]+', text):
        token = token.strip()
        if not token:
            continue
        try:
            parsed = float(token)
        except ValueError:
            continue
        if math.isfinite(parsed):
            onset_times.append(parsed)

    return sorted(onset_times)


def format_onset_string(onset_times: list[float], precision: int = 6) -> str:
    normalized = [float(time_sec) for time_sec in onset_times if math.isfinite(float(time_sec))]
    return ', '.join(f'{time_sec:.{precision}f}' for time_sec in sorted(normalized))


def _json_safe_cell_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def compute_ioi(onset_times: list[float]) -> list[float | None]:
    if len(onset_times) < 2:
        return [None] * len(onset_times)

    iois: list[float | None] = [None]
    for index in range(1, len(onset_times)):
        iois.append((onset_times[index] - onset_times[index - 1]) * 1000.0)
    return iois


def compute_rk(onset_times: list[float]) -> list[float | None]:
    if len(onset_times) < 3:
        return [None] * len(onset_times)

    result: list[float | None] = [None, None]
    for index in range(2, len(onset_times)):
        interval_1 = onset_times[index - 1] - onset_times[index - 2]
        interval_2 = onset_times[index] - onset_times[index - 1]
        cycle_duration = interval_1 + interval_2
        result.append(interval_1 / cycle_duration if cycle_duration > 0 else None)
    return result


def compute_stable(onset_times: list[float], tolerance: float = DEFAULT_STABLE_TOLERANCE) -> list[bool | None]:
    if len(onset_times) < 3:
        return [None] * len(onset_times)

    intervals = [onset_times[index] - onset_times[index - 1] for index in range(1, len(onset_times))]
    result: list[bool | None] = [None, None]

    def _match(interval_a: float, interval_b: float) -> bool:
        max_interval = max(interval_a, interval_b)
        if max_interval <= 0:
            return False
        return abs(interval_a - interval_b) / max_interval <= tolerance

    for dyad_index in range(len(intervals) - 1):
        comparisons = []
        if dyad_index + 2 < len(intervals):
            comparisons.append(_match(intervals[dyad_index], intervals[dyad_index + 2]))
        if dyad_index + 3 < len(intervals):
            comparisons.append(_match(intervals[dyad_index + 1], intervals[dyad_index + 3]))
        result.append(bool(comparisons) and all(comparisons))

    return result


def _round_or_na(value: float | None, digits: int) -> float | str:
    if value is None:
        return 'N/A'
    return round(float(value), digits)


def _ensure_columns(dataframe: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    frame = dataframe.copy()
    for column_name in columns:
        if column_name not in frame.columns:
            frame[column_name] = pd.Series(dtype='object')
        elif frame[column_name].dtype != object:
            frame[column_name] = frame[column_name].astype('object')
    return frame


def _find_matching_row(dataframe: pd.DataFrame, audio_filename: str, filename_column: str = DEFAULT_FILENAME_COLUMN) -> WorkbookMatch | None:
    if filename_column not in dataframe.columns:
        return None

    target = _normalize_filename(audio_filename)
    if not target:
        return None

    for row_index, raw_value in dataframe[filename_column].items():
        if _normalize_filename(raw_value) == target:
            return WorkbookMatch(row_index=int(row_index), matched_value=str(raw_value))

    return None


def _load_workbook_sheets(workbook_path: str | Path) -> dict[str, pd.DataFrame]:
    path = Path(workbook_path)
    if not path.exists():
        return {}
    return pd.read_excel(path, sheet_name=None, engine='openpyxl')


def _build_dyad_rows(audio_filename: str, onset_times: list[float], tolerance: float = DEFAULT_STABLE_TOLERANCE) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    stable_flags = compute_stable(onset_times, tolerance=tolerance)
    all_dyads: list[dict[str, Any]] = []
    stable_dyads: list[dict[str, Any]] = []

    for dyad_index in range(len(onset_times) - 2):
        interval_1 = (onset_times[dyad_index + 1] - onset_times[dyad_index]) * 1000.0
        interval_2 = (onset_times[dyad_index + 2] - onset_times[dyad_index + 1]) * 1000.0
        cycle_duration = interval_1 + interval_2
        rhythm_ratio = interval_1 / cycle_duration if cycle_duration > 0 else 0.0
        stable_flag = stable_flags[dyad_index + 2] if (dyad_index + 2) < len(stable_flags) else None

        row = {
            DEFAULT_FILENAME_COLUMN: audio_filename,
            'Dyad Index': dyad_index + 1,
            'Interval 1 (ms)': round(interval_1, 4),
            'Interval 2 (ms)': round(interval_2, 4),
            'Cycle Duration [cd] (ms)': round(cycle_duration, 4),
            'Short Interval [i_s] (ms)': round(min(interval_1, interval_2), 4),
            'Long Interval [i_l] (ms)': round(max(interval_1, interval_2), 4),
            'Rhythm Ratio [r_k]': round(rhythm_ratio, 6),
            'Stable Rhythm': bool(stable_flag) if stable_flag is not None else False,
        }
        all_dyads.append(row)
        if row['Stable Rhythm']:
            stable_dyads.append(dict(row))

    return all_dyads, stable_dyads


def _build_summary_updates(audio_filename: str, onset_times: list[float], tolerance: float = DEFAULT_STABLE_TOLERANCE) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    sorted_onsets = sorted(float(time_sec) for time_sec in onset_times if math.isfinite(float(time_sec)))
    all_dyads, stable_dyads = _build_dyad_rows(audio_filename, sorted_onsets, tolerance=tolerance)

    rk_values = np.array([row['Rhythm Ratio [r_k]'] for row in all_dyads], dtype=float) if all_dyads else np.array([], dtype=float)
    cycle_durations = np.array([row['Cycle Duration [cd] (ms)'] for row in all_dyads], dtype=float) if all_dyads else np.array([], dtype=float)
    stable_rk_values = np.array([row['Rhythm Ratio [r_k]'] for row in stable_dyads], dtype=float) if stable_dyads else np.array([], dtype=float)
    intervals_sec = np.diff(sorted_onsets) if len(sorted_onsets) > 1 else np.array([], dtype=float)
    stable_intervals_ms = np.array(
        [value for row in stable_dyads for value in (row['Interval 1 (ms)'], row['Interval 2 (ms)'])],
        dtype=float,
    ) if stable_dyads else np.array([], dtype=float)

    avg_cycle_duration_ms = float(np.mean(cycle_durations)) if cycle_durations.size > 0 else None
    mean_interval_sec = float(np.mean(intervals_sec)) if intervals_sec.size > 0 else 0.0
    cv_intervals = float(np.std(intervals_sec) / mean_interval_sec) if mean_interval_sec > 0 else None
    npvi_value = (400.0 / rk_values.size) * float(np.sum(np.abs(rk_values - 0.5))) if rk_values.size > 0 else None
    rk_std = float(np.std(rk_values)) if rk_values.size > 0 else None

    rk_entropy = None
    if rk_values.size > 0:
        histogram, _ = np.histogram(rk_values, bins=10, range=(0, 1))
        rk_entropy = float(scipy_entropy(histogram))

    stable_npvi = (400.0 / stable_rk_values.size) * float(np.sum(np.abs(stable_rk_values - 0.5))) if stable_rk_values.size > 0 else None
    stable_cv = None
    if stable_intervals_ms.size > 0:
        stable_mean = float(np.mean(stable_intervals_ms))
        stable_cv = float(np.std(stable_intervals_ms) / stable_mean) if stable_mean > 0 else None
    stable_rk_std = float(np.std(stable_rk_values)) if stable_rk_values.size > 0 else None

    stable_entropy = None
    if stable_rk_values.size > 0:
        stable_histogram, _ = np.histogram(stable_rk_values, bins=10, range=(0, 1))
        stable_entropy = float(scipy_entropy(stable_histogram))

    summary_updates = {
        DEFAULT_FILENAME_COLUMN: audio_filename,
        'Total Onsets Used': len(sorted_onsets),
        'Average Cycle Duration (ms)': _round_or_na(avg_cycle_duration_ms, 2),
        'Stable Dyads Retained': len(stable_dyads),
        'nPVI (Isochrony)': _round_or_na(npvi_value, 2),
        'CV of Intervals': _round_or_na(cv_intervals, 4),
        'r_k Std Dev': _round_or_na(rk_std, 4),
        'r_k Entropy (Categorical Measure)': _round_or_na(rk_entropy, 4),
        'Stable Rhythm nPVI': _round_or_na(stable_npvi, 2),
        'Stable Rhythm CV': _round_or_na(stable_cv, 4),
        'Stable Rhythm r_k Std Dev': _round_or_na(stable_rk_std, 4),
        'Stable Rhythm Entropy': _round_or_na(stable_entropy, 4),
        DEFAULT_ONSET_COLUMN: format_onset_string(sorted_onsets),
    }

    return summary_updates, all_dyads, stable_dyads


def load_onsets_for_audio(
    workbook_path: str | Path,
    audio_filename: str,
    *,
    filename_column: str = DEFAULT_FILENAME_COLUMN,
    onset_column: str = DEFAULT_ONSET_COLUMN,
    sheet_name: str = SUMMARY_SHEET_NAME,
) -> dict[str, Any]:
    workbook_sheets = _load_workbook_sheets(workbook_path)
    summary_sheet = workbook_sheets.get(sheet_name)
    if summary_sheet is None:
        raise ValueError(f'Sheet not found: {sheet_name}')

    match = _find_matching_row(summary_sheet, audio_filename, filename_column)
    if match is None:
        raise ValueError(f'Audio file not found in workbook: {audio_filename}')

    if onset_column not in summary_sheet.columns:
        raise ValueError(f'Onset column not found: {onset_column}')

    raw_cell_value = summary_sheet.at[match.row_index, onset_column]
    onset_times = parse_onset_string(raw_cell_value)

    summary_row = {
        column_name: _json_safe_cell_value(summary_sheet.at[match.row_index, column_name])
        for column_name in summary_sheet.columns
    }

    return {
        'workbookPath': str(Path(workbook_path).resolve()),
        'sheetName': sheet_name,
        'filenameColumn': filename_column,
        'onsetColumn': onset_column,
        'rowIndex': match.row_index,
        'matchedFileName': match.matched_value,
        'requestedFileName': audio_filename,
        'onsetTimes': onset_times,
        'summaryRow': summary_row,
        'sheetNames': list(workbook_sheets.keys()),
    }


def _write_workbook_sheets(output_path: Path, workbook_sheets: dict[str, pd.DataFrame]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for sheet_name, dataframe in workbook_sheets.items():
            dataframe.to_excel(writer, sheet_name=sheet_name, index=False)


def sync_workbook_onsets(
    workbook_path: str | Path,
    audio_filename: str,
    onset_times: list[float],
    *,
    output_path: str | Path | None = None,
    filename_column: str = DEFAULT_FILENAME_COLUMN,
    onset_column: str = DEFAULT_ONSET_COLUMN,
    summary_sheet_name: str = SUMMARY_SHEET_NAME,
    dyads_sheet_name: str = DYADS_SHEET_NAME,
    stable_dyads_sheet_name: str = STABLE_DYADS_SHEET_NAME,
    stable_tolerance: float = DEFAULT_STABLE_TOLERANCE,
) -> dict[str, Any]:
    source_path = Path(workbook_path)
    destination_path = Path(output_path) if output_path else source_path

    workbook_sheets = _load_workbook_sheets(source_path)
    summary_sheet = workbook_sheets.get(summary_sheet_name, pd.DataFrame())
    summary_sheet = _ensure_columns(summary_sheet, SUMMARY_EXPORT_COLUMNS)

    summary_updates, all_dyads, stable_dyads = _build_summary_updates(
        audio_filename,
        onset_times,
        tolerance=stable_tolerance,
    )

    match = _find_matching_row(summary_sheet, audio_filename, filename_column)
    if match is None:
        new_row = {column_name: '' for column_name in summary_sheet.columns}
        new_row.update(summary_updates)
        summary_sheet = pd.concat([summary_sheet, pd.DataFrame([new_row])], ignore_index=True)
        row_index = int(summary_sheet.index[-1])
        matched_value = audio_filename
    else:
        row_index = match.row_index
        matched_value = match.matched_value
        for column_name, value in summary_updates.items():
            if column_name not in summary_sheet.columns:
                summary_sheet[column_name] = pd.Series(dtype='object')
            if summary_sheet[column_name].dtype != object:
                summary_sheet[column_name] = summary_sheet[column_name].astype('object')
            summary_sheet.at[row_index, column_name] = value

    summary_sheet = _ensure_columns(summary_sheet, SUMMARY_EXPORT_COLUMNS)
    workbook_sheets[summary_sheet_name] = summary_sheet

    normalized_audio_filename = _normalize_filename(audio_filename)

    existing_dyads = workbook_sheets.get(dyads_sheet_name, pd.DataFrame())
    if not existing_dyads.empty and DEFAULT_FILENAME_COLUMN in existing_dyads.columns:
        existing_dyads = existing_dyads[
            existing_dyads[DEFAULT_FILENAME_COLUMN].map(_normalize_filename) != normalized_audio_filename
        ]
    existing_dyads = _ensure_columns(existing_dyads, DYAD_EXPORT_COLUMNS)
    next_dyads = pd.concat([existing_dyads, pd.DataFrame(all_dyads)], ignore_index=True) if all_dyads else existing_dyads
    workbook_sheets[dyads_sheet_name] = next_dyads

    existing_stable_dyads = workbook_sheets.get(stable_dyads_sheet_name, pd.DataFrame())
    if not existing_stable_dyads.empty and DEFAULT_FILENAME_COLUMN in existing_stable_dyads.columns:
        existing_stable_dyads = existing_stable_dyads[
            existing_stable_dyads[DEFAULT_FILENAME_COLUMN].map(_normalize_filename) != normalized_audio_filename
        ]
    existing_stable_dyads = _ensure_columns(existing_stable_dyads, DYAD_EXPORT_COLUMNS)
    next_stable_dyads = pd.concat([existing_stable_dyads, pd.DataFrame(stable_dyads)], ignore_index=True) if stable_dyads else existing_stable_dyads
    workbook_sheets[stable_dyads_sheet_name] = next_stable_dyads

    if not workbook_sheets:
        workbook_sheets = {
            summary_sheet_name: summary_sheet,
            dyads_sheet_name: next_dyads,
            stable_dyads_sheet_name: next_stable_dyads,
        }

    _write_workbook_sheets(destination_path, workbook_sheets)

    return {
        'sourceWorkbookPath': str(source_path.resolve()),
        'outputWorkbookPath': str(destination_path.resolve()),
        'requestedFileName': audio_filename,
        'matchedFileName': matched_value,
        'rowIndex': row_index,
        'sheetNames': list(workbook_sheets.keys()),
        'summarySheetName': summary_sheet_name,
        'dyadsSheetName': dyads_sheet_name,
        'stableDyadsSheetName': stable_dyads_sheet_name,
        'summaryUpdates': summary_updates,
        'onsetCount': len(onset_times),
        'dyadCount': len(all_dyads),
        'stableDyadCount': len(stable_dyads),
    }