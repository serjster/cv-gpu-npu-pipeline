# Phase 5 — VLM async (GPU via Ollama)

**Goal:** Per-track captions enriched by a Vision-Language Model running **off the per-frame critical path**. Per-frame FPS must be unaffected by VLM latency. First backend is **Ollama**, which abstracts the host GPU (ROCm on Linux, Metal/MPS on macOS) behind a single HTTP API — fastest dev loop and validates the async architecture before adding NPU-specific complexity.

**Why Ollama before the NPU backends:** the Strategy pattern means swapping later is contained. The risk being de-risked here is the *decoupling*, not the choice of accelerator. Once the architecture holds with a slow backend, the NPU backends in Phase 6 are drop-ins.

**Cross-profile note:** the Ollama backend is identical on both profiles — only the model selection differs (e.g. `qwen2-vl:7b` on ROCm with enough VRAM, a smaller `moondream` on macOS Metal).

**Design patterns introduced:**

- **Command** — `CaptionRequest(track_id, crop, frame_id, prompt)` carries everything the VLM needs and is serialisable for cross-process workers.
- **Strategy** — `VLM` Protocol with backend Strategy; Ollama backend here, FastFlowLM later, fake for tests.
- **Factory Method** — `VLM.from_config(cfg.vlm)`.
- **Producer–Consumer (decoupled)** — VLM has its own queue, separate from the per-frame queue. Critical-path stages never `await` the VLM.
- **Single Responsibility** — `Tracker` emits requests; `VLM` processes; `Overlay` reads results. No stage knows another's internals.
- **Single source of truth** — caption results live in one shared `dict[track_id, Caption]`, written by the VLM worker, read by `Overlay`. No broadcast copies.

**Tasks:**

- [x] `src/lowlatcv/pipeline/vlm.py` — `VLM` Protocol
- [x] `OllamaVLM` backend (HTTP client to local Ollama; configurable model, e.g. `moondream`, `llava`, `qwen2-vl`)
- [x] Reuse `CaptionRequest` Command from `models/caption.py` (Phase 1) — extend with `prompt: str | None`
- [x] Caption-request emitter: `CaptionScheduler` stage between `Tracker` and `VLM`, with sparse policy (per-track cooldown + global rate limit, both config-driven)
- [x] VLM worker on a **separate thread** by default, **separate process** behind a config flag (for GIL-bound or crash-isolation cases)
- [x] Caption join-back: `CaptionResultStore` (thread-safe `dict[int, Caption]`), updated by VLM worker, read by `Overlay`
- [x] `Overlay` reads caption store and renders the latest per-track caption, truncated to N chars
- [x] Drop policy from `ARCHITECTURE.md`: if request queue fills, drop *new-track-but-not-first-sighting* requests so first-seen requests are preserved
- [x] Benchmark proof: introduce 1 s of artificial VLM latency, verify per-frame FPS unchanged in the latency report
- [x] Test: `FakeVLM` backend, `CaptionScheduler` honours cooldown and rate limit
- [x] Test: caption written for track A is never rendered on track B (no id mix-up)
- [x] Test: queue-full drop policy preserves first-sighting requests
- [x] Test: VLM worker crash is contained — pipeline continues, error logged, no captions emitted

**Done when:** the pipeline sustains its detector-bound FPS even with a deliberately slow VLM, and live captions appear under track boxes within a few seconds of activity.
