"""
Common interface for the three defect-detection options standing in for
ViDi (see plan section 3). All three take/return the same shapes so the
Detection page can swap between them live and a recipe step can just record
which one to use, mirroring how the old grid stored a `.vrws` path per row.
"""
from __future__ import annotations

import base64
from abc import ABC, abstractmethod

import cv2
import numpy as np
from pydantic import BaseModel


class DefectBox(BaseModel):
    x: int
    y: int
    w: int
    h: int
    score: float


class DetectionResult(BaseModel):
    detector: str
    pass_fail: str  # "pass" | "fail"
    score: float     # higher = more likely defective
    threshold: float
    boxes: list[DefectBox]
    overlay_image_b64: str  # JPEG, base64-encoded, defect regions highlighted


class DefectDetector(ABC):
    name: str

    @abstractmethod
    def load(self, golden_images: list[np.ndarray]) -> None:
        """Prepare the detector from reference "good" images. No labeled defects required
        for options A/B; option C additionally needs a trained weights file — see its
        own docstring for what happens when one isn't available yet."""

    @abstractmethod
    def infer(self, image: np.ndarray) -> DetectionResult:
        """Run the detector on one BGR image."""


def encode_overlay(image_bgr: np.ndarray) -> str:
    ok, buf = cv2.imencode(".jpg", image_bgr)
    if not ok:
        raise RuntimeError("Failed to JPEG-encode overlay image")
    return base64.b64encode(buf.tobytes()).decode("ascii")
