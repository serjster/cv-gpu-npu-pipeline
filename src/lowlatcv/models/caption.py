from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Caption:
    track_id: int
    text: str
    model: str
    ts_ns: int


@dataclass(frozen=True, slots=True)
class CaptionRequest:
    track_id: int
    frame_id: int
    crop: Any
