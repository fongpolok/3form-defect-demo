"""End-to-end: teach two steps (one plain move, one with a detector),
run the recipe, and confirm the robot actually moved to each pose and the
detector actually ran against a live camera-source frame — the full old
"Do" button behavior, automated across a whole sequence."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
        c.delete("/api/program/recipes/pytest_run_recipe")
        c.post("/api/robot/move", json={"joints_deg": [0, 0, 0, 0, 0, 0], "speed": 5.0})


def test_full_recipe_run(client: TestClient):
    client.post("/api/robot/move", json={"joints_deg": [5, 0, 0, 0, 0, 0], "speed": 5.0})
    client.post("/api/program/recipes/pytest_run_recipe/steps",
                json={"step_name": "Approach", "stay_only": True})

    client.post("/api/robot/move", json={"joints_deg": [20, -10, 0, 0, 0, 0], "speed": 5.0})
    client.post("/api/program/recipes/pytest_run_recipe/steps",
                json={"step_name": "Inspect", "detector": "classical"})

    r = client.post("/api/program/recipes/pytest_run_recipe/run")
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 2

    assert results[0]["step_name"] == "Approach"
    assert results[0]["moved"] is True
    assert results[0]["detection"] is None

    assert results[1]["step_name"] == "Inspect"
    assert results[1]["moved"] is True
    assert results[1]["detection"] is not None
    assert results[1]["detection"]["detector"] == "classical"
    assert results[1]["detection"]["pass_fail"] in ("pass", "fail")

    pose = client.get("/api/robot/pose").json()["joints_deg"]
    assert pose[0] == pytest.approx(20, abs=0.5)
    assert pose[1] == pytest.approx(-10, abs=0.5)
