import base64
import json
import sys
import wave
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "packages"
GRAPH_BACKEND_DIR = ROOT / "3DAudioGraphs-main" / "backend"

if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

if str(GRAPH_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(GRAPH_BACKEND_DIR))


from main import process_audio_file  # noqa: E402
from bioacoustics_workbook import sync_workbook_onsets  # noqa: E402
from import_recorded_audio import import_recorded_audio  # noqa: E402
from run_selection_analysis import (  # noqa: E402
    _resolve_bio_sync_output_path,
    _save_result,
)
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


def test_data_manager_publishes_backend_call_json_and_wav_exports(tmp_path):
    data_manager = DataManager(tmp_path)

    json_export_path = data_manager.publish_backend_call_json_export(
        {
            "ok": True,
            "analysisType": "slice-summary",
        },
        label="Marsh Dawn",
        analysis_type="slice-summary",
        request_id="abc12345",
    )
    wav_export_path = data_manager.publish_backend_call_wav_export(
        np.array([0.0, 0.25, -0.25], dtype=np.float32),
        sample_rate=24000,
        label="Marsh Dawn",
        analysis_type="export-time-slice-audio",
        request_id="def67890",
    )

    assert json_export_path == tmp_path / "data" / "exports" / "backend_calls" / "marsh-dawn_slice-summary_abc12345.json"
    assert wav_export_path == tmp_path / "data" / "exports" / "backend_calls" / "marsh-dawn_export-time-slice-audio_def67890.wav"

    with json_export_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload == {
        "ok": True,
        "analysisType": "slice-summary",
    }

    with wave.open(str(wav_export_path), "rb") as wav_file:
        assert wav_file.getframerate() == 24000
        assert wav_file.getnframes() == 3


def test_data_manager_publishes_source_audio_input_and_shared_write_helpers(tmp_path):
    data_manager = DataManager(tmp_path)

    source_audio_path = data_manager.publish_source_audio_input(
        b"RIFFRECORDED",
        stem_hint="Marsh Recording",
        extension="wav",
    )
    text_path = tmp_path / "AudioOnsetFinder-main" / "outputs" / "review.txt"
    json_path = tmp_path / "AudioOnsetFinder-main" / "outputs" / "review.json"
    csv_path = tmp_path / "AudioOnsetFinder-main" / "outputs" / "review.csv"
    csv_with_index_path = tmp_path / "AudioOnsetFinder-main" / "outputs" / "review_with_index.csv"
    audio_path = tmp_path / "AudioOnsetFinder-main" / "outputs" / "selection.wav"
    binary_path = tmp_path / "AudioOnsetFinder-main" / "outputs" / "plot.png"

    DataManager.write_text_file(text_path, "alpha\nbeta\n")
    DataManager.write_json_file(json_path, {"ok": True, "count": 2})
    DataManager.write_csv_dataframe(csv_path, pd.DataFrame({"value": [1, 2]}))
    DataManager.write_csv_dataframe(csv_with_index_path, pd.DataFrame({"value": [3, 4]}), index=True)
    DataManager.write_audio_file(audio_path, np.array([0.0, 0.5, -0.5], dtype=np.float32), 16000)
    DataManager.write_binary_file(binary_path, b"PNGDATA")

    assert source_audio_path.parent == tmp_path / "data" / "source_audio" / "recorded"
    assert source_audio_path.suffix == ".wav"
    assert source_audio_path.read_bytes() == b"RIFFRECORDED"
    assert source_audio_path.name.startswith("marsh-recording-")

    assert text_path.read_text(encoding="utf-8") == "alpha\nbeta\n"
    with json_path.open("r", encoding="utf-8") as handle:
        assert json.load(handle) == {"ok": True, "count": 2}
    assert csv_path.read_text(encoding="utf-8").splitlines() == ["value", "1", "2"]
    assert csv_with_index_path.read_text(encoding="utf-8").splitlines() == [",value", "0,3", "1,4"]
    assert binary_path.read_bytes() == b"PNGDATA"

    with wave.open(str(audio_path), "rb") as wav_file:
        assert wav_file.getframerate() == 16000
        assert wav_file.getnframes() == 3



def test_import_recorded_audio_routes_base64_source_publication_through_data_manager(tmp_path, monkeypatch):
    recorded = {}

    def _fake_process_audio_file(audio_path, *, include_mfcc, display_name, project_root, logger=None):
        recorded["audioPath"] = Path(audio_path)
        recorded["includeMfcc"] = include_mfcc
        recorded["displayName"] = display_name
        recorded["projectRoot"] = Path(project_root)
        return {
            "id": "marsh-recording-wav",
            "label": display_name,
            "revisionId": "rev-0001",
        }

    def _fake_upsert_manifest_entry(manifest_path, manifest_entry):
        recorded["manifestPath"] = Path(manifest_path)
        recorded["manifestEntry"] = manifest_entry
        return [manifest_entry]

    monkeypatch.setattr("import_recorded_audio.process_audio_file", _fake_process_audio_file)
    monkeypatch.setattr("import_recorded_audio.upsert_manifest_entry", _fake_upsert_manifest_entry)

    result = import_recorded_audio({
        "audioBufferBase64": base64.b64encode(b"RIFFINTEGRATION").decode("ascii"),
        "assetLabel": "Marsh Take",
        "fileStem": "marsh take",
        "fileExtension": ".wav",
        "includeMfcc": True,
        "projectRoot": str(tmp_path),
    })

    saved_audio_path = Path(result["savedAudioPath"])

    assert saved_audio_path.parent == tmp_path / "data" / "source_audio" / "recorded"
    assert saved_audio_path.read_bytes() == b"RIFFINTEGRATION"
    assert recorded["audioPath"] == saved_audio_path
    assert recorded["displayName"] == "Marsh Take"
    assert recorded["projectRoot"] == tmp_path
    assert recorded["manifestPath"] == tmp_path / "frontend" / "public" / "audio_assets_manifest.json"
    assert recorded["manifestEntry"]["label"] == "Marsh Take"


def test_run_selection_analysis_save_result_routes_exports_through_data_manager(tmp_path, monkeypatch):
    monkeypatch.setattr("run_selection_analysis._project_root", lambda: tmp_path)

    json_save_result = _save_result({
        "analysisType": "slice-summary",
        "asset": {
            "id": "asset-marsh-001",
            "label": "Marsh Dawn",
        },
        "callMeta": {
            "requestId": "jsonreq1",
        },
        "saveOptions": {
            "mode": "json",
            "label": "Marsh Dawn",
        },
        "result": {
            "summary": {
                "durationSec": 1.25,
            },
        },
    })

    wav_save_result = _save_result({
        "analysisType": "export-time-slice-audio",
        "asset": {
            "id": "asset-marsh-001",
            "label": "Marsh Dawn",
        },
        "callMeta": {
            "requestId": "wavreq1",
        },
        "saveOptions": {
            "mode": "wav",
            "label": "Marsh Dawn",
        },
    }, save_artifact={
        "type": "wav",
        "audio": np.array([0.0, 0.1, -0.1, 0.2], dtype=np.float32),
        "sampleRate": 22050,
    })

    assert json_save_result["path"] == "data/exports/backend_calls/marsh-dawn_slice-summary_jsonreq1.json"
    assert wav_save_result["path"] == "data/exports/backend_calls/marsh-dawn_export-time-slice-audio_wavreq1.wav"
    assert (tmp_path / json_save_result["path"]).exists()
    assert (tmp_path / wav_save_result["path"]).exists()


def test_bio_sync_output_fallback_and_workbook_write_route_through_data_manager(tmp_path, monkeypatch):
    monkeypatch.setattr("run_selection_analysis._project_root", lambda: tmp_path)
    output_path = _resolve_bio_sync_output_path({
        "bioacoustics": {
            "outputMode": "export",
        },
        "saveOptions": {
            "label": "Wetland Focus",
        },
    }, "wetland.wav")

    assert output_path == tmp_path / "data" / "exports" / "backend_calls" / "wetland-focus_bioacoustics.xlsx"

    real_writer = DataManager.write_workbook_sheets
    delegated_call = {}

    def _recording_writer(path_value, workbook_sheets):
        delegated_call["outputPath"] = Path(path_value)
        delegated_call["sheetNames"] = sorted(workbook_sheets.keys())
        return real_writer(path_value, workbook_sheets)

    monkeypatch.setattr(DataManager, "write_workbook_sheets", staticmethod(_recording_writer))

    workbook_result = sync_workbook_onsets(
        tmp_path / "template.xlsx",
        "wetland.wav",
        [0.1, 0.3, 0.6],
        output_path=output_path,
    )

    assert delegated_call["outputPath"] == output_path
    assert delegated_call["sheetNames"] == [
        "Dyadic Events (For Plots)",
        "Dyadic Events (Stable Rhythms)",
        "File Summaries",
    ]
    assert Path(workbook_result["outputWorkbookPath"]) == output_path.resolve()
    assert output_path.exists()