"""Tests for shared dyad and rhythm-metric helpers."""

import pytest

from scripts.onset_metrics import (
    build_dyad_records,
    calculate_rhythm_metrics,
    calculate_speech_rhythm_metrics,
    calculate_stable_subset_metrics,
    get_stable_dyad_flags,
    is_stable_match,
)


def test_is_stable_match_rejects_zero_length_intervals():
    assert is_stable_match(0.0, 10.0, 0.2) is False
    assert is_stable_match(10.0, 11.0, 0.2) is True


def test_get_stable_dyad_flags_detects_repeating_pattern():
    flags = get_stable_dyad_flags([100.0, 200.0, 100.0, 200.0, 100.0], 0.1)

    assert flags == [True, True, True, False]


def test_build_dyad_records_and_rhythm_metrics_return_expected_values():
    records = build_dyad_records("demo.wav", [100.0, 200.0, 100.0], [True, False])
    metrics = calculate_rhythm_metrics([0.1, 0.2, 0.1], records)

    assert records == [
        {
            "File Name": "demo.wav",
            "Dyad Index": 1,
            "Interval 1 (ms)": 100.0,
            "Interval 2 (ms)": 200.0,
            "Cycle Duration [cd] (ms)": 300.0,
            "Short Interval [i_s] (ms)": 100.0,
            "Long Interval [i_l] (ms)": 200.0,
            "Rhythm Ratio [r_k]": 0.3333,
            "Stable Rhythm": True,
        },
        {
            "File Name": "demo.wav",
            "Dyad Index": 2,
            "Interval 1 (ms)": 200.0,
            "Interval 2 (ms)": 100.0,
            "Cycle Duration [cd] (ms)": 300.0,
            "Short Interval [i_s] (ms)": 100.0,
            "Long Interval [i_l] (ms)": 200.0,
            "Rhythm Ratio [r_k]": 0.6667,
            "Stable Rhythm": False,
        },
    ]
    assert metrics["Average Cycle Duration (ms)"] == pytest.approx(300.0)
    assert metrics["nPVI (Isochrony)"] == pytest.approx(66.68, abs=0.01)
    assert metrics["CV of Intervals"] == pytest.approx(0.353553, abs=1e-6)
    assert metrics["r_k Std Dev"] == pytest.approx(0.1667, abs=1e-4)
    assert metrics["r_k Entropy (Categorical Measure)"] > 0.0


def test_stable_subset_and_speech_metrics_cover_pause_handling():
    stable_metrics = calculate_stable_subset_metrics(
        [
            {
                "Rhythm Ratio [r_k]": 0.3333,
                "Interval 1 (ms)": 100.0,
                "Interval 2 (ms)": 200.0,
            }
        ]
    )
    speech_metrics = calculate_speech_rhythm_metrics([100.0, 120.0, 400.0, 140.0], pause_threshold_ms=250.0)

    assert stable_metrics["Stable Rhythm nPVI"] == pytest.approx(66.68, abs=0.01)
    assert stable_metrics["Stable Rhythm CV"] == pytest.approx(0.333333, abs=1e-6)
    assert stable_metrics["Stable Rhythm r_k Std Dev"] == pytest.approx(0.0)
    assert stable_metrics["Stable Rhythm Entropy"] == pytest.approx(0.0)

    assert speech_metrics == {
        "Speech Rate (onsets/sec)": pytest.approx(5.263, abs=0.001),
        "Mean IOI (ms)": pytest.approx(190.0),
        "Std IOI (ms)": pytest.approx(122.07, abs=0.01),
        "PVI-raw (ms)": pytest.approx(186.67, abs=0.01),
        "nPVI (%)": pytest.approx(74.06, abs=0.01),
        "VarcoIOI (%)": pytest.approx(64.25, abs=0.01),
        "Articulation Rate (onsets/sec)": pytest.approx(8.333, abs=0.001),
        "Pause Count": 1,
        "Mean Pause Duration (ms)": pytest.approx(400.0),
        "Phonation Time Ratio": pytest.approx(0.4737, abs=0.0001),
    }