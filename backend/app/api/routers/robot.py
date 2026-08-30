"""
Robot endpoints: live pose, absolute/relative moves, and the Phase-1 demo
move kept as-is (see its own docstring). Which `RobotDriver` implementation
backs these is chosen once at import time from `config.yaml -> robot.driver`
— swapping in a real UR5e later is a one-line config change, not a rewrite.
"""
from __future__ import annotations

import asyncio
import math
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.ws import ws_manager
from app.config import get_settings
from app.logging_setup import get_logger
from app.robot.base import RobotDriver
from app.robot.simulated_driver import NUM_JOINTS, SimulatedRobotDriver
from app.safety import MotionBlockedError, stop_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/api/robot", tags=["robot"])

settings = get_settings()


def _build_driver() -> RobotDriver:
    driver_name = settings.robot.driver
    if driver_name == "simulated":
        return SimulatedRobotDriver(stop_manager)
    if driver_name == "ur5e_rtde":
        raise NotImplementedError(
            "robot.driver=ur5e_rtde selected, but no physical UR5e is on hand to "
            "test against yet (see Plan section 6). ur5e_rtde_driver.py isn't wired "
            "up here — switch config.yaml back to 'simulated' or implement it once "
            "hardware is available."
        )
    if driver_name == "robodk":
        raise NotImplementedError(
            "robot.driver=robodk selected, but this requires the RoboDK desktop app "
            "installed and running, which isn't available on this machine. Switch "
            "config.yaml back to 'simulated'."
        )
    raise ValueError(f"Unknown robot.driver {driver_name!r} in config.yaml")


robot_driver: RobotDriver = _build_driver()
logger.info("Robot driver in use: %s", type(robot_driver).__name__)

if isinstance(robot_driver, SimulatedRobotDriver):
    async def _broadcast_pose(joints_rad: list[float]) -> None:
        await ws_manager.broadcast({
            "type": "robot_pose",
            "joints_deg": [math.degrees(r) for r in joints_rad],
        })

    robot_driver.on_pose_changed = _broadcast_pose


class PoseResponse(BaseModel):
    joints_deg: list[float]


class MoveRequest(BaseModel):
    joints_deg: list[float]
    speed: float = settings.robot.default_speed
    acceleration: float = settings.robot.default_acceleration


class JogRequest(BaseModel):
    joint_index: int
    delta_deg: float
    speed: float = settings.robot.default_speed


@router.get("/pose", response_model=PoseResponse)
def get_pose() -> PoseResponse:
    return PoseResponse(joints_deg=[math.degrees(r) for r in robot_driver.get_joint_positions()])


@router.post("/move", response_model=PoseResponse)
async def move(body: MoveRequest) -> PoseResponse:
    if len(body.joints_deg) != NUM_JOINTS:
        raise HTTPException(status_code=422, detail=f"Expected {NUM_JOINTS} joint values")
    try:
        await robot_driver.move_joints(
            [math.radians(d) for d in body.joints_deg], body.speed, body.acceleration
        )
    except MotionBlockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PoseResponse(joints_deg=[math.degrees(r) for r in robot_driver.get_joint_positions()])


@router.post("/jog", response_model=PoseResponse)
async def jog(body: JogRequest) -> PoseResponse:
    try:
        await robot_driver.jog_joint(body.joint_index, math.radians(body.delta_deg))
    except MotionBlockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PoseResponse(joints_deg=[math.degrees(r) for r in robot_driver.get_joint_positions()])


class DemoMoveResponse(BaseModel):
    moved: bool
    duration_seconds: float


@router.post("/demo-move", response_model=DemoMoveResponse)
async def demo_move() -> DemoMoveResponse:
    """
    Phase-1 placeholder kept for its original purpose: a trivial ~1s "move"
    used by the frontend's first proof-of-wiring page and its test. The real
    pendant (Phase 2 onward) uses /move and /jog above, which actually drive
    `robot_driver`.
    """
    try:
        stop_manager.guard()
    except MotionBlockedError as exc:
        logger.info("Demo move refused: %s", exc)
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    start = time.monotonic()
    logger.info("Demo move started")
    await asyncio.sleep(1.0)
    duration = time.monotonic() - start
    logger.info("Demo move finished (%.2fs)", duration)
    return DemoMoveResponse(moved=True, duration_seconds=duration)
