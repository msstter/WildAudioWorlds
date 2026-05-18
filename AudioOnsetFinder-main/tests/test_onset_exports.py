"""Tests for onset export helpers."""

from scripts.onset_exports import (
    write_audacity_labels,
    write_praat_textgrid_export,
    write_whisper_transcript_exports,
)


def test_write_audacity_labels_uses_expected_precision_and_tags(tmp_path):
    refined_path = write_audacity_labels(
        str(tmp_path),
        "demo.wav",
        [0.1234567, 1.2345678],
        refine_enabled=True,
    )

    assert refined_path.endswith("demo_labels.txt")
    assert tmp_path.joinpath("demo_labels.txt").read_text(encoding="utf-8") == (
        "0.123457\t0.123457\tOnsetR_1\n"
        "1.234568\t1.234568\tOnsetR_2\n"
    )

    plain_path = write_audacity_labels(
        str(tmp_path),
        "plain.wav",
        [0.1234567],
        refine_enabled=False,
    )

    assert plain_path.endswith("plain_labels.txt")
    assert tmp_path.joinpath("plain_labels.txt").read_text(encoding="utf-8") == (
        "0.1235\t0.1235\tOnset_1\n"
    )


def test_write_whisper_transcript_exports_writes_text_srt_and_full_text(tmp_path):
    export = write_whisper_transcript_exports(
        str(tmp_path),
        "speech.wav",
        [
            {"start": 0.25, "end": 0.75, "word": "hello"},
            {"start": 61.5, "end": 62.0, "word": "world"},
        ],
    )

    assert export["full_text"] == "hello world"
    assert tmp_path.joinpath("speech_transcript.txt").read_text(encoding="utf-8") == (
        "[0.250 - 0.750]  hello\n"
        "[61.500 - 62.000]  world\n"
    )
    assert tmp_path.joinpath("speech_transcript.srt").read_text(encoding="utf-8") == (
        "1\n"
        "00:00:00.250 --> 00:00:00.750\n"
        "hello\n\n"
        "2\n"
        "00:01:01.500 --> 00:01:02.000\n"
        "world\n\n"
    )
    assert export["txt_path"].endswith("speech_transcript.txt")
    assert export["srt_path"].endswith("speech_transcript.srt")


def test_write_praat_textgrid_export_writes_onset_and_word_tiers(tmp_path):
    textgrid_path = write_praat_textgrid_export(
        str(tmp_path),
        "speech.wav",
        [0.5, 1.25],
        2.0,
        transcript_entries=[
            {"start": 0.6, "end": 0.9, "word": "hello"},
            {"start": 1.2, "end": 1.5, "word": "world"},
        ],
    )

    content = tmp_path.joinpath("speech.TextGrid").read_text(encoding="utf-8")
    assert textgrid_path.endswith("speech.TextGrid")
    assert 'Object class = "TextGrid"' in content
    assert 'name = "Onsets"' in content
    assert 'mark = "Onset_1"' in content
    assert 'name = "Words"' in content
    assert 'text = "hello"' in content
    assert 'text = "world"' in content