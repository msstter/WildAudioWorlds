import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "packages"
GUI_DIR = ROOT / "AudioOnsetFinder-main" / "GUI"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

if str(GUI_DIR) not in sys.path:
    sys.path.insert(0, str(GUI_DIR))


from local_integration_session import (  # noqa: E402
    AUDIO_GRAPHS_SHELL_TYPE,
    AUDIO_ONSET_FINDER_SHELL_TYPE,
    LOCAL_INTEGRATION_HOST_SHELL_ID,
    attach_to_local_integration_session,
    clear_audio_onset_selection,
    consume_local_integration_launch_args,
    get_local_integration_session_state,
    normalize_local_integration_audio_path,
    open_audio_graphs_companion,
    poll_local_integration_events,
    publish_audio_onset_asset_state,
    publish_audio_onset_playhead,
    publish_audio_onset_selection,
)
from services.local_integration.bootstrap_service import _handle_command  # noqa: E402
from wild_audio_worlds.session.shell_launch import parse_shell_launch_cli_args  # noqa: E402
from wild_audio_worlds.session.session_manifest import load_session_manifest  # noqa: E402


def test_consume_local_integration_launch_args_strips_waw_flags():
    launch_request, remaining_argv = consume_local_integration_launch_args([
        "pipeline_gui.py",
        "--waw-session-id",
        "waw-session-demo",
        "--waw-origin-shell",
        "audio-graphs",
        "--waw-launch-reason",
        "open-companion",
        "--demo-mode",
    ])

    assert launch_request == {
        "sessionId": "waw-session-demo",
        "originatingShell": "audio-graphs",
        "launchReason": "open-companion",
    }
    assert remaining_argv == [
        "pipeline_gui.py",
        "--demo-mode",
    ]


def test_audio_onset_shell_attach_uses_real_bootstrap_service(tmp_path):
    bootstrap_response = _handle_command({
        "command": "service/bootstrap",
        "workspaceRoot": str(tmp_path),
        "session": {
            "hostShell": {
                "shellId": "shell-graph-001",
                "shellType": "audio-graphs",
                "startedAt": "2026-05-19T12:00:00+00:00",
            },
            "asset": {
                "assetId": "asset-forest-001",
                "activeRevisionId": "rev-0007",
            },
            "launchContext": {
                "originatingShell": "audio-graphs",
                "launchReason": "service-bootstrap",
            },
        },
    })

    attach_response = attach_to_local_integration_session({
        "sessionId": bootstrap_response["session"]["sessionId"],
        "manifestPath": bootstrap_response["session"]["manifestPath"],
        "serviceEndpoint": bootstrap_response["session"]["service"]["endpoint"],
        "originatingShell": "audio-graphs",
        "launchReason": "open-companion",
    }, workspace_root=tmp_path, bootstrap_root=ROOT)

    assert attach_response["ok"] is True
    assert attach_response["mode"] == "linked"
    assert attach_response["attachedShell"]["shellType"] == AUDIO_ONSET_FINDER_SHELL_TYPE
    assert attach_response["attachedShell"]["shellId"] == LOCAL_INTEGRATION_HOST_SHELL_ID
    assert attach_response["service"]["transport"] == "unix-domain-socket"

    manifest = load_session_manifest(attach_response["manifestPath"])
    assert manifest["mode"] == "linked"
    assert {peer["shellId"] for peer in manifest["peers"]} == {
        "shell-graph-001",
        LOCAL_INTEGRATION_HOST_SHELL_ID,
    }


def test_audio_onset_shell_open_companion_bootstraps_session_and_launches_electron(tmp_path, monkeypatch):
    launched_command: dict[str, object] = {}

    class _FakeProcess:
        pid = 4242

    def _fake_popen(command, **kwargs):
        launched_command["command"] = command
        launched_command["kwargs"] = kwargs
        return _FakeProcess()

    response = open_audio_graphs_companion(
        workspace_root=tmp_path,
        bootstrap_root=ROOT,
        frontend_root=ROOT / "3DAudioGraphs-main" / "frontend",
        launch_process_factory=_fake_popen,
    )

    assert response["ok"] is True
    assert response["mode"] == "standalone"
    assert response["launchedShell"]["shellType"] == AUDIO_GRAPHS_SHELL_TYPE
    assert response["launchedShell"]["requestedByShellId"] == LOCAL_INTEGRATION_HOST_SHELL_ID
    assert response["launchedProcess"]["pid"] == 4242

    expected_npm_command = "npm.cmd" if sys.platform == "win32" else "npm"
    launch_command = launched_command["command"]
    assert launch_command[:4] == [expected_npm_command, "run", "electron:dev", "--"]
    assert launched_command["kwargs"] == {
        "cwd": str((ROOT / "3DAudioGraphs-main" / "frontend").resolve()),
        "stdin": -3,
        "stdout": -3,
        "stderr": -3,
        "start_new_session": True,
    }

    parsed_request, remaining_argv = parse_shell_launch_cli_args([
        "electron",
        "main.cjs",
        *launch_command[4:],
    ])
    assert parsed_request["sessionId"] == response["sessionId"]
    assert parsed_request["originatingShell"] == AUDIO_ONSET_FINDER_SHELL_TYPE
    assert parsed_request["launchReason"] == "open-companion"
    assert remaining_argv == [
        "electron",
        "main.cjs",
    ]

    manifest = load_session_manifest(response["manifestPath"])
    assert manifest["launchContext"]["requestedCompanion"] == AUDIO_GRAPHS_SHELL_TYPE
    assert manifest["launchContext"]["requestedByShellId"] == LOCAL_INTEGRATION_HOST_SHELL_ID


def test_audio_onset_companion_launch_failure_leaves_session_reusable(tmp_path):
    def _failing_popen(_command, **_kwargs):
        raise OSError("launcher failed")

    with pytest.raises(OSError, match="launcher failed"):
        open_audio_graphs_companion(
            workspace_root=tmp_path,
            bootstrap_root=ROOT,
            frontend_root=ROOT / "3DAudioGraphs-main" / "frontend",
            launch_process_factory=_failing_popen,
        )

    manifest_paths = list((tmp_path / "data" / "sessions").glob("*/session_manifest.json"))
    assert len(manifest_paths) == 1
    failed_manifest = load_session_manifest(manifest_paths[0])
    assert failed_manifest["mode"] == "standalone"
    assert failed_manifest["launchContext"]["requestedCompanion"] == AUDIO_GRAPHS_SHELL_TYPE
    failed_session_id = failed_manifest["sessionId"]
    failed_revision = failed_manifest["stateRevision"]

    class _FakeProcess:
        pid = 4343

    def _successful_popen(_command, **_kwargs):
        return _FakeProcess()

    retry_response = open_audio_graphs_companion(
        workspace_root=tmp_path,
        bootstrap_root=ROOT,
        frontend_root=ROOT / "3DAudioGraphs-main" / "frontend",
        launch_process_factory=_successful_popen,
    )

    assert retry_response["ok"] is True
    assert retry_response["sessionId"] == failed_session_id
    assert retry_response["stateRevision"] == failed_revision + 1
    assert retry_response["launchedProcess"]["pid"] == 4343


def test_audio_onset_companion_attach_failure_leaves_session_reusable(tmp_path):
    bootstrap_response = _handle_command({
        "command": "service/bootstrap",
        "workspaceRoot": str(tmp_path),
        "session": {
            "hostShell": {
                "shellId": "shell-graph-001",
                "shellType": "audio-graphs",
                "startedAt": "2026-05-19T12:00:00+00:00",
            },
            "asset": {
                "assetId": "asset-forest-001",
                "activeRevisionId": "rev-0007",
            },
            "launchContext": {
                "originatingShell": "audio-graphs",
                "launchReason": "service-bootstrap",
            },
        },
    })

    with pytest.raises(RuntimeError, match="Session manifest not found|requested sessionId"):
        attach_to_local_integration_session({
            "sessionId": "missing-session",
            "manifestPath": bootstrap_response["session"]["manifestPath"],
            "serviceEndpoint": bootstrap_response["session"]["service"]["endpoint"],
            "originatingShell": "audio-graphs",
            "launchReason": "open-companion",
        }, workspace_root=tmp_path, bootstrap_root=ROOT)

    manifest_after_failure = load_session_manifest(bootstrap_response["session"]["manifestPath"])
    assert manifest_after_failure["stateRevision"] == 1
    assert manifest_after_failure["mode"] == "standalone"

    attach_response = attach_to_local_integration_session({
        "sessionId": bootstrap_response["session"]["sessionId"],
        "manifestPath": bootstrap_response["session"]["manifestPath"],
        "serviceEndpoint": bootstrap_response["session"]["service"]["endpoint"],
        "originatingShell": "audio-graphs",
        "launchReason": "open-companion",
    }, workspace_root=tmp_path, bootstrap_root=ROOT)

    assert attach_response["ok"] is True
    assert attach_response["sessionId"] == bootstrap_response["session"]["sessionId"]
    assert attach_response["mode"] == "linked"


def test_audio_onset_shell_attach_reuses_persistent_service_without_respawning_bootstrap(tmp_path, monkeypatch):
    bootstrap_response = _handle_command({
        "command": "service/bootstrap",
        "workspaceRoot": str(tmp_path),
        "session": {
            "hostShell": {
                "shellId": "shell-graph-001",
                "shellType": "audio-graphs",
                "startedAt": "2026-05-19T12:00:00+00:00",
            },
            "launchContext": {
                "originatingShell": "audio-graphs",
                "launchReason": "service-bootstrap",
            },
        },
    })

    def _unexpected_run(*_args, **_kwargs):
        raise AssertionError("attach should reuse the persistent local integration service instead of respawning bootstrap_service.py")

    monkeypatch.setattr("local_integration_session.subprocess.run", _unexpected_run)

    attach_response = attach_to_local_integration_session({
        "sessionId": bootstrap_response["session"]["sessionId"],
        "manifestPath": bootstrap_response["session"]["manifestPath"],
        "serviceEndpoint": bootstrap_response["session"]["service"]["endpoint"],
        "originatingShell": "audio-graphs",
        "launchReason": "open-companion",
    }, workspace_root=tmp_path, bootstrap_root=ROOT)

    assert attach_response["ok"] is True
    assert attach_response["service"]["transport"] == "unix-domain-socket"


def test_audio_onset_shell_publish_helpers_update_audio_manager_state(tmp_path):
    audio_path = tmp_path / "sample_audio.wav"
    audio_path.write_bytes(b"RIFF")

    asset_response = publish_audio_onset_asset_state(
        audio_path,
        workspace_root=tmp_path,
        bootstrap_root=ROOT,
    )

    assert asset_response["ok"] is True
    assert asset_response["session"]["asset"]["sourceAudioPath"] == str(audio_path.resolve())
    assert asset_response["session"]["asset"]["assetLabel"] == "sample_audio.wav"

    playhead_response = publish_audio_onset_playhead(
        3.5,
        workspace_root=tmp_path,
        bootstrap_root=ROOT,
        force=True,
    )

    assert playhead_response["ok"] is True
    assert playhead_response["session"]["transportState"]["playheadSec"] == 3.5

    selection_response = publish_audio_onset_selection(
        3.0,
        4.25,
        playhead_sec=3.5,
        workspace_root=tmp_path,
        bootstrap_root=ROOT,
    )

    assert selection_response["ok"] is True
    assert selection_response["session"]["transportState"]["selectionWindow"]["timeRangeSec"] == {
        "start": 3.0,
        "end": 4.25,
        "duration": 1.25,
    }

    cleared_selection_response = clear_audio_onset_selection(
        playhead_sec=4.0,
        workspace_root=tmp_path,
        bootstrap_root=ROOT,
    )

    assert cleared_selection_response["ok"] is True
    assert cleared_selection_response["session"]["transportState"]["playheadSec"] == 4.0
    assert cleared_selection_response["session"]["transportState"]["selectionWindow"]["isReady"] is False

    manifest = load_session_manifest(cleared_selection_response["manifestPath"])
    assert manifest["asset"]["sourceAudioPath"] == str(audio_path.resolve())
    assert manifest["transportState"]["playheadSec"] == 4.0
    assert manifest["transportState"]["selectionWindow"]["isReady"] is False


def test_audio_onset_shell_can_poll_audio_manager_events(tmp_path):
    audio_path = tmp_path / "session_asset.wav"
    audio_path.write_bytes(b"RIFF")

    initial_state = get_local_integration_session_state(
        workspace_root=tmp_path,
        bootstrap_root=ROOT,
    )
    assert initial_state["ok"] is True

    publish_audio_onset_asset_state(
        audio_path,
        workspace_root=tmp_path,
        bootstrap_root=ROOT,
    )
    publish_audio_onset_playhead(
        2.25,
        workspace_root=tmp_path,
        bootstrap_root=ROOT,
        force=True,
    )

    poll_response = poll_local_integration_events(
        workspace_root=tmp_path,
        bootstrap_root=ROOT,
        after_event_id=0,
        limit=20,
    )

    assert poll_response["ok"] is True
    event_kinds = [event["kind"] for event in poll_response["events"]]
    assert "asset/opened" in event_kinds
    assert "transport/time_changed" in event_kinds
    assert poll_response["eventsState"]["latestEventId"] >= len(poll_response["events"])


def test_normalize_local_integration_audio_path_handles_file_urls(tmp_path):
    audio_path = tmp_path / "bird song.wav"
    audio_path.write_text("demo", encoding="utf-8")

    normalized_path = normalize_local_integration_audio_path(audio_path.as_uri())

    assert normalized_path == str(audio_path.resolve())