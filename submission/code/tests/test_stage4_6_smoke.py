
import numpy as np

from ai05.models import InstanceData
from ai05.regions import prepare_regions
from ai05.routing import solve_cvrp, improve_routes_2opt
from ai05.metrics import calculate_metrics
from ai05.constraints import validate_routes
from ai05.optimization import solve_joint_search, improve_allocation_same_region


def synthetic_instance():
    coords = np.array([
        [0, 0],
        [10, 10],
        [-10, 10],
        [-10, -10],
        [10, -10],
        [8, 12],
        [-12, 8],
    ], dtype=float)

    demand = np.array([0, 10, 12, 11, 9, 8, 7])
    diff = coords[:, None, :] - coords[None, :, :]
    euclidean = np.sqrt(np.sum(diff * diff, axis=2))
    dist = np.rint(euclidean).astype(float)
    np.fill_diagonal(dist, 0)

    return InstanceData(
        name="A-n32-k5",
        node_coord=coords,
        demand=demand,
        depot=0,
        vehicles=2,
        capacity=100,
        edge_weight_type="EUC_2D",
        edge_weight=dist,
    )


def test_routing_and_metrics():
    inst = synthetic_instance()
    prepared = prepare_regions(inst)

    q = np.array([0, 5, 6, 5, 4, 4, 3])
    route = solve_cvrp(inst, q, time_limit_s=1)
    validate_routes(inst, q, route.routes)

    improved = improve_routes_2opt(inst, q, route)
    validate_routes(inst, q, improved.routes)

    metrics = calculate_metrics(prepared, q, improved)
    assert metrics.total_distance >= 0
    assert 0 <= metrics.minimum_service_ratio <= 1


def test_joint_and_local_search():
    inst = synthetic_instance()
    prepared = prepare_regions(inst)

    result = solve_joint_search(
        prepared,
        allocation_candidates=4,
        route_time_limit_s=1,
        seed=42,
    )
    validate_routes(inst, result.allocation, result.route_plan.routes)

    improved = improve_allocation_same_region(
        prepared,
        result,
        max_iterations=2,
        route_time_limit_s=1,
    )
    validate_routes(inst, improved.allocation, improved.route_plan.routes)

    assert (
        improved.metrics.minimum_service_ratio + 1e-9
        >= result.metrics.minimum_service_ratio
    )
