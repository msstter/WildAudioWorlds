"""Tests for the shared MFCC-template analysis boundary."""

import numpy as np
import pytest

from analysis import clean_audio_with_mfcc_template
from scripts.mfcc_audio_cleaner import (
    clean_audio_with_mfcc_template as clean_audio_with_mfcc_template_wrapper,
)


def _make_tone(freq, duration, sr=8000):
    timeline = np.arange(int(sr * duration)) / sr
    return np.sin(2 * np.pi * freq * timeline).astype(np.float32)


def test_shared_mfcc_cleaner_matches_compatibility_wrapper():
    sr = 8000
    y_raw = np.concatenate(
        [
            _make_tone(600, 0.35, sr=sr),
            np.zeros(int(sr * 0.15), dtype=np.float32),
            _make_tone(600, 0.35, sr=sr),
        ]
    )
    template = [_make_tone(600, 0.3, sr=sr)]

    shared = clean_audio_with_mfcc_template(
        y_raw,
        sr,
        template,
        threshold_percentile=30.0,
        smooth_ms=5.0,
        n_mfcc=8,
    )
    compat = clean_audio_with_mfcc_template_wrapper(
        y_raw,
        sr,
        template,
        threshold_percentile=30.0,
        smooth_ms=5.0,
        n_mfcc=8,
    )

    assert shared.shape == y_raw.shape
    np.testing.assert_allclose(shared, compat)


def test_shared_mfcc_cleaner_rejects_empty_templates():
    with pytest.raises(ValueError, match="At least one template"):
        clean_audio_with_mfcc_template(np.zeros(128, dtype=np.float32), 8000, [])