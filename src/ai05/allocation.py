from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from ortools.linear_solver import pywraplp

from .constraints import validate_allocation
from .models import InstanceData, PreparedInstance, Region


@dataclass(frozen=True)
class AllocationResult:
    allocation: np.ndarray
    minimum_service_ratio: float
    upper_bound: float
    regional_delivered: dict[Region, int]
    regional_service_ratio: dict[Region, float]


def solve_max_min_allocation(
    prepared: PreparedInstance,
    *,
    time_limit_ms: int = 10_000,
) -> AllocationResult:
    """
    Stage 3 exact max-min allocation.

    q_i = integer delivered quantity
    t   = minimum regional service ratio

    maximize t

    s.t.
      0 <= q_i <= d_i
      sum q_i <= S
      delivered_r >= t * original_demand_r
    """
    instance = prepared.instance

    solver = pywraplp.Solver.CreateSolver("CBC")
    if solver is None:
        raise RuntimeError("OR-Tools CBC solver is unavailable.")

    solver.SetTimeLimit(time_limit_ms)

    customers = instance.customers

    q = {
        i: solver.IntVar(
            0,
            int(instance.demand[i]),
            f"q_{i}",
        )
        for i in customers
    }
    t = solver.NumVar(0.0, 1.0, "t")

    solver.Add(sum(q[i] for i in customers) <= instance.stock)

    for region in Region:
        region_nodes = [
            i for i in customers
            if prepared.regions[i] == region
        ]
        region_demand = prepared.regional_demand[region]

        if region_demand == 0:
            # A zero-demand region is defined to have service ratio 1.0
            # for reporting, but it imposes no allocation requirement.
            continue

        solver.Add(
            sum(q[i] for i in region_nodes) >= region_demand * t
        )

    solver.Maximize(t)

    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        raise RuntimeError(f"Allocation solver failed. status={status}")

    allocation = np.zeros(instance.dimension, dtype=int)
    for i in customers:
        allocation[i] = int(round(q[i].solution_value()))

    validate_allocation(instance, allocation)

    regional_delivered = {
        region: int(
            sum(
                allocation[i]
                for i in customers
                if prepared.regions[i] == region
            )
        )
        for region in Region
    }

    service = {}
    for region in Region:
        demand = prepared.regional_demand[region]
        service[region] = (
            regional_delivered[region] / demand
            if demand > 0
            else 1.0
        )

    achieved_min = min(service.values()) if service else 1.0
    upper_bound = (
        instance.stock / instance.total_demand
        if instance.total_demand
        else 1.0
    )

    return AllocationResult(
        allocation=allocation,
        minimum_service_ratio=achieved_min,
        upper_bound=upper_bound,
        regional_delivered=regional_delivered,
        regional_service_ratio=service,
    )
