from __future__ import annotations

import asyncio
import gc
import time

import numpy as np
import pytest
from numpy.typing import NDArray

from lowlatcv.config import SinkConfig
from lowlatcv.models.frame import Frame
from lowlatcv.pipeline.sink import FileSink, NullSink, from_config


def _make_frame(i: int, h: int = 32, w: int = 32) -> Frame:
    img: NDArray[np.uint8] = np.full((h, w, 3), i % 255, dtype=np.uint8)
    return Frame(id=i, timestamp_ns=time.perf_counter_ns(), image=img)


def test_null_sink_consumes_without_retaining_frames() -> None:
    async def go() -> None:
        sink = NullSink()
        await sink.setup()
        try:
            for i in range(1000):
                await sink.process(_make_frame(i))
        finally:
            await sink.teardown()

    asyncio.run(go())
    gc.collect()
    alive = [o for o in gc.get_objects() if isinstance(o, Frame)]
    assert alive == []


def test_sink_factory_routes_by_kind(tmp_path: object) -> None:
    assert isinstance(from_config(SinkConfig(kind="null")), NullSink)
    out = str(tmp_path) + "/x.mp4"  # type: ignore[operator]
    assert isinstance(from_config(SinkConfig(kind="file", output=out)), FileSink)
    with pytest.raises(ValueError, match="output"):
        from_config(SinkConfig(kind="file"))
