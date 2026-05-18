"""Tests for shared onset metadata helpers."""

import json

from scripts.onset_metadata import (
    build_file_demographics_rows,
    load_user_metadata,
    merge_user_metadata_into_summary_rows,
)


def test_load_user_metadata_extracts_per_file_and_general_defaults(tmp_path):
    settings_path = tmp_path / "per_file_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "__general_metadata__": {
                    "Group": "A",
                    "Species": "Chimpanzee",
                    "IgnoreBlank": "   ",
                    "IgnoreNone": None,
                },
                "demo.wav": {
                    "metadata": {
                        "Latitude": 1.23,
                        "Habitat": "Forest",
                    }
                },
                "skip.wav": {"metadata": {}},
                "not_a_dict": "ignore me",
            }
        ),
        encoding="utf-8",
    )

    per_file_metadata, general_metadata = load_user_metadata(str(settings_path))

    assert per_file_metadata == {
        "demo.wav": {
            "Latitude": 1.23,
            "Habitat": "Forest",
        }
    }
    assert general_metadata == {
        "Group": "A",
        "Species": "Chimpanzee",
    }


def test_merge_user_metadata_into_summary_rows_preserves_existing_values():
    summary_rows = [
        {"File Name": "demo.wav", "Species": "Measured"},
        {"File Name": "other.wav"},
    ]

    metadata_fields = merge_user_metadata_into_summary_rows(
        summary_rows,
        {
            "demo.wav": {"Species": "Override", "Habitat": "Forest"},
        },
        {"Group": "A", "Habitat": "General"},
    )

    assert metadata_fields == ["Species", "Habitat", "Group"]
    assert summary_rows[0]["Species"] == "Measured"
    assert summary_rows[0]["Habitat"] == "Forest"
    assert summary_rows[0]["Group"] == "A"
    assert summary_rows[1]["Species"] == ""
    assert summary_rows[1]["Habitat"] == "General"
    assert summary_rows[1]["Group"] == "A"


def test_build_file_demographics_rows_uses_per_file_then_general_then_na():
    demographics_rows = build_file_demographics_rows(
        [
            {"File Name": "demo.wav"},
            {"File Name": "other.wav"},
        ],
        {
            "demo.wav": {
                "Species": "Chimpanzee",
                "Latitude": 1.23,
                "Habitat": "Forest",
            }
        },
        {
            "Group": "A",
            "Species": "Bonobo",
            "Tempo_BPM": 90,
        },
    )

    assert demographics_rows[0]["File Name"] == "demo.wav"
    assert demographics_rows[0]["Group"] == "A"
    assert demographics_rows[0]["Species"] == "Chimpanzee"
    assert demographics_rows[0]["Latitude"] == 1.23
    assert demographics_rows[0]["Tempo_BPM"] == 90
    assert demographics_rows[0]["Habitat"] == "Forest"

    assert demographics_rows[1]["File Name"] == "other.wav"
    assert demographics_rows[1]["Group"] == "A"
    assert demographics_rows[1]["Species"] == "Bonobo"
    assert demographics_rows[1]["Habitat"] == "NA"
    assert demographics_rows[1]["BodyMass_kg"] == "NA"