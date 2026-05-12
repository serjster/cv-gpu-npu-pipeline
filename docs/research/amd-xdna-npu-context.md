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

## See also

- `docs/research/versal-vek385-pipeline.md` — FPGA reference pipeline (same AIE-ML cores).
- `docs/research/fastflowlm.md` — adjacent prior research on this NPU.
- `docs/references.md` — raw link list (kernel driver telemetry + RyzenAI-SW).
- `CLAUDE.md` — pipeline architecture, why VLM is off the critical path.
