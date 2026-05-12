# Phase 9 — Performance hardening

**Goal:** Squeeze the pipeline. Get to the FPS / latency envelope that justifies the FPGA comparison. Optimisation is **profile-driven** — the tracer's percentile table tells us where to look; never optimise without a measurement showing the cost first.

**Design patterns introduced:**

- **Object Pool** — pre-allocated `numpy` buffers for `Frame.image` and `Frame.tensor`, recycled per pipeline tick. Removes the per-frame allocation hit.
- **Flyweight** — share immutable metadata (class names, palette, font glyphs) across frames; never copy when a reference suffices.
- **Lazy initialisation** — model loading and CUDA/ROCm warmups happen in `Stage.setup`, never in `process`.
- **Profile-guided refactor** — measurements first, code changes second. Reject any change that doesn't show up in the latency report.

**Tasks:**

- [ ] Establish the current baseline: capture the latency report on a fixed fixture clip, commit it to `docs/perf/baseline.json`
- [ ] Identify hottest stage from the baseline (the report is the spec)
- [ ] Frame buffer pool: eliminate per-frame `numpy.zeros` allocations on the critical path
- [ ] Evaluate thread vs process workers per stage; switch only stages where the measurement justifies it
- [ ] Pinned host memory for GPU upload, if a GPU detector backend is in use
- [ ] Confirm `Frame` metadata mutation never copies the image array — `numpy` views, asserted in a test
- [ ] Per-stage FPS budget table added at the bottom of this doc, with targets set from the baseline
- [ ] Comparison report vs FPGA reference (`docs/research/versal-vek385-pipeline.md`), as a new section in this doc
- [ ] Update `ARCHITECTURE.md` with the final stage-by-stage latency model (numbers from the perf run)
- [ ] Re-run the baseline after each change; reject changes that don't move the needle

**Done when:** the fixture clip sustains the target FPS (defined in the budget table once the baseline is in), the latency report numbers match the target, and the FPGA comparison section is filled in.

## Per-stage FPS budget (to be filled after baseline)

| Stage      | p50 (ms) | p90 (ms) | p99 (ms) | Budget (ms) | Notes |
|------------|----------|----------|----------|-------------|-------|
| Source     |          |          |          |             |       |
| Preprocess |          |          |          |             |       |
| Detector   |          |          |          |             |       |
| Tracker    |          |          |          |             |       |
| Overlay    |          |          |          |             |       |
| Sink       |          |          |          |             |       |
