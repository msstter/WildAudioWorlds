"""Pre-process audio by muting background noise while preserving the timeline.

This script is the first step in the bioacoustics rhythm pipeline. It scans a
folder of raw audio recordings, identifies intervals that fall below a
configurable dB threshold, and replaces them with silence — without cutting or
shortening the file. This guarantees that inter-onset intervals measured by the
downstream onset finder reflect the true temporal structure of the recording.

Two output folders are created:
- ``<input_folder>_muted_clean/``   — cleaned audio for the onset finder
- ``<input_folder>_rejected_noise/`` — rejected noise tracks for manual auditing

All noise-related pre-filtering (high-pass filter, dB-based muting) is
centralised here so that the onset finder can focus purely on onset
detection without applying its own redundant noise filters.

Usage examples:
    # Process the default audioFiles/ folder
    python audio_editor.py

    # Process a specific folder with custom settings
    python audio_editor.py /path/to/audioFiles_birds --db-threshold 35 --highpass 500

    # Disable high-pass filter and crossfade
    python audio_editor.py audioFiles_chimpanzee --highpass 0 --fade-ms 0

    # Use adaptive per-file threshold instead of a fixed dB value
    python audio_editor.py --auto-threshold

    # Adaptive threshold with custom margin and noise profile export
    python audio_editor.py --auto-threshold --noise-margin-db 18 --save-noise-profile

    # Spectral denoising to remove persistent background (cicadas, hiss, hum)
    python audio_editor.py --spectral-denoise

    # Combine spectral denoising with adaptive muting for maximum cleanup
    python audio_editor.py --spectral-denoise --auto-threshold --highpass 200

    # HPSS: keep only percussive transients (primate drumming, insect clicks)
    python audio_editor.py --hpss --hpss-target percussive

    # HPSS: keep only harmonic content (bird calls, whale moans)
    python audio_editor.py --hpss --hpss-target harmonic --hpss-margin 4.0

    # HPSS + spectral denoise + adaptive muting (full pipeline)
    python audio_editor.py --hpss --hpss-target percussive --spectral-denoise --auto-threshold

    # --- Enhancement / amplification features (opposite of removal) ---

    # Bandpass boost: amplify bird call frequencies (1-6 kHz) by 8 dB
    python audio_editor.py --bandpass-boost --boost-low-hz 1000 --boost-high-hz 6000 --boost-gain-db 8

    # HPSS emphasis: boost percussive transients by 6 dB while retaining harmonics
    python audio_editor.py --hpss --hpss-target percussive --hpss-emphasis-db 6

    # Spectral contrast enhancement: amplify sounds that stand out from background
    python audio_editor.py --spectral-enhance --enhance-factor 3.0

    # Dynamic range compression: boost quiet sounds closer to loud ones
    python audio_editor.py --compress --compress-ratio 4.0

    # Transient sharpening: emphasize the attack of each onset for cleaner detection
    python audio_editor.py --sharpen-transients --sharpen-gain-db 9

    # Full enhancement pipeline: boost target band + enhance + compress + sharpen
    python audio_editor.py --bandpass-boost --boost-low-hz 500 --boost-high-hz 4000 --spectral-enhance --compress --sharpen-transients

    # --- Utility / standardisation features ---

    # Low-pass filter: cut everything above 8 kHz (useful for birdsong analysis)
    python audio_editor.py --lowpass 8000

    # Combined high-pass + low-pass = bandpass isolation (200-6000 Hz)
    python audio_editor.py --highpass 200 --lowpass 6000

    # Notch filter: remove 50 Hz and 60 Hz power-line hum
    python audio_editor.py --notch 50 60

    # Pre-emphasis: compensate for high-frequency distance roll-off
    python audio_editor.py --pre-emphasis 0.97

    # Peak normalization: standardise volume across all files
    python audio_editor.py --normalize peak --normalize-target-db -1.0

    # RMS normalization: match perceived loudness across files
    python audio_editor.py --normalize rms --normalize-target-db -18.0

    # Trim leading/trailing silence from output
    python audio_editor.py --trim-silence --trim-threshold-db 40

    # Resample all files to 44100 Hz for consistent onset timing
    python audio_editor.py --resample 44100

    # Use just the left channel of stereo recordings
    python audio_editor.py --channel left

    # Full kitchen-sink pipeline: all cleaning + enhancement + standardisation
    python audio_editor.py --highpass 200 --lowpass 8000 --notch 50 60 \\
        --pre-emphasis 0.97 --hpss --hpss-target percussive \\
        --spectral-denoise --spectral-enhance --compress --sharpen-transients \\
        --normalize peak --trim-silence --resample 44100
"""

import argparse  # parse command-line arguments for user-configurable run options
import json      # save noise profile data
import os        # path operations, directory listing, folder creation
import sys       # exit with status code and error handling

import librosa   # audio I/O and signal-processing helpers (splitting, loading)
import noisereduce as nr  # spectral gating for persistent background noise removal
import numpy as np  # numerical arrays for waveform manipulation
import soundfile as sf  # writing the output WAV files
from scipy.signal import butter, iirnotch, sosfilt  # filter implementations


# ==========================================
# 1. ARGUMENT PARSING
# ==========================================
def parse_arguments():
    """Parse command-line arguments for the audio muter."""
    parser = argparse.ArgumentParser(
        description="Pre-process audio files by muting background noise below a dB "
                    "threshold. Preserves the original timeline and duration so "
                    "downstream rhythm extraction is not distorted."
    )
    parser.add_argument(
        "input_folder",
        nargs="?",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "audioFiles"),
        help="Path to the folder of raw audio files to process. "
             "(default: %(default)s)"
    )
    parser.add_argument(
        "--files",
        nargs="+",
        default=None,
        metavar="FILE",
        help="Only process the specified files from the input folder. "
             "When omitted, all supported audio files in the folder are processed."
    )
    parser.add_argument(
        "--db-threshold",
        type=int,
        default=30,
        help="How far below the peak volume (in dB) is considered noise. "
             "Lower values are more aggressive (mute more). "
             "Recommended: 20-25 for clean studio recordings, 30-40 for field "
             "recordings. (default: %(default)s)"
    )
    parser.add_argument(
        "--highpass",
        type=int,
        default=0,
        metavar="HZ",
        help="Apply a high-pass filter at this frequency (in Hz) before muting. "
             "Removes low-frequency environmental rumble (wind, traffic, etc.). "
             "Set to 0 to disable. Recommended: 200 for general use, 500 for "
             "birdsong, 80 for percussion. (default: %(default)s)"
    )
    parser.add_argument(
        "--lowpass",
        type=int,
        default=0,
        metavar="HZ",
        help="Apply a low-pass filter at this frequency (in Hz) before muting. "
             "Removes high-frequency noise above the species' vocal range "
             "(e.g. equipment hiss, ultrasonic interference). Companion to "
             "--highpass. Set to 0 to disable. Recommended: 8000 for birdsong, "
             "2000 for elephant/whale infrasound, 10000 for general use. "
             "(default: %(default)s)"
    )
    parser.add_argument(
        "--notch",
        type=float,
        nargs="+",
        default=None,
        metavar="HZ",
        help="Apply narrow notch (band-reject) filters at one or more specific "
             "frequencies. Surgically removes known interference without "
             "affecting neighbouring frequencies — e.g. 50 or 60 Hz power-line "
             "hum, a specific cicada frequency. More precise than spectral "
             "denoising. Multiple values can be given: --notch 50 60 120. "
             "(default: disabled)"
    )
    parser.add_argument(
        "--notch-q",
        type=float,
        default=30.0,
        help="Quality factor for the notch filter(s). Higher = narrower notch. "
             "30 is suitable for power-line hum; 10-15 for broader tonal "
             "interference. (default: %(default)s)"
    )
    parser.add_argument(
        "--fade-ms",
        type=float,
        default=5.0,
        help="Crossfade duration in milliseconds at each mute boundary. "
             "Prevents hard transients from being falsely detected as onsets "
             "by the onset finder. Set to 0 to disable. (default: %(default)s)"
    )
    parser.add_argument(
        "--auto-threshold",
        action="store_true",
        default=False,
        help="Enable adaptive per-file threshold. Estimates each file's noise "
             "floor and sets top_db relative to it, instead of using a fixed "
             "value. Overrides --db-threshold when enabled."
    )
    parser.add_argument(
        "--noise-margin-db",
        type=float,
           default=6.0,
        help="When --auto-threshold is enabled, how many dB above the estimated "
             "noise floor to set the muting threshold. Higher values preserve "
               "less signal and mute more noise. Recommended: 4-10. "
             "(default: %(default)s)"
    )
    parser.add_argument(
        "--save-noise-profile",
        action="store_true",
        default=False,
        help="Save a JSON noise profile for each file alongside the cleaned "
             "output. Contains noise floor estimate, chosen threshold, and "
             "per-band spectral levels. (default: %(default)s)"
    )
    parser.add_argument(
        "--spectral-denoise",
        action="store_true",
        default=False,
        help="Enable spectral noise reduction before amplitude muting. "
             "Estimates the stationary (persistent) background spectrum — "
             "e.g. cicadas, generator hum, tape hiss — and attenuates it "
             "while preserving transient events like vocalizations. "
             "Runs BEFORE the dB-based muting step."
    )
    parser.add_argument(
        "--denoise-strength",
        type=float,
        default=1.5,
        help="How aggressively to suppress stationary noise when "
             "--spectral-denoise is enabled. 1.0 = standard reduction, "
             "2.0 = very aggressive. Recommended: 1.0-2.0. "
             "(default: %(default)s)"
    )
    parser.add_argument(
        "--hpss",
        action="store_true",
        default=False,
        help="Enable Harmonic-Percussive Source Separation (HPSS). Decomposes "
             "the audio into a smooth harmonic track (sustained tones like bird "
             "calls, whale moans, wind) and a sharp percussive track (transients "
             "like primate drumming, insect clicks, human percussion). Runs "
             "BEFORE spectral denoising and dB muting. The component selected "
             "by --hpss-target is muted and saved; both raw components are also "
             "saved for auditing. Preserves the global timeline."
    )
    parser.add_argument(
        "--hpss-target",
        type=str,
        default="percussive",
        choices=["harmonic", "percussive", "both"],
        help="Which HPSS component to keep for downstream analysis. "
             "'harmonic' = sustained tones (bird song, whale moans). "
             "'percussive' = sharp transients (drumming, clicks, percussion). "
             "'both' = no separation, just export the component tracks for "
             "auditing. (default: %(default)s)"
    )
    parser.add_argument(
        "--hpss-margin",
        type=float,
        default=2.0,
        help="HPSS separation margin. Higher values give cleaner separation "
             "but may lose quieter signal. 1.0 = soft split, 2.0 = moderate "
             "(default), 4.0 = hard split. (default: %(default)s)"
    )
    parser.add_argument(
        "--hpss-emphasis-db",
        type=float,
        default=0.0,
        help="When > 0 and --hpss is enabled, BOOST the target HPSS component "
             "by this many dB instead of isolating it. Both harmonic and "
             "percussive parts are kept in the output — the target is simply "
             "made louder. This is the 'positive counterpart' to full HPSS "
             "isolation. Recommended: 3-9 dB. 0 = isolate (default behaviour). "
             "(default: %(default)s)"
    )

    # --- Enhancement / amplification arguments ---
    parser.add_argument(
        "--bandpass-boost",
        action="store_true",
        default=False,
        help="Enable bandpass frequency boost. Amplifies a target frequency "
             "band (set by --boost-low-hz and --boost-high-hz) by --boost-gain-db. "
             "This is the positive counterpart to the high-pass filter: instead "
             "of cutting unwanted frequencies, it boosts the wanted ones. "
             "Useful for amplifying species-specific frequency ranges "
             "(e.g. 1-6 kHz for bird calls, 80-500 Hz for primate drumming)."
    )
    parser.add_argument(
        "--boost-low-hz",
        type=int,
        default=500,
        metavar="HZ",
        help="Lower edge of the bandpass boost range in Hz. "
             "(default: %(default)s)"
    )
    parser.add_argument(
        "--boost-high-hz",
        type=int,
        default=4000,
        metavar="HZ",
        help="Upper edge of the bandpass boost range in Hz. "
             "(default: %(default)s)"
    )
    parser.add_argument(
        "--boost-gain-db",
        type=float,
        default=6.0,
        help="How many dB to boost the target frequency band when "
             "--bandpass-boost is enabled. Higher values amplify more. "
             "Recommended: 3-12. (default: %(default)s)"
    )
    parser.add_argument(
        "--spectral-enhance",
        action="store_true",
        default=False,
        help="Enable spectral contrast enhancement. Amplifies spectral peaks "
             "that deviate from the stationary background — transient "
             "vocalizations, percussion hits, etc. become louder relative to "
             "the constant background. This is the positive counterpart to "
             "spectral denoising: instead of pushing noise down, it lifts "
             "signal up. Runs AFTER spectral denoising if both are enabled."
    )
    parser.add_argument(
        "--enhance-factor",
        type=float,
        default=2.0,
        help="How much to amplify spectral peaks above the background when "
             "--spectral-enhance is enabled. 1.0 = no change, 2.0 = double "
             "the deviation (default), 4.0 = aggressive. (default: %(default)s)"
    )
    parser.add_argument(
        "--compress",
        action="store_true",
        default=False,
        help="Enable upward dynamic range compression. Boosts audio that "
             "falls below --compress-threshold-db toward that threshold, "
             "making quiet sounds more audible. This is the positive "
             "counterpart to dB-based muting: instead of silencing quiet "
             "parts, it amplifies them. Useful for field recordings where "
             "target calls vary greatly in distance/volume."
    )
    parser.add_argument(
        "--compress-ratio",
        type=float,
        default=3.0,
        help="Compression ratio for --compress. Higher = more aggressive "
             "levelling. 2.0 = gentle, 3.0 = moderate (default), 6.0+ = heavy. "
             "(default: %(default)s)"
    )
    parser.add_argument(
        "--compress-threshold-db",
        type=float,
        default=-30.0,
        help="Threshold in dBFS below which upward compression is applied. "
             "Audio quieter than this is boosted toward this level. "
             "(default: %(default)s)"
    )
    parser.add_argument(
        "--sharpen-transients",
        action="store_true",
        default=False,
        help="Enable transient sharpening. Detects onset locations and boosts "
             "the attack portion of each event by --sharpen-gain-db. This is "
             "the positive counterpart to crossfade smoothing: instead of "
             "softening edges, it emphasizes them — making onset detection "
             "more reliable for rhythm extraction."
    )
    parser.add_argument(
        "--sharpen-gain-db",
        type=float,
        default=6.0,
        help="How many dB to boost the attack portion of each detected onset "
             "when --sharpen-transients is enabled. (default: %(default)s)"
    )
    parser.add_argument(
        "--sharpen-attack-ms",
        type=float,
        default=15.0,
        help="Duration in milliseconds of the attack window to boost at each "
             "onset when --sharpen-transients is enabled. (default: %(default)s)"
    )

    # --- Utility / standardisation arguments ---
    parser.add_argument(
        "--pre-emphasis",
        type=float,
        default=0.0,
        help="Apply a pre-emphasis filter that boosts higher frequencies to "
             "compensate for natural high-frequency roll-off in field recordings "
             "(sound attenuates faster at high frequencies over distance). "
             "Value is the filter coefficient (0.0-1.0). 0.0 = disabled, "
             "0.97 = standard speech/bioacoustics value. (default: %(default)s)"
    )
    parser.add_argument(
        "--normalize",
        type=str,
        default=None,
        choices=["peak", "rms"],
        help="Normalize audio levels after all processing, just before saving. "
             "'peak' = scale so the loudest sample reaches --normalize-target-db. "
             "'rms' = scale so the RMS energy reaches --normalize-target-db. "
             "Ensures consistent volume across files from different equipment "
             "or distances. Critical for fair cross-species comparisons. "
             "(default: disabled)"
    )
    parser.add_argument(
        "--normalize-target-db",
        type=float,
        default=-1.0,
        help="Target level in dBFS for normalization. -1.0 leaves a little "
             "headroom below clipping. -3.0 is more conservative. "
             "Only used when --normalize is set. (default: %(default)s)"
    )
    parser.add_argument(
        "--trim-silence",
        action="store_true",
        default=False,
        help="Trim leading and trailing silence from the output file after "
             "all processing is complete. Internal timing (inter-onset "
             "intervals) is preserved — only dead time at the very start "
             "and end is removed. Reduces file size and speeds up downstream "
             "onset detection. (default: %(default)s)"
    )
    parser.add_argument(
        "--trim-threshold-db",
        type=float,
        default=40.0,
        help="dB threshold for --trim-silence. Audio below this level "
             "(relative to peak) at the edges is considered silence. "
             "(default: %(default)s)"
    )
    parser.add_argument(
        "--resample",
        type=int,
        default=0,
        metavar="HZ",
        help="Resample all output files to this sample rate (in Hz). Ensures "
             "consistent timing resolution across files from different "
             "recording equipment. Onset detection precision depends on "
             "sample rate (~0.023 ms at 44100 Hz). Set to 0 to keep the "
             "native rate. Recommended: 44100 or 22050. (default: %(default)s)"
    )
    parser.add_argument(
        "--channel",
        type=str,
        default="mix",
        choices=["mix", "left", "right"],
        help="For multi-channel (stereo) recordings, choose which channel(s) "
             "to use. 'mix' = average all channels to mono (default). "
             "'left' = use only the left channel. 'right' = use only the "
             "right channel. Useful when one mic/channel has less noise. "
             "(default: %(default)s)"
    )
    parser.add_argument(
        "--output-folder",
        type=str,
        default=None,
        help="Explicit output folder for cleaned audio. When set, overrides "
             "the default <input_folder>_muted_clean derivation. Sibling "
             "folders (_rejected_noise, _hpss_harmonic, _hpss_percussive) "
             "are still derived from this path."
    )
    return parser.parse_args()


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def apply_highpass(signal, sr, cutoff_hz):
    """Apply a 4th-order Butterworth high-pass filter to remove low-frequency rumble."""
    sos = butter(4, cutoff_hz, btype="high", fs=sr, output="sos")
    return sosfilt(sos, signal).astype(signal.dtype)


def apply_lowpass(signal, sr, cutoff_hz):
    """Apply a 4th-order Butterworth low-pass filter to remove high-frequency noise.

    Companion to the high-pass filter.  Useful for species whose signals are
    concentrated in low frequencies (elephants, whales) where high-frequency
    equipment hiss or ultrasonic interference should be discarded.
    """
    sos = butter(4, cutoff_hz, btype="low", fs=sr, output="sos")
    return sosfilt(sos, signal).astype(signal.dtype)


def apply_notch(signal, sr, freq_hz, quality=30.0):
    """Apply a narrow notch (band-reject) filter at a specific frequency.

    Surgically removes tonal interference at a known frequency — power-line
    hum (50/60 Hz), a specific insect call, equipment resonance — without
    affecting neighbouring frequencies.  More precise than broadband spectral
    denoising.

    Parameters
    ----------
    signal : np.ndarray
        Audio time-series.
    sr : int
        Sample rate.
    freq_hz : float
        Centre frequency of the notch in Hz.
    quality : float
        Quality factor (Q).  Higher = narrower notch.  30 is good for hum;
        10-15 for broader tonal interference.
    """
    b, a = iirnotch(freq_hz, quality, fs=sr)
    # sosfilt expects SOS format; use lfilter for the b/a coefficients
    from scipy.signal import lfilter
    return lfilter(b, a, signal).astype(signal.dtype)


def apply_pre_emphasis(signal, coeff=0.97):
    """Apply a first-order pre-emphasis filter to boost high frequencies.

    Compensates for the natural high-frequency roll-off that occurs when sound
    propagates over distance in the field.  Standard in speech and bioacoustics
    processing.  The output is ``y[n] = x[n] - coeff * x[n-1]``, which tilts
    the spectrum upward at ~6 dB/octave.

    Parameters
    ----------
    signal : np.ndarray
        Audio time-series.
    coeff : float
        Filter coefficient (0.0 = disabled, 0.97 = standard).
    """
    return np.append(signal[0], signal[1:] - coeff * signal[:-1]).astype(signal.dtype)


def apply_normalize(y, mode="peak", target_db=-1.0):
    """Normalize the amplitude of an audio signal.

    Ensures consistent volume levels across files recorded at different gains
    or distances.  Should be applied as the **last** processing step before
    saving, so all prior edits are captured.

    Parameters
    ----------
    y : np.ndarray
        Audio time-series.
    mode : str
        'peak' — scale so max |sample| = target_db.
        'rms'  — scale so RMS energy = target_db.
    target_db : float
        Target level in dBFS (e.g. -1.0 for near-full-scale with headroom).

    Returns
    -------
    y_norm : np.ndarray
        Normalized audio, same length as input.
    gain_db : float
        The gain that was applied, in dB (for diagnostics).
    """
    target_linear = 10.0 ** (target_db / 20.0)

    if mode == "peak":
        current = np.max(np.abs(y))
    else:  # rms
        current = float(np.sqrt(np.mean(y ** 2)))

    if current < 1e-10:
        return y.copy(), 0.0  # signal is silent — nothing to normalise

    gain = target_linear / current
    y_norm = y * gain

    # Clamp to prevent clipping (only possible with RMS mode where
    # individual peaks might exceed the target)
    peak = np.max(np.abs(y_norm))
    if peak > 1.0:
        y_norm /= peak

    gain_db = 20.0 * np.log10(max(gain, 1e-10))
    return y_norm.astype(y.dtype), float(gain_db)


def apply_trim_silence(y, top_db=40.0):
    """Trim leading and trailing silence from an audio signal.

    Uses ``librosa.effects.trim`` to remove dead time at the very start and
    end of the recording.  Internal timing is fully preserved — only the
    edges are clipped.  Useful for reducing file size and speeding up
    downstream onset detection.

    Parameters
    ----------
    y : np.ndarray
        Audio time-series.
    top_db : float
        Audio below this level (relative to peak) at the edges is considered
        silence and is trimmed.

    Returns
    -------
    y_trimmed : np.ndarray
        Trimmed audio.
    n_trimmed : int
        Total samples removed (start + end).
    """
    y_trimmed, index = librosa.effects.trim(y, top_db=top_db)
    n_trimmed = len(y) - len(y_trimmed)
    return y_trimmed, n_trimmed


def apply_spectral_denoise(y, sr, prop_decrease=1.5):
    """Remove stationary/persistent background noise using spectral gating.

    This targets sounds that are spectrally constant throughout the recording —
    cicada choruses, generator hum, tape hiss, wind — while preserving transient
    events like animal vocalizations or percussion hits.

    The algorithm (via the ``noisereduce`` library) works by:
    1. Computing the STFT of the full signal.
    2. Estimating the "stationary" noise profile as the median amplitude in each
       frequency bin across all time frames.
    3. Applying a soft spectral gate: frequency bins whose amplitude is close to
       the median profile are attenuated; bins that deviate significantly
       (i.e. transient events) are preserved.

    Parameters
    ----------
    y : np.ndarray
        Audio time-series.
    sr : int
        Sample rate.
    prop_decrease : float
        How much to attenuate the detected noise (0.0 = no change, 1.0 = full
        removal of stationary component, >1.0 = over-suppress). Default 1.5
        is moderately aggressive to handle loud persistent sources like cicadas.

    Returns
    -------
    y_denoised : np.ndarray
        The denoised audio, same length as input.
    """
    y_denoised = nr.reduce_noise(
        y=y,
        sr=sr,
        stationary=True,       # treat the noise as spectrally constant
        prop_decrease=min(prop_decrease, 1.0),  # clamp to [0, 1] for the API
        n_fft=2048,
        hop_length=512,
    )

    # If the user wants extra suppression beyond 1.0, apply a second pass
    # with residual-based (non-stationary) gating to catch what remains.
    if prop_decrease > 1.0:
        y_denoised = nr.reduce_noise(
            y=y_denoised,
            sr=sr,
            stationary=False,      # adaptive non-stationary gate
            prop_decrease=min(prop_decrease - 1.0, 1.0),
            n_fft=2048,
            hop_length=512,
        )

    return y_denoised.astype(y.dtype)


def apply_hpss(y, margin=2.0):
    """Decompose audio into harmonic and percussive components using HPSS.

    Harmonic-Percussive Source Separation uses median filtering on the
    spectrogram: horizontal medians capture smooth harmonic content (sustained
    tones like bird song, whale moans, wind), while vertical medians capture
    sharp percussive content (transients like primate drumming, insect clicks,
    human clapping).

    Both output arrays have exactly the same length as the input, preserving
    the global timeline.

    Parameters
    ----------
    y : np.ndarray
        Audio time-series.
    margin : float
        Separation softness. 1.0 = soft (components overlap), 2.0 = moderate
        (good default), 4.0+ = hard (cleaner but risks losing quiet signal).

    Returns
    -------
    y_harmonic : np.ndarray
        The harmonic (sustained-tone) component.
    y_percussive : np.ndarray
        The percussive (transient) component.
    """
    y_harmonic, y_percussive = librosa.effects.hpss(y, margin=margin)
    return y_harmonic.astype(y.dtype), y_percussive.astype(y.dtype)


def estimate_noise_floor(y, sr, frame_length=2048, hop_length=512):
    """Estimate the noise floor of an audio signal.

    Uses three complementary approaches and returns the median:
    1. RMS percentile — 10th percentile of per-frame RMS energy
    2. Frequency-band median — median energy across freq bands in the
       quietest 20% of frames (captures steady-state hiss/hum)
    3. Mode of low-energy frames — peak of the RMS histogram below the
       median, which targets the most common quiet level

    Returns
    -------
    noise_floor_db : float
        Estimated noise floor in dB (relative to full-scale).
    profile : dict
        Diagnostic info: per-band levels, RMS distribution, chosen values.
    """
    # --- Per-frame RMS ---
    rms = librosa.feature.rms(y=y, frame_length=frame_length,
                              hop_length=hop_length)[0]
    # Avoid log of zero
    rms_safe = np.maximum(rms, 1e-10)
    rms_db = 20.0 * np.log10(rms_safe)

    # 1. RMS percentile approach
    noise_pct_db = float(np.percentile(rms_db, 10))

    # 2. Spectral band median on the quietest frames
    quiet_mask = rms_db <= np.percentile(rms_db, 20)
    S = np.abs(librosa.stft(y, n_fft=frame_length, hop_length=hop_length))
    S_db = librosa.amplitude_to_db(S, ref=np.max)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=frame_length)

    band_edges = [0, 250, 1000, 4000, sr / 2]
    band_names = ["0-250", "250-1k", "1k-4k", "4k+"]
    band_levels = {}
    for i in range(len(band_edges) - 1):
        mask = (freqs >= band_edges[i]) & (freqs < band_edges[i + 1])
        if mask.any() and quiet_mask.any():
            band_levels[band_names[i]] = float(
                np.median(S_db[mask][:, quiet_mask]))
        else:
            band_levels[band_names[i]] = -80.0
    spectral_floor_db = float(np.median(list(band_levels.values())))

    # 3. Mode of low-energy frames (histogram peak below median)
    median_rms_db = float(np.median(rms_db))
    low_frames = rms_db[rms_db <= median_rms_db]
    if len(low_frames) > 10:
        counts, bin_edges = np.histogram(low_frames, bins=50)
        mode_idx = np.argmax(counts)
        mode_db = float((bin_edges[mode_idx] + bin_edges[mode_idx + 1]) / 2.0)
    else:
        mode_db = noise_pct_db

    # Combine: median of the three estimates for robustness
    noise_floor_db = float(np.median([noise_pct_db, spectral_floor_db, mode_db]))

    peak_db = float(np.max(rms_db))

    profile = {
        "noise_floor_db": round(noise_floor_db, 2),
        "peak_db": round(peak_db, 2),
        "dynamic_range_db": round(peak_db - noise_floor_db, 2),
        "rms_percentile_10_db": round(noise_pct_db, 2),
        "spectral_floor_db": round(spectral_floor_db, 2),
        "mode_low_energy_db": round(mode_db, 2),
        "band_levels_db": {k: round(v, 2) for k, v in band_levels.items()},
        "total_frames": int(len(rms)),
        "quiet_frames_pct": round(100.0 * quiet_mask.sum() / len(rms), 1),
    }
    return noise_floor_db, profile


def compute_adaptive_top_db(noise_floor_db, peak_db, margin_db=6.0,
                            min_top_db=10.0, max_top_db=60.0):
    """Derive an adaptive top_db value from the noise floor estimate.

    The threshold is set so that anything within `margin_db` of the noise floor
    is treated as noise.  The result is clamped to [min_top_db, max_top_db].

    Parameters
    ----------
    noise_floor_db : float
        Estimated noise floor in dB (full-scale, typically negative).
    peak_db : float
        Peak RMS level in dB.
    margin_db : float
        dB above the noise floor that still counts as "noise".
    min_top_db, max_top_db : float
        Clamp range to avoid pathological thresholds.

    Returns
    -------
    top_db : float
        The value to pass to `librosa.effects.split(top_db=...)`.
    """
    # top_db is measured downward from the peak, so:
    # mute threshold (dBFS) = peak_db - top_db
    # We want: mute threshold = noise_floor_db + margin_db
    # Therefore: top_db = peak_db - (noise_floor_db + margin_db)
    top_db = peak_db - (noise_floor_db + margin_db)
    return float(np.clip(top_db, min_top_db, max_top_db))


# ==========================================
# 2b. ENHANCEMENT / AMPLIFICATION HELPERS
# ==========================================
def apply_bandpass_boost(signal, sr, low_hz, high_hz, gain_db):
    """Boost a specific frequency band by *gain_db* decibels.

    This is the positive counterpart to the high-pass filter: instead of
    *cutting* unwanted frequencies, it *amplifies* a target frequency range
    so that species-specific calls become more prominent.  The rest of the
    spectrum is left untouched.

    Implementation: a 4th-order Butterworth bandpass filter isolates the
    target band, then (gain − 1)× that isolated band is added back to the
    original signal, achieving a net boost of *gain_db* in that band only.

    Parameters
    ----------
    signal : np.ndarray
        Audio time-series.
    sr : int
        Sample rate.
    low_hz, high_hz : int
        Lower and upper edges of the frequency band to boost.
    gain_db : float
        How many dB to amplify the band.

    Returns
    -------
    boosted : np.ndarray
        Signal with the target band amplified.  Peak-normalised to ±1.0
        if clipping would otherwise occur.
    """
    sos = butter(4, [low_hz, high_hz], btype="band", fs=sr, output="sos")
    band_signal = sosfilt(sos, signal)
    gain_linear = 10.0 ** (gain_db / 20.0)
    boosted = signal + band_signal * (gain_linear - 1.0)
    # Prevent clipping
    peak = np.max(np.abs(boosted))
    if peak > 1.0:
        boosted /= peak
    return boosted.astype(signal.dtype)


def apply_spectral_enhance(y, sr, enhance_factor=2.0):
    """Amplify spectral peaks that deviate from the stationary background.

    This is the positive counterpart to spectral denoising: instead of
    *suppressing* the background, it *lifts* transient events (vocalizations,
    percussion) that stand out from the median spectral profile.

    Implementation:
    1. Compute the STFT magnitude and phase.
    2. Estimate the background as the median magnitude in each frequency bin.
    3. Compute the "excess" = how far each time-frequency cell exceeds the
       background.
    4. Add (enhance_factor − 1) × excess back to the magnitude.
    5. Reconstruct via inverse STFT.

    Parameters
    ----------
    y : np.ndarray
        Audio time-series.
    sr : int
        Sample rate (unused but kept for API consistency).
    enhance_factor : float
        The multiplier for spectral peaks above the background.
        1.0 = no change, 2.0 = doubles the deviation (default),
        4.0 = aggressive enhancement.

    Returns
    -------
    y_enhanced : np.ndarray
        Enhanced audio, same length as input.  Peak-normalised to ±1.0
        if clipping would otherwise occur.
    """
    n_fft = 2048
    hop_length = 512
    S = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)
    mag = np.abs(S)
    phase = np.angle(S)

    # Background estimate: median magnitude per frequency bin
    median_spectrum = np.median(mag, axis=1, keepdims=True)

    # How much each cell exceeds the background (clamp to ≥0)
    excess = np.maximum(mag - median_spectrum, 0.0)

    # Boost the excess
    mag_enhanced = mag + excess * (enhance_factor - 1.0)

    # Reconstruct
    S_enhanced = mag_enhanced * np.exp(1j * phase)
    y_enhanced = librosa.istft(S_enhanced, hop_length=hop_length, length=len(y))

    # Prevent clipping
    peak = np.max(np.abs(y_enhanced))
    if peak > 1.0:
        y_enhanced /= peak
    return y_enhanced.astype(y.dtype)


def apply_dynamic_compression(y, sr, threshold_db=-30.0, ratio=3.0,
                              frame_length=2048, hop_length=512):
    """Apply upward dynamic range compression to boost quiet audio.

    This is the positive counterpart to dB-based muting: instead of
    *silencing* audio below a threshold, it *amplifies* it toward the
    threshold — making distant or quiet vocalisations more audible while
    leaving loud events at their original level.

    Implementation: per-frame RMS is computed; frames below *threshold_db*
    receive a gain that reduces their distance below the threshold by the
    compression *ratio*.  Gain is interpolated to sample-level for smooth
    transitions.

    Parameters
    ----------
    y : np.ndarray
        Audio time-series.
    sr : int
        Sample rate.
    threshold_db : float
        dBFS level below which upward gain is applied (default −30).
    ratio : float
        Compression ratio.  Higher = more gain for quiet audio.
        2.0 = gentle, 3.0 = moderate, 6.0+ = heavy.
    frame_length, hop_length : int
        STFT parameters for RMS calculation.

    Returns
    -------
    y_compressed : np.ndarray
        Compressed audio, same length as input.  Peak-normalised to ±1.0
        if clipping would otherwise occur.
    """
    rms = librosa.feature.rms(y=y, frame_length=frame_length,
                              hop_length=hop_length)[0]
    rms_db = 20.0 * np.log10(np.maximum(rms, 1e-10))

    # Compute per-frame gain: boost only frames below the threshold
    gain_db = np.zeros_like(rms_db)
    below = rms_db < threshold_db
    # Upward compression: reduce the distance below threshold by the ratio
    gain_db[below] = (threshold_db - rms_db[below]) * (1.0 - 1.0 / ratio)

    gain_linear = 10.0 ** (gain_db / 20.0)

    # Interpolate gain to sample-level for smooth application
    frame_centres = np.arange(len(gain_linear)) * hop_length
    gain_samples = np.interp(np.arange(len(y)), frame_centres, gain_linear)

    y_compressed = y * gain_samples

    # Prevent clipping
    peak = np.max(np.abs(y_compressed))
    if peak > 1.0:
        y_compressed /= peak
    return y_compressed.astype(y.dtype)


def apply_transient_sharpening(y, sr, attack_ms=15.0, gain_db=6.0):
    """Boost the attack portion of detected onsets to emphasise transients.

    This is the positive counterpart to crossfade smoothing: instead of
    *softening* the silence→signal boundary, it *sharpens* it — making
    each onset more prominent and easier for the downstream onset finder
    to detect.

    Implementation: ``librosa.onset.onset_detect`` locates onset frames;
    for each onset a short gain envelope (decaying from *gain_db* to 0)
    is applied over *attack_ms* milliseconds.

    Parameters
    ----------
    y : np.ndarray
        Audio time-series.
    sr : int
        Sample rate.
    attack_ms : float
        Duration of the attack boost window in milliseconds (default 15).
    gain_db : float
        Peak gain at the onset in dB (default 6).

    Returns
    -------
    y_sharpened : np.ndarray
        Audio with boosted transients, same length as input.
        Peak-normalised to ±1.0 if clipping would otherwise occur.
    """
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, hop_length=512,
                                              backtrack=True)
    onset_samples = librosa.frames_to_samples(onset_frames, hop_length=512)

    attack_samples = int(sr * attack_ms / 1000.0)
    gain_linear = 10.0 ** (gain_db / 20.0)

    # Build a gain envelope: starts at 1.0 everywhere, with short gain
    # bumps at each detected onset
    gain_envelope = np.ones(len(y), dtype=np.float64)

    for onset in onset_samples:
        end = min(onset + attack_samples, len(y))
        n = end - onset
        if n > 0:
            # Envelope for this onset: decays from full gain to 1.0
            attack_env = np.linspace(gain_linear, 1.0, n)
            gain_envelope[onset:end] = np.maximum(gain_envelope[onset:end],
                                                  attack_env)

    y_sharpened = y * gain_envelope

    # Prevent clipping
    peak = np.max(np.abs(y_sharpened))
    if peak > 1.0:
        y_sharpened /= peak
    return y_sharpened.astype(y.dtype)


# ==========================================
# 2g. REUSABLE PROCESSING PIPELINE
# ==========================================
def process_signal(y, sr, cfg):
    """Apply the full Audio Editor processing chain to a mono signal.

    Parameters
    ----------
    y : np.ndarray (float32, 1-D)
        Mono audio signal.
    sr : int
        Sample rate in Hz.
    cfg : dict
        Configuration dict with the same ``MUTER_*`` keys that
        ``MuterPanel.get_values()`` produces.  Missing keys fall back to
        safe defaults so callers only need to supply what they care about.
        An optional ``MUTER_PROC_ORDER`` list of ints (0–10) controls the
        order in which processing groups are applied.  The default order
        is [0, 1, 2, …, 10].

    Returns
    -------
    y_clean : np.ndarray (float32, 1-D)
        The processed (muted + effects) signal.
    """
    # Unpack with safe defaults
    highpass_hz       = int(cfg.get("MUTER_HIGHPASS_HZ", 0))
    lowpass_hz        = int(cfg.get("MUTER_LOWPASS_HZ", 0))
    notch_freqs       = cfg.get("MUTER_NOTCH_FREQS") or []
    notch_q           = float(cfg.get("MUTER_NOTCH_Q", 30.0))
    pre_emphasis_coeff = float(cfg.get("MUTER_PRE_EMPHASIS", 0.0))
    bandpass_boost    = bool(cfg.get("MUTER_BANDPASS_BOOST", False))
    boost_low_hz      = int(cfg.get("MUTER_BOOST_LOW_HZ", 300))
    boost_high_hz     = int(cfg.get("MUTER_BOOST_HIGH_HZ", 3000))
    boost_gain_db     = float(cfg.get("MUTER_BOOST_GAIN_DB", 6.0))
    hpss_enabled      = bool(cfg.get("MUTER_HPSS_ENABLED", False))
    hpss_target       = str(cfg.get("MUTER_HPSS_TARGET", "percussive"))
    hpss_margin       = float(cfg.get("MUTER_HPSS_MARGIN", 2.0))
    hpss_emphasis_db  = float(cfg.get("MUTER_HPSS_EMPHASIS_DB", 0.0))
    spectral_denoise  = bool(cfg.get("MUTER_SPECTRAL_DENOISE", False))
    denoise_strength  = float(cfg.get("MUTER_DENOISE_STRENGTH", 1.5))
    spectral_enhance  = bool(cfg.get("MUTER_SPECTRAL_ENHANCE", False))
    enhance_factor_v  = float(cfg.get("MUTER_ENHANCE_FACTOR", 2.0))
    compress          = bool(cfg.get("MUTER_COMPRESS", False))
    compress_ratio    = float(cfg.get("MUTER_COMPRESS_RATIO", 3.0))
    compress_thresh   = float(cfg.get("MUTER_COMPRESS_THRESHOLD_DB", -30.0))
    sharpen           = bool(cfg.get("MUTER_SHARPEN_TRANSIENTS", False))
    sharpen_gain      = float(cfg.get("MUTER_SHARPEN_GAIN_DB", 6.0))
    sharpen_attack    = float(cfg.get("MUTER_SHARPEN_ATTACK_MS", 15.0))
    auto_threshold    = bool(cfg.get("MUTER_AUTO_THRESHOLD", True))
    db_threshold      = int(cfg.get("MUTER_DB_THRESHOLD", 30))
    noise_margin_db   = float(cfg.get("MUTER_NOISE_MARGIN_DB", 6.0))
    fade_ms           = float(cfg.get("MUTER_FADE_MS", 5.0))
    normalize_mode    = cfg.get("MUTER_NORMALIZE")  # None, "peak", or "rms"
    normalize_tgt_db  = float(cfg.get("MUTER_NORMALIZE_TARGET_DB", -1.0))
    trim_silence_on   = bool(cfg.get("MUTER_TRIM_SILENCE", False))
    trim_threshold_db = float(cfg.get("MUTER_TRIM_THRESHOLD_DB", 40.0))
    mfcc_enabled        = bool(cfg.get("MUTER_MFCC_ENABLED", False))
    mfcc_template_paths = cfg.get("MUTER_MFCC_TEMPLATE_PATHS") or []
    mfcc_threshold_pct  = float(cfg.get("MUTER_MFCC_THRESHOLD_PERCENTILE", 15.0))
    mfcc_smooth_ms      = float(cfg.get("MUTER_MFCC_SMOOTH_MS", 50.0))
    mfcc_n_mfcc         = int(cfg.get("MUTER_MFCC_N_MFCC", 13))

    # Processing step order (GUI groups 0–11)
    proc_order = cfg.get("MUTER_PROC_ORDER", list(range(12)))

    sig = y.astype(np.float32)

    for step_idx in proc_order:
        # 0 — Channel & Resampling (handled in process_file, not here)
        if step_idx == 0:
            continue

        # 1 — Frequency Filters
        elif step_idx == 1:
            if highpass_hz > 0:
                sig = apply_highpass(sig, sr, highpass_hz)
            if lowpass_hz > 0:
                sig = apply_lowpass(sig, sr, lowpass_hz)
            if notch_freqs:
                for nf in notch_freqs:
                    sig = apply_notch(sig, sr, nf, quality=notch_q)
            if pre_emphasis_coeff > 0:
                sig = apply_pre_emphasis(sig, coeff=pre_emphasis_coeff)

        # 2 — Bandpass Boost
        elif step_idx == 2:
            if bandpass_boost:
                sig = apply_bandpass_boost(sig, sr, boost_low_hz,
                                          boost_high_hz, boost_gain_db)

        # 3 — HPSS
        elif step_idx == 3:
            if hpss_enabled:
                y_h, y_p = apply_hpss(sig, margin=hpss_margin)
                if hpss_emphasis_db > 0:
                    gain = 10.0 ** (hpss_emphasis_db / 20.0)
                    if hpss_target == "harmonic":
                        sig = y_h * gain + y_p
                    elif hpss_target == "percussive":
                        sig = y_h + y_p * gain
                    else:
                        sig = y_h * gain + y_p * gain
                    peak = np.max(np.abs(sig))
                    if peak > 1.0:
                        sig /= peak
                elif hpss_target == "harmonic":
                    sig = y_h
                elif hpss_target == "percussive":
                    sig = y_p

        # 4 — Spectral Denoising
        elif step_idx == 4:
            if spectral_denoise:
                sig = apply_spectral_denoise(sig, sr,
                                             prop_decrease=denoise_strength)

        # 5 — Spectral Enhancement
        elif step_idx == 5:
            if spectral_enhance:
                sig = apply_spectral_enhance(sig, sr,
                                             enhance_factor=enhance_factor_v)

        # 6 — Dynamic Compression
        elif step_idx == 6:
            if compress:
                sig = apply_dynamic_compression(sig, sr,
                                                threshold_db=compress_thresh,
                                                ratio=compress_ratio)

        # 7 — Transient Sharpening
        elif step_idx == 7:
            if sharpen:
                sig = apply_transient_sharpening(sig, sr,
                                                 attack_ms=sharpen_attack,
                                                 gain_db=sharpen_gain)

        # 8 — Amplitude Muting (+ Crossfade from group 9)
        elif step_idx == 8:
            if auto_threshold:
                noise_floor_db, noise_profile = estimate_noise_floor(sig, sr)
                peak_db = noise_profile["peak_db"]
                file_top_db = compute_adaptive_top_db(
                    noise_floor_db, peak_db, margin_db=noise_margin_db)
            else:
                file_top_db = db_threshold

            intervals = librosa.effects.split(sig, top_db=file_top_db)
            y_clean = np.zeros_like(sig)
            fade_samples = (int(sr * fade_ms / 1000.0)
                            if fade_ms > 0 else 0)

            for start, end in intervals:
                y_clean[start:end] = sig[start:end]
                if fade_samples > 0:
                    seg_len = end - start
                    if seg_len <= 2 * fade_samples:
                        half = seg_len // 2
                        if half > 0:
                            y_clean[start:start + half] *= np.linspace(
                                0, 1, half)
                            y_clean[start + half:end] *= np.linspace(
                                1, 0, seg_len - half)
                    else:
                        y_clean[start:start + fade_samples] *= np.linspace(
                            0, 1, fade_samples)
                        y_clean[end - fade_samples:end] *= np.linspace(
                            1, 0, fade_samples)
            sig = y_clean

        # 9 — Crossfade (handled together with Amplitude Muting above)
        elif step_idx == 9:
            continue

        # 10 — Normalization & Trimming
        elif step_idx == 10:
            if normalize_mode:
                sig, _ = apply_normalize(sig, mode=normalize_mode,
                                         target_db=normalize_tgt_db)
            if trim_silence_on:
                sig, _ = apply_trim_silence(sig, top_db=trim_threshold_db)

        # 11 — MFCC Template Matching
        elif step_idx == 11:
            if mfcc_enabled and mfcc_template_paths:
                import sys as _sys
                _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if _project_root not in _sys.path:
                    _sys.path.insert(0, _project_root)
                from analysis.mfcc_template import clean_audio_with_mfcc_template
                import librosa as _librosa
                templates = []
                for tpath in mfcc_template_paths:
                    if os.path.isfile(tpath):
                        y_t, _ = _librosa.load(tpath, sr=sr, mono=True)
                        templates.append(y_t.astype(np.float32))
                if templates:
                    sig = clean_audio_with_mfcc_template(
                        sig, sr, templates,
                        threshold_percentile=mfcc_threshold_pct,
                        smooth_ms=mfcc_smooth_ms,
                        n_mfcc=mfcc_n_mfcc,
                    )

    return sig


def process_signal_full(y, sr, cfg):
    """Like process_signal but returns a dict of all track variants.

    Returns
    -------
    dict
        Keys: ``"muted_clean"``, ``"hpss_harmonic"`` (or None),
        ``"hpss_percussive"`` (or None), ``"rejected_noise"``.
    """
    # Unpack with safe defaults
    highpass_hz       = int(cfg.get("MUTER_HIGHPASS_HZ", 0))
    lowpass_hz        = int(cfg.get("MUTER_LOWPASS_HZ", 0))
    notch_freqs       = cfg.get("MUTER_NOTCH_FREQS") or []
    notch_q           = float(cfg.get("MUTER_NOTCH_Q", 30.0))
    pre_emphasis_coeff = float(cfg.get("MUTER_PRE_EMPHASIS", 0.0))
    bandpass_boost    = bool(cfg.get("MUTER_BANDPASS_BOOST", False))
    boost_low_hz      = int(cfg.get("MUTER_BOOST_LOW_HZ", 300))
    boost_high_hz     = int(cfg.get("MUTER_BOOST_HIGH_HZ", 3000))
    boost_gain_db     = float(cfg.get("MUTER_BOOST_GAIN_DB", 6.0))
    hpss_enabled      = bool(cfg.get("MUTER_HPSS_ENABLED", False))
    hpss_target       = str(cfg.get("MUTER_HPSS_TARGET", "percussive"))
    hpss_margin       = float(cfg.get("MUTER_HPSS_MARGIN", 2.0))
    hpss_emphasis_db  = float(cfg.get("MUTER_HPSS_EMPHASIS_DB", 0.0))
    spectral_denoise  = bool(cfg.get("MUTER_SPECTRAL_DENOISE", False))
    denoise_strength  = float(cfg.get("MUTER_DENOISE_STRENGTH", 1.5))
    spectral_enhance  = bool(cfg.get("MUTER_SPECTRAL_ENHANCE", False))
    enhance_factor_v  = float(cfg.get("MUTER_ENHANCE_FACTOR", 2.0))
    compress          = bool(cfg.get("MUTER_COMPRESS", False))
    compress_ratio    = float(cfg.get("MUTER_COMPRESS_RATIO", 3.0))
    compress_thresh   = float(cfg.get("MUTER_COMPRESS_THRESHOLD_DB", -30.0))
    sharpen           = bool(cfg.get("MUTER_SHARPEN_TRANSIENTS", False))
    sharpen_gain      = float(cfg.get("MUTER_SHARPEN_GAIN_DB", 6.0))
    sharpen_attack    = float(cfg.get("MUTER_SHARPEN_ATTACK_MS", 15.0))
    auto_threshold    = bool(cfg.get("MUTER_AUTO_THRESHOLD", True))
    db_threshold      = int(cfg.get("MUTER_DB_THRESHOLD", 30))
    noise_margin_db   = float(cfg.get("MUTER_NOISE_MARGIN_DB", 6.0))
    fade_ms           = float(cfg.get("MUTER_FADE_MS", 5.0))
    normalize_mode    = cfg.get("MUTER_NORMALIZE")
    normalize_tgt_db  = float(cfg.get("MUTER_NORMALIZE_TARGET_DB", -1.0))
    trim_silence_on   = bool(cfg.get("MUTER_TRIM_SILENCE", False))
    trim_threshold_db = float(cfg.get("MUTER_TRIM_THRESHOLD_DB", 40.0))
    mfcc_enabled        = bool(cfg.get("MUTER_MFCC_ENABLED", False))
    mfcc_template_paths = cfg.get("MUTER_MFCC_TEMPLATE_PATHS") or []
    mfcc_threshold_pct  = float(cfg.get("MUTER_MFCC_THRESHOLD_PERCENTILE", 15.0))
    mfcc_smooth_ms      = float(cfg.get("MUTER_MFCC_SMOOTH_MS", 50.0))
    mfcc_n_mfcc         = int(cfg.get("MUTER_MFCC_N_MFCC", 13))

    y_input = y.astype(np.float32)
    y = y_input.copy()

    y_h_out = None
    y_p_out = None

    # Filters
    if highpass_hz > 0:
        y = apply_highpass(y, sr, highpass_hz)
    if lowpass_hz > 0:
        y = apply_lowpass(y, sr, lowpass_hz)
    if notch_freqs:
        for nf in notch_freqs:
            y = apply_notch(y, sr, nf, quality=notch_q)
    if pre_emphasis_coeff > 0:
        y = apply_pre_emphasis(y, coeff=pre_emphasis_coeff)
    if bandpass_boost:
        y = apply_bandpass_boost(y, sr, boost_low_hz, boost_high_hz, boost_gain_db)

    # HPSS — capture components
    if hpss_enabled:
        y_h, y_p = apply_hpss(y, margin=hpss_margin)
        y_h_out = y_h.copy()
        y_p_out = y_p.copy()
        if hpss_emphasis_db > 0:
            gain = 10.0 ** (hpss_emphasis_db / 20.0)
            if hpss_target == "harmonic":
                y = y_h * gain + y_p
            elif hpss_target == "percussive":
                y = y_h + y_p * gain
            else:
                y = y_h * gain + y_p * gain
            peak = np.max(np.abs(y))
            if peak > 1.0:
                y /= peak
        elif hpss_target == "harmonic":
            y = y_h
        elif hpss_target == "percussive":
            y = y_p

    # Spectral + dynamics
    if spectral_denoise:
        y = apply_spectral_denoise(y, sr, prop_decrease=denoise_strength)
    if spectral_enhance:
        y = apply_spectral_enhance(y, sr, enhance_factor=enhance_factor_v)
    if compress:
        y = apply_dynamic_compression(y, sr, threshold_db=compress_thresh,
                                      ratio=compress_ratio)
    if sharpen:
        y = apply_transient_sharpening(y, sr, attack_ms=sharpen_attack,
                                       gain_db=sharpen_gain)

    # Threshold + muting
    if auto_threshold:
        noise_floor_db, noise_profile = estimate_noise_floor(y, sr)
        peak_db = noise_profile["peak_db"]
        file_top_db = compute_adaptive_top_db(noise_floor_db, peak_db,
                                              margin_db=noise_margin_db)
    else:
        file_top_db = db_threshold

    intervals = librosa.effects.split(y, top_db=file_top_db)
    y_clean = np.zeros_like(y)
    fade_samples = int(sr * fade_ms / 1000.0) if fade_ms > 0 else 0

    for start, end in intervals:
        y_clean[start:end] = y[start:end]
        if fade_samples > 0:
            seg_len = end - start
            if seg_len <= 2 * fade_samples:
                half = seg_len // 2
                if half > 0:
                    y_clean[start:start + half] *= np.linspace(0, 1, half)
                    y_clean[start + half:end] *= np.linspace(1, 0, seg_len - half)
            else:
                y_clean[start:start + fade_samples] *= np.linspace(0, 1, fade_samples)
                y_clean[end - fade_samples:end] *= np.linspace(1, 0, fade_samples)

    if normalize_mode:
        y_clean, _ = apply_normalize(y_clean, mode=normalize_mode,
                                     target_db=normalize_tgt_db)
    if trim_silence_on:
        y_clean, _ = apply_trim_silence(y_clean, top_db=trim_threshold_db)

    # MFCC Template Matching (step 11)
    if mfcc_enabled and mfcc_template_paths:
        import sys as _sys
        _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _project_root not in _sys.path:
            _sys.path.insert(0, _project_root)
        from analysis.mfcc_template import clean_audio_with_mfcc_template
        import librosa as _librosa
        templates = []
        for tpath in mfcc_template_paths:
            if os.path.isfile(tpath):
                y_t, _ = _librosa.load(tpath, sr=sr, mono=True)
                templates.append(y_t.astype(np.float32))
        if templates:
            y_clean = clean_audio_with_mfcc_template(
                y_clean, sr, templates,
                threshold_percentile=mfcc_threshold_pct,
                smooth_ms=mfcc_smooth_ms,
                n_mfcc=mfcc_n_mfcc,
            )

    # Rejected noise = original input minus the clean output
    # (pad/trim to match lengths after possible trim-silence)
    min_len = min(len(y_input), len(y_clean))
    y_rejected = y_input[:min_len] - y_clean[:min_len]

    return {
        "muted_clean":     y_clean,
        "hpss_harmonic":   y_h_out,
        "hpss_percussive": y_p_out,
        "rejected_noise":  y_rejected,
    }


def process_folder_with_per_file_settings(
    input_folder, per_file_settings, output_folder=None, selected_filenames=None):
    """Process each audio file in *input_folder* with its own settings dict.

    Parameters
    ----------
    input_folder : str
        Path to the folder containing audio files.
    per_file_settings : dict[str, dict]
        Mapping of ``filename → {MUTER_* settings dict}``.
        Files not in this dict are skipped.
    output_folder : str, optional
        Where to write cleaned audio.  Defaults to
        ``<input_folder>_AudioEdited``.
    selected_filenames : list[str], optional
        Optional allowlist of filenames to process. Files outside this list
        are skipped even if present in *per_file_settings*.

    Returns
    -------
    int
        Number of files successfully processed.
    """
    import librosa
    import soundfile as sf

    if output_folder is None:
        output_folder = input_folder.rstrip(os.sep) + "_AudioEdited"
    os.makedirs(output_folder, exist_ok=True)

    requested = list(dict.fromkeys(selected_filenames or []))
    if requested:
        requested_set = set(requested)
        missing = [name for name in requested
                   if not os.path.isfile(os.path.join(input_folder, name))]
        for name in missing:
            print(f"  [skip] {name}: file not found")
        filenames = sorted(
            name for name in per_file_settings
            if name in requested_set)
    else:
        filenames = sorted(per_file_settings)

    processed = 0
    for filename in filenames:
        cfg = per_file_settings[filename]
        filepath = os.path.join(input_folder, filename)
        if not os.path.isfile(filepath):
            print(f"  [skip] {filename}: file not found")
            continue
        try:
            sr_target = int(cfg.get("MUTER_RESAMPLE_SR", 0)) or None
            y, sr = librosa.load(filepath, sr=sr_target, mono=True)
            y_clean = process_signal(y, sr, cfg)
            out_path = os.path.join(output_folder, filename)
            sf.write(out_path, y_clean, sr)
            print(f"  [ok] {filename}")
            processed += 1
        except Exception as e:
            print(f"  [err] {filename}: {e}")
    return processed


# ==========================================
# 3. MAIN PROCESSING
# ==========================================
def main():
    args = parse_arguments()

    input_folder = args.input_folder
    db_threshold = args.db_threshold
    highpass_hz = args.highpass
    fade_ms = args.fade_ms
    auto_threshold = args.auto_threshold
    noise_margin_db = args.noise_margin_db
    save_noise_profile = args.save_noise_profile
    spectral_denoise = args.spectral_denoise
    denoise_strength = args.denoise_strength
    hpss_enabled = args.hpss
    hpss_target = args.hpss_target
    hpss_margin = args.hpss_margin
    hpss_emphasis_db = args.hpss_emphasis_db
    bandpass_boost = args.bandpass_boost
    boost_low_hz = args.boost_low_hz
    boost_high_hz = args.boost_high_hz
    boost_gain_db = args.boost_gain_db
    spectral_enhance = args.spectral_enhance
    enhance_factor = args.enhance_factor
    compress = args.compress
    compress_ratio = args.compress_ratio
    compress_threshold_db = args.compress_threshold_db
    sharpen_transients = args.sharpen_transients
    sharpen_gain_db = args.sharpen_gain_db
    sharpen_attack_ms = args.sharpen_attack_ms
    pre_emphasis_coeff = args.pre_emphasis
    normalize_mode = args.normalize
    normalize_target_db = args.normalize_target_db
    trim_silence = args.trim_silence
    trim_threshold_db = args.trim_threshold_db
    resample_hz = args.resample
    channel = args.channel
    lowpass_hz = args.lowpass
    notch_freqs = args.notch
    notch_q = args.notch_q
    selected_filenames = list(dict.fromkeys(args.files or []))

    # Output folders: use explicit --output-folder if given, else auto-derive
    if args.output_folder:
        clean_output_folder = args.output_folder.rstrip("/\\")
    else:
        clean_output_folder = input_folder.rstrip("/\\") + "_muted_clean"

    # Sibling folders derived from the clean output folder base
    _base = clean_output_folder.replace("_muted_clean", "") if clean_output_folder.endswith("_muted_clean") else clean_output_folder
    audit_output_folder = _base + "_rejected_noise"

    # HPSS component folders sit alongside the clean/rejected folders
    hpss_harmonic_folder = _base + "_hpss_harmonic"
    hpss_percussive_folder = _base + "_hpss_percussive"

    # --- Validate input folder ---
    if not os.path.isdir(input_folder):
        print(f"ERROR: Input folder does not exist: {input_folder}")
        sys.exit(1)

    folders_to_create = [clean_output_folder, audit_output_folder]
    if hpss_enabled:
        folders_to_create.extend([hpss_harmonic_folder, hpss_percussive_folder])
    for folder in folders_to_create:
        if not os.path.exists(folder):
            os.makedirs(folder)

    # --- Print run configuration ---
    print(f"Input folder:   {input_folder}")
    print(f"Clean output:   {clean_output_folder}")
    print(f"Audit output:   {audit_output_folder}")
    if hpss_enabled:
        if hpss_emphasis_db > 0:
            print(f"HPSS:           EMPHASIS mode (target={hpss_target}, "
                  f"boost={hpss_emphasis_db} dB, margin={hpss_margin})")
        else:
            print(f"HPSS:           ISOLATE mode (target={hpss_target}, margin={hpss_margin})")
        print(f"  Harmonic →    {hpss_harmonic_folder}")
        print(f"  Percussive →  {hpss_percussive_folder}")
    else:
        print(f"HPSS:           Off")
    if auto_threshold:
        print(f"Threshold:      ADAPTIVE (margin {noise_margin_db} dB above noise floor)")
        print(f"                Fixed --db-threshold ({db_threshold}) used as fallback")
    else:
        print(f"dB threshold:   {db_threshold}")
    print(f"High-pass:      {highpass_hz} Hz" if highpass_hz > 0 else "High-pass:      Off")
    print(f"Low-pass:       {lowpass_hz} Hz" if lowpass_hz > 0 else "Low-pass:       Off")
    if notch_freqs:
        print(f"Notch filter:   {', '.join(str(f) for f in notch_freqs)} Hz (Q={notch_q})")
    else:
        print(f"Notch filter:   Off")
    if pre_emphasis_coeff > 0:
        print(f"Pre-emphasis:   ON (coeff {pre_emphasis_coeff})")
    else:
        print(f"Pre-emphasis:   Off")
    print(f"Crossfade:      {fade_ms} ms")
    if spectral_denoise:
        print(f"Spectral denoise: ON (strength {denoise_strength})")
    else:
        print(f"Spectral denoise: Off")
    if save_noise_profile:
        print(f"Noise profiles: Will be saved alongside clean output")
    # --- Enhancement features ---
    if bandpass_boost:
        print(f"Bandpass boost: ON ({boost_low_hz}-{boost_high_hz} Hz, +{boost_gain_db} dB)")
    else:
        print(f"Bandpass boost: Off")
    if spectral_enhance:
        print(f"Spectral enhance: ON (factor {enhance_factor})")
    else:
        print(f"Spectral enhance: Off")
    if compress:
        print(f"Compression:    ON (ratio {compress_ratio}, threshold {compress_threshold_db} dBFS)")
    else:
        print(f"Compression:    Off")
    if sharpen_transients:
        print(f"Transient sharp: ON (+{sharpen_gain_db} dB, attack {sharpen_attack_ms} ms)")
    else:
        print(f"Transient sharp: Off")
    # --- Utility / standardisation features ---
    if normalize_mode:
        print(f"Normalize:      {normalize_mode.upper()} to {normalize_target_db} dBFS")
    else:
        print(f"Normalize:      Off")
    if trim_silence:
        print(f"Trim silence:   ON (threshold {trim_threshold_db} dB)")
    else:
        print(f"Trim silence:   Off")
    if resample_hz > 0:
        print(f"Resample:       {resample_hz} Hz")
    else:
        print(f"Resample:       Off (keep native rate)")
    print(f"Channel:        {channel}")
    print()

    valid_extensions = (".wav", ".mp3", ".flac", ".ogg")
    processed_count = 0
    warning_count = 0

    requested_set = set(selected_filenames) if selected_filenames else None
    available_files = [
        filename for filename in sorted(os.listdir(input_folder))
        if filename.lower().endswith(valid_extensions)
    ]
    if requested_set is not None:
        missing = [name for name in selected_filenames if name not in available_files]
        for name in missing:
            print(f"WARNING: Requested file not found or unsupported: {name}")
        audio_files = [name for name in available_files if name in requested_set]
        print(f"Selected files: {len(audio_files)} of {len(available_files)} supported file(s)")
    else:
        audio_files = available_files

    if not audio_files:
        print(f"WARNING: No audio files matched in {input_folder}")
        if requested_set is not None:
            print("Check the selected file names and supported extensions.")

    for filename in audio_files:
        file_path = os.path.join(input_folder, filename)
        print(f"Processing: {filename}...")

        try:
            # 1. Load the original audio file at its native sample rate
            y, sr = librosa.load(file_path, sr=None, mono=False)

            # 1a. Channel selection: for stereo recordings, pick which
            #     channel(s) to use before any processing.
            if y.ndim > 1:
                if channel == "left":
                    y = y[0]
                    print(f"  [channel] Using LEFT channel")
                elif channel == "right":
                    y = y[-1]
                    print(f"  [channel] Using RIGHT channel")
                else:  # "mix" — average to mono
                    y = np.mean(y, axis=0)
            # Ensure float32 mono
            y = y.astype(np.float32)

            # 1b. Optional resampling: standardise sample rate across files.
            if resample_hz > 0 and sr != resample_hz:
                y = librosa.resample(y, orig_sr=sr, target_sr=resample_hz)
                print(f"  [resample] {sr} Hz → {resample_hz} Hz")
                sr = resample_hz

            # 2. Optional high-pass filter: removes low-frequency rumble (wind,
            #    traffic, generator hum) BEFORE the dB-based split so that
            #    bass-heavy noise doesn't mask quieter animal calls.
            if highpass_hz > 0:
                y = apply_highpass(y, sr, highpass_hz)

            # 2-low. Optional low-pass filter: removes high-frequency noise
            #        above the species' vocal range (equipment hiss, ultrasonic
            #        interference). Companion to the high-pass filter.
            if lowpass_hz > 0:
                y = apply_lowpass(y, sr, lowpass_hz)

            # 2-notch. Optional notch filter(s): surgically removes specific
            #          tonal interference (power-line hum, specific insect freq).
            if notch_freqs:
                for nf in notch_freqs:
                    y = apply_notch(y, sr, nf, quality=notch_q)
                print(f"  [notch] Removed {', '.join(str(f) for f in notch_freqs)} Hz "
                      f"(Q={notch_q})")

            # 2-pre. Optional pre-emphasis: boosts high frequencies to
            #        compensate for distance-based roll-off in field recordings.
            if pre_emphasis_coeff > 0:
                y = apply_pre_emphasis(y, coeff=pre_emphasis_coeff)
                print(f"  [pre-emphasis] coeff={pre_emphasis_coeff}")

            # 2a. Optional bandpass boost: amplifies a target frequency band.
            #     Positive counterpart to the high-pass filter — instead of
            #     cutting unwanted frequencies, boost the wanted ones.
            if bandpass_boost:
                y = apply_bandpass_boost(y, sr, boost_low_hz, boost_high_hz,
                                        boost_gain_db)
                print(f"  [bandpass boost] {boost_low_hz}-{boost_high_hz} Hz "
                      f"boosted by {boost_gain_db} dB")

            # 2b. Optional HPSS: decomposes the signal into harmonic (sustained
            #     tones) and percussive (sharp transients) components. Always
            #     saves both component tracks for auditing. The selected target
            #     component replaces y for downstream processing.
            if hpss_enabled:
                y_harmonic, y_percussive = apply_hpss(y, margin=hpss_margin)

                # Save both raw component tracks for manual auditing
                stem = os.path.splitext(filename)[0]
                sf.write(os.path.join(hpss_harmonic_folder, stem + ".wav"),
                         y_harmonic, sr)
                sf.write(os.path.join(hpss_percussive_folder, stem + ".wav"),
                         y_percussive, sr)

                if hpss_emphasis_db > 0:
                    # Emphasis mode: boost target component within the mix
                    # instead of isolating it.  Positive counterpart to HPSS
                    # isolation — keeps both components, amplifies the target.
                    gain = 10.0 ** (hpss_emphasis_db / 20.0)
                    if hpss_target == "harmonic":
                        y = y_harmonic * gain + y_percussive
                    elif hpss_target == "percussive":
                        y = y_harmonic + y_percussive * gain
                    else:  # "both"
                        y = y_harmonic * gain + y_percussive * gain
                    # Prevent clipping
                    peak = np.max(np.abs(y))
                    if peak > 1.0:
                        y /= peak
                    print(f"  [HPSS] EMPHASIS: {hpss_target} boosted by "
                          f"{hpss_emphasis_db} dB (margin={hpss_margin})")
                elif hpss_target == "harmonic":
                    y = y_harmonic
                    print(f"  [HPSS] Using HARMONIC component (margin={hpss_margin})")
                elif hpss_target == "percussive":
                    y = y_percussive
                    print(f"  [HPSS] Using PERCUSSIVE component (margin={hpss_margin})")
                else:  # "both" — keep original signal, just export the components
                    print(f"  [HPSS] Exported components; keeping full signal (margin={hpss_margin})")

            # 2c. Optional spectral denoising: suppresses spectrally persistent
            #     background sounds (cicadas, hiss, hum) while preserving
            #     transient events like vocalizations.
            if spectral_denoise:
                rms_before = float(np.sqrt(np.mean(y ** 2)))
                y = apply_spectral_denoise(y, sr, prop_decrease=denoise_strength)
                rms_after = float(np.sqrt(np.mean(y ** 2)))
                reduction_db = 20.0 * np.log10(max(rms_after, 1e-10) /
                                               max(rms_before, 1e-10))
                print(f"  [spectral denoise] RMS reduction: {reduction_db:.1f} dB "
                      f"(strength {denoise_strength})")

            # 2d. Optional spectral contrast enhancement: amplifies spectral
            #     peaks that deviate from the background.  Positive counterpart
            #     to spectral denoising — lifts signal up instead of pushing
            #     noise down.
            if spectral_enhance:
                rms_before = float(np.sqrt(np.mean(y ** 2)))
                y = apply_spectral_enhance(y, sr, enhance_factor=enhance_factor)
                rms_after = float(np.sqrt(np.mean(y ** 2)))
                boost_db = 20.0 * np.log10(max(rms_after, 1e-10) /
                                           max(rms_before, 1e-10))
                print(f"  [spectral enhance] RMS boost: +{boost_db:.1f} dB "
                      f"(factor {enhance_factor})")

            # 2e. Optional dynamic range compression: boosts quiet audio toward
            #     a threshold.  Positive counterpart to dB-based muting —
            #     amplifies quiet parts instead of silencing them.
            if compress:
                rms_before = float(np.sqrt(np.mean(y ** 2)))
                y = apply_dynamic_compression(
                    y, sr,
                    threshold_db=compress_threshold_db,
                    ratio=compress_ratio)
                rms_after = float(np.sqrt(np.mean(y ** 2)))
                boost_db = 20.0 * np.log10(max(rms_after, 1e-10) /
                                           max(rms_before, 1e-10))
                print(f"  [compress] RMS boost: +{boost_db:.1f} dB "
                      f"(ratio {compress_ratio}, threshold {compress_threshold_db} dBFS)")

            # 2f. Optional transient sharpening: boosts the attack of each
            #     detected onset.  Positive counterpart to crossfade
            #     smoothing — emphasises edges instead of softening them.
            if sharpen_transients:
                rms_before = float(np.sqrt(np.mean(y ** 2)))
                y = apply_transient_sharpening(
                    y, sr,
                    attack_ms=sharpen_attack_ms,
                    gain_db=sharpen_gain_db)
                rms_after = float(np.sqrt(np.mean(y ** 2)))
                boost_db = 20.0 * np.log10(max(rms_after, 1e-10) /
                                           max(rms_before, 1e-10))
                print(f"  [sharpen] RMS boost: +{boost_db:.1f} dB "
                      f"(+{sharpen_gain_db} dB over {sharpen_attack_ms} ms attacks)")

            # 3. Determine the dB threshold for this file
            if auto_threshold:
                noise_floor_db, noise_profile = estimate_noise_floor(y, sr)
                peak_db = noise_profile["peak_db"]
                file_top_db = compute_adaptive_top_db(
                    noise_floor_db, peak_db,
                    margin_db=noise_margin_db)
                print(f"  [adaptive] noise floor: {noise_floor_db:.1f} dB | "
                      f"peak: {peak_db:.1f} dB | "
                      f"dynamic range: {noise_profile['dynamic_range_db']:.1f} dB | "
                      f"top_db: {file_top_db:.1f}")

                if save_noise_profile:
                    profile_path = os.path.join(
                        clean_output_folder,
                        os.path.splitext(filename)[0] + "_noise_profile.json")
                    noise_profile["adaptive_top_db"] = round(file_top_db, 2)
                    noise_profile["margin_db"] = noise_margin_db
                    with open(profile_path, "w") as fp:
                        json.dump(noise_profile, fp, indent=2)
            else:
                file_top_db = db_threshold

            # 4. Find all the intervals where the audio is LOUDER than the threshold
            intervals = librosa.effects.split(y, top_db=file_top_db)

            # 5. Compute before/after summary for diagnostics
            rms_all = librosa.feature.rms(y=y)[0]
            total_samples = len(y)
            loud_samples = sum(end - start for start, end in intervals)
            quiet_samples = total_samples - loud_samples
            quiet_rms = np.mean(rms_all[rms_all <= np.percentile(rms_all, 25)]) \
                if len(rms_all) > 0 else 0.0
            print(f"  non-silent: {1000.0 * loud_samples / sr:.0f} ms "
                  f"({100.0 * loud_samples / total_samples:.1f}%) | "
                  f"muted: {1000.0 * quiet_samples / sr:.0f} ms | "
                  f"avg RMS quiet frames: {quiet_rms:.6f}")

            # 6. Warn if the entire file falls below the threshold
            if len(intervals) == 0:
                print(f"  -> WARNING: {filename} is entirely below {file_top_db:.1f} dB "
                      f"— output will be silent!")
                warning_count += 1

            # 7. Create a track of pure silence (exact same length as original)
            y_clean = np.zeros_like(y)

            # 8. Paste the loud (valid) audio back into the silent track.
            #    Short crossfades are applied at each boundary to prevent the
            #    hard silence→signal transient from being falsely detected as
            #    an onset by the downstream onset finder.
            fade_samples = int(sr * fade_ms / 1000.0) if fade_ms > 0 else 0

            for start, end in intervals:
                y_clean[start:end] = y[start:end]

                if fade_samples > 0:
                    segment_len = end - start
                    if segment_len <= 2 * fade_samples:
                        # Interval is shorter than two full fades — apply a
                        # single symmetric envelope to avoid overlapping
                        # fade-in and fade-out which would over-attenuate.
                        half = segment_len // 2
                        if half > 0:
                            y_clean[start:start + half] *= np.linspace(0, 1, half)
                            y_clean[start + half:end] *= np.linspace(1, 0, segment_len - half)
                    else:
                        # Normal case: separate fade-in and fade-out, no overlap
                        y_clean[start:start + fade_samples] *= np.linspace(0, 1, fade_samples)
                        y_clean[end - fade_samples:end] *= np.linspace(1, 0, fade_samples)

            # 9. The rejected noise is simply the Original minus the Clean
            y_rejected = y - y_clean

            # 9a. Optional normalization: standardise volume levels across
            #     files. Applied AFTER all processing so every edit is
            #     captured in the final level.
            if normalize_mode:
                y_clean, norm_gain_db = apply_normalize(
                    y_clean, mode=normalize_mode,
                    target_db=normalize_target_db)
                print(f"  [normalize] {normalize_mode} → {normalize_target_db} dBFS "
                      f"(gain: {norm_gain_db:+.1f} dB)")

            # 9b. Optional trim: remove leading/trailing silence. Internal
            #     timing (IOIs) is preserved — only dead edges are removed.
            if trim_silence:
                y_clean, n_trimmed = apply_trim_silence(
                    y_clean, top_db=trim_threshold_db)
                if n_trimmed > 0:
                    print(f"  [trim] Removed {1000.0 * n_trimmed / sr:.0f} ms "
                          f"of edge silence")

            # 10. Save the newly isolated audio files (always as .wav)
            out_filename = os.path.splitext(filename)[0] + ".wav"

            clean_out_path = os.path.join(clean_output_folder, out_filename)
            sf.write(clean_out_path, y_clean, sr)

            audit_out_path = os.path.join(audit_output_folder, "REJECTED_" + out_filename)
            sf.write(audit_out_path, y_rejected, sr)

            processed_count += 1

        except Exception as e:
            print(f"  -> Error processing {filename}: {e}")

    print(f"\nSUCCESS! Processed {processed_count} files.")
    if warning_count > 0:
        print(f"WARNING: {warning_count} file(s) produced fully silent output "
              f"— consider lowering --db-threshold.")
    print(f"Your clean audio is in: {clean_output_folder}")
    print(f"Your audit tracks are in: {audit_output_folder}")


if __name__ == "__main__":
    main()