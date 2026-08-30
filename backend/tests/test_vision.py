"""Verifies both no-training-data-needed detectors actually discriminate
good vs. defect on the bundled synthetic sample images, and that the
not-yet-trained YOLO option fails loudly instead of faking a result."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_detectors_list():
    with TestClient(app) as client:
        r = client.get("/api/vision/detectors")
        assert r.status_code == 200
        by_name = {d["name"]: d for d in r.json()}
        assert by_name["classical"]["ready"] is True
        assert by_name["patchcore"]["ready"] is True
        assert by_name["yolo"]["ready"] is False


def test_classical_detector_passes_good_fails_defect():
    with TestClient(app) as client:
        good = client.post("/api/vision/infer/classical", json={"sample_name": "good_00.png"})
        assert good.status_code == 200
        assert good.json()["pass_fail"] == "pass"

        defect = client.post("/api/vision/infer/classical", json={"sample_name": "defect_02_missing.png"})
        assert defect.status_code == 200
        body = defect.json()
        assert body["pass_fail"] == "fail"
        assert len(body["boxes"]) >= 1
        assert body["overlay_image_b64"]


def test_patchcore_detector_scores_defect_higher_than_good():
    with TestClient(app) as client:
        good = client.post("/api/vision/infer/patchcore", json={"sample_name": "good_01.png"})
        defect = client.post("/api/vision/infer/patchcore", json={"sample_name": "defect_01_blob.png"})
        assert good.status_code == 200 and defect.status_code == 200
        assert defect.json()["score"] >= good.json()["score"]


def test_yolo_not_ready_returns_503_not_a_fake_result():
    with TestClient(app) as client:
        r = client.post("/api/vision/infer/yolo", json={"sample_name": "good_00.png"})
        assert r.status_code == 503
