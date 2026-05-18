# New Personal Setup

Concise steps for pulling this private repo onto a MacBook and confirming it runs.

## 1. One-time Mac setup

Install Apple's command-line tools:

```bash
xcode-select --install
```

Install Conda.

Recommended:
- Miniforge: https://github.com/conda-forge/miniforge

After Conda finishes installing, close Terminal and open a new one.

## 2. Make sure GitHub access works

This repo is private, so your GitHub account must already have access.

HTTPS clone:

```bash
git clone https://github.com/msstter/AudioOnsetFinder.git
```

If GitHub rejects your password, use either:
- a Personal Access Token instead of a password, or
- SSH if your Mac already has a GitHub SSH key configured.

## 3. Clone the repo and enter it

```bash
cd ~/Documents
git clone https://github.com/msstter/AudioOnsetFinder.git
cd AudioOnsetFinder
```

## 4. Create the environment

For the full local app environment:

```bash
conda env create -f environment.yml
conda activate rhythm_env
```

If you only want the lean smoke-test environment:

```bash
conda env create -f environment-ci.yml
conda activate rhythm_ci
```

## 5. Run a quick validation

Full environment:

```bash
bash scripts/refactor_guardrails.sh doctor
bash scripts/refactor_guardrails.sh smoke
```

If you created the CI environment instead, run:

```bash
conda run -n rhythm_ci bash scripts/refactor_guardrails.sh smoke
```

## 6. Launch the GUI

Recommended:

```bash
bash scripts/refactor_guardrails.sh launch
```

Direct launch also works:

```bash
conda activate rhythm_env
python GUI/pipeline_gui.py
```

## 7. Mac-specific notes

- If `conda` is not found, restart Terminal or source your shell profile.
- If the `.app` launcher is blocked by Gatekeeper, right-click it and choose `Open`, or launch from Terminal instead.
- If `environment.yml` changes later, update with:

```bash
conda activate rhythm_env
conda env update -f environment.yml --prune
```

## 8. Pull later updates

```bash
cd ~/Documents/AudioOnsetFinder
git pull --ff-only
conda activate rhythm_env
conda env update -f environment.yml --prune
```