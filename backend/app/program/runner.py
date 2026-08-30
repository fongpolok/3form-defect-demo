"""
Replays a full Recipe end to end — move, (optionally) set camera/light,
capture, detect — tying together the robot, camera, lighting, and vision
modules exactly the way the old app's grid "Do" button did per row, but for
the whole sequence in one pass. This is the piece that makes the pendant's
taught points into an actual automatic inspection cycle.
"""
from __future__ import annotations

import math
from typing import Awaitable, Callable

from pydantic import BaseModel

from app.camera.base import CameraSource
from app.logging_setup import get_logger
from app.program.recipe import Recipe, RecipeStep
from app.robot.base import RobotDriver
from app.safety import MotionBlockedError
from app.vision.base import DefectDetector, DetectionResult

logger = get_logger(__name__)

ProgressCallback = Callable[["StepResult"], Awaitable[None]]


class StepResult(BaseModel):
    step_id: str
    step_name: str
    moved: bool
    detection: DetectionResult | None = None
    error: str | None = None


class RecipeRunner:
    def __init__(
        self,
        robot_driver: RobotDriver,
        camera_source: CameraSource,
        detectors: dict[str, DefectDetector],
        apply_light_pattern: Callable[[object], object],
    ) -> None:
        self._robot = robot_driver
        self._camera = camera_source
        self._detectors = detectors
        self._apply_light_pattern = apply_light_pattern

    async def run(self, recipe: Recipe, on_progress: ProgressCallback | None = None) -> list[StepResult]:
        logger.info("Starting recipe run %r (%d steps)", recipe.name, len(recipe.steps))
        results: list[StepResult] = []
        for step in recipe.steps:
            result = await self._run_step(step)
            results.append(result)
            if on_progress:
                await on_progress(result)
            if result.error and "stop" in result.error.lower():
                logger.warning("Recipe run %r aborted at step %r: %s", recipe.name, step.name, result.error)
                break
        logger.info("Recipe run %r finished: %d/%d steps completed", recipe.name, len(results), len(recipe.steps))
        return results

    async def _run_step(self, step: RecipeStep) -> StepResult:
        try:
            await self._robot.move_joints(
                [math.radians(d) for d in step.joint_positions_deg], step.speed, step.acceleration
            )
        except MotionBlockedError as exc:
            return StepResult(step_id=step.id, step_name=step.name, moved=False, error=str(exc))

        if step.stay_only:
            return StepResult(step_id=step.id, step_name=step.name, moved=True)

        if step.camera_brightness is not None:
            self._camera.set_brightness(step.camera_brightness)
        if step.camera_contrast is not None:
            self._camera.set_contrast(step.camera_contrast)
        if step.camera_exposure is not None:
            self._camera.set_exposure(step.camera_exposure)
        if step.focus_position is not None:
            self._camera.set_focus(step.focus_position)
        self._apply_light_pattern(step.light_pattern)

        if not step.detector:
            return StepResult(step_id=step.id, step_name=step.name, moved=True)

        detector = self._detectors.get(step.detector)
        if detector is None:
            return StepResult(step_id=step.id, step_name=step.name, moved=True,
                               error=f"Unknown detector {step.detector!r}")
        try:
            frame = self._camera.get_frame()
            detection = detector.infer(frame)
        except (RuntimeError, NotImplementedError) as exc:
            return StepResult(step_id=step.id, step_name=step.name, moved=True, error=str(exc))

        return StepResult(step_id=step.id, step_name=step.name, moved=True, detection=detection)
