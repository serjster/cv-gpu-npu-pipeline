"""``DebugWindow``: separate pygame window with live performance metrics.

Spawns its own SDL window (positioned next to the scene window) so the
metrics don't eat scene real estate. Renders:

- Frame index, source FPS (rolling 1 s window).
- Per-stage p50 / p99 from the shared ``Tracer``.
- Detection / track counts at the current frame.
- AsyncDetector counters (published, dropped, last worker ms, staleness).
- Pause / step status.

Keys (pumped by this stage — must run BEFORE ``SDLDisplaySink`` in the
pipeline so it sees keyboard input first):

- ``Space``: toggle pause. While paused the source stage stalls.
- ``Right``: step one frame.
- ``r``: reset tracer percentile buffers.

Implemented as a tap Stage — ``process`` passes the ``Frame`` through.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import logging
import time
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from lowlatcv.metrics.tracer import Tracer
from lowlatcv.models.frame import Frame

log = logging.getLogger(__name__)


class PauseGate:
    """Cooperative gate the source stage polls before each frame read."""

    def __init__(self) -> None:
        self._paused = False
        self._step_pending = False

    @property
    def paused(self) -> bool:
        return self._paused

    def toggle_pause(self) -> None:
        self._paused = not self._paused
        self._step_pending = False

    def request_step(self) -> None:
        self._step_pending = True
        self._paused = True

    async def wait_for_release(self) -> None:
        while self._paused and not self._step_pending:
            await asyncio.sleep(0.02)
        if self._step_pending:
            self._step_pending = False


class DebugWindow:
    """Pipeline tap stage that renders metrics in its own SDL window."""

    name = "debug_window"

    def __init__(
        self,
        tracer: Tracer,
        gate: PauseGate,
        async_detector: Any | None = None,
        width: int = 540,
        height: int = 620,
        x_offset: int = 1320,
        y_offset: int = 80,
        title: str = "lowlatcv debug",
    ) -> None:
        self._tracer = tracer
        self._gate = gate
        self._async_detector = async_detector
        self._w = width
        self._h = height
        self._x = x_offset
        self._y = y_offset
        self._title = title
        self._pygame: Any = None
        self._sdl2: Any = None
        self._window: Any = None
        self._renderer: Any = None
        self._texture: Any = None
        self._buf_bgr: NDArray[np.uint8] | None = None
        self._buf_bgra: NDArray[np.uint8] | None = None
        self._frame_times: collections.deque[float] = collections.deque(maxlen=60)
        self._stage_order: list[str] = []
        self._quit_requested = False
        # Background event-pump task — runs even when the pipeline is paused
        # (source isn't producing frames) so the debug window stays responsive
        # to keyboard input.
        self._pump_task: asyncio.Task[None] | None = None
        self._pump_stop = asyncio.Event()

    async def setup(self) -> None:
        import pygame  # type: ignore[import-untyped]
        from pygame._sdl2 import video as sdl2_video  # type: ignore[import-untyped]

        if not pygame.get_init():
            pygame.init()
        self._pygame = pygame
        self._sdl2 = sdl2_video
        self._window = sdl2_video.Window(title=self._title, size=(self._w, self._h), resizable=True)
        with contextlib.suppress(Exception):
            self._window.position = (self._x, self._y)
        self._renderer = sdl2_video.Renderer(self._window, accelerated=1, vsync=False)
        self._texture = sdl2_video.Texture(self._renderer, size=(self._w, self._h), streaming=True)
        self._buf_bgr = np.zeros((self._h, self._w, 3), dtype=np.uint8)
        self._buf_bgra = np.empty((self._h, self._w, 4), dtype=np.uint8)
        self._pump_task = asyncio.create_task(self._pump_loop(), name="debug-pump")
        log.info("DebugWindow opened %dx%d at (%d, %d)", self._w, self._h, self._x, self._y)

    async def process(self, item: Frame) -> Frame:
        # Events are pumped by the background _pump_loop so the window stays
        # responsive even while the source is paused (no frames flowing).
        # Here we just render the latest metrics.
        self._frame_times.append(time.perf_counter())
        self._render(item)
        return item

    async def _pump_loop(self) -> None:
        """Pumps pygame events at ~50 Hz independent of the per-frame pipeline.

        While the user pauses playback the source stage stalls — no Frames
        traverse downstream stages, so the per-frame ``process`` never runs.
        Without this loop the debug window would freeze, including key input
        (so the user could pause but not unpause). Running on the same asyncio
        loop as the orchestrator keeps pygame calls on the main thread.
        """
        try:
            while not self._pump_stop.is_set():
                self._pump_events()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._pump_stop.wait(), timeout=0.02)
        except asyncio.CancelledError:
            pass

    async def teardown(self) -> None:
        self._pump_stop.set()
        if self._pump_task is not None:
            self._pump_task.cancel()
            with contextlib.suppress(Exception):
                await self._pump_task
            self._pump_task = None
        if self._window is not None:
            with contextlib.suppress(Exception):
                self._window.destroy()
        self._window = None
        self._renderer = None
        self._texture = None

    def _pump_events(self) -> None:
        if self._pygame is None:
            return
        for ev in self._pygame.event.get():
            if ev.type == self._pygame.KEYDOWN:
                self._on_keydown(ev.key)
            elif ev.type == self._pygame.QUIT:
                self._quit_requested = True

    def _on_keydown(self, key: int) -> None:
        pg = self._pygame
        if key == pg.K_SPACE:
            self._gate.toggle_pause()
        elif key == pg.K_RIGHT:
            self._gate.request_step()
        elif key == pg.K_r:
            # Best-effort: clear the tracer's sliding-window buffers so
            # percentile readings reflect only post-reset latencies.
            self._tracer._buffers.clear()  # noqa: SLF001 — debug-only
        elif key == pg.K_q:
            self._quit_requested = True

    def _render(self, item: Frame) -> None:
        if self._buf_bgr is None or self._buf_bgra is None:
            return
        self._buf_bgr[:] = (24, 22, 30)
        y = [28]

        buf = self._buf_bgr

        def line(
            text: str, color: tuple[int, int, int] = (220, 220, 220), scale: float = 0.5
        ) -> None:
            cv2.putText(
                buf,
                text,
                (12, y[0]),
                cv2.FONT_HERSHEY_SIMPLEX,
                scale,
                color,
                1,
                cv2.LINE_AA,
            )
            y[0] += int(max(20.0, scale * 36))

        # Top: frame + FPS
        fps = self._rolling_fps()
        line(f"frame {item.id}    fps {fps:5.1f}", (180, 255, 180), 0.7)
        line(
            f"paused: {self._gate.paused}",
            (180, 200, 255) if self._gate.paused else (140, 140, 160),
            0.5,
        )

        y[0] += 8
        line("STAGE LATENCY (ms)", (180, 180, 220), 0.5)
        line(f"{'stage':<18}{'n':>6}{'p50':>8}{'p99':>8}{'max':>8}", (160, 160, 180), 0.45)
        # Stages tracked in tracer (Tracer._buffers is the source-of-truth).
        for name in self._tracer.stages():
            stats = self._tracer.stats(name)
            if stats is None:
                continue
            line(
                f"{name[:18]:<18}{stats.count:>6}{stats.p50_ns / 1e6:>8.2f}{stats.p99_ns / 1e6:>8.2f}{stats.max_ns / 1e6:>8.2f}",
                (220, 220, 220),
                0.42,
            )

        y[0] += 8
        line("TRACKS / DETECTIONS", (180, 180, 220), 0.5)
        active = sum(1 for t in item.tracks if t.state.value == "active")
        lost = sum(1 for t in item.tracks if t.state.value == "lost")
        tent = sum(1 for t in item.tracks if t.state.value == "tentative")
        line(
            f"tracks  ACT {active:<4} LOST {lost:<4} TENT {tent:<4}",
            (220, 255, 220),
            0.5,
        )
        line(f"dets   this frame: {len(item.detections):<6}", (220, 255, 220), 0.5)

        if self._async_detector is not None:
            y[0] += 8
            line("ASYNC DETECTOR", (180, 180, 220), 0.5)
            published = getattr(self._async_detector, "published_count", 0)
            submitted = getattr(self._async_detector, "submitted_count", 0)
            dropped = getattr(self._async_detector, "dropped_count", 0)
            worker_ms = getattr(self._async_detector, "last_worker_ms", 0.0)
            last_pub = getattr(self._async_detector, "last_published_frame_id", -1)
            staleness = max(0, item.id - last_pub) if last_pub >= 0 else -1
            line(
                f"submitted {submitted}  dropped {dropped}  published {published}",
                (220, 220, 220),
                0.45,
            )
            line(f"worker last: {worker_ms:.1f} ms", (220, 220, 220), 0.45)
            line(
                f"staleness: {staleness} frames",
                (255, 200, 200) if staleness > 5 else (220, 220, 220),
                0.5,
            )

        y[0] += 12
        line("[SPACE] pause  [→] step  [R] reset  [Q] quit", (160, 160, 160), 0.42)

        # Upload to SDL texture.
        cv2.cvtColor(self._buf_bgr, cv2.COLOR_BGR2BGRA, dst=self._buf_bgra)
        surf = self._pygame.image.frombuffer(self._buf_bgra.data, (self._w, self._h), "BGRA")
        self._texture.update(surf)
        self._renderer.clear()
        self._texture.draw()
        self._renderer.present()

    def _rolling_fps(self) -> float:
        if len(self._frame_times) < 2:
            return 0.0
        dt = self._frame_times[-1] - self._frame_times[0]
        if dt <= 0:
            return 0.0
        return (len(self._frame_times) - 1) / dt
