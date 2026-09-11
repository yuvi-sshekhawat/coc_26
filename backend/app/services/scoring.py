from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


EPS = 1e-9


@dataclass(frozen=True)
class JudgeMetrics:
    minimum_service_ratio: float
    maximum_service_ratio: float
    balance: float
    total_distance: int
    total_allocated: int
    fairness_upper_bound: float
    fairness_gap: float

    @property
    def valid_metric_range(self) -> bool:
        return (
            -EPS <= self.minimum_service_ratio <= 1 + EPS
            and -EPS <= self.maximum_service_ratio <= 1 + EPS
            and -EPS <= self.balance <= 1 + EPS
        )


def lexicographic_key(metrics: JudgeMetrics) -> tuple[float, int, float]:
    """
    Mirrors the judging priority:
      1) higher minimum regional service
      2) lower total route distance
      3) higher Balance

    Python's tuple ordering cannot mix max/min directions directly,
    so selection code should use better_than().
    """
    return (
        metrics.minimum_service_ratio,
        metrics.total_distance,
        metrics.balance,
    )


def better_than(candidate: JudgeMetrics, incumbent: JudgeMetrics | None) -> bool:
    if incumbent is None:
        return True

    if candidate.minimum_service_ratio > incumbent.minimum_service_ratio + EPS:
        return True
    if abs(candidate.minimum_service_ratio - incumbent.minimum_service_ratio) > EPS:
        return False

    if candidate.total_distance < incumbent.total_distance:
        return True
    if candidate.total_distance > incumbent.total_distance:
        return False

    return candidate.balance > incumbent.balance + EPS


def regional_service(
    regional_original: Mapping[str, int],
    regional_delivered: Mapping[str, int],
) -> dict[str, float]:
    service: dict[str, float] = {}

    for region in ("RIGHT_UP", "LEFT_UP", "LEFT_DOWN", "RIGHT_DOWN"):
        original = int(regional_original.get(region, 0))
        delivered = int(regional_delivered.get(region, 0))
        service[region] = delivered / original if original else 1.0

    return service


def balance_from_service(service: Mapping[str, float]) -> float:
    values = list(service.values())
    if not values:
        return 1.0
    return 1.0 - (max(values) - min(values))
