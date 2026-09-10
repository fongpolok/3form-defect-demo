"""Verifies the pure-geometry path-generation math (no RoboDK app needed)
and that the API degrades honestly — reporting RoboDK unavailable rather
than faking a simulation — when the desktop app isn't installed, which is
the case in this dev environment (confirmed 2026-08-27)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import trimesh
from fastapi.testclient import TestClient

from app.main import app
from app.robodk_integration.path_generation import generate_scan_viewpoints


def test_generate_scan_viewpoints_covers_a_box():
    box = trimesh.creation.box(extents=[100, 100, 100])
    viewpoints = generate_scan_viewpoints(box, standoff_mm=50, spacing_mm=20, max_points=100)

    assert len(viewpoints) > 10
    for vp in viewpoints:
        assert len(vp.position) == 3
        # every viewpoint should be further from the origin than the box
        # surface itself, since it's offset outward by the standoff
        import numpy as np
        assert np.linalg.norm(vp.position) > 50


def test_generate_scan_viewpoints_rejects_bad_params():
    box = trimesh.creation.box(extents=[10, 10, 10])
    with pytest.raises(ValueError):
        generate_scan_viewpoints(box, standoff_mm=0, spacing_mm=5)
    with pytest.raises(ValueError):
        generate_scan_viewpoints(box, standoff_mm=5, spacing_mm=-1)


def test_robodk_status_reports_unavailable_honestly():
    with TestClient(app) as client:
        r = client.get("/api/robodk/status")
        assert r.status_code == 200
        body = r.json()
        # RoboDK desktop app is not installed in this dev environment.
        assert body["available"] is False
        assert "RoboDK" in body["message"]


def test_generate_path_endpoint_with_uploaded_stl():
    box = trimesh.creation.box(extents=[50, 50, 50])
    with tempfile.TemporaryDirectory() as tmp:
        stl_path = Path(tmp) / "test_box.stl"
        box.export(stl_path)

        with TestClient(app) as client:
            with open(stl_path, "rb") as f:
                r = client.post(
                    "/api/robodk/generate-path",
                    files={"file": ("test_box.stl", f, "application/octet-stream")},
                    params={"standoff_mm": 30, "spacing_mm": 20, "max_points": 50},
                )
            assert r.status_code == 200
            body = r.json()
            assert len(body["viewpoints"]) > 0
            assert body["robodk_simulation_available"] is False

            sim = client.post("/api/robodk/simulate")
            assert sim.status_code == 503


def test_list_and_serve_uploads():
    # generate-path saves into the *real* UPLOAD_DIR (it's the whole point —
    # so later /uploads calls can see it) — clean up what this test adds so
    # repeat runs don't pollute the real uploads list with test artifacts.
    from app.api.routers.robodk import UPLOAD_DIR

    box = trimesh.creation.box(extents=[20, 20, 20])
    with tempfile.TemporaryDirectory() as tmp:
        stl_path = Path(tmp) / "listing_test.stl"
        box.export(stl_path)

        with TestClient(app) as client:
            with open(stl_path, "rb") as f:
                client.post(
                    "/api/robodk/generate-path",
                    files={"file": ("listing_test.stl", f, "application/octet-stream")},
                    params={"standoff_mm": 10, "spacing_mm": 10, "max_points": 20},
                )

            names = client.get("/api/robodk/uploads").json()
            assert "listing_test.stl" in names

            r = client.get("/api/robodk/uploads/listing_test.stl")
            assert r.status_code == 200
            assert len(r.content) == stl_path.stat().st_size

            # path traversal attempts must not escape the upload directory
            escape = client.get("/api/robodk/uploads/..%2F..%2Fconfig.yaml")
            assert escape.status_code == 404

    (UPLOAD_DIR / "listing_test.stl").unlink(missing_ok=True)
