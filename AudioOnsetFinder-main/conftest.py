from __future__ import annotations

import os
from importlib.util import find_spec
from pathlib import Path


def _find_pyqt6_plugin_root() -> Path | None:
	spec = find_spec("PyQt6")
	if spec is None or spec.origin is None:
		return None

	package_dir = Path(spec.origin).resolve().parent
	for relative_path in ("Qt6/plugins", "Qt/plugins", "plugins"):
		candidate = package_dir / relative_path
		if candidate.is_dir() and (candidate / "platforms").is_dir():
			return candidate
	return None


def _configure_qt_headless() -> None:
	plugin_root = _find_pyqt6_plugin_root()
	if plugin_root is None:
		return

	platforms_dir = plugin_root / "platforms"
	if not os.environ.get("QT_PLUGIN_PATH"):
		os.environ["QT_PLUGIN_PATH"] = str(plugin_root)
	if not os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
		os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platforms_dir)
	os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


_configure_qt_headless()