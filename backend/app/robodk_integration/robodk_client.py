"""
Thin connection wrapper around RoboDK's Python API (`Robolink`). It talks to
the RoboDK *desktop application* over a local socket — that application is
not installed in this environment (confirmed 2026-08-27), so
`is_available()` will return False here. Every other module in this package
calls `get_robolink()` and lets its `RoboDKUnavailableError` propagate
rather than silently no-op-ing, so a missing RoboDK install fails loudly.
"""
from __future__ import annotations

from app.logging_setup import get_logger

logger = get_logger(__name__)


class RoboDKUnavailableError(RuntimeError):
    pass


def get_robolink():
    """Returns a connected `robolink.Robolink`, or raises RoboDKUnavailableError."""
    from robodk import robolink

    # Robolink() attempts to auto-launch the app at its default install path
    # as a side effect. On macOS a missing install just makes Connect() below
    # return falsy; on Linux (confirmed on the Render deploy host) the
    # constructor itself raises a bare Exception instead — so both the
    # constructor and Connect() need to fold into the same unavailable state.
    try:
        rdk = robolink.Robolink()
        connected = rdk.Connect()
    except Exception as exc:
        raise RoboDKUnavailableError(
            "Could not connect to the RoboDK desktop application. It must be "
            "installed and running on this machine. See the plan's 'Explicitly "
            "open / blocked items' section."
        ) from exc
    if not connected:
        raise RoboDKUnavailableError(
            "Could not connect to the RoboDK desktop application. It must be "
            "installed and running on this machine. See the plan's 'Explicitly "
            "open / blocked items' section."
        )
    return rdk


def is_available() -> bool:
    try:
        get_robolink()
        return True
    except Exception as exc:
        logger.info("RoboDK not available: %s", exc)
        return False
