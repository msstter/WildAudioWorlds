# MacBook Personal Setup

This is the shortest path to pull this private repo onto a MacBook and run it from source.

## 1. Install the basics

Install these first:

1. Xcode Command Line Tools
2. Git
3. Node.js 24
4. Miniforge or Miniconda

Useful checks after install:

```bash
xcode-select --install
git --version
node -v
npm -v
conda --version
```

Expected frontend runtime baseline:

- Node `24.x`
- npm `11.x`

## 2. Clone the private repo

```bash
git clone https://github.com/msstter/3DAudioGraphs.git
cd 3DAudioGraphs
```

If GitHub prompts for authentication, sign in with the GitHub account that has access to the private repo.

## 3. Install the frontend

```bash
cd frontend
npm install
cd ..
```

## 4. Create the backend environment

```bash
conda create -p ./.conda-backend -c conda-forge python=3.11 librosa umap-learn scikit-learn numpy websockets pandas openpyxl ffmpeg -y
conda activate ./.conda-backend
```

Quick backend check:

```bash
python -c "import librosa, numpy, pandas, openpyxl, sklearn, umap, soundfile; print('Backend environment OK')"
```

## 5. Launch the app

From the repo root:

```bash
export BACKEND_PYTHON="$(pwd)/.conda-backend/bin/python"
cd frontend
npm run electron:dev
```

## 6. Important asset note

This repo intentionally ships with an empty bundled manifest, so a fresh clone will open without demo audio already loaded.

That is expected.

If you want actual audio assets to test with, use one of these:

1. Put your own audio files into `data/sample_audio` and run `python ./backend/main.py` from the repo root.
2. Open the app and use `Mode_Audio/Data -> Choose Asset Folder`, then select a folder that contains `audio_assets_manifest.json`.
3. Use the recorded import flow inside the app.

## 7. Quick sanity check

You are in good shape if:

1. The Electron window opens.
2. The app does not complain about a missing Python backend.
3. After generating or selecting assets, the audio list populates.

## 8. Optional packaged Mac build

If you want to test a packaged app instead of only dev mode:

```bash
cd frontend
npm run electron:build:mac:arm
```

Use `npm run electron:build:mac:intel` instead if that MacBook is Intel.