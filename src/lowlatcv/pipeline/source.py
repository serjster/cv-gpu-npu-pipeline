"""Frame sources: ``FrameSource`` Protocol + cv2-backed adapters + URI factory.

``FileSource`` and ``WebcamSource`` are Adapters around ``cv2.VideoCapture``
running each blocking ``.read()`` on the asyncio default executor so the
event loop stays free to drive downstream stages. ``from_uri(uri, cfg,
frame_limit, pace)`` is the Factory Method that picks the right backend
from the URI scheme (``file://`` / bare path → file; ``webcam:N`` / bare
digit → webcam; ``rtsp://`` / ``http(s)://`` / ``udp://`` / ``tcp://`` →
network via VideoCapture). The same factory is also exposed as
``FrameSource.from_uri`` on the Protocol class for ergonomics.

Pacing: when ``pace=True``, ``FileSource`` throttles emission to
``SourceConfig.target_fps`` (falling back to the file's intrinsic FPS
reported by ``cv2.CAP_PROP_FPS``). Bench runs leave ``pace=False`` so the
pipeline runs at maximum decode rate.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Protocol

import cv2

from lowlatcv.config import SourceConfig
from lowlatcv.models.frame import Frame
from lowlatcv.pipeline.stage import EOF, _EOFType

log = logging.getLogger(__name__)


class FrameSource(Protocol):
    """Strategy for emitting Frames into the pipeline. Source-mode stage."""

    name: str

    async def setup(self) -> None: ...
    async def process(self, item: Any) -> Frame | _EOFType: ...
    async def teardown(self) -> None: ...


def from_uri(
    uri: str,
    cfg: SourceConfig | None = None,
    frame_limit: int | None = None,
    pace: bool = False,
    pause_gate: Any | None = None,
) -> FrameSource:
    """Factory Method: select a source backend from the URI scheme."""
    return _from_uri(uri, cfg or SourceConfig(), frame_limit, pace, pause_gate)


if not TYPE_CHECKING:
    # Sugar so callers can write FrameSource.from_uri(...) per the design pattern intent
    # without forcing concrete classes to implement a static factory member.
    FrameSource.from_uri = staticmethod(from_uri)


class FileSource:
    """Adapter around ``cv2.VideoCapture`` for file / RTSP / HTTP URIs."""

    name = "source"

    def __init__(
        self,
        path: str,
        cfg: SourceConfig | None = None,
        frame_limit: int | None = None,
        pace: bool = False,
        pause_gate: Any | None = None,
    ) -> None:
        self._path = path
        self._cfg = cfg or SourceConfig()
        self._frame_limit = frame_limit
        self._pace = pace
        self._cap: Any = None
        self._i = 0
        self._frame_period_ns: int | None = None
        self._next_frame_ns: int | None = None
        self._pause_gate = pause_gate

    async def setup(self) -> None:
        loop = asyncio.get_running_loop()
        cap = await loop.run_in_executor(None, cv2.VideoCapture, self._path)
        if not cap.isOpened():
            raise RuntimeError(f"failed to open source: {self._path}")
        self._cap = cap
        self._frame_period_ns = self._compute_frame_period_ns(cap)
        log.info(
            "FileSource opened path=%s pace=%s effective_fps=%s",
            self._path,
            self._pace,
            None if self._frame_period_ns is None else round(1e9 / self._frame_period_ns, 2),
        )

    def _compute_frame_period_ns(self, cap: Any) -> int | None:
        if not self._pace:
            return None
        fps = self._cfg.target_fps
        if fps is None:
            try:
                detected = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            except Exception:
                detected = 0.0
            if detected > 0:
                fps = detected
        if fps is None or fps <= 0:
            return None
        return int(round(1e9 / fps))

    async def process(self, item: Any) -> Frame | _EOFType:
        if self._frame_limit is not None and self._i >= self._frame_limit:
            return EOF
        if self._pause_gate is not None:
            await self._pause_gate.wait_for_release()
        await self._wait_for_next_slot()
        loop = asyncio.get_running_loop()
        ok, image = await loop.run_in_executor(None, self._cap.read)
        if not ok or image is None:
            return EOF
        frame = Frame(id=self._i, timestamp_ns=time.perf_counter_ns(), image=image)
        self._i += 1
        return frame

    async def _wait_for_next_slot(self) -> None:
        if self._frame_period_ns is None:
            return
        now = time.perf_counter_ns()
        if self._next_frame_ns is None:
            self._next_frame_ns = now + self._frame_period_ns
            return
        wait_ns = self._next_frame_ns - now
        if wait_ns > 0:
            await asyncio.sleep(wait_ns / 1e9)
        self._next_frame_ns += self._frame_period_ns

    async def teardown(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class WebcamSource(FileSource):
    """Adapter around ``cv2.VideoCapture`` for a device index (V4L2 on Linux, AVFoundation on macOS)."""

    def __init__(
        self,
        device_index: int,
        cfg: SourceConfig | None = None,
        frame_limit: int | None = None,
        pace: bool = False,
        pause_gate: Any | None = None,
    ) -> None:
        super().__init__(
            path=str(device_index),
            cfg=cfg,
            frame_limit=frame_limit,
            pace=pace,
            pause_gate=pause_gate,
        )
        self._device_index = device_index

    async def setup(self) -> None:
        loop = asyncio.get_running_loop()
        cap = await loop.run_in_executor(None, cv2.VideoCapture, self._device_index)
        if not cap.isOpened():
            raise RuntimeError(f"failed to open webcam: {self._device_index}")
        if self._cfg.target_fps is not None:
            cap.set(cv2.CAP_PROP_FPS, float(self._cfg.target_fps))
        self._cap = cap
        self._frame_period_ns = self._compute_frame_period_ns(cap)


_NETWORK_SCHEMES = ("rtsp://", "http://", "https://", "udp://", "tcp://")


def _from_uri(
    uri: str,
    cfg: SourceConfig,
    frame_limit: int | None,
    pace: bool,
    pause_gate: Any | None = None,
) -> FrameSource:
    common = dict(cfg=cfg, frame_limit=frame_limit, pace=pace, pause_gate=pause_gate)
    if uri.startswith("webcam:"):
        idx = int(uri.split(":", 1)[1])
        return WebcamSource(device_index=idx, **common)  # type: ignore[arg-type]
    if uri.startswith(_NETWORK_SCHEMES):
        return FileSource(path=uri, **common)  # type: ignore[arg-type]
    if uri.startswith("file://"):
        return FileSource(path=uri[len("file://") :], **common)  # type: ignore[arg-type]
    if uri.isdigit():
        return WebcamSource(device_index=int(uri), **common)  # type: ignore[arg-type]
    return FileSource(path=uri, **common)  # type: ignore[arg-type]
