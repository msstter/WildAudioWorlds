"""Shared analysis helpers used across GUI and pipeline surfaces."""

from .mfcc_template import clean_audio_with_mfcc_template
from .signal_profiles import (
    analyze_region,
    build_per_signal_profiles,
    build_signal_profile,
    cluster_signal_regions,
    compute_spectrogram,
    summarize_signal_region_analyses,
)

from .spectral_profiles import (
    build_spectral_profile,
    compute_spectral_similarity_at_time,
    gate_onsets_by_spectral_match,
)

__all__ = [
    "analyze_region",
    "build_per_signal_profiles",
    "build_signal_profile",
    "build_spectral_profile",
    "clean_audio_with_mfcc_template",
    "cluster_signal_regions",
    "compute_spectrogram",
    "compute_spectral_similarity_at_time",
    "gate_onsets_by_spectral_match",
    "summarize_signal_region_analyses",
]