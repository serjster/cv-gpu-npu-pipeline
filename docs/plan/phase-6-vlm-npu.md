# Phase 6 — VLM on NPU via FastFlowLM

**Goal:** Swap (or run side-by-side with) the VLM backend on the AMD XDNA NPU via FastFlowLM. Validate end-to-end on the actual accelerator targeted by the FPGA reference architecture.

**Reference:** `docs/research/fastflowlm/` (research doc + any session-recorded findings).

**Design patterns introduced:**

- **Strategy** — already in place from Phase 5. This phase adds a sibling backend.
- **Open/Closed** — zero changes to `pipeline/vlm.py` consumers; only a new backend module and a config option.
- **Chain of Responsibility (optional)** — a `FallbackVLM` composite that tries the NPU first, falls back to the GPU backend if the NPU queue depth exceeds a threshold. Implement only if Phase 6 benchmarks show it's needed.

**Tasks:**

- [ ] Survey the FastFlowLM surface (CLI / HTTP / Python SDK); record what's actually usable in `docs/research/fastflowlm/findings.md` (create if absent)
- [ ] `FastFlowLMVLM` backend module
- [ ] Wire backend selection: `cfg.vlm.backend in {"ollama", "fastflowlm", "fake"}` via the existing factory
- [ ] Benchmark NPU vs GPU on the same fixture: per-caption latency p50/p90/p99, sustainable captions/sec, host memory
- [ ] Record the benchmark in this phase doc as a comparison table
- [ ] Document the routing policy decision: primary backend, fallback trigger (if any)
- [ ] (Optional) `FallbackVLM` composite implementing the routing policy
- [ ] Test: backend factory dispatches by config string
- [ ] Test: `FastFlowLMVLM` mocked for CI (no real NPU in CI)
- [ ] Test: `FallbackVLM` (if built) routes to fallback when primary queue exceeds threshold

**Decision (block):** which backend is primary at the end of this phase? Options:

- **NPU primary, GPU fallback** — closer to the FPGA target; only acceptable if NPU sustains the required captions/sec.
- **GPU primary, NPU exploration** — fastest end-to-end demo; defers the NPU dependency.
- **Both, side-by-side** — different tracks routed to different backends; only if benchmarks show it's worth the complexity.

Resolve after running the benchmark, not before. Record the resolution at the top of this file.

**Done when:** the pipeline runs with `cfg.vlm.backend=fastflowlm` and produces captions at the cadence required by the routing policy. The comparison table in this doc is filled in with real numbers.
