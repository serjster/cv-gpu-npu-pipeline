# Phase 6 — VLM on platform NPU (XDNA / ANE)

**Status (2026-05-13): Linux track in-progress (FastFlowLMVLM backend
shipped); macOS track deferred.** Work shifted to Linux when the project
came up on the Strix Halo box. FastFlowLM is wired in as a sibling backend
to OllamaVLM. The proprietary-kernel constraints from the research doc
remain — only model families FLM ships kernels for are reachable today
(no LFM2.5-VL on NPU yet; see `docs/research/fastflowlm.md` §6 for the
"Case B" port cost). macOS ANE half stays deferred — phase 5's Ollama-Metal
is currently good enough for the demo.

## Resolution log

- **Linux backend choice:** primary = **FastFlowLM** when NPU-resident
  captioning is the goal; **Ollama-ROCm** is the fast/quality alternative
  on the iGPU. Both wired; user picks via `--vlm`.
- **First working VLM on NPU:** `gemma4-it:e4b` (Gemma 4 4B vision-language,
  ships as an NPU2 xclbin set in the FLM release).
- **First benchmark (2026-05-13, Strix Halo, gemma4-it:e4b, 200×300 px
  crop, 80-token cap):** ~4.0 s end-to-end roundtrip via OpenAI-compat
  `/v1/chat/completions`. Compare Ollama-ROCm + `ibm/granite3.3-vision:2b`
  on the same fixture: ~0.65 s. Apples-to-apples is pending a smaller VLM
  that FLM publishes kernels for (Gemma 4 E2B candidate).



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

- [x] Survey the FastFlowLM surface (CLI / HTTP / Python SDK); record what's actually usable in `docs/research/fastflowlm.md` (top-level doc, not the subdir originally proposed)
- [x] `FastFlowLMVLM` backend module — Strategy-style sibling of `OllamaVLM`, uses OpenAI-compat `/v1/chat/completions` so we don't need a separate Python SDK. Auto-redirects to FLM's default port (52625) when the user opts in without overriding the host.
- [ ] Benchmark NPU (XDNA) vs GPU (ROCm Ollama) on the same fixture: per-caption latency p50/p90/p99, sustainable captions/sec, host memory — *first datapoint logged above; full sweep pending*
- [ ] Record the benchmark in this phase doc as a comparison table

**Tasks (macOS + Apple Silicon profile):**

- [ ] Survey what's available for VLM on ANE today (CoreML model zoo, MLX-VLM compiled artefacts, conversion via `coremltools`); record in `docs/research/coreml-vlm.md`
- [ ] Pick one candidate VLM that compiles cleanly to CoreML for ANE residency
- [ ] `CoreMLVLM` backend module, lazy-imported (so Linux profile doesn't need `coremltools`)
- [ ] Benchmark ANE vs GPU (Metal Ollama) on the same fixture: per-caption latency p50/p90/p99, sustainable captions/sec
- [ ] Record the benchmark in this phase doc as a sibling comparison table

**Shared tasks:**

- [x] Wire backend selection: `cfg.vlm.backend in {"ollama", "fastflowlm", "coreml", "fake"}` via the existing factory. `fastflowlm` and `ollama` land; `coreml` still pending the macOS sub-track.
- [ ] Document the routing policy per profile: primary backend, fallback trigger (if any)
- [ ] (Optional) `FallbackVLM` composite implementing the routing policy
- [x] Test: backend factory dispatches by config string and raises on missing platform-only deps
- [x] Test: `FastFlowLMVLM` mocked for CI on Linux runners — `tests/test_vlm.py` covers payload shape, host resolution, and missing-content error path.
- [ ] Test: `CoreMLVLM` mocked for CI on macOS runners
- [ ] Test: `FallbackVLM` (if built) routes to fallback when primary queue exceeds threshold

**Decision (block):** which backend is primary on each profile at the end of this phase? Options per profile:

- **NPU primary, GPU fallback** — closer to the FPGA target; only acceptable if the NPU sustains the required captions/sec.
- **GPU primary, NPU exploration** — fastest end-to-end demo; defers the NPU dependency.
- **Both, side-by-side** — different tracks routed to different backends; only if benchmarks justify the complexity.

Resolve after running the benchmarks on the respective profile, not before. Record both resolutions at the top of this file.

**Done when:** on the Linux profile, `cfg.vlm.backend=fastflowlm` produces captions at the cadence required by the routing policy; on the macOS profile, `cfg.vlm.backend=coreml` does the same. Both comparison tables are filled in with real numbers.
