from __future__ import annotations

import asyncio
import time

import numpy as np
from numpy.typing import NDArray

from lowlatcv.config import PreprocessConfig
from lowlatcv.models.frame import Frame
from lowlatcv.pipeline.preprocess import Preprocess


def _make_frame(h: int, w: int) -> Frame:
    img: NDArray[np.uint8] = np.zeros((h, w, 3), dtype=np.uint8)
    return Frame(id=0, timestamp_ns=time.perf_counter_ns(), image=img)


def test_preprocess_nchw_shape_and_dtype() -> None:
    cfg = PreprocessConfig(width=320, height=320, layout="NCHW", normalize=True)
    pre = Preprocess(cfg)

    async def go() -> Frame:
        await pre.setup()
        try:
            return await pre.process(_make_frame(480, 640))
        finally:
            await pre.teardown()

    out = asyncio.run(go())
    assert out.tensor is not None
    assert out.tensor.shape == (1, 3, 320, 320)
    assert out.tensor.dtype == np.float32
    assert 0.0 <= float(out.tensor.min()) <= float(out.tensor.max()) <= 1.0


def test_preprocess_nhwc_unnormalised_pass() -> None:
    cfg = PreprocessConfig(width=128, height=96, layout="NHWC", normalize=False)
    pre = Preprocess(cfg)

    async def go() -> Frame:
        return await pre.process(_make_frame(200, 300))

    out = asyncio.run(go())
    assert out.tensor is not None
    assert out.tensor.shape == (1, 96, 128, 3)
    assert out.tensor.dtype == np.float32
    assert float(out.tensor.max()) <= 255.0


def test_preprocess_letterbox_preserves_aspect_ratio() -> None:
    cfg = PreprocessConfig(width=200, height=200, layout="NHWC", normalize=False)
    pre = Preprocess(cfg)
    img: NDArray[np.uint8] = np.full((100, 400, 3), 240, dtype=np.uint8)
    frame = Frame(id=0, timestamp_ns=0, image=img)
    out = asyncio.run(pre.process(frame))
    assert out.tensor is not None
    # 400×100 → fits 200×50 inside 200×200, padded vertically with grey 114.
    nhwc = out.tensor[0]
    pad_row = nhwc[0]
    content_row = nhwc[100]
    assert int(pad_row.mean()) == 114
    assert int(content_row.mean()) != 114
