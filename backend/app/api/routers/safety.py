"""Hard-stop endpoints: trigger, reset, status. See `app/safety/estop.py`."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.logging_setup import get_logger
from app.safety import stop_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/api/safety", tags=["safety"])


class StopRequest(BaseModel):
    reason: str = "manual"


class StopStatusResponse(BaseModel):
    stopped: bool
    reason: str | None
    triggered_at: float | None
    hardware_estop_present: bool


def _response(status) -> StopStatusResponse:
    settings = get_settings()
    return StopStatusResponse(
        stopped=status.stopped,
        reason=status.reason,
        triggered_at=status.triggered_at,
        hardware_estop_present=settings.safety.hardware_estop_present,
    )


@router.get("/status", response_model=StopStatusResponse)
def get_status() -> StopStatusResponse:
    return _response(stop_manager.status())


@router.post("/stop", response_model=StopStatusResponse)
def trigger_stop(body: StopRequest) -> StopStatusResponse:
    logger.warning("Hard-stop requested via API (reason=%s)", body.reason)
    return _response(stop_manager.trigger(body.reason))


@router.post("/reset", response_model=StopStatusResponse)
def reset_stop() -> StopStatusResponse:
    logger.info("Stop reset requested via API")
    return _response(stop_manager.reset())
