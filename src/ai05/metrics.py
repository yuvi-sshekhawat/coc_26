from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .models import InstanceData, PreparedInstance, Region
from .routing import RoutePlan


@dataclass(frozen=True)
class SolutionMetrics:
    total_distance: int
    minimum_service_ratio: float
    maximum_service_ratio: float
    balance: float
    total_allocated: int
    fairness_upper_bound: float
    fairness_gap: float
    regional_original: dict[Region, int]
    regional_delivered: dict[Region, int]
    regional_service: dict[Region, float]


def calculate_metrics(
    prepared: PreparedInstance,
    allocation: np.ndarray,
    route_plan: RoutePlan,
) -> SolutionMetrics:
    instance = prepared.instance

    total_allocated = int(sum(allocation[i] for i in instance.customers))

    regional_original = {
        region: int(prepared.regional_demand[region])
        for region in Region
    }

    regional_delivered = {
        region: int(
            sum(
                allocation[i]
                for i in instance.customers
                if prepared.regions[i] == region
            )
        )
        for region in Region
    }

    regional_service = {
        region: (
            regional_delivered[region] / regional_original[region]
            if regional_original[region] > 0
            else 1.0
        )
        for region in Region
    }

    minimum_service = min(regional_service.values())
    maximum_service = max(regional_service.values())
    balance = 1.0 - (maximum_service - minimum_service)

    upper_bound = (
        instance.stock / instance.total_demand
        if instance.total_demand
        else 1.0
    )

    return SolutionMetrics(
        total_distance=int(route_plan.total_distance),
        minimum_service_ratio=float(minimum_service),
        maximum_service_ratio=float(maximum_service),
        balance=float(balance),
        total_allocated=total_allocated,
        fairness_upper_bound=float(upper_bound),
        fairness_gap=float(upper_bound - minimum_service),
        regional_original=regional_original,
        regional_delivered=regional_delivered,
        regional_service=regional_service,
    )
