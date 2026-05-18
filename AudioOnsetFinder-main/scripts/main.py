"""Main pipeline runner for the Bioacoustics Rhythm Analysis project.

This script runs each stage of the pipeline in the correct order:

  1. audio_editor.py       — Pre-process: mute background noise (preserves timeline)
  2. onset_finder.py       — Core: detect onsets and compute rhythm metrics
     OR thebeat_extractor.py (alternative engine using the thebeat package)
  3. flower_raster_plots.py — Visualise: generate raster plots of dyadic events
  4. histogram_generator.py — Visualise: generate r_k distribution histograms

Usage:
    python scripts/main.py

Edit the CONFIGURATION section below to control which steps run and what
arguments are passed to each script. Each step can be toggled on/off
independently — for example, set RUN_MUTER = False if you have already
muted the audio and only want to re-run extraction and plotting.
"""

import os # directory listing and file path joining
import subprocess  # run each step script as a subprocess with command list
import sys  # access Python executable path and handle script exit status


def _configure_utf8_console() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_configure_utf8_console()

# ==========================================
# CONFIGURATION — Edit these to customise the pipeline run
# ==========================================

# Base directory of the project (auto-detected from this script's location).
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")

# ------------------------------------------------------------------
# STEP 0 (optional): YouTube Download. Downloads audio from a URL.
# ------------------------------------------------------------------
# Set a YouTube URL here to download audio before processing.
# Leave empty ("") to skip.
YOUTUBE_URL = ""

# ------------------------------------------------------------------
# STEP 1: Audio Editor (pre-processing). See audio_editor.py for details.
# ------------------------------------------------------------------
# Set to True to run the muter before extraction. Set to False if you
# have already muted the audio and just want to re-run later steps.
RUN_MUTER = True

# The folder of RAW audio files to process. Change this when switching
# between datasets (e.g. "audioFiles_birds", "audioFiles_chimpanzee").
#
# IMPORTANT: The muter outputs to <input_folder>_muted_clean/. If you
# change this path, you MUST also update the `audio_folder` variable
# at the top of onset_finder.py to match the new output folder.
# For example:
#   MUTER_INPUT_FOLDER → ".../audioFiles_birds"
#   onset_finder.py audio_folder → ".../audioFiles_birds_muted_clean"
MUTER_INPUT_FOLDER = os.path.join(PROJECT_DIR, "audioFiles")

# Explicit output folder for the muter. When set (non-empty), passed as
# --output-folder to audio_editor.py, overriding the auto-derived name.
# Leave empty to auto-derive as <input_folder>_muted_clean.
MUTER_OUTPUT_FOLDER = ""

# How far below the peak volume (in dB) is considered "noise".
# Lower = more aggressive (removes more). Higher = more permissive.
#   20-25  → clean studio recordings with minimal background
#   30     → general purpose (good default)
#   35-40  → noisy field recordings where target calls are faint
MUTER_DB_THRESHOLD = 30

# High-pass filter cutoff in Hz. Removes low-frequency environmental
# rumble (wind, traffic, generators) BEFORE the dB-based muting step.
# Set to 0 to disable.
#   0    → disabled
#   80   → percussion / primate drumming (keep low-end content)
#   200  → general purpose
#   500  → birdsong / high-frequency calls
MUTER_HIGHPASS_HZ = 200

# Crossfade duration (ms) applied at each mute/unmute boundary.
# Prevents the hard silence→signal edge from being falsely detected
# as an onset by the onset finder.
#   0   → disabled (not recommended)
#   5   → good default
#   10  → extra-safe for very sensitive onset detectors
MUTER_FADE_MS = 5.0

# Adaptive per-file threshold. When True, the muter estimates each file's
# noise floor and derives a dynamic top_db instead of using the fixed
# MUTER_DB_THRESHOLD for all files. Recommended for mixed-quality datasets.
MUTER_AUTO_THRESHOLD = True

# How many dB above the estimated noise floor to set the muting threshold.
# Only used when MUTER_AUTO_THRESHOLD is True. Recommended: 4-10.
MUTER_NOISE_MARGIN_DB = 6.0

# Save a JSON noise profile for each file alongside the cleaned output.
# Only used when MUTER_AUTO_THRESHOLD is True.
MUTER_SAVE_NOISE_PROFILE = True

# Spectral denoising: suppress spectrally persistent background sounds
# (cicadas, hiss, generator hum) before amplitude muting. Recommended
# for noisy field recordings with constant background sources.
MUTER_SPECTRAL_DENOISE = True

# How aggressively to suppress persistent noise. 1.0 = standard removal,
# 1.5 = moderate (good default for cicadas), 2.0 = very aggressive.
MUTER_DENOISE_STRENGTH = 1.5

# Harmonic-Percussive Source Separation (HPSS). Decomposes audio into a
# smooth harmonic track (bird calls, whale moans, wind) and a sharp
# percussive track (drumming, clicks, percussion). Useful when background
# noise is the same volume as the target signal — something dB muting
# alone cannot handle.
MUTER_HPSS_ENABLED = False

# Which HPSS component to keep for downstream onset extraction:
#   "harmonic"   → sustained tones (bird song, whale moans)
#   "percussive" → sharp transients (primate drumming, insect clicks)
#   "both"       → no separation, just export the component tracks
MUTER_HPSS_TARGET = "percussive"

# Separation softness. 1.0 = soft (components overlap), 2.0 = moderate
# (good default), 4.0 = hard split (cleaner but risks losing quiet signal).
MUTER_HPSS_MARGIN = 2.0

# ------------------------------------------------------------------
# STEP 2: Onset Finder (core analysis)
# ------------------------------------------------------------------
# Set to True to run the onset finder. Requires muted audio to
# already exist in the folder specified by the finder's
# `audio_folder` variable.
#
# EXTRACTOR_ENGINE controls which extraction script is used:
#   "standard" → onset_finder.py
#       Full-featured: onset clustering, stable-rhythm filtering, named
#       presets, spectrograms, Audacity labels, amplitude gate, high-pass
#       filter, and min inter-onset spacing. Produces a 3-sheet Excel
#       workbook (File Summaries, Dyadic Events, Stable Dyadic Events).
#       Configure its toggles directly inside onset_finder.py.
#
#   "thebeat" → thebeat_extractor.py
#       Lightweight alternative that delegates IOI calculation to the
#       thebeat package (an object-oriented sequence handler designed
#       for bioacoustics). Produces a 2-sheet Excel workbook (File
#       Summaries, Dyadic Events). Does not currently support onset
#       clustering, stable-rhythm filtering, spectrograms, or labels.
#       Requires: pip install thebeat
RUN_EXTRACTOR = True
EXTRACTOR_ENGINE = "standard"  # "standard" or "thebeat"

# ------------------------------------------------------------------
# STEP 3: Flower Raster Plots (visualisation).
# ------------------------------------------------------------------
# Set to True to generate raster plots from the extractor's Excel output.
# Requires Cross_Species_Rhythm_Data.xlsx to exist (produced by Step 2).
RUN_PLOT_GENERATOR = True

# ------------------------------------------------------------------
# STEP 4: Histogram Generator (visualisation)
# ------------------------------------------------------------------
# Set to True to generate r_k histograms from the extractor's Excel output.
# Requires Cross_Species_Rhythm_Data.xlsx to exist (produced by Step 2).
RUN_HISTOGRAM_GENERATOR = True

# ------------------------------------------------------------------
# STEP 5: nPVI Group Plot (visualisation)
# ------------------------------------------------------------------
# Set to True to generate nPVI-by-group raincloud plots from the
# extractor's Excel output. Inspired by Eleuteri et al. (2025).
# Requires Cross_Species_Rhythm_Data.xlsx to exist (produced by Step 2).
RUN_NPVI_GROUP_GENERATOR = True

# ------------------------------------------------------------------
# STEP 2b: Beat and Tempo (enrichment — runs after Onset Finder)
# ------------------------------------------------------------------
# Detects beat events with librosa.beat.beat_track and estimates
# time-varying tempo with librosa.beat.plp.  Writes beat times, global
# tempo estimate, and PLP pulse-curve peaks to a dedicated Excel file
# (data/AudioData_BeatTempo.xlsx).  Off by default.
RUN_BEAT_TEMPO = False

# ------------------------------------------------------------------
# STEP 6: Association Rule Learning (experimental)
# ------------------------------------------------------------------
# Set to True to run Apriori association-rule mining on the per-file
# rhythm metrics already produced by the Onset Finder.  Outputs CSV +
# plots into Association_Rules/.  Off by default.
RUN_ASSOC_RULE_LEARNING = False

# ------------------------------------------------------------------
# STEPS 8-17: Multi-species rhythmic-landscape analyses
# (see docs/plan_MultiSpeciesRhythmicLandscapeAnalyses.md)
# All default off; toggle individually or from the GUI.
# ------------------------------------------------------------------
RUN_RHYTHM_RATIOS = False            # A1
RUN_KS_TEST = False                  # A2
RUN_WILCOXON_ISOCHRONY = False       # A3
RUN_LAG_ONE_AUTOCORRELATION = False  # A4
RUN_TEMPO_RATIO_HEATMAP = False      # B1
RUN_RAINCLOUD_METRICS = False        # B2
RUN_PDFA = False                     # C1
RUN_MANTEL_TEST = False              # C2
RUN_GLMM_RHYTHM = False              # C3
RUN_PGLS = False                     # D1

# ------------------------------------------------------------------
# GUI CONFIG OVERRIDE — Read settings from pipeline_config.json if present.
# This allows the GUI to inject settings without editing this file.
# ------------------------------------------------------------------
_config_path = os.path.join(PROJECT_DIR, "pipeline_config.json")
if os.path.isfile(_config_path):
    import json as _json
    with open(_config_path) as _f:
        _cfg = _json.load(_f)
    # Muter settings
    _m = _cfg.get("muter", {})
    RUN_MUTER = _m.get("RUN_MUTER", RUN_MUTER)
    MUTER_INPUT_FOLDER = _m.get("MUTER_INPUT_FOLDER", MUTER_INPUT_FOLDER)
    MUTER_OUTPUT_FOLDER = _m.get("MUTER_OUTPUT_FOLDER", MUTER_OUTPUT_FOLDER)
    MUTER_SPECIFY_FILES = _m.get("MUTER_SPECIFY_FILES", False)
    MUTER_SELECTED_FILES = _m.get("MUTER_SELECTED_FILES", [])
    MUTER_DB_THRESHOLD = _m.get("MUTER_DB_THRESHOLD", MUTER_DB_THRESHOLD)
    MUTER_HIGHPASS_HZ = _m.get("MUTER_HIGHPASS_HZ", MUTER_HIGHPASS_HZ)
    MUTER_FADE_MS = _m.get("MUTER_FADE_MS", MUTER_FADE_MS)
    MUTER_AUTO_THRESHOLD = _m.get("MUTER_AUTO_THRESHOLD", MUTER_AUTO_THRESHOLD)
    MUTER_NOISE_MARGIN_DB = _m.get("MUTER_NOISE_MARGIN_DB", MUTER_NOISE_MARGIN_DB)
    MUTER_SAVE_NOISE_PROFILE = _m.get("MUTER_SAVE_NOISE_PROFILE", MUTER_SAVE_NOISE_PROFILE)
    MUTER_SPECTRAL_DENOISE = _m.get("MUTER_SPECTRAL_DENOISE", MUTER_SPECTRAL_DENOISE)
    MUTER_DENOISE_STRENGTH = _m.get("MUTER_DENOISE_STRENGTH", MUTER_DENOISE_STRENGTH)
    MUTER_HPSS_ENABLED = _m.get("MUTER_HPSS_ENABLED", MUTER_HPSS_ENABLED)
    MUTER_HPSS_TARGET = _m.get("MUTER_HPSS_TARGET", MUTER_HPSS_TARGET)
    MUTER_HPSS_MARGIN = _m.get("MUTER_HPSS_MARGIN", MUTER_HPSS_MARGIN)
    YOUTUBE_URL = _m.get("YOUTUBE_URL", YOUTUBE_URL)
    # Demucs settings
    MUTER_DEMUCS_ENABLED = _m.get("MUTER_DEMUCS_ENABLED", False)
    MUTER_DEMUCS_ONLY = _m.get("MUTER_DEMUCS_ONLY", False)
    MUTER_DEMUCS_MODEL = _m.get("MUTER_DEMUCS_MODEL", "htdemucs")
    MUTER_DEMUCS_TWO_STEMS = _m.get("MUTER_DEMUCS_TWO_STEMS", None)
    MUTER_DEMUCS_OTHER_METHOD = _m.get("MUTER_DEMUCS_OTHER_METHOD", "add")
    MUTER_DEMUCS_DEVICE = _m.get("MUTER_DEMUCS_DEVICE", "auto")
    MUTER_DEMUCS_SHIFTS = _m.get("MUTER_DEMUCS_SHIFTS", 1)
    MUTER_DEMUCS_OVERLAP = _m.get("MUTER_DEMUCS_OVERLAP", 0.25)
    MUTER_DEMUCS_SEGMENT = _m.get("MUTER_DEMUCS_SEGMENT", None)
    MUTER_DEMUCS_OUTPUT_FORMAT = _m.get("MUTER_DEMUCS_OUTPUT_FORMAT", "wav-int16")
    MUTER_DEMUCS_MP3_BITRATE = _m.get("MUTER_DEMUCS_MP3_BITRATE", 320)
    MUTER_DEMUCS_CLIP_MODE = _m.get("MUTER_DEMUCS_CLIP_MODE", "rescale")
    MUTER_DEMUCS_JOBS = _m.get("MUTER_DEMUCS_JOBS", 1)
    # Extractor settings
    _e = _cfg.get("extractor", {})
    RUN_EXTRACTOR = _e.get("RUN_EXTRACTOR", RUN_EXTRACTOR)
    EXTRACTOR_ENGINE = _e.get("EXTRACTOR_ENGINE", EXTRACTOR_ENGINE)
    EXTRACTOR_SPECIFY_FILES = _e.get("EXTRACTOR_SPECIFY_FILES", False)
    # Beat and Tempo settings
    _bt = _cfg.get("beat_tempo", {})
    RUN_BEAT_TEMPO = _bt.get("RUN_BEAT_TEMPO", RUN_BEAT_TEMPO)
    # Plot / histogram settings
    _p = _cfg.get("plot_generator", {})
    RUN_PLOT_GENERATOR = _p.get("RUN_PLOT_GENERATOR", RUN_PLOT_GENERATOR)
    _h = _cfg.get("histogram_generator", {})
    RUN_HISTOGRAM_GENERATOR = _h.get("RUN_HISTOGRAM_GENERATOR", RUN_HISTOGRAM_GENERATOR)
    _n = _cfg.get("npvi_group_generator", {})
    RUN_NPVI_GROUP_GENERATOR = _n.get("RUN_NPVI_GROUP_GENERATOR", RUN_NPVI_GROUP_GENERATOR)
    _a = _cfg.get("assoc_rule_learning", {})
    RUN_ASSOC_RULE_LEARNING = _a.get("RUN_ASSOC_RULE_LEARNING", RUN_ASSOC_RULE_LEARNING)
    # New multi-species analyses (Steps 8-17)
    for _key, _var in [("rhythm_ratios", "RUN_RHYTHM_RATIOS"),
                       ("ks_test", "RUN_KS_TEST"),
                       ("wilcoxon_isochrony", "RUN_WILCOXON_ISOCHRONY"),
                       ("lag_one_autocorrelation", "RUN_LAG_ONE_AUTOCORRELATION"),
                       ("tempo_ratio_heatmap", "RUN_TEMPO_RATIO_HEATMAP"),
                       ("raincloud_metrics", "RUN_RAINCLOUD_METRICS"),
                       ("pdfa", "RUN_PDFA"),
                       ("mantel_test", "RUN_MANTEL_TEST"),
                       ("glmm_rhythm", "RUN_GLMM_RHYTHM"),
                       ("pgls", "RUN_PGLS")]:
        _sec = _cfg.get(_key, {})
        if f"RUN_{_key.upper()}" in _sec:
            globals()[_var] = _sec[f"RUN_{_key.upper()}"]
        elif "enabled" in _sec:
            globals()[_var] = bool(_sec["enabled"])
    # Per-file settings (legacy — may still exist in config)
    _aa = _cfg.get("audio_analyzer", {})
    _PER_FILE_AUDIO_SETTINGS_PATH = _aa.get("per_file_settings_path", "")
    del _json, _f, _cfg, _m, _e, _bt, _p, _h, _n, _a, _aa
else:
    _PER_FILE_AUDIO_SETTINGS_PATH = ""
    MUTER_SPECIFY_FILES = False
    MUTER_SELECTED_FILES = []
    EXTRACTOR_SPECIFY_FILES = False
    EXTRACTOR_SELECTED_FILES = []
    MUTER_DEMUCS_ENABLED = False
    MUTER_DEMUCS_ONLY = False
    MUTER_DEMUCS_MODEL = "htdemucs"
    MUTER_DEMUCS_TWO_STEMS = None
    MUTER_DEMUCS_OTHER_METHOD = "add"
    MUTER_DEMUCS_DEVICE = "auto"
    MUTER_DEMUCS_SHIFTS = 1
    MUTER_DEMUCS_OVERLAP = 0.25
    MUTER_DEMUCS_SEGMENT = None
    MUTER_DEMUCS_OUTPUT_FORMAT = "wav-int16"
    MUTER_DEMUCS_MP3_BITRATE = 320
    MUTER_DEMUCS_CLIP_MODE = "rescale"
    MUTER_DEMUCS_JOBS = 1


# ==========================================
# PIPELINE EXECUTION — No need to edit below this line
# ==========================================

# ------------------------------------------------------------------
# Per-step metadata used by the AnalysisReport.md writer.
# For every script the pipeline dispatches we record:
#   output_folder : folder where that step writes its figures/CSVs,
#                   resolved against PROJECT_DIR. This is where the
#                   AnalysisReport.md is placed.
#   config_section: key inside pipeline_config.json that holds the
#                   settings actually used by that script.
#   description   : short "what does this test do" blurb.
#   columns_used  : Excel columns (from Cross_Species_Rhythm_Data.xlsx)
#                   that the script relies on. Listed here so the user
#                   can see at a glance which sheet columns fed the
#                   model. Kept readable, not exhaustive.
# ------------------------------------------------------------------
_STEP_METADATA: dict = {
    "youtube_downloader.py": {
        "output_folder": "audioFiles",
        "config_section": "muter",
        "description": (
            "Downloads a YouTube video's audio track and converts it to a "
            "format the rest of the pipeline can ingest. Not a scientific "
            "analysis — just a data-acquisition convenience step."),
        "columns_used": [],
    },
    "demucs_separator.py": {
        "output_folder": "",  # derives from input folder at runtime
        "config_section": "muter",
        "description": (
            "Runs Facebook's Demucs source-separation model to split each "
            "audio file into stems (vocals / drums / bass / other). Used "
            "optionally as a pre-processing step before the Audio Editor "
            "mutes background noise."),
        "columns_used": [],
    },
    "audio_editor.py": {
        "output_folder": "",  # input_folder + '_muted_clean'
        "config_section": "muter",
        "description": (
            "Pre-processes the raw recordings by silencing quiet "
            "background sections while preserving the global timeline, "
            "applying a high-pass filter, and optionally denoising. The "
            "muted output is what the Onset Finder ingests."),
        "columns_used": [],
    },
    "beat_tempo_step.py": {
        "output_folder": "data",
        "config_section": "beat_tempo",
        "description": (
            "Detects beat events and estimates tempo per audio file using "
            "librosa.beat.beat_track (dynamic-programming beat tracker) and "
            "librosa.beat.plp (Predominant Local Pulse). Writes beat times, "
            "global tempo estimate, and PLP pulse-curve peaks to "
            "AudioData_BeatTempo.xlsx in the data/ folder."),
        "columns_used": [
            "File Name",
            "Beat Tempo Estimate (BPM)",
            "Beat Times Used (s)",
            "Beat Count",
            "PLP Peak Count",
            "PLP Peak Times (s)",
        ],
    },
    "onset_finder.py": {
        "output_folder": "data",
        "config_section": "extractor",
        "description": (
            "Detects onset events in every muted recording and computes "
            "the core rhythm metrics (IOIs, nPVI, CV, r_k, Mean IOI, "
            "entropy, etc.). Writes Cross_Species_Rhythm_Data.xlsx with "
            "a File Summaries sheet and a Dyadic Events sheet. "
            "Also drops a .TextGrid file next to each audio file (Praat "
            "annotation format — one point tier per detected onset, "
            "openable in Praat for visual QC). Disable via "
            "EXPORT_TEXTGRID=False in the Onset Finder panel if you "
            "don't want them."),
        "columns_used": [
            "File Name", "Group", "Total Duration (s)", "Total Onsets Used",
            "Mean IOI (ms)", "nPVI (Isochrony)", "CV of Intervals",
            "r_k Entropy (Categorical Measure)",
            "Stable Rhythm nPVI", "Stable Rhythm Entropy",
            "Stable Rhythm CV",
            "Rhythm Ratio [r_k]", "Cycle Duration [cd] (ms)",
            "Short Interval [i_s] (ms)", "Long Interval [i_l] (ms)",
            "Interval 1 (ms)", "Interval 2 (ms)",
        ],
    },
    "thebeat_extractor.py": {
        "output_folder": "data",
        "config_section": "extractor",
        "description": (
            "Alternative onset/rhythm engine powered by the thebeat "
            "package. Produces the same Cross_Species_Rhythm_Data.xlsx "
            "schema as onset_finder.py so downstream steps are engine-"
            "agnostic."),
        "columns_used": [
            "File Name", "Group", "Total Duration (s)", "Total Onsets Used",
            "Mean IOI (ms)", "nPVI (Isochrony)", "CV of Intervals",
            "r_k Entropy (Categorical Measure)",
            "Rhythm Ratio [r_k]", "Cycle Duration [cd] (ms)",
            "Short Interval [i_s] (ms)", "Long Interval [i_l] (ms)",
            "Interval 1 (ms)", "Interval 2 (ms)",
        ],
    },
    "flower_raster_plots.py": {
        "output_folder": "Raster_Plots",
        "config_section": "plot_generator",
        "description": (
            "Visualises each file's dyadic events as a 'flower' raster — "
            "radial scatter where angle encodes r_k and radius encodes "
            "IOI sum — grouped by dataset. Good for spotting isochronous "
            "clusters at a glance."),
        "columns_used": [
            "File Name", "Rhythm Ratio [r_k]",
            "Cycle Duration [cd] (ms)",
            "Short Interval [i_s] (ms)", "Long Interval [i_l] (ms)",
        ],
    },
    "flower_raster_3Dplots.py": {
        "output_folder": "Raster_Plots",
        "config_section": "plot_generator",
        "description": (
            "3-D variant of the flower raster plot; adds a third axis "
            "(typically tempo) to separate overlapping clusters."),
        "columns_used": [
            "File Name", "Rhythm Ratio [r_k]",
            "Cycle Duration [cd] (ms)",
            "Short Interval [i_s] (ms)", "Long Interval [i_l] (ms)",
        ],
    },
    "histogram_generator.py": {
        "output_folder": "Histogram_Plots",
        "config_section": "histogram_generator",
        "description": (
            "Builds histograms of r_k (and related ratio metrics) so you "
            "can see how strongly each species/group clusters around "
            "small-integer ratios (0.5, 0.33, 0.67 …)."),
        "columns_used": [
            "File Name", "Group", "Rhythm Ratio [r_k]",
            "nPVI (Isochrony)", "r_k Entropy (Categorical Measure)",
            "CV of Intervals",
            "Stable Rhythm nPVI", "Stable Rhythm Entropy",
            "Stable Rhythm CV",
        ],
    },
    "nPVI_byGroup.py": {
        "output_folder": "nPVI_Group_Plots",
        "config_section": "npvi_group_generator",
        "description": (
            "Raincloud plot of the normalised pairwise variability index "
            "(nPVI) across groups (e.g. species or populations). "
            "Inspired by Eleuteri et al. 2025."),
        "columns_used": [
            "File Name", "Group",
            "nPVI (Isochrony)", "Stable Rhythm nPVI",
        ],
    },
    "assocRuleLearning.py": {
        "output_folder": "Association_Rules",
        "config_section": "assoc_rule_learning",
        "description": (
            "Discretises the continuous rhythm metrics and runs Apriori "
            "association-rule mining to surface recurring co-occurrences "
            "(e.g. 'high nPVI ⇒ low CV'). Outputs a ranked rules CSV + "
            "support/confidence plots."),
        "columns_used": [
            "File Name", "Group",
            "nPVI (Isochrony)", "CV of Intervals", "Mean IOI (ms)",
            "r_k Entropy (Categorical Measure)", "Total Onsets Used",
        ],
    },
    "rhythmRatios.py": {
        "output_folder": "Rhythm_Ratios",
        "config_section": "rhythm_ratios",
        "description": (
            "Computes the per-file proportion of IOI ratios that fall in "
            "an 'isochronous band' (default 0.45-0.55) and plots the "
            "r_k distribution for each group with reference lines at "
            "small-integer ratios."),
        "columns_used": [
            "File Name", "Group", "Rhythm Ratio [r_k]",
        ],
    },
    "ksTest.py": {
        "output_folder": "KS_Test",
        "config_section": "ks_test",
        "description": (
            "One-sample Kolmogorov-Smirnov test comparing each group's "
            "r_k distribution to the uniform null expected under "
            "'random' (no rhythmic preference)."),
        "columns_used": [
            "File Name", "Group", "Rhythm Ratio [r_k]",
        ],
    },
    "wilcoxonIsochrony.py": {
        "output_folder": "Wilcoxon_Isochrony",
        "config_section": "wilcoxon_isochrony",
        "description": (
            "Wilcoxon signed-rank test on a binary 'isochronous / not' "
            "label (r_k ∈ [0.45, 0.55]) to check whether each group "
            "produces isochrony above chance."),
        "columns_used": [
            "File Name", "Group", "Rhythm Ratio [r_k]",
        ],
    },
    "lagOneAutocorrelation.py": {
        "output_folder": "Lag1_Autocorrelation",
        "config_section": "lag_one_autocorrelation",
        "description": (
            "Lag-1 autocorrelation of consecutive IOIs per file; "
            "positive values indicate tempo persistence, negative "
            "values indicate alternation."),
        "columns_used": [
            "File Name", "Group",
            "Interval 1 (ms)", "Interval 2 (ms)",
        ],
    },
    "tempoRatioHeatmap.py": {
        "output_folder": "Tempo_Ratio_Heatmap",
        "config_section": "tempo_ratio_heatmap",
        "description": (
            "2-D kernel density / heatmap of tempo (Mean IOI) vs. r_k "
            "ratio — lets you see the joint rhythmic landscape each "
            "group occupies."),
        "columns_used": [
            "File Name", "Group",
            "Rhythm Ratio [r_k]", "Cycle Duration [cd] (ms)",
        ],
    },
    "raincloudMetrics.py": {
        "output_folder": "Raincloud_Metrics",
        "config_section": "raincloud_metrics",
        "description": (
            "Side-by-side raincloud plots of every continuous rhythm "
            "metric (nPVI, CV, entropy …) across groups."),
        "columns_used": [
            "File Name", "Group",
            "nPVI (Isochrony)", "CV of Intervals", "Mean IOI (ms)",
            "r_k Entropy (Categorical Measure)",
        ],
    },
    "pDFA.py": {
        "output_folder": "pDFA",
        "config_section": "pdfa",
        "description": (
            "Permuted Discriminant Function Analysis — tests whether "
            "a group label can be predicted from the rhythm metrics "
            "better than random permutations of that label."),
        "columns_used": [
            "File Name", "Group", "Total Onsets Used", "Total Duration (s)",
            "nPVI (Isochrony)", "CV of Intervals", "Mean IOI (ms)",
            "r_k Entropy (Categorical Measure)",
        ],
    },
    "mantelTest.py": {
        "output_folder": "Mantel_Test",
        "config_section": "mantel_test",
        "description": (
            "Mantel / partial-Mantel test correlating a rhythm-distance "
            "matrix with a geographic-distance (and optional "
            "phylogenetic) matrix to see whether rhythmic similarity "
            "tracks space / phylogeny."),
        "columns_used": [
            "File Name", "Group", "Latitude", "Longitude",
            "nPVI (Isochrony)", "CV of Intervals", "Mean IOI (ms)",
            "r_k Entropy (Categorical Measure)",
        ],
    },
    "glmmRhythm.py": {
        "output_folder": "GLMM",
        "config_section": "glmm_rhythm",
        "description": (
            "Generalized linear mixed-effects model of a rhythm response "
            "(e.g. nPVI) on fixed effects (Modality, Function, "
            "Tempo_BPM, BodyMass_kg) with Group as a random effect."),
        "columns_used": [
            "File Name", "Group",
            "nPVI (Isochrony)", "Mean IOI (ms)", "CV of Intervals",
            "Total Duration (s)",
            "Modality", "Function", "Tempo_BPM", "BodyMass_kg",
        ],
    },
    "pgls.py": {
        "output_folder": "PGLS",
        "config_section": "pgls",
        "description": (
            "Phylogenetic Generalized Least Squares regression — fits a "
            "linear model with residuals structured by a supplied tree "
            "so species non-independence is accounted for."),
        "columns_used": [
            "File Name", "Species",
            "nPVI (Isochrony)", "Tempo_BPM", "BodyMass_kg",
        ],
    },
}


# ------------------------------------------------------------------
# Execution-feedback infrastructure (progress bar + analyses summary)
# ------------------------------------------------------------------
# Records collected across the run; one entry per run_step / run_step_soft
# invocation. Used to write ``AudioData_AnalysesSummary.xlsx`` at the end.
_PIPELINE_STEP_RECORDS: list = []

# Counters used to emit machine-parseable progress markers that the GUI
# parses to update its central QProgressBar. We do not know the total
# up-front (toggles decide), so ``_PIPELINE_TOTAL_STEPS`` is set once at
# the top of ``main()`` and ``_PIPELINE_DONE_STEPS`` is bumped after each
# step completes (or fails).
_PIPELINE_TOTAL_STEPS: int = 0
_PIPELINE_DONE_STEPS: int = 0

# Progress marker prefix. Kept intentionally distinctive so the GUI can
# strip it from the user-visible terminal output.
_PROGRESS_MARKER = "[[PIPELINE_PROGRESS]]"


def _emit_progress(label: str = "") -> None:
    """Print a machine-parseable progress marker on its own line.

    Format::

        [[PIPELINE_PROGRESS]] done=<int> total=<int> label=<text>

    The GUI strips these lines from the displayed terminal output and
    uses them to drive the central pipeline progress bar.
    """
    safe = str(label).replace("\n", " ").replace("\r", " ")
    print(f"{_PROGRESS_MARKER} done={_PIPELINE_DONE_STEPS} "
          f"total={_PIPELINE_TOTAL_STEPS} label={safe}", flush=True)


_FINDING_SKIP_PREFIXES = ("===", "---", ">>>", "***", "[[PIPELINE_PROGRESS]]")


def _extract_finding(captured: str) -> str:
    """Pick a short, human-readable 'findings' line from a step's stdout.

    Rules, in order:
    1. Any line beginning with ``[SUMMARY]`` (explicit opt-in).
    2. Otherwise the last non-blank line that is not a banner / progress
       marker / bare-punctuation separator.
    """
    if not captured:
        return "(no output)"
    summary_lines = [
        ln.strip() for ln in captured.splitlines()
        if ln.strip().startswith("[SUMMARY]")
    ]
    if summary_lines:
        text = summary_lines[-1].removeprefix("[SUMMARY]").strip()
        return text[:240] if text else "(empty [SUMMARY])"
    # Fallback: last non-banner, non-empty line.
    for ln in reversed(captured.splitlines()):
        s = ln.strip()
        if not s:
            continue
        if any(s.startswith(p) for p in _FINDING_SKIP_PREFIXES):
            continue
        # Skip lines that are only punctuation / separators
        if set(s) <= set("=-_*# "):
            continue
        return s[:240]
    return "(no descriptive output)"


def _record_step(*, number, description, script, exit_code, duration_sec,
                 captured, error_reason=""):
    """Append one row to ``_PIPELINE_STEP_RECORDS`` for the summary xlsx."""
    ok = (exit_code == 0)
    if ok:
        status = "PASS"
        finding = _extract_finding(captured)
    else:
        status = "FAIL"
        reason = error_reason or f"exit code {exit_code}"
        last = _extract_finding(captured)
        finding = f"{reason} — {last}" if last and last.startswith("(") is False else reason
    _PIPELINE_STEP_RECORDS.append({
        "step": number,
        "test_name": description,
        "script": script,
        "status": status,
        "exit_code": exit_code if exit_code is not None else "",
        "duration_sec": round(float(duration_sec or 0.0), 2),
        "finding": finding,
    })


def _resolve_report_folder(script_name: str) -> str:
    """Return the absolute folder that ``script_name`` writes its outputs
    to (and where ``AnalysisReport.md`` should be written).

    The per-script metadata is consulted first. If the folder field is
    blank (a few scripts derive it at runtime), we fall back to a safe
    default under ``PROJECT_DIR/AnalysisReports/<script>/`` so the
    report still lands somewhere predictable.
    """
    meta = _STEP_METADATA.get(script_name, {})
    folder = meta.get("output_folder", "")

    # Scripts whose output folder is dynamic (driven by user config).
    # Resolve them from the globals that main.py has already loaded
    # from pipeline_config.json so reports land next to real outputs.
    if script_name in ("audio_editor.py", "demucs_separator.py"):
        try:
            explicit = (MUTER_OUTPUT_FOLDER or "").strip()
            base = (MUTER_INPUT_FOLDER or "").strip()
        except NameError:
            explicit, base = "", ""
        if explicit:
            folder = explicit
        elif base:
            folder = base + "_muted_clean"
    elif script_name in ("onset_finder.py", "thebeat_extractor.py"):
        # Onset Finder writes next to its Excel workbook, which lives
        # in <input>/data/ by convention. Prefer that if it exists.
        try:
            base = (MUTER_INPUT_FOLDER or "").strip()
        except NameError:
            base = ""
        if base:
            candidate = os.path.join(base, "data")
            folder = candidate if os.path.isdir(candidate) else base

    if folder:
        if not os.path.isabs(folder):
            folder = os.path.join(PROJECT_DIR, folder)
    else:
        folder = os.path.join(
            PROJECT_DIR, "AnalysisReports",
            os.path.splitext(script_name)[0])
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        # If the filesystem refuses (read-only / permissions), fall
        # back to a sibling of PROJECT_DIR that should always work.
        folder = os.path.join(PROJECT_DIR, "AnalysisReports",
                              os.path.splitext(script_name)[0])
        os.makedirs(folder, exist_ok=True)
    return folder


def _load_config_section(section_key: str) -> dict:
    """Return ``pipeline_config.json``'s *section_key* as a dict."""
    if not section_key:
        return {}
    cfg_path = os.path.join(PROJECT_DIR, "pipeline_config.json")
    if not os.path.isfile(cfg_path):
        return {}
    try:
        import json as _rj
        with open(cfg_path, encoding="utf-8") as f:
            data = _rj.load(f)
        sec = data.get(section_key, {})
        return sec if isinstance(sec, dict) else {}
    except Exception:
        return {}


def _write_analysis_report(
    step_number,
    description: str,
    script_name: str,
    args: list | None,
    cmd: list,
    returncode: int | None,
    captured_output: str,
    started_at: str,
    finished_at: str,
    duration_sec: float,
    error_reason: str = "",
) -> str:
    """Write an ``AnalysisReport.md`` for a single pipeline step.

    Returns the path of the written report, or ``""`` if writing
    failed (logged as a warning — never raises, the pipeline must
    always reach the end).
    """
    meta = _STEP_METADATA.get(script_name, {})
    folder = _resolve_report_folder(script_name)
    report_path = os.path.join(folder, "AnalysisReport.md")
    script_path = os.path.join(SCRIPTS_DIR, script_name)

    ok = (returncode == 0)
    status_badge = "✅ Success" if ok else "❌ Failed"
    status_line = (
        f"Step completed successfully (exit code 0)." if ok
        else (f"Step failed — {error_reason}" if error_reason
              else f"Step failed (exit code {returncode})."))

    # Excel columns used
    cols = meta.get("columns_used", []) or []
    cols_md = ("\n".join(f"- `{c}`" for c in cols)
               if cols else "- _(none — this step does not read the "
               "Cross_Species_Rhythm_Data.xlsx workbook)_")

    # Config section actually applied
    cfg_section_key = meta.get("config_section", "")
    cfg_vals = _load_config_section(cfg_section_key)
    if cfg_vals:
        cfg_lines = [f"- `{k}` = `{v!r}`" for k, v in sorted(cfg_vals.items())]
        cfg_md = "\n".join(cfg_lines)
    else:
        cfg_md = ("- _(no settings recorded for this step in "
                  "pipeline_config.json)_")

    # Command used
    cmd_str = " ".join(cmd) if cmd else "(no command recorded)"

    # Captured output — trim to a reasonable size so the report stays
    # readable. Keep the head (setup messages) and tail (error tracebacks)
    # rather than a middle slice.
    out = captured_output or ""
    MAX_CHARS = 20_000
    if len(out) > MAX_CHARS:
        head = out[:MAX_CHARS // 2]
        tail = out[-MAX_CHARS // 2:]
        out = (head + "\n\n... [output truncated — "
               f"{len(captured_output) - MAX_CHARS} chars omitted] ...\n\n"
               + tail)

    desc_text = meta.get("description", description or "(no description)")

    report = f"""# Analysis Report — {description}

**Status:** {status_badge}
**Step number:** {step_number}
**Script:** `scripts/{script_name}`
**Started:** {started_at}
**Finished:** {finished_at}
**Duration:** {duration_sec:.2f} s
**Exit code:** {returncode if returncode is not None else 'n/a'}

## 1. Outcome

{status_line}

## 2. What this test actually does

{desc_text}

## 3. Excel columns used

Source workbook: `Cross_Species_Rhythm_Data.xlsx` (produced by Step 2 — Onset Finder).

{cols_md}

## 4. Settings applied (from `pipeline_config.json` → `{cfg_section_key or '—'}`)

{cfg_md}

## 5. Exact command the pipeline ran

```bash
{cmd_str}
```

The script file used was:

```
{script_path}
```

## 6. Captured stdout / stderr

<details>
<summary>Click to expand ({len(captured_output)} chars captured)</summary>

```
{out if out.strip() else '(no output captured)'}
```

</details>

---

_This report was written automatically by `scripts/main.py` after the step
finished. Re-running the pipeline overwrites it._
"""
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
    except OSError as exc:
        print(f"  WARNING: could not write AnalysisReport.md "
              f"to {report_path}: {exc}")
        return ""
    return report_path


def _run_subprocess_capture(cmd: list) -> tuple[int, str]:
    """Run *cmd*, stream its output live AND capture it into a string.

    We want the user to keep seeing progress in real time (the GUI's
    terminal panel tails the same stdout) but we also need the full
    transcript to embed in the step's ``AnalysisReport.md``.
    """
    import time
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    lines: list[str] = []
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")  # live echo
            lines.append(line)
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        raise
    return proc.returncode, "".join(lines)


def run_step(step_number, description, script_name, args=None):
    """Run a single pipeline step as a subprocess and report its outcome."""
    import datetime as _dt
    import time as _time
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.isfile(script_path):
        reason = f"Script not found: {script_path}"
        print(f"\n>>> [STEP {step_number}] \u2717 STEP FAILED \u2014 {description}")
        print(f"    Reason: {reason}")
        # Still write a report so the user sees what happened.
        _write_analysis_report(
            step_number=step_number, description=description,
            script_name=script_name, args=args, cmd=[sys.executable, script_path],
            returncode=None, captured_output="",
            started_at=_dt.datetime.now().isoformat(timespec="seconds"),
            finished_at=_dt.datetime.now().isoformat(timespec="seconds"),
            duration_sec=0.0,
            error_reason=reason,
        )
        _record_step(number=step_number, description=description,
                     script=script_name, exit_code=None, duration_sec=0.0,
                     captured="", error_reason=reason)
        global _PIPELINE_DONE_STEPS
        _PIPELINE_DONE_STEPS += 1
        _emit_progress(f"failed: {description}")
        return False

    cmd = [sys.executable, script_path]
    if args:
        cmd.extend(args)

    print(f"\n{'=' * 60}")
    print(f">>> [STEP {step_number}] \u25B6 Starting: {description}")
    print(f"    Script: scripts/{script_name}")
    print(f"    Executing: {' '.join(cmd)}")
    print(f"{'=' * 60}\n")
    _emit_progress(f"running: {description}")

    started = _dt.datetime.now()
    t0 = _time.time()
    rc, captured = _run_subprocess_capture(cmd)
    dt_sec = _time.time() - t0
    finished = _dt.datetime.now()

    _write_analysis_report(
        step_number=step_number, description=description,
        script_name=script_name, args=args, cmd=cmd,
        returncode=rc, captured_output=captured,
        started_at=started.isoformat(timespec="seconds"),
        finished_at=finished.isoformat(timespec="seconds"),
        duration_sec=dt_sec,
        error_reason="" if rc == 0 else f"non-zero exit code {rc}",
    )

    _record_step(number=step_number, description=description,
                 script=script_name, exit_code=rc, duration_sec=dt_sec,
                 captured=captured,
                 error_reason="" if rc == 0 else f"non-zero exit code {rc}")
    globals()["_PIPELINE_DONE_STEPS"] = _PIPELINE_DONE_STEPS + 1

    if rc != 0:
        print(f"\n>>> [STEP {step_number}] \u2717 STEP FAILED \u2014 "
              f"{description} (exit code {rc}, {dt_sec:.1f}s)")
        print("    Fix the issue above and re-run the pipeline.")
        _emit_progress(f"failed: {description}")
        # NOTE: this is a fail-fast step; the pipeline aborts here.
        # The analyses summary is written by main()'s finally-branch.
        sys.exit(rc)

    print(f"\n>>> [STEP {step_number}] \u2713 STEP COMPLETE \u2014 "
          f"{description} ({dt_sec:.1f}s)")
    _emit_progress(f"done: {description}")
    return True


# Collected errors/warnings from fail-soft (experimental) steps. Reported at
# the end of the pipeline run so users see a consolidated summary in the
# terminal output panel without the whole pipeline aborting.
_EXPERIMENTAL_ERRORS: list = []


def run_step_soft(step_number, description, script_name, args=None):
    """Run an experimental step without stopping the pipeline on failure.

    Unlike ``run_step`` (which calls ``sys.exit`` on non-zero exit codes),
    this captures the failure into ``_EXPERIMENTAL_ERRORS`` and returns so
    the next experimental step can still run. Intended for the 10
    multi-species rhythmic-landscape analyses and ARL — NOT for the
    Audio Editor or Onset Finder, which remain fail-fast.
    """
    import datetime as _dt
    import time as _time
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.isfile(script_path):
        msg = f"Script not found: {script_path}"
        print(f"\n>>> [STEP {step_number}] \u2717 STEP FAILED \u2014 {description}")
        print(f"    Reason: {msg}")
        _EXPERIMENTAL_ERRORS.append({
            "step": step_number, "description": description,
            "script": script_name, "exit_code": None, "reason": msg,
        })
        _write_analysis_report(
            step_number=step_number, description=description,
            script_name=script_name, args=args,
            cmd=[sys.executable, script_path], returncode=None,
            captured_output="",
            started_at=_dt.datetime.now().isoformat(timespec="seconds"),
            finished_at=_dt.datetime.now().isoformat(timespec="seconds"),
            duration_sec=0.0, error_reason=msg,
        )
        _record_step(number=step_number, description=description,
                     script=script_name, exit_code=None, duration_sec=0.0,
                     captured="", error_reason=msg)
        globals()["_PIPELINE_DONE_STEPS"] = _PIPELINE_DONE_STEPS + 1
        _emit_progress(f"failed: {description}")
        return False

    cmd = [sys.executable, script_path]
    if args:
        cmd.extend(args)

    print(f"\n{'=' * 60}")
    print(f">>> [STEP {step_number}] \u25B6 Starting: {description}")
    print(f"    Script: scripts/{script_name}  (experimental \u2014 fail-soft)")
    print(f"    Executing: {' '.join(cmd)}")
    print(f"{'=' * 60}\n")
    _emit_progress(f"running: {description}")

    started = _dt.datetime.now()
    t0 = _time.time()
    captured = ""
    try:
        rc, captured = _run_subprocess_capture(cmd)
    except Exception as e:
        rc = -1
        reason = f"{type(e).__name__}: {e}"
        _EXPERIMENTAL_ERRORS.append({
            "step": step_number, "description": description,
            "script": script_name, "exit_code": rc,
            "reason": reason,
        })
        dt_sec = _time.time() - t0
        _write_analysis_report(
            step_number=step_number, description=description,
            script_name=script_name, args=args, cmd=cmd,
            returncode=rc, captured_output=captured,
            started_at=started.isoformat(timespec="seconds"),
            finished_at=_dt.datetime.now().isoformat(timespec="seconds"),
            duration_sec=dt_sec, error_reason=reason,
        )
        _record_step(number=step_number, description=description,
                     script=script_name, exit_code=rc, duration_sec=dt_sec,
                     captured=captured, error_reason=reason)
        globals()["_PIPELINE_DONE_STEPS"] = _PIPELINE_DONE_STEPS + 1
        print(f"\n>>> [STEP {step_number}] \u2717 STEP FAILED \u2014 "
              f"{description} ({reason})")
        print("    (continuing to next experimental step)")
        _emit_progress(f"failed: {description}")
        return False

    dt_sec = _time.time() - t0
    finished = _dt.datetime.now()

    error_reason = "" if rc == 0 else f"non-zero exit code {rc}"
    _write_analysis_report(
        step_number=step_number, description=description,
        script_name=script_name, args=args, cmd=cmd,
        returncode=rc, captured_output=captured,
        started_at=started.isoformat(timespec="seconds"),
        finished_at=finished.isoformat(timespec="seconds"),
        duration_sec=dt_sec, error_reason=error_reason,
    )
    _record_step(number=step_number, description=description,
                 script=script_name, exit_code=rc, duration_sec=dt_sec,
                 captured=captured, error_reason=error_reason)
    globals()["_PIPELINE_DONE_STEPS"] = _PIPELINE_DONE_STEPS + 1

    if rc != 0:
        _EXPERIMENTAL_ERRORS.append({
            "step": step_number, "description": description,
            "script": script_name, "exit_code": rc,
            "reason": error_reason,
        })
        print(f"\n>>> [STEP {step_number}] \u2717 STEP FAILED \u2014 "
              f"{description} (exit code {rc}, {dt_sec:.1f}s)")
        print("    (continuing to next experimental step \u2014 see summary at end)")
        _emit_progress(f"failed: {description}")
        return False

    print(f"\n>>> [STEP {step_number}] \u2713 STEP COMPLETE \u2014 "
          f"{description} ({dt_sec:.1f}s)")
    _emit_progress(f"done: {description}")
    return True


def _print_experimental_summary():
    """Print the collected errors/warnings from experimental steps at the
    end of the pipeline run. Called once from ``main`` after all steps."""
    if not _EXPERIMENTAL_ERRORS:
        print("\nAll experimental analyses completed successfully.")
        return
    print("\n" + "=" * 60)
    print("  EXPERIMENTAL STEP — ERRORS & WARNINGS")
    print("=" * 60)
    print(f"\n  {len(_EXPERIMENTAL_ERRORS)} experimental step(s) did not "
          "complete successfully:\n")
    for i, err in enumerate(_EXPERIMENTAL_ERRORS, 1):
        print(f"  {i}. Step {err['step']}: {err['description']}")
        print(f"       Script: {err['script']}")
        if err.get("exit_code") is not None:
            print(f"       Exit code: {err['exit_code']}")
        print(f"       Reason: {err['reason']}")
        print(
            "       → Check the step's 'Excel Data Used…' dialog in the GUI")
        print(
            "         to confirm the Input Excel has all required columns.")
        print(
            "       → The warning box under that button lists any columns")
        print("         currently missing from your workbook.\n")
    print("  (The Audio Editor and Onset Finder steps are fail-fast and")
    print("   would have stopped the pipeline; these experimental steps")
    print("   are logged here and skipped so later steps can still run.)")


def _load_per_file_settings(path):
    """Load per-file settings from a JSON file or directory of JSON files.

    Returns a dict ``{filename: {settings_dict}}``, or ``None`` if the path
    is empty or doesn't exist.
    """
    if not path:
        return None
    import json
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # Could be a single entry or a combined dict
        if isinstance(data, dict) and "settings" in data:
            # Single-file format
            return {data["filename"]: data["settings"]}
        # Combined format: {filename: {entry}}.  Keys starting with
        # '__' are reserved (e.g. '__pre_analysis_original__' holds the
        # frozen pre-analysis backup used by the GUI's per-file dialog)
        # and MUST be ignored at runtime.
        result = {}
        for key, val in data.items():
            if key.startswith("__"):
                continue
            if isinstance(val, dict):
                result[key] = val.get("settings", val)
        return result if result else None
    elif os.path.isdir(path):
        result = {}
        for fn in sorted(os.listdir(path)):
            if fn.endswith(".json"):
                fp = os.path.join(path, fn)
                with open(fp, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    if "filename" in data and "settings" in data:
                        result[data["filename"]] = data["settings"]
                    else:
                        for key, val in data.items():
                            if key.startswith("__"):
                                continue
                            if isinstance(val, dict):
                                result[key] = val.get("settings", val)
        return result if result else None
    return None


def _count_total_steps() -> int:
    """Pre-compute how many pipeline steps will actually run, so the
    GUI progress bar can show an honest ``done / total`` percentage."""
    n = 0
    if YOUTUBE_URL:
        n += 1
    if RUN_MUTER:
        if MUTER_DEMUCS_ENABLED:
            n += 1  # Demucs separation step
            if not MUTER_DEMUCS_ONLY:
                n += 1  # Audio Editor on separated stems
        else:
            n += 1  # Audio Editor only
    if RUN_EXTRACTOR:
        n += 1
    if RUN_BEAT_TEMPO:
        n += 1
    if RUN_PLOT_GENERATOR:
        n += 2  # 2-D flower + 3-D flower
    if RUN_HISTOGRAM_GENERATOR:
        n += 1
    if RUN_NPVI_GROUP_GENERATOR:
        n += 1
    if RUN_ASSOC_RULE_LEARNING:
        n += 1
    for flag in (RUN_RHYTHM_RATIOS, RUN_KS_TEST, RUN_WILCOXON_ISOCHRONY,
                 RUN_LAG_ONE_AUTOCORRELATION, RUN_TEMPO_RATIO_HEATMAP,
                 RUN_RAINCLOUD_METRICS, RUN_PDFA, RUN_MANTEL_TEST,
                 RUN_GLMM_RHYTHM, RUN_PGLS):
        if flag:
            n += 1
    return max(n, 1)


def _resolve_summary_folder() -> str:
    """Where to write ``AudioData_AnalysesSummary.xlsx``.

    Prefer the Onset Finder's output folder (next to
    ``AudioData_OnsetFinder.xlsx``). If that can't be resolved, fall
    back to ``PROJECT_DIR/AnalysisReports``.
    """
    try:
        folder = _resolve_report_folder("onset_finder.py")
    except Exception:
        folder = ""
    if folder and os.path.isdir(folder):
        return folder
    fallback = os.path.join(PROJECT_DIR, "AnalysisReports")
    os.makedirs(fallback, exist_ok=True)
    return fallback


def _write_analyses_summary_xlsx() -> str:
    """Write ``AudioData_AnalysesSummary.xlsx`` summarising every step.

    Columns: ``Step | Test Name | Status | Exit Code | Duration (s) |
    Findings / Summary | Script``. Returns the written path (empty
    string if writing failed).
    """
    if not _PIPELINE_STEP_RECORDS:
        return ""
    try:
        import pandas as _pd
    except Exception as exc:
        print(f"  WARNING: pandas not available, cannot write "
              f"AudioData_AnalysesSummary.xlsx: {exc}")
        return ""
    rows = []
    for r in _PIPELINE_STEP_RECORDS:
        rows.append({
            "Step": r.get("step", ""),
            "Test Name": r.get("test_name", ""),
            "Status": r.get("status", ""),
            "Exit Code": r.get("exit_code", ""),
            "Duration (s)": r.get("duration_sec", ""),
            "Findings / Summary": r.get("finding", ""),
            "Script": r.get("script", ""),
        })
    df = _pd.DataFrame(rows, columns=[
        "Step", "Test Name", "Status", "Exit Code", "Duration (s)",
        "Findings / Summary", "Script"])
    folder = _resolve_summary_folder()
    out_path = os.path.join(folder, "AudioData_AnalysesSummary.xlsx")
    try:
        with _pd.ExcelWriter(out_path, engine="openpyxl") as xw:
            df.to_excel(xw, sheet_name="Pipeline Summary", index=False)
            # Auto-size columns for readability.
            ws = xw.sheets["Pipeline Summary"]
            for i, col in enumerate(df.columns, start=1):
                max_len = max(
                    [len(str(col))]
                    + [len(str(v)) for v in df[col].tolist()])
                ws.column_dimensions[ws.cell(row=1, column=i).column_letter]\
                    .width = min(max(max_len + 2, 12), 80)
    except Exception as exc:
        print(f"  WARNING: could not write {out_path}: {exc}")
        return ""
    return out_path


def main():
    print("=" * 60)
    print("  BIOACOUSTICS RHYTHM ANALYSIS PIPELINE")
    print("=" * 60)

    # Reset per-run state (important if ``main`` is re-invoked inside
    # the same interpreter, e.g. from tests).
    global _PIPELINE_TOTAL_STEPS, _PIPELINE_DONE_STEPS
    _PIPELINE_TOTAL_STEPS = _count_total_steps()
    _PIPELINE_DONE_STEPS = 0
    _PIPELINE_STEP_RECORDS.clear()
    _EXPERIMENTAL_ERRORS.clear()
    print(f"  Total enabled steps: {_PIPELINE_TOTAL_STEPS}")
    _emit_progress("starting pipeline")

    # Step 0: YouTube Download (optional)
    if YOUTUBE_URL:
        yt_args = [YOUTUBE_URL, "-o", MUTER_INPUT_FOLDER]
        run_step(0, "YouTube Download", "youtube_downloader.py", yt_args)
    else:
        print("\nStep 0: YouTube Download — SKIPPED (no URL)")

    # Step 1: Audio Editor (with optional Demucs source separation)
    if RUN_MUTER:
        selected_muter_files = MUTER_SELECTED_FILES if MUTER_SPECIFY_FILES else []

        # --- Demucs source separation (optional pre-step) ---
        if MUTER_DEMUCS_ENABLED:
            demucs_args = [
                MUTER_INPUT_FOLDER,
                "--model", str(MUTER_DEMUCS_MODEL),
                "--device", str(MUTER_DEMUCS_DEVICE),
                "--shifts", str(MUTER_DEMUCS_SHIFTS),
                "--overlap", str(MUTER_DEMUCS_OVERLAP),
                "--clip-mode", str(MUTER_DEMUCS_CLIP_MODE),
                "--output-format", str(MUTER_DEMUCS_OUTPUT_FORMAT),
                "--other-method", str(MUTER_DEMUCS_OTHER_METHOD),
                "--mp3-bitrate", str(MUTER_DEMUCS_MP3_BITRATE),
                "-j", str(MUTER_DEMUCS_JOBS),
            ]
            if MUTER_DEMUCS_TWO_STEMS:
                demucs_args.extend(["--two-stems", str(MUTER_DEMUCS_TWO_STEMS)])
            if MUTER_DEMUCS_SEGMENT is not None:
                demucs_args.extend(["--segment", str(MUTER_DEMUCS_SEGMENT)])
            if MUTER_OUTPUT_FOLDER:
                demucs_args.extend(["--output-folder", str(MUTER_OUTPUT_FOLDER)])
            if selected_muter_files:
                demucs_args.extend(["--files", *selected_muter_files])
            run_step(1, "Demucs Source Separation", "demucs_separator.py", demucs_args)

            if MUTER_DEMUCS_ONLY:
                print("  (ONLY Run Demucs mode — skipping Audio Editor processing)")

        # --- Standard Audio Editor processing ---
        if not (MUTER_DEMUCS_ENABLED and MUTER_DEMUCS_ONLY):
            per_file_audio = _load_per_file_settings(_PER_FILE_AUDIO_SETTINGS_PATH)
            if per_file_audio:
                print(f"\n{'=' * 60}")
                print(f">>> [STEP 1] \u25B6 Starting: Audio Editor (per-file settings)")
                if selected_muter_files:
                    print(f"    Filtering to {len(selected_muter_files)} selected file(s)")
                else:
                    print(f"    Processing {len(per_file_audio)} file(s) with individual settings")
                print(f"{'=' * 60}\n")
                _emit_progress("running: Audio Editor (per-file)")
                sys.path.insert(0, SCRIPTS_DIR)
                from audio_editor import process_folder_with_per_file_settings
                output_folder = MUTER_OUTPUT_FOLDER or None
                import time as _t0
                _t_start = _t0.time()
                _perfile_ok = True
                try:
                    n = process_folder_with_per_file_settings(
                        MUTER_INPUT_FOLDER, per_file_audio, output_folder,
                        selected_filenames=selected_muter_files)
                except Exception as _exc:
                    _perfile_ok = False
                    n = 0
                    _perfile_err = f"{type(_exc).__name__}: {_exc}"
                _t_dur = _t0.time() - _t_start
                if _perfile_ok:
                    _record_step(number=1,
                                 description="Audio Editor (per-file)",
                                 script="audio_editor.py",
                                 exit_code=0, duration_sec=_t_dur,
                                 captured=f"[SUMMARY] {n} file(s) processed")
                    globals()["_PIPELINE_DONE_STEPS"] = _PIPELINE_DONE_STEPS + 1
                    print(f"\n>>> [STEP 1] \u2713 STEP COMPLETE \u2014 "
                          f"Audio Editor (per-file): {n} file(s) "
                          f"({_t_dur:.1f}s)")
                    _emit_progress("done: Audio Editor (per-file)")
                else:
                    _record_step(number=1,
                                 description="Audio Editor (per-file)",
                                 script="audio_editor.py",
                                 exit_code=-1, duration_sec=_t_dur,
                                 captured="", error_reason=_perfile_err)
                    globals()["_PIPELINE_DONE_STEPS"] = _PIPELINE_DONE_STEPS + 1
                    print(f"\n>>> [STEP 1] \u2717 STEP FAILED \u2014 "
                          f"Audio Editor (per-file): {_perfile_err}")
                    _emit_progress("failed: Audio Editor (per-file)")
                    raise SystemExit(1)
            else:
                muter_args = [
                    MUTER_INPUT_FOLDER,
                    "--db-threshold", str(MUTER_DB_THRESHOLD),
                    "--highpass", str(MUTER_HIGHPASS_HZ),
                    "--fade-ms", str(MUTER_FADE_MS),
                ]
                if MUTER_AUTO_THRESHOLD:
                    muter_args.append("--auto-threshold")
                    muter_args.extend(["--noise-margin-db", str(MUTER_NOISE_MARGIN_DB)])
                if MUTER_SAVE_NOISE_PROFILE:
                    muter_args.append("--save-noise-profile")
                if MUTER_SPECTRAL_DENOISE:
                    muter_args.append("--spectral-denoise")
                    muter_args.extend(["--denoise-strength", str(MUTER_DENOISE_STRENGTH)])
                if MUTER_HPSS_ENABLED:
                    muter_args.append("--hpss")
                    muter_args.extend(["--hpss-target", str(MUTER_HPSS_TARGET)])
                    muter_args.extend(["--hpss-margin", str(MUTER_HPSS_MARGIN)])
                if MUTER_OUTPUT_FOLDER:
                    muter_args.extend(["--output-folder", str(MUTER_OUTPUT_FOLDER)])
                if selected_muter_files:
                    muter_args.extend(["--files", *selected_muter_files])
                run_step(1, "Audio Editor (pre-processing)", "audio_editor.py", muter_args)
    else:
        print("\nStep 1: Audio Editor — SKIPPED")

    # Step 2: Onset Finder (standard or thebeat engine)
    if RUN_EXTRACTOR:
        if EXTRACTOR_ENGINE == "thebeat":
            run_step(2, "Onset Finder — thebeat engine (onset detection & metrics)",
                     "thebeat_extractor.py")
        elif EXTRACTOR_ENGINE == "standard":
            run_step(2, "Onset Finder — standard engine (onset detection & metrics)",
                     "onset_finder.py")
        else:
            print(f"\n*** ERROR: Unknown EXTRACTOR_ENGINE '{EXTRACTOR_ENGINE}'. "
                  f"Use 'standard' or 'thebeat'. ***")
            sys.exit(1)
    else:
        print("\nStep 2: Onset Finder — SKIPPED")

    # Step 2b: Beat and Tempo
    if RUN_BEAT_TEMPO:
        run_step("2b", "Beat and Tempo (beat tracking & PLP)",
                 "beat_tempo_step.py")
    else:
        print("\nStep 2b: Beat and Tempo — SKIPPED")

    # Step 3: Flower Raster Plots
    if RUN_PLOT_GENERATOR:
        run_step(3, "Flower Raster Plots", "flower_raster_plots.py")
        # 3D flower runs as part of Step 3 when enabled (reads its own config)
        run_step("3b", "3D Flower Raster", "flower_raster_3Dplots.py")
    else:
        print("\nStep 3: Flower Raster Plots — SKIPPED")

    # Step 4: Histogram Generator
    if RUN_HISTOGRAM_GENERATOR:
        run_step(4, "Histogram Generator", "histogram_generator.py")
    else:
        print("\nStep 4: Histogram Generator — SKIPPED")

    # Step 5: nPVI Group Plot
    if RUN_NPVI_GROUP_GENERATOR:
        run_step(5, "nPVI Group Plot", "nPVI_byGroup.py")
    else:
        print("\nStep 5: nPVI Group Plot — SKIPPED")

    # Step 6: Association Rule Learning (experimental — fail-soft)
    if RUN_ASSOC_RULE_LEARNING:
        run_step_soft(6, "Association Rule Learning (experimental)",
                      "assocRuleLearning.py")
    else:
        print("\nStep 6: Association Rule Learning — SKIPPED")

    # Steps 8-17: Multi-species rhythmic-landscape analyses
    _new_steps = [
        (RUN_RHYTHM_RATIOS, 8, "Rhythm Ratio Distributions", "rhythmRatios.py"),
        (RUN_KS_TEST, 9, "KS Test vs. Uniform Null", "ksTest.py"),
        (RUN_WILCOXON_ISOCHRONY, 10, "Wilcoxon Isochrony Preference",
         "wilcoxonIsochrony.py"),
        (RUN_LAG_ONE_AUTOCORRELATION, 11, "Lag-1 Autocorrelation",
         "lagOneAutocorrelation.py"),
        (RUN_TEMPO_RATIO_HEATMAP, 12, "Tempo × Ratio Density Heatmap",
         "tempoRatioHeatmap.py"),
        (RUN_RAINCLOUD_METRICS, 13, "Multi-metric Raincloud Plots",
         "raincloudMetrics.py"),
        (RUN_PDFA, 14, "Permuted Discriminant Function Analysis", "pDFA.py"),
        (RUN_MANTEL_TEST, 15, "Mantel / Partial Mantel Test", "mantelTest.py"),
        (RUN_GLMM_RHYTHM, 16, "GLMM for Rhythmic Responses", "glmmRhythm.py"),
        (RUN_PGLS, 17, "Phylogenetic Generalized Least Squares", "pgls.py"),
    ]
    for _flag, _n, _desc, _script in _new_steps:
        if _flag:
            run_step_soft(_n, _desc, _script)
        else:
            print(f"\nStep {_n}: {_desc} — SKIPPED")

    # Final summary of any experimental-step errors/warnings
    _print_experimental_summary()

    # --- Analyses summary xlsx (always written, even on partial runs) ---
    summary_path = _write_analyses_summary_xlsx()

    # Determine overall success: all recorded steps PASSed. (Fail-fast
    # steps would have sys.exited before we got here, so the only way
    # to reach this point with any FAILs is via fail-soft experimental
    # steps.)
    n_pass = sum(1 for r in _PIPELINE_STEP_RECORDS if r.get("status") == "PASS")
    n_fail = sum(1 for r in _PIPELINE_STEP_RECORDS if r.get("status") == "FAIL")
    _emit_progress("pipeline complete")

    print("\n" + "=" * 60)
    if n_fail == 0:
        print("  >>> [PIPELINE] \u2713 FULL PIPELINE EXECUTION SUCCESSFUL")
        print(f"      All {n_pass} enabled step(s) completed without errors.")
    else:
        print("  >>> [PIPELINE] \u26A0  PIPELINE FINISHED WITH SOFT FAILURES")
        print(f"      {n_pass} step(s) passed, {n_fail} experimental "
              f"step(s) failed (see table above).")
    if summary_path:
        print(f"      Analyses summary: {summary_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()