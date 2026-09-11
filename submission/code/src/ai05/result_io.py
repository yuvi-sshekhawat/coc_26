from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from .metrics import SolutionMetrics
from .routing import RoutePlan


def save_solution(
    out_dir: str | Path,
    *,
    instance_name: str,
    allocation: Sequence[int],
    route_plan: RoutePlan,
    metrics: SolutionMetrics,
    seed: int,
    solver_config: dict,
    validation_valid: bool,
) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    routes_payload = {
        "instance": instance_name,
        "routes": [
            {
                "vehicle": idx + 1,
                "nodes": list(route),
                "load": int(load),
                "distance": int(distance),
            }
            for idx, (route, load, distance)
            in enumerate(
                zip(
                    route_plan.routes,
                    route_plan.loads,
                    route_plan.route_distances,
                )
            )
        ],
    }

    metrics_payload = {
        "instance": instance_name,
        "minimum_service_ratio": metrics.minimum_service_ratio,
        "maximum_service_ratio": metrics.maximum_service_ratio,
        "balance": metrics.balance,
        "total_distance": metrics.total_distance,
        "total_allocated": metrics.total_allocated,
        "fairness_upper_bound": metrics.fairness_upper_bound,
        "fairness_gap": metrics.fairness_gap,
        "regional_original": {
            k.name: int(v) for k, v in metrics.regional_original.items()
        },
        "regional_delivered": {
            k.name: int(v) for k, v in metrics.regional_delivered.items()
        },
        "regional_service": {
            k.name: float(v) for k, v in metrics.regional_service.items()
        },
        "validation_valid": bool(validation_valid),
        "seed": int(seed),
        "solver_config": solver_config,
    }

    allocation_payload = {
        "instance": instance_name,
        "allocation": [int(v) for v in allocation],
    }

    summary_payload = {
        "instance": instance_name,
        "minimum_service_ratio": metrics.minimum_service_ratio,
        "maximum_service_ratio": metrics.maximum_service_ratio,
        "balance": metrics.balance,
        "total_distance": metrics.total_distance,
        "total_allocated": metrics.total_allocated,
        "fairness_upper_bound": metrics.fairness_upper_bound,
        "fairness_gap": metrics.fairness_gap,
        "validation_valid": bool(validation_valid),
        "seed": int(seed),
        "solver_config": solver_config,
    }

    (out / "metrics.json").write_text(
        json.dumps(metrics_payload, indent=2),
        encoding="utf-8",
    )
    (out / "summary.json").write_text(
        json.dumps(summary_payload, indent=2),
        encoding="utf-8",
    )
    (out / "routes.json").write_text(
        json.dumps(routes_payload, indent=2),
        encoding="utf-8",
    )
    (out / "allocation.json").write_text(
        json.dumps(allocation_payload, indent=2),
        encoding="utf-8",
    )

    lines = []
    for item in routes_payload["routes"]:
        lines.append(
            f"Vehicle {item['vehicle']}: "
            f"{' -> '.join(map(str, item['nodes']))} | "
            f"load={item['load']} | distance={item['distance']}"
        )
    (out / "routes.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
