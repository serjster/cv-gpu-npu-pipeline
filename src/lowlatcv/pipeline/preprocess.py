from __future__ import annotations

import asyncio
import dataclasses
import logging
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from lowlatcv.config import PreprocessConfig
from lowlatcv.models.frame import Frame

log = logging.getLogger(__name__)


class Preprocess:
    """Letterbox resize + BGR→RGB + normalise + NCHW pack to the detector tensor shape.

    FPGA equivalent: PL Vitis Vision resize + cvtColor + convertTo chained over AXI-Stream.
    """

    name = "preprocess"

    def __init__(self, cfg: PreprocessConfig) -> None:
        self._cfg = cfg

    async def setup(self) -> None: ...

    async def process(self, item: Frame) -> Frame:
        loop = asyncio.get_running_loop()
        tensor = await loop.run_in_executor(None, self._transform, item.image)
        return dataclasses.replace(item, tensor=tensor)

    async def teardown(self) -> None: ...

    def _transform(self, image: NDArray[np.uint8]) -> NDArray[Any]:
        canvas = _letterbox(image, target_h=self._cfg.height, target_w=self._cfg.width)
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        arr: NDArray[Any] = rgb.astype(np.float32, copy=False)
        if self._cfg.normalize:
            arr = arr / np.float32(255.0)
        if self._cfg.layout == "NCHW":
            arr = np.transpose(arr, (2, 0, 1))
        arr = np.expand_dims(arr, 0)
        return np.ascontiguousarray(arr)


def _letterbox(image: NDArray[np.uint8], target_h: int, target_w: int) -> NDArray[np.uint8]:
    h, w = image.shape[:2]
    scale = min(target_w / w, target_h / h)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas: NDArray[np.uint8] = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
    top = (target_h - new_h) // 2
    left = (target_w - new_w) // 2
    canvas[top : top + new_h, left : left + new_w] = resized
    return canvas
