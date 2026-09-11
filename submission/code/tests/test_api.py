import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app

client = TestClient(app)


def test_api_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


def test_api_instances():
    res = client.get("/api/instances")
    assert res.status_code == 200
    data = res.json()
    assert "A-n32-k5" in data["instances"]
    assert "A-n33-k5" in data["instances"]
    assert "B-n31-k5" in data["instances"]


def test_api_results():
    res = client.get("/api/results")
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    assert len(data["results"]) >= 3


def test_api_instance_endpoints():
    for name in ["A-n32-k5", "A-n33-k5", "B-n31-k5"]:
        res = client.get(f"/api/results/{name}")
        assert res.status_code == 200
        metrics = res.json()
        assert metrics["instance"] == name
        assert metrics["minimum_service_ratio"] > 0
        assert metrics["validation_valid"] is True

        # Routes
        r_res = client.get(f"/api/results/{name}/routes")
        assert r_res.status_code == 200
        routes_data = r_res.json()
        assert len(routes_data["routes"]) == 5

        # Allocation
        a_res = client.get(f"/api/results/{name}/allocation")
        assert a_res.status_code == 200
        alloc_data = a_res.json()
        assert len(alloc_data["allocation"]) > 0

        # Validation
        v_res = client.get(f"/api/results/{name}/validation")
        assert v_res.status_code == 200
        val_data = v_res.json()
        assert val_data["valid"] is True
        assert val_data["status"] == "PASS"

        # Baselines
        b_res = client.get(f"/api/results/{name}/baselines")
        assert b_res.status_code == 200
        b_data = b_res.json()
        assert len(b_data) == 4
