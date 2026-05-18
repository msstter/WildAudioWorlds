# Getting Started — Setup Guide

How to set up and run the Bioacoustics Rhythm Pipeline on a new machine.

---

## What You Need

The pipeline is a Python application. To run it, the recipient needs:

1. **The project folder** — the entire `BioacousticsProject/` directory
2. **Conda** (Anaconda or Miniconda) — a Python environment manager
3. **The `rhythm_env` conda environment** — created from the included `environment.yml`

That's it. Everything else (libraries, GUI, launchers) is included in the folder.

---

## Step-by-Step Setup

### 1. Install Conda (if not already installed)

Download and install one of:
- **Miniconda** (lightweight, recommended): https://docs.conda.io/en/latest/miniconda.html
- **Anaconda** (full distribution): https://www.anaconda.com/download

Follow the installer prompts and accept the defaults.

### 2. Copy the project folder

Copy the entire `BioacousticsProject/` folder to the new machine. It can live anywhere — the Desktop, Documents, or any other location. The internal paths are all relative.

### 3. Create the conda environment

Open a terminal (macOS/Linux) or Anaconda Prompt (Windows) and run:

```bash
cd /path/to/BioacousticsProject
conda env create -f environment.yml
```

This reads `environment.yml` and installs Python 3.11 plus all required packages into a conda environment called `rhythm_env`. It may take a few minutes.

### 4. Launch the GUI

For day-to-day refactor work, the project includes small OS-native wrappers so you do not have to remember the working launch and validation commands:

**Windows PowerShell:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/refactor_guardrails.ps1 launch
powershell -ExecutionPolicy Bypass -File scripts/refactor_guardrails.ps1 smoke
powershell -ExecutionPolicy Bypass -File scripts/refactor_guardrails.ps1 wider
```

**macOS / Linux:**

```bash
bash scripts/refactor_guardrails.sh launch
bash scripts/refactor_guardrails.sh smoke
bash scripts/refactor_guardrails.sh wider
```

**macOS:**
- Double-click `GUI/Bioacoustics Rhythm Pipeline.app`
- Or from a terminal: `conda activate rhythm_env && python GUI/pipeline_gui.py`

**Windows:**
- Double-click `GUI/launch_gui.bat`
- Or from Anaconda Prompt: `conda activate rhythm_env` then `python GUI\pipeline_gui.py`

**Linux:**
- Run `bash GUI/install_linux_shortcut.sh` to create a desktop shortcut
- Or from a terminal: `conda activate rhythm_env && python GUI/pipeline_gui.py`

The guardrail helpers auto-detect common Conda locations on macOS, Linux, and Windows. If your environment lives somewhere unusual, set `BIOACOUSTICS_PYTHON` to the interpreter you want them to use.

The GUI will open and auto-detect the project folder. All default paths (input audio, output folders) are set relative to wherever the project folder lives.

---

## Quick Verification

After launching the GUI:

1. The four pipeline steps should appear in the left sidebar
2. Place some audio files (`.wav`, `.mp3`, `.flac`, or `.ogg`) in the `audioFiles/` folder
3. Click **Run Pipeline** — the terminal panel at the bottom will show progress
4. Output appears in `audioFiles_muted_clean/`, `Cross_Species_Rhythm_Data.xlsx`, `Raster_Plots/`, and `Histogram_Plots/`

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `conda: command not found` | Conda isn't on your PATH. Restart the terminal, or use the full path (e.g. `~/miniconda3/bin/conda`) |
| `environment.yml` fails | Run `conda update conda` first, then retry |
| `.app` won't open (macOS) | Right-click → Open (bypasses Gatekeeper). Or run from terminal |
| `.bat` closes immediately (Windows) | Open Anaconda Prompt, `cd` to the project folder, and run `python GUI\pipeline_gui.py` to see the error |
| Missing package error at runtime | Run `conda activate rhythm_env && pip install <package_name>` |
| GUI opens but paths are wrong | The GUI defaults are relative — just update the input/output folder paths in each panel to point to your local folders |

---

## Updating the Environment

If the project adds new dependencies in the future:

```bash
conda activate rhythm_env
conda env update -f environment.yml --prune
```

---

## What the Launchers Do

The `.app` (macOS) and `.bat` (Windows) launchers are simple scripts that:
1. Find the `rhythm_env` conda Python on your machine
2. `cd` into the project folder
3. Run `GUI/pipeline_gui.py`

They search several common Anaconda/Miniconda install locations automatically. If conda is installed in an unusual location, just run the GUI manually from a terminal as shown above.
