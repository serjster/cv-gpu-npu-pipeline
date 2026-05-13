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

## See also

- `docs/research/versal-vek385-pipeline.md` — FPGA reference pipeline (same AIE-ML cores).
- `docs/research/fastflowlm.md` — adjacent prior research on this NPU.
- `docs/references.md` — raw link list (kernel driver telemetry + RyzenAI-SW).
- `CLAUDE.md` — pipeline architecture, why VLM is off the critical path.
