"""Shared helpers for graph-audio asset paths and manifests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TypedDict


class GraphProjectPaths(TypedDict):
    project_root: str
    sample_audio_dir: str
    exports_dir: str
    public_assets_dir: str
    manifest_path: str


def build_project_paths(project_root: str | Path) -> GraphProjectPaths:
    resolved_project_root = Path(project_root).resolve()
    return {
        "project_root": str(resolved_project_root),
        "sample_audio_dir": str(resolved_project_root / "data" / "sample_audio"),
        "exports_dir": str(resolved_project_root / "data" / "exports"),
        "public_assets_dir": str(resolved_project_root / "frontend" / "public" / "audio_assets"),
        "manifest_path": str(resolved_project_root / "frontend" / "public" / "audio_assets_manifest.json"),
    }


def load_manifest_entries(manifest_path: str | Path) -> list[dict]:
    manifest_file_path = Path(manifest_path)
    if not manifest_file_path.exists():
        return []

    with open(manifest_file_path, "r", encoding="utf-8") as manifest_file:
        payload = json.load(manifest_file)

    if not isinstance(payload, dict) or not isinstance(payload.get("assets"), list):
        return []
    return payload["assets"]


def save_manifest_entries(manifest_path: str | Path, manifest_entries: list[dict]) -> None:
    from .data_manager import DataManager

    project_root = DataManager.resolve_project_root_from_manifest_path(manifest_path)
    DataManager(project_root).save_manifest_entries(manifest_entries)


def upsert_manifest_entry(manifest_path: str | Path, manifest_entry: dict) -> list[dict]:
    from .data_manager import DataManager

    project_root = DataManager.resolve_project_root_from_manifest_path(manifest_path)
    payload = DataManager(project_root).upsert_manifest_entry(manifest_entry)
    return payload.get("assets", [])