"""Helpers for loading and exporting user-supplied onset metadata."""

from __future__ import annotations

import json
import os


DEMOGRAPHIC_FIELDS = [
    "Group",
    "Species",
    "Latitude",
    "Longitude",
    "Modality",
    "Function",
    "Tempo_BPM",
    "BodyMass_kg",
]


def load_user_metadata(per_file_settings_path: str | None) -> tuple[dict, dict]:
    """Load per-file and general metadata defaults from the per-file settings JSON."""
    per_file_metadata: dict = {}
    general_metadata: dict = {}

    if not per_file_settings_path or not os.path.isfile(per_file_settings_path):
        return per_file_metadata, general_metadata

    try:
        with open(per_file_settings_path, encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            general_block = data.get("__general_metadata__")
            if isinstance(general_block, dict):
                general_metadata = {
                    key: value
                    for key, value in general_block.items()
                    if value is not None and str(value).strip() != ""
                }
            for filename, entry in data.items():
                if filename.startswith("__") or not isinstance(entry, dict):
                    continue
                metadata = entry.get("metadata")
                if isinstance(metadata, dict) and metadata:
                    per_file_metadata[filename] = metadata
    except Exception as error:
        print(f"WARNING: could not load per-file metadata: {error}")

    return per_file_metadata, general_metadata


def merge_user_metadata_into_summary_rows(
    file_summary_data: list[dict],
    per_file_metadata: dict,
    general_metadata: dict,
) -> list[str]:
    """Merge user-supplied metadata into file-summary rows without overwriting measurements."""
    if not (per_file_metadata or general_metadata):
        return []

    all_metadata_fields: list[str] = []
    seen_fields: set[str] = set()

    for row in file_summary_data:
        filename = row.get("File Name", "")
        metadata = per_file_metadata.get(filename, {})

        for key, value in metadata.items():
            if key not in row:
                row[key] = value
            if key not in seen_fields:
                seen_fields.add(key)
                all_metadata_fields.append(key)

        for key, value in general_metadata.items():
            if key not in row:
                row[key] = value
            if key not in seen_fields:
                seen_fields.add(key)
                all_metadata_fields.append(key)

    for row in file_summary_data:
        for key in all_metadata_fields:
            row.setdefault(key, "")

    return all_metadata_fields


def build_file_demographics_rows(
    file_summary_data: list[dict],
    per_file_metadata: dict,
    general_metadata: dict,
    demographic_fields: list[str] | None = None,
) -> list[dict]:
    """Build rows for the dedicated File Demographics worksheet."""
    if not (per_file_metadata or general_metadata):
        return []

    base_fields = list(demographic_fields or DEMOGRAPHIC_FIELDS)
    extra_fields: list[str] = []
    known_fields = set(base_fields)

    for metadata in list(per_file_metadata.values()) + [general_metadata]:
        if not isinstance(metadata, dict):
            continue
        for key in metadata.keys():
            if key not in known_fields and key not in extra_fields:
                extra_fields.append(key)

    all_fields = base_fields + extra_fields
    demographics_rows: list[dict] = []

    for row in file_summary_data:
        filename = row.get("File Name", "")
        metadata = per_file_metadata.get(filename, {})
        demographics_row = {"File Name": filename}

        for key in all_fields:
            value = metadata.get(key)
            if value in (None, ""):
                value = general_metadata.get(key, "")
            if value in (None, ""):
                value = "NA"
            demographics_row[key] = value

        demographics_rows.append(demographics_row)

    return demographics_rows


__all__ = [
    "DEMOGRAPHIC_FIELDS",
    "build_file_demographics_rows",
    "load_user_metadata",
    "merge_user_metadata_into_summary_rows",
]