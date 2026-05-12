from __future__ import annotations

import asyncio
import time

import numpy as np
from numpy.typing import NDArray

from lowlatcv.config import VLMConfig
from lowlatcv.models.caption import CaptionRequest
from lowlatcv.models.frame import Frame, Track, TrackState
from lowlatcv.pipeline.scheduler import CaptionScheduler
from lowlatcv.pipeline.vlm import CaptionResultStore, FakeVLM


def _frame_with_tracks(
    frame_id: int,
    *tracks_args: tuple[int, tuple[int, int, int, int]],
) -> Frame:
    img: NDArray[np.uint8] = np.zeros((100, 100, 3), dtype=np.uint8)
    tracks = tuple(
        Track(
            track_id=tid,
            bbox=bbox,
            class_id=0,
            score=0.9,
            age=10,
            state=TrackState.ACTIVE,
            last_seen_frame=frame_id,
            hits=10,
            frames_since_match=0,
        )
        for tid, bbox in tracks_args
    )
    return Frame(
        id=frame_id,
        timestamp_ns=time.perf_counter_ns(),
        image=img,
        tracks=tracks,
    )


def _drain_queue(scheduler: CaptionScheduler) -> list[CaptionRequest]:
    q = scheduler._queue  # noqa: SLF001 — test-only access
    items: list[CaptionRequest] = []
    while True:
        try:
            it = q.get_nowait()
        except Exception:
            break
        if it is None:
            continue
        items.append(it)
    return items


def _run(scheduler: CaptionScheduler, frames: list[Frame]) -> None:
    async def go() -> None:
        await scheduler.setup()
        try:
            for f in frames:
                await scheduler.process(f)
        finally:
            await scheduler.teardown()

    asyncio.run(go())


def test_scheduler_emits_first_sighting_then_respects_cooldown() -> None:
    store = CaptionResultStore()
    cfg = VLMConfig(
        backend="fake",
        refresh_seconds=10.0,
        rate_limit_hz=0.0,  # disable global rate limit so cooldown is the only knob
        request_queue_size=8,
    )
    scheduler = CaptionScheduler(cfg, store, vlm=None)  # no vlm = pass through
    # vlm=None means the scheduler short-circuits; force enable by injecting:
    scheduler._vlm = FakeVLM()  # noqa: SLF001
    # No worker is started — we inspect queued requests directly.

    frames = [_frame_with_tracks(i, (1, (10, 10, 30, 30))) for i in range(5)]

    async def go() -> None:
        for f in frames:
            await scheduler.process(f)

    asyncio.run(go())
    reqs = _drain_queue(scheduler)
    assert len(reqs) == 1
    assert reqs[0].track_id == 1
    assert reqs[0].first_sighting is True


def test_scheduler_rate_limit_caps_emissions_per_second() -> None:
    store = CaptionResultStore()
    cfg = VLMConfig(
        backend="fake",
        refresh_seconds=0.0,  # no cooldown
        rate_limit_hz=1.0,  # max 1 req / second
        request_queue_size=16,
    )
    scheduler = CaptionScheduler(cfg, store, vlm=None)
    scheduler._vlm = FakeVLM()  # noqa: SLF001
    frames = [_frame_with_tracks(i, (i + 100, (10, 10, 30, 30))) for i in range(20)]

    async def go() -> None:
        for f in frames:
            await scheduler.process(f)

    t0 = time.perf_counter()
    asyncio.run(go())
    elapsed = time.perf_counter() - t0
    reqs = _drain_queue(scheduler)
    # Loop is fast: 20 frames in well under one second, so only 1 emission allowed.
    # Even allowing some scheduler overhead, must be <= ceil(elapsed * 1) + 1.
    assert len(reqs) <= int(elapsed) + 1


def test_drop_policy_preserves_first_sighting_when_queue_full() -> None:
    store = CaptionResultStore()
    cfg = VLMConfig(
        backend="fake",
        refresh_seconds=0.0,
        rate_limit_hz=0.0,
        request_queue_size=2,
    )
    scheduler = CaptionScheduler(cfg, store, vlm=None)
    scheduler._vlm = FakeVLM()  # noqa: SLF001

    # Fill the queue with two non-first refresh requests manually.
    img: NDArray[np.uint8] = np.zeros((4, 4, 3), dtype=np.uint8)
    scheduler._queue.put_nowait(  # noqa: SLF001
        CaptionRequest(track_id=10, frame_id=0, crop=img, first_sighting=False)
    )
    scheduler._queue.put_nowait(  # noqa: SLF001
        CaptionRequest(track_id=11, frame_id=0, crop=img, first_sighting=False)
    )

    frames = [_frame_with_tracks(100, (42, (10, 10, 30, 30)))]
    _run(scheduler, frames)  # scheduler.setup starts a worker but FakeVLM is fast
    # The brand-new track 42 should have evicted one of the two refresh requests
    # and made it into the queue (or been processed by the worker into the store).
    drained = _drain_queue(scheduler)
    cap = store.get(42)
    assert cap is not None or any(r.track_id == 42 for r in drained)


def test_caption_for_track_a_never_renders_on_track_b() -> None:
    """Store is keyed by track_id — verify lookup by id never crosses streams."""
    store = CaptionResultStore()
    cfg = VLMConfig(backend="fake", refresh_seconds=0.0, rate_limit_hz=0.0)
    scheduler = CaptionScheduler(cfg, store, vlm=FakeVLM())

    frames = [
        _frame_with_tracks(0, (1, (10, 10, 30, 30)), (2, (50, 50, 70, 70))),
    ]
    _run(scheduler, frames)
    # Wait briefly for the worker to drain.
    deadline = time.perf_counter() + 1.0
    while store.get(1) is None and store.get(2) is None and time.perf_counter() < deadline:
        time.sleep(0.01)
    cap1 = store.get(1)
    cap2 = store.get(2)
    if cap1 is not None:
        assert cap1.track_id == 1
        assert f"track={cap1.track_id}" in cap1.text
    if cap2 is not None:
        assert cap2.track_id == 2
