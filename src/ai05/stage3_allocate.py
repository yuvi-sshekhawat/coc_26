from __future__ import annotations

import sys

from .allocation import solve_max_min_allocation
from .loader import load_instance
from .regions import prepare_regions


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m ai05.stage3_allocate data/A-n32-k5.vrp"
        )

    instance = load_instance(sys.argv[1])
    prepared = prepare_regions(instance)
    result = solve_max_min_allocation(prepared)

    print(f"Instance: {instance.name}")
    print(f"Total demand: {instance.total_demand}")
    print(f"Available stock: {instance.stock}")
    print(
        "Theoretical min-service upper bound: "
        f"{result.upper_bound:.6f}"
    )
    print(
        "Achieved min-service ratio: "
        f"{result.minimum_service_ratio:.6f}"
    )
    print(
        "Fairness gap to upper bound: "
        f"{result.upper_bound - result.minimum_service_ratio:.6f}"
    )

    print("\nRegional service:")
    for region, ratio in result.regional_service_ratio.items():
        print(
            f"  {region.name:12s} "
            f"original={prepared.regional_demand[region]:4d} "
            f"delivered={result.regional_delivered[region]:4d} "
            f"service={ratio:.6f}"
        )

    print("\nAllocation q_i:")
    for node in instance.customers:
        print(
            f"  node {node:2d}: "
            f"demand={instance.demand[node]:3d}, "
            f"q={result.allocation[node]:3d}"
        )


if __name__ == "__main__":
    main()
