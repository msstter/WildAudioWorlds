"""Export helpers for onset-finder review artifacts."""

from __future__ import annotations

import os


def write_audacity_labels(audio_folder: str, filename: str, onset_times, *, refine_enabled: bool) -> str:
    """Write Audacity label lines for the supplied onset times and return the output path."""
    label_filename = f"{os.path.splitext(filename)[0]}_labels.txt"
    label_path = os.path.join(audio_folder, label_filename)
    precision = 6 if refine_enabled else 4
    tag = "OnsetR" if refine_enabled else "Onset"

    with open(label_path, "w", encoding="utf-8") as handle:
        for index, onset_time in enumerate(onset_times, start=1):
            handle.write(
                f"{onset_time:.{precision}f}\t{onset_time:.{precision}f}\t{tag}_{index}\n"
            )

    return label_path


def write_whisper_transcript_exports(audio_folder: str, filename: str, transcript_entries: list[dict]) -> dict:
    """Write plain-text and SRT transcript exports and return their paths plus combined text."""
    base = os.path.splitext(filename)[0]
    txt_path = os.path.join(audio_folder, f"{base}_transcript.txt")
    srt_path = os.path.join(audio_folder, f"{base}_transcript.srt")

    with open(txt_path, "w", encoding="utf-8") as handle:
        for entry in transcript_entries:
            handle.write(f"[{entry['start']:.3f} - {entry['end']:.3f}]  {entry['word']}\n")

    with open(srt_path, "w", encoding="utf-8") as handle:
        for index, entry in enumerate(transcript_entries, start=1):
            start_hours, start_rest = divmod(entry["start"], 3600)
            start_minutes, start_seconds = divmod(start_rest, 60)
            end_hours, end_rest = divmod(entry["end"], 3600)
            end_minutes, end_seconds = divmod(end_rest, 60)
            handle.write(f"{index}\n")
            handle.write(
                f"{int(start_hours):02d}:{int(start_minutes):02d}:{start_seconds:06.3f} --> "
                f"{int(end_hours):02d}:{int(end_minutes):02d}:{end_seconds:06.3f}\n"
            )
            handle.write(f"{entry['word']}\n\n")

    return {
        "txt_path": txt_path,
        "srt_path": srt_path,
        "full_text": " ".join(entry["word"] for entry in transcript_entries),
    }


def write_praat_textgrid_export(
    audio_folder: str,
    filename: str,
    onset_times,
    total_duration: float,
    *,
    transcript_entries: list[dict] | None = None,
) -> str:
    """Write a Praat TextGrid containing onset points and optional word intervals."""
    base = os.path.splitext(filename)[0]
    textgrid_path = os.path.join(audio_folder, f"{base}.TextGrid")
    has_words = bool(transcript_entries)
    duration = float(total_duration)

    tier_lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0",
        f"xmax = {duration:.6f}",
        "tiers? <exists>",
        f"size = {2 if has_words else 1}",
        "item []:",
        "    item [1]:",
        '        class = "TextTier"',
        '        name = "Onsets"',
        "        xmin = 0",
        f"        xmax = {duration:.6f}",
        f"        points: size = {len(onset_times)}",
    ]

    for onset_index, onset_time in enumerate(onset_times, start=1):
        tier_lines.append(f"        points [{onset_index}]:")
        tier_lines.append(f"            number = {float(onset_time):.6f}")
        tier_lines.append(f'            mark = "Onset_{onset_index}"')

    if has_words:
        word_intervals: list[tuple[float, float, str]] = []
        previous_end = 0.0
        for entry in transcript_entries or []:
            if entry["start"] > previous_end + 0.001:
                word_intervals.append((previous_end, entry["start"], ""))
            word_intervals.append((entry["start"], entry["end"], entry["word"]))
            previous_end = entry["end"]
        if previous_end < duration:
            word_intervals.append((previous_end, duration, ""))

        tier_lines.extend(
            [
                "    item [2]:",
                '        class = "IntervalTier"',
                '        name = "Words"',
                "        xmin = 0",
                f"        xmax = {duration:.6f}",
                f"        intervals: size = {len(word_intervals)}",
            ]
        )
        for interval_index, (start, end, word) in enumerate(word_intervals, start=1):
            tier_lines.append(f"        intervals [{interval_index}]:")
            tier_lines.append(f"            xmin = {float(start):.6f}")
            tier_lines.append(f"            xmax = {float(end):.6f}")
            tier_lines.append(f'            text = "{word}"')

    with open(textgrid_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(tier_lines) + "\n")

    return textgrid_path


__all__ = [
    "write_audacity_labels",
    "write_praat_textgrid_export",
    "write_whisper_transcript_exports",
]