"""Verifies the simulated driver: absolute/relative moves, and that a
hard-stop actually interrupts a move already in progress (not just future
ones) via StopManager's abort-callback mechanism."""
from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
        c.post("/api/safety/reset")
        c.post("/api/robot/move", json={"joints_deg": [0, 0, 0, 0, 0, 0], "speed": 5.0})


def test_move_and_jog(client: TestClient):
    r = client.post("/api/robot/move", json={"joints_deg": [10, 0, 0, 0, 0, 0], "speed": 5.0})
    assert r.status_code == 200
    assert r.json()["joints_deg"][0] == pytest.approx(10, abs=0.5)

    r = client.post("/api/robot/jog", json={"joint_index": 1, "delta_deg": 5, "speed": 5.0})
    assert r.status_code == 200
    assert r.json()["joints_deg"][1] == pytest.approx(5, abs=0.5)


def test_hard_stop_interrupts_in_flight_move(client: TestClient):
    client.post("/api/robot/move", json={"joints_deg": [0, 0, 0, 0, 0, 0], "speed": 5.0})

    result = {}

    def do_slow_move():
        # slow enough (speed=0.05 rad/s over 90deg ~1.57rad) to guarantee
        # the stop below lands mid-motion, not after it finishes.
        r = client.post("/api/robot/move", json={"joints_deg": [90, 0, 0, 0, 0, 0], "speed": 0.05})
        result["status_code"] = r.status_code

    t = threading.Thread(target=do_slow_move)
    t.start()
    time.sleep(0.3)
    stop_resp = client.post("/api/safety/stop", json={"reason": "pytest mid-move"})
    assert stop_resp.json()["stopped"] is True
    t.join(timeout=5)

    assert result.get("status_code") == 409
    pose = client.get("/api/robot/pose").json()["joints_deg"][0]
    assert 0 < pose < 90, f"expected the move to have been interrupted partway, got {pose}"
