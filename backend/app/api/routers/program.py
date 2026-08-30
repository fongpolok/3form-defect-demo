"""
Recipe CRUD, the two pendant actions that mirror the old grid's
"Learn"/"Do" buttons (teach a step from the robot's current pose; move back
to a saved step's pose), and /run — full step playback (robot + camera +
light + detector) via RecipeRunner, the old grid's "Do" button extended to
the whole sequence at once.
"""
from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.routers.camera import camera_source, ensure_started
from app.api.routers.lighting import apply_pattern
from app.api.routers.robot import robot_driver
from app.api.routers.vision import detectors
from app.api.ws import ws_manager
from app.logging_setup import get_logger
from app.program.recipe import Recipe, RecipeStep, RecipeStore
from app.program.runner import RecipeRunner, StepResult
from app.safety import MotionBlockedError

logger = get_logger(__name__)
router = APIRouter(prefix="/api/program", tags=["program"])

store = RecipeStore()
runner = RecipeRunner(robot_driver, camera_source, detectors, apply_pattern)


@router.get("/recipes", response_model=list[str])
def list_recipes() -> list[str]:
    return store.list_names()


@router.get("/recipes/{name}", response_model=Recipe)
def get_recipe(name: str) -> Recipe:
    return store.load(name)


@router.put("/recipes/{name}", response_model=Recipe)
def put_recipe(name: str, recipe: Recipe) -> Recipe:
    recipe.name = name
    store.save(recipe)
    return recipe


@router.delete("/recipes/{name}")
def delete_recipe(name: str) -> dict:
    deleted = store.delete(name)
    return {"deleted": deleted}


class TeachRequest(BaseModel):
    step_name: str = "Step"
    stay_only: bool = False
    detector: str | None = None


@router.post("/recipes/{name}/steps", response_model=Recipe)
def teach_step(name: str, body: TeachRequest) -> Recipe:
    """Appends a new step captured from the robot's current live pose."""
    recipe = store.load(name)
    joints_deg = [math.degrees(r) for r in robot_driver.get_joint_positions()]
    step = RecipeStep(name=body.step_name, stay_only=body.stay_only, detector=body.detector,
                       joint_positions_deg=joints_deg)
    recipe.steps.append(step)
    store.save(recipe)
    logger.info("Taught step %r at %s into recipe %r", step.name, joints_deg, name)
    return recipe


@router.delete("/recipes/{name}/steps/{step_id}", response_model=Recipe)
def delete_step(name: str, step_id: str) -> Recipe:
    recipe = store.load(name)
    recipe.steps = [s for s in recipe.steps if s.id != step_id]
    store.save(recipe)
    return recipe


@router.post("/recipes/{name}/steps/{step_id}/goto")
async def goto_step(name: str, step_id: str) -> dict:
    """Moves the robot to a saved step's pose — the old grid's "Do" button."""
    recipe = store.load(name)
    step = next((s for s in recipe.steps if s.id == step_id), None)
    if step is None:
        raise HTTPException(status_code=404, detail=f"No step {step_id!r} in recipe {name!r}")
    try:
        await robot_driver.move_joints(
            [math.radians(d) for d in step.joint_positions_deg], step.speed, step.acceleration
        )
    except MotionBlockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"moved_to": step.id}


@router.post("/recipes/{name}/run", response_model=list[StepResult])
async def run_recipe(name: str) -> list[StepResult]:
    """Replays every step: move, apply camera/light settings, capture, and
    (if the step names one) run a detector — broadcasting each step's
    result over /ws with type "recipe_progress" as it goes."""
    recipe = store.load(name)
    if not recipe.steps:
        raise HTTPException(status_code=400, detail=f"Recipe {name!r} has no steps")
    ensure_started()

    async def on_progress(result: StepResult) -> None:
        await ws_manager.broadcast({"type": "recipe_progress", "result": result.model_dump()})

    return await runner.run(recipe, on_progress=on_progress)
