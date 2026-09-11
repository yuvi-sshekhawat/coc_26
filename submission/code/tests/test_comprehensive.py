import math
import numpy as np
import pytest

from ai05.constraints import ConstraintViolation
from ai05.models import InstanceData, PreparedInstance, Region
from ai05.regions import classify_region, prepare_regions
from ai05.metrics import calculate_metrics, SolutionMetrics
from ai05.routing import RoutePlan, solve_cvrp, improve_routes_2opt
from ai05.validation import (
    validate_allocation,
    validate_regions,
    validate_routes,
    validate_metrics,
    validate_all,
)


def make_test_instance():
    # Depot at (10, 10)
    # Customers in various quadrants and exact axes
    coords = np.array([
        [10.0, 10.0],  # 0: depot
        [20.0, 20.0],  # 1: Q1 (right-up)
        [5.0, 20.0],   # 2: Q2 (left-up)
        [5.0, 5.0],    # 3: Q3 (left-down)
        [20.0, 5.0],   # 4: Q4 (right-down)
        [10.0, 25.0],  # 5: on y-axis positive -> right-up
        [25.0, 10.0],  # 6: on x-axis positive -> right-up
        [10.0, 0.0],   # 7: on y-axis negative -> right-down
        [0.0, 10.0],   # 8: on x-axis negative -> left-up
    ], dtype=float)

    demand = np.array([0, 10, 10, 10, 10, 10, 10, 10, 10])
    diff = coords[:, None, :] - coords[None, :, :]
    dist = np.rint(np.sqrt(np.sum(diff * diff, axis=2))).astype(float)
    np.fill_diagonal(dist, 0)

    return InstanceData(
        name="A-n32-k5",
        node_coord=coords,
        demand=demand,
        depot=0,
        vehicles=4,
        capacity=50,
        edge_weight_type="EUC_2D",
        edge_weight=dist,
    )


# -------------------------------------------------------------
# A. REGION ASSIGNMENT TESTS
# -------------------------------------------------------------
def test_region_assignment_all_quadrants():
    inst = make_test_instance()
    assert classify_region(inst, 1) == Region.RIGHT_UP
    assert classify_region(inst, 2) == Region.LEFT_UP
    assert classify_region(inst, 3) == Region.LEFT_DOWN
    assert classify_region(inst, 4) == Region.RIGHT_DOWN


def test_region_assignment_axes_rules():
    inst = make_test_instance()
    # x == depot_x, y > depot_y (node 5) -> positive/right & positive/up -> RIGHT_UP
    assert classify_region(inst, 5) == Region.RIGHT_UP
    # x > depot_x, y == depot_y (node 6) -> positive/right & positive/up -> RIGHT_UP
    assert classify_region(inst, 6) == Region.RIGHT_UP
    # x == depot_x, y < depot_y (node 7) -> positive/right & negative/down -> RIGHT_DOWN
    assert classify_region(inst, 7) == Region.RIGHT_DOWN
    # x < depot_x, y == depot_y (node 8) -> negative/left & positive/up -> LEFT_UP
    assert classify_region(inst, 8) == Region.LEFT_UP


# -------------------------------------------------------------
# B. ALLOCATION TESTS
# -------------------------------------------------------------
def test_allocation_valid_zero_and_full():
    inst = make_test_instance()
    # S = floor(0.70 * 80) = 56
    assert inst.stock == 56

    # Valid: some zero, some full, total <= 56
    q = np.array([0, 10, 10, 10, 10, 10, 6, 0, 0])
    assert np.sum(q) == 56
    validate_allocation(inst, q)


def test_allocation_exceeds_individual_demand_fails():
    inst = make_test_instance()
    q = np.array([0, 11, 0, 0, 0, 0, 0, 0, 0])  # d_1 is 10
    with pytest.raises(ConstraintViolation, match="q_i > d_i"):
        validate_allocation(inst, q)


def test_allocation_negative_fails():
    inst = make_test_instance()
    q = np.array([0, -1, 5, 0, 0, 0, 0, 0, 0])
    with pytest.raises(ConstraintViolation, match="q_i < 0"):
        validate_allocation(inst, q)


def test_allocation_stock_overflow_fails():
    inst = make_test_instance()
    # Stock is 56, try allocating 60
    q = np.array([0, 10, 10, 10, 10, 10, 10, 0, 0])
    with pytest.raises(ConstraintViolation, match="exceeds stock"):
        validate_allocation(inst, q)


def test_allocation_depot_nonzero_fails():
    inst = make_test_instance()
    q = np.array([1, 5, 5, 0, 0, 0, 0, 0, 0])
    with pytest.raises(ConstraintViolation, match="Depot allocation must be zero"):
        validate_allocation(inst, q)


# -------------------------------------------------------------
# C. ROUTING TESTS
# -------------------------------------------------------------
def test_routing_depot_start_end():
    inst = make_test_instance()
    q = np.array([0, 10, 10, 0, 0, 0, 0, 0, 0])
    # Route not starting/ending at depot
    bad_routes = [[1, 2, 0]]
    with pytest.raises(ConstraintViolation, match="must start and end at official depot"):
        validate_routes(inst, q, bad_routes)


def test_routing_capacity_overflow():
    inst = make_test_instance()
    # capacity is 50
    q = np.array([0, 10, 10, 10, 10, 10, 5, 0, 0])
    # route visiting 1, 2, 3, 4, 5, 6 with load 55 > 50
    overflow_routes = [[0, 1, 2, 3, 4, 5, 6, 0]]
    with pytest.raises(ConstraintViolation, match="exceeds vehicle capacity"):
        validate_routes(inst, q, overflow_routes)


def test_routing_missing_customer():
    inst = make_test_instance()
    q = np.array([0, 10, 10, 0, 0, 0, 0, 0, 0])
    # Only visits customer 1, customer 2 is missing
    partial_routes = [[0, 1, 0]]
    with pytest.raises(ConstraintViolation, match="Route coverage mismatch"):
        validate_routes(inst, q, partial_routes)


def test_routing_duplicate_customer():
    inst = make_test_instance()
    q = np.array([0, 10, 10, 0, 0, 0, 0, 0, 0])
    # Visits customer 1 twice
    duplicate_routes = [[0, 1, 2, 1, 0]]
    with pytest.raises(ConstraintViolation, match="visited more than once"):
        validate_routes(inst, q, duplicate_routes)


def test_routing_zero_allocation_customer_routed_fails():
    inst = make_test_instance()
    q = np.array([0, 10, 10, 0, 0, 0, 0, 0, 0])  # customer 3 has q_3 = 0
    routes_with_zero_alloc = [[0, 1, 2, 3, 0]]
    with pytest.raises(ConstraintViolation, match="with zero allocation"):
        validate_routes(inst, q, routes_with_zero_alloc)


# -------------------------------------------------------------
# D. METRICS & FAIRNESS TESTS
# -------------------------------------------------------------
def test_metrics_balance_and_upper_bound():
    inst = make_test_instance()
    prep = prepare_regions(inst)

    q = np.array([0, 7, 7, 7, 7, 7, 7, 7, 7])
    # Create valid routes for active customers
    route_plan = RoutePlan(
        routes=[[0, 1, 2, 0], [0, 3, 4, 0], [0, 5, 6, 0], [0, 7, 8, 0]],
        loads=[14, 14, 14, 14],
        route_distances=[
            int(round(inst.edge_weight[0, 1] + inst.edge_weight[1, 2] + inst.edge_weight[2, 0])),
            int(round(inst.edge_weight[0, 3] + inst.edge_weight[3, 4] + inst.edge_weight[4, 0])),
            int(round(inst.edge_weight[0, 5] + inst.edge_weight[5, 6] + inst.edge_weight[6, 0])),
            int(round(inst.edge_weight[0, 7] + inst.edge_weight[7, 8] + inst.edge_weight[8, 0])),
        ],
        total_distance=0,
    )
    total_dist = sum(route_plan.route_distances)
    route_plan = RoutePlan(
        routes=route_plan.routes,
        loads=route_plan.loads,
        route_distances=route_plan.route_distances,
        total_distance=total_dist,
    )

    metrics = calculate_metrics(prep, q, route_plan)
    assert metrics.fairness_upper_bound == pytest.approx(56 / 80)
    assert metrics.fairness_gap >= 0
    assert 0 <= metrics.balance <= 1.0

    report = validate_all(prep, q, route_plan.routes, route_plan, metrics)
    assert report.valid


# -------------------------------------------------------------
# E. END-TO-END WORKFLOW TESTS
# -------------------------------------------------------------
def test_end_to_end_pipeline():
    inst = make_test_instance()
    prep = prepare_regions(inst)

    from ai05.allocation import solve_max_min_allocation
    alloc_res = solve_max_min_allocation(prep)
    q = alloc_res.allocation

    route_plan = solve_cvrp(inst, q, time_limit_s=1, seed=42)
    improved_routes = improve_routes_2opt(inst, q, route_plan)
    metrics = calculate_metrics(prep, q, improved_routes)

    report = validate_all(prep, q, improved_routes.routes, improved_routes, metrics)
    assert report.valid
    assert len(report.errors) == 0
