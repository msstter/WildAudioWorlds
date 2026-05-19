"""Shared DataManager for graph-asset publication and manifest ownership."""

from __future__ import annotations

import json
import shutil
import wave
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .audio_asset_store import GraphProjectPaths, build_project_paths


DATA_MANAGER_SCHEMA_VERSION = "0.1"
DATA_MANAGER_NAME = "wild_audio_worlds.data.DataManager"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return deepcopy(value) if isinstance(value, list) else []


def _text_or_empty(value: Any) -> str:
    return str(value or "").strip()


def _coerce_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


def _slugify(value: str) -> str:
    slug = []
    for char in value.lower():
        if char.isalnum():
            slug.append(char)
        else:
            slug.append("-")
    cleaned = "".join(slug).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "audio"


def _write_json_atomic(destination_path: Path, payload: dict[str, Any]) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _build_temp_output_path(destination_path)
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    temp_path.replace(destination_path)


def _build_temp_output_path(destination_path: Path) -> Path:
    if destination_path.suffix:
        return destination_path.with_name(f"{destination_path.stem}.tmp{destination_path.suffix}")
    return destination_path.with_name(f"{destination_path.name}.tmp")


def _write_wav_pcm16_atomic(destination_path: Path, audio_data: Any, sample_rate: Any) -> None:
    audio = np.asarray(audio_data, dtype=np.float32)
    if audio.ndim != 1:
        audio = np.reshape(audio, (-1,))
    clipped = np.clip(audio, -1.0, 1.0)
    pcm16 = np.asarray(np.round(clipped * 32767.0), dtype=np.int16)

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _build_temp_output_path(destination_path)
    with wave.open(str(temp_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(max(1, _coerce_int(sample_rate, 22050)))
        wav_file.writeframes(pcm16.tobytes())
    temp_path.replace(destination_path)


class DataManager:
    def __init__(self, project_root: str | Path):
        self.paths: GraphProjectPaths = build_project_paths(project_root)
        self.project_root = Path(self.paths["project_root"]).resolve()
        self.manifest_path = Path(self.paths["manifest_path"]).resolve()
        self.public_assets_dir = Path(self.paths["public_assets_dir"]).resolve()
        self.exports_dir = Path(self.paths["exports_dir"]).resolve()
        self.backend_call_exports_dir = (self.exports_dir / "backend_calls").resolve()

    @staticmethod
    def resolve_project_root_from_manifest_path(manifest_path: str | Path) -> Path:
        path = Path(manifest_path).resolve()
        if len(path.parents) < 3:
            raise ValueError(f"Unable to resolve project root from manifest path: {path}")
        return path.parents[2]

    def load_manifest_payload(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {
                "schemaVersion": DATA_MANAGER_SCHEMA_VERSION,
                "manifestRevision": 0,
                "publishedAt": "",
                "managedBy": DATA_MANAGER_NAME,
                "assets": [],
            }

        with self.manifest_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if not isinstance(loaded, dict):
            return {
                "schemaVersion": DATA_MANAGER_SCHEMA_VERSION,
                "manifestRevision": 0,
                "publishedAt": "",
                "managedBy": DATA_MANAGER_NAME,
                "assets": [],
            }

        return {
            "schemaVersion": _text_or_empty(loaded.get("schemaVersion")) or DATA_MANAGER_SCHEMA_VERSION,
            "manifestRevision": _coerce_int(loaded.get("manifestRevision"), 0),
            "publishedAt": _text_or_empty(loaded.get("publishedAt")),
            "managedBy": _text_or_empty(loaded.get("managedBy")) or DATA_MANAGER_NAME,
            "assets": _list_or_empty(loaded.get("assets")),
        }

    def load_manifest_entries(self) -> list[dict[str, Any]]:
        return [
            _mapping_or_empty(entry)
            for entry in self.load_manifest_payload().get("assets", [])
            if isinstance(entry, dict)
        ]

    def _next_asset_revision_id(self, asset_id: str) -> str:
        current_entries = self.load_manifest_entries()
        current_entry = next(
            (
                entry
                for entry in current_entries
                if _text_or_empty(entry.get("id")) == asset_id or _text_or_empty(entry.get("assetId")) == asset_id
            ),
            {},
        )
        previous_revision_id = _text_or_empty(current_entry.get("revisionId"))
        previous_revision_number = 0
        if previous_revision_id.startswith("rev-"):
            previous_revision_number = _coerce_int(previous_revision_id[4:], 0)
        return f"rev-{previous_revision_number + 1:04d}"

    def save_manifest_entries(
        self,
        manifest_entries: list[dict[str, Any]],
        *,
        expected_manifest_revision: int | None = None,
    ) -> dict[str, Any]:
        current_payload = self.load_manifest_payload()
        current_revision = _coerce_int(current_payload.get("manifestRevision"), 0)
        if expected_manifest_revision is not None and current_revision != int(expected_manifest_revision):
            raise ValueError(
                f"Manifest revision mismatch: expected {expected_manifest_revision}, current {current_revision}."
            )

        next_payload = {
            "schemaVersion": DATA_MANAGER_SCHEMA_VERSION,
            "manifestRevision": current_revision + 1,
            "publishedAt": _iso_now(),
            "managedBy": DATA_MANAGER_NAME,
            "assets": [
                _mapping_or_empty(entry)
                for entry in manifest_entries
                if isinstance(entry, dict)
            ],
        }
        _write_json_atomic(self.manifest_path, next_payload)
        return next_payload

    def relative_to_project_root(self, path_value: str | Path) -> str:
        path_obj = Path(path_value).resolve()
        try:
            return str(path_obj.relative_to(self.project_root))
        except ValueError:
            return str(path_obj)

    def build_backend_call_export_path(
        self,
        label: str,
        *,
        extension: str,
        analysis_type: str = "",
        request_id: str = "",
    ) -> Path:
        stem_parts = [_slugify(label)]
        if analysis_type:
            stem_parts.append(_slugify(analysis_type))
        if request_id:
            stem_parts.append(_slugify(request_id))
        file_name = f"{'_'.join(part for part in stem_parts if part)}{extension}"
        export_path = self.backend_call_exports_dir / file_name
        export_path.parent.mkdir(parents=True, exist_ok=True)
        return export_path

    def publish_backend_call_json_export(
        self,
        payload: dict[str, Any],
        *,
        label: str,
        analysis_type: str,
        request_id: str,
    ) -> Path:
        export_path = self.build_backend_call_export_path(
            label,
            extension=".json",
            analysis_type=analysis_type,
            request_id=request_id,
        )
        _write_json_atomic(export_path, _mapping_or_empty(payload))
        return export_path

    def publish_backend_call_wav_export(
        self,
        audio_data: Any,
        *,
        sample_rate: Any,
        label: str,
        analysis_type: str,
        request_id: str,
    ) -> Path:
        export_path = self.build_backend_call_export_path(
            label,
            extension=".wav",
            analysis_type=analysis_type,
            request_id=request_id,
        )
        _write_wav_pcm16_atomic(export_path, audio_data, sample_rate)
        return export_path

    @staticmethod
    def write_workbook_sheets(output_path: str | Path, workbook_sheets: dict[str, pd.DataFrame]) -> None:
        destination_path = Path(output_path)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = _build_temp_output_path(destination_path)
        with pd.ExcelWriter(temp_path, engine="openpyxl") as writer:
            for sheet_name, dataframe in workbook_sheets.items():
                dataframe.to_excel(writer, sheet_name=sheet_name, index=False)
        temp_path.replace(destination_path)

    def upsert_manifest_entry(
        self,
        manifest_entry: dict[str, Any],
        *,
        expected_manifest_revision: int | None = None,
    ) -> dict[str, Any]:
        normalized_entry = _mapping_or_empty(manifest_entry)
        asset_id = _text_or_empty(normalized_entry.get("id")) or _text_or_empty(normalized_entry.get("assetId"))
        if not asset_id:
            raise ValueError("Manifest entry is missing asset identity.")

        manifest_entries = [
            entry
            for entry in self.load_manifest_entries()
            if _text_or_empty(entry.get("id")) != asset_id and _text_or_empty(entry.get("assetId")) != asset_id
        ]
        manifest_entries.append(normalized_entry)
        return self.save_manifest_entries(
            manifest_entries,
            expected_manifest_revision=expected_manifest_revision,
        )

    def publish_graph_asset_artifacts(
        self,
        *,
        source_audio_path: str | Path,
        display_name: str,
        fft_export_matrix: Any,
        fft_header: str,
        fft_file_name: str,
        terrain_envelope: dict[str, Any],
        terrain_file_name: str,
        mfcc_export_matrix: Any | None = None,
        mfcc_header: str = "",
        mfcc_file_name: str | None = None,
        manifest_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        audio_path = Path(source_audio_path).resolve()
        asset_id = _slugify(audio_path.stem + audio_path.suffix)
        revision_id = self._next_asset_revision_id(asset_id)
        public_revision_dir = self.public_assets_dir / asset_id / revision_id
        export_revision_dir = self.exports_dir / asset_id / revision_id
        public_revision_dir.mkdir(parents=True, exist_ok=True)
        export_revision_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(audio_path, public_revision_dir / audio_path.name)

        np.savetxt(
            public_revision_dir / fft_file_name,
            fft_export_matrix,
            delimiter=",",
            header=fft_header,
            comments="",
        )
        np.savetxt(
            export_revision_dir / fft_file_name,
            fft_export_matrix,
            delimiter=",",
            header=fft_header,
            comments="",
        )
        _write_json_atomic(public_revision_dir / terrain_file_name, _mapping_or_empty(terrain_envelope))
        _write_json_atomic(export_revision_dir / terrain_file_name, _mapping_or_empty(terrain_envelope))

        if mfcc_export_matrix is not None and mfcc_file_name:
            np.savetxt(
                public_revision_dir / mfcc_file_name,
                mfcc_export_matrix,
                delimiter=",",
                header=mfcc_header,
                comments="",
            )
            np.savetxt(
                export_revision_dir / mfcc_file_name,
                mfcc_export_matrix,
                delimiter=",",
                header=mfcc_header,
                comments="",
            )

        published_at = _iso_now()
        manifest_entry = {
            "id": asset_id,
            "assetId": asset_id,
            "label": _text_or_empty(display_name) or audio_path.stem,
            "revisionId": revision_id,
            "publishedAt": published_at,
            "audioUrl": f"./audio_assets/{asset_id}/{revision_id}/{audio_path.name}",
            "mfccCsvUrl": f"./audio_assets/{asset_id}/{revision_id}/{mfcc_file_name}" if mfcc_export_matrix is not None and mfcc_file_name else None,
            "fftCsvUrl": f"./audio_assets/{asset_id}/{revision_id}/{fft_file_name}",
            "terrainEnvelopeUrl": f"./audio_assets/{asset_id}/{revision_id}/{terrain_file_name}",
            **_mapping_or_empty(manifest_fields),
        }
        manifest_entry["hasMfccData"] = bool(mfcc_export_matrix is not None and mfcc_file_name)
        return manifest_entry


__all__ = [
    "DATA_MANAGER_NAME",
    "DATA_MANAGER_SCHEMA_VERSION",
    "DataManager",
]