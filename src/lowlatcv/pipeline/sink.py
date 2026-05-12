"""Frame sinks: ``FrameSink`` Protocol + concrete adapters + kind factory.

``NullSink`` drops frames (bench mode). ``SDLDisplaySink`` uses
pygame-ce's ``_sdl2`` Renderer + a single streaming Texture so the
per-frame upload runs on the GPU (Metal on macOS, OpenGL/Vulkan on
Linux, D3D on Windows). ``FileSink`` adapts ``cv2.VideoWriter``
(ffmpeg-pipe backend deferred to a later phase). ``from_config(cfg)``
is the Factory Method that selects a backend from ``SinkConfig.kind``;
it is also surfaced as ``FrameSink.from_config`` on the Protocol class
for ergonomics.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any, Protocol

import cv2
import numpy as np
from numpy.typing import NDArray

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


class SDLDisplaySink:
    """GPU-accelerated display sink via pygame-ce ``_sdl2`` Renderer + streaming Texture.

    Per frame: BGR → BGRA (one cv2.cvtColor into a preallocated buffer),
    DMA upload to a single persistent Texture, GPU draws a textured quad,
    present. No per-frame allocations. Renderer picks Metal on macOS,
    OpenGL/Vulkan on Linux, D3D on Windows. Must run on the main thread.
    """

    name = "sink"

    def __init__(self, window_name: str = "lowlatcv", vsync: bool = False) -> None:
        self._window_name = window_name
        self._vsync = vsync
        self._pygame: Any = None
        self._sdl2: Any = None
        self._window: Any = None
        self._renderer: Any = None
        self._texture: Any = None
        self._bgra: NDArray[np.uint8] | None = None
        self._size: tuple[int, int] | None = None

    async def setup(self) -> None:
        # Lazy import — pygame.init touches SDL globals and pulls in the C ext.
        import pygame  # type: ignore[import-untyped]
        from pygame._sdl2 import video as sdl2_video  # type: ignore[import-untyped]

        pygame.init()
        self._pygame = pygame
        self._sdl2 = sdl2_video

    async def process(self, item: Frame) -> None:
        h, w = item.image.shape[:2]
        if self._window is None or self._size != (w, h):
            self._init_window(w, h)
        assert self._bgra is not None
        cv2.cvtColor(item.image, cv2.COLOR_BGR2BGRA, dst=self._bgra)
        # Zero-copy view of the BGRA buffer as an SDL Surface; SDL_UpdateTexture
        # is a single DMA into the streaming texture.
        surf = self._pygame.image.frombuffer(self._bgra.data, (w, h), "BGRA")
        self._texture.update(surf)
        self._renderer.clear()
        self._texture.draw()
        self._renderer.present()
        # Pump the event queue so the window stays responsive on macOS.
        for _ in self._pygame.event.get():
            pass
        return None

    def _init_window(self, w: int, h: int) -> None:
        if self._window is not None:
            self._teardown_window()
        self._size = (w, h)
        self._window = self._sdl2.Window(title=self._window_name, size=(w, h), resizable=True)
        self._renderer = self._sdl2.Renderer(
            self._window, accelerated=1, vsync=1 if self._vsync else 0
        )
        # Default texture format is ARGB8888 (uint32 0xAARRGGBB → bytes LE [B,G,R,A]),
        # which matches the byte layout produced by cv2.COLOR_BGR2BGRA + frombuffer("BGRA").
        # No per-pixel format conversion happens inside SDL_UpdateTexture → straight DMA.
        self._texture = self._sdl2.Texture(self._renderer, size=(w, h), streaming=True)
        self._bgra = np.empty((h, w, 4), dtype=np.uint8)
        log.info("SDLDisplaySink window=%dx%d vsync=%s", w, h, self._vsync)

    def _teardown_window(self) -> None:
        self._texture = None
        self._renderer = None
        if self._window is not None:
            with contextlib.suppress(Exception):
                self._window.destroy()
            self._window = None
        self._bgra = None
        self._size = None

    async def teardown(self) -> None:
        self._teardown_window()
        if self._pygame is not None:
            self._pygame.quit()
            self._pygame = None
        self._sdl2 = None


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
        return SDLDisplaySink(vsync=cfg.vsync)
    if cfg.kind == "null":
        return NullSink()
    if cfg.kind == "file":
        if cfg.output is None:
            raise ValueError("file sink requires SinkConfig.output")
        return FileSink(output=cfg.output, codec=cfg.codec)
    raise ValueError(f"unknown sink kind: {cfg.kind}")
