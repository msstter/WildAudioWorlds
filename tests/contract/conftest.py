import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


from services.local_integration.service_runtime import shutdown_persistent_service  # noqa: E402


@pytest.fixture(autouse=True)
def _shutdown_persistent_local_integration_services():
	yield
	socket_root = Path("/tmp") / "wild_audio_worlds"
	if not socket_root.exists():
		return
	for socket_path in socket_root.glob("*.sock"):
		shutdown_persistent_service(socket_path)