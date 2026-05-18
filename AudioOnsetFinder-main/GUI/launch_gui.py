from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from tkinter import Tk, messagebox


def _gui_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


GUI_DIR = _gui_dir()
PROJECT_DIR = GUI_DIR.parent
PIPELINE_GUI = GUI_DIR / "pipeline_gui.py"


def _show_error(title: str, message: str) -> None:
    root = Tk()
    root.withdraw()
    try:
        messagebox.showerror(title, message)
    finally:
        root.destroy()


def _python_candidates() -> list[Path]:
    user_profile = Path(os.environ.get("USERPROFILE", ""))
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    base_candidates = [
        user_profile / "anaconda3" / "envs" / "rhythm_env" / "python.exe",
        user_profile / "miniconda3" / "envs" / "rhythm_env" / "python.exe",
        local_app_data / "anaconda3" / "envs" / "rhythm_env" / "python.exe",
        local_app_data / "miniconda3" / "envs" / "rhythm_env" / "python.exe",
        Path(r"C:\ProgramData\anaconda3\envs\rhythm_env\python.exe"),
    ]
    candidates: list[Path] = []
    for candidate in base_candidates:
        candidates.append(candidate.with_name("pythonw.exe"))
        candidates.append(candidate)
    return candidates


def find_python() -> str:
    for candidate in _python_candidates():
        if candidate.is_file():
            return str(candidate)
    python_on_path = shutil.which("python")
    return python_on_path or ""


def _launcher_env(python_path: str) -> dict[str, str]:
    env = os.environ.copy()
    python_exe = Path(python_path).resolve()
    env_root = python_exe.parent
    if not ((env_root / "python.exe").is_file() or (env_root / "pythonw.exe").is_file()):
        return env

    path_prefixes = [
        env_root,
        env_root / "Library" / "mingw-w64" / "bin",
        env_root / "Library" / "usr" / "bin",
        env_root / "Library" / "bin",
        env_root / "Scripts",
        env_root / "bin",
    ]
    existing_prefixes = [str(path) for path in path_prefixes if path.is_dir()]
    if existing_prefixes:
        env["PATH"] = os.pathsep.join(existing_prefixes + [env.get("PATH", "")])
    env["CONDA_PREFIX"] = str(env_root)
    env["CONDA_DEFAULT_ENV"] = "rhythm_env"
    return env


def main() -> int:
    python_path = find_python()
    if not python_path:
        _show_error(
            "Bioacoustics Rhythm Pipeline",
            "Could not find Python for the rhythm_env Conda environment.\n\n"
            "Open Anaconda Prompt, activate rhythm_env, and launch the app once from there first.",
        )
        return 1

    if not PIPELINE_GUI.is_file():
        _show_error(
            "Bioacoustics Rhythm Pipeline",
            f"Could not find the GUI entrypoint:\n{PIPELINE_GUI}",
        )
        return 1

    try:
        process = subprocess.Popen(
            [python_path, str(PIPELINE_GUI)],
            cwd=str(PROJECT_DIR),
            env=_launcher_env(python_path),
        )
    except OSError as exc:
        _show_error(
            "Bioacoustics Rhythm Pipeline",
            f"Failed to launch the GUI.\n\n{exc}",
        )
        return 1

    return int(process.poll() or 0)


if __name__ == "__main__":
    raise SystemExit(main())