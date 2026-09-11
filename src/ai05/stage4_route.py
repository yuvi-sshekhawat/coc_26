from __future__ import annotations

import sys
import numpy as np

from .allocation import solve_max_min_allocation
from .loader import load_instance
from .regions import prepare_regions
from .routing import improve_routes_2opt, solve_cvrp
from .metrics import calculate_metrics
from .constraints import validate_routes


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m ai05.stage4_route data/A-n32-k5.vrp"
        )

    instance = load_instance(sys.argv[1])
    prepared = prepare_regions(instance)
    alloc = solve_max_min_allocation(prepared)

    route = solve_cvrp(instance, alloc.allocation)
    route = improve_routes_2opt(instance, alloc.allocation, route)
    validate_routes(instance, alloc.allocation, route.routes)

    metrics = calculate_metrics(prepared, alloc.allocation, route)

    print(f"Instance: {instance.name}")
    print(f"Min service: {metrics.minimum_service_ratio:.6f}")
    print(f"Balance: {metrics.balance:.6f}")
    print(f"Distance: {metrics.total_distance}")
    print("\nRoutes:")
    for k, (r, load, dist) in enumerate(
        zip(route.routes, route.loads, route.route_distances), start=1
    ):
        print(f"Vehicle {k}: {r} | load={load} | distance={dist}")


if __name__ == "__main__":
    main()
