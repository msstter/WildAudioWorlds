import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "packages"

if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from wild_audio_worlds.session.command_contracts import (  # noqa: E402
    DEFAULT_BACKEND_ANALYSIS_TYPE,
    DEFAULT_BACKEND_SAVE_MODE,
    normalize_backend_analysis_request,
    parse_backend_analysis_request_json,
)


def test_parse_backend_analysis_request_json_applies_defaults():
    parsed = parse_backend_analysis_request_json('{"asset": {"id": "asset-1"}, "selection": {"isReady": 1, "timeRangeSec": null}, "saveOptions": {"label": "  Demo  "}}')

    assert parsed["analysisType"] == DEFAULT_BACKEND_ANALYSIS_TYPE
    assert parsed["asset"] == {"id": "asset-1"}
    assert parsed["selection"] == {
        "isReady": True,
        "frameRange": {},
        "sampleRange": {},
        "timeRangeSec": {},
        "frequencyBinRange": {},
        "amplitudePctRange": {},
    }
    assert parsed["bioacoustics"] == {}
    assert parsed["uiContext"] == {}
    assert parsed["saveOptions"]["mode"] == DEFAULT_BACKEND_SAVE_MODE
    assert parsed["saveOptions"]["label"] == "Demo"


def test_normalize_backend_analysis_request_preserves_known_sections():
    normalized = normalize_backend_analysis_request({
        "analysisType": " bioacoustics-sync-workbook ",
        "asset": {"id": "asset-2", "audioUrl": "./audio.wav"},
        "selection": {"isReady": True},
        "bioacoustics": {"workbookPath": "book.xlsx", "onsetTimes": [0.1, 0.5]},
        "saveOptions": {"mode": "XLSX", "label": " Sync "},
        "callMeta": {"requestId": " abc-123 ", "requestedAt": "2026-05-18T18:00:00Z"},
    })

    assert normalized["analysisType"] == "bioacoustics-sync-workbook"
    assert normalized["asset"]["audioUrl"] == "./audio.wav"
    assert normalized["selection"]["isReady"] is True
    assert normalized["bioacoustics"]["workbookPath"] == "book.xlsx"
    assert normalized["saveOptions"]["mode"] == "xlsx"
    assert normalized["saveOptions"]["label"] == "Sync"
    assert normalized["callMeta"]["requestId"] == "abc-123"


def test_parse_backend_analysis_request_json_rejects_non_object_payloads():
    try:
        parse_backend_analysis_request_json('[1, 2, 3]')
    except ValueError as error:
        assert str(error) == "Selection analysis payload must be a JSON object."
    else:
        raise AssertionError("Expected ValueError for non-object JSON payload.")