"""
RoboDK endpoints. Path generation from an uploaded mesh works standalone
(pure geometry, see path_generation.py) regardless of whether the RoboDK
desktop app is installed; simulate/export need a live RoboDK connection and
return 503 with a clear message if it's not available — see
robodk_client.py. In this environment RoboDK is NOT installed (confirmed
2026-08-27), so /status will report unavailable and /simulate,/export are
untestable here — they're still real code, just unverified against a live
instance.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import BACKEND_DIR
from app.logging_setup import get_logger
from app.robodk_integration.path_generation import Viewpoint, generate_scan_viewpoints, load_mesh
from app.robodk_integration.robodk_client import RoboDKUnavailableError, get_robolink

logger = get_logger(__name__)
router = APIRouter(prefix="/api/robodk", tags=["robodk"])

UPLOAD_DIR = BACKEND_DIR / "data" / "cad_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Last generated path, kept in memory so /simulate can reuse it without
# re-uploading — fine for a single-operator demo station, not multi-user safe.
_last_mesh_path: Path | None = None
_last_viewpoints: list[Viewpoint] = []


class StatusResponse(BaseModel):
    available: bool
    message: str


@router.get("/status", response_model=StatusResponse)
def status() -> StatusResponse:
    try:
        get_robolink()
        return StatusResponse(available=True, message="Connected to RoboDK")
    except RoboDKUnavailableError as exc:
        return StatusResponse(available=False, message=str(exc))


class ViewpointsResponse(BaseModel):
    viewpoints: list[Viewpoint]
    mesh_area_mm2: float
    robodk_simulation_available: bool


@router.post("/generate-path", response_model=ViewpointsResponse)
async def generate_path(
    file: UploadFile,
    standoff_mm: float = 100.0,
    spacing_mm: float = 20.0,
    max_points: int = 200,
) -> ViewpointsResponse:
    global _last_mesh_path, _last_viewpoints

    dest = UPLOAD_DIR / file.filename
    contents = await file.read()
    dest.write_bytes(contents)
    logger.info("Saved uploaded CAD file to %s (%d bytes)", dest, len(contents))

    try:
        mesh = load_mesh(str(dest))
        viewpoints = generate_scan_viewpoints(mesh, standoff_mm, spacing_mm, max_points)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    _last_mesh_path = dest
    _last_viewpoints = viewpoints

    from app.robodk_integration.robodk_client import is_available
    return ViewpointsResponse(
        viewpoints=viewpoints,
        mesh_area_mm2=float(mesh.area),
        robodk_simulation_available=is_available(),
    )


@router.post("/simulate")
def simulate() -> dict:
    if _last_mesh_path is None or not _last_viewpoints:
        raise HTTPException(status_code=400, detail="Call /generate-path first")

    try:
        rdk = get_robolink()
    except RoboDKUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    from app.robodk_integration.cad_import import import_cad
    from app.robodk_integration.simulate import build_targets, run_and_capture

    part = import_cad(rdk, str(_last_mesh_path))
    robot = rdk.ItemUserPick("Select the robot", rdk.ITEM_TYPE_ROBOT)
    if not robot.Valid():
        raise HTTPException(status_code=400, detail="No robot selected/available in the RoboDK station")

    targets = build_targets(rdk, _last_viewpoints, part)
    output_dir = BACKEND_DIR / "data" / "robodk_frames"
    frames = run_and_capture(rdk, robot, targets, output_dir)
    return {"frame_count": len(frames), "output_dir": str(output_dir)}
