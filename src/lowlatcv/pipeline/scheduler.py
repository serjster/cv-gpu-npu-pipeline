"""``CaptionScheduler`` stage — bridge from per-frame critical path to VLM worker.

Sits between ``Tracker`` and ``Overlay``. For each frame it inspects
``Frame.tracks``, applies a per-track cooldown plus a global rate limit,
crops the original image at the track bbox, builds a ``CaptionRequest``
Command and submits it to the VLM worker's bounded queue with
``put_nowait``. The frame is passed through unchanged. Drop policy on
``queue.Full``: try to evict a non-first-sighting request to make room
for a first-sighting one, so a new-track caption is never starved by a
backlog of refresh requests. Critical-path stages never ``await`` the
VLM and never block on this queue.
"""

from __future__ import annotations

import logging
import queue
import time

from lowlatcv.config import VLMConfig
from lowlatcv.models.caption import CaptionRequest
from lowlatcv.models.frame import Frame, TrackState
from lowlatcv.pipeline.vlm import VLM, CaptionResultStore, VLMWorker

log = logging.getLogger(__name__)


class CaptionScheduler:
    """Per-frame stage that emits at most one VLM request per frame.

    Owns the VLM worker's lifecycle: worker is started in ``setup`` and
    joined in ``teardown`` so the pipeline orchestrator does not need to
    know about background threads.
    """

    name = "caption_scheduler"

    def __init__(
        self,
        cfg: VLMConfig,
        store: CaptionResultStore,
        vlm: VLM | None = None,
    ) -> None:
        self._cfg = cfg
        self._store = store
        self._vlm = vlm
        self._queue: queue.Queue[CaptionRequest | None] = queue.Queue(
            maxsize=max(1, cfg.request_queue_size)
        )
        self._worker: VLMWorker | None = None
        self._cooldown_ns = int(cfg.refresh_seconds * 1e9)
        self._min_emit_interval_ns = int(1e9 / cfg.rate_limit_hz) if cfg.rate_limit_hz > 0 else 0
        self._last_request_ns: dict[int, int] = {}
        self._last_emit_ns = 0
        self._seen_tracks: set[int] = set()

    async def setup(self) -> None:
        if self._vlm is None:
            return
        await self._vlm.setup()
        self._worker = VLMWorker(self._vlm, self._store, self._queue)
        self._worker.start()

    async def process(self, item: Frame) -> Frame:
        if self._vlm is None or not item.tracks:
            return item
        now = time.perf_counter_ns()
        if self._min_emit_interval_ns and (now - self._last_emit_ns) < self._min_emit_interval_ns:
            return item
        for tr in item.tracks:
            if tr.state is not TrackState.ACTIVE:
                continue
            tid = tr.track_id
            first = tid not in self._seen_tracks
            if not first:
                last = self._last_request_ns.get(tid)
                if last is not None and (now - last) < self._cooldown_ns:
                    continue
            crop = _crop_bbox(item, tr.bbox)
            if crop is None:
                continue
            req = CaptionRequest(
                track_id=tid,
                frame_id=item.id,
                crop=crop,
                prompt=self._cfg.prompt,
                first_sighting=first,
                submitted_ns=now,
            )
            if self._enqueue(req):
                self._seen_tracks.add(tid)
                self._last_request_ns[tid] = now
                self._last_emit_ns = now
            break  # one request per frame respects the rate limit
        return item

    async def teardown(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self._worker = None
        if self._vlm is not None:
            await self._vlm.teardown()

    def _enqueue(self, req: CaptionRequest) -> bool:
        try:
            self._queue.put_nowait(req)
            return True
        except queue.Full:
            if not req.first_sighting:
                return False
            return self._evict_non_first_and_put(req)

    def _evict_non_first_and_put(self, req: CaptionRequest) -> bool:
        """Drop one non-first-sighting request from the queue (if any) and re-queue
        the rest. If all queued requests are first-sighting, give up — the new
        first-sighting request is dropped instead of evicting another first-sighter."""
        drained: list[CaptionRequest] = []
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is None:
                continue
            drained.append(item)
        evicted = False
        kept: list[CaptionRequest] = []
        for it in drained:
            if not evicted and not it.first_sighting:
                evicted = True
                continue
            kept.append(it)
        for it in kept:
            try:
                self._queue.put_nowait(it)
            except queue.Full:
                break
        if not evicted:
            return False
        try:
            self._queue.put_nowait(req)
            return True
        except queue.Full:
            return False


def _crop_bbox(item: Frame, bbox: tuple[int, int, int, int]) -> object | None:
    h, w = item.image.shape[:2]
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(x1, w))
    x2 = max(0, min(x2, w))
    y1 = max(0, min(y1, h))
    y2 = max(0, min(y2, h))
    if x2 <= x1 or y2 <= y1:
        return None
    return item.image[y1:y2, x1:x2].copy()
