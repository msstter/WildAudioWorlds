"""Shared backend analysis-type registry for Python and Electron."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict


class BackendActionUiConfig(TypedDict, total=False):
    label: str
    help: str
    showBioOutputMode: bool


class BackendActionReadinessMessages(TypedDict, total=False):
    notReady: str
    missingWorkbookPath: str
    missingOnsetTimes: str
    missingWorkbookPathForOutputMode: str


class BackendActionReadinessConfig(TypedDict, total=False):
    requiresSelectionReady: bool
    requiresBioacousticsStateField: str
    requiresWorkbookPath: bool
    acceptsAutoDiscover: bool
    requiresOnsetTimes: bool
    defaultOutputMode: str
    workbookPathRequiredForOutputModes: list[str]
    messages: BackendActionReadinessMessages


class BackendAnalysisTypeConfig(TypedDict, total=False):
    group: str
    runner: str
    operation: str
    defaultSaveMode: str
    allowedSaveModes: list[str]
    readiness: BackendActionReadinessConfig
    ui: BackendActionUiConfig


def _load_analysis_type_registry() -> dict[str, Any]:
    registry_path = Path(__file__).with_name("analysis_types.json")
    with registry_path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)

    if not isinstance(registry, dict):
        raise ValueError("Backend analysis type registry must be a JSON object.")

    action_registry = registry.get("actions")
    if not isinstance(action_registry, dict) or not action_registry:
        raise ValueError("Backend analysis type registry must define at least one action.")

    default_analysis_type = str(registry.get("default") or "").strip()
    if not default_analysis_type or default_analysis_type not in action_registry:
        raise ValueError("Backend analysis type registry default must reference a known action.")

    return registry


_ANALYSIS_TYPE_REGISTRY = _load_analysis_type_registry()

BACKEND_ANALYSIS_TYPE_CONFIGS: dict[str, BackendAnalysisTypeConfig] = {
    str(analysis_type): dict(config) if isinstance(config, dict) else {}
    for analysis_type, config in _ANALYSIS_TYPE_REGISTRY["actions"].items()
}
DEFAULT_BACKEND_ANALYSIS_TYPE = str(_ANALYSIS_TYPE_REGISTRY["default"]).strip()


def normalize_backend_analysis_type(value: object) -> str:
    normalized = str(value or "").strip()
    return normalized or DEFAULT_BACKEND_ANALYSIS_TYPE


def get_backend_analysis_type_config(analysis_type: object) -> BackendAnalysisTypeConfig | None:
    normalized = normalize_backend_analysis_type(analysis_type)
    config = BACKEND_ANALYSIS_TYPE_CONFIGS.get(normalized)
    return dict(config) if isinstance(config, dict) else None


def is_bioacoustics_analysis_type(analysis_type: object) -> bool:
    config = get_backend_analysis_type_config(analysis_type)
    return bool(config and config.get("group") == "bioacoustics")


def is_bioacoustics_import_analysis_type(analysis_type: object) -> bool:
    config = get_backend_analysis_type_config(analysis_type)
    return bool(config and config.get("operation") == "import-workbook")


def is_bioacoustics_sync_analysis_type(analysis_type: object) -> bool:
    config = get_backend_analysis_type_config(analysis_type)
    return bool(config and config.get("operation") == "sync-workbook")