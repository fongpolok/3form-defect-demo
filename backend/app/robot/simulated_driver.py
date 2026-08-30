"""
Pure-kinematic dummy robot. No hardware, no network calls — it just tracks 6
joint angles and animates moves between them over a realistic-looking
duration, so the pendant has something real to jog against before any
physical UR5e exists. Every other driver (`ur5e_rtde_driver.py`,
`robodk_driver.py`) implements the same `RobotDriver` interface, so this can
be swapped out in `config.yaml` without touching the API or frontend.
"""
from __future__ import annotations

import asyncio
import math
from typing import Awaitable, Callable

from app.logging_setup import get_logger
from app.robot.base import RobotDriver
from app.safety import MotionBlockedError, StopManager

logger = get_logger(__name__)

NUM_JOINTS = 6
STEP_DT = 0.02  # seconds between interpolation frames — tunable smoothness/CPU tradeoff

# A UR5e's real joint limits are roughly +-360 deg on every joint; this is
# only used to keep the dummy from reporting nonsense, not a safety limit.
JOINT_LIMIT_RAD = 2 * math.pi


class SimulatedRobotDriver(RobotDriver):
    def __init__(
        self,
        stop_manager: StopManager,
        home_position_rad: list[float] | None = None,
    ) -> None:
        self._stop_manager = stop_manager
        self._positions: list[float] = list(home_position_rad or [0.0] * NUM_JOINTS)
        self._aborted = False
        self._moving = False
        self.on_pose_changed: Callable[[list[float]], Awaitable[None]] | None = None
        stop_manager.register_abort_callback(self._abort)
        logger.info("SimulatedRobotDriver initialised at %s", self._positions)

    def _abort(self) -> None:
        if self._moving:
            logger.warning("Simulated move aborted by hard-stop")
        self._aborted = True

    def get_joint_positions(self) -> list[float]:
        return list(self._positions)

    async def move_joints(self, joint_positions: list[float], speed: float = 0.5, acceleration: float = 0.5) -> None:
        self._stop_manager.guard()
        if len(joint_positions) != NUM_JOINTS:
            raise ValueError(f"Expected {NUM_JOINTS} joint values, got {len(joint_positions)}")
        for v in joint_positions:
            if abs(v) > JOINT_LIMIT_RAD:
                raise ValueError(f"Joint target {v:.3f} rad exceeds +-{JOINT_LIMIT_RAD:.3f} rad limit")

        speed = max(speed, 0.01)
        start = list(self._positions)
        delta = [t - s for t, s in zip(joint_positions, start)]
        max_delta = max(abs(d) for d in delta)
        if max_delta < 1e-6:
            return  # already there

        duration = max(max_delta / speed, STEP_DT)
        steps = max(int(duration / STEP_DT), 1)

        self._aborted = False
        self._moving = True
        logger.info("Move start: %s -> %s (speed=%.2f, ~%.2fs)", start, joint_positions, speed, duration)
        try:
            for i in range(1, steps + 1):
                if self._aborted or self._stop_manager.is_stopped:
                    logger.warning("Move interrupted at step %d/%d", i, steps)
                    raise MotionBlockedError("Move aborted: stop was triggered mid-motion")
                frac = i / steps
                self._positions = [s + d * frac for s, d in zip(start, delta)]
                await self._notify()
                await asyncio.sleep(STEP_DT)
            self._positions = list(joint_positions)
            await self._notify()
            logger.info("Move complete: %s", self._positions)
        finally:
            self._moving = False

    async def jog_joint(self, joint_index: int, delta_radians: float) -> None:
        if not 0 <= joint_index < NUM_JOINTS:
            raise ValueError(f"joint_index must be 0-{NUM_JOINTS - 1}")
        target = list(self._positions)
        target[joint_index] += delta_radians
        await self.move_joints(target, speed=0.5, acceleration=0.5)

    def stop(self) -> None:
        self._abort()

    def dispose(self) -> None:
        logger.info("SimulatedRobotDriver disposed")

    async def _notify(self) -> None:
        if self.on_pose_changed is not None:
            await self.on_pose_changed(list(self._positions))
