import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "packages"

if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from wild_audio_worlds.session.shell_launch import (  # noqa: E402
    build_shell_launch_cli_args,
    parse_shell_launch_cli_args,
)


def test_build_and_parse_shell_launch_cli_args_round_trip():
    launch_request = {
        "sessionId": "waw-session-demo",
        "manifestPath": "/tmp/demo/session_manifest.json",
        "serviceEndpoint": "/tmp/demo/bootstrap_service.py",
        "originatingShell": "audio-graphs",
        "launchReason": "open-companion",
    }

    cli_args = build_shell_launch_cli_args(launch_request)
    parsed_request, remaining_argv = parse_shell_launch_cli_args([
        "pipeline_gui.py",
        *cli_args,
        "--demo-mode",
    ])

    assert parsed_request == launch_request
    assert remaining_argv == [
        "pipeline_gui.py",
        "--demo-mode",
    ]


def test_parse_shell_launch_cli_args_returns_empty_without_session_id():
    parsed_request, remaining_argv = parse_shell_launch_cli_args([
        "pipeline_gui.py",
        "--demo-mode",
    ])

    assert parsed_request == {}
    assert remaining_argv == [
        "pipeline_gui.py",
        "--demo-mode",
    ]