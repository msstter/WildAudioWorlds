"""Tests for the shared recommendation analysis boundary."""

import os
import sys
import tempfile

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import onset_analyzer
from analysis.audio_recommendations import analyze_audio as analyze_audio_shared
from analysis.onset_recommendations import analyze_for_onsets as analyze_for_onsets_shared
from audio_analyzer import analyze_audio as analyze_audio_wrapper


def _write_test_audio(duration=1.0, sr=22050):
    timeline = np.arange(int(sr * duration), dtype=np.float32) / sr
    waveform = (
        0.5 * np.sin(2 * np.pi * 440 * timeline)
        + 0.2 * np.sin(2 * np.pi * 880 * timeline)
    ).astype(np.float32)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        sf.write(handle.name, waveform, sr)
        return handle.name


def test_shared_audio_recommendations_match_script_wrapper():
    audio_path = _write_test_audio(duration=1.5)

    try:
        shared = analyze_audio_shared(audio_path)
        compat = analyze_audio_wrapper(audio_path)
    finally:
        os.unlink(audio_path)

    assert shared == compat


def test_shared_onset_recommendations_accept_injected_detector_hooks():
    audio_path = _write_test_audio(duration=2.0)

    def _stub_detect_onsets(method, y, sr, **kwargs):
        assert method == "librosa"
        return np.array([0.20, 0.65, 1.10], dtype=float)

    def _stub_build_detector_call(settings):
        return settings["ONSET_METHOD"], {}

    try:
        result = analyze_for_onsets_shared(
            audio_path,
            available_methods_fn=lambda: ["librosa"],
            detect_onsets_fn=_stub_detect_onsets,
            build_detector_call_fn=_stub_build_detector_call,
        )
    finally:
        os.unlink(audio_path)

    assert result["analysis"]["n_methods_tested"] == 1
    assert result["settings"]["ONSET_METHOD"] == "librosa"
    assert result["settings"]["ONSET_HOP_LENGTH"] == 256
    assert set(result["method_results"]) == {"librosa"}


def test_script_onset_analyzer_wrapper_uses_module_level_hooks(monkeypatch):
    audio_path = _write_test_audio(duration=2.0)

    monkeypatch.setattr(onset_analyzer, "available_methods", lambda: ["librosa"])
    monkeypatch.setattr(
        onset_analyzer,
        "build_detector_call",
        lambda settings: (settings["ONSET_METHOD"], {}),
    )
    monkeypatch.setattr(
        onset_analyzer,
        "detect_onsets",
        lambda method, y, sr, **kwargs: np.array([0.15, 0.55, 0.95], dtype=float),
    )

    try:
        result = onset_analyzer.analyze_for_onsets(audio_path)
    finally:
        os.unlink(audio_path)

    assert result["analysis"]["n_methods_tested"] == 1
    assert result["settings"]["ONSET_METHOD"] == "librosa"
    assert set(result["method_results"]) == {"librosa"}