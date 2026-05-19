import sys
from pathlib import Path


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
    AUDIO_ONSET_FINDER_SHELL_TYPE,
    LOCAL_INTEGRATION_HOST_SHELL_ID,
    attach_to_local_integration_session,
    consume_local_integration_launch_args,
)
from services.local_integration.bootstrap_service import _handle_command  # noqa: E402
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
        "originatingShell": "audio-graphs",
        "launchReason": "open-companion",
    }, workspace_root=tmp_path, bootstrap_root=ROOT)

    assert attach_response["ok"] is True
    assert attach_response["mode"] == "linked"
    assert attach_response["attachedShell"]["shellType"] == AUDIO_ONSET_FINDER_SHELL_TYPE
    assert attach_response["attachedShell"]["shellId"] == LOCAL_INTEGRATION_HOST_SHELL_ID

    manifest = load_session_manifest(attach_response["manifestPath"])
    assert manifest["mode"] == "linked"
    assert {peer["shellId"] for peer in manifest["peers"]} == {
        "shell-graph-001",
        LOCAL_INTEGRATION_HOST_SHELL_ID,
    }