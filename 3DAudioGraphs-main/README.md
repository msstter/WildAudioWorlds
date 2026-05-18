# 3DAudioGraph

This repository intentionally ships without bundled demo audio assets.

The tracked manifest at `frontend/public/audio_assets_manifest.json` is expected to stay empty by default, so a fresh clone will start without a bundled audio selection.

To work with audio locally, use the app's asset-folder chooser or import recorded audio from your own local files.

Frontend development and packaging are validated against Node.js 24.

Local working data under `data/sample_audio/` and generated exports under `data/exports/` are intentionally excluded from Git.