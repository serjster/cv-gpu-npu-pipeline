# Phase 2 — Source & sink (end-to-end skeleton)

**Goal:** A real video frame travels from a source through a preprocess passthrough to a sink, with bounded back-pressure and a working latency report. No detection yet — this phase validates the framework on real frame data.

**Design patterns introduced:**

- **Strategy** — `FrameSource` and `FrameSink` are interchangeable backends behind a single protocol.
- **Adapter** — `cv2.VideoCapture` and `cv2.imshow` wrapped to emit/consume the internal `Frame` type rather than leaking OpenCV types upstream/downstream.
- **Factory Method** — `FrameSource.from_uri(uri)` selects file vs webcam vs RTSP from the URI scheme.
- **Producer–Consumer** — bounded queues between stages with explicit `tready`-equivalent back-pressure.

**Tasks:**

- [ ] `src/lowlatcv/pipeline/source.py` — `FileSource` (cv2.VideoCapture file backend)
- [ ] `src/lowlatcv/pipeline/source.py` — `WebcamSource` (cv2.VideoCapture device index, V4L2 on Linux)
- [ ] `FrameSource.from_uri(uri)` Factory Method (`file://`, `webcam:0`, `rtsp://`)
- [ ] `src/lowlatcv/pipeline/preprocess.py` — `Preprocess` stage (letterbox resize + BGR→RGB + normalise + NCHW pack); shape from `PreprocessConfig`
- [ ] `src/lowlatcv/pipeline/sink.py` — `DisplaySink` (OpenCV imshow on main thread)
- [ ] `src/lowlatcv/pipeline/sink.py` — `NullSink` (benchmark mode, no rendering)
- [ ] `src/lowlatcv/pipeline/sink.py` — `FileSink` (ffmpeg writer) — defer if time-pressed; track here
- [ ] Wire `FrameSource → Preprocess → Sink` minimally in `app.build_pipeline(cfg)`
- [ ] CLI: `lowlatcv run --source <path|webcam:0> --display` plays the stream
- [ ] CLI: `lowlatcv bench --source <path> --frames 1000` reports source/preproc/sink p50/p90/p99
- [ ] All inter-stage queues default `maxsize=2`
- [ ] Back-pressure regression test: a sleep-injected slow stage stalls upstream, queue depth never exceeds 2
- [ ] Test: `FileSource` yields exactly N frames for a known fixture clip
- [ ] Test: `Preprocess` output tensor shape and dtype match `PreprocessConfig`
- [ ] Test: `WebcamSource` opens / closes cleanly (skip the test when no device)
- [ ] Test: `NullSink` consumes without leaking memory across 1000 frames (object count assertion)

**Done when:** `lowlatcv run --source <mp4> --display` plays a real file in a window, `lowlatcv bench` produces a three-row latency table, and the back-pressure test holds queue depths to `maxsize=2`.
