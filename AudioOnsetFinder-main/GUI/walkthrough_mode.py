"""Guided Walkthrough Mode for the Bioacoustics Rhythm Pipeline GUI.

Opens a wizard-style dialog that walks a new user through every
pipeline step, explains each setting in plain language, and offers
data-type-specific advice on how to configure it.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# ── Colour constants (mirrored from pipeline_gui) ──────────────────
_ACCENT = "#4caf50"
_ACCENT_HOVER = "#66bb6a"
_ACCENT_DIM = "#2e7d32"
_BG = "#1e1e2e"
_BG_MID = "#262636"
_BG_WIDGET = "#2c2c3c"
_BG_INPUT = "#323248"
_BORDER = "#3a3a50"
_BORDER_FOCUS = "#5c6bc0"
_TEXT = "#dcdcdc"
_TEXT_DIM = "#8888a0"
_TEXT_DESC = "#a8a8c0"

# ── Layout helpers ─────────────────────────────────────────────────

def _sep():
    s = QFrame()
    s.setFrameShape(QFrame.Shape.HLine)
    s.setStyleSheet(f"background-color: {_BORDER}; max-height: 1px;")
    return s


def _heading(text, size=15):
    lbl = QLabel(text)
    lbl.setFont(QFont("", size, QFont.Weight.Bold))
    lbl.setStyleSheet(f"color: {_ACCENT}; background: transparent;")
    lbl.setWordWrap(True)
    return lbl


def _body(text):
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: {_TEXT}; font-size: 13px; background: transparent;"
        f"  line-height: 1.55; padding: 2px 0px;"
    )
    lbl.setTextFormat(Qt.TextFormat.RichText)
    return lbl


def _dim(text):
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"color: {_TEXT_DESC}; font-size: 12px; background: transparent;")
    return lbl


# ── Walkthrough content ────────────────────────────────────────────
# Each setting entry is a tuple:
#   (widget_attr, label, explanation, advice)
# widget_attr is the attribute name on the panel object (e.g. "highpass_hz").
# advice is a list of (condition, recommended_range) strings.

# ── Package inventory (shown via the "What's under the hood?" button) ──

_PACKAGE_INFO = [
    ("librosa 0.11",
     "https://librosa.org/",
     "The main audio analysis library. Reads audio files, generates "
     "spectrograms, runs onset detection algorithms, and performs the "
     "harmonic/percussive separation (HPSS)."),
    ("NumPy 1.26",
     "https://numpy.org/",
     "The fundamental number-crunching engine. Nearly every calculation "
     "in the pipeline — from rhythm ratios to array maths — runs through "
     "NumPy under the hood."),
    ("pandas 3.0",
     "https://pandas.pydata.org/",
     "Handles all of the tabular data: reading and writing Excel "
     "workbooks, structuring beat-event tables, and computing per-file "
     "summary statistics."),
    ("matplotlib 3.8",
     "https://matplotlib.org/",
     "Produces all 2D plots — raster scatter plots, histograms, and "
     "spectrograms — as well as static PNG renders of the 3D flower."),
    ("SciPy 1.17",
     "https://scipy.org/",
     "Provides signal-processing essentials: digital filters, the "
     "Hilbert transform for sub-millisecond onset refinement, median "
     "filtering, cubic-spline interpolation for 3D surfaces, and "
     "Shannon entropy. Also powers every statistical test in the "
     "multi-species analyses (KS, Wilcoxon, Pearson, Spearman, …)."),
    ("soundfile 0.13",
     "https://github.com/bastibe/python-soundfile",
     "Low-level audio file I/O — reads and writes WAV, FLAC, and OGG "
     "files for the Audio Editor step."),
    ("noisereduce 3.0",
     "https://github.com/timsainb/noisereduce",
     "Implements spectral gating to subtract stationary background "
     "noise (hum, hiss, cicada chorus) from recordings before onset "
     "detection."),
    ("Plotly 6.6",
     "https://plotly.com/python/",
     "Powers the interactive 3D flower raster plots. Generates "
     "self-contained HTML files you can rotate, zoom, and explore in "
     "any web browser."),
    ("openpyxl 3.1",
     "https://openpyxl.readthedocs.io/",
     "The Excel engine behind the scenes — pandas uses it to read and "
     "write .xlsx workbooks with multiple sheets."),
    ("thebeat 0.3",
     "https://github.com/jellevanderwerff/thebeat",
     "An alternative rhythm-analysis toolkit. Provides Sequence objects "
     "for inter-onset-interval computation, compatible with thebeat's "
     "wider ecosystem."),
    ("PyQt6 6.11",
     "https://www.riverbankcomputing.com/software/pyqt/",
     "The desktop GUI framework that builds this entire application — "
     "windows, buttons, panels, and dialogs all come from PyQt6."),
    ("Praat-Parselmouth 0.4",
     "https://github.com/YannickJadoul/Parselmouth",
     "A Python interface to the Praat phonetics engine.  Powers the "
     "syllable_nuclei onset method (de Jong & Wempe, 2009) and "
     "extracts F0/pitch, intensity, and jitter metrics from speech."),
    ("OpenAI Whisper",
     "https://github.com/openai/whisper",
     "Open-source automatic speech recognition by OpenAI. Runs "
     "entirely on your machine — no internet, no API key, no cost, and "
     "your audio is never sent anywhere. Powers the whisper_words onset "
     "method for word-level speech rhythm analysis."),
    ("WhisperX 3.1",
     "https://github.com/m-bain/whisperX",
     "Extends Whisper with phoneme-level forced alignment (Bain et al., "
     "2023). Powers the whisperx_phonemes onset method, which computes "
     "Ramus et al. (1999) speech rhythm metrics (%V, ΔV, ΔC, rPVI-C, "
     "nPVI-V). Also runs fully offline."),
    ("PyTorch",
     "https://pytorch.org/",
     "The deep-learning framework that powers both Whisper and WhisperX "
     "models. Installed automatically as a dependency — no separate "
     "setup needed."),
    ("madmom",
     "https://github.com/CPJKU/madmom",
     "Audio signal processing library for Music Information Retrieval (MIR). "
     "Includes state-of-the-art deep-learning beat, downbeat and tempo "
     "tracking (Böck, Krebs & Widmer, 2016). Powers the madmom_beats "
     "onset method. Runs locally and offline."),
    ("torchcrepe",
     "https://github.com/maxrmorrison/torchcrepe",
     "PyTorch implementation of the CREPE neural-network pitch tracker "
     "(Kim et al. 2018). Provides highly accurate monophonic F0 estimation, "
     "especially for singing voices. Used by the standalone Pitch Tracker "
     "when set to 'crepe'. Runs locally and offline."),
    ("statsmodels 0.14",
     "https://www.statsmodels.org/",
     "The Python statistics toolkit. Powers the Generalized Linear "
     "Mixed Models (GLMM) analysis — Gaussian / Binomial / Poisson "
     "responses with random intercepts and slopes — and the Phylogenetic "
     "Generalized Least Squares (PGLS) regression via its GLS solver."),
    ("DendroPy 4.6",
     "https://dendropy.org/",
     "Phylogenetic computing library for Python. Reads Newick / NEXUS "
     "tree files and computes the variance–covariance matrix under "
     "Brownian motion that PGLS needs to correct species-level "
     "regressions for shared evolutionary history."),
]


class _PackageInfoDialog(QDialog):
    """Small pop-up listing every package and a brief description."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Packages Used by the Pipeline")
        self.setMinimumSize(520, 420)
        self.resize(560, 500)
        self.setStyleSheet(
            f"QDialog {{ background-color: {_BG}; color: {_TEXT}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(10)

        root.addWidget(_heading("Under the Hood", size=16))
        root.addWidget(_dim(
            "These are the open-source Python packages the pipeline relies "
            "on. You don't need to interact with any of them directly — "
            "the GUI handles everything — but it's good to know what's "
            "powering each part."
        ))
        root.addSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {_BG}; }}"
        )
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(8)

        for pkg_name, pkg_url, description in _PACKAGE_INFO:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background-color: {_BG_MID};"
                f"  border: 1px solid {_BORDER}; border-radius: 6px; }}"
            )
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(12, 8, 12, 8)
            card_lay.setSpacing(3)

            # Header row: package name + clickable link
            header_lay = QHBoxLayout()
            header_lay.setContentsMargins(0, 0, 0, 0)
            header_lay.setSpacing(8)
            name_lbl = QLabel(pkg_name)
            name_lbl.setFont(QFont("", 12, QFont.Weight.Bold))
            name_lbl.setStyleSheet(
                f"color: {_ACCENT}; background: transparent;"
            )
            header_lay.addWidget(name_lbl)
            header_lay.addStretch()
            link_lbl = QLabel(
                f'<a href="{pkg_url}" '
                f'style="color:{_ACCENT}; text-decoration:none;">'
                f'website ↗</a>'
            )
            link_lbl.setTextFormat(Qt.TextFormat.RichText)
            link_lbl.setOpenExternalLinks(True)
            link_lbl.setToolTip(pkg_url)
            link_lbl.setStyleSheet(
                "background: transparent; font-size: 11px;"
            )
            header_lay.addWidget(link_lbl)
            card_lay.addLayout(header_lay)

            desc_lbl = QLabel(description)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet(
                f"color: {_TEXT_DESC}; font-size: 12px;"
                f"  background: transparent; line-height: 1.4;"
            )
            desc_lbl.setTextFormat(Qt.TextFormat.PlainText)
            card_lay.addWidget(desc_lbl)

            lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(120)
        close_btn.setStyleSheet(
            f"QPushButton {{ background-color: {_BG_WIDGET}; color: {_TEXT}; "
            f"border-radius: 6px; padding: 7px 14px; border: 1px solid {_BORDER}; "
            f"font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {_BG_INPUT}; border-color: {_ACCENT}; }}"
        )
        close_btn.clicked.connect(self.accept)
        root.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)


STEP_INTRO = {
    0: (
        "Audio Editor",
        "The Audio Editor is a core processing step that <b>cleans up your "
        "raw recordings</b> so that only the sounds you care about survive."
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Optionally runs <b>Demucs</b> deep-learning source separation "
        "to isolate drums, bass, vocals, or other stems before any "
        "processing</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Selects a stereo channel and resamples all files to a consistent "
        "sample rate</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Removes unwanted frequencies with high-pass, low-pass, notch, "
        "and pre-emphasis filters</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Amplifies a target frequency band with bandpass boost</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Optionally separates harmonic (sustained tones) from percussive "
        "(sharp hits) using HPSS — with isolate <i>or</i> emphasis mode</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Subtracts constant background noise via spectral denoising, "
        "or amplifies signals above the noise floor with spectral "
        "enhancement</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Boosts quiet passages with dynamic compression and sharpens "
        "onset attacks with transient sharpening</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Silences quiet noise-only sections while leaving the timeline "
        "intact, so event timing stays accurate</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Normalizes output levels and trims edge silence for "
        "consistent, ready-to-analyse files</td></tr>"
        "</table>"
        "<br>"
        "Think of it like turning down the volume on the background noise "
        "in each recording, while leaving the interesting sounds at full "
        "volume."
        "<br><br>"
        "<b style='color:" + _ACCENT + ";'>Presets</b><br>"
        "If you know what type of recording you are working with, choose "
        "an <b>Audio Editor Preset</b> (e.g. 'birdsong', 'percussion_clean', "
        "'primate') to load expert-tuned defaults for all the settings "
        "below. A green <b>✱</b> annotation will appear under each "
        "affected setting explaining what was changed and why."
        "<br><br>"
        "<b style='color:" + _ACCENT + ";'>Output folders explained</b><br>"
        "Starting from your input folder (e.g. <code>audioFiles/</code>), "
        "the Audio Editor creates up to <b>5 output folders</b>:"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td><b>audioFiles_muted_clean/</b> — <i>always created.</i> This is "
        "the finished product: recordings with noise silenced and all "
        "processing applied. <b>This is the folder the rest of the "
        "pipeline uses.</b></td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td><b>audioFiles_rejected_noise/</b> — <i>always created.</i> "
        "Contains only the audio that was <i>removed</i> (the inverse of "
        "the clean output). Useful for auditing — play these files to check "
        "you haven't accidentally silenced real events.</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td><b>audioFiles_hpss_harmonic/</b> — <i>only created when HPSS "
        "is enabled.</i> The harmonic (sustained tone) layer of each "
        "recording, saved for manual inspection.</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td><b>audioFiles_hpss_percussive/</b> — <i>only created when HPSS "
        "is enabled.</i> The percussive (sharp transient) layer, also saved "
        "for inspection.</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td><b>audioFiles_demucs_stems/</b> — <i>only created when Demucs "
        "is enabled.</i> Contains the separated stems (e.g. drums.wav, "
        "bass.wav, vocals.wav, other.wav) for each input file.</td></tr>"
        "</table>"
        "<br>"
        "The HPSS folders are <b>diagnostic/auditing</b> outputs — they let "
        "you listen to the separated components to verify the decomposition "
        "worked correctly. The component you selected as the 'HPSS Target' "
        "is automatically fed into the cleaning pipeline; the folders just "
        "save both sides so you can check."
    ),
    1: (
        "Onset Finder",
        "The Onset Finder listens to each cleaned recording and "
        "<b>pinpoints the exact moment every distinct sound event "
        "begins</b> — each drum hit, bird chirp, or click. Those "
        "time-stamps are called <i>onsets</i>."
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Chooses from six different detection algorithms, each suited "
        "to different signal types</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Refines each onset to sub-millisecond precision using the "
        "Hilbert envelope</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Filters out false detections using sharpness and amplitude "
        "gates</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Computes rhythm metrics (rhythm ratio, nPVI, entropy, CV) "
        "from the inter-onset intervals</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Identifies stretches of steady, metronomic rhythm and exports "
        "them separately</td></tr>"
        "</table>"
        "<br>"
        "<b style='color:" + _ACCENT + ";'>Presets</b><br>"
        "Choose a <b>Detection Preset</b> to load expert-tuned parameters "
        "for your recording type. When active, a green <b>✱</b> annotation "
        "appears below each adjusted setting explaining the choice."
        "<br><br>"
        "<b style='color:" + _ACCENT + ";'>Input &amp; output</b><br>"
        "The Onset Finder reads <b>only</b> the audio folder you specify "
        "in the <i>'Input Audio Folder'</i> setting (by default "
        "<code>audioFiles_muted_clean/</code> — the output of the Audio "
        "Editor). "
        "It does <b>not</b> look at any other folder. You can verify "
        "this in the JSON config preview, where the <code>audio_folder</code> "
        "key shows the exact path being used."
        "<br><br>"
        "The output is a single Excel workbook with <b>three sheets</b>:"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>1.</td>"
        "<td><b>File Summaries</b> — one row per audio file with its "
        "settings, onset counts, and rhythm metrics for both the raw and "
        "stable datasets.</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>2.</td>"
        "<td><b>Dyadic Events (For Plots)</b> — every consecutive pair of "
        "inter-onset intervals (a 'dyad'), with computed rhythm ratio, "
        "cycle duration, and short/long intervals. This is the <i>"
        "raw</i> dataset — <b>all</b> detected events, no filtering.</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>3.</td>"
        "<td><b>Dyadic Events (Stable Rhythms)</b> — a <i>subset</i> of "
        "the raw dyads, keeping only those where the rhythm is locally "
        "consistent (the 'stable' dataset). Only present when "
        "'Extract Stable Rhythms' is enabled.</td></tr>"
        "</table>"
        "<br>"
        "<b style='color:" + _ACCENT + ";'>Raw vs Stable — what's the difference?</b><br>"
        "The <b>raw</b> dataset contains every dyad the pipeline detected "
        "— including irregular gaps, false positives that slipped through "
        "the gates, and one-off timing anomalies."
        "<br><br>"
        "The <b>stable</b> dataset applies an additional filter based on "
        "Roeske et&nbsp;al.&nbsp;(2020): for a dyad at position <i>n</i>, "
        "the algorithm checks whether interval <i>i<sub>n</sub></i> is "
        "similar to interval <i>i<sub>n+2</sub></i> (same position in the "
        "next cycle), and whether <i>i<sub>n+1</sub></i> is similar to "
        "<i>i<sub>n+3</sub></i>. 'Similar' means they differ by no more "
        "than the <b>Stable Rhythm Tolerance</b> (default 25%). If both "
        "checks pass, the dyad is marked as stable."
        "<br><br>"
        "In plain terms: stable rhythms are stretches where the performer "
        "(or animal) is keeping a <b>consistent beat pattern across "
        "consecutive cycles</b>. This filters out hesitations, one-off "
        "events, and noise-induced irregularities."
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td><b>Use raw</b> when you want to study the <i>overall</i> "
        "rhythmic profile, including irregular patterns. Good for "
        "characterising the full range of rhythmic behaviour.</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td><b>Use stable</b> when you want to study <i>structured, "
        "repeating</i> rhythmic behaviour — metronomic or near-metronomic "
        "passages. This is closer to what musicologists call 'beat-level' "
        "rhythm.</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td><b>Use both</b> (the default) to compare the two views side "
        "by side. If the raw and stable plots look very similar, the "
        "recording has consistently structured rhythm throughout. If they "
        "differ markedly, much of the recording is rhythmically "
        "irregular.</td></tr>"
        "</table>"
    ),
    2: (
        "Flower Raster Plots",
        "Raster plots give you <b>a visual picture of each recording's "
        "rhythmic structure</b>."
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>For every pair of consecutive inter-beat gaps, the shorter gap "
        "is plotted to the left and the longer gap to the right</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>The total cycle length sits on the vertical axis, giving a "
        "'flower'-like shape — hence the name</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>A combined corpus plot overlays all recordings for at-a-glance "
        "comparison</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>An optional interactive 3D version gives each recording its "
        "own petal that you can spin around in a web browser</td></tr>"
        "</table>"
        "<br>"
        "<b style='color:" + _ACCENT + ";'>raw/ vs stable/ output folders</b><br>"
        "The Flower Raster Plots and Histogram Generator both create a <b>raw/</b> and a <b>stable/</b> "
        "subfolder inside their output directory (e.g. "
        "<code>Raster_Plots/raw/</code> and "
        "<code>Raster_Plots/stable/</code>). These correspond directly "
        "to the two Excel sheets from the Onset Finder:"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td><b>raw/</b> — plots generated from the <i>Dyadic Events "
        "(For Plots)</i> sheet = <b>all</b> detected rhythm events</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td><b>stable/</b> — plots from the <i>Dyadic Events "
        "(Stable Rhythms)</i> sheet = only the rhythmically consistent "
        "subset</td></tr>"
        "</table>"
        "Which folders are created depends on the <b>Datasets to Plot</b> "
        "setting. By default it is set to <b>raw + stable</b>, so you get "
        "both. You can verify which data was used by checking the Excel "
        "sheet each folder draws from."
    ),
    3: (
        "Histogram Generator",
        "The Histogram Generator creates <b>bar charts showing how rhythm "
        "ratios are distributed</b> for each recording and across the "
        "whole dataset."
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>The rhythm ratio (r<sub>k</sub>) runs from 0 to 1, where 0.5 "
        "means perfectly even timing (isochrony)</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Reference lines at key ratios (1:1, 1:2, 1:3, etc.) help you "
        "see whether rhythms cluster at simple integer relationships</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>An isochronous shaded band highlights the region around "
        "r<sub>k</sub>&nbsp;=&nbsp;0.5</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Per-file and combined-corpus histograms are generated for both "
        "raw and stable-rhythm datasets</td></tr>"
        "</table>"
    ),
    4: (
        "nPVI Group Plot",
        "The nPVI Group Plot lets you <b>compare rhythmic variability "
        "across groups</b> of recordings using raincloud plots."
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Reads per-file nPVI scores from the Excel workbook produced "
        "by the Onset Finder</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Assigns recordings to groups using filename patterns, "
        "a mapping CSV, manual entry, or an Excel column</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Generates <b>raincloud plots</b> — a half-violin density "
        "curve, a box plot, and individual jittered data points — "
        "giving a rich visual summary of each group's nPVI distribution</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Useful for asking questions like 'Does species A have more "
        "regular rhythm than species B?' or 'Do recordings from site X "
        "differ from site Y?'</td></tr>"
        "</table>"
        "<br>"
        "<b style='color:" + _ACCENT + ";'>Group assignment methods</b><br>"
        "You have four ways to assign recordings to groups:"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>1.</td>"
        "<td><b>Filename pattern</b> — a regex that extracts the group "
        "name from each filename (e.g. the species prefix)</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>2.</td>"
        "<td><b>Mapping CSV</b> — a two-column CSV file mapping filenames "
        "to group names</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>3.</td>"
        "<td><b>Manual</b> — type filename → group pairs directly in "
        "the GUI</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>4.</td>"
        "<td><b>Excel column</b> — use a column already present in the "
        "input workbook</td></tr>"
        "</table>"
    ),
    # ── Multi-species rhythmic-landscape analyses (sidebar steps 8–17) ──
    5: (
        "Rhythm Ratio Distributions",
        "This analysis draws the <b>distribution of rhythm ratios "
        "(r<sub>k</sub>)</b> for each group on a single page, so you can "
        "see at a glance where each population sits on the 0–1 rhythm "
        "axis."
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Reads the <i>Dyadic Events</i> sheet produced by the Onset "
        "Finder and builds a histogram or density curve per group</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Shades the <b>isochronous band</b> around r = 0.5 so you "
        "can see how much of each group's mass sits on steady, even "
        "rhythms</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Draws dashed guide lines at classic musical ratios "
        "(1:2, 1:1, 2:1, etc.) so small-integer preferences are easy "
        "to spot</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Optionally overlays every group on one plot <i>and</i> "
        "saves one clean figure per group</td></tr>"
        "</table>"
        "<br>"
        "Think of it as the <i>'group fingerprint'</i> view: two groups "
        "with very similar rhythm profiles will have overlapping "
        "histograms; groups that favour different rhythmic styles will "
        "visibly separate."
    ),
    6: (
        "KS Test vs. Uniform Null",
        "The <b>Kolmogorov–Smirnov test</b> asks a simple question: "
        "<i>'Does this group's rhythm-ratio distribution differ from "
        "what you'd expect by chance?'</i>"
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Compares each group's r<sub>k</sub> distribution against a "
        "chosen <b>null distribution</b> — uniform noise, a bootstrap "
        "shuffle of your pooled data, or a custom CSV</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Reports the KS <i>D</i> statistic (the largest vertical gap "
        "between the two cumulative curves) and the associated p-value</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Corrects for running many tests at once using Bonferroni "
        "or Benjamini–Hochberg FDR, so 'significant' doesn't mean "
        "'significant by accident'</td></tr>"
        "</table>"
        "<br>"
        "A small p-value means the group clearly prefers some rhythm "
        "ratios over others — they are <b>not</b> drumming at random."
    ),
    7: (
        "Wilcoxon Isochrony Preference",
        "This analysis asks: <i>'Do recordings in this group favour "
        "even (isochronous) rhythms more than you'd expect by chance?'</i>"
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>For each recording, counts the fraction of rhythm ratios "
        "that fall inside the <b>isochronous band</b> (near r = 0.5)</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Runs a <b>one-sample Wilcoxon signed-rank test</b> on those "
        "fractions against a chance level (derived automatically from "
        "the band width, or set manually)</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Reports the test statistic, p-value, and direction for "
        "each group separately</td></tr>"
        "</table>"
        "<br>"
        "Unlike the KS test (which compares <i>shapes</i>), this one "
        "targets a single question — <i>'Are steady rhythms over-"
        "represented?'</i> — and is very interpretable."
    ),
    8: (
        "Lag-1 Autocorrelation",
        "The <b>lag-1 autocorrelation</b> measures whether each interval "
        "between beats tends to be <i>followed by a similar interval</i> "
        "(positive r), a <i>different interval</i> (negative r, i.e. "
        "short–long alternation), or is essentially independent (r ≈ 0)."
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>For each bout, computes Pearson correlation between "
        "consecutive inter-onset intervals</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Optional <b>detrending</b> removes slow speeding-up or "
        "slowing-down so you measure only short-term alternation, not "
        "tempo drift</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Returns confidence intervals via either the Fisher-z "
        "transform (fast, classical) or bootstrap resampling "
        "(robust, slower)</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Can either give you one correlation per bout or one pooled "
        "correlation per group</td></tr>"
        "</table>"
        "<br>"
        "<b style='color:" + _ACCENT + ";'>Interpreting r</b><br>"
        "Positive r suggests <i>tempo stability</i> (a slow beat tends "
        "to be followed by another slow beat). Negative r is the "
        "signature of <i>regular short–long alternation</i> (swing or "
        "limping rhythms). Near-zero r suggests the intervals are "
        "essentially independent — noisy or free-form timing."
    ),
    9: (
        "Tempo × Ratio Density Heatmap",
        "This is the <b>Roeske-style rhythmic landscape</b>: a 2-D "
        "density map showing where a group concentrates its beats in "
        "the joint space of <b>tempo</b> (or cycle duration) and "
        "<b>rhythm ratio</b> (r<sub>k</sub>)."
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>The X axis can be BPM, raw IOI in milliseconds, or "
        "logarithmic BPM — handy when tempos span orders of magnitude</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Choose between a crisp 2-D histogram and a smooth Gaussian "
        "KDE</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Normalise each group's heatmap independently (compare "
        "shapes) or use a joint colour scale (compare intensities)</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Save one heatmap per group plus a pooled cross-group map</td></tr>"
        "</table>"
        "<br>"
        "Bright ridges running horizontally indicate a preferred rhythm "
        "ratio used across many tempos. Bright vertical columns indicate "
        "a preferred tempo used with many ratios. Isolated bright blobs "
        "pinpoint specific (tempo, ratio) sweet spots — think of the "
        "'categorical attractors' from Roeske et al. (2020)."
    ),
    10: (
        "Multi-metric Raincloud Plots",
        "A <b>raincloud</b> combines three views into one picture: the "
        "smooth density shape of the data (half-violin), its summary "
        "statistics (boxplot), and every individual observation "
        "(jittered points)."
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Draws one raincloud figure <b>per metric</b> (nPVI, CV, "
        "entropy, …) — rather than squeezing all metrics onto one plot</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Optionally runs <b>pairwise comparison tests</b> (Mann–"
        "Whitney, Wilcoxon signed-rank, or KS) between groups and draws "
        "significance brackets at the top</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Applies Bonferroni or Benjamini–Hochberg correction to "
        "keep false-positive rates in check</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Horizontal or vertical orientation — vertical is standard, "
        "horizontal is handy when group names are long</td></tr>"
        "</table>"
        "<br>"
        "Think of it as an upgraded boxplot that never hides the "
        "underlying data."
    ),
    11: (
        "Permuted Discriminant Function Analysis (pDFA)",
        "pDFA asks: <i>'Can we reliably tell these groups apart using "
        "their rhythm measurements?'</i> — while honestly accounting for "
        "repeated measurements from the same individual."
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Trains a <b>linear discriminant analysis</b> (LDA) to "
        "predict group membership from rhythm predictors (nPVI, CV, "
        "entropy, bout duration, …)</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Reports classification accuracy with optional "
        "cross-validation: leave-one-out, k-fold, or leave-one-<i>group</i>-"
        "out for the most honest estimate when individuals are measured "
        "repeatedly</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Computes p-values using <b>restricted permutation</b> "
        "(Mundry & Sommer 2007): labels are shuffled at the repeated-"
        "measures unit level, so pseudoreplication can't inflate "
        "significance</td></tr>"
        "</table>"
        "<br>"
        "A significant pDFA means the groups have <b>rhythmically "
        "distinct profiles</b> — not just that you measured one "
        "individual many times and got lucky."
    ),
    12: (
        "Mantel / Partial Mantel Test",
        "The Mantel test compares <b>two distance matrices</b> and asks "
        "whether they agree: do <i>rhythmically similar</i> groups tend "
        "to also be <i>geographically close</i> (and/or "
        "<i>phylogenetically related</i>)?"
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Builds a rhythmic distance matrix from a single metric "
        "(nPVI, CV, entropy, mean IOI) or a standardised Euclidean "
        "distance across many metrics at once</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Builds a geographic distance matrix from lat/lon columns "
        "(great-circle kilometres via haversine) or reads a "
        "pre-computed CSV</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Optionally also builds a <b>phylogenetic</b> distance "
        "matrix from a Newick tree or a pre-computed CSV</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Runs plain <b>two-matrix Mantel</b>, or <b>partial "
        "Mantel</b> to control for a third matrix (e.g. 'rhythmic "
        "vs geographic, controlling for phylogeny')</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>p-values come from row+column permutation of the "
        "distance matrix — the correct null for distance data</td></tr>"
        "</table>"
        "<br>"
        "Useful for asking <i>'is rhythmic variation spatially "
        "structured?'</i> or <i>'does rhythm track relatedness?'</i>"
    ),
    13: (
        "GLMM for Rhythmic Responses",
        "A <b>Generalised Linear Mixed-effects Model</b> tests how "
        "multiple predictors (fixed effects) jointly explain a rhythmic "
        "measurement, while absorbing nuisance variance from repeated "
        "measurements with random effects."
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Predicts a <b>response</b> column (e.g. nPVI, CV) from any "
        "combination of <b>fixed effects</b> — modality, function, "
        "tempo, body mass, etc. — plus optional interactions</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Uses <b>random intercepts</b> for grouping variables "
        "(individual, species, site) to handle repeated measurements "
        "properly — values from the same individual aren't treated as "
        "independent</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Supports Gaussian, beta (proportions), binomial, and "
        "Poisson families — for continuous, bounded, yes/no, or count "
        "responses</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Runs an optional <b>likelihood-ratio test</b> against an "
        "intercept-only null, giving a single overall 'did my predictors "
        "help?' p-value</td></tr>"
        "</table>"
        "<br>"
        "This is the workhorse analysis when you have covariates to "
        "control for and want proper handling of nested/repeated data."
    ),
    14: (
        "Phylogenetic Generalized Least Squares (PGLS)",
        "PGLS is <b>regression for species-level data</b> that accounts "
        "for the fact that closely related species are not independent "
        "observations."
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Aggregates your data per species (or other taxonomic unit) "
        "and fits a linear regression of a rhythmic response against "
        "predictors such as body mass, ecology, preferred tempo, etc.</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Incorporates a <b>phylogenetic covariance matrix</b> — "
        "either a ready-made CSV or a matrix derived automatically from "
        "a Newick tree under Brownian motion</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Supports <b>Pagel's λ</b> scaling: the program can estimate "
        "how strongly the trait tracks the tree (profile likelihood), "
        "or you can fix λ — λ = 0 collapses PGLS to ordinary "
        "regression, λ = 1 is pure Brownian motion</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Reports coefficients, standard errors, confidence "
        "intervals and p-values for each predictor — corrected for the "
        "phylogenetic non-independence</td></tr>"
        "</table>"
        "<br>"
        "Use this when your unit of analysis is <i>species</i> rather "
        "than <i>recording</i>, and you want evolutionary "
        "non-independence handled properly."
    ),
    15: (
        "Association Rule Learning",
        "Association Rule Learning (ARL) is an <b>exploratory, "
        "hypothesis-generating</b> analysis that mines the per-file rhythm "
        "metrics table for <i>co-occurring feature combinations</i> — e.g. "
        "<i>\"files with <b>high nPVI</b> and <b>low CV of IOI</b> tend to "
        "come from <b>Group = Chimp</b>\"</i>."
        "<br><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Reads the <b>File Summaries</b> sheet produced by the Onset "
        "Finder — one row per recording — and treats each row as a "
        "'transaction' for the classic <b>Apriori</b> algorithm</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td><b>Discretises</b> every selected numeric metric (nPVI, "
        "entropy, CV, mean IOI, …) into a small number of ordered bins "
        "(e.g. <i>low / medium / high</i>). Each file then becomes a set "
        "of items like <code>nPVI=high</code>, <code>CV=low</code></td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Optionally adds a <b>Group=…</b> item per file (from filename "
        "pattern, CSV, manual list, or Excel column) so that mined rules "
        "can predict group membership directly</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Finds frequent itemsets and generates <b>association rules</b> "
        "<i>A ⇒ B</i> ranked by three classic measures: <b>support</b> "
        "(how common the pattern is), <b>confidence</b> (how often A "
        "implies B), and <b>lift</b> (how much more often than chance)</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Saves a ranked CSV of rules plus visual summaries: a top-N "
        "bar chart, a support-vs-confidence scatter, and an optional "
        "circular network diagram of the strongest rules</td></tr>"
        "</table>"
        "<br>"
        "<b style='color:" + _ACCENT + ";'>When to use this</b><br>"
        "ARL is a <i>descriptive</i> tool — it surfaces patterns you can "
        "then test rigorously with the confirmatory analyses above "
        "(GLMM, pDFA, Mantel, PGLS). Use it to answer open-ended "
        "questions like <i>\"what metric combinations consistently "
        "appear together?\"</i> or <i>\"what rhythm-bin profile "
        "distinguishes each group?\"</i> before committing to a "
        "specific model."
        "<br><br>"
        "<b style='color:" + _ACCENT + ";'>Key caveats</b><br>"
        "<table style='margin-left:8px; border-spacing:4px;'>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>ARL has <b>no built-in significance test</b> — a rule with "
        "high confidence in a small dataset can easily be spurious. Treat "
        "rules as leads to investigate, not conclusions.</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>Binning choices matter: too few bins hide structure, too "
        "many bins fragment the data. Start with <b>3 quantile bins</b>.</td></tr>"
        "<tr><td style='color:" + _ACCENT + "; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
        "<td>The number of rules can explode combinatorially. Raise "
        "<i>Min support</i> and <i>Min lift</i> until the result set is "
        "manageable.</td></tr>"
        "</table>"
    ),
}

# ---------- Step 1: Audio Editor settings ---------------------------------
_STEP1_SETTINGS = [
    # ── I/O ──
    ("input_folder", "Input Folder",
     "This is where the program looks for your raw audio recordings.  Point "
     "it at the folder that contains your .wav, .mp3, .flac, or .ogg files.",
     []),
    ("output_folder", "Output Folder",
     "Where the cleaned-up recordings will be saved.  By default the program "
     "creates an output folder next to your input folder, so you usually "
     "don't need to change this.",
     []),
    # ── Preset ──
    ("muter_preset", "Audio Editor Preset",
     "Pick a cleaning profile tailored to a specific type of recording.  "
     "Each preset pre-sets the filter, noise removal, and muting options "
     "so you don't have to dial every knob yourself.  Choose 'None' to "
     "set everything manually.\n\n"
     "When a preset is active, a green ✱ annotation appears below each "
     "adjusted setting explaining <i>what</i> was changed and <i>why</i>.",
     [("You're working with <b>birdsong</b>",
       "choose <b>birdsong</b> — high-pass at 500 Hz, HPSS harmonic, "
       "moderate denoising."),
      ("You have <b>clean percussion / drumming</b> recordings",
       "choose <b>percussion_clean</b> — minimal processing, no HPSS or "
       "denoising, preserves quiet hits."),
      ("You have <b>noisy percussion / drumming</b> recordings",
       "choose <b>percussion_messy</b> — HPSS percussive, hard separation, "
       "stronger denoising."),
      ("You're studying <b>primate</b> calls or drumming",
       "choose <b>primate</b> — 150 Hz cutoff, aggressive denoising for "
       "forest environments."),
      ("You have <b>insect</b> recordings (stridulations, clicks)",
       "choose <b>insect</b> — 1000 Hz cutoff, tight noise margin."),
      ("You're working with <b>whale / marine mammal</b> recordings",
       "choose <b>whale / marine mammal</b> — very low cutoff (20 Hz), "
       "harmonic HPSS, conservative denoising."),
      ("You have <b>frog / toad</b> recordings",
       "choose <b>amphibian</b> — 300 Hz cutoff, moderate denoising."),
      ("You're not sure or have <b>mixed</b> recordings",
       "choose <b>general / mixed</b> — balanced defaults that work "
       "reasonably well for most data."),
      ("You're analysing <b>human songs</b> and want to focus on the <b>singing voice</b>",
       "choose <b>music_vocal_isolation</b> — pre-emphasis for consonant clarity, "
       "HPSS harmonic to keep sustained vocals, compression for dynamic levelling. "
       "Best used after Demucs vocal-stem separation."),
      ("You're analysing <b>drums/percussion in music</b>",
       "choose <b>music_drums_isolation</b> — hard HPSS percussive split, "
       "aggressive transient sharpening to make hits pop. Best after Demucs drums-stem separation."),
      ("You're analysing a <b>full music mix</b> without source separation",
       "choose <b>music_full_mix</b> — minimal processing preserves the mix; pair with "
       "per_band onset detection which naturally separates frequency ranges."),
      ("You're analysing <b>group or choral singing</b>",
       "choose <b>music_group_singing</b> — compression levels all singers, "
       "HPSS harmonic keeps vocal content, gentle denoising for room/outdoor noise.")]),
    # ── Channel & Resampling ──
    ("channel", "Channel Selection",
     "If your recordings are stereo (two channels), this decides how to "
     "handle them.  'Mix' averages both channels together into a single "
     "mono track.  'Left' or 'Right' keeps only one channel — useful when "
     "one microphone picked up less background noise than the other.",
     [("Your recordings are <b>mono</b>",
       "leave at <b>mix</b> — it has no effect on mono files."),
      ("One channel is <b>cleaner</b> than the other",
       "choose <b>left</b> or <b>right</b> to use only the cleaner channel."),
      ("You're not sure",
       "leave at <b>mix</b> — blending both channels preserves all audio.")]),
    ("resample_hz", "Resample (Hz)",
     "Force all output files to a uniform sample rate.  Different recorders "
     "may capture at 22050, 44100, or 48000 Hz; resampling to a common rate "
     "ensures consistent FFT bin widths and timing precision across all your "
     "files.\n\nUse the <b>Enable resampling</b> checkbox to turn this on.",
     [("Your files have <b>different sample rates</b>",
       "enable resampling and set to <b>44100</b> for a standard, consistent rate."),
      ("All files already share the <b>same sample rate</b>",
       "leave the <b>Enable resampling</b> checkbox unchecked.")]),
    # ── High-pass filter ──
    ("highpass_hz", "High-Pass Filter (Hz)",
     "This removes low-frequency rumble — things like wind noise, traffic, "
     "or the hum of recording equipment.  You set a cutoff frequency and "
     "everything below it gets filtered out.\n\n"
     "Think of it like placing a barrier across the low end of the frequency "
     "spectrum: nothing below that barrier gets through.",
     [("You're working with <b>percussion or drumming</b>",
       "try <b>80</b> Hz — drums have useful low-frequency content you don't "
       "want to lose."),
      ("You have <b>general-purpose field recordings</b>",
       "try <b>200</b> Hz — a good all-round starting point."),
      ("You're analysing <b>birdsong</b>",
       "try <b>500</b> Hz — most bird vocalisations sit well above this."),
      ("You're studying <b>insects</b> (e.g. stridulation, clicks)",
       "try <b>1000</b> Hz — insect sounds tend to be very high-pitched."),
      ("Your recordings are <b>already clean</b> (studio/indoor)",
       "set to <b>0</b> to disable the filter entirely.")]),
    # ── Low-pass filter ──
    ("lowpass_hz", "Low-Pass Filter (Hz)",
     "The opposite of high-pass: this removes everything <i>above</i> a "
     "certain frequency.  Useful for suppressing high-pitched equipment "
     "hiss, insect interference, or ultrasonic artefacts while keeping "
     "the lower-frequency sounds you care about.\n\nUse the <b>Enable low-pass filter</b> checkbox to turn this on.",
     [("You're studying <b>whale or elephant</b> calls",
       "enable low-pass and try <b>2000</b> Hz — these species vocalise well below this."),
      ("You're analysing <b>birdsong</b> with high-pitched interference",
       "try <b>8000</b> Hz — brackets most birdsong frequencies."),
      ("You just want general cleanup",
       "try <b>10000</b> Hz — removes ultrasonic noise above 10 kHz."),
      ("You don't need it",
       "leave the <b>Enable low-pass filter</b> checkbox unchecked.")]),
    # ── Notch filter ──
    ("notch_freqs", "Notch Filter Frequencies (Hz)",
     "Surgically removes specific tonal interference — for example the 50 "
     "or 60 Hz hum from electrical wiring, or a constant tone from a nearby "
     "generator.  Enter one or more frequencies separated by spaces.\n\n"
     "Leave blank to disable.",
     [("You hear a <b>50 Hz or 60 Hz hum</b> (mains power)",
       "enter <b>50</b> (Europe/Asia/Africa) or <b>60</b> (Americas/Japan), "
       "plus harmonics like <b>100 120</b>."),
      ("You don't hear any specific tonal hum",
       "leave the <b>Enable notch filter</b> checkbox unchecked.")]),
    ("notch_q", "Notch Q Factor",
     "How narrow each notch is.  A high Q cuts a very precise sliver of "
     "frequency — just the offending tone.  A low Q cuts a wider band around "
     "it, useful when the interference wobbles.",
     [("You're removing <b>power hum</b> at a fixed frequency",
       "try <b>30</b> — a very narrow notch."),
      ("The interference <b>wobbles or has sidebands</b>",
       "try <b>10–15</b> — a wider notch to catch the spread.")]),
    # ── Pre-emphasis ──
    ("pre_emphasis", "Pre-emphasis Coefficient",
     "Boosts high frequencies to compensate for the natural high-frequency "
     "roll-off caused by distance between the microphone and the sound "
     "source.  Like adjusting the 'treble' dial on a stereo.\n\n"
     "Use the <b>Enable pre-emphasis</b> checkbox to turn this on.",
     [("Your recordings were made <b>at a distance</b> and sound muffled",
       "enable pre-emphasis and try <b>0.97</b> — the standard value for speech/vocalization."),
      ("Your recordings are <b>close-range and already bright</b>",
       "leave the <b>Enable pre-emphasis</b> checkbox unchecked.")]),
    # ── Bandpass Boost ──
    ("bandpass_boost", "Bandpass Boost",
     "Instead of removing unwanted frequencies, this turns <i>up</i> the "
     "volume on a specific frequency range where your species of interest "
     "actually sings or calls.  Like focusing a spotlight on the part of "
     "the audio spectrum you care about most.",
     [("You know the <b>frequency range</b> your species uses",
       "enable this and set the low/high boundaries to bracket that range."),
      ("You're not sure of the target frequency range",
       "leave this <b>off</b> until you've inspected a spectrogram.")]),
    ("boost_low_hz", "Boost Low (Hz)",
     "The lower edge of the frequency band to amplify.  Set this to just "
     "below the fundamental frequency of your target species' vocalisation.",
     []),
    ("boost_high_hz", "Boost High (Hz)",
     "The upper edge of the frequency band to amplify.  Set this to just "
     "above the highest harmonic you want to capture.",
     []),
    ("boost_gain_db", "Boost Gain (dB)",
     "How much louder to make the target band.  3 dB is subtle; 6 dB is "
     "moderate; 12 dB is very strong and may cause clipping if you don't "
     "also enable normalization.",
     [("You want a <b>gentle nudge</b>",
       "try <b>3</b> dB."),
      ("A <b>moderate boost</b>",
       "try <b>6</b> dB (the default)."),
      ("A <b>strong boost</b> (combine with normalization)",
       "try <b>12</b> dB.")]),
    # ── HPSS ──
    ("hpss_enabled", "HPSS (Harmonic-Percussive Separation)",
     "This separates your audio into two layers: <b>harmonic</b> (smooth, "
     "sustained tones like a flute or a steady call) and <b>percussive</b> "
     "(sharp, punchy transients like a drum hit or a click).\n\n"
     "This is useful when the sounds you care about belong to only one of "
     "those categories, and the other category is getting in the way.",
     [("You want to detect <b>sharp hits or clicks</b> (percussion, "
       "woodpecker taps, chimpanzee buttress drumming)",
       "enable HPSS and keep the <b>percussive</b> component."),
      ("You want to detect <b>tonal calls or melodic phrases</b>",
       "enable HPSS and keep the <b>harmonic</b> component."),
      ("Your recordings contain <b>only one type of sound</b>",
       "you can leave HPSS <b>off</b> — it won't help if there's nothing "
       "to separate.")]),
    ("hpss_target", "HPSS Target Component",
     "After the separation, which layer do you want to keep?  "
     "'Percussive' keeps the punchy sounds, 'Harmonic' keeps the smooth "
     "sounds, 'Both' keeps everything (useful if you just want the "
     "separation for auditing).",
     [("You're focused on <b>rhythmic timing</b> from hits, taps, or clicks",
       "choose <b>percussive</b>."),
      ("You're focused on <b>melodic or tonal timing</b>",
       "choose <b>harmonic</b>.")]),
    ("hpss_margin", "HPSS Margin (Separation Strictness)",
     "Controls how strictly the two layers are split.  A low number blends "
     "them gently (some sounds end up in both layers); a high number enforces "
     "a hard split with no overlap.",
     [("You're not sure or want a safe start",
       "try <b>2.0</b> — a moderate middle ground."),
      ("Sounds are clearly either tonal or percussive",
       "try <b>4.0</b> for a hard, clean separation."),
      ("Sounds are ambiguous or overlap in character",
       "try <b>1.0</b> — a softer split that doesn't force "
       "borderline sounds into one layer.")]),
    ("hpss_emphasis_db", "HPSS Emphasis (dB)",
     "Instead of throwing away one layer entirely (isolation), this option "
     "keeps the full signal and just <i>turns up</i> the target component by "
     "the specified dB.  Like raising one singer's microphone in a duet "
     "instead of muting the other singer.\n\n"
     "Set to 0 for classic isolation (discard non-target).",
     [("You want to <b>fully isolate</b> the target component",
       "leave at <b>0</b> — classic mode."),
      ("You want to keep context but <b>highlight</b> the target",
       "try <b>3–6</b> dB for gentle emphasis."),
      ("You want the target to <b>dominate strongly</b>",
       "try <b>9+</b> dB.")]),
    # ── Spectral denoising ──
    ("spectral_denoise", "Spectral Denoising",
     "This learns what the constant background noise in each recording "
     "sounds like (air conditioning, cicadas, hiss) and subtracts it.  "
     "It works at the frequency level, so it can remove noise that a "
     "simple volume-based approach would miss.",
     [("Your recordings have a <b>constant background hum or buzz</b>",
       "turn this <b>on</b> — it's designed exactly for this."),
      ("Your recordings are <b>clean</b> with little background noise",
       "leave it <b>off</b> — it could slightly degrade quality for "
       "no benefit.")]),
    ("denoise_strength", "Denoising Strength",
     "How aggressively the program erases that background noise.  A gentle "
     "setting plays it safe; a more aggressive one removes more noise but "
     "may start eating into the sounds you want to keep.",
     [("You want a safe, conservative clean",
       "try <b>1.0</b>."),
      ("Moderate noise levels (general fieldwork)",
       "try <b>1.5</b> (the default)."),
      ("Heavy constant noise (loud cicadas, strong hum)",
       "try <b>2.0</b> — but listen to the result to make sure it hasn't "
       "distorted your target sounds.")]),
    # ── Spectral enhancement ──
    ("spectral_enhance", "Spectral Enhancement",
     "The positive counterpart to spectral denoising.  Instead of "
     "<i>subtracting</i> the background, this <i>amplifies</i> sounds "
     "that rise above the noise floor — bird calls, percussion hits, "
     "anything that stands out from the constant backdrop.\n\n"
     "Like a spotlight that automatically finds the performers on a "
     "dark stage.",
     [("You want to make target sounds <b>louder</b> without removing noise",
       "enable this and set enhance factor to <b>2.0</b>."),
      ("You're already using spectral denoising",
       "you can use both together — denoising subtracts noise, enhancement "
       "amplifies signal.")]),
    ("enhance_factor", "Enhance Factor",
     "How bright the spotlight is.  1.0 does nothing; 2.0 doubles the "
     "contrast between signal and background; 4.0 really makes target "
     "sounds pop.",
     [("A <b>moderate boost</b>",
       "try <b>2.0</b> (the default)."),
      ("A <b>strong boost</b>",
       "try <b>4.0</b> — but watch for artefacts.")]),
    # ── Dynamic compression ──
    ("compress", "Dynamic Compression",
     "Instead of silencing quiet parts, this makes them <i>louder</i> — "
     "bringing distant, faint calls closer to the volume of nearby ones.  "
     "Like automatic gain control on a phone call: when someone whispers, "
     "the system turns the volume up automatically.\n\n"
     "This is the positive counterpart to amplitude muting.",
     [("You have calls at <b>varying distances</b> and want even volume",
       "enable this, try ratio <b>3.0</b> and threshold <b>-30</b>."),
      ("Your recordings are already <b>consistent in volume</b>",
       "leave this <b>off</b>.")]),
    ("compress_ratio", "Compression Ratio",
     "How aggressively the program evens out the volume.  A gentle ratio "
     "just nudges quiet sounds up a bit; heavy ratio squashes everything "
     "toward the same level.",
     [("You want <b>gentle</b> levelling",
       "try <b>2.0</b>."),
      ("A <b>moderate</b> approach",
       "try <b>3.0</b> (the default)."),
      ("You need <b>heavy</b> compression",
       "try <b>6.0+</b> — but the result may sound unnatural.")]),
    ("compress_threshold_db", "Compression Threshold (dBFS)",
     "Sounds quieter than this level get boosted; anything louder is left "
     "alone.  Like a volume floor that catches sounds before they get "
     "too quiet.",
     [("For most field recordings",
       "try <b>-30</b> dBFS (the default)."),
      ("For cleaner recordings",
       "try <b>-20</b> dBFS — more conservative.")]),
    # ── Transient sharpening ──
    ("sharpen_transients", "Transient Sharpening",
     "Boosts the very first moment of each detected onset, making attacks "
     "crisper and more prominent.  This is the positive counterpart to "
     "crossfade smoothing — it sharpens the edge of each sound event "
     "rather than softening it.\n\n"
     "Helps the downstream onset finder detect beats more reliably.",
     [("Your target sounds have <b>soft, gradual onsets</b>",
       "enable this to give each onset a crisper 'edge'."),
      ("Your sounds already have <b>sharp, crisp attacks</b>",
       "leave this <b>off</b> — sharpening may over-emphasise them.")]),
    ("sharpen_gain_db", "Sharpen Gain (dB)",
     "How much extra volume each onset attack gets.  3 dB is subtle; "
     "6 dB is a noticeable boost; 12+ makes onsets dramatically louder.",
     [("For a <b>subtle</b> sharpening",
       "try <b>3</b> dB."),
      ("A <b>noticeable boost</b>",
       "try <b>6</b> dB (the default).")]),
    ("sharpen_attack_ms", "Attack Window (ms)",
     "How long the attack boost lasts, starting at each onset.  A short "
     "window boosts just the very first crack; a longer window extends "
     "the emphasis further into the sound.",
     [("For <b>very sharp</b> transients (clicks, taps)",
       "try <b>5</b> ms."),
      ("For <b>natural</b> attack envelopes",
       "try <b>15</b> ms (the default).")]),
    # ── Thresholding ──
    ("auto_threshold", "Adaptive Threshold",
     "When enabled, the program listens to the quietest parts of each "
     "recording and automatically estimates what counts as 'noise'.  "
     "This means you don't have to set a threshold manually — the "
     "program adapts to each file.",
     [("Your recordings vary in noise level from file to file",
       "turn this <b>on</b> — it adapts automatically per file."),
      ("All your recordings have similar noise characteristics",
       "you can leave it <b>off</b> and use a fixed threshold instead "
       "for consistency.")]),
    ("db_threshold", "Fixed dB Threshold",
     "If Adaptive Threshold is off, this is where you draw the line "
     "manually: anything quieter than this many decibels below the peak "
     "is treated as noise and silenced.",
     [("Clean studio recordings",
       "try <b>20—25</b> dB."),
      ("General-purpose or moderate-quality recordings",
       "try <b>30</b> dB (the default)."),
      ("Noisy field recordings",
       "try <b>35—40</b> dB — this keeps the threshold low so you "
       "don't accidentally mute real sounds.")]),
    ("noise_margin", "Adaptive Noise Margin (dB)",
     "When Adaptive Threshold is on, this is how far above the estimated "
     "noise floor the program places the 'keep or mute' line.  A narrow "
     "margin mutes aggressively; a wide margin preserves more of the "
     "quieter real sounds.",
     [("You want aggressive noise removal",
       "try <b>4</b> dB."),
      ("A balanced approach",
       "try <b>6</b> dB (the default)."),
      ("You'd rather keep borderline sounds",
       "try <b>10</b> dB — safer but leaves more residual noise.")]),
    ("save_profile", "Save Noise Profile",
     "Saves a small JSON report alongside each cleaned file, documenting "
     "what the program estimated as noise and where it drew the threshold.  "
     "Handy for auditing or troubleshooting.",
     []),
    ("fade_ms", "Crossfade Duration (ms)",
     "When the program mutes a noisy section, this controls how quickly the "
     "volume fades out (and back in).  A gentle fade prevents audible clicks "
     "at the boundaries — which is important because hard silence edges can "
     "trigger false onset detections in the Onset Finder.",
     [("In most cases",
       "<b>5 ms</b> (the default) works well — short enough to be "
       "invisible, long enough to avoid artefacts.")]),
    # ── Normalization & Trimming ──
    ("normalize", "Normalize",
     "After all processing, this adjusts the overall volume of every output "
     "file so they're all at the same loudness level.  'Peak' scales "
     "the loudest sample to the target; 'RMS' scales by average energy "
     "(better for perceived-loudness consistency).\n\n"
     "Set to 'None' to skip normalization.",
     [("You want all files at <b>consistent loudness</b>",
       "choose <b>rms</b> — matches perceived volume across files."),
      ("You just want to prevent <b>clipping</b>",
       "choose <b>peak</b>."),
      ("Loudness doesn't matter for your analysis",
       "leave at <b>None</b>.")]),
    ("normalize_target_db", "Normalization Target (dBFS)",
     "What loudness level to normalize to.  -1.0 makes the audio almost "
     "as loud as possible without distortion; -3.0 leaves more headroom.",
     [("For most purposes",
       "try <b>-1.0</b> (the default)."),
      ("You need extra headroom (e.g. further downstream processing)",
       "try <b>-3.0</b>.")]),
    ("trim_silence", "Trim Silence",
     "Snips off dead silence at the very start and end of each output "
     "file — like trimming blank margins from a page.  Internal timing "
     "is preserved.",
     [("Your recordings have <b>long silent pre-roll / post-roll</b>",
       "enable this to clean up the edges."),
      ("Timing relative to file start matters for your analysis",
       "leave this <b>off</b> to preserve original alignment.")]),
    ("trim_threshold_db", "Trim Threshold (dB)",
     "How quiet the edges need to be to count as 'silence' and get "
     "trimmed.  A high number trims more aggressively.",
     [("You want <b>conservative</b> trimming (only very quiet edges)",
       "try <b>40</b> dB (the default)."),
      ("You want <b>aggressive</b> trimming",
       "try <b>20–30</b> dB.")]),
]

# ---------- Step 2: Onset Finder settings ---------------------------------
_STEP2_SETTINGS = [
    # ── I/O ──
    ("audio_folder", "Input Folder (cleaned audio)",
     "Point this at the folder of cleaned recordings — the ones the Audio "
     "Editor produced.",
     []),
    ("output_excel", "Output Excel Workbook",
     "Where the program writes its results — a spreadsheet listing every "
     "detected beat event and all computed rhythm metrics.",
     []),
    # ── Engine & preset ──
    ("engine", "Extractor Engine",
     "Which beat-detection engine to use.  <b>Standard</b> is the full-featured "
     "engine with all the analysis bells and whistles.  <b>thebeat</b> is a "
     "leaner alternative that exports results compatible with the thebeat "
     "rhythm-analysis toolkit.",
     [("You want the most comprehensive analysis",
       "use <b>standard</b>."),
      ("You're importing results into thebeat for further analysis",
       "use <b>thebeat</b>.")]),
    ("preset", "Detection Preset",
     "Pre-tuned configurations optimised for different data types.  Choosing "
     "a preset automatically adjusts the onset detection sensitivity, noise "
     "filters, and clustering window to values that work well for that kind "
     "of sound.  Set to 'None' if you want full manual control.\n\n"
     "When a preset is active, a green ✱ annotation appears below each "
     "adjusted setting explaining <i>what</i> was changed and <i>why</i>.",
     [("You're analysing <b>birdsong</b>",
       "try the <b>birdsong</b> preset."),
      ("You're analysing <b>clean percussion or drumming</b>",
       "try the <b>percussion_clean</b> preset — extra-sensitive to quiet hits."),
      ("You're analysing <b>noisy percussion or drumming</b>",
       "try the <b>percussion_messy</b> preset — stricter gates for noisy recordings."),
      ("You're analysing <b>primate vocalisations or drumming</b>",
       "try the <b>primate</b> preset."),
      ("You're analysing <b>insect sounds</b>",
       "try the <b>insect</b> preset."),
      ("You're analysing <b>whale or marine mammal</b> recordings",
       "try the <b>whale / marine mammal</b> preset."),
      ("You're analysing <b>frog or toad</b> recordings",
       "try the <b>amphibian</b> preset."),
      ("You have <b>mixed or unknown</b> recordings",
       "try the <b>general / mixed</b> preset."),
      ("You're analysing <b>human speech</b> and want syllable-level rhythm",
       "try the <b>speech_syllable</b> preset — uses Praat's intensity-peak "
       "algorithm (de Jong & Wempe, 2009) to detect syllable nuclei. Also "
       "extracts F0 (pitch) and prosody metrics. No internet needed."),
      ("You're analysing <b>human speech</b> and want word-level rhythm",
       "try the <b>speech_word</b> preset — uses OpenAI's Whisper model "
       "(runs locally, completely free) to transcribe speech and extract "
       "word onset times. Also exports .txt and .srt transcripts."),
      ("You're analysing <b>human speech</b> and want phoneme-level metrics",
       "try the <b>speech_phoneme</b> preset — uses WhisperX forced alignment "
       "(Bain et al., 2023) to get precise phoneme timestamps, then "
       "computes Ramus et al. (1999) rhythm metrics: %%V, ΔV, ΔC, rPVI-C, nPVI-V."),
      ("You're analysing <b>human speech</b> acoustically (no extra packages)",
       "try the <b>speech_acoustic</b> preset — detects syllable-level "
       "amplitude onsets using the standard energy-based methods."),
      ("You're analysing <b>music or songs</b> and want beat/tempo",
       "try the <b>music_beat_tracking</b> preset — uses madmom's deep-learning "
       "RNN + DBN beat tracker (Böck et al., 2016) to find the metrical pulse. "
       "Also estimates tempo (BPM) and can detect downbeats."),
      ("You want to fine-tune everything yourself",
       "set to <b>None</b>.")]),
    # ── Onset detection core ──
    ("onset_method", "Onset Detection Method",
     "The core algorithm that identifies when a sound event begins.  Each "
     "method has different strengths:\n\n"
     "• <b>adaptive_hp</b> — The default and most robust for noisy data.  "
     "Uses a smoothing filter to estimate the background trend and flags "
     "peaks above it.\n"
     "• <b>librosa</b> — Simple spectral flux.  Fast, good for clean audio.\n"
     "• <b>moving_median</b> — Compares loudness to a running median.  "
     "Resilient to isolated loud artefacts.\n"
     "• <b>superflux</b> — Enhanced spectral flux that handles vibrato well.\n"
     "• <b>cfar</b> — Radar-inspired; great for non-stationary noise.\n"
     "• <b>per_band</b> — Splits audio into frequency bands and votes; good "
     "when energy is concentrated in a specific range.\n\n"
     "<b>Speech-specific methods</b> (for human speech and language):\n\n"
     "• <b>syllable_nuclei</b> — Detects syllable centres using Praat's "
     "intensity-peak algorithm (de Jong & Wempe, 2009). Also extracts "
     "F0/pitch metrics (mean, std, range, jitter) and intensity statistics. "
     "Runs entirely offline via the Praat engine — no internet or API key needed.\n"
     "• <b>whisper_words</b> — Uses OpenAI's open-source Whisper model to "
     "transcribe speech and extract word-level onset times. The model runs "
     "100%% locally on your machine — completely free, no API key, no data "
     "sent to OpenAI. Can export timestamped transcripts (.txt and .srt) "
     "and Praat TextGrid files.\n"
     "• <b>whisperx_phonemes</b> — Uses WhisperX (Bain et al., 2023) for "
     "phoneme-level forced alignment, then computes speech rhythm metrics "
     "from Ramus et al. (1999): %%V (proportion of vowel intervals), ΔV and "
     "ΔC (variability of vowel/consonant durations), rPVI-C (raw Pairwise "
     "Variability Index for consonants), and nPVI-V (normalised PVI for "
     "vowels — Grabe & Low, 2002). Also runs locally and offline.\n"
     "• <b>madmom_beats</b> — Deep-learning beat tracker (Böck, Krebs & Widmer, "
     "2016) that finds the metrical pulse — i.e. the underlying beat that "
     "listeners would tap to — rather than individual acoustic onsets. Uses "
     "a Recurrent Neural Network + Dynamic Bayesian Network. Also estimates "
     "tempo (BPM) and can detect downbeats (bar-level '1'). Best for music "
     "and songs. Runs locally and offline.",
     [("You're unsure or have noisy field recordings",
       "start with <b>adaptive_hp</b> — the safest default."),
      ("Clean recordings with sharp attacks",
       "try <b>librosa</b> — simple and fast."),
      ("Pitched content with vibrato (e.g. tonal bird calls)",
       "try <b>superflux</b> — it's designed to handle frequency wobble."),
      ("Noise changes over time (shifting wind, moving animals)",
       "try <b>cfar</b> — it adapts its noise estimate continuously."),
      ("Sounds concentrated in a particular frequency range",
       "try <b>per_band</b> — it finds beats in each frequency band "
       "independently."),
      ("Analysing <b>human speech</b> at the syllable level",
       "use <b>syllable_nuclei</b> — based on de Jong & Wempe (2009)."),
      ("Analysing <b>human speech</b> at the word level",
       "use <b>whisper_words</b> — free, offline Whisper ASR."),
      ("Analysing <b>speech rhythm</b> at the phoneme level",
       "use <b>whisperx_phonemes</b> — Ramus et al. (1999) metrics."),
      ("Analysing <b>music or songs</b> for beat/tempo",
       "use <b>madmom_beats</b> — deep-learning beat tracker (Böck et al. 2016).")]),
    ("onset_delta", "Peak-Picking Sensitivity (delta)",
     "How prominent a sound spike needs to be before the detector flags it "
     "as a beat.  A lower threshold catches subtler events; a higher one "
     "is pickier and only flags obvious peaks.",
     [("You're missing real beats (too few detected)",
       "try lowering to <b>0.03—0.05</b>."),
      ("You're getting too many false detections",
       "try raising to <b>0.10—0.15</b>.")]),
    ("onset_hop", "Hop Length (samples)",
     "How many audio samples to advance between each analysis frame.  Fewer "
     "samples = finer time resolution but slower processing.",
     [("You need fine timing resolution",
       "use <b>128</b>."),
      ("General purpose",
       "use <b>256</b> (the default, a good balance)."),
      ("Speed matters more than precision",
       "use <b>512</b>.")]),
    ("onset_backtrack", "Backtrack to Energy Minimum",
     "After finding a peak, should the program look backwards to find where "
     "the sound energy truly started rising?  Can improve accuracy for clean "
     "recordings but may overshoot on noisy ones.",
     [("Clean recordings with well-defined attacks",
       "try turning this <b>on</b>."),
      ("Noisy field recordings",
       "leave this <b>off</b> (the default) — backtracking can latch onto "
       "noise.")]),
    ("min_ioi", "Minimum Inter-Onset Interval (ms)",
     "The shortest allowed gap between two consecutive beats.  If two "
     "detections land closer together than this, the later one is discarded.",
     [("Analysing <b>insect clicks</b> (very rapid)",
       "try <b>10</b> ms."),
      ("Analysing <b>birdsong</b>",
       "try <b>12</b> ms."),
      ("Analysing <b>human percussion</b>",
       "try <b>30</b> ms."),
      ("Analysing <b>primate calls</b>",
       "try <b>40</b> ms.")]),
    # ── Refinement ──
    ("refine_enabled", "Sub-Millisecond Refinement",
     "After the initial rough detection, a second pass zooms in on each "
     "beat to pinpoint the exact onset with sub-millisecond precision.  "
     "This uses the Hilbert envelope — a mathematical technique for "
     "extracting the instantaneous amplitude of a signal.",
     [("You need precise timing measurements",
       "keep this <b>on</b> (recommended for rhythm analysis)."),
      ("You just need approximate onset counts",
       "you can turn it <b>off</b> to speed things up marginally.")]),
    ("refine_window", "Refinement Window (ms)",
     "How wide the zoom-in search window is around each coarse onset.",
     [("Most cases",
       "<b>10</b> ms (the default) provides a good balance.")]),
    ("refine_energy_gate", "Refinement Energy Gate",
     "If the refined position lands on a very quiet spot, it probably found "
     "noise rather than a real onset.  This threshold says 'ignore the "
     "refined result if the energy there is too faint.'  Set to 0 to disable.",
     []),
    # ── Sharpness gate ──
    ("sharpness_gate", "Sharpness Gate",
     "Real beat events start with a sharp rise in energy.  This filter "
     "measures how 'punchy' each detected onset is and discards ones that "
     "rise too gradually — they're probably not genuine onsets.\n\n"
     "The value is a fraction of the sharpest attack in the file.  Set to "
     "0 to disable the filter entirely.",
     [("Your target sounds have <b>sharp, crisp attacks</b> (drums, clicks)",
       "try <b>0.1—0.3</b> to filter out soft false positives."),
      ("Your target sounds have <b>softer, more gradual attacks</b>",
       "set to <b>0</b> or very low to avoid filtering out real events.")]),
    ("sharpness_window", "Sharpness Window (ms)",
     "How wide a time window to use when measuring the rise speed of each "
     "onset.",
     []),
    # ── Column Comments ──
    ("add_column_comments", "Add Column Header Comments",
     "When enabled, adds explanatory comments to every column header in "
     "the output Excel workbook. Hover over a column header in Excel to "
     "read a plain-language description of what that column contains — "
     "useful for collaborators or when revisiting data months later.",
     [("You share Excel files with others or want self-documenting output",
       "keep this <b>on</b> (the default)."),
      ("You post-process the Excel file with scripts that choke on comments",
       "turn this <b>off</b>.")]),
    # ── Outputs ──
    ("create_spectrograms", "Generate Spectrograms",
     "Produces a colour 'heat map' of each recording's audio with markers "
     "showing where every detected beat falls.  These are excellent for "
     "visually verifying whether the detections are landing in the right "
     "places.",
     [("You're running the pipeline for the first time on new data",
       "turn this <b>on</b> — visual checking is invaluable."),
      ("You've already validated your settings and are batch-processing",
       "you can turn this <b>off</b> to save time.")]),
    ("spectrogram_chunk_enabled", "Chunk Spectrograms",
     "For long recordings, splits each spectrogram into shorter segments "
     "so you can see the detail up close.",
     []),
    ("spectrogram_chunk_seconds", "Chunk Duration (seconds)",
     "How many seconds of audio each spectrogram segment covers.",
     [("Recordings under 30 seconds",
       "you don't need chunking."),
      ("Recordings 1–5 minutes",
       "try <b>30</b> seconds per chunk."),
      ("Recordings over 5 minutes",
       "try <b>60</b> seconds per chunk.")]),
    ("create_labels", "Export Audacity Labels",
     "Writes a text file for each recording that Audacity (a free audio "
     "editor) can import.  This lets you listen to each detected onset "
     "and verify it by ear.",
     [("You want to do any manual checking",
       "keep this <b>on</b> — it's lightweight and very useful.")]),
    # ── Clustering ──
    ("cluster_onsets", "Onset Clustering",
     "If the detector flags the same event multiple times (just slightly "
     "apart), this merges those duplicate detections into one.",
     [("You're analysing <b>ensemble recordings</b> (multiple people "
       "or animals playing together)",
       "turn this <b>on</b> — very helpful for handling near-simultaneous "
       "hits."),
      ("You're analysing <b>solo performances</b>",
       "it's still useful to leave on as a safety net.")]),
    ("cluster_window", "Cluster Window (ms)",
     "How close together do two detections need to be before they're merged "
     "into one.",
     [("Multi-player drumming ensembles",
       "use <b>25</b> ms (the value from the Roeske et al. methodology)."),
      ("Solo recordings",
       "a smaller value like <b>10—15</b> ms is usually sufficient.")]),
    # ── Stable rhythms ──
    ("filter_stable", "Extract Stable Rhythms",
     "Looks for stretches where rhythm is very consistent — like a steady "
     "metronome — and exports those separately.  This filtered dataset can "
     "reveal structured rhythmic behaviour that would otherwise be hidden "
     "by messy, irregular sections.",
     [("You're studying rhythmic regularity or looking for isochrony",
       "turn this <b>on</b> — it's one of the most informative features "
       "of the pipeline."),
      ("You only care about all onsets regardless of regularity",
       "you can leave it off, but it costs virtually nothing to have on.")]),
    ("stable_tolerance", "Stable Rhythm Tolerance",
     "How similar consecutive intervals need to be to qualify as 'stable'.  "
     "Lower = stricter (must be very regular), higher = more lenient.",
     [("You want to identify strictly isochronous sections",
       "try <b>0.15—0.20</b>."),
      ("A moderate definition of stability",
       "use <b>0.25</b> (the default, matching the Roeske et al. paper)."),
      ("You want a generous definition of regularity",
       "try <b>0.30—0.35</b>.")]),
    # ── High-pass (Onset Finder) ──
    ("apply_highpass", "Built-In High-Pass Filter",
     "A redundant high-pass filter inside the onset finder.  Usually "
     "unnecessary because the Audio Editor already filtered the audio.  Only enable "
     "this if you're skipping the Audio Editor and feeding in raw audio.",
     [("You ran the Audio Editor",
       "leave this <b>off</b>."),
      ("You're skipping the Audio Editor",
       "turn this <b>on</b> and set the cutoff.")]),
    # ── Amplitude gate ──
    ("amplitude_gate", "Amplitude Gate",
     "Discards detections that occur during very quiet passages — they're "
     "likely false positives from near-silence.  The value is a fraction "
     "of the file's peak loudness.  Set to 0 to disable.",
     [("Noisy recordings with quiet passages",
       "try <b>0.02—0.05</b>."),
      ("Clean recordings",
       "set to <b>0</b> — you probably don't need this.")]),

    # ── Pitch Tracker ──
    ("pitch_tracker", "Pitch Tracker Method",
     "Standalone F0 pitch tracker that runs after onset detection.  "
     "Extracts fundamental-frequency metrics (mean, std, min, max, range, "
     "jitter, intensity) independently of the chosen onset method.  "
     "<b>pYIN</b> (Mauch & Dixon 2014): probabilistic YIN, fast, built "
     "into librosa.  <b>CREPE</b> (Kim et al. 2018): neural-network "
     "tracker, very accurate for monophonic singing — requires torchcrepe.  "
     "<b>Praat</b>: classic autocorrelation via parselmouth.  <b>none</b>: "
     "no standalone pitch tracking (syllable_nuclei still provides its own "
     "Praat F0 internally).",
     [("Analysing singing or pitched calls",
       "use <b>pyin</b> for speed or <b>crepe</b> for best accuracy."),
      ("Drumming / unpitched percussion",
       "set to <b>none</b> — pitch tracking is not meaningful.")]),

    ("pitch_fmin", "Pitch F0 Min (Hz)",
     "Lower bound for the pitch search range.  Default 65 Hz ≈ C2.",
     [("Male singing or low-pitched animal calls",
       "keep at <b>65</b> or lower."),
      ("Soprano / high-pitched bird song",
       "raise to <b>100–200</b> to avoid octave errors.")]),

    ("pitch_fmax", "Pitch F0 Max (Hz)",
     "Upper bound for the pitch search range.  Default 1047 Hz ≈ C6.",
     [("Low-pitched instruments / bass",
       "lower to <b>400–600</b>."),
      ("Very high-pitched sources (piccolo, bat)",
       "raise above <b>2000</b>.")]),

    # ── Tempo-Adaptive Min IOI ──
    ("tempo_adaptive_enabled", "Tempo-Adaptive Min IOI",
     "When enabled, the minimum inter-onset spacing is automatically "
     "computed from the detected tempo (BPM × fraction) instead of "
     "using the static MIN_INTER_ONSET_MS value.  This prevents removing "
     "legitimate fast onsets in slow music or keeping spurious doubles "
     "in fast music.",
     [("Music with variable tempo",
       "enable and set fraction to <b>0.5</b>."),
      ("Fixed-tempo metronome recordings",
       "the static MIN_INTER_ONSET_MS may be sufficient.")]),

    ("tempo_adaptive_fraction", "Tempo-Adaptive Fraction",
     "Fraction of the beat interval used as the adaptive minimum spacing.  "
     "0.5 = onsets closer than half a beat apart are merged.",
     [("Preserving ornamental / grace notes",
       "lower to <b>0.25</b>."),
      ("Thinning to main beats only",
       "raise to <b>0.75</b>.")]),
]

# ---------- Step 3: Raster Plot settings (key settings only) -----
_STEP3_SETTINGS = [
    ("excel_path", "Input Excel Workbook",
     "The spreadsheet of beat events produced by the Onset Finder.  The raster plots "
     "pull their data from this.",
     []),
    ("output_folder", "Output Folder",
     "Where the raster plot images will be saved.",
     []),
    ("plot_datasets", "Datasets to Plot",
     "Which set of events to visualise: the raw (all onsets), the stable "
     "(only steady rhythm sections), or both.",
     [("You want the full picture plus the filtered view",
       "choose <b>raw + stable</b> (the default)."),
      ("You only care about structured rhythms",
       "choose <b>stable only</b>.")]),
    ("raster_dpi", "Image Resolution (DPI)",
     "How sharp the output images are.  Higher DPI means crisper images, "
     "but larger file sizes.",
     [("Quick draft to check results",
       "use <b>150</b> DPI."),
      ("Publication-quality figures",
       "use <b>300</b> DPI.")]),
    ("raster_dot_size", "Point Size",
     "How large each data point is on the plot.  Use small dots when you "
     "have a lot of data, larger ones when data is sparse.",
     [("Dense data (hundreds or thousands of events per file)",
       "try <b>1—3</b>."),
      ("Sparse data (fewer than ~100 events per file)",
       "try <b>5—10</b>.")]),
    ("raster_alpha", "Point Transparency",
     "How see-through each point is.  Transparent points let you see "
     "overlapping clusters; fully opaque points stand out when data is "
     "sparse.",
     [("Dense, overlapping data",
       "try <b>0.3—0.5</b>."),
      ("Sparse data",
       "try <b>0.6—1.0</b>.")]),
    ("raster_combined", "Combined Corpus Plot",
     "Generate one extra plot that overlays all recordings on a single "
     "raster, so you can compare them at a glance.",
     [("You have multiple recordings and want to compare",
       "turn this <b>on</b>.")]),
    # ── 3D Flower ──
    ("raster_3d_enabled", "3D Flower Raster",
     "Transforms the raster plots into a 3D flower that you can rotate "
     "and explore interactively in a web browser.  Each recording becomes "
     "a petal radiating outward from a central axis.",
     [("You want an interactive, exploratory view of multiple recordings",
       "turn this <b>on</b> — it's one of the most distinctive features "
       "of this pipeline."),
      ("You only need standard 2D plots",
       "you can leave it off.")]),
    ("raster_3d_format", "3D Output Format",
     "Save the 3D flower as an interactive web page (HTML — you can spin "
     "it in a browser), a static image (PNG — for papers), or both.",
     [("You want to explore the data interactively",
       "choose <b>Interactive HTML</b>."),
      ("You need a figure for a paper or presentation",
       "choose <b>Static PNG</b> or <b>Both</b>.")]),
]

# ---------- Step 4: Histogram settings (key settings only) --------
_STEP4_SETTINGS = [
    ("excel_path", "Input Excel Workbook",
     "The same spreadsheet from the Onset Finder — the histogram generator reads "
     "from it too.",
     []),
    ("output_folder", "Output Folder",
     "Where to save the histogram images.",
     []),
    ("hist_datasets", "Datasets to Plot",
     "Which events to build histograms from: all onsets, stable rhythms "
     "only, or both.",
     [("You want the complete view and the filtered view",
       "choose <b>raw + stable</b>.")]),
    ("hist_bins", "Number of Bins",
     "How many buckets to sort the rhythm ratios into.  More bins = finer "
     "detail, but the distribution can look sparse if you don't have much "
     "data.",
     [("You have <b>lots of data</b> (thousands of dyadic events)",
       "try <b>30—50</b> bins."),
      ("You have <b>limited data</b> (fewer than ~200 events)",
       "try <b>15—20</b> bins so the histogram doesn't look too patchy.")]),
    ("hist_dpi", "Image Resolution (DPI)",
     "Same as for raster plots — 150 for drafts, 300 for publication.",
     []),
    ("hist_ref_lines", "Show Ratio Reference Lines",
     "Draw vertical lines at key rhythm ratios (1:1, 1:2, 1:3, etc.) so "
     "you can see whether your data clusters near these important values.",
     [("You're interested in <b>whether rhythms cluster at simple ratios</b>",
       "keep this <b>on</b> — it's one of the core visualisation features.")]),
    ("hist_iso_band", "Isochronous Band",
     "Highlights the zone around r<sub>k</sub> = 0.5 where consecutive "
     "intervals are roughly equal — a perfectly steady beat.  This makes "
     "it easy to see how much of the data falls near isochrony.",
     [("You're studying rhythmic regularity",
       "keep this <b>on</b>.")]),
    ("hist_show_stats", "Show Statistics Box",
     "Overlays a summary panel with nPVI (variability), entropy "
     "(unpredictability), and CV (coefficient of variation) for each "
     "recording.  These numbers give you a quantitative handle on what "
     "the histogram is showing.",
     [("You want quantitative summaries alongside the visuals",
       "keep this <b>on</b>.")]),
    ("hist_combined", "Combined Histogram",
     "Pool all recordings into one big histogram, so you can see the "
     "overall rhythmic profile of your entire dataset.",
     [("You have multiple recordings",
       "turn this <b>on</b> for a cross-corpus summary.")]),
]

# ---------- Step 5: nPVI Group Plot settings ------------------------------
_STEP5_SETTINGS = [
    ("excel_path", "Input Excel Workbook",
     "The same spreadsheet from the Onset Finder — the nPVI Group Plot reads the "
     "File Summaries sheet for per-file nPVI scores.",
     []),
    ("output_folder", "Output Folder",
     "Where the raincloud plot images will be saved.",
     []),
    ("npvi_dataset", "nPVI Dataset",
     "Which nPVI scores to plot: from the raw dataset (all onsets) or "
     "the stable-rhythm dataset (only steady sections).",
     [("You want to compare overall rhythmic variability",
       "choose <b>raw</b>."),
      ("You want to compare only structured, metronomic passages",
       "choose <b>stable</b>.")]),
    ("group_source", "Group Assignment Method",
     "How to decide which group each recording belongs to.  This is "
     "how the X-axis of the raincloud plot gets its categories.\n\n"
     "• <b>Filename pattern</b> — extracts a group name from each "
     "filename using a regular expression.\n"
     "• <b>Mapping CSV</b> — a two-column file mapping filenames to groups.\n"
     "• <b>Manual</b> — type filename → group pairs directly.\n"
     "• <b>Excel column</b> — reads group labels from a column already "
     "present in the workbook.",
     [("Your filenames contain species or site codes (e.g. 'zebrafinch_01.wav')",
       "use <b>filename_pattern</b> with a regex that captures the prefix."),
      ("You have a separate metadata spreadsheet",
       "use <b>mapping_csv</b>."),
      ("You just have a few files and want to type it in",
       "use <b>manual</b>.")]),
    ("filename_pattern", "Filename Regex Pattern",
     "When using 'filename_pattern' grouping, this regular expression "
     "extracts the group name from each filename.  The first capture "
     "group (parentheses) becomes the group label.\n\n"
     "For example, <code>^([A-Za-z]+)_</code> captures everything before "
     "the first underscore.",
     [("Filenames start with the species name (e.g. 'zebrafinch_01')",
       "try <b>^([A-Za-z]+)_</b>"),
      ("Filenames contain the site in the middle (e.g. '01_siteA_call')",
       "try <b>_([A-Za-z]+)_</b>")]),
    ("plot_dpi", "Image Resolution (DPI)",
     "How sharp the output images are.  Higher DPI means crisper images, "
     "but larger file sizes.",
     [("Quick draft to check results",
       "use <b>150</b> DPI."),
      ("Publication-quality figures",
       "use <b>300</b> DPI.")]),
]

_ALL_STEP_SETTINGS = {
    0: _STEP1_SETTINGS,
    1: _STEP2_SETTINGS,
    2: _STEP3_SETTINGS,
    3: _STEP4_SETTINGS,
    4: _STEP5_SETTINGS,
}

_STEP_NAMES = {
    0: "Audio Editor",
    1: "Onset Finder",
    2: "Flower Raster Plots",
    3: "Histogram Generator",
    4: "nPVI Group Plot",
}


# ── Multi-species analyses: derive setting cards from NEW_ANALYSIS_SPECS ──
#
# Walkthrough step indices 5-14 correspond to sidebar steps 8-17 (the ten
# new multi-species rhythmic-landscape analyses). Their setting cards are
# derived programmatically from the help / help_detailed / help_novice
# strings already authored on each spec, so walkthrough content stays in
# sync with the panels automatically.

_NEW_ANALYSIS_WALKTHROUGH_NAMES = [
    "Rhythm Ratio Distributions",
    "KS Test vs. Uniform Null",
    "Wilcoxon Isochrony Preference",
    "Lag-1 Autocorrelation",
    "Tempo × Ratio Density Heatmap",
    "Multi-metric Raincloud Plots",
    "Permuted Discriminant Function Analysis (pDFA)",
    "Mantel / Partial Mantel Test",
    "GLMM for Rhythmic Responses",
    "Phylogenetic Generalized Least Squares (PGLS)",
]

for _i, _name in enumerate(_NEW_ANALYSIS_WALKTHROUGH_NAMES):
    _STEP_NAMES[5 + _i] = _name

# Walkthrough step 15 → Association Rule Learning (experimental).
# Kept at the end of the list because ARL is moved to the bottom of the
# Experimental Analyses / Figures section on the sidebar.
_STEP_NAMES[15] = "Association Rule Learning"


def _build_new_analysis_settings():
    """Build setting-card tuples for walkthrough pages 5-14.

    Pulls the 3-level descriptions (help / help_detailed / help_novice)
    from NEW_ANALYSIS_SPECS in pipeline_gui and formats them for the
    walkthrough's _SettingCard widgets. Import is done lazily to avoid a
    circular import (pipeline_gui imports walkthrough_mode at top).
    """
    try:
        from pipeline_gui import NEW_ANALYSIS_SPECS  # type: ignore
    except Exception:
        try:
            from GUI.pipeline_gui import NEW_ANALYSIS_SPECS  # type: ignore
        except Exception:
            return {5 + i: [] for i in range(10)}

    out = {}
    for i, spec in enumerate(NEW_ANALYSIS_SPECS):
        cards = []
        for s in spec.get("settings", []):
            label = s.get("label", s.get("key", ""))
            concise = (s.get("help") or "").strip()
            detailed = (s.get("help_detailed") or "").strip()
            novice = (s.get("help_novice") or "").strip()

            # Prefer detailed as the main explanation; append novice
            # below as a friendlier paraphrase if it adds anything.
            main = detailed or concise
            extras = []
            if novice and novice != main and novice != concise:
                extras.append(
                    f"<br><br><i style='color:{_TEXT_DIM};'>In plainer "
                    f"terms:</i> {novice}"
                )
            explanation = main + "".join(extras)

            cards.append((s.get("key", ""), label, explanation, []))
        out[5 + i] = cards
    return out


# NOTE: Actually populating _ALL_STEP_SETTINGS for the new analyses is
# deferred to WalkthroughDialog.__init__ — at module-import time
# pipeline_gui hasn't finished loading yet (it imports us), so the lazy
# import would fail. We pre-seed empty lists so key lookups always work.
for _i in range(10):
    _ALL_STEP_SETTINGS.setdefault(5 + _i, [])

# Walkthrough step 15 (ARL) — hand-authored setting cards (the ARL panel
# predates NEW_ANALYSIS_SPECS, so settings are written directly here in
# the same 4-tuple format: key, label, explanation, advice items).
_STEP16_SETTINGS = [
    # ── I/O ──
    ("excel_path", "Input Excel file",
     "The .xlsx workbook produced by the <b>Onset Finder</b> step. ARL "
     "mines the <i>File Summaries</i> sheet — one row per recording — "
     "so every file's numeric metrics (nPVI, CV, entropy, mean IOI, "
     "total onsets) must already be present.",
     [("You ran the Onset Finder earlier in this pipeline",
       "leave <b>Auto-set input</b> on — it will track the Onset "
       "Finder's output automatically."),
      ("You're analysing an Excel workbook from a previous run",
       "turn auto-set off and point this field at the .xlsx directly.")]),
    ("output_folder", "Output folder",
     "Where the association-rule CSVs and plots are saved. ARL writes "
     "<code>association_rules.csv</code>, "
     "<code>frequent_itemsets.csv</code>, a top-N bar chart, a "
     "support-vs-confidence scatter, and (optionally) a circular rule "
     "network diagram.",
     [("You want a consistent layout",
       "leave <b>Auto-set output</b> on — it creates an "
       "<code>Association_Rules/</code> folder next to the input Excel.")]),
    # ── Data Source ──
    ("arl_dataset", "Rhythm dataset (raw vs stable)",
     "Which rhythm metrics to mine. <b>Raw</b> uses the all-events "
     "metrics (<i>nPVI (Isochrony)</i>, <i>r_k Entropy</i>); <b>stable</b> "
     "swaps them for the stable-rhythm-only versions (<i>Stable Rhythm "
     "nPVI</i>, <i>Stable Rhythm Entropy</i>). Choose the one that "
     "matches your scientific question.",
     [("You want to characterise <b>overall</b> rhythmic profiles",
       "choose <b>raw</b>."),
      ("You want to focus on <b>structured, metronomic</b> stretches",
       "choose <b>stable</b>."),
      ("You're not sure",
       "run both and compare — if rules diverge, the stable-rhythm "
       "signal is telling you something different from the full data.")]),
    ("arl_features", "Features to mine",
     "Comma-separated names of the Excel columns that should be "
     "discretised and fed into Apriori. Each feature becomes one item "
     "per file (e.g. <code>nPVI=high</code>). Rows with <i>any</i> "
     "missing value in the selected columns are dropped, so keep the "
     "list focused.",
     [("You want a quick first pass",
       "keep the default five (nPVI, entropy, CV, mean IOI, total "
       "onsets) — it's a good balance of coverage and rule readability."),
      ("You care only about isochrony vs variability",
       "use just <b>nPVI (Isochrony), CV of Intervals</b> and add a "
       "<b>Group</b> item so rules predict group membership."),
      ("You want to include stability",
       "append <b>Stable Rhythm nPVI</b> or <b>Stable Rhythm Entropy</b>.")]),
    # ── Binning ──
    ("arl_bin_method", "Bin method",
     "How each numeric feature is split into categorical bins. "
     "<b>Quantile</b> puts roughly equal numbers of files in each bin — "
     "robust to outliers and usually the better default. "
     "<b>Equal-width</b> splits the min→max range into equal intervals, "
     "which can leave bins almost empty if the distribution is skewed.",
     [("Your metric distributions look skewed or have outliers",
       "use <b>quantile</b> (the default)."),
      ("Your metrics are already on a natural, symmetric scale",
       "<b>equal_width</b> is fine and easier to explain.")]),
    ("arl_n_bins", "Number of bins",
     "How many bins each feature is split into. More bins = finer rules "
     "but lower support per bin — with small datasets you will end up "
     "with very few frequent itemsets.",
     [("You have <b>fewer than ~100 files</b>",
       "use <b>3</b> (low / medium / high)."),
      ("You have a large corpus and want finer granularity",
       "try <b>4</b> (quartiles) — but expect fewer rules to clear "
       "the min-support bar."),
      ("You just want 'above average vs below average'",
       "use <b>2</b>.")]),
    ("arl_bin_labels", "Bin labels",
     "Comma-separated human-readable labels, one per bin, ordered "
     "low → high. These labels appear in every rule (e.g. "
     "<code>nPVI=high</code>), so short, ordered words work best.",
     [("Using 3 bins",
       "<b>low, medium, high</b>."),
      ("Using 4 bins",
       "<b>Q1, Q2, Q3, Q4</b>."),
      ("Label count doesn't match <i>Number of bins</i>",
       "ARL falls back to <b>bin1, bin2, …</b> — no error, just less "
       "pretty.")]),
    # ── Group Assignment ──
    ("arl_include_group", "Include a per-file Group item",
     "When <b>on</b>, every file gets an extra item such as "
     "<code>Group=Chimp</code> in addition to its metric bins. This lets "
     "ARL mine rules that <i>predict</i> group membership — e.g. "
     "<code>{nPVI=high, CV=low} ⇒ Group=Chimp</code>.",
     [("Your dataset spans multiple species, sites, or conditions",
       "turn this <b>on</b> — it's where ARL gets most of its value."),
      ("Single-group dataset (all files are the same species)",
       "leave it <b>off</b> — every transaction would share the same "
       "Group item, which adds noise without information.")]),
    ("arl_group_source", "Group source",
     "How each file's group label is determined.\n\n"
     "<b>filename_pattern</b> — extract the group from each filename "
     "using a regex with a named capture <code>(?P&lt;group&gt;…)</code>.\n"
     "<b>mapping_csv</b> — load a CSV with columns <code>File Name</code> "
     "and <code>Group</code>.\n"
     "<b>manual</b> — type <code>file1.wav=GroupA, file2.wav=GroupB</code> "
     "pairs directly.\n"
     "<b>excel_column</b> — reuse a column that is already present in "
     "the File Summaries sheet.",
     [("Your filenames encode the group (e.g. <i>Chimp_site1_rec03</i>)",
       "use <b>filename_pattern</b> with <code>(?P&lt;group&gt;[A-Za-z]+)_</code>."),
      ("You already maintain a groups spreadsheet",
       "use <b>mapping_csv</b> or <b>excel_column</b> — keeps ARL in "
       "sync with your canonical source."),
      ("Small dataset with irregular names",
       "use <b>manual</b>.")]),
    ("arl_group_pattern", "Filename pattern (regex)",
     "Regular expression with a named capture group <code>(?P&lt;group&gt;…)</code> "
     "that extracts the group label from each filename. Only used when "
     "<i>Group source = filename_pattern</i>.",
     [("Filenames start with the group, separated by underscore",
       "<code>(?P&lt;group&gt;[A-Za-z]+)_</code> (the default)."),
      ("Group appears <i>between</i> two underscores",
       "<code>_(?P&lt;group&gt;[A-Za-z]+)_</code>."),
      ("Group is the last segment before the extension",
       "<code>_(?P&lt;group&gt;[A-Za-z]+)\\.wav$</code>.")]),
    ("arl_group_csv_path", "Mapping CSV file",
     "External CSV with columns <b>File Name</b> and <b>Group</b>. Only "
     "used when <i>Group source = mapping_csv</i>. Files missing from "
     "this CSV fall through to the <i>Ungrouped label</i>.",
     [("You already maintain a metadata spreadsheet",
       "export a File Name + Group CSV and point this field at it — "
       "single source of truth.")]),
    ("arl_manual_groups", "Manual groups",
     "Comma-separated <code>filename=group</code> pairs — used when "
     "<i>Group source = manual</i>. Handy for small exploratory runs.",
     [("Quickly testing a handful of recordings",
       "type e.g. <code>rec01.wav=Chimp, rec02.wav=Chimp, "
       "rec03.wav=Bonobo</code>.")]),
    ("arl_group_excel_column", "Excel column name",
     "Name of a column already present in the File Summaries sheet that "
     "holds each file's group label. Only used when <i>Group source = "
     "excel_column</i>. The default is simply <code>Group</code>.",
     [("Group is in the workbook already",
       "just set this to the column name — no extra files needed.")]),
    ("arl_ungrouped_label", "Ungrouped label",
     "Label used for files that <i>can't</i> be assigned to any group "
     "(e.g. the regex didn't match, or the file isn't in the mapping "
     "CSV).",
     [("You want to spot unmatched files at a glance",
       "leave as <b>Ungrouped</b> — any rule mentioning "
       "<code>Group=Ungrouped</code> flags a gap in your metadata.")]),
    # ── Apriori thresholds ──
    ("arl_min_support", "Min support",
     "The minimum fraction of files (0–1) in which an itemset must "
     "appear before it's considered. Lower values retain more — and "
     "rarer — itemsets but dramatically slow mining and inflate false "
     "positives.",
     [("Small dataset (&lt; 40 files)",
       "start at <b>0.20–0.25</b> — rules need to appear in ≥ 8–10 "
       "files to be trustworthy."),
      ("Medium dataset (~100 files)",
       "<b>0.15</b> (the default) is a sensible starting point."),
      ("Large dataset (hundreds of files)",
       "you can drop to <b>0.05–0.10</b> and still get stable rules.")]),
    ("arl_min_confidence", "Min confidence",
     "The minimum <code>P(consequent | antecedent)</code>. A rule with "
     "confidence 0.80 means: whenever the antecedent is present, the "
     "consequent is present 80% of the time. Drops low-reliability rules.",
     [("Exploratory first pass",
       "<b>0.60</b> (the default)."),
      ("You want only strong, near-deterministic rules",
       "raise to <b>0.80</b>."),
      ("You're drowning in weak rules",
       "raise to <b>0.70</b> first before touching other thresholds.")]),
    ("arl_min_lift", "Min lift",
     "Lift = confidence ÷ P(consequent). It tells you <i>how much "
     "better than chance</i> the rule is. Lift = 1 means the antecedent "
     "doesn't help predict the consequent at all; lift &gt; 1 means the "
     "combination is genuinely over-represented.",
     [("Exploratory browsing",
       "<b>1.10</b> (the default) — weeds out rules that are only "
       "marginally better than random."),
      ("You want distinctive, newsworthy rules",
       "raise to <b>1.5–2.0</b>.")]),
    ("arl_max_itemset", "Max itemset size",
     "The largest itemset Apriori will consider. Caps the combinatorial "
     "explosion: size 4 means rules of at most 4 items (3-item "
     "antecedent ⇒ 1-item consequent, or any combination up to 4).",
     [("5–6 features + a group",
       "<b>3</b> or <b>4</b> (the default) is plenty — larger itemsets "
       "rarely survive the support threshold anyway."),
      ("You only care about simple 'A ⇒ B' rules",
       "use <b>2</b>.")]),
    ("arl_require_group", "Require Group in consequent",
     "When <b>on</b>, only rules whose consequent mentions a "
     "<code>Group=…</code> item are kept. Useful for focused, "
     "'what-predicts-group' analyses.",
     [("You want 'rhythm profile ⇒ group' style rules only",
       "turn this <b>on</b>."),
      ("You want to see all co-occurrence patterns, including "
       "metric↔metric ones",
       "leave <b>off</b> (the default).")]),
    ("arl_top_n", "Top-N for plots",
     "How many rules are shown in the bar chart and network plot. The "
     "CSV always contains <i>every</i> rule that passes the thresholds "
     "— this setting only affects the plots.",
     [("Clean publication figure",
       "<b>10–15</b> keeps labels readable."),
      ("Exploratory browsing",
       "up to <b>25–30</b> is fine but labels will get cramped.")]),
    # ── Plot Appearance ──
    ("arl_width", "Width (inches)",
     "Figure width. Wider figures suit many rules or long labels.",
     [("Single-column figure",
       "<b>8–10</b>."),
      ("Wide poster / slide figure",
       "<b>14–16</b>.")]),
    ("arl_height", "Height (inches)",
     "Figure height. Increase when rule labels are long or when you "
     "have many top-N bars.",
     [("~15 rules",
       "<b>7</b> (the default) is plenty."),
      ("25+ rules",
       "bump to <b>10–12</b>.")]),
    ("arl_dpi", "DPI (image resolution)",
     "Pixels-per-inch of the saved raster images. Higher = crisper but "
     "larger files.",
     [("Quick draft",
       "<b>150</b>."),
      ("Publication",
       "<b>300</b> (the default)."),
      ("Poster-sized final",
       "<b>450–600</b>.")]),
    ("arl_bg_color", "Background color",
     "Background colour of the figure and axes. White is the safest "
     "choice for print; a light grey works well on slides.",
     [("Standard publication look",
       "<b>#ffffff</b> (pure white, the default)."),
      ("Presentation / dark theme",
       "try <b>#1a1d24</b> with a light palette.")]),
    ("arl_palette", "Color palette",
     "Matplotlib colormap used to colour the bar chart, scatter, and "
     "network edges. Sequential perceptually-uniform maps like "
     "<i>viridis</i> are best when colour encodes <b>lift</b>.",
     [("You're mapping continuous lift / confidence",
       "use <b>viridis</b>, <b>plasma</b>, or <b>cividis</b>."),
      ("You're colouring by categorical group",
       "use <b>tab10</b>, <b>Set2</b>, or <b>Dark2</b>.")]),
    ("arl_title_fs", "Title font size",
     "Size of the plot title text (in points).",
     [("Default figure",
       "<b>15</b> points."),
      ("Poster",
       "<b>20+</b>.")]),
    ("arl_axis_fs", "Axis font size",
     "Size of the axis-label text (in points).",
     [("Default",
       "<b>12</b> points.")]),
    ("arl_tick_fs", "Tick / rule-label font size",
     "Font size of tick labels <i>and</i> the rule text on the top-N "
     "bar chart. Shrink this when rule labels get long.",
     [("Long rule labels are being clipped",
       "drop to <b>8–9</b> points.")]),
    ("arl_draw_network", "Draw rule network diagram",
     "Enables an optional circular network plot of the top-N rules, "
     "with items as nodes and rules as edges coloured by lift. Useful "
     "for spotting hub features that appear in many rules.",
     [("First pass — you want every view",
       "leave <b>on</b>."),
      ("The network is cluttered with too many items",
       "turn <b>off</b> and rely on the bar chart + CSV instead.")]),
    ("arl_output_format", "Output file format",
     "Image format for the saved plots. PNG is universal; SVG / PDF are "
     "vector formats that scale to any size without pixellation.",
     [("Quick look or slide embedding",
       "<b>png</b>."),
      ("Publication-quality figure",
       "<b>svg</b> or <b>pdf</b>."),
      ("You want both a preview and a scalable copy",
       "<b>png+svg</b>.")]),
]

_ALL_STEP_SETTINGS[15] = _STEP16_SETTINGS


# ── Widget: individual setting card ────────────────────────────────

class _SettingCard(QFrame):
    """A single setting card inside the walkthrough scroll area."""

    def __init__(self, label, explanation, advice_items, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"_SettingCard {{"
            f"  background-color: {_BG_MID};"
            f"  border: 1px solid {_BORDER};"
            f"  border-radius: 8px;"
            f"  padding: 12px;"
            f"}}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        # Setting name
        name_lbl = QLabel(label)
        name_lbl.setFont(QFont("", 13, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color: {_TEXT}; background: transparent;")
        name_lbl.setWordWrap(True)
        lay.addWidget(name_lbl)

        # Explanation
        expl = QLabel(explanation)
        expl.setWordWrap(True)
        expl.setTextFormat(Qt.TextFormat.RichText)
        expl.setStyleSheet(
            f"color: {_TEXT_DESC}; font-size: 13px; background: transparent;"
            f"  line-height: 1.5;"
        )
        lay.addWidget(expl)

        # Advice items
        if advice_items:
            lay.addSpacing(6)
            advice_header = QLabel("&#x1F4A1;  Suggested settings")
            advice_header.setFont(QFont("", 12, QFont.Weight.Bold))
            advice_header.setTextFormat(Qt.TextFormat.RichText)
            advice_header.setStyleSheet(
                f"color: {_ACCENT}; background: transparent;"
            )
            lay.addWidget(advice_header)

            for condition, recommendation in advice_items:
                item_lbl = QLabel(
                    f"<span style='color:{_TEXT_DIM};'>If</span> "
                    f"{condition}<span style='color:{_TEXT_DIM};'> &#x2192;</span> "
                    f"{recommendation}"
                )
                item_lbl.setWordWrap(True)
                item_lbl.setTextFormat(Qt.TextFormat.RichText)
                item_lbl.setStyleSheet(
                    f"color: {_TEXT}; font-size: 12px; background: transparent;"
                    f"  padding: 3px 10px;"
                    f"  border-left: 2px solid {_ACCENT_DIM};"
                    f"  margin: 2px 0px;"
                )
                lay.addWidget(item_lbl)


# ── Widget: scrollable step settings page ──────────────────────────

class _StepSettingsPage(QWidget):
    """A scrollable page showing the intro + all setting cards for one step."""

    def __init__(self, step_index, parent=None):
        super().__init__(parent)
        self._step = step_index

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {_BG}; }}"
        )
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        # Step intro
        title, intro_text = STEP_INTRO[step_index]
        lay.addWidget(_heading(title, size=17))
        lay.addWidget(_body(intro_text))
        lay.addWidget(_sep())
        lay.addSpacing(6)

        # Settings section header
        settings_header = QLabel(f"Settings for {_STEP_NAMES[step_index]}")
        settings_header.setFont(QFont("", 14, QFont.Weight.Bold))
        settings_header.setStyleSheet(
            f"color: {_TEXT}; background: transparent;"
        )
        lay.addWidget(settings_header)
        lay.addWidget(_dim(
            "Each card below explains one setting you can adjust. "
            "Green-bordered tips offer suggested values based on your "
            "data type."
        ))
        lay.addSpacing(6)

        # Setting cards
        for _attr, label, explanation, advice in _ALL_STEP_SETTINGS[step_index]:
            lay.addWidget(_SettingCard(label, explanation, advice))

        lay.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)


# ── Main walkthrough dialog ────────────────────────────────────────

class WalkthroughDialog(QDialog):
    """Multi-page guided walkthrough wizard."""

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self._main = main_window
        self.setWindowTitle("Pipeline Walkthrough")
        self.setMinimumSize(980, 640)
        self.resize(1060, 720)
        self.setStyleSheet(
            f"WalkthroughDialog {{"
            f"  background-color: {_BG};"
            f"  color: {_TEXT};"
            f"}}"
            f"QLabel {{ background: transparent; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Body: sidebar (Section Selection) + page stack ──
        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)
        root.addWidget(body, stretch=1)

        # Left rail: section selector
        self._section_list = self._build_section_list()
        body_lay.addWidget(self._section_list)

        # ── Page stack ──
        self._pages = QStackedWidget()
        body_lay.addWidget(self._pages, stretch=1)

        # Page 0: Welcome
        self._pages.addWidget(self._build_welcome())
        # Page 1: Pipeline overview
        self._pages.addWidget(self._build_overview())
        # Page 2: Step selection
        self._pages.addWidget(self._build_step_selection())
        # Populate multi-species setting cards now (pipeline_gui has
        # finished importing by the time the dialog is constructed).
        try:
            _ALL_STEP_SETTINGS.update(_build_new_analysis_settings())
        except Exception:
            pass
        # Pages 3–18: Per-step settings (5 core + 10 multi-species + 1 ARL)
        self._step_pages_start = 3
        self._n_steps = 16
        for i in range(self._n_steps):
            self._pages.addWidget(_StepSettingsPage(i))
        # Final page: Finish
        self._finish_idx = self._step_pages_start + self._n_steps
        self._pages.addWidget(self._build_finish())

        # Track which steps are selected. Core production steps (0-4) are
        # on by default; the 10 multi-species analyses (5-14) and ARL (15)
        # are opt-in, so the walkthrough stays short unless the user
        # explicitly wants the experimental pages.
        self._selected_steps = [True] * 5 + [False] * 11

        # ── Navigation bar ──
        nav = QWidget()
        nav.setStyleSheet(f"background-color: {_BG_MID};")
        nav_lay = QHBoxLayout(nav)
        nav_lay.setContentsMargins(16, 10, 16, 10)

        self._page_indicator = QLabel()
        self._page_indicator.setStyleSheet(
            f"color: {_TEXT_DIM}; font-size: 12px;"
        )
        nav_lay.addWidget(self._page_indicator)
        nav_lay.addStretch()

        self._back_btn = QPushButton("← Back")
        self._back_btn.setFixedWidth(100)
        self._back_btn.setStyleSheet(
            f"QPushButton {{ background-color: {_BG_WIDGET}; color: {_TEXT}; "
            f"border-radius: 6px; padding: 7px 14px; border: 1px solid {_BORDER}; "
            f"font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {_BG_INPUT}; border-color: {_ACCENT}; }}"
        )
        self._back_btn.clicked.connect(self._go_back)
        nav_lay.addWidget(self._back_btn)
        nav_lay.addSpacing(8)

        self._next_btn = QPushButton("Next →")
        self._next_btn.setFixedWidth(100)
        self._next_btn.setStyleSheet(
            f"QPushButton {{ background-color: {_ACCENT_DIM}; color: white; "
            f"border-radius: 6px; padding: 7px 14px; border: none; "
            f"font-size: 13px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {_ACCENT}; }}"
        )
        self._next_btn.clicked.connect(self._go_next)
        nav_lay.addWidget(self._next_btn)

        root.addWidget(nav)

        self._ordered_pages = []
        self._current_order_idx = 0
        self._rebuild_page_order()
        self._sync_nav()

    # ── Page builders ──────────────────────────────────────────────

    def _build_welcome(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(40, 32, 40, 20)
        lay.setSpacing(10)

        lay.addStretch(1)

        # ── Artistic title with decorative rule ──
        title = QLabel("Welcome to the Bioacoustics\nRhythm Pipeline")
        title.setFont(QFont("", 26, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color: {_ACCENT}; background: transparent;"
            "  letter-spacing: 1px;"
        )
        title.setWordWrap(True)
        lay.addWidget(title)

        # Decorative accent rule under the title
        rule = QFrame()
        rule.setFixedHeight(3)
        rule.setFixedWidth(200)
        rule.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f"  stop:0 {_ACCENT}, stop:1 transparent);"
            "  border: none; border-radius: 1px;"
        )
        lay.addWidget(rule)
        lay.addSpacing(10)

        # Purpose / aim paragraph
        lay.addWidget(_body(
            "This pipeline helps you <b>extract, measure, and visualise "
            "rhythmic patterns</b> from audio recordings of any species — "
            "human percussion, birdsong, primate drumming, insect calls, "
            "and more. It implements the dyadic rhythm-ratio framework of "
            "Roeske et al. (2020), characterising rhythm not as tempo "
            "(beats per minute) but as the <i>ratio</i> between consecutive "
            "inter-onset intervals."
        ))
        lay.addSpacing(6)

        # ── Section header: What this walkthrough covers ──
        wt_header = QLabel("What this walkthrough covers")
        wt_header.setFont(QFont("", 16, QFont.Weight.Bold))
        wt_header.setStyleSheet(
            f"color: {_TEXT}; background: transparent;"
            "  letter-spacing: 0.5px;"
        )
        lay.addWidget(wt_header)
        lay.addWidget(_body(
            "<table style='margin-left:8px; border-spacing:5px;'>"
            f"<tr><td style='color:{_ACCENT}; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
            "<td>Explain what each pipeline panel does and why it matters</td></tr>"
            f"<tr><td style='color:{_ACCENT}; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
            "<td>Let you choose which steps to run</td></tr>"
            f"<tr><td style='color:{_ACCENT}; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
            "<td>Walk through every setting with plain-language explanations</td></tr>"
            f"<tr><td style='color:{_ACCENT}; vertical-align:top; padding-right:6px;'>&#x2022;</td>"
            "<td>Offer data-type-specific advice (e.g. 'if your data is birdsong, try X')</td></tr>"
            "</table>"
        ))
        lay.addSpacing(6)

        # ── Section header: Sidebar layout ──
        layout_header = QLabel("Sidebar layout — four sections")
        layout_header.setFont(QFont("", 16, QFont.Weight.Bold))
        layout_header.setStyleSheet(
            f"color: {_TEXT}; background: transparent;"
            "  letter-spacing: 0.5px;"
        )
        lay.addWidget(layout_header)
        lay.addWidget(_body(
            "The sidebar organises the pipeline into <b>four sections</b>, "
            "separated by divider lines:"
        ))
        lay.addWidget(_body(
            "<table style='margin-left:8px; border-spacing:5px;'>"
            # ── Section 1: Setup ──
            f"<tr><td colspan='2' style='color:{_TEXT_DIM}; font-size:11px; "
            f"padding-top:4px;'><i>Setup</i></td></tr>"
            f"<tr><td style='color:{_ACCENT}; font-weight:bold; vertical-align:top; padding-right:6px; padding-left:10px;'>&#x25B8;</td>"
            "<td><b>Pipeline Prep</b> — scan a folder for audio files and see "
            "which pipeline artefacts already exist for each file</td></tr>"
            f"<tr><td style='color:{_ACCENT}; font-weight:bold; vertical-align:top; padding-right:6px; padding-left:10px;'>&#x25B8;</td>"
            "<td><b>Onset Editor</b> — interactively view, add, remove, and "
            "drag onset markers on a waveform + spectrogram display</td></tr>"
            # ── Section 2: Core Processing ──
            f"<tr><td colspan='2' style='color:{_TEXT_DIM}; font-size:11px; "
            f"padding-top:8px;'><i>Core Processing</i></td></tr>"
            f"<tr><td style='color:{_ACCENT}; font-weight:bold; vertical-align:top; padding-right:6px; padding-left:10px;'>&#x25B8;</td>"
            "<td><b>Audio Editor</b> — cleans up raw recordings (Demucs source "
            "separation, noise removal, filtering)</td></tr>"
            f"<tr><td style='color:{_ACCENT}; font-weight:bold; vertical-align:top; padding-right:6px; padding-left:10px;'>&#x25B8;</td>"
            "<td><b>Onset Finder</b> — detects every individual sound event "
            "and computes rhythm metrics</td></tr>"
            # ── Section 3: Analyses / Figures ──
            f"<tr><td colspan='2' style='color:{_TEXT_DIM}; font-size:11px; "
            f"padding-top:8px;'><i>Analyses / Figures</i></td></tr>"
            f"<tr><td style='color:{_ACCENT}; font-weight:bold; vertical-align:top; padding-right:6px; padding-left:10px;'>&#x25B8;</td>"
            "<td><b>Flower Raster Plots</b> — visualises rhythmic structure "
            "as 2D scatter plots and interactive 3D flowers</td></tr>"
            f"<tr><td style='color:{_ACCENT}; font-weight:bold; vertical-align:top; padding-right:6px; padding-left:10px;'>&#x25B8;</td>"
            "<td><b>Histograms</b> — shows the distribution of rhythm ratios "
            "per recording and across the corpus</td></tr>"
            f"<tr><td style='color:{_ACCENT}; font-weight:bold; vertical-align:top; padding-right:6px; padding-left:10px;'>&#x25B8;</td>"
            "<td><b>nPVI Group Plot</b> — compares rhythmic variability "
            "across groups using raincloud plots</td></tr>"
            # ── Section 4: Experimental Analyses / Figures ──
            f"<tr><td colspan='2' style='color:{_TEXT_DIM}; font-size:11px; "
            f"padding-top:8px;'><i>Experimental Analyses / Figures "
            "(optional, collapsible)</i></td></tr>"
            f"<tr><td style='color:{_ACCENT}; font-weight:bold; vertical-align:top; padding-right:6px; padding-left:10px;'>&#x25B8;</td>"
            "<td><b>Multi-species analyses</b> — r_k distributions, KS / "
            "Wilcoxon tests, autocorrelation, tempo × ratio heatmap, "
            "raincloud metrics, pDFA, Mantel, GLMM, PGLS</td></tr>"
            f"<tr><td style='color:{_ACCENT}; font-weight:bold; vertical-align:top; padding-right:6px; padding-left:10px;'>&#x25B8;</td>"
            "<td><b>Association Rule Learning</b> — exploratory Apriori "
            "mining over per-file rhythm metrics</td></tr>"
            "</table>"
        ))
        lay.addSpacing(4)
        lay.addWidget(_dim(
            "Pipeline Prep and the Onset Editor are setup / interactive "
            "tools — they don't run as batch steps. This walkthrough "
            "covers the five production steps (Audio Editor through nPVI "
            "Group Plot) in detail."
        ))

        lay.addStretch(1)

        # "What's under the hood?" button
        pkg_btn = QPushButton("  What's under the hood?  (Show packages)  ")
        pkg_btn.setStyleSheet(
            f"QPushButton {{ background-color: {_BG_WIDGET}; color: {_TEXT_DIM}; "
            f"border-radius: 6px; padding: 7px 16px; border: 1px solid {_BORDER}; "
            f"font-size: 12px; }}"
            f"QPushButton:hover {{ background-color: {_BG_INPUT}; color: {_TEXT}; "
            f"border-color: {_ACCENT}; }}"
        )
        pkg_btn.clicked.connect(self._show_package_info)
        lay.addWidget(pkg_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(6)

        lay.addWidget(_dim(
            "No technical background needed — everything is explained in "
            "plain language. Click \"Next\" to begin."
        ))

        lay.addStretch(1)

        return page

    def _build_overview(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {_BG}; }}")
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(40, 30, 40, 20)
        lay.setSpacing(12)

        lay.addWidget(_heading("How the Pipeline Works", size=18))
        lay.addSpacing(4)
        lay.addWidget(_body(
            "The sidebar organises the pipeline into <b>seven panels</b> "
            "across <b>three sections</b>. The five production steps each "
            "take the output of the previous one as input, building on "
            "it like an assembly line:"
        ))
        lay.addSpacing(2)

        # Flow diagram
        flow_lbl = QLabel(
            f"<div style='text-align:center; color:{_TEXT_DIM}; font-size:12px; "
            f"padding:8px 0;'>"
            f"Raw Audio &nbsp;&#x279C;&nbsp; "
            f"<span style='color:{_ACCENT};'>Prep</span> &nbsp;&#x279C;&nbsp; "
            f"<span style='color:{_ACCENT};'>Clean</span> &nbsp;&#x279C;&nbsp; "
            f"<span style='color:{_ACCENT};'>Detect</span> &nbsp;&#x279C;&nbsp; "
            f"<span style='color:{_TEXT_DIM};'>[Edit]</span> &nbsp;&#x279C;&nbsp; "
            f"<span style='color:{_ACCENT};'>Plot</span> &nbsp;&#x279C;&nbsp; "
            f"<span style='color:{_ACCENT};'>Histogram</span> &nbsp;&#x279C;&nbsp; "
            f"<span style='color:{_ACCENT};'>nPVI</span>"
            f"</div>"
        )
        flow_lbl.setTextFormat(Qt.TextFormat.RichText)
        flow_lbl.setStyleSheet(
            f"background-color: {_BG_MID}; border: 1px solid {_BORDER}; "
            f"border-radius: 6px; padding: 6px;"
        )
        lay.addWidget(flow_lbl)
        lay.addSpacing(6)

        lay.addWidget(_dim(
            "Below is a closer look at each panel. "
            "On the next page you'll choose which production steps to "
            "include."
        ))
        lay.addSpacing(4)

        # ── Setup section ──
        lay.addWidget(_heading("Setup", size=15))

        # Pipeline Prep card
        prep_card = QFrame()
        prep_card.setStyleSheet(
            f"QFrame {{ background-color: {_BG_MID};"
            f"  border: 1px solid {_BORDER}; border-radius: 8px; }}"
        )
        prep_lay = QVBoxLayout(prep_card)
        prep_lay.setContentsMargins(14, 12, 14, 12)
        prep_lay.setSpacing(6)
        prep_lay.addWidget(_heading("Pipeline Prep", size=14))
        prep_lay.addWidget(_body(
            "Scans your audio folder and shows a <b>file inventory table</b> "
            "listing each recording alongside the pipeline artefacts that "
            "already exist for it — onset layers, focus regions, selected "
            "signals, edited output folders, Excel presence, and Audacity "
            "labels. Use it to see at a glance where you are in the "
            "analysis before running any processing steps."
        ))
        lay.addWidget(prep_card)
        lay.addSpacing(2)

        # Production step cards
        lay.addWidget(_heading("Core Processing", size=15))
        for i in range(2):
            title, intro = STEP_INTRO[i]
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background-color: {_BG_MID};"
                f"  border: 1px solid {_BORDER}; border-radius: 8px; }}"
            )
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(14, 12, 14, 12)
            card_lay.setSpacing(6)
            card_lay.addWidget(_heading(title, size=14))
            card_lay.addWidget(_body(intro))
            lay.addWidget(card)
            lay.addSpacing(2)

        lay.addWidget(_heading("Analyses / Figures", size=15))
        for i in range(2, 5):
            title, intro = STEP_INTRO[i]
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background-color: {_BG_MID};"
                f"  border: 1px solid {_BORDER}; border-radius: 8px; }}"
            )
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(14, 12, 14, 12)
            card_lay.setSpacing(6)
            card_lay.addWidget(_heading(title, size=14))
            card_lay.addWidget(_body(intro))
            lay.addWidget(card)
            lay.addSpacing(2)

        # ── Onset Editor section ──
        lay.addWidget(_heading("Interactive Tools", size=15))
        lay.addSpacing(6)
        lay.addWidget(_heading("Onset Editor", size=14))
        lay.addWidget(_body(
            "After running the Onset Finder, open the <b>Onset "
            "Editor</b> panel from the sidebar to manually review and "
            "correct detected onsets. It provides a pyqtgraph-powered "
            "waveform + spectrogram display where you can:"
        ))
        lay.addWidget(_body(
            "<table style='margin-left:8px; border-spacing:3px;'>"
            f"<tr><td style='color:{_ACCENT}; vertical-align:top;'>•</td>"
            "<td><b>Drag</b> onset markers to adjust their timing</td></tr>"
            f"<tr><td style='color:{_ACCENT}; vertical-align:top;'>•</td>"
            "<td><b>Shift+click</b> the waveform to add new onsets</td></tr>"
            f"<tr><td style='color:{_ACCENT}; vertical-align:top;'>•</td>"
            "<td><b>Delete</b> incorrect onsets via the table or keyboard</td></tr>"
            f"<tr><td style='color:{_ACCENT}; vertical-align:top;'>•</td>"
            "<td><b>Undo / Redo</b> any change (Ctrl+Z / Ctrl+Shift+Z)</td></tr>"
            f"<tr><td style='color:{_ACCENT}; vertical-align:top;'>•</td>"
            "<td><b>Save</b> corrected onsets back to Audacity label files or Excel</td></tr>"
            f"<tr><td style='color:{_ACCENT}; vertical-align:top;'>•</td>"
            "<td>Use <b>Onset Layers</b> to maintain multiple independent "
            "onset sets per file</td></tr>"
            f"<tr><td style='color:{_ACCENT}; vertical-align:top;'>•</td>"
            "<td>Define <b>Focus Regions</b> (time + frequency bounds) to "
            "concentrate analysis on specific sections</td></tr>"
            "</table>"
        ))
        lay.addWidget(_dim(
            "The table beside the viewer shows each onset's time, "
            "inter-onset interval (IOI), rhythm ratio (r_k), and "
            "whether the dyad is rhythmically stable. Editing an onset "
            "in either the viewer or the table updates both instantly."
        ))

        lay.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return page

    def _build_step_selection(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {_BG}; }}")
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(40, 36, 40, 20)
        lay.setSpacing(10)

        lay.addWidget(_heading("Which steps do you want to walk through?", size=18))
        lay.addSpacing(4)
        lay.addWidget(_body(
            "Tick the steps you'd like the walkthrough to cover. We'll "
            "skip any unchecked steps and won't walk through their "
            "settings."
        ))
        lay.addSpacing(2)
        lay.addWidget(_dim(
            "First time? Keep the five core steps checked. The "
            "Experimental Analyses / Figures section below is opt-in — "
            "click its header to expand it and enable the pages you "
            "want to read through."
        ))
        lay.addSpacing(10)

        self._step_checks = [None] * 16
        step_descriptions = [
            # Core production steps (0-4)
            "Clean and denoise your raw audio files (includes optional Demucs source separation)",
            "Detect beat events and compute rhythm metrics",
            "Generate 2D raster plots and optional 3D flowers",
            "Create rhythm-ratio distribution histograms",
            "Compare nPVI across groups using raincloud plots",
            # Experimental: multi-species analyses (5-14)
            "Plot r_k distributions per group with isochronous-band overlay",
            "Kolmogorov–Smirnov test of each group's r_k distribution against a null",
            "One-sample Wilcoxon test of isochrony preference vs. chance",
            "Pearson lag-1 autocorrelation of inter-onset intervals per bout",
            "2-D density heatmap of tempo (BPM) × rhythm ratio — the Roeske landscape",
            "Raincloud plots (half-violin + box + jitter) for multiple rhythm metrics",
            "Permuted Discriminant Function Analysis (LDA + restricted permutation)",
            "Test rhythmic vs. geographic (and optional phylogenetic) distance",
            "Mixed-effects model of a rhythmic response with random effects",
            "Species-level regression with phylogenetic covariance correction",
            # Experimental: association-rule mining (15)
            "Apriori association-rule mining over the rhythm-metric table (exploratory)",
        ]

        def _add_section_label(parent_lay, text, tooltip=None):
            hdr = QLabel(text)
            hdr.setFont(QFont("", 13, QFont.Weight.Bold))
            hdr.setStyleSheet(
                f"color: {_ACCENT}; background: transparent;"
                "  padding-top: 4px;"
            )
            parent_lay.addWidget(hdr)
            if tooltip:
                parent_lay.addWidget(_dim(tooltip))
            parent_lay.addSpacing(4)

        def _add_step_card(parent_lay, i, default_checked):
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background-color: {_BG_MID};"
                f"  border: 1px solid {_BORDER}; border-radius: 6px; }}"
            )
            card_lay = QHBoxLayout(card)
            card_lay.setContentsMargins(12, 8, 12, 8)
            card_lay.setSpacing(10)

            cb = QCheckBox()
            cb.setChecked(default_checked)
            cb.setStyleSheet(
                f"QCheckBox {{ background: transparent; }}"
                f"QCheckBox::indicator {{ width: 18px; height: 18px; }}"
            )
            cb.toggled.connect(
                lambda checked, idx=i: self._on_step_toggled(idx, checked)
            )
            card_lay.addWidget(cb)

            text_lay = QVBoxLayout()
            text_lay.setSpacing(2)
            name_lbl = QLabel(_STEP_NAMES[i])
            name_lbl.setFont(QFont("", 13, QFont.Weight.Bold))
            name_lbl.setStyleSheet(f"color: {_TEXT}; background: transparent;")
            text_lay.addWidget(name_lbl)
            desc_lbl = QLabel(step_descriptions[i])
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet(
                f"color: {_TEXT_DIM}; font-size: 12px; background: transparent;"
            )
            text_lay.addWidget(desc_lbl)
            card_lay.addLayout(text_lay, stretch=1)

            parent_lay.addWidget(card)
            self._step_checks[i] = cb

        # ── Core Analyses / Figures (always visible) ──
        _add_section_label(lay, "Analyses / Figures")
        for i in range(5):
            _add_step_card(lay, i, default_checked=True)

        lay.addSpacing(10)

        # ── Experimental Analyses / Figures (collapsible, default collapsed) ──
        self._exp_selection_collapsed = True
        exp_toggle = QPushButton()
        exp_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        exp_toggle.setStyleSheet(
            f"QPushButton {{"
            f"  text-align: left; color: {_ACCENT};"
            f"  background: transparent; border: none;"
            f"  border-top: 1px solid {_BORDER};"
            f"  font-size: 13px; font-weight: bold;"
            f"  padding: 10px 4px 6px 4px;"
            f"}}"
            f"QPushButton:hover {{ color: {_ACCENT_HOVER}; }}"
        )
        exp_toggle.setToolTip(
            "Click to show or hide the experimental analyses. "
            "These cross-group analyses are optional and all opt-in."
        )
        lay.addWidget(exp_toggle)

        exp_hint = _dim(
            "Advanced cross-group analyses that consume the Excel "
            "workbook from the Onset Finder. Each is independent — "
            "enable only the ones you need. Association Rule Learning "
            "is an exploratory hypothesis-generation tool and lives at "
            "the bottom of this section."
        )
        exp_hint.setVisible(False)
        lay.addWidget(exp_hint)

        exp_container = QWidget()
        exp_container.setStyleSheet("background: transparent;")
        exp_lay = QVBoxLayout(exp_container)
        exp_lay.setContentsMargins(0, 4, 0, 0)
        exp_lay.setSpacing(8)
        exp_container.setVisible(False)
        lay.addWidget(exp_container)

        # Multi-species analyses (5-14) + ARL (15) — all inside collapsible
        for i in range(5, 16):
            _add_step_card(exp_lay, i, default_checked=False)

        def _refresh_exp_toggle():
            arrow = "▸" if self._exp_selection_collapsed else "▾"
            exp_toggle.setText(
                f"  {arrow}  EXPERIMENTAL ANALYSES / FIGURES"
            )

        def _toggle_exp():
            self._exp_selection_collapsed = not self._exp_selection_collapsed
            exp_container.setVisible(not self._exp_selection_collapsed)
            exp_hint.setVisible(not self._exp_selection_collapsed)
            _refresh_exp_toggle()

        exp_toggle.clicked.connect(_toggle_exp)
        _refresh_exp_toggle()

        lay.addSpacing(8)
        lay.addWidget(_dim(
            "These choices also update the run-include checkboxes on the "
            "main sidebar, so the pipeline will only execute the steps "
            "you select here."
        ))
        lay.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return page

    def _build_finish(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(40, 36, 40, 20)
        lay.setSpacing(10)

        lay.addStretch(1)

        # Large title
        done_lbl = QLabel("You're all set!")
        done_lbl.setFont(QFont("", 22, QFont.Weight.Bold))
        done_lbl.setStyleSheet(f"color: {_ACCENT}; background: transparent;")
        lay.addWidget(done_lbl)
        lay.addSpacing(8)

        lay.addWidget(_body(
            "You've walked through all the selected pipeline steps and "
            "their settings. Here's what to do next:"
        ))
        lay.addSpacing(4)

        lay.addWidget(_body(
            "<table style='margin-left:8px; border-spacing:6px;'>"
            f"<tr><td style='color:{_ACCENT}; font-weight:bold; vertical-align:top; "
            f"padding-right:6px;'>1.</td>"
            "<td>Review or tweak any settings on the main window — the "
            "panels are on the right-hand side</td></tr>"
            f"<tr><td style='color:{_ACCENT}; font-weight:bold; vertical-align:top; "
            f"padding-right:6px;'>2.</td>"
            "<td>Check the <b>Config Preview</b> at the bottom to see "
            "exactly what will be sent to the pipeline</td></tr>"
            f"<tr><td style='color:{_ACCENT}; font-weight:bold; vertical-align:top; "
            f"padding-right:6px;'>3.</td>"
            "<td>Hit the green <b>Run &#x25B6;</b> button to start "
            "processing!</td></tr>"
            "</table>"
        ))

        lay.addSpacing(8)
        lay.addWidget(_dim(
            "You can re-open this walkthrough any time from the Descriptions "
            "dropdown in the top bar."
        ))

        lay.addStretch(2)

        close_btn = QPushButton("  Close Walkthrough  ")
        close_btn.setFixedWidth(220)
        close_btn.setStyleSheet(
            f"QPushButton {{ background-color: {_ACCENT_DIM}; color: white; "
            f"border-radius: 7px; padding: 10px 20px; border: none; "
            f"font-size: 14px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {_ACCENT}; }}"
        )
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        lay.addStretch(1)
        return page

    # ── Step selection callback ────────────────────────────────────

    def _show_package_info(self):
        """Open the package inventory pop-up."""
        dlg = _PackageInfoDialog(parent=self)
        dlg.exec()

    # Map walkthrough step indices → sidebar step indices.
    #   0-4  → sidebar 2-6 (Audio Editor … nPVI Group Plot)
    #   5-14 → sidebar 7-16 (the ten multi-species analyses)
    #   15   → sidebar 17  (Association Rule Learning, experimental)
    _WALKTHROUGH_TO_SIDEBAR = [2, 3, 4, 5, 6] + list(range(7, 17)) + [17]

    def _on_step_toggled(self, idx, checked):
        self._selected_steps[idx] = checked
        self._rebuild_page_order()
        # Also update sidebar run checkboxes on the main window
        if self._main is not None:
            sidebar_idx = self._WALKTHROUGH_TO_SIDEBAR[idx]
            try:
                self._main.sidebar._set_run_flag(sidebar_idx, checked)
            except Exception:
                pass

    # ── Page ordering ──────────────────────────────────────────────

    def _rebuild_page_order(self):
        """Rebuild the list of page indices based on selected steps.

        Core production steps (0-4) appear only when ticked, matching
        the original 'walk through the steps I'm going to run' behaviour.

        Experimental Analyses / Figures steps (5-15) are <b>always</b>
        included so they can be browsed / read from the walkthrough
        regardless of whether the user has ticked them to run. The tick
        box on those cards still controls the sidebar run-flag on the
        main window — it just no longer gates walkthrough navigation.
        """
        order = [0, 1, 2]  # Welcome, Overview, Step Selection
        for i in range(self._n_steps):
            if i < 5:
                if self._selected_steps[i]:
                    order.append(self._step_pages_start + i)
            else:
                # Experimental: always navigable
                order.append(self._step_pages_start + i)
        order.append(self._finish_idx)
        self._ordered_pages = order
        # Clamp current index
        if self._current_order_idx >= len(self._ordered_pages):
            self._current_order_idx = len(self._ordered_pages) - 1
        self._rebuild_section_list()
        self._sync_nav()

    # ── Section selector sidebar ───────────────────────────────────

    def _build_section_list(self):
        """Create the left-hand Section Selection list widget (empty)."""
        lst = QListWidget()
        lst.setFixedWidth(240)
        lst.setFrameShape(QFrame.Shape.NoFrame)
        lst.setStyleSheet(
            f"QListWidget {{"
            f"  background-color: {_BG_MID};"
            f"  color: {_TEXT};"
            f"  border: none;"
            f"  border-right: 1px solid {_BORDER};"
            f"  padding: 6px 0px;"
            f"  outline: 0;"
            f"  font-size: 13px;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 8px 14px;"
            f"  border-left: 3px solid transparent;"
            f"}}"
            f"QListWidget::item:hover {{"
            f"  background-color: {_BG_WIDGET};"
            f"}}"
            f"QListWidget::item:selected {{"
            f"  background-color: {_BG_INPUT};"
            f"  color: {_TEXT};"
            f"  border-left: 3px solid {_ACCENT};"
            f"}}"
            f"QListWidget::item:disabled {{"
            f"  color: {_TEXT_DIM};"
            f"  background: transparent;"
            f"  padding-top: 10px;"
            f"  padding-bottom: 2px;"
            f"  font-size: 11px;"
            f"  font-weight: bold;"
            f"  letter-spacing: 0.5px;"
            f"}}"
        )
        lst.itemClicked.connect(self._on_section_clicked)
        return lst

    def _rebuild_section_list(self):
        """Refresh the Section Selection sidebar to match the current
        ordered page list. Section headers are added as disabled items
        for visual grouping. The Experimental Analyses / Figures group
        is collapsible (click the header to toggle)."""
        lst = self._section_list
        lst.blockSignals(True)
        lst.clear()
        # Track rows belonging to the collapsible experimental group
        # so they can be hidden/shown in one shot.
        self._exp_section_rows = []
        if not hasattr(self, "_exp_section_collapsed"):
            self._exp_section_collapsed = True

        # Sentinel for the experimental-group toggle header row
        _EXP_TOGGLE = -99

        def _add_header(text, toggle_data=-1):
            it = QListWidgetItem(text.upper())
            if toggle_data == _EXP_TOGGLE:
                it.setFlags(Qt.ItemFlag.ItemIsEnabled)  # clickable, not "selectable"
                it.setData(Qt.ItemDataRole.UserRole, _EXP_TOGGLE)
                it.setToolTip(
                    "Click to show or hide the experimental analyses."
                )
            else:
                it.setFlags(Qt.ItemFlag.NoItemFlags)  # decorative
                it.setData(Qt.ItemDataRole.UserRole, -1)
            lst.addItem(it)
            return lst.count() - 1  # row index

        def _add_entry(label, order_idx):
            it = QListWidgetItem("   " + label)
            it.setData(Qt.ItemDataRole.UserRole, order_idx)
            lst.addItem(it)
            return lst.count() - 1

        # Fixed intro entries (always present)
        _add_header("Getting Started")
        _add_entry("Welcome", 0)
        _add_entry("Pipeline Overview", 1)
        _add_entry("Step Selection", 2)

        # Core processing (Audio Editor, Onset Finder — walkthrough 0-1)
        core_added = False
        for order_idx in range(3, len(self._ordered_pages) - 1):
            page_idx = self._ordered_pages[order_idx]
            step_i = page_idx - self._step_pages_start
            if 0 <= step_i < 2:
                if not core_added:
                    _add_header("Core Processing")
                    core_added = True
                _add_entry(_STEP_NAMES[step_i], order_idx)

        # Analyses / Figures (Flower Raster, Histogram, nPVI — walkthrough 2-4)
        figs_added = False
        for order_idx in range(3, len(self._ordered_pages) - 1):
            page_idx = self._ordered_pages[order_idx]
            step_i = page_idx - self._step_pages_start
            if 2 <= step_i < 5:
                if not figs_added:
                    _add_header("Analyses / Figures")
                    figs_added = True
                _add_entry(_STEP_NAMES[step_i], order_idx)

        # Experimental Analyses / Figures (collapsible)
        # Build the header row regardless of whether any entries follow;
        # the user can click it to toggle visibility of the whole group.
        arrow = "▸" if self._exp_section_collapsed else "▾"
        hdr_row = _add_header(
            f"{arrow}  Experimental Analyses / Figures",
            toggle_data=_EXP_TOGGLE,
        )
        self._exp_header_row = hdr_row
        for order_idx in range(3, len(self._ordered_pages) - 1):
            page_idx = self._ordered_pages[order_idx]
            step_i = page_idx - self._step_pages_start
            if 5 <= step_i < self._n_steps:
                row = _add_entry(_STEP_NAMES[step_i], order_idx)
                self._exp_section_rows.append(row)

        # Finish entry
        _add_header("Wrap Up")
        _add_entry("Finish", len(self._ordered_pages) - 1)

        # Apply current collapsed state
        for row in self._exp_section_rows:
            lst.setRowHidden(row, self._exp_section_collapsed)

        lst.blockSignals(False)
        # Highlight current
        self._sync_section_selection()

    def _sync_section_selection(self):
        """Highlight the list item matching the current page."""
        if not hasattr(self, "_section_list"):
            return
        lst = self._section_list
        target = self._current_order_idx
        for row in range(lst.count()):
            it = lst.item(row)
            if it.data(Qt.ItemDataRole.UserRole) == target:
                lst.blockSignals(True)
                lst.setCurrentRow(row)
                lst.blockSignals(False)
                return
        lst.clearSelection()

    def _on_section_clicked(self, item):
        """Jump to the page a user clicked in the sidebar, or toggle the
        experimental group if the user clicked its header."""
        order_idx = item.data(Qt.ItemDataRole.UserRole)
        # Experimental-group toggle header
        if order_idx == -99:
            self._exp_section_collapsed = not self._exp_section_collapsed
            # Update header caption arrow + hide/show rows in place.
            lst = self._section_list
            if getattr(self, "_exp_header_row", None) is not None:
                hdr = lst.item(self._exp_header_row)
                arrow = "▸" if self._exp_section_collapsed else "▾"
                hdr.setText(
                    f"{arrow}  EXPERIMENTAL ANALYSES / FIGURES"
                )
            for row in getattr(self, "_exp_section_rows", []):
                lst.setRowHidden(row, self._exp_section_collapsed)
            # Re-sync selection highlight after the list mutates.
            self._sync_section_selection()
            return
        if order_idx is None or order_idx < 0:
            return
        if 0 <= order_idx < len(self._ordered_pages):
            self._current_order_idx = order_idx
            self._sync_nav()

    # ── Navigation ─────────────────────────────────────────────────

    def _sync_nav(self):
        idx = self._current_order_idx
        total = len(self._ordered_pages)
        page_idx = self._ordered_pages[idx]
        self._pages.setCurrentIndex(page_idx)
        self._back_btn.setEnabled(idx > 0)
        is_last = idx == total - 1
        self._next_btn.setText("Finish" if is_last else "Next →")
        self._page_indicator.setText(f"Page {idx + 1} of {total}")
        self._sync_section_selection()

    def _go_next(self):
        if self._current_order_idx >= len(self._ordered_pages) - 1:
            self.accept()
            return
        self._current_order_idx += 1
        self._sync_nav()

    def _go_back(self):
        if self._current_order_idx > 0:
            self._current_order_idx -= 1
            self._sync_nav()
