from __future__ import annotations

import csv
import io
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import numpy as np

from ai05.allocation import solve_max_min_allocation
from ai05.metrics import SolutionMetrics, calculate_metrics
from ai05.models import InstanceData, PreparedInstance, Region
from ai05.regions import prepare_regions
from ai05.routing import RoutePlan, improve_routes_2opt, solve_cvrp
from ai05.validation import ValidationReport, validate_all
from .road_geometry import compute_vehicle_road_route, get_road_geometry_for_route


@dataclass(frozen=True)
class CustomerRecord:
    customer_id: int
    location_name: str
    latitude: float
    longitude: float
    demand: int


@dataclass(frozen=True)
class ScenarioInput:
    name: str
    depot_name: str
    depot_latitude: float
    depot_longitude: float
    customers: list[CustomerRecord]


def sanitize_scenario_id(name: str) -> str:
    """
    Sanitize a scenario name to prevent path traversal and ensure a safe folder name.
    """
    # Replace non-alphanumeric chars with underscores
    cleaned = re.sub(r"[^a-zA-Z0-9_\- ]", "", name.strip())
    # Replace spaces with underscores
    slug = re.sub(r"\s+", "_", cleaned).lower()
    slug = slug.strip("._-")
    if not slug:
        slug = "relief_scenario"
    return slug[:60]


def parse_and_validate_csv(csv_content: str) -> list[CustomerRecord]:
    """
    Validate and parse uploaded requirements CSV.
    
    Validation requirements:
    - Required columns: customer_id, location_name, latitude, longitude, demand
    - Numeric demand > 0
    - Valid latitude (-90 to 90)
    - Valid longitude (-180 to 180)
    - Unique customer IDs
    - No malformed/empty required rows
    """
    f = io.StringIO(csv_content.strip())
    reader = csv.DictReader(f)

    if not reader.fieldnames:
        raise ValueError("The uploaded CSV is empty or has no header row.")

    # Normalize column names
    field_map = {col.strip().lower(): col for col in reader.fieldnames if col}
    required_keys = ["customer_id", "location_name", "latitude", "longitude", "demand"]
    missing = [k for k in required_keys if k not in field_map]
    if missing:
        raise ValueError(
            f"Missing required CSV columns: {', '.join(missing)}. "
            f"Expected: customer_id, location_name, latitude, longitude, demand"
        )

    records: list[CustomerRecord] = []
    seen_ids: set[int] = set()

    for row_idx, row in enumerate(reader, start=2):
        # Skip completely empty rows
        if not any(row.values()):
            continue

        raw_id = row.get(field_map["customer_id"], "").strip()
        raw_name = row.get(field_map["location_name"], "").strip()
        raw_lat = row.get(field_map["latitude"], "").strip()
        raw_lon = row.get(field_map["longitude"], "").strip()
        raw_demand = row.get(field_map["demand"], "").strip()

        if not raw_id or not raw_name or not raw_lat or not raw_lon or not raw_demand:
            raise ValueError(
                f"Row {row_idx}: Missing required values. All columns must be filled."
            )

        try:
            cust_id = int(raw_id)
        except ValueError:
            raise ValueError(f"Row {row_idx}: 'customer_id' must be an integer, got '{raw_id}'.")

        if cust_id <= 0:
            raise ValueError(f"Row {row_idx}: 'customer_id' must be positive, got {cust_id}.")

        if cust_id in seen_ids:
            raise ValueError(f"Row {row_idx}: Duplicate 'customer_id' {cust_id} detected.")
        seen_ids.add(cust_id)

        try:
            lat = float(raw_lat)
        except ValueError:
            raise ValueError(f"Row {row_idx}: 'latitude' must be a valid number, got '{raw_lat}'.")

        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Row {row_idx}: 'latitude' {lat} is out of bounds (-90.0 to 90.0).")

        try:
            lon = float(raw_lon)
        except ValueError:
            raise ValueError(f"Row {row_idx}: 'longitude' must be a valid number, got '{raw_lon}'.")

        if not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Row {row_idx}: 'longitude' {lon} is out of bounds (-180.0 to 180.0).")

        try:
            demand = int(float(raw_demand))
        except ValueError:
            raise ValueError(f"Row {row_idx}: 'demand' must be a valid integer, got '{raw_demand}'.")

        if demand <= 0:
            raise ValueError(f"Row {row_idx}: 'demand' must be strictly positive, got {demand}.")

        records.append(
            CustomerRecord(
                customer_id=cust_id,
                location_name=raw_name,
                latitude=lat,
                longitude=lon,
                demand=demand,
            )
        )

    if not records:
        raise ValueError("The uploaded CSV contains no customer rows.")

    return records


def build_scenario_instance(scenario: ScenarioInput) -> tuple[InstanceData, PreparedInstance]:
    """
    ADAPTER LAYER: Convert real-world geographic scenario into AI-05 InstanceData.
    
    SYSTEM 1 (Optimization):
      - Planar coordinates (x, y) projected from lat/lon relative to depot
      - Euclidean 2D distance matrix
      - CVRPLIB-compatible integer demands and bounds
    
    SYSTEM 2 (Geographic):
      - Strictly preserved in scenario metadata, NOT mixed into CVRPLIB coordinates.
    """
    depot_lat = scenario.depot_latitude
    depot_lon = scenario.depot_longitude
    customers = scenario.customers
    n = len(customers) + 1  # 0 is depot, 1..len are customers

    # Planar projection (approximate 1 unit = ~100m)
    # Keeping quadrant signs exactly aligned:
    # x_rel >= 0 (East), y_rel >= 0 (North) -> RIGHT_UP
    # x_rel < 0 (West), y_rel >= 0 (North)  -> LEFT_UP
    # x_rel < 0 (West), y_rel < 0 (South)   -> LEFT_DOWN
    # x_rel >= 0 (East), y_rel < 0 (South)  -> RIGHT_DOWN
    lat_rad = math.radians(depot_lat)
    cos_lat = math.cos(lat_rad)
    # Base coordinate origin at (1000.0, 1000.0)
    base_x = 1000.0
    base_y = 1000.0

    node_coord = np.zeros((n, 2), dtype=float)
    node_coord[0] = [base_x, base_y]

    demand = np.zeros(n, dtype=int)
    demand[0] = 0

    for idx, c in enumerate(customers, start=1):
        dx_km = (c.longitude - depot_lon) * 111.32 * cos_lat
        dy_km = (c.latitude - depot_lat) * 111.32
        # Scale to integer-friendly coordinate space (e.g. 1 unit = 0.1 km = 100m)
        node_coord[idx] = [round(base_x + dx_km * 10.0, 2), round(base_y + dy_km * 10.0, 2)]
        demand[idx] = c.demand

    # Determine vehicles K and capacity Q
    total_demand = int(np.sum(demand[1:]))
    stock = int(math.floor(0.70 * total_demand))
    num_cust = len(customers)
    # Target 3-5 stops per vehicle
    num_vehicles = max(2, min(6, math.ceil(num_cust / 4)))
    # Capacity must comfortably hold average stock share plus margin
    vehicle_capacity = int(math.ceil((stock / num_vehicles) * 1.35))

    diff = node_coord[:, np.newaxis, :] - node_coord[np.newaxis, :, :]
    dist = np.sqrt(np.sum(diff ** 2, axis=-1))
    edge_weight = np.rint(dist)

    instance = InstanceData(
        name=scenario.name,
        node_coord=node_coord,
        demand=demand,
        depot=0,
        vehicles=num_vehicles,
        capacity=vehicle_capacity,
        edge_weight_type="EUC_2D",
        edge_weight=edge_weight,
    )

    prepared = prepare_regions(instance)
    return instance, prepared


def solve_scenario_relief(
    scenario: ScenarioInput,
    route_time_limit_s: int = 5,
) -> dict[str, Any]:
    """
    Run the AI-05 Fair Relief optimization pipeline for a real-world scenario.
    """
    instance, prepared = build_scenario_instance(scenario)

    # 1. Stage 3: Exact Max-Min Fair Allocation
    alloc_result = solve_max_min_allocation(prepared)
    allocation = np.asarray(alloc_result.allocation, dtype=int)

    # 2. Stage 4: Active-customer OR-Tools CVRP
    raw_plan = solve_cvrp(
        instance,
        allocation,
        first_solution="PARALLEL_CHEAPEST_INSERTION",
        metaheuristic="GUIDED_LOCAL_SEARCH",
        time_limit_s=route_time_limit_s,
    )

    # 3. Deterministic 2-opt route improvement
    improved_plan = improve_routes_2opt(instance, allocation, raw_plan)

    # 4. Authoritative Solution Metrics
    metrics: SolutionMetrics = calculate_metrics(prepared, allocation, improved_plan)

    # 5. Authoritative Constraint Validation
    validation_report: ValidationReport = validate_all(
        prepared,
        allocation,
        improved_plan.routes,
    )

    # Map back to real-world customer IDs and locations
    id_map = {idx: c for idx, c in enumerate(scenario.customers, start=1)}

    # Build detailed node records with strict coordinate separation
    nodes_payload = []
    # Depot node
    nodes_payload.append({
        "id": 0,
        "is_depot": True,
        "location_name": scenario.depot_name,
        "geographic": {
            "latitude": scenario.depot_latitude,
            "longitude": scenario.depot_longitude,
        },
        "optimization": {
            "x": float(instance.node_coord[0, 0]),
            "y": float(instance.node_coord[0, 1]),
        },
        "original_demand": 0,
        "allocated_demand": 0,
        "ratio": 1.0,
        "region": "DEPOT",
    })

    for idx, c in enumerate(scenario.customers, start=1):
        q_i = int(allocation[idx])
        d_i = c.demand
        ratio = float(q_i / d_i) if d_i > 0 else 0.0
        region_enum = prepared.regions[idx]
        nodes_payload.append({
            "id": idx,
            "customer_id": c.customer_id,
            "is_depot": False,
            "location_name": c.location_name,
            "geographic": {
                "latitude": c.latitude,
                "longitude": c.longitude,
            },
            "optimization": {
                "x": float(instance.node_coord[idx, 0]),
                "y": float(instance.node_coord[idx, 1]),
            },
            "original_demand": d_i,
            "allocated_demand": q_i,
            "ratio": ratio,
            "region": region_enum.name,
        })

    # Build routes with real road geometries and diagnostic validation
    routes_payload = []
    for veh_idx, route_nodes in enumerate(improved_plan.routes, start=1):
        ordered_coords: list[list[float] | None] = []
        ordered_names: list[str] = []
        ordered_node_ids: list[int] = list(route_nodes)

        for node_id in route_nodes:
            if node_id == 0:
                ordered_coords.append([scenario.depot_longitude, scenario.depot_latitude])
                ordered_names.append(scenario.depot_name)
            else:
                cust = id_map.get(node_id)
                if cust:
                    ordered_coords.append([cust.longitude, cust.latitude])
                    ordered_names.append(cust.location_name)
                else:
                    ordered_coords.append(None)
                    ordered_names.append(f"Customer #{node_id} (Unmapped)")

        road_res = compute_vehicle_road_route(
            vehicle=veh_idx,
            node_ids=ordered_node_ids,
            node_names=ordered_names,
            coords_list=ordered_coords,
        )

        load = int(improved_plan.loads[veh_idx - 1]) if veh_idx - 1 < len(improved_plan.loads) else 0
        dist = int(improved_plan.route_distances[veh_idx - 1]) if veh_idx - 1 < len(improved_plan.route_distances) else 0

        valid_ordered_coords = [c for c in ordered_coords if c is not None]

        routes_payload.append({
            "vehicle": veh_idx,
            "nodes": ordered_node_ids,
            "location_names": ordered_names,
            "load": load,
            "capacity": instance.capacity,
            "distance": dist,  # Official CVRPLIB distance - PRESERVED!
            "road_distance_km": road_res.road_distance_km,
            "road_distance_meters": road_res.road_distance_meters,
            "road_duration_seconds": road_res.road_duration_seconds,
            "road_duration_minutes": road_res.road_duration_minutes,
            "road_duration_formatted": road_res.road_duration_formatted,
            "status": road_res.status,
            "has_errors": road_res.has_errors,
            "error_summary": road_res.error_summary,
            "segments": [s.to_dict() for s in road_res.segments],
            "ordered_coords": valid_ordered_coords,
            "road_geometry": road_res.full_geometry if road_res.full_geometry else valid_ordered_coords,
        })

    return {
        "status": "active",
        "scenario": {
            "name": scenario.name,
            "depot_name": scenario.depot_name,
            "depot_latitude": scenario.depot_latitude,
            "depot_longitude": scenario.depot_longitude,
            "total_customers": len(scenario.customers),
            "total_demand": int(instance.total_demand),
            "stock": int(instance.stock),
            "vehicles": int(instance.vehicles),
            "capacity": int(instance.capacity),
        },
        "nodes": nodes_payload,
        "allocation": [int(x) for x in allocation],
        "routes": routes_payload,
        "metrics": {
            "minimum_service_ratio": float(metrics.minimum_service_ratio),
            "maximum_service_ratio": float(metrics.maximum_service_ratio),
            "balance": float(metrics.balance),
            "total_distance": int(metrics.total_distance),
            "total_allocated": int(metrics.total_allocated),
            "fairness_upper_bound": float(metrics.fairness_upper_bound),
            "fairness_gap": float(metrics.fairness_gap),
            "regional_original": {r.name: int(metrics.regional_original[r]) for r in Region},
            "regional_delivered": {r.name: int(metrics.regional_delivered[r]) for r in Region},
            "regional_service": {r.name: float(metrics.regional_service[r]) for r in Region},
        },
        "validation": {
            "valid": bool(validation_report.valid),
            "status": "PASS" if validation_report.valid else "FAIL",
            "errors": list(validation_report.errors),
            "checks": {
                "allocation_bounds": validation_report.allocation_bounds_ok,
                "stock_bound": validation_report.stock_ok,
                "regional_coverage": validation_report.regional_coverage_ok,
                "depot_start_end": validation_report.depot_start_end_ok,
                "vehicle_capacity": validation_report.vehicle_capacity_ok,
                "route_coverage": validation_report.route_coverage_ok,
                "customer_uniqueness": validation_report.customer_uniqueness_ok,
            },
        },
    }
