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
import os
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
        # Counters exposed for the debug HUD.
        self._submitted_count = 0
        self._dropped_count = 0
        self._published_count = 0
        self._last_worker_ms: float = 0.0

    @property
    def submitted_count(self) -> int:
        return self._submitted_count

    @property
    def dropped_count(self) -> int:
        return self._dropped_count

    @property
    def published_count(self) -> int:
        return self._published_count

    @property
    def last_worker_ms(self) -> float:
        return self._last_worker_ms

    @property
    def last_published_frame_id(self) -> int:
        _, fid = self._store.get()
        return fid

    # Cold MIGraphX compile of a 1280-imgsz YOLO model takes ~40 s, and on
    # bigger / multi-shape graphs it can exceed a minute. 300 s gives the
    # cold path enough headroom; warm runs (cached .mxr in
    # $LOWLATCV_MIGRAPHX_CACHE or ~/.cache/lowlatcv/migraphx) complete in
    # ~1 s. Override via $LOWLATCV_DETECTOR_SETUP_TIMEOUT for slower SKUs.
    _SETUP_TIMEOUT_S = float(os.environ.get("LOWLATCV_DETECTOR_SETUP_TIMEOUT", "300"))

    async def setup(self) -> None:
        self._thread = threading.Thread(
            target=self._worker_loop, name="async-detector", daemon=True
        )
        self._thread.start()
        await asyncio.get_running_loop().run_in_executor(
            None, self._setup_done.wait, self._SETUP_TIMEOUT_S
        )
        if not self._setup_done.is_set():
            raise RuntimeError(f"AsyncDetector setup timed out after {self._SETUP_TIMEOUT_S:.0f}s")
        if self._setup_error is not None:
            raise self._setup_error

    async def process(self, item: Frame) -> Frame:
        if (self._submitted % self._every_n) == 0:
            self._submit(item)
        self._submitted += 1
        dets, _src_frame_id = self._store.get()
        # NOTE: re-emits the latest published set on every call. A previous
        # version deduplicated so each result was emitted once, but that
        # broke fast-moving tracks: by the time fresh detections arrived
        # (from worker source frame X), the tracker had Kalman-predicted
        # forward to frame T >> X, so predicted positions disagreed with
        # the stale measurement by velocity × (T-X) pixels. Stationary cars
        # matched; horizontal-highway cars did not. Proper fix is to rewind
        # Kalman state to the source frame before association — TODO.
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
        try:
            self._q.get_nowait()
            self._dropped_count += 1
        except queue.Empty:
            pass
        with contextlib.suppress(queue.Full):
            self._q.put_nowait(frame)
            self._submitted_count += 1

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
            self._published_count += 1
            self._last_worker_ms = dt
            log.debug(
                "AsyncDetector frame=%d dets=%d worker_ms=%.1f",
                item.id,
                len(out.detections),
                dt,
            )
