import json
import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "packages"
GRAPH_BACKEND_DIR = ROOT / "3DAudioGraphs-main" / "backend"

if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

if str(GRAPH_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(GRAPH_BACKEND_DIR))


from main import process_audio_file  # noqa: E402
from wild_audio_worlds.data import DataManager  # noqa: E402
from wild_audio_worlds.data.audio_asset_store import (  # noqa: E402
    load_manifest_entries as compatibility_load_manifest_entries,
    upsert_manifest_entry as compatibility_upsert_manifest_entry,
)


def _build_frame_metadata(frame_count=2):
    return {
        "sample_rate": 24000,
        "hop_length": 240,
        "frame_length": 480,
        "frame_count": frame_count,
        "clip_duration_sec": frame_count * 0.01,
        "fft_nfft": 4,
        "frame_indices": np.arange(frame_count),
        "time_starts_sec": np.linspace(0.0, 0.01 * max(frame_count - 1, 0), frame_count),
        "time_centers_sec": np.linspace(0.005, 0.005 + (0.01 * max(frame_count - 1, 0)), frame_count),
        "time_ends_sec": np.linspace(0.01, 0.01 + (0.01 * max(frame_count - 1, 0)), frame_count),
        "sample_starts": np.arange(frame_count) * 240,
        "sample_centers": np.arange(frame_count) * 240 + 120,
        "sample_ends": np.arange(frame_count) * 240 + 240,
    }


def _write_source_audio(project_root: Path, file_name: str = "forest.wav") -> Path:
    source_path = project_root / "data" / "sample_audio" / file_name
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(b"RIFFTEST")
    return source_path


def test_data_manager_publishes_revisioned_assets_and_manifest_metadata(tmp_path):
    data_manager = DataManager(tmp_path)
    source_audio_path = _write_source_audio(tmp_path)

    manifest_entry = data_manager.publish_graph_asset_artifacts(
        source_audio_path=source_audio_path,
        display_name="Forest Dawn",
        fft_export_matrix=np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
        fft_header="FFT_Bin_0,FFT_Bin_1",
        fft_file_name="forest_FFTs.csv",
        terrain_envelope={"kind": "terrain-envelope-v2", "frameCount": 2},
        terrain_file_name="forest_TerrainEnvelope.json",
        mfcc_export_matrix=np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32),
        mfcc_header="Audio_UMAP_X,Audio_UMAP_Y",
        mfcc_file_name="forest_MFCC.csv",
        manifest_fields={"analysisFrameCount": 2},
    )
    manifest_payload = data_manager.upsert_manifest_entry(manifest_entry)

    assert manifest_entry["id"] == "forest-wav"
    assert manifest_entry["assetId"] == "forest-wav"
    assert manifest_entry["revisionId"] == "rev-0001"
    assert manifest_entry["audioUrl"] == "./audio_assets/forest-wav/rev-0001/forest.wav"
    assert manifest_payload["manifestRevision"] == 1
    assert manifest_payload["managedBy"] == "wild_audio_worlds.data.DataManager"
    assert manifest_payload["assets"][0]["revisionId"] == "rev-0001"

    assert (tmp_path / "frontend" / "public" / "audio_assets" / "forest-wav" / "rev-0001" / "forest.wav").exists()
    assert (tmp_path / "frontend" / "public" / "audio_assets" / "forest-wav" / "rev-0001" / "forest_FFTs.csv").exists()
    assert (tmp_path / "data" / "exports" / "forest-wav" / "rev-0001" / "forest_TerrainEnvelope.json").exists()


def test_data_manager_increments_asset_revision_and_rejects_stale_manifest_writes(tmp_path):
    data_manager = DataManager(tmp_path)
    source_audio_path = _write_source_audio(tmp_path)

    first_entry = data_manager.publish_graph_asset_artifacts(
        source_audio_path=source_audio_path,
        display_name="Forest Dawn",
        fft_export_matrix=np.array([[1.0, 2.0]], dtype=np.float32),
        fft_header="FFT_Bin_0,FFT_Bin_1",
        fft_file_name="forest_FFTs.csv",
        terrain_envelope={"kind": "terrain-envelope-v2", "frameCount": 1},
        terrain_file_name="forest_TerrainEnvelope.json",
    )
    first_payload = data_manager.upsert_manifest_entry(first_entry)

    second_entry = data_manager.publish_graph_asset_artifacts(
        source_audio_path=source_audio_path,
        display_name="Forest Dawn",
        fft_export_matrix=np.array([[5.0, 6.0]], dtype=np.float32),
        fft_header="FFT_Bin_0,FFT_Bin_1",
        fft_file_name="forest_FFTs.csv",
        terrain_envelope={"kind": "terrain-envelope-v2", "frameCount": 1},
        terrain_file_name="forest_TerrainEnvelope.json",
    )

    assert second_entry["revisionId"] == "rev-0002"
    second_payload = data_manager.upsert_manifest_entry(
        second_entry,
        expected_manifest_revision=first_payload["manifestRevision"],
    )

    assert second_payload["manifestRevision"] == 2
    assert second_payload["assets"][0]["revisionId"] == "rev-0002"
    assert (tmp_path / "frontend" / "public" / "audio_assets" / "forest-wav" / "rev-0001" / "forest.wav").exists()
    assert (tmp_path / "frontend" / "public" / "audio_assets" / "forest-wav" / "rev-0002" / "forest.wav").exists()

    with pytest.raises(ValueError, match="Manifest revision mismatch"):
        data_manager.upsert_manifest_entry(second_entry, expected_manifest_revision=1)


class _FakeAudioProcessor:
    def extract_features(self, _audio_path):
        return (
            np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32),
            np.array([0.5, 0.6], dtype=np.float32),
            np.array([220.0, 221.0], dtype=np.float32),
            np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
            _build_frame_metadata(),
        )


def test_process_audio_file_routes_publication_through_data_manager(tmp_path):
    source_audio_path = _write_source_audio(tmp_path, "wetland.wav")

    manifest_entry = process_audio_file(
        source_audio_path,
        include_mfcc=True,
        display_name="Wetland Dawn",
        project_root=tmp_path,
        logger=None,
        audio_proc=_FakeAudioProcessor(),
        dim_reducer=None,
    )

    assert manifest_entry["id"] == "wetland-wav"
    assert manifest_entry["revisionId"] == "rev-0001"
    assert manifest_entry["hasMfccData"] is True
    assert manifest_entry["audioUrl"] == "./audio_assets/wetland-wav/rev-0001/wetland.wav"
    assert manifest_entry["mfccCsvUrl"] == "./audio_assets/wetland-wav/rev-0001/wetland_MFCC.csv"
    assert manifest_entry["fftCsvUrl"] == "./audio_assets/wetland-wav/rev-0001/wetland_FFTs.csv"
    assert manifest_entry["terrainEnvelopeUrl"] == "./audio_assets/wetland-wav/rev-0001/wetland_TerrainEnvelope.json"
    assert (tmp_path / "frontend" / "public" / "audio_assets" / "wetland-wav" / "rev-0001" / "wetland.wav").exists()
    assert (tmp_path / "data" / "exports" / "wetland-wav" / "rev-0001" / "wetland_MFCC.csv").exists()


def test_audio_asset_store_manifest_helpers_delegate_to_data_manager(tmp_path):
    data_manager = DataManager(tmp_path)
    source_audio_path = _write_source_audio(tmp_path, "river.wav")
    manifest_entry = data_manager.publish_graph_asset_artifacts(
        source_audio_path=source_audio_path,
        display_name="River Dawn",
        fft_export_matrix=np.array([[1.0, 2.0]], dtype=np.float32),
        fft_header="FFT_Bin_0,FFT_Bin_1",
        fft_file_name="river_FFTs.csv",
        terrain_envelope={"kind": "terrain-envelope-v2", "frameCount": 1},
        terrain_file_name="river_TerrainEnvelope.json",
    )

    manifest_entries = compatibility_upsert_manifest_entry(data_manager.manifest_path, manifest_entry)

    assert manifest_entries[0]["revisionId"] == "rev-0001"
    assert compatibility_load_manifest_entries(data_manager.manifest_path)[0]["assetId"] == "river-wav"

    with data_manager.manifest_path.open("r", encoding="utf-8") as handle:
        manifest_payload = json.load(handle)

    assert manifest_payload["managedBy"] == "wild_audio_worlds.data.DataManager"
    assert manifest_payload["manifestRevision"] == 1