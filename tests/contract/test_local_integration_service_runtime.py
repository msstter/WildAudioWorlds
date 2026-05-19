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
			"launchContext": {
				"originatingShell": "audio-onset-finder",
				"launchReason": "service-bootstrap",
			},
		},
	})


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