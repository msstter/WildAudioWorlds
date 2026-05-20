import base64
import json
import sys
import traceback
from pathlib import Path

from shared_graph_paths import resolve_graph_project_root

try:
    from main import DataManager, build_project_paths, process_audio_file, upsert_manifest_entry
except ModuleNotFoundError:
    from backend.main import DataManager, build_project_paths, process_audio_file, upsert_manifest_entry


def _read_payload():
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("No JSON payload received for recorded audio import.")

    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Recorded audio import payload must be a JSON object.")
    return payload


def _resolve_audio_path(payload: dict, data_manager: DataManager) -> Path:
    audio_buffer_base64 = str(payload.get("audioBufferBase64") or "").strip()
    if audio_buffer_base64:
        try:
            audio_bytes = base64.b64decode(audio_buffer_base64, validate=True)
        except Exception as exc:
            raise ValueError("Recorded audio import payload included invalid audioBufferBase64.") from exc
        if not audio_bytes:
            raise ValueError("Recorded audio import payload included an empty audio buffer.")

        stem_hint = str(payload.get("fileStem") or payload.get("assetLabel") or "recorded-audio").strip()
        extension = str(payload.get("fileExtension") or ".wav").strip() or ".wav"
        return data_manager.publish_source_audio_input(
            audio_bytes,
            stem_hint=stem_hint,
            extension=extension,
        )

    audio_path = Path(str(payload.get("audioPath") or "")).expanduser().resolve()
    if not audio_path.exists() or not audio_path.is_file():
        raise FileNotFoundError(f"Recorded audio file was not found: {audio_path}")
    return audio_path


def import_recorded_audio(payload: dict) -> dict:
    project_root = resolve_graph_project_root(payload.get("projectRoot"), anchor_file=__file__)
    data_manager = DataManager(project_root)
    audio_path = _resolve_audio_path(payload, data_manager)

    include_mfcc = payload.get("includeMfcc") is not False
    asset_label = str(payload.get("assetLabel") or "").strip() or audio_path.stem
    paths = build_project_paths(project_root)

    manifest_entry = process_audio_file(
        audio_path,
        include_mfcc=include_mfcc,
        display_name=asset_label,
        project_root=project_root,
        logger=None,
    )
    upsert_manifest_entry(paths["manifest_path"], manifest_entry)

    return {
        "ok": True,
        "asset": manifest_entry,
        "promotedAsset": manifest_entry,
        "savedAudioPath": str(audio_path),
        "manifestPath": paths["manifest_path"],
    }


def main():
    payload = _read_payload()
    print(json.dumps(import_recorded_audio(payload)), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({
            "ok": False,
            "error": str(error),
            "traceback": traceback.format_exc(),
        }), flush=True)
        sys.exit(1)