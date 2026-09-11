from __future__ import annotations

from pathlib import Path

import numpy as np
import vrplib

from .models import InstanceData


REQUIRED_INSTANCES = ("A-n32-k5", "A-n33-k5", "B-n31-k5")


def load_instance(path: str | Path) -> InstanceData:
    """Load one official CVRPLIB instance through vrplib."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Instance file not found: {path}")

    raw = vrplib.read_instance(str(path), compute_edge_weights=True)

    required = (
        "name",
        "node_coord",
        "demand",
        "depot",
        "capacity",
        "edge_weight",
    )
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"VRPLIB instance is missing required fields: {missing}")

    name = str(raw["name"])
    vehicles = None
    if raw.get("vehicles") is not None:
        vehicles = int(raw["vehicles"])
    else:
        import re
        m_name = re.search(r"-k(\d+)", name, re.IGNORECASE)
        if m_name:
            vehicles = int(m_name.group(1))
        elif raw.get("comment"):
            m_comm = re.search(r"(?:trucks|vehicles|k)\s*[:=]?\s*(\d+)", str(raw["comment"]), re.IGNORECASE)
            if m_comm:
                vehicles = int(m_comm.group(1))

    if vehicles is None:
        raise ValueError(f"Could not determine vehicle count for instance {name}")

    depot = int(np.asarray(raw["depot"]).reshape(-1)[0])
    coords = np.asarray(raw["node_coord"], dtype=float)
    demand = np.asarray(raw["demand"], dtype=int)
    edge_weight = np.asarray(raw["edge_weight"], dtype=float)

    edge_weight_type = str(raw.get("edge_weight_type", "UNKNOWN"))
    # Standard CVRPLIB / TSPLIB EUC_2D semantics: distances rounded to nearest integer
    if edge_weight_type == "EUC_2D":
        edge_weight = np.rint(edge_weight)

    if coords.shape[0] != demand.shape[0]:
        raise ValueError("Coordinate count and demand count differ.")

    if edge_weight.shape != (len(coords), len(coords)):
        raise ValueError("Edge-weight matrix has unexpected shape.")

    if demand[depot] != 0:
        raise ValueError("Depot demand must be zero.")

    instance = InstanceData(
        name=name,
        node_coord=coords,
        demand=demand,
        depot=depot,
        vehicles=vehicles,
        capacity=int(raw["capacity"]),
        edge_weight_type=str(raw.get("edge_weight_type", "UNKNOWN")),
        edge_weight=edge_weight,
        edge_weight_format=(
            str(raw["edge_weight_format"])
            if raw.get("edge_weight_format") is not None
            else None
        ),
    )

    if instance.name not in REQUIRED_INSTANCES:
        raise ValueError(
            f"Unexpected instance {instance.name}. "
            f"Required: {REQUIRED_INSTANCES}."
        )

    return instance
