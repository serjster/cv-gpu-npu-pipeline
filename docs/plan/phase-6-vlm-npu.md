# Phase 6 — VLM on platform NPU (XDNA / ANE)

**Status (2026-05-13): deferred.** Work has been on the macOS profile for
detection/tracking quality + debug tooling. The Linux + AMD profile (where
FastFlowLM on the XDNA NPU lives) hasn't been picked up. Re-open this phase
when the work shifts to a Linux machine, OR when the macOS-side ANE VLM
becomes the active sub-track. The macOS half (`CoreMLVLM` on ANE) is also
deferred because phase 5's Ollama backend has been good enough for the
current demo + the immediate quality issues live on the detection /
tracking side, not the captioning side.



**Goal:** Run the VLM on the dedicated neural accelerator native to each runtime profile, alongside the Ollama/GPU backend from Phase 5. Validate end-to-end on the accelerator class that the FPGA reference architecture targets.

- **Linux + AMD profile:** FastFlowLM on the Ryzen AI NPU (XDNA).
- **macOS + Apple Silicon profile:** CoreML VLM on the Neural Engine (ANE).

Both backends are siblings to the Ollama backend behind the same `VLM` Protocol. The choice is a config switch per profile.

**References:**

- `docs/research/fastflowlm/` — XDNA backend research and session findings.
- `docs/research/coreml-vlm.md` (create in this phase) — ANE backend research, model conversion notes.

**Design patterns introduced:**

- **Strategy** — already in place from Phase 5. This phase adds two sibling backends.
- **Open/Closed** — zero changes to `pipeline/vlm.py` consumers; only new backend modules and config options.
- **Chain of Responsibility (optional)** — a `FallbackVLM` composite that tries the NPU first, falls back to the GPU backend if the NPU queue depth exceeds a threshold. Implement only if benchmarks show it's needed.

**Tasks (Linux + AMD profile):**

- [ ] Survey the FastFlowLM surface (CLI / HTTP / Python SDK); record what's actually usable in `docs/research/fastflowlm/findings.md` (create if absent)
- [ ] `FastFlowLMVLM` backend module, lazy-imported
- [ ] Benchmark NPU (XDNA) vs GPU (ROCm Ollama) on the same fixture: per-caption latency p50/p90/p99, sustainable captions/sec, host memory
- [ ] Record the benchmark in this phase doc as a comparison table

**Tasks (macOS + Apple Silicon profile):**

- [ ] Survey what's available for VLM on ANE today (CoreML model zoo, MLX-VLM compiled artefacts, conversion via `coremltools`); record in `docs/research/coreml-vlm.md`
- [ ] Pick one candidate VLM that compiles cleanly to CoreML for ANE residency
- [ ] `CoreMLVLM` backend module, lazy-imported (so Linux profile doesn't need `coremltools`)
- [ ] Benchmark ANE vs GPU (Metal Ollama) on the same fixture: per-caption latency p50/p90/p99, sustainable captions/sec
- [ ] Record the benchmark in this phase doc as a sibling comparison table

**Shared tasks:**

- [ ] Wire backend selection: `cfg.vlm.backend in {"ollama", "fastflowlm", "coreml", "fake"}` via the existing factory; per-profile defaults in `config.py`
- [ ] Document the routing policy per profile: primary backend, fallback trigger (if any)
- [ ] (Optional) `FallbackVLM` composite implementing the routing policy
- [ ] Test: backend factory dispatches by config string and raises on missing platform-only deps
- [ ] Test: `FastFlowLMVLM` mocked for CI on Linux runners
- [ ] Test: `CoreMLVLM` mocked for CI on macOS runners
- [ ] Test: `FallbackVLM` (if built) routes to fallback when primary queue exceeds threshold

**Decision (block):** which backend is primary on each profile at the end of this phase? Options per profile:

- **NPU primary, GPU fallback** — closer to the FPGA target; only acceptable if the NPU sustains the required captions/sec.
- **GPU primary, NPU exploration** — fastest end-to-end demo; defers the NPU dependency.
- **Both, side-by-side** — different tracks routed to different backends; only if benchmarks justify the complexity.

Resolve after running the benchmarks on the respective profile, not before. Record both resolutions at the top of this file.

**Done when:** on the Linux profile, `cfg.vlm.backend=fastflowlm` produces captions at the cadence required by the routing policy; on the macOS profile, `cfg.vlm.backend=coreml` does the same. Both comparison tables are filled in with real numbers.
