from __future__ import annotations

import json
import os

import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFontMetrics
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from form_widgets import (
        AUDIO_EXTENSIONS,
        DescriptionLabel,
        _ALL_DESC_LABELS,
        _add_checkbox,
        _add_row,
        get_form_widget_palette,
    )
except ImportError:
    from GUI.form_widgets import (
        AUDIO_EXTENSIONS,
        DescriptionLabel,
        _ALL_DESC_LABELS,
        _add_checkbox,
        _add_row,
        get_form_widget_palette,
    )


_PREP_HINT_DEFAULTS = {
    "target_character": "auto",
    "recording_quality": "auto",
    "target_density": "auto",
    "prefer_onset_method": "auto",
    "speech_like": False,
    "use_signal_hints": True,
    "expected_bpm": None,
    "signal_min_hz": None,
    "signal_max_hz": None,
}


def _prep_default_hints() -> dict:
    return dict(_PREP_HINT_DEFAULTS)


def _prep_float_or_none(value):
    if value in (None, "", "None", "none"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _prep_sanitize_hints(raw: dict | None) -> dict:
    hints = _prep_default_hints()
    if not isinstance(raw, dict):
        return hints

    for key in hints:
        if key in raw:
            hints[key] = raw.get(key)

    valid_target = {"auto", "percussive", "harmonic", "mixed"}
    valid_quality = {"auto", "clean", "moderate", "noisy"}
    valid_density = {"auto", "sparse", "moderate", "dense"}
    valid_methods = {
        "auto", "adaptive_hp", "librosa", "moving_median", "superflux",
        "cfar", "per_band", "madmom_beats", "syllable_nuclei",
        "whisper_words", "whisperx_phonemes",
    }

    target_character = str(hints.get("target_character", "auto")).strip().lower()
    hints["target_character"] = target_character if target_character in valid_target else "auto"

    recording_quality = str(hints.get("recording_quality", "auto")).strip().lower()
    hints["recording_quality"] = recording_quality if recording_quality in valid_quality else "auto"

    target_density = str(hints.get("target_density", "auto")).strip().lower()
    hints["target_density"] = target_density if target_density in valid_density else "auto"

    preferred_method = str(hints.get("prefer_onset_method", "auto")).strip().lower()
    hints["prefer_onset_method"] = preferred_method if preferred_method in valid_methods else "auto"

    hints["speech_like"] = bool(hints.get("speech_like", False))
    hints["use_signal_hints"] = bool(hints.get("use_signal_hints", True))
    hints["expected_bpm"] = _prep_float_or_none(hints.get("expected_bpm"))
    hints["signal_min_hz"] = _prep_float_or_none(hints.get("signal_min_hz"))
    hints["signal_max_hz"] = _prep_float_or_none(hints.get("signal_max_hz"))

    signal_min_hz = hints["signal_min_hz"]
    signal_max_hz = hints["signal_max_hz"]
    if signal_min_hz is not None and signal_min_hz < 20:
        signal_min_hz = 20.0
    if signal_max_hz is not None and signal_max_hz < 20:
        signal_max_hz = None
    if signal_min_hz is not None and signal_max_hz is not None and signal_min_hz >= signal_max_hz:
        signal_min_hz, signal_max_hz = min(signal_min_hz, signal_max_hz), max(signal_min_hz, signal_max_hz)
    hints["signal_min_hz"] = signal_min_hz
    hints["signal_max_hz"] = signal_max_hz
    return hints


def _prep_infer_signal_character(harmonicity: float) -> str:
    if harmonicity >= 0.65:
        return "harmonic"
    if harmonicity <= 0.35:
        return "percussive"
    return "mixed"


def _make_title_info_button(group, tooltip: str, callback):
    """Attach a small circular help button next to a QGroupBox title."""
    palette = get_form_widget_palette()
    btn = QPushButton("i", group)
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedSize(16, 16)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setStyleSheet(
        f"QPushButton {{ background-color: {palette.bg_widget}; color: {palette.text_dim}; "
        f"border: 1px solid {palette.border}; border-radius: 8px; "
        f"padding: 0px; font-size: 10px; font-weight: 700; "
        f"font-style: italic; font-family: Georgia, serif; }} "
        f"QPushButton:hover {{ color: {palette.accent}; border-color: {palette.accent}; }}"
    )
    btn.clicked.connect(callback)

    def _position():
        title = (group.title() or "").upper()
        font_metrics = QFontMetrics(group.font())
        text_width = font_metrics.horizontalAdvance(title) + int(0.6 * max(0, len(title) - 1))
        x = 16 + 8 + text_width + 6
        y = 2
        btn.move(x, y)
        btn.raise_()

    _position()
    QTimer.singleShot(0, _position)
    return btn


def _prep_profile_from_focus_regions(folder: str, filename: str):
    stem = os.path.splitext(filename)[0]
    path = os.path.join(folder, f"{stem}_focus_regions.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as file_obj:
            data = json.load(file_obj)
    except Exception:
        return None

    regions = []
    if isinstance(data, dict):
        regions = data.get(filename, data.get(stem, []))
    if not isinstance(regions, list) or not regions:
        return None

    positive_regions = [region for region in regions if isinstance(region, dict)
                        and region.get("polarity") != "negative"]
    negative_regions = [region for region in regions if isinstance(region, dict)
                        and region.get("polarity") == "negative"]

    def _summarize(region_rows: list[dict]):
        if not region_rows:
            return {}
        lows = [float(region.get("f_low", 0)) for region in region_rows if region.get("f_low") is not None]
        highs = [float(region.get("f_high", 0)) for region in region_rows if region.get("f_high") is not None]
        if not lows or not highs:
            return {}
        f_low = max(20.0, min(lows))
        f_high = max(f_low + 20.0, max(highs))
        bandwidth = max(50.0, f_high - f_low)
        return {
            "freq_range_hz": [round(f_low, 1), round(f_high, 1)],
            "harmonicity": 0.5,
            "attack_sharpness": 0.2,
            "signal_character": "mixed",
            "spectral_bandwidth_hz": round(bandwidth, 1),
            "avg_signal_duration_s": round(np.mean([
                max(0.0, float(region.get("t_end", 0)) - float(region.get("t_start", 0)))
                for region in region_rows
            ]), 3),
            "n_regions": len(region_rows),
        }

    summary = _summarize(positive_regions)
    if not summary:
        return None
    return {
        "summary": summary,
        "regions": positive_regions,
        "negative_summary": _summarize(negative_regions),
        "negative_regions": negative_regions,
    }


def _prep_profile_from_selected_signals(folder: str, filename: str,
                                        spectral_profile_fn,
                                        hp_ratio_fn):
    stem = os.path.splitext(filename)[0]
    base = os.path.join(folder, f"{stem}_SelectedSignals")
    if not os.path.isdir(base):
        return None

    def _list_clips(subdir: str):
        path = os.path.join(base, subdir)
        if not os.path.isdir(path):
            return []
        return [
            os.path.join(path, clip_name)
            for clip_name in sorted(os.listdir(path))
            if os.path.splitext(clip_name)[1].lower() in AUDIO_EXTENSIONS
        ]

    positive_clips = _list_clips("signalPositive")
    negative_clips = _list_clips("signalNegative")
    if not positive_clips and not negative_clips:
        return None

    def _summarize(clips: list[str]):
        if not clips:
            return {}
        import librosa

        lows, highs, harmonicities, attacks, durations = [], [], [], [], []
        for clip in clips[:12]:
            try:
                y, sr = librosa.load(clip, sr=None, mono=True)
            except Exception:
                continue
            if y.size < 16 or sr <= 0:
                continue
            durations.append(float(y.size) / float(sr))
            spectral_profile = spectral_profile_fn(y, sr)
            harmonicity, _ = hp_ratio_fn(y, sr)
            harmonicities.append(float(harmonicity))

            centroid = float(spectral_profile.get("spectral_centroid_hz", 0.0))
            bandwidth = max(50.0, float(spectral_profile.get("spectral_bandwidth_hz", 200.0)))
            low = max(20.0, centroid - 0.7 * bandwidth)
            high = min(float(sr) / 2.0, centroid + 0.7 * bandwidth)
            lows.append(low)
            highs.append(max(high, low + 20.0))

            envelope = np.abs(y)
            if envelope.size > 4:
                diff = np.diff(envelope)
                rising = np.maximum(diff, 0.0)
                scale = float(np.mean(envelope) + 1e-9)
                attacks.append(float(np.percentile(rising, 95) / scale))

        if not lows or not highs:
            return {}

        f_low = float(np.percentile(lows, 15))
        f_high = float(np.percentile(highs, 85))
        harmonicity = float(np.mean(harmonicities)) if harmonicities else 0.5
        attack = float(np.mean(attacks)) if attacks else 0.2
        return {
            "freq_range_hz": [round(f_low, 1), round(max(f_high, f_low + 20), 1)],
            "harmonicity": round(harmonicity, 4),
            "attack_sharpness": round(max(0.0, min(attack, 3.0)), 4),
            "signal_character": _prep_infer_signal_character(harmonicity),
            "spectral_bandwidth_hz": round(max(50.0, f_high - f_low), 1),
            "avg_signal_duration_s": round(float(np.mean(durations)), 3) if durations else 0.0,
            "n_regions": len(clips),
        }

    positive_summary = _summarize(positive_clips)
    if not positive_summary:
        return None
    negative_summary = _summarize(negative_clips)
    return {
        "summary": positive_summary,
        "regions": [],
        "negative_summary": negative_summary,
        "negative_regions": [],
    }


def _prep_load_signal_profile_hint(folder: str, filename: str,
                                   spectral_profile_fn,
                                   hp_ratio_fn):
    stem = os.path.splitext(filename)[0]
    explicit = os.path.join(folder, f"{stem}_signal_profile.json")
    if os.path.isfile(explicit):
        try:
            with open(explicit, encoding="utf-8") as file_obj:
                data = json.load(file_obj)
            if isinstance(data, dict) and isinstance(data.get("summary"), dict):
                return data, "signal_profile"
        except Exception:
            pass

    from_selected = _prep_profile_from_selected_signals(
        folder, filename, spectral_profile_fn, hp_ratio_fn)
    if from_selected:
        return from_selected, "selected_signals"

    from_focus = _prep_profile_from_focus_regions(folder, filename)
    if from_focus:
        return from_focus, "focus_regions"

    return None, "none"


def _prep_apply_hints_to_profile(profile: dict | None, hints: dict):
    hints = _prep_sanitize_hints(hints)
    signal_min_hz = hints.get("signal_min_hz")
    signal_max_hz = hints.get("signal_max_hz")
    target_character = hints.get("target_character", "auto")

    if profile is None:
        if signal_min_hz is None and signal_max_hz is None and target_character == "auto":
            return None
        base_low = float(signal_min_hz if signal_min_hz is not None else 80.0)
        base_high = float(signal_max_hz if signal_max_hz is not None else max(base_low + 300.0, 4000.0))
        harmonicity = 0.5
        if target_character == "harmonic":
            harmonicity = 0.8
        elif target_character == "percussive":
            harmonicity = 0.2
        profile = {
            "summary": {
                "freq_range_hz": [base_low, base_high],
                "harmonicity": harmonicity,
                "attack_sharpness": 0.25,
                "signal_character": ("mixed" if target_character == "auto" else target_character),
                "spectral_bandwidth_hz": max(50.0, base_high - base_low),
                "avg_signal_duration_s": 0.08,
                "n_regions": 1,
            },
            "regions": [],
            "negative_summary": {},
            "negative_regions": [],
        }

    summary = profile.setdefault("summary", {})
    freq_range = summary.get("freq_range_hz", [80.0, 5000.0])
    current_low = _prep_float_or_none(freq_range[0] if isinstance(freq_range, list) and freq_range else 80.0) or 80.0
    current_high = _prep_float_or_none(freq_range[1] if isinstance(freq_range, list) and len(freq_range) > 1 else 5000.0) or 5000.0
    if signal_min_hz is not None:
        current_low = signal_min_hz
    if signal_max_hz is not None:
        current_high = signal_max_hz
    if current_high <= current_low:
        current_high = current_low + 50.0
    summary["freq_range_hz"] = [float(current_low), float(current_high)]
    summary["spectral_bandwidth_hz"] = float(max(50.0, current_high - current_low))

    if target_character != "auto":
        summary["signal_character"] = target_character
        if target_character == "harmonic":
            summary["harmonicity"] = 0.8
        elif target_character == "percussive":
            summary["harmonicity"] = 0.2
        else:
            summary["harmonicity"] = 0.5

    summary.setdefault("attack_sharpness", 0.2)
    summary.setdefault("n_regions", 1)
    return profile


def _prep_apply_hint_overrides_to_muter(settings: dict,
                                        analysis: dict,
                                        hints: dict):
    hints = _prep_sanitize_hints(hints)
    notes = []

    quality = hints.get("recording_quality", "auto")
    if quality == "noisy":
        settings["MUTER_SPECTRAL_DENOISE"] = True
        settings["MUTER_DENOISE_STRENGTH"] = max(
            1.5, float(settings.get("MUTER_DENOISE_STRENGTH", 1.5)))
        settings["MUTER_NOISE_MARGIN_DB"] = max(
            9.0, float(settings.get("MUTER_NOISE_MARGIN_DB", 8.0)))
        notes.append("noisy-profile")
    elif quality == "clean":
        settings["MUTER_DENOISE_STRENGTH"] = min(
            1.0, float(settings.get("MUTER_DENOISE_STRENGTH", 1.0)))
        settings["MUTER_NOISE_MARGIN_DB"] = min(
            7.0, float(settings.get("MUTER_NOISE_MARGIN_DB", 7.0)))
        notes.append("clean-profile")

    signal_min_hz = hints.get("signal_min_hz")
    signal_max_hz = hints.get("signal_max_hz")
    if signal_min_hz is not None:
        highpass = max(20, int(round(max(20.0, signal_min_hz * 0.65) / 10.0) * 10))
        settings["MUTER_HIGHPASS_HZ"] = highpass
        notes.append(f"hint-hp:{highpass}")
    if signal_max_hz is not None:
        lowpass = int(round(min(22000.0, signal_max_hz * 1.35) / 10.0) * 10)
        settings["MUTER_LOWPASS_HZ"] = max(lowpass, int((signal_min_hz or 20) + 50))
        notes.append(f"hint-lp:{settings['MUTER_LOWPASS_HZ']}")

    target_character = hints.get("target_character", "auto")
    if target_character in {"percussive", "harmonic"}:
        settings["MUTER_HPSS_ENABLED"] = True
        settings["MUTER_HPSS_TARGET"] = target_character
        settings["MUTER_HPSS_MARGIN"] = max(
            2.0, float(settings.get("MUTER_HPSS_MARGIN", 2.0)))
        notes.append(f"hpss:{target_character}")

    settings["MUTER_RESAMPLE_SR"] = int(settings.get("MUTER_RESAMPLE_HZ", 0) or 0)

    snr = _prep_float_or_none(analysis.get("snr_db"))
    if snr is not None and snr < 10:
        settings["MUTER_AUTO_THRESHOLD"] = True
        settings["MUTER_NOISE_MARGIN_DB"] = max(
            10.0, float(settings.get("MUTER_NOISE_MARGIN_DB", 10.0)))
        notes.append("low-snr")

    return notes


def _prep_recommend_onset_settings(analysis: dict,
                                   muter_settings: dict,
                                   hints: dict):
    hints = _prep_sanitize_hints(hints)
    reasoning = {}

    preferred_method = hints.get("prefer_onset_method", "auto")
    speech_like = bool(hints.get("speech_like", False))
    harmonic_ratio = float(analysis.get("harmonic_ratio", 0.5) or 0.5)
    percussive_ratio = float(analysis.get("percussive_ratio", 0.5) or 0.5)
    snr = float(analysis.get("snr_db", 20.0) or 20.0)

    if preferred_method != "auto":
        method = preferred_method
        reasoning["ONSET_METHOD"] = f"User hint selected {method}."
    elif speech_like:
        method = "syllable_nuclei"
        reasoning["ONSET_METHOD"] = "Speech-like hint favors syllable nuclei detection."
    elif percussive_ratio >= 0.62:
        method = "madmom_beats" if snr >= 12 else "superflux"
        reasoning["ONSET_METHOD"] = (
            f"Percussive-dominant signal (P={percussive_ratio:.2f}) favors {method}.")
    elif harmonic_ratio >= 0.62:
        method = "adaptive_hp"
        reasoning["ONSET_METHOD"] = (
            f"Harmonic-dominant signal (H={harmonic_ratio:.2f}) favors adaptive HP onset tracking.")
    else:
        method = "librosa" if snr >= 15 else "superflux"
        reasoning["ONSET_METHOD"] = (
            f"Mixed content with SNR {snr:.1f} dB favors {method}.")

    expected_bpm = hints.get("expected_bpm")
    if expected_bpm is not None and expected_bpm > 0:
        min_ioi = int(max(8.0, min(120.0, (60000.0 / expected_bpm) * 0.45)))
        reasoning["MIN_INTER_ONSET_MS"] = (
            f"Expected tempo {expected_bpm:.0f} BPM sets min inter-onset to {min_ioi} ms.")
    else:
        target_density = hints.get("target_density", "auto")
        if target_density == "dense":
            min_ioi = 12
        elif target_density == "sparse":
            min_ioi = 42
        elif target_density == "moderate":
            min_ioi = 24
        else:
            if percussive_ratio >= 0.65:
                min_ioi = 18
            elif harmonic_ratio >= 0.65:
                min_ioi = 36
            else:
                min_ioi = 26
            if snr < 12:
                min_ioi += 6
        reasoning["MIN_INTER_ONSET_MS"] = (
            f"Density/SNR heuristic selected {min_ioi} ms.")

    if snr < 10:
        delta = 0.13
    elif snr < 18:
        delta = 0.10
    elif snr < 28:
        delta = 0.08
    else:
        delta = 0.06

    highpass = int(muter_settings.get("MUTER_HIGHPASS_HZ", 0) or 0)

    target_character = hints.get("target_character", "auto")
    if target_character == "harmonic" and not speech_like:
        pitch_tracker = "pyin"
    else:
        pitch_tracker = "none"

    onset_settings = {
        "ONSET_METHOD": method,
        "MIN_INTER_ONSET_MS": int(min_ioi),
        "ONSET_DELTA": round(delta, 3),
        "APPLY_HIGHPASS_FILTER": highpass > 0,
        "HIGHPASS_CUTOFF_HZ": highpass if highpass > 0 else 80,
        "ONSET_REFINE_ENABLED": True,
        "TEMPO_ADAPTIVE_MIN_IOI": expected_bpm is None,
        "TEMPO_ADAPTIVE_FRACTION": 0.5,
        "PITCH_TRACKER": pitch_tracker,
    }
    return onset_settings, reasoning


class AnalysisHintsDialog(QDialog):
    """Small editor for pre-analysis hints used by Pipeline Prep."""

    def __init__(self, hints: dict | None = None, title: str = "Pre-Analysis Hints",
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        intro = QLabel(
            "These hints guide the Pre-Analyze step. Leave values on 'auto' when unknown.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.target_character = QComboBox()
        self.target_character.addItems(["auto", "percussive", "harmonic", "mixed"])
        _add_row(layout, "Target character", self.target_character,
                 "Main sound character you care about.",
                 extended_desc="Tells pre-analysis what kind of sound matters most in your "
                 "recordings. 'percussive' = sharp, transient events (drums, claps, knocks); "
                 "'harmonic' = sustained tonal sounds (whistles, songs, vocal calls); "
                 "'mixed' = both; 'auto' = let the program infer from spectral content. "
                 "Strongly affects HPSS settings and onset method choice.",
                 label_width=190)

        self.recording_quality = QComboBox()
        self.recording_quality.addItems(["auto", "clean", "moderate", "noisy"])
        _add_row(layout, "Recording quality", self.recording_quality,
                 "Expected noise level in the recording.",
                 extended_desc="Your expectation of how clean the recordings are. 'clean' = "
                 "studio or close-mic'd (SNR > 30 dB); 'moderate' = typical field recording "
                 "(SNR 15–30 dB); 'noisy' = distant, windy, or rainforest recordings "
                 "(SNR < 15 dB); 'auto' = estimate per file. Guides how aggressive denoising "
                 "and amplitude-gating recommendations will be.",
                 label_width=190)

        self.target_density = QComboBox()
        self.target_density.addItems(["auto", "sparse", "moderate", "dense"])
        _add_row(layout, "Event density", self.target_density,
                 "How frequent target onsets are expected to be.",
                 extended_desc="Roughly how often your target events occur. 'sparse' = a few "
                 "events per minute (single calls, isolated drums); 'moderate' = regular "
                 "events every few seconds (bouts, phrases); 'dense' = rapid-fire "
                 "(syllables, trills, fast drumming); 'auto' = infer from onset density. "
                 "Drives recommendations for minimum inter-onset interval and amplitude gate.",
                 label_width=190)

        self.prefer_onset_method = QComboBox()
        self.prefer_onset_method.addItems([
            "auto", "adaptive_hp", "librosa", "moving_median", "superflux",
            "cfar", "per_band", "madmom_beats", "syllable_nuclei",
            "whisper_words", "whisperx_phonemes",
        ])
        _add_row(layout, "Preferred onset method", self.prefer_onset_method,
                 "Force a specific onset method, or leave auto.",
                 extended_desc="Pin the Onset Finder to a specific detection algorithm rather "
                 "than letting pre-analysis pick for you. 'auto' = choose per file based on "
                 "acoustic character. See the Onset Finder panel for details on each method "
                 "(adaptive_hp is a robust default; madmom_beats = music; syllable_nuclei / "
                 "whisper_* = speech).",
                 label_width=190)

        self.speech_like = QCheckBox("Speech-like or vocal-rich content")
        _add_checkbox(layout, self.speech_like,
                      "Favor speech-aware onset heuristics.",
                      "When checked, pre-analysis weights syllable-nuclei and Whisper-based "
                      "onset methods higher, applies pause-based thresholding, and relaxes "
                      "minimum inter-onset intervals to accommodate natural speech rhythms. "
                      "Check this for human speech, primate vocalisations, or bird songs "
                      "with rapid syllabic structure.")

        self.use_signal_hints = QCheckBox("Use Selected Signals / Focus Regions hints")
        _add_checkbox(layout, self.use_signal_hints,
                      "Use positive/negative signal cues when available.",
                      "When checked, pre-analysis reads any Selected Signals (positive "
                      "exemplars) or Focus Regions (time-frequency zones) you drew in the "
                      "Onset Editor and uses them to tighten filter bands, amplitude gates, "
                      "and preset choices. Files without any signal/focus data fall back to "
                      "purely acoustic heuristics.")

        self.expected_bpm = QLineEdit("")
        self.expected_bpm.setPlaceholderText("e.g. 120")
        _add_row(layout, "Expected tempo (BPM)", self.expected_bpm,
                 "Optional expected tempo to tune minimum inter-onset interval.",
                 extended_desc="If you know the approximate tempo of the recordings (beats per "
                 "minute), enter it here. Pre-analysis uses it to derive a sensible minimum "
                 "inter-onset interval (≈ 60000 / BPM × 0.5). Leave blank for non-musical "
                 "data or when tempo is unknown.",
                 label_width=190)

        self.signal_min_hz = QLineEdit("")
        self.signal_min_hz.setPlaceholderText("e.g. 150")
        _add_row(layout, "Signal min frequency (Hz)", self.signal_min_hz,
                 "Optional lower frequency bound for target signal.",
                 extended_desc="Lowest frequency where your target signal has energy. Pre-"
                 "analysis uses this to pick a high-pass cutoff and target the bandpass "
                 "boost. Example values: 80 Hz for large mammal drumming, 500 Hz for bird "
                 "song, 2000 Hz for bat social calls. Leave blank for auto-detection.",
                 label_width=190)

        self.signal_max_hz = QLineEdit("")
        self.signal_max_hz.setPlaceholderText("e.g. 4000")
        _add_row(layout, "Signal max frequency (Hz)", self.signal_max_hz,
                 "Optional upper frequency bound for target signal.",
                 extended_desc="Highest frequency where your target signal has meaningful "
                 "energy. Used together with min frequency to set a low-pass cutoff and "
                 "define the bandpass boost region. Leave blank for auto-detection from the "
                 "spectrogram.",
                 label_width=190)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        reset_btn = buttons.addButton("Reset", QDialogButtonBox.ButtonRole.ResetRole)
        reset_btn.clicked.connect(self._reset)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._set_values(_prep_sanitize_hints(hints or {}))

    def _set_values(self, hints: dict):
        self.target_character.setCurrentText(str(hints.get("target_character", "auto")))
        self.recording_quality.setCurrentText(str(hints.get("recording_quality", "auto")))
        self.target_density.setCurrentText(str(hints.get("target_density", "auto")))
        self.prefer_onset_method.setCurrentText(str(hints.get("prefer_onset_method", "auto")))
        self.speech_like.setChecked(bool(hints.get("speech_like", False)))
        self.use_signal_hints.setChecked(bool(hints.get("use_signal_hints", True)))
        expected_bpm = hints.get("expected_bpm")
        self.expected_bpm.setText("" if expected_bpm is None else str(expected_bpm))
        signal_min_hz = hints.get("signal_min_hz")
        self.signal_min_hz.setText("" if signal_min_hz is None else str(signal_min_hz))
        signal_max_hz = hints.get("signal_max_hz")
        self.signal_max_hz.setText("" if signal_max_hz is None else str(signal_max_hz))

    def _reset(self):
        self._set_values(_prep_default_hints())

    def values(self) -> dict:
        return _prep_sanitize_hints({
            "target_character": self.target_character.currentText(),
            "recording_quality": self.recording_quality.currentText(),
            "target_density": self.target_density.currentText(),
            "prefer_onset_method": self.prefer_onset_method.currentText(),
            "speech_like": self.speech_like.isChecked(),
            "use_signal_hints": self.use_signal_hints.isChecked(),
            "expected_bpm": self.expected_bpm.text().strip(),
            "signal_min_hz": self.signal_min_hz.text().strip(),
            "signal_max_hz": self.signal_max_hz.text().strip(),
        })


class _MetadataColumnMappingDialog(QDialog):
    """Prompt the user to map imported-file columns to metadata fields."""

    def __init__(self, available_columns: list[str], auto_map: dict[str, str],
                 metadata_fields: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        palette = get_form_widget_palette()
        self.setWindowTitle("Map Metadata Columns")
        self.setMinimumWidth(520)
        self.setStyleSheet(
            f"QDialog {{ background-color: {palette.bg_mid}; color: {palette.text}; }}"
            f"QLabel {{ color: {palette.text}; background: transparent; }}"
            f"QComboBox {{ background-color: {palette.bg_widget}; color: {palette.text}; "
            f"border: 1px solid {palette.border}; padding: 3px 6px; }}"
        )
        self._combos: dict[str, QComboBox] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)

        intro = QLabel(
            "<b>Some expected columns were not auto-detected.</b><br>"
            "Pick the column from your file that should fill each field, "
            "or leave as <i>(none)</i> to fill missing values with "
            "<code>NA</code>."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {palette.text}; font-size: 12px;")
        root.addWidget(intro)

        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setColumnStretch(1, 1)

        file_name_label = QLabel("<b>File Name column</b>")
        grid.addWidget(file_name_label, 0, 0)
        file_name_combo = QComboBox()
        file_name_combo.addItem("(none — match by audio filename)")
        for column in available_columns:
            file_name_combo.addItem(column)
        preset = auto_map.get("__FILE__")
        if preset and preset in available_columns:
            file_name_combo.setCurrentText(preset)
        grid.addWidget(file_name_combo, 0, 1)
        self._combos["__FILE__"] = file_name_combo

        for row, (field, description) in enumerate(metadata_fields, start=1):
            label = QLabel(f"<b>{field}</b>")
            label.setToolTip(description)
            grid.addWidget(label, row, 0)
            combo = QComboBox()
            combo.addItem("(none — leave blank / fill NA)")
            for column in available_columns:
                combo.addItem(column)
            preset = auto_map.get(field)
            if preset and preset in available_columns:
                combo.setCurrentText(preset)
            grid.addWidget(combo, row, 1)
            self._combos[field] = combo

        root.addLayout(grid)
        root.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def mapping(self) -> dict[str, str]:
        output = {}
        for key, combo in self._combos.items():
            output[key] = "" if combo.currentIndex() == 0 else combo.currentText()
        return output


class _FileMetadataSection(QGroupBox):
    """Per-file metadata editor shown inside Pipeline Prep."""

    _NA = "NA"

    def __init__(self, parent_panel, metadata_fields: list[tuple[str, str]],
                 desc_level: int, parent=None):
        super().__init__("File Metadata", parent)
        self._panel = parent_panel
        self._metadata_fields = list(metadata_fields)
        self._desc_level = desc_level
        self._palette = get_form_widget_palette()
        self._filenames: list[str] = []
        self._per_file: dict[str, dict] = {}
        self._general: dict[str, str] = {}
        self._populating = False

        self._build_ui()
        self._reload_from_json()

    def _build_ui(self):
        palette = self._palette
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 14, 10, 10)
        root.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        hint = QLabel(
            "Enter metadata the experimental analyses (pDFA, Mantel, GLMM, "
            "PGLS) need. Use <b>Apply ↓</b> to broadcast a value to every "
            f"file, or import an external table. Missing cells will be "
            f"saved as <code>{self._NA}</code>."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color: {palette.text_dim}; font-size: 11px; background: transparent;")
        header_row.addWidget(hint, stretch=1)

        self._import_btn = QPushButton("  Import Metadata File…  ")
        self._import_btn.setToolTip(
            "Load a CSV or Excel file and auto-fill this table. "
            "Columns that can't be auto-detected can be mapped manually.")
        self._import_btn.setStyleSheet(
            f"QPushButton {{ background-color: {palette.bg_widget}; color: {palette.text}; "
            f"border: 1px solid {palette.border}; border-radius: 5px; "
            f"padding: 4px 10px; font-size: 11px; }} "
            f"QPushButton:hover {{ border-color: {palette.accent}; }}"
        )
        self._import_btn.clicked.connect(self._on_import_file)
        header_row.addWidget(self._import_btn)

        self._save_btn = QPushButton("  Save Metadata  ")
        self._save_btn.setToolTip(
            "Save the table as an Excel workbook at "
            "<code>…/data/[folder]_metadata.xlsx</code>. Also updates the "
            "Pre-Analysis JSON so the Onset Finder merges these values "
            "into the File Demographics sheet.")
        self._save_btn.setStyleSheet(
            f"QPushButton {{ background-color: {palette.accent_dim}; color: white; "
            f"border-radius: 5px; padding: 4px 12px; font-size: 11px; "
            f"border: none; }} "
            f"QPushButton:hover {{ background-color: {palette.accent}; }}"
        )
        self._save_btn.clicked.connect(self._on_save)
        header_row.addWidget(self._save_btn)

        root.addLayout(header_row)

        section_desc = DescriptionLabel(
            "Enter per-file demographics (Group, Species, Latitude, etc.). "
            "Saved to <folder>/data/[folder]_metadata.xlsx.",
            "Populate this table with the demographic / contextual values "
            "your downstream analyses require — Group (for pDFA, GLMM, "
            "Mantel), Species & Latitude/Longitude (for PGLS and Mantel), "
            "Modality / Function / Tempo_BPM / BodyMass_kg (for GLMM & PGLS "
            "models).  Use the <b>Apply General Values</b> row above the "
            "table to broadcast a value to every file, or import an "
            "external CSV/Excel and map its columns with one click.  "
            "Clicking <b>Save Metadata</b> writes "
            "<code>[folder]/data/[folder]_metadata.xlsx</code> (the "
            "user-facing artefact, which you can re-open and edit in Excel) "
            "and also mirrors the values into the Pre-Analysis JSON so the "
            "Onset Finder adds a <b>File Demographics</b> sheet to the "
            "output workbook automatically.",
            "This is where you fill in the extra facts about each audio "
            "recording — things like which group the animal belongs to, "
            "what species it is, or where it was recorded.  You can type "
            "the values in by hand, or if you already have them in a "
            "spreadsheet, just click <b>Import Metadata File…</b> and the "
            "app will fill them in for you.  When you're done, click "
            "<b>Save Metadata</b> — it creates a little spreadsheet called "
            "<code>[folder]_metadata.xlsx</code> in the <code>data/</code> "
            "folder so you can open it again later and tweak it."
        )
        root.addWidget(section_desc)
        _ALL_DESC_LABELS.append(section_desc)
        section_desc.apply_level(self._desc_level)

        banner = QWidget()
        banner.setStyleSheet(
            f"background-color: {palette.bg_widget}; border: 1px solid {palette.border}; "
            f"border-radius: 4px;")
        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(8, 6, 8, 6)
        banner_layout.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.addWidget(QLabel("<b>Apply General Values</b>"))
        title_row.addSpacing(12)
        self._apply_all_btn = QPushButton("Apply All ↓")
        self._apply_all_btn.setToolTip(
            "Apply every non-empty General value below to its column at once.")
        self._apply_all_btn.setStyleSheet(
            f"QPushButton {{ background-color: {palette.bg_mid}; color: {palette.text}; "
            f"border: 1px solid {palette.border}; border-radius: 3px; "
            f"padding: 2px 10px; font-size: 11px; }} "
            f"QPushButton:hover {{ border-color: {palette.accent}; }}")
        self._apply_all_btn.clicked.connect(self._on_apply_all_general)
        title_row.addWidget(self._apply_all_btn)
        title_row.addStretch(1)
        banner_layout.addLayout(title_row)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)

        self._general_edits: dict[str, QLineEdit] = {}
        for column, (field, description) in enumerate(self._metadata_fields):
            label = QLabel(field)
            label.setToolTip(description)
            label.setStyleSheet(f"color: {palette.text}; font-size: 11px;")
            edit = QLineEdit()
            edit.setPlaceholderText(field)
            edit.setToolTip(description)
            edit.setMinimumWidth(70)
            edit.setStyleSheet(
                f"QLineEdit {{ background-color: {palette.bg_mid}; color: {palette.text}; "
                f"border: 1px solid {palette.border}; padding: 2px 4px; }}")
            button = QPushButton("Apply ↓")
            button.setStyleSheet(
                f"QPushButton {{ background-color: {palette.bg_mid}; color: {palette.text}; "
                f"border: 1px solid {palette.border}; border-radius: 3px; "
                f"padding: 2px 6px; font-size: 11px; }} "
                f"QPushButton:hover {{ border-color: {palette.accent}; }}")
            button.clicked.connect(
                lambda _=False, f=field, e=edit: self._on_apply_general(f, e))
            grid.addWidget(label, 0, column)
            grid.addWidget(edit, 1, column)
            grid.addWidget(button, 2, column)
            grid.setColumnStretch(column, 1)
            self._general_edits[field] = edit

        banner_layout.addLayout(grid)
        root.addWidget(banner)

        self._table = QTableWidget()
        column_count = 1 + len(self._metadata_fields)
        self._table.setColumnCount(column_count)
        headers = ["Audio File"] + [field for field, _ in self._metadata_fields]
        self._table.setHorizontalHeaderLabels(headers)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        for index in range(1, column_count):
            self._table.horizontalHeader().setSectionResizeMode(
                index, QHeaderView.ResizeMode.ResizeToContents)
            header_item = self._table.horizontalHeaderItem(index)
            if header_item:
                header_item.setToolTip(self._metadata_fields[index - 1][1])
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setMinimumHeight(160)
        self._table.setStyleSheet(
            f"QTableWidget {{ background-color: {palette.bg_mid}; color: {palette.text}; "
            f"gridline-color: {palette.border}; }} "
            f"QHeaderView::section {{ background-color: {palette.bg_widget}; "
            f"color: {palette.text}; padding: 4px; border: 1px solid {palette.border}; "
            f"font-weight: 600; }} "
            f"QTableWidget::item:alternate {{ background-color: {palette.bg_widget}; }}"
        )
        self._table.itemChanged.connect(self._on_item_changed)

        self._empty_label = QLabel(
            "No audio files scanned yet — click <b>Scan Folder</b> above to "
            "populate this list.")
        self._empty_label.setStyleSheet(
            f"color: {palette.text_dim}; font-size: 11px; font-style: italic; "
            f"padding: 10px; background: transparent;")
        self._empty_label.setVisible(True)
        self._table.setVisible(False)

        root.addWidget(self._empty_label)
        root.addWidget(self._table, stretch=1)

    def set_filenames(self, filenames: list[str]):
        self._filenames = list(filenames)
        self._reload_from_json()

    def _json_path(self) -> str:
        path = ""
        try:
            path = self._panel.per_file_settings_path.text().strip()
        except Exception:
            path = ""
        if path:
            return path
        folder = ""
        try:
            folder = self._panel.input_folder.text().strip()
        except Exception:
            folder = ""
        if not folder:
            return ""
        data_dir = os.path.join(folder, "data")
        output_dir = data_dir if os.path.isdir(data_dir) else folder
        return os.path.join(output_dir, "AudioEditor_PerFile_PreAnalysis.json")

    def _xlsx_path(self) -> str:
        folder = ""
        try:
            folder = self._panel.input_folder.text().strip()
        except Exception:
            folder = ""
        if not folder:
            return ""
        base = os.path.basename(os.path.normpath(folder)) or "metadata"
        data_dir = os.path.join(folder, "data")
        return os.path.join(data_dir, f"{base}_metadata.xlsx")

    def _reload_from_json(self):
        path = self._json_path()
        self._general = {}
        self._per_file = {}
        if path and os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as file_obj:
                    data = json.load(file_obj)
            except (OSError, ValueError):
                data = {}
            if isinstance(data, dict):
                general_metadata = data.get("__general_metadata__")
                if isinstance(general_metadata, dict):
                    self._general = {
                        key: str(value)
                        for key, value in general_metadata.items()
                        if value is not None and str(value).strip() != ""
                    }
                for filename, file_data in data.items():
                    if filename.startswith("__") or not isinstance(file_data, dict):
                        continue
                    metadata = file_data.get("metadata")
                    if isinstance(metadata, dict) and metadata:
                        self._per_file[filename] = {
                            key: str(value)
                            for key, value in metadata.items()
                            if value is not None
                        }
        self._merge_from_xlsx(self._xlsx_path())
        self._repaint_general()
        self._repaint_table()

    def _merge_from_xlsx(self, xlsx_path: str) -> None:
        if not xlsx_path or not os.path.isfile(xlsx_path):
            return
        try:
            import pandas as pd
            dataframe = pd.read_excel(xlsx_path)
        except Exception:
            return
        if dataframe is None or dataframe.empty or "File Name" not in dataframe.columns:
            return
        known_fields = {field for field, _ in self._metadata_fields}
        for _, row in dataframe.iterrows():
            filename = str(row.get("File Name", "")).strip()
            if not filename:
                continue
            for field in dataframe.columns:
                if field == "File Name":
                    continue
                value = row[field]
                if value is None:
                    continue
                try:
                    import pandas as _pd
                    if _pd.isna(value):
                        continue
                except Exception:
                    pass
                text = str(value).strip()
                if not text or text == self._NA:
                    continue
                if filename == "__general__" and field in known_fields:
                    self._general[field] = text
                else:
                    self._per_file.setdefault(filename, {})[field] = text

    def _repaint_general(self):
        self._populating = True
        try:
            for field, edit in self._general_edits.items():
                edit.setText(self._general.get(field, ""))
        finally:
            self._populating = False

    def _repaint_table(self):
        self._populating = True
        try:
            if not self._filenames:
                self._table.setRowCount(0)
                self._table.setVisible(False)
                self._empty_label.setVisible(True)
                return
            self._empty_label.setVisible(False)
            self._table.setVisible(True)
            self._table.setRowCount(len(self._filenames))
            for row, filename in enumerate(self._filenames):
                filename_item = QTableWidgetItem(filename)
                filename_item.setFlags(filename_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                filename_item.setToolTip(filename)
                self._table.setItem(row, 0, filename_item)
                metadata = self._per_file.get(filename, {})
                for column, (field, _description) in enumerate(self._metadata_fields, start=1):
                    value = metadata.get(field, "")
                    item = QTableWidgetItem(str(value) if value else "")
                    general_value = self._general.get(field, "")
                    if not value and general_value:
                        item.setToolTip(
                            f"General default: {general_value}\n"
                            f"(applied at export time unless overridden here)")
                        item.setForeground(QColor(self._palette.text_dim))
                        item.setText(f"⟨{general_value}⟩")
                    self._table.setItem(row, column, item)
        finally:
            self._populating = False

    def _on_item_changed(self, item):
        if self._populating:
            return
        row = item.row()
        column = item.column()
        if column == 0 or row < 0 or row >= len(self._filenames):
            return
        filename = self._filenames[row]
        field = self._metadata_fields[column - 1][0]
        value = item.text().strip()
        if value.startswith("⟨") and value.endswith("⟩"):
            value = ""
        file_data = self._per_file.setdefault(filename, {})
        if value:
            file_data[field] = value
        else:
            file_data.pop(field, None)
        if not file_data:
            self._per_file.pop(filename, None)

    def _on_apply_general(self, field: str, edit: QLineEdit):
        value = edit.text().strip()
        if not value:
            QMessageBox.information(
                self, "Apply General Value",
                f"Enter a value for <b>{field}</b> first.")
            return
        self._general[field] = value
        has_existing = any(
            (self._per_file.get(filename, {}).get(field, "") or "").strip()
            for filename in self._filenames)
        if has_existing:
            reply = QMessageBox.question(
                self, "Apply to all files?",
                f"Set <b>{field}</b> = <b>{value}</b> for every file?<br><br>"
                f"• <b>Yes</b> — overwrite every row.<br>"
                f"• <b>No</b> — fill blank cells only.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                return
            overwrite = reply == QMessageBox.StandardButton.Yes
        else:
            overwrite = True
        self._apply_value_to_column(field, value, overwrite)

    def _on_apply_all_general(self):
        pending: list[tuple[str, str]] = []
        for field, edit in self._general_edits.items():
            value = edit.text().strip()
            if value:
                pending.append((field, value))
        if not pending:
            QMessageBox.information(
                self, "Apply General Values",
                "Enter at least one General value before clicking "
                "<b>Apply All</b>.")
            return

        has_existing = False
        for field, _value in pending:
            if any((self._per_file.get(filename, {}).get(field, "") or "").strip()
                   for filename in self._filenames):
                has_existing = True
                break
        if has_existing:
            reply = QMessageBox.question(
                self, "Apply to all files?",
                "Apply the General values below to every file?<br><br>"
                + "<br>".join(f"• <b>{field}</b> = <b>{value}</b>" for field, value in pending)
                + "<br><br>"
                "• <b>Yes</b> — overwrite every row.<br>"
                "• <b>No</b> — fill blank cells only.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                return
            overwrite = reply == QMessageBox.StandardButton.Yes
        else:
            overwrite = True

        for field, value in pending:
            self._general[field] = value
            self._apply_value_to_column(field, value, overwrite)

    def _apply_value_to_column(self, field: str, value: str, overwrite: bool) -> None:
        column = 1 + [name for name, _ in self._metadata_fields].index(field)
        self._populating = True
        try:
            for row, filename in enumerate(self._filenames):
                existing = self._per_file.get(filename, {}).get(field, "")
                if existing and not overwrite:
                    continue
                self._per_file.setdefault(filename, {})[field] = value
                item = self._table.item(row, column)
                if item is None:
                    item = QTableWidgetItem(value)
                    self._table.setItem(row, column, item)
                else:
                    item.setText(value)
                item.setForeground(QColor(self._palette.text))
        finally:
            self._populating = False

    def _on_import_file(self):
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Import Audio Metadata File",
            "",
            "Metadata files (*.csv *.tsv *.xlsx *.xls);;All files (*.*)")
        if not path:
            return
        try:
            import pandas as pd
            extension = os.path.splitext(path)[1].lower()
            if extension in (".xlsx", ".xls"):
                dataframe = pd.read_excel(path, dtype=str)
            elif extension == ".tsv":
                dataframe = pd.read_csv(path, sep="\t", dtype=str)
            else:
                dataframe = pd.read_csv(path, dtype=str)
        except Exception as exc:
            QMessageBox.critical(
                self, "Import Failed",
                f"Could not read <code>{os.path.basename(path)}</code>:<br><br>{exc}")
            return

        if dataframe.empty:
            QMessageBox.warning(self, "Empty File", "The selected file contains no rows.")
            return

        dataframe.columns = [str(column) for column in dataframe.columns]
        available = list(dataframe.columns)
        lower = {column.lower(): column for column in available}
        aliases = {
            "Group": ["group", "population", "condition"],
            "Species": ["species", "taxon", "tree_tip", "tip"],
            "Latitude": ["latitude", "lat"],
            "Longitude": ["longitude", "long", "lon", "lng"],
            "Modality": ["modality", "modality_label"],
            "Function": ["function", "function_label"],
            "Tempo_BPM": ["tempo_bpm", "tempo", "bpm"],
            "BodyMass_kg": ["bodymass_kg", "body_mass_kg", "body_mass", "mass_kg", "mass"],
        }
        auto: dict[str, str] = {}
        file_aliases = [
            "file name", "filename", "file", "audio file", "audio_file", "recording", "name",
        ]
        for alias in file_aliases:
            if alias in lower:
                auto["__FILE__"] = lower[alias]
                break
        for field, _description in self._metadata_fields:
            if field.lower() in lower:
                auto[field] = lower[field.lower()]
                continue
            for alias in aliases.get(field, []):
                if alias in lower:
                    auto[field] = lower[alias]
                    break

        missing = [field for field, _ in self._metadata_fields if field not in auto]
        mapping = dict(auto)
        if missing or "__FILE__" not in auto:
            dialog = _MetadataColumnMappingDialog(
                available, auto, self._metadata_fields, parent=self)
            if dialog.exec() != int(QDialog.DialogCode.Accepted):
                return
            mapping = dialog.mapping()

        file_name_column = mapping.get("__FILE__") or ""
        row_index: dict[str, int] = {}
        if file_name_column and file_name_column in dataframe.columns:
            for index, value in enumerate(dataframe[file_name_column].fillna("").astype(str).tolist()):
                key = value.strip()
                if key:
                    row_index[key] = index
                    stem = os.path.splitext(os.path.basename(key))[0]
                    row_index.setdefault(stem, index)

        filled = 0
        na_filled = 0
        for filename in self._filenames:
            index = None
            if file_name_column:
                stem = os.path.splitext(filename)[0]
                index = row_index.get(filename)
                if index is None:
                    index = row_index.get(stem)
            elif len(self._filenames) == len(dataframe):
                index = self._filenames.index(filename)
            file_data = self._per_file.setdefault(filename, {})
            for field, _description in self._metadata_fields:
                source = mapping.get(field, "")
                if source and index is not None and source in dataframe.columns:
                    raw = dataframe[source].iloc[index]
                    value = "" if (raw is None or (isinstance(raw, float) and pd.isna(raw))) else str(raw).strip()
                else:
                    value = ""
                if value and value.lower() != "nan":
                    file_data[field] = value
                    filled += 1
                else:
                    file_data[field] = self._NA
                    na_filled += 1

        self._repaint_table()
        QMessageBox.information(
            self, "Metadata Imported",
            f"Filled <b>{filled}</b> value(s) and wrote <b>{na_filled}</b> "
            f"<code>{self._NA}</code> placeholder(s) across "
            f"<b>{len(self._filenames)}</b> file(s).<br><br>"
            "Click <b>Save Metadata</b> to persist.")

    def _on_save(self):
        ok, json_path, xlsx_path, xlsx_err, err = self._persist_metadata()
        if not ok:
            if err == "no_folder":
                QMessageBox.warning(
                    self, "No Input Folder",
                    "Set an input folder (or Pre-Analysis JSON path) first.")
            else:
                QMessageBox.critical(
                    self, "Save Failed",
                    f"Could not write <code>{json_path}</code>:<br><br>{err}")
            return
        if xlsx_path and not xlsx_err:
            QMessageBox.information(
                self, "Metadata Saved",
                f"Saved metadata for <b>{len(self._filenames)}</b> file(s) to:<br>"
                f"<code>{xlsx_path}</code><br><br>"
                f"(also mirrored to <code>{os.path.basename(json_path)}</code> "
                f"so the Onset Finder picks it up automatically.)")
        else:
            message = (
                f"Saved metadata for <b>{len(self._filenames)}</b> file(s) to:<br>"
                f"<code>{json_path}</code>")
            if xlsx_err:
                message += (
                    f"<br><br><b>Note:</b> could not also write the user-facing xlsx: "
                    f"{xlsx_err}")
            QMessageBox.information(self, "Metadata Saved", message)

    def save_silent(self) -> bool:
        ok, _json_path, _xlsx_path, _xerr, _err = self._persist_metadata()
        return ok

    def _persist_metadata(self):
        path = self._json_path()
        if not path:
            return False, "", "", "", "no_folder"

        self._flush_table_to_state()
        for field, edit in self._general_edits.items():
            value = edit.text().strip()
            if value:
                self._general[field] = value
            else:
                self._general.pop(field, None)

        data: dict = {}
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as file_obj:
                    loaded = json.load(file_obj)
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, ValueError):
                data = {}

        if self._general:
            data["__general_metadata__"] = dict(self._general)
        else:
            data.pop("__general_metadata__", None)

        for filename in self._filenames:
            metadata = {
                key: value
                for key, value in self._per_file.get(filename, {}).items()
                if value is not None and str(value).strip() != ""
            }
            entry = data.get(filename)
            if not isinstance(entry, dict):
                entry = {}
            if metadata:
                entry["metadata"] = metadata
            else:
                entry.pop("metadata", None)
            if entry:
                data[filename] = entry
            else:
                data.pop(filename, None)

        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as file_obj:
                json.dump(data, file_obj, indent=2)
        except OSError as exc:
            return False, path, "", "", str(exc)

        try:
            if not self._panel.per_file_settings_path.text().strip():
                self._panel.per_file_settings_path.setText(path)
        except Exception:
            pass

        xlsx_path = self._xlsx_path()
        xlsx_err = ""
        if xlsx_path:
            try:
                import pandas as pd

                columns = ["File Name"] + [field for field, _ in self._metadata_fields]
                rows: list[dict] = []
                if self._general:
                    general_row: dict = {"File Name": "__general__"}
                    for field, _description in self._metadata_fields:
                        general_row[field] = self._general.get(field, "") or ""
                    rows.append(general_row)
                for filename in self._filenames:
                    row: dict = {"File Name": filename}
                    metadata = self._per_file.get(filename, {})
                    for field, _description in self._metadata_fields:
                        value = metadata.get(field, "")
                        if not value:
                            value = self._general.get(field, "")
                        row[field] = value if value else self._NA
                    rows.append(row)
                dataframe = pd.DataFrame(rows, columns=columns)
                os.makedirs(os.path.dirname(xlsx_path), exist_ok=True)
                with pd.ExcelWriter(xlsx_path) as writer:
                    dataframe.to_excel(writer, sheet_name="File Metadata", index=False)
            except Exception as exc:
                xlsx_err = str(exc)
                xlsx_path = ""
        return True, path, xlsx_path, xlsx_err, ""

    def _flush_table_to_state(self):
        for row in range(self._table.rowCount()):
            if row >= len(self._filenames):
                continue
            filename = self._filenames[row]
            file_data = self._per_file.setdefault(filename, {})
            for column, (field, _description) in enumerate(self._metadata_fields, start=1):
                item = self._table.item(row, column)
                value = item.text().strip() if item else ""
                if value.startswith("⟨") and value.endswith("⟩"):
                    value = ""
                if value:
                    file_data[field] = value
                else:
                    file_data.pop(field, None)
            if not file_data:
                self._per_file.pop(filename, None)


__all__ = [
    "AnalysisHintsDialog",
    "_FileMetadataSection",
    "_make_title_info_button",
    "_prep_apply_hint_overrides_to_muter",
    "_prep_apply_hints_to_profile",
    "_prep_default_hints",
    "_prep_float_or_none",
    "_prep_infer_signal_character",
    "_prep_load_signal_profile_hint",
    "_prep_recommend_onset_settings",
    "_prep_sanitize_hints",
]