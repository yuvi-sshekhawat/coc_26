from __future__ import annotations

import sys

from .loader import load_instance
from .regions import prepare_regions
from .optimization import solve_joint_search


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m ai05.stage5_joint data/A-n32-k5.vrp"
        )

    instance = load_instance(sys.argv[1])
    prepared = prepare_regions(instance)

    result = solve_joint_search(
        prepared,
        allocation_candidates=20,
        route_time_limit_s=3,
        seed=42,
    )

    m = result.metrics
    print(f"Instance: {instance.name}")
    print(f"Minimum regional service: {m.minimum_service_ratio:.6f}")
    print(f"Balance: {m.balance:.6f}")
    print(f"Distance: {m.total_distance}")
    print(f"Total allocated: {m.total_allocated}")
    print(f"Fairness upper bound: {m.fairness_upper_bound:.6f}")
    print(f"Fairness gap: {m.fairness_gap:.6f}")

    for k, (route, load, dist) in enumerate(
        zip(
            result.route_plan.routes,
            result.route_plan.loads,
            result.route_plan.route_distances,
        ),
        start=1,
    ):
        print(f"Vehicle {k}: {route} | load={load} | distance={dist}")


if __name__ == "__main__":
    main()
