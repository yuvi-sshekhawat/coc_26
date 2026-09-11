from __future__ import annotations

from dataclasses import dataclass

import math
import random
from typing import Iterable

import numpy as np
from ortools.linear_solver import pywraplp

from .allocation import AllocationResult, solve_max_min_allocation
from .constraints import validate_allocation, validate_routes
from .distance import validate_distance_matrix
from .metrics import SolutionMetrics, calculate_metrics
from .models import PreparedInstance, Region
from .routing import RoutePlan, improve_routes_2opt, solve_cvrp


EPS = 1e-9


@dataclass(frozen=True)
class CandidateSolution:
    allocation: np.ndarray
    route_plan: RoutePlan
    metrics: SolutionMetrics


def lexicographically_better(
    candidate: CandidateSolution,
    incumbent: CandidateSolution | None,
) -> bool:
    if incumbent is None:
        return True

    a = candidate.metrics
    b = incumbent.metrics

    if a.minimum_service_ratio > b.minimum_service_ratio + EPS:
        return True
    if abs(a.minimum_service_ratio - b.minimum_service_ratio) > EPS:
        return False

    if a.total_distance < b.total_distance:
        return True
    if a.total_distance > b.total_distance:
        return False

    return a.balance > b.balance + EPS


def _allocation_as_array(
    prepared: PreparedInstance,
    allocation_by_node: dict[int, int],
) -> np.ndarray:
    q = np.zeros(prepared.instance.dimension, dtype=int)
    for i, value in allocation_by_node.items():
        q[int(i)] = int(value)
    return q


def generate_near_optimal_allocations(
    prepared: PreparedInstance,
    base_result: AllocationResult,
    *,
    count: int = 20,
    seed: int = 42,
    time_limit_ms: int = 2_000,
) -> list[np.ndarray]:
    """
    Stage 5 candidate generation.

    We preserve every region's delivered amount from the base max-min solution
    as a hard lower bound, so no generated candidate can have a worse regional
    service ratio than the base allocation.

    Secondary objectives:
      - deterministic route proxy (round-trip depot distance per unit)
      - randomized small perturbation for diversification

    Actual quality is decided only after running the real CVRP.
    """
    instance = prepared.instance
    rng = random.Random(seed)

    base = np.asarray(base_result.allocation, dtype=int)
    required_region = {
        region: int(base_result.regional_delivered[region])
        for region in Region
    }

    seen = {tuple(base.tolist())}
    candidates = [base.copy()]

    D = instance.edge_weight
    proxy = {
        i: 2.0 * float(D[instance.depot, i])
        for i in instance.customers
    }

    for k in range(max(0, count - 1)):
        solver = pywraplp.Solver.CreateSolver("CBC")
        if solver is None:
            break

        solver.SetTimeLimit(int(time_limit_ms))

        q = {
            i: solver.IntVar(0, int(instance.demand[i]), f"q_{i}")
            for i in instance.customers
        }

        solver.Add(sum(q[i] for i in instance.customers) <= instance.stock)

        for region in Region:
            nodes = [
                i for i in instance.customers
                if prepared.regions[i] == region
            ]
            solver.Add(
                sum(q[i] for i in nodes) >= required_region[region]
            )

        # Diversification: exact proxy + tiny deterministic noise.
        objective_terms = []
        for i in instance.customers:
            noise = rng.uniform(-0.03, 0.03)
            objective_terms.append((proxy[i] + noise, q[i]))

        solver.Minimize(sum(coef * var for coef, var in objective_terms))

        status = solver.Solve()
        if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            continue

        q_arr = _allocation_as_array(
            prepared,
            {
                i: int(round(q[i].solution_value()))
                for i in instance.customers
            },
        )

        validate_allocation(instance, q_arr)

        key = tuple(q_arr.tolist())
        if key not in seen:
            seen.add(key)
            candidates.append(q_arr)

    return candidates


def solve_joint_search(
    prepared: PreparedInstance,
    *,
    allocation_candidates: int = 20,
    route_time_limit_s: int = 3,
    allocation_time_limit_ms: int = 10_000,
    seed: int = 42,
) -> CandidateSolution:
    """
    Stage 5:
      fairness -> near-optimal allocation candidates -> exact CVRP evaluation.
    """
    validate_distance_matrix(prepared.instance)

    base = solve_max_min_allocation(
        prepared,
        time_limit_ms=allocation_time_limit_ms,
    )

    candidates = generate_near_optimal_allocations(
        prepared,
        base,
        count=allocation_candidates,
        seed=seed,
    )

    best: CandidateSolution | None = None

    first_solutions = [
        "PARALLEL_CHEAPEST_INSERTION",
        "SAVINGS",
        "PATH_CHEAPEST_ARC",
    ]
    metaheuristics = [
        "GUIDED_LOCAL_SEARCH",
        "TABU_SEARCH",
    ]

    for idx, q in enumerate(candidates):
        validate_allocation(prepared.instance, q)

        # A small deterministic portfolio of routing configurations.
        first = first_solutions[idx % len(first_solutions)]
        meta = metaheuristics[idx % len(metaheuristics)]

        route = solve_cvrp(
            prepared.instance,
            q,
            first_solution=first,
            metaheuristic=meta,
            time_limit_s=route_time_limit_s,
            seed=seed + idx,
        )
        route = improve_routes_2opt(
            prepared.instance,
            q,
            route,
        )

        metrics = calculate_metrics(
            prepared,
            q,
            route,
        )

        candidate = CandidateSolution(
            allocation=q.copy(),
            route_plan=route,
            metrics=metrics,
        )

        if lexicographically_better(candidate, best):
            best = candidate

    if best is None:
        raise RuntimeError("Joint search produced no feasible candidate.")

    validate_routes(
        prepared.instance,
        best.allocation,
        best.route_plan.routes,
    )

    return best


def improve_allocation_same_region(
    prepared: PreparedInstance,
    incumbent: CandidateSolution,
    *,
    max_iterations: int = 15,
    step_sizes: tuple[int, ...] = (1, 2, 5),
    route_time_limit_s: int = 1,
    total_time_limit_s: float = 25.0,
) -> CandidateSolution:
    """
    Stage 6 local allocation search.

    Move quantity between two customers in the same region.
    Regional delivered totals remain unchanged, so every regional service
    ratio remains unchanged; only routeability can improve.

    Screened by geographic distance proxy and stop-elimination potential,
    bounded by total_time_limit_s for reproducible, fast execution.
    """
    import time
    start_time = time.perf_counter()

    instance = prepared.instance
    best = incumbent
    customers = instance.customers
    depot = instance.depot

    for _ in range(max_iterations):
        if time.perf_counter() - start_time >= total_time_limit_s:
            break

        improved_this_round = False

        # Collect candidate moves across donors and receivers in same region
        candidate_moves = []
        for donor in customers:
            if best.allocation[donor] <= 0:
                continue
            d_donor_depot = float(instance.edge_weight[depot, donor])

            for receiver in customers:
                if donor == receiver:
                    continue
                if prepared.regions[donor] != prepared.regions[receiver]:
                    continue
                if best.allocation[receiver] >= instance.demand[receiver]:
                    continue

                d_recv_depot = float(instance.edge_weight[depot, receiver])
                available = int(best.allocation[donor])
                room = int(instance.demand[receiver] - best.allocation[receiver])
                max_transfer = min(available, room)
                if max_transfer <= 0:
                    continue

                # Consider step sizes plus full remaining transfer (which eliminates a customer stop)
                amounts = [s for s in step_sizes if 0 < s <= max_transfer]
                if available <= max_transfer and available not in amounts:
                    amounts.append(available)

                for delta in amounts:
                    # Heuristic proxy benefit: distance savings plus bonus if stop is completely removed
                    eliminates_stop = (best.allocation[donor] == delta)
                    proxy_saving = (d_donor_depot - d_recv_depot) + (50.0 if eliminates_stop else 0.0)

                    # Only test moves that have positive or neutral proxy potential
                    if proxy_saving >= -1e-6:
                        candidate_moves.append((proxy_saving, donor, receiver, delta))

        # Sort candidate moves by highest potential benefit
        candidate_moves.sort(key=lambda m: m[0], reverse=True)

        # Evaluate the top promising candidate moves
        for _, donor, receiver, delta in candidate_moves[:12]:
            if time.perf_counter() - start_time >= total_time_limit_s:
                break

            q = best.allocation.copy()
            q[donor] -= delta
            q[receiver] += delta

            try:
                validate_allocation(instance, q)
                route = solve_cvrp(
                    instance,
                    q,
                    first_solution="PARALLEL_CHEAPEST_INSERTION",
                    metaheuristic="GUIDED_LOCAL_SEARCH",
                    time_limit_s=route_time_limit_s,
                )
                route = improve_routes_2opt(instance, q, route)
                metrics = calculate_metrics(prepared, q, route)
                candidate = CandidateSolution(q, route, metrics)
            except (ValueError, RuntimeError):
                continue

            if lexicographically_better(candidate, best):
                best = candidate
                improved_this_round = True
                break

        if not improved_this_round:
            break

    return best
