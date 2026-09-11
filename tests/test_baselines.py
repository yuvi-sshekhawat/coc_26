import numpy as np
import pytest

from ai05.baselines import (
    solve_nearest_first,
    solve_proportional,
    solve_fair_greedy,
    run_all_baselines_and_final,
)
from ai05.models import InstanceData
from ai05.regions import prepare_regions
from ai05.validation import validate_all


def synthetic_instance():
    coords = np.array([
        [0.0, 0.0],
        [10.0, 10.0],
        [-10.0, 10.0],
        [-10.0, -10.0],
        [10.0, -10.0],
        [8.0, 12.0],
        [-12.0, 8.0],
    ], dtype=float)

    demand = np.array([0, 10, 12, 11, 9, 8, 7])
    diff = coords[:, None, :] - coords[None, :, :]
    dist = np.rint(np.sqrt(np.sum(diff * diff, axis=2))).astype(float)
    np.fill_diagonal(dist, 0)

    return InstanceData(
        name="A-n32-k5",
        node_coord=coords,
        demand=demand,
        depot=0,
        vehicles=3,
        capacity=50,
        edge_weight_type="EUC_2D",
        edge_weight=dist,
    )


def test_baselines_execution_and_validity():
    inst = synthetic_instance()
    prep = prepare_regions(inst)

    # Test Baseline 1
    b1 = solve_nearest_first(prep, route_time_limit_s=1, seed=42)
    rep1 = validate_all(prep, b1.allocation, b1.route_plan.routes, b1.route_plan, b1.metrics)
    assert rep1.valid

    # Test Baseline 2
    b2 = solve_proportional(prep, route_time_limit_s=1, seed=42)
    rep2 = validate_all(prep, b2.allocation, b2.route_plan.routes, b2.route_plan, b2.metrics)
    assert rep2.valid

    # Test Baseline 3
    b3 = solve_fair_greedy(prep, route_time_limit_s=1, seed=42)
    rep3 = validate_all(prep, b3.allocation, b3.route_plan.routes, b3.route_plan, b3.metrics)
    assert rep3.valid

    # Check that final joint optimizer produces a valid solution with high fairness
    all_res = run_all_baselines_and_final(prep, route_time_limit_s=1, candidate_count=4, seed=42)
    assert "final_joint_optimizer" in all_res
    final_sol = all_res["final_joint_optimizer"]
    rep_final = validate_all(prep, final_sol.allocation, final_sol.route_plan.routes, final_sol.route_plan, final_sol.metrics)
    assert rep_final.valid
