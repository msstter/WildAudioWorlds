import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "packages"

if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

if str(PACKAGES_DIR) not in sys.path:
	sys.path.insert(0, str(PACKAGES_DIR))


from services.local_integration.bootstrap_service import _handle_command  # noqa: E402
from services.local_integration.service_runtime import send_service_command  # noqa: E402
from wild_audio_worlds.session.session_manifest import load_session_manifest  # noqa: E402


def _write_backend_runner(path: Path, *, sleep_seconds: float = 0.0) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(
		"\n".join([
			"import json",
			"import sys",
			"import time",
			"payload = json.load(sys.stdin)",
			f"time.sleep({sleep_seconds})",
			"print(json.dumps({'ok': True, 'received': payload}))",
		]),
		encoding="utf-8",
	)


def _bootstrap_service(tmp_path: Path) -> dict[str, object]:
	return _handle_command({
		"command": "service/bootstrap",
		"workspaceRoot": str(tmp_path),
		"session": {
			"hostShell": {
				"shellId": "shell-aof-001",
				"shellType": "audio-onset-finder",
				"startedAt": "2026-05-19T12:00:00+00:00",
			},
			"asset": {
				"assetId": "asset-forest-001",
				"assetLabel": "Forest Dawn",
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
	})


def test_persistent_service_audio_manager_owns_asset_transport_and_revision_state(tmp_path):
	bootstrap_response = _bootstrap_service(tmp_path)
	endpoint = bootstrap_response["session"]["service"]["endpoint"]
	manifest_path = Path(bootstrap_response["session"]["manifestPath"])

	initial_state = send_service_command(endpoint, {
		"command": "session/get_state",
	})

	assert initial_state["ok"] is True
	assert initial_state["session"]["asset"] == {
		"assetId": "asset-forest-001",
		"assetLabel": "Forest Dawn",
		"activeRevisionId": "rev-0007",
	}
	assert initial_state["session"]["transportState"]["playheadSec"] == 12.345

	open_asset_response = send_service_command(endpoint, {
		"command": "session/open_asset",
		"payload": {
			"asset": {
				"assetId": "asset-rain-002",
				"assetLabel": "Rain Chorus",
				"activeRevisionId": "rev-0012",
			},
			"transportState": {
				"playheadSec": 4.25,
			},
			"updatedByShellId": "shell-graph-001",
		},
	})

	assert open_asset_response["ok"] is True
	assert open_asset_response["session"]["asset"]["assetId"] == "asset-rain-002"
	assert open_asset_response["session"]["transportState"]["playheadSec"] == 4.25

	selection_response = send_service_command(endpoint, {
		"command": "transport/set_selection",
		"payload": {
			"selectionWindow": {
				"selectionModel": "spectroterrain-full-sculpt",
				"isReady": True,
				"timeRangeSec": {
					"start": 4.0,
					"end": 5.5,
				},
			},
			"updatedByShellId": "shell-graph-001",
		},
	})

	assert selection_response["ok"] is True
	assert selection_response["session"]["transportState"]["selectionWindow"]["isReady"] is True

	revision_response = send_service_command(endpoint, {
		"command": "asset/set_revision",
		"payload": {
			"assetId": "asset-rain-002",
			"activeRevisionId": "rev-0013",
			"updatedByShellId": "shell-aof-001",
		},
	})

	assert revision_response["ok"] is True
	assert revision_response["session"]["asset"]["activeRevisionId"] == "rev-0013"

	state_response = send_service_command(endpoint, {
		"command": "session/get_state",
	})

	assert state_response["ok"] is True
	assert state_response["session"]["asset"] == {
		"assetId": "asset-rain-002",
		"assetLabel": "Rain Chorus",
		"activeRevisionId": "rev-0013",
		"updatedByShellId": "shell-aof-001",
	}
	assert state_response["session"]["transportState"]["playheadSec"] == 4.25
	assert state_response["session"]["transportState"]["selectionWindow"]["updatedByShellId"] == "shell-graph-001"

	manifest = load_session_manifest(manifest_path)
	assert manifest["asset"]["assetId"] == "asset-rain-002"
	assert manifest["asset"]["activeRevisionId"] == "rev-0013"
	assert manifest["transportState"]["selectionWindow"]["selectionModel"] == "spectroterrain-full-sculpt"

	clear_asset_response = send_service_command(endpoint, {
		"command": "session/clear_asset",
		"payload": {
			"transportState": {
				"playheadSec": 0.0,
				"selectionWindow": {
					"isReady": False,
					"selectionModel": "spectroterrain-full-sculpt",
				},
			},
			"updatedByShellId": "shell-graph-001",
		},
	})

	assert clear_asset_response["ok"] is True
	assert clear_asset_response["session"]["asset"] == {}
	assert clear_asset_response["session"]["transportState"]["playheadSec"] == 0.0
	assert clear_asset_response["session"]["transportState"]["selectionWindow"]["isReady"] is False

	cleared_manifest = load_session_manifest(manifest_path)
	assert cleared_manifest["asset"] == {}
	assert cleared_manifest["transportState"]["playheadSec"] == 0.0


def test_persistent_service_attach_returns_audio_manager_snapshot(tmp_path):
	bootstrap_response = _bootstrap_service(tmp_path)
	endpoint = bootstrap_response["session"]["service"]["endpoint"]
	session_id = bootstrap_response["session"]["sessionId"]

	send_service_command(endpoint, {
		"command": "transport/set_time",
		"payload": {
			"playheadSec": 21.5,
			"updatedByShellId": "shell-aof-001",
		},
	})

	send_service_command(endpoint, {
		"command": "transport/set_selection",
		"payload": {
			"selectionWindow": {
				"selectionModel": "spectroterrain-full-sculpt",
				"isReady": True,
				"timeRangeSec": {
					"start": 20.0,
					"end": 23.0,
				},
			},
			"updatedByShellId": "shell-aof-001",
		},
	})

	send_service_command(endpoint, {
		"command": "asset/set_revision",
		"payload": {
			"assetId": "asset-forest-001",
			"activeRevisionId": "rev-0008",
			"updatedByShellId": "shell-aof-001",
		},
	})

	attach_response = send_service_command(endpoint, {
		"command": "session/attach",
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
		},
	})

	assert attach_response["ok"] is True
	assert attach_response["manifest"]["asset"]["activeRevisionId"] == "rev-0008"
	assert attach_response["manifest"]["transportState"]["playheadSec"] == 21.5
	assert attach_response["manifest"]["transportState"]["selectionWindow"]["timeRangeSec"] == {
		"start": 20.0,
		"end": 23.0,
	}


def test_persistent_service_backend_call_returns_job_metadata(tmp_path):
	_write_backend_runner(tmp_path / "3DAudioGraphs-main" / "backend" / "run_selection_analysis.py")
	bootstrap_response = _bootstrap_service(tmp_path)
	session_id = bootstrap_response["session"]["sessionId"]
	endpoint = bootstrap_response["session"]["service"]["endpoint"]

	response = send_service_command(endpoint, {
		"command": "backend-call/run",
		"workspaceRoot": str(tmp_path),
		"session": {
			"sessionId": session_id,
		},
		"payload": {
			"sessionId": session_id,
			"input": "demo",
		},
	})

	assert response["ok"] is True
	assert response["response"]["ok"] is True
	assert response["response"]["received"] == {
		"sessionId": session_id,
		"input": "demo",
	}
	assert response["job"]["jobId"].startswith("waw-job-")
	assert response["job"]["status"] == "completed"


def test_persistent_service_can_cancel_running_backend_job(tmp_path):
	_write_backend_runner(
		tmp_path / "3DAudioGraphs-main" / "backend" / "run_selection_analysis.py",
		sleep_seconds=5.0,
	)
	bootstrap_response = _bootstrap_service(tmp_path)
	session_id = bootstrap_response["session"]["sessionId"]
	endpoint = bootstrap_response["session"]["service"]["endpoint"]
	worker_result: dict[str, object] = {}

	def _run_job() -> None:
		worker_result["response"] = send_service_command(endpoint, {
			"command": "backend-call/run",
			"workspaceRoot": str(tmp_path),
			"session": {
				"sessionId": session_id,
			},
			"payload": {
				"sessionId": session_id,
				"input": "cancel-me",
			},
		})

	worker = threading.Thread(target=_run_job)
	worker.start()

	job_id = ""
	for _ in range(40):
		ping_response = send_service_command(endpoint, {
			"command": "service/ping",
		})
		active_jobs = ping_response.get("serviceState", {}).get("activeJobs", [])
		if active_jobs:
			job_id = active_jobs[0]["jobId"]
			break
		time.sleep(0.05)

	assert job_id

	cancel_response = send_service_command(endpoint, {
		"command": "job/cancel",
		"payload": {
			"jobId": job_id,
		},
	})
	assert cancel_response["ok"] is True
	assert cancel_response["job"]["status"] in {"cancel-requested", "cancelled"}

	worker.join(timeout=10)
	assert not worker.is_alive()
	assert worker_result["response"]["response"]["ok"] is False
	assert worker_result["response"]["response"]["errorCode"] == "job-cancelled"
	assert worker_result["response"]["job"]["status"] == "cancelled"