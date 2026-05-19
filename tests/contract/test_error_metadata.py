import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "packages"

if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from wild_audio_worlds.session.error_metadata import (  # noqa: E402
    build_backend_failure,
    enrich_backend_failure,
    get_backend_error_metadata,
)


def test_get_backend_error_metadata_returns_shared_message():
    metadata = get_backend_error_metadata("backend-call-invoke-failed")

    assert metadata == {
        "message": "Backend call failed.",
    }


def test_build_backend_failure_applies_shared_code_and_message():
    failure = build_backend_failure("backend-no-payload", stderr="demo stderr")

    assert failure == {
        "ok": False,
        "errorCode": "backend-no-payload",
        "error": "Backend analysis returned no payload.",
        "stderr": "demo stderr",
    }


def test_enrich_backend_failure_preserves_explicit_error_text():
    failure = enrich_backend_failure({
        "error": "Audio asset not found on disk.",
    }, error_code="backend-analysis-failed")

    assert failure == {
        "ok": False,
        "errorCode": "backend-analysis-failed",
        "error": "Audio asset not found on disk.",
    }