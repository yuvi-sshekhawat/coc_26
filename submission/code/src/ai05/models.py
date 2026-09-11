from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

import numpy as np


class Region(IntEnum):
    RIGHT_UP = 0
    LEFT_UP = 1
    LEFT_DOWN = 2
    RIGHT_DOWN = 3


@dataclass(frozen=True)
class InstanceData:
    name: str
    node_coord: np.ndarray
    demand: np.ndarray
    depot: int
    vehicles: int
    capacity: int
    edge_weight_type: str
    edge_weight: np.ndarray
    edge_weight_format: Optional[str] = None

    @property
    def dimension(self) -> int:
        return int(len(self.node_coord))

    @property
    def customers(self) -> list[int]:
        return [i for i in range(self.dimension) if i != self.depot]

    @property
    def total_demand(self) -> int:
        return int(np.sum(self.demand[self.customers]))

    @property
    def stock(self) -> int:
        return int(np.floor(0.70 * self.total_demand))


@dataclass(frozen=True)
class PreparedInstance:
    instance: InstanceData
    regions: dict[int, Region]
    regional_demand: dict[Region, int]
