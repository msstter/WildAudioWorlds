import json
import sys
import traceback
from pathlib import Path

from shared_graph_paths import resolve_graph_project_root

try:
    from main import build_project_paths, process_audio_file, upsert_manifest_entry
except ModuleNotFoundError:
    from backend.main import build_project_paths, process_audio_file, upsert_manifest_entry


def _read_payload() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("No JSON payload received for graph asset processing.")

    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Graph asset processing payload must be a JSON object.")
    return payload


def _resolve_audio_path(payload: dict) -> Path:
    audio_path = Path(str(payload.get("audioPath") or "")).expanduser().resolve()
    if not audio_path.exists() or not audio_path.is_file():
        raise FileNotFoundError(f"Graph asset processing source audio was not found: {audio_path}")
    return audio_path


def process_graph_asset(payload: dict) -> dict:
    project_root = resolve_graph_project_root(payload.get("projectRoot"), anchor_file=__file__)
    audio_path = _resolve_audio_path(payload)
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
        "processedAudioPath": str(audio_path),
        "manifestPath": paths["manifest_path"],
    }


def main() -> None:
    payload = _read_payload()
    print(json.dumps(process_graph_asset(payload)), flush=True)


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