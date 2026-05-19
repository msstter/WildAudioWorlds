import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "packages"

if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from wild_audio_worlds.session.session_manifest import (  # noqa: E402
    build_session_manifest,
    build_session_summary,
    load_session_manifest,
    resolve_session_manifest_path,
    save_session_manifest,
)


def test_build_session_manifest_generates_defaults_for_audio_graph_host():
    manifest = build_session_manifest({
        "hostShell": {
            "shellId": "shell-graph-001",
            "shellType": "audio-graphs",
        },
        "asset": {
            "assetId": "asset-001",
            "activeRevisionId": "rev-001",
        },
        "transportState": {
            "playheadSec": 1.25,
        },
        "launchContext": {
            "originatingShell": "audio-graphs",
            "launchReason": "backend-call-run",
        },
    }, service_descriptor={
        "transport": "stdio",
        "endpoint": "/tmp/bootstrap_service.py",
    })

    assert manifest["schemaVersion"] == "0.1"
    assert manifest["sessionId"].startswith("waw-session-")
    assert manifest["mode"] == "standalone"
    assert manifest["stateRevision"] == 1
    assert manifest["service"]["transport"] == "stdio"
    assert manifest["hostShell"]["shellType"] == "audio-graphs"
    assert manifest["asset"]["assetId"] == "asset-001"
    assert manifest["transportState"]["playheadSec"] == 1.25
    assert manifest["peers"] == [{
        "shellId": "shell-graph-001",
        "shellType": "audio-graphs",
        "status": "attached",
        "attachedAt": manifest["hostShell"]["startedAt"],
        "lastSeenAt": manifest["updatedAt"],
    }]


def test_save_and_reload_session_manifest_increments_state_revision(tmp_path):
    initial_manifest = build_session_manifest({
        "sessionId": "demo-session",
        "hostShell": {
            "shellId": "shell-aof-001",
            "shellType": "audio-onset-finder",
        },
        "asset": {
            "assetId": "asset-forest-001",
            "activeRevisionId": "rev-0007",
        },
    })
    manifest_path = resolve_session_manifest_path(tmp_path, initial_manifest["sessionId"])
    save_session_manifest(manifest_path, initial_manifest)

    loaded_manifest = load_session_manifest(manifest_path)
    next_manifest = build_session_manifest({
        "sessionId": "demo-session",
        "transportState": {
            "playheadSec": 12.345,
        },
    }, existing_manifest=loaded_manifest)

    assert next_manifest["sessionId"] == "demo-session"
    assert next_manifest["stateRevision"] == 2
    assert next_manifest["createdAt"] == initial_manifest["createdAt"]
    assert next_manifest["transportState"]["playheadSec"] == 12.345

    summary = build_session_summary(next_manifest, manifest_path)
    assert summary == {
        "schemaVersion": "0.1",
        "sessionId": "demo-session",
        "mode": "standalone",
        "stateRevision": 2,
        "manifestPath": str(manifest_path.resolve()),
        "service": {},
        "hostShell": {
            "shellId": "shell-aof-001",
            "shellType": "audio-onset-finder",
            "startedAt": initial_manifest["hostShell"]["startedAt"],
        },
        "asset": {
            "assetId": "asset-forest-001",
            "activeRevisionId": "rev-0007",
        },
    }


def test_build_session_manifest_promotes_to_linked_when_new_peer_attaches():
    initial_manifest = build_session_manifest({
        "sessionId": "linked-session-demo",
        "hostShell": {
            "shellId": "shell-aof-001",
            "shellType": "audio-onset-finder",
        },
        "launchContext": {
            "originatingShell": "audio-onset-finder",
            "launchReason": "service-bootstrap",
        },
    })

    linked_manifest = build_session_manifest({
        "sessionId": "linked-session-demo",
        "peers": [{
            "shellId": "shell-graph-001",
            "shellType": "audio-graphs",
            "status": "attached",
        }],
    }, existing_manifest=initial_manifest)

    assert linked_manifest["sessionId"] == "linked-session-demo"
    assert linked_manifest["mode"] == "linked"
    assert linked_manifest["stateRevision"] == 2
    assert {peer["shellId"] for peer in linked_manifest["peers"]} == {
        "shell-aof-001",
        "shell-graph-001",
    }


def test_build_session_manifest_downgrades_to_standalone_when_peer_detaches():
    initial_manifest = build_session_manifest({
        "sessionId": "detach-session-demo",
        "hostShell": {
            "shellId": "shell-aof-001",
            "shellType": "audio-onset-finder",
        },
    })

    linked_manifest = build_session_manifest({
        "sessionId": "detach-session-demo",
        "peers": [{
            "shellId": "shell-graph-001",
            "shellType": "audio-graphs",
            "status": "attached",
        }],
    }, existing_manifest=initial_manifest)

    detached_manifest = build_session_manifest({
        "sessionId": "detach-session-demo",
        "autoAttachHostPeer": False,
        "detachedPeerIds": ["shell-graph-001"],
    }, existing_manifest=linked_manifest)

    assert detached_manifest["sessionId"] == "detach-session-demo"
    assert detached_manifest["mode"] == "standalone"
    assert detached_manifest["stateRevision"] == 3
    assert detached_manifest["peers"] == [{
        "shellId": "shell-aof-001",
        "shellType": "audio-onset-finder",
        "status": "attached",
        "attachedAt": initial_manifest["hostShell"]["startedAt"],
        "lastSeenAt": detached_manifest["updatedAt"],
    }]


def test_build_session_manifest_allows_final_host_detach_without_readding_host_peer():
    initial_manifest = build_session_manifest({
        "sessionId": "final-detach-demo",
        "hostShell": {
            "shellId": "shell-aof-001",
            "shellType": "audio-onset-finder",
        },
    })

    detached_manifest = build_session_manifest({
        "sessionId": "final-detach-demo",
        "autoAttachHostPeer": False,
        "detachedPeerIds": ["shell-aof-001"],
    }, existing_manifest=initial_manifest)

    assert detached_manifest["sessionId"] == "final-detach-demo"
    assert detached_manifest["mode"] == "standalone"
    assert detached_manifest["stateRevision"] == 2
    assert detached_manifest["hostShell"] == initial_manifest["hostShell"]
    assert detached_manifest["peers"] == []
