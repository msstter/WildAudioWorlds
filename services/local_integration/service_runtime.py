from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import socket
import socketserver
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _ensure_shared_package_path() -> Path:
	current_path = Path(__file__).resolve()
	for parent in current_path.parents:
		packages_dir = parent / "packages"
		if (packages_dir / "wild_audio_worlds").exists():
			parent_str = str(parent)
			packages_dir_str = str(packages_dir)
			if parent_str not in sys.path:
				sys.path.insert(0, parent_str)
			if packages_dir_str not in sys.path:
				sys.path.insert(0, packages_dir_str)
			return parent
	raise RuntimeError("Unable to locate the shared packages directory for WildAudioWorlds.")


WORKSPACE_ROOT = _ensure_shared_package_path()

from wild_audio_worlds.session.session_manifest import build_session_summary  # noqa: E402


SERVICE_PROTOCOL_VERSION = "0.2"
SERVICE_SOCKET_ROOT = Path("/tmp") / "wild_audio_worlds"
SERVICE_STARTUP_TIMEOUT_SEC = 3.0
SERVICE_PING_TIMEOUT_SEC = 0.2
SERVICE_COMMAND_TIMEOUT_SEC = 30.0


def _iso_now() -> str:
	return datetime.now(timezone.utc).isoformat()


def _mapping_or_empty(value: Any) -> dict[str, Any]:
	return value if isinstance(value, dict) else {}


def _text_or_empty(value: Any) -> str:
	return str(value or "").strip()


def resolve_service_socket_path(workspace_root: str | Path, session_id: str) -> Path:
	del workspace_root
	SERVICE_SOCKET_ROOT.mkdir(parents=True, exist_ok=True)
	normalized_session_id = _text_or_empty(session_id)
	endpoint_name = hashlib.sha256(normalized_session_id.encode("utf-8")).hexdigest()[:20]
	return SERVICE_SOCKET_ROOT / f"waw-{endpoint_name}.sock"


def build_persistent_service_descriptor(
	workspace_root: str | Path,
	session_id: str,
	*,
	owner_shell_id: str = "",
	owner_shell_type: str = "",
) -> dict[str, Any]:
	return {
		"protocolVersion": SERVICE_PROTOCOL_VERSION,
		"transport": "unix-domain-socket",
		"endpoint": str(resolve_service_socket_path(workspace_root, session_id)),
		"bootMode": f"persistent-daemon-for-{_text_or_empty(owner_shell_type) or 'session'}",
		"ownerShellId": _text_or_empty(owner_shell_id),
	}


def send_service_command(
	endpoint: str | Path,
	envelope: dict[str, Any],
	*,
	timeout: float = SERVICE_COMMAND_TIMEOUT_SEC,
) -> dict[str, Any]:
	endpoint_path = Path(endpoint)
	with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
		client.settimeout(timeout)
		client.connect(str(endpoint_path))
		client.sendall(json.dumps(envelope).encode("utf-8"))
		try:
			client.shutdown(socket.SHUT_WR)
		except OSError:
			pass

		chunks: list[bytes] = []
		while True:
			chunk = client.recv(65536)
			if not chunk:
				break
			chunks.append(chunk)

	raw_response = b"".join(chunks).decode("utf-8").strip()
	if not raw_response:
		raise RuntimeError("Local integration service returned an empty response.")

	parsed = json.loads(raw_response)
	if not isinstance(parsed, dict):
		raise RuntimeError("Local integration service returned a non-object JSON payload.")
	return parsed


def is_service_available(endpoint: str | Path) -> bool:
	try:
		response = send_service_command(
			endpoint,
			{"command": "service/ping"},
			timeout=SERVICE_PING_TIMEOUT_SEC,
		)
		return response.get("ok") is True
	except Exception:
		return False


def shutdown_persistent_service(endpoint: str | Path) -> None:
	try:
		send_service_command(endpoint, {"command": "service/shutdown"}, timeout=1.0)
	except Exception:
		return


def ensure_persistent_service(
	workspace_root: str | Path,
	session_id: str,
	*,
	owner_shell_id: str = "",
	owner_shell_type: str = "",
	python_executable: str | None = None,
	startup_timeout_sec: float = SERVICE_STARTUP_TIMEOUT_SEC,
) -> dict[str, Any]:
	workspace = Path(workspace_root).resolve()
	normalized_session_id = _text_or_empty(session_id)
	if not normalized_session_id:
		raise ValueError("Persistent local integration service requires a sessionId.")

	descriptor = build_persistent_service_descriptor(
		workspace,
		normalized_session_id,
		owner_shell_id=owner_shell_id,
		owner_shell_type=owner_shell_type,
	)
	endpoint_path = Path(descriptor["endpoint"])
	if is_service_available(endpoint_path):
		return descriptor

	if endpoint_path.exists():
		endpoint_path.unlink()

	command = [
		python_executable or sys.executable,
		str(Path(__file__).resolve()),
		"--workspace-root",
		str(workspace),
		"--session-id",
		normalized_session_id,
	]
	if _text_or_empty(owner_shell_id):
		command.extend(["--owner-shell-id", _text_or_empty(owner_shell_id)])
	if _text_or_empty(owner_shell_type):
		command.extend(["--owner-shell-type", _text_or_empty(owner_shell_type)])

	subprocess.Popen(
		command,
		cwd=str(workspace),
		stdin=subprocess.DEVNULL,
		stdout=subprocess.DEVNULL,
		stderr=subprocess.DEVNULL,
		start_new_session=True,
	)

	deadline = time.monotonic() + float(startup_timeout_sec)
	while time.monotonic() < deadline:
		if is_service_available(endpoint_path):
			return descriptor
		time.sleep(0.05)

	raise RuntimeError(
		f"Timed out waiting for the persistent local integration service to start for session {normalized_session_id}."
	)


@dataclass
class _JobRecord:
	job_id: str
	command: str
	session_id: str
	status: str
	submitted_at: str
	started_at: str = ""
	completed_at: str = ""
	canceled_at: str = ""
	return_code: int | None = None
	error: str = ""
	error_code: str = ""
	superseded_by: str = ""
	response_payload: dict[str, Any] = field(default_factory=dict)
	process: subprocess.Popen[str] | None = field(default=None, repr=False)
	cancel_requested: bool = field(default=False, repr=False)


class _ServiceState:
	def __init__(self, workspace_root: Path, session_id: str, *, owner_shell_id: str = "", owner_shell_type: str = ""):
		self.workspace_root = workspace_root
		self.session_id = session_id
		self.owner_shell_id = owner_shell_id
		self.owner_shell_type = owner_shell_type
		self.started_at = _iso_now()
		self._jobs: dict[str, _JobRecord] = {}
		self._lock = threading.Lock()

	def descriptor(self) -> dict[str, Any]:
		return build_persistent_service_descriptor(
			self.workspace_root,
			self.session_id,
			owner_shell_id=self.owner_shell_id,
			owner_shell_type=self.owner_shell_type,
		)

	def _job_summary(self, job: _JobRecord) -> dict[str, Any]:
		return {
			"jobId": job.job_id,
			"command": job.command,
			"sessionId": job.session_id,
			"status": job.status,
			"submittedAt": job.submitted_at,
			"startedAt": job.started_at,
			"completedAt": job.completed_at,
			"canceledAt": job.canceled_at,
			"returnCode": job.return_code,
			"error": job.error,
			"errorCode": job.error_code,
			"supersededBy": job.superseded_by,
			"progress": {
				"phase": job.status,
				"message": job.status.replace("-", " "),
			},
		}

	def _active_job_summaries(self) -> list[dict[str, Any]]:
		with self._lock:
			jobs = [
				self._job_summary(job)
				for job in self._jobs.values()
				if job.status in {"queued", "running", "cancel-requested"}
			]
		return jobs

	def _create_job(self, command: str, session_id: str) -> _JobRecord:
		job = _JobRecord(
			job_id=f"waw-job-{uuid4().hex[:12]}",
			command=command,
			session_id=session_id,
			status="queued",
			submitted_at=_iso_now(),
		)
		with self._lock:
			self._jobs[job.job_id] = job
		return job

	def _cancel_job(self, job_id: str, *, superseded_by: str = "") -> _JobRecord:
		normalized_job_id = _text_or_empty(job_id)
		if not normalized_job_id:
			raise ValueError("job/cancel payload is missing jobId.")

		with self._lock:
			job = self._jobs.get(normalized_job_id)
			if job is None:
				raise ValueError(f"Unknown local integration jobId: {normalized_job_id}")

			if _text_or_empty(superseded_by):
				job.superseded_by = _text_or_empty(superseded_by)

			if job.status in {"completed", "failed", "cancelled"}:
				return job

			job.cancel_requested = True
			if job.process is None:
				job.status = "cancelled"
				job.canceled_at = _iso_now()
				job.completed_at = job.canceled_at
				job.error = "Local integration job cancelled before execution."
				job.error_code = "job-cancelled"
				return job

			job.status = "cancel-requested"
			process = job.process

		if process is not None and process.poll() is None:
			try:
				process.terminate()
			except OSError:
				pass

		return job

	def handle_job_cancel_request(self, envelope: dict[str, Any]) -> dict[str, Any]:
		payload = _mapping_or_empty(envelope.get("payload"))
		job = self._cancel_job(
			_text_or_empty(payload.get("jobId")) or _text_or_empty(envelope.get("jobId")),
			superseded_by=_text_or_empty(payload.get("supersededByJobId")),
		)
		return {
			"ok": True,
			"job": self._job_summary(job),
			"service": self.descriptor(),
		}

	def handle_job_status_request(self, envelope: dict[str, Any]) -> dict[str, Any]:
		payload = _mapping_or_empty(envelope.get("payload"))
		job_id = _text_or_empty(payload.get("jobId")) or _text_or_empty(envelope.get("jobId"))
		if not job_id:
			raise ValueError("job/status payload is missing jobId.")

		with self._lock:
			job = self._jobs.get(job_id)
			if job is None:
				raise ValueError(f"Unknown local integration jobId: {job_id}")

		return {
			"ok": True,
			"job": self._job_summary(job),
			"service": self.descriptor(),
		}

	def _bootstrap_module(self):
		from services.local_integration import bootstrap_service

		return bootstrap_service

	def _run_runner_job(
		self,
		job: _JobRecord,
		command: str,
		runner_path: Path,
		payload: dict[str, Any],
		*,
		cwd: Path,
	) -> dict[str, Any]:
		bootstrap_service = self._bootstrap_module()

		if not runner_path.exists():
			job.status = "failed"
			job.completed_at = _iso_now()
			job.error = f"Compatibility runner not found for {command}: {runner_path}"
			job.error_code = "runner-not-found"
			job.response_payload = {
				"ok": False,
				"error": job.error,
				"errorCode": job.error_code,
			}
			return job.response_payload

		process = subprocess.Popen(
			[sys.executable, str(runner_path)],
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True,
			cwd=str(cwd),
		)

		with self._lock:
			job.process = process
			job.status = "running"
			job.started_at = _iso_now()

		stdout, stderr = process.communicate(json.dumps(payload))

		with self._lock:
			job.process = None
			job.return_code = process.returncode

		if job.cancel_requested:
			job.status = "cancelled"
			job.canceled_at = _iso_now()
			job.completed_at = job.canceled_at
			job.error = "Local integration job cancelled."
			job.error_code = "job-cancelled"
			job.response_payload = {
				"ok": False,
				"error": job.error,
				"errorCode": job.error_code,
			}
			return job.response_payload

		try:
			parsed = bootstrap_service._parse_runner_output(stdout or "", command=command)
		except Exception as error:
			job.status = "failed"
			job.completed_at = _iso_now()
			job.error = str(error)
			job.error_code = "runner-invalid-response"
			job.response_payload = {
				"ok": False,
				"error": job.error,
				"errorCode": job.error_code,
			}
			if stderr.strip():
				job.response_payload["stderr"] = stderr.strip()
			return job.response_payload

		response = bootstrap_service._mapping_or_empty(parsed)
		if process.returncode != 0 and response.get("ok") is True:
			response = {
				"ok": False,
				"error": f"{command} exited with code {process.returncode} but reported ok=true.",
				"errorCode": "runner-exit-mismatch",
			}

		if process.returncode != 0 and response.get("ok") is not False:
			response["ok"] = False
			response.setdefault("error", f"{command} exited with code {process.returncode}.")
			response.setdefault("errorCode", f"{command.replace('/', '-')}-failed")

		if stderr.strip() and response.get("ok") is False and not _text_or_empty(response.get("stderr")):
			response["stderr"] = stderr.strip()

		job.response_payload = response
		job.completed_at = _iso_now()
		if response.get("ok") is False:
			job.status = "failed"
			job.error = _text_or_empty(response.get("error"))
			job.error_code = _text_or_empty(response.get("errorCode"))
		else:
			job.status = "completed"

		return response

	def handle_runner_command(self, envelope: dict[str, Any]) -> dict[str, Any]:
		bootstrap_service = self._bootstrap_module()
		command = _text_or_empty(envelope.get("command"))
		workspace_root, existing_manifest, manifest_path = bootstrap_service._load_existing_session(
			envelope,
			command=command,
		)
		session_summary = build_session_summary(existing_manifest, manifest_path)
		payload = bootstrap_service._mapping_or_empty(envelope.get("payload"))
		graph_project_root = bootstrap_service._resolve_graph_project_root(envelope, workspace_root)
		runner_path = (
			bootstrap_service._resolve_backend_runner_path(graph_project_root)
			if command == "backend-call/run"
			else bootstrap_service._resolve_recorded_audio_import_runner_path(graph_project_root)
		)

		job = self._create_job(command, session_summary["sessionId"])
		supersedes_job_id = _text_or_empty(payload.get("supersedesJobId")) or _text_or_empty(envelope.get("supersedesJobId"))
		if supersedes_job_id:
			self._cancel_job(supersedes_job_id, superseded_by=job.job_id)

		response = self._run_runner_job(job, command, runner_path, payload, cwd=graph_project_root)
		return {
			"ok": True,
			"session": session_summary,
			"response": response,
			"job": self._job_summary(job),
			"service": self.descriptor(),
		}


class _ThreadingUnixStreamServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
	daemon_threads = True


class _LocalIntegrationRequestHandler(socketserver.StreamRequestHandler):
	def handle(self) -> None:
		try:
			raw_payload = self.rfile.read().decode("utf-8")
			if not raw_payload.strip():
				raise ValueError("No JSON payload received for the persistent local integration service.")

			envelope = json.loads(raw_payload)
			if not isinstance(envelope, dict):
				raise ValueError("Persistent local integration service payload must be a JSON object.")

			normalized_envelope = {
				**envelope,
				"workspaceRoot": str(self.server.state.workspace_root),
			}
			response = self.server.dispatch(normalized_envelope)
		except Exception as error:
			response = {
				"ok": False,
				"error": str(error),
				"traceback": traceback.format_exc(),
			}

		self.wfile.write(json.dumps(response).encode("utf-8"))
		self.wfile.flush()


class _LocalIntegrationSocketServer(_ThreadingUnixStreamServer):
	def __init__(self, socket_path: str, state: _ServiceState):
		self.state = state
		super().__init__(socket_path, _LocalIntegrationRequestHandler)

	def dispatch(self, envelope: dict[str, Any]) -> dict[str, Any]:
		command = _text_or_empty(envelope.get("command"))
		if command == "service/ping":
			return {
				"ok": True,
				"sessionId": self.state.session_id,
				"service": self.state.descriptor(),
				"serviceState": {
					"startedAt": self.state.started_at,
					"activeJobs": self.state._active_job_summaries(),
				},
			}

		if command == "service/shutdown":
			threading.Thread(target=self.shutdown, daemon=True).start()
			return {
				"ok": True,
				"sessionId": self.state.session_id,
				"service": self.state.descriptor(),
				"serviceState": {
					"startedAt": self.state.started_at,
					"shuttingDown": True,
				},
			}

		if command == "job/cancel":
			return self.state.handle_job_cancel_request(envelope)

		if command == "job/status":
			return self.state.handle_job_status_request(envelope)

		if command in {"backend-call/run", "recorded-audio/import"}:
			return self.state.handle_runner_command(envelope)

		from services.local_integration.bootstrap_service import _handle_command

		return _handle_command(envelope)


def _cleanup_socket(socket_path: Path) -> None:
	try:
		if socket_path.exists():
			socket_path.unlink()
	except OSError:
		return


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description="WildAudioWorlds persistent local integration service")
	parser.add_argument("--workspace-root", required=True)
	parser.add_argument("--session-id", required=True)
	parser.add_argument("--owner-shell-id", default="")
	parser.add_argument("--owner-shell-type", default="")
	args = parser.parse_args(argv)

	workspace_root = Path(args.workspace_root).resolve()
	session_id = _text_or_empty(args.session_id)
	socket_path = resolve_service_socket_path(workspace_root, session_id)
	_cleanup_socket(socket_path)
	atexit.register(_cleanup_socket, socket_path)

	state = _ServiceState(
		workspace_root,
		session_id,
		owner_shell_id=_text_or_empty(args.owner_shell_id),
		owner_shell_type=_text_or_empty(args.owner_shell_type),
	)
	server = _LocalIntegrationSocketServer(str(socket_path), state)
	try:
		server.serve_forever(poll_interval=0.1)
	finally:
		server.server_close()
		_cleanup_socket(socket_path)
	return 0


__all__ = [
	"build_persistent_service_descriptor",
	"ensure_persistent_service",
	"is_service_available",
	"resolve_service_socket_path",
	"send_service_command",
	"shutdown_persistent_service",
]


if __name__ == "__main__":
	raise SystemExit(main())