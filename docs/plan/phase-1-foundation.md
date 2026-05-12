# Phase 1 — Foundation & scaffolding

**Goal:** Stand up the Python package, the core data types, the `Stage` protocol, the pipeline orchestrator skeleton, and tracing/reporting. No real CV stages yet — they get filled in as later phases plug into the framework set up here.

**Design patterns introduced:**

- **Protocol-oriented design** — `Stage`, `FrameSource`, `FrameSink` defined as `typing.Protocol`. Open/Closed at the type level.
- **Pipes & Filters** — `Pipeline` wires bounded queues between independent stages.
- **Facade** — `Pipeline.start()` / `stop()` / `await_completion()` hides graph construction and lifecycle.
- **Observer** — `tracer` publishes per-span timings to one or more `Reporter` subscribers.
- **Dependency Injection (constructor)** — wiring lives in `app.build_pipeline(cfg)`. Stages take collaborators via `__init__`.
- **Value Object** — `Frame`, `Detection`, `Track`, `Caption` are frozen dataclasses; no raw dicts cross stage boundaries.

**Tasks:**

- [ ] `pyproject.toml` with `uv` (deps: `typer`, `opencv-python`, `numpy`, `pytest`, `ruff`, `mypy`; gate heavier deps to extras)
- [ ] `src/lowlatcv/__init__.py`
- [ ] `src/lowlatcv/app.py` — typer CLI with `run` and `bench` subcommands (stubs invoking the orchestrator)
- [ ] `src/lowlatcv/config.py` — `PipelineConfig` + sub-configs from `ARCHITECTURE.md`, env + YAML overlay loading
- [ ] `src/lowlatcv/models/frame.py` — `Frame`, `Detection`, `Track` (`@dataclass(frozen=True, slots=True)`)
- [ ] `src/lowlatcv/models/caption.py` — `Caption`, `CaptionRequest`
- [ ] `src/lowlatcv/pipeline/stage.py` — `Stage[InT, OutT]` Protocol, `StageRunner` (pull–process–push loop with tracer)
- [ ] `src/lowlatcv/pipeline/runner.py` — `Pipeline` Facade (graph build, start, stop, await, reverse-order teardown)
- [ ] `src/lowlatcv/metrics/tracer.py` — `tracer.span("name")` context manager; sliding-window p50/p90/p99/max
- [ ] `src/lowlatcv/metrics/reporter.py` — Observer subscribers for table / JSON / CSV
- [ ] `tests/test_stage_protocol.py` — dummy stage runs end-to-end through `StageRunner`
- [ ] `tests/test_pipeline_lifecycle.py` — start → process N items → stop, teardown order is reverse
- [ ] `tests/test_tracer.py` — percentile maths, nested-span isolation, queue-depth capture
- [ ] `ruff` + `mypy --strict` + `pytest` configured in `pyproject.toml`; `uv run lint`, `uv run test`, `uv run format` all green on empty scaffold
- [ ] Update `ARCHITECTURE.md` to cover **both** runtime profiles (Linux + AMD ROCm/XDNA and macOS + Apple Silicon CoreML/MPS/ANE) as parallel first-class hosts, kept swappable via Strategy. Keep the FPGA target intact.
- [ ] `ast-index update` after `src/` has files, confirm `ast-index stats` reports a non-empty index

**Done when:** `uv run pytest` is green on the contract tests, `uv run lint` is clean, and `uv run lowlatcv bench --frames 10` runs a stub pipeline end-to-end and prints a latency table (even if every stage is a passthrough).
