from __future__ import annotations

import sys

from .loader import load_instance
from .regions import prepare_regions
from .optimization import solve_joint_search, improve_allocation_same_region


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m ai05.stage6_improve data/A-n32-k5.vrp"
        )

    instance = load_instance(sys.argv[1])
    prepared = prepare_regions(instance)

    baseline = solve_joint_search(
        prepared,
        allocation_candidates=20,
        route_time_limit_s=3,
        seed=42,
    )

    improved = improve_allocation_same_region(
        prepared,
        baseline,
        max_iterations=15,
        route_time_limit_s=2,
    )

    print(f"Instance: {instance.name}")
    print("BASELINE")
    print(f"  min service = {baseline.metrics.minimum_service_ratio:.6f}")
    print(f"  balance     = {baseline.metrics.balance:.6f}")
    print(f"  distance    = {baseline.metrics.total_distance}")

    print("IMPROVED")
    print(f"  min service = {improved.metrics.minimum_service_ratio:.6f}")
    print(f"  balance     = {improved.metrics.balance:.6f}")
    print(f"  distance    = {improved.metrics.total_distance}")

    if improved.metrics.total_distance <= baseline.metrics.total_distance:
        print("Status: local search kept or improved the route distance.")
    else:
        print("Status: baseline should be retained by lexicographic selection.")


if __name__ == "__main__":
    main()
