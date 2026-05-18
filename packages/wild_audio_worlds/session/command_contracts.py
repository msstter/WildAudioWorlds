"""Shared backend session and command-contract helpers."""

from __future__ import annotations

import json
from typing import Any, Mapping, TypedDict

from .analysis_types import DEFAULT_BACKEND_ANALYSIS_TYPE, normalize_backend_analysis_type
from .selection_contracts import BackendSelectionContract, normalize_backend_selection_contract


DEFAULT_BACKEND_SAVE_MODE = "json"


class BackendAssetContract(TypedDict, total=False):
    id: str
    label: str
    audioUrl: str
    mfccCsvUrl: str | None
    fftCsvUrl: str | None
    terrainEnvelopeUrl: str | None
    analysisSampleRate: int
    analysisHopLength: int
    analysisFrameLength: int
    analysisFrameCount: int
    analysisHopDurationSec: float
    analysisWindowDurationSec: float
    analysisClipDurationSec: float
    analysisFftNfft: int
class BackendBioacousticsContract(TypedDict, total=False):
    autoDiscover: bool
    workbookPath: str
    outputPath: str
    outputMode: str
    targetLabel: str
    targetKind: str
    assetAudioFileName: str
    onsetCount: int
    onsetTimes: list[float]
    importedOnsetCount: int
    importedWorkbookPath: str
    importedMatchedFileName: str
    importedAt: str | None
    isAssetReady: bool
    canImport: bool
    canSync: bool
    statusMessage: str


class BackendSaveOptionsContract(TypedDict, total=False):
    mode: str
    label: str


class BackendCallMetaContract(TypedDict, total=False):
    requestId: str
    requestedAt: str
    completedAt: str


class BackendAnalysisRequestContract(TypedDict, total=False):
    analysisType: str
    asset: BackendAssetContract
    selection: BackendSelectionContract
    uiContext: dict[str, Any]
    bioacoustics: BackendBioacousticsContract
    saveOptions: BackendSaveOptionsContract
    callMeta: BackendCallMetaContract


def _mapping_or_empty(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def normalize_backend_save_mode(value: object, fallback: str = DEFAULT_BACKEND_SAVE_MODE) -> str:
    normalized = str(value or "").strip().lower()
    return normalized or fallback


def normalize_backend_analysis_request(payload: Mapping[str, Any] | None) -> BackendAnalysisRequestContract:
    if not isinstance(payload, Mapping):
        raise ValueError("Selection analysis payload must be a JSON object.")

    save_options = _mapping_or_empty(payload.get("saveOptions"))
    call_meta = _mapping_or_empty(payload.get("callMeta"))

    return {
        "analysisType": normalize_backend_analysis_type(payload.get("analysisType")),
        "asset": _mapping_or_empty(payload.get("asset")),
        "selection": normalize_backend_selection_contract(payload.get("selection")),
        "uiContext": _mapping_or_empty(payload.get("uiContext")),
        "bioacoustics": _mapping_or_empty(payload.get("bioacoustics")),
        "saveOptions": {
            **save_options,
            "mode": normalize_backend_save_mode(save_options.get("mode")),
            "label": str(save_options.get("label") or "").strip(),
        },
        "callMeta": {
            **call_meta,
            "requestId": str(call_meta.get("requestId") or "").strip(),
            "requestedAt": str(call_meta.get("requestedAt") or "").strip(),
        },
    }


def parse_backend_analysis_request_json(raw_payload: str) -> BackendAnalysisRequestContract:
    raw_text = str(raw_payload or "")
    if not raw_text.strip():
        raise ValueError("No JSON payload received on stdin.")

    parsed = json.loads(raw_text)
    if not isinstance(parsed, dict):
        raise ValueError("Selection analysis payload must be a JSON object.")

    return normalize_backend_analysis_request(parsed)