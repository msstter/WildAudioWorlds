"""Shared session manifest helpers for the thin local integration bootstrap."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_SESSION_SCHEMA_VERSION = "0.1"
DEFAULT_SESSION_MODE = "standalone"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return deepcopy(value) if isinstance(value, list) else []


def _text_or_empty(value: Any) -> str:
    return str(value or "").strip()


def _coerce_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = _mapping_or_empty(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def build_session_id(prefix: str = "waw-session") -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{timestamp}-{uuid4().hex[:8]}"


def resolve_session_manifest_path(workspace_root: str | Path, session_id: str) -> Path:
    root_path = Path(workspace_root).resolve()
    return root_path / "data" / "sessions" / str(session_id).strip() / "session_manifest.json"


def load_session_manifest(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path)
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    return _mapping_or_empty(loaded)


def save_session_manifest(manifest_path: str | Path, manifest: dict[str, Any]) -> None:
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    temp_path.replace(path)


def _normalize_peers(
    peers_payload: list[Any],
    *,
    host_shell: dict[str, Any],
    existing_peers: list[Any],
    now: str,
    auto_attach_host_peer: bool = True,
    detached_peer_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    detached_ids = {
        _text_or_empty(item)
        for item in (detached_peer_ids or [])
        if _text_or_empty(item)
    }

    for source in (existing_peers, peers_payload):
        for item in source:
            if not isinstance(item, dict):
                continue
            shell_id = _text_or_empty(item.get("shellId"))
            if not shell_id:
                continue
            normalized[shell_id] = _deep_merge(normalized.get(shell_id, {}), item)

    host_shell_id = _text_or_empty(host_shell.get("shellId"))
    if auto_attach_host_peer and host_shell_id:
        normalized[host_shell_id] = _deep_merge(normalized.get(host_shell_id, {}), {
            "shellId": host_shell_id,
            "shellType": _text_or_empty(host_shell.get("shellType")),
            "status": "attached",
            "attachedAt": _text_or_empty(normalized.get(host_shell_id, {}).get("attachedAt")) or _text_or_empty(host_shell.get("startedAt")) or now,
            "lastSeenAt": now,
        })

    for detached_peer_id in detached_ids:
        normalized.pop(detached_peer_id, None)

    for shell_id, peer in list(normalized.items()):
        normalized[shell_id] = {
            "shellId": shell_id,
            "shellType": _text_or_empty(peer.get("shellType")),
            "status": _text_or_empty(peer.get("status")) or "attached",
            "attachedAt": _text_or_empty(peer.get("attachedAt")) or now,
            "lastSeenAt": now,
        }

    return list(normalized.values())


def build_session_manifest(
    session_payload: dict[str, Any] | None,
    *,
    existing_manifest: dict[str, Any] | None = None,
    service_descriptor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session = _mapping_or_empty(session_payload)
    existing = _mapping_or_empty(existing_manifest)
    now = _iso_now()

    session_id = _text_or_empty(session.get("sessionId")) or _text_or_empty(existing.get("sessionId")) or build_session_id()
    host_shell = _deep_merge(_mapping_or_empty(existing.get("hostShell")), _mapping_or_empty(session.get("hostShell")))
    if host_shell:
        host_shell["startedAt"] = _text_or_empty(host_shell.get("startedAt")) or now

    service = _deep_merge(_mapping_or_empty(existing.get("service")), _mapping_or_empty(session.get("service")))
    if service_descriptor:
        service = _deep_merge(service, _mapping_or_empty(service_descriptor))

    detached_peer_ids = [
        _text_or_empty(item)
        for item in _list_or_empty(session.get("detachedPeerIds"))
        if _text_or_empty(item)
    ]
    auto_attach_host_value = session.get("autoAttachHostPeer")
    auto_attach_host_peer = auto_attach_host_value if isinstance(auto_attach_host_value, bool) else True

    peers = _normalize_peers(
        _list_or_empty(session.get("peers")),
        host_shell=host_shell,
        existing_peers=_list_or_empty(existing.get("peers")),
        now=now,
        auto_attach_host_peer=auto_attach_host_peer,
        detached_peer_ids=detached_peer_ids,
    )
    requested_mode = _text_or_empty(session.get("mode"))
    if requested_mode:
        mode = requested_mode
    elif len(peers) > 1:
        mode = "linked"
    else:
        mode = DEFAULT_SESSION_MODE

    manifest = {
        "schemaVersion": _text_or_empty(session.get("schemaVersion")) or _text_or_empty(existing.get("schemaVersion")) or DEFAULT_SESSION_SCHEMA_VERSION,
        "sessionId": session_id,
        "mode": mode,
        "stateRevision": _coerce_int(existing.get("stateRevision"), 0) + 1,
        "createdAt": _text_or_empty(existing.get("createdAt")) or _text_or_empty(session.get("createdAt")) or now,
        "updatedAt": now,
        "service": service,
        "hostShell": host_shell,
        "asset": _deep_merge(_mapping_or_empty(existing.get("asset")), _mapping_or_empty(session.get("asset"))),
        "transportState": _deep_merge(_mapping_or_empty(existing.get("transportState")), _mapping_or_empty(session.get("transportState"))),
        "launchContext": _deep_merge(_mapping_or_empty(existing.get("launchContext")), _mapping_or_empty(session.get("launchContext"))),
        "peers": peers,
    }
    return manifest


def build_session_summary(manifest: dict[str, Any], manifest_path: str | Path) -> dict[str, Any]:
    return {
        "schemaVersion": _text_or_empty(manifest.get("schemaVersion")) or DEFAULT_SESSION_SCHEMA_VERSION,
        "sessionId": _text_or_empty(manifest.get("sessionId")),
        "mode": _text_or_empty(manifest.get("mode")) or DEFAULT_SESSION_MODE,
        "stateRevision": _coerce_int(manifest.get("stateRevision"), 0),
        "createdAt": _text_or_empty(manifest.get("createdAt")),
        "updatedAt": _text_or_empty(manifest.get("updatedAt")),
        "manifestPath": str(Path(manifest_path).resolve()),
        "service": _mapping_or_empty(manifest.get("service")),
        "hostShell": _mapping_or_empty(manifest.get("hostShell")),
        "asset": _mapping_or_empty(manifest.get("asset")),
        "transportState": _mapping_or_empty(manifest.get("transportState")),
        "launchContext": _mapping_or_empty(manifest.get("launchContext")),
        "peers": _list_or_empty(manifest.get("peers")),
    }