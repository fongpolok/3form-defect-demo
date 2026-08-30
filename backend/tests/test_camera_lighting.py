"""Verifies the demo video camera source and the ported stripe-pattern math."""
from __future__ import annotations

from fastapi.testclient import TestClient
from PIL import Image
import io

from app.lighting.pattern import generate_pattern
from app.main import app


def test_camera_capture_and_settings():
    with TestClient(app) as client:
        r = client.get("/api/camera/capture")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/jpeg"
        img = Image.open(io.BytesIO(r.content))
        assert img.size[0] > 0 and img.size[1] > 0

        r = client.post("/api/camera/settings", json={"brightness": 20, "contrast": 1.2})
        assert r.status_code == 200
        settings = r.json()
        assert settings["brightness"] == 20
        assert settings["contrast"] == 1.2
        assert settings["exposure_and_focus_are_noop"] is True


def test_lighting_settings_validation_and_preview():
    with TestClient(app) as client:
        r = client.post("/api/lighting/settings", json={"width": 40, "rotation": 15, "shift": 5, "intensity": 200})
        assert r.status_code == 200
        assert r.json()["width"] == 40

        bad = client.post("/api/lighting/settings", json={"width": 40, "rotation": 999, "shift": 5, "intensity": 200})
        assert bad.status_code == 422

        r = client.get("/api/lighting/preview.png")
        assert r.status_code == 200
        img = Image.open(io.BytesIO(r.content))
        assert img.size == (640, 360)


def test_pattern_stripe_toggle():
    img = generate_pattern(width_px=100, height_px=10, stripe_width=10, rotation_deg=0, shift=0, intensity=255)
    row = [img.getpixel((x, 5)) for x in range(100)]
    # first 10px one color, next 10px the other, per the ported toggle logic
    assert row[0] != row[10]
    assert row[0] == row[9]
    assert row[10] == row[19]
