"""
Pure geometry: given a triangle mesh of the product, generate camera
viewpoints that cover its surface at a tunable standoff distance and
spacing. This is real, fully testable code with no dependency on the
RoboDK desktop app — it only needs a mesh (STL loads directly via
`trimesh`; STEP/IGES go through RoboDK's own CAD import instead, since its
kernel handles those formats far more reliably than any pure-Python option).

`cad_import.py` / `simulate.py` / `export.py` build on top of this to
actually place these viewpoints in a RoboDK station, but this module works
standalone — useful for previewing a scan path even before RoboDK is
installed/licensed.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh


@dataclass
class Viewpoint:
    position: list[float]  # mm, world/mesh frame
    normal: list[float]    # unit vector; the camera looks along -normal toward the surface


def load_mesh(path: str) -> trimesh.Trimesh:
    mesh = trimesh.load(path, force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError(f"Could not load a triangle mesh from {path!r} (got {type(mesh).__name__})")
    return mesh


def generate_scan_viewpoints(
    mesh: trimesh.Trimesh,
    standoff_mm: float = 100.0,
    spacing_mm: float = 20.0,
    max_points: int = 200,
    seed: int = 0,
) -> list[Viewpoint]:
    """
    Samples points across the mesh surface at roughly `spacing_mm` density
    (capped at `max_points` so a dense mesh doesn't produce an unreasonably
    long inspection path — tune both to trade coverage against cycle time),
    and offsets each one along its face normal by `standoff_mm` to get a
    camera position that looks straight at that patch of surface.
    """
    if standoff_mm <= 0:
        raise ValueError("standoff_mm must be > 0")
    if spacing_mm <= 0:
        raise ValueError("spacing_mm must be > 0")
    if mesh.area <= 0:
        raise ValueError("Mesh has zero surface area")

    approx_count = max(1, min(max_points, int(mesh.area / (spacing_mm ** 2))))
    rng = np.random.default_rng(seed)
    points, face_index = trimesh.sample.sample_surface(mesh, approx_count, seed=rng)
    normals = mesh.face_normals[face_index]

    viewpoints: list[Viewpoint] = []
    for p, n in zip(points, normals):
        norm = np.linalg.norm(n)
        n_unit = n / norm if norm > 1e-9 else np.array([0.0, 0.0, 1.0])
        cam_pos = p + n_unit * standoff_mm
        viewpoints.append(Viewpoint(position=cam_pos.tolist(), normal=n_unit.tolist()))
    return viewpoints
