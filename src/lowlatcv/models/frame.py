"""Per-frame value objects: ``Frame``, ``Detection``, ``Track``.

``Frame`` carries the raw image (HxWx3 uint8 BGR) and an optional
preprocessed tensor. ``Detection`` is what the detector emits; ``Track``
is what the tracker emits after assigning persistent IDs. All three are
``@dataclass(frozen=True, slots=True)`` so they can cross stage queues
without surprises.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from lowlatcv.models.caption import Caption


@dataclass(frozen=True, slots=True)
class LetterboxMeta:
    """Parameters of a letterbox transform, needed to map detector boxes
    back from preprocessed coords into the original frame."""

    orig_h: int
    orig_w: int
    canvas_h: int
    canvas_w: int
    pad_top: int
    pad_left: int
    scale: float


@dataclass(frozen=True, slots=True)
class Frame:
    id: int
    timestamp_ns: int
    image: NDArray[np.uint8]
    tensor: NDArray[Any] | None = None
    letterbox: LetterboxMeta | None = None
    detections: tuple[Detection, ...] = ()


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
