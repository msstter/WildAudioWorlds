"""Optional bridge to the shared WildAudioWorlds DataManager.

This module keeps the legacy AudioOnsetFinder scripts usable outside the
combined workspace. When the shared package tree is present, callers can route
writes through DataManager; otherwise they fall back to their local behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _load_shared_data_manager():
    current_path = Path(__file__).resolve()
    for parent in current_path.parents:
        packages_dir = parent / "packages"
        if not (packages_dir / "wild_audio_worlds").exists():
            continue

        packages_dir_str = str(packages_dir)
        if packages_dir_str not in sys.path:
            sys.path.insert(0, packages_dir_str)

        try:
            from wild_audio_worlds.data import DataManager
        except Exception:
            return None
        return DataManager

    return None


SharedDataManager = _load_shared_data_manager()

__all__ = ["SharedDataManager"]
