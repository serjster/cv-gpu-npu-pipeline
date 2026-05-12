from __future__ import annotations

import asyncio
import time

import numpy as np
from numpy.typing import NDArray

from lowlatcv.config import OverlayConfig
from lowlatcv.models.frame import Detection, Frame
from lowlatcv.pipeline.overlay import Overlay


def _frame(detections: tuple[Detection, ...] = ()) -> Frame:
    img: NDArray[np.uint8] = np.zeros((100, 100, 3), dtype=np.uint8)
    return Frame(
        id=0,
        timestamp_ns=time.perf_counter_ns(),
        image=img,
        detections=detections,
    )


def test_overlay_no_detections_is_a_noop_passthrough() -> None:
    ov = Overlay(OverlayConfig())
    before = _frame()

    async def go() -> Frame:
        return await ov.process(before)

    after = asyncio.run(go())
    assert after is before
    assert int(after.image.sum()) == 0


def test_overlay_draws_for_each_detection() -> None:
    ov = Overlay(OverlayConfig(color=(0, 255, 0)))
    f = _frame(
        detections=(
            Detection(bbox=(10, 10, 50, 50), score=0.9, class_id=0),
            Detection(bbox=(60, 60, 90, 90), score=0.8, class_id=1),
        )
    )

    asyncio.run(ov.process(f))
    # Each box leaves green pixels along its edges.
    assert int((f.image[:, :, 1] > 0).sum()) > 0
