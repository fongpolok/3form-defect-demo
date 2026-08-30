"""
Common interface every robot backend implements, so the rest of the app
(pendant UI, recipe runner, RoboDK path export) doesn't care whether it's
talking to the pure-kinematic dummy, a real UR5e over RTDE, or a RoboDK
station. `move_joints`/`jog_joint` are async because a real move takes
real time and must stay interruptible by a hard-stop without blocking
the FastAPI event loop.

Every implementation MUST call `stop_manager.guard()` as the first line of
every motion-issuing method, and register an abort callback with the
`StopManager` in `__init__` so a hard-stop can interrupt a move already in
flight — see `app/safety/estop.py` and `simulated_driver.py` for the pattern.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class RobotDriver(ABC):
    @abstractmethod
    def get_joint_positions(self) -> list[float]:
        """Radians, 6 elements."""

    @abstractmethod
    async def move_joints(self, joint_positions: list[float], speed: float, acceleration: float) -> None:
        """Move to an absolute joint-space target. Must call stop_manager.guard() first."""

    @abstractmethod
    async def jog_joint(self, joint_index: int, delta_radians: float) -> None:
        """Relative move of a single joint, used by pendant +/- buttons. Must call stop_manager.guard() first."""

    @abstractmethod
    def stop(self) -> None:
        """Immediately halt any in-progress motion (called by the hard-stop path)."""

    @abstractmethod
    def dispose(self) -> None:
        """Release any hardware/network resources."""
