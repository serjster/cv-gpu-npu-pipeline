# AMD XDNA / Ryzen AI NPU — Project Context

Findings consolidated from `docs/conversation-marcelo.json` (Teams chat with Marcelo Marques) and `docs/references.md`. This is the **NPU-side** counterpart to `versal-vek385-pipeline.md`: the Versal AI Edge AIE-ML array and the Ryzen AI NPU use the *same* AI Engine architecture, so toolchain knowledge transfers in both directions.

> Source: project conversation 2025-08 → 2026-05-12. The colleague (Marcelo) is the AMD-side reference inside Topic NL; deliverable scoping is pending an ask from Henri.

## Hardware targets

| SKU | Class | Ryzen AI SDK officially supported? | Role in project |
|---|---|---|---|
| **Ryzen AI MAX+ 395** ("Strix Halo") | Consumer laptop / workstation APU | **No** — driver yes, SDK no. Tracked in [RyzenAI-SW #366](https://github.com/amd/RyzenAI-SW/issues/366) | Dev machine (the user's box). Useful for running compile/conversion flows even without runtime support. |
| **Ryzen AI Embedded X100** | Embedded variant of Strix Halo | Same status as Strix Halo | Embedded form of the dev box. |
| **Ryzen AI Embedded P100** | Embedded series (Strix Point) | Yes | The **actual deployment target** — `https://www.amd.com/en/products/embedded/ryzen-ai/p100-series.html` |
| Versal AI Edge VE2802 / VEK385 | FPGA + AIE-ML v2 | n/a (Vitis flow) | The FPGA reference platform the Python pipeline emulates (`versal-vek385-pipeline.md`). Same AIE-ML cores. |

**Implication for this repo.** The Python emulator targets the Versal pipeline, but the same per-stage latency model applies to the Ryzen AI NPU because the AI Engine tiles are identical. A second backend mapping (NPU instead of AIE-ML on Versal) can reuse stage names and budgets.

## Target VLM

- **Model**: [`LiquidAI/LFM2.5-VL-1.6B-ONNX`](https://huggingface.co/LiquidAI/LFM2.5-VL-1.6B-ONNX) — Liquid Foundation Model 2.5, 1.6B vision-language, exported to ONNX.
- **Why this one**: small enough to be a plausible NPU candidate (vs. Gemma-3-4B which AMD already ported — see below). Conversion to the Ryzen AI runtime is the open task.
- **Reference port (already done by AMD)**: [`amd/Gemma-3-4b-it-mm-onnx-ryzenai-npu`](https://huggingface.co/amd/Gemma-3-4b-it-mm-onnx-ryzenai-npu) — use as a worked example of the ONNX→NPU compile path.

**Architectural note (already encoded in `CLAUDE.md`):** VLM latency dwarfs detection (100s of ms vs. single-digit ms). It must stay off the per-frame critical path and be multiplexed sparsely across active tracks. This stays true on the NPU — the agreement in the chat was that heavy ops like VLM are *not* the strong suit of the NPU; the strong suit is many small low-latency ops.

## AMD toolchain stack (top → bottom)

1. **Ryzen AI SW** — high-level SDK. ONNX/PyTorch in, NPU-deployable artefacts out.
   - Repo: <https://github.com/amd/RyzenAI-SW>
   - Docs: <https://ryzenai.docs.amd.com/en/latest/index.html> (also `linux.html`)
   - VLM example: <https://github.com/amd/RyzenAI-SW/tree/main/LLM-examples/VLM>
2. **Riallto** — high-level Python framework for programming the AIE array (NPU). Good entry point for understanding the dataflow model.
   - Docs: <https://riallto.ai/index.html>
3. **IRON** — close-to-metal NPU programming (MLIR-AIE based). When SDK abstractions don't fit, drop here.
   - Repo: <https://github.com/amd/IRON>
4. **xdna-driver** — Linux kernel driver for the NPU.
   - Repo: <https://github.com/amd/xdna-driver>
   - Kernel docs + **telemetry**: <https://docs.kernel.org/accel/amdxdna/amdnpu.html#telemetry>
     — telemetry hook is the one that maps cleanly to our `tracer.span(...)` reporter; per-stage NPU counters become percentiles in the same table.

## Background reading (paralellism + compile flow)

- **CERN AIE tutorial** — slides 8–13 are the clearest explanation of the AIE parallelism levels (tile, vector, dataflow). PDF: <https://indico.cern.ch/event/1645811/contributions/6919327/attachments/3243548/5786413/CERN_NGT_AIE4ML_TUTORIAL.pdf>
- **ARIES paper** — MLIR-based compilation flow for reconfigurable devices with AI Engines. Useful framing for what IRON is doing under the hood. <https://dl.acm.org/doi/epdf/10.1145/3706628.3708870>
- **"Unlocking the AMD NPU" (arXiv 2504.03083)** — bare-metal ML *training* on the client NPU. Even though training isn't our use case, the data-movement breakdowns are reusable. <https://arxiv.org/pdf/2504.03083>
- **BrrrViz** — GPU-kernel visualisations (not NPU, but useful for kernel intuition): <https://brrr-viz.vercel.app/>
- Plus internal PDF: `llm 1 1.pdf` on LLM inference (shared by Marcelo via Teams, OneDrive link in the chat — not redistributable here).

## Project framing (paraphrased from the chat)

- **Mental model agreed with Marcelo**: *"apply AI to every application that can be software-defined."* SDR, network security, drones — anything where a sub-millisecond inference flips a decision. This is the framing for what makes the NPU/FPGA worth using over a regular PC.
- **Demo constraint**: low-latency ethernet-frame prediction (e.g. for trading) was floated as a technically interesting use case but rejected by Marcelo as not interactive enough for a trade show demo. The CV pipeline in this repo *is* the interactive demo candidate.
- **Open**: Henri asked for a concrete deliverable to be defined. Until that lands, the safest scope is "Python pipeline + NPU backend stub + measurable per-stage latency parity with the Versal reference."

## What this changes in the repo

Nothing structural yet — the Python pipeline design (Stage protocol, bounded queues, `tracer.span`, VLM off critical path) already accommodates a Ryzen AI NPU backend as just another `Detector` / `VLM` implementation. Concrete follow-ups when the deliverable is scoped:

1. Add an NPU-backed `Detector.from_config(...)` variant alongside the CoreML/ONNX/Ultralytics ones, gated by a `backend: "ryzenai"` config.
2. Wire `xdna-driver` telemetry counters into `metrics/reporter.py` so the table reports NPU-side timings the same way it reports Python-side spans.
3. Track the LFM2.5-VL ONNX → Ryzen AI conversion as a separate sub-task; it is not a prerequisite for the rest of the pipeline working.
4. Open question to resolve with Marcelo: does the demo need to run on Strix Halo (user's machine, SDK-unsupported but driver-supported) or only on a P100 box?

## NPU detector path — status & blockers (2026-05-13)

Investigated after the Linux profile bring-up landed. Recording what is and isn't on the table.

**Working today (this repo, this box):**
- VLM on the NPU via **FastFlowLM** — XDNA2 / NPU2 is fully supported; `gemma4-it:e4b` runs end-to-end at ~4 s/caption (see `phase-6-vlm-npu.md`). XRT + `amdxdna` 0.6 driver + NPU FW 1.1.2.65 validate clean via `flm validate`.

**Blocked, requires AMD support:**

| Layer | Status on Strix Halo (this box) | Notes |
|---|---|---|
| XRT + amdxdna driver | ✅ works (`xrt-smi examine` sees `RyzenAI-npu5`) | Mainline kernel 7.0 |
| AMD Quark (`amd-quark==0.11.2`) — ONNX/PyTorch quantizer | ✅ Linux-portable, on PyPI | Pure Python toolkit, no NPU runtime |
| `onnxruntime-vitisai` wheel (the EP) | ❌ not shipped for Strix Halo | Ryzen AI 1.7.1 Linux supports STX + KRK only; binaries built for Ubuntu 24.04 + Py 3.12. The Vitis-AI EP loads xclbins compiled for blessed SKUs. |
| `VitisAIExecutionProvider` activating on Strix Halo | ❌ untested but unlikely to work | Per RyzenAI-SW#366: driver yes, SDK no. Strix Halo isn't an enabled target in the shipped xclbins. |

**Practical implication.** For the demo box, the detector stays on **MIGraphX EP / ROCm GPU** (5 ms p50, well under budget). NPU runs the VLM via FastFlowLM. This matches the Versal reference architecture — the iGPU plays the role of the AIE-ML array for vision, and the NPU runs the heavy off-critical-path captioner.

**Routes to revisit, by cost:**
1. **Cheapest: wait.** AMD's Ryzen AI Linux release cadence is roughly quarterly; Strix Halo support is the most-requested gap in the public tracker. Re-probe each release: install Ubuntu 24.04 in a VM or `distrobox` on Arch, try `onnxruntime-vitisai`, see if `VitisAIExecutionProvider` activates on `/dev/accel/accel0`.
2. **Medium: P100 / Embedded.** If a P100 dev kit is available (officially blessed), the YOLOv8n ONNX → Quark INT8 → VitisAI EP path is a known recipe (`docs/research/amd-xdna-npu-context.md` §3). Latency target ~5 ms on Strix Point; should be similar on Strix Halo when blessed.
3. **Expensive: roll our own kernel via IRON / mlir-aie.** This is Phase 10 territory — author the YOLO head's tile mapping in `aie2p.mlir`, build via Vitis AIE tools + xchesscc, dispatch via XRT from Python. FastFlowLM's `lib/*_npu.so` libs demonstrate this is feasible; the open-source `flm` binary uses the same XRT API surface (`xrt::device(0)` + `xrt::ext::kernel`). That same harness could run our own xclbin.

**Re-open this section when** any of these is unblocked.

### Empirical attempt log (2026-05-13)

Tried Route 1 ("install RAI 1.7.1 Linux on Arch, see what happens"). Recording the
result here so the next person doesn't repeat the experiment.

**Inputs:**
- `RAI_1.7.1_Linux_NPU_XRT.zip` (driver bundle — XRT 2.21.75 + amdxdna plugin). The Arch
  packages provide equivalents.
- `ryzen_ai-1.7.1.tgz` (the actual SDK — `onnxruntime-vitisai`, AMD Quark, flexml,
  llvm_aie, ryzenai_dynamic_dispatch, voe, device_essentials_{strx,phx}, etc.).

**Setup on Arch (cp312 side-venv at `~/.local/share/ryzen-ai-venv`):**

1. `uv python install 3.12` — wheels are cp312-only.
2. Install all wheels via `uv pip install --find-links <tgz dir> ...`. AMD's
   `install_ryzen_ai.sh` does this but enforces `python3.12 -m venv --copies` +
   patches `bin/activate`. Skipping that script — `uv venv --python 3.12` does the
   same job cleaner on Arch.
3. Order matters: install the union first (pulls in vanilla `onnxruntime` 1.22.1 as
   a transitive of `onnxruntime-providers-ryzenai`), then `uv pip uninstall` it,
   then reinstall `onnxruntime-vitisai-1.23.3` so it owns the `onnxruntime` namespace.
4. Pin `numpy<2` — the AMD wheels were compiled against NumPy 1.x and crash on import
   with NumPy 2.x ("module compiled using NumPy 1.x cannot be run in NumPy 2.4").
5. Extract `voe-min.tar.gz` into site-packages (xclbins + `vaip_config.json`).
6. Env vars per `ryzen_ai/scripts/activate.patch`:
   `LD_LIBRARY_PATH=$SP/flexml/flexml_extras/lib:$SP/onnxruntime/capi:$SP/voe/lib:...`,
   `XILINX_VITIS=$SP`, `XILINX_VITIS_AIETOOLS=$XILINX_VITIS`,
   `RYZEN_AI_INSTALLATION_PATH=<venv>`, `XILINX_XRT=<xrt install>`.
7. XRT — extract from the deb to `~/.local/share/xilinx-xrt/opt/xilinx/xrt`. Patch
   the Boost 1.83 SONAMEs to symlink to Arch's 1.91 versions
   (`libboost_filesystem.so.1.83.0 → libboost_filesystem.so.1.91.0`, same for
   `program_options` and `system`).

**Result on Strix Halo:**

- `import onnxruntime` succeeds.
- `ort.get_available_providers()` lists **`VitisAIExecutionProvider`** alongside CPU. ✅
- `ort.InferenceSession(<onnx>, providers=['VitisAIExecutionProvider', ...])` constructs
  without raising. The verifier prints
  `All nodes placed on [VitisAIExecutionProvider]. Number of nodes: 5` (the EP wraps
  the model into a small number of super-nodes).
- BUT the EP prints two errors during construction:
  1. `F vaiml_compile.cpp:633 Model compilation is not supported in a deployment only installation. Please compile the model with a full installation.`
  2. `INFO: [VAIP-VAIML-CUSTOMOP] XRT is not installed. This InferenceSession generates model binaries only. The session handle can not be used for inference run.`
- `session.run(...)` returns numbers, but **the NPU is not engaged**:
  - `/proc/<pid>/maps` shows `libonnxruntime_vitisai_ep.so` loaded but no
    `libxrt_driver_xdna` and no `/dev/accel/accel0` fd in `/proc/<pid>/fd`.
  - `xrt-smi examine -r aie-partitions` shows `No hardware contexts running on device`
    throughout the inference loop.

**Apples-to-apples on `amd/yolox-s` (the AMD-published INT8 ONNX, 1×3×640×640):**

| EP / path                                      | mean latency | what it actually is |
|------------------------------------------------|--------------|---------------------|
| `MIGraphXExecutionProvider` (iGPU 8060S, ROCm) | **4.0 ms**   | actually on GPU; `xrt-smi` confirms |
| `VitisAIExecutionProvider` (claimed NPU)        | 8.6 ms      | **CPU fallback**; the AMD-built ORT has better INT8 kernels than vanilla CPU EP, but `/dev/accel/accel0` is never opened |
| `CPUExecutionProvider` (vanilla ORT)            | 45.1 ms     | vanilla CPU INT8 |

**Conclusion.** AMD's deployment-only Linux SDK 1.7.1 cannot bring up the NPU for
new ONNX models on Strix Halo: the `vaiml_compile` step is hard-gated to "full
installation" (which AMD doesn't ship for this SKU), and no pre-compiled NPU
artifacts targeting NPU5 (8-column XDNA2) ship in `device_essentials_strx`
(its `xclbin/strx/base.xclbin` is for Strix Point's 4-column NPU4).

### Empirical attempt log — Route 3 (IRON / mlir-aie), 2026-05-13

Tried Route 3 ("custom kernels via IRON / mlir-aie") to see if we can run *any*
real compute on Strix Halo's NPU5 from this Linux box. Outcome: **yes — and
unlike the VitisAI EP, the NPU actually executes the work.**

**Setup (Arch, cp312 side-venv at `~/.local/share/iron-venv`):**

1. `git clone -b devel https://github.com/amd/IRON ~/.local/share/iron-work/iron`.
2. `uv venv --python 3.12 ~/.local/share/iron-venv`.
3. `pip install -r requirements.txt` — pulls `mlir_aie==0.0.1.2026033104+e4f35d6`
   (cp312 wheel, ~700 MB) and `llvm-aie==21.0.0.2026051101+adc9df1a`
   (~1.5 GB) from Xilinx GitHub release indices.
4. Need pyxrt from the deb extract: `export PYTHONPATH=$XRT/python:$PYTHONPATH`
   (it's a cp312 `.so` inside the Linux NPU XRT bundle from the previous experiment).
5. `export XILINX_XRT=~/.local/share/xilinx-xrt/opt/xilinx/xrt`,
   `export LD_LIBRARY_PATH=$XILINX_XRT/lib:$LD_LIBRARY_PATH`.

**mlir-aie recognises Strix Halo:** `aie.utils.get_current_device()` returns an
`NPU2` instance with `cols=8, rows=6` — all 48 AIE tiles addressable. The
`NPU_MODELS` table in `aie/utils/hostruntime/xrtruntime/hostruntime.py` already
maps `npu5 / Strix Halo` to the `npu2` family, so no patching needed.

**Tests pass — the toolchain compiles for AIE2P and dispatches via XRT:**
- `pytest iron/operators/axpy/` → **160 / 160 PASSED** in 29 s (covers
  1, 2, 4, **8** column configurations).
- `pytest iron/operators/gemm/ -m "not extensive"` → **45 / 45 PASSED** in 48 s
  (covers 2048×2048×2048 bf16 GEMM on 1, 2, 4, 8 columns, plus smaller shapes
  with different tile partitions).

The CSV emitted by `iron/common/test_utils.run_test` records per-test
`latency_us` and `bandwidth_gbps` measured from the NPU itself (not host
wall-clock), giving us real on-device numbers.

**Apples-to-apples bench — pure GEMM 2048×2048×2048 (17.2 GFLOPs/call):**

| Backend                                  | Precision | Latency  | Throughput |
|------------------------------------------|-----------|---------:|-----------:|
| **iGPU Radeon 8060S (MIGraphX EP)**      | FP32      | **2.54 ms** | **6.8 TFLOPS** |
| NPU Strix Halo XDNA2 (IRON, 8 columns)   | bf16      | 7.42 ms  | 2.3 TFLOPS |
| NPU Strix Halo XDNA2 (IRON, 4 columns)   | bf16      | 13.5 ms  | 1.3 TFLOPS |
| NPU Strix Halo XDNA2 (IRON, 2 columns)   | bf16      | 27.1 ms  | 0.6 TFLOPS |
| NPU Strix Halo XDNA2 (IRON, 1 column)    | bf16      | 48.4 ms  | 0.4 TFLOPS |
| CPU Ryzen AI MAX+ 395 (numpy)            | FP32      | 29.8 ms  | 0.6 TFLOPS |

**Interpretation.**

- For raw matmul on this SKU the **iGPU beats the NPU by ~3×** even though
  iGPU runs FP32 and NPU runs bf16. The 8060S is a 16-CU RDNA3.5 part with
  hipBLAS/MIGraphX-optimised paths; a single NPU column does ~1/8th of the
  iGPU's work at half the precision width.
- The NPU's throughput scales near-linearly with columns (×2 cols → ×2 TFLOPS),
  i.e. there's no obvious column-shared bottleneck inside this kernel design.
- For a full YOLOv8n forward (~8.5 GFLOPs, conv-heavy), at 2.3 TFLOPS bf16 NPU
  matmul the *ideal* upper bound is sub-millisecond per inference — but conv
  isn't yet wired in IRON for AIE2P (the dashboard marks Convolution 🟡
  in-development; only matmul / attention / norm / activations are shipped).
  Until conv lands or we route through im2col-matmul ourselves, the NPU can't
  run YOLO directly through IRON.

**Where the NPU wins anyway:**

- **Power.** XDNA2 sustains its TFLOPS at ~15 W vs the iGPU at 40–50 W for
  similar matmul throughput. Most of the time we're not throughput-limited.
- **Concurrency.** Detector on iGPU + VLM on NPU (via FastFlowLM) is the
  architecture the FPGA reference targets — both accelerators productive at
  once.
- **AMD's hand-tuned kernels.** FastFlowLM's closed-source `_npu.so` libs are
  not generic IRON; they're production-optimised attention/MLP for specific
  model families. For language models on NPU they're hard to beat from
  scratch.

**Practical implication for this repo.** Three routes are real, in cost order:

1. **Keep the current split** (detector iGPU, VLM NPU via FLM). Best latency
   today; matches the FPGA reference. Phase 6 / 10 work continues here.
2. **Author conv2d in IRON for AIE2P** as a research deliverable. ~weeks of
   MLIR-AIE kernel work (`aie_kernels/aie2p/conv2d.cc` doesn't exist yet;
   `mm.cc` does and could be adapted via im2col). Worth scoping if the
   demo's story includes "we wrote a YOLO kernel on the NPU."
3. **Wait for AMD's Conv kernel** to land in IRON (Convolution is 🟡 on
   the operator dashboard — actively in development). Cheapest path; we
   re-bench once it ships.

**Re-open this section when** Conv2D lands in IRON for AIE2P, or when we
decide to invest in option 2.

## See also

- `docs/research/versal-vek385-pipeline.md` — FPGA reference pipeline (same AIE-ML cores).
- `docs/research/fastflowlm.md` — adjacent prior research on this NPU.
- `docs/references.md` — raw link list (kernel driver telemetry + RyzenAI-SW).
- `CLAUDE.md` — pipeline architecture, why VLM is off the critical path.
