from __future__ import annotations

import asyncio
import time

import numpy as np
import pytest
from numpy.typing import NDArray

from lowlatcv.config import DetectorConfig
from lowlatcv.models.frame import Detection, Frame
from lowlatcv.pipeline.detector import FakeDetector, from_config


def _make_frame(h: int = 100, w: int = 200) -> Frame:
    img: NDArray[np.uint8] = np.zeros((h, w, 3), dtype=np.uint8)
    return Frame(id=0, timestamp_ns=time.perf_counter_ns(), image=img)


def test_fake_detector_emits_central_bbox() -> None:
    det = FakeDetector()

    async def go() -> Frame:
        await det.setup()
        try:
            return await det.process(_make_frame(h=100, w=200))
        finally:
            await det.teardown()

    out = asyncio.run(go())
    assert len(out.detections) == 1
    d = out.detections[0]
    assert isinstance(d, Detection)
    assert d.bbox == (50, 25, 150, 75)
    assert d.score == 0.9
    assert d.class_id == 0


def test_detector_factory_routes_by_backend() -> None:
    assert isinstance(from_config(DetectorConfig(backend="fake")), FakeDetector)
    with pytest.raises(ValueError, match="weights"):
        from_config(DetectorConfig(backend="onnx", weights=None))
    with pytest.raises(ValueError, match="unknown detector backend"):
        from_config(DetectorConfig(backend="nope"))
