"""Tests for onset-finder batch routing helpers."""

from types import SimpleNamespace

from scripts.onset_batching import (
    ONSET_SETTING_NAMES,
    load_batch_routing_inputs,
    load_per_file_onset_settings,
    temporary_module_settings,
)


def test_load_per_file_onset_settings_supports_directory_payloads(tmp_path):
    payload = tmp_path / "clip.json"
    payload.write_text(
        '{"filename": "demo.wav", "onset_recommendations": {"ONSET_METHOD": "superflux", "ONSET_DELTA": 0.04}}',
        encoding="utf-8",
    )

    result = load_per_file_onset_settings(str(tmp_path))

    assert result == {
        "demo.wav": {"ONSET_METHOD": "superflux", "ONSET_DELTA": 0.04}
    }


def test_load_batch_routing_inputs_collects_focus_and_selected_layers(tmp_path):
    audio_file = tmp_path / "demo.wav"
    audio_file.write_bytes(b"wav")

    settings_path = tmp_path / "per_file_settings.json"
    settings_path.write_text(
        '{"demo.wav": {"onset_recommendations": {"ONSET_METHOD": "adaptive_hp"}}, "__general_metadata__": {"Group": "A"}}',
        encoding="utf-8",
    )

    focus_path = tmp_path / "focus_regions.json"
    focus_path.write_text(
        '{"demo.wav": [{"t_start": 0.1, "t_end": 0.3, "polarity": "positive"}]}',
        encoding="utf-8",
    )

    layer_dir = tmp_path / "demo_OnsetLayers"
    layer_dir.mkdir()
    (layer_dir / "Layer_1.json").write_text(
        '{"name": "Keep", "focus_regions": []}',
        encoding="utf-8",
    )
    (layer_dir / "Layer_2.json").write_text(
        '{"name": "Skip", "focus_regions": []}',
        encoding="utf-8",
    )

    result = load_batch_routing_inputs(
        str(tmp_path),
        ["demo.wav"],
        per_file_settings_path=str(settings_path),
        focus_regions_path=str(focus_path),
        specify_layers=True,
        selected_layers=["Keep"],
    )

    assert result.per_file_cfg == {"demo.wav": {"ONSET_METHOD": "adaptive_hp"}}
    assert result.per_file_focus["demo.wav"][0]["polarity"] == "positive"
    assert len(result.layer_configs["demo.wav"]) == 1
    assert result.layer_configs["demo.wav"][0]["name"] == "Keep"


def test_temporary_module_settings_restores_after_context_exit():
    module = SimpleNamespace()
    for name in ONSET_SETTING_NAMES:
        setattr(module, name, None)
    module.ONSET_METHOD = "librosa"
    module.ONSET_DELTA = 0.06

    with temporary_module_settings(module, {"ONSET_METHOD": "cfar", "ONSET_DELTA": 0.12}):
        assert module.ONSET_METHOD == "cfar"
        assert module.ONSET_DELTA == 0.12

    assert module.ONSET_METHOD == "librosa"
    assert module.ONSET_DELTA == 0.06