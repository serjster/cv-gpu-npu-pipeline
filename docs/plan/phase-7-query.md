# Phase 7 — Queryable VLM

**Goal:** A user query (free-text prompt, optional class filter) steers what the VLM looks for, without restarting the pipeline. The query is shared state read by the VLM scheduler when assembling each `CaptionRequest`.

This phase implements the *backend* of the query. The UI to type the query is Phase 8.

**Design patterns introduced:**

- **Single source of truth** — one `QueryState` instance, thread-safe, injected via constructor into the components that read or write it. No broadcast copies, no module-level globals.
- **Observer (optional)** — if multiple stages need to react to query changes (e.g. `Tracker` could re-emit on prompt change), `QueryState` notifies subscribers. Skip until a second consumer materialises.
- **Command extension** — `CaptionRequest` carries `prompt: str` and optional `class_filter: tuple[int, ...]`, both populated from `QueryState` at request-build time.

**Tasks:**

- [ ] `src/lowlatcv/pipeline/query.py` — `QueryState` (thread-safe; `set(text, classes=None)`, `snapshot() -> QuerySnapshot`)
- [ ] `Pipeline.set_query(text, classes=None)` public API on the orchestrator
- [ ] `CaptionScheduler` reads `QueryState.snapshot()` when building each request; in-flight requests are not modified
- [ ] Optional per-class filter applied at scheduler time (don't emit requests for filtered-out classes)
- [ ] CLI `--query "<text>"` flag for a static start-up query (dynamic query comes with the dashboard)
- [ ] Test: `set_query` is reflected in the *next* `CaptionRequest`, in-flight requests untouched
- [ ] Test: class filter drops requests for non-matching classes
- [ ] Test: thread-safety — concurrent `set` + `snapshot` produce coherent snapshots (no torn reads)
- [ ] Test: empty query falls back to the configured default prompt

**Done when:** changing the query mid-run changes the next batch of captions, the pipeline keeps running, and the unit tests cover concurrent access.
