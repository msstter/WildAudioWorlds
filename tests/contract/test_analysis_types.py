import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "packages"

if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from wild_audio_worlds.session.analysis_types import (  # noqa: E402
    BACKEND_ANALYSIS_TYPE_CONFIGS,
    DEFAULT_BACKEND_ANALYSIS_TYPE,
    get_backend_analysis_type_config,
    is_bioacoustics_analysis_type,
    is_bioacoustics_import_analysis_type,
    is_bioacoustics_sync_analysis_type,
    normalize_backend_analysis_type,
)


def test_analysis_type_registry_matches_expected_actions():
    assert list(BACKEND_ANALYSIS_TYPE_CONFIGS) == [
        "slice-summary",
        "mfcc-profile",
        "spectral-shape",
        "export-time-slice-audio",
        "export-spectral-mask-audio",
        "bioacoustics-import-workbook",
        "bioacoustics-sync-workbook",
    ]


def test_analysis_type_helpers_classify_bioacoustics_actions():
    assert is_bioacoustics_analysis_type("bioacoustics-import-workbook") is True
    assert is_bioacoustics_import_analysis_type("bioacoustics-import-workbook") is True
    assert is_bioacoustics_sync_analysis_type("bioacoustics-import-workbook") is False
    assert is_bioacoustics_sync_analysis_type("bioacoustics-sync-workbook") is True
    assert is_bioacoustics_analysis_type("slice-summary") is False


def test_analysis_type_helpers_use_shared_default_and_configs():
    assert DEFAULT_BACKEND_ANALYSIS_TYPE == "slice-summary"
    assert normalize_backend_analysis_type("  ") == DEFAULT_BACKEND_ANALYSIS_TYPE
    config = get_backend_analysis_type_config("export-time-slice-audio")

    assert config is not None
    assert config["group"] == "analysis"
    assert config["runner"] == "export_time_slice_audio"
    assert config["defaultSaveMode"] == "wav"
    assert config["allowedSaveModes"] == ["wav"]
    assert config["ui"]["label"] == "Export Time Slice Audio"
    assert config["ui"]["showBioOutputMode"] is False
    assert config["readiness"]["requiresSelectionReady"] is True


def test_analysis_type_readiness_metadata_captures_bioacoustics_preconditions():
    import_config = get_backend_analysis_type_config("bioacoustics-import-workbook")
    sync_config = get_backend_analysis_type_config("bioacoustics-sync-workbook")

    assert import_config is not None
    assert import_config["readiness"]["requiresBioacousticsStateField"] == "canImport"
    assert import_config["readiness"]["requiresWorkbookPath"] is True
    assert import_config["readiness"]["acceptsAutoDiscover"] is True

    assert sync_config is not None
    assert sync_config["readiness"]["requiresBioacousticsStateField"] == "canSync"
    assert sync_config["readiness"]["requiresOnsetTimes"] is True
    assert sync_config["readiness"]["workbookPathRequiredForOutputModes"] == ["duplicate", "overwrite"]