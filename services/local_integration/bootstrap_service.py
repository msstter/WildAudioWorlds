from __future__ import annotations

import json
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any


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

from wild_audio_worlds.session.session_manifest import (  # noqa: E402
    build_session_id,
    build_session_manifest,
    build_session_summary,
    load_session_manifest,
    resolve_session_manifest_path,
    save_session_manifest,
)


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text_or_empty(value: Any) -> str:
    return str(value or "").strip()


def _read_envelope() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("No JSON payload received for the local integration service bootstrap.")

    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Local integration service payload must be a JSON object.")
    return payload


def _resolve_workspace_root(envelope: dict[str, Any]) -> Path:
    workspace_root = _text_or_empty(envelope.get("workspaceRoot"))
    return Path(workspace_root).resolve() if workspace_root else WORKSPACE_ROOT


def _resolve_graph_project_root(envelope: dict[str, Any], workspace_root: Path) -> Path:
    project_root = _text_or_empty(envelope.get("projectRoot"))
    if project_root:
        return Path(project_root).resolve()
    return (workspace_root / "3DAudioGraphs-main").resolve()


def _resolve_backend_runner_path(graph_project_root: Path) -> Path:
    return graph_project_root / "backend" / "run_selection_analysis.py"


def _resolve_recorded_audio_import_runner_path(graph_project_root: Path) -> Path:
    return graph_project_root / "backend" / "import_recorded_audio.py"


def _resolve_graph_process_asset_runner_path(graph_project_root: Path) -> Path:
    return graph_project_root / "backend" / "process_graph_asset.py"


def _resolve_runner_path(command: str, graph_project_root: Path) -> Path:
    if command == "backend-call/run":
        return _resolve_backend_runner_path(graph_project_root)
    if command == "recorded-audio/import":
        return _resolve_recorded_audio_import_runner_path(graph_project_root)
    if command == "graph/process_asset":
        return _resolve_graph_process_asset_runner_path(graph_project_root)
    raise ValueError(f"Unsupported compatibility runner command: {command}")


def _build_service_descriptor(envelope: dict[str, Any], session_payload: dict[str, Any]) -> dict[str, Any]:
    host_shell = _mapping_or_empty(session_payload.get("hostShell"))
    launch_context = _mapping_or_empty(session_payload.get("launchContext"))
    owner_shell_id = _text_or_empty(host_shell.get("shellId"))
    owner_shell_type = _text_or_empty(host_shell.get("shellType")) or _text_or_empty(launch_context.get("originatingShell")) or "audio-graphs"

    return {
        "protocolVersion": "0.1",
        "transport": "stdio",
        "endpoint": str(Path(__file__).resolve()),
        "bootMode": f"spawned-by-{owner_shell_type}",
        "ownerShellId": owner_shell_id,
    }


def _save_session(
    workspace_root: Path,
    session_payload: dict[str, Any],
    *,
    existing_manifest: dict[str, Any] | None = None,
    service_descriptor: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path]:
    manifest = build_session_manifest(
        session_payload,
        existing_manifest=existing_manifest,
        service_descriptor=service_descriptor,
    )
    manifest_path = resolve_session_manifest_path(workspace_root, manifest["sessionId"])
    save_session_manifest(manifest_path, manifest)
    _sync_persistent_service_session_state(manifest)
    return manifest, manifest_path


def _sync_persistent_service_session_state(manifest: dict[str, Any]) -> None:
    service_descriptor = _mapping_or_empty(manifest.get("service"))
    endpoint = _text_or_empty(service_descriptor.get("endpoint"))
    transport = _text_or_empty(service_descriptor.get("transport"))
    if not endpoint or transport == "stdio":
        return

    try:
        from services.local_integration.service_runtime import send_service_command

        send_service_command(endpoint, {"command": "session/sync_manifest"}, timeout=1.0)
    except Exception:
        return


def _ensure_session(envelope: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    workspace_root = _resolve_workspace_root(envelope)
    session_payload = _mapping_or_empty(envelope.get("session"))
    requested_session_id = _text_or_empty(session_payload.get("sessionId"))
    existing_manifest = {}
    if requested_session_id:
        existing_manifest = load_session_manifest(resolve_session_manifest_path(workspace_root, requested_session_id))

    return _save_session(
        workspace_root,
        session_payload,
        existing_manifest=existing_manifest,
        service_descriptor=None if _mapping_or_empty(existing_manifest.get("service")) else _build_service_descriptor(envelope, session_payload),
    )


def _prepare_bootstrap_session(envelope: dict[str, Any]) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    workspace_root = _resolve_workspace_root(envelope)
    session_payload = _mapping_or_empty(envelope.get("session"))
    session_id = _text_or_empty(session_payload.get("sessionId")) or build_session_id()
    session_payload["sessionId"] = session_id

    existing_manifest = load_session_manifest(resolve_session_manifest_path(workspace_root, session_id))
    host_shell = _mapping_or_empty(session_payload.get("hostShell"))
    launch_context = _mapping_or_empty(session_payload.get("launchContext"))

    from services.local_integration.service_runtime import ensure_persistent_service

    service_descriptor = ensure_persistent_service(
        workspace_root,
        session_id,
        owner_shell_id=_text_or_empty(host_shell.get("shellId")),
        owner_shell_type=_text_or_empty(host_shell.get("shellType"))
        or _text_or_empty(launch_context.get("originatingShell"))
        or "audio-graphs",
    )
    return workspace_root, session_payload, existing_manifest, service_descriptor


def _load_existing_session(envelope: dict[str, Any], *, command: str) -> tuple[Path, dict[str, Any], Path]:
    workspace_root = _resolve_workspace_root(envelope)
    payload = _mapping_or_empty(envelope.get("payload"))
    session_payload = _mapping_or_empty(envelope.get("session"))
    session_id = (
        _text_or_empty(payload.get("sessionId"))
        or _text_or_empty(envelope.get("sessionId"))
        or _text_or_empty(session_payload.get("sessionId"))
    )
    if not session_id:
        raise ValueError(f"{command} payload is missing sessionId.")

    manifest_path = resolve_session_manifest_path(workspace_root, session_id)
    existing_manifest = load_session_manifest(manifest_path)
    if not existing_manifest:
        raise FileNotFoundError(f"Session manifest not found for {command}: {manifest_path}")

    return workspace_root, existing_manifest, manifest_path


def _build_session_response_fields(manifest: dict[str, Any], manifest_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    session_summary = build_session_summary(manifest, manifest_path)
    response_fields = {
        "sessionId": session_summary["sessionId"],
        "mode": session_summary["mode"],
        "stateRevision": session_summary["stateRevision"],
        "manifestPath": session_summary["manifestPath"],
        "service": _mapping_or_empty(manifest.get("service")),
        "manifest": manifest,
    }
    return session_summary, response_fields


def _build_open_companion_session_payload(
    envelope: dict[str, Any],
    existing_manifest: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = _mapping_or_empty(envelope.get("payload"))
    envelope_session = _mapping_or_empty(envelope.get("session"))
    existing_host_shell = _mapping_or_empty(existing_manifest.get("hostShell"))
    origin_shell = _mapping_or_empty(request.get("originShell")) or _mapping_or_empty(envelope_session.get("hostShell")) or existing_host_shell
    request_launch_context = _mapping_or_empty(request.get("launchContext"))
    target_shell = _text_or_empty(request.get("targetShell")) or _text_or_empty(request_launch_context.get("requestedCompanion"))
    if not target_shell:
        raise ValueError("shell/open_companion payload is missing targetShell.")

    launch_context = {
        **_mapping_or_empty(existing_manifest.get("launchContext")),
        **request_launch_context,
    }
    requested_by_shell_id = (
        _text_or_empty(request_launch_context.get("requestedByShellId"))
        or _text_or_empty(origin_shell.get("shellId"))
        or _text_or_empty(launch_context.get("requestedByShellId"))
    )
    launch_context.update({
        "originatingShell": _text_or_empty(request_launch_context.get("originatingShell"))
        or _text_or_empty(launch_context.get("originatingShell"))
        or _text_or_empty(origin_shell.get("shellType"))
        or _text_or_empty(existing_host_shell.get("shellType")),
        "launchReason": _text_or_empty(request_launch_context.get("launchReason"))
        or _text_or_empty(launch_context.get("launchReason"))
        or "open-companion",
        "requestedCompanion": target_shell,
        "requestedByShellId": requested_by_shell_id,
    })

    session_payload: dict[str, Any] = {
        "sessionId": _text_or_empty(existing_manifest.get("sessionId")),
        "hostShell": origin_shell or existing_host_shell,
        "launchContext": launch_context,
    }

    asset = _mapping_or_empty(request.get("asset")) or _mapping_or_empty(envelope_session.get("asset"))
    if asset:
        session_payload["asset"] = asset

    transport_state = _mapping_or_empty(request.get("transportState")) or _mapping_or_empty(envelope_session.get("transportState"))
    if transport_state:
        session_payload["transportState"] = transport_state

    return session_payload, {
        "shellType": target_shell,
        "status": "requested",
        "requestedByShellId": requested_by_shell_id,
    }


def _build_session_attach_payload(
    envelope: dict[str, Any],
    existing_manifest: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = _mapping_or_empty(envelope.get("payload"))
    envelope_session = _mapping_or_empty(envelope.get("session"))
    shell = _mapping_or_empty(request.get("shell")) or _mapping_or_empty(envelope_session.get("hostShell"))
    shell_id = _text_or_empty(shell.get("shellId"))
    shell_type = _text_or_empty(shell.get("shellType"))
    if not shell_id or not shell_type:
        raise ValueError("session/attach payload is missing shell.shellId or shell.shellType.")

    launch_context = _mapping_or_empty(existing_manifest.get("launchContext"))
    if not _text_or_empty(launch_context.get("originatingShell")):
        launch_context["originatingShell"] = _text_or_empty(_mapping_or_empty(existing_manifest.get("hostShell")).get("shellType")) or shell_type
    if not _text_or_empty(launch_context.get("launchReason")):
        launch_context["launchReason"] = "session-attach"

    requested_capabilities = request.get("requestedCapabilities")
    normalized_capabilities = [
        str(item).strip()
        for item in requested_capabilities
        if isinstance(item, str) and str(item).strip()
    ] if isinstance(requested_capabilities, list) else []

    session_payload = {
        "sessionId": _text_or_empty(existing_manifest.get("sessionId")),
        "launchContext": launch_context,
        "peers": [{
            "shellId": shell_id,
            "shellType": shell_type,
            "status": "attached",
            "attachedAt": _text_or_empty(shell.get("startedAt")),
            "lastSeenAt": _text_or_empty(shell.get("startedAt")),
        }],
    }

    return session_payload, {
        "shellId": shell_id,
        "shellType": shell_type,
        "status": "attached",
        "requestedCapabilities": normalized_capabilities,
        "lastKnownStateRevision": request.get("lastKnownStateRevision"),
    }


def _build_session_detach_payload(
    envelope: dict[str, Any],
    existing_manifest: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = _mapping_or_empty(envelope.get("payload"))
    shell = _mapping_or_empty(request.get("shell"))
    shell_id = _text_or_empty(request.get("shellId")) or _text_or_empty(shell.get("shellId"))
    if not shell_id:
        raise ValueError("session/detach payload is missing shellId.")

    existing_peer = {}
    for peer in existing_manifest.get("peers", []):
        if isinstance(peer, dict) and _text_or_empty(peer.get("shellId")) == shell_id:
            existing_peer = peer
            break

    if not existing_peer:
        raise ValueError(f"session/detach requested shellId is not attached: {shell_id}")

    detach_reason = _text_or_empty(request.get("reason")) or "detached"
    session_payload = {
        "sessionId": _text_or_empty(existing_manifest.get("sessionId")),
        "autoAttachHostPeer": False,
        "detachedPeerIds": [shell_id],
    }

    return session_payload, {
        "shellId": shell_id,
        "shellType": _text_or_empty(existing_peer.get("shellType")) or _text_or_empty(shell.get("shellType")),
        "status": "detached",
        "reason": detach_reason,
    }


def _parse_runner_output(stdout: str, *, command: str) -> dict[str, Any]:
    output_lines = stdout.strip().splitlines()
    if not output_lines:
        raise ValueError(f"{command} did not return a JSON payload.")

    try:
        payload = json.loads(output_lines[-1])
    except json.JSONDecodeError as error:
        raise ValueError(f"{command} returned invalid JSON: {error}") from error

    if not isinstance(payload, dict):
        raise ValueError(f"{command} returned a non-object JSON payload.")
    return payload


def _run_compatibility_runner(command: str, runner_path: Path, payload: dict[str, Any], *, cwd: Path) -> dict[str, Any]:
    if not runner_path.exists():
        raise FileNotFoundError(f"Compatibility runner not found for {command}: {runner_path}")

    result = subprocess.run(
        [sys.executable, str(runner_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(cwd),
        check=False,
    )

    if result.stderr:
        sys.stderr.write(result.stderr)
        sys.stderr.flush()

    parsed = _parse_runner_output(result.stdout or "", command=command)
    if result.returncode != 0 and parsed.get("ok") is True:
        raise ValueError(f"{command} exited with code {result.returncode} but reported ok=true.")
    return parsed


def _handle_command(envelope: dict[str, Any]) -> dict[str, Any]:
    command = _text_or_empty(envelope.get("command"))
    if not command:
        raise ValueError("Local integration bootstrap payload is missing command.")

    if command == "service/bootstrap":
        workspace_root, session_payload, existing_manifest, service_descriptor = _prepare_bootstrap_session(envelope)
        manifest, manifest_path = _save_session(
            workspace_root,
            session_payload,
            existing_manifest=existing_manifest,
            service_descriptor=service_descriptor,
        )
        session_summary = build_session_summary(manifest, manifest_path)
        return {
            "ok": True,
            "session": session_summary,
        }

    if command == "shell/open_companion":
        workspace_root, existing_manifest, _ = _load_existing_session(envelope, command=command)
        session_payload, launched_shell = _build_open_companion_session_payload(envelope, existing_manifest)
        manifest, manifest_path = _save_session(
            workspace_root,
            session_payload,
            existing_manifest=existing_manifest,
        )
        session_summary, response_fields = _build_session_response_fields(manifest, manifest_path)
        return {
            "ok": True,
            "session": session_summary,
            **response_fields,
            "launchedShell": launched_shell,
        }

    if command == "session/attach":
        workspace_root, existing_manifest, _ = _load_existing_session(envelope, command=command)
        session_payload, attached_shell = _build_session_attach_payload(envelope, existing_manifest)
        manifest, manifest_path = _save_session(
            workspace_root,
            session_payload,
            existing_manifest=existing_manifest,
        )
        session_summary, response_fields = _build_session_response_fields(manifest, manifest_path)
        return {
            "ok": True,
            "session": session_summary,
            **response_fields,
            "attachedShell": attached_shell,
        }

    if command == "session/detach":
        workspace_root, existing_manifest, _ = _load_existing_session(envelope, command=command)
        session_payload, detached_shell = _build_session_detach_payload(envelope, existing_manifest)
        manifest, manifest_path = _save_session(
            workspace_root,
            session_payload,
            existing_manifest=existing_manifest,
        )
        session_summary, response_fields = _build_session_response_fields(manifest, manifest_path)
        return {
            "ok": True,
            "session": session_summary,
            **response_fields,
            "detachedShell": detached_shell,
        }

    manifest, manifest_path = _ensure_session(envelope)
    session_summary = build_session_summary(manifest, manifest_path)

    payload = _mapping_or_empty(envelope.get("payload"))
    graph_project_root = _resolve_graph_project_root(envelope, _resolve_workspace_root(envelope))

    if command in {"backend-call/run", "recorded-audio/import", "graph/process_asset"}:
        response = _run_compatibility_runner(
            command,
            _resolve_runner_path(command, graph_project_root),
            payload,
            cwd=graph_project_root,
        )
        return {
            "ok": True,
            "session": session_summary,
            "response": response,
        }

    raise ValueError(f"Unsupported local integration bootstrap command: {command}")


def main() -> int:
    try:
        response = _handle_command(_read_envelope())
        sys.stdout.write(json.dumps(response))
        sys.stdout.flush()
        return 0
    except Exception as error:
        failure = {
            "ok": False,
            "error": str(error),
            "traceback": traceback.format_exc(),
        }
        sys.stdout.write(json.dumps(failure))
        sys.stdout.flush()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())