"""Integration test for dual-mode (positive/negative) signal profile."""
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pytest
import soundfile as sf

import onset_analyzer
from signal_selector import SpectrogramSelector, build_signal_profile
from audio_analyzer import analyze_audio
from onset_analyzer import analyze_for_onsets


def _build_test_profile():
    y = np.random.randn(44100 * 5).astype(np.float32)
    sr = 44100
    sel = SpectrogramSelector(y, sr)
    assert sel._selection_mode == 'positive', 'Default should be positive'

    sel.profile_regions.append({
        't_start': 0.5, 't_end': 1.0, 'f_low': 200, 'f_high': 2000
    })
    sel.negative_regions.append({
        't_start': 2.0, 't_end': 2.5, 'f_low': 50, 'f_high': 150
    })

    profile = sel._finalize()

    return profile


def _write_temp_wav(y, sr):
    fd, path = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    sf.write(path, y, sr)
    return path


@pytest.fixture
def profile():
    return _build_test_profile()


def test_profile_structure(profile):
    assert isinstance(profile, dict)

    assert 'regions' in profile
    assert 'summary' in profile
    assert 'negative_regions' in profile
    assert 'negative_summary' in profile
    assert profile['summary']['n_regions'] == 1
    assert profile['negative_summary']['n_regions'] == 1
    print(f"  Positive: {profile['summary']['n_regions']} region(s), "
          f"freq={profile['summary']['freq_range_hz']}")
    print(f"  Negative: {profile['negative_summary']['n_regions']} region(s), "
          f"freq={profile['negative_summary']['freq_range_hz']}")


def test_audio_analyzer(profile):
    y = np.random.randn(44100 * 5).astype(np.float32)
    sr = 44100
    path = _write_temp_wav(y, sr)
    try:
        result = analyze_audio(path, signal_profile=profile)
    finally:
        os.unlink(path)

    s = result['settings']
    r = result['reasoning']
    print(f"  HIGHPASS: {s['MUTER_HIGHPASS_HZ']} Hz")
    print(f"    {r.get('MUTER_HIGHPASS_HZ', '')}")
    print(f"  HPSS: {s['MUTER_HPSS_ENABLED']}")
    print(f"    {r.get('MUTER_HPSS_ENABLED', '')}")
    print(f"  NOTCH: {s['MUTER_NOTCH_FREQS']}")
    if 'MUTER_NOTCH_FREQS' in r:
        print(f"    {r['MUTER_NOTCH_FREQS']}")
    assert isinstance(result, dict)
    assert 'settings' in result
    assert 'reasoning' in result


def test_onset_analyzer(monkeypatch, profile):
    monkeypatch.setattr(
        onset_analyzer,
        "available_methods",
        lambda: [
            "adaptive_hp",
            "librosa",
            "moving_median",
            "superflux",
            "cfar",
            "per_band",
        ],
    )

    y = np.random.randn(44100 * 5).astype(np.float32)
    sr = 44100
    path = _write_temp_wav(y, sr)
    try:
        result = analyze_for_onsets(path, signal_profile=profile)
    finally:
        os.unlink(path)

    s = result['settings']
    r = result['reasoning']
    print(f"  METHOD: {s['ONSET_METHOD']}")
    print(f"    {r.get('ONSET_METHOD', '')}")
    print(f"  SHARPNESS_GATE: {s['ONSET_SHARPNESS_GATE']}")
    print(f"    {r.get('ONSET_SHARPNESS_GATE', '')}")
    assert isinstance(result, dict)
    assert 'settings' in result
    assert 'reasoning' in result


def test_status_text():
    y = np.random.randn(44100 * 3).astype(np.float32)
    sel = SpectrogramSelector(y, 44100)
    sel._pending_regions = [{'t_start': 0, 't_end': 1, 'f_low': 0, 'f_high': 100}]
    sel._pending_neg_regions = [{'t_start': 1, 't_end': 2, 'f_low': 0, 'f_high': 50}]
    sel.profile_regions = [{'t_start': 0, 't_end': 1, 'f_low': 200, 'f_high': 2000}]
    sel.negative_regions = [{'t_start': 2, 't_end': 3, 'f_low': 50, 'f_high': 150}]
    txt = sel._status_text()
    print(f"  Status text: {txt}")
    assert '1+ pending' in txt
    assert '1\u2212 pending' in txt
    assert '1+ in profile' in txt
    assert '1\u2212 to suppress' in txt


if __name__ == '__main__':
    print("1. Profile structure...")
    profile = _build_test_profile()
    test_profile_structure(profile)
    print("   PASS\n")

    print("2. Audio Analyzer with dual profile...")
    test_audio_analyzer(profile)
    print("   PASS\n")

    print("3. Onset Analyzer with dual profile...")
    test_onset_analyzer(profile)
    print("   PASS\n")

    print("4. Status text...")
    test_status_text()
    print("   PASS\n")

    print("All tests passed!")
