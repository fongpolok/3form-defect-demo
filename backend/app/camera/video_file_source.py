"""
Loops a recorded clip as a stand-in camera. Works today with no hardware —
this is what the demo/pitch runs against until a real camera is wired up.
`brightness`/`contrast` are real (applied per-frame via OpenCV's
convertScaleAbs, the same linear transform a real camera's ISP does).
`exposure`/`focus` are stored but are no-ops here — you can't refocus or
re-expose a file that was already recorded; they exist so the UI/recipe
schema doesn't have to change when a real camera source is swapped in.
"""
from __future__ import annotations

import threading

import cv2
import numpy as np

from app.camera.base import CameraSource
from app.logging_setup import get_logger

logger = get_logger(__name__)


class VideoFileSource(CameraSource):
    def __init__(self, path: str, loop: bool = True) -> None:
        self._path = path
        self._loop = loop
        self._cap: cv2.VideoCapture | None = None
        self._lock = threading.Lock()
        self._brightness = 0.0   # -100..100, added after contrast scaling
        self._contrast = 1.0     # 0.1..3.0, multiplicative
        self._exposure = 0.0     # stored only, no-op (see module docstring)
        self._focus = 0          # stored only, no-op

    def start(self) -> None:
        with self._lock:
            self._cap = cv2.VideoCapture(self._path)
            if not self._cap.isOpened():
                raise RuntimeError(f"Could not open demo video at {self._path!r}")
        logger.info("VideoFileSource started: %s", self._path)

    def get_frame(self) -> np.ndarray:
        with self._lock:
            if self._cap is None:
                raise RuntimeError("start() must be called before get_frame()")
            ok, frame = self._cap.read()
            if not ok:
                if not self._loop:
                    raise RuntimeError("Video ended and loop=False")
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self._cap.read()
                if not ok:
                    raise RuntimeError(f"Demo video at {self._path!r} produced no frames")
            brightness, contrast = self._brightness, self._contrast
        return cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness)

    def set_brightness(self, value: float) -> None:
        self._brightness = value

    def set_contrast(self, value: float) -> None:
        self._contrast = value

    def set_exposure(self, value: float) -> None:
        self._exposure = value  # no-op, see module docstring

    def set_focus(self, position: int) -> None:
        self._focus = position  # no-op, see module docstring

    def get_settings(self) -> dict:
        return {
            "brightness": self._brightness,
            "contrast": self._contrast,
            "exposure": self._exposure,
            "focus_position": self._focus,
            "exposure_and_focus_are_noop": True,
        }

    def stop(self) -> None:
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
        logger.info("VideoFileSource stopped")
