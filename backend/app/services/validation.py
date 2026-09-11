from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


EPS = 1e-9


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]


def validate_allocation(
    demand: Sequence[int],
    depot: int,
    stock: int,
    allocation: Sequence[int],
) -> ValidationResult:
    errors: list[str] = []

    if len(demand) != len(allocation):
        errors.append("Allocation length does not match demand length.")
        return ValidationResult(False, tuple(errors))

    q = np.asarray(allocation, dtype=float)
    d = np.asarray(demand, dtype=float)

    if abs(q[depot]) > EPS:
        errors.append("Depot allocation must be zero.")

    if np.any(q < -EPS):
        errors.append("Found q_i < 0.")

    customers = [i for i in range(len(demand)) if i != depot]
    if np.any(q[customers] - d[customers] > EPS):
        errors.append("Found q_i > d_i.")

    if float(np.sum(q[customers])) > stock + EPS:
        errors.append("Total allocated quantity exceeds stock.")

    if np.any(np.abs(q[customers] - np.rint(q[customers])) > EPS):
        errors.append("Allocation contains non-integer quantities.")

    return ValidationResult(not errors, tuple(errors))


def validate_routes(
    depot: int,
    allocation: Sequence[int],
    routes: Sequence[Sequence[int]],
    capacity: int,
) -> ValidationResult:
    errors: list[str] = []
    q = np.asarray(allocation, dtype=float)

    seen: list[int] = []
    expected = {i for i, value in enumerate(q) if i != depot and value > EPS}

    for route_idx, route in enumerate(routes):
        if not route:
            continue

        if route[0] != depot or route[-1] != depot:
            errors.append(f"Route {route_idx + 1} does not start/end at depot.")

        customers = list(route[1:-1])
        seen.extend(customers)

        for node in customers:
            if node == depot:
                errors.append(
                    f"Route {route_idx + 1} has an internal depot node."
                )
            elif node < 0 or node >= len(q):
                errors.append(
                    f"Route {route_idx + 1} contains invalid node {node}."
                )

        load = sum(int(round(q[node])) for node in customers)
        if load > capacity:
            errors.append(
                f"Route {route_idx + 1} load {load} exceeds capacity {capacity}."
            )

    if len(seen) != len(set(seen)):
        errors.append("A customer is visited more than once.")

    if set(seen) != expected:
        missing = sorted(expected - set(seen))
        extra = sorted(set(seen) - expected)
        errors.append(
            f"Route coverage mismatch. missing={missing}, extra={extra}."
        )

    return ValidationResult(not errors, tuple(errors))


def validate_full_solution(
    *,
    demand: Sequence[int],
    depot: int,
    stock: int,
    allocation: Sequence[int],
    routes: Sequence[Sequence[int]],
    capacity: int,
) -> ValidationResult:
    a = validate_allocation(demand, depot, stock, allocation)
    if not a.valid:
        return a

    r = validate_routes(depot, allocation, routes, capacity)
    if not r.valid:
        return r

    return ValidationResult(True, ())
