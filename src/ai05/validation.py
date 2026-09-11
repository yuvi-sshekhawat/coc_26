from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .distance import validate_distance_matrix
from .models import InstanceData, PreparedInstance, Region
from .regions import classify_region


EPS = 1e-9


class ConstraintViolation(ValueError):
    """Raised when an authoritative project constraint is violated."""


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    errors: tuple[str, ...]
    allocation_bounds_ok: bool
    stock_ok: bool
    regional_coverage_ok: bool
    depot_start_end_ok: bool
    vehicle_capacity_ok: bool
    route_coverage_ok: bool
    customer_uniqueness_ok: bool
    metrics_ok: bool


def validate_allocation(
    instance: InstanceData,
    allocation: Sequence[int | float],
) -> None:
    """Authoritative allocation validation."""
    q = np.asarray(allocation, dtype=float)

    if q.shape != instance.demand.shape:
        raise ConstraintViolation(
            f"Allocation shape {q.shape} does not match demand shape {instance.demand.shape}."
        )

    customer_q = q[instance.customers]
    customer_d = instance.demand[instance.customers]

    if np.any(customer_q < -EPS):
        raise ConstraintViolation("Allocation contains q_i < 0.")

    if np.any(customer_q - customer_d > EPS):
        raise ConstraintViolation("Allocation contains q_i > d_i.")

    allocated = float(np.sum(customer_q))
    if allocated > instance.stock + EPS:
        raise ConstraintViolation(
            f"Allocated supply {allocated} exceeds stock {instance.stock}."
        )

    if abs(float(q[instance.depot])) > EPS:
        raise ConstraintViolation("Depot allocation must be zero.")

    if np.any(np.abs(customer_q - np.round(customer_q)) > EPS):
        raise ConstraintViolation("Allocation q_i must be integer-valued.")


def validate_regions(
    instance: InstanceData,
    regions: dict[int, Region],
) -> None:
    """Authoritative regional assignment and axis rule validation."""
    customers_set = set(instance.customers)
    if set(regions.keys()) != customers_set:
        raise ConstraintViolation(
            "Every customer must be assigned to exactly one region. "
            f"Expected {len(customers_set)} customers, got {len(regions)}."
        )

    for node in instance.customers:
        expected_region = classify_region(instance, node)
        if regions[node] != expected_region:
            raise ConstraintViolation(
                f"Customer {node} assigned to {regions[node]}, expected {expected_region} "
                "under the official depot axis rule."
            )


def validate_routes(
    instance: InstanceData,
    allocation: Sequence[int | float],
    routes: Sequence[Sequence[int]],
) -> None:
    """Authoritative CVRP route plan validation."""
    q = np.asarray(allocation, dtype=float)
    validate_allocation(instance, q)

    expected_customers = {i for i in instance.customers if q[i] > EPS}
    unallocated_customers = {i for i in instance.customers if q[i] <= EPS}

    seen: list[int] = []

    for route_idx, route in enumerate(routes):
        if not route:
            continue

        if len(route) < 2:
            raise ConstraintViolation(
                f"Route {route_idx + 1} has fewer than 2 stops: {route}."
            )

        if route[0] != instance.depot or route[-1] != instance.depot:
            raise ConstraintViolation(
                f"Route {route_idx + 1} must start and end at official depot {instance.depot}."
            )

        customers = list(route[1:-1])
        seen.extend(customers)

        load = 0
        for node in customers:
            if node == instance.depot:
                raise ConstraintViolation(
                    f"Route {route_idx + 1} has depot {instance.depot} as an internal stop."
                )
            if node not in instance.customers:
                raise ConstraintViolation(
                    f"Route {route_idx + 1} contains unknown customer node {node}."
                )
            if node in unallocated_customers:
                raise ConstraintViolation(
                    f"Route {route_idx + 1} serves customer {node} with zero allocation (q_{node}=0)."
                )
            load += int(round(q[node]))

        if load > instance.capacity:
            raise ConstraintViolation(
                f"Route {route_idx + 1} load {load} exceeds vehicle capacity {instance.capacity}."
            )

    seen_set = set(seen)
    if len(seen) != len(seen_set):
        raise ConstraintViolation(
            "A customer is visited more than once across routes."
        )

    if seen_set != expected_customers:
        missing = sorted(expected_customers - seen_set)
        extra = sorted(seen_set - expected_customers)
        raise ConstraintViolation(
            f"Route coverage mismatch. Missing customers: {missing}, Extra customers: {extra}."
        )


def validate_metrics(
    prepared: PreparedInstance,
    allocation: Sequence[int | float],
    route_plan: any,
    metrics: any,
) -> None:
    """Authoritative metrics and score calculation validation."""
    instance = prepared.instance
    q = np.asarray(allocation, dtype=float)

    for r in Region:
        expected_orig = sum(
            int(instance.demand[i])
            for i in instance.customers
            if prepared.regions[i] == r
        )
        if metrics.regional_original[r] != expected_orig:
            raise ConstraintViolation(
                f"Regional original demand mismatch for {r.name}: "
                f"expected {expected_orig}, got {metrics.regional_original[r]}."
            )

        expected_deliv = sum(
            int(round(q[i]))
            for i in instance.customers
            if prepared.regions[i] == r
        )
        if metrics.regional_delivered[r] != expected_deliv:
            raise ConstraintViolation(
                f"Regional delivered demand mismatch for {r.name}: "
                f"expected {expected_deliv}, got {metrics.regional_delivered[r]}."
            )

        expected_ratio = (
            expected_deliv / expected_orig if expected_orig > 0 else 1.0
        )
        if abs(metrics.regional_service[r] - expected_ratio) > EPS:
            raise ConstraintViolation(
                f"Regional service ratio mismatch for {r.name}: "
                f"expected {expected_ratio:.6f}, got {metrics.regional_service[r]:.6f}."
            )

    expected_min_s = min(metrics.regional_service.values())
    expected_max_s = max(metrics.regional_service.values())
    expected_balance = 1.0 - (expected_max_s - expected_min_s)

    if abs(metrics.minimum_service_ratio - expected_min_s) > EPS:
        raise ConstraintViolation(
            f"Minimum service ratio mismatch: expected {expected_min_s:.6f}, "
            f"got {metrics.minimum_service_ratio:.6f}."
        )

    if abs(metrics.balance - expected_balance) > EPS:
        raise ConstraintViolation(
            f"Balance mismatch: expected {expected_balance:.6f}, got {metrics.balance:.6f}."
        )

    # Validate route distance using official edge-weight matrix
    D = instance.edge_weight
    computed_total_distance = 0
    for r_idx, route in enumerate(route_plan.routes):
        r_dist = 0
        for u, v in zip(route[:-1], route[1:]):
            r_dist += int(round(D[u, v]))
        if abs(r_dist - route_plan.route_distances[r_idx]) > EPS:
            raise ConstraintViolation(
                f"Route {r_idx + 1} distance mismatch: expected {r_dist}, "
                f"got {route_plan.route_distances[r_idx]}."
            )
        computed_total_distance += r_dist

    if abs(computed_total_distance - metrics.total_distance) > EPS:
        raise ConstraintViolation(
            f"Total route distance mismatch: expected {computed_total_distance}, "
            f"got {metrics.total_distance}."
        )


def validate_all(
    prepared: PreparedInstance,
    allocation: Sequence[int | float],
    routes: Sequence[Sequence[int]],
    route_plan: any = None,
    metrics: any = None,
) -> ValidationReport:
    """Run all validation checks and return a structured report."""
    instance = prepared.instance
    errors: list[str] = []

    alloc_ok = True
    stock_ok = True
    try:
        validate_allocation(instance, allocation)
    except ConstraintViolation as e:
        msg = str(e)
        errors.append(msg)
        if "exceeds stock" in msg:
            stock_ok = False
        else:
            alloc_ok = False

    reg_ok = True
    try:
        validate_regions(instance, prepared.regions)
    except ConstraintViolation as e:
        reg_ok = False
        errors.append(str(e))

    depot_ok = True
    cap_ok = True
    cov_ok = True
    uniq_ok = True
    try:
        validate_routes(instance, allocation, routes)
    except ConstraintViolation as e:
        msg = str(e)
        errors.append(msg)
        if "start and end at official depot" in msg or "internal stop" in msg:
            depot_ok = False
        elif "exceeds vehicle capacity" in msg:
            cap_ok = False
        elif "visited more than once" in msg:
            uniq_ok = False
        else:
            cov_ok = False

    metrics_ok = True
    if route_plan is not None and metrics is not None:
        try:
            validate_metrics(prepared, allocation, route_plan, metrics)
        except ConstraintViolation as e:
            metrics_ok = False
            errors.append(str(e))

    return ValidationReport(
        valid=len(errors) == 0,
        errors=tuple(errors),
        allocation_bounds_ok=alloc_ok,
        stock_ok=stock_ok,
        regional_coverage_ok=reg_ok,
        depot_start_end_ok=depot_ok,
        vehicle_capacity_ok=cap_ok,
        route_coverage_ok=cov_ok,
        customer_uniqueness_ok=uniq_ok,
        metrics_ok=metrics_ok,
    )
