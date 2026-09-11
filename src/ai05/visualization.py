from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .models import InstanceData, PreparedInstance, Region
from .routing import RoutePlan


def plot_routes(
    instance: InstanceData,
    route_plan: RoutePlan,
    allocation: Sequence[int],
    out_path: str | Path,
) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 8))

    colors = plt.cm.tab10(np.linspace(0, 1, max(1, instance.vehicles)))

    for vehicle_id, route in enumerate(route_plan.routes):
        if len(route) < 2:
            continue

        xy = instance.node_coord[route]
        ax.plot(
            xy[:, 0],
            xy[:, 1],
            marker="o",
            linewidth=2,
            color=colors[vehicle_id % len(colors)],
            label=f"Vehicle {vehicle_id + 1}",
        )

    depot_xy = instance.node_coord[instance.depot]
    ax.scatter(
        [depot_xy[0]],
        [depot_xy[1]],
        marker="*",
        s=260,
        color="black",
        zorder=5,
        label="Depot",
    )

    for node in instance.customers:
        x, y = instance.node_coord[node]
        if allocation[node] > 0:
            ax.annotate(
                f"{node}\nq={allocation[node]}",
                (x, y),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=8,
            )

    ax.axhline(depot_xy[1], linewidth=1, linestyle="--", color="gray")
    ax.axvline(depot_xy[0], linewidth=1, linestyle="--", color="gray")
    ax.set_title(f"{instance.name} — Final Vehicle Routes")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.grid(alpha=0.2)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_regional_service(
    prepared: PreparedInstance,
    regional_service: Mapping[Region, float],
    out_path: str | Path,
) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    labels = [r.name.replace("_", "\n") for r in Region]
    values = [float(regional_service.get(r, 0.0)) * 100 for r in Region]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(labels, values)
    ax.axhline(
        float(prepared.instance.stock / prepared.instance.total_demand) * 100,
        linestyle="--",
        linewidth=2,
        label="Stock ratio upper bound",
    )
    ax.set_ylim(0, max(100, max(values, default=0) + 10))
    ax.set_ylabel("Service ratio (%)")
    ax.set_title(f"{prepared.instance.name} — Regional Service")
    ax.grid(axis="y", alpha=0.2)
    ax.legend()

    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + 1,
            f"{value:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_allocation_map(
    instance: InstanceData,
    allocation: Sequence[int],
    out_path: str | Path,
) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    q = np.asarray(allocation, dtype=float)
    demand = instance.demand.astype(float)
    ratio = np.divide(
        q,
        demand,
        out=np.zeros_like(q, dtype=float),
        where=demand > 0,
    )

    fig, ax = plt.subplots(figsize=(9, 7))
    points = ax.scatter(
        instance.node_coord[instance.customers, 0],
        instance.node_coord[instance.customers, 1],
        s=60 + 350 * ratio[instance.customers],
        c=ratio[instance.customers],
        cmap="viridis",
        vmin=0,
        vmax=1,
        alpha=0.85,
        edgecolors="black",
        linewidths=0.7,
    )

    depot_xy = instance.node_coord[instance.depot]
    ax.scatter(
        [depot_xy[0]],
        [depot_xy[1]],
        marker="*",
        s=300,
        color="black",
        label="Depot",
        zorder=5,
    )

    for node in instance.customers:
        if q[node] > 0:
            x, y = instance.node_coord[node]
            ax.annotate(
                f"{node}: {int(q[node])}/{int(demand[node])}",
                (x, y),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=7,
            )

    fig.colorbar(points, ax=ax, label="Delivered / original demand")
    ax.set_title(f"{instance.name} — Allocation Intensity")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_fairness_distance_frontier(
    points: Sequence[tuple[float, int]],
    out_path: str | Path,
) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not points:
        return

    x = [p[0] * 100 for p in points]
    y = [p[1] for p in points]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(x, y, s=60)
    ax.set_xlabel("Minimum regional service (%)")
    ax.set_ylabel("Total route distance")
    ax.set_title("Fairness vs Route Distance")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
