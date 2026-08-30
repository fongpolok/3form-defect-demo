"""
Detection option A: classical rule-based blob analysis. No training data
needed — compare each captured image against an averaged "golden" reference
built from a handful of known-good images, threshold the difference, clean
up with morphology, and flag surviving blobs bigger than a tunable size.
This is the same category of technique as a traditional Cognex "blob tool",
just OpenCV instead of VisionPro.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.logging_setup import get_logger
from app.vision.base import DefectBox, DefectDetector, DetectionResult, encode_overlay

logger = get_logger(__name__)


class ClassicalOpenCVDetector(DefectDetector):
    name = "classical"

    def __init__(
        self,
        diff_threshold: int = 30,
        min_blob_area: int = 40,
        blur_ksize: int = 5,
        fail_area_threshold: float = 40.0,
    ) -> None:
        self.diff_threshold = diff_threshold
        self.min_blob_area = min_blob_area
        self.blur_ksize = blur_ksize if blur_ksize % 2 == 1 else blur_ksize + 1
        self.fail_area_threshold = fail_area_threshold
        self._golden_gray: np.ndarray | None = None

    def load(self, golden_images: list[np.ndarray]) -> None:
        if not golden_images:
            raise ValueError("ClassicalOpenCVDetector needs at least one golden (good) image")
        grays = [cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) for img in golden_images]
        shape = grays[0].shape
        grays = [g if g.shape == shape else cv2.resize(g, (shape[1], shape[0])) for g in grays]
        self._golden_gray = np.mean(np.stack(grays), axis=0).astype(np.uint8)
        logger.info("ClassicalOpenCVDetector loaded %d golden image(s)", len(golden_images))

    def infer(self, image: np.ndarray) -> DetectionResult:
        if self._golden_gray is None:
            raise RuntimeError("load() must be called before infer()")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if gray.shape != self._golden_gray.shape:
            gray = cv2.resize(gray, (self._golden_gray.shape[1], self._golden_gray.shape[0]))
            image = cv2.resize(image, (self._golden_gray.shape[1], self._golden_gray.shape[0]))

        k = (self.blur_ksize, self.blur_ksize)
        diff = cv2.absdiff(cv2.GaussianBlur(gray, k, 0), cv2.GaussianBlur(self._golden_gray, k, 0))
        _, mask = cv2.threshold(diff, self.diff_threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes: list[DefectBox] = []
        for c in contours:
            area = cv2.contourArea(c)
            if area >= self.min_blob_area:
                x, y, w, h = cv2.boundingRect(c)
                boxes.append(DefectBox(x=x, y=y, w=w, h=h, score=float(area)))

        total_area = sum(b.score for b in boxes)
        overlay = image.copy()
        for b in boxes:
            cv2.rectangle(overlay, (b.x, b.y), (b.x + b.w, b.y + b.h), (0, 0, 255), 2)

        return DetectionResult(
            detector=self.name,
            pass_fail="fail" if total_area >= self.fail_area_threshold else "pass",
            score=float(total_area),
            threshold=self.fail_area_threshold,
            boxes=boxes,
            overlay_image_b64=encode_overlay(overlay),
        )
