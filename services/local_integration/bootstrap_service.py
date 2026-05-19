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
            packages_dir_str = str(packages_dir)
            if packages_dir_str not in sys.path:
                sys.path.insert(0, packages_dir_str)
            return parent
    raise RuntimeError("Unable to locate the shared packages directory for WildAudioWorlds.")


WORKSPACE_ROOT = _ensure_shared_package_path()

from wild_audio_worlds.session.session_manifest import (  # noqa: E402
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


def _ensure_session(envelope: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    workspace_root = _resolve_workspace_root(envelope)
    session_payload = _mapping_or_empty(envelope.get("session"))
    requested_session_id = _text_or_empty(session_payload.get("sessionId"))
    existing_manifest = {}
    if requested_session_id:
        existing_manifest = load_session_manifest(resolve_session_manifest_path(workspace_root, requested_session_id))

    manifest = build_session_manifest(
        session_payload,
        existing_manifest=existing_manifest,
        service_descriptor=_build_service_descriptor(envelope, session_payload),
    )
    manifest_path = resolve_session_manifest_path(workspace_root, manifest["sessionId"])
    save_session_manifest(manifest_path, manifest)
    return manifest, manifest_path


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

    manifest, manifest_path = _ensure_session(envelope)
    session_summary = build_session_summary(manifest, manifest_path)

    if command == "service/bootstrap":
        return {
            "ok": True,
            "session": session_summary,
        }

    payload = _mapping_or_empty(envelope.get("payload"))
    graph_project_root = _resolve_graph_project_root(envelope, _resolve_workspace_root(envelope))

    if command == "backend-call/run":
        response = _run_compatibility_runner(
            command,
            _resolve_backend_runner_path(graph_project_root),
            payload,
            cwd=graph_project_root,
        )
        return {
            "ok": True,
            "session": session_summary,
            "response": response,
        }

    if command == "recorded-audio/import":
        response = _run_compatibility_runner(
            command,
            _resolve_recorded_audio_import_runner_path(graph_project_root),
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