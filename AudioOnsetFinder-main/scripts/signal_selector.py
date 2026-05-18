"""Interactive spectrogram signal selector for bioacoustics analysis.

Opens a matplotlib spectrogram view of an audio file and lets the user draw
rectangular regions around the signals of interest.  The selected regions are
saved as a **signal profile** JSON that downstream analyzers (audio_analyzer.py,
onset_analyzer.py) use to recommend optimal pipeline settings.

The spectrogram is displayed in 10-second chunks for performance.  Use the
◀ / ▶ buttons (or left/right arrow keys) to navigate chunks.  Use the play
buttons to audition the current chunk or a selected region.

Usage (standalone):
    python scripts/signal_selector.py path/to/audio.wav
    python scripts/signal_selector.py path/to/audio.wav -o profile.json

The GUI integrates this via ``select_signal_regions()`` which returns the
profile dict directly.
"""

import argparse
import json
import os
import sys
import threading

import librosa
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.widgets import Button, RectangleSelector
import numpy as np

try:
    import sounddevice as sd
    _HAS_SD = True
except ImportError:
    _HAS_SD = False


_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from analysis.signal_profiles import (
    analyze_region as _analyze_region_impl,
    build_per_signal_profiles as _build_per_signal_profiles_impl,
    build_signal_profile as _build_signal_profile_impl,
    cluster_signal_regions as _cluster_signal_regions_impl,
    compute_spectrogram as _compute_spectrogram_impl,
)


# ─────────────────────────────────────────────────────────────────────
# Core analysis helpers
# ─────────────────────────────────────────────────────────────────────

def compute_spectrogram(y, sr, n_fft=2048, hop_length=512):
    """Return log-power spectrogram, frequencies, and times arrays."""
    return _compute_spectrogram_impl(y, sr, n_fft=n_fft, hop_length=hop_length)


def analyze_region(y, sr, t_start, t_end, f_low, f_high, n_fft=2048,
                   hop_length=512):
    """Extract spectral and temporal features from a selected region."""
    return _analyze_region_impl(
        y,
        sr,
        t_start,
        t_end,
        f_low,
        f_high,
        n_fft=n_fft,
        hop_length=hop_length,
    )


def build_signal_profile(y, sr, regions):
    """Build a complete signal profile from a list of selected regions.

    Parameters
    ----------
    y : np.ndarray
        Full audio signal.
    sr : int
        Sample rate.
    regions : list[dict]
        Each dict has keys: t_start, t_end, f_low, f_high.

    Returns
    -------
    dict
        Signal profile with per-region analysis and aggregate summary.
    """
    return _build_signal_profile_impl(y, sr, regions)


def build_per_signal_profiles(y, sr, regions):
    """Build individual signal profiles for each region separately.

    Unlike :func:`build_signal_profile` which aggregates across all regions,
    this returns a list of per-region profile dicts so that each region's
    acoustic characteristics can be inspected and tuned independently.

    Parameters
    ----------
    y : np.ndarray
        Full audio signal.
    sr : int
        Sample rate.
    regions : list[dict]
        Each dict must have keys: t_start, t_end, f_low, f_high, polarity.

    Returns
    -------
    list[dict]
        One dict per region with keys:
        ``analysis`` (output of :func:`analyze_region`),
        ``region`` (the original region dict),
        ``index`` (0-based position in the input list).
    """
    return _build_per_signal_profiles_impl(y, sr, regions)


def cluster_signal_regions(region_analyses: list[dict], max_clusters: int = 6) -> dict:
    """Cluster analysed positive regions by spectral similarity.

    Uses agglomerative clustering on normalised spectral features
    (centroid, bandwidth, harmonicity, attack_sharpness) with an
    automatic cluster-count selection based on the gap between
    successive merge distances.

    Parameters
    ----------
    region_analyses : list[dict]
        Per-region analysis dicts as returned by :func:`build_signal_profile`
        (each must have ``spectral_centroid_hz``, ``spectral_bandwidth_hz``,
        ``harmonicity``, ``attack_sharpness``).
    max_clusters : int
        Upper bound on the number of clusters to consider.

    Returns
    -------
    dict
        ``{"n_clusters": int, "labels": list[int], "descriptions": list[str]}``
        where *labels[i]* is the 0-based cluster id for region *i* and
        *descriptions[j]* is a human-readable summary of cluster *j*.
    """
    return _cluster_signal_regions_impl(region_analyses, max_clusters=max_clusters)


# ─────────────────────────────────────────────────────────────────────
# Audio playback helpers
# ─────────────────────────────────────────────────────────────────────

_playback_lock = threading.Lock()
_playback_start_time = 0.0      # absolute time (s) in the full file
_playback_start_wall = 0.0      # wall-clock when playback started
_playback_duration = 0.0        # duration of the clip being played
_playback_active = False


def _play_audio(y, sr, file_offset=0.0):
    """Play a mono audio signal.  *file_offset* is the absolute time in
    the source file that sample 0 of *y* corresponds to (used by the
    playback bar)."""
    global _playback_start_time, _playback_start_wall
    global _playback_duration, _playback_active
    if not _HAS_SD:
        return
    import time as _time
    with _playback_lock:
        sd.stop()
        _playback_start_time = file_offset
        _playback_start_wall = _time.time()
        _playback_duration = len(y) / sr
        _playback_active = True
        sd.play(y.astype(np.float32), samplerate=sr)


def _stop_audio():
    """Stop any currently playing audio."""
    global _playback_active
    if _HAS_SD:
        try:
            sd.stop()
        except Exception:
            pass
    _playback_active = False


def _current_playback_time():
    """Return the current playback position as absolute file time (s),
    or *None* if nothing is playing."""
    import time as _time
    with _playback_lock:
        if not _playback_active:
            return None
        elapsed = _time.time() - _playback_start_wall
        if elapsed > _playback_duration:
            return None
        return _playback_start_time + elapsed


def _bandpass_segment(y, sr, f_low, f_high):
    """Extract frequency-band filtered version of a signal for audition."""
    from scipy.signal import butter, sosfilt
    nyq = sr / 2
    lo = max(f_low, 20) / nyq
    hi = min(f_high, nyq - 1) / nyq
    if lo >= hi or lo <= 0 or hi >= 1:
        return y
    sos = butter(4, [lo, hi], btype="band", output="sos")
    return sosfilt(sos, y)


# ─────────────────────────────────────────────────────────────────────
# Interactive spectrogram selector (matplotlib)
# ─────────────────────────────────────────────────────────────────────

CHUNK_SECONDS = 10  # duration of each displayed chunk


def _unique_path(path):
    """Return *path* if it doesn't exist, otherwise append _1, _2, ... before
    the extension until a free name is found."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 1
    while True:
        candidate = f"{base}_{counter}{ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


class SpectrogramSelector:
    """Interactive matplotlib figure for selecting signal regions on a spectrogram.

    Displays the audio in CHUNK_SECONDS-second pages for performance.
    Provides navigation, audio playback with a scrub bar, and dedicated
    buttons for adding selections to the signal profile and saving
    selections as individual WAV files.
    """

    def __init__(self, y, sr, n_fft=2048, hop_length=512, source_path=None):
        self.y = y
        self.sr = sr
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.source_path = source_path  # original file path (for Save)

        # Selection mode: "positive" (green) or "negative" (red)
        self._selection_mode = "positive"

        # Pending rectangles on the current view (not yet committed)
        self._pending_regions = []       # positive pending
        self._pending_neg_regions = []   # negative pending

        # Committed regions that form the signal profile
        self.profile_regions = []        # positive committed
        self.negative_regions = []       # negative committed
        self._profile = None

        # Callback used by Qt dialog to close the window (instead of plt.close)
        self._close_callback = None

        self.total_duration = len(y) / sr
        self.n_chunks = max(1, int(np.ceil(self.total_duration / CHUNK_SECONDS)))
        self._chunk_idx = 0

    # ---- chunk helpers ----

    def _chunk_time_range(self, idx=None):
        if idx is None:
            idx = self._chunk_idx
        t0 = idx * CHUNK_SECONDS
        t1 = min(t0 + CHUNK_SECONDS, self.total_duration)
        return t0, t1

    def _chunk_samples(self, idx=None):
        t0, t1 = self._chunk_time_range(idx)
        return int(t0 * self.sr), int(t1 * self.sr)

    # ---- drawing ----

    def _draw_chunk(self):
        """Compute spectrogram for the current chunk and redraw."""
        ax = self.ax_spec
        ax.clear()

        t0, t1 = self._chunk_time_range()
        s0, s1 = self._chunk_samples()
        chunk_y = self.y[s0:s1]

        S_db, freqs, times = compute_spectrogram(
            chunk_y, self.sr, self.n_fft, self.hop_length)

        ax.imshow(S_db, aspect='auto', origin='lower', cmap='magma',
                  extent=[t0, t0 + CHUNK_SECONDS, freqs[0], freqs[-1]])
        ax.set_ylabel("Frequency (Hz)")
        ax.set_xlabel("Time (s)")
        ax.set_xlim(t0, t0 + CHUNK_SECONDS)
        ax.set_title(
            f"Chunk {self._chunk_idx + 1} / {self.n_chunks}   "
            f"({t0:.1f}s – {t1:.1f}s of {self.total_duration:.1f}s)")

        # Draw committed positive (profile) regions — blue
        for i, region in enumerate(self.profile_regions):
            if region["t_end"] > t0 and region["t_start"] < t0 + CHUNK_SECONDS:
                vis_t0 = max(region["t_start"], t0)
                vis_t1 = min(region["t_end"], t0 + CHUNK_SECONDS)
                rect = patches.Rectangle(
                    (vis_t0, region["f_low"]),
                    vis_t1 - vis_t0,
                    region["f_high"] - region["f_low"],
                    linewidth=2, edgecolor="#2196f3", facecolor="#2196f3",
                    alpha=0.25,
                )
                ax.add_patch(rect)
                ax.text(
                    vis_t0 + (vis_t1 - vis_t0) / 2,
                    region["f_high"] + 20,
                    f"+P{i + 1}", fontsize=8, color="#2196f3",
                    ha="center", va="bottom",
                    bbox=dict(boxstyle="round,pad=0.2",
                              facecolor="black", alpha=0.5),
                )

        # Draw committed negative regions — dark red
        for i, region in enumerate(self.negative_regions):
            if region["t_end"] > t0 and region["t_start"] < t0 + CHUNK_SECONDS:
                vis_t0 = max(region["t_start"], t0)
                vis_t1 = min(region["t_end"], t0 + CHUNK_SECONDS)
                rect = patches.Rectangle(
                    (vis_t0, region["f_low"]),
                    vis_t1 - vis_t0,
                    region["f_high"] - region["f_low"],
                    linewidth=2, edgecolor="#d32f2f", facecolor="#d32f2f",
                    alpha=0.25,
                )
                ax.add_patch(rect)
                ax.text(
                    vis_t0 + (vis_t1 - vis_t0) / 2,
                    region["f_high"] + 20,
                    f"\u2212N{i + 1}", fontsize=8, color="#ef5350",
                    ha="center", va="bottom",
                    bbox=dict(boxstyle="round,pad=0.2",
                              facecolor="black", alpha=0.5),
                )

        # Draw pending positive selections — green
        for i, region in enumerate(self._pending_regions):
            if region["t_end"] > t0 and region["t_start"] < t0 + CHUNK_SECONDS:
                vis_t0 = max(region["t_start"], t0)
                vis_t1 = min(region["t_end"], t0 + CHUNK_SECONDS)
                rect = patches.Rectangle(
                    (vis_t0, region["f_low"]),
                    vis_t1 - vis_t0,
                    region["f_high"] - region["f_low"],
                    linewidth=2, edgecolor="#4caf50", facecolor="#4caf50",
                    alpha=0.25,
                )
                ax.add_patch(rect)
                ax.text(
                    vis_t0 + (vis_t1 - vis_t0) / 2,
                    region["f_high"] + 20,
                    f"+R{i + 1}", fontsize=8, color="#4caf50",
                    ha="center", va="bottom",
                    bbox=dict(boxstyle="round,pad=0.2",
                              facecolor="black", alpha=0.5),
                )

        # Draw pending negative selections — red
        for i, region in enumerate(self._pending_neg_regions):
            if region["t_end"] > t0 and region["t_start"] < t0 + CHUNK_SECONDS:
                vis_t0 = max(region["t_start"], t0)
                vis_t1 = min(region["t_end"], t0 + CHUNK_SECONDS)
                rect = patches.Rectangle(
                    (vis_t0, region["f_low"]),
                    vis_t1 - vis_t0,
                    region["f_high"] - region["f_low"],
                    linewidth=2, edgecolor="#f44336", facecolor="#f44336",
                    alpha=0.25,
                )
                ax.add_patch(rect)
                ax.text(
                    vis_t0 + (vis_t1 - vis_t0) / 2,
                    region["f_high"] + 20,
                    f"\u2212R{i + 1}", fontsize=8, color="#f44336",
                    ha="center", va="bottom",
                    bbox=dict(boxstyle="round,pad=0.2",
                              facecolor="black", alpha=0.5),
                )

        # Mode indicator
        mode_color = "#4caf50" if self._selection_mode == "positive" else "#f44336"
        mode_label = ("\u2795 POSITIVE (target sounds)"
                      if self._selection_mode == "positive"
                      else "\u2796 NEGATIVE (sounds to suppress)")
        ax.text(
            0.5, 0.97, mode_label,
            transform=ax.transAxes, fontsize=10, color=mode_color,
            ha="center", va="top", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.7),
        )

        # Instruction overlay
        ax.text(
            0.02, 0.02,
            "Drag: select  |  U: undo  |  T: toggle +/\u2212  |  \u2190/\u2192: chunks  |  Enter: done",
            transform=ax.transAxes, fontsize=9, color="white",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.6),
            verticalalignment="bottom",
        )
        self._status = ax.text(
            0.98, 0.02,
            self._status_text(),
            transform=ax.transAxes, fontsize=9, color="#4caf50", ha="right",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.6),
            verticalalignment="bottom",
        )

        self.fig.canvas.draw_idle()

    def _status_text(self):
        parts = []
        pending_pos = len(self._pending_regions)
        pending_neg = len(self._pending_neg_regions)
        if pending_pos or pending_neg:
            pend_parts = []
            if pending_pos:
                pend_parts.append(f"{pending_pos}+ pending")
            if pending_neg:
                pend_parts.append(f"{pending_neg}\u2212 pending")
            parts.append(", ".join(pend_parts))
        parts.append(f"{len(self.profile_regions)}+ in profile")
        if self.negative_regions:
            parts.append(f"{len(self.negative_regions)}\u2212 to suppress")
        return "  |  ".join(parts)

    def _update_status(self):
        if hasattr(self, '_status'):
            self._status.set_text(self._status_text())
            self.fig.canvas.draw_idle()

    # ---- playback bar ----

    def _draw_playback_bar(self):
        """Draw / update the playback scrub bar axis."""
        ax = self.ax_bar
        ax.clear()
        t0, t1 = self._chunk_time_range()
        ax.set_xlim(t0, t0 + CHUNK_SECONDS)
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        ax.set_xlabel("")
        ax.patch.set_facecolor("#1a1a2e")

        # Chunk background
        ax.axhspan(0, 1, xmin=0, xmax=1, color="#2a2a3e")

        # Shade pending positive regions
        for r in self._pending_regions:
            if r["t_end"] > t0 and r["t_start"] < t0 + CHUNK_SECONDS:
                ax.axvspan(max(r["t_start"], t0), min(r["t_end"], t0 + CHUNK_SECONDS),
                           color="#4caf50", alpha=0.3)

        # Shade pending negative regions
        for r in self._pending_neg_regions:
            if r["t_end"] > t0 and r["t_start"] < t0 + CHUNK_SECONDS:
                ax.axvspan(max(r["t_start"], t0), min(r["t_end"], t0 + CHUNK_SECONDS),
                           color="#f44336", alpha=0.3)

        # Shade committed profile regions
        for r in self.profile_regions:
            if r["t_end"] > t0 and r["t_start"] < t0 + CHUNK_SECONDS:
                ax.axvspan(max(r["t_start"], t0), min(r["t_end"], t0 + CHUNK_SECONDS),
                           color="#2196f3", alpha=0.3)

        # Shade committed negative regions
        for r in self.negative_regions:
            if r["t_end"] > t0 and r["t_start"] < t0 + CHUNK_SECONDS:
                ax.axvspan(max(r["t_start"], t0), min(r["t_end"], t0 + CHUNK_SECONDS),
                           color="#d32f2f", alpha=0.3)

        # Playback cursor
        pos = _current_playback_time()
        if pos is not None and t0 <= pos <= t0 + CHUNK_SECONDS:
            self._cursor_line = ax.axvline(pos, color="white", linewidth=2)
        else:
            self._cursor_line = None

        self.fig.canvas.draw_idle()

    def _tick_playback_bar(self):
        """Called periodically by a timer to update the playback cursor."""
        if not hasattr(self, 'ax_bar'):
            return
        pos = _current_playback_time()
        t0, _ = self._chunk_time_range()

        had_cursor = (hasattr(self, '_cursor_line')
                      and self._cursor_line is not None)
        needs_cursor = (pos is not None
                        and t0 <= pos <= t0 + CHUNK_SECONDS)

        if not had_cursor and not needs_cursor:
            return  # nothing changed — skip redraw

        # Remove old cursor
        if had_cursor:
            try:
                self._cursor_line.remove()
            except Exception:
                pass
            self._cursor_line = None

        if needs_cursor:
            self._cursor_line = self.ax_bar.axvline(
                pos, color="white", linewidth=2)

        self.fig.canvas.draw_idle()

    def _on_bar_click(self, event):
        """Seek playback to clicked position on the scrub bar."""
        if event.inaxes != self.ax_bar:
            return
        if event.button != 1:
            return
        click_t = event.xdata
        if click_t is None:
            return
        t0, t1 = self._chunk_time_range()
        click_t = max(t0, min(click_t, t1))
        s_start = int(click_t * self.sr)
        s_end = int(t1 * self.sr)
        if s_end <= s_start:
            return
        _play_audio(self.y[s_start:s_end], self.sr, file_offset=click_t)

    # ---- main entry ----

    def _setup_figure(self, fig=None):
        """Create the figure, axes, buttons, selectors, and key bindings.

        Parameters
        ----------
        fig : matplotlib.figure.Figure, optional
            Pre-created figure (e.g. from a Qt canvas).  When *None* a
            pyplot-managed figure is created (suitable for CLI usage).
        """
        if fig is None:
            fig = plt.figure(figsize=(14, 8))

        # Main spectrogram axes and playback bar
        self.ax_spec = fig.add_axes([0.07, 0.22, 0.88, 0.65])
        self.ax_bar = fig.add_axes([0.07, 0.14, 0.88, 0.04])
        self.fig = fig

        fig.suptitle(
            "Signal Selector \u2014 Draw rectangles, then click "
            "'Add to Profile' to commit them\n"
            "(Green = target sounds  \u2022  Red = sounds to suppress  \u2022  "
            "Blue = committed positive  \u2022  Dark red = committed negative)",
            fontsize=11, y=0.98,
        )

        # Initial draw
        self._draw_chunk()
        self._draw_playback_bar()

        # Rectangle selector — start in positive (green) mode
        self._selector = RectangleSelector(
            self.ax_spec, self._on_select, useblit=True,
            button=[1],
            minspanx=0.01, minspany=10,
            spancoords="data",
            interactive=False,
            props=dict(facecolor="#4caf50", alpha=0.3, edgecolor="#4caf50",
                       linewidth=2),
        )

        # -- Bottom button bar --
        btn_h = 0.04
        btn_y = 0.025
        x = 0.02

        def _btn(pos_x, w, label):
            ax_b = fig.add_axes([pos_x, btn_y, w, btn_h])
            return Button(ax_b, label)

        # Mode toggle — starts green (positive)
        self._btn_mode = _btn(x, 0.12, "\u2795 Target Sound"); x += 0.125
        self._btn_mode.on_clicked(self._toggle_mode)
        self._btn_mode.ax.set_facecolor("#2e7d32")
        self._btn_mode.label.set_color("white")
        self._btn_mode.label.set_fontweight("bold")

        self._btn_prev = _btn(x, 0.06, "\u25c0 Prev"); x += 0.065
        self._btn_prev.on_clicked(self._go_prev)

        self._btn_next = _btn(x, 0.06, "Next \u25b6"); x += 0.07
        self._btn_next.on_clicked(self._go_next)

        # -- Add to Profile --
        self._btn_add = _btn(x, 0.12, "\u2605 Add to Profile"); x += 0.13
        self._btn_add.on_clicked(self._add_to_profile)
        self._btn_add.ax.set_facecolor("#2e7d32")
        self._btn_add.label.set_color("white")
        self._btn_add.label.set_fontweight("bold")

        # -- Save Selections --
        self._btn_save = _btn(x, 0.11, "\U0001f4be Save Selections"); x += 0.12
        self._btn_save.on_clicked(self._save_selections)

        if _HAS_SD:
            self._btn_play = _btn(x, 0.08, "\u25b6 Chunk"); x += 0.085
            self._btn_play.on_clicked(self._play_chunk)

            self._btn_play_sel = _btn(x, 0.09, "\u25b6 Selection"); x += 0.095
            self._btn_play_sel.on_clicked(self._play_last_selection)

            self._btn_stop = _btn(x, 0.06, "\u23f9 Stop"); x += 0.07
            self._btn_stop.on_clicked(lambda _: _stop_audio())

        # Key bindings + bar click
        fig.canvas.mpl_connect("key_press_event", self._on_key)
        fig.canvas.mpl_connect("button_press_event", self._on_bar_click)

        # Playback cursor timer (~10 fps)
        self._timer = fig.canvas.new_timer(interval=100)
        self._timer.add_callback(self._tick_playback_bar)
        self._timer.start()

    def _finalize(self):
        """Stop timer/audio and build the signal profile from committed regions."""
        _stop_audio()
        if hasattr(self, '_timer'):
            self._timer.stop()
        self._profile = build_signal_profile(
            self.y, self.sr, self.profile_regions)
        # Build negative profile and attach it
        if self.negative_regions:
            neg_profile = build_signal_profile(
                self.y, self.sr, self.negative_regions)
            self._profile["negative_regions"] = neg_profile.get("regions", [])
            self._profile["negative_summary"] = neg_profile.get("summary", {})
        else:
            self._profile["negative_regions"] = []
            self._profile["negative_summary"] = {}
        return self._profile

    def run(self):
        """Open the interactive selector window (blocking).  Returns signal profile dict.

        Use this for CLI / standalone usage where no Qt event loop is running.
        """
        self._setup_figure()
        plt.show()
        return self._finalize()

    def run_async(self, on_done=None):
        """Open the selector window non-blocking (for use inside a Qt app).

        Parameters
        ----------
        on_done : callable or None
            Called with the signal profile dict when the user closes the window.
        """
        self._on_done_callback = on_done
        self._setup_figure()

        # Connect the figure close event so we finalize when the window closes
        self.fig.canvas.mpl_connect("close_event", self._on_figure_closed)
        plt.show(block=False)

    def _on_figure_closed(self, _event=None):
        """Handle the matplotlib figure being closed."""
        profile = self._finalize()
        if self._on_done_callback is not None:
            self._on_done_callback(profile)

    # ---- Add / Save callbacks ----

    def _toggle_mode(self, _event=None):
        """Switch between positive (target) and negative (suppress) selection modes."""
        if self._selection_mode == "positive":
            self._selection_mode = "negative"
            self._btn_mode.label.set_text("\u2796 Suppress Sound")
            self._btn_mode.ax.set_facecolor("#c62828")
            # Update rectangle selector color to red
            self._selector.artists[0].set_edgecolor("#f44336")
            self._selector.artists[0].set_facecolor("#f44336")
        else:
            self._selection_mode = "positive"
            self._btn_mode.label.set_text("\u2795 Target Sound")
            self._btn_mode.ax.set_facecolor("#2e7d32")
            self._selector.artists[0].set_edgecolor("#4caf50")
            self._selector.artists[0].set_facecolor("#4caf50")
        self._draw_chunk()
        self.fig.canvas.draw_idle()

    def _add_to_profile(self, _event=None):
        """Commit all pending selections (positive and negative) to the profile."""
        n_pos = len(self._pending_regions)
        n_neg = len(self._pending_neg_regions)
        if not n_pos and not n_neg:
            return
        self.profile_regions.extend(self._pending_regions)
        self.negative_regions.extend(self._pending_neg_regions)
        self._pending_regions = []
        self._pending_neg_regions = []
        self._draw_chunk()
        self._draw_playback_bar()
        parts = []
        if n_pos:
            parts.append(f"{n_pos} positive")
        if n_neg:
            parts.append(f"{n_neg} negative")
        print(f"[Signal Selector] Added {', '.join(parts)} region(s) to profile "
              f"(total: {len(self.profile_regions)}+, "
              f"{len(self.negative_regions)}\u2212)")

    def _save_selections(self, _event=None):
        """Save each profile region as a separate bandpass-filtered WAV.

        Positive selections → ``{base}_SelectedSignals/signalPositive/``
        Negative selections → ``{base}_SelectedSignals/signalNegative/``
        """
        pos_regions = self.profile_regions + self._pending_regions
        neg_regions = self.negative_regions + self._pending_neg_regions
        if not pos_regions and not neg_regions:
            print("[Signal Selector] Nothing to save \u2014 no selections.")
            return
        import soundfile as sf
        if self.source_path:
            base = os.path.splitext(self.source_path)[0]
            audio_dir = os.path.dirname(self.source_path)
        else:
            base = "signal"
            audio_dir = "."

        base_name = os.path.basename(base)

        # Root output directory
        out_dir = os.path.join(audio_dir, f"{base_name}_SelectedSignals")

        saved = 0
        for label, regions in [("signalPositive", pos_regions),
                                ("signalNegative", neg_regions)]:
            if not regions:
                continue
            sub_dir = os.path.join(out_dir, label)
            os.makedirs(sub_dir, exist_ok=True)
            for i, r in enumerate(regions, 1):
                s0 = max(0, int(r["t_start"] * self.sr))
                s1 = min(len(self.y), int(r["t_end"] * self.sr))
                seg = self.y[s0:s1]
                filtered = _bandpass_segment(
                    seg, self.sr, r["f_low"], r["f_high"])

                candidate = os.path.join(
                    sub_dir, f"{base_name}_SignalSelection{i}.wav")
                out_path = _unique_path(candidate)
                sf.write(out_path, filtered, self.sr)
                print(f"  Saved: {out_path}")
                saved += 1
        print(f"[Signal Selector] Saved {saved} selection(s) to {out_dir}")

    # ---- navigation callbacks ----

    def _go_prev(self, _event=None):
        if self._chunk_idx > 0:
            _stop_audio()
            self._chunk_idx -= 1
            self._draw_chunk()
            self._draw_playback_bar()

    def _go_next(self, _event=None):
        if self._chunk_idx < self.n_chunks - 1:
            _stop_audio()
            self._chunk_idx += 1
            self._draw_chunk()
            self._draw_playback_bar()

    # ---- playback callbacks ----

    def _play_chunk(self, _event=None):
        t0, _ = self._chunk_time_range()
        s0, s1 = self._chunk_samples()
        _play_audio(self.y[s0:s1], self.sr, file_offset=t0)

    def _play_last_selection(self, _event=None):
        """Play the most recent pending selection, bandpass-filtered."""
        regions = (self._pending_regions or self._pending_neg_regions
                   or self.profile_regions or self.negative_regions)
        if not regions:
            return
        r = regions[-1]
        s0 = max(0, int(r["t_start"] * self.sr))
        s1 = min(len(self.y), int(r["t_end"] * self.sr))
        segment = self.y[s0:s1]
        filtered = _bandpass_segment(segment, self.sr, r["f_low"], r["f_high"])
        _play_audio(filtered, self.sr, file_offset=r["t_start"])

    # ---- selection / key callbacks ----

    def _on_select(self, eclick, erelease):
        """Handle completed rectangle selection."""
        t_start = min(eclick.xdata, erelease.xdata)
        t_end = max(eclick.xdata, erelease.xdata)
        f_low = min(eclick.ydata, erelease.ydata)
        f_high = max(eclick.ydata, erelease.ydata)

        t_start = max(0, t_start)
        t_end = min(self.total_duration, t_end)
        f_low = max(0, f_low)
        f_high = min(self.sr / 2, f_high)

        region = {
            "t_start": t_start,
            "t_end": t_end,
            "f_low": f_low,
            "f_high": f_high,
        }

        if self._selection_mode == "positive":
            self._pending_regions.append(region)
            color = "#4caf50"
            label = f"+R{len(self._pending_regions)}"
        else:
            self._pending_neg_regions.append(region)
            color = "#f44336"
            label = f"\u2212R{len(self._pending_neg_regions)}"

        rect = patches.Rectangle(
            (t_start, f_low), t_end - t_start, f_high - f_low,
            linewidth=2, edgecolor=color, facecolor=color,
            alpha=0.25,
        )
        self.ax_spec.add_patch(rect)
        self.ax_spec.text(
            t_start + (t_end - t_start) / 2, f_high + 20,
            label, fontsize=8, color=color,
            ha="center", va="bottom",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="black", alpha=0.5),
        )

        self._update_status()
        self._draw_playback_bar()

        # Auto-play the selected region
        if _HAS_SD:
            self._play_last_selection()

    def _on_key(self, event):
        if event.key == "u":
            _stop_audio()
            # Undo the most recent pending selection in the active mode
            if (self._selection_mode == "negative"
                    and self._pending_neg_regions):
                self._pending_neg_regions.pop()
            elif self._pending_regions:
                self._pending_regions.pop()
            elif self._pending_neg_regions:
                self._pending_neg_regions.pop()
            else:
                return
            self._draw_chunk()
            self._draw_playback_bar()
        elif event.key == "t":
            self._toggle_mode()
        elif event.key == "enter":
            # Commit any remaining pending selections before closing
            if self._pending_regions or self._pending_neg_regions:
                self._add_to_profile()
            if self._close_callback:
                self._close_callback()
            else:
                plt.close(self.fig)
        elif event.key == "right":
            self._go_next()
        elif event.key == "left":
            self._go_prev()


# ─────────────────────────────────────────────────────────────────────
# Interactive onset marker selector (matplotlib)
# ─────────────────────────────────────────────────────────────────────

class OnsetSelector:
    """Interactive matplotlib figure for marking onset positions on a spectrogram.

    Similar to :class:`SpectrogramSelector` but instead of drawing rectangles,
    the user **clicks** on the spectrogram to place vertical onset markers.

    Positive markers (green) = "detect onsets like this"
    Negative markers (red)   = "do NOT detect onsets here"

    The selector also supports loading Audacity label files to import
    existing onset positions in bulk.
    """

    # Frequency analysis window: how wide a time window (seconds) around
    # each onset to analyse for spectral characteristics.
    _ANALYSIS_HALF_WINDOW = 0.05  # 50 ms each side

    def __init__(self, y, sr, n_fft=2048, hop_length=512, source_path=None):
        self.y = y
        self.sr = sr
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.source_path = source_path

        # Selection mode
        self._selection_mode = "positive"

        # Onset markers: lists of float (seconds)
        self._pending_pos = []
        self._pending_neg = []
        self.committed_pos = []
        self.committed_neg = []

        self._profile = None
        self._close_callback = None

        self.total_duration = len(y) / sr
        self.n_chunks = max(1, int(np.ceil(self.total_duration / CHUNK_SECONDS)))
        self._chunk_idx = 0

    # ---- chunk helpers (identical to SpectrogramSelector) ----

    def _chunk_time_range(self, idx=None):
        if idx is None:
            idx = self._chunk_idx
        t0 = idx * CHUNK_SECONDS
        t1 = min(t0 + CHUNK_SECONDS, self.total_duration)
        return t0, t1

    def _chunk_samples(self, idx=None):
        t0, t1 = self._chunk_time_range(idx)
        return int(t0 * self.sr), int(t1 * self.sr)

    # ---- drawing ----

    def _draw_chunk(self):
        """Compute spectrogram for the current chunk and draw onset markers."""
        ax = self.ax_spec
        ax.clear()

        t0, t1 = self._chunk_time_range()
        s0, s1 = self._chunk_samples()
        chunk_y = self.y[s0:s1]

        S_db, freqs, times = compute_spectrogram(
            chunk_y, self.sr, self.n_fft, self.hop_length)

        ax.imshow(S_db, aspect='auto', origin='lower', cmap='magma',
                  extent=[t0, t0 + CHUNK_SECONDS, freqs[0], freqs[-1]])
        ax.set_ylabel("Frequency (Hz)")
        ax.set_xlabel("Time (s)")
        ax.set_xlim(t0, t0 + CHUNK_SECONDS)
        ax.set_title(
            f"Chunk {self._chunk_idx + 1} / {self.n_chunks}   "
            f"({t0:.1f}s \u2013 {t1:.1f}s of {self.total_duration:.1f}s)")

        ymin, ymax = freqs[0], freqs[-1]

        # Draw committed positive onsets — blue vertical lines
        for i, t in enumerate(self.committed_pos):
            if t0 <= t <= t0 + CHUNK_SECONDS:
                ax.axvline(t, color="#2196f3", linewidth=2, alpha=0.8)
                ax.text(t, ymax * 0.97, f"+P{i+1}", fontsize=7,
                        color="#2196f3", ha="center", va="top",
                        bbox=dict(boxstyle="round,pad=0.15",
                                  facecolor="black", alpha=0.6))

        # Draw committed negative onsets — dark red
        for i, t in enumerate(self.committed_neg):
            if t0 <= t <= t0 + CHUNK_SECONDS:
                ax.axvline(t, color="#d32f2f", linewidth=2, alpha=0.8,
                           linestyle="--")
                ax.text(t, ymax * 0.97, f"\u2212N{i+1}", fontsize=7,
                        color="#ef5350", ha="center", va="top",
                        bbox=dict(boxstyle="round,pad=0.15",
                                  facecolor="black", alpha=0.6))

        # Draw pending positive onsets — green
        for i, t in enumerate(self._pending_pos):
            if t0 <= t <= t0 + CHUNK_SECONDS:
                ax.axvline(t, color="#4caf50", linewidth=2, alpha=0.8)
                ax.text(t, ymax * 0.97, f"+R{i+1}", fontsize=7,
                        color="#4caf50", ha="center", va="top",
                        bbox=dict(boxstyle="round,pad=0.15",
                                  facecolor="black", alpha=0.6))

        # Draw pending negative onsets — red
        for i, t in enumerate(self._pending_neg):
            if t0 <= t <= t0 + CHUNK_SECONDS:
                ax.axvline(t, color="#f44336", linewidth=2, alpha=0.8,
                           linestyle="--")
                ax.text(t, ymax * 0.97, f"\u2212R{i+1}", fontsize=7,
                        color="#f44336", ha="center", va="top",
                        bbox=dict(boxstyle="round,pad=0.15",
                                  facecolor="black", alpha=0.6))

        # Mode indicator
        mode_color = "#4caf50" if self._selection_mode == "positive" else "#f44336"
        mode_label = ("\u2795 POSITIVE (mark real onsets)"
                      if self._selection_mode == "positive"
                      else "\u2796 NEGATIVE (mark false onsets)")
        ax.text(
            0.5, 0.97, mode_label,
            transform=ax.transAxes, fontsize=10, color=mode_color,
            ha="center", va="top", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.7))

        # Instructions
        ax.text(
            0.02, 0.02,
            "Click: place onset  |  U: undo  |  T: toggle +/\u2212  |  "
            "\u2190/\u2192: chunks  |  Enter: done",
            transform=ax.transAxes, fontsize=9, color="white",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.6),
            verticalalignment="bottom")
        self._status = ax.text(
            0.98, 0.02, self._status_text(),
            transform=ax.transAxes, fontsize=9, color="#4caf50", ha="right",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.6),
            verticalalignment="bottom")

        self.fig.canvas.draw_idle()

    def _status_text(self):
        parts = []
        pp, pn = len(self._pending_pos), len(self._pending_neg)
        if pp or pn:
            pend = []
            if pp:
                pend.append(f"{pp}+ pending")
            if pn:
                pend.append(f"{pn}\u2212 pending")
            parts.append(", ".join(pend))
        parts.append(f"{len(self.committed_pos)}+ committed")
        if self.committed_neg:
            parts.append(f"{len(self.committed_neg)}\u2212 committed")
        return "  |  ".join(parts)

    def _update_status(self):
        if hasattr(self, '_status'):
            self._status.set_text(self._status_text())
            self.fig.canvas.draw_idle()

    # ---- playback bar ----

    def _draw_playback_bar(self):
        ax = self.ax_bar
        ax.clear()
        t0, t1 = self._chunk_time_range()
        ax.set_xlim(t0, t0 + CHUNK_SECONDS)
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        ax.patch.set_facecolor("#1a1a2e")
        ax.axhspan(0, 1, xmin=0, xmax=1, color="#2a2a3e")

        # Show onset markers on scrub bar
        for t in self.committed_pos:
            if t0 <= t <= t0 + CHUNK_SECONDS:
                ax.axvline(t, color="#2196f3", linewidth=1.5, alpha=0.7)
        for t in self.committed_neg:
            if t0 <= t <= t0 + CHUNK_SECONDS:
                ax.axvline(t, color="#d32f2f", linewidth=1.5, alpha=0.7)
        for t in self._pending_pos:
            if t0 <= t <= t0 + CHUNK_SECONDS:
                ax.axvline(t, color="#4caf50", linewidth=1.5, alpha=0.7)
        for t in self._pending_neg:
            if t0 <= t <= t0 + CHUNK_SECONDS:
                ax.axvline(t, color="#f44336", linewidth=1.5, alpha=0.7)

        pos = _current_playback_time()
        if pos is not None and t0 <= pos <= t0 + CHUNK_SECONDS:
            self._cursor_line = ax.axvline(pos, color="white", linewidth=2)
        else:
            self._cursor_line = None
        self.fig.canvas.draw_idle()

    def _tick_playback_bar(self):
        if not hasattr(self, 'ax_bar'):
            return
        pos = _current_playback_time()
        t0, _ = self._chunk_time_range()
        had_cursor = (hasattr(self, '_cursor_line')
                      and self._cursor_line is not None)
        needs_cursor = (pos is not None
                        and t0 <= pos <= t0 + CHUNK_SECONDS)
        if not had_cursor and not needs_cursor:
            return
        if had_cursor:
            try:
                self._cursor_line.remove()
            except Exception:
                pass
            self._cursor_line = None
        if needs_cursor:
            self._cursor_line = self.ax_bar.axvline(
                pos, color="white", linewidth=2)
        self.fig.canvas.draw_idle()

    def _on_bar_click(self, event):
        if event.inaxes != self.ax_bar or event.button != 1:
            return
        click_t = event.xdata
        if click_t is None:
            return
        t0, t1 = self._chunk_time_range()
        click_t = max(t0, min(click_t, t1))
        s_start = int(click_t * self.sr)
        s_end = int(t1 * self.sr)
        if s_end > s_start:
            _play_audio(self.y[s_start:s_end], self.sr, file_offset=click_t)

    # ---- main entry ----

    def _setup_figure(self, fig=None):
        if fig is None:
            fig = plt.figure(figsize=(14, 8))

        self.ax_spec = fig.add_axes([0.07, 0.22, 0.88, 0.65])
        self.ax_bar = fig.add_axes([0.07, 0.14, 0.88, 0.04])
        self.fig = fig

        fig.suptitle(
            "Onset Selector \u2014 Click on the spectrogram to place "
            "onset markers\n"
            "(Green = real onsets  \u2022  Red = false onsets  \u2022  "
            "Blue = committed positive  \u2022  Dark red = committed negative)",
            fontsize=11, y=0.98)

        self._draw_chunk()
        self._draw_playback_bar()

        # Button bar
        btn_h = 0.04
        btn_y = 0.025
        x = 0.02

        def _btn(pos_x, w, label):
            ax_b = fig.add_axes([pos_x, btn_y, w, btn_h])
            return Button(ax_b, label)

        # Mode toggle
        self._btn_mode = _btn(x, 0.12, "\u2795 Real Onset"); x += 0.125
        self._btn_mode.on_clicked(self._toggle_mode)
        self._btn_mode.ax.set_facecolor("#2e7d32")
        self._btn_mode.label.set_color("white")
        self._btn_mode.label.set_fontweight("bold")

        self._btn_prev = _btn(x, 0.06, "\u25c0 Prev"); x += 0.065
        self._btn_prev.on_clicked(self._go_prev)

        self._btn_next = _btn(x, 0.06, "Next \u25b6"); x += 0.07
        self._btn_next.on_clicked(self._go_next)

        # Commit
        self._btn_add = _btn(x, 0.12, "\u2605 Commit Onsets"); x += 0.13
        self._btn_add.on_clicked(self._commit_onsets)
        self._btn_add.ax.set_facecolor("#2e7d32")
        self._btn_add.label.set_color("white")
        self._btn_add.label.set_fontweight("bold")

        # Save
        self._btn_save = _btn(x, 0.11, "\U0001f4be Save Onsets"); x += 0.12
        self._btn_save.on_clicked(self._save_onsets)

        if _HAS_SD:
            self._btn_play = _btn(x, 0.08, "\u25b6 Chunk"); x += 0.085
            self._btn_play.on_clicked(self._play_chunk)

            self._btn_stop = _btn(x, 0.06, "\u23f9 Stop"); x += 0.07
            self._btn_stop.on_clicked(lambda _: _stop_audio())

        # Click handler for placing onsets on the spectrogram
        fig.canvas.mpl_connect("button_press_event", self._on_click)
        fig.canvas.mpl_connect("key_press_event", self._on_key)
        fig.canvas.mpl_connect("button_press_event", self._on_bar_click)

        # Playback timer
        self._timer = fig.canvas.new_timer(interval=100)
        self._timer.add_callback(self._tick_playback_bar)
        self._timer.start()

    def _analyze_onset_point(self, t):
        """Return spectral characteristics around a single onset time."""
        hw = self._ANALYSIS_HALF_WINDOW
        s0 = max(0, int((t - hw) * self.sr))
        s1 = min(len(self.y), int((t + hw) * self.sr))
        seg = self.y[s0:s1]
        if len(seg) < self.n_fft:
            seg = np.pad(seg, (0, max(0, self.n_fft - len(seg))))

        S = np.abs(librosa.stft(seg, n_fft=self.n_fft,
                                hop_length=self.hop_length))
        freqs = librosa.fft_frequencies(sr=self.sr, n_fft=self.n_fft)
        mean_spec = np.mean(S, axis=1)

        # Dominant frequency
        peak_idx = np.argmax(mean_spec)
        peak_freq = float(freqs[peak_idx])

        # Spectral centroid and bandwidth
        total = np.sum(mean_spec)
        if total > 1e-10:
            centroid = float(np.sum(mean_spec * freqs) / total)
            variance = float(np.sum(mean_spec * (freqs - centroid) ** 2) / total)
            bandwidth = float(np.sqrt(max(variance, 0)))
        else:
            centroid = peak_freq
            bandwidth = 0.0

        # Energy in bands
        lo_mask = freqs < 500
        mid_mask = (freqs >= 500) & (freqs < 4000)
        hi_mask = freqs >= 4000
        lo_energy = float(np.sum(mean_spec[lo_mask] ** 2))
        mid_energy = float(np.sum(mean_spec[mid_mask] ** 2))
        hi_energy = float(np.sum(mean_spec[hi_mask] ** 2))
        total_energy = lo_energy + mid_energy + hi_energy + 1e-10

        # Attack sharpness via Hilbert envelope
        try:
            from scipy.signal import hilbert
            env = np.abs(hilbert(seg))
            if len(env) > 1:
                env_diff = np.diff(env)
                sharpness = float(np.max(env_diff) / (np.max(env) + 1e-10))
            else:
                sharpness = 0.0
        except Exception:
            sharpness = 0.0

        # Harmonicity via HPSS
        try:
            H, P = librosa.decompose.hpss(S)
            h_e = float(np.sum(H ** 2))
            p_e = float(np.sum(P ** 2))
            harmonicity = h_e / max(h_e + p_e, 1e-10)
        except Exception:
            harmonicity = 0.5

        return {
            "time": round(t, 6),
            "peak_frequency_hz": round(peak_freq, 1),
            "spectral_centroid_hz": round(centroid, 1),
            "spectral_bandwidth_hz": round(bandwidth, 1),
            "attack_sharpness": round(sharpness, 4),
            "harmonicity": round(harmonicity, 4),
            "energy_low_frac": round(lo_energy / total_energy, 4),
            "energy_mid_frac": round(mid_energy / total_energy, 4),
            "energy_high_frac": round(hi_energy / total_energy, 4),
        }

    def _finalize(self):
        """Build onset profile from committed + pending markers."""
        _stop_audio()
        if hasattr(self, '_timer'):
            self._timer.stop()

        # Merge pending into committed
        all_pos = sorted(set(self.committed_pos + self._pending_pos))
        all_neg = sorted(set(self.committed_neg + self._pending_neg))

        # Analyse each onset
        pos_analyses = [self._analyze_onset_point(t) for t in all_pos]
        neg_analyses = [self._analyze_onset_point(t) for t in all_neg]

        # IOI statistics for positive onsets
        pos_ioi_stats = {}
        if len(all_pos) >= 2:
            iois = np.diff(all_pos) * 1000  # ms
            pos_ioi_stats = {
                "min_ioi_ms": round(float(np.min(iois)), 2),
                "max_ioi_ms": round(float(np.max(iois)), 2),
                "mean_ioi_ms": round(float(np.mean(iois)), 2),
                "std_ioi_ms": round(float(np.std(iois)), 2),
                "median_ioi_ms": round(float(np.median(iois)), 2),
                "n_intervals": len(iois),
            }

        # Aggregate spectral summary
        def _summarize(analyses):
            if not analyses:
                return {}
            return {
                "n_onsets": len(analyses),
                "freq_range_hz": [
                    round(min(a["peak_frequency_hz"] for a in analyses), 1),
                    round(max(a["peak_frequency_hz"] for a in analyses), 1),
                ],
                "mean_centroid_hz": round(float(np.mean(
                    [a["spectral_centroid_hz"] for a in analyses])), 1),
                "mean_bandwidth_hz": round(float(np.mean(
                    [a["spectral_bandwidth_hz"] for a in analyses])), 1),
                "mean_sharpness": round(float(np.mean(
                    [a["attack_sharpness"] for a in analyses])), 4),
                "mean_harmonicity": round(float(np.mean(
                    [a["harmonicity"] for a in analyses])), 4),
                "mean_energy_low": round(float(np.mean(
                    [a["energy_low_frac"] for a in analyses])), 4),
                "mean_energy_mid": round(float(np.mean(
                    [a["energy_mid_frac"] for a in analyses])), 4),
                "mean_energy_high": round(float(np.mean(
                    [a["energy_high_frac"] for a in analyses])), 4),
                "signal_character": (
                    "harmonic" if float(np.mean(
                        [a["harmonicity"] for a in analyses])) > 0.65
                    else "percussive" if float(np.mean(
                        [a["harmonicity"] for a in analyses])) < 0.35
                    else "mixed"
                ),
            }

        self._profile = {
            "source_file": os.path.basename(self.source_path or ""),
            "sr": self.sr,
            "positive_onsets": all_pos,
            "negative_onsets": all_neg,
            "positive_analyses": pos_analyses,
            "negative_analyses": neg_analyses,
            "positive_summary": _summarize(pos_analyses),
            "negative_summary": _summarize(neg_analyses),
            "ioi_stats": pos_ioi_stats,
        }
        return self._profile

    def run(self):
        self._setup_figure()
        plt.show()
        return self._finalize()

    # ---- callbacks ----

    def _toggle_mode(self, _event=None):
        if self._selection_mode == "positive":
            self._selection_mode = "negative"
            self._btn_mode.label.set_text("\u2796 False Onset")
            self._btn_mode.ax.set_facecolor("#c62828")
        else:
            self._selection_mode = "positive"
            self._btn_mode.label.set_text("\u2795 Real Onset")
            self._btn_mode.ax.set_facecolor("#2e7d32")
        self._draw_chunk()
        self.fig.canvas.draw_idle()

    def _commit_onsets(self, _event=None):
        n_pos = len(self._pending_pos)
        n_neg = len(self._pending_neg)
        if not n_pos and not n_neg:
            return
        self.committed_pos.extend(self._pending_pos)
        self.committed_neg.extend(self._pending_neg)
        self._pending_pos = []
        self._pending_neg = []
        self._draw_chunk()
        self._draw_playback_bar()
        parts = []
        if n_pos:
            parts.append(f"{n_pos} positive")
        if n_neg:
            parts.append(f"{n_neg} negative")
        print(f"[Onset Selector] Committed {', '.join(parts)} onset(s) "
              f"(total: {len(self.committed_pos)}+, "
              f"{len(self.committed_neg)}\u2212)")

    def _save_onsets(self, _event=None):
        """Save onset markers as Audacity-format label files."""
        all_pos = sorted(set(self.committed_pos + self._pending_pos))
        all_neg = sorted(set(self.committed_neg + self._pending_neg))
        if not all_pos and not all_neg:
            print("[Onset Selector] Nothing to save.")
            return

        if self.source_path:
            base = os.path.splitext(self.source_path)[0]
            audio_dir = os.path.dirname(self.source_path)
        else:
            base = "onsets"
            audio_dir = "."

        base_name = os.path.basename(base)
        out_dir = os.path.join(audio_dir, f"{base_name}_OnsetSelections")
        os.makedirs(out_dir, exist_ok=True)

        saved = 0
        if all_pos:
            pos_path = _unique_path(os.path.join(
                out_dir, f"{base_name}_positive_onsets.txt"))
            with open(pos_path, "w") as f:
                for i, t in enumerate(all_pos, 1):
                    f.write(f"{t:.6f}\t{t:.6f}\tOnsetPos_{i}\n")
            print(f"  Saved: {pos_path}")
            saved += 1

        if all_neg:
            neg_path = _unique_path(os.path.join(
                out_dir, f"{base_name}_negative_onsets.txt"))
            with open(neg_path, "w") as f:
                for i, t in enumerate(all_neg, 1):
                    f.write(f"{t:.6f}\t{t:.6f}\tOnsetNeg_{i}\n")
            print(f"  Saved: {neg_path}")
            saved += 1

        print(f"[Onset Selector] Saved {saved} file(s) to {out_dir}")

    def load_label_file(self, path, mode="positive"):
        """Import onset times from an Audacity label file.

        Parameters
        ----------
        path : str
            Path to a tab-separated label file (time\\ttime\\tlabel).
        mode : str
            ``"positive"`` or ``"negative"``.
        """
        times = []
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                try:
                    t = float(parts[0])
                    if 0 <= t <= self.total_duration:
                        times.append(t)
                except (ValueError, IndexError):
                    continue
        if mode == "positive":
            self.committed_pos.extend(times)
            self.committed_pos = sorted(set(self.committed_pos))
        else:
            self.committed_neg.extend(times)
            self.committed_neg = sorted(set(self.committed_neg))
        print(f"[Onset Selector] Loaded {len(times)} onsets from {path} "
              f"as {mode}")

    # ---- navigation ----

    def _go_prev(self, _event=None):
        if self._chunk_idx > 0:
            _stop_audio()
            self._chunk_idx -= 1
            self._draw_chunk()
            self._draw_playback_bar()

    def _go_next(self, _event=None):
        if self._chunk_idx < self.n_chunks - 1:
            _stop_audio()
            self._chunk_idx += 1
            self._draw_chunk()
            self._draw_playback_bar()

    def _play_chunk(self, _event=None):
        t0, _ = self._chunk_time_range()
        s0, s1 = self._chunk_samples()
        _play_audio(self.y[s0:s1], self.sr, file_offset=t0)

    # ---- click / key handlers ----

    def _on_click(self, event):
        """Place an onset marker on click within the spectrogram axes."""
        if event.inaxes != self.ax_spec:
            return
        if event.button != 1:
            return
        t = event.xdata
        if t is None:
            return
        t = max(0, min(t, self.total_duration))

        if self._selection_mode == "positive":
            self._pending_pos.append(t)
            color = "#4caf50"
        else:
            self._pending_neg.append(t)
            color = "#f44336"

        # Draw immediately without full redraw
        self.ax_spec.axvline(t, color=color, linewidth=2, alpha=0.8,
                             linestyle=("-" if self._selection_mode == "positive"
                                        else "--"))
        self._update_status()
        self._draw_playback_bar()

    def _on_key(self, event):
        if event.key == "u":
            _stop_audio()
            if (self._selection_mode == "negative"
                    and self._pending_neg):
                self._pending_neg.pop()
            elif self._pending_pos:
                self._pending_pos.pop()
            elif self._pending_neg:
                self._pending_neg.pop()
            else:
                return
            self._draw_chunk()
            self._draw_playback_bar()
        elif event.key == "t":
            self._toggle_mode()
        elif event.key == "enter":
            if self._pending_pos or self._pending_neg:
                self._commit_onsets()
            if self._close_callback:
                self._close_callback()
            else:
                plt.close(self.fig)
        elif event.key == "right":
            self._go_next()
        elif event.key == "left":
            self._go_prev()


def _make_onset_selector_dialog():
    """Return an *OnsetSelectorDialog* class, importing PyQt6 lazily."""
    from PyQt6.QtWidgets import QDialog, QVBoxLayout
    from PyQt6.QtCore import Qt as QtConst
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure as MplFigure

    class OnsetSelectorDialog(QDialog):
        """Qt dialog embedding the OnsetSelector."""

        def __init__(self, y, sr, source_path=None, parent=None,
                     on_done=None, pre_pos=None, pre_neg=None):
            super().__init__(parent)
            self.setWindowTitle("Onset Selector \u2014 Spectrogram")
            self.setMinimumSize(900, 550)
            self.resize(1200, 750)

            self._on_done = on_done
            self._finished = False

            self._sel = OnsetSelector(y, sr, source_path=source_path)
            self._sel._close_callback = self.accept

            # Pre-load any existing onsets
            if pre_pos:
                self._sel.committed_pos = sorted(set(pre_pos))
            if pre_neg:
                self._sel.committed_neg = sorted(set(pre_neg))

            fig = MplFigure(figsize=(14, 8), dpi=100)
            self._canvas = FigureCanvasQTAgg(fig)
            self._canvas.setFocusPolicy(QtConst.FocusPolicy.StrongFocus)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(2, 2, 2, 2)
            layout.addWidget(self._canvas)

            self._sel._setup_figure(fig=fig)
            self._canvas.draw()

        @property
        def selector(self):
            return self._sel

        def _finish(self):
            if self._finished:
                return
            self._finished = True
            profile = self._sel._finalize()
            if self._on_done:
                self._on_done(profile)

        def accept(self):
            self._finish()
            super().accept()

        def reject(self):
            self._finish()
            super().reject()

        def closeEvent(self, event):
            self._finish()
            super().closeEvent(event)

    return OnsetSelectorDialog


def select_signal_regions(audio_path, sr=None):
    """Load an audio file and open the interactive signal selector.

    Parameters
    ----------
    audio_path : str
        Path to the audio file.
    sr : int or None
        Target sample rate (None = native).

    Returns
    -------
    dict
        Signal profile with regions and summary.
    """
    y, sr = librosa.load(audio_path, sr=sr, mono=True)
    selector = SpectrogramSelector(y, sr, source_path=audio_path)
    profile = selector.run()
    profile["source_file"] = os.path.basename(audio_path)
    return profile


# ─────────────────────────────────────────────────────────────────────
# Qt-embedded dialog (for use inside a running PyQt application)
# ─────────────────────────────────────────────────────────────────────

def _make_spectrogram_dialog():
    """Return a *SpectrogramDialog* class, importing PyQt6 lazily.

    This avoids hard-depending on PyQt6 at module level so that
    standalone / CLI usage continues to work without Qt installed.
    """
    from PyQt6.QtWidgets import QDialog, QVBoxLayout
    from PyQt6.QtCore import Qt as QtConst
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure as MplFigure

    class SpectrogramDialog(QDialog):
        """Qt-native dialog embedding the spectrogram selector.

        Renders the matplotlib figure inside a *FigureCanvasQTAgg* widget
        so that it shares the existing Qt event loop.  This eliminates
        the ``plt.show()`` / dual-event-loop problem that freezes the GUI
        on macOS (and sometimes Linux).
        """

        def __init__(self, y, sr, source_path=None, parent=None,
                     on_done=None):
            super().__init__(parent)
            self.setWindowTitle("Signal Selector — Spectrogram")
            self.setMinimumSize(900, 550)
            self.resize(1200, 750)

            self._on_done = on_done
            self._finished = False

            # Create the selector (all analysis + interaction logic)
            self._sel = SpectrogramSelector(y, sr, source_path=source_path)
            self._sel._close_callback = self.accept

            # Non-pyplot Figure → embedded canvas
            fig = MplFigure(figsize=(14, 8), dpi=100)
            self._canvas = FigureCanvasQTAgg(fig)
            self._canvas.setFocusPolicy(QtConst.FocusPolicy.StrongFocus)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(2, 2, 2, 2)
            layout.addWidget(self._canvas)

            # Initialise axes, buttons, key bindings on the embedded figure
            self._sel._setup_figure(fig=fig)
            self._canvas.draw()

        # -- lifecycle --

        def _finish(self):
            """Finalise exactly once and invoke callback."""
            if self._finished:
                return
            self._finished = True
            profile = self._sel._finalize()
            if self._on_done:
                self._on_done(profile)

        def accept(self):
            self._finish()
            super().accept()

        def reject(self):
            self._finish()
            super().reject()

        def closeEvent(self, event):
            self._finish()
            super().closeEvent(event)

    return SpectrogramDialog


# ─────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Interactive spectrogram signal selector for bioacoustics."
    )
    parser.add_argument("audio_file", help="Path to audio file to analyze.")
    parser.add_argument("-o", "--output", default=None,
                        help="Output JSON path for signal profile. "
                             "(default: <audio_file>_signal_profile.json)")
    parser.add_argument("--sr", type=int, default=None,
                        help="Target sample rate (None = native).")
    args = parser.parse_args()

    if not os.path.isfile(args.audio_file):
        print(f"ERROR: File not found: {args.audio_file}")
        sys.exit(1)

    profile = select_signal_regions(args.audio_file, sr=args.sr)

    out_path = args.output
    if out_path is None:
        base = os.path.splitext(args.audio_file)[0]
        out_path = f"{base}_signal_profile.json"

    with open(out_path, "w") as f:
        json.dump(profile, f, indent=2)

    n = profile.get("summary", {}).get("n_regions", 0)
    print(f"\nSignal profile saved to {out_path}")
    print(f"  {n} region(s) selected")
    if n > 0:
        s = profile["summary"]
        print(f"  Frequency range: {s['freq_range_hz'][0]:.0f} – {s['freq_range_hz'][1]:.0f} Hz")
        print(f"  Character: {s['signal_character']}")
        print(f"  Harmonicity: {s['harmonicity']:.2f}")
        print(f"  Attack sharpness: {s['attack_sharpness']:.3f}")


if __name__ == "__main__":
    main()
