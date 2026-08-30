"""
Camera endpoints: an MJPEG live-view stream (works directly in an <img> tag,
no WebSocket/WebRTC plumbing needed) plus brightness/contrast/exposure/focus
controls and a single-frame capture. Which `CameraSource` backs this is
chosen once from `config.yaml -> camera.source`.
"""
from __future__ import annotations

import threading
import time

import cv2
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.camera.base import CameraSource
from app.camera.insight_native_source import InSightNativeSource
from app.camera.opencv_generic_source import OpenCVGenericSource
from app.camera.video_file_source import VideoFileSource
from app.config import BACKEND_DIR, get_settings
from app.logging_setup import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/camera", tags=["camera"])

settings = get_settings()

STREAM_FPS = 15  # tunable: lower = less CPU/bandwidth, higher = smoother preview


def _build_source() -> CameraSource:
    source_name = settings.camera.source
    if source_name == "video_file":
        path = BACKEND_DIR / settings.camera.demo_video_path
        return VideoFileSource(str(path))
    if source_name == "opencv_generic":
        return OpenCVGenericSource(settings.camera.device_index)
    if source_name == "insight_native":
        return InSightNativeSource(settings.camera.insight_ip)
    raise ValueError(f"Unknown camera.source {source_name!r} in config.yaml")


camera_source: CameraSource = _build_source()
_start_lock = threading.Lock()
_started = False


def ensure_started() -> None:
    global _started
    with _start_lock:
        if not _started:
            camera_source.start()
            _started = True


class CameraSettingsRequest(BaseModel):
    brightness: float | None = None
    contrast: float | None = None
    exposure: float | None = None
    focus_position: int | None = None


@router.get("/settings")
def get_settings_endpoint() -> dict:
    ensure_started()
    return camera_source.get_settings()


@router.post("/settings")
def set_settings(body: CameraSettingsRequest) -> dict:
    ensure_started()
    if body.brightness is not None:
        camera_source.set_brightness(body.brightness)
    if body.contrast is not None:
        camera_source.set_contrast(body.contrast)
    if body.exposure is not None:
        camera_source.set_exposure(body.exposure)
    if body.focus_position is not None:
        camera_source.set_focus(body.focus_position)
    return camera_source.get_settings()


@router.get("/capture")
def capture() -> Response:
    ensure_started()
    try:
        frame = camera_source.get_frame()
    except (RuntimeError, NotImplementedError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode captured frame as JPEG")
    return Response(content=buf.tobytes(), media_type="image/jpeg")


def _mjpeg_generator():
    period = 1.0 / STREAM_FPS
    while True:
        start = time.monotonic()
        try:
            frame = camera_source.get_frame()
            ok, buf = cv2.imencode(".jpg", frame)
            if ok:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
        except Exception:
            logger.exception("Camera stream frame failed; stopping this client's stream")
            return
        elapsed = time.monotonic() - start
        time.sleep(max(0.0, period - elapsed))


@router.get("/stream")
def stream() -> StreamingResponse:
    ensure_started()
    return StreamingResponse(_mjpeg_generator(), media_type="multipart/x-mixed-replace; boundary=frame")
