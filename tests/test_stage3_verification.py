import math
import shutil
import sys
from pathlib import Path
from unittest.mock import patch
import urllib.error

import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from ai05.allocation import solve_max_min_allocation
from ai05.loader import load_instance
from ai05.models import InstanceData
from ai05.regions import prepare_regions
from ai05.routing import solve_cvrp
from ai05.validation import validate_all
from app.main import app
from app.services.road_geometry import (
    compute_vehicle_road_route,
    fetch_road_distance_matrix,
    haversine_distance_km,
    validate_waypoint,
)
from app.services.scenario_adapter import (
    HouseRecord,
    LocationPoint,
    ScenarioInput,
    determine_fleet_size,
    solve_scenario_relief,
    validate_house_records,
)

client = TestClient(app)


# ---------------------------------------------------------------------
# 1. Single House Scenario
# ---------------------------------------------------------------------
def test_01_single_house():
    depot = LocationPoint("Depot Center", 26.9124, 75.7873)
    houses = [HouseRecord(1, "Isolated Community A", 26.9200, 75.7900, demand=20)]
    scen = ScenarioInput("Single House Ops", depot, None, houses)

    sol = solve_scenario_relief(scen, route_time_limit_s=1)
    assert sol["status"] == "active"
    assert sol["scenario"]["total_houses"] == 1
    assert sol["fleet"]["number_of_vehicles"] == 1

    # Total allocated <= floor(0.70 * 20) = 14
    alloc = sol["allocation"]
    assert alloc[1] == 14
    assert alloc[0] == 0

    # Route visits house 1 and returns to depot
    assert len(sol["routes"]) == 1
    route = sol["routes"][0]
    assert 1 in route["assigned_houses"]
    assert route["nodes"][0] == 0
    assert route["nodes"][-1] == 0
    assert route["return_to_depot"] is True
    assert sol["validation"]["valid"] is True


# ---------------------------------------------------------------------
# 2. Several Houses Scenario
# ---------------------------------------------------------------------
def test_02_several_houses():
    depot = LocationPoint("Jaipur Staging Hub", 26.9124, 75.7873)
    houses = [
        HouseRecord(1, "House East 1", 26.9150, 75.8100, demand=15),
        HouseRecord(2, "House North 1", 26.9300, 75.7850, demand=20),
        HouseRecord(3, "House West 1", 26.9100, 75.7600, demand=25),
        HouseRecord(4, "House South 1", 26.8900, 75.7800, demand=30),
        HouseRecord(5, "House East 2", 26.9200, 75.8250, demand=10),
    ]
    scen = ScenarioInput("Multi-Quadrant Ops", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=2)

    assert sol["status"] == "active"
    assert sol["scenario"]["total_houses"] == 5
    assert len(sol["routes"]) >= 1

    # Confirm all active houses are assigned to routes
    assigned_houses = set()
    for r in sol["routes"]:
        assigned_houses.update(r["assigned_houses"])
        assert r["load"] <= r["capacity"]
        assert r["nodes"][0] == 0
        assert r["nodes"][-1] == 0

    active_customers = [idx for idx, q in enumerate(sol["allocation"]) if idx > 0 and q > 0]
    assert set(active_customers).issubset(assigned_houses)
    assert sol["validation"]["valid"] is True


# ---------------------------------------------------------------------
# 3. Exactly 50 Houses Scenario
# ---------------------------------------------------------------------
def test_03_exactly_50_houses():
    depot = LocationPoint("Central Depot", 26.9124, 75.7873)
    houses = []
    for i in range(1, 51):
        angle = (i / 50.0) * 2 * math.pi
        radius = 0.02 + (i % 5) * 0.005
        lat = round(26.9124 + radius * math.sin(angle), 5)
        lon = round(75.7873 + radius * math.cos(angle), 5)
        houses.append(HouseRecord(i, f"House Cluster #{i}", lat, lon, demand=10 + (i % 15)))

    assert len(houses) == 50
    scen = ScenarioInput("50-House Scale Stress Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=2)

    assert sol["scenario"]["total_houses"] == 50
    assert sol["validation"]["checks"]["stock_bound"] is True
    assert sol["validation"]["checks"]["vehicle_capacity"] is True
    assert sol["validation"]["checks"]["customer_uniqueness"] is True
    assert sol["validation"]["valid"] is True


# ---------------------------------------------------------------------
# 4. Invalid > 50 Houses Scenario Rejection
# ---------------------------------------------------------------------
def test_04_invalid_greater_than_50_houses():
    depot = LocationPoint("Depot", 26.9124, 75.7873)
    houses_51 = [
        HouseRecord(i, f"House #{i}", 26.9 + (i * 0.001), 75.7 + (i * 0.001), demand=10)
        for i in range(1, 52)
    ]
    assert len(houses_51) == 51

    # Python Adapter Level Rejection
    with pytest.raises(ValueError, match="Number of houses cannot exceed 50"):
        validate_house_records(houses_51)

    # API Schema Validation Level Rejection
    payload = {
        "name": "Over 50 Houses API Rejection Test",
        "depot_name": "Depot",
        "depot_latitude": 26.9124,
        "depot_longitude": 75.7873,
        "houses": [
            {"house_id": h.house_id, "location_name": h.location_name, "latitude": h.latitude, "longitude": h.longitude, "demand": h.demand}
            for h in houses_51
        ],
    }
    resp = client.post("/api/scenarios", json=payload)
    assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------
# 5. Duplicate Houses Rejection
# ---------------------------------------------------------------------
def test_05_duplicate_houses_rejection():
    # Duplicate ID
    dup_id_houses = [
        HouseRecord(1, "House A", 26.9100, 75.7800, demand=10),
        HouseRecord(1, "House B", 26.9200, 75.7900, demand=15),
    ]
    with pytest.raises(ValueError, match="Duplicate house ID"):
        validate_house_records(dup_id_houses)

    # Duplicate Coordinates
    dup_coord_houses = [
        HouseRecord(1, "House A", 26.9100, 75.7800, demand=10),
        HouseRecord(2, "House B", 26.9100, 75.7800, demand=15),
    ]
    with pytest.raises(ValueError, match="Duplicate house location"):
        validate_house_records(dup_coord_houses)


# ---------------------------------------------------------------------
# 6. Source and Destination Handling
# ---------------------------------------------------------------------
def test_06_source_and_destination_handling():
    depot = LocationPoint("Base Depot", 26.9124, 75.7873)
    dest = LocationPoint("Target Staging Hospital", 26.8800, 75.8200)
    houses = [
        HouseRecord(1, "Clinic North", 26.9300, 75.7900, demand=20),
        HouseRecord(2, "Clinic South", 26.9000, 75.8000, demand=25),
    ]
    scen = ScenarioInput("Destination Route Test", depot, dest, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=1)

    assert sol["destination"] is not None
    assert sol["destination"]["name"] == "Target Staging Hospital"

    for r in sol["routes"]:
        assert r["destination_visited"] is True
        # Waypoint itinerary must include -1 for destination
        assert -1 in r["nodes"]
        dest_idx = r["nodes"].index(-1)
        assert dest_idx > 0  # After starting depot
        assert r["nodes"][-1] == 0  # Ends at depot
        assert dest_idx < len(r["nodes"]) - 1  # Destination is visited BEFORE returning to depot


# ---------------------------------------------------------------------
# 7. System-Determined Fleet Sizing (Constraint-Driven)
# ---------------------------------------------------------------------
def test_07_system_determined_fleet_sizing():
    depot = LocationPoint("Depot Hub", 26.9124, 75.7873)
    houses = [
        HouseRecord(1, "Heavy 1", 26.9200, 75.7900, demand=150),
        HouseRecord(2, "Heavy 2", 26.9300, 75.8000, demand=180),
        HouseRecord(3, "Heavy 3", 26.9000, 75.7700, demand=140),
        HouseRecord(4, "Heavy 4", 26.8900, 75.7600, demand=160),
    ]
    scen = ScenarioInput("Fleet Sizing Math Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=2)

    # Must NOT be an arbitrary formula like len(houses) // 4 = 1
    fleet_info = sol["fleet"]
    assert "rationale" in fleet_info
    assert "bin-packing" in fleet_info["rationale"]
    assert "OR-Tools CVRP solver" in fleet_info["rationale"]
    assert fleet_info["number_of_vehicles"] >= 2  # High demand cannot be packed in 1 vehicle


# ---------------------------------------------------------------------
# 8. Capacity Constraints Obeyed
# ---------------------------------------------------------------------
def test_08_capacity_constraints_obeyed():
    depot = LocationPoint("Depot Hub", 26.9124, 75.7873)
    houses = [
        HouseRecord(i, f"House {i}", 26.91 + (i * 0.005), 75.78 + (i * 0.005), demand=30)
        for i in range(1, 9)
    ]
    scen = ScenarioInput("Capacity Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=2)

    cap = sol["scenario"]["capacity"]
    for r in sol["routes"]:
        assigned_load = sum(sol["allocation"][nid] for nid in r["assigned_houses"])
        assert assigned_load <= cap
        assert r["load"] <= cap
    assert sol["validation"]["checks"]["vehicle_capacity"] is True


# ---------------------------------------------------------------------
# 9. All Allocated Houses Covered
# ---------------------------------------------------------------------
def test_09_all_allocated_houses_covered():
    depot = LocationPoint("Depot Hub", 26.9124, 75.7873)
    houses = [
        HouseRecord(1, "H1", 26.92, 75.79, demand=10),
        HouseRecord(2, "H2", 26.93, 75.80, demand=15),
        HouseRecord(3, "H3", 26.90, 75.77, demand=20),
    ]
    scen = ScenarioInput("Coverage Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=1)

    all_visited = set()
    for r in sol["routes"]:
        all_visited.update(r["assigned_houses"])

    active_houses = {idx for idx, q in enumerate(sol["allocation"]) if idx > 0 and q > 0}
    assert active_houses == all_visited
    assert sol["validation"]["checks"]["route_coverage"] is True


# ---------------------------------------------------------------------
# 10. No Duplicate Customer Visits
# ---------------------------------------------------------------------
def test_10_no_duplicate_customer_visits():
    depot = LocationPoint("Depot Hub", 26.9124, 75.7873)
    houses = [
        HouseRecord(i, f"House {i}", 26.91 + (i * 0.004), 75.78 + (i * 0.003), demand=20)
        for i in range(1, 7)
    ]
    scen = ScenarioInput("Uniqueness Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=2)

    visited_list = []
    for r in sol["routes"]:
        visited_list.extend(r["assigned_houses"])

    # No duplicates among assigned customer houses
    assert len(visited_list) == len(set(visited_list))
    assert sol["validation"]["checks"]["customer_uniqueness"] is True


# ---------------------------------------------------------------------
# 11. Return to Depot
# ---------------------------------------------------------------------
def test_11_return_to_depot():
    depot = LocationPoint("Depot Hub", 26.9124, 75.7873)
    houses = [
        HouseRecord(1, "House 1", 26.9200, 75.7900, demand=15),
        HouseRecord(2, "House 2", 26.9150, 75.8000, demand=20),
    ]
    scen = ScenarioInput("Return Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=1)

    for r in sol["routes"]:
        assert r["return_to_depot"] is True
        assert r["nodes"][0] == 0
        assert r["nodes"][-1] == 0
        # Check coordinates start and end at depot
        assert r["ordered_coords"][0] == [depot.longitude, depot.latitude]
        assert r["ordered_coords"][-1] == [depot.longitude, depot.latitude]
    assert sol["validation"]["checks"]["depot_start_end"] is True


# ---------------------------------------------------------------------
# 12. Routing API Failure Handling (Graceful Geodesic Fallback)
# ---------------------------------------------------------------------
def test_12_routing_api_failure_handling():
    coords = [[75.7873, 26.9124], [75.7900, 26.9200], [75.8000, 26.9150]]

    # Simulate network outage on OSRM API
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network unreachable")):
        dist_mat, dur_mat, source, warnings = fetch_road_distance_matrix(coords)
        assert source == "GEODESIC_ROAD_ESTIMATE"
        assert len(warnings) > 0
        assert "OSRM Table service unavailable" in warnings[0]
        assert dist_mat.shape == (3, 3)
        assert dist_mat[0, 1] > 0
        assert np.diag(dist_mat).sum() == 0


# ---------------------------------------------------------------------
# 13. Disconnected Route Detection (No Fake Straight Lines)
# ---------------------------------------------------------------------
def test_13_disconnected_route_detection():
    # Node 1 and Node 2 where routing fails
    node_ids = [0, 1, 0]
    node_names = ["Depot", "Remote Island House", "Depot"]
    coords_list = [[75.7873, 26.9124], [75.7900, 26.9200], [75.7873, 26.9124]]

    # Mock single segment OSRM query returning failure
    with patch("app.services.road_geometry._fetch_single_segment_osrm", return_value={"connected": False, "error_reason": "No water crossing found"}):
        with patch("urllib.request.urlopen", side_effect=Exception("API down")):
            route_res = compute_vehicle_road_route(
                vehicle=1,
                node_ids=node_ids,
                node_names=node_names,
                coords_list=coords_list,
            )
            assert route_res.has_errors is True
            assert route_res.status in ("ROUTING_FAILED", "PARTIALLY_ROUTED")
            # Failed segment must NOT have fake straight line coordinates
            failed_segs = [s for s in route_res.segments if not s.connected]
            assert len(failed_segs) > 0
            for fs in failed_segs:
                assert fs.status == "ROUTING_FAILED"
                assert fs.geometry == []  # No fake straight lines


# ---------------------------------------------------------------------
# 14. Invalid Coordinates Rejection
# ---------------------------------------------------------------------
def test_14_invalid_coordinates_rejection():
    # Waypoint coordinate validation
    ok1, err1 = validate_waypoint("Invalid Lat", [75.78, 95.0])
    assert ok1 is False
    assert "latitude" in err1.lower()

    ok2, err2 = validate_waypoint("Invalid Lon", [190.0, 26.9])
    assert ok2 is False
    assert "longitude" in err2.lower()

    ok3, err3 = validate_waypoint("NaN Coords", [float("nan"), 26.9])
    assert ok3 is False
    assert "nan" in err3.lower()

    # HouseRecord validation
    with pytest.raises(ValueError, match="latitude .* is out of bounds"):
        validate_house_records([HouseRecord(1, "Bad Lat", -95.0, 75.0, demand=10)])

    with pytest.raises(ValueError, match="longitude .* is out of bounds"):
        validate_house_records([HouseRecord(1, "Bad Lon", 26.0, 210.0, demand=10)])


# ---------------------------------------------------------------------
# 15. Road Distance Consistency
# ---------------------------------------------------------------------
def test_15_road_distance_consistency():
    coords = [
        [75.7873, 26.9124],  # Depot
        [75.8100, 26.9150],  # East
        [75.7850, 26.9300],  # North
    ]
    dist_mat, _, _, _ = fetch_road_distance_matrix(coords)

    # 1. Non-negativity and zero diagonal
    for i in range(3):
        assert dist_mat[i, i] == 0.0
        for j in range(3):
            if i != j:
                assert dist_mat[i, j] > 0.0
                straight_line_meters = haversine_distance_km(coords[i][0], coords[i][1], coords[j][0], coords[j][1]) * 1000.0
                # Road distance must be >= straight line distance (within 1m numerical precision)
                assert dist_mat[i, j] >= straight_line_meters - 1.0


# ---------------------------------------------------------------------
# 16. Route Geometry Consistency
# ---------------------------------------------------------------------
def test_16_route_geometry_consistency():
    depot = LocationPoint("Depot", 26.9124, 75.7873)
    houses = [
        HouseRecord(1, "House 1", 26.9200, 75.7900, demand=10),
        HouseRecord(2, "House 2", 26.9150, 75.8000, demand=15),
    ]
    scen = ScenarioInput("Geom Consistency Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=1)

    for r in sol["routes"]:
        for seg in r["segments"]:
            if seg["connected"]:
                assert len(seg["geometry"]) >= 2
                for pt in seg["geometry"]:
                    assert len(pt) == 2
                    lon, lat = pt
                    assert -180.0 <= lon <= 180.0
                    assert -90.0 <= lat <= 90.0
                    assert not math.isnan(lon) and not math.isnan(lat)


# ---------------------------------------------------------------------
# 17. Official 3 Benchmarks Unaffected (A-n32-k5, A-n33-k5, B-n31-k5)
# ---------------------------------------------------------------------
@pytest.mark.parametrize("instance_name", ["A-n32-k5", "A-n33-k5", "B-n31-k5"])
def test_17_official_three_benchmarks_unaffected(instance_name: str):
    instance_path = ROOT / "data" / f"{instance_name}.vrp"
    assert instance_path.exists(), f"Benchmark instance {instance_name}.vrp missing"

    inst = load_instance(instance_path)
    prep = prepare_regions(inst)

    # 1. Exact Max-Min Fair Allocation
    alloc_res = solve_max_min_allocation(prep)
    alloc = np.asarray(alloc_res.allocation, dtype=int)

    # 2. Total allocated must obey stock constraint floor(0.70 * total_demand)
    expected_stock = int(math.floor(0.70 * np.sum(inst.demand)))
    assert np.sum(alloc) <= expected_stock
    assert alloc[inst.depot] == 0

    # 3. CVRP Routing
    plan = solve_cvrp(inst, alloc, time_limit_s=1)

    # 4. Official AI-05 Authoritative Validation
    report = validate_all(prep, alloc, plan.routes, plan)
    assert report.valid is True, f"Benchmark {instance_name} failed validation: {report.errors}"
    assert report.stock_ok is True
    assert report.allocation_bounds_ok is True
    assert report.vehicle_capacity_ok is True
    assert report.customer_uniqueness_ok is True


# ---------------------------------------------------------------------
# 18. Fairness Constraints (Max-Min Service Ratio)
# ---------------------------------------------------------------------
def test_18_fairness_constraints_max_min():
    depot = LocationPoint("Depot Hub", 26.9124, 75.7873)
    houses = [
        HouseRecord(1, "House High Demand", 26.9200, 75.7900, demand=50),
        HouseRecord(2, "House Low Demand", 26.9100, 75.7700, demand=10),
    ]
    scen = ScenarioInput("Fairness MaxMin Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=1)

    alloc = sol["allocation"]
    ratio1 = alloc[1] / 50.0
    ratio2 = alloc[2] / 10.0

    # Max-min ensures minimum service ratio is maximized; no starvation
    assert min(ratio1, ratio2) > 0.50
    assert sol["metrics"]["minimum_service_ratio"] > 0.50


# ---------------------------------------------------------------------
# 19. Stock and Allocation Bounds
# ---------------------------------------------------------------------
def test_19_stock_and_allocation_bounds():
    depot = LocationPoint("Depot Hub", 26.9124, 75.7873)
    houses = [
        HouseRecord(1, "House 1", 26.92, 75.79, demand=33),
        HouseRecord(2, "House 2", 26.91, 75.78, demand=47),
        HouseRecord(3, "House 3", 26.90, 75.77, demand=25),
    ]
    scen = ScenarioInput("Stock Bounds Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=1)

    total_demand = 33 + 47 + 25
    expected_stock = math.floor(0.70 * total_demand)
    actual_allocated = sum(sol["allocation"])

    assert actual_allocated <= expected_stock
    assert sol["allocation"][0] == 0
    assert sol["allocation"][1] <= 33
    assert sol["allocation"][2] <= 47
    assert sol["allocation"][3] <= 25
    assert sol["validation"]["checks"]["stock_bound"] is True
    assert sol["validation"]["checks"]["allocation_bounds"] is True


# ---------------------------------------------------------------------
# 20. End-to-End Scenario Solve & JSON Payload
# ---------------------------------------------------------------------
def test_20_end_to_end_scenario_solve_json_payload():
    payload = {
        "name": "E2E Stage 3 Verification",
        "depot_name": "Regional Staging Center",
        "depot_latitude": 26.9124,
        "depot_longitude": 75.7873,
        "destination_name": "Emergency Hospital",
        "destination_latitude": 26.8850,
        "destination_longitude": 75.8150,
        "houses": [
            {"house_id": 1, "location_name": "Site Alpha", "latitude": 26.9250, "longitude": 75.7950, "demand": 25},
            {"house_id": 2, "location_name": "Site Beta", "latitude": 26.9050, "longitude": 75.7750, "demand": 30},
        ],
        "auto_solve": True,
    }

    test_dir = ROOT / "relief_scenarios" / "e2e_stage_3_verification"
    try:
        # Create and auto-solve via API
        post_resp = client.post("/api/scenarios", json=payload)
        assert post_resp.status_code == 200
        data = post_resp.json()

        # Check Root Keys
        assert "id" in data
        assert "metadata" in data
        assert "is_solved" in data
        assert data["is_solved"] is True
        assert "solution" in data

        sol = data["solution"]
        assert "scenario" in sol
        assert "fleet" in sol
        assert "nodes" in sol
        assert "destination" in sol
        assert "allocation" in sol
        assert "routes" in sol
        assert "metrics" in sol
        assert "validation" in sol

        # Check Fleet & Validation status
        assert sol["fleet"]["number_of_vehicles"] >= 1
        assert sol["validation"]["status"] == "PASS"
        assert sol["validation"]["valid"] is True

        # Check GET retrieval
        get_resp = client.get(f"/api/scenarios/{data['id']}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["metadata"]["name"] == "E2E Stage 3 Verification"
        assert get_data["solution"]["metrics"]["total_allocated"] > 0
    finally:
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)
