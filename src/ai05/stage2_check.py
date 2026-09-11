from __future__ import annotations

import sys

from .distance import validate_distance_matrix
from .loader import load_instance
from .regions import prepare_regions


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m ai05.stage2_check data/A-n32-k5.vrp"
        )

    instance = load_instance(sys.argv[1])
    validate_distance_matrix(instance)
    prepared = prepare_regions(instance)

    print(f"Instance: {instance.name}")
    print(f"Dimension: {instance.dimension}")
    print(f"Customers: {len(instance.customers)}")
    print(f"Depot: {instance.depot}")
    print(f"Vehicles: {instance.vehicles}")
    print(f"Capacity: {instance.capacity}")
    print(f"Edge weight type: {instance.edge_weight_type}")
    print(f"Edge weight format: {instance.edge_weight_format}")
    print(f"Total demand: {instance.total_demand}")
    print(f"Available stock S: {instance.stock}")

    print("\nRegional demand:")
    for region, value in prepared.regional_demand.items():
        print(f"  {region.name:12s}: {value}")


if __name__ == "__main__":
    main()
