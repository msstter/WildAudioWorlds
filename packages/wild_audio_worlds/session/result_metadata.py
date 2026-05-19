"""Shared backend result and save-artifact metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, TypedDict


DEFAULT_BACKEND_SAVE_MODE = "json"


class BackendSaveModeMetadata(TypedDict, total=False):
    label: str
    artifactType: str
    artifactLabel: str


def _load_result_metadata_registry() -> dict[str, Any]:
    registry_path = Path(__file__).with_name("result_metadata.json")
    with registry_path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)

    if not isinstance(registry, dict):
        raise ValueError("Backend result metadata registry must be a JSON object.")

    save_modes = registry.get("saveModes")
    if not isinstance(save_modes, dict) or not save_modes:
        raise ValueError("Backend result metadata registry must define saveModes.")

    return registry


_RESULT_METADATA_REGISTRY = _load_result_metadata_registry()

BACKEND_SAVE_MODE_METADATA: dict[str, BackendSaveModeMetadata] = {
    str(mode): dict(metadata) if isinstance(metadata, dict) else {}
    for mode, metadata in _RESULT_METADATA_REGISTRY["saveModes"].items()
}


def normalize_backend_save_mode_key(value: object) -> str:
    normalized = str(value or "").strip().lower()
    return normalized or DEFAULT_BACKEND_SAVE_MODE


def get_backend_save_mode_metadata(mode: object) -> BackendSaveModeMetadata:
    normalized_mode = normalize_backend_save_mode_key(mode)
    metadata = BACKEND_SAVE_MODE_METADATA.get(normalized_mode)
    if isinstance(metadata, dict):
        return dict(metadata)

    return {
        "label": normalized_mode,
        "artifactType": normalized_mode,
        "artifactLabel": normalized_mode,
    }


def enrich_backend_save_result(save_result: Mapping[str, Any] | None, *, mode: object | None = None) -> dict[str, Any]:
    base = dict(save_result) if isinstance(save_result, Mapping) else {}
    normalized_mode = normalize_backend_save_mode_key(mode if mode is not None else base.get("mode"))
    metadata = get_backend_save_mode_metadata(normalized_mode)

    return {
        **base,
        "mode": normalized_mode,
        "modeLabel": str(metadata.get("label") or normalized_mode),
        "artifactType": str(metadata.get("artifactType") or normalized_mode),
        "artifactLabel": str(metadata.get("artifactLabel") or normalized_mode),
    }