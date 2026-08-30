"""
Builds RoboDK targets from `path_generation.py`'s viewpoints, attaches them
to a program on the given robot, and runs a simulated pass — capturing
periodic screenshots so the frontend can play the simulation back without
needing a live 3D viewer embedded in the browser (see plan section 4).

UNVERIFIED: written against RoboDK's documented Python API but not runnable
here — see cad_import.py's docstring for why. The screenshot-capture calls
in particular (`Cam2D_Snapshot`) are the part most likely to need
adjustment against a real RoboDK install; treat this as a solid starting
point, not a finished, tested implementation.
"""
from __future__ import annotations

from pathlib import Path

from robodk import robomath

from app.logging_setup import get_logger
from app.robodk_integration.path_generation import Viewpoint

logger = get_logger(__name__)


def build_targets(rdk, viewpoints: list[Viewpoint], frame_item, name_prefix: str = "ScanPoint"):
    """Creates one RoboDK target per viewpoint, oriented so the tool Z axis
    points along -normal (i.e. toward the surface)."""
    targets = []
    for i, vp in enumerate(viewpoints):
        # Camera sits at vp.position, looking back toward the surface —
        # i.e. tool Z axis points along -normal.
        z_axis = [-n for n in vp.normal]
        pose = robomath.point_Zaxis_2_pose(vp.position, z_axis)
        target = rdk.AddTarget(f"{name_prefix}_{i:03d}", frame_item)
        target.setPose(pose)
        targets.append(target)
    logger.info("Created %d RoboDK targets", len(targets))
    return targets


def run_and_capture(rdk, robot_item, targets, output_dir: Path, camera_item=None) -> list[Path]:
    """Moves the robot through each target in simulation, saving one
    screenshot per stop into output_dir. Returns the list of image paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    frame_paths: list[Path] = []

    for i, target in enumerate(targets):
        robot_item.MoveJ(target)
        frame_path = output_dir / f"frame_{i:03d}.png"
        if camera_item is not None:
            rdk.Cam2D_Snapshot(str(frame_path), camera_item)
        else:
            rdk.SaveImage(str(frame_path))
        frame_paths.append(frame_path)

    logger.info("Captured %d simulation frames to %s", len(frame_paths), output_dir)
    return frame_paths
