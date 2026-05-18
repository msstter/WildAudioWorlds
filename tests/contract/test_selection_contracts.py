import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "packages"

if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from wild_audio_worlds.session.selection_contracts import (  # noqa: E402
    normalize_backend_selection_contract,
    normalize_selection_amplitude_pct_range,
    normalize_selection_frequency_window,
    normalize_selection_time_window,
)


def test_normalize_backend_selection_contract_coerces_nested_sections():
    normalized = normalize_backend_selection_contract({
        "isReady": 1,
        "timeRangeSec": None,
        "frequencyBinRange": {"startBin": 2},
        "amplitudePctRange": "invalid",
    })

    assert normalized["isReady"] is True
    assert normalized["timeRangeSec"] == {}
    assert normalized["frequencyBinRange"] == {"startBin": 2}
    assert normalized["amplitudePctRange"] == {}


def test_normalize_selection_time_window_clamps_to_clip_duration():
    window = normalize_selection_time_window({
        "timeRangeSec": {
            "start": -2,
            "end": 8,
        },
    }, 5.0)

    assert window == {
        "startSec": 0.0,
        "endSec": 5.0,
        "durationSec": 5.0,
    }


def test_normalize_selection_frequency_window_clamps_to_available_bins():
    window = normalize_selection_frequency_window({
        "frequencyBinRange": {
            "startBin": -10,
            "endBin": 99,
            "totalBins": 20,
        },
    }, available_bin_count=16, preferred_total_bins=32)

    assert window == {
        "startBin": 0,
        "endBin": 15,
        "totalBins": 16,
    }


def test_normalize_selection_amplitude_pct_range_can_clamp_for_export_paths():
    amplitude_range = normalize_selection_amplitude_pct_range({
        "amplitudePctRange": {
            "min": -5,
            "max": 140,
        },
    }, clamp_values=True)

    assert amplitude_range == {
        "min": 0.0,
        "max": 100.0,
    }