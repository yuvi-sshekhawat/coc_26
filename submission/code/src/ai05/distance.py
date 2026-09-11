from __future__ import annotations

import numpy as np

from .models import InstanceData


def validate_distance_matrix(instance: InstanceData) -> None:
    """Check structural properties without changing official edge weights."""
    D = instance.edge_weight

    if D.shape != (instance.dimension, instance.dimension):
        raise ValueError("Distance matrix shape mismatch.")

    if not np.allclose(np.diag(D), 0.0, atol=1e-9):
        raise ValueError("Distance matrix diagonal must be zero.")

    if not np.allclose(D, D.T, atol=1e-9):
        raise ValueError("Expected symmetric CVRP edge weights.")

    if np.any(D < -1e-9):
        raise ValueError("Distance matrix contains negative values.")


def get_distance(instance: InstanceData, i: int, j: int) -> float:
    validate_node(instance, i)
    validate_node(instance, j)
    return float(instance.edge_weight[i, j])


def validate_node(instance: InstanceData, node: int) -> None:
    if not 0 <= int(node) < instance.dimension:
        raise IndexError(
            f"Node {node} outside instance dimension {instance.dimension}."
        )
