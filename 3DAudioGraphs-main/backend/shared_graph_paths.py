from __future__ import annotations

import sys
from pathlib import Path


def _ensure_shared_package_path() -> None:
    current_path = Path(__file__).resolve()
    for parent in current_path.parents:
        packages_dir = parent / "packages"
        if (packages_dir / "wild_audio_worlds").exists():
            packages_dir_str = str(packages_dir)
            if packages_dir_str not in sys.path:
                sys.path.insert(0, packages_dir_str)
            return


_ensure_shared_package_path()

try:
    from wild_audio_worlds.graph.runtime_paths import (  # type: ignore
        resolve_backend_runner_path,
        resolve_graph_project_root,
        resolve_recorded_audio_import_runner_path,
    )
except ModuleNotFoundError:
    def resolve_graph_project_root(project_root=None, *, anchor_file=None):
        if project_root is not None:
            return Path(project_root).resolve()
        if anchor_file is not None:
            return Path(anchor_file).resolve().parent.parent
        raise ValueError("Either project_root or anchor_file must be provided.")

    def resolve_backend_runner_path(project_root=None, *, anchor_file=None):
        return resolve_graph_project_root(project_root, anchor_file=anchor_file) / "backend" / "run_selection_analysis.py"

    def resolve_recorded_audio_import_runner_path(project_root=None, *, anchor_file=None):
        return resolve_graph_project_root(project_root, anchor_file=anchor_file) / "backend" / "import_recorded_audio.py"