# Quickstart

Copy-pasteable CLI commands for every supported mode. Keep this in sync with
`src/lowlatcv/app.py` — when a flag is added, renamed, or removed, update this
file in the same commit (see `CLAUDE.md` → *Keep QUICKSTART in sync*).

The example source is `data/b3d/videos/hwy00.mp4` (4K aerial highway). Swap in
your own clip / device anywhere it appears.

---

## 1. Setup

```bash
# One-off: install dependencies into .venv
uv sync

# Lint / typecheck / test (after any change)
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src
uv run pytest -q
```

## 2. Get YOLOv8 weights

```bash
# VisDrone-trained (recommended for aerial / drone footage — 10 classes:
# pedestrian, people, bicycle, car, van, truck, tricycle, awning-tricycle,
# bus, motor)
uv run python scripts/download_yolov8_weights.py --variant visdrone

# Vanilla COCO (80 classes, street-view trained — works for normal camera
# angles; struggles with aerial scale)
uv run python scripts/download_yolov8_weights.py --variant coco

# Larger / more accurate VisDrone
uv run python scripts/download_yolov8_weights.py --variant visdrone-s --imgsz 1280
```

Weights land in `data/models/`. The script also prints the right `lowlatcv`
command for each variant.

## 3. Raw playback (decode + GPU display only)

Baseline for "is the framework adding overhead?" — no preprocess, no
detector, no overlay. Source → SDLDisplaySink (Metal on macOS, Vulkan/GL on
Linux). Paces to the file's intrinsic FPS by default.

```bash
uv run lowlatcv run --raw --source data/b3d/videos/hwy00.mp4 --display
```

Useful flags:

- `--fps N` override pace (`0` disables, source goes as fast as decode allows)
- `--vsync` enable display vsync
- `--sink null` headless decode-only — useful to isolate decoder cost

## 4. Detection + tracking, no captions

**Accuracy is dominated by imgsz, not model size.** Numbers below measured on
one VisDrone test image (`0000126_11844_d_0000130.jpg`, 1920×1080, 327 cars)
with `scripts/eval_detector.py`:

| Config                    | car F1 | overall F1 | det ms | ~fps |
|---------------------------|--------|-----------|--------|------|
| n @ 640 single            | 0.45   | 0.39      | 15     | 30   |
| s @ 640 single            | 0.48   | 0.42      | 25     | 30   |
| **n @ 1280 single**       | 0.63   | 0.56      | 53     | ~19  |
| s @ 1280 single           | 0.68   | 0.62      | 97     | ~10  |
| n @ 640 tiles 3×3         | 0.68   | 0.60      | 119    | ~8   |
| s @ 640 tiles 3×3         | 0.72   | 0.65      | 172    | ~6   |
| **n @ 1280 tiles 2×2**    | **0.74** | **0.67**  | 184    | ~5   |

The ONNX export is **shape-locked** to its export imgsz (CoreML EP refuses
mismatches). Pick one of these per use-case:

```bash
# Real-time-ish (~19 fps), good recall — recommended default for live demo
uv run python scripts/download_yolov8_weights.py --variant visdrone --imgsz 1280
uv run lowlatcv run --source data/b3d/videos/hwy00.mp4 --display \
  --detector onnx --weights data/models/yolov8n-visdrone-1280.onnx \
  --num-classes 10 --imgsz 1280
```

```bash
# Best recall (~5 fps) — tile a 1280-export model 2×2 over a 4K frame
uv run lowlatcv run --source data/b3d/videos/hwy00.mp4 --display \
  --detector onnx-tiled --weights data/models/yolov8n-visdrone-1280.onnx \
  --num-classes 10 --tiles 2x2 --fps 0
```

```bash
# Decouple heavy detector from the per-frame critical path. The tracker
# Kalman-propagates boxes between detection updates so playback stays at
# source FPS even when the detector runs slower. Detection runs every Nth
# frame in a worker thread.
uv run lowlatcv run --source data/b3d/videos/hwy00.mp4 --display \
  --detector onnx --weights data/models/yolov8n-visdrone-1280.onnx \
  --num-classes 10 --imgsz 1280 \
  --async-detection --detect-every-n 3
```

```bash
# Tile-on-demand: detector runs only on tiles where the tracker reports
# lost/tentative tracks plus one rotating refresh tile per cycle. Per-tile
# detection cache keeps the aggregate output full-frame. Combine with
# --async-detection so the per-frame critical path stays cheap.
uv run lowlatcv run --source data/b3d/videos/hwy00.mp4 --display \
  --detector onnx-tiled --weights data/models/yolov8n-visdrone.onnx \
  --num-classes 10 --tiles 3x3 \
  --tile-on-demand --tile-refresh-tiles-per-cycle 1 \
  --async-detection --detect-every-n 2
```

(`--tile-input-size` auto-snaps to the model's fixed imgsz, so you only need
to pass it if the model was exported with `dynamic=True`.)

```bash
# Fast smoke test at 640 (lower recall but ~30 fps; OK for sanity checks)
uv run python scripts/download_yolov8_weights.py --variant visdrone
uv run lowlatcv run --source data/b3d/videos/hwy00.mp4 --display \
  --detector onnx --weights data/models/yolov8n-visdrone.onnx \
  --num-classes 10
```

With COCO weights instead (only useful for street-view footage):

```bash
uv run lowlatcv run --source data/b3d/videos/hwy00.mp4 --display \
  --detector onnx --weights data/models/yolov8n.onnx \
  --num-classes 80
```

Tune detection thresholds:

```bash
... --score-threshold 0.30 --iou-threshold 0.50
```

Force a specific ONNX Runtime execution provider (auto-picked by default):

```bash
... --execution-provider CoreMLExecutionProvider     # macOS Apple Si
... --execution-provider ROCMExecutionProvider        # Linux + AMD
... --execution-provider MIGraphXExecutionProvider    # Linux + AMD (compiled graph)
... --execution-provider CPUExecutionProvider         # fallback
```

## 5. Tiled detection (SAHI-style, for tiny objects)

Slice the frame into ROWS×COLS overlapping tiles, run the detector on each,
merge with global NMS. Much higher recall on aerial / drone footage; ~N×N
slower than single-tile.

```bash
uv run lowlatcv run --source data/b3d/videos/hwy00.mp4 --display \
  --detector onnx-tiled --weights data/models/yolov8n-visdrone.onnx \
  --num-classes 10 \
  --tiles 3x3 --tile-overlap 0.2 --tile-input-size 640 \
  --fps 0
```

`--fps 0` removes source pacing — the tiled detector (~140 ms / 7 fps) sets
the rate naturally via back-pressure.

## 6. + VLM captions (Ollama)

Needs a local Ollama server with the model pulled:

```bash
ollama pull moondream
ollama serve   # (or already running)
```

Then:

```bash
uv run lowlatcv run --source data/b3d/videos/hwy00.mp4 --display \
  --detector onnx --weights data/models/yolov8n-visdrone.onnx \
  --num-classes 10 \
  --vlm ollama --vlm-model moondream \
  --vlm-cooldown 3 --vlm-rate 1
```

VLM runs **off** the critical path on a worker thread. Captions appear under
each tracked box every few seconds.

VLM flags:

- `--vlm fake|ollama|none`
- `--vlm-model <ollama-model>` e.g. `moondream`, `llava`, `qwen2-vl`
- `--vlm-host http://localhost:11434`
- `--vlm-prompt "Describe ..."`
- `--vlm-cooldown SECONDS` — per-track refresh interval
- `--vlm-rate HZ` — global rate limit (0 = unlimited)
- `--vlm-fake-latency SECONDS` — artificial latency on FakeVLM for the
  "no-impact" proof

## 7. Benchmark mode (no display, latency report)

Always uses NullSink. Detector / tracker / VLM all selectable identically.

```bash
# Just decode + null sink — baseline source cost
uv run lowlatcv bench --source data/b3d/videos/hwy00.mp4 --frames 1000

# Full pipeline with VisDrone weights
uv run lowlatcv bench --source data/b3d/videos/hwy00.mp4 --frames 200 \
  --detector onnx --weights data/models/yolov8n-visdrone.onnx --num-classes 10

# Tiled bench
uv run lowlatcv bench --source data/b3d/videos/hwy00.mp4 --frames 100 \
  --detector onnx-tiled --weights data/models/yolov8n-visdrone.onnx \
  --num-classes 10 --tiles 3x3

# Prove VLM does not block the critical path (1 s artificial latency)
uv run lowlatcv bench --source data/b3d/videos/hwy00.mp4 --frames 90 \
  --detector fake --vlm fake --vlm-fake-latency 1.0 --vlm-rate 0 --vlm-cooldown 0.1

# JSON output for diffing across runs / hosts / FPGA bring-up
uv run lowlatcv bench --source data/b3d/videos/hwy00.mp4 --frames 1000 \
  --report-format json --report-path bench/macos-visdrone.json
```

## 8. Webcam / RTSP / network sources

```bash
uv run lowlatcv run --source webcam:0 --display
uv run lowlatcv run --source 0 --display              # bare digit also = webcam
uv run lowlatcv run --source rtsp://cam.local/stream --display
uv run lowlatcv run --source file:///abs/path/clip.mp4 --display
```

## 9. Imgsz override

If you exported ONNX at a non-640 size, match it with `--imgsz`:

```bash
uv run python scripts/download_yolov8_weights.py --variant visdrone --imgsz 1280
uv run lowlatcv run --source data/b3d/videos/hwy00.mp4 --display \
  --detector onnx --weights data/models/yolov8n-visdrone-1280.onnx \
  --num-classes 10 --imgsz 1280
```

## 10. Objective accuracy check (VisDrone GT)

Eyeballing detection quality is unreliable. `scripts/eval_detector.py` runs
the configured detector over a labeled VisDrone image and prints per-class
precision / recall / F1 vs ground truth.

```bash
# Download a few labeled samples (113 MB labels file + chosen images)
mkdir -p data/visdrone-sample
hf download Voxel51/VisDrone2019-DET --repo-type dataset \
  metadata.json samples.json \
  data/0000126_11844_d_0000130.jpg \
  --local-dir data/visdrone-sample

# Single-tile 640
uv run python scripts/eval_detector.py \
  --samples-json data/visdrone-sample/samples.json \
  --image data/visdrone-sample/data/0000126_11844_d_0000130.jpg \
  --weights data/models/yolov8n-visdrone.onnx --num-classes 10 \
  --save-render /tmp/eval_single.jpg

# Tiled 3x3 (much higher recall on aerial scale)
uv run python scripts/eval_detector.py \
  --samples-json data/visdrone-sample/samples.json \
  --image data/visdrone-sample/data/0000126_11844_d_0000130.jpg \
  --weights data/models/yolov8n-visdrone.onnx --num-classes 10 \
  --tiles 3x3 --save-render /tmp/eval_tiled3x3.jpg
```

`--save-render` writes an annotated JPEG with GT in red and predictions in
green for visual sanity-check.

## 11. Config file overlay

Everything above can be set in YAML and loaded once, instead of long flags:

```bash
uv run lowlatcv run --config configs/hwy00-visdrone.yaml
```

Layout: keys mirror `PipelineConfig` (`source`, `preprocess`, `detector`,
`tracker`, `vlm`, `overlay`, `sink`, `metrics`). Env overrides win over YAML:
`LOWLATCV_DETECTOR__SCORE_THRESHOLD=0.35`.

---

## 12. Troubleshooting

Common failure modes seen so far and the knob that fixes each. Add a row
when you hit a new one — this is meant to be the muscle memory we
accumulate as the project matures.

| Symptom                                          | Likely cause                                                      | Fix                                                                                       |
|--------------------------------------------------|-------------------------------------------------------------------|-------------------------------------------------------------------------------------------|
| Boxes flicker on / off                           | per-frame IoU matching can't keep up with motion at 4K            | `--async-detection` + Kalman is enabled in tracker by default; combine with `--detect-every-n 2-3` so tracks coast on motion model |
| Almost no cars on aerial / drone footage         | COCO-trained yolov8n can't see 5-10 px cars                       | use `--variant visdrone` weights (`scripts/download_yolov8_weights.py`), `--num-classes 10` |
| Recall still low with VisDrone @ 640             | cars too small inside 640 letterbox                               | re-export at `--imgsz 1280` *and* pass `--imgsz 1280` to the CLI (export size is shape-locked) |
| Even more recall needed                          | need to zoom further into the frame                               | `--detector onnx-tiled --tiles 3x3` (or 2×2); combine with `--tile-on-demand --async-detection` to stay real-time |
| `--tile-input-size N` does nothing               | ONNX shape-locked to its export imgsz; CoreML EP rejects mismatch | TiledOnnxDetector auto-snaps to the model's imgsz now — re-export the model at the size you want |
| 200 % CPU on raw playback                        | cv2.imshow software-blits 4K frames on macOS                      | already swapped to SDLDisplaySink (Metal/GL); raw mode now ~15 % CPU at 4K                |
| Many boxes on factory yards / parking lots       | model fires on dense object clusters in tiles                     | raise `--score-threshold 0.35-0.45`; or use a larger model (`--variant visdrone-s`)       |
| ID swaps when cars pass close together           | greedy IoU matching, no appearance features                       | known limitation; add a re-ID head later (phase 9 perf)                                   |
| Boxes grow / gain phantom velocity over time     | Kalman had vw/vh state + huge initial velocity variance           | fixed — Kalman is now 6-state (no w/h velocity), velocity clamped, frozen on LOST         |
| Per-tile cache emits stale boxes in on-demand    | TiledOnnxDetector cached old detections from un-rerun tiles       | fixed — on-demand mode emits only this cycle's fresh detections; tracker Kalman holds rest |
| Fast cars leave a trail of LOST boxes            | Kalman has 0 velocity on first frames → predicted bbox doesn't overlap new detection → IoU=0 → new ID spawns | fixed — tracker now has a 3rd association pass: centroid distance gated by predicted box size + class. Tune via TrackerConfig.motion_distance_factor (default 2.0) |
| Activity Monitor "GPU" at 1 %                    | macOS GPU column doesn't show ANE                                 | ANE is busy via CoreML EP — `powermetrics --samplers ane` to confirm                       |
| `lowlatcv` segfaults on macOS with `imshow`      | cv2 + pygame both bundle SDL2 — known objc class clash warning    | use `--display-backend sdl` (default); the cv2 fallback was removed                       |
| `Error in building plan` from CoreML EP          | model imgsz ≠ tensor imgsz                                        | re-export the ONNX at the exact imgsz you're feeding (no `dynamic=True` for CoreML EP)    |

## Known gaps (work in progress)

- Tracker has no appearance feature → ID swaps in dense traffic. Add re-ID or
  motion-only Hungarian assignment later.
- VisDrone `pedestrian` / `people` / `bicycle` recall is near zero at 640 — too
  small. Tile-on-demand helps a bit; a larger model or further zoom needed.
- Tile-on-demand cold start: brand-new clips have no track hints yet, so the
  first ~9 frames are needed for the rotating refresh to cover all tiles.
- Preprocess still runs on the critical path even when `--detector onnx-tiled`
  (which ignores `Frame.tensor`). Wasted ~3-15 ms of CPU per frame — move
  into the AsyncDetector worker.
- cv2.VideoCapture forces a BGR memcpy per frame. PyAV / direct VideoToolbox
  hand-off could skip that and feed NV12 straight to the GPU texture.

## Cheat sheet of every CLI flag

Built from `src/lowlatcv/app.py`. Re-run `uv run lowlatcv run --help` for the
authoritative list.

| Flag                       | Mode  | Notes                                             |
|----------------------------|-------|---------------------------------------------------|
| `--source URI`             | both  | file path, `webcam:N`, `N`, `rtsp://…`, `file://…`|
| `--config PATH`            | both  | YAML overlay                                      |
| `--frames N`               | both  | `run`: 0 = until EOF; `bench`: 1000 default       |
| `--display`                | run   | force `SinkConfig.kind=display`                   |
| `--sink display\|null\|file` | run | sink kind override                                |
| `--output PATH`            | run   | file sink path                                    |
| `--fps N`                  | run   | source pacing Hz; 0 disables                      |
| `--vsync`                  | run   | display vsync                                     |
| `--raw`                    | run   | Source → Sink only                                |
| `--imgsz N`                | both  | square preprocess input size                      |
| `--detector fake\|onnx\|onnx-tiled\|coreml` | both | detector backend           |
| `--weights PATH`           | both  | model file                                        |
| `--num-classes N`          | both  | COCO=80, VisDrone=10                              |
| `--score-threshold X`      | both  | detection confidence floor                        |
| `--iou-threshold X`        | both  | NMS IoU                                           |
| `--execution-provider EP`  | both  | ONNX Runtime EP override                          |
| `--tiles ROWSxCOLS`        | both  | tiled inference grid                              |
| `--tile-overlap X`         | both  | fractional overlap [0, 0.95)                      |
| `--tile-input-size N`      | both  | per-tile letterbox target                         |
| `--async-detection`        | both  | detector runs on a worker thread (off crit path)  |
| `--detect-every-n N`       | both  | submit a frame to async detector every N frames   |
| `--tile-on-demand`         | both  | onnx-tiled only: run only tracker-hinted tiles    |
| `--tile-refresh-tiles-per-cycle N` | both | rotating refresh tiles per cycle (default 1) |
| `--vlm fake\|ollama\|none` | both  | VLM backend                                       |
| `--vlm-model NAME`         | both  | Ollama model name                                 |
| `--vlm-host URL`           | both  | Ollama base URL                                   |
| `--vlm-prompt TEXT`        | both  | per-track prompt                                  |
| `--vlm-cooldown SECONDS`   | both  | per-track refresh interval                        |
| `--vlm-rate HZ`            | both  | global rate limit                                 |
| `--vlm-fake-latency S`     | both  | FakeVLM synthetic latency                         |
| `--report-format table\|json\|csv` | bench |                                           |
| `--report-path PATH`       | bench | write report to file                              |
