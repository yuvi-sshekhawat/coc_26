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

    # Verify Coordinate Separation (Part 15)
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


def test_validate_csv_success():
    valid_csv = """customer_id,location_name,latitude,longitude,demand
1,Center Alpha,26.9124,75.7873,40
2,Center Beta,26.8950,75.8120,30
3,Center Gamma,26.8500,75.7600,50
"""
    response = client.post("/api/scenarios/validate-csv", json={"csv_content": valid_csv})
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["total_customers"] == 3
    assert data["total_demand"] == 120
    assert data["estimated_stock"] == 84  # floor(0.70 * 120)


def test_validate_csv_failures():
    # Missing required column
    bad_csv_1 = "customer_id,location_name,latitude,demand\n1,Alpha,26.9,50\n"
    res1 = client.post("/api/scenarios/validate-csv", json={"csv_content": bad_csv_1})
    assert res1.json()["valid"] is False
    assert "Missing required CSV columns" in res1.json()["error"]

    # Duplicate customer ID
    bad_csv_2 = """customer_id,location_name,latitude,longitude,demand
1,Alpha,26.9,75.7,50
1,Beta,26.8,75.8,30
"""
    res2 = client.post("/api/scenarios/validate-csv", json={"csv_content": bad_csv_2})
    assert res2.json()["valid"] is False
    assert "Duplicate 'customer_id'" in res2.json()["error"]

    # Invalid latitude
    bad_csv_3 = """customer_id,location_name,latitude,longitude,demand
1,Alpha,999.0,75.7,50
"""
    res3 = client.post("/api/scenarios/validate-csv", json={"csv_content": bad_csv_3})
    assert res3.json()["valid"] is False
    assert "out of bounds" in res3.json()["error"]

    # Invalid demand (non-positive)
    bad_csv_4 = """customer_id,location_name,latitude,longitude,demand
1,Alpha,26.9,75.7,-10
"""
    res4 = client.post("/api/scenarios/validate-csv", json={"csv_content": bad_csv_4})
    assert res4.json()["valid"] is False
    assert "strictly positive" in res4.json()["error"]


import shutil

def test_create_and_solve_custom_scenario():
    csv_data = """customer_id,location_name,latitude,longitude,demand
1,Test Clinic 1,26.9200,75.7900,25
2,Test Clinic 2,26.8800,75.8200,35
3,Test Clinic 3,26.9500,75.7500,40
"""
    payload = {
        "name": "Custom Test Relief Operation",
        "depot_name": "Test Staging Facility",
        "depot_latitude": 26.9100,
        "depot_longitude": 75.7800,
        "csv_content": csv_data,
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
    finally:
        if test_scenario_dir.exists():
            shutil.rmtree(test_scenario_dir, ignore_errors=True)
