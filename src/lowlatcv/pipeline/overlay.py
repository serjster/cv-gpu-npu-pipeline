"""``Overlay`` stage: renders bounding boxes + labels onto ``Frame.image``.

Draws in place on the original frame image — Frame is "frozen" at the
dataclass level but the underlying ndarray buffer is intentionally mutable
so the overlay can avoid an extra full-frame copy on the per-frame critical
path. The display / file sink then renders the same buffer.

For phase 3 the label is just the class id; phase 4 swaps in track IDs and
phase 5 appends the latest VLM caption.
"""

from __future__ import annotations

import logging

import cv2

from lowlatcv.config import OverlayConfig
from lowlatcv.models.frame import Frame

log = logging.getLogger(__name__)


class Overlay:
    name = "overlay"

    def __init__(self, cfg: OverlayConfig | None = None) -> None:
        self._cfg = cfg or OverlayConfig()

    async def setup(self) -> None: ...

    async def process(self, item: Frame) -> Frame:
        if not item.detections:
            return item
        img = item.image
        for det in item.detections:
            x1, y1, x2, y2 = det.bbox
            cv2.rectangle(img, (x1, y1), (x2, y2), self._cfg.color, thickness=2)
            label = f"{det.class_id} {det.score:.2f}"
            cv2.putText(
                img,
                label,
                (x1, max(0, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                self._cfg.font_scale,
                self._cfg.color,
                thickness=1,
                lineType=cv2.LINE_AA,
            )
        return item

    async def teardown(self) -> None: ...
