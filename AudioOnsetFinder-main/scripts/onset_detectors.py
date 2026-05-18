"""Pluggable onset detection methods for bioacoustic rhythm analysis.

Each public ``detect_*`` function takes an audio signal and sample rate plus
method-specific keyword arguments, and returns onset times in seconds as a 1-D
numpy array.  ``onset_finder.py`` selects which method to use via the
``ONSET_METHOD`` configuration variable and calls :func:`detect_onsets` as a
single dispatch point.

Available methods (set ``ONSET_METHOD`` to one of these strings):

    adaptive_hp   — Hodrick-Prescott adaptive baseline (Roeske et al. 2020).
                    Robust to gradually shifting noise floors. Default.
    librosa       — librosa spectral-flux onset detection. Good general-purpose
                    detector with a global delta threshold.
    moving_median — Moving-median adaptive baseline. Simpler/faster alternative
                    to the HP filter with similar adaptive behaviour.
    superflux     — Spectral flux with vibrato suppression (Böck & Widmer 2013).
                    Excellent for frequency-modulated calls (birdsong trills).
    cfar          — Constant False Alarm Rate detector. Formally controls false-
                    positive rate; best when noise is locally stationary.
    per_band      — Per-frequency-band adaptive threshold. Isolates calls from
                    background noise that occupies a different frequency range.
    madmom_beats  — Deep-learning beat tracker (Böck et al. 2016). Finds the
                    metrical pulse (beats/downbeats/tempo) in music. Best for
                    songs and polyphonic recordings.

The helper :func:`refine_onsets_to_sample` (Hilbert envelope derivative) is also
housed here — it is method-agnostic and can refine onsets from any detector to
~0.023 ms precision at 44.1 kHz.

Architecture
------------
All methods follow the same two-stage pattern used throughout the pipeline:

    Stage 1 — Coarse detection (this module)
        Decides **which** audio events are real onsets.  Each method has its
        own coarse resolution determined by its envelope/frame hop size.
        This stage filters out noise and non-target sounds.

    Stage 2 — Sample-level refinement  (:func:`refine_onsets_to_sample`)
        Decides **exactly when** each onset starts by finding the steepest
        energy rise in the Hilbert amplitude envelope within a narrow window
        around the coarse candidate.  Gives ~0.023 ms precision at 44.1 kHz
        *regardless* of which coarse method was used in Stage 1.

So changing the coarse method never affects your final timing precision —
it only affects which onsets are found (sensitivity / false-positive balance).
"""

import warnings

import librosa
import numpy as np
from scipy import sparse
from scipy.signal import hilbert, medfilt
from scipy.sparse.linalg import spsolve

# Optional speech-analysis dependencies — imported lazily so the pipeline
# works without them when only bioacoustic methods are used.
try:
    import parselmouth
    from parselmouth.praat import call as praat_call
    _HAS_PARSELMOUTH = True
except ImportError:
    _HAS_PARSELMOUTH = False

try:
    import whisper as _whisper_module
    _HAS_WHISPER = True
except ImportError:
    _HAS_WHISPER = False

try:
    import whisperx as _whisperx_module
    _HAS_WHISPERX = True
except ImportError:
    _HAS_WHISPERX = False

try:
    import madmom as _madmom_module
    _HAS_MADMOM = True
except ImportError:
    _HAS_MADMOM = False

try:
    import torchcrepe as _torchcrepe_module
    import torch as _torch_module
    _HAS_TORCHCREPE = True
except ImportError:
    _HAS_TORCHCREPE = False


# =====================================================================
# DISPATCH
# =====================================================================

#: Registry mapping method names to (function, accepted_kwargs).
_METHODS = {}


def _register(name):
    """Decorator that registers a detector function under *name*."""
    def wrapper(fn):
        _METHODS[name] = fn
        return fn
    return wrapper


def detect_onsets(method, signal, sr, **kwargs):
    """Dispatch to the detector registered under *method*.

    Parameters
    ----------
    method : str
        One of the keys in ``AVAILABLE_METHODS``.
    signal : np.ndarray
        Mono audio signal.
    sr : int
        Sample rate in Hz.
    **kwargs
        Forwarded to the chosen detector function.

    Returns
    -------
    np.ndarray
        Onset times in seconds.
    """
    if method not in _METHODS:
        raise ValueError(
            f"Unknown onset method '{method}'. "
            f"Available: {sorted(_METHODS.keys())}"
        )
    return _METHODS[method](signal, sr, **kwargs)


def available_methods():
    """Return a sorted list of registered method names."""
    return sorted(_METHODS.keys())


# =====================================================================
# 1. HODRICK-PRESCOTT ADAPTIVE BASELINE  (Roeske et al. 2020)
# =====================================================================

def hodrick_prescott_filter(y, lamb):
    """HP filter: decompose *y* into trend + cycle.  Returns the trend."""
    n = len(y)
    identity = sparse.eye(n, format="csc")
    second_diff = sparse.diags(
        [1, -2, 1], [0, 1, 2], shape=(n - 2, n), format="csc", dtype=float
    )
    trend = spsolve(identity + lamb * second_diff.T.dot(second_diff), y)
    return np.asarray(trend)


@_register("adaptive_hp")
def detect_onsets_adaptive_hp(
    signal, sr, *,
    hp_smooth_lambda=50,
    hp_threshold_lambda=5e7,
    envelope_window_ms=10,
    envelope_hop_ms=1,
):
    """Detect onsets using an HP-filter adaptive baseline (Roeske et al. 2020).

    How it works
    ~~~~~~~~~~~~
    1. Compute an RMS amplitude envelope in short windows with a fine hop.
    2. HP-smooth the envelope with a **small** lambda — this removes sample-level
       micro-noise while still tracking note-level amplitude changes.
    3. Derive an adaptive threshold baseline with a **large** lambda — this
       produces a very slow-moving curve that follows the overall loudness
       contour of the recording (e.g. a song phrase getting louder/softer).
    4. An onset fires at every point where the smoothed envelope **rises above**
       the baseline (positive zero-crossing of the residual).

    Why it's useful
    ~~~~~~~~~~~~~~~
    Because the baseline moves with overall loudness, quiet notes in quiet
    passages can still cross the threshold — unlike a fixed global threshold
    which would miss them.  This makes it robust for field recordings where
    background noise (cicadas, wind, other callers) fades in and out.

    Best for:  birdsong, primate calls, any recording with shifting noise floor.
    Not ideal for: extremely noisy recordings where the noise itself has
    sharp transients (e.g. rain on leaves) — the HP baseline treats those as
    signal too.  Use ``cfar`` or ``per_band`` instead for that scenario.

    Parameters
    ----------
    hp_smooth_lambda : float
        Controls how responsive the envelope smoother is.

        - Lower values (10–30) track the envelope very closely — good for very
          fast staccato notes, but may retain micro-noise bumps.
        - Default (50) — Roeske et al. value.  Good general-purpose balance.
        - Higher values (100–500) over-smooth — can merge closely-spaced notes
          into a single blob.

        **When to change:** If you see two rapid notes being merged into one
        onset, try lowering this.  If you get false onsets from envelope jitter,
        try raising it.

    hp_threshold_lambda : float
        Controls how slowly the adaptive threshold baseline moves.

        - Very large values (5e7–1e8) — baseline is nearly flat within a single
          song phrase.  **Roeske et al. used 5e7.**  Good default.
        - Medium values (1e5–1e6) — baseline tracks volume changes within a
          phrase.  Useful if calls have wildly varying loudness within a single
          bout, but can cause the baseline to "eat into" loud calls and miss
          their onsets.
        - Small values (<1e4) — baseline tracks moment-to-moment energy.
          Almost never useful; the smoothed envelope and baseline will be
          nearly identical, so few onsets will be detected.

        **When to change:** If you're missing quiet onsets that occur right
        after a loud section (the baseline is too high), try increasing this.
        If the detector finds too many noise events in long silent gaps, try
        decreasing it so the baseline drops faster.

    envelope_window_ms : float
        Width of the RMS averaging window (ms).

        - 10 ms (default, matches SoundAnalysisPro) — good for birdsong and
          most bioacoustic signals.
        - 5 ms — finer detail, useful for very rapid clicks (insects).
        - 20–50 ms — smoother, less noise-prone, for slower signals (whale
          calls, primate drumming).

    envelope_hop_ms : float
        Step size between consecutive RMS frames (ms).

        - 1 ms (default, matches SoundAnalysisPro) — gives the HP filter 1 ms
          coarse resolution before the Hilbert refinement sharpens it further.
        - 0.5 ms — slightly finer but doubles the envelope length and HP solve
          time; rarely needed since refinement handles sub-ms precision.
        - 2–5 ms — faster processing for very long files (hours); coarse
          resolution is still refined by the Hilbert step.
    """
    window_samples = max(int(sr * envelope_window_ms / 1000.0), 1)
    hop_samples = max(int(sr * envelope_hop_ms / 1000.0), 1)

    rms = librosa.feature.rms(
        y=signal, frame_length=window_samples, hop_length=hop_samples
    )[0]

    if len(rms) < 4:
        return np.array([], dtype=float)

    smoothed = hodrick_prescott_filter(rms, hp_smooth_lambda)
    baseline = hodrick_prescott_filter(rms, hp_threshold_lambda)
    residual = smoothed - baseline

    onset_frames = []
    for i in range(1, len(residual)):
        if residual[i] > 0 and residual[i - 1] <= 0:
            onset_frames.append(i)

    return np.array(onset_frames, dtype=float) * hop_samples / sr


# =====================================================================
# 2. LIBROSA SPECTRAL-FLUX
# =====================================================================

@_register("librosa")
def detect_onsets_librosa(
    signal, sr, *,
    hop_length=256,
    delta=0.10,
    backtrack=False,
):
    """Standard librosa spectral-flux onset detection.

    How it works
    ~~~~~~~~~~~~
    Computes a spectrogram, measures how much the spectrum changes between
    consecutive frames (spectral flux), then peak-picks that curve.  A frame
    counts as an onset if its spectral flux value is a local maximum that
    exceeds the surrounding average by at least ``delta``.

    Why it's useful
    ~~~~~~~~~~~~~~~
    This is the simplest, most battle-tested approach.  It works directly on
    spectral content, so it can detect onsets even when the overall amplitude
    doesn't change much (e.g. a pitch change within a sustained note).

    Best for:  sharp percussive attacks, clean recordings, quick exploration.
    Not ideal for: recordings with shifting noise floors (uses a global
    threshold, so quiet calls in quiet passages may be missed while loud
    noise in loud passages may trigger false onsets).  Use ``adaptive_hp``
    or ``moving_median`` if that's a problem.

    Parameters
    ----------
    hop_length : int
        Number of audio samples between consecutive spectrogram frames.
        Controls coarse temporal resolution **before** refinement.

        - 512 (~11.6 ms at 44.1 kHz) — librosa default, very coarse.
        - 256 (~5.8 ms) — recommended default in this pipeline.
        - 128 (~2.9 ms) — finer, but the onset-strength curve gets noisier
          and may trigger more false positives.

        **When to change:** Rarely needed; the Hilbert refinement step handles
        sub-ms precision regardless.  Only lower this if you're getting missed
        onsets because they fall between frames (unlikely at 256).

    delta : float
        Peak-picking threshold on the onset-strength curve.  An onset frame
        must exceed the local average by at least this value.

        - 0.03–0.05 — very sensitive.  Good for quiet birdsong in clean
          recordings.  May produce many false positives in noisy audio.
        - 0.07–0.10 — moderate (default).  Balanced for general use.
        - 0.10–0.15 — conservative.  Good for noisy field recordings where
          you only want the most prominent events.

        **When to change:** This is the single most impactful knob for this
        method.  If you're missing real onsets, lower it.  If you're getting
        too many false detections from noise, raise it.

    backtrack : bool
        When True, each detected onset is rolled backward to the nearest
        preceding local energy minimum (intended to find the "true start" of
        the attack).

        - False (default) — keep onsets at the spectral-flux peak.
          Recommended for this pipeline because the Hilbert refinement step
          already finds the true attack start more precisely.
        - True — can help if refinement is disabled, but on noisy field
          recordings it often overshoots (places onsets too early).
    """
    return librosa.onset.onset_detect(
        y=signal,
        sr=sr,
        hop_length=hop_length,
        units="time",
        backtrack=backtrack,
        delta=delta,
        pre_max=1,
        post_max=1,
    )


# =====================================================================
# 3. MOVING-MEDIAN ADAPTIVE BASELINE
# =====================================================================

@_register("moving_median")
def detect_onsets_moving_median(
    signal, sr, *,
    envelope_window_ms=10,
    envelope_hop_ms=1,
    median_window_ms=200,
    threshold_scale=1.5,
):
    """Detect onsets where the RMS envelope exceeds a moving-median baseline.

    How it works
    ~~~~~~~~~~~~
    Computes an RMS amplitude envelope, then runs a sliding median filter over
    it to produce a slowly-moving baseline.  An onset fires whenever the
    envelope rises above ``threshold_scale × baseline``.  Conceptually similar
    to ``adaptive_hp`` but uses a median instead of an HP-filter decomposition.

    Why it's useful
    ~~~~~~~~~~~~~~~
    The median is naturally robust to outliers — a single sharp click won't
    pull the baseline up the way a mean-based method would.  It's also much
    faster to compute than the HP filter (no sparse matrix solve), making it
    a good choice for very long recordings (hours) or batch processing many
    files.

    Best for:  fast alternative to HP when you need adaptive behaviour but
    don't need the smoothest possible baseline; primate drumming bouts with
    uneven loudness; quick batch exploration of large datasets.
    Not ideal for: recordings where the noise floor changes *very* gradually
    over minutes — the HP filter tracks slow trends more smoothly.  Also
    doesn't distinguish frequency content, so if noise and signal share the
    same amplitude range but different frequencies, ``per_band`` is better.

    Parameters
    ----------
    envelope_window_ms : float
        Width of the RMS averaging window (ms).  Same role as in ``adaptive_hp``.
        10 ms default.

    envelope_hop_ms : float
        Step size between consecutive RMS frames (ms).  1 ms default.

    median_window_ms : float
        Width of the sliding median window (ms of envelope time).  Controls
        how "long-term" the baseline's memory is.

        - 100 ms — responsive.  Baseline follows bursts closely.  Good for
          very rapid note sequences but may cause the baseline to rise during
          a burst and suppress later notes within it.
        - 200 ms (default) — balanced.  Works for most birdsong and drumming.
        - 500 ms–1 s — very smooth.  Baseline barely reacts to individual
          notes; only tracks overall loudness over many seconds.  Good for
          long frog or whale choruses.

        **When to change:** If notes within a rapid burst are being missed
        (baseline rises too fast), increase this.  If quiet calls in quiet
        sections are missed (baseline stays too high from a previous loud
        section), decrease this.

    threshold_scale : float
        Multiplier applied to the median baseline.  An onset fires when
        ``envelope > threshold_scale × median_baseline``.

        - 1.2 — very sensitive.  Catches quiet notes but may trigger on noise.
        - 1.5 (default) — balanced.
        - 2.0–3.0 — conservative.  Only prominent transients detected.

        **When to change:** This is the primary sensitivity knob.  If you get
        too many false positives, raise it.  If you miss real onsets, lower it.
    """
    window_samples = max(int(sr * envelope_window_ms / 1000.0), 1)
    hop_samples = max(int(sr * envelope_hop_ms / 1000.0), 1)

    rms = librosa.feature.rms(
        y=signal, frame_length=window_samples, hop_length=hop_samples
    )[0]

    if len(rms) < 4:
        return np.array([], dtype=float)

    # Median filter kernel must be odd.
    kernel_frames = int(median_window_ms / envelope_hop_ms)
    kernel_frames = kernel_frames if kernel_frames % 2 == 1 else kernel_frames + 1
    kernel_frames = max(kernel_frames, 3)

    baseline = medfilt(rms, kernel_size=kernel_frames)
    above = rms > (threshold_scale * baseline)

    # Rising edges.
    onset_frames = []
    for i in range(1, len(above)):
        if above[i] and not above[i - 1]:
            onset_frames.append(i)

    return np.array(onset_frames, dtype=float) * hop_samples / sr


# =====================================================================
# 4. SUPERFLUX  (Böck & Widmer 2013)
# =====================================================================

@_register("superflux")
def detect_onsets_superflux(
    signal, sr, *,
    hop_length=256,
    n_fft=2048,
    lag=2,
    max_size=3,
    delta=0.05,
):
    """Spectral-flux onset detection with vibrato suppression (Böck & Widmer 2013).

    How it works
    ~~~~~~~~~~~~
    Standard spectral flux compares each spectrogram frame to the *immediately*
    preceding frame.  The problem: if a bird is singing a trill with vibrato
    (rapid pitch wobble), the spectrum changes from frame to frame even though
    no new note has started — triggering false onsets.

    Superflux fixes this by:
      a) Comparing each frame to a frame *lag* steps back (not just 1 step),
         which reduces sensitivity to fast FM wobbles.
      b) Replacing each spectral bin with the **local maximum** over
         *max_size* neighbouring frequency bins before computing the flux.
         This lets the algorithm tolerate small frequency shifts without
         seeing them as spectral change.

    The result is a spectral-flux onset-strength curve that fires on real new
    notes but ignores vibrato, trills, and gentle pitch slides.

    Why it's useful
    ~~~~~~~~~~~~~~~
    Many bird species (nightingales, wrens, warblers) and some frogs produce
    frequency-modulated calls where the pitch sweeps rapidly within a single
    note.  Standard spectral flux or amplitude-based detectors see these
    sweeps as multiple onsets.  Superflux suppresses them.

    Best for:  birdsong with trills/vibrato, frog calls with FM sweeps,
    any signal where pitch changes within a note.
    Not ideal for: amplitude-only signals with no spectral structure (e.g.
    primate drumming on buttress roots, which is essentially broadband noise
    bursts) — use ``adaptive_hp`` or ``moving_median`` instead.

    Parameters
    ----------
    hop_length : int
        Spectrogram frame hop (samples).  Same role as in ``librosa`` method.
        256 default.

    n_fft : int
        FFT window size (samples).  Controls frequency resolution.

        - 2048 (default) — good frequency resolution (~21 Hz bins at 44.1 kHz).
          Standard for most bioacoustic work.
        - 1024 — coarser frequency bins but better temporal resolution.
          Try this for very rapid trills (>20 notes/sec).
        - 4096 — very fine frequency resolution.  Useful if you need to
          separate two species calling at very close frequencies, but reduces
          temporal sharpness.

        **When to change:** Only change this if you have a specific frequency-
        resolution need.  For most birdsong, 2048 works well.

    lag : int
        Number of frames to look back when computing spectral flux.

        - 1 — standard flux (no vibrato suppression).  Equivalent to the
          basic ``librosa`` method.
        - 2 (default) — skips one frame.  Catches vibrato up to ~86 Hz
          (at 256 hop / 44.1 kHz).  Good for most birdsong.
        - 3–4 — wider look-back.  Catches slower FM sweeps (e.g. frog calls)
          but reduces sensitivity to genuinely rapid note sequences.

        **When to change:** If trills/vibrato are still producing false
        onsets, increase lag.  If real rapid-fire notes are being missed,
        decrease it.

    max_size : int
        Size of the local-maximum filter along the frequency axis.

        - 1 — no frequency-axis smoothing (equivalent to standard flux).
        - 3 (default) — each bin is compared to the max of itself and its
          two neighbours.  Tolerates ~2 bin widths of frequency shift.
        - 5–7 — tolerates larger pitch slides.  Good for species with very
          wide vibrato or portamento.

        **When to change:** If you still get false onsets from pitch slides,
        increase this.  If the detector stops finding onsets that involve a
        large frequency jump (e.g. an octave leap), decrease it — a large
        max_size can "blur" genuine spectral changes.

    delta : float
        Peak-picking threshold on the onset-strength curve.

        - 0.03 — very sensitive.
        - 0.05 (default) — balanced for birdsong.
        - 0.10–0.15 — conservative, only prominent attacks.

        Same role as in the ``librosa`` method.
    """
    onset_env = librosa.onset.onset_strength(
        y=signal, sr=sr,
        hop_length=hop_length,
        n_fft=n_fft,
        lag=lag,
        max_size=max_size,
    )

    # Peak-pick the onset strength envelope.
    onset_frames = librosa.util.peak_pick(
        onset_env,
        pre_max=1, post_max=1,
        pre_avg=1, post_avg=1,
        delta=delta,
        wait=1,
    )

    return librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)


# =====================================================================
# 5. CFAR  (Constant False Alarm Rate)
# =====================================================================

@_register("cfar")
def detect_onsets_cfar(
    signal, sr, *,
    envelope_window_ms=10,
    envelope_hop_ms=1,
    guard_ms=20,
    training_ms=200,
    threshold_factor=4.0,
):
    """CFAR (Constant False Alarm Rate) onset detector.

    How it works
    ~~~~~~~~~~~~
    Borrowed from radar signal processing.  For each point in the RMS
    envelope, the algorithm estimates the local noise level by looking at
    two "training windows" (one before, one after the candidate point),
    separated by a "guard band" that prevents the onset itself from
    contaminating the noise estimate.

    It computes the noise mean and standard deviation from those training
    windows, then declares an onset if the candidate point exceeds
    ``noise_mean + threshold_factor × noise_std``.

    Why it's useful
    ~~~~~~~~~~~~~~~
    Unlike the other methods which use heuristic thresholds, CFAR gives you
    a *statistically principled* false-alarm rate.  If the noise is roughly
    Gaussian and stationary within the training window, ``threshold_factor``
    directly controls how many standard deviations above noise an onset must
    be.  This is especially useful when you need to formally report detection
    reliability (e.g. in a publication).

    Best for:  recordings where the noise is relatively steady within each
    training window (e.g. steady cicada drone, constant river/waterfall
    background, lab recordings with ventilation hum).
    Not ideal for: recordings where the noise changes rapidly (e.g. dawn
    chorus with many species overlapping, rain bursts) — the noise estimate
    becomes unreliable.  Use ``adaptive_hp`` or ``per_band`` instead.

    Parameters
    ----------
    envelope_window_ms : float
        Width of the RMS averaging window (ms).  10 ms default.

    envelope_hop_ms : float
        Step size between consecutive RMS frames (ms).  1 ms default.

    guard_ms : float
        Half-width of the guard band (ms) around the cell under test.

        - 10 ms — tight guard.  Good for very short clicks (insects).
        - 20 ms (default) — covers most bioacoustic transients.
        - 50 ms — wide guard.  Use for signals with long attack ramps
          (e.g. whale calls that ramp up over 30–50 ms).

        **When to change:** The guard band must be wider than the onset
        transient itself.  If you see onsets being split into two detections,
        the guard is too narrow (the tail of one onset is leaking into the
        training window of the next).  If you miss closely-spaced notes
        because the guard overlaps the next note, it's too wide.

    training_ms : float
        Half-width of each training window (ms) on each side of the guard.

        - 100 ms — shorter training window.  Noise estimate adapts faster
          but is noisier (fewer samples to average).  Good for recordings
          shorter than a few seconds.
        - 200 ms (default) — balanced.
        - 500 ms — longer training window.  More stable noise estimate, but
          assumes the noise floor doesn't change over a full second.

        **When to change:** If the noise floor shifts noticeably over the
        training window width (e.g. cicadas ramping up), shorten this.
        If your noise estimate seems jittery (onsets appear/disappear when
        you re-run), lengthen this.

    threshold_factor : float
        Number of noise standard deviations above the noise mean.

        - 2.0–3.0 — very sensitive.  Catches quiet onsets but may have
          elevated false-positive rate.
        - 4.0 (default) — ~0.006% false alarm rate for Gaussian noise.
          Good general-purpose setting.
        - 5.0–6.0 — very conservative.  Almost no false positives, but may
          miss quiet onsets.

        **When to change:** This is the single most impactful knob.  Lower
        it if you're missing onsets; raise it if you're getting false
        detections from noise.
    """
    window_samples = max(int(sr * envelope_window_ms / 1000.0), 1)
    hop_samples = max(int(sr * envelope_hop_ms / 1000.0), 1)

    rms = librosa.feature.rms(
        y=signal, frame_length=window_samples, hop_length=hop_samples
    )[0]

    if len(rms) < 4:
        return np.array([], dtype=float)

    guard_frames = max(int(guard_ms / envelope_hop_ms), 1)
    train_frames = max(int(training_ms / envelope_hop_ms), 1)
    margin = guard_frames + train_frames

    above = np.zeros(len(rms), dtype=bool)

    for i in range(margin, len(rms) - margin):
        lead = rms[i - margin : i - guard_frames]
        trail = rms[i + guard_frames + 1 : i + margin + 1]
        noise = np.concatenate([lead, trail])
        noise_mean = float(np.mean(noise))
        noise_std = float(np.std(noise))
        if rms[i] > noise_mean + threshold_factor * noise_std:
            above[i] = True

    # Rising edges.
    onset_frames = []
    for i in range(1, len(above)):
        if above[i] and not above[i - 1]:
            onset_frames.append(i)

    return np.array(onset_frames, dtype=float) * hop_samples / sr


# =====================================================================
# 6. PER-BAND ADAPTIVE THRESHOLD
# =====================================================================

@_register("per_band")
def detect_onsets_per_band(
    signal, sr, *,
    hop_length=256,
    n_fft=2048,
    n_bands=6,
    freq_min=200,
    freq_max=None,
    median_window_ms=200,
    threshold_scale=1.5,
    min_bands=2,
):
    """Per-frequency-band adaptive threshold onset detector.

    How it works
    ~~~~~~~~~~~~
    1. Compute a spectrogram, then divide the frequency axis into *n_bands*
       Mel-spaced bands between *freq_min* and *freq_max*.
    2. In each band, compute spectral flux (how much energy increases from
       one frame to the next) and apply a moving-median adaptive threshold
       independently.
    3. A global onset is declared at frames where **at least** *min_bands*
       bands fire simultaneously.

    Why it's useful
    ~~~~~~~~~~~~~~~
    Most other methods work on the total broadband amplitude envelope.  If
    your target call and the background noise occupy different frequency
    ranges (e.g. a bird calling at 3–5 kHz over cicada noise at 6–10 kHz),
    broadband methods see the cicada energy as part of the overall envelope
    and either miss quiet bird onsets or trigger on cicada bursts.

    Per-band detection sidesteps this: the bird-call band fires on the bird,
    the cicada band fires on the cicada, and since only the bird band produces
    consistent onsets at the right frames, the voting threshold filters out
    the cicada events.

    Best for:  mixed-species recordings, target calls in a narrow frequency
    band with noise in a different band, separating overlapping callers.
    Not ideal for:  broadband percussion or drumming (energy spans all bands
    equally, so every band fires on every hit — works but gives no advantage
    over simpler methods).

    Parameters
    ----------
    hop_length : int
        Spectrogram frame hop (samples).  256 default.

    n_fft : int
        FFT window size (samples).  2048 default.  Controls how finely
        the frequency axis is sliced.  See ``superflux`` docs for guidance.

    n_bands : int
        Number of frequency bands to split the spectrogram into.

        - 3–4 — coarse split.  Each band covers a wide frequency range.
          Good when you just want to separate "low / mid / high".
        - 6 (default) — balanced.  Enough resolution to isolate most species
          from common noise types.
        - 10–12 — fine split.  Useful when you have many overlapping callers
          at different pitches and want each to be detected independently.

        **When to change:** More bands = more frequency selectivity but
        requires more onsets to agree (see *min_bands*).  If you know your
        target species occupies a narrow band, increase this.

    freq_min : float
        Lower frequency boundary (Hz).

        - 200 (default) — excludes low-frequency rumble (wind, traffic).
        - 500 — for birdsong, skip everything below typical call range.
        - 80 — for primate drumming, include low-frequency content.

    freq_max : float or None
        Upper frequency boundary (Hz).  ``None`` defaults to sr/2.

        - None (default) — uses the full frequency range up to Nyquist.
        - 8000 — if you know your target is below 8 kHz, setting this
          excludes high-frequency noise bands from the vote.

    median_window_ms : float
        Moving-median window width per band (ms).  200 ms default.
        Same role as in ``moving_median``.

    threshold_scale : float
        Per-band onset threshold multiplier.  1.5 default.
        Same role as in ``moving_median``.

    min_bands : int
        Minimum number of bands that must fire at the same frame for a
        global onset to be declared.

        - 1 — any single band firing counts.  Very sensitive but loses the
          noise-separation advantage (equivalent to broadband detection).
        - 2 (default) — at least 2 bands must agree.  Filters out
          narrow-band noise spikes.
        - 3+ — conservative.  Only broadband events (hitting many frequency
          bands simultaneously) are detected.  Good for percussion.

        **When to change:** If you're missing valid onsets, lower this (or
        increase *n_bands* so more bands overlap with your target signal).
        If you're getting false positives from narrow-band noise, raise it.
    """
    if freq_max is None:
        freq_max = sr / 2.0

    S = np.abs(librosa.stft(signal, n_fft=n_fft, hop_length=hop_length))
    n_frames = S.shape[1]

    # Mel-spaced band edges.
    mel_min = librosa.hz_to_mel(freq_min)
    mel_max = librosa.hz_to_mel(freq_max)
    mel_edges = np.linspace(mel_min, mel_max, n_bands + 1)
    hz_edges = librosa.mel_to_hz(mel_edges)

    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    band_detections = np.zeros((n_bands, n_frames), dtype=bool)

    for b in range(n_bands):
        lo_hz, hi_hz = hz_edges[b], hz_edges[b + 1]
        bin_mask = (freqs >= lo_hz) & (freqs < hi_hz)
        if not np.any(bin_mask):
            continue

        band_energy = np.sum(S[bin_mask, :], axis=0)

        # Spectral flux (positive half-wave rectified first-difference).
        flux = np.zeros_like(band_energy)
        flux[1:] = np.maximum(0, np.diff(band_energy))

        # Moving-median baseline.
        hop_ms = (hop_length / sr) * 1000.0
        kernel = int(median_window_ms / hop_ms)
        kernel = kernel if kernel % 2 == 1 else kernel + 1
        kernel = max(kernel, 3)

        baseline = medfilt(flux, kernel_size=kernel)
        band_detections[b] = flux > (threshold_scale * baseline)

    # Global onset: enough bands fire at the same frame.
    votes = np.sum(band_detections, axis=0)
    global_above = votes >= min_bands

    onset_frames = []
    for i in range(1, len(global_above)):
        if global_above[i] and not global_above[i - 1]:
            onset_frames.append(i)

    return librosa.frames_to_time(
        np.array(onset_frames), sr=sr, hop_length=hop_length
    )


# =====================================================================
# 7. SYLLABLE NUCLEI  (Parselmouth / Praat)
# =====================================================================

# Side-channel for F0/prosody metrics computed during syllable_nuclei detection.
# Populated by detect_onsets_syllable_nuclei; read by onset_finder.py after the call.
# Keys: "F0 Mean (Hz)", "F0 Std (Hz)", "F0 Min (Hz)", "F0 Max (Hz)",
#        "F0 Range (Hz)", "Jitter (local)", "Intensity Mean (dB)", "Intensity Std (dB)"
last_f0_metrics = {}

@_register("syllable_nuclei")
def detect_onsets_syllable_nuclei(
    signal, sr, *,
    intensity_threshold=-25.0,
    min_dip_db=2.0,
    min_pause_ms=30.0,
    voicing_threshold=0.3,
    time_step=0.01,
):
    """Detect syllable nuclei (vowel centres) using Praat via Parselmouth.

    How it works
    ~~~~~~~~~~~~
    1. Compute an intensity contour (energy envelope in dB) with Praat's
       ``To Intensity`` algorithm, which uses a Gaussian-windowed sum of
       squares with a configurable time step.
    2. Find local intensity peaks (candidate syllable nuclei).
    3. Between consecutive peaks, measure the **dip** (the minimum intensity
       value in the valley between them).  If the dip is shallower than
       ``min_dip_db``, the two peaks are merged (they belong to the same
       syllable).
    4. Optionally filter by voicing: only keep peaks that coincide with a
       voiced segment (pitch > 0) if ``voicing_threshold > 0``.

    This is a faithful reimplementation of the classic *syllable_nuclei.praat*
    script by Nivja de Jong & Ton Wempe (2009), widely used in speech rhythm
    research (Grabe & Low 2002, Ramus et al. 1999).

    Why it's useful
    ~~~~~~~~~~~~~~~
    Speech rhythm metrics (nPVI, %V, ΔC/ΔV) require syllable- or vowel-level
    segmentation.  Unlike amplitude-only onset detectors, this method uses
    the intensity-dip heuristic to handle co-articulated consonant clusters
    and the voicing constraint to avoid triggering on unvoiced noise.

    Best for:  human speech and singing, conversational recordings, read
    passages, field recordings of language.
    Not ideal for: non-vocal sounds (use ``adaptive_hp`` or ``librosa``
    instead); whispered speech (no voicing to detect).

    Parameters
    ----------
    intensity_threshold : float
        Minimum intensity (dB relative to peak) for a peak to be considered.

        - −25 dB (default) — keeps peaks down to ~25 dB below the loudest
          point.  Good for normal conversational speech.
        - −30 dB — more permissive; catches very quiet syllables in soft
          speech or distant speakers.
        - −15 dB — stricter; only prominent syllables survive.  Good for
          noisy recordings where quiet peaks are usually noise.

        **When to change:** If you miss weak syllables at phrase edges, lower
        this.  If you get false peaks from background noise, raise it.

    min_dip_db : float
        Minimum intensity dip (dB) between two consecutive peaks for them to
        count as separate syllables.

        - 2 dB (default) — standard value from de Jong & Wempe (2009).
        - 1 dB — very sensitive; may over-segment diphthongs and long vowels.
        - 4 dB — conservative; may under-segment rapid casual speech.

        **When to change:** If syllables in rapid connected speech are being
        merged, lower this.  If single long vowels are split into two
        detections, raise it.

    min_pause_ms : float
        Minimum silence gap (ms) between syllable groups.

        - 30 ms (default) — typical minimum for syllable boundaries.
        - 15 ms — very short; keeps pauses between all adjacent syllables.
        - 100 ms — only detects phrase-level gaps.

    voicing_threshold : float
        Praat pitch-detection voicing threshold (0–1).  Higher = stricter
        voicing criterion.

        - 0.0 — disabled; all intensity peaks are kept regardless of voicing.
        - 0.3 (default) — mild voicing check; filters most unvoiced noise
          while keeping voiced fricatives and nasals.
        - 0.5 — stricter; more reliable on clean recordings but may miss
          syllables starting with voiceless consonants on noisy audio.

        **When to change:** Set to 0.0 for whispered speech or recordings
        where voicing detection is unreliable.  Raise for very clean
        recordings to reduce false alarms.

    time_step : float
        Time step (seconds) for the intensity contour computation.

        - 0.01 (default, 10 ms) — matches Praat's standard.
        - 0.005 (5 ms) — finer; useful for rapid speech.
        - 0.02 (20 ms) — coarser; faster, adequate for read speech.
    """
    if not _HAS_PARSELMOUTH:
        raise RuntimeError(
            "The 'syllable_nuclei' onset method requires the parselmouth package.\n"
            "Install it with:  pip install praat-parselmouth"
        )

    # --- Create Praat Sound object from numpy array ---
    snd = parselmouth.Sound(signal, sampling_frequency=sr)

    # --- Intensity contour ---
    intensity = snd.to_intensity(
        minimum_pitch=100,  # Hz; standard for intensity computation
        time_step=time_step,
    )

    # --- Pitch (for voicing check) ---
    pitch = None
    if voicing_threshold > 0:
        pitch = snd.to_pitch(time_step=time_step)

    # Extract intensity values and times
    n_frames = intensity.get_number_of_frames()
    if n_frames < 3:
        return np.array([], dtype=float)

    times = np.array([intensity.get_time_from_frame_number(i + 1)
                       for i in range(n_frames)])
    values = np.array([intensity.get_value(t) for t in times])

    # Replace NaN with -inf so they never count as peaks
    values = np.where(np.isfinite(values), values, -np.inf)

    peak_db = float(np.max(values[np.isfinite(values)])) if np.any(np.isfinite(values)) else 0.0
    abs_threshold = peak_db + intensity_threshold  # intensity_threshold is negative

    # --- Find local maxima (candidate syllable nuclei) ---
    peaks = []
    for i in range(1, n_frames - 1):
        if values[i] > values[i - 1] and values[i] >= values[i + 1]:
            if values[i] >= abs_threshold:
                peaks.append(i)

    if len(peaks) == 0:
        return np.array([], dtype=float)

    # --- Merge peaks with shallow dips ---
    merged = [peaks[0]]
    for j in range(1, len(peaks)):
        prev_idx = merged[-1]
        curr_idx = peaks[j]
        # Find minimum intensity between previous and current peak
        valley = values[prev_idx:curr_idx + 1]
        min_valley = float(np.min(valley))
        # If the dip from either peak to the valley is deep enough, keep both
        dip_from_prev = values[prev_idx] - min_valley
        dip_from_curr = values[curr_idx] - min_valley
        if dip_from_prev >= min_dip_db and dip_from_curr >= min_dip_db:
            merged.append(curr_idx)
        else:
            # Keep whichever peak is louder
            if values[curr_idx] > values[prev_idx]:
                merged[-1] = curr_idx

    # --- Voicing filter ---
    if pitch is not None and voicing_threshold > 0:
        voiced_peaks = []
        for idx in merged:
            t = times[idx]
            try:
                f0 = praat_call(pitch, "Get value at time", t, "Hertz", "Linear")
            except Exception:
                f0 = 0.0
            if f0 is not None and not np.isnan(f0) and f0 > 0:
                voiced_peaks.append(idx)
        merged = voiced_peaks

    # --- Min pause filter ---
    if min_pause_ms > 0 and len(merged) > 1:
        min_gap = min_pause_ms / 1000.0
        filtered = [merged[0]]
        for idx in merged[1:]:
            if times[idx] - times[filtered[-1]] >= min_gap:
                filtered.append(idx)
            else:
                # Keep louder peak
                if values[idx] > values[filtered[-1]]:
                    filtered[-1] = idx
        merged = filtered

    onset_times = times[merged]

    # --- Extract F0/prosody metrics from the Praat pitch object ---
    f0_metrics = {}
    try:
        # Build pitch contour if not already computed (voicing_threshold==0 case)
        if pitch is None:
            pitch = snd.to_pitch(time_step=time_step)
        # Extract F0 values at each frame
        n_pitch = pitch.get_number_of_frames()
        f0_vals = []
        for i in range(n_pitch):
            t = pitch.get_time_from_frame_number(i + 1)
            try:
                f0 = praat_call(pitch, "Get value at time", t, "Hertz", "Linear")
            except Exception:
                f0 = 0.0
            if f0 is not None and not np.isnan(f0) and f0 > 0:
                f0_vals.append(f0)
        if len(f0_vals) >= 2:
            f0_arr = np.array(f0_vals)
            f0_metrics["F0 Mean (Hz)"] = round(float(np.mean(f0_arr)), 2)
            f0_metrics["F0 Std (Hz)"] = round(float(np.std(f0_arr)), 2)
            f0_metrics["F0 Min (Hz)"] = round(float(np.min(f0_arr)), 2)
            f0_metrics["F0 Max (Hz)"] = round(float(np.max(f0_arr)), 2)
            f0_metrics["F0 Range (Hz)"] = round(float(np.max(f0_arr) - np.min(f0_arr)), 2)
        # Jitter (local) — cycle-to-cycle F0 perturbation
        try:
            point_process = praat_call(snd, "To PointProcess (periodic, cc)", 75, 500)
            jitter = praat_call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
            if jitter is not None and not np.isnan(jitter):
                f0_metrics["Jitter (local)"] = round(float(jitter), 6)
        except Exception:
            pass
        # Intensity statistics
        int_vals = values[np.isfinite(values)]
        if len(int_vals) > 0:
            f0_metrics["Intensity Mean (dB)"] = round(float(np.mean(int_vals)), 2)
            f0_metrics["Intensity Std (dB)"] = round(float(np.std(int_vals)), 2)
    except Exception:
        pass  # F0 metrics are optional; don't break detection on failure
    last_f0_metrics.clear()
    last_f0_metrics.update(f0_metrics)

    return np.asarray(onset_times, dtype=float)


# =====================================================================
# 8. WHISPER WORD ONSETS  (OpenAI Whisper)
# =====================================================================

# Side-channel for Whisper transcript data (word text + timing).
# Populated by detect_onsets_whisper_words; read by onset_finder.py for export.
# List of dicts: [{"word": str, "start": float, "end": float}, ...]
last_whisper_transcript = []

@_register("whisper_words")
def detect_onsets_whisper_words(
    signal, sr, *,
    model_size="base",
    language=None,
    word_timestamps=True,
):
    """Detect word (or segment) onsets using OpenAI's Whisper ASR model.

    How it works
    ~~~~~~~~~~~~
    1. Load or reuse a Whisper model of the requested size.
    2. Transcribe the audio with word-level timestamps enabled.
    3. Extract the start time of each detected word as an onset.

    If ``word_timestamps`` is False, Whisper returns only segment-level
    boundaries (typically one per sentence/phrase), which may still be useful
    for coarse phrase-rhythm analysis.

    Why it's useful
    ~~~~~~~~~~~~~~~
    Whisper provides the most linguistically meaningful segmentation
    available without a pre-existing transcript.  Word onsets capture
    lexical rhythm — useful for speech rate, pause analysis, and
    cross-linguistic rhythm comparisons where syllable segmentation is
    unnecessary or too fine-grained.

    Best for:  word-level speech rhythm, speech rate measurement, pause
    analysis, multi-language recordings (Whisper handles 99+ languages).
    Not ideal for: syllable-level timing (use ``syllable_nuclei`` instead);
    non-speech audio; very short utterances (< 1 second).

    Parameters
    ----------
    model_size : str
        Whisper model to use.  Larger models are more accurate but slower.

        - ``"tiny"`` — fastest, least accurate.  Good for quick exploration.
        - ``"base"`` (default) — good balance.  Runs in real-time on CPU.
        - ``"small"`` — noticeably better accuracy, ~2× slower than base.
        - ``"medium"`` — strong accuracy, ~5× slower than base.
        - ``"large"`` — best accuracy, requires GPU for reasonable speed.

        **When to change:** If word boundaries seem inaccurate (words
        merged or split incorrectly), try a larger model.  For batch
        processing many files, ``tiny`` or ``base`` are most practical.

    language : str or None
        ISO language code (e.g. ``"en"``, ``"fr"``, ``"de"``).  ``None``
        lets Whisper auto-detect the language from the first 30 seconds.

        **When to change:** Set explicitly if auto-detection fails (e.g.
        for short clips, code-switched speech, or minority languages).

    word_timestamps : bool
        When True (default), extract per-word onset times.  When False,
        extract per-segment (sentence/phrase) onset times instead.

        - True — one onset per word.  Best for speech rhythm analysis.
        - False — one onset per segment (~5–30 seconds).  Useful for
          phrase-level timing or when word boundaries aren't needed.
    """
    if not _HAS_WHISPER:
        raise RuntimeError(
            "The 'whisper_words' onset method requires the openai-whisper package.\n"
            "Install it with:  pip install openai-whisper"
        )

    # Cache the model on the function object to avoid reloading per file.
    cache_attr = f"_whisper_model_{model_size}"
    if not hasattr(detect_onsets_whisper_words, cache_attr):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            setattr(detect_onsets_whisper_words, cache_attr,
                    _whisper_module.load_model(model_size))
    model = getattr(detect_onsets_whisper_words, cache_attr)

    # Whisper expects float32 audio at 16 kHz.
    if sr != 16000:
        signal_16k = librosa.resample(signal.astype(np.float32), orig_sr=sr, target_sr=16000)
    else:
        signal_16k = signal.astype(np.float32)

    # Pad or trim to 30-second chunks (Whisper's native window).
    transcribe_kwargs = dict(word_timestamps=word_timestamps)
    if language is not None:
        transcribe_kwargs["language"] = language

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        result = model.transcribe(signal_16k, **transcribe_kwargs)

    onsets = []
    transcript_entries = []
    if word_timestamps:
        for seg in result.get("segments", []):
            for word_info in seg.get("words", []):
                start = word_info.get("start")
                if start is not None:
                    onsets.append(float(start))
                    transcript_entries.append({
                        "word": word_info.get("word", "").strip(),
                        "start": float(start),
                        "end": float(word_info.get("end", start)),
                    })
    else:
        for seg in result.get("segments", []):
            start = seg.get("start")
            if start is not None:
                onsets.append(float(start))
                transcript_entries.append({
                    "word": seg.get("text", "").strip(),
                    "start": float(start),
                    "end": float(seg.get("end", start)),
                })

    # Populate side-channel for transcript export
    last_whisper_transcript.clear()
    last_whisper_transcript.extend(transcript_entries)

    return np.array(sorted(set(onsets)), dtype=float)


# =====================================================================
# 9. WHISPERX PHONEME ALIGNMENT  (Ramus et al. 1999 metrics)
# =====================================================================

# Side-channel for phoneme-level data and Ramus metrics.
# Populated by detect_onsets_whisperx_phonemes; read by onset_finder.py.
# phonemes: [{"phone": str, "start": float, "end": float, "is_vowel": bool}, ...]
# ramus_metrics: {"%V": float, "DeltaV (ms)": float, "DeltaC (ms)": float,
#                  "rPVI-C (ms)": float, "nPVI-V (%)": float}
last_whisperx_phonemes = []
last_ramus_metrics = {}

# Populated by detect_onsets_madmom_beats; read by onset_finder.py.
# last_madmom_tempo: {"BPM": float, "BPM_alt": float|None}  (primary + secondary tempo)
# last_madmom_downbeats: np.ndarray of downbeat times in seconds (or empty)
last_madmom_tempo = {}
last_madmom_downbeats = np.array([])

# Vowel phone symbols (IPA / ARPAbet).  Used to classify phonemes.
_VOWEL_PHONES = {
    # IPA vowels
    "a", "e", "i", "o", "u", "ɪ", "ɛ", "æ", "ʌ", "ɔ", "ʊ", "ə",
    "ɑ", "ɒ", "ɨ", "ʉ", "ɯ", "ɤ", "ø", "œ", "y", "ɶ",
    # ARPAbet vowels (Whisper/WhisperX may use these)
    "AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY",
    "IH", "IY", "OW", "OY", "UH", "UW",
    # Lowercase ARPAbet
    "aa", "ae", "ah", "ao", "aw", "ay", "eh", "er", "ey",
    "ih", "iy", "ow", "oy", "uh", "uw",
}


@_register("whisperx_phonemes")
def detect_onsets_whisperx_phonemes(
    signal, sr, *,
    model_size="base",
    language=None,
    device="cpu",
):
    """Detect phoneme onsets using WhisperX forced alignment.

    How it works
    ~~~~~~~~~~~~
    1. Transcribe audio with Whisper (via WhisperX's wrapper).
    2. Run forced phoneme alignment using wav2vec2/MMS models.
    3. Classify each phoneme as vowel or consonant.
    4. Compute Ramus et al. (1999) rhythm class metrics:
       %V, ΔV, ΔC, rPVI-C, nPVI-V.
    5. Return vowel-onset times as detected onsets (syllable nuclei proxy).

    Why it's useful
    ~~~~~~~~~~~~~~~
    The gold-standard rhythm typology metrics (%V, ΔC, ΔV from Ramus et al.
    1999; rPVI-C, nPVI-V from Grabe & Low 2002) require phoneme-level
    segmentation into vocalic (V) and consonantal (C) intervals.  WhisperX
    provides this via automatic forced alignment without requiring a
    pre-existing transcript.

    Best for: cross-linguistic rhythm comparison, Rhythm Class Hypothesis
    testing, detailed phonetic analysis of speech timing.
    Requires: whisperx package (``pip install whisperx``).

    Parameters
    ----------
    model_size : str
        Whisper model to use for transcription (same as whisper_words).
    language : str or None
        ISO language code.  Required for forced alignment (WhisperX needs
        it to select the correct alignment model).
    device : str
        Torch device: ``"cpu"`` or ``"cuda"``.
    """
    if not _HAS_WHISPERX:
        raise RuntimeError(
            "The 'whisperx_phonemes' onset method requires the whisperx package.\n"
            "Install it with:  pip install whisperx"
        )

    import torch

    # --- Step 1: Transcribe ---
    cache_attr = f"_whisperx_model_{model_size}"
    if not hasattr(detect_onsets_whisperx_phonemes, cache_attr):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            setattr(detect_onsets_whisperx_phonemes, cache_attr,
                    _whisperx_module.load_model(model_size, device=device))
    model = getattr(detect_onsets_whisperx_phonemes, cache_attr)

    # WhisperX expects float32 at 16 kHz
    if sr != 16000:
        audio_16k = librosa.resample(signal.astype(np.float32), orig_sr=sr, target_sr=16000)
    else:
        audio_16k = signal.astype(np.float32)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        result = model.transcribe(audio_16k, language=language)

    # Detect language if not specified
    detected_lang = language or result.get("language", "en")

    # --- Step 2: Forced alignment ---
    align_model, align_metadata = _whisperx_module.load_align_model(
        language_code=detected_lang, device=device
    )
    aligned = _whisperx_module.align(
        result["segments"], align_model, align_metadata,
        audio_16k, device=device, return_char_alignments=True,
    )

    # --- Step 3: Extract phoneme data ---
    phoneme_entries = []
    for seg in aligned.get("segments", []):
        for char_info in seg.get("chars", []):
            phone = char_info.get("char", "")
            start = char_info.get("start")
            end = char_info.get("end")
            if start is not None and end is not None and phone.strip():
                # Strip stress/length marks for vowel classification
                clean = phone.strip().replace("ˈ", "").replace("ˌ", "").replace("ː", "")
                is_vowel = clean in _VOWEL_PHONES
                phoneme_entries.append({
                    "phone": phone.strip(),
                    "start": float(start),
                    "end": float(end),
                    "is_vowel": is_vowel,
                })

    # --- Step 4: Compute Ramus metrics ---
    ramus = {}
    if phoneme_entries:
        v_durs = [e["end"] - e["start"] for e in phoneme_entries if e["is_vowel"]]
        c_durs = [e["end"] - e["start"] for e in phoneme_entries if not e["is_vowel"]]
        all_durs_ms = [(e["end"] - e["start"]) * 1000 for e in phoneme_entries]
        v_durs_ms = [d * 1000 for d in v_durs]
        c_durs_ms = [d * 1000 for d in c_durs]
        total_dur = sum(all_durs_ms)

        # %V: proportion of vocalic intervals
        if total_dur > 0:
            ramus["%V"] = round(100.0 * sum(v_durs_ms) / total_dur, 2)

        # ΔV, ΔC: standard deviation of V/C interval durations
        if len(v_durs_ms) >= 2:
            ramus["DeltaV (ms)"] = round(float(np.std(v_durs_ms)), 2)
        if len(c_durs_ms) >= 2:
            ramus["DeltaC (ms)"] = round(float(np.std(c_durs_ms)), 2)

        # rPVI-C: raw PVI for consonantal intervals
        if len(c_durs_ms) >= 2:
            c_arr = np.array(c_durs_ms)
            ramus["rPVI-C (ms)"] = round(float(np.mean(np.abs(np.diff(c_arr)))), 2)

        # nPVI-V: normalized PVI for vocalic intervals
        if len(v_durs_ms) >= 2:
            v_arr = np.array(v_durs_ms)
            v_diffs = np.abs(np.diff(v_arr))
            v_sums = np.array([v_arr[i] + v_arr[i + 1] for i in range(len(v_arr) - 1)])
            v_norms = np.where(v_sums > 0, v_diffs / (v_sums / 2.0), 0.0)
            ramus["nPVI-V (%)"] = round(float(100.0 * np.mean(v_norms)), 2)

    # Populate side-channels
    last_whisperx_phonemes.clear()
    last_whisperx_phonemes.extend(phoneme_entries)
    last_ramus_metrics.clear()
    last_ramus_metrics.update(ramus)

    # --- Step 5: Return vowel onsets as onset times ---
    onsets = [e["start"] for e in phoneme_entries if e["is_vowel"]]
    return np.array(sorted(set(onsets)), dtype=float)


# =====================================================================
# 10. MADMOM BEAT TRACKER  (Böck et al. 2016)
# =====================================================================

@_register("madmom_beats")
def detect_onsets_madmom_beats(
    signal, sr, *,
    min_bpm=40,
    max_bpm=240,
    fps=100,
    downbeats=False,
    transition_lambda=100,
    correct=True,
    num_tempi=60,
):
    """Detect beat positions using madmom's RNN beat processor + Dynamic
    Bayesian Network (DBN) beat tracker (Böck, Krebs & Widmer, 2016).

    This is the state-of-the-art deep-learning beat tracker, widely used in
    music information retrieval research.  It finds the *metrical pulse* of
    the audio — i.e. the underlying beat that listeners would tap to —
    rather than individual acoustic onsets.

    Parameters
    ----------
    signal : np.ndarray
        Mono audio signal (float, –1…1).
    sr : int
        Sample rate in Hz.
    min_bpm : float
        Minimum tempo hypothesis in BPM (default 40).
    max_bpm : float
        Maximum tempo hypothesis in BPM (default 240).
    fps : int
        Frames per second for the beat activation function (default 100 =
        10 ms resolution).
    downbeats : bool
        If True, also detect downbeats (bar-level "1"s) and populate the
        ``last_madmom_downbeats`` side-channel.
    transition_lambda : int
        DBN transition model parameter — higher = stricter tempo continuity,
        lower = more tempo flexibility (default 100).
    correct : bool
        Correct beats to nearest beat activation maximum (default True).
    num_tempi : int
        Number of tempo hypotheses for DBN (default 60).

    Returns
    -------
    np.ndarray
        Beat times in seconds (sorted, unique).

    Side-channels populated
    -----------------------
    ``last_madmom_tempo``  : dict  — ``{"BPM": float, "BPM_alt": float|None}``
    ``last_madmom_downbeats`` : np.ndarray  — downbeat times (if *downbeats* is True)
    """
    global last_madmom_tempo, last_madmom_downbeats

    if not _HAS_MADMOM:
        raise ImportError(
            "madmom is not installed.  Install it with:\n"
            "    pip install madmom\n"
            "See https://github.com/CPJKU/madmom for details."
        )

    import tempfile, soundfile as sf

    # madmom's RNNBeatProcessor expects a file path or a madmom Signal.
    # The safest cross-version approach is to write a temporary WAV file.
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        _tmp_path = tmp.name
    try:
        sf.write(_tmp_path, signal, sr, subtype="FLOAT")

        # --- Beat activation ---
        beat_proc = _madmom_module.features.beats.RNNBeatProcessor()
        act = beat_proc(_tmp_path)

        # --- Beat tracking via DBN ---
        dbn = _madmom_module.features.beats.DBNBeatTrackingProcessor(
            min_bpm=min_bpm,
            max_bpm=max_bpm,
            fps=fps,
            transition_lambda=transition_lambda,
            correct=correct,
            num_tempi=num_tempi,
        )
        beats = dbn(act)
        beats = np.asarray(beats, dtype=float)

        # --- Tempo estimation ---
        try:
            tempo_proc = _madmom_module.features.tempo.TempoEstimationProcessor(fps=fps)
            tempi = tempo_proc(act)  # shape (N, 2): [[bpm, strength], ...]
            if len(tempi) >= 1:
                last_madmom_tempo["BPM"] = float(tempi[0][0])
            if len(tempi) >= 2:
                last_madmom_tempo["BPM_alt"] = float(tempi[1][0])
            else:
                last_madmom_tempo["BPM_alt"] = None
        except Exception:
            if len(beats) >= 2:
                iois = np.diff(beats)
                median_ioi = float(np.median(iois))
                last_madmom_tempo["BPM"] = 60.0 / median_ioi if median_ioi > 0 else 0.0
                last_madmom_tempo["BPM_alt"] = None
            else:
                last_madmom_tempo = {"BPM": 0.0, "BPM_alt": None}

        # --- Optional downbeat tracking ---
        last_madmom_downbeats = np.array([], dtype=float)
        if downbeats and len(beats) >= 2:
            try:
                db_proc = _madmom_module.features.beats.RNNDownBeatProcessor()
                db_act = db_proc(_tmp_path)
                db_dbn = _madmom_module.features.downbeats.DBNDownBeatTrackingProcessor(
                    beats_per_bar=[3, 4],
                    fps=fps,
                )
                db_result = db_dbn(db_act)
                # db_result rows: [time, beat_position].  Downbeats have position 1.
                if len(db_result) > 0:
                    db_times = np.asarray(
                        [row[0] for row in db_result if int(row[1]) == 1],
                        dtype=float,
                    )
                    last_madmom_downbeats = db_times
            except Exception:
                pass  # downbeat tracking is optional; beat times are still valid

    finally:
        import os
        os.unlink(_tmp_path)

    return beats


# =====================================================================
# STANDALONE PITCH TRACKER  (independent of onset method)
# =====================================================================

def extract_pitch_metrics(signal, sr, method="pyin", *, fmin=65.0, fmax=1047.0):
    """Extract fundamental frequency (F0) metrics from an audio signal.

    This is a standalone pitch tracker that can run after *any* onset
    detection method.  It populates ``last_f0_metrics`` with the same
    keys used by the Praat-based extraction inside ``syllable_nuclei``,
    so downstream consumers (Excel export, GUI) work unchanged.

    Parameters
    ----------
    signal : np.ndarray
        Mono audio signal (float, -1…1).
    sr : int
        Sample rate in Hz.
    method : str
        ``"pyin"``  — probabilistic YIN via librosa (Mauch & Dixon, 2014).
        ``"crepe"`` — CREPE neural pitch tracker via torchcrepe (Kim et al., 2018).
        ``"praat"`` — Praat autocorrelation via parselmouth.
    fmin : float
        Minimum expected F0 in Hz (default 65 ≈ C2).
    fmax : float
        Maximum expected F0 in Hz (default 1047 ≈ C6).

    Returns
    -------
    dict
        Pitch metrics dict (also written to ``last_f0_metrics``).
    """
    if method == "pyin":
        return _extract_pitch_pyin(signal, sr, fmin=fmin, fmax=fmax)
    elif method == "crepe":
        return _extract_pitch_crepe(signal, sr, fmin=fmin, fmax=fmax)
    elif method == "praat":
        return _extract_pitch_praat(signal, sr, fmin=fmin, fmax=fmax)
    else:
        raise ValueError(f"Unknown pitch tracking method: {method!r}")


def _f0_summary(f0_vals, signal, sr):
    """Compute summary statistics from an array of voiced F0 values.

    Returns a dict with the standard F0 metric keys.
    """
    metrics = {}
    if len(f0_vals) < 2:
        return metrics

    f0_arr = np.asarray(f0_vals, dtype=float)
    metrics["F0 Mean (Hz)"] = round(float(np.mean(f0_arr)), 2)
    metrics["F0 Std (Hz)"] = round(float(np.std(f0_arr)), 2)
    metrics["F0 Min (Hz)"] = round(float(np.min(f0_arr)), 2)
    metrics["F0 Max (Hz)"] = round(float(np.max(f0_arr)), 2)
    metrics["F0 Range (Hz)"] = round(float(np.max(f0_arr) - np.min(f0_arr)), 2)

    # Jitter (local): average absolute period-to-period difference / mean period
    periods = 1.0 / f0_arr
    if len(periods) >= 2:
        abs_diffs = np.abs(np.diff(periods))
        jitter = float(np.mean(abs_diffs) / np.mean(periods))
        metrics["Jitter (local)"] = round(jitter, 6)

    # Intensity: RMS energy in dB
    rms = np.sqrt(np.mean(signal ** 2))
    if rms > 0:
        db = 20.0 * np.log10(rms + 1e-12)
        metrics["Intensity Mean (dB)"] = round(float(db), 2)
        # Windowed RMS for Std
        hop = max(1, len(signal) // 100)
        frame_len = max(hop, int(0.03 * sr))  # ~30 ms frames
        rms_frames = []
        for i in range(0, len(signal) - frame_len, hop):
            rms_frames.append(np.sqrt(np.mean(signal[i:i + frame_len] ** 2)))
        if rms_frames:
            db_frames = 20.0 * np.log10(np.array(rms_frames) + 1e-12)
            metrics["Intensity Std (dB)"] = round(float(np.std(db_frames)), 2)

    return metrics


def _extract_pitch_pyin(signal, sr, *, fmin=65.0, fmax=1047.0):
    """pYIN pitch tracker (Mauch & Dixon, 2014) via librosa."""
    import librosa
    f0, voiced_flag, voiced_probs = librosa.pyin(
        signal, fmin=fmin, fmax=fmax, sr=sr,
    )
    f0_voiced = f0[~np.isnan(f0)]
    metrics = _f0_summary(f0_voiced, signal, sr)
    metrics["Pitch Tracker"] = "pyin"
    last_f0_metrics.clear()
    last_f0_metrics.update(metrics)
    return metrics


def _extract_pitch_crepe(signal, sr, *, fmin=65.0, fmax=1047.0):
    """CREPE neural pitch tracker (Kim et al., 2018) via torchcrepe."""
    if not _HAS_TORCHCREPE:
        raise ImportError(
            "torchcrepe is not installed.  Install it with:\n"
            "    pip install torchcrepe\n"
            "See https://github.com/maxrmorrison/torchcrepe"
        )
    audio_tensor = _torch_module.tensor(
        signal, dtype=_torch_module.float32,
    ).unsqueeze(0)
    device = "cpu"
    # CREPE predict: returns pitch tensor in Hz
    pitch = _torchcrepe_module.predict(
        audio_tensor, sr,
        hop_length=int(sr * 0.01),  # 10 ms hop
        fmin=fmin, fmax=fmax,
        model="tiny",
        batch_size=2048,
        device=device,
        pad=True,
    )
    # Get periodicity for voicing decision
    periodicity = _torchcrepe_module.filter.median(
        _torchcrepe_module.periodicity(audio_tensor, sr, pitch, device=device),
        3,
    )
    pitch_np = pitch.squeeze().cpu().numpy()
    period_np = periodicity.squeeze().cpu().numpy()
    # Keep only voiced frames (periodicity > 0.5) within fmin..fmax
    voiced_mask = (period_np > 0.5) & (pitch_np >= fmin) & (pitch_np <= fmax)
    f0_voiced = pitch_np[voiced_mask]
    metrics = _f0_summary(f0_voiced, signal, sr)
    metrics["Pitch Tracker"] = "crepe"
    last_f0_metrics.clear()
    last_f0_metrics.update(metrics)
    return metrics


def _extract_pitch_praat(signal, sr, *, fmin=65.0, fmax=1047.0):
    """Praat autocorrelation pitch tracker via parselmouth."""
    if not _HAS_PARSELMOUTH:
        raise ImportError(
            "parselmouth is not installed.  Install it with:\n"
            "    pip install praat-parselmouth"
        )
    import parselmouth
    from parselmouth.praat import call as praat_call

    snd = parselmouth.Sound(signal, sampling_frequency=sr)
    pitch = snd.to_pitch(pitch_floor=fmin, pitch_ceiling=fmax)
    n_frames = pitch.get_number_of_frames()
    f0_vals = []
    for i in range(n_frames):
        t = pitch.get_time_from_frame_number(i + 1)
        try:
            f0 = praat_call(pitch, "Get value at time", t, "Hertz", "Linear")
        except Exception:
            f0 = 0.0
        if f0 is not None and not np.isnan(f0) and f0 > 0:
            f0_vals.append(f0)
    metrics = _f0_summary(np.array(f0_vals) if f0_vals else np.array([]),
                          signal, sr)
    # Praat-specific: Jitter via PointProcess (more accurate than period-based)
    try:
        pp = praat_call(snd, "To PointProcess (periodic, cc)", fmin, fmax)
        jitter = praat_call(pp, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
        if jitter is not None and not np.isnan(jitter):
            metrics["Jitter (local)"] = round(float(jitter), 6)
    except Exception:
        pass
    # Praat intensity statistics
    try:
        intensity = snd.to_intensity()
        int_vals = intensity.values.flatten()
        int_vals = int_vals[np.isfinite(int_vals)]
        if len(int_vals) > 0:
            metrics["Intensity Mean (dB)"] = round(float(np.mean(int_vals)), 2)
            metrics["Intensity Std (dB)"] = round(float(np.std(int_vals)), 2)
    except Exception:
        pass
    metrics["Pitch Tracker"] = "praat"
    last_f0_metrics.clear()
    last_f0_metrics.update(metrics)
    return metrics


# =====================================================================
# SAMPLE-LEVEL REFINEMENT  (method-agnostic)
# =====================================================================

def refine_onsets_to_sample(onset_times, signal, sr, window_ms=10, energy_gate=0.0):
    """Refine coarse onset times to sample accuracy using the Hilbert envelope.

    This is the **Stage 2** refinement that runs after any coarse detector.
    It is method-agnostic — no matter which ``ONSET_METHOD`` you choose, this
    function gives the same sub-millisecond precision.

    How it works
    ~~~~~~~~~~~~
    For each coarse onset time, extracts a ±*window_ms* neighbourhood from
    the audio, computes the Hilbert analytic-signal amplitude envelope, takes
    the first-difference of that envelope, and finds the sample with the
    largest positive difference (the steepest energy rise).  That sample
    becomes the refined onset time.

    At 44.1 kHz: 1 sample ≈ 0.023 ms, so the final precision is ~0.023 ms
    regardless of the coarse detector's resolution.

    Parameters
    ----------
    onset_times : np.ndarray
        Coarse onset times (seconds) from any detector.

    signal : np.ndarray
        The full audio signal (same one passed to the detector).

    sr : int
        Sample rate in Hz.

    window_ms : float
        Half-width of the search window (ms) around each coarse onset.

        - 5 ms — narrow.  Use when you're confident the coarse detector
          lands very close to the true onset (e.g. adaptive_hp at 1 ms hop).
        - 10 ms (default) — safe for most detectors.
        - 20 ms — wide.  Use if the coarse detector has poor resolution
          (e.g. librosa at hop_length=512, ~11.6 ms grid).

        **When to change:** If refined onsets seem to snap to the wrong
        transient (e.g. a pre-echo before the real attack), narrow this.
        If the coarse detector lands far from the true onset and refinement
        doesn't reach it, widen this.

    energy_gate : float
        Local energy ratio threshold (0.0–1.0).

        - 0.0 (default) — disabled.  Every onset is refined.
        - 0.05–0.10 — onsets in very quiet regions (below this fraction of
          the file's peak envelope) keep their coarse time instead of being
          refined.  Prevents "snapping to noise" in silent passages.
        - 0.2+ — aggressive gating.  Only onsets in loud regions are refined.

        **When to change:** If refined onsets in quiet passages seem to jump
        to random positions (noise), enable this with a small value like 0.05.
    """
    if len(onset_times) == 0:
        return onset_times

    n_samples = len(signal)
    window_samples = int(sr * window_ms / 1000.0)

    analytic_full = hilbert(signal)
    envelope_full = np.abs(analytic_full)
    peak_envelope = float(np.max(envelope_full))

    refined = np.empty_like(onset_times, dtype=float)

    for i, t in enumerate(onset_times):
        centre = int(round(t * sr))
        lo = max(centre - window_samples, 0)
        hi = min(centre + window_samples + 1, n_samples)

        segment_env = envelope_full[lo:hi]

        if energy_gate > 0 and peak_envelope > 0:
            if float(np.max(segment_env)) < energy_gate * peak_envelope:
                refined[i] = t
                continue

        env_diff = np.diff(segment_env)
        if len(env_diff) == 0:
            refined[i] = t
            continue

        best_local = int(np.argmax(env_diff))
        refined_sample = lo + best_local
        refined[i] = refined_sample / sr

    return refined
