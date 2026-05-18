"""
Overall Preset Manager
======================
Save / load / list / delete whole-pipeline presets.

Each preset is a JSON file stored in ``<project_root>/GUI/Presets/``.
A preset captures **every** editable setting across all four pipeline panels
(Audio Editor, Onset Finder, Flower Raster Plots, Histogram Generator).
"""

import json
import os
import re

# Folder lives inside the GUI directory.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESET_DIR = os.path.join(_PROJECT_ROOT, "GUI", "Presets")

# Name of the built-in factory-defaults preset (read-only in spirit).
DEFAULT_PRESET_NAME = "Preset_Default"


def _ensure_dir():
    os.makedirs(PRESET_DIR, exist_ok=True)


def list_presets():
    """Return sorted list of preset names (without .json extension)."""
    _ensure_dir()
    names = []
    for f in os.listdir(PRESET_DIR):
        if f.lower().endswith(".json"):
            names.append(os.path.splitext(f)[0])
    return sorted(names)


def _next_default_name():
    """Generate the next available 'Preset_Custom_<N>' name."""
    existing = set(list_presets())
    n = 1
    while f"Preset_Custom_{n}" in existing:
        n += 1
    return f"Preset_Custom_{n}"


def _sanitize_name(name):
    """Strip characters that are unsafe in filenames."""
    name = name.strip()
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name or "Preset_Custom_1"


def save_preset(config_dict, name=None):
    """Save *config_dict* as ``<name>.json``.  Returns the final name used."""
    _ensure_dir()
    if not name:
        name = _next_default_name()
    name = _sanitize_name(name)
    path = os.path.join(PRESET_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(config_dict, f, indent=2, default=str)
    return name


def load_preset(name):
    """Load and return the config dict for the given preset name."""
    path = os.path.join(PRESET_DIR, f"{name}.json")
    with open(path) as f:
        return json.load(f)


def delete_preset(name):
    """Delete the preset file.  Returns True if it existed."""
    path = os.path.join(PRESET_DIR, f"{name}.json")
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def preset_path(name):
    """Return the full filesystem path for a preset name."""
    return os.path.join(PRESET_DIR, f"{name}.json")


def ensure_default_preset(default_config):
    """Create *Preset_Default* if it does not already exist.

    ``default_config`` should be the full config dict captured from a
    freshly-opened MainWindow (before the user changes anything).
    """
    _ensure_dir()
    path = os.path.join(PRESET_DIR, f"{DEFAULT_PRESET_NAME}.json")
    if not os.path.isfile(path):
        with open(path, "w") as f:
            json.dump(default_config, f, indent=2, default=str)
    return DEFAULT_PRESET_NAME
