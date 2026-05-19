"""Focused non-GUI tests for onset editor writer helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
GUI_DIR = ROOT / "GUI"
SCRIPTS_DIR = ROOT / "scripts"

for directory in (GUI_DIR, SCRIPTS_DIR):
    directory_str = str(directory)
    if directory_str not in sys.path:
        sys.path.insert(0, directory_str)


from onset_editor_io import (  # noqa: E402
    _export_selections_audio,
    _load_labels,
    _save_labels,
    _write_focus_regions_json,
    _write_onset_layer_settings,
)


def test_save_labels_round_trips_through_writer_helper(tmp_path):
    label_path = tmp_path / "song_labels.txt"

    _save_labels(str(label_path), [1.5, 0.5])

    assert _load_labels(str(label_path)) == [0.5, 1.5]
    assert label_path.read_text(encoding="utf-8") == (
        "0.500000\t0.500000\tOnsetR_1\n"
        "1.500000\t1.500000\tOnsetR_2\n"
    )


def test_write_focus_regions_json_merges_regions(tmp_path):
    output_path = _write_focus_regions_json(
        str(tmp_path),
        "song",
        [
            {
                "focus_regions": {
                    "song.wav": [{"t_start": 0.1, "t_end": 0.2, "polarity": "positive"}],
                    "skip.wav": [],
                }
            },
            {
                "focus_regions": {
                    "song.wav": [{"t_start": 0.3, "t_end": 0.4, "polarity": "negative"}],
                }
            },
        ],
    )

    assert output_path == str(tmp_path / "song_focus_regions.json")
    with Path(output_path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    assert list(payload.keys()) == ["song.wav"]
    assert len(payload["song.wav"]) == 2


def test_write_onset_layer_settings_writes_per_layer_json(tmp_path):
    audio_path = tmp_path / "song.wav"
    audio_path.write_bytes(b"RIFF")

    layers_dir = _write_onset_layer_settings(
        str(audio_path),
        [
            {
                "name": "Layer A",
                "focus_regions": {
                    "song.wav": [{"t_start": 0.1, "t_end": 0.2, "polarity": "positive"}],
                },
                "onset_times": [0.1234567, 1.0],
            },
            {
                "name": "Layer B",
                "focus_regions": {"other.wav": [{"t_start": 0.9, "t_end": 1.0, "polarity": "negative"}]},
                "onset_times": [2.3456789],
            },
        ],
    )

    assert layers_dir == str(tmp_path / "song_OnsetLayers")

    first = json.loads((Path(layers_dir) / "Layer_1.json").read_text(encoding="utf-8"))
    second = json.loads((Path(layers_dir) / "Layer_2.json").read_text(encoding="utf-8"))

    assert first["focus_regions"][0]["polarity"] == "positive"
    assert first["onset_times"] == [0.123457, 1.0]
    assert second["focus_regions"] == []
    assert second["onset_times"] == [2.345679]


def test_export_selections_audio_writes_audio_and_manifest(tmp_path):
    audio_path = tmp_path / "song.wav"
    audio_path.write_bytes(b"RIFF")
    output_dir = tmp_path / "exports"

    export_count = _export_selections_audio(
        str(audio_path),
        np.linspace(-1.0, 1.0, 1600, dtype=np.float32),
        16000,
        str(output_dir),
        [
            (
                0,
                {
                    "name": "Layer A",
                    "focus_regions": {
                        "song.wav": [{"t_start": 0.0, "t_end": 0.05, "polarity": "positive"}],
                    },
                },
            )
        ],
        individual=True,
        bandpass=False,
    )

    exported_audio_files = sorted(output_dir.glob("song_Positive*.wav"))
    manifest_path = output_dir / "song_PositiveSignals.json"

    assert export_count == 1
    assert len(exported_audio_files) == 1
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["files"][0]["audio_file"] == exported_audio_files[0].name
    assert manifest["regions"][0]["layer_name"] == "Layer A"
