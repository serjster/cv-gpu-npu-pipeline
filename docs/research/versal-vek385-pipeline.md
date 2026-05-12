# Versal VEK385 — Reference Pipeline (placeholder)

> **STATUS: PLACEHOLDER.** The user has a pipeline document they intend to attach here. Replace this file with that content. The Python emulator in `src/lowlatcv/` and the diagrams in `ARCHITECTURE.md` should be updated to match whatever lands in this file.

This document is the **source of truth** for the FPGA-side pipeline that the Python project in this repo emulates. Stage names, ordering, and rough latency budgets in `ARCHITECTURE.md` and the `Stage` implementations under `src/lowlatcv/pipeline/` must match it.

## Target platform

- **Board**: AMD VEK385 — Versal AI Edge Series Gen 2 evaluation kit
- **Device**: VE2802 (Versal AI Edge Gen 2)
- **Compute resources**:
  - **AIE-ML v2 array** — primary ML accelerator (INT8 / BF16). Detector and VLM live here.
  - **Programmable Logic (PL)** — Vitis Vision kernels for capture, preprocess, overlay, output.
  - **APU**: dual-core Arm Cortex-A78 — orchestration, tracker control flow, host-side glue.
  - **RPU**: dual Cortex-R52 — real-time control, watchdog (not in the CV path).
- **Toolchain**: Vitis 2024.2+, Vitis Vision Library, AIE-ML compiler.

## Assumed pipeline (until the real document is dropped in)

```
[Sensor] ──MIPI──▶ [PL: Capture+DMA] ──AXI-S──▶ [PL: Resize+CSC+Norm]
   ──AXI-S──▶ [AIE-ML: YOLO Detector]
   ──AXI/AXI-S──▶ [APU: ByteTrack]
   ──AXI──▶ [AIE-ML: VLM Captioner]   ⟵ sparse, multiplexed across active tracks
                  │
                  ▼
   [PL: Overlay] ──AXI-S──▶ [PL: HDMI/DP TX]
```

Per-stage budget targets (placeholder, to be replaced by real numbers):

| Stage | Budget | Notes |
|-------|--------|-------|
| Capture + DMA | < 1 ms | line-buffered, near-zero latency |
| Preprocess | < 1 ms | chained AXI-S, no DDR round-trip |
| Detector (YOLO) | 5–10 ms | INT8, AIE-ML array partitioned |
| Tracker (ByteTrack) | < 1 ms | APU, control-flow heavy, low compute |
| Overlay | < 1 ms | PL drawing kernels on output stream |
| Sink (HDMI TX) | < 1 ms | framebuffer DMA |
| **End-to-end (per frame)** | **< 15 ms** | target ≥ 60 fps headroom |
| VLM (per request, off path) | 100–500 ms | dedicated AIE-ML partition, multiplexed across tracks |

## Open questions for the real document

When you drop in the actual `versal-vek385-pipeline.md`, please cover:

1. Exact YOLO variant + quantisation strategy.
2. VLM choice and how it's partitioned on AIE-ML (or whether it sits off-board).
3. Memory hierarchy used per stage (URAM / BRAM / DDR), plus AXI widths.
4. Concurrency model: how many in-flight frames; queue depths between PL kernels and AIE-ML.
5. Drop / back-pressure policy at the source.
6. Trace / profiling hooks (Vitis Analyzer span names) — these should match `tracer.span(name)` calls in the Python emulator so reports diff cleanly.
