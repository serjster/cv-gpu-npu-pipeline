# Phase 10 — NPU lower-level exploration (stretch)

**Goal:** Investigate going closer to the XDNA hardware than FastFlowLM allows, so we can run models FastFlowLM doesn't support. Exploratory — no commitment to ship a custom backend at the end of this phase.

**Design patterns introduced:**

- **Strategy** — any custom backend slots in next to `OllamaVLM` and `FastFlowLMVLM`. No changes elsewhere.
- **Spike (research pattern)** — outcome is a *recommendation* in a research doc, not production code. Spike code lives on a branch and may or may not graduate.

**Tasks:**

- [ ] Survey the XDNA stack: `xrt`, `mlir-aie`, `RyzenAI-SW`, the iree-amd-aie path, any Linux-kernel-side options
- [ ] Catalogue what runs today on XDNA outside FastFlowLM — what compiler / runtime combination, what model shapes are supported
- [ ] Pick **one** candidate model that's currently unsupported by FastFlowLM and would be useful here (e.g. a more recent VLM)
- [ ] Spike: prototype a custom `VLM` backend behind the existing Strategy interface; goal is end-to-end one caption, no perf target
- [ ] Capture every dead-end and surprise in `docs/research/npu-lowlevel.md` (create the file in this phase)
- [ ] Recommendation at the bottom of the research doc: **ship it** (with a Phase 11 outline), **defer** (with the conditions that would change the answer), or **drop**
- [ ] Open a follow-up plan phase only if the recommendation is "ship it"

**Done when:** the research doc concludes with a yes / defer / no recommendation. If yes, a Phase 11 stub exists in `docs/plan.md` and a phase doc has been drafted.
