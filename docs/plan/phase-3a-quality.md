# Phase 3a — Detection & tracking quality (interleaved with phases 3, 4, 9)

**Goal:** A cluster of refinements that fell out of testing on real 4K aerial
footage (`data/b3d/videos/hwy00.mp4`). Not a clean separate phase — these
land while phases 3 (detection) and 4 (tracking) are nominally closed and
phase 9 (perf) is unopened. Keeping the work captured here so plan.md is
honest about reality.

## Done

### Detection

- [x] Switch off COCO weights for aerial scale — they max at ~0.1 confidence on
      hwy00. Use VisDrone-trained YOLOv8n (`mshamrai/yolov8n-visdrone`) at
      `imgsz=1280` as the default for this footage class.
- [x] Tiled inference (SAHI-style): new `TiledOnnxDetector` backend slices
      the frame into ROWSxCOLS overlapping tiles. CoreML EP is shape-locked
      to the export imgsz; auto-snap `tile_input_size` to the model's
      fixed imgsz to prevent silent runtime failures.
- [x] Tile-on-demand: tracker emits hint bboxes (LOST + TENTATIVE lanes)
      into a shared `TileHintBoard`; tiled detector runs only those tiles
      plus a rotating refresh tile each cycle. Per-tile detection cache so
      aggregate output stays full-frame even when the cycle is sparse.
- [x] Async detector: `AsyncDetector` wraps any base detector on a daemon
      worker thread with a single-slot drop-oldest queue, so the per-frame
      critical path stays cheap even with 200 ms inference. CLI knobs
      `--async-detection --detect-every-n N`.
- [x] YOLO26 / YOLOv10 NMS-free output (`(1, N, 6)`) decoded by
      `decode_yolov8` auto-detect.
- [x] Survey of newer YOLO families on HF (v9 / v10 / v11 / v12 / v26) —
      eval'd v11n-visdrone and the only public v26m-visdrone. v11n is
      marginal (+3 % F1 / +36 % latency); v26m as published is undertrained.
      Documented in `QUICKSTART.md` §2.
- [x] `DetectorConfig.max_detections` default raised from 100 → 1000 after
      the consensus reference showed the cap was silently throwing away
      80–90 % of true positives.
- [x] CLI: `--num-classes`, `--tiles`, `--tile-overlap`, `--tile-input-size`,
      `--max-detections`, `--tile-on-demand`, `--tile-refresh-tiles-per-cycle`,
      `--async-detection`, `--detect-every-n`, `--imgsz`.

### Tracking

- [x] Kalman motion model in `ByteTracker`. 6-state `[cx, cy, w, h, vx, vy]`
      (no velocity on w/h — aerial size is essentially constant; an earlier
      8-state version grew boxes under LOST gaps). Initial velocity variance
      moderate (100, not 1e4). Max-speed clamp at 50 px/frame.
      `freeze_velocity()` on ACTIVE → LOST.
- [x] Soft update for distance-only matches: snap position + size, do not
      infer velocity from the large residual. Stops the "ejection"
      symptom where one wrong match would slam Kalman velocity and the
      next predict flung the box.
- [x] Third-pass distance-based association: when a fast-moving track's
      Kalman has zero / stale velocity, its predicted bbox doesn't overlap
      the new measurement → IoU=0 → without this pass, the IoU passes
      fail and a new track spawns. Centroid distance gated by predicted
      box size + class match. Default `motion_distance_factor=2.0`.
- [x] Class-aware Hungarian assignment for both IoU passes
      (`scipy.optimize.linear_sum_assignment`). Cost = 1 − IoU; INF for
      class mismatch / below threshold. Optimal pairing in dense clusters;
      cannot match a car track to a truck detection.
- [x] Empty-detection frames = "no observation": tracker runs Kalman
      predict + emits snapshots but skips association + transitions. Lets
      tile-on-demand mode emit empty cycles without burning
      `frames_since_match` toward LOST/DEAD.
- [x] CLI overrides for tracker knobs (`--tracker-iou-threshold`,
      `--tracker-motion-distance-factor`, `--tracker-max-age`,
      `--tracker-lost-age`, `--tracker-min-hits`).
- [x] Sweep against the heavy reference proved `min_hits=1` cuts ID
      switches 137 → 86 (−37 %). Default left at 3; user opts in.

### Measurement & debug rig (overlap with phase 9)

- [x] `JsonlExportSink` tap stage. Per-frame `{frame_id, timestamp_ns,
      detections, tracks}` records.
- [x] `--export-jsonl` on `run` and `bench`.
- [x] `scripts/build_reference.py` — offline run with heaviest weights
      (`yolov8x-visdrone-1920`, `yolov11x-visdrone-1920`) at tile grids.
- [x] `scripts/ensemble_refs.py` — N-of-M consensus filter across model
      references; 79.7 % retention on hwy00 with 2 of 2 at IoU 0.5.
- [x] `scripts/diff_runs.py` — per-frame detection P/R/F1 + ID switch
      count vs reference.
- [x] `scripts/sweep_tracker.py` — runs `lowlatcv bench --export-jsonl`
      across a tracker-knob grid, diffs each, prints summary table.
- [x] `scripts/eval_detector.py` — single-image evaluation against
      VisDrone GT, with `--save-render` GT-vs-pred overlay.
- [x] `scripts/compare_detectors.py` — side-by-side multi-model panel +
      grid composite on a chosen video frame.
- [x] `scripts/download_yolov8_weights.py` — fetch + export VisDrone /
      COCO weights at requested `--imgsz`.

### Debug UI (overlap with phase 8)

- [x] `SDLDisplaySink` (already in place) — pygame-CE `_sdl2` streaming
      texture, Metal on macOS / OpenGL on Linux. Replaced cv2.imshow.
- [x] `DebugWindow` — separate pygame window with live per-stage p50 / p99
      / max from the shared `Tracer`, track-state counts, AsyncDetector
      counters + staleness gauge. Pause / step controls. Background
      pump task so the window stays responsive while the source is
      paused. CLI: `--debug`.
- [x] Tile-activity overlay (`--debug-tiles`) — `TileActivityBoard` plumbed
      from `TiledOnnxDetector` to `Overlay`. Per-tile translucent
      rectangles colour-coded by reason (red = recovery / blue = refresh /
      green = sweep / grey = never), border thickens when ran-this-cycle,
      corner badge shows `R|F|S a<age> n<n_dets>`.
- [x] `docs/debug-ui-guide.md` — operator manual: every indicator's
      meaning + symptom-to-CLI-knob table (trails / ejections / dominant
      LOST / cold tiles / ...).

## Known issues still open

### Tracking

- [ ] **Async detection at high worker latency yanks fast-moving tracks.**
      When the worker takes N frames to publish, the tracker is at frame
      T but detections describe frame T-N. Predicted-T position for a
      horizontal-highway car is N×velocity px ahead of measured-(T-N)
      → IoU = 0, motion-distance gate misses → tracks respawn.
      Quick remediation was to keep emitting the stale detection set
      every frame (current behaviour); proper fix is per-lane Kalman
      rewind to the source frame before association.
- [ ] **No appearance features.** ID swaps still possible when two
      same-class objects cross paths closely. Cheap candidate:
      per-track HSV histogram on the crop, combined into the Hungarian
      cost matrix.

### Detection

- [ ] **`pedestrian` / `people` / `bicycle` recall near zero on hwy00.**
      Too small at 1280; tiling helps a little; specialised model or
      higher imgsz would help more.
- [ ] **NMM (Non-Maximum Merging) at the global aggregation step.**
      Today `TiledOnnxDetector._aggregate` runs plain NMS across
      detections from all tiles. When the same car straddles two tiles
      and both detect it slightly differently, NMS picks one and *drops*
      the other; NMM *merges* them (weighted-average xyxy, max of the
      two scores) for a more stable bbox on boundary objects.
      SAHI-style.
- [ ] **Batched tile inference.** Today the tile loop in
      `_infer_blocking` calls `session.run` once per tile (9 sequential
      calls for tiles=3x3, ~50 ms each → ~450 ms wall). Batching to a
      single `session.run` with a `(N, 3, H, W)` input would halve or
      better the wall time on most EPs. Caveat: CoreML EP compiles for
      a fixed batch size, so the ONNX export would need
      `dynamic={"images": {0: "batch"}}` or a fixed `batch=N`. Worth
      probing — could be the cheapest 2× speedup available.
- [ ] **Auto-slice sizing.** Pick `tile_rows × tile_cols` from a target
      object-pixel range (e.g. "I want cars at ~40 px in each tile")
      instead of the user guessing at the grid manually. Equivalent to
      SAHI's `auto_slice_resolution` heuristic. Could probe the first
      few frames and lock the grid for the rest of the run.

### Pipeline / engineering

- [ ] **Critical-path preprocess is wasted CPU when `--detector
      onnx-tiled`** — tiled backend ignores `Frame.tensor` and re-does
      its own letterbox per tile. Move preprocess into the worker.
- [ ] **BGR memcpy from cv2.VideoCapture** is 24 MB / frame at 4K.
      PyAV → SDL NV12 texture path would skip it.
