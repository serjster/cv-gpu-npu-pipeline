# Debug UI guide

What every indicator on screen means, what numbers in the metrics window
mean, and which CLI knob to turn when you see a particular problem. Keep
this open in another tab while running the live pipeline.

```bash
uv run lowlatcv run --source data/b3d/videos/hwy00.mp4 --display \
  --detector onnx-tiled --weights data/models/yolov8n-visdrone-1280.onnx \
  --num-classes 10 --imgsz 1280 --tiles 2x2 \
  --async-detection --detect-every-n 2 \
  --tile-on-demand --tracker-min-hits 1 \
  --debug --debug-tiles
```

This opens two windows:

- **Scene** (main): the video + bbox overlays + (with ``--debug-tiles``)
  per-tile activity rectangles.
- **Debug** (next to scene): per-stage latency, track counts, async
  detector counters, pause/step.

Click the **Debug** window to give it focus, then use ``Space`` to pause,
``→`` to step one frame, ``R`` to reset the percentile buffers, ``Q`` for
a quit hint.

---

## Scene window — what the boxes mean

Bounding-box style is driven by the track's state (set by ``ByteTracker``):

| Style on screen | Track state | Means |
|---|---|---|
| Solid thick (2 px) | **ACTIVE** | Matched a fresh detection recently; confidently tracked |
| Solid thin (1 px)  | **TENTATIVE** | Just spawned, not yet confirmed (``min_hits`` not reached) |
| Dashed line | **LOST** | No match for ``max_age`` frames; held alive by Kalman |
| *no draw* | **DEAD** | Pruned; ID never reused |

Label format: ``#<track_id> <state-initial> <score>``. e.g. ``#42 A 0.91``.

If a VLM caption store is attached, the most recent caption per track is
drawn below the box.

### Tile-activity rectangles (``--debug-tiles``)

Each grid cell paints a translucent rectangle and a corner badge:

```
┌─────────────────┐ ← border colour = REASON the tile last ran
│ R a0 n12        │
│                 │ ← border thickness = freshness
│   (scene)       │   (thick when age=0, thin once old)
└─────────────────┘
```

| Hue | Reason | Meaning |
|---|---|---|
| 🔴 red | **recovery** | Tracker has a LOST or TENTATIVE track somewhere inside this tile. Detector ran it to try to re-acquire. |
| 🔵 blue | **refresh** | Round-robin coverage. No track was lost here; the detector ran it anyway to discover new objects entering the frame. |
| 🟢 green | **sweep** | Full-sweep mode (no ``--tile-on-demand``). Every tile runs every cycle. |
| ⚪ grey | **never run** | The detector has not run this tile yet. Shouldn't persist long — the refresh rotation eventually covers everything. |

Badge: ``<R|F|S|·>  a<age>  n<n_dets>``

- ``R / F / S`` = reason letter (recovery / refresh / sweep).
- ``a<age>`` = frames since this tile was last run.
- ``n<n_dets>`` = how many detections came out of the last run on this tile.

---

## Debug window — what the metrics mean

The HUD is regenerated each frame the source emits. Layout from top:

```
frame 4218    fps 28.7
paused: False

STAGE LATENCY (ms)
stage              n     p50     p99     max
source             ...
preprocess         ...
detector           ...
tracker            ...
caption_scheduler  ...
overlay            ...
export_jsonl       ...           (only when --export-jsonl is set)
sink               ...

TRACKS / DETECTIONS
tracks  ACT 23   LOST 4   TENT 2
dets   this frame: 47

ASYNC DETECTOR
submitted 1100  dropped 480  published 620
worker last: 213.5 ms
staleness: 3 frames

[SPACE] pause  [→] step  [R] reset  [Q] quit
```

| Block | Field | Meaning |
|---|---|---|
| top | ``frame`` | Source frame counter (cv2.CAP_PROP_POS_FRAMES). |
| top | ``fps`` | Rolling-60-frame source FPS. End-to-end pipeline rate, not raw decoder rate. |
| top | ``paused`` | True while Space-paused. Source coroutine is stalled. |
| stage table | ``n`` | Number of samples in the sliding window for this stage's tracer. |
| stage table | ``p50 / p99 / max`` | Per-stage wall time in **milliseconds**. ``p99`` is your real-time budget — if any stage's p99 exceeds frame budget (33 ms at 30 fps) it's the bottleneck. |
| tracks | ``ACT`` | ACTIVE — tracks that matched a detection recently. |
| tracks | ``LOST`` | LOST — held alive by Kalman, waiting for re-acquisition. |
| tracks | ``TENT`` | TENTATIVE — newly spawned, not yet confirmed. |
| dets | ``this frame`` | How many detections the latest inference returned. |
| async | ``submitted`` | Frames the scheduler offered to the worker queue. |
| async | ``dropped`` | Frames evicted (drop-oldest) because the worker hadn't picked up the previous one. |
| async | ``published`` | Inference results the worker has completed. |
| async | ``worker last`` | Wall time of the last single ONNX run (one tile-set), in ms. |
| async | ``staleness`` | ``current_frame_id - last_published_frame_id``. **How many frames behind reality the current detection set is.** |

### What a healthy run looks like

- ``fps`` is stable and close to the source's intrinsic frame rate.
- Stage ``p99`` columns are each under your frame budget.
- ``staleness`` oscillates between 0 and roughly ``detect_every_n + 1``;
  it should not climb monotonically.
- ``ACT`` track count is the dominant state; ``LOST`` and ``TENT`` are a
  small fraction.
- ``dropped`` grows slowly relative to ``submitted`` (some drops are
  fine — drop-oldest is by design).
- Tile-activity grid alternates colour: red recovery tiles cluster where
  cars actually are; refresh-blue rotates through cold tiles; ages stay
  under, say, 10 frames.

---

## Symptom → knob: how to read the UI and what to tune

| What you see | Likely cause | Knob to try |
|---|---|---|
| One stage's ``p99`` >> all others | That stage is the bottleneck. | If detector: lower tile count, lower imgsz, or enable ``--async-detection``. If preprocess: lower ``--imgsz``. |
| ``fps`` collapsing then recovering | Periodic GC or model-warmup spikes. | Look at ``max`` column to find the offender; pin if recurring. |
| ``staleness`` climbs >> ``detect_every_n`` | Worker can't keep up — inference is slower than the cadence. | Either raise ``--detect-every-n`` (slow down submissions), pick a cheaper tile config, or use a smaller model. |
| ``dropped`` grows fast | Same as above — worker is behind. | Same fixes. The drop-oldest policy is correct; you just need fewer submissions or faster work. |
| ``TENT`` dominates ``ACT`` | Tracks aren't confirming. | Lower ``--tracker-min-hits`` (proven win at min_hits=1) or check detector recall. |
| ``LOST`` dominates ``ACT`` | Detector is missing tracked objects. | Lower ``--score-threshold``, add tiles (``--tiles 2x2`` → ``3x3``), or enlarge imgsz (re-export weights at 1280 → 1920). |
| Cars going fast leave a "trail" of LOST boxes | Async stale measurement pulls Kalman backward. | Known issue — proper fix is per-lane Kalman rewind. Mitigations: lower ``--detect-every-n``, use sync detector (omit ``--async-detection``). |
| Boxes "eject" / fly off in a straight line | Wrong association feeding bad velocity to Kalman. | Lower ``--tracker-motion-distance-factor`` 2.0 → 1.5; or set to 0 to disable the distance pass entirely (then fast cars will respawn). |
| Cars get two different IDs over time | Greedy IoU or wrong-class match (mostly fixed). Or genuine occlusion. | Verify class is consistent on the offending track. For occlusions, raise ``--tracker-max-age``. |
| Tiles 4–8 stay grey or age=high | Refresh rotation isn't covering enough. | ``--tile-refresh-tiles-per-cycle 2`` or 3. |
| One tile is stuck red (recovery) for many frames | Tracker keeps re-hinting a lost track that's gone (e.g. occluded by a building). | Lower ``--tracker-lost-age`` so the track DEADs sooner. |
| Empty / very few green-found dets on certain tiles | The model can't see at that scale. | Raise tile count or tile_input_size (re-export model). |
| Stationary cars get dropped after a few frames | Class flicker between car / van / truck across frames. | Currently no remediation; raising ``--score-threshold`` makes the model more decisive but reduces recall. |
| Whole screen full of tentative tracks that never confirm | Detector is jittery (different position each call). | Raise ``--score-threshold`` or pick larger weights variant (``visdrone-s``). |
| Detector ``p99`` is fine but tracker ``p99`` is 30+ ms | Too many tracks per frame (e.g. 500+). | Raise ``--score-threshold`` to thin the candidate set; or raise ``--tracker-iou-threshold``. |

---

## Quick keyboard reference (Debug window must have focus)

| Key | Action |
|---|---|
| ``Space`` | Toggle pause |
| ``→`` | Step one frame (forces pause after the step) |
| ``R`` | Reset all tracer percentile buffers — useful right before timing a change |
| ``Q`` | Quit-requested flag (best-effort; for hard stop use Ctrl-C in terminal) |

---

## Workflow: tune the pipeline against an objective reference

The eyeballed UI is for "is something obviously wrong"; for numbers, use
the JSONL pipeline:

```bash
# 1. Build a heavy reference once per clip (slow, run once).
uv run python scripts/build_reference.py \
  --source data/b3d/videos/hwy00.mp4 \
  --weights data/models/yolov8x-visdrone-1920.onnx \
  --imgsz 1920 --tiles 3x3 \
  --out data/refs/hwy00-v8x.jsonl --frames 200

uv run python scripts/build_reference.py \
  --source data/b3d/videos/hwy00.mp4 \
  --weights data/models/yolov11x-visdrone-1920.onnx \
  --imgsz 1920 --tiles 3x3 \
  --out data/refs/hwy00-v11x.jsonl --frames 200

uv run python scripts/ensemble_refs.py \
  --input data/refs/hwy00-v8x.jsonl \
  --input data/refs/hwy00-v11x.jsonl \
  --out data/refs/hwy00-consensus.jsonl --min-models 2 --match-iou 0.5

# 2. Run the live pipeline with --export-jsonl to capture its output.
uv run lowlatcv bench --source data/b3d/videos/hwy00.mp4 --frames 200 \
  --detector onnx-tiled --weights data/models/yolov8n-visdrone-1280.onnx \
  --num-classes 10 --imgsz 1280 --tiles 2x2 \
  --export-jsonl data/refs/hwy00-live.jsonl

# 3. Diff.
uv run python scripts/diff_runs.py \
  --reference data/refs/hwy00-consensus.jsonl \
  --ours      data/refs/hwy00-live.jsonl --match-iou 0.5
```

When the debug UI shows you a candidate fix, run ``sweep_tracker.py`` to
measure the change against the reference rather than guessing.
