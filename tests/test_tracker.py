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
    # Frames that DO carry detections but at a far-away non-matching position —
    # these count as misses (the upstream looked and didn't see this track).
    # Empty-detection frames are "no observation" and skip association entirely,
    # so we use a decoy detection to exercise the unmatched path.
    miss = [_frame(2 + i, (_det(900, 900),)) for i in range(3)]
    out = _run(tracker, confirm + miss)
    assert out[1].tracks[0].state is TrackState.ACTIVE
    # Find the original track (id=1) in the final frame.
    lost = next((t for t in out[-1].tracks if t.track_id == 1), None)
    assert lost is not None
    assert lost.state is TrackState.LOST
    assert lost.frames_since_match == cfg.max_age


def test_lost_to_dead_after_extra_lost_age_frames_then_pruned() -> None:
    cfg = TrackerConfig(iou_threshold=0.3, min_hits=1, max_age=2, lost_age=2)
    tracker = ByteTracker(cfg)
    confirm = [_frame(i, (_det(10, 10),)) for i in range(2)]
    miss = [_frame(2 + i, (_det(900, 900),)) for i in range(5)]
    out = _run(tracker, confirm + miss)
    # Original (id=1) is gone; only the decoy's track (id=2) survives.
    track_ids = {t.track_id for t in out[-1].tracks}
    assert 1 not in track_ids


def test_track_id_not_reused_after_dead() -> None:
    cfg = TrackerConfig(iou_threshold=0.3, min_hits=1, max_age=1, lost_age=1)
    tracker = ByteTracker(cfg)
    # Phase 1: confirm a track at (10, 10), then starve it (with a decoy
    # detection elsewhere) until DEAD + pruned.
    seed = [_frame(0, (_det(10, 10),))]
    starve = [_frame(1 + i, (_det(900, 900),)) for i in range(5)]
    new = [_frame(10, (_det(70, 70),))]
    out = _run(tracker, seed + starve + new)
    first_id = out[0].tracks[0].track_id
    new_track = next(
        (t for t in out[-1].tracks if abs(t.bbox[0] - 70) < 5), None
    )
    assert new_track is not None
    assert new_track.track_id != first_id
    assert new_track.track_id > first_id


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
