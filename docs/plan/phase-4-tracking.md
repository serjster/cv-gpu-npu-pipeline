# Phase 4 — Tracking

**Goal:** Cross-frame identity for detections so VLM captions can persist per object. Identity must survive brief occlusions. The tracker is the smallest CPU-bound stage on the critical path and the place where per-track state lives.

**Design patterns introduced:**

- **Strategy** — `Tracker` Protocol with multiple algorithms (start with one).
- **State pattern** — `Track.state` transitions `tentative → active → lost → dead`. Transitions encoded explicitly, not as ad-hoc booleans.
- **Adapter** — wrap an existing tracker library (`supervision`, `lap`, custom ByteTrack) behind the protocol; the rest of the pipeline never sees the library types.
- **Factory Method** — `Tracker.from_config(cfg.tracker)`.

**Tasks:**

- [ ] `src/lowlatcv/pipeline/tracker.py` — `Tracker` Protocol
- [ ] Extend `Track` with `state: TrackState`, `age: int`, `last_seen_frame: int`, `history: tuple[BBox, ...]`
- [ ] `TrackState` enum: `TENTATIVE`, `ACTIVE`, `LOST`, `DEAD`
- [ ] `ByteTracker` backend — IoU + low-score recovery; Kalman motion model optional
- [ ] `Tracker.from_config` Factory Method
- [ ] Wire `Detector → Tracker → Overlay`; overlay now draws `track_id` per box
- [ ] Test: ID persists across consecutive frames with overlapping detections (deterministic synthetic input)
- [ ] Test: state transitions `TENTATIVE → ACTIVE` after `min_hits` frames
- [ ] Test: `ACTIVE → LOST` when no match for `max_age` frames
- [ ] Test: `LOST → DEAD` after configurable timeout, no longer rendered
- [ ] Test: ID does not get reused when a track moves to `DEAD`

**Done when:** running on a fixture clip shows stable per-object IDs, the unit tests cover every state transition, and the overlay clearly distinguishes `ACTIVE` from `LOST` tracks (e.g. dashed box for `LOST`).
