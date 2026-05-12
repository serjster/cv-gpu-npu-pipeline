# ARCHITECTURE.md

## Goal

Build a Python reference pipeline whose **stage graph, queue depths, and latency contract** mirror the future AMD Versal
AI Edge VEK385 (VE2802) FPGA implementation closely enough that a benchmark on the host produces numbers directly
comparable to the FPGA bring-up. The Python implementation is the *behavioural model*; the Vitis/AIE-ML implementation
will be the *production target*.

The FPGA reference pipeline lives in `docs/research/versal-vek385-pipeline.md` and is the source of truth for stage
names, ordering, and rough latency budget. Anything in this document that disagrees with that file is wrong — fix it
here, not there.

## Runtime profiles

Two host runtimes are first-class. Both run the **same stage graph, the same queue contracts, the same tracer span
names**, and the same orchestrator code. Only the per-stage backends differ, selected at construction time via the
Strategy pattern (`Detector`, `VLM`, `FrameSource`, `FrameSink`). A change is only complete when it works on both
profiles — or when the work is explicitly scoped to one and the gap on the other is documented in the phase doc.

| Profile              | OS            | Detector backends                                                          | VLM backends                         | Accelerator                              |
|----------------------|---------------|----------------------------------------------------------------------------|--------------------------------------|------------------------------------------|
| **macOS + Apple Si** | macOS 14+     | CoreML (`.mlpackage`), ONNX Runtime (`CoreMLExecutionProvider`, `CPU`)     | Ollama (Metal), CoreML-converted VLM | M-series GPU (Metal/MPS) + Neural Engine |
| **Linux + AMD**      | Arch / Ubuntu | ONNX Runtime (`ROCMExecutionProvider`, `MIGraphXExecutionProvider`, `CPU`) | Ollama (ROCm), FastFlowLM (XDNA NPU) | Radeon GPU (ROCm) + Ryzen AI NPU (XDNA)  |

Neither profile replaces the other. The FPGA target (AMD Versal VEK385) sits behind both — both host pipelines are
*reference implementations* and a comparison rig for the FPGA bring-up.

## Pipeline overview

```
                                                ┌─────────────────────────┐
                                                │   VLM Captioner         │
                                                │   (sparse, off the      │
                                                │    per-frame critical   │
                                                │    path)                │
                                                └──────────┬──────────────┘
                                                           │ Caption
                                                           ▼
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  Source  │──▶│Preprocess│──▶│ Detector │──▶│ Tracker  │──▶│ Overlay  │──▶│   Sink   │
│ file/cam │   │ resize+  │   │  YOLO-   │   │ ByteTrack│   │ draw box │   │ display/ │
│  /RTSP   │   │ colour   │   │  class   │   │  IDs     │   │ + label  │   │ file/null│
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
      │              │              │              │              ▲              │
      │   Frame      │  Frame       │ Detections   │ Tracks       │              │
      │              │              │              │              │              │
      └─ q(2) ───────┴─ q(2) ───────┴─ q(2) ───────┴─ q(2) ───────┘              │
                                                                                  ▼
                                                                            EOF / Ctrl-C
```

All inter-stage edges are **bounded queues, default `maxsize=2`**. Back-pressure on a downstream stage stalls the
upstream one — the same behaviour as AXI-Stream `tready` deassertion on the FPGA.

## Stage contract

```python
class Stage(Protocol[InT, OutT]):
    name: str

    async def setup(self) -> None: ...

    async def process(self, item: InT) -> OutT | None: ...

    async def teardown(self) -> None: ...
```

- `process` returning `None` means the item was consumed but produced no downstream work (e.g. a sampling stage dropping
  a frame).
- Errors propagate to the orchestrator, which shuts the graph down in reverse order.
- Every implementation wraps its work in `tracer.span(self.name)` so latency is always traced.

## Stages

### 1. Source (`pipeline/source.py`)

Reads frames from a file, camera, or RTSP stream and emits `Frame` records.

| Property        | Value                                              |
|-----------------|----------------------------------------------------|
| Input           | path / device index / URL                          |
| Output          | `Frame(id, timestamp_ns, ndarray HxWx3 uint8 BGR)` |
| Backends        | OpenCV `VideoCapture`, ffmpeg pipe                 |
| Threading       | I/O-bound, runs on the asyncio loop                |
| FPGA equivalent | MIPI / HDMI capture + DMA into PL block-RAM        |

### 2. Preprocess (`pipeline/preprocess.py`)

Resize and colour-convert to the detector's input tensor shape and dtype.

| Property        | Value                                                                                               |
|-----------------|-----------------------------------------------------------------------------------------------------|
| Input           | `Frame`                                                                                             |
| Output          | `Frame` with `tensor: ndarray` attached                                                             |
| Ops             | letterbox resize, BGR→RGB, normalise, NCHW pack                                                     |
| Threading       | CPU-bound, executor thread                                                                          |
| FPGA equivalent | PL kernels: Vitis Vision `resize` + `cvtColor` + `convertTo`, AXI-Stream chained, no DDR round-trip |

### 3. Detector (`pipeline/detector.py`)

Runs the bounding-box detector. Returns zero or more `Detection`s per frame.

| Property             | Value                                                                                                                 |
|----------------------|-----------------------------------------------------------------------------------------------------------------------|
| Input                | preprocessed `Frame`                                                                                                  |
| Output               | `Frame` + `list[Detection]`                                                                                           |
| Backends (macOS)     | CoreML (`.mlpackage`), ONNX Runtime (`CoreMLExecutionProvider`, `CPU`), Ultralytics (`YOLOv8/11n` etc.)               |
| Backends (Linux/AMD) | ONNX Runtime (`ROCMExecutionProvider`, `MIGraphXExecutionProvider`, `CPU`), Ultralytics with `device='cuda'` via ROCm |
| Selection            | via `DetectorConfig.backend` + active runtime profile                                                                 |
| Threading            | CPU/GPU-bound, executor thread                                                                                        |
| FPGA equivalent      | YOLO-class model compiled to AIE-ML v2 array; INT8 weights in URAM, activations in BRAM                               |

`Detection`:

```python
@dataclass(frozen=True, slots=True)
class Detection:
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2 (frame coords)
    score: float
    class_id: int
```

### 4. Tracker (`pipeline/tracker.py`)

Assigns persistent integer track IDs across frames.

| Property        | Value                                                                |
|-----------------|----------------------------------------------------------------------|
| Input           | `Frame` + detections                                                 |
| Output          | `Frame` + `list[Track]`                                              |
| Algorithm       | ByteTrack-class (Kalman + IoU + low-score recovery)                  |
| State           | per-track Kalman filter, lifetime counters                           |
| Threading       | CPU-bound, executor thread                                           |
| FPGA equivalent | PS (Cortex-A78) or AIE tile — small, control-flow heavy, low compute |

`Track`:

```python
@dataclass(frozen=True, slots=True)
class Track:
    track_id: int
    bbox: tuple[int, int, int, int]
    class_id: int
    score: float
    age: int  # frames since first seen
    last_caption: Caption | None  # latest VLM caption, if any
```

### 5. VLM captioner (`pipeline/vlm.py`) — **off the per-frame critical path**

Generates a natural-language description for a track. The slow stage. **Must not block per-frame work.**

| Property             | Value                                                                                                                |
|----------------------|----------------------------------------------------------------------------------------------------------------------|
| Input                | `CaptionRequest(track_id, crop, frame_id)` (own queue)                                                               |
| Output               | `Caption(track_id, text, model, ts_ns)` posted to a result map                                                       |
| Schedule             | once on first detection of a new track; optional refresh every `vlm.refresh_seconds` per track                       |
| Backends (macOS)     | Ollama (Metal) running LLaVA / SmolVLM / Florence-2 class models; optional CoreML-converted VLM for ANE              |
| Backends (Linux/AMD) | Ollama (ROCm) on the Radeon GPU; FastFlowLM on the Ryzen AI XDNA NPU; `transformers` + `torch` on ROCm as a fallback |
| Concurrency          | dedicated worker (thread or process), single in-flight request at a time by default                                  |
| Drop policy          | if the request queue fills, drop **oldest** new-track requests last so first-seen requests are preserved             |
| Threading            | CPU/GPU/NPU-bound, dedicated executor / process pool                                                                 |
| FPGA equivalent      | dedicated AIE-ML partition or off-chip accelerator (PCIe to host); single-instance, multiplexed across tracks        |

The tracker emits a `CaptionRequest` the first time it sees a track. The VLM worker processes requests serially and
posts `Caption` results into a shared `dict[track_id, Caption]` consulted by the overlay stage.

### 6. Overlay (`pipeline/overlay.py`)

Renders bounding boxes, IDs, and (when available) the latest caption text onto the frame.

| Property        | Value                                                                        |
|-----------------|------------------------------------------------------------------------------|
| Input           | `Frame` + `list[Track]` (+ caption map lookup by `track_id`)                 |
| Output          | `Frame` with annotated `ndarray`                                             |
| Backends        | OpenCV `cv2.rectangle` / `cv2.putText`                                       |
| Threading       | CPU-bound, executor thread                                                   |
| FPGA equivalent | PL overlay kernel (Vitis Vision drawing primitives) on the output AXI-Stream |

### 7. Sink (`pipeline/sink.py`)

Terminal consumer — display, file, or null.

| Property        | Value                                                                        |
|-----------------|------------------------------------------------------------------------------|
| Input           | annotated `Frame`                                                            |
| Output          | side-effect (window / file / nothing)                                        |
| Backends        | `cv2.imshow` (display), ffmpeg writer (file), no-op (null/bench)             |
| Threading       | display sink runs on **main thread** (macOS requirement), others on executor |
| FPGA equivalent | HDMI TX or DisplayPort + framebuffer DMA                                     |

## Concurrency & back-pressure

- **Orchestrator** (`pipeline/runner.py`) builds the graph, starts each stage's `StageRunner`, and `await`s completion.
- **Each stage** runs in its own coroutine / executor task, pulling from its input queue and pushing to its output
  queue.
- **Bounded queues** make back-pressure explicit and bounded memory usage automatic.
- **Drop policy** is per-stage and explicit. The default is no-drop (block on full queue). The VLM request queue uses an
  explicit drop-oldest-non-first-sighting policy.
- **Shutdown** is initiated by EOF from the source, an exception in any stage, or `SIGINT`. Stages drain in topological
  order; teardown runs in reverse.

## Latency tracing & reporting

- `metrics/tracer.py` exposes `tracer.span(stage_name)` — a context manager recording
  `(stage, t_start, t_end, queue_depth_in)`.
- `metrics/reporter.py` aggregates spans into per-stage p50 / p90 / p99 / max plus end-to-end frame latency (source
  enqueue → sink complete).
- Output formats: table (default), JSON, CSV. Useful for diffing macOS runs against future FPGA runs.
- The same span names are intended to appear in Vitis Analyzer traces from the FPGA build.

## Configuration

`config.py` exposes a `PipelineConfig` dataclass. Loaded from CLI flags with optional YAML overlay (
`--config path.yaml`). Sub-configs:

- `SourceConfig` — uri, target FPS, hardware decoder hint
- `PreprocessConfig` — input shape, normalisation, layout
- `DetectorConfig` — backend, weights, score / NMS thresholds, max detections
- `TrackerConfig` — IoU, max age, min hits
- `VLMConfig` — backend, weights, max in-flight, refresh seconds, drop policy
- `OverlayConfig` — colours, font, draw caption flag
- `SinkConfig` — kind (display/file/null), file path, codec
- `MetricsConfig` — report interval, output format, output path

## Mapping to the Versal VEK385

| Python stage     | Versal target                                              | Notes                                                            |
|------------------|------------------------------------------------------------|------------------------------------------------------------------|
| Source           | PL: MIPI/HDMI RX → DMA                                     | Frame buffer in DDR4 attached to PS, or directly streamed        |
| Preprocess       | PL: Vitis Vision `resize` + `cvtColor` + normalise         | Chained AXI-Stream, no DDR round-trip                            |
| Detector         | AIE-ML v2 array                                            | Quantised INT8, weights in URAM, kernel partitioned across tiles |
| Tracker          | PS (Cortex-A78) or single AIE tile                         | Control-flow heavy, low compute                                  |
| VLM              | Dedicated AIE-ML partition, or off-board (PCIe → host GPU) | Single instance, multiplexed across tracks                       |
| Overlay          | PL: Vitis Vision drawing kernels                           | On the output AXI-Stream                                         |
| Sink             | PL: HDMI TX / DisplayPort                                  | Framebuffer DMA                                                  |
| Tracer / metrics | PS (host) — Vitis Analyzer traces                          | Same span names so reports diff cleanly                          |

> The FPGA-reference document `docs/research/versal-vek385-pipeline.md` is the source of truth. Any divergence between
> this table and that document is a bug in this file — update here.

## Testing strategy

- **Unit tests** per stage with synthetic inputs (a static `numpy` frame, a hand-crafted detection list).
- **Integration test**: end-to-end on a 30-frame fixture clip, asserting stable track IDs and at least one caption
  emitted.
- **Latency regression test**: bench mode produces a JSON report; CI compares against a stored baseline with a tolerance
  band.
- **No real model downloads in CI**: detector and VLM stages have a `FakeBackend` returning canned outputs at known
  latencies, used for deterministic tests.

## Out of scope (for now)

- Multi-camera / multi-stream
- On-device training or fine-tuning
- Re-identification across non-adjacent frames after a long gap
- Profile-exclusive features that break parity between macOS and Linux/AMD without an explicit phase scope and a
  documented gap on the other profile

These can be added once both host references match the FPGA reference end-to-end.
