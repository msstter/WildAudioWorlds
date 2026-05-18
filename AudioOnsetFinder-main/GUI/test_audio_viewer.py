"""
Test suite and standalone demo for AudioViewerWidget.

Usage:
    conda run -n rhythm_env python GUI/test_audio_viewer.py [audio_file.wav]
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtWidgets import QApplication

# Ensure GUI/ parent is on path so we can import audio_viewer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audio_viewer import AudioViewerWidget, _HAS_SOUNDDEVICE, _HAS_LIBROSA


_APP = QApplication.instance() or QApplication(sys.argv)


class _DummyWheelEvent:
    """Minimal wheel event shim for deterministic unit checks."""

    def __init__(self, *, angle_x=0, angle_y=0, pixel_x=0, pixel_y=0,
                 mods=Qt.KeyboardModifier.NoModifier,
                 pos: QPointF | None = None):
        self._angle = QPoint(int(angle_x), int(angle_y))
        self._pixel = QPoint(int(pixel_x), int(pixel_y))
        self._mods = mods
        self._pos = QPointF(0.0, 0.0) if pos is None else pos

    def angleDelta(self):
        return self._angle

    def pixelDelta(self):
        return self._pixel

    def modifiers(self):
        return self._mods

    def position(self):
        return self._pos


def _wait_for_spectrogram(
    viewer: AudioViewerWidget, timeout_s: float | None = None
):
    """Wait for async spectrogram rendering to populate frequency bounds."""
    if timeout_s is None:
        timeout_s = 20.0
        timeout_s = 40.0 if sys.platform.startswith("win") else timeout_s
        if os.environ.get("CI"):
            timeout_s = max(timeout_s, 45.0)

    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        QApplication.processEvents()
        if viewer._spec_db is not None and viewer._spec_freqs is not None:
            return
        if viewer._last_spectrogram_error is not None:
            raise AssertionError(
                f"Spectrogram failed: {viewer._last_spectrogram_error}"
            )
        time.sleep(0.02)
    if viewer._stft_thread is None:
        raise AssertionError("Spectrogram worker did not start")
    raise AssertionError(
        f"Timed out waiting for spectrogram data after {timeout_s:.1f}s"
    )


def _generate_test_audio(sr: int = 22050, duration: float = 5.0):
    """Generate a synthetic audio signal for testing."""
    t = np.linspace(0, duration, int(sr * duration), dtype=np.float32)
    # Mix of sine waves with amplitude envelope
    sig = (
        0.3 * np.sin(2 * np.pi * 440 * t) +               # A4
        0.2 * np.sin(2 * np.pi * 880 * t) +               # A5
        0.1 * np.sin(2 * np.pi * 1320 * t) +              # E6
        0.05 * np.random.randn(len(t)).astype(np.float32)  # noise
    )
    # Apply amplitude envelope (fade in/out)
    env = np.ones_like(t)
    fade = int(0.1 * sr)
    env[:fade] = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    sig *= env
    # Simulate onset bursts
    for onset_t in [0.5, 1.5, 2.5, 3.5]:
        idx = int(onset_t * sr)
        burst_len = int(0.05 * sr)
        if idx + burst_len < len(sig):
            sig[idx:idx + burst_len] += 0.5 * np.sin(
                2 * np.pi * 2000 * t[:burst_len])
    sig = np.clip(sig, -1, 1)
    return sig, sr


def test_basic_construction():
    """Test that the widget can be constructed."""
    w = AudioViewerWidget()
    assert w is not None
    assert w.duration == 0.0
    assert w.sampleRate == 22050
    assert w.audioData is None
    print("  [PASS] Basic construction")


def test_load_array():
    """Test loading audio from a numpy array."""
    w = AudioViewerWidget()
    y, sr = _generate_test_audio(duration=3.0)
    t0 = time.perf_counter()
    w.load_audio_array(y, sr, "<test>")
    dt = (time.perf_counter() - t0) * 1000
    assert w.audioData is not None
    assert w.sampleRate == sr
    assert abs(w.duration - 3.0) < 0.01
    print(f"  [PASS] Load from array ({dt:.1f}ms)")


def test_startup_spectrogram_range_not_narrow_high_band():
    """Startup spectrogram should open at a broad low-to-high range, not a tiny top-band sliver."""
    w = AudioViewerWidget()
    y, sr = _generate_test_audio(duration=6.0)
    w.load_audio_array(y, sr)
    _wait_for_spectrogram(w)

    # Allow deferred startup range sanitizers/timers to run.
    for _ in range(12):
        QApplication.processEvents()
        time.sleep(0.01)

    y_lo, y_hi = w._spec_plot.viewRange()[1]
    span = y_hi - y_lo
    expected_hi = min(24000.0, float(w._spec_f_max))

    assert y_lo <= 5.0
    assert span >= max(1000.0, expected_hi * 0.2)
    assert abs(y_hi - expected_hi) <= max(250.0, expected_hi * 0.05)
    print("  [PASS] Startup spectrogram range sane (no narrow high-band lock)")


def test_onset_markers():
    """Test onset marker API."""
    w = AudioViewerWidget()
    y, sr = _generate_test_audio(duration=5.0)
    w.load_audio_array(y, sr)

    # Set markers
    times = np.array([0.5, 1.5, 2.5, 3.5])
    lines = w.set_onset_markers(times, draggable=True)
    assert len(lines) == 4
    assert len(w.onsetTimes) == 4
    assert np.allclose(w.onsetTimes, times)
    print("  [PASS] Set onset markers")

    # Add a marker
    new_idx = w.add_onset_marker(2.0)
    assert len(w.onsetTimes) == 5
    assert 2.0 in w.onsetTimes
    print("  [PASS] Add onset marker")

    # Remove a marker
    w.remove_onset_marker(0)
    assert len(w.onsetTimes) == 4
    assert 0.5 not in w.onsetTimes
    print("  [PASS] Remove onset marker")

    # Clear all
    w.clear_onset_markers()
    assert len(w.onsetTimes) == 0
    print("  [PASS] Clear onset markers")


def test_regions():
    """Test region overlay API."""
    w = AudioViewerWidget()
    y, sr = _generate_test_audio(duration=5.0)
    w.load_audio_array(y, sr)

    region = w.add_region(1.0, 2.0, label="test_region")
    assert region is not None
    print("  [PASS] Add region")

    w.clear_regions()
    print("  [PASS] Clear regions")


def test_seek():
    """Test seek functionality."""
    w = AudioViewerWidget()
    y, sr = _generate_test_audio(duration=5.0)
    w.load_audio_array(y, sr)

    w.seek(2.5)
    assert abs(w._play_offset - 2.5) < 0.01
    print("  [PASS] Seek")


def test_chunk_navigation():
    """Test chunk navigation for long files."""
    w = AudioViewerWidget(chunk_duration=2.0)
    y, sr = _generate_test_audio(duration=10.0)
    w.load_audio_array(y, sr)

    assert w._total_chunks() == 5
    w._on_chunk_changed(3)
    vr = w.get_visible_range()
    assert vr[0] >= 3.5  # chunk 3 starts at 4.0s
    print("  [PASS] Chunk navigation")


def test_playback():
    """Test playback (only if sounddevice available)."""
    if not _HAS_SOUNDDEVICE:
        print("  [SKIP] Playback (sounddevice not installed)")
        return

    w = AudioViewerWidget()
    y, sr = _generate_test_audio(duration=2.0)
    w.load_audio_array(y, sr)

    try:
        w.play()
    except Exception:
        print("  [SKIP] Playback (no usable audio output device)")
        return

    if not w._playing:
        print(
            "  [SKIP] Playback "
            f"({w._last_playback_error or 'device unavailable in CI'})"
        )
        return

    time.sleep(0.2)
    w.stop()
    assert not w._playing
    print("  [PASS] Playback start/stop")


def test_mouse_wheel_pan_direction():
    """Mouse wheel up should pan right, down should pan left."""
    w = AudioViewerWidget()
    y, sr = _generate_test_audio(duration=10.0)
    w.load_audio_array(y, sr)
    w._waveform_plot.setXRange(2.0, 4.0, padding=0)

    vp = w._waveform_plot.viewport()
    center = vp.rect().center()
    pos = QPointF(float(center.x()), float(center.y()))

    before = w._waveform_plot.viewRange()[0]
    w._handle_wheel(vp, _DummyWheelEvent(angle_y=120, pos=pos))
    after_up = w._waveform_plot.viewRange()[0]
    assert after_up[0] > before[0]

    w._handle_wheel(vp, _DummyWheelEvent(angle_y=-120, pos=pos))
    after_down = w._waveform_plot.viewRange()[0]
    assert after_down[0] < after_up[0]
    print("  [PASS] Mouse-wheel pan direction")


def test_shift_wheel_zoom_y_axis():
    """Shift+wheel keeps waveform centered but anchors spectrogram at cursor."""
    w = AudioViewerWidget()
    y, sr = _generate_test_audio(duration=6.0)
    w.load_audio_array(y, sr)
    _wait_for_spectrogram(w)

    # Waveform Y zoom
    wv = w._waveform_plot.viewport()
    wv_center = wv.rect().center()
    # Use a non-centered cursor position and verify y-center still stays fixed.
    wv_pos = QPointF(float(wv_center.x()), float(wv.rect().top() + 4))
    before_wave = w._waveform_plot.viewRange()[1]
    before_wave_center = (before_wave[0] + before_wave[1]) / 2.0
    w._handle_wheel(
        wv,
        _DummyWheelEvent(
            angle_y=120,
            mods=Qt.KeyboardModifier.ShiftModifier,
            pos=wv_pos,
        ),
    )
    after_wave = w._waveform_plot.viewRange()[1]
    after_wave_center = (after_wave[0] + after_wave[1]) / 2.0
    assert (after_wave[1] - after_wave[0]) < (before_wave[1] - before_wave[0])
    assert abs(after_wave_center - before_wave_center) < 1e-6

    # Spectrogram Y zoom
    sv = w._spec_plot.viewport()
    sv_center = sv.rect().center()
    sv_pos = QPointF(float(sv_center.x()), float(sv.rect().top() + 4))
    before_spec = w._spec_plot.viewRange()[1]
    before_spec_center = (before_spec[0] + before_spec[1]) / 2.0
    w._handle_wheel(
        sv,
        _DummyWheelEvent(
            angle_y=120,
            mods=Qt.KeyboardModifier.ShiftModifier,
            pos=sv_pos,
        ),
    )
    after_spec = w._spec_plot.viewRange()[1]
    after_spec_center = (after_spec[0] + after_spec[1]) / 2.0
    assert (after_spec[1] - after_spec[0]) < (before_spec[1] - before_spec[0])
    assert abs(after_spec_center - before_spec_center) > 1.0
    print("  [PASS] Shift+wheel Y-axis zoom")


def test_shift_wheel_horizontal_delta_still_zooms_y():
    """Shift+mouse-wheel reported on x-delta should still perform Y-axis zoom."""
    w = AudioViewerWidget()
    y, sr = _generate_test_audio(duration=6.0)
    w.load_audio_array(y, sr)
    _wait_for_spectrogram(w)

    wv = w._waveform_plot.viewport()
    center = wv.rect().center()
    pos = QPointF(float(center.x()), float(center.y()))

    w._waveform_plot.setYRange(-0.5, 0.5, padding=0)
    before = w._waveform_plot.viewRange()[1]
    w._handle_wheel(
        wv,
        _DummyWheelEvent(
            angle_x=120,
            angle_y=0,
            mods=Qt.KeyboardModifier.ShiftModifier,
            pos=pos,
        ),
    )
    after = w._waveform_plot.viewRange()[1]
    assert (after[1] - after[0]) < (before[1] - before[0])
    print("  [PASS] Shift+wheel horizontal-delta Y-axis zoom")


def test_trackpad_shift_scroll_reversed_y_zoom():
    """Trackpad Shift+scroll should reverse the Y-zoom direction only for pixel deltas."""
    w = AudioViewerWidget()
    y, sr = _generate_test_audio(duration=6.0)
    w.load_audio_array(y, sr)
    _wait_for_spectrogram(w)

    wv = w._waveform_plot.viewport()
    center = wv.rect().center()
    pos = QPointF(float(center.x()), float(center.y()))

    w._waveform_plot.setYRange(-0.5, 0.5, padding=0)
    before = w._waveform_plot.viewRange()[1]
    w._handle_wheel(
        wv,
        _DummyWheelEvent(
            pixel_y=30,
            mods=Qt.KeyboardModifier.ShiftModifier,
            pos=pos,
        ),
    )
    after = w._waveform_plot.viewRange()[1]
    assert (after[1] - after[0]) > (before[1] - before[0])
    print("  [PASS] Trackpad Shift+scroll reversed Y-axis zoom")


def test_ctrl_wheel_zoom_x_axis():
    """Ctrl/Cmd+wheel/scroll should zoom X-axis for mouse and trackpad paths."""
    w = AudioViewerWidget()
    y, sr = _generate_test_audio(duration=6.0)
    w.load_audio_array(y, sr)
    _wait_for_spectrogram(w)

    sv = w._spec_plot.viewport()
    sv_center = sv.rect().center()
    sv_pos = QPointF(float(sv_center.x()), float(sv_center.y()))
    w._waveform_plot.setXRange(1.0, 5.0, padding=0)
    before_x = w._waveform_plot.viewRange()[0]
    before_y = w._spec_plot.viewRange()[1]

    # Mouse-wheel path (angleDelta)
    w._handle_wheel(
        sv,
        _DummyWheelEvent(
            angle_y=120,
            mods=Qt.KeyboardModifier.ControlModifier,
            pos=sv_pos,
        ),
    )
    mid_x = w._waveform_plot.viewRange()[0]
    assert (mid_x[1] - mid_x[0]) < (before_x[1] - before_x[0])

    # Trackpad-scroll path (pixelDelta)
    w._handle_wheel(
        sv,
        _DummyWheelEvent(
            angle_y=0,
            pixel_y=30,
            mods=Qt.KeyboardModifier.ControlModifier,
            pos=sv_pos,
        ),
    )
    after_x = w._waveform_plot.viewRange()[0]
    after_y = w._spec_plot.viewRange()[1]
    assert (after_x[1] - after_x[0]) > (mid_x[1] - mid_x[0])
    # Ctrl/Cmd path should not invoke y-zoom.
    assert abs((after_y[1] - after_y[0]) - (before_y[1] - before_y[0])) < 1e-6
    print("  [PASS] Ctrl/Cmd + wheel/scroll X-axis zoom")


def test_trackpad_pixel_delta_priority():
    """Trackpad pixel deltas should override conflicting angle deltas and reverse direction."""
    w = AudioViewerWidget()
    y, sr = _generate_test_audio(duration=10.0)
    w.load_audio_array(y, sr)
    w._waveform_plot.setXRange(2.0, 4.0, padding=0)

    vp = w._waveform_plot.viewport()
    center = vp.rect().center()
    pos = QPointF(float(center.x()), float(center.y()))

    before = w._waveform_plot.viewRange()[0]
    # Reversed trackpad pixel delta says pan left; mouse angle delta says pan right.
    w._handle_wheel(
        vp,
        _DummyWheelEvent(angle_y=120, pixel_y=30, pos=pos),
    )
    after = w._waveform_plot.viewRange()[0]
    assert after[0] < before[0]
    print("  [PASS] Trackpad pixel-delta priority")


def test_fullscreen_toggle_preserves_spectrogram_y_range():
    """Fullscreen toggles should not collapse spectrogram into a narrow high band."""
    w = AudioViewerWidget()
    y, sr = _generate_test_audio(duration=6.0)
    w.load_audio_array(y, sr)
    _wait_for_spectrogram(w)

    for _ in range(8):
        QApplication.processEvents()
        time.sleep(0.01)

    expected_hi = min(24000.0, float(w._spec_f_max))

    for _cycle in range(3):
        w._toggle_maximize()
        for _ in range(16):
            QApplication.processEvents()
            time.sleep(0.01)

        y_lo, y_hi = w._spec_plot.viewRange()[1]
        span = y_hi - y_lo
        assert y_lo <= 5.0
        assert span >= max(1000.0, expected_hi * 0.2)
        assert abs(y_hi - expected_hi) <= max(250.0, expected_hi * 0.05)

    print("  [PASS] Fullscreen toggle preserves spectrogram Y-range")


def run_all_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("AudioViewerWidget — Test Suite")
    print("=" * 60)
    print(f"  librosa available: {_HAS_LIBROSA}")
    print(f"  sounddevice available: {_HAS_SOUNDDEVICE}")
    print()

    tests = [
        test_basic_construction,
        test_load_array,
        test_startup_spectrogram_range_not_narrow_high_band,
        test_onset_markers,
        test_regions,
        test_seek,
        test_chunk_navigation,
        test_mouse_wheel_pan_direction,
        test_shift_wheel_zoom_y_axis,
        test_shift_wheel_horizontal_delta_still_zooms_y,
        test_trackpad_shift_scroll_reversed_y_zoom,
        test_ctrl_wheel_zoom_x_axis,
        test_trackpad_pixel_delta_priority,
        test_fullscreen_toggle_preserves_spectrogram_y_range,
        test_playback,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            print(f"Running {test.__name__}...")
            test()
            passed += 1
        except Exception as exc:
            print(f"  [FAIL] {test.__name__}: {exc}")
            import traceback
            traceback.print_exc()
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Run tests first
    all_passed = run_all_tests()

    if "--demo" in sys.argv or len(sys.argv) > 1 and sys.argv[1] != "--demo":
        # Launch interactive demo
        print()
        print("Launching interactive demo...")
        from audio_viewer import _demo
        # Don't call sys.exit from _demo, we already have an app
        viewer = AudioViewerWidget(
            show_waveform=True,
            show_spectrogram=True,
            show_transport=True,
            show_chunk_nav=True)
        viewer.setWindowTitle("AudioViewerWidget — Test Demo")
        viewer.resize(1000, 700)
        viewer.show()

        # Use file from arg or generate synthetic
        path = None
        for a in sys.argv[1:]:
            if a != "--demo" and os.path.isfile(a):
                path = a
                break

        if path:
            viewer.load_audio(path)
            viewer.audioLoaded.connect(
                lambda p: print(f"Demo loaded: {p} ({viewer.duration:.1f}s)"))
        else:
            y, sr = _generate_test_audio(duration=10.0)
            viewer.load_audio_array(y, sr, "<synthetic>")
            times = np.array([0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5])
            viewer.set_onset_markers(times, draggable=True)
            print(f"Demo: synthetic audio ({viewer.duration:.1f}s)")

        sys.exit(app.exec())
    else:
        sys.exit(0 if all_passed else 1)
