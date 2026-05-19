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

from wild_audio_worlds.session.session_manifest import load_session_manifest  # noqa: E402
from wild_audio_worlds.session.shell_launch import (  # noqa: E402
    build_shell_launch_cli_args,
    parse_shell_launch_cli_args,
)


AUDIO_ONSET_FINDER_SHELL_TYPE = "audio-onset-finder"
AUDIO_GRAPHS_SHELL_TYPE = "audio-graphs"
LOCAL_INTEGRATION_HOST_SHELL_ID = f"shell-aof-{uuid4().hex[:8]}"
LOCAL_INTEGRATION_HOST_STARTED_AT = datetime.now(timezone.utc).isoformat()
LOCAL_INTEGRATION_SESSION_CACHE: dict[str, Any] = {}


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text_or_empty(value: Any) -> str:
    return str(value or "").strip()


def _resolve_workspace_root(workspace_root: str | Path | None = None) -> Path:
    return Path(workspace_root).resolve() if workspace_root is not None else WORKSPACE_ROOT


def _current_host_shell_descriptor() -> dict[str, str]:
    return {
        "shellId": LOCAL_INTEGRATION_HOST_SHELL_ID,
        "shellType": AUDIO_ONSET_FINDER_SHELL_TYPE,
        "startedAt": LOCAL_INTEGRATION_HOST_STARTED_AT,
    }


def _resolve_audio_graphs_frontend_root(
    frontend_root: str | Path | None = None,
    *,
    workspace_root: str | Path | None = None,
) -> Path:
    if frontend_root is not None:
        return Path(frontend_root).resolve()
    return (_resolve_workspace_root(workspace_root) / "3DAudioGraphs-main" / "frontend").resolve()


def _resolve_cached_session(workspace_root: str | Path | None = None) -> dict[str, Any]:
    workspace = _resolve_workspace_root(workspace_root)
    cached = _mapping_or_empty(LOCAL_INTEGRATION_SESSION_CACHE)
    if not cached:
        return {}

    if _text_or_empty(cached.get("workspaceRoot")) != str(workspace):
        return {}

    manifest_path = _text_or_empty(cached.get("manifestPath"))
    if manifest_path and not Path(manifest_path).exists():
        return {}

    return cached


def _update_local_integration_session_cache(
    response: dict[str, Any],
    *,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    global LOCAL_INTEGRATION_SESSION_CACHE

    workspace = _resolve_workspace_root(workspace_root)
    current_cache = _resolve_cached_session(workspace)
    parsed = _mapping_or_empty(response)
    session_summary = _mapping_or_empty(parsed.get("session"))
    if not session_summary and _text_or_empty(parsed.get("sessionId")):
        session_summary = {
            "sessionId": _text_or_empty(parsed.get("sessionId")),
            "mode": _text_or_empty(parsed.get("mode")),
            "stateRevision": parsed.get("stateRevision"),
            "manifestPath": _text_or_empty(parsed.get("manifestPath")),
        }

    if not session_summary:
        return current_cache

    next_cache = {
        **current_cache,
        **session_summary,
        "workspaceRoot": str(workspace),
    }
    service = _mapping_or_empty(parsed.get("service"))
    if service:
        next_cache["service"] = service

    LOCAL_INTEGRATION_SESSION_CACHE = next_cache
    return next_cache


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


def _load_cached_session_manifest(workspace_root: str | Path | None = None) -> dict[str, Any]:
    cached_session = _resolve_cached_session(workspace_root)
    manifest_path = _text_or_empty(cached_session.get("manifestPath"))
    if not manifest_path:
        return {}
    return _mapping_or_empty(load_session_manifest(manifest_path))


def _run_local_integration_command(
    envelope: dict[str, Any],
    *,
    bootstrap_root: str | Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    workspace = _resolve_workspace_root(envelope.get("workspaceRoot"))
    normalized_envelope = {
        **envelope,
        "workspaceRoot": str(workspace),
    }
    bootstrap_path = resolve_local_integration_bootstrap_path(bootstrap_root)
    if not bootstrap_path.exists():
        raise FileNotFoundError(f"Local integration bootstrap not found: {bootstrap_path}")

    result = subprocess.run(
        [python_executable or sys.executable, str(bootstrap_path)],
        input=json.dumps(normalized_envelope),
        capture_output=True,
        text=True,
        cwd=str(workspace),
        check=False,
    )

    try:
        parsed = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError as error:
        raise RuntimeError(f"AudioOnsetFinder local integration command returned invalid JSON: {error}") from error

    parsed_payload = _mapping_or_empty(parsed)
    if result.returncode != 0 or not parsed_payload.get("ok"):
        error_message = _text_or_empty(parsed_payload.get("error")) or (
            f"AudioOnsetFinder local integration command failed with exit code {result.returncode}."
        )
        if result.stderr.strip():
            error_message = f"{error_message}\n{result.stderr.strip()}"
        raise RuntimeError(error_message)

    _update_local_integration_session_cache(parsed_payload, workspace_root=workspace)
    return parsed_payload


def build_audio_onset_bootstrap_envelope(
    *,
    workspace_root: str | Path | None = None,
    launch_reason: str = "service-bootstrap",
) -> dict[str, Any]:
    workspace = _resolve_workspace_root(workspace_root)
    cached_session = _resolve_cached_session(workspace)
    return {
        "command": "service/bootstrap",
        "workspaceRoot": str(workspace),
        "session": {
            "sessionId": _text_or_empty(cached_session.get("sessionId")),
            "mode": "standalone",
            "hostShell": _current_host_shell_descriptor(),
            "launchContext": {
                "originatingShell": AUDIO_ONSET_FINDER_SHELL_TYPE,
                "launchReason": launch_reason,
                "requestedCompanion": "",
                "requestedByShellId": LOCAL_INTEGRATION_HOST_SHELL_ID,
            },
        },
    }


def ensure_local_integration_session(
    *,
    workspace_root: str | Path | None = None,
    bootstrap_root: str | Path | None = None,
    python_executable: str | None = None,
    launch_reason: str = "service-bootstrap",
) -> dict[str, Any]:
    workspace = _resolve_workspace_root(workspace_root)
    cached_session = _resolve_cached_session(workspace)
    if _text_or_empty(cached_session.get("sessionId")):
        return cached_session

    response = _run_local_integration_command(
        build_audio_onset_bootstrap_envelope(workspace_root=workspace, launch_reason=launch_reason),
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
    )
    return _mapping_or_empty(response.get("session"))


def build_audio_onset_attach_envelope(launch_request: dict[str, str], *, workspace_root: str | Path | None = None) -> dict[str, Any]:
    workspace = _resolve_workspace_root(workspace_root)
    session_id = _text_or_empty(launch_request.get("sessionId"))
    if not session_id:
        raise ValueError("AudioOnsetFinder attach request is missing sessionId.")

    last_known_state_revision = _resolve_last_known_state_revision(launch_request)
    payload = {
        "sessionId": session_id,
        "shell": _current_host_shell_descriptor(),
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
    return _run_local_integration_command(
        envelope,
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
    )


def build_audio_graphs_open_companion_envelope(
    *,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    workspace = _resolve_workspace_root(workspace_root)
    cached_session = _resolve_cached_session(workspace)
    manifest = _load_cached_session_manifest(workspace)
    session_id = _text_or_empty(cached_session.get("sessionId")) or _text_or_empty(manifest.get("sessionId"))
    if not session_id:
        raise ValueError("AudioOnsetFinder companion launch requires an active shared session.")

    payload: dict[str, Any] = {
        "sessionId": session_id,
        "originShell": _current_host_shell_descriptor(),
        "targetShell": AUDIO_GRAPHS_SHELL_TYPE,
        "launchContext": {
            "originatingShell": AUDIO_ONSET_FINDER_SHELL_TYPE,
            "launchReason": "open-companion",
            "requestedCompanion": AUDIO_GRAPHS_SHELL_TYPE,
            "requestedByShellId": LOCAL_INTEGRATION_HOST_SHELL_ID,
        },
    }

    asset = _mapping_or_empty(manifest.get("asset"))
    if asset:
        payload["asset"] = asset

    transport_state = _mapping_or_empty(manifest.get("transportState"))
    if transport_state:
        payload["transportState"] = transport_state

    return {
        "command": "shell/open_companion",
        "workspaceRoot": str(workspace),
        "payload": payload,
    }


def _resolve_npm_command() -> str:
    return "npm.cmd" if sys.platform == "win32" else "npm"


def _launch_audio_graphs_companion_process(
    open_response: dict[str, Any],
    *,
    frontend_root: str | Path | None = None,
    workspace_root: str | Path | None = None,
    launch_process_factory: Any | None = None,
) -> dict[str, Any]:
    launched_shell = _mapping_or_empty(open_response.get("launchedShell"))
    target_shell = _text_or_empty(launched_shell.get("shellType")) or AUDIO_GRAPHS_SHELL_TYPE
    if target_shell != AUDIO_GRAPHS_SHELL_TYPE:
        raise ValueError(f"Unsupported companion shell target: {target_shell}")

    frontend = _resolve_audio_graphs_frontend_root(frontend_root, workspace_root=workspace_root)
    entry_path = frontend / "main.cjs"
    package_json_path = frontend / "package.json"
    if not package_json_path.exists():
        raise FileNotFoundError(f"3D Audio Graphs package.json not found: {package_json_path}")
    if not entry_path.exists():
        raise FileNotFoundError(f"3D Audio Graphs entrypoint not found: {entry_path}")

    launch_args = build_shell_launch_cli_args({
        "sessionId": _text_or_empty(open_response.get("sessionId"))
        or _text_or_empty(_mapping_or_empty(open_response.get("session")).get("sessionId")),
        "manifestPath": _text_or_empty(open_response.get("manifestPath"))
        or _text_or_empty(_resolve_cached_session(workspace_root).get("manifestPath")),
        "serviceEndpoint": _text_or_empty(_mapping_or_empty(open_response.get("service")).get("endpoint")),
        "originatingShell": AUDIO_ONSET_FINDER_SHELL_TYPE,
        "launchReason": "open-companion",
    })
    process_launcher = launch_process_factory or subprocess.Popen
    launched_process = process_launcher(
        [_resolve_npm_command(), "run", "electron:dev", "--", *launch_args],
        cwd=str(frontend),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    return {
        "targetShell": target_shell,
        "entryPath": str(entry_path),
        "pid": launched_process.pid,
    }


def open_audio_graphs_companion(
    *,
    workspace_root: str | Path | None = None,
    bootstrap_root: str | Path | None = None,
    frontend_root: str | Path | None = None,
    python_executable: str | None = None,
    launch_process_factory: Any | None = None,
) -> dict[str, Any]:
    workspace = _resolve_workspace_root(workspace_root)
    ensure_local_integration_session(
        workspace_root=workspace,
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
        launch_reason="open-companion-bootstrap",
    )
    open_response = _run_local_integration_command(
        build_audio_graphs_open_companion_envelope(workspace_root=workspace),
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
    )
    launched_process = _launch_audio_graphs_companion_process(
        open_response,
        frontend_root=frontend_root,
        workspace_root=workspace,
        launch_process_factory=launch_process_factory,
    )
    return {
        **open_response,
        "ok": True,
        "launchedProcess": launched_process,
    }


__all__ = [
    "AUDIO_GRAPHS_SHELL_TYPE",
    "AUDIO_ONSET_FINDER_SHELL_TYPE",
    "LOCAL_INTEGRATION_HOST_SHELL_ID",
    "LOCAL_INTEGRATION_HOST_STARTED_AT",
    "attach_to_local_integration_session",
    "build_audio_graphs_open_companion_envelope",
    "build_audio_onset_bootstrap_envelope",
    "build_audio_onset_attach_envelope",
    "consume_local_integration_launch_args",
    "ensure_local_integration_session",
    "open_audio_graphs_companion",
    "resolve_local_integration_bootstrap_path",
]