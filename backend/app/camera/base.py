"""
Common interface every camera backend implements. `brightness`/`contrast`
are always meaningful (applied as a post-process on whatever frame came
back); `exposure`/`focus` are only meaningful on a real camera and are
no-ops on `VideoFileSource` — each implementation documents which of these
actually change anything, rather than silently pretending they all do.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class CameraSource(ABC):
    @abstractmethod
    def start(self) -> None:
        """Open the device/file. Safe to call once before the first get_frame()."""

    @abstractmethod
    def get_frame(self) -> np.ndarray:
        """Returns the next frame as a BGR uint8 array (OpenCV convention)."""

    @abstractmethod
    def set_brightness(self, value: float) -> None: ...

    @abstractmethod
    def set_contrast(self, value: float) -> None: ...

    @abstractmethod
    def set_exposure(self, value: float) -> None: ...

    @abstractmethod
    def set_focus(self, position: int) -> None: ...

    @abstractmethod
    def get_settings(self) -> dict:
        """Current brightness/contrast/exposure/focus, for the UI to display."""

    @abstractmethod
    def stop(self) -> None: ...
