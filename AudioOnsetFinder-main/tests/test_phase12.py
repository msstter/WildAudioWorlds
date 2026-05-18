"""Headless tests for Phase-12 AudioPreviewWindow changes.

This module is both:
- a normal pytest test module for CI collection, and
- a direct script entrypoint used by the local `phase12` helper command.
"""

import os
import sys
import time

import numpy as np
from PyQt6.QtWidgets import QApplication


os.environ["QT_QPA_PLATFORM"] = "offscreen"

TESTS_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.join(TESTS_DIR, "..")
GUI_ROOT = os.path.join(PROJECT_ROOT, "GUI")

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, GUI_ROOT)

from pipeline_gui import AudioPreviewWindow, MuterPanel


app = QApplication.instance() or QApplication(sys.argv)


def _run_phase12_checks():
    results = []

    def check(label, cond):
        results.append((label, bool(cond)))

    mp = MuterPanel()
    check("MuterPanel has no _preview_btn", not hasattr(mp, "_preview_btn"))
    check("MuterPanel has no _open_preview", not hasattr(mp, "_open_preview"))

    apw = AudioPreviewWindow(muter_panel=mp)
    try:
        check("Has _play_orig_btn", hasattr(apw, "_play_orig_btn"))
        check("Has _play_proc_btn", hasattr(apw, "_play_proc_btn"))
        check("Has _loop_orig_btn", hasattr(apw, "_loop_orig_btn"))
        check("Has _loop_proc_btn", hasattr(apw, "_loop_proc_btn"))
        check("Has _rewind_orig_btn", hasattr(apw, "_rewind_orig_btn"))
        check("Has _rewind_proc_btn", hasattr(apw, "_rewind_proc_btn"))

        for name in (
            "_play_orig_btn",
            "_loop_orig_btn",
            "_rewind_orig_btn",
            "_play_proc_btn",
            "_loop_proc_btn",
            "_rewind_proc_btn",
        ):
            btn = getattr(apw, name)
            check(
                f"{name} fixed size is 38x38",
                btn.maximumWidth() == 38 and btn.maximumHeight() == 38,
            )

        check("_loop_orig_btn is checkable", apw._loop_orig_btn.isCheckable())
        check("_loop_proc_btn is checkable", apw._loop_proc_btn.isCheckable())
        check("_loop_proc_btn starts disabled", not apw._loop_proc_btn.isEnabled())
        check("_rewind_proc_btn starts disabled", not apw._rewind_proc_btn.isEnabled())

        check(
            "_is_loop_active('original') is False",
            apw._is_loop_active("original") is False,
        )
        check(
            "_is_loop_active('processed') is False",
            apw._is_loop_active("processed") is False,
        )

        apw._loop_orig_btn.setChecked(True)
        check(
            "_is_loop_active('original') is True after toggle",
            apw._is_loop_active("original") is True,
        )

        check("Has _bg_cache attribute", hasattr(apw, "_bg_cache"))
        check("_bg_cache starts as None", apw._bg_cache is None)

        sr = 22050
        apw._y_orig = np.random.randn(sr * 5).astype(np.float32)
        apw._sr = sr
        apw._chunk_sec = 5
        apw._y_chunk = apw._y_orig.copy()
        apw._draw()
        app.processEvents()
        time.sleep(0.15)
        app.processEvents()
        check("_bg_cache populated after _draw", apw._bg_cache is not None)

        apw._seek_to(1.5)
        check("Playhead1 visible after visual seek", apw._playhead1.get_visible())
        check("Playhead2 visible after visual seek", apw._playhead2.get_visible())

        apw._playhead1.set_visible(False)
        apw._playhead2.set_visible(False)
        apw._rewind("original")
        check("Rewind orig: playhead1 visible", apw._playhead1.get_visible())
        check("Rewind orig: playhead2 stays hidden", not apw._playhead2.get_visible())

        check("Animation interval is 50ms", apw._anim_timer.interval() == 50)
    finally:
        apw.close()

    return results


def test_phase12_preview_window_smoke():
    failures = [label for label, passed in _run_phase12_checks() if not passed]
    assert not failures, "Phase12 checks failed: " + ", ".join(failures)


def main():
    results = _run_phase12_checks()
    passed_count = 0
    failed_count = 0

    for label, passed in results:
        if passed:
            passed_count += 1
            print(f"  PASS  {label}")
        else:
            failed_count += 1
            print(f"  FAIL  {label}")

    print(f"\n{'=' * 40}")
    print(f"Results: {passed_count} passed, {failed_count} failed out of {len(results)}")
    return 1 if failed_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
