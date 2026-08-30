"""
Detection option C: a small supervised YOLOv8 detector — the closest analog
to how ViDi's supervised mode was used (label defects, train a model). This
is the highest-accuracy option once real labeled defect images exist, and
the least useful right now, since none do yet.

This module is fully wired to `ultralytics` and will train/run for real —
it does NOT fake a result when no trained weights are available. `infer()`
raises a clear "not trained yet" error instead of pretending to detect
anything, per the plan's "don't fake a blocked capability" rule.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.logging_setup import get_logger
from app.vision.base import DefectBox, DefectDetector, DetectionResult, encode_overlay

logger = get_logger(__name__)

NOT_TRAINED_MESSAGE = (
    "No trained YOLO weights available. This detector needs a folder of "
    "labeled good/defect images to train on — none exist yet. Use the "
    "'classical' or 'patchcore' detectors until labeled data is collected, "
    "then call train_yolo_detector() below to produce weights for this one."
)


class YoloDetector(DefectDetector):
    name = "yolo"

    def __init__(self, weights_path: str | None = None, confidence: float = 0.25) -> None:
        self.weights_path = weights_path
        self.confidence = confidence
        self._model = None

    def load(self, golden_images: list[np.ndarray]) -> None:
        # Unlike the other two, this detector doesn't learn from golden
        # images at request time — it loads a weights file that was
        # produced ahead of time by train_yolo_detector(). golden_images
        # is accepted only to satisfy the shared DefectDetector interface.
        #
        # Raises (rather than just logging) when no weights exist, so the
        # caller's ready-tracking — "did load() succeed?" — reports this
        # detector as not ready instead of silently marking it ready with
        # nothing loaded.
        if self.weights_path and Path(self.weights_path).exists():
            from ultralytics import YOLO
            self._model = YOLO(self.weights_path)
            logger.info("YoloDetector loaded weights from %s", self.weights_path)
        else:
            self._model = None
            raise RuntimeError(NOT_TRAINED_MESSAGE)

    def infer(self, image: np.ndarray) -> DetectionResult:
        if self._model is None:
            raise RuntimeError(NOT_TRAINED_MESSAGE)

        results = self._model.predict(image, conf=self.confidence, verbose=False)[0]
        boxes: list[DefectBox] = []
        overlay = image.copy()
        for box in results.boxes:
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
            score = float(box.conf[0])
            boxes.append(DefectBox(x=int(x1), y=int(y1), w=int(x2 - x1), h=int(y2 - y1), score=score))
            cv2.rectangle(overlay, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)

        overall_score = max((b.score for b in boxes), default=0.0)
        return DetectionResult(
            detector=self.name,
            pass_fail="fail" if boxes else "pass",
            score=overall_score,
            threshold=self.confidence,
            boxes=boxes,
            overlay_image_b64=encode_overlay(overlay),
        )


def train_yolo_detector(
    data_yaml_path: str,
    output_weights_dir: str,
    epochs: int = 50,
    image_size: int = 640,
    base_model: str = "yolov8n.pt",
) -> str:
    """
    Trains a small YOLOv8 detector on a labeled dataset once one exists.
    `data_yaml_path` follows ultralytics' standard dataset YAML format
    (train/val image dirs + class names). Returns the path to best.pt.

    Not covered by automated tests — there is no labeled dataset to train
    on yet, so this is exercised manually once real defect images and
    labels are available.
    """
    from ultralytics import YOLO

    logger.info("Training YOLO detector: data=%s epochs=%d imgsz=%d", data_yaml_path, epochs, image_size)
    model = YOLO(base_model)
    results = model.train(data=data_yaml_path, epochs=epochs, imgsz=image_size, project=output_weights_dir)
    best_path = Path(results.save_dir) / "weights" / "best.pt"
    logger.info("YOLO training complete: %s", best_path)
    return str(best_path)
