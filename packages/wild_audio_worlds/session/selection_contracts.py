"""Shared backend selection-payload contracts and normalizers."""

from __future__ import annotations

from typing import Any, Mapping, TypedDict


DEFAULT_SELECTION_AMPLITUDE_MIN_PCT = 0.0
DEFAULT_SELECTION_AMPLITUDE_MAX_PCT = 100.0


class SelectionTimeRangeContract(TypedDict, total=False):
    start: float
    end: float
    duration: float


class SelectionFrequencyBinRangeContract(TypedDict, total=False):
    startBin: int
    endBin: int
    totalBins: int


class SelectionAmplitudePctRangeContract(TypedDict, total=False):
    min: float
    max: float


class BackendSelectionContract(TypedDict, total=False):
    isReady: bool
    source: str
    selectionModel: str
    currentTarget: str
    enabled: bool
    workflowMode: str
    overviewMode: str
    activePlanes: list[Any]
    activeSelectionSpaces: list[Any]
    missingAxes: list[Any]
    statusMessage: str
    frameRange: dict[str, Any]
    sampleRange: dict[str, Any]
    timeRangeSec: SelectionTimeRangeContract
    frequencyBinRange: SelectionFrequencyBinRangeContract
    amplitudePctRange: SelectionAmplitudePctRangeContract


def _mapping_or_empty(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _coerce_float(value: object, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _coerce_int(value: object, fallback: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return int(fallback)


def _clamp(value: float | int, lower: float | int, upper: float | int) -> float | int:
    return max(lower, min(upper, value))


def normalize_backend_selection_contract(selection_payload: Mapping[str, Any] | None) -> BackendSelectionContract:
    selection = _mapping_or_empty(selection_payload)
    return {
        **selection,
        "isReady": bool(selection.get("isReady")),
        "frameRange": _mapping_or_empty(selection.get("frameRange")),
        "sampleRange": _mapping_or_empty(selection.get("sampleRange")),
        "timeRangeSec": _mapping_or_empty(selection.get("timeRangeSec")),
        "frequencyBinRange": _mapping_or_empty(selection.get("frequencyBinRange")),
        "amplitudePctRange": _mapping_or_empty(selection.get("amplitudePctRange")),
    }


def normalize_selection_time_window(selection_payload: Mapping[str, Any] | None, clip_duration_sec: float) -> dict[str, float]:
    selection = normalize_backend_selection_contract(selection_payload)
    time_range = selection.get("timeRangeSec") or {}

    start_sec = _coerce_float(time_range.get("start"), 0.0)
    end_sec = _coerce_float(time_range.get("end"), clip_duration_sec)

    if clip_duration_sec > 0:
        start_sec = _clamp(start_sec, 0.0, clip_duration_sec)
        end_sec = _clamp(end_sec, 0.0, clip_duration_sec)
    else:
        start_sec = max(0.0, start_sec)
        end_sec = max(0.0, end_sec)

    if end_sec <= start_sec:
        raise ValueError("Selection time window is empty. Enable terrain plane selections that define a non-zero time slice.")

    return {
        "startSec": float(start_sec),
        "endSec": float(end_sec),
        "durationSec": float(end_sec - start_sec),
    }


def normalize_selection_frequency_window(
    selection_payload: Mapping[str, Any] | None,
    available_bin_count: int,
    preferred_total_bins: int,
) -> dict[str, int]:
    selection = normalize_backend_selection_contract(selection_payload)
    frequency_range = selection.get("frequencyBinRange") or {}

    total_bins = max(1, min(_coerce_int(available_bin_count, 1), _coerce_int(preferred_total_bins, 1)))
    preferred_total_bins = _coerce_int(frequency_range.get("totalBins"), total_bins)
    total_bins = max(1, min(total_bins, preferred_total_bins))

    start_bin = _coerce_int(frequency_range.get("startBin"), 0)
    end_bin = _coerce_int(frequency_range.get("endBin"), total_bins - 1)
    start_bin = _coerce_int(_clamp(start_bin, 0, max(0, total_bins - 1)), 0)
    end_bin = _coerce_int(_clamp(end_bin, start_bin, max(0, total_bins - 1)), total_bins - 1)

    return {
        "startBin": start_bin,
        "endBin": end_bin,
        "totalBins": total_bins,
    }


def normalize_selection_amplitude_pct_range(
    selection_payload: Mapping[str, Any] | None,
    *,
    clamp_values: bool = False,
) -> dict[str, float]:
    selection = normalize_backend_selection_contract(selection_payload)
    amplitude_range = selection.get("amplitudePctRange") or {}

    min_pct = _coerce_float(amplitude_range.get("min"), DEFAULT_SELECTION_AMPLITUDE_MIN_PCT)
    max_pct = _coerce_float(amplitude_range.get("max"), DEFAULT_SELECTION_AMPLITUDE_MAX_PCT)

    if clamp_values:
        min_pct = _clamp(min_pct, DEFAULT_SELECTION_AMPLITUDE_MIN_PCT, DEFAULT_SELECTION_AMPLITUDE_MAX_PCT)
        max_pct = _clamp(max_pct, min_pct, DEFAULT_SELECTION_AMPLITUDE_MAX_PCT)

    return {
        "min": float(min_pct),
        "max": float(max_pct),
    }