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

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import linear_sum_assignment

from lowlatcv.config import TrackerConfig
from lowlatcv.models.frame import Detection, Frame, Track, TrackState
from lowlatcv.pipeline.tile_hints import TileHintBoard

log = logging.getLogger(__name__)


class Tracker(Protocol):
    name: str

    async def setup(self) -> None: ...
    async def process(self, item: Frame) -> Frame: ...
    async def teardown(self) -> None: ...


class _Kalman2D:
    """Position-only constant-velocity Kalman filter on an axis-aligned bbox.

    State vector: ``[cx, cy, w, h, vx, vy]`` (6-state). Observation:
    ``[cx, cy, w, h]`` (4-d). The previous 8-state version included
    velocities for ``w`` and ``h`` — that turns out to be a bad fit for
    aerial / top-down footage where box size is essentially constant
    between detections, and the filter would learn spurious size-velocity
    from noisy detections and then keep growing the box across LOST
    frames. Width / height are observed directly with no integration.

    Process and measurement covariances are scaled by box height so motion
    uncertainty is proportional to object size (classic SORT/DeepSORT
    trick). Initial velocity variance is moderate (100, not 1e4) so the
    filter doesn't over-trust the first noisy measurement and let velocity
    spike.

    Velocity magnitude is clamped after each predict to keep a track from
    flying off when it has been LOST for many frames. ``freeze_velocity()``
    is called by the tracker when a lane transitions to LOST so the
    extrapolation stays put rather than running away.
    """

    __slots__ = ("x", "P", "_F", "_H", "_Q_scale", "_R_scale", "_max_speed_px")

    def __init__(
        self,
        cx: float,
        cy: float,
        w: float,
        h: float,
        max_speed_px: float = 50.0,
    ) -> None:
        self.x: NDArray[np.float64] = np.array(
            [cx, cy, w, h, 0.0, 0.0], dtype=np.float64
        )
        # position uncertainty moderate, velocity uncertainty bounded (was 1e4)
        # so the filter doesn't latch onto the first noisy measurement and
        # invent a velocity that compounds.
        self.P: NDArray[np.float64] = np.diag([10.0, 10.0, 10.0, 10.0, 100.0, 100.0])
        # transition: cx += vx, cy += vy; w, h held constant.
        self._F: NDArray[np.float64] = np.eye(6, dtype=np.float64)
        self._F[0, 4] = 1.0
        self._F[1, 5] = 1.0
        # observation matrix: cx, cy, w, h directly observed (no velocity obs).
        self._H: NDArray[np.float64] = np.zeros((4, 6), dtype=np.float64)
        for i in range(4):
            self._H[i, i] = 1.0
        self._Q_scale: float = 1.0 / 20.0
        self._R_scale: float = 1.0 / 20.0
        self._max_speed_px: float = max_speed_px

    def predict(self) -> None:
        self.x = self._F @ self.x
        # clamp velocity magnitude — prevents runaway extrapolation under
        # long LOST gaps with no measurement to correct.
        speed = float(np.hypot(self.x[4], self.x[5]))
        if speed > self._max_speed_px:
            scale = self._max_speed_px / speed
            self.x[4] *= scale
            self.x[5] *= scale
        h_scale = max(self.x[3], 1.0)
        q_pos = (self._Q_scale * h_scale) ** 2
        q_size = (self._Q_scale * h_scale * 0.2) ** 2  # box size barely drifts
        q_vel = (self._Q_scale * h_scale * 0.5) ** 2
        Q = np.diag([q_pos, q_pos, q_size, q_size, q_vel, q_vel])
        self.P = self._F @ self.P @ self._F.T + Q

    def update(self, cx: float, cy: float, w: float, h: float) -> None:
        z = np.array([cx, cy, w, h], dtype=np.float64)
        h_scale = max(self.x[3], 1.0)
        R = np.diag([(self._R_scale * h_scale) ** 2] * 4)
        y = z - self._H @ self.x
        S = self._H @ self.P @ self._H.T + R
        K = self.P @ self._H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        I_KH = np.eye(6, dtype=np.float64) - K @ self._H
        self.P = I_KH @ self.P

    def freeze_velocity(self) -> None:
        """Zero the velocity components — call when a track goes LOST so its
        predicted bbox stops moving instead of running away into the void."""
        self.x[4] = 0.0
        self.x[5] = 0.0

    def soft_update(self, cx: float, cy: float, w: float, h: float) -> None:
        """Snap the bbox position and size to the measurement without letting
        the filter infer a new velocity from the residual.

        Used for low-confidence association passes (e.g. centroid-distance
        match for a fast-moving object): the position and size jump to the
        measurement, but the velocity stays at its previous (predicted) value
        so a single noisy / wrong match can't slam the box into a new
        trajectory. Reduces ``P`` for the observed states modestly so a
        subsequent full update can still adjust velocity.
        """
        self.x[0] = cx
        self.x[1] = cy
        self.x[2] = w
        self.x[3] = h
        # Shrink position/size covariance to reflect the fresh observation
        # without crediting it as a high-confidence Kalman update.
        for i in range(4):
            self.P[i, i] = min(self.P[i, i], 20.0)

    def bbox_xyxy(self) -> tuple[int, int, int, int]:
        cx, cy, w, h = self.x[:4]
        x1 = int(round(cx - w / 2))
        y1 = int(round(cy - h / 2))
        x2 = int(round(cx + w / 2))
        y2 = int(round(cy + h / 2))
        return x1, y1, x2, y2


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
    kalman: _Kalman2D
    history: list[tuple[int, int, int, int]] = field(default_factory=list)


class ByteTracker:
    """Greedy-IoU two-pass associator with explicit State-pattern lifecycle."""

    name = "tracker"

    def __init__(
        self,
        cfg: TrackerConfig | None = None,
        hint_board: TileHintBoard | None = None,
    ) -> None:
        self._cfg = cfg or TrackerConfig()
        self._hint_board = hint_board
        self._lanes: list[_Lane] = []
        self._next_id = 1
        self._frame_idx = -1

    async def setup(self) -> None: ...

    async def process(self, item: Frame) -> Frame:
        self._frame_idx += 1

        # Kalman predict step: roll every live lane forward by one frame so
        # association uses the *expected* position, not the stale last
        # observation. Tracks survive gaps without detection because their
        # predicted bbox is what downstream stages read.
        for lane in self._lanes:
            if lane.state is TrackState.DEAD:
                continue
            lane.kalman.predict()
            lane.bbox = lane.kalman.bbox_xyxy()

        # No detections this frame means the upstream stage has nothing fresh
        # to associate (e.g. AsyncDetector deduplicated its stale published
        # set). Treating that as "every track missed" would burn frames_since_match
        # and force tracks LOST/DEAD between async publications. Instead skip
        # association entirely — predict-only, no transitions toward LOST,
        # but still emit snapshots so downstream stages see the rolled-forward
        # bboxes.
        if not item.detections:
            snapshots = tuple(self._snapshot(lane) for lane in self._lanes)
            return dataclasses.replace(item, tracks=snapshots)

        dets = list(item.detections)
        high = [d for d in dets if d.score >= self._cfg.score_high_threshold]
        low = [d for d in dets if d.score < self._cfg.score_high_threshold]

        live = [lane for lane in self._lanes if lane.state is not TrackState.DEAD]

        matches_high, unmatched_live_idx, unmatched_high_idx = _hungarian_iou_match(
            [lane.bbox for lane in live],
            [lane.class_id for lane in live],
            [d.bbox for d in high],
            [d.class_id for d in high],
            iou_threshold=self._cfg.iou_threshold,
        )
        for li, di in matches_high:
            self._on_match(live[li], high[di])

        # Second pass: low-score detections recover unmatched live tracks.
        recover_lanes = [live[i] for i in unmatched_live_idx]
        matches_low, still_unmatched_idx, _ = _hungarian_iou_match(
            [lane.bbox for lane in recover_lanes],
            [lane.class_id for lane in recover_lanes],
            [d.bbox for d in low],
            [d.class_id for d in low],
            iou_threshold=self._cfg.iou_threshold,
        )
        for li, di in matches_low:
            self._on_match(recover_lanes[li], low[di])

        # Third pass: distance-based fallback for fast objects whose Kalman
        # prediction has zero (or stale) velocity — the predicted bbox does
        # not overlap the new measurement, so IoU is 0 even though the
        # detection clearly belongs to this track. Match by centroid
        # distance gated by predicted bbox size; require class agreement so
        # a moving car doesn't snap onto a stationary truck nearby.
        still_unmatched_after_motion: list[int] = list(still_unmatched_idx)
        if self._cfg.motion_distance_factor > 0 and unmatched_high_idx:
            motion_lanes = [recover_lanes[i] for i in still_unmatched_idx]
            motion_dets = [high[i] for i in unmatched_high_idx]
            motion_matches, leftover_motion_lane_idx, leftover_motion_det_idx = (
                _greedy_match_by_distance(
                    [lane.bbox for lane in motion_lanes],
                    [lane.class_id for lane in motion_lanes],
                    [d.bbox for d in motion_dets],
                    [d.class_id for d in motion_dets],
                    distance_factor=self._cfg.motion_distance_factor,
                )
            )
            for li, di in motion_matches:
                # Soft update — distance-only matches are low confidence; let
                # the position snap to the measurement but don't infer a new
                # velocity from the large residual (else the box "ejects" on
                # the next predict).
                self._on_match(motion_lanes[li], motion_dets[di], soft=True)
            still_unmatched_after_motion = [
                still_unmatched_idx[i] for i in leftover_motion_lane_idx
            ]
            unmatched_high_idx = [unmatched_high_idx[i] for i in leftover_motion_det_idx]

        for li in still_unmatched_after_motion:
            self._on_miss(recover_lanes[li])

        for lane in self._lanes:
            self._transition(lane)

        # Spawn TENTATIVE tracks for unmatched high-score detections.
        for di in unmatched_high_idx:
            self._spawn(high[di])

        self._lanes = [lane for lane in self._lanes if lane.state is not TrackState.DEAD]

        # Tell the tiled detector which regions still need attention. LOST and
        # TENTATIVE lanes are the ones a future inference cycle should re-cover.
        if self._hint_board is not None:
            self._hint_board.update_recovery_bboxes(
                [
                    lane.bbox
                    for lane in self._lanes
                    if lane.state is TrackState.LOST or lane.state is TrackState.TENTATIVE
                ]
            )

        snapshots = tuple(self._snapshot(lane) for lane in self._lanes)
        return dataclasses.replace(item, tracks=snapshots)

    async def teardown(self) -> None: ...

    def _on_match(self, lane: _Lane, det: Detection, soft: bool = False) -> None:
        cx, cy, w, h = _xyxy_to_cxcywh(det.bbox)
        if soft:
            lane.kalman.soft_update(cx, cy, w, h)
        else:
            lane.kalman.update(cx, cy, w, h)
        lane.bbox = lane.kalman.bbox_xyxy()
        lane.class_id = det.class_id
        lane.score = det.score
        lane.hits += 1
        lane.frames_since_match = 0
        lane.last_seen_frame = self._frame_idx
        lane.age += 1
        lane.history.append(lane.bbox)
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
                # Freeze position once we lose sight — extrapolation is more
                # likely to mislead than help over long gaps.
                lane.kalman.freeze_velocity()
        elif lane.state is TrackState.LOST:
            if lane.frames_since_match == 0:
                lane.state = TrackState.ACTIVE
            elif lane.frames_since_match >= self._cfg.max_age + self._cfg.lost_age:
                lane.state = TrackState.DEAD

    def _spawn(self, det: Detection) -> None:
        cx, cy, w, h = _xyxy_to_cxcywh(det.bbox)
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
            kalman=_Kalman2D(cx, cy, w, h),
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


def _xyxy_to_cxcywh(b: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = b
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0, float(x2 - x1), float(y2 - y1))


def _hungarian_iou_match(
    track_bboxes: list[tuple[int, int, int, int]],
    track_classes: list[int],
    det_bboxes: list[tuple[int, int, int, int]],
    det_classes: list[int],
    iou_threshold: float,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Class-aware Hungarian IoU matching.

    Cost = ``1 - IoU`` for pairs that share a class AND have IoU above
    ``iou_threshold``; ``INF`` otherwise so the solver cannot pick them.
    Hungarian assignment then minimises total cost over all feasible
    pairings — better than greedy "best-pair-first" in dense clusters where
    a single high-IoU match can rob an adjacent track of its only candidate.
    Class agreement prevents a car track from snapping onto an overlapping
    truck detection (and the subsequent Kalman.update from inferring phantom
    velocity from the wrong target — the classic "ejection" symptom).
    """
    if not track_bboxes or not det_bboxes:
        return [], list(range(len(track_bboxes))), list(range(len(det_bboxes)))
    nt = len(track_bboxes)
    nd = len(det_bboxes)
    INF = 1e6
    cost = np.full((nt, nd), INF, dtype=np.float64)
    for ti, tb in enumerate(track_bboxes):
        tcls = track_classes[ti]
        for di, db in enumerate(det_bboxes):
            if det_classes[di] != tcls:
                continue
            iou = _iou_xyxy(tb, db)
            if iou >= iou_threshold:
                cost[ti, di] = 1.0 - iou
    row_idx, col_idx = linear_sum_assignment(cost)
    matches: list[tuple[int, int]] = []
    used_t: set[int] = set()
    used_d: set[int] = set()
    for ti, di in zip(row_idx, col_idx, strict=False):
        if cost[ti, di] >= INF:
            continue
        matches.append((int(ti), int(di)))
        used_t.add(int(ti))
        used_d.add(int(di))
    unmatched_t = [i for i in range(nt) if i not in used_t]
    unmatched_d = [i for i in range(nd) if i not in used_d]
    return matches, unmatched_t, unmatched_d


def _greedy_match_by_distance(
    track_bboxes: list[tuple[int, int, int, int]],
    track_classes: list[int],
    det_bboxes: list[tuple[int, int, int, int]],
    det_classes: list[int],
    distance_factor: float,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Greedy centroid-distance matching, gated by predicted bbox size and class.

    Used as the fallback pass when IoU is 0 because a fast-moving object has
    outpaced the Kalman prediction. A pair is a candidate iff the detection
    centroid sits within ``distance_factor * max(predicted_w, predicted_h)``
    of the track centroid AND they share a class. Sorted by smallest distance.
    """
    if not track_bboxes or not det_bboxes:
        return [], list(range(len(track_bboxes))), list(range(len(det_bboxes)))
    pairs: list[tuple[float, int, int]] = []
    for ti, tb in enumerate(track_bboxes):
        tcx = (tb[0] + tb[2]) / 2.0
        tcy = (tb[1] + tb[3]) / 2.0
        tw = max(1.0, tb[2] - tb[0])
        th = max(1.0, tb[3] - tb[1])
        gate = distance_factor * max(tw, th)
        for di, db in enumerate(det_bboxes):
            if track_classes[ti] != det_classes[di]:
                continue
            dcx = (db[0] + db[2]) / 2.0
            dcy = (db[1] + db[3]) / 2.0
            dist = ((dcx - tcx) ** 2 + (dcy - tcy) ** 2) ** 0.5
            if dist <= gate:
                pairs.append((dist, ti, di))
    pairs.sort()  # smallest distance first
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


def from_config(
    cfg: TrackerConfig,
    hint_board: TileHintBoard | None = None,
) -> Tracker:
    """Factory Method: select a tracker backend from ``TrackerConfig.backend``."""
    backend = cfg.backend.lower()
    if backend in ("bytetrack", "byte"):
        return ByteTracker(cfg, hint_board=hint_board)
    raise ValueError(f"unknown tracker backend: {cfg.backend}")


if not TYPE_CHECKING:
    Tracker.from_config = staticmethod(from_config)
