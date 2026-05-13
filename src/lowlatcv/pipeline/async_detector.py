"""Async detector wrapper: runs an inner Detector on a worker thread.

The per-frame critical path stays cheap — ``process`` submits the current
frame to a bounded queue (with drop-oldest policy so the worker always
sees the freshest frame), then returns the same frame stamped with the
*latest available* detections from the worker's thread-safe result store.
Tracker downstream is expected to Kalman-propagate positions between
detection updates.

Pattern mirrors the VLM async stage (Command + Producer-Consumer +
shared latest-result map) but for the detector. Same Strategy
Protocol — any ``Detector`` can be wrapped behind this.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import queue
import threading
import time
from typing import Any

from lowlatcv.models.frame import Detection, Frame
from lowlatcv.pipeline.detector import Detector

log = logging.getLogger(__name__)


class _DetectionLatest:
    """Thread-safe holder for the latest detection result."""

    def __init__(self) -> None:
        self._dets: tuple[Detection, ...] = ()
        self._frame_id: int = -1
        self._lock = threading.Lock()

    def get(self) -> tuple[tuple[Detection, ...], int]:
        with self._lock:
            return self._dets, self._frame_id

    def put(self, dets: tuple[Detection, ...], frame_id: int) -> None:
        with self._lock:
            self._dets = dets
            self._frame_id = frame_id


class AsyncDetector:
    """Wraps any ``Detector`` behind a daemon worker thread.

    - ``setup`` spawns the worker, which runs the inner detector's own
      async setup on its own event loop. Inference state (the ONNX
      session etc.) is therefore owned by the worker thread.
    - ``process`` submits the current frame at the configured cadence
      with a drop-oldest policy (worker always sees the freshest frame),
      then attaches the latest detections from the shared store and
      returns immediately.
    - ``teardown`` signals stop, drains, joins the thread.
    """

    name = "detector"

    def __init__(self, inner: Detector, detect_every_n: int = 1) -> None:
        if detect_every_n < 1:
            raise ValueError("detect_every_n must be >= 1")
        self._inner = inner
        self._every_n = detect_every_n
        self._store = _DetectionLatest()
        # Single-slot queue: we always want the most recent frame, not a backlog.
        self._q: queue.Queue[Frame | None] = queue.Queue(maxsize=1)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._submitted = 0
        # Last source frame_id that we *emitted* downstream. Used to dedup —
        # the store keeps the latest worker result and would otherwise be
        # re-emitted on every process() call; the tracker would then
        # repeatedly Kalman.update with a stale measurement, dragging
        # tracks backward and producing the "trail" / phantom-velocity
        # artifacts.
        self._last_emitted_src_frame_id = -1
        self._setup_done = threading.Event()
        self._setup_error: BaseException | None = None

    async def setup(self) -> None:
        self._thread = threading.Thread(
            target=self._worker_loop, name="async-detector", daemon=True
        )
        self._thread.start()
        await asyncio.get_running_loop().run_in_executor(None, self._setup_done.wait, 60.0)
        if not self._setup_done.is_set():
            raise RuntimeError("AsyncDetector setup timed out")
        if self._setup_error is not None:
            raise self._setup_error

    async def process(self, item: Frame) -> Frame:
        if (self._submitted % self._every_n) == 0:
            self._submit(item)
        self._submitted += 1
        dets, src_frame_id = self._store.get()
        # Emit fresh detections exactly once per worker publication. Once
        # consumed, subsequent process() calls return empty detections so
        # the tracker downstream only runs Kalman.predict (no update from
        # a stale measurement).
        if src_frame_id == self._last_emitted_src_frame_id:
            return dataclasses.replace(item, detections=())
        self._last_emitted_src_frame_id = src_frame_id
        return dataclasses.replace(item, detections=dets)

    async def teardown(self) -> None:
        self._stop.set()
        with contextlib.suppress(queue.Full):
            self._q.put_nowait(None)
        if self._thread is not None:
            await asyncio.get_running_loop().run_in_executor(None, self._thread.join, 5.0)
            self._thread = None

    def _submit(self, frame: Frame) -> None:
        # Drop-oldest: if a stale frame is still queued, kick it out so the
        # worker picks up the freshest one when it becomes ready.
        with contextlib.suppress(queue.Empty):
            self._q.get_nowait()
        with contextlib.suppress(queue.Full):
            self._q.put_nowait(frame)

    def _worker_loop(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._inner.setup())
            except BaseException as e:  # noqa: BLE001 — propagate via _setup_error
                self._setup_error = e
                self._setup_done.set()
                return
            self._setup_done.set()
            self._drain_loop(loop)
            with contextlib.suppress(Exception):
                loop.run_until_complete(self._inner.teardown())
        finally:
            loop.close()

    def _drain_loop(self, loop: Any) -> None:
        while not self._stop.is_set():
            try:
                item = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                return
            t0 = time.perf_counter()
            try:
                out = loop.run_until_complete(self._inner.process(item))
            except Exception:
                log.exception("AsyncDetector worker error frame=%d", item.id)
                continue
            dt = (time.perf_counter() - t0) * 1000
            self._store.put(out.detections, item.id)
            log.debug(
                "AsyncDetector frame=%d dets=%d worker_ms=%.1f",
                item.id,
                len(out.detections),
                dt,
            )
