from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .constraints import validate_routes
from .distance import validate_distance_matrix
from .models import InstanceData


@dataclass(frozen=True)
class RoutePlan:
    routes: list[list[int]]
    loads: list[int]
    route_distances: list[int]
    total_distance: int


def _integer_distance_matrix(instance: InstanceData) -> np.ndarray:
    """
    OR-Tools uses integer transit costs. For these CVRPLIB instances the
    published/computed edge weights are integer-valued, so we preserve them
    exactly rather than inventing a new rounding convention.
    """
    validate_distance_matrix(instance)
    D = instance.edge_weight

    if not np.allclose(D, np.rint(D), atol=1e-9):
        raise ValueError(
            "Non-integer edge weights detected. Do not introduce ad-hoc rounding; "
            "the instance's official edge-weight semantics must first be resolved."
        )

    return np.rint(D).astype(np.int64)


def solve_cvrp(
    instance: InstanceData,
    allocation: Sequence[int | float],
    *,
    first_solution: str = "PARALLEL_CHEAPEST_INSERTION",
    metaheuristic: str = "GUIDED_LOCAL_SEARCH",
    time_limit_s: int = 5,
    seed: int = 42,
) -> RoutePlan:
    """
    Stage 4 CVRP.

    Important:
      routing demand = allocation q_i, NOT original demand d_i.

    Customers with q_i == 0 are not routed in this single-visit implementation.
    """
    q = np.asarray(allocation, dtype=float)
    D = _integer_distance_matrix(instance)

    active = [i for i in instance.customers if q[i] > 1e-9]

    # No active customers -> empty routes, zero distance.
    if not active:
        routes = [[instance.depot, instance.depot] for _ in range(instance.vehicles)]
        loads = [0] * instance.vehicles
        distances = [0] * instance.vehicles
        return RoutePlan(routes, loads, distances, 0)

    # A single-visit customer cannot require more than vehicle capacity.
    too_large = [i for i in active if q[i] > instance.capacity + 1e-9]
    if too_large:
        raise ValueError(
            "Single-visit routing cannot serve customers whose allocated quantity "
            f"exceeds vehicle capacity: {too_large}"
        )

    # Active nodes map: index 0 is depot, indices 1..len(active) are active customers
    node_list = [instance.depot] + active
    num_nodes = len(node_list)

    manager = pywrapcp.RoutingIndexManager(
        num_nodes,
        instance.vehicles,
        0,  # depot index in node_list is 0
    )
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        u = node_list[manager.IndexToNode(from_index)]
        v = node_list[manager.IndexToNode(to_index)]
        return int(D[u, v])

    transit_idx = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    def demand_callback(from_index: int) -> int:
        u = node_list[manager.IndexToNode(from_index)]
        return int(round(q[u]))

    demand_idx = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_idx,
        0,  # no slack
        [int(instance.capacity)] * instance.vehicles,
        True,  # start cumul at zero
        "Capacity",
    )

    params = pywrapcp.DefaultRoutingSearchParameters()

    first_map = {
        "PATH_CHEAPEST_ARC":
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC,
        "PARALLEL_CHEAPEST_INSERTION":
            routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION,
        "SAVINGS":
            routing_enums_pb2.FirstSolutionStrategy.SAVINGS,
        "AUTOMATIC":
            routing_enums_pb2.FirstSolutionStrategy.AUTOMATIC,
    }
    meta_map = {
        "GUIDED_LOCAL_SEARCH":
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH,
        "TABU_SEARCH":
            routing_enums_pb2.LocalSearchMetaheuristic.TABU_SEARCH,
        "SIMULATED_ANNEALING":
            routing_enums_pb2.LocalSearchMetaheuristic.SIMULATED_ANNEALING,
        "AUTOMATIC":
            routing_enums_pb2.LocalSearchMetaheuristic.AUTOMATIC,
    }

    params.first_solution_strategy = first_map.get(
        first_solution,
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION,
    )
    params.local_search_metaheuristic = meta_map.get(
        metaheuristic,
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH,
    )
    params.time_limit.seconds = int(max(1, time_limit_s))
    params.log_search = False

    del seed

    solution = routing.SolveWithParameters(params)
    if solution is None:
        raise RuntimeError(
            f"No feasible CVRP route found for {instance.name}."
        )

    routes: list[list[int]] = []
    loads: list[int] = []
    route_distances: list[int] = []

    for vehicle_id in range(instance.vehicles):
        index = routing.Start(vehicle_id)
        route: list[int] = []
        route_load = 0
        route_distance = 0

        while not routing.IsEnd(index):
            local_node = manager.IndexToNode(index)
            global_node = node_list[local_node]
            route.append(global_node)
            route_load += int(round(q[global_node]))

            previous = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(
                previous,
                index,
                vehicle_id,
            )

        local_end = manager.IndexToNode(index)
        global_end = node_list[local_end]
        route.append(global_end)

        routes.append(route)
        loads.append(route_load)
        route_distances.append(int(route_distance))

    validate_routes(instance, allocation, routes)

    return RoutePlan(
        routes=routes,
        loads=loads,
        route_distances=route_distances,
        total_distance=int(sum(route_distances)),
    )


def two_opt_route(
    instance: InstanceData,
    route: Sequence[int],
) -> list[int]:
    """
    Feasibility-preserving 2-opt for a fixed route.

    It only changes order, so route load and customer coverage remain unchanged.
    """
    if len(route) <= 3:
        return list(route)

    best = list(route)
    improved = True

    while improved:
        improved = False
        best_distance = route_distance(instance, best)

        # Keep endpoints fixed at the depot.
        for i in range(1, len(best) - 2):
            for j in range(i + 1, len(best) - 1):
                candidate = (
                    best[:i]
                    + list(reversed(best[i:j + 1]))
                    + best[j + 1:]
                )
                candidate_distance = route_distance(instance, candidate)

                if candidate_distance + 1e-9 < best_distance:
                    best = candidate
                    improved = True
                    best_distance = candidate_distance

    return best


def route_distance(instance: InstanceData, route: Sequence[int]) -> int:
    return int(
        sum(
            round(instance.edge_weight[u, v])
            for u, v in zip(route, route[1:])
        )
    )


def improve_routes_2opt(
    instance: InstanceData,
    allocation: Sequence[int | float],
    route_plan: RoutePlan,
) -> RoutePlan:
    improved_routes = [
        two_opt_route(instance, route)
        if len([n for n in route[1:-1] if n != instance.depot]) >= 3
        else list(route)
        for route in route_plan.routes
    ]

    validate_routes(instance, allocation, improved_routes)

    distances = [route_distance(instance, r) for r in improved_routes]
    loads = [
        int(sum(float(allocation[n]) for n in r[1:-1]))
        for r in improved_routes
    ]

    return RoutePlan(
        routes=improved_routes,
        loads=loads,
        route_distances=distances,
        total_distance=int(sum(distances)),
    )
