from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

import cv2

from lowlatcv.config import SinkConfig
from lowlatcv.models.frame import Frame

log = logging.getLogger(__name__)


class FrameSink(Protocol):
    """Strategy for the terminal stage. Returns ``None`` (consumer)."""

    name: str

    async def setup(self) -> None: ...
    async def process(self, item: Frame) -> None: ...
    async def teardown(self) -> None: ...


def from_config(cfg: SinkConfig) -> FrameSink:
    """Factory Method: select a sink backend from ``SinkConfig.kind``."""
    return _from_config(cfg)


if not TYPE_CHECKING:
    FrameSink.from_config = staticmethod(from_config)


class NullSink:
    """Bench-mode sink: drops frames, lets the latency report do the talking."""

    name = "sink"

    async def setup(self) -> None: ...

    async def process(self, item: Frame) -> None:
        return None

    async def teardown(self) -> None: ...


class DisplaySink:
    """Adapter around ``cv2.imshow`` — must run on the main thread (macOS requirement)."""

    name = "sink"

    def __init__(self, window_name: str = "lowlatcv") -> None:
        self._window = window_name
        self._opened = False

    async def setup(self) -> None: ...

    async def process(self, item: Frame) -> None:
        if not self._opened:
            cv2.namedWindow(self._window, cv2.WINDOW_NORMAL)
            self._opened = True
        cv2.imshow(self._window, item.image)
        cv2.waitKey(1)
        return None

    async def teardown(self) -> None:
        if self._opened:
            cv2.destroyWindow(self._window)
            cv2.waitKey(1)
            self._opened = False


class FileSink:
    """Adapter around ``cv2.VideoWriter``. ffmpeg-pipe backend deferred to a later phase."""

    name = "sink"

    def __init__(self, output: str, codec: str = "h264", fps: float = 30.0) -> None:
        self._output = output
        self._codec = codec
        self._fps = fps
        self._writer: Any = None

    async def setup(self) -> None: ...

    async def process(self, item: Frame) -> None:
        if self._writer is None:
            fourcc = cv2.VideoWriter_fourcc(*_codec_to_fourcc(self._codec))  # type: ignore[attr-defined]
            h, w = item.image.shape[:2]
            self._writer = cv2.VideoWriter(self._output, fourcc, self._fps, (w, h))
            if not self._writer.isOpened():
                raise RuntimeError(f"failed to open writer: {self._output}")
        self._writer.write(item.image)
        return None

    async def teardown(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None


def _codec_to_fourcc(codec: str) -> str:
    table = {"h264": "avc1", "avc1": "avc1", "mp4v": "mp4v", "mjpg": "MJPG"}
    return table.get(codec.lower(), "avc1")


def _from_config(cfg: SinkConfig) -> FrameSink:
    if cfg.kind == "display":
        return DisplaySink()
    if cfg.kind == "null":
        return NullSink()
    if cfg.kind == "file":
        if cfg.output is None:
            raise ValueError("file sink requires SinkConfig.output")
        return FileSink(output=cfg.output, codec=cfg.codec)
    raise ValueError(f"unknown sink kind: {cfg.kind}")
