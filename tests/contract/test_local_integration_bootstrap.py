import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "packages"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))


from services.local_integration.bootstrap_service import _handle_command  # noqa: E402
from wild_audio_worlds.session.session_manifest import load_session_manifest  # noqa: E402


def _build_bootstrap_envelope(workspace_root: Path) -> dict[str, object]:
    return {
        "command": "service/bootstrap",
        "workspaceRoot": str(workspace_root),
        "session": {
            "hostShell": {
                "shellId": "shell-aof-001",
                "shellType": "audio-onset-finder",
                "startedAt": "2026-05-19T12:00:00+00:00",
            },
            "asset": {
                "assetId": "asset-forest-001",
                "activeRevisionId": "rev-0007",
            },
            "transportState": {
                "playheadSec": 12.345,
            },
            "launchContext": {
                "originatingShell": "audio-onset-finder",
                "launchReason": "service-bootstrap",
            },
        },
    }


def test_open_companion_and_attach_update_manifest_revision(tmp_path):
    bootstrap_response = _handle_command(_build_bootstrap_envelope(tmp_path))
    session_id = bootstrap_response["session"]["sessionId"]

    assert bootstrap_response["ok"] is True
    assert bootstrap_response["session"]["stateRevision"] == 1
    assert bootstrap_response["session"]["mode"] == "standalone"

    open_response = _handle_command({
        "command": "shell/open_companion",
        "workspaceRoot": str(tmp_path),
        "session": {
            "sessionId": session_id,
        },
        "payload": {
            "sessionId": session_id,
            "originShell": {
                "shellId": "shell-aof-001",
                "shellType": "audio-onset-finder",
            },
            "targetShell": "audio-graphs",
            "transportState": {
                "playheadSec": 12.5,
                "selectionWindow": {
                    "isReady": True,
                    "timeRangeSec": {
                        "start": 11.8,
                        "end": 13.1,
                    },
                },
            },
            "launchContext": {
                "originatingShell": "audio-onset-finder",
                "launchReason": "open-companion",
            },
        },
    })

    assert open_response["ok"] is True
    assert open_response["sessionId"] == session_id
    assert open_response["stateRevision"] == 2
    assert open_response["mode"] == "standalone"
    assert open_response["launchedShell"] == {
        "shellType": "audio-graphs",
        "status": "requested",
        "requestedByShellId": "shell-aof-001",
    }

    manifest_after_open = load_session_manifest(open_response["manifestPath"])
    assert manifest_after_open["launchContext"]["requestedCompanion"] == "audio-graphs"
    assert manifest_after_open["launchContext"]["requestedByShellId"] == "shell-aof-001"
    assert manifest_after_open["transportState"]["selectionWindow"]["isReady"] is True

    attach_response = _handle_command({
        "command": "session/attach",
        "workspaceRoot": str(tmp_path),
        "payload": {
            "sessionId": session_id,
            "shell": {
                "shellId": "shell-graph-001",
                "shellType": "audio-graphs",
                "startedAt": "2026-05-19T12:00:30+00:00",
            },
            "requestedCapabilities": [
                "transport-read",
                "transport-write",
                "asset-read",
            ],
            "lastKnownStateRevision": 2,
        },
    })

    assert attach_response["ok"] is True
    assert attach_response["sessionId"] == session_id
    assert attach_response["stateRevision"] == 3
    assert attach_response["mode"] == "linked"
    assert attach_response["attachedShell"] == {
        "shellId": "shell-graph-001",
        "shellType": "audio-graphs",
        "status": "attached",
        "requestedCapabilities": [
            "transport-read",
            "transport-write",
            "asset-read",
        ],
        "lastKnownStateRevision": 2,
    }
    assert attach_response["manifest"]["asset"] == {
        "assetId": "asset-forest-001",
        "activeRevisionId": "rev-0007",
    }
    assert {peer["shellId"] for peer in attach_response["manifest"]["peers"]} == {
        "shell-aof-001",
        "shell-graph-001",
    }


def test_session_attach_requires_existing_session(tmp_path):
    with pytest.raises(FileNotFoundError, match="Session manifest not found"):
        _handle_command({
            "command": "session/attach",
            "workspaceRoot": str(tmp_path),
            "payload": {
                "sessionId": "missing-session",
                "shell": {
                    "shellId": "shell-graph-001",
                    "shellType": "audio-graphs",
                },
            },
        })