import numpy as np

from ai05.models import InstanceData, Region
from ai05.regions import classify_region


def make_instance():
    return InstanceData(
        name="A-n32-k5",
        node_coord=np.array([
            [10.0, 10.0],  # depot
            [10.0, 20.0],  # up axis
            [20.0, 10.0],  # right axis
            [20.0, 20.0],  # right-up
            [0.0, 20.0],   # left-up
            [0.0, 0.0],    # left-down
            [20.0, 0.0],   # right-down
        ]),
        demand=np.array([0, 1, 1, 1, 1, 1, 1]),
        depot=0,
        vehicles=5,
        capacity=100,
        edge_weight_type="EUC_2D",
        edge_weight=np.zeros((7, 7)),
    )


def test_axis_and_quadrant_rules():
    inst = make_instance()

    assert classify_region(inst, 1) == Region.RIGHT_UP
    assert classify_region(inst, 2) == Region.RIGHT_UP
    assert classify_region(inst, 3) == Region.RIGHT_UP
    assert classify_region(inst, 4) == Region.LEFT_UP
    assert classify_region(inst, 5) == Region.LEFT_DOWN
    assert classify_region(inst, 6) == Region.RIGHT_DOWN
