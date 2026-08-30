"""
Software emergency-stop plumbing.

IMPORTANT — read before wiring this to real hardware:
This `StopManager` is a SOFTWARE stop only. It can cancel motion commands
issued through this application, but it is NOT a certified safety device: it
cannot cut motor power, and it does nothing if the robot is being driven by
anything other than this app. Real production deployment of a robot arm
requires a hardwired, category-rated Emergency Stop circuit independent of
any software, per machinery safety standards (e.g. ISO 13850 / IEC 60204-1).
See `Settings.safety.hardware_estop_present` in config.yaml, which the
frontend uses to decide whether to show a warning banner about this.

Usage: every function that commands robot motion must call
`stop_manager.guard()` as its first action, so a triggered stop blocks any
new motion instead of only stopping the "next" step.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from app.logging_setup import get_logger

logger = get_logger(__name__)


class MotionBlockedError(RuntimeError):
    """Raised by `StopManager.guard()` when a motion command is attempted while stopped."""


@dataclass
class StopStatus:
    stopped: bool
    reason: str | None
    triggered_at: float | None


class StopManager:
    """Thread-safe latch: once tripped, stays tripped until explicitly reset."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stopped = False
        self._reason: str | None = None
        self._triggered_at: float | None = None
        self._abort_callbacks: list[Callable[[], None]] = []

    def register_abort_callback(self, callback: Callable[[], None]) -> None:
        """
        A driver calls this once at startup with a function that aborts
        whatever motion it currently has in flight (e.g. flips an
        `_aborted` flag its interpolation loop checks). `trigger()` calls
        every registered callback so a hard-stop interrupts an in-progress
        move, not just future ones.
        """
        with self._lock:
            self._abort_callbacks.append(callback)

    def trigger(self, reason: str = "manual") -> StopStatus:
        with self._lock:
            self._stopped = True
            self._reason = reason
            self._triggered_at = time.time()
            callbacks = list(self._abort_callbacks)
            logger.warning("STOP triggered (reason=%s)", reason)
        for callback in callbacks:
            try:
                callback()
            except Exception:
                logger.exception("Abort callback raised while handling STOP")
        return self.status()

    def reset(self) -> StopStatus:
        with self._lock:
            was_stopped = self._stopped
            self._stopped = False
            self._reason = None
            self._triggered_at = None
            if was_stopped:
                logger.info("STOP reset — motion commands allowed again")
            return self._status_locked()

    def guard(self) -> None:
        """Call at the start of every motion-issuing function. Raises if stopped."""
        if self._stopped:
            raise MotionBlockedError(
                f"Motion blocked: stop is active (reason={self._reason!r}). Reset it first."
            )

    @property
    def is_stopped(self) -> bool:
        with self._lock:
            return self._stopped

    def status(self) -> StopStatus:
        with self._lock:
            return self._status_locked()

    def _status_locked(self) -> StopStatus:
        return StopStatus(stopped=self._stopped, reason=self._reason, triggered_at=self._triggered_at)


# Process-wide singleton — every router/module imports this same instance.
stop_manager = StopManager()
