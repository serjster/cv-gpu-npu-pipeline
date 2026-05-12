# low-latency-cv — Build Guide

## Prerequisites

- macOS (Apple Silicon recommended — Metal / MPS / CoreML acceleration)
- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/) — install with `brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`
- `ffmpeg` on `PATH` — `brew install ffmpeg`

The repo ships a `.venv/` already at Python 3.13. `uv sync` will populate it from `pyproject.toml` / `uv.lock`.

## Setup

```bash
# Install / sync deps from pyproject.toml + uv.lock
uv sync

# Optional: pre-cache model weights (avoids first-run download during a benchmark)
hf download <detector-repo-id>
hf download <vlm-repo-id>
```

## Run

```bash
# Run a video through the pipeline with a display window
uv run lowlatcv run --source path/to/video.mp4 --display

# Run a live camera (device index 0) with file sink
uv run lowlatcv run --source 0 --sink file --output out.mp4

# Run an RTSP stream, no rendering, for a fixed number of frames
uv run lowlatcv run --source rtsp://... --sink null --frames 5000
```

## Benchmark

```bash
# Per-stage latency (p50/p90/p99) + end-to-end FPS over N frames
uv run lowlatcv bench --source path/to/video.mp4 --frames 1000

# Emit JSON report for diffing against an FPGA run
uv run lowlatcv bench --source path/to/video.mp4 --frames 1000 \
  --report-format json --report-path bench/macos.json
```

## Lint, typecheck, test

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
```

## Common issues

- **`ModuleNotFoundError` on first run.** Run `uv sync`. If a dep was added by another agent, `uv.lock` may need an update — `uv lock && uv sync`.
- **First run hangs for minutes.** Detector / VLM weights are downloading. Pre-cache with `hf download <repo>`.
- **`cv2.imshow` raises `NSInternalInconsistencyException`.** OpenCV display calls must run on the main thread. The display sink is wired this way; do not move it to a worker.
- **MPS fallback warnings.** Some operators silently fall back to CPU. Set `PYTORCH_ENABLE_MPS_FALLBACK=0` to surface the real cost when investigating.
- **Pipeline stalls upstream.** Expected behaviour when a downstream stage is slow — bounded queues create back-pressure on purpose. Look at the queue-depth column in the latency report to identify the bottleneck.
- **VLM dominates the trace.** Also expected. The VLM is intentionally off the per-frame critical path; it should never block the source / detector / tracker / sink chain. If it does, check that the `CaptionRequest` queue and worker are wired correctly.

## After making changes

1. `uv run ruff format src tests`
2. `uv run ruff check src tests --fix`
3. `uv run mypy src`
4. `uv run pytest -q`
5. If you added a stage, update `ARCHITECTURE.md` (stage diagram + FPGA-mapping table) in the same commit.
