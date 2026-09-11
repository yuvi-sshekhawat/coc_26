from __future__ import annotations

import math
from typing import Mapping

import numpy as np

from .models import InstanceData, PreparedInstance, Region
from .metrics import SolutionMetrics, calculate_metrics
from .optimization import CandidateSolution, solve_joint_search, improve_allocation_same_region
from .routing import solve_cvrp, improve_routes_2opt
from .validation import validate_allocation, validate_routes


def solve_nearest_first(
    prepared: PreparedInstance,
    *,
    route_time_limit_s: int = 3,
    seed: int = 42,
) -> CandidateSolution:
    """
    Baseline 1: Nearest-first allocation.
    Greedily satisfies customers closest to depot until stock S is exhausted.
    """
    instance = prepared.instance
    depot = instance.depot
    stock_remaining = instance.stock

    # Sort customers by distance to depot
    customers = sorted(
        instance.customers,
        key=lambda i: float(instance.edge_weight[depot, i]),
    )

    q = np.zeros(instance.dimension, dtype=int)
    for c in customers:
        if stock_remaining <= 0:
            break
        alloc = min(int(instance.demand[c]), stock_remaining)
        q[c] = alloc
        stock_remaining -= alloc

    validate_allocation(instance, q)

    route_plan = solve_cvrp(
        instance,
        q,
        first_solution="PARALLEL_CHEAPEST_INSERTION",
        metaheuristic="GUIDED_LOCAL_SEARCH",
        time_limit_s=route_time_limit_s,
        seed=seed,
    )
    route_plan = improve_routes_2opt(instance, q, route_plan)
    validate_routes(instance, q, route_plan.routes)

    metrics = calculate_metrics(prepared, q, route_plan)
    return CandidateSolution(allocation=q, route_plan=route_plan, metrics=metrics)


def solve_proportional(
    prepared: PreparedInstance,
    *,
    route_time_limit_s: int = 3,
    seed: int = 42,
) -> CandidateSolution:
    """
    Baseline 2: Proportional allocation.
    Allocates to each customer proportionally: q_i ≈ d_i * (S / sum(d_i)),
    using largest remainder method to ensure sum(q_i) == S and q_i <= d_i.
    """
    instance = prepared.instance
    total_demand = instance.total_demand
    stock = instance.stock

    q = np.zeros(instance.dimension, dtype=int)
    if total_demand == 0 or stock == 0:
        route_plan = solve_cvrp(instance, q, time_limit_s=route_time_limit_s, seed=seed)
        metrics = calculate_metrics(prepared, q, route_plan)
        return CandidateSolution(allocation=q, route_plan=route_plan, metrics=metrics)

    ratio = stock / total_demand
    remainders = []
    allocated_sum = 0

    for c in instance.customers:
        exact = instance.demand[c] * ratio
        base = int(math.floor(exact))
        q[c] = min(base, int(instance.demand[c]))
        allocated_sum += q[c]
        remainders.append((exact - base, c))

    # Allocate remaining units by largest remainder
    remainders.sort(key=lambda x: x[0], reverse=True)
    rem_units = stock - allocated_sum

    for _, c in remainders:
        if rem_units <= 0:
            break
        if q[c] < instance.demand[c]:
            q[c] += 1
            rem_units -= 1

    validate_allocation(instance, q)

    route_plan = solve_cvrp(
        instance,
        q,
        first_solution="PARALLEL_CHEAPEST_INSERTION",
        metaheuristic="GUIDED_LOCAL_SEARCH",
        time_limit_s=route_time_limit_s,
        seed=seed,
    )
    route_plan = improve_routes_2opt(instance, q, route_plan)
    validate_routes(instance, q, route_plan.routes)

    metrics = calculate_metrics(prepared, q, route_plan)
    return CandidateSolution(allocation=q, route_plan=route_plan, metrics=metrics)


def solve_fair_greedy(
    prepared: PreparedInstance,
    *,
    route_time_limit_s: int = 3,
    seed: int = 42,
) -> CandidateSolution:
    """
    Baseline 3: Fair Greedy allocation.
    Iteratively finds the region with the lowest current service ratio,
    and greedily allocates to the customer in that region closest to depot.
    """
    instance = prepared.instance
    depot = instance.depot
    stock_remaining = instance.stock

    q = np.zeros(instance.dimension, dtype=int)
    regional_delivered = {r: 0 for r in Region}
    regional_orig = prepared.regional_demand

    active_regions = [r for r in Region if regional_orig[r] > 0]

    # Pre-sort customers in each region by distance to depot
    customers_by_region: dict[Region, list[int]] = {r: [] for r in Region}
    for c in instance.customers:
        customers_by_region[prepared.regions[c]].append(c)

    for r in Region:
        customers_by_region[r].sort(key=lambda i: float(instance.edge_weight[depot, i]))

    while stock_remaining > 0:
        # Find active region with minimum current service ratio that still has unfulfilled demand
        eligible_regions = [
            r for r in active_regions
            if any(q[c] < instance.demand[c] for c in customers_by_region[r])
        ]
        if not eligible_regions:
            break

        # Region with lowest service ratio
        chosen_region = min(
            eligible_regions,
            key=lambda r: regional_delivered[r] / regional_orig[r],
        )

        # Pick nearest customer in that region with unfulfilled demand
        cand_cust = next(
            c for c in customers_by_region[chosen_region]
            if q[c] < instance.demand[c]
        )

        room = int(instance.demand[cand_cust] - q[cand_cust])
        step = min(room, stock_remaining)
        q[cand_cust] += step
        regional_delivered[chosen_region] += step
        stock_remaining -= step

    validate_allocation(instance, q)

    route_plan = solve_cvrp(
        instance,
        q,
        first_solution="PARALLEL_CHEAPEST_INSERTION",
        metaheuristic="GUIDED_LOCAL_SEARCH",
        time_limit_s=route_time_limit_s,
        seed=seed,
    )
    route_plan = improve_routes_2opt(instance, q, route_plan)
    validate_routes(instance, q, route_plan.routes)

    metrics = calculate_metrics(prepared, q, route_plan)
    return CandidateSolution(allocation=q, route_plan=route_plan, metrics=metrics)


def run_all_baselines_and_final(
    prepared: PreparedInstance,
    *,
    route_time_limit_s: int = 3,
    candidate_count: int = 30,
    seed: int = 42,
) -> dict[str, CandidateSolution]:
    """
    Run all three baselines and the final joint optimizer for comparison.
    """
    results: dict[str, CandidateSolution] = {}

    # Baseline 1
    results["baseline_nearest_first"] = solve_nearest_first(
        prepared,
        route_time_limit_s=route_time_limit_s,
        seed=seed,
    )

    # Baseline 2
    results["baseline_proportional"] = solve_proportional(
        prepared,
        route_time_limit_s=route_time_limit_s,
        seed=seed,
    )

    # Baseline 3
    results["baseline_fair_greedy"] = solve_fair_greedy(
        prepared,
        route_time_limit_s=route_time_limit_s,
        seed=seed,
    )

    # Final Joint Optimizer
    joint = solve_joint_search(
        prepared,
        allocation_candidates=candidate_count,
        route_time_limit_s=route_time_limit_s,
        seed=seed,
    )
    improved = improve_allocation_same_region(
        prepared,
        joint,
        max_iterations=30,
        route_time_limit_s=max(1, route_time_limit_s // 2),
    )
    final_routes = improve_routes_2opt(
        prepared.instance,
        improved.allocation,
        improved.route_plan,
    )
    final_metrics = calculate_metrics(
        prepared,
        improved.allocation,
        final_routes,
    )
    results["final_joint_optimizer"] = CandidateSolution(
        allocation=improved.allocation,
        route_plan=final_routes,
        metrics=final_metrics,
    )

    return results
