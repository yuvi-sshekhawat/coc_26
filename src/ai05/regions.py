from __future__ import annotations

from collections import defaultdict

from .models import InstanceData, PreparedInstance, Region


def classify_region(instance: InstanceData, node: int) -> Region:
    """
    Classify a customer relative to the depot.

    Axis rule from the problem:
      x == depot_x -> positive/right
      y == depot_y -> positive/up
    """
    depot_x, depot_y = instance.node_coord[instance.depot]
    x, y = instance.node_coord[node]

    x_rel = x - depot_x
    y_rel = y - depot_y

    if x_rel >= 0 and y_rel >= 0:
        return Region.RIGHT_UP
    if x_rel < 0 and y_rel >= 0:
        return Region.LEFT_UP
    if x_rel < 0 and y_rel < 0:
        return Region.LEFT_DOWN
    return Region.RIGHT_DOWN


def prepare_regions(instance: InstanceData) -> PreparedInstance:
    regions: dict[int, Region] = {}
    regional_demand: dict[Region, int] = defaultdict(int)

    for node in instance.customers:
        region = classify_region(instance, node)
        regions[node] = region
        regional_demand[region] += int(instance.demand[node])

    for region in Region:
        regional_demand.setdefault(region, 0)

    if set(regions) != set(instance.customers):
        raise ValueError("Every customer must belong to exactly one region.")

    if sum(regional_demand.values()) != instance.total_demand:
        raise ValueError("Regional demand does not equal total demand.")

    return PreparedInstance(
        instance=instance,
        regions=regions,
        regional_demand=dict(regional_demand),
    )
