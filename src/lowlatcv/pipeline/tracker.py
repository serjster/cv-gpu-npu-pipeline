"""Multi-object tracker stage: ``Tracker`` Protocol + ByteTrack-style backend + factory.

``Tracker.process`` consumes a ``Frame`` carrying ``detections`` and returns
the same Frame with ``tracks`` populated. The default backend is a small
in-tree implementation of the BYTE association idea (no Kalman): high-score
detections are associated to all live tracks via greedy IoU matching, then
low-score detections recover unmatched tracks. The lifecycle is encoded
with the State pattern via ``TrackState``: ``TENTATIVE → ACTIVE`` after
``min_hits`` consecutive matches, ``ACTIVE → LOST`` after ``max_age``
unmatched frames, ``LOST → DEAD`` after a further ``lost_age`` unmatched
frames; ``DEAD`` tracks are pruned and their IDs are never reused.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from lowlatcv.config import TrackerConfig
from lowlatcv.models.frame import Detection, Frame, Track, TrackState

log = logging.getLogger(__name__)


class Tracker(Protocol):
    name: str

    async def setup(self) -> None: ...
    async def process(self, item: Frame) -> Frame: ...
    async def teardown(self) -> None: ...


@dataclass(slots=True)
class _Lane:
    """Mutable per-track state owned internally by the tracker.

    Snapshotted into an immutable ``Track`` whenever a frame is emitted so
    nothing downstream ever sees the mutable view.
    """

    track_id: int
    bbox: tuple[int, int, int, int]
    class_id: int
    score: float
    age: int
    state: TrackState
    hits: int
    frames_since_match: int
    last_seen_frame: int
    history: list[tuple[int, int, int, int]] = field(default_factory=list)


class ByteTracker:
    """Greedy-IoU two-pass associator with explicit State-pattern lifecycle."""

    name = "tracker"

    def __init__(self, cfg: TrackerConfig | None = None) -> None:
        self._cfg = cfg or TrackerConfig()
        self._lanes: list[_Lane] = []
        self._next_id = 1
        self._frame_idx = -1

    async def setup(self) -> None: ...

    async def process(self, item: Frame) -> Frame:
        self._frame_idx += 1
        dets = list(item.detections)
        high = [d for d in dets if d.score >= self._cfg.score_high_threshold]
        low = [d for d in dets if d.score < self._cfg.score_high_threshold]

        live = [lane for lane in self._lanes if lane.state is not TrackState.DEAD]

        matches_high, unmatched_live_idx, unmatched_high_idx = _greedy_match(
            [lane.bbox for lane in live],
            [d.bbox for d in high],
            self._cfg.iou_threshold,
        )
        for li, di in matches_high:
            self._on_match(live[li], high[di])

        # Second pass: low-score detections recover unmatched live tracks.
        recover_lanes = [live[i] for i in unmatched_live_idx]
        matches_low, still_unmatched_idx, _ = _greedy_match(
            [lane.bbox for lane in recover_lanes],
            [d.bbox for d in low],
            self._cfg.iou_threshold,
        )
        for li, di in matches_low:
            self._on_match(recover_lanes[li], low[di])

        for li in still_unmatched_idx:
            self._on_miss(recover_lanes[li])

        for lane in self._lanes:
            self._transition(lane)

        # Spawn TENTATIVE tracks for unmatched high-score detections.
        for di in unmatched_high_idx:
            self._spawn(high[di])

        self._lanes = [lane for lane in self._lanes if lane.state is not TrackState.DEAD]

        snapshots = tuple(self._snapshot(lane) for lane in self._lanes)
        return dataclasses.replace(item, tracks=snapshots)

    async def teardown(self) -> None: ...

    def _on_match(self, lane: _Lane, det: Detection) -> None:
        lane.bbox = det.bbox
        lane.class_id = det.class_id
        lane.score = det.score
        lane.hits += 1
        lane.frames_since_match = 0
        lane.last_seen_frame = self._frame_idx
        lane.age += 1
        lane.history.append(det.bbox)
        if len(lane.history) > self._cfg.history_size:
            del lane.history[0]

    def _on_miss(self, lane: _Lane) -> None:
        lane.frames_since_match += 1
        lane.age += 1

    def _transition(self, lane: _Lane) -> None:
        if lane.state is TrackState.TENTATIVE:
            if lane.frames_since_match > 0:
                lane.state = TrackState.DEAD
            elif lane.hits >= self._cfg.min_hits:
                lane.state = TrackState.ACTIVE
        elif lane.state is TrackState.ACTIVE:
            if lane.frames_since_match >= self._cfg.max_age:
                lane.state = TrackState.LOST
        elif lane.state is TrackState.LOST:
            if lane.frames_since_match == 0:
                lane.state = TrackState.ACTIVE
            elif lane.frames_since_match >= self._cfg.max_age + self._cfg.lost_age:
                lane.state = TrackState.DEAD

    def _spawn(self, det: Detection) -> None:
        lane = _Lane(
            track_id=self._next_id,
            bbox=det.bbox,
            class_id=det.class_id,
            score=det.score,
            age=1,
            state=TrackState.TENTATIVE,
            hits=1,
            frames_since_match=0,
            last_seen_frame=self._frame_idx,
            history=[det.bbox],
        )
        self._next_id += 1
        self._lanes.append(lane)

    def _snapshot(self, lane: _Lane) -> Track:
        return Track(
            track_id=lane.track_id,
            bbox=lane.bbox,
            class_id=lane.class_id,
            score=lane.score,
            age=lane.age,
            state=lane.state,
            last_seen_frame=lane.last_seen_frame,
            hits=lane.hits,
            frames_since_match=lane.frames_since_match,
            history=tuple(lane.history),
        )


def _greedy_match(
    track_bboxes: list[tuple[int, int, int, int]],
    det_bboxes: list[tuple[int, int, int, int]],
    iou_threshold: float,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Greedy IoU matching. Returns (matches, unmatched_track_idxs, unmatched_det_idxs)."""
    if not track_bboxes or not det_bboxes:
        return [], list(range(len(track_bboxes))), list(range(len(det_bboxes)))
    pairs: list[tuple[float, int, int]] = []
    for ti, tb in enumerate(track_bboxes):
        for di, db in enumerate(det_bboxes):
            iou = _iou_xyxy(tb, db)
            if iou >= iou_threshold:
                pairs.append((iou, ti, di))
    pairs.sort(reverse=True)
    used_t: set[int] = set()
    used_d: set[int] = set()
    matches: list[tuple[int, int]] = []
    for _, ti, di in pairs:
        if ti in used_t or di in used_d:
            continue
        matches.append((ti, di))
        used_t.add(ti)
        used_d.add(di)
    unmatched_t = [i for i in range(len(track_bboxes)) if i not in used_t]
    unmatched_d = [i for i in range(len(det_bboxes)) if i not in used_d]
    return matches, unmatched_t, unmatched_d


def _iou_xyxy(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def from_config(cfg: TrackerConfig) -> Tracker:
    """Factory Method: select a tracker backend from ``TrackerConfig.backend``."""
    backend = cfg.backend.lower()
    if backend in ("bytetrack", "byte"):
        return ByteTracker(cfg)
    raise ValueError(f"unknown tracker backend: {cfg.backend}")


if not TYPE_CHECKING:
    Tracker.from_config = staticmethod(from_config)
