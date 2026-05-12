# Phase 3 — Object detection

**Decision resolved (2026-05-12):** default detector weights = **YOLOv8n** (ONNX export). Picked over YOLOv11n (similar size, marginal accuracy gain, less battle-tested ecosystem) and RT-DETR-S (anchor-free transformer head — heavier per-frame cost and divergent postprocessing; revisit once the anchor-based pipeline is benched end-to-end). YOLOv8n has well-trodden CoreML / ONNX Runtime / ROCm export paths so both runtime profiles can run an identical model graph. Weights download: `hf download Xenova/yolov8n yolov8n.onnx` (community ONNX export). Backends remain Strategy-swappable; this only picks the default.

**Goal:** Per-frame bounding-box detection wired into the pipeline, rendered by an overlay stage, and visible in the display. This is the heaviest synchronous stage on the per-frame critical path; everything from here is latency-budgeted against it.

**Design patterns introduced:**

- **Strategy** — `Detector` Protocol; concrete backends are interchangeable (ONNX Runtime, optional Ultralytics).
- **Factory Method** — `Detector.from_config(cfg.detector)` selects backend, weights, and execution provider.
- **Adapter** — raw model output tensor → `list[Detection]` via a pure function, isolated from the backend.
- **Open/Closed** — adding a new backend never touches `pipeline/detector.py` consumers.
- **Pure function** — postprocessing (NMS, score threshold, coord-space conversion) lives in `pipeline/detector_post.py`, no model coupling.

**Tasks:**

- [x] `src/lowlatcv/pipeline/detector.py` — `Detector` Protocol, `Detector.from_config` Factory Method
- [x] `OnnxDetector` backend with execution-provider selection (`CPUExecutionProvider`, `ROCMExecutionProvider`, `MIGraphXExecutionProvider`, `CoreMLExecutionProvider`, `CUDAExecutionProvider`) — picked from `cfg.detector.execution_provider`, with a sensible default per OS
- [x] `CoreMLDetector` backend (`.mlpackage` via `coremltools`) — sibling Strategy; lazy-imported so Linux profile doesn't need `coremltools` installed
- [x] `src/lowlatcv/pipeline/detector_post.py` — pure NMS + threshold + coord-back-to-original-frame transform
- [x] `src/lowlatcv/pipeline/overlay.py` — `Overlay` stage rendering bboxes onto `Frame.image` (label = class id for now)
- [x] Wire `FrameSource → Preprocess → Detector → Overlay → Sink` in `app.build_pipeline`
- [x] CLI flags: `--detector onnx --weights <path> --score-threshold 0.25 --iou-threshold 0.45`
- [x] Benchmark mode shows detector p50/p90/p99 separately
- [x] `hf` skill: document the default-weights download command in this phase doc
- [x] Test: `OnnxDetector` receives a `Frame.tensor` and emits ≥0 `Detection` objects (using a tiny fixture model or `FakeDetector`)
- [x] Test: NMS function — overlapping boxes collapse to the highest-score one
- [x] Test: `Overlay` renders without exception when given an empty detection list
- [x] Test: end-to-end pipeline still drains EOF cleanly with detector inserted

**Decision (block):** which weights ship as the default? Candidates: YOLOv8n (small, fast), YOLOv11n (newer, similar size), RT-DETR-S (transformer, heavier but anchor-free). Resolve before benchmarking. Until resolved, use `FakeDetector` returning canned boxes for tests.

**Done when:** `lowlatcv run --source <mp4> --display --detector onnx --weights yolov8n.onnx` shows live bounding boxes on the Linux profile, the CoreML backend produces equivalent boxes on macOS, and `lowlatcv bench` reports detector latency as a distinct line in the table on both profiles.
