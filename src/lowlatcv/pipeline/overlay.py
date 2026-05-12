"""``Overlay`` stage: renders bounding boxes + labels onto ``Frame.image``.

Draws in place on the original frame image — Frame is "frozen" at the
dataclass level but the underlying ndarray buffer is intentionally mutable
so the overlay can avoid an extra full-frame copy on the per-frame critical
path. The display / file sink then renders the same buffer.

When the upstream tracker has populated ``Frame.tracks`` the overlay
renders tracks (per-state styling — solid for ``ACTIVE``, thin for
``TENTATIVE``, dashed for ``LOST``, skip ``DEAD``) and labels them with
the track id. Otherwise it falls back to rendering ``Frame.detections``
with the class id as the label.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np
from numpy.typing import NDArray

from lowlatcv.config import OverlayConfig
from lowlatcv.models.frame import Frame, Track, TrackState
from lowlatcv.pipeline.vlm import CaptionResultStore

log = logging.getLogger(__name__)


_STATE_STYLE: dict[TrackState, tuple[int, bool]] = {
    # (thickness, dashed)
    TrackState.TENTATIVE: (1, False),
    TrackState.ACTIVE: (2, False),
    TrackState.LOST: (1, True),
}


class Overlay:
    name = "overlay"

    def __init__(
        self,
        cfg: OverlayConfig | None = None,
        caption_store: CaptionResultStore | None = None,
        caption_chars: int = 64,
    ) -> None:
        self._cfg = cfg or OverlayConfig()
        self._caption_store = caption_store
        self._caption_chars = caption_chars

    async def setup(self) -> None: ...

    async def process(self, item: Frame) -> Frame:
        if item.tracks:
            self._draw_tracks(item)
        elif item.detections:
            self._draw_detections(item)
        return item

    async def teardown(self) -> None: ...

    def _draw_tracks(self, item: Frame) -> None:
        img = item.image
        color = self._cfg.color
        for tr in item.tracks:
            if tr.state is TrackState.DEAD:
                continue
            thickness, dashed = _STATE_STYLE.get(tr.state, (2, False))
            x1, y1, x2, y2 = tr.bbox
            if dashed:
                _draw_dashed_rect(img, (x1, y1), (x2, y2), color, thickness)
            else:
                cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness=thickness)
            cv2.putText(
                img,
                _track_label(tr),
                (x1, max(0, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                self._cfg.font_scale,
                color,
                thickness=1,
                lineType=cv2.LINE_AA,
            )
            self._maybe_draw_caption(img, tr, x1, y2)

    def _maybe_draw_caption(
        self,
        img: NDArray[np.uint8],
        tr: Track,
        x1: int,
        y2: int,
    ) -> None:
        if not self._cfg.draw_caption or self._caption_store is None:
            return
        cap = self._caption_store.get(tr.track_id)
        if cap is None:
            return
        text = cap.text[: self._caption_chars]
        cv2.putText(
            img,
            text,
            (x1, min(img.shape[0] - 2, y2 + 16)),
            cv2.FONT_HERSHEY_SIMPLEX,
            self._cfg.font_scale,
            self._cfg.color,
            thickness=1,
            lineType=cv2.LINE_AA,
        )

    def _draw_detections(self, item: Frame) -> None:
        img = item.image
        color = self._cfg.color
        for det in item.detections:
            x1, y1, x2, y2 = det.bbox
            cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness=2)
            cv2.putText(
                img,
                f"{det.class_id} {det.score:.2f}",
                (x1, max(0, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                self._cfg.font_scale,
                color,
                thickness=1,
                lineType=cv2.LINE_AA,
            )


def _track_label(tr: Track) -> str:
    return f"#{tr.track_id} {tr.state.value[:1].upper()} {tr.score:.2f}"


def _draw_dashed_rect(
    img: NDArray[np.uint8],
    p1: tuple[int, int],
    p2: tuple[int, int],
    color: tuple[int, int, int],
    thickness: int,
    dash: int = 8,
    gap: int = 6,
) -> None:
    x1, y1 = p1
    x2, y2 = p2
    _dashed_line(img, (x1, y1), (x2, y1), color, thickness, dash, gap)
    _dashed_line(img, (x2, y1), (x2, y2), color, thickness, dash, gap)
    _dashed_line(img, (x2, y2), (x1, y2), color, thickness, dash, gap)
    _dashed_line(img, (x1, y2), (x1, y1), color, thickness, dash, gap)


def _dashed_line(
    img: NDArray[np.uint8],
    p1: tuple[int, int],
    p2: tuple[int, int],
    color: tuple[int, int, int],
    thickness: int,
    dash: int,
    gap: int,
) -> None:
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    length = max(1, int((dx * dx + dy * dy) ** 0.5))
    step = dash + gap
    nx, ny = dx / length, dy / length
    pos = 0
    while pos < length:
        a = (int(x1 + nx * pos), int(y1 + ny * pos))
        b_end = min(pos + dash, length)
        b = (int(x1 + nx * b_end), int(y1 + ny * b_end))
        cv2.line(img, a, b, color, thickness=thickness, lineType=cv2.LINE_AA)
        pos += step
