"""``TileHintBoard`` + ``TileActivityBoard`` — bidirectional state between tracker, tiled detector, and overlay.

The pipeline graph is unidirectional (Source → … → Sink) but tile-on-demand
inference needs the tracker to tell the detector which tiles still matter,
and the overlay needs to read which tiles the detector actually ran so it
can paint the debug visualisation. Encoded as two thread-safe shared
objects:

- ``TileHintBoard``: tracker → detector. Tracker writes recovery bboxes
  (LOST + TENTATIVE lanes); detector reads them and converts to tile
  indices. Also handles the rotating refresh tile.
- ``TileActivityBoard``: detector → overlay. Detector records which tile
  ran this cycle, why ("recovery" vs "refresh" vs "sweep"), and how many
  detections were found in it. Overlay renders fading translucent
  rectangles so the operator can see coverage.

The two boards are independent — you can enable activity tracking without
tile-on-demand (full sweeps will just paint everything "sweep" green).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class TileActivity:
    """Snapshot of a single tile's most recent inference cycle."""

    last_frame_id: int
    reason: str  # "recovery" | "refresh" | "sweep"
    n_dets: int


class TileHintBoard:
    """Shared mutable channel: tracker → tiled detector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recovery_bboxes: list[tuple[int, int, int, int]] = []
        self._refresh_idx: int = 0

    def update_recovery_bboxes(self, bboxes: list[tuple[int, int, int, int]]) -> None:
        with self._lock:
            self._recovery_bboxes = list(bboxes)

    def select_tiles(
        self,
        rows: int,
        cols: int,
        frame_h: int,
        frame_w: int,
        refresh_per_cycle: int,
    ) -> dict[tuple[int, int], str]:
        """Return ``{(row, col): reason}`` for tiles to run this cycle.

        Always includes:
        - One tile per recovery bbox (tile containing its centre) → ``"recovery"``.
        - ``refresh_per_cycle`` tiles from a rotating index so cold tiles
          eventually get coverage → ``"refresh"``.

        If the same tile is selected by both a recovery hint and the
        refresh rotation this cycle, "recovery" wins (it's the more
        actionable signal).
        """
        with self._lock:
            selections: dict[tuple[int, int], str] = {}
            tile_h = max(1.0, frame_h / rows)
            tile_w = max(1.0, frame_w / cols)
            for x1, y1, x2, y2 in self._recovery_bboxes:
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                r = min(rows - 1, max(0, int(cy / tile_h)))
                c = min(cols - 1, max(0, int(cx / tile_w)))
                selections[(r, c)] = "recovery"
            for _ in range(max(1, refresh_per_cycle)):
                r = self._refresh_idx // cols
                c = self._refresh_idx % cols
                selections.setdefault((r, c), "refresh")
                self._refresh_idx = (self._refresh_idx + 1) % max(1, rows * cols)
            return selections


class TileActivityBoard:
    """Shared mutable channel: tiled detector → overlay.

    Records the most recent inference activity per tile (which frame ran
    it, why, and how many detections came out). Overlay fades colour by
    ``current_frame_id - last_frame_id`` so cold tiles dim out.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[tuple[int, int], TileActivity] = {}

    def record(self, row: int, col: int, frame_id: int, reason: str, n_dets: int) -> None:
        with self._lock:
            self._states[(row, col)] = TileActivity(
                last_frame_id=frame_id, reason=reason, n_dets=n_dets
            )

    def snapshot(self) -> dict[tuple[int, int], TileActivity]:
        with self._lock:
            return dict(self._states)
