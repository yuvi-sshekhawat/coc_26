from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai05.baselines import (
    solve_nearest_first,
    solve_proportional,
    solve_fair_greedy,
)
from ai05.loader import REQUIRED_INSTANCES, load_instance
from ai05.metrics import calculate_metrics
from ai05.optimization import improve_allocation_same_region, solve_joint_search
from ai05.regions import prepare_regions
from ai05.result_io import save_solution
from ai05.routing import improve_routes_2opt
from ai05.validation import validate_all


def run_instance(
    instance_path: Path,
    output_root: Path,
    seed: int,
    candidate_count: int,
    route_seconds: int,
) -> dict:
    start = time.perf_counter()

    instance = load_instance(instance_path)
    prepared = prepare_regions(instance)
    out_dir = output_root / instance.name
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 60}")
    print(f"RUNNING INSTANCE: {instance.name}")
    print(f"{'=' * 60}")

    # Run Baselines for benchmarking comparison
    print("Evaluating Baseline 1: nearest-first...")
    b1 = solve_nearest_first(prepared, route_time_limit_s=max(1, route_seconds), seed=seed)
    print("Evaluating Baseline 2: proportional allocation...")
    b2 = solve_proportional(prepared, route_time_limit_s=max(1, route_seconds), seed=seed)
    print("Evaluating Baseline 3: fair greedy...")
    b3 = solve_fair_greedy(prepared, route_time_limit_s=max(1, route_seconds), seed=seed)

    # Run Final Joint Optimizer
    print(f"Running Final Joint Optimizer (candidates={candidate_count}, route_seconds={route_seconds})...")
    result = solve_joint_search(
        prepared,
        allocation_candidates=candidate_count,
        route_time_limit_s=route_seconds,
        allocation_time_limit_ms=10_000,
        seed=seed,
    )

    improved = improve_allocation_same_region(
        prepared,
        result,
        max_iterations=30,
        route_time_limit_s=max(1, route_seconds // 2),
    )

    # Final 2-opt pass is deterministic and allocation-preserving.
    improved_route = improve_routes_2opt(
        instance,
        improved.allocation,
        improved.route_plan,
    )

    final_metrics = calculate_metrics(
        prepared,
        improved.allocation,
        improved_route,
    )

    # Validate candidate with authoritative validator
    validation_report = validate_all(
        prepared,
        improved.allocation,
        improved_route.routes,
        improved_route,
        final_metrics,
    )

    if not validation_report.valid:
        raise ValueError(
            f"Authoritative validation failed for {instance.name}: {validation_report.errors}"
        )

    solver_config = {
        "candidate_count": candidate_count,
        "route_seconds_per_candidate": route_seconds,
        "allocation_time_limit_ms": 10_000,
        "local_search_iterations": 30,
        "seed": seed,
    }

    save_solution(
        out_dir,
        instance_name=instance.name,
        allocation=improved.allocation,
        route_plan=improved_route,
        metrics=final_metrics,
        seed=seed,
        solver_config=solver_config,
        validation_valid=True,
    )

    # Baselines summary table
    baselines_data = [
        {
            "method": "nearest-first",
            "min_service": round(b1.metrics.minimum_service_ratio, 6),
            "balance": round(b1.metrics.balance, 6),
            "distance": int(b1.metrics.total_distance),
        },
        {
            "method": "proportional",
            "min_service": round(b2.metrics.minimum_service_ratio, 6),
            "balance": round(b2.metrics.balance, 6),
            "distance": int(b2.metrics.total_distance),
        },
        {
            "method": "fair-greedy",
            "min_service": round(b3.metrics.minimum_service_ratio, 6),
            "balance": round(b3.metrics.balance, 6),
            "distance": int(b3.metrics.total_distance),
        },
        {
            "method": "final_joint_optimizer",
            "min_service": round(final_metrics.minimum_service_ratio, 6),
            "balance": round(final_metrics.balance, 6),
            "distance": int(final_metrics.total_distance),
        },
    ]

    (out_dir / "baselines.json").write_text(
        json.dumps(baselines_data, indent=2),
        encoding="utf-8",
    )

    print("\nBENCHMARK COMPARISON TABLE:")
    print(f"{'method':<25} | {'min service':<12} | {'balance':<10} | {'distance':<10}")
    print("-" * 65)
    for row in baselines_data:
        print(f"{row['method']:<25} | {row['min_service']:<12.4f} | {row['balance']:<10.4f} | {row['distance']:<10}")

    plots = {
        "route_map": out_dir / "routes.png",
        "regional_service": out_dir / "regional_service.png",
        "allocation_map": out_dir / "allocation.png",
    }

    from ai05.visualization import (
        plot_allocation_map,
        plot_regional_service,
        plot_routes,
    )

    plot_routes(
        instance,
        improved_route,
        improved.allocation,
        plots["route_map"],
    )
    plot_regional_service(
        prepared,
        final_metrics.regional_service,
        plots["regional_service"],
    )
    plot_allocation_map(
        instance,
        improved.allocation,
        plots["allocation_map"],
    )

    elapsed = time.perf_counter() - start

    summary = {
        "instance": instance.name,
        "runtime_seconds": elapsed,
        "minimum_service_ratio": final_metrics.minimum_service_ratio,
        "maximum_service_ratio": final_metrics.maximum_service_ratio,
        "balance": final_metrics.balance,
        "total_distance": final_metrics.total_distance,
        "total_allocated": final_metrics.total_allocated,
        "fairness_upper_bound": final_metrics.fairness_upper_bound,
        "fairness_gap": final_metrics.fairness_gap,
        "validation_valid": True,
        "baselines": baselines_data,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "results",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--candidates", type=int, default=30)
    parser.add_argument("--route-seconds", type=int, default=3)
    args = parser.parse_args()

    missing = []
    summaries = []

    for name in REQUIRED_INSTANCES:
        path_candidates = [
            args.data_dir / f"{name}.vrp",
            args.data_dir / name,
        ]
        path = next((p for p in path_candidates if p.exists()), None)

        if path is None:
            missing.append(name)
            continue

        try:
            summaries.append(
                run_instance(
                    path,
                    args.output_dir,
                    args.seed,
                    args.candidates,
                    args.route_seconds,
                )
            )
        except Exception as exc:
            summaries.append({
                "instance": name,
                "status": "FAILED",
                "error": str(exc),
            })

    manifest = {
        "seed": args.seed,
        "candidate_count": args.candidates,
        "route_seconds": args.route_seconds,
        "required_instances": list(REQUIRED_INSTANCES),
        "missing_instance_files": missing,
        "summaries": summaries,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "benchmark_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    if missing:
        print(
            "Missing official instance files: "
            + ", ".join(missing)
            + ". Put them in data/ and re-run."
        )
        return 2

    failed = [s for s in summaries if s.get("status") == "FAILED"]
    if failed:
        print("One or more instances failed:")
        for item in failed:
            print(item)
        return 1

    print("\nBenchmark completed successfully!")
    print(json.dumps(summaries, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
