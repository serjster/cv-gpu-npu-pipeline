"""``TileHintBoard`` — bidirectional channel from tracker to tiled detector.

The pipeline graph is unidirectional (Source → … → Sink) but tile-on-demand
inference needs the tracker to tell the detector which tiles still matter.
Encoded as a thread-safe shared object that both stages take via DI:

- ``ByteTracker`` writes hints after each ``process``: bboxes of LOST and
  TENTATIVE lanes — those need re-detection most urgently.
- ``TiledOnnxDetector`` (in tile-on-demand mode) reads + clears hints,
  maps them to (row, col) tile indices, adds a few round-robin refresh
  tiles so cold regions still get periodic coverage, and runs inference
  on that subset only. The detector also keeps a per-tile latest-detection
  cache so its aggregate output stays full-frame.
"""

from __future__ import annotations

import threading


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
    ) -> set[tuple[int, int]]:
        """Return the set of tile indices ``(row, col)`` to run this cycle.

        Always includes:
        - One tile per recovery bbox (the tile containing its centre).
        - ``refresh_per_cycle`` tiles from a rotating index so cold tiles
          eventually get coverage even when nothing is lost.
        """
        with self._lock:
            tiles: set[tuple[int, int]] = set()
            tile_h = max(1.0, frame_h / rows)
            tile_w = max(1.0, frame_w / cols)
            for x1, y1, x2, y2 in self._recovery_bboxes:
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                r = min(rows - 1, max(0, int(cy / tile_h)))
                c = min(cols - 1, max(0, int(cx / tile_w)))
                tiles.add((r, c))
            for _ in range(max(1, refresh_per_cycle)):
                r = self._refresh_idx // cols
                c = self._refresh_idx % cols
                tiles.add((r, c))
                self._refresh_idx = (self._refresh_idx + 1) % max(1, rows * cols)
            return tiles
