"""VLM value objects: ``Caption`` results and ``CaptionRequest`` jobs.

Used by the VLM stage (off the per-frame critical path). The tracker emits a
``CaptionRequest`` on first sighting of a new track; the VLM worker posts
``Caption`` results into a shared map keyed by ``track_id`` for the overlay
stage to render.
"""

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
    """Command sent from the per-frame critical path to the VLM worker."""

    track_id: int
    frame_id: int
    crop: Any
    prompt: str | None = None
    first_sighting: bool = False
    submitted_ns: int = 0
