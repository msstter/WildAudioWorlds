"""Shared frontend/backend failure metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, TypedDict


DEFAULT_BACKEND_ERROR_CODE = "backend-analysis-failed"


class BackendErrorMetadata(TypedDict, total=False):
    message: str


def _load_error_metadata_registry() -> dict[str, Any]:
    registry_path = Path(__file__).with_name("error_metadata.json")
    with registry_path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)

    if not isinstance(registry, dict):
        raise ValueError("Backend error metadata registry must be a JSON object.")

    errors = registry.get("errors")
    if not isinstance(errors, dict) or not errors:
        raise ValueError("Backend error metadata registry must define errors.")

    return registry


_ERROR_METADATA_REGISTRY = _load_error_metadata_registry()

BACKEND_ERROR_METADATA: dict[str, BackendErrorMetadata] = {
    str(error_code): dict(metadata) if isinstance(metadata, dict) else {}
    for error_code, metadata in _ERROR_METADATA_REGISTRY["errors"].items()
}


def normalize_backend_error_code(value: object, fallback: str = DEFAULT_BACKEND_ERROR_CODE) -> str:
    normalized = str(value or "").strip()
    return normalized or fallback


def get_backend_error_metadata(error_code: object) -> BackendErrorMetadata:
    normalized_error_code = normalize_backend_error_code(error_code)
    metadata = BACKEND_ERROR_METADATA.get(normalized_error_code)
    if isinstance(metadata, dict):
        return dict(metadata)

    return {
        "message": normalized_error_code,
    }


def enrich_backend_failure(failure_payload: Mapping[str, Any] | None, *, error_code: object | None = None) -> dict[str, Any]:
    base = dict(failure_payload) if isinstance(failure_payload, Mapping) else {}
    resolved_error_code = normalize_backend_error_code(base.get("errorCode") if error_code is None else error_code)
    metadata = get_backend_error_metadata(resolved_error_code)
    error_message = str(base.get("error") or metadata.get("message") or resolved_error_code).strip()

    return {
        **base,
        "ok": False,
        "errorCode": resolved_error_code,
        "error": error_message,
    }


def build_backend_failure(error_code: object, **overrides: Any) -> dict[str, Any]:
    return enrich_backend_failure(overrides, error_code=error_code)