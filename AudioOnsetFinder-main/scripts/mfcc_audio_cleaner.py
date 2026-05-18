"""Compatibility wrapper for the shared MFCC-template cleaner."""

from __future__ import annotations

import os
import sys

import numpy as np


_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from analysis.mfcc_template import clean_audio_with_mfcc_template as _clean_audio_with_mfcc_template_impl


def clean_audio_with_mfcc_template(
    y_raw: np.ndarray,
    sr: int,
    templates: list[np.ndarray],
    *,
    threshold_percentile: float = 15.0,
    n_mfcc: int = 13,
    hop_length: int = 512,
    smooth_ms: float = 50.0,
) -> np.ndarray:
    """Delegate MFCC-template cleaning to the shared analysis module."""
    return _clean_audio_with_mfcc_template_impl(
        y_raw,
        sr,
        templates,
        threshold_percentile=threshold_percentile,
        n_mfcc=n_mfcc,
        hop_length=hop_length,
        smooth_ms=smooth_ms,
    )
