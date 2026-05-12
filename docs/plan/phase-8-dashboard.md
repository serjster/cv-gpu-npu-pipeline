# Phase 8 — Dashboard & control UI

**Goal:** A live operator surface — annotated video stream + prompt input for the VLM query + per-stage metrics + start/stop and source-selection controls.

## Decision (must resolve before tasks)

**Web vs native vs hybrid.** Capture the resolution at the top of this file before opening any task below.

| | Web (FastAPI + simple JS frontend) | Native (PySide6 / Qt) | Hybrid (OpenCV imshow + web/native control panel) |
|---|---|---|---|
| Video latency | Higher (encode + WebSocket / MJPEG / WebRTC) | Lowest (Qt widget) | Lowest (imshow stays direct) |
| Dev velocity | High (FastAPI scaffolding) | Medium (Qt boilerplate) | Medium (two-process glue) |
| Cross-machine access | Yes | No | Partial (control panel only) |
| Process model | Single | Single | Two-process (imshow + dashboard) |
| Fits CV ecosystem | OK | Best (Qt + OpenCV pairs cleanly) | OK |
| Operator polish | Familiar browser UX | Native feel | Functional |

Recommendation: start with **Web (FastAPI + simple JS)** unless live-video latency turns out to be a problem in Phase 9. Web is the cheapest path to the controls + metrics surface, and the OpenCV imshow display already exists as a low-latency fallback. The Strategy pattern means the Sink can grow a `WebSink` alongside the existing `DisplaySink` without disruption.

Tasks below assume the Web path. If a different option is chosen, rewrite the task list accordingly.

- [ ] **Decision resolved** — record choice + rationale at the top of this file

**Design patterns introduced:**

- **Strategy** — a new `WebSink` (or `WebSocketBroadcaster` stage tee'd off `Overlay`) joins the existing `Sink` family.
- **Pub/Sub** — the metrics `Reporter` gets a `WebSocketReporter` subscriber that pushes the latency table to the dashboard.
- **MVC (or thin variant)** — backend exposes `Pipeline.set_query` / `start` / `stop`; the frontend is a view.
- **Adapter** — the dashboard API is the only place where the internal `PipelineConfig` is rendered to/from JSON.

**Tasks (Web path):**

- [ ] FastAPI app under `src/lowlatcv/dashboard/server.py`, mounted by a new `lowlatcv serve` CLI subcommand
- [ ] `/api/start` and `/api/stop` endpoints driving `Pipeline.start()` / `stop()`
- [ ] `/api/query` POST endpoint → `Pipeline.set_query(text, classes)`
- [ ] `/ws/frames` WebSocket → annotated frames as MJPEG-over-WebSocket or per-frame JPEG blobs (start simple, optimise in Phase 9 if needed)
- [ ] `/ws/metrics` WebSocket → per-stage p50/p90/p99 + queue depths, pushed by `WebSocketReporter`
- [ ] Static frontend: single `index.html` + minimal JS (no build step), `<video>` or `<canvas>` consumer, prompt input, metrics table
- [ ] Source selector field (file path / `webcam:N`) wired to `start`
- [ ] Test: `set_query` API call updates the next `CaptionRequest` (reuses Phase 7 test infra)
- [ ] Test: metrics WebSocket emits a snapshot on connect, then updates on the configured interval
- [ ] Test: start/stop is idempotent and safe to call repeatedly

**Done when:** an operator opens the dashboard, picks a source, starts the pipeline, sees annotated video, types a prompt, and watches captions shift accordingly. Metrics update live.
