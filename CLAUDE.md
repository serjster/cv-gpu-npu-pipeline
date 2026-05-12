# CLAUDE.md

Python reference pipeline that emulates an ultra-low-latency computer-vision app for the AMD Versal AI Edge VEK385 FPGA platform. Runs on macOS. Performs per-frame object detection + tracking, with periodic VLM captioning per track. Designed so per-stage latency, queue depths, and back-pressure behaviour can be compared 1:1 against the future FPGA implementation.

## Agent Instructions

Follow DRY, SOLID, TDD, and design patterns. See `AGENTS.md` for details.

Skills available in `.claude/skills/`: `design-patterns`, `test`, `lint`, `format`, `todo`, `hf-cli`.

Design pattern documentation: `docs/coding/design_patterns/` (SOLID, GoF patterns with UML, examples, anti-patterns).

FPGA reference: `docs/research/versal-vek385-pipeline.md` — the source-of-truth for what we are emulating. Stage names and ordering should match it.

## Rules

### Auto-Commit

Commit immediately after making file changes. Do NOT wait for the user to ask.

- Commit after each meaningful unit of work (file edits complete, agent finishes, 3+ file changes accumulated)
- Stage specific files, not `git add -A`
- Use imperative mood, no conventional commit prefixes
- Do NOT push unless the user asks
- Do NOT stage `.env` files, credentials, or secrets

### Discuss Before Acting

When the user expresses uncertainty, asks "what do you think", "do you have any idea", "can we maybe" — this is a DISCUSSION, not an instruction.

1. Propose the idea in text first — explain what you'd do and why
2. Wait for the user to approve before making any file changes
3. Never edit files during a brainstorming/discussion phase

### Self-Improvement

When a tool, skill, or agent fails or produces suboptimal results, and the cause is in the tool/skill/agent itself (not user input or environment):

1. Do NOT stop your main task. Note the issue, continue with a workaround.
2. Launch a background agent to investigate and fix the issue.
3. Resume your main task immediately — don't wait for the subagent.
4. When the subagent completes, briefly inform the user what was improved.

This applies to `.claude/skills/`, `.claude/agents/`, `.claude/rules/`, and `scripts/` invoked by skills. Does NOT apply to built-in tools or user code outside `.claude/`.

## Build & Test

```bash
# Install / sync dependencies
uv sync

# Run a video through the pipeline (display window)
uv run lowlatcv run --source path/to/video.mp4 --display

# Benchmark: per-stage latency + end-to-end FPS over N frames
uv run lowlatcv bench --source path/to/video.mp4 --frames 1000

# Lint + typecheck
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src

# Tests
uv run pytest -q
```

- Python 3.13+ (CPython). Apple Silicon recommended (uses MPS / CoreML where supported).
- Dependency manager: `uv`. `pyproject.toml` is the single source of truth.
- ffmpeg required on `PATH` for arbitrary container formats.
- No system packages required beyond ffmpeg.

## Directory Structure

```
low-latency-cv/
├── pyproject.toml                    # uv-managed deps, project metadata, ruff/mypy/pytest config
├── README.md                         # project overview
├── AGENTS.md                         # rules for AI agents
├── ARCHITECTURE.md                   # stage graph, FPGA mapping, latency model
├── BUILD.md                          # build/run/benchmark guide
├── CLAUDE.md                         # this file
├── docs/
│   ├── research/
│   │   └── versal-vek385-pipeline.md # FPGA reference pipeline (source of truth)
│   └── coding/design_patterns/       # SOLID + GoF reference docs
├── src/
│   └── lowlatcv/
│       ├── __init__.py
│       ├── app.py                    # CLI entry point (typer), DI wiring of pipeline
│       ├── config.py                 # PipelineConfig dataclass, env / file loading
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── stage.py              # Stage protocol, StageRunner, queue helpers
│       │   ├── runner.py             # Pipeline orchestrator (graph build, lifecycle)
│       │   ├── source.py             # FrameSource: file / camera / RTSP via OpenCV/ffmpeg
│       │   ├── preprocess.py         # Resize + colour convert (mirrors FPGA PL preproc)
│       │   ├── detector.py           # YOLO-class detector (CoreML / ONNX / Ultralytics)
│       │   ├── tracker.py            # ByteTrack-style multi-object tracker
│       │   ├── vlm.py                # VLM captioner, sparse schedule, off critical path
│       │   ├── overlay.py            # Bounding-box + label rendering
│       │   └── sink.py               # Display / file / null sink
│       ├── models/
│       │   ├── frame.py              # Frame, Detection, Track dataclasses (immutable)
│       │   └── caption.py            # VLM result types
│       └── metrics/
│           ├── tracer.py             # tracer.span("stage") context manager, percentiles
│           └── reporter.py           # Per-stage latency / queue-depth report
└── tests/
    ├── test_pipeline.py
    ├── test_tracker.py
    └── test_metrics.py
```

## Coding Conventions

- **Type-annotate everything.** `mypy --strict` is the target.
- **No comments** that restate the code. Use docstrings on public classes / functions only when behaviour is non-obvious.
- **Dataclasses** (`@dataclass(frozen=True, slots=True)`) for `Frame`, `Detection`, `Track`, `Caption`. No raw dicts crossing stage boundaries.
- **Protocol-oriented**: stages conform to `Stage`, sources to `FrameSource`, sinks to `FrameSink`.
- **Constructor injection**: stages take dependencies via `__init__`. No singletons except `logging`.
- **`logging.getLogger(__name__)`** in every module. Categories follow module path: `lowlatcv.pipeline.detector` etc.
- **`tracer.span("stage_name")`** wraps the work in every stage so latency percentiles are always available.
- **Bounded queues** between stages (default `maxsize=2`) so back-pressure is visible — matches FPGA AXI-Stream `tready`.
- **No heavy imports at module top level** in stages — gate `torch`, `coremltools`, `transformers` behind the stage that needs them.
- **No global mutable state.** Pipeline wiring lives in `lowlatcv.app`.

## Design Patterns in Use

| Pattern | Where Used |
|---------|-----------|
| **Strategy** | Detector / Tracker / VLM backends are swappable via the `Stage` protocol — same interface, different model behind it |
| **Pipeline (Pipes & Filters)** | Core architecture — bounded queues between stages, each stage a pure transform |
| **Producer-Consumer** | `FrameSource` → queue → `Detector` → queue → `Tracker` → … with back-pressure |
| **Observer** | `tracer` publishes per-span timings to subscribed reporters (CLI, JSON, Prometheus) |
| **Facade** | `Pipeline` in `runner.py` hides graph construction + lifecycle behind `start()` / `stop()` / `await_completion()` |
| **Command** | VLM jobs are queued as `CaptionRequest` objects, processed off the critical path |
| **Factory Method** | `Detector.from_config(cfg)`, `VLM.from_config(cfg)` build the right backend from config |
| **Adapter** | OpenCV / ffmpeg / CoreML wrappers adapt third-party APIs to the internal `Frame` / `Detection` types |
| **Dependency Injection** | Manual constructor injection in `lowlatcv.app.build_pipeline(cfg)` |

For pattern reference docs and UML diagrams: `docs/coding/design_patterns/`.

## Architecture Patterns

### Concurrency model

- **One thread (or process) per stage**, owned by `StageRunner`. Each stage pulls from its input queue and pushes to its output queue.
- **`asyncio` event loop** runs the orchestrator and the I/O-bound stages (source, sink). CPU-bound stages (detector, tracker, VLM) run in worker threads via `loop.run_in_executor` or in a dedicated `multiprocessing` worker for the VLM.
- **Bounded queues** (`asyncio.Queue(maxsize=N)` or `queue.Queue` for thread crossings) make back-pressure explicit. `maxsize=2` is the default — matches the FPGA model where each stage holds at most a couple of in-flight items.
- **VLM is off the per-frame critical path.** Detected tracks emit `CaptionRequest` items into a separate queue served by the VLM stage at its own pace. Captions are joined back into the overlay stage by track ID.

### Stage contract (`Stage` protocol)

```python
class Stage(Protocol[InT, OutT]):
    name: str
    async def setup(self) -> None: ...
    async def process(self, item: InT) -> OutT | None: ...
    async def teardown(self) -> None: ...
```

`process` returning `None` means the item was consumed but produced no downstream work (e.g. a frame skipped by a sampling stage). Errors propagate up so the orchestrator can shut the graph down cleanly.

### Latency tracing

- `tracer.span("stage_name")` is a context manager that records start/end and stage queue depth at entry.
- The `reporter` aggregates by stage and reports p50 / p90 / p99 / max plus end-to-end frame latency on shutdown or on a `--report-interval` tick.
- Output formats: human-readable table (default), JSON (`--report-format json`), CSV.

### FPGA parity

- Stage names match `docs/research/versal-vek385-pipeline.md` so a row in the latency report maps directly to a kernel on the Versal target.
- Queue depth and back-pressure behaviour mirror AXI-Stream `tvalid`/`tready`.
- Per-track sparse VLM scheduling matches the FPGA plan (a single VLM accelerator multiplexed across active tracks).

## Common Pitfalls

- **First run downloads model weights** (detector, VLM). Use `hf` CLI to pre-cache: `hf download <repo>`.
- **OpenCV `imshow` on macOS** must be called from the main thread. The `display` sink runs on the main thread; do not move it to a worker.
- **MPS fallbacks**: some operators silently fall back to CPU. If a stage looks slow, set `PYTORCH_ENABLE_MPS_FALLBACK=0` to surface the real cost.
- **VLM latency dwarfs everything else** (often 200–2000 ms). Never put it inline. The pipeline is designed around this fact.
- **Bounded queues at `maxsize=2`** mean a slow stage stalls upstream — that is the desired behaviour, not a bug. To diagnose, look at the queue-depth column in the latency report.
- **`uv sync` re-locks if `pyproject.toml` changes.** Commit `uv.lock` so other agents and CI get reproducible installs.
