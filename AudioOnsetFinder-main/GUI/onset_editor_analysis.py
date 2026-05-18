"""Extracted analysis and detector helpers for the onset editor workbench."""

from __future__ import annotations

import copy
import os
import sys
from typing import Callable

import numpy as np

_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
_SCRIPT_DIR = os.path.join(_PROJECT_ROOT, "scripts")

try:
    from analysis.signal_profiles import (
        build_signal_profile as _build_signal_profile_impl,
        summarize_signal_region_analyses as _summarize_signal_region_analyses_impl,
    )
    from analysis.spectral_profiles import (
        build_spectral_profile as _build_spectral_profile_impl,
        compute_spectral_similarity_at_time as _compute_spectral_similarity_at_time_impl,
    )
except ImportError:
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    from analysis.signal_profiles import (
        build_signal_profile as _build_signal_profile_impl,
        summarize_signal_region_analyses as _summarize_signal_region_analyses_impl,
    )
    from analysis.spectral_profiles import (
        build_spectral_profile as _build_spectral_profile_impl,
        compute_spectral_similarity_at_time as _compute_spectral_similarity_at_time_impl,
    )

try:
    from scripts.onset_routing import build_detector_call as _build_detector_call_impl
except ImportError:
    if _SCRIPT_DIR not in sys.path:
        sys.path.insert(0, _SCRIPT_DIR)
    from onset_routing import build_detector_call as _build_detector_call_impl


def _summarize_signal_region_analyses(analyses: list[dict]) -> dict:
    """Build a compact signal-profile summary from per-region analyses."""
    return _summarize_signal_region_analyses_impl(analyses)


def _build_focus_signal_profile(
    source_file: str,
    focus_regions: dict[str, list[dict]],
    y: np.ndarray,
    sr: int,
    *,
    loaded_signal_profile: dict | None = None,
) -> dict | None:
    """Build a combined positive/negative focus-signal profile for one file."""
    regions = list(focus_regions.get(source_file, []))
    if not regions:
        return copy.deepcopy(loaded_signal_profile) if loaded_signal_profile else None

    pos_regions = [region for region in regions if region.get("polarity") == "positive"]
    neg_regions = [region for region in regions if region.get("polarity") == "negative"]
    if not pos_regions and not neg_regions:
        return None

    profile = {
        "source_file": source_file,
        "sr": sr,
        "regions": [],
        "summary": {},
        "negative_regions": [],
        "negative_summary": {},
    }
    if pos_regions:
        pos_profile = _build_signal_profile_impl(y, sr, pos_regions)
        profile["regions"] = pos_profile.get("regions", [])
        profile["summary"] = pos_profile.get("summary", {})
    if neg_regions:
        neg_profile = _build_signal_profile_impl(y, sr, neg_regions)
        profile["negative_regions"] = neg_profile.get("regions", [])
        profile["negative_summary"] = neg_profile.get("summary", {})
    return profile


def _analyze_focus_region_settings(
    audio_path: str | None,
    profile: dict | None,
) -> tuple[dict | None, dict | None]:
    """Return analyzer recommendations for a pre-built focus-signal profile."""
    if not audio_path or not os.path.isfile(audio_path):
        return None, None

    if not profile or not profile.get("summary"):
        return profile, None

    try:
        from analysis.onset_recommendations import analyze_for_onsets
    except ImportError:
        if _PROJECT_ROOT not in sys.path:
            sys.path.insert(0, _PROJECT_ROOT)
        try:
            from analysis.onset_recommendations import analyze_for_onsets
        except Exception:
            return profile, None

    try:
        result = analyze_for_onsets(audio_path, signal_profile=profile)
    except Exception:
        return profile, None
    return profile, result


def _build_signal_profile_from_saved_dirs(
    audio_path: str | None,
    positive_dir: str,
    negative_dir: str,
    pos_manifest: dict | None,
    neg_manifest: dict | None,
) -> dict | None:
    """Build a signal-profile fallback from saved WAV clips when geometry is absent."""
    try:
        import librosa
    except ImportError:
        return None

    def _collect_profile(directory: str, manifest: dict | None) -> tuple[list[dict], dict]:
        entries: list[tuple[str, dict | None]] = []
        if manifest and manifest.get("files"):
            for file_entry in manifest.get("files", []):
                audio_file = file_entry.get("audio_file")
                if not audio_file:
                    continue
                clip_path = os.path.join(directory, audio_file)
                if os.path.isfile(clip_path):
                    entries.append((clip_path, file_entry))
        elif os.path.isdir(directory):
            for filename in sorted(os.listdir(directory)):
                if filename.lower().endswith(".wav"):
                    entries.append((os.path.join(directory, filename), None))

        analyses: list[dict] = []
        summary: dict = {}
        for clip_path, file_entry in entries:
            y_clip, sr_clip = librosa.load(clip_path, sr=None, mono=True)
            if y_clip.size == 0:
                continue
            duration = len(y_clip) / sr_clip
            region_meta = (file_entry or {}).get("region") or {}
            f_low = float(region_meta.get("f_low", 0.0))
            f_high = float(region_meta.get("f_high", sr_clip / 2.0))
            if f_high <= f_low:
                f_low, f_high = 0.0, sr_clip / 2.0
            clip_profile = _build_signal_profile_impl(
                y_clip,
                sr_clip,
                [{"t_start": 0.0, "t_end": duration, "f_low": f_low, "f_high": f_high}],
            )
            analyses.extend(clip_profile.get("regions", []))
            summary = _summarize_signal_region_analyses(analyses)
        return analyses, summary

    pos_regions, pos_summary = _collect_profile(positive_dir, pos_manifest)
    neg_regions, neg_summary = _collect_profile(negative_dir, neg_manifest)
    if not pos_regions and not neg_regions:
        return None

    return {
        "source_file": os.path.basename(audio_path) if audio_path else "",
        "regions": pos_regions,
        "summary": pos_summary,
        "negative_regions": neg_regions,
        "negative_summary": neg_summary,
    }


def _extract_recommended_detect_settings(result: dict | None) -> dict:
    """Return the detector settings payload from an analyzer result."""
    if not isinstance(result, dict):
        return {}

    settings = result.get("settings")
    if isinstance(settings, dict):
        return dict(settings)

    if any(key in result for key in ("ONSET_METHOD", "ONSET_DELTA", "ONSET_HOP_LENGTH")):
        return dict(result)

    return {}


def _compute_per_signal_spectral_threshold(cfg: dict) -> float:
    """Map per-signal deviation settings to a cosine-similarity threshold."""
    vals = []
    for value in cfg.values():
        if not isinstance(value, dict) or not value.get("enabled"):
            continue
        if "lower_pct" in value and "upper_pct" in value:
            vals.append((value["lower_pct"] + value["upper_pct"]) / 2.0)
        elif "deviation_pct" in value:
            vals.append(value["deviation_pct"])

    avg_deviation = float(np.mean(vals)) if vals else 30.0
    bounded = float(np.clip(avg_deviation, 5.0, 100.0))
    return float(np.interp(bounded, [5.0, 100.0], [0.55, 0.20]))


def _compute_per_signal_variable_score_threshold(cfg: dict) -> float:
    """Map per-signal deviation settings to a weighted-match score threshold."""
    vals = []
    for value in cfg.values():
        if not isinstance(value, dict) or not value.get("enabled"):
            continue
        if "lower_pct" in value and "upper_pct" in value:
            vals.append((value["lower_pct"] + value["upper_pct"]) / 2.0)
        elif "deviation_pct" in value:
            vals.append(value["deviation_pct"])

    avg_deviation = float(np.mean(vals)) if vals else 30.0
    bounded = float(np.clip(avg_deviation, 5.0, 100.0))
    return float(np.interp(bounded, [5.0, 100.0], [0.72, 0.52]))


def _build_per_signal_variable_checks(ref_analysis: dict, per_var_config: dict) -> list[dict]:
    """Prepare enabled per-variable bounds for weighted matching."""
    checks = []
    for key, value in per_var_config.items():
        if key == "duration_s":
            continue
        if not isinstance(value, dict) or not value.get("enabled"):
            continue
        ref_val = ref_analysis.get(key)
        if ref_val is None:
            continue
        lower_pct = value.get("lower_pct", value.get("deviation_pct", 30))
        upper_pct = value.get("upper_pct", value.get("deviation_pct", 30))
        lo_bound = float(value.get("lower_bound", float(ref_val) * (1 - lower_pct / 100.0)))
        hi_bound = float(value.get("upper_bound", float(ref_val) * (1 + upper_pct / 100.0)))
        checks.append(
            {
                "key": key,
                "ref_val": float(ref_val),
                "lo_bound": lo_bound,
                "hi_bound": hi_bound,
            }
        )
    return checks


def _score_onsets_by_variable_match(
    onset_times,
    y: np.ndarray,
    sr: int,
    ref_analysis: dict,
    per_var_config: dict,
    ref_region: dict,
    window_sec: float = 0.1,
) -> list[dict]:
    """Score candidate onsets against the selected signal's variable bounds."""
    times = np.array(onset_times, dtype=float)
    if len(times) == 0:
        return []

    checks = _build_per_signal_variable_checks(ref_analysis, per_var_config)
    if not checks:
        return [
            {"time": float(t), "score": 1.0, "failed_keys": [], "candidate": {}}
            for t in times
        ]

    try:
        from analysis.signal_profiles import analyze_region
    except ImportError:
        if _PROJECT_ROOT not in sys.path:
            sys.path.insert(0, _PROJECT_ROOT)
        try:
            from analysis.signal_profiles import analyze_region
        except Exception:
            return [
                {"time": float(t), "score": 1.0, "failed_keys": [], "candidate": {}}
                for t in times
            ]

    f_low = ref_region.get("f_low", 0)
    f_high = ref_region.get("f_high", sr // 2)
    half_win = window_sec / 2.0
    results = []

    for onset_time in times:
        t0 = max(0.0, float(onset_time) - half_win)
        t1 = min(len(y) / sr, float(onset_time) + half_win)
        if t1 - t0 < 0.005:
            results.append(
                {
                    "time": float(onset_time),
                    "score": 0.0,
                    "failed_keys": [check["key"] for check in checks],
                    "candidate": {},
                }
            )
            continue

        try:
            candidate = analyze_region(y, sr, t0, t1, f_low, f_high)
        except Exception:
            results.append(
                {
                    "time": float(onset_time),
                    "score": 0.0,
                    "failed_keys": [check["key"] for check in checks],
                    "candidate": {},
                }
            )
            continue

        components = []
        failed_keys = []
        per_variable = {}
        for check in checks:
            key = check["key"]
            ref_val = check["ref_val"]
            lo_bound = check["lo_bound"]
            hi_bound = check["hi_bound"]
            cand_val = candidate.get(key)
            if cand_val is None:
                component = 0.0
                failed_keys.append(key)
                per_variable[key] = {"component": component, "candidate": None}
                components.append(component)
                continue

            tolerance = max(
                abs(ref_val - lo_bound),
                abs(hi_bound - ref_val),
                abs(ref_val) * 0.05,
                1e-6,
            )
            normalized_distance = abs(float(cand_val) - ref_val) / tolerance
            component = max(0.0, 1.0 - (0.4 * normalized_distance))
            if cand_val < lo_bound or cand_val > hi_bound:
                failed_keys.append(key)
            per_variable[key] = {
                "component": component,
                "candidate": float(cand_val),
                "reference": ref_val,
                "lo_bound": lo_bound,
                "hi_bound": hi_bound,
            }
            components.append(component)

        score = float(np.mean(components)) if components else 1.0
        results.append(
            {
                "time": float(onset_time),
                "score": score,
                "failed_keys": failed_keys,
                "candidate": candidate,
                "per_variable": per_variable,
            }
        )

    return results


def _compute_spectral_similarity_at_time(
    candidate_time: float,
    y: np.ndarray,
    sr: int,
    profile: dict | None,
    window_sec: float = 0.1,
) -> float | None:
    """Return cosine similarity between a candidate window and a spectral template."""
    return _compute_spectral_similarity_at_time_impl(
        candidate_time,
        y,
        sr,
        profile,
        window_sec=window_sec,
    )


def _build_uniform_probe_times(
    region: dict,
    fractions: tuple[float, ...] = (0.05, 0.25, 0.5, 0.75),
) -> list[float]:
    """Return a small set of probe times spanning a focus region."""
    t_start = float(region.get("t_start", 0.0))
    t_end = float(region.get("t_end", t_start))
    duration = max(0.0, t_end - t_start)
    if duration <= 0:
        return [t_start]

    probe_times = []
    for fraction in fractions:
        probe_t = t_start + (duration * fraction)
        probe_t = min(max(probe_t, t_start), t_end)
        if not probe_times or abs(probe_t - probe_times[-1]) > 0.001:
            probe_times.append(probe_t)
    return probe_times


def _region_contains_onset(
    onset_times: list[float] | np.ndarray,
    region: dict,
    margin_sec: float = 0.015,
) -> bool:
    """Return True when an onset lies within or very near a focus region."""
    t_start = float(region.get("t_start", 0.0)) - margin_sec
    t_end = float(region.get("t_end", 0.0)) + margin_sec
    return any(t_start <= float(onset_time) <= t_end for onset_time in onset_times)


def _candidate_peak_times_for_region(
    y: np.ndarray,
    sr: int,
    region: dict,
    *,
    hop_length: int = 128,
    max_candidates: int = 6,
) -> list[float]:
    """Return a few onset-like candidate times from inside a focus region."""
    try:
        import librosa
    except ImportError:
        return []

    t_start = float(region.get("t_start", 0.0))
    t_end = float(region.get("t_end", t_start))
    if t_end <= t_start:
        return []

    context = min(0.03, max((t_end - t_start) * 0.2, 0.005))
    s0 = max(0, int((t_start - context) * sr))
    s1 = min(len(y), int((t_end + context) * sr))
    segment = y[s0:s1]
    if len(segment) < 32:
        return []

    onset_envelope = librosa.onset.onset_strength(
        y=segment,
        sr=sr,
        hop_length=max(1, int(hop_length)),
    )
    if len(onset_envelope) == 0:
        return []

    peak_indices = [
        idx
        for idx in range(len(onset_envelope))
        if (idx == 0 or onset_envelope[idx] >= onset_envelope[idx - 1])
        and (idx == len(onset_envelope) - 1 or onset_envelope[idx] >= onset_envelope[idx + 1])
    ]
    if not peak_indices:
        peak_indices = list(np.argsort(onset_envelope)[-max_candidates:])

    peak_indices = sorted(
        peak_indices,
        key=lambda idx: onset_envelope[idx],
        reverse=True,
    )[:max_candidates]
    frame_times = librosa.frames_to_time(
        np.array(peak_indices),
        sr=sr,
        hop_length=max(1, int(hop_length)),
    )

    candidates = []
    for rel_t in frame_times:
        abs_t = (s0 / sr) + float(rel_t)
        if (t_start - context) <= abs_t <= (t_end + context):
            candidates.append(abs_t)

    deduped = []
    for onset_time in sorted(candidates):
        if not deduped or abs(onset_time - deduped[-1]) > 0.001:
            deduped.append(onset_time)
    return deduped


def _diagnose_candidate_matches(
    candidate_times: list[float],
    y: np.ndarray,
    sr: int,
    signal_profile: dict,
    cfg: dict,
    effective_settings: dict,
    *,
    compute_per_signal_variable_score_threshold: Callable[[dict], float],
    score_onsets_by_variable_match: Callable[..., list[dict]],
    compute_spectral_similarity_at_time: Callable[..., float | None],
) -> dict:
    """Score candidate times against the current per-signal match settings."""
    focus_regions = signal_profile.get("regions", []) or signal_profile.get("positive_regions", [])
    if not focus_regions:
        return {"results": [], "best_result": None, "passed": False}

    ref_region = focus_regions[0]
    region_copy = dict(ref_region)
    region_copy.setdefault("polarity", "positive")

    spectral_profile = _build_spectral_profile_impl(y, sr, [region_copy])
    spectral_threshold = float(effective_settings.get("_spectral_match_threshold", 0.3))
    variable_threshold = float(
        effective_settings.get(
            "_per_signal_variable_score_threshold",
            compute_per_signal_variable_score_threshold(cfg),
        )
    )

    variable_results = score_onsets_by_variable_match(
        candidate_times,
        y,
        sr,
        ref_region,
        cfg,
        ref_region,
    )
    results = []
    for entry in variable_results:
        spectral_similarity = compute_spectral_similarity_at_time(
            entry["time"],
            y,
            sr,
            spectral_profile,
        )
        spectral_pass = (spectral_similarity is None) or (spectral_similarity >= spectral_threshold)
        variable_pass = entry["score"] >= variable_threshold
        norm_spec = 1.0 if spectral_similarity is None else (
            spectral_similarity / max(spectral_threshold, 1e-6)
        )
        norm_var = entry["score"] / max(variable_threshold, 1e-6)
        results.append(
            {
                **entry,
                "spectral_similarity": spectral_similarity,
                "spectral_pass": spectral_pass,
                "variable_pass": variable_pass,
                "passed": spectral_pass and variable_pass,
                "combined_ratio": float((norm_spec + norm_var) / 2.0),
                "spectral_threshold": spectral_threshold,
                "variable_threshold": variable_threshold,
            }
        )

    best_result = max(results, key=lambda item: item["combined_ratio"], default=None)
    return {
        "results": results,
        "best_result": best_result,
        "passed": any(item["passed"] for item in results),
        "spectral_threshold": spectral_threshold,
        "variable_threshold": variable_threshold,
    }


def _evaluate_exemplar_self_check(
    y: np.ndarray,
    sr: int,
    signal_profile: dict,
    cfg: dict,
    effective_settings: dict,
    *,
    build_uniform_probe_times: Callable[[dict], list[float]],
    diagnose_candidate_matches: Callable[..., dict],
) -> dict:
    """Check whether an exemplar can satisfy its own current match settings."""
    focus_regions = signal_profile.get("regions", []) or signal_profile.get("positive_regions", [])
    if not focus_regions:
        return {"passed": True, "probe_results": [], "best_result": None}

    ref_region = focus_regions[0]
    probe_times = build_uniform_probe_times(ref_region)
    report = diagnose_candidate_matches(
        probe_times,
        y,
        sr,
        signal_profile,
        cfg,
        effective_settings,
    )
    return {
        "passed": report.get("passed", False),
        "probe_results": report.get("results", []),
        "best_result": report.get("best_result"),
        "spectral_threshold": report.get("spectral_threshold"),
        "variable_threshold": report.get("variable_threshold"),
    }


def _recover_focus_region_onset(
    y: np.ndarray,
    sr: int,
    region: dict,
    signal_profile: dict,
    cfg: dict,
    effective_settings: dict,
    *,
    build_uniform_probe_times: Callable[[dict], list[float]],
    candidate_peak_times_for_region: Callable[..., list[float]],
    diagnose_candidate_matches: Callable[..., dict],
) -> dict:
    """Try to recover an onset inside a focus region when full-file detection missed it."""
    probe_times = build_uniform_probe_times(region)
    peak_times = candidate_peak_times_for_region(
        y,
        sr,
        region,
        hop_length=int(effective_settings.get("ONSET_HOP_LENGTH", 128)),
    )
    candidate_times = sorted({round(float(t), 6) for t in (probe_times + peak_times)})
    report = diagnose_candidate_matches(
        candidate_times,
        y,
        sr,
        signal_profile,
        cfg,
        effective_settings,
    )
    passing = [item for item in report.get("results", []) if item.get("passed")]
    if passing:
        max_ratio = max(item.get("combined_ratio", 0.0) for item in passing)
        near_best = [
            item for item in passing if item.get("combined_ratio", 0.0) >= max_ratio - 0.05
        ]
        recovered = min(near_best, key=lambda item: item.get("time", float("inf")))
    else:
        recovered = None

    return {
        **report,
        "candidate_times": candidate_times,
        "recovered_time": (None if recovered is None else float(recovered["time"])),
        "recovered_result": recovered,
    }


def _format_match_miss_reason(result: dict | None) -> str:
    """Return a concise human-readable reason for a missed exemplar match."""
    if not result:
        return "no candidate passed local exemplar checks"

    reasons = []
    spec = result.get("spectral_similarity")
    spec_thr = result.get("spectral_threshold")
    if spec is not None and spec_thr is not None and spec < spec_thr:
        reasons.append(f"spectral {spec:.2f}/{spec_thr:.2f}")

    score = result.get("score")
    score_thr = result.get("variable_threshold")
    if score is not None and score_thr is not None and score < score_thr:
        reasons.append(f"variable {score:.2f}/{score_thr:.2f}")

    failed_keys = result.get("failed_keys", []) or []
    if failed_keys:
        reasons.append("weakest: " + ", ".join(failed_keys[:3]))

    return "; ".join(reasons) if reasons else "candidate search did not yield a usable onset"


def _merge_negative_detection_hits(
    existing_hits: list[dict],
    onset_time: float,
    similarity: float,
    signal_num: int,
) -> None:
    """Merge negative detections that refer to the same onset time."""
    for hit in existing_hits:
        if abs(hit["time"] - onset_time) < 0.001:
            hit["similarity"] = max(float(hit.get("similarity", 0.0)), float(similarity))
            if signal_num not in hit["signal_nums"]:
                hit["signal_nums"].append(signal_num)
                hit["signal_nums"].sort()
            return

    existing_hits.append(
        {
            "time": float(onset_time),
            "similarity": float(similarity),
            "signal_nums": [int(signal_num)],
        }
    )


def _build_region_detector_kwargs(settings: dict) -> tuple[str, dict]:
    """Translate onset-finder style settings into onset_detectors kwargs."""
    return _build_detector_call_impl(settings)


__all__ = [
    "_build_per_signal_variable_checks",
    "_build_region_detector_kwargs",
    "_build_uniform_probe_times",
    "_candidate_peak_times_for_region",
    "_compute_per_signal_spectral_threshold",
    "_compute_per_signal_variable_score_threshold",
    "_compute_spectral_similarity_at_time",
    "_diagnose_candidate_matches",
    "_evaluate_exemplar_self_check",
    "_extract_recommended_detect_settings",
    "_format_match_miss_reason",
    "_merge_negative_detection_hits",
    "_recover_focus_region_onset",
    "_region_contains_onset",
    "_score_onsets_by_variable_match",
]