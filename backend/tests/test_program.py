"""Verifies the recipe teach/goto flow (the old grid's Learn/Do buttons) and
.xlsx round-trip export/import."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.program.recipe import Recipe, RecipeStep, export_xlsx, import_xlsx


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
        c.delete("/api/program/recipes/pytest_recipe")
        c.post("/api/robot/move", json={"joints_deg": [0, 0, 0, 0, 0, 0], "speed": 5.0})


def test_teach_and_goto(client: TestClient):
    client.post("/api/robot/move", json={"joints_deg": [15, -20, 0, 0, 0, 0], "speed": 5.0})

    r = client.post("/api/program/recipes/pytest_recipe/steps", json={"step_name": "Point A"})
    assert r.status_code == 200
    recipe = r.json()
    assert len(recipe["steps"]) == 1
    step = recipe["steps"][0]
    assert step["joint_positions_deg"][0] == pytest.approx(15, abs=0.5)

    client.post("/api/robot/move", json={"joints_deg": [0, 0, 0, 0, 0, 0], "speed": 5.0})
    r = client.post(f"/api/program/recipes/pytest_recipe/steps/{step['id']}/goto")
    assert r.status_code == 200

    pose = client.get("/api/robot/pose").json()["joints_deg"]
    assert pose[0] == pytest.approx(15, abs=0.5)
    assert pose[1] == pytest.approx(-20, abs=0.5)


def test_xlsx_round_trip():
    recipe = Recipe(name="roundtrip", steps=[
        RecipeStep(name="A", joint_positions_deg=[1, 2, 3, 4, 5, 6], detector="classical"),
        RecipeStep(name="B", stay_only=True, joint_positions_deg=[-1, -2, -3, -4, -5, -6]),
    ])
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "recipe.xlsx"
        export_xlsx(recipe, path)
        loaded = import_xlsx(path, name="roundtrip")

    assert loaded.name == "roundtrip"
    assert len(loaded.steps) == 2
    assert loaded.steps[0].name == "A"
    assert loaded.steps[0].joint_positions_deg == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert loaded.steps[0].detector == "classical"
    assert loaded.steps[1].stay_only is True
