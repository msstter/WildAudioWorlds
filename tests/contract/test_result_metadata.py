import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "packages"

if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from wild_audio_worlds.session.result_metadata import (  # noqa: E402
    enrich_backend_save_result,
    get_backend_save_mode_metadata,
)


def test_get_backend_save_mode_metadata_returns_shared_labels():
    metadata = get_backend_save_mode_metadata("xlsx")

    assert metadata == {
        "label": "Write Workbook Output (.xlsx)",
        "artifactType": "workbook-output",
        "artifactLabel": "Workbook Output",
    }


def test_enrich_backend_save_result_adds_shared_mode_and_artifact_labels():
    enriched = enrich_backend_save_result({
        "mode": "wav",
        "saved": True,
        "path": "data/exports/backend_calls/example.wav",
    })

    assert enriched["mode"] == "wav"
    assert enriched["modeLabel"] == "Save WAV to data/exports/backend_calls"
    assert enriched["artifactType"] == "wav-audio"
    assert enriched["artifactLabel"] == "WAV Audio"