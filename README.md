# low-latency-cv

Python reference pipeline that emulates an ultra-low-latency computer-vision app targeting an AMD Versal AI Edge (
VEK385) FPGA platform. Runs on macOS for development and benchmarking; the same stage topology is meant to be
re-implemented in Vitis / AIE-ML kernels for the FPGA later, so per-stage latency numbers are directly comparable.

## What it does

Given a video file or live stream:

1. **Detect** — bounding-box detector (YOLO-class model) on every frame.
2. **Track** — multi-object tracker assigns persistent track IDs across frames.
3. **Caption (VLM)** — per-track vision-language description, computed **once on first detection** and optionally
   refreshed at a configurable interval (the VLM is the slow stage; it must not block the per-frame pipeline).
4. **Overlay & sink** — annotate frames and write to file / display / null.

Each stage is a pluggable component with its own queue, worker, and latency tracer. The pipeline is structured to mirror
an FPGA dataflow graph (see `ARCHITECTURE.md`), so latency, throughput, and back-pressure behaviour can be compared 1:1
with the future Versal implementation.

## Requirements

- macOS (Apple Silicon recommended — uses MPS / CoreML when available)
- Python 3.13+
- `uv` (recommended) or `pip`
- ffmpeg on `PATH` (for arbitrary container formats)

See `BUILD.md` for setup, run, and benchmarking commands.

## Quick start

```bash
uv sync
uv run lowlatcv run --source path/to/video.mp4 --display
uv run lowlatcv bench --source path/to/video.mp4 --frames 1000
```

## Project layout

| Path                                      | Purpose                                                           |
|-------------------------------------------|-------------------------------------------------------------------|
| `src/lowlatcv/`                           | Pipeline source                                                   |
| `src/lowlatcv/pipeline/`                  | Stages: source, preprocess, detector, tracker, vlm, overlay, sink |
| `src/lowlatcv/metrics/`                   | Per-stage latency tracer, FPS counter                             |
| `tests/`                                  | Pytest unit + integration tests                                   |
| `docs/research/versal-vek385-pipeline.md` | FPGA reference pipeline this project emulates                     |
| `ARCHITECTURE.md`                         | Stage graph, queues, back-pressure model, FPGA mapping            |
| `BUILD.md`                                | Setup, run, benchmark commands                                    |
| `AGENTS.md`                               | Coding principles for AI agents working in this repo              |

## Status

Early scaffold. Pipeline contract and stage interfaces are defined in `ARCHITECTURE.md`; concrete stages are implemented
incrementally.
