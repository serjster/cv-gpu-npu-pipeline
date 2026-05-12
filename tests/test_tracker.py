from __future__ import annotations

import asyncio
import time

import numpy as np
from numpy.typing import NDArray

from lowlatcv.config import TrackerConfig
from lowlatcv.models.frame import Detection, Frame, TrackState
from lowlatcv.pipeline.tracker import ByteTracker, from_config


def _frame(
    frame_id: int,
    detections: tuple[Detection, ...] = (),
) -> Frame:
    img: NDArray[np.uint8] = np.zeros((100, 100, 3), dtype=np.uint8)
    return Frame(
        id=frame_id,
        timestamp_ns=time.perf_counter_ns(),
        image=img,
        detections=detections,
    )


def _det(x: int, y: int, score: float = 0.9, cls: int = 0) -> Detection:
    return Detection(bbox=(x, y, x + 20, y + 20), score=score, class_id=cls)


def _run(tracker: ByteTracker, frames: list[Frame]) -> list[Frame]:
    async def go() -> list[Frame]:
        await tracker.setup()
        try:
            return [await tracker.process(f) for f in frames]
        finally:
            await tracker.teardown()

    return asyncio.run(go())


def test_track_id_persists_across_consecutive_matched_frames() -> None:
    cfg = TrackerConfig(iou_threshold=0.3, min_hits=1)
    tracker = ByteTracker(cfg)
    frames = [_frame(i, (_det(10 + i, 10 + i),)) for i in range(5)]
    out = _run(tracker, frames)
    ids = [f.tracks[0].track_id for f in out]
    assert len(set(ids)) == 1


def test_tentative_to_active_after_min_hits() -> None:
    cfg = TrackerConfig(iou_threshold=0.3, min_hits=3)
    tracker = ByteTracker(cfg)
    frames = [_frame(i, (_det(10 + i, 10),)) for i in range(5)]
    out = _run(tracker, frames)
    states = [f.tracks[0].state for f in out]
    # Frame 0: spawn → TENTATIVE.  Frames 1,2: hits=2,3 → TENTATIVE then ACTIVE.
    assert states[0] is TrackState.TENTATIVE
    assert states[1] is TrackState.TENTATIVE
    assert states[2] is TrackState.ACTIVE
    assert states[3] is TrackState.ACTIVE
    assert states[4] is TrackState.ACTIVE


def test_active_to_lost_after_max_age_unmatched_frames() -> None:
    cfg = TrackerConfig(iou_threshold=0.3, min_hits=1, max_age=3)
    tracker = ByteTracker(cfg)
    confirm = [_frame(i, (_det(10, 10),)) for i in range(2)]
    # 3 empty frames → frames_since_match reaches max_age=3 → LOST
    miss = [_frame(2 + i) for i in range(3)]
    out = _run(tracker, confirm + miss)
    assert out[1].tracks[0].state is TrackState.ACTIVE
    assert out[-1].tracks[0].state is TrackState.LOST
    # frames_since_match must equal max_age at the transition
    assert out[-1].tracks[0].frames_since_match == cfg.max_age


def test_lost_to_dead_after_extra_lost_age_frames_then_pruned() -> None:
    cfg = TrackerConfig(iou_threshold=0.3, min_hits=1, max_age=2, lost_age=2)
    tracker = ByteTracker(cfg)
    confirm = [_frame(i, (_det(10, 10),)) for i in range(2)]
    miss = [_frame(2 + i) for i in range(5)]  # plenty to exceed max_age + lost_age = 4
    out = _run(tracker, confirm + miss)
    # By the last frame the lane has been pruned (DEAD removed) → no tracks emitted
    assert out[-1].tracks == ()


def test_track_id_not_reused_after_dead() -> None:
    cfg = TrackerConfig(iou_threshold=0.3, min_hits=1, max_age=1, lost_age=1)
    tracker = ByteTracker(cfg)
    # Phase 1: confirm a track at (10, 10), then starve it until DEAD + pruned.
    seed = [_frame(0, (_det(10, 10),))]
    starve = [_frame(1 + i) for i in range(5)]
    # Phase 2: brand-new detection in a different region — must get a fresh id.
    new = [_frame(10, (_det(70, 70),))]
    out = _run(tracker, seed + starve + new)
    first_id = out[0].tracks[0].track_id
    assert out[-2].tracks == ()  # original is gone
    new_id = out[-1].tracks[0].track_id
    assert new_id != first_id
    assert new_id > first_id


def test_low_score_recovery_reassociates_unmatched_track() -> None:
    cfg = TrackerConfig(
        iou_threshold=0.3,
        min_hits=1,
        max_age=5,
        score_high_threshold=0.5,
    )
    tracker = ByteTracker(cfg)
    # Frame 0: high-score detection confirms the track.
    f0 = _frame(0, (_det(10, 10, score=0.9),))
    # Frame 1: only a low-score detection at the same place — should recover.
    f1 = _frame(1, (_det(11, 11, score=0.2),))
    out = _run(tracker, [f0, f1])
    assert out[0].tracks[0].track_id == out[1].tracks[0].track_id
    assert out[1].tracks[0].frames_since_match == 0


def test_tracker_factory_routes_by_backend() -> None:
    assert isinstance(from_config(TrackerConfig(backend="bytetrack")), ByteTracker)
    assert isinstance(from_config(TrackerConfig(backend="byte")), ByteTracker)
    import pytest

    with pytest.raises(ValueError, match="unknown tracker backend"):
        from_config(TrackerConfig(backend="kalman-mt"))
