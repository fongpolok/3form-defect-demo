"""
Detection endpoints: list the three detectors and their ready/blocked
status, and run one against either a live camera capture or a named sample
image (see backend/data/sample_images/, synthetic — see its generator
script). Options A and B (classical, patchcore) load automatically from the
bundled "good" sample images; option C (yolo) stays unready until trained
weights exist — see app/vision/trained_yolo.py.
"""
from __future__ import annotations

import glob
import threading

import cv2
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.routers.camera import camera_source, ensure_started
from app.config import BACKEND_DIR
from app.logging_setup import get_logger
from app.vision.anomaly_patchcore import PatchCoreDetector
from app.vision.base import DefectDetector, DetectionResult
from app.vision.classical_opencv import ClassicalOpenCVDetector
from app.vision.trained_yolo import YoloDetector

logger = get_logger(__name__)
router = APIRouter(prefix="/api/vision", tags=["vision"])

SAMPLE_DIR = BACKEND_DIR / "data" / "sample_images"

detectors: dict[str, DefectDetector] = {
    "classical": ClassicalOpenCVDetector(),
    "patchcore": PatchCoreDetector(),
    "yolo": YoloDetector(weights_path=None),  # no labeled data yet — see trained_yolo.py
}
_ready: dict[str, bool] = {name: False for name in detectors}
_load_lock = threading.Lock()


def _load_all() -> None:
    with _load_lock:
        golden_paths = sorted(glob.glob(str(SAMPLE_DIR / "good_*.png")))
        golden_images = [cv2.imread(p) for p in golden_paths]
        golden_images = [g for g in golden_images if g is not None]

        for name, detector in detectors.items():
            if _ready[name]:
                continue
            try:
                detector.load(golden_images)
                _ready[name] = True
                logger.info("Detector %r ready", name)
            except Exception as exc:
                logger.warning("Detector %r not ready: %s", name, exc)


_load_all()


class DetectorInfo(BaseModel):
    name: str
    ready: bool
    note: str | None = None


@router.get("/detectors", response_model=list[DetectorInfo])
def list_detectors() -> list[DetectorInfo]:
    notes = {
        "classical": "Golden-template diff + blob analysis. No labeled data needed.",
        "patchcore": "Pretrained-backbone anomaly detection. No labeled data needed.",
        "yolo": "Supervised YOLOv8. Needs labeled good/defect images to train — none collected yet."
                if not _ready["yolo"] else "Trained weights loaded.",
    }
    return [DetectorInfo(name=n, ready=_ready[n], note=notes.get(n)) for n in detectors]


@router.get("/samples", response_model=list[str])
def list_samples() -> list[str]:
    return sorted(p.name for p in SAMPLE_DIR.glob("*.png"))


class InferRequest(BaseModel):
    sample_name: str | None = None  # omit to use a live camera capture instead


@router.post("/infer/{detector_name}", response_model=DetectionResult)
def infer(detector_name: str, body: InferRequest) -> DetectionResult:
    if detector_name not in detectors:
        raise HTTPException(status_code=404, detail=f"Unknown detector {detector_name!r}")
    if not _ready[detector_name]:
        raise HTTPException(status_code=503, detail=f"Detector {detector_name!r} is not ready yet")

    if body.sample_name:
        path = SAMPLE_DIR / body.sample_name
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"No sample image {body.sample_name!r}")
        image = cv2.imread(str(path))
    else:
        ensure_started()
        image = camera_source.get_frame()

    try:
        return detectors[detector_name].infer(image)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
