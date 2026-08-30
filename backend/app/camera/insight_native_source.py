"""
BLOCKED — not implemented.

The physical camera on hand is a Cognex In-Sight IS8500, a smart camera
(its own onboard processor, not a raw sensor). Talking to it for real needs
either Cognex's In-Sight SDK/CCS Toolkit or the documented Native Mode
protocol reference, neither of which is available in this environment (see
the plan's "Explicitly open / blocked items" section, confirmed with the
user 2026-08-27).

This class exists so the rest of the app can already depend on the
`CameraSource` interface and switch to it later with a one-line config
change — but every method raises loudly instead of pretending to work.
Do not stub this out with fake frames; use `VideoFileSource` for demos.
"""
from __future__ import annotations

import numpy as np

from app.camera.base import CameraSource

_BLOCKED_MESSAGE = (
    "insight_native_source is not implemented: no Cognex In-Sight SDK or "
    "Native Mode protocol documentation is available in this environment. "
    "Use camera.source=video_file in config.yaml for now, and revisit this "
    "once SDK access or protocol docs are obtained."
)


class InSightNativeSource(CameraSource):
    def __init__(self, ip: str) -> None:
        self._ip = ip

    def start(self) -> None:
        raise NotImplementedError(_BLOCKED_MESSAGE)

    def get_frame(self) -> np.ndarray:
        raise NotImplementedError(_BLOCKED_MESSAGE)

    def set_brightness(self, value: float) -> None:
        raise NotImplementedError(_BLOCKED_MESSAGE)

    def set_contrast(self, value: float) -> None:
        raise NotImplementedError(_BLOCKED_MESSAGE)

    def set_exposure(self, value: float) -> None:
        raise NotImplementedError(_BLOCKED_MESSAGE)

    def set_focus(self, position: int) -> None:
        raise NotImplementedError(_BLOCKED_MESSAGE)

    def get_settings(self) -> dict:
        raise NotImplementedError(_BLOCKED_MESSAGE)

    def stop(self) -> None:
        pass  # never started; nothing to release
