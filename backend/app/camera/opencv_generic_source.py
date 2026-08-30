"""
Any UVC/GigE camera OpenCV can open via VideoCapture(device_index) — a
laptop webcam, a USB inspection camera, anything generic. Real
brightness/contrast/exposure controls where the underlying driver exposes
them (OpenCV's CAP_PROP_* are best-effort and vary a lot by OS/driver, which
is why every set_* here logs whether the device actually accepted it rather
than assuming success).
"""
from __future__ import annotations

import threading

import cv2
import numpy as np

from app.camera.base import CameraSource
from app.logging_setup import get_logger

logger = get_logger(__name__)


class OpenCVGenericSource(CameraSource):
    def __init__(self, device_index: int = 0) -> None:
        self._device_index = device_index
        self._cap: cv2.VideoCapture | None = None
        self._lock = threading.Lock()
        self._focus = 0

    def start(self) -> None:
        with self._lock:
            self._cap = cv2.VideoCapture(self._device_index)
            if not self._cap.isOpened():
                raise RuntimeError(f"Could not open camera device index {self._device_index}")
        logger.info("OpenCVGenericSource started: device %d", self._device_index)

    def get_frame(self) -> np.ndarray:
        with self._lock:
            if self._cap is None:
                raise RuntimeError("start() must be called before get_frame()")
            ok, frame = self._cap.read()
        if not ok:
            raise RuntimeError(f"Failed to read a frame from device {self._device_index}")
        return frame

    def _set_prop(self, prop_id: int, value: float, label: str) -> None:
        with self._lock:
            if self._cap is None:
                raise RuntimeError("start() must be called first")
            accepted = self._cap.set(prop_id, value)
        if not accepted:
            logger.warning("Device %d rejected %s=%s (driver may not support it)",
                            self._device_index, label, value)

    def set_brightness(self, value: float) -> None:
        self._set_prop(cv2.CAP_PROP_BRIGHTNESS, value, "brightness")

    def set_contrast(self, value: float) -> None:
        self._set_prop(cv2.CAP_PROP_CONTRAST, value, "contrast")

    def set_exposure(self, value: float) -> None:
        self._set_prop(cv2.CAP_PROP_EXPOSURE, value, "exposure")

    def set_focus(self, position: int) -> None:
        self._focus = position
        self._set_prop(cv2.CAP_PROP_FOCUS, position, "focus")

    def get_settings(self) -> dict:
        with self._lock:
            if self._cap is None:
                return {}
            return {
                "brightness": self._cap.get(cv2.CAP_PROP_BRIGHTNESS),
                "contrast": self._cap.get(cv2.CAP_PROP_CONTRAST),
                "exposure": self._cap.get(cv2.CAP_PROP_EXPOSURE),
                "focus_position": self._focus,
            }

    def stop(self) -> None:
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
        logger.info("OpenCVGenericSource stopped")
