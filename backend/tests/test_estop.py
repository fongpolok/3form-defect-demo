"""
Verifies the hard-stop path both at the unit level (StopManager) and
end-to-end through the FastAPI app (button -> API -> guard()).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.safety import MotionBlockedError, StopManager


def test_stop_manager_blocks_and_unblocks():
    mgr = StopManager()
    mgr.guard()  # not stopped yet -> no raise

    mgr.trigger(reason="unit-test")
    assert mgr.is_stopped is True
    with pytest.raises(MotionBlockedError):
        mgr.guard()

    mgr.reset()
    assert mgr.is_stopped is False
    mgr.guard()  # no raise


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
        # leave global stop_manager clean for other tests
        c.post("/api/safety/reset")


def test_demo_move_end_to_end(client: TestClient):
    status = client.get("/api/safety/status").json()
    assert status["stopped"] is False

    ok = client.post("/api/robot/demo-move")
    assert ok.status_code == 200
    assert ok.json()["moved"] is True

    stopped = client.post("/api/safety/stop", json={"reason": "pytest"})
    assert stopped.json()["stopped"] is True

    blocked = client.post("/api/robot/demo-move")
    assert blocked.status_code == 409

    resumed = client.post("/api/safety/reset")
    assert resumed.json()["stopped"] is False

    ok_again = client.post("/api/robot/demo-move")
    assert ok_again.status_code == 200
