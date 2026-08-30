"""Stripe light-pattern endpoints: validate/store the tunable parameters and
serve a preview PNG. The live full-screen projection is rendered by the
frontend (see app/lighting/pattern.py's docstring for why)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.lighting.pattern import pattern_to_png_bytes
from app.logging_setup import get_logger
from app.program.recipe import LightPatternSettings

logger = get_logger(__name__)
router = APIRouter(prefix="/api/lighting", tags=["lighting"])

# In-memory "current" pattern settings so the pendant and the projector
# window agree on what's live. Tunable min/max live here, not scattered
# across the frontend.
LIMITS = {
    "width": (1, 1920),
    "rotation": (-90, 90),
    "shift": (0, 60),
    "intensity": (0, 255),
}

_current = LightPatternSettings()


def _validate(settings: LightPatternSettings) -> None:
    for field, (lo, hi) in LIMITS.items():
        value = getattr(settings, field)
        if not lo <= value <= hi:
            raise ValueError(f"{field}={value} out of range [{lo}, {hi}]")


def apply_pattern(settings: LightPatternSettings) -> LightPatternSettings:
    """Shared by the /settings endpoint and the recipe runner (program/runner.py),
    so a recipe step's light-pattern settings go through the same validation."""
    global _current
    _validate(settings)
    _current = settings
    logger.info("Light pattern updated: %s", settings)
    return _current


@router.get("/settings", response_model=LightPatternSettings)
def get_pattern() -> LightPatternSettings:
    return _current


@router.post("/settings", response_model=LightPatternSettings)
def set_pattern(settings: LightPatternSettings) -> LightPatternSettings:
    try:
        return apply_pattern(settings)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/preview.png")
def preview(width_px: int = 640, height_px: int = 360) -> Response:
    png = pattern_to_png_bytes(
        width_px, height_px, _current.width, _current.rotation, _current.shift, _current.intensity
    )
    return Response(content=png, media_type="image/png")
