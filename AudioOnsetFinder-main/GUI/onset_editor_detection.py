"""Detection worker helpers extracted from the onset editor workbench."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QThread, pyqtSignal


class _DetectOnsetsWorker(QThread):
    """Run onset detection off the main thread so the UI stays responsive."""

    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(
        self,
        y_slice,
        sr,
        n_requested,
        *,
        settings=None,
        signal_profile=None,
        hop_length=256,
        initial_delta=0.3,
        backtrack=True,
        min_ioi_ms=30,
        amplitude_gate=0.0,
        sharpness_gate=0.0,
        cluster_enabled=True,
        cluster_window_ms=25,
        refine_enabled=True,
        refine_window_ms=10.0,
        run_detection: Callable[..., list[float]] | None = None,
    ):
        super().__init__()
        self._y_slice = y_slice
        self._sr = sr
        self._n_requested = n_requested
        self._signal_profile = signal_profile
        self._settings = dict(
            settings
            or {
                "ONSET_METHOD": "librosa",
                "ONSET_HOP_LENGTH": hop_length,
                "ONSET_DELTA": initial_delta,
                "ONSET_BACKTRACK": backtrack,
                "MIN_INTER_ONSET_MS": min_ioi_ms,
                "ONSET_AMPLITUDE_GATE": amplitude_gate,
                "ONSET_SHARPNESS_GATE": sharpness_gate,
                "CLUSTER_OVERLAPPING_ONSETS": cluster_enabled,
                "ONSET_CLUSTER_WINDOW_MS": cluster_window_ms,
                "ONSET_REFINE_ENABLED": refine_enabled,
                "ONSET_REFINE_WINDOW_MS": refine_window_ms,
            }
        )
        self._run_detection = run_detection
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        if self._run_detection is None:
            self.error.emit("No onset detection callback was configured.")
            return

        try:
            result = self._run_detection(
                self._y_slice,
                self._sr,
                self._n_requested,
                settings=self._settings,
                signal_profile=self._signal_profile,
                _cancel_flag=self,
            )
            if self._cancelled:
                self.finished.emit([])
            else:
                self.finished.emit(result)
        except Exception as exc:
            if self._cancelled:
                self.finished.emit([])
            else:
                self.error.emit(str(exc))


__all__ = ["_DetectOnsetsWorker"]