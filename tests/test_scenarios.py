import shutil
import sys
from pathlib import Path
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.main import app

client = TestClient(app)


def test_list_scenarios():
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert "scenarios" in data
    assert len(data["scenarios"]) >= 3
    names = [s["name"] for s in data["scenarios"]]
    assert "Jaipur Flood Relief" in names
    assert "Delhi Emergency Relief" in names
    assert "Mumbai Cyclone Relief" in names


def test_get_scenario_detail():
    response = client.get("/api/scenarios/jaipur_flood_relief")
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["name"] == "Jaipur Flood Relief"
    assert data["is_solved"] is True
    assert "solution" in data
    
    sol = data["solution"]
    assert sol["status"] == "active"
    assert sol["validation"]["valid"] is True
    assert sol["validation"]["status"] == "PASS"
    assert len(sol["routes"]) > 0
    assert len(sol["nodes"]) > 0

    # Verify Coordinate Separation
    depot_node = sol["nodes"][0]
    assert depot_node["is_depot"] is True
    assert "geographic" in depot_node
    assert "latitude" in depot_node["geographic"]
    assert "longitude" in depot_node["geographic"]
    assert "optimization" in depot_node
    assert "x" in depot_node["optimization"]
    assert "y" in depot_node["optimization"]

    customer_node = sol["nodes"][1]
    assert customer_node["is_depot"] is False
    assert "geographic" in customer_node
    assert "optimization" in customer_node
    assert customer_node["original_demand"] > 0
    assert customer_node["allocated_demand"] >= 0


def test_create_and_solve_custom_scenario_structured():
    payload = {
        "name": "Custom Test Relief Operation",
        "depot_name": "Test Staging Facility",
        "depot_latitude": 26.9100,
        "depot_longitude": 75.7800,
        "destination_name": "Test Destination Hospital",
        "destination_latitude": 26.8900,
        "destination_longitude": 75.8100,
        "houses": [
            {"house_id": 1, "location_name": "Test Clinic 1", "latitude": 26.9200, "longitude": 75.7900, "demand": 25},
            {"house_id": 2, "location_name": "Test Clinic 2", "latitude": 26.8800, "longitude": 75.8200, "demand": 35},
            {"house_id": 3, "location_name": "Test Clinic 3", "latitude": 26.9500, "longitude": 75.7500, "demand": 40},
        ],
        "auto_solve": True,
    }
    test_scenario_dir = ROOT / "relief_scenarios" / "custom_test_relief_operation"
    try:
        response = client.post("/api/scenarios", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["name"] == "Custom Test Relief Operation"
        assert data["is_solved"] is True
        assert data["solution"]["validation"]["valid"] is True
        assert data["metadata"]["destination_name"] == "Test Destination Hospital"
        assert len(data["solution"]["routes"]) > 0
    finally:
        if test_scenario_dir.exists():
            shutil.rmtree(test_scenario_dir, ignore_errors=True)


def test_create_scenario_max_houses_limit():
    # 51 houses must be rejected (max limit is 50)
    oversized_houses = [
        {"house_id": i, "location_name": f"House {i}", "latitude": 26.9 + (i * 0.001), "longitude": 75.7 + (i * 0.001), "demand": 10}
        for i in range(1, 52)
    ]
    payload = {
        "name": "Oversized Operation",
        "depot_name": "Depot",
        "depot_latitude": 26.9,
        "depot_longitude": 75.7,
        "houses": oversized_houses,
    }
    response = client.post("/api/scenarios", json=payload)
    assert response.status_code in (400, 422)


def test_create_scenario_zero_houses_fails():
    payload = {
        "name": "Empty Operation",
        "depot_name": "Depot",
        "depot_latitude": 26.9,
        "depot_longitude": 75.7,
        "houses": [],
    }
    response = client.post("/api/scenarios", json=payload)
    assert response.status_code in (400, 422)


def test_create_scenario_invalid_coordinates():
    payload = {
        "name": "Invalid Coords Operation",
        "depot_name": "Depot",
        "depot_latitude": 195.0,  # Invalid latitude
        "depot_longitude": 75.7,
        "houses": [
            {"house_id": 1, "location_name": "House 1", "latitude": 26.9, "longitude": 75.7, "demand": 10}
        ],
    }
    response = client.post("/api/scenarios", json=payload)
    assert response.status_code == 422
