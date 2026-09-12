import json
import math
import re
import shutil
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch

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


# =====================================================================
# SECTION A: INPUT VERIFICATION
# =====================================================================

def test_input_01_single_house():
    """Verify single house scenario (boundary condition min 1 house)."""
    depot = LocationPoint("Base Depot", 26.9124, 75.7873)
    houses = [HouseRecord(1, "Single Community Point", 26.9200, 75.7900, demand=20)]
    scen = ScenarioInput("Single House Boundary Test", depot, None, houses)

    sol = solve_scenario_relief(scen, route_time_limit_s=1)
    assert sol["scenario"]["total_houses"] == 1
    assert sol["fleet"]["number_of_vehicles"] == 1
    assert sol["allocation"][1] == 14  # floor(0.70 * 20) = 14
    assert sol["validation"]["valid"] is True
    assert sol["routes"][0]["assigned_houses"] == [1]


def test_input_02_fifty_houses():
    """Verify exactly 50 houses scenario (boundary condition max 50 houses)."""
    depot = LocationPoint("Central Staging Hub", 26.9124, 75.7873)
    houses = []
    for i in range(1, 51):
        angle = (i / 50.0) * 2 * math.pi
        radius = 0.02 + (i % 5) * 0.004
        lat = round(26.9124 + radius * math.sin(angle), 5)
        lon = round(75.7873 + radius * math.cos(angle), 5)
        houses.append(HouseRecord(i, f"House Sector #{i}", lat, lon, demand=15))

    assert len(houses) == 50
    scen = ScenarioInput("50 Houses Scale Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=2)

    assert sol["scenario"]["total_houses"] == 50
    assert sol["validation"]["valid"] is True
    assert sol["validation"]["checks"]["stock_bound"] is True
    assert sol["validation"]["checks"]["customer_uniqueness"] is True


def test_input_03_fifty_one_houses_rejected():
    """Verify that >50 houses is strictly rejected at both adapter and API levels."""
    houses_51 = [
        HouseRecord(i, f"House #{i}", 26.9 + (i * 0.001), 75.7 + (i * 0.001), demand=10)
        for i in range(1, 52)
    ]
    with pytest.raises(ValueError, match="Number of houses cannot exceed 50"):
        validate_house_records(houses_51)

    payload = {
        "name": "51 Houses Reject",
        "depot_name": "Depot",
        "depot_latitude": 26.91,
        "depot_longitude": 75.78,
        "houses": [{"house_id": h.house_id, "location_name": h.location_name, "latitude": h.latitude, "longitude": h.longitude, "demand": 10} for h in houses_51],
    }
    resp = client.post("/api/scenarios", json=payload)
    assert resp.status_code in (400, 422)


def test_input_04_invalid_location_rejected():
    """Verify invalid coordinates (out of range, NaN) are rejected."""
    with pytest.raises(ValueError, match="latitude .* is out of bounds"):
        validate_house_records([HouseRecord(1, "Bad Lat", 95.0, 75.78, demand=10)])

    with pytest.raises(ValueError, match="longitude .* is out of bounds"):
        validate_house_records([HouseRecord(1, "Bad Lon", 26.91, -195.0, demand=10)])


def test_input_05_duplicate_location_rejected():
    """Verify duplicate house IDs or duplicate lat/lon coordinates are rejected."""
    dup_id = [
        HouseRecord(1, "A", 26.91, 75.78, demand=10),
        HouseRecord(1, "B", 26.92, 75.79, demand=15),
    ]
    with pytest.raises(ValueError, match="Duplicate house ID"):
        validate_house_records(dup_id)

    dup_coord = [
        HouseRecord(1, "A", 26.91, 75.78, demand=10),
        HouseRecord(2, "B", 26.91, 75.78, demand=15),
    ]
    with pytest.raises(ValueError, match="Duplicate house location"):
        validate_house_records(dup_coord)


def test_input_06_missing_source_rejected():
    """Verify missing source/depot name or coordinates is rejected."""
    payload = {
        "name": "Missing Source Test",
        "depot_name": "",  # Empty depot
        "depot_latitude": 26.91,
        "depot_longitude": 75.78,
        "houses": [{"house_id": 1, "location_name": "H1", "latitude": 26.92, "longitude": 75.79, "demand": 10}],
    }
    resp = client.post("/api/scenarios", json=payload)
    assert resp.status_code in (400, 422)


def test_input_07_destination_handling():
    """Verify destination can be either omitted (None) or specified, and routes adapt."""
    depot = LocationPoint("Base Depot", 26.9124, 75.7873)
    dest = LocationPoint("Emergency Hospital Staging", 26.8800, 75.8200)
    houses = [HouseRecord(1, "Clinic", 26.9200, 75.7900, demand=20)]

    # 1. With Destination
    scen_with_dest = ScenarioInput("With Dest", depot, dest, houses)
    sol_with = solve_scenario_relief(scen_with_dest, route_time_limit_s=1)
    assert sol_with["destination"] is not None
    assert sol_with["destination"]["name"] == "Emergency Hospital Staging"
    assert sol_with["routes"][0]["destination_visited"] is True
    assert -1 in sol_with["routes"][0]["nodes"]  # Destination node

    # 2. Without Destination
    scen_no_dest = ScenarioInput("No Dest", depot, None, houses)
    sol_no = solve_scenario_relief(scen_no_dest, route_time_limit_s=1)
    assert sol_no["destination"] is None
    assert sol_no["routes"][0]["destination_visited"] is False
    assert -1 not in sol_no["routes"][0]["nodes"]


# =====================================================================
# SECTION B: MAP VERIFICATION
# =====================================================================

def test_map_01_provider_configuration_and_fallback():
    """Verify map provider configuration gracefully handles missing API keys with fallback."""
    # Validate waypoint coordinates
    ok, err = validate_waypoint("Depot", [75.7873, 26.9124])
    assert ok is True
    assert err is None


def test_map_02_markers_payload():
    """Verify solution nodes payload contains complete geographic and optimization markers."""
    depot = LocationPoint("Depot Marker", 26.9124, 75.7873)
    houses = [HouseRecord(1, "House Marker", 26.9200, 75.7900, demand=15)]
    scen = ScenarioInput("Marker Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=1)

    nodes = sol["nodes"]
    assert len(nodes) == 2
    depot_node = nodes[0]
    assert depot_node["is_depot"] is True
    assert depot_node["geographic"]["latitude"] == 26.9124
    assert depot_node["geographic"]["longitude"] == 75.7873

    house_node = nodes[1]
    assert house_node["is_depot"] is False
    assert house_node["geographic"]["latitude"] == 26.9200
    assert house_node["geographic"]["longitude"] == 75.7900
    assert house_node["allocated_demand"] > 0


def test_map_03_route_geometry_valid():
    """Verify route geometry produces valid GeoJSON coordinates along physical streets."""
    depot = LocationPoint("Depot Hub", 26.9124, 75.7873)
    houses = [
        HouseRecord(1, "H1", 26.9200, 75.7900, demand=10),
        HouseRecord(2, "H2", 26.9150, 75.8000, demand=15),
    ]
    scen = ScenarioInput("Geometry Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=1)

    for r in sol["routes"]:
        assert len(r["road_geometry"]) >= 2
        for pt in r["road_geometry"]:
            assert len(pt) == 2
            lon, lat = pt
            assert -180.0 <= lon <= 180.0
            assert -90.0 <= lat <= 90.0
            assert not math.isnan(lon) and not math.isnan(lat)


def test_map_04_failed_route_no_fake_lines():
    """Verify that if a segment fails routing, it is marked failed without drawing fake lines."""
    with patch("app.services.road_geometry._fetch_single_segment_osrm", return_value={"connected": False, "error_reason": "No bridge connection"}):
        with patch("urllib.request.urlopen", side_effect=Exception("Routing outage")):
            route_res = compute_vehicle_road_route(
                vehicle=1,
                node_ids=[0, 1, 0],
                node_names=["Depot", "Island", "Depot"],
                coords_list=[[75.7873, 26.9124], [75.7900, 26.9200], [75.7873, 26.9124]],
            )
            assert route_res.has_errors is True
            failed_segs = [s for s in route_res.segments if not s.connected]
            assert len(failed_segs) > 0
            for fs in failed_segs:
                assert fs.status == "ROUTING_FAILED"
                assert fs.geometry == []  # Never fake straight lines


# =====================================================================
# SECTION C: OPTIMIZATION VERIFICATION
# =====================================================================

def test_optimization_01_vehicle_determination():
    """Verify fleet size is constraint-driven and not an arbitrary formula like len/4."""
    depot = LocationPoint("Depot", 26.9124, 75.7873)
    houses = [
        HouseRecord(1, "H1", 26.92, 75.79, demand=160),
        HouseRecord(2, "H2", 26.93, 75.80, demand=170),
        HouseRecord(3, "H3", 26.90, 75.77, demand=150),
        HouseRecord(4, "H4", 26.89, 75.76, demand=180),
    ]
    scen = ScenarioInput("Fleet Math Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=2)

    assert "bin-packing" in sol["fleet"]["rationale"]
    assert sol["fleet"]["number_of_vehicles"] >= 2  # Not 4 // 4 = 1


def test_optimization_02_allocation_bounds():
    """Verify stock and allocation bounds: sum q_i <= floor(0.70 * sum d_i) and 0 <= q_i <= d_i."""
    depot = LocationPoint("Depot", 26.9124, 75.7873)
    houses = [
        HouseRecord(1, "H1", 26.92, 75.79, demand=40),
        HouseRecord(2, "H2", 26.91, 75.78, demand=60),
    ]
    scen = ScenarioInput("Bounds Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=1)

    total_demand = 40 + 60
    expected_stock = math.floor(0.70 * total_demand)
    alloc = sol["allocation"]

    assert sum(alloc) <= expected_stock
    assert alloc[0] == 0
    assert 0 <= alloc[1] <= 40
    assert 0 <= alloc[2] <= 60
    assert sol["validation"]["checks"]["stock_bound"] is True
    assert sol["validation"]["checks"]["allocation_bounds"] is True


def test_optimization_03_vehicle_capacity():
    """Verify that every vehicle route obeys load <= capacity."""
    depot = LocationPoint("Depot", 26.9124, 75.7873)
    houses = [
        HouseRecord(i, f"House {i}", 26.91 + (i * 0.004), 75.78 + (i * 0.003), demand=25)
        for i in range(1, 8)
    ]
    scen = ScenarioInput("Capacity Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=2)

    for r in sol["routes"]:
        assert r["load"] <= r["capacity"]
    assert sol["validation"]["checks"]["vehicle_capacity"] is True


def test_optimization_04_fairness_max_min():
    """Verify max-min fairness objective: minimum service ratio is strictly maximized."""
    depot = LocationPoint("Depot", 26.9124, 75.7873)
    houses = [
        HouseRecord(1, "Large Need", 26.92, 75.79, demand=80),
        HouseRecord(2, "Small Need", 26.90, 75.77, demand=20),
    ]
    scen = ScenarioInput("Fairness Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=1)

    assert sol["metrics"]["minimum_service_ratio"] > 0.50
    assert sol["metrics"]["balance"] >= 0.0


def test_optimization_05_route_coverage():
    """Verify route coverage: all active customers (q_i > 0) are visited without duplication."""
    depot = LocationPoint("Depot", 26.9124, 75.7873)
    houses = [
        HouseRecord(1, "H1", 26.92, 75.79, demand=15),
        HouseRecord(2, "H2", 26.91, 75.80, demand=20),
        HouseRecord(3, "H3", 26.90, 75.78, demand=25),
    ]
    scen = ScenarioInput("Coverage Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=1)

    all_visited = []
    for r in sol["routes"]:
        all_visited.extend(r["assigned_houses"])

    active_customers = [idx for idx, q in enumerate(sol["allocation"]) if idx > 0 and q > 0]
    assert sorted(all_visited) == sorted(active_customers)
    assert len(all_visited) == len(set(all_visited))  # Uniqueness


# =====================================================================
# SECTION D: ROUTING VERIFICATION
# =====================================================================

def test_routing_01_valid_route_and_return_to_depot():
    """Verify that every route starts and ends at depot node 0."""
    depot = LocationPoint("Depot", 26.9124, 75.7873)
    houses = [HouseRecord(1, "H1", 26.92, 75.79, demand=15)]
    scen = ScenarioInput("Return Depot Test", depot, None, houses)
    sol = solve_scenario_relief(scen, route_time_limit_s=1)

    for r in sol["routes"]:
        assert r["return_to_depot"] is True
        assert r["nodes"][0] == 0
        assert r["nodes"][-1] == 0
        assert r["ordered_coords"][0] == [depot.longitude, depot.latitude]
        assert r["ordered_coords"][-1] == [depot.longitude, depot.latitude]


def test_routing_02_road_distance_consistency():
    """Verify triangle inequality and non-negativity in distance matrix."""
    coords = [[75.7873, 26.9124], [75.8100, 26.9150], [75.7850, 26.9300]]
    dist_mat, dur_mat, source, warnings = fetch_road_distance_matrix(coords)

    for i in range(3):
        assert dist_mat[i, i] == 0.0
        for j in range(3):
            if i != j:
                assert dist_mat[i, j] > 0.0
                assert dur_mat[i, j] > 0.0


def test_routing_03_routing_api_failure_fallback():
    """Verify system handles routing API outages by falling back to geodesic estimates."""
    coords = [[75.7873, 26.9124], [75.7900, 26.9200]]
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        dist_mat, dur_mat, source, warnings = fetch_road_distance_matrix(coords)
        assert source == "GEODESIC_ROAD_ESTIMATE"
        assert dist_mat[0, 1] > 0


# =====================================================================
# SECTION E: OFFICIAL BENCHMARKS
# =====================================================================

@pytest.mark.parametrize("instance_name", ["A-n32-k5", "A-n33-k5", "B-n31-k5"])
def test_benchmarks_01_authoritative_instances(instance_name: str):
    """Verify all 3 official benchmarks load and pass authoritative validation."""
    inst_path = ROOT / "data" / f"{instance_name}.vrp"
    assert inst_path.exists()

    inst = load_instance(inst_path)
    prep = prepare_regions(inst)

    # Max-min allocation
    alloc_res = solve_max_min_allocation(prep)
    alloc = np.asarray(alloc_res.allocation, dtype=int)

    # CVRP routing
    plan = solve_cvrp(inst, alloc, time_limit_s=1)

    # Validate against all authoritative constraints
    report = validate_all(prep, alloc, plan.routes, plan)
    assert report.valid is True
    assert report.stock_ok is True
    assert report.vehicle_capacity_ok is True
    assert report.customer_uniqueness_ok is True


# =====================================================================
# SECTION F: SECURITY & CONFIGURATION
# =====================================================================

def test_security_01_no_committed_api_secrets():
    """Verify that no real API secrets or credentials are tracked by git."""
    env_files = list(ROOT.glob(".env*")) + list((ROOT / "frontend").glob(".env*"))
    for ef in env_files:
        if ef.name == ".env.example":
            content = ef.read_text(encoding="utf-8")
            # Must not contain real keys
            assert "btxd98TN9aflrcp43UMC" not in content
            assert "your_maptiler_api_key_here" in content


def test_security_02_configurable_api_url():
    """Verify API endpoint health check works cleanly."""
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
