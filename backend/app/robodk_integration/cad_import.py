"""
Imports a CAD file (STEP/IGES/STL/etc.) into a running RoboDK station using
RoboDK's own CAD import (its kernel handles STEP/IGES properly, unlike pure-
Python options — see path_generation.py's docstring).

UNVERIFIED: written against RoboDK's documented Python API
(https://robodk.com/doc/en/PythonAPI/robolink.html) but not runnable here —
the RoboDK desktop app isn't installed in this environment (confirmed
2026-08-27). Exercise this for real once it is, via
`app/api/routers/robodk.py`'s /import-cad endpoint, which reports RoboDK's
absence clearly instead of pretending this ran.
"""
from __future__ import annotations

from app.logging_setup import get_logger

logger = get_logger(__name__)


def import_cad(rdk, file_path: str):
    """Adds `file_path` to the open RoboDK station and returns the resulting Item."""
    item = rdk.AddFile(file_path)
    if not item.Valid():
        raise RuntimeError(f"RoboDK failed to import {file_path!r} — check the file is a supported CAD format")
    logger.info("Imported %s into RoboDK station as %s", file_path, item.Name())
    return item
