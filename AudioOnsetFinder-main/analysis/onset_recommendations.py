"""Shared onset-analysis recommendations used by GUI and script surfaces."""

import os
import sys

import librosa
import numpy as np
from scipy.signal import hilbert as scipy_hilbert


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT_DIR = os.path.join(_PROJECT_ROOT, "scripts")

try:
    from scripts.onset_detectors import detect_onsets as _default_detect_onsets
    from scripts.onset_detectors import available_methods as _default_available_methods
    from scripts.onset_routing import build_detector_call as _default_build_detector_call
except ImportError:
    if _SCRIPT_DIR not in sys.path:
        sys.path.insert(0, _SCRIPT_DIR)
    from onset_detectors import detect_onsets as _default_detect_onsets
    from onset_detectors import available_methods as _default_available_methods
    from onset_routing import build_detector_call as _default_build_detector_call


def characterize_transients(y, sr, onset_times, window_ms=20):
    """Characterize the transient profile at each onset."""
    if len(onset_times) == 0:
        return {
            "mean_attack_slope": 0,
            "median_attack_slope": 0,
            "mean_local_energy": 0,
            "attack_slope_cv": 0,
            "energy_cv": 0,
        }

    analytic = scipy_hilbert(y)
    envelope = np.abs(analytic).astype(np.float64)
    env_diff = np.diff(envelope)

    window_samples = int(sr * window_ms / 1000)
    half_win = window_samples // 2

    slopes = []
    energies = []

    for onset_time in onset_times:
        center = int(onset_time * sr)
        start = max(0, center - half_win)
        end = min(len(env_diff), center + half_win)

        if start < end:
            local_slope = float(np.max(env_diff[start:end]))
            slopes.append(max(0, local_slope))

        energy_start = max(0, center)
        energy_end = min(len(y), center + window_samples)
        if energy_start < energy_end:
            rms = float(np.sqrt(np.mean(y[energy_start:energy_end] ** 2)))
            energies.append(rms)

    if not slopes:
        slopes = [0.0]
    if not energies:
        energies = [0.0]

    slopes = np.array(slopes)
    energies = np.array(energies)

    mean_slope = float(np.mean(slopes))
    mean_energy = float(np.mean(energies))

    return {
        "mean_attack_slope": round(mean_slope, 6),
        "median_attack_slope": round(float(np.median(slopes)), 6),
        "mean_local_energy": round(mean_energy, 6),
        "attack_slope_cv": round(float(np.std(slopes) / max(mean_slope, 1e-10)), 3),
        "energy_cv": round(float(np.std(energies) / max(mean_energy, 1e-10)), 3),
    }


def evaluate_onset_quality(onset_times, y, sr):
    """Score an onset detection result's quality."""
    if len(onset_times) < 2:
        return {
            "n_onsets": len(onset_times),
            "mean_ioi_ms": 0,
            "ioi_cv": 0,
            "min_ioi_ms": 0,
            "suspicious_close_pairs": 0,
            "regularity_score": 0,
            "overall_score": 0,
        }

    iois = np.diff(onset_times) * 1000

    mean_ioi = float(np.mean(iois))
    std_ioi = float(np.std(iois))
    cv = std_ioi / max(mean_ioi, 1e-10)
    min_ioi = float(np.min(iois))

    suspicious = int(np.sum(iois < 15))

    median_ioi = float(np.median(iois))
    regular = np.sum((iois > median_ioi * 0.25) & (iois < median_ioi * 4.0))
    regularity = float(regular) / len(iois) if len(iois) > 0 else 0

    n_penalty = max(0, 10 - len(onset_times)) * 3
    suspicious_penalty = suspicious * 5
    cv_penalty = max(0, (cv - 1.5)) * 10

    score = max(0, 100 - n_penalty - suspicious_penalty - cv_penalty)
    if 5 <= len(onset_times) <= 500:
        score = min(100, score + 10)

    return {
        "n_onsets": len(onset_times),
        "mean_ioi_ms": round(mean_ioi, 2),
        "ioi_cv": round(cv, 3),
        "min_ioi_ms": round(min_ioi, 2),
        "suspicious_close_pairs": suspicious,
        "regularity_score": round(regularity, 3),
        "overall_score": round(max(0, min(100, score)), 1),
    }


def try_detection_method(
    method,
    y,
    sr,
    delta,
    hop_length,
    *,
    detect_onsets_fn=None,
    build_detector_call_fn=None,
):
    """Run a detection method with given parameters, return onsets and quality."""
    detect_onsets_fn = detect_onsets_fn or _default_detect_onsets
    build_detector_call_fn = build_detector_call_fn or _default_build_detector_call

    try:
        settings = {
            "ONSET_METHOD": method,
            "ONSET_DELTA": delta,
            "ONSET_HOP_LENGTH": hop_length,
        }

        if method == "adaptive_hp":
            settings.update(
                {
                    "HP_SMOOTH_LAMBDA": 50,
                    "HP_THRESHOLD_LAMBDA": 5e7,
                    "envelope_window_ms": 10,
                    "HP_ENVELOPE_WINDOW_MS": 10,
                    "HP_ENVELOPE_HOP_MS": 1,
                }
            )
        elif method == "moving_median":
            settings.update(
                {
                    "MEDIAN_WINDOW_MS": 200,
                    "MEDIAN_THRESHOLD_SCALE": 1.5,
                }
            )
        elif method == "superflux":
            settings.update(
                {
                    "SUPERFLUX_LAG": 2,
                    "SUPERFLUX_MAX_SIZE": 3,
                }
            )
        elif method == "cfar":
            settings.update(
                {
                    "CFAR_GUARD_MS": 20,
                    "CFAR_TRAINING_MS": 200,
                    "CFAR_THRESHOLD_FACTOR": 4.0,
                }
            )
        elif method == "per_band":
            settings.update(
                {
                    "PER_BAND_N_BANDS": 6,
                    "PER_BAND_FREQ_MIN": 200,
                    "PER_BAND_FREQ_MAX": None,
                    "PER_BAND_MEDIAN_MS": 200,
                    "PER_BAND_THRESHOLD_SCALE": 1.5,
                    "PER_BAND_MIN_BANDS": 2,
                }
            )

        resolved_method, kwargs = build_detector_call_fn(settings)
        onsets = detect_onsets_fn(resolved_method, y, sr, **kwargs)
        quality = evaluate_onset_quality(onsets, y, sr)
        return onsets, quality
    except Exception as exc:
        return np.array([]), {
            "n_onsets": 0,
            "error": str(exc),
            "overall_score": 0,
        }


def analyze_for_onsets(
    audio_path,
    signal_profile=None,
    sr=None,
    *,
    available_methods_fn=None,
    detect_onsets_fn=None,
    build_detector_call_fn=None,
):
    """Analyze a cleaned audio file and recommend Onset Finder settings."""
    available_methods_fn = available_methods_fn or _default_available_methods
    detect_onsets_fn = detect_onsets_fn or _default_detect_onsets
    build_detector_call_fn = build_detector_call_fn or _default_build_detector_call

    y, file_sr = librosa.load(audio_path, sr=sr, mono=True)
    duration = len(y) / file_sr

    has_profile = (
        signal_profile is not None
        and "summary" in signal_profile
        and signal_profile["summary"].get("n_regions", 0) > 0
    )
    has_neg_profile = (
        signal_profile is not None
        and "negative_summary" in signal_profile
        and signal_profile["negative_summary"].get("n_regions", 0) > 0
    )

    if has_profile:
        sp = signal_profile["summary"]
        sig_character = sp["signal_character"]
        sig_sharpness = sp["attack_sharpness"]
        sig_duration = sp.get("avg_signal_duration_s", 0.1)
        sig_harmonicity = sp["harmonicity"]
    else:
        sig_character = None
        sig_sharpness = None
        sig_duration = None
        sig_harmonicity = None

    if has_neg_profile:
        nsp = signal_profile["negative_summary"]
        neg_character = nsp["signal_character"]
        neg_sharpness = nsp["attack_sharpness"]
        neg_harmonicity = nsp["harmonicity"]
    else:
        neg_character = None
        neg_sharpness = None
        neg_harmonicity = None

    methods = available_methods_fn()
    method_results = {}
    delta_default = 0.06
    hop_default = 256

    for method in methods:
        onsets, quality = try_detection_method(
            method,
            y,
            file_sr,
            delta_default,
            hop_default,
            detect_onsets_fn=detect_onsets_fn,
            build_detector_call_fn=build_detector_call_fn,
        )
        transients = characterize_transients(y, file_sr, onsets)
        method_results[method] = {
            "quality": quality,
            "transients": transients,
        }

    best_method = max(
        method_results,
        key=lambda method_name: method_results[method_name]["quality"].get(
            "overall_score", 0
        ),
    )

    delta_sweep = [0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.12, 0.15]
    delta_results = {}
    for delta in delta_sweep:
        _onsets, quality = try_detection_method(
            best_method,
            y,
            file_sr,
            delta,
            hop_default,
            detect_onsets_fn=detect_onsets_fn,
            build_detector_call_fn=build_detector_call_fn,
        )
        delta_results[delta] = quality

    best_delta = delta_default
    best_delta_score = 0
    for delta, quality in delta_results.items():
        score = quality.get("overall_score", 0)
        n_onsets = quality.get("n_onsets", 0)
        adjusted_score = score
        if n_onsets < 3:
            adjusted_score -= 30
        if quality.get("suspicious_close_pairs", 0) > n_onsets * 0.1:
            adjusted_score -= 20
        if adjusted_score > best_delta_score:
            best_delta_score = adjusted_score
            best_delta = delta

    settings = {}
    reasoning = {}

    settings["ONSET_METHOD"] = best_method
    best_score = method_results[best_method]["quality"]["overall_score"]
    second_best = sorted(
        method_results.items(),
        key=lambda item: item[1]["quality"].get("overall_score", 0),
        reverse=True,
    )
    if len(second_best) > 1:
        runner_up = second_best[1]
        reasoning["ONSET_METHOD"] = (
            f"{best_method} — best quality score ({best_score:.0f}/100); "
            f"runner-up: {runner_up[0]} ({runner_up[1]['quality']['overall_score']:.0f}/100)"
        )
    else:
        reasoning["ONSET_METHOD"] = (
            f"{best_method} — best quality score ({best_score:.0f}/100)"
        )

    if has_profile:
        if sig_character == "harmonic" and sig_harmonicity > 0.7:
            if "superflux" in methods:
                settings["ONSET_METHOD"] = "superflux"
                reasoning["ONSET_METHOD"] = (
                    f"superflux — signal is highly harmonic (harmonicity={sig_harmonicity:.2f}); "
                    f"superflux excels at vibrato/trill suppression"
                )
        elif sig_character == "percussive" and sig_sharpness > 0.5:
            if best_method not in ("adaptive_hp", "librosa"):
                settings["ONSET_METHOD"] = "adaptive_hp"
                reasoning["ONSET_METHOD"] = (
                    f"adaptive_hp — sharp percussive signal (sharpness={sig_sharpness:.2f}); "
                    f"HP baseline handles transients well"
                )

    if has_neg_profile and has_profile:
        if (
            neg_character == "harmonic"
            and sig_character == "percussive"
            and "adaptive_hp" in methods
        ):
            settings["ONSET_METHOD"] = "adaptive_hp"
            reasoning["ONSET_METHOD"] = (
                f"adaptive_hp — target is percussive while unwanted sound is "
                f"harmonic; HP baseline naturally rejects sustained tonal energy"
            )
        elif (
            neg_character == "percussive"
            and sig_character == "harmonic"
            and "superflux" in methods
        ):
            settings["ONSET_METHOD"] = "superflux"
            reasoning["ONSET_METHOD"] = (
                f"superflux — target is harmonic while unwanted sound is "
                f"percussive; superflux suppresses transient false-positives"
            )

    settings["ONSET_DELTA"] = best_delta
    best_delta_quality = delta_results.get(best_delta, {})
    reasoning["ONSET_DELTA"] = (
        f"{best_delta:.2f} — optimal sensitivity; "
        f"gives {best_delta_quality.get('n_onsets', '?')} onsets "
        f"with {best_delta_quality.get('suspicious_close_pairs', '?')} suspicious pairs"
    )

    if has_profile and sig_duration is not None and sig_duration < 0.05:
        settings["ONSET_HOP_LENGTH"] = 128
        reasoning["ONSET_HOP_LENGTH"] = (
            "128 — very short signal events require fine temporal resolution"
        )
    elif has_profile and sig_duration is not None and sig_duration > 0.5:
        settings["ONSET_HOP_LENGTH"] = 512
        reasoning["ONSET_HOP_LENGTH"] = (
            "512 — long signal events; coarser resolution reduces noise sensitivity"
        )
    else:
        settings["ONSET_HOP_LENGTH"] = 256
        reasoning["ONSET_HOP_LENGTH"] = (
            "256 — good balance of precision (~5.8 ms) and noise robustness"
        )

    best_transients = method_results[settings["ONSET_METHOD"]]["transients"]
    energy_cv = best_transients.get("energy_cv", 0)

    if energy_cv > 1.0:
        settings["ONSET_AMPLITUDE_GATE"] = 0.08
        reasoning["ONSET_AMPLITUDE_GATE"] = (
            f"0.08 — onset energies vary widely (CV={energy_cv:.2f}); "
            f"moderate gate filters weakest false positives"
        )
    elif energy_cv > 0.5:
        settings["ONSET_AMPLITUDE_GATE"] = 0.05
        reasoning["ONSET_AMPLITUDE_GATE"] = (
            f"0.05 — moderate onset energy variation (CV={energy_cv:.2f})"
        )
    else:
        settings["ONSET_AMPLITUDE_GATE"] = 0.03
        reasoning["ONSET_AMPLITUDE_GATE"] = (
            f"0.03 — consistent onset energies (CV={energy_cv:.2f}); "
            f"low gate preserves all legitimate onsets"
        )
    settings["ONSET_AMPLITUDE_WINDOW_MS"] = 50

    attack_cv = best_transients.get("attack_slope_cv", 0)

    if has_profile and sig_character == "percussive":
        gate = 0.10
        reason = "0.10 — percussive signal; sharpness gate filters gradual non-target events"
        if (
            has_neg_profile
            and neg_character == "percussive"
            and neg_sharpness is not None
            and sig_sharpness is not None
            and neg_sharpness < sig_sharpness
        ):
            gate = max(0.10, round((sig_sharpness + neg_sharpness) / 2, 2))
            gate = min(gate, 0.30)
            reason = (
                f"{gate:.2f} — raised to distinguish target attacks "
                f"(sharpness={sig_sharpness:.2f}) from unwanted percussive "
                f"sounds (sharpness={neg_sharpness:.2f})"
            )
        settings["ONSET_SHARPNESS_GATE"] = gate
        reasoning["ONSET_SHARPNESS_GATE"] = reason
    elif has_neg_profile and neg_character == "harmonic" and neg_sharpness is not None:
        settings["ONSET_SHARPNESS_GATE"] = 0.12
        reasoning["ONSET_SHARPNESS_GATE"] = (
            "0.12 — unwanted sound has gradual onsets; sharpness gate "
            "rejects it while preserving sharper target events"
        )
    elif attack_cv > 1.5:
        settings["ONSET_SHARPNESS_GATE"] = 0.15
        reasoning["ONSET_SHARPNESS_GATE"] = (
            f"0.15 — attack slopes vary widely (CV={attack_cv:.2f}); "
            f"moderate gate removes weak attacks"
        )
    else:
        settings["ONSET_SHARPNESS_GATE"] = 0.0
        reasoning["ONSET_SHARPNESS_GATE"] = (
            f"Disabled — consistent attack profiles (CV={attack_cv:.2f})"
        )
    settings["ONSET_SHARPNESS_WINDOW_MS"] = 20

    best_quality = delta_results.get(best_delta, {})
    min_ioi = best_quality.get("min_ioi_ms", 30)
    if has_profile and sig_duration is not None:
        min_ms = max(5, int(sig_duration * 1000 * 0.5))
        min_ms = min(min_ms, 100)
        settings["MIN_INTER_ONSET_MS"] = min_ms
        reasoning["MIN_INTER_ONSET_MS"] = (
            f"{min_ms} ms — based on signal duration ({sig_duration * 1000:.0f} ms); "
            f"half the typical signal length"
        )
    elif min_ioi < 10:
        settings["MIN_INTER_ONSET_MS"] = 15
        reasoning["MIN_INTER_ONSET_MS"] = (
            f"15 ms — very short minimum IOIs detected ({min_ioi:.1f} ms); "
            f"guard against impossibly fast false triggers"
        )
    elif min_ioi < 30:
        settings["MIN_INTER_ONSET_MS"] = int(min_ioi * 0.8)
        reasoning["MIN_INTER_ONSET_MS"] = (
            f"{int(min_ioi * 0.8)} ms — just below the shortest detected IOI "
            f"({min_ioi:.1f} ms) to preserve all real events"
        )
    else:
        settings["MIN_INTER_ONSET_MS"] = 30
        reasoning["MIN_INTER_ONSET_MS"] = (
            "30 ms — standard minimum; all detected IOIs are above this"
        )

    suspicious = best_quality.get("suspicious_close_pairs", 0)
    n_onsets = best_quality.get("n_onsets", 0)
    if suspicious > 0 and n_onsets > 0:
        cluster_ratio = suspicious / n_onsets
        if cluster_ratio > 0.1:
            settings["ONSET_CLUSTER_WINDOW_MS"] = 30
            reasoning["ONSET_CLUSTER_WINDOW_MS"] = (
                f"30 ms — {suspicious} near-simultaneous onset pairs detected; "
                f"wider cluster window merges duplicates"
            )
        else:
            settings["ONSET_CLUSTER_WINDOW_MS"] = 25
            reasoning["ONSET_CLUSTER_WINDOW_MS"] = (
                "25 ms — standard clustering for occasional near-coincident onsets"
            )
    else:
        settings["ONSET_CLUSTER_WINDOW_MS"] = 20
        reasoning["ONSET_CLUSTER_WINDOW_MS"] = (
            "20 ms — clean detection; minimal clustering needed"
        )
    settings["CLUSTER_OVERLAPPING_ONSETS"] = True

    settings["ONSET_REFINE_ENABLED"] = True
    settings["ONSET_REFINE_WINDOW_MS"] = 10
    settings["ONSET_REFINE_ENERGY_GATE"] = 0.0
    reasoning["ONSET_REFINE_ENABLED"] = (
        "Enabled — sample-level refinement achieves ~0.023 ms precision (always recommended)"
    )

    settings["ONSET_BACKTRACK"] = False
    reasoning["ONSET_BACKTRACK"] = (
        "Disabled — keeping onsets at energy peak avoids overshoot on noisy recordings"
    )

    settings["FILTER_STABLE_RHYTHMS"] = True
    settings["STABLE_RHYTHM_TOLERANCE"] = 0.25
    reasoning["FILTER_STABLE_RHYTHMS"] = (
        "Enabled — exports stable-rhythm subset alongside full data"
    )

    settings["APPLY_HIGHPASS_FILTER"] = False
    reasoning["APPLY_HIGHPASS_FILTER"] = (
        "Disabled — filtering is handled by the Audio Editor to avoid double-filtering"
    )

    settings["CREATE_SPECTROGRAMS"] = True
    settings["CREATE_AUDACITY_LABELS"] = True

    analysis = {
        "file": os.path.basename(audio_path),
        "sample_rate": file_sr,
        "duration_s": round(duration, 2),
        "n_methods_tested": len(methods),
        "best_method": best_method,
        "best_delta": best_delta,
    }

    return {
        "analysis": analysis,
        "settings": settings,
        "reasoning": reasoning,
        "method_results": {method: result["quality"] for method, result in method_results.items()},
        "delta_sweep": {str(delta): quality for delta, quality in delta_results.items()},
    }


def analyze_from_onset_examples(
    audio_path,
    onset_profile,
    sr=None,
    *,
    detect_onsets_fn=None,
    build_detector_call_fn=None,
):
    """Recommend Onset Finder settings from user-marked onset examples."""
    detect_onsets_fn = detect_onsets_fn or _default_detect_onsets
    build_detector_call_fn = build_detector_call_fn or _default_build_detector_call

    y, file_sr = librosa.load(audio_path, sr=sr, mono=True)
    duration = len(y) / file_sr

    pos_times = onset_profile.get("positive_onsets", [])
    neg_times = onset_profile.get("negative_onsets", [])
    pos_summary = onset_profile.get("positive_summary", {})
    neg_summary = onset_profile.get("negative_summary", {})
    ioi_stats = onset_profile.get("ioi_stats", {})
    pos_analyses = onset_profile.get("positive_analyses", [])
    neg_analyses = onset_profile.get("negative_analyses", [])

    settings = {}
    reasoning = {}

    pos_character = pos_summary.get("signal_character", "mixed")
    pos_sharpness = pos_summary.get("mean_sharpness", 0.3)
    pos_harmonicity = pos_summary.get("mean_harmonicity", 0.5)
    neg_character = neg_summary.get("signal_character", None)
    neg_sharpness = neg_summary.get("mean_sharpness", None)

    best_method = "adaptive_hp"
    if pos_harmonicity > 0.7:
        best_method = "superflux"
        reasoning["ONSET_METHOD"] = (
            f"Positive onsets are strongly harmonic (harmonicity {pos_harmonicity:.2f}); "
            f"superflux handles tonal onsets best."
        )
    elif pos_sharpness > 0.5:
        best_method = "adaptive_hp"
        reasoning["ONSET_METHOD"] = (
            f"Positive onsets have sharp attacks (sharpness {pos_sharpness:.3f}); "
            f"adaptive_hp detects percussive transients reliably."
        )
    elif pos_character == "percussive" and neg_character == "harmonic":
        best_method = "adaptive_hp"
        reasoning["ONSET_METHOD"] = (
            "Target is percussive but noise is harmonic; adaptive_hp is best "
            "at separating transient peaks from smooth backgrounds."
        )
    elif pos_character == "harmonic" and neg_character == "percussive":
        best_method = "superflux"
        reasoning["ONSET_METHOD"] = (
            "Target is harmonic, noise is percussive; superflux focuses "
            "on spectral flux that handles vibrato/tonal content."
        )
    else:
        reasoning["ONSET_METHOD"] = (
            "Default: adaptive_hp is the most robust general-purpose method."
        )
    settings["ONSET_METHOD"] = best_method

    test_deltas = [0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.12, 0.15]
    best_delta = 0.06
    best_score = -1
    delta_results = {}

    min_ioi_ms = ioi_stats.get("min_ioi_ms", 30)
    match_tolerance = min(min_ioi_ms / 2, 25.0) / 1000.0

    for delta in test_deltas:
        onsets, quality = try_detection_method(
            best_method,
            y,
            file_sr,
            delta,
            256,
            detect_onsets_fn=detect_onsets_fn,
            build_detector_call_fn=build_detector_call_fn,
        )
        pos_matched = 0
        for positive_time in pos_times:
            for detected_time in onsets:
                if abs(detected_time - positive_time) <= match_tolerance:
                    pos_matched += 1
                    break

        neg_matched = 0
        for negative_time in neg_times:
            for detected_time in onsets:
                if abs(detected_time - negative_time) <= match_tolerance:
                    neg_matched += 1
                    break

        n_pos = max(len(pos_times), 1)
        n_neg = max(len(neg_times), 1)
        recall = pos_matched / n_pos
        neg_penalty = neg_matched / n_neg if neg_times else 0
        n_excess = max(0, quality.get("n_onsets", 0) - len(pos_times) * 3)
        excess_penalty = min(0.3, n_excess * 0.01)

        score = recall - 0.5 * neg_penalty - excess_penalty
        delta_results[delta] = {
            "delta": delta,
            "n_detected": quality.get("n_onsets", 0),
            "pos_recall": round(recall, 3),
            "neg_matched": neg_matched,
            "score": round(score, 3),
        }

        if score > best_score:
            best_score = score
            best_delta = delta

    settings["ONSET_DELTA"] = best_delta
    reasoning["ONSET_DELTA"] = (
        f"Delta {best_delta:.2f} best reproduces your marked onsets "
        f"(recall {delta_results[best_delta]['pos_recall']:.0%}, "
        f"{delta_results[best_delta]['neg_matched']} false matches)."
    )

    settings["ONSET_HOP_LENGTH"] = 256
    reasoning["ONSET_HOP_LENGTH"] = "Default 256 — good balance of resolution and speed."
    if min_ioi_ms < 20:
        settings["ONSET_HOP_LENGTH"] = 128
        reasoning["ONSET_HOP_LENGTH"] = (
            f"Min IOI is very short ({min_ioi_ms:.0f} ms); "
            f"using 128 for finer time resolution."
        )

    if min_ioi_ms > 0 and len(pos_times) >= 2:
        recommended_min_ioi = max(5, int(min_ioi_ms * 0.7))
        settings["MIN_INTER_ONSET_MS"] = recommended_min_ioi
        reasoning["MIN_INTER_ONSET_MS"] = (
            f"Your shortest positive IOI is {min_ioi_ms:.1f} ms; "
            f"setting min to {recommended_min_ioi} ms (70% margin)."
        )
    else:
        settings["MIN_INTER_ONSET_MS"] = 30
        reasoning["MIN_INTER_ONSET_MS"] = (
            "Default 30 ms (not enough onsets to determine IOI bounds)."
        )

    settings["CLUSTER_OVERLAPPING_ONSETS"] = True
    settings["ONSET_CLUSTER_WINDOW_MS"] = 25
    reasoning["CLUSTER_OVERLAPPING_ONSETS"] = "Enabled to merge near-duplicate detections."
    if min_ioi_ms > 0 and min_ioi_ms < 50:
        cluster_window = max(5, int(min_ioi_ms * 0.4))
        settings["ONSET_CLUSTER_WINDOW_MS"] = cluster_window
        reasoning["ONSET_CLUSTER_WINDOW_MS"] = (
            f"Tight cluster window ({cluster_window} ms) for fast events "
            f"(min IOI {min_ioi_ms:.0f} ms)."
        )
    else:
        reasoning["ONSET_CLUSTER_WINDOW_MS"] = "Default 25 ms."

    if pos_sharpness > 0 and neg_sharpness is not None and neg_sharpness > 0:
        gate = round((pos_sharpness + neg_sharpness) / 2, 3)
        gate = max(0.02, min(gate, pos_sharpness * 0.9))
        settings["ONSET_SHARPNESS_GATE"] = gate
        reasoning["ONSET_SHARPNESS_GATE"] = (
            f"Gate {gate:.3f} separates positive (sharpness "
            f"{pos_sharpness:.3f}) from negative ({neg_sharpness:.3f})."
        )
    elif pos_character == "percussive":
        settings["ONSET_SHARPNESS_GATE"] = 0.10
        reasoning["ONSET_SHARPNESS_GATE"] = (
            "Percussive onsets — moderate sharpness gate to reject soft events."
        )
    else:
        settings["ONSET_SHARPNESS_GATE"] = 0.0
        reasoning["ONSET_SHARPNESS_GATE"] = "Disabled — no clear sharpness distinction."
    settings["ONSET_SHARPNESS_WINDOW_MS"] = 20
    reasoning["ONSET_SHARPNESS_WINDOW_MS"] = "Default 20 ms window."

    if pos_analyses and neg_analyses:
        pos_energies = [analysis.get("energy_mid_frac", 0.5) for analysis in pos_analyses]
        neg_energies = [analysis.get("energy_mid_frac", 0.5) for analysis in neg_analyses]
        mean_pos_energy = float(np.mean(pos_energies))
        mean_neg_energy = float(np.mean(neg_energies))
        if mean_neg_energy < mean_pos_energy * 0.6:
            gate = round(0.03, 3)
            settings["ONSET_AMPLITUDE_GATE"] = gate
            reasoning["ONSET_AMPLITUDE_GATE"] = (
                f"Negative onsets are quieter (energy ratio "
                f"{mean_neg_energy:.3f} vs {mean_pos_energy:.3f}); "
                f"amplitude gate set to {gate}."
            )
        else:
            settings["ONSET_AMPLITUDE_GATE"] = 0.0
            reasoning["ONSET_AMPLITUDE_GATE"] = "No clear energy difference — gate disabled."
    else:
        settings["ONSET_AMPLITUDE_GATE"] = 0.0
        reasoning["ONSET_AMPLITUDE_GATE"] = "Default: disabled."
    settings["ONSET_AMPLITUDE_WINDOW_MS"] = 20
    reasoning["ONSET_AMPLITUDE_WINDOW_MS"] = "Default 20 ms."

    settings["ONSET_REFINE_ENABLED"] = True
    settings["ONSET_REFINE_WINDOW_MS"] = 10
    settings["ONSET_REFINE_ENERGY_GATE"] = 0.0
    reasoning["ONSET_REFINE_ENABLED"] = "Enabled for sub-ms precision."
    reasoning["ONSET_REFINE_WINDOW_MS"] = "Default 10 ms refinement window."
    reasoning["ONSET_REFINE_ENERGY_GATE"] = "Default: no energy gate on refinement."

    settings["ONSET_BACKTRACK"] = False
    reasoning["ONSET_BACKTRACK"] = "Disabled — refinement handles onset placement."

    settings["FILTER_STABLE_RHYTHMS"] = True
    settings["STABLE_RHYTHM_TOLERANCE"] = 0.25
    reasoning["FILTER_STABLE_RHYTHMS"] = "Enabled to identify structured rhythm."
    reasoning["STABLE_RHYTHM_TOLERANCE"] = "Default 0.25 (25% tolerance)."

    settings["APPLY_HIGHPASS_FILTER"] = False
    reasoning["APPLY_HIGHPASS_FILTER"] = "Disabled — Audio Editor already applied filtering."

    settings["CREATE_SPECTROGRAMS"] = True
    settings["CREATE_AUDACITY_LABELS"] = True

    analysis = {
        "file": os.path.basename(audio_path),
        "sample_rate": file_sr,
        "duration_s": round(duration, 2),
        "mode": "onset_examples",
        "n_positive_onsets": len(pos_times),
        "n_negative_onsets": len(neg_times),
        "best_method": best_method,
        "best_delta": best_delta,
        "ioi_stats": ioi_stats,
        "positive_summary": pos_summary,
        "negative_summary": neg_summary,
    }

    return {
        "analysis": analysis,
        "settings": settings,
        "reasoning": reasoning,
        "delta_sweep": {str(delta): result for delta, result in delta_results.items()},
    }


def analyze_folder_for_onsets(
    folder_path,
    signal_profile=None,
    sr=None,
    *,
    available_methods_fn=None,
    detect_onsets_fn=None,
    build_detector_call_fn=None,
):
    """Analyze the first audio file in a folder for onset detection settings."""
    audio_exts = {".wav", ".mp3", ".flac", ".ogg", ".mp4", ".m4a", ".aiff"}
    files = sorted(
        [
            entry
            for entry in os.listdir(folder_path)
            if os.path.splitext(entry)[1].lower() in audio_exts
        ]
    )

    if not files:
        return {"error": f"No audio files found in {folder_path}"}

    first_path = os.path.join(folder_path, files[0])
    result = analyze_for_onsets(
        first_path,
        signal_profile=signal_profile,
        sr=sr,
        available_methods_fn=available_methods_fn,
        detect_onsets_fn=detect_onsets_fn,
        build_detector_call_fn=build_detector_call_fn,
    )
    result["analysis"]["n_files_in_folder"] = len(files)
    result["analysis"]["representative_file"] = files[0]
    return result


__all__ = [
    "analyze_for_onsets",
    "analyze_folder_for_onsets",
    "analyze_from_onset_examples",
    "characterize_transients",
    "evaluate_onset_quality",
    "try_detection_method",
]