"""
Exports a RoboDK program two ways: as a post-processed robot program
(URScript, via RoboDK's UR post-processor) for eventual real-robot use, and
as a plain joint-waypoint list consumable directly by
`app/robot/simulated_driver.py` or `ur5e_rtde_driver.py` without needing
RoboDK at all at playback time.

UNVERIFIED — see cad_import.py's docstring.
"""
from __future__ import annotations

from pathlib import Path

from app.logging_setup import get_logger

logger = get_logger(__name__)


def export_urscript(program_item, output_dir: Path, robot_post: str = "Universal Robots") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_path = program_item.MakeProgram(str(output_dir))
    if not saved_path:
        raise RuntimeError("RoboDK program export failed (MakeProgram returned nothing)")
    logger.info("Exported RoboDK program to %s", saved_path)
    return Path(saved_path)


def export_joint_waypoints(robot_item, targets) -> list[list[float]]:
    """Solves inverse kinematics for each target and returns the joint
    angles (degrees) in order, so the simulated/real driver can replay the
    path without RoboDK being installed at playback time."""
    waypoints: list[list[float]] = []
    for target in targets:
        joints = robot_item.SolveIK(target.Pose())
        if joints is None or len(joints) == 0:
            raise RuntimeError(f"No IK solution for target {target.Name()!r}")
        waypoints.append(list(joints))
    logger.info("Solved %d joint waypoints from RoboDK targets", len(waypoints))
    return waypoints
