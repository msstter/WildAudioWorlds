from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _ensure_shared_package_path() -> Path:
    current_path = Path(__file__).resolve()
    for parent in current_path.parents:
        packages_dir = parent / "packages"
        if (packages_dir / "wild_audio_worlds").exists():
            packages_dir_str = str(packages_dir)
            if packages_dir_str not in sys.path:
                sys.path.insert(0, packages_dir_str)
            return parent
    raise RuntimeError("Unable to locate the shared packages directory for WildAudioWorlds.")


WORKSPACE_ROOT = _ensure_shared_package_path()

from wild_audio_worlds.session.shell_launch import parse_shell_launch_cli_args  # noqa: E402


AUDIO_ONSET_FINDER_SHELL_TYPE = "audio-onset-finder"
LOCAL_INTEGRATION_HOST_SHELL_ID = f"shell-aof-{uuid4().hex[:8]}"
LOCAL_INTEGRATION_HOST_STARTED_AT = datetime.now(timezone.utc).isoformat()


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text_or_empty(value: Any) -> str:
    return str(value or "").strip()


def resolve_local_integration_bootstrap_path(bootstrap_root: str | Path | None = None) -> Path:
    root_path = Path(bootstrap_root).resolve() if bootstrap_root is not None else WORKSPACE_ROOT
    return root_path / "services" / "local_integration" / "bootstrap_service.py"


def consume_local_integration_launch_args(argv: list[str] | None = None) -> tuple[dict[str, str], list[str]]:
    return parse_shell_launch_cli_args(argv if argv is not None else sys.argv)


def _resolve_last_known_state_revision(launch_request: dict[str, str]) -> int | None:
    manifest_path = _text_or_empty(launch_request.get("manifestPath"))
    if not manifest_path:
        return None

    path = Path(manifest_path)
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None

    state_revision = loaded.get("stateRevision") if isinstance(loaded, dict) else None
    try:
        return int(state_revision)
    except (TypeError, ValueError):
        return None


def build_audio_onset_attach_envelope(launch_request: dict[str, str], *, workspace_root: str | Path | None = None) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve() if workspace_root is not None else WORKSPACE_ROOT
    session_id = _text_or_empty(launch_request.get("sessionId"))
    if not session_id:
        raise ValueError("AudioOnsetFinder attach request is missing sessionId.")

    last_known_state_revision = _resolve_last_known_state_revision(launch_request)
    payload = {
        "sessionId": session_id,
        "shell": {
            "shellId": LOCAL_INTEGRATION_HOST_SHELL_ID,
            "shellType": AUDIO_ONSET_FINDER_SHELL_TYPE,
            "startedAt": LOCAL_INTEGRATION_HOST_STARTED_AT,
        },
        "requestedCapabilities": [
            "transport-read",
            "transport-write",
            "asset-read",
        ],
    }
    if last_known_state_revision is not None:
        payload["lastKnownStateRevision"] = last_known_state_revision

    return {
        "command": "session/attach",
        "workspaceRoot": str(workspace),
        "payload": payload,
    }


def attach_to_local_integration_session(
    launch_request: dict[str, str],
    *,
    workspace_root: str | Path | None = None,
    bootstrap_root: str | Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    envelope = build_audio_onset_attach_envelope(launch_request, workspace_root=workspace_root)
    workspace = Path(envelope["workspaceRoot"]).resolve()
    bootstrap_path = resolve_local_integration_bootstrap_path(bootstrap_root)
    if not bootstrap_path.exists():
        raise FileNotFoundError(f"Local integration bootstrap not found: {bootstrap_path}")

    result = subprocess.run(
        [python_executable or sys.executable, str(bootstrap_path)],
        input=json.dumps(envelope),
        capture_output=True,
        text=True,
        cwd=str(workspace),
        check=False,
    )

    try:
        parsed = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError as error:
        raise RuntimeError(f"AudioOnsetFinder attach returned invalid JSON: {error}") from error

    if result.returncode != 0 or not _mapping_or_empty(parsed).get("ok"):
        failure = _mapping_or_empty(parsed)
        error_message = _text_or_empty(failure.get("error")) or f"AudioOnsetFinder attach failed with exit code {result.returncode}."
        if result.stderr.strip():
            error_message = f"{error_message}\n{result.stderr.strip()}"
        raise RuntimeError(error_message)

    return parsed


__all__ = [
    "AUDIO_ONSET_FINDER_SHELL_TYPE",
    "LOCAL_INTEGRATION_HOST_SHELL_ID",
    "LOCAL_INTEGRATION_HOST_STARTED_AT",
    "attach_to_local_integration_session",
    "build_audio_onset_attach_envelope",
    "consume_local_integration_launch_args",
    "resolve_local_integration_bootstrap_path",
]