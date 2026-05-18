"""Source separation using Demucs (Meta / Kyutai, MIT license).

This script wraps the Demucs deep-learning source separation model to split
audio recordings into isolated stems (drums, bass, vocals, other — and
optionally guitar + piano with the 6-source model).

It can be used as a standalone pre-processing step or integrated into the
Audio Editor pipeline.  When enabled in the GUI the separated stems are
saved to subfolders and can optionally be fed into the rest of the Audio
Editor for further cleaning.

Usage (standalone):
    python demucs_separator.py /path/to/audioFiles

    # Use fine-tuned model for higher quality (4× slower)
    python demucs_separator.py /path/to/audioFiles --model htdemucs_ft

    # Separate only vocals vs. everything else (karaoke mode)
    python demucs_separator.py /path/to/audioFiles --two-stems vocals

    # 6-source model (adds guitar + piano)
    python demucs_separator.py /path/to/audioFiles --model htdemucs_6s

    # Save output as float32 WAV (higher precision)
    python demucs_separator.py /path/to/audioFiles --float32

    # Force CPU (no GPU)
    python demucs_separator.py /path/to/audioFiles --device cpu

    # Reduce memory usage with smaller segment size
    python demucs_separator.py /path/to/audioFiles --segment 8
"""

import argparse
import os
import sys


def check_demucs_available():
    """Check if demucs is installed and importable."""
    try:
        import demucs.separate  # noqa: F401
        return True
    except ImportError:
        return False


def parse_arguments():
    """Parse command-line arguments for the Demucs separator."""
    parser = argparse.ArgumentParser(
        description="Separate audio into stems using Demucs deep-learning "
                    "source separation. Produces isolated drums, bass, vocals, "
                    "and other tracks for each input file."
    )
    parser.add_argument(
        "input_folder",
        help="Path to the folder of audio files to separate."
    )
    parser.add_argument(
        "--files",
        nargs="+",
        default=None,
        metavar="FILE",
        help="Only process the specified files from the input folder."
    )
    parser.add_argument(
        "--output-folder",
        type=str,
        default=None,
        help="Output folder for separated stems. Default: <input>_demucs_stems"
    )
    parser.add_argument(
        "--model", "-n",
        type=str,
        default="htdemucs",
        help="Demucs model to use. Options: htdemucs (default, fast), "
             "htdemucs_ft (fine-tuned, 4× slower but better), "
             "htdemucs_6s (6 sources: adds guitar + piano), "
             "hdemucs_mmi (v3 hybrid). (default: %(default)s)"
    )
    parser.add_argument(
        "--two-stems",
        type=str,
        default=None,
        metavar="STEM",
        help="Only separate into two stems: the named stem vs. everything "
             "else. E.g. --two-stems vocals produces vocals.wav and "
             "no_vocals.wav. Options: vocals, drums, bass, other. "
             "(default: disabled — full separation)"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cpu", "cuda", "mps"],
        help="Device to run inference on. 'auto' uses GPU if available, "
             "falls back to CPU. 'mps' = Apple Silicon GPU. (default: %(default)s)"
    )
    parser.add_argument(
        "--shifts",
        type=int,
        default=1,
        help="Number of random shift predictions to average (shift trick). "
             "Higher = better quality but SHIFTS× slower. Only useful with "
             "GPU. 1 = disabled (default). (default: %(default)s)"
    )
    parser.add_argument(
        "--overlap",
        type=float,
        default=0.25,
        help="Overlap between prediction windows (0.0-1.0). "
             "Default 0.25 (25%%). Reduce to 0.1 for faster processing. "
             "(default: %(default)s)"
    )
    parser.add_argument(
        "--segment",
        type=int,
        default=None,
        help="Segment length in seconds for splitting long files. "
             "Reduce to save GPU memory (minimum ~8). Default: model default. "
             "Note: Hybrid Transformer models support max 7.8s segments."
    )
    parser.add_argument(
        "--float32",
        action="store_true",
        default=False,
        help="Save output as float32 WAV instead of int16. "
             "Higher precision, larger files. (default: int16)"
    )
    parser.add_argument(
        "--int24",
        action="store_true",
        default=False,
        help="Save output as 24-bit WAV instead of int16. "
             "Higher dynamic range. (default: int16)"
    )
    parser.add_argument(
        "--flac",
        action="store_true",
        default=False,
        help="Save output as FLAC (lossless compressed). (default: WAV)"
    )
    parser.add_argument(
        "--mp3",
        action="store_true",
        default=False,
        help="Save output as MP3 instead of WAV. (default: WAV)"
    )
    parser.add_argument(
        "--mp3-bitrate",
        type=int,
        default=320,
        help="MP3 bitrate in kbps when --mp3 is used. (default: %(default)s)"
    )
    parser.add_argument(
        "--output-format",
        type=str,
        default=None,
        choices=["wav-int16", "wav-int24", "wav-float32", "flac", "mp3"],
        help="Output format shorthand. Overrides --float32/--int24/--flac/--mp3 "
             "flags when set. (default: wav-int16)"
    )
    parser.add_argument(
        "--other-method",
        type=str,
        default="add",
        choices=["add", "minus", "none"],
        help="How to compute the 'no_<stem>' track in two-stems mode. "
             "'add' = sum remaining stems. 'minus' = subtract from original. "
             "'none' = don't save it. (default: %(default)s)"
    )
    parser.add_argument(
        "--clip-mode",
        type=str,
        default="rescale",
        choices=["rescale", "clamp", "none"],
        help="How to handle output clipping. 'rescale' (default) adjusts "
             "volume to prevent clipping (may change relative stem volumes). "
             "'clamp' hard-clips at \u00b11.0. 'none' = no strategy. "
             "(default: %(default)s)"
    )
    parser.add_argument(
        "--jobs", "-j",
        type=int,
        default=1,
        help="Number of parallel separation jobs. Multiplies RAM usage. "
             "(default: %(default)s)"
    )
    return parser.parse_args()


def build_demucs_args(input_paths, output_folder, model="htdemucs",
                      two_stems=None, other_method="add",
                      device="auto", shifts=1,
                      overlap=0.25, segment=None, float32=False,
                      int24=False, flac=False,
                      mp3=False, mp3_bitrate=320, clip_mode="rescale",
                      jobs=1):
    """Build the argument list for demucs.separate.main().

    Parameters
    ----------
    input_paths : list of str
        Paths to individual audio files to separate.
    output_folder : str
        Root output directory. Stems will be saved under
        ``<output_folder>/<model_name>/<track_name>/``.
    model : str
        Model name (e.g. "htdemucs", "htdemucs_ft", "htdemucs_6s").
    two_stems : str or None
        If set, only produce two stems (named + "no_<named>").
    other_method : str
        How to compute the complementary stem in two-stems mode.
        "add", "minus", or "none".
    device : str
        "auto", "cpu", "cuda", or "mps".
    shifts : int
        Number of random-shift predictions to average.
    overlap : float
        Overlap ratio between windows (0.0-1.0).
    segment : int or None
        Segment length in seconds (None = model default).
    float32 : bool
        Save as float32 WAV.
    int24 : bool
        Save as 24-bit WAV.
    flac : bool
        Save as FLAC.
    mp3 : bool
        Save as MP3.
    mp3_bitrate : int
        MP3 bitrate in kbps.
    clip_mode : str
        "rescale", "clamp", or "none".
    jobs : int
        Number of parallel jobs.

    Returns
    -------
    list of str
        Argument list suitable for ``demucs.separate.main()``.
    """
    args = ["-n", model, "-o", output_folder]

    if device == "cpu":
        args.extend(["-d", "cpu"])
    elif device == "cuda":
        args.extend(["-d", "cuda"])
    elif device == "mps":
        args.extend(["-d", "mps"])
    # "auto" = let demucs decide (default behaviour)

    if two_stems:
        args.extend(["--two-stems", two_stems])
        if other_method != "add":
            args.extend(["--other-method", other_method])

    if shifts > 1:
        args.extend(["--shifts", str(shifts)])

    if overlap != 0.25:
        args.extend(["--overlap", str(overlap)])

    if segment is not None:
        args.extend(["--segment", str(segment)])

    if float32:
        args.append("--float32")
    elif int24:
        args.append("--int24")

    if flac:
        args.append("--flac")
    elif mp3:
        args.append("--mp3")
        args.extend(["--mp3-bitrate", str(mp3_bitrate)])

    if clip_mode != "rescale":
        args.extend(["--clip-mode", clip_mode])

    if jobs > 1:
        args.extend(["-j", str(jobs)])

    args.extend(input_paths)
    return args


def run_demucs(input_folder, output_folder=None, model="htdemucs",
               two_stems=None, other_method="add",
               device="auto", shifts=1, overlap=0.25,
               segment=None, float32=False, int24=False, flac=False,
               mp3=False, mp3_bitrate=320,
               clip_mode="rescale", jobs=1, selected_files=None):
    """Run Demucs source separation on all audio files in a folder.

    Parameters
    ----------
    input_folder : str
        Folder containing audio files.
    output_folder : str or None
        Output folder.  Defaults to ``<input_folder>_demucs_stems``.
    model : str
        Demucs model name.
    two_stems : str or None
        If set, only produce two stems.
    other_method : str
        "add", "minus", or "none" — how to build the no_<stem> track.
    device : str
        "auto", "cpu", "cuda", or "mps".
    shifts : int
        Number of shift-trick predictions.
    overlap : float
        Window overlap ratio.
    segment : int or None
        Segment length in seconds.
    float32 : bool
        Save as float32 WAV.
    int24 : bool
        Save as 24-bit WAV.
    flac : bool
        Save as FLAC.
    mp3 : bool
        Save as MP3.
    mp3_bitrate : int
        MP3 bitrate.
    clip_mode : str
        "rescale", "clamp", or "none".
    jobs : int
        Parallel jobs.
    selected_files : list of str or None
        Only process these filenames.  None = all files.

    Returns
    -------
    int
        Number of files processed.
    str
        Path to the output folder containing stems.
    """
    if not check_demucs_available():
        print("ERROR: Demucs is not installed. Install it with:")
        print("  pip install demucs")
        sys.exit(1)

    import demucs.separate

    if output_folder is None:
        output_folder = input_folder.rstrip("/\\") + "_demucs_stems"

    os.makedirs(output_folder, exist_ok=True)

    valid_extensions = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac")
    available_files = sorted(
        f for f in os.listdir(input_folder)
        if f.lower().endswith(valid_extensions)
    )

    if selected_files:
        sel_set = set(selected_files)
        audio_files = [f for f in available_files if f in sel_set]
    else:
        audio_files = available_files

    if not audio_files:
        print(f"WARNING: No audio files found in {input_folder}")
        return 0, output_folder

    # Build full paths
    input_paths = [os.path.join(input_folder, f) for f in audio_files]

    # Determine output format label
    if flac:
        fmt_label = "FLAC"
    elif mp3:
        fmt_label = f"MP3 {mp3_bitrate}kbps"
    elif float32:
        fmt_label = "float32 WAV"
    elif int24:
        fmt_label = "24-bit WAV"
    else:
        fmt_label = "int16 WAV"

    print(f"\n{'=' * 60}")
    print(f"  DEMUCS SOURCE SEPARATION")
    print(f"{'=' * 60}")
    print(f"  Model:         {model}")
    print(f"  Input folder:  {input_folder}")
    print(f"  Output folder: {output_folder}")
    print(f"  Files:         {len(audio_files)}")
    if two_stems:
        print(f"  Two-stems:     {two_stems} vs. no_{two_stems}")
        print(f"  Other-method:  {other_method}")
    else:
        stems = "drums, bass, vocals, other"
        if "6s" in model:
            stems += ", guitar, piano"
        print(f"  Stems:         {stems}")
    print(f"  Device:        {device}")
    if shifts > 1:
        print(f"  Shifts:        {shifts} (shift trick)")
    if segment is not None:
        print(f"  Segment:       {segment}s")
    print(f"  Output format: {fmt_label}")
    print(f"  Clip mode:     {clip_mode}")
    print()

    # Build and run demucs
    demucs_args = build_demucs_args(
        input_paths, output_folder, model=model,
        two_stems=two_stems, other_method=other_method,
        device=device, shifts=shifts,
        overlap=overlap, segment=segment, float32=float32,
        int24=int24, flac=flac,
        mp3=mp3, mp3_bitrate=mp3_bitrate, clip_mode=clip_mode,
        jobs=jobs
    )

    print(f"  Running: demucs {' '.join(demucs_args[:6])}{'...' if len(demucs_args) > 6 else ''}")
    print()

    try:
        demucs.separate.main(demucs_args)
    except SystemExit as e:
        if e.code != 0:
            print(f"ERROR: Demucs exited with code {e.code}")
            return 0, output_folder
    except Exception as e:
        print(f"ERROR: Demucs failed: {e}")
        return 0, output_folder

    print(f"\n  Demucs complete — {len(audio_files)} file(s) separated.")
    print(f"  Stems saved to: {output_folder}")

    return len(audio_files), output_folder


def main():
    args = parse_arguments()

    if not check_demucs_available():
        print("ERROR: Demucs is not installed. Install it with:")
        print("  pip install demucs")
        print("\nDemucs requires PyTorch. If you don't have it:")
        print("  pip install torch torchaudio")
        sys.exit(1)

    if not os.path.isdir(args.input_folder):
        print(f"ERROR: Input folder does not exist: {args.input_folder}")
        sys.exit(1)

    device = args.device
    if device == "auto":
        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        except ImportError:
            device = "cpu"

    # Resolve output-format shorthand into individual flags
    float32 = args.float32
    int24 = args.int24
    flac = args.flac
    mp3 = args.mp3
    if args.output_format:
        float32 = args.output_format == "wav-float32"
        int24 = args.output_format == "wav-int24"
        flac = args.output_format == "flac"
        mp3 = args.output_format == "mp3"

    n_processed, output_path = run_demucs(
        args.input_folder,
        output_folder=args.output_folder,
        model=args.model,
        two_stems=args.two_stems,
        other_method=args.other_method,
        device=device,
        shifts=args.shifts,
        overlap=args.overlap,
        segment=args.segment,
        float32=float32,
        int24=int24,
        flac=flac,
        mp3=mp3,
        mp3_bitrate=args.mp3_bitrate,
        clip_mode=args.clip_mode,
        jobs=args.jobs,
        selected_files=args.files,
    )

    if n_processed == 0:
        print("\nNo files were processed.")
        sys.exit(1)

    print(f"\nSUCCESS! Separated {n_processed} file(s).")
    print(f"Stems are in: {output_path}")


if __name__ == "__main__":
    main()
