from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from lowlatcv.models.caption import Caption


@dataclass(frozen=True, slots=True)
class Frame:
    id: int
    timestamp_ns: int
    image: NDArray[np.uint8]
    tensor: NDArray[Any] | None = None


@dataclass(frozen=True, slots=True)
class Detection:
    bbox: tuple[int, int, int, int]
    score: float
    class_id: int


@dataclass(frozen=True, slots=True)
class Track:
    track_id: int
    bbox: tuple[int, int, int, int]
    class_id: int
    score: float
    age: int
    last_caption: Caption | None = None
