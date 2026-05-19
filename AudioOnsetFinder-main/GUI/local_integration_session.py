from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any
from urllib.parse import unquote, urlparse
from uuid import uuid4


def _ensure_shared_package_path() -> Path:
    current_path = Path(__file__).resolve()
    for parent in current_path.parents:
        packages_dir = parent / "packages"
        if (packages_dir / "wild_audio_worlds").exists():
            parent_str = str(parent)
            packages_dir_str = str(packages_dir)
            if parent_str not in sys.path:
                sys.path.insert(0, parent_str)
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
LOCAL_INTEGRATION_AUDIO_MANAGER_CACHE: dict[str, Any] = {}


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text_or_empty(value: Any) -> str:
    return str(value or "").strip()


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _resolve_cached_audio_manager_state(workspace_root: str | Path | None = None) -> dict[str, Any]:
    manifest = _load_cached_session_manifest(workspace_root)
    if manifest:
        return manifest
    return _resolve_cached_session(workspace_root)


def _normalize_audio_path(audio_path: str | Path) -> str:
    return str(Path(audio_path).resolve())


def normalize_local_integration_audio_path(audio_path: str | Path | None) -> str:
    normalized_audio_path = _text_or_empty(audio_path)
    if not normalized_audio_path:
        return ""

    parsed = urlparse(normalized_audio_path)
    if parsed.scheme == "file":
        return _normalize_audio_path(unquote(parsed.path))

    return _normalize_audio_path(normalized_audio_path)


def _build_audio_onset_asset_payload(
    audio_path: str | Path,
    *,
    asset_label: str = "",
    active_revision_id: str = "",
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    normalized_audio_path = _normalize_audio_path(audio_path)
    current_asset = _mapping_or_empty(_resolve_cached_audio_manager_state(workspace_root).get("asset"))
    current_source_audio_path = _text_or_empty(current_asset.get("sourceAudioPath"))
    current_asset_id = _text_or_empty(current_asset.get("assetId"))
    current_revision_id = _text_or_empty(current_asset.get("activeRevisionId"))
    normalized_label = _text_or_empty(asset_label) or Path(normalized_audio_path).name

    if current_source_audio_path == normalized_audio_path and current_asset_id:
        asset_id = current_asset_id
    else:
        asset_id = f"aof-asset:{normalized_audio_path}"

    if _text_or_empty(active_revision_id):
        revision_id = _text_or_empty(active_revision_id)
    elif current_source_audio_path == normalized_audio_path and current_revision_id:
        revision_id = current_revision_id
    else:
        revision_id = asset_id

    return {
        "assetId": asset_id,
        "assetLabel": normalized_label,
        "sourceAudioPath": normalized_audio_path,
        "sourceKind": "raw-audio",
        "activeRevisionId": revision_id,
        "updatedByShellId": LOCAL_INTEGRATION_HOST_SHELL_ID,
    }


def _build_audio_onset_selection_window(start_sec: float, end_sec: float) -> dict[str, Any]:
    normalized_start = max(0.0, float(min(start_sec, end_sec)))
    normalized_end = max(normalized_start, float(max(start_sec, end_sec)))
    return {
        "isReady": (normalized_end - normalized_start) > 0,
        "source": "audio-onset-finder-viewer",
        "selectionModel": "onset-editor-region",
        "currentTarget": "viewer-region",
        "timeRangeSec": {
            "start": normalized_start,
            "end": normalized_end,
            "duration": max(0.0, normalized_end - normalized_start),
        },
        "updatedByShellId": LOCAL_INTEGRATION_HOST_SHELL_ID,
    }


def _clear_audio_manager_publish_cache(*, workspace_root: str | Path | None = None) -> None:
    workspace = _resolve_workspace_root(workspace_root)
    LOCAL_INTEGRATION_AUDIO_MANAGER_CACHE[str(workspace)] = {}


def _audio_manager_publish_cache(workspace_root: str | Path | None = None) -> dict[str, Any]:
    workspace = _resolve_workspace_root(workspace_root)
    key = str(workspace)
    cache = LOCAL_INTEGRATION_AUDIO_MANAGER_CACHE.get(key)
    if isinstance(cache, dict):
        return cache
    LOCAL_INTEGRATION_AUDIO_MANAGER_CACHE[key] = {}
    return LOCAL_INTEGRATION_AUDIO_MANAGER_CACHE[key]


def get_local_integration_session_state(
    *,
    workspace_root: str | Path | None = None,
    bootstrap_root: str | Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    workspace = _resolve_workspace_root(workspace_root)
    ensure_local_integration_session(
        workspace_root=workspace,
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
        launch_reason="audio-manager-state-read",
    )
    return _run_local_integration_command(
        {
            "command": "session/get_state",
            "workspaceRoot": str(workspace),
            "payload": {
                "sessionId": _text_or_empty(_resolve_cached_session(workspace).get("sessionId")),
            },
        },
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
    )


def poll_local_integration_events(
    *,
    workspace_root: str | Path | None = None,
    bootstrap_root: str | Path | None = None,
    python_executable: str | None = None,
    after_event_id: int | None = None,
    limit: int = 25,
    wait_timeout_ms: int = 0,
) -> dict[str, Any]:
    workspace = _resolve_workspace_root(workspace_root)
    ensure_local_integration_session(
        workspace_root=workspace,
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
        launch_reason="audio-manager-event-poll",
    )

    cache = _audio_manager_publish_cache(workspace)
    normalized_after_event_id = after_event_id
    if normalized_after_event_id is None:
        normalized_after_event_id = int(cache.get("lastEventId") or 0)

    response = _run_local_integration_command(
        {
            "command": "events/poll",
            "workspaceRoot": str(workspace),
            "payload": {
                "sessionId": _text_or_empty(_resolve_cached_session(workspace).get("sessionId")),
                "afterEventId": max(0, int(normalized_after_event_id)),
                "limit": max(1, int(limit)),
                "waitTimeoutMs": max(0, int(wait_timeout_ms)),
            },
        },
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
    )

    events_state = _mapping_or_empty(response.get("eventsState"))
    latest_event_id = int(events_state.get("latestEventId") or 0)
    cache["lastEventId"] = latest_event_id
    if events_state.get("resetRequired"):
        cache["lastEventId"] = latest_event_id
    return response


def publish_audio_onset_asset_state(
    audio_path: str | Path,
    *,
    asset_label: str = "",
    active_revision_id: str = "",
    workspace_root: str | Path | None = None,
    bootstrap_root: str | Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    workspace = _resolve_workspace_root(workspace_root)
    ensure_local_integration_session(
        workspace_root=workspace,
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
        launch_reason="audio-manager-open-asset",
    )
    response = _run_local_integration_command(
        {
            "command": "session/open_asset",
            "workspaceRoot": str(workspace),
            "payload": {
                "sessionId": _text_or_empty(_resolve_cached_session(workspace).get("sessionId")),
                "asset": _build_audio_onset_asset_payload(
                    audio_path,
                    asset_label=asset_label,
                    active_revision_id=active_revision_id,
                    workspace_root=workspace,
                ),
                "updatedByShellId": LOCAL_INTEGRATION_HOST_SHELL_ID,
            },
        },
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
    )
    cache = _audio_manager_publish_cache(workspace)
    cache["assetKey"] = json.dumps(_mapping_or_empty(_mapping_or_empty(response.get("session")).get("asset")), sort_keys=True)
    return response


def publish_audio_onset_playhead(
    playhead_sec: float,
    *,
    workspace_root: str | Path | None = None,
    bootstrap_root: str | Path | None = None,
    python_executable: str | None = None,
    force: bool = False,
    min_interval_sec: float = 0.15,
    min_delta_sec: float = 0.1,
) -> dict[str, Any]:
    normalized_playhead_sec = _float_or_none(playhead_sec)
    if normalized_playhead_sec is None:
        raise ValueError("AudioOnsetFinder playhead publish requires a numeric playheadSec.")

    workspace = _resolve_workspace_root(workspace_root)
    cache = _audio_manager_publish_cache(workspace)
    now = time.monotonic()
    last_published_at = _float_or_none(cache.get("playheadPublishedAt")) or 0.0
    last_playhead_sec = _float_or_none(cache.get("playheadSec"))
    if (
        not force
        and last_playhead_sec is not None
        and abs(normalized_playhead_sec - last_playhead_sec) < float(min_delta_sec)
        and (now - last_published_at) < float(min_interval_sec)
    ):
        return {}

    ensure_local_integration_session(
        workspace_root=workspace,
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
        launch_reason="audio-manager-transport-time",
    )
    response = _run_local_integration_command(
        {
            "command": "transport/set_time",
            "workspaceRoot": str(workspace),
            "payload": {
                "sessionId": _text_or_empty(_resolve_cached_session(workspace).get("sessionId")),
                "playheadSec": normalized_playhead_sec,
                "updatedByShellId": LOCAL_INTEGRATION_HOST_SHELL_ID,
            },
        },
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
    )
    cache["playheadSec"] = normalized_playhead_sec
    cache["playheadPublishedAt"] = now
    return response


def publish_audio_onset_selection(
    start_sec: float,
    end_sec: float,
    *,
    playhead_sec: float | None = None,
    workspace_root: str | Path | None = None,
    bootstrap_root: str | Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    workspace = _resolve_workspace_root(workspace_root)
    ensure_local_integration_session(
        workspace_root=workspace,
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
        launch_reason="audio-manager-transport-selection",
    )

    payload: dict[str, Any] = {
        "sessionId": _text_or_empty(_resolve_cached_session(workspace).get("sessionId")),
        "selectionWindow": _build_audio_onset_selection_window(start_sec, end_sec),
        "updatedByShellId": LOCAL_INTEGRATION_HOST_SHELL_ID,
    }
    normalized_playhead_sec = _float_or_none(playhead_sec)
    if normalized_playhead_sec is not None:
        payload["playheadSec"] = normalized_playhead_sec

    response = _run_local_integration_command(
        {
            "command": "transport/set_selection",
            "workspaceRoot": str(workspace),
            "payload": payload,
        },
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
    )
    cache = _audio_manager_publish_cache(workspace)
    cache["selectionKey"] = json.dumps(payload["selectionWindow"], sort_keys=True)
    if normalized_playhead_sec is not None:
        cache["playheadSec"] = normalized_playhead_sec
        cache["playheadPublishedAt"] = time.monotonic()
    return response


def clear_audio_onset_selection(
    *,
    playhead_sec: float | None = None,
    workspace_root: str | Path | None = None,
    bootstrap_root: str | Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    workspace = _resolve_workspace_root(workspace_root)
    ensure_local_integration_session(
        workspace_root=workspace,
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
        launch_reason="audio-manager-clear-selection",
    )

    payload: dict[str, Any] = {
        "sessionId": _text_or_empty(_resolve_cached_session(workspace).get("sessionId")),
        "selectionWindow": {
            "isReady": False,
            "source": "audio-onset-finder-viewer",
            "selectionModel": "onset-editor-region",
            "currentTarget": "viewer-region",
            "updatedByShellId": LOCAL_INTEGRATION_HOST_SHELL_ID,
        },
        "updatedByShellId": LOCAL_INTEGRATION_HOST_SHELL_ID,
    }
    normalized_playhead_sec = _float_or_none(playhead_sec)
    if normalized_playhead_sec is not None:
        payload["playheadSec"] = normalized_playhead_sec

    response = _run_local_integration_command(
        {
            "command": "transport/set_selection",
            "workspaceRoot": str(workspace),
            "payload": payload,
        },
        bootstrap_root=bootstrap_root,
        python_executable=python_executable,
    )
    cache = _audio_manager_publish_cache(workspace)
    cache["selectionKey"] = json.dumps(payload["selectionWindow"], sort_keys=True)
    if normalized_playhead_sec is not None:
        cache["playheadSec"] = normalized_playhead_sec
        cache["playheadPublishedAt"] = time.monotonic()
    return response


def _load_manifest_service_descriptor(manifest_path: str | Path | None) -> dict[str, Any]:
    normalized_manifest_path = _text_or_empty(manifest_path)
    if not normalized_manifest_path:
        return {}

    path = Path(normalized_manifest_path)
    if not path.exists():
        return {}

    return _mapping_or_empty(load_session_manifest(path).get("service"))


def _resolve_service_transport(endpoint: str, transport: str) -> str:
    normalized_transport = _text_or_empty(transport)
    if normalized_transport:
        return normalized_transport
    if endpoint.endswith(".py"):
        return "stdio"
    return "unix-domain-socket" if endpoint else ""


def _resolve_envelope_service_descriptor(envelope: dict[str, Any], workspace_root: Path) -> dict[str, str]:
    explicit_endpoint = _text_or_empty(envelope.get("serviceEndpoint"))
    explicit_transport = _text_or_empty(envelope.get("serviceTransport"))
    if explicit_endpoint:
        return {
            "endpoint": explicit_endpoint,
            "transport": _resolve_service_transport(explicit_endpoint, explicit_transport),
        }

    cached_service = _mapping_or_empty(_resolve_cached_session(workspace_root).get("service"))
    cached_endpoint = _text_or_empty(cached_service.get("endpoint"))
    if cached_endpoint:
        return {
            "endpoint": cached_endpoint,
            "transport": _resolve_service_transport(cached_endpoint, _text_or_empty(cached_service.get("transport"))),
        }

    manifest_service = _load_manifest_service_descriptor(envelope.get("manifestPath"))
    manifest_endpoint = _text_or_empty(manifest_service.get("endpoint"))
    if manifest_endpoint:
        return {
            "endpoint": manifest_endpoint,
            "transport": _resolve_service_transport(manifest_endpoint, _text_or_empty(manifest_service.get("transport"))),
        }

    return {}


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

    service_descriptor = _resolve_envelope_service_descriptor(normalized_envelope, workspace)
    service_endpoint = _text_or_empty(service_descriptor.get("endpoint"))
    service_transport = _text_or_empty(service_descriptor.get("transport"))
    if _text_or_empty(normalized_envelope.get("command")) != "service/bootstrap" and service_endpoint and service_transport != "stdio":
        from services.local_integration.service_runtime import send_service_command

        try:
            parsed_payload = _mapping_or_empty(send_service_command(service_endpoint, normalized_envelope))
        except Exception:
            parsed_payload = {}
        else:
            if not parsed_payload.get("ok"):
                error_message = _text_or_empty(parsed_payload.get("error")) or "AudioOnsetFinder local integration service command failed."
                raise RuntimeError(error_message)
            _update_local_integration_session_cache(parsed_payload, workspace_root=workspace)
            return parsed_payload

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
        "manifestPath": _text_or_empty(launch_request.get("manifestPath")),
        "serviceEndpoint": _text_or_empty(launch_request.get("serviceEndpoint")),
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
    "clear_audio_onset_selection",
    "consume_local_integration_launch_args",
    "ensure_local_integration_session",
    "get_local_integration_session_state",
    "normalize_local_integration_audio_path",
    "open_audio_graphs_companion",
    "poll_local_integration_events",
    "publish_audio_onset_asset_state",
    "publish_audio_onset_playhead",
    "publish_audio_onset_selection",
    "resolve_local_integration_bootstrap_path",
]