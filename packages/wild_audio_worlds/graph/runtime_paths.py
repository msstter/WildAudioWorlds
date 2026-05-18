"""Shared 3DAudioGraphs backend path helpers."""

from __future__ import annotations

from pathlib import Path


def resolve_graph_project_root(project_root: str | Path | None = None, *, anchor_file: str | Path | None = None) -> Path:
    if project_root is not None:
        return Path(project_root).resolve()
    if anchor_file is not None:
        return Path(anchor_file).resolve().parent.parent
    raise ValueError("Either project_root or anchor_file must be provided.")


def resolve_backend_runner_path(project_root: str | Path | None = None, *, anchor_file: str | Path | None = None) -> Path:
    return resolve_graph_project_root(project_root, anchor_file=anchor_file) / "backend" / "run_selection_analysis.py"


def resolve_recorded_audio_import_runner_path(project_root: str | Path | None = None, *, anchor_file: str | Path | None = None) -> Path:
    return resolve_graph_project_root(project_root, anchor_file=anchor_file) / "backend" / "import_recorded_audio.py"