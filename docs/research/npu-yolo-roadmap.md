# Running YOLO-class models on the XDNA2 NPU — roadmap & resume doc

**Final objective:** run per-frame object detection (YOLO-class) on the
AMD Ryzen AI XDNA2 NPU (Strix Halo, "RyzenAI-npu5", AIE2P — 8 columns ×
6 rows), as a close-to-metal path comparable 1:1 with the future Versal
VEK385 FPGA implementation this project emulates.

This is the **paused** track. Active work right now is the IRON Conv2D
operator PR — see `iron-conv2d-pr.md`. This doc is the bookmark for
picking the NPU-YOLO objective back up afterwards. Full investigation
log: `amd-xdna-npu-context.md`.

---

## Where we landed — the whole stack is mapped

| Layer | Status |
|-------|--------|
| XRT / driver / NPU reachable (`/dev/accel/accel0`) | works |
| mlir-aie / IRON targets AIE2P | works |
| Conv designs compile (3D/4D-pad DMA fix, 8-column scaling) | works |
| Multi-block chain with conv kernels | works & correct, but the conv microkernels are AIE2-tuned → 1–2% NPU util |
| Single GEMM (AIE2P-tuned `aie2p/mm.cc`) | works, ~40% util, ~3× the iGPU |
| im2col → GEMM as convolution | validated, ~20× the conv-kernel utilisation |
| **Conv2D as an IRON operator (1×1 + general K×K)** | **works & verified on the NPU — see `iron-conv2d-pr.md`** |
| Fused multi-GEMM chain (intermediates resident on-NPU) | **BLOCKED** — full-ELF GEMM compile bug in the pinned mlir-aie wheel |

### Key measured results

- Conv-kernel 8-block chain @ 40×40, C=64: ~3338 µs, 1–2% NPU util,
  ~6.7× slower than the iGPU (497 µs).
- im2col + GEMM single 3×3 conv: ~3× slower than the iGPU, ~1800 GFLOPS.
- GEMM chain study: same-xclbin repeat is stable ~630 µs/op; an xclbin
  **context switch costs ~2.4 ms** — this is the ceiling a host-driven
  multi-layer chain hits, and the reason a *fused* chain matters.

---

## The one blocker — fused multi-GEMM chain

A real YOLO backbone is many conv layers. Dispatching them one xclbin at
a time pays the ~2.4 ms context-switch tax per layer. The fix is a
**fused** chain: multiple matmul stages in one xclbin, intermediates
resident on-NPU, single dispatch.

IRON's `FusedMLIROperator` is exactly that machinery — but
`fused.compile()` crashes (SIGABRT) in aiecc's resource-allocation
pipeline. Narrowed down: even a *single* GEMM through `FusedMLIROperator`
crashes. The `--generate-full-elf` aiecc path (which fusion requires) is
broken for the GEMM operator in the pinned `mlir_aie==0.0.1.2026033104`
wheel. The standard xclbin path works fine for GEMM; only the full-ELF
path is broken. (The Llama example works because it fuses GEMV, not
GEMM.)

### Options to unblock (from `amd-xdna-npu-context.md`)

1. **Newer mlir-aie wheel.** ❌ Ruled out — tested `2026051405`; IRON's
   GEMM operator breaks immediately (`aie.iron.placers` namespace
   moved). A newer wheel needs a matching newer IRON checkout (its own
   multi-day port), no guarantee the bug is fixed there.
2. **Hand-write the fused multi-matmul MLIR.** Combine the per-GEMM
   `aie.device` blocks into one module by hand, manage shared on-NPU
   buffers manually. No IRON-fusion dependency. Multi-day.
3. **⭐ Use the conv-kernel chain framework with GEMM-style kernels.**
   `resnet_8col.py` already chains multiple kernels in **one xclbin** on
   the **standard** compile path (not full-ELF) with on-NPU
   intermediates via ObjectFifo. Swap its AIE2-tuned conv microkernels
   for the AIE2P-tuned `aie2p/mm.cc` matmul kernel and we get the fused
   chain *and* good utilisation, sidestepping the compiler bug entirely.
   This is the recommended path. Scoped in `amd-xdna-npu-context.md`
   ("Option 3 — fully scoped"): fork `gemm/design.py::my_matmul`, route
   stage-0's `C_l1l2` fifo into stage-1's `A_l2l1` input (the
   depth-first on-chip hand-off `resnet_8col.py` does for conv kernels),
   with a `dims_to_stream` reshape on the mem tile between stages.
   Multi-day but no external dependency.
4. **Wait for AMD** to fix the full-ELF GEMM path upstream.

---

## How the Conv2D operator (the current PR) fits in

The Conv2D operator is the **building block** for YOLO-on-NPU. Once it
lands:

- It gives a clean, tested, single-layer conv on the NPU via im2col +
  the AIE2P matmul kernel — the per-layer primitive.
- The fused-chain work (option 3 above) becomes "chain N Conv2D-style
  GEMM stages in one xclbin" instead of starting from scratch.
- A `NPUConvDetector` backend in this project's pipeline
  (`src/lowlatcv/pipeline/detector.py`) could then wrap it — see "resume
  steps" below.

So: finish the Conv2D PR first (including on-NPU im2col, #36), *then*
the fused chain, *then* wire it into the pipeline.

---

## What ships TODAY (independent of all the above)

The project's actual demo does **not** wait on NPU-YOLO. The validated,
shipping split is:

- **Detector on the iGPU** (Radeon 8060S) via ONNXRuntime + MIGraphX EP,
  with the model cache wired up (`migraphx_model_cache_dir`).
- **VLM on the NPU** via FastFlowLM (OpenAI-compatible HTTP, port
  52625).

Both are validated and in `QUICKSTART.md`. NPU-YOLO is a research
stretch goal on top of a working baseline, not a dependency of it.

---

## Resume steps — when picking this back up

1. **Finish the Conv2D PR** (`iron-conv2d-pr.md`) — it's the per-layer
   primitive and the fused-chain starting point.
2. **Build the fused GEMM chain via option 3:** fork
   `gemm/design.py::my_matmul`, wire stage-0 `C_l1l2` → stage-1
   `A_l2l1` with a mem-tile `dims_to_stream` reshape, compile on the
   standard xclbin path. Target a 2-stage chain first, then N-stage.
   Validate against a torch reference; measure vs. the ~2.4 ms
   context-switch baseline.
3. **Map a real YOLO backbone** (e.g. yolov8n) onto chained
   im2col+GEMM stages — the conv layers are the bulk; decide where
   downsampling / concat / detect-head ops run.
4. **Add an `NPUConvDetector`** backend in
   `src/lowlatcv/pipeline/detector.py` conforming to the `Stage`
   protocol, wired through `Detector.from_config` and the CLI.
5. Compare per-stage latency 1:1 against the iGPU detector and the
   FPGA reference pipeline (`versal-vek385-pipeline.md`).

### NPU scratch work location

All the close-to-metal NPU experiments live **outside** this repo in
`~/.local/share/iron-work/` (not version-controlled with the project):

- `iron/` — the IRON checkout (branch `conv2d-operator` has the PR work)
- `resnet-build/resnet_8col.py` — the working 8-column single-xclbin
  conv-kernel chain; the framework for fused-chain option 3
- `bottleneck-build/` — GEMM-chain benchmarks, the fused-chain spike
  (`bench_fused_gemm_chain.py`, blocked by the compiler bug)

See `amd-xdna-npu-context.md` for the env setup recipe and the full
blow-by-blow.

---

## See also

- `iron-conv2d-pr.md` — the active PR track.
- `amd-xdna-npu-context.md` — full investigation log (env setup, the
  3D/4D DMA fix, 8-column scaling, the CInit≥64 SIMD finding, the
  im2col→GEMM proof, the fused-chain blocker, option scoping).
- `versal-vek385-pipeline.md` — the FPGA reference pipeline being
  emulated (same AIE-ML cores as the NPU).
- `fastflowlm.md` — the NPU VLM runtime that ships today.
