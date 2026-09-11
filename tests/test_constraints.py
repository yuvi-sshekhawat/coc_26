import numpy as np
import pytest

from ai05.constraints import ConstraintViolation, validate_allocation
from ai05.models import InstanceData


def make_instance():
    return InstanceData(
        name="A-n32-k5",
        node_coord=np.array([[0, 0], [1, 0], [2, 0]], dtype=float),
        demand=np.array([0, 10, 20]),
        depot=0,
        vehicles=5,
        capacity=100,
        edge_weight_type="EUC_2D",
        edge_weight=np.zeros((3, 3)),
    )


def test_valid_allocation():
    validate_allocation(
        make_instance(),
        np.array([0, 7, 14]),
    )


def test_demand_violation():
    with pytest.raises(ConstraintViolation):
        validate_allocation(
            make_instance(),
            np.array([0, 11, 10]),
        )


def test_stock_violation():
    with pytest.raises(ConstraintViolation):
        validate_allocation(
            make_instance(),
            np.array([0, 10, 20]),
        )
