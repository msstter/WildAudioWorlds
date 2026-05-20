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
				"audioUrl": "file:///tmp/rain-chorus.wav",
				"analysisClipDurationSec": 9.75,
			},
			"transportState": {
				"playheadSec": 4.25,
			},
			"updatedByShellId": "shell-graph-001",
		},
	})

	assert open_asset_response["ok"] is True
	assert open_asset_response["session"]["asset"]["assetId"] == "asset-rain-002"
	assert open_asset_response["session"]["asset"]["audioUrl"] == "file:///tmp/rain-chorus.wav"
	assert open_asset_response["session"]["asset"]["analysisClipDurationSec"] == 9.75
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
	assert state_response["session"]["asset"]["assetId"] == "asset-rain-002"
	assert state_response["session"]["asset"]["assetLabel"] == "Rain Chorus"
	assert state_response["session"]["asset"]["activeRevisionId"] == "rev-0013"
	assert state_response["session"]["asset"]["updatedByShellId"] == "shell-aof-001"
	assert state_response["session"]["asset"]["audioUrl"] == "file:///tmp/rain-chorus.wav"
	assert state_response["session"]["asset"]["analysisClipDurationSec"] == 9.75
	assert state_response["session"]["transportState"]["playheadSec"] == 4.25
	assert state_response["session"]["transportState"]["selectionWindow"]["updatedByShellId"] == "shell-graph-001"

	manifest = load_session_manifest(manifest_path)
	assert manifest["asset"]["assetId"] == "asset-rain-002"
	assert manifest["asset"]["activeRevisionId"] == "rev-0013"
	assert manifest["asset"]["audioUrl"] == "file:///tmp/rain-chorus.wav"
	assert manifest["asset"]["analysisClipDurationSec"] == 9.75
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


def test_persistent_service_emits_audio_manager_events(tmp_path):
	bootstrap_response = _bootstrap_service(tmp_path)
	endpoint = bootstrap_response["session"]["service"]["endpoint"]

	initial_poll = send_service_command(endpoint, {
		"command": "events/poll",
		"payload": {
			"afterEventId": 0,
			"limit": 20,
		},
	})

	assert initial_poll["ok"] is True
	initial_latest_event_id = initial_poll["eventsState"]["latestEventId"]
	assert initial_latest_event_id >= 0

	transport_response = send_service_command(endpoint, {
		"command": "transport/set_time",
		"payload": {
			"playheadSec": 33.75,
			"updatedByShellId": "shell-graph-001",
		},
	})

	assert transport_response["ok"] is True

	poll_response = send_service_command(endpoint, {
		"command": "events/poll",
		"payload": {
			"afterEventId": initial_latest_event_id,
			"limit": 20,
		},
	})

	assert poll_response["ok"] is True
	assert poll_response["eventsState"]["latestEventId"] >= 1
	assert len(poll_response["events"]) == 1
	assert poll_response["events"][0]["kind"] == "transport/time_changed"
	assert poll_response["events"][0]["stateRevision"] == transport_response["stateRevision"]
	assert poll_response["events"][0]["payload"] == {
		"playheadSec": 33.75,
	}
	assert poll_response["events"][0]["audioManager"]["transportState"]["playheadSec"] == 33.75


def test_persistent_service_coordinates_dirty_and_revision_lifecycle(tmp_path):
	bootstrap_response = _bootstrap_service(tmp_path)
	endpoint = bootstrap_response["session"]["service"]["endpoint"]
	manifest_path = Path(bootstrap_response["session"]["manifestPath"])

	dirty_response = send_service_command(endpoint, {
		"command": "asset/set_dirty_state",
		"payload": {
			"assetId": "asset-forest-001",
			"pendingRevisionId": "rev-0008",
			"updatedByShellId": "shell-aof-001",
		},
	})

	assert dirty_response["ok"] is True
	assert dirty_response["session"]["asset"]["activeRevisionId"] == "rev-0007"
	assert dirty_response["session"]["asset"]["revisionState"] == {
		"isDirty": True,
		"status": "dirty",
		"pendingRevisionId": "rev-0008",
		"requestedAt": dirty_response["session"]["asset"]["revisionState"]["requestedAt"],
		"updatedAt": dirty_response["session"]["asset"]["revisionState"]["updatedAt"],
		"updatedByShellId": "shell-aof-001",
	}

	failed_response = send_service_command(endpoint, {
		"command": "asset/revision_failed",
		"payload": {
			"assetId": "asset-forest-001",
			"failedRevisionId": "rev-0008",
			"error": "graph rebuild failed",
			"updatedByShellId": "shell-graph-001",
		},
	})

	assert failed_response["ok"] is True
	assert failed_response["session"]["asset"]["activeRevisionId"] == "rev-0007"
	assert failed_response["session"]["asset"]["revisionState"]["isDirty"] is True
	assert failed_response["session"]["asset"]["revisionState"]["status"] == "failed"
	assert failed_response["session"]["asset"]["revisionState"]["lastFailedRevisionId"] == "rev-0008"
	assert failed_response["session"]["asset"]["revisionState"]["failureMessage"] == "graph rebuild failed"
	assert "pendingRevisionId" not in failed_response["session"]["asset"]["revisionState"]

	ready_response = send_service_command(endpoint, {
		"command": "asset/revision_ready",
		"payload": {
			"assetId": "asset-forest-001",
			"activeRevisionId": "rev-0008",
			"asset": {
				"audioUrl": "file:///tmp/forest-dawn-rev-0008.wav",
				"analysisClipDurationSec": 14.5,
			},
			"updatedByShellId": "shell-graph-001",
		},
	})

	assert ready_response["ok"] is True
	assert ready_response["session"]["asset"]["activeRevisionId"] == "rev-0008"
	assert ready_response["session"]["asset"]["audioUrl"] == "file:///tmp/forest-dawn-rev-0008.wav"
	assert ready_response["session"]["asset"]["analysisClipDurationSec"] == 14.5
	assert ready_response["session"]["asset"]["revisionState"]["isDirty"] is False
	assert ready_response["session"]["asset"]["revisionState"]["status"] == "clean"
	assert ready_response["session"]["asset"]["revisionState"]["lastReadyRevisionId"] == "rev-0008"
	assert "pendingRevisionId" not in ready_response["session"]["asset"]["revisionState"]
	assert "failureMessage" not in ready_response["session"]["asset"]["revisionState"]

	manifest = load_session_manifest(manifest_path)
	assert manifest["asset"]["activeRevisionId"] == "rev-0008"
	assert manifest["asset"]["revisionState"]["isDirty"] is False
	assert manifest["asset"]["revisionState"]["lastReadyRevisionId"] == "rev-0008"

	poll_response = send_service_command(endpoint, {
		"command": "events/poll",
		"payload": {
			"afterEventId": 0,
			"limit": 20,
		},
	})

	assert poll_response["ok"] is True
	event_kinds = [event["kind"] for event in poll_response["events"]]
	assert "asset/dirty_state_changed" in event_kinds
	assert "asset/revision_failed" in event_kinds
	assert "asset/revision_ready" in event_kinds


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


def test_persistent_service_graph_process_asset_returns_job_metadata(tmp_path):
	_write_backend_runner(tmp_path / "3DAudioGraphs-main" / "backend" / "process_graph_asset.py")
	bootstrap_response = _bootstrap_service(tmp_path)
	session_id = bootstrap_response["session"]["sessionId"]
	endpoint = bootstrap_response["session"]["service"]["endpoint"]

	response = send_service_command(endpoint, {
		"command": "graph/process_asset",
		"workspaceRoot": str(tmp_path),
		"session": {
			"sessionId": session_id,
		},
		"payload": {
			"sessionId": session_id,
			"audioPath": "/tmp/marsh.wav",
			"assetLabel": "Marsh Dawn",
		},
	})

	assert response["ok"] is True
	assert response["response"]["ok"] is True
	assert response["response"]["received"] == {
		"sessionId": session_id,
		"audioPath": "/tmp/marsh.wav",
		"assetLabel": "Marsh Dawn",
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