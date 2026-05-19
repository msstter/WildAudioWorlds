"""Service-owned audio session state helpers for the persistent local integration service."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Mapping

from wild_audio_worlds.session.selection_contracts import normalize_backend_selection_contract
from wild_audio_worlds.session.session_manifest import (
    build_session_manifest,
    build_session_summary,
    load_session_manifest,
    resolve_session_manifest_path,
    save_session_manifest,
)


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return deepcopy(value) if isinstance(value, list) else []


def _text_or_empty(value: Any) -> str:
    return str(value or "").strip()


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(fallback)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AudioManager:
    def __init__(
        self,
        workspace_root: str | Path,
        session_id: str,
        *,
        service_descriptor_provider: Callable[[], dict[str, Any]],
    ):
        self.workspace_root = Path(workspace_root).resolve()
        self.session_id = _text_or_empty(session_id)
        self._service_descriptor_provider = service_descriptor_provider
        self._manifest_path = resolve_session_manifest_path(self.workspace_root, self.session_id)
        self._lock = RLock()
        self._manifest = load_session_manifest(self._manifest_path)

    @property
    def manifest_path(self) -> Path:
        return self._manifest_path

    def current_manifest(self) -> dict[str, Any]:
        with self._lock:
            return _mapping_or_empty(self._manifest)

    def session_summary(self) -> dict[str, Any]:
        manifest = self.current_manifest()
        if not manifest:
            manifest = {
                "sessionId": self.session_id,
                "service": self._service_descriptor_provider(),
            }
        return build_session_summary(manifest, self._manifest_path)

    def state_snapshot(self, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
        normalized_manifest = _mapping_or_empty(manifest) if manifest is not None else self.current_manifest()
        return {
            "hostShell": _mapping_or_empty(normalized_manifest.get("hostShell")),
            "asset": _mapping_or_empty(normalized_manifest.get("asset")),
            "transportState": _mapping_or_empty(normalized_manifest.get("transportState")),
            "launchContext": _mapping_or_empty(normalized_manifest.get("launchContext")),
            "peers": _list_or_empty(normalized_manifest.get("peers")),
        }

    def sync_from_disk(self) -> dict[str, Any]:
        loaded_manifest = load_session_manifest(self._manifest_path)
        if loaded_manifest:
            with self._lock:
                self._manifest = loaded_manifest
        return self.current_manifest()

    def sync_from_manifest(self, manifest: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized_manifest = _mapping_or_empty(manifest)
        if normalized_manifest:
            with self._lock:
                self._manifest = normalized_manifest
        return self.current_manifest()

    def apply_session_payload(
        self,
        session_payload: Mapping[str, Any] | None,
        *,
        existing_manifest: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_payload = _mapping_or_empty(session_payload)
        normalized_payload["sessionId"] = _text_or_empty(normalized_payload.get("sessionId")) or self.session_id

        with self._lock:
            base_manifest = _mapping_or_empty(existing_manifest) if existing_manifest is not None else _mapping_or_empty(self._manifest)
            manifest = build_session_manifest(
                normalized_payload,
                existing_manifest=base_manifest,
                service_descriptor=self._service_descriptor_provider(),
            )
            save_session_manifest(self._manifest_path, manifest)
            self._manifest = manifest

        return _mapping_or_empty(manifest)

    def open_asset(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        request = _mapping_or_empty(payload)
        asset_updates = _mapping_or_empty(request.get("asset"))
        base_manifest = self.current_manifest()
        previous_asset = _mapping_or_empty(base_manifest.get("asset"))
        previous_asset_id = _text_or_empty(previous_asset.get("assetId"))
        previous_source_audio_path = _text_or_empty(previous_asset.get("sourceAudioPath"))
        asset_id = _text_or_empty(request.get("assetId")) or _text_or_empty(asset_updates.get("assetId"))
        if not asset_id:
            raise ValueError("session/open_asset payload is missing asset.assetId.")

        current_asset = _mapping_or_empty(previous_asset)
        current_asset.update(asset_updates)
        current_asset["assetId"] = asset_id

        next_source_audio_path = _text_or_empty(asset_updates.get("sourceAudioPath"))
        asset_switched = (
            (previous_asset_id and previous_asset_id != asset_id)
            or (next_source_audio_path and previous_source_audio_path and previous_source_audio_path != next_source_audio_path)
        )
        if asset_switched and "revisionState" not in asset_updates:
            current_asset.pop("revisionState", None)

        updated_by_shell_id = _text_or_empty(request.get("updatedByShellId")) or _text_or_empty(current_asset.get("updatedByShellId"))
        if updated_by_shell_id:
            current_asset["updatedByShellId"] = updated_by_shell_id

        session_payload: dict[str, Any] = {
            "sessionId": self.session_id,
            "asset": current_asset,
        }

        transport_updates = _mapping_or_empty(request.get("transportState"))
        if transport_updates:
            session_payload["transportState"] = self._merge_transport_state(
                transport_updates,
                updated_by_shell_id=updated_by_shell_id,
            )

        base_manifest["asset"] = _mapping_or_empty(current_asset)
        if "transportState" in session_payload:
            base_manifest["transportState"] = _mapping_or_empty(session_payload["transportState"])

        return self.apply_session_payload(session_payload, existing_manifest=base_manifest)

    def clear_asset(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        request = _mapping_or_empty(payload)
        updated_by_shell_id = _text_or_empty(request.get("updatedByShellId"))
        base_manifest = self.current_manifest()
        base_manifest["asset"] = {}

        session_payload: dict[str, Any] = {
            "sessionId": self.session_id,
            "asset": {},
        }

        transport_updates = _mapping_or_empty(request.get("transportState"))
        if transport_updates:
            session_payload["transportState"] = self._merge_transport_state(
                transport_updates,
                current_transport=base_manifest.get("transportState"),
                updated_by_shell_id=updated_by_shell_id,
            )

        return self.apply_session_payload(session_payload, existing_manifest=base_manifest)

    def set_playhead(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        request = _mapping_or_empty(payload)
        if "playheadSec" not in request:
            raise ValueError("transport/set_time payload is missing playheadSec.")

        playhead_sec = _coerce_float(request.get("playheadSec"))
        if playhead_sec is None:
            raise ValueError("transport/set_time payload playheadSec must be numeric.")

        transport_state = self._merge_transport_state(
            {"playheadSec": playhead_sec},
            updated_by_shell_id=_text_or_empty(request.get("updatedByShellId")),
        )
        return self.apply_session_payload({
            "sessionId": self.session_id,
            "transportState": transport_state,
        })

    def set_selection(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        request = _mapping_or_empty(payload)
        selection_window = request.get("selectionWindow")
        if not isinstance(selection_window, Mapping):
            raise ValueError("transport/set_selection payload is missing selectionWindow.")

        transport_state = self._merge_transport_state(
            {"selectionWindow": selection_window},
            updated_by_shell_id=_text_or_empty(request.get("updatedByShellId")),
        )

        if "playheadSec" in request:
            playhead_sec = _coerce_float(request.get("playheadSec"))
            if playhead_sec is None:
                raise ValueError("transport/set_selection payload playheadSec must be numeric when provided.")
            transport_state["playheadSec"] = playhead_sec

        return self.apply_session_payload({
            "sessionId": self.session_id,
            "transportState": transport_state,
        })

    def set_revision(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        request = _mapping_or_empty(payload)
        base_manifest = self.current_manifest()
        current_asset = _mapping_or_empty(base_manifest.get("asset"))
        asset_updates = _mapping_or_empty(request.get("asset"))
        current_asset.update(asset_updates)

        asset_id = _text_or_empty(request.get("assetId")) or _text_or_empty(current_asset.get("assetId"))
        if not asset_id:
            raise ValueError("asset/set_revision payload is missing assetId.")

        active_revision_id = _text_or_empty(request.get("activeRevisionId")) or _text_or_empty(request.get("revisionId"))
        if not active_revision_id:
            raise ValueError("asset/set_revision payload is missing activeRevisionId.")

        current_asset["assetId"] = asset_id
        current_asset["activeRevisionId"] = active_revision_id

        updated_by_shell_id = _text_or_empty(request.get("updatedByShellId")) or _text_or_empty(current_asset.get("updatedByShellId"))
        if updated_by_shell_id:
            current_asset["updatedByShellId"] = updated_by_shell_id

        revision_state = _mapping_or_empty(current_asset.get("revisionState"))
        now = _iso_now()
        revision_state["isDirty"] = False
        revision_state["status"] = "clean"
        revision_state["lastReadyRevisionId"] = active_revision_id
        revision_state["lastReadyAt"] = now
        revision_state["updatedAt"] = now
        revision_state.pop("pendingRevisionId", None)
        revision_state.pop("requestedAt", None)
        revision_state.pop("failureMessage", None)
        if updated_by_shell_id:
            revision_state["updatedByShellId"] = updated_by_shell_id
        current_asset["revisionState"] = revision_state

        base_manifest["asset"] = _mapping_or_empty(current_asset)

        return self.apply_session_payload({
            "sessionId": self.session_id,
            "asset": current_asset,
        }, existing_manifest=base_manifest)

    def set_dirty_state(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        request = _mapping_or_empty(payload)
        base_manifest = self.current_manifest()
        current_asset = _mapping_or_empty(base_manifest.get("asset"))
        asset_updates = _mapping_or_empty(request.get("asset"))
        current_asset.update(asset_updates)

        asset_id = _text_or_empty(request.get("assetId")) or _text_or_empty(current_asset.get("assetId"))
        if not asset_id:
            raise ValueError("asset/set_dirty_state payload is missing assetId.")

        current_asset["assetId"] = asset_id

        updated_by_shell_id = _text_or_empty(request.get("updatedByShellId")) or _text_or_empty(current_asset.get("updatedByShellId"))
        if updated_by_shell_id:
            current_asset["updatedByShellId"] = updated_by_shell_id

        revision_state = _mapping_or_empty(current_asset.get("revisionState"))
        is_dirty = _coerce_bool(request.get("isDirty"), True)
        pending_revision_id = _text_or_empty(revision_state.get("pendingRevisionId"))
        if "pendingRevisionId" in request:
            pending_revision_id = _text_or_empty(request.get("pendingRevisionId"))

        now = _iso_now()
        revision_state["isDirty"] = is_dirty
        revision_state["status"] = "dirty" if is_dirty else "clean"
        revision_state["updatedAt"] = now
        if updated_by_shell_id:
            revision_state["updatedByShellId"] = updated_by_shell_id

        if is_dirty and pending_revision_id:
            revision_state["pendingRevisionId"] = pending_revision_id
            revision_state["requestedAt"] = now
        else:
            revision_state.pop("pendingRevisionId", None)
            if not is_dirty:
                revision_state.pop("requestedAt", None)

        if not is_dirty:
            revision_state.pop("failureMessage", None)

        current_asset["revisionState"] = revision_state
        base_manifest["asset"] = _mapping_or_empty(current_asset)
        return self.apply_session_payload({
            "sessionId": self.session_id,
            "asset": current_asset,
        }, existing_manifest=base_manifest)

    def mark_revision_ready(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        request = _mapping_or_empty(payload)
        base_manifest = self.current_manifest()
        current_asset = _mapping_or_empty(base_manifest.get("asset"))
        asset_updates = _mapping_or_empty(request.get("asset"))
        current_asset.update(asset_updates)

        asset_id = _text_or_empty(request.get("assetId")) or _text_or_empty(current_asset.get("assetId"))
        if not asset_id:
            raise ValueError("asset/revision_ready payload is missing assetId.")

        active_revision_id = _text_or_empty(request.get("activeRevisionId")) or _text_or_empty(request.get("revisionId"))
        if not active_revision_id:
            raise ValueError("asset/revision_ready payload is missing activeRevisionId.")

        current_asset["assetId"] = asset_id
        current_asset["activeRevisionId"] = active_revision_id

        updated_by_shell_id = _text_or_empty(request.get("updatedByShellId")) or _text_or_empty(current_asset.get("updatedByShellId"))
        if updated_by_shell_id:
            current_asset["updatedByShellId"] = updated_by_shell_id

        revision_state = _mapping_or_empty(current_asset.get("revisionState"))
        now = _iso_now()
        revision_state["isDirty"] = False
        revision_state["status"] = "clean"
        revision_state["lastReadyRevisionId"] = active_revision_id
        revision_state["lastReadyAt"] = now
        revision_state["updatedAt"] = now
        revision_state.pop("pendingRevisionId", None)
        revision_state.pop("requestedAt", None)
        revision_state.pop("failureMessage", None)
        if updated_by_shell_id:
            revision_state["updatedByShellId"] = updated_by_shell_id
        current_asset["revisionState"] = revision_state

        base_manifest["asset"] = _mapping_or_empty(current_asset)

        return self.apply_session_payload({
            "sessionId": self.session_id,
            "asset": current_asset,
        }, existing_manifest=base_manifest)

    def mark_revision_failed(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        request = _mapping_or_empty(payload)
        base_manifest = self.current_manifest()
        current_asset = _mapping_or_empty(base_manifest.get("asset"))
        asset_updates = _mapping_or_empty(request.get("asset"))
        current_asset.update(asset_updates)

        asset_id = _text_or_empty(request.get("assetId")) or _text_or_empty(current_asset.get("assetId"))
        if not asset_id:
            raise ValueError("asset/revision_failed payload is missing assetId.")

        current_asset["assetId"] = asset_id

        updated_by_shell_id = _text_or_empty(request.get("updatedByShellId")) or _text_or_empty(current_asset.get("updatedByShellId"))
        if updated_by_shell_id:
            current_asset["updatedByShellId"] = updated_by_shell_id

        revision_state = _mapping_or_empty(current_asset.get("revisionState"))
        failed_revision_id = _text_or_empty(request.get("failedRevisionId")) or _text_or_empty(request.get("pendingRevisionId")) or _text_or_empty(revision_state.get("pendingRevisionId"))
        failure_message = _text_or_empty(request.get("error")) or _text_or_empty(request.get("message"))
        now = _iso_now()

        revision_state["isDirty"] = _coerce_bool(request.get("isDirty"), True)
        revision_state["status"] = "failed"
        revision_state["updatedAt"] = now
        revision_state["lastFailedAt"] = now
        revision_state.pop("pendingRevisionId", None)
        revision_state.pop("requestedAt", None)
        if failed_revision_id:
            revision_state["lastFailedRevisionId"] = failed_revision_id
        if failure_message:
            revision_state["failureMessage"] = failure_message
        if updated_by_shell_id:
            revision_state["updatedByShellId"] = updated_by_shell_id
        current_asset["revisionState"] = revision_state

        base_manifest["asset"] = _mapping_or_empty(current_asset)

        return self.apply_session_payload({
            "sessionId": self.session_id,
            "asset": current_asset,
        }, existing_manifest=base_manifest)

    def _merge_transport_state(
        self,
        transport_updates: Mapping[str, Any] | None,
        *,
        current_transport: Mapping[str, Any] | None = None,
        updated_by_shell_id: str = "",
    ) -> dict[str, Any]:
        current_transport = _mapping_or_empty(current_transport)
        if not current_transport:
            current_transport = _mapping_or_empty(self.current_manifest().get("transportState"))
        normalized_updates = _mapping_or_empty(transport_updates)

        if "playheadSec" in normalized_updates:
            playhead_sec = _coerce_float(normalized_updates.get("playheadSec"))
            if playhead_sec is None:
                raise ValueError("Transport playheadSec must be numeric.")
            current_transport["playheadSec"] = playhead_sec

        selection_window = normalized_updates.get("selectionWindow")
        if selection_window is not None:
            if not isinstance(selection_window, Mapping):
                raise ValueError("Transport selectionWindow must be a JSON object.")
            normalized_selection = normalize_backend_selection_contract(selection_window)
            if _text_or_empty(updated_by_shell_id):
                normalized_selection["updatedByShellId"] = _text_or_empty(updated_by_shell_id)
            current_transport["selectionWindow"] = normalized_selection

        return current_transport