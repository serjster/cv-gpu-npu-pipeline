# Project plan

This file is the **entry point for picking up work**. Before starting any task, read this file to find the active phase,
then open the matching `plan/phase-N-*.md` for the task list.

## Status legend

- **open** — no tasks ticked yet
- **in-progress** — at least one task ticked, more to do
- **closed** — every task in the phase doc is ticked

## Runtime profiles

This project supports **two parallel runtime profiles**. Both are first-class; neither replaces the other. The FPGA target (AMD Versal VEK385) sits behind both — the host pipelines are *reference implementations* and a comparison rig.

| Profile | OS | Detector backends | VLM backends | Accelerator |
|---------|----|-------------------|--------------|-------------|
| **Linux + AMD** | Linux (Arch / Ubuntu) | ONNX Runtime (`ROCMExecutionProvider`, `MIGraphX`, `CPU`) | Ollama (ROCm), FastFlowLM | Radeon GPU (ROCm) + Ryzen AI NPU (XDNA) |
| **macOS + Apple Silicon** | macOS 14+ | CoreML, ONNX Runtime (`CoreMLExecutionProvider`, `CPU`) | Ollama (Metal), CoreML VLM | M-series GPU (Metal/MPS) + Neural Engine (ANE) |

The Strategy pattern (`Detector`, `VLM`, `FrameSource`, `FrameSink`) keeps the profiles swappable behind one config switch. The orchestrator, tracer, queue contracts, and stage graph are identical across profiles. **A change is only complete when it works on both profiles** — or when its phase doc explicitly scopes itself to one and documents the gap on the other.

## Working rules

- Work on one phase at a time. Finish the in-progress phase before opening a new one.
- Inside a phase doc, tasks are markdown checkboxes (`- [ ]` / `- [x]`). Tick each as you finish it. Do not batch.
- When every checkbox in a phase is ticked, mark the phase **closed** in the table below and move the next phase to *
  *in-progress**.
- A phase doc may contain a **Decision** block. Resolve the decision with the user before implementing tasks in that
  phase. Capture the resolution at the top of the phase doc.
- Do not jump phases. If a real blocker forces it, add a note in the relevant phase doc and surface it to the user.

## Phases

| #  | Phase                                                                  | Status |
|----|------------------------------------------------------------------------|--------|
| 1  | [Foundation & scaffolding](plan/phase-1-foundation.md)                 | closed |
| 2  | [Source & sink (end-to-end skeleton)](plan/phase-2-source-sink.md)     | closed |
| 3  | [Object detection](plan/phase-3-detection.md)                          | closed |
| 4  | [Tracking](plan/phase-4-tracking.md)                                   | closed |
| 5  | [VLM async (GPU/ROCm via Ollama)](plan/phase-5-vlm-async.md)           | closed |
| 6  | [VLM on NPU via FastFlowLM](plan/phase-6-vlm-npu.md)                   | in-progress |
| 7  | [Queryable VLM (user prompts steer focus)](plan/phase-7-query.md)      | open   |
| 8  | [Dashboard & control UI](plan/phase-8-dashboard.md)                    | open   |
| 9  | [Performance hardening](plan/phase-9-performance.md)                   | open   |
| 10 | [NPU lower-level exploration (stretch)](plan/phase-10-npu-lowlevel.md) | open   |

## Cross-phase invariants

These apply to every phase. If a phase task violates one, refactor before ticking the box.

- **Stage boundaries are sacred.** A stage does one thing. New behaviour goes in a new stage, not by widening an
  existing one.
- **The per-frame critical path stays lean.** Source → Preprocess → Detector → Tracker → Overlay → Sink. Anything
  heavier (VLM, dashboard streaming, logging fan-out) runs off this path.
- **Bounded queues, `maxsize=2` default.** Back-pressure must remain visible in the latency report.
- **Constructor injection only.** Stages take dependencies via `__init__`. No singletons except `logging`.
- **Protocols over ABCs.** New stage interfaces use `typing.Protocol`.
- **Tracer instrumentation in every stage.** `tracer.span(self.name)` wraps the work. Untraced stages are invisible to
  the report and not acceptable.
- **No heavy imports at module top.** `torch`, `transformers`, `coremltools`, `onnxruntime` are gated behind the stage
  that needs them.
- **Both runtime profiles stay green.** A new backend lives next to the existing ones via Strategy; it never edits a consumer. If a stage gains a platform-specific dependency, it goes behind a config switch and the other profile keeps a working backend.
