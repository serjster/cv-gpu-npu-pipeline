# Phase 3 — Object detection

**Goal:** Per-frame bounding-box detection wired into the pipeline, rendered by an overlay stage, and visible in the display. This is the heaviest synchronous stage on the per-frame critical path; everything from here is latency-budgeted against it.

**Design patterns introduced:**

- **Strategy** — `Detector` Protocol; concrete backends are interchangeable (ONNX Runtime, optional Ultralytics).
- **Factory Method** — `Detector.from_config(cfg.detector)` selects backend, weights, and execution provider.
- **Adapter** — raw model output tensor → `list[Detection]` via a pure function, isolated from the backend.
- **Open/Closed** — adding a new backend never touches `pipeline/detector.py` consumers.
- **Pure function** — postprocessing (NMS, score threshold, coord-space conversion) lives in `pipeline/detector_post.py`, no model coupling.

**Tasks:**

- [ ] `src/lowlatcv/pipeline/detector.py` — `Detector` Protocol, `Detector.from_config` Factory Method
- [ ] `OnnxDetector` backend with execution-provider selection (`CPUExecutionProvider`, `CUDAExecutionProvider`, `ROCMExecutionProvider`, `MIGraphXExecutionProvider`)
- [ ] `src/lowlatcv/pipeline/detector_post.py` — pure NMS + threshold + coord-back-to-original-frame transform
- [ ] `src/lowlatcv/pipeline/overlay.py` — `Overlay` stage rendering bboxes onto `Frame.image` (label = class id for now)
- [ ] Wire `FrameSource → Preprocess → Detector → Overlay → Sink` in `app.build_pipeline`
- [ ] CLI flags: `--detector onnx --weights <path> --score-threshold 0.25 --iou-threshold 0.45`
- [ ] Benchmark mode shows detector p50/p90/p99 separately
- [ ] `hf` skill: document the default-weights download command in this phase doc
- [ ] Test: `OnnxDetector` receives a `Frame.tensor` and emits ≥0 `Detection` objects (using a tiny fixture model or `FakeDetector`)
- [ ] Test: NMS function — overlapping boxes collapse to the highest-score one
- [ ] Test: `Overlay` renders without exception when given an empty detection list
- [ ] Test: end-to-end pipeline still drains EOF cleanly with detector inserted

**Decision (block):** which weights ship as the default? Candidates: YOLOv8n (small, fast), YOLOv11n (newer, similar size), RT-DETR-S (transformer, heavier but anchor-free). Resolve before benchmarking. Until resolved, use `FakeDetector` returning canned boxes for tests.

**Done when:** `lowlatcv run --source <mp4> --display --detector onnx --weights yolov8n.onnx` shows live bounding boxes, and `lowlatcv bench` reports detector latency as a distinct line in the table.
