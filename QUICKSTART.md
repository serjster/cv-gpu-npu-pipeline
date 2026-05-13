# Quickstart

Copy-pasteable CLI commands for every supported mode. Keep this in sync with
`src/lowlatcv/app.py` — when a flag is added, renamed, or removed, update this
file in the same commit (see `CLAUDE.md` → *Keep QUICKSTART in sync*).

The example source is `data/b3d/videos/hwy00.mp4` (4K aerial highway). Swap in
your own clip / device anywhere it appears.

**Related docs:**
- [`docs/debug-ui-guide.md`](docs/debug-ui-guide.md) — every indicator in the
  scene + debug window explained, plus a symptom→knob table for tuning the
  pipeline when something looks wrong.
- [`docs/plan/phase-3a-quality.md`](docs/plan/phase-3a-quality.md) — running
  log of detection/tracking quality improvements + known-open issues.

---

## 1. Setup

```bash
# macOS (Apple Silicon) — PyPI onnxruntime ships the CoreML EP
uv sync --extra detector-onnx

# Linux + AMD (ROCm GPU + XDNA NPU) — Looong's onnxruntime-migraphx wheel
# (cp313) — exposes MIGraphX + ROCM EPs against ROCm 7.x. Pulled via
# [tool.uv.sources] from a GitHub release; AMD's own repo only ships
# cp310 / cp312 today.
uv sync --extra detector-onnx-amd

# Lint / typecheck / test (after any change)
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src
uv run pytest -q
```

> **Linux system prerequisites (Arch shown — Ubuntu has equivalents):**
> ROCm (`rocm-hip-libraries` or `magma-hip`) for the GPU detector path,
> `migraphx` (the AMD compiled-graph runtime; the wheel dlopen's
> `libmigraphx_c.so.3`), `xrt` + `xrt-plugin-amdxdna` + `amdxdna-dkms`
> for the NPU, `ffmpeg` for video decode, and `ollama-rocm` if you want
> the GPU VLM path. Verify the NPU with `xrt-smi examine` —
> `RyzenAI-npu5` should be listed and `[Linux] NPU: /dev/accel/accel0`
> should appear with `flm validate`.

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

### Newer YOLO families (manual)

The Ultralytics ONNX export path is identical for YOLOv9 / v10 / v11 / v12,
so swapping in a newer family is a one-liner. Measured on the same VisDrone
GT image used in §10 (1920×1080, 327 cars):

| Family         | HF repo                          | car F1 @1280 | det ms |
|----------------|----------------------------------|-------------:|-------:|
| yolov8n        | `mshamrai/yolov8n-visdrone`      | 0.63         | 53     |
| yolov11n       | `erbayat/yolov11n-visdrone`      | 0.65         | 72     |
| yolov12s       | `jadenvr/YOLOv12s-VisDrone`      | not measured | —      |
| yolov10l       | `dalietng/yolov10l-visdrone`     | not measured | —      |
| yolo26m        | `kailunw/visdrone-yolo26m`       | 0.23 ⚠       | 185    |

Take-away: at this scale the v11n upgrade is +3% F1 for +36% latency. Stick
with v8n unless you have the headroom. **YOLO26** (Ultralytics, Jan 2026) is
real and the decoder supports its NMS-free `(1, N, 6)` output — but the only
public VisDrone-trained v26 weights (`kailunw/visdrone-yolo26m`) are
under-tuned and score below v8n. Would need to fine-tune properly to get a
fair comparison. To try v11n manually:

```bash
hf download erbayat/yolov11n-visdrone best.pt --local-dir data/models/yolov11n-visdrone
uv run python -c "from ultralytics import YOLO; YOLO('data/models/yolov11n-visdrone/best.pt').export(format='onnx', imgsz=1280, opset=12)"
mv data/models/yolov11n-visdrone/best.onnx data/models/yolov11n-visdrone-1280.onnx
uv run lowlatcv run --source data/b3d/videos/hwy00.mp4 --display \
  --detector onnx --weights data/models/yolov11n-visdrone-1280.onnx \
  --num-classes 10 --imgsz 1280 --async-detection --detect-every-n 3
```

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
... --execution-provider MIGraphXExecutionProvider    # Linux + AMD (compiled graph) — recommended on Strix Halo
... --execution-provider ROCMExecutionProvider        # Linux + AMD (HIP direct) — needs the separate onnxruntime-rocm wheel
... --execution-provider CPUExecutionProvider         # fallback
```

> **Linux + AMD first-run cost:** MIGraphX compiles the ONNX graph to AMD
> bytecode the first time a model is loaded — ~40 s on yolov8n-visdrone at
> 640. After that, steady-state detector p50 on the Radeon 8060S is ~5 ms
> (vs ~40 ms on CPU). The compile isn't cached across runs in this build;
> tolerate the cold start or use `--detector fake` for non-detection bench
> work.

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

## 6. + VLM captions (Ollama — GPU)

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

**Linux + AMD note:** the system `ollama-rocm` package provides GPU-accelerated
inference on the Radeon iGPU (8060S on Strix Halo). `ollama serve` picks ROCm
automatically. Reference latency on this box: `ibm/granite3.3-vision:2b` ~0.65 s
per caption against a 200×300 px crop.

VLM flags:

- `--vlm fake|ollama|fastflowlm|none`
- `--vlm-model <ollama-model>` e.g. `moondream`, `llava`, `qwen2-vl`
- `--vlm-host http://localhost:11434`
- `--vlm-prompt "Describe ..."`
- `--vlm-cooldown SECONDS` — per-track refresh interval
- `--vlm-rate HZ` — global rate limit (0 = unlimited)
- `--vlm-fake-latency SECONDS` — artificial latency on FakeVLM for the
  "no-impact" proof

## 6a. + VLM captions on the NPU (FastFlowLM, Linux + Ryzen AI only)

FastFlowLM runs VLMs directly on the AMD XDNA2 NPU. Linux + Strix Halo /
Strix Point / Krackan / Gorgon Point only.

```bash
# 1. Install: grab the latest .deb from
#    https://github.com/FastFlowLM/FastFlowLM/releases and extract to /opt
#    (or any user dir + set env vars below). On Arch this means:
mkdir -p ~/.local/share/fastflowlm
bsdtar xf fastflowlm_*_ubuntu*.deb -C /tmp/flm
bsdtar xf /tmp/flm/data.tar.zst -C ~/.local/share/fastflowlm
# Symlink Boost 1.91 to the expected 1.90 SONAME on Arch:
ln -sf /usr/lib/libboost_program_options.so.1.91.0 \
  ~/.local/share/fastflowlm/opt/fastflowlm/lib/flm/libboost_program_options.so.1.90.0

# 2. Env vars (drop into your shell rc):
export FLM_HOME=~/.local/share/fastflowlm/opt/fastflowlm
export LD_LIBRARY_PATH="$FLM_HOME/lib/flm:${LD_LIBRARY_PATH-}"
export FLM_XCLBIN_PATH="$FLM_HOME/share/flm/xclbins"
export FLM_CONFIG_PATH="$FLM_HOME/share/flm/model_list.json"

# 3. Verify and pull a VLM (Gemma 4 4B has NPU2 kernels in the FLM release):
$FLM_HOME/bin/flm validate    # expects NPU FW 1.1.x.x, /dev/accel/accel0
$FLM_HOME/bin/flm pull gemma4-it:e4b

# 4. Run the FLM server (default port 52625):
$FLM_HOME/bin/flm serve gemma4-it:e4b &

# 5. Pipeline with the NPU VLM backend:
uv run lowlatcv run --source data/b3d/videos/hwy00.mp4 --display \
  --detector onnx --weights data/models/yolov8n-visdrone.onnx \
  --num-classes 10 \
  --vlm fastflowlm --vlm-model gemma4-it:e4b \
  --vlm-cooldown 5 --vlm-rate 0.5
```

`--vlm-host` defaults to FLM's port automatically when `--vlm fastflowlm` is
chosen and you haven't overridden it. Reference latency on Strix Halo for the
above: ~4 s per caption end-to-end on `gemma4-it:e4b` — bigger model than the
Ollama path, so the cooldown / rate-limit are tuned lower. Smaller models that
FLM ships kernels for (e.g. `gemma4-it:e2b`, `gemma3:1b`) will get you under
1 s. See `flm list` for the catalog.

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

## 12. Debug UI

Two-window operator surface (scene + metrics) with pause/step + per-tile
activity visualisation. Full reference: [`docs/debug-ui-guide.md`](docs/debug-ui-guide.md).

```bash
uv run lowlatcv run --source data/b3d/videos/hwy00.mp4 --display \
  --detector onnx-tiled --weights data/models/yolov8n-visdrone-1280.onnx \
  --num-classes 10 --imgsz 1280 --tiles 2x2 \
  --async-detection --detect-every-n 2 \
  --tile-on-demand --tracker-min-hits 1 \
  --debug --debug-tiles
```

| Key (with Debug window focused) | Action |
|---|---|
| `Space` | Toggle pause |
| `→` | Step one frame |
| `R` | Reset tracer percentile buffers |
| `Q` | Quit-requested flag |

`--debug-tiles` paints translucent rectangles per tile on the scene:
🔴 red = recovery (tracker lost a track here) · 🔵 blue = refresh (rotating
coverage) · 🟢 green = full-sweep · ⚪ grey = never run. Border thickness
shows freshness. Corner badge: `R|F|S a<age> n<n_dets>`.

## 13. Troubleshooting

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
| ID swaps when cars pass close together           | greedy IoU matching ignored class; in crowds the "best pair first" heuristic stole a track's only candidate | fixed — Hungarian (linear_sum_assignment) IoU match, class-aware. Same-class only and globally optimal. No appearance features yet; pure-IoU ID swaps in dense crowds still possible |
| Boxes grow / gain phantom velocity over time     | Kalman had vw/vh state + huge initial velocity variance           | fixed — Kalman is now 6-state (no w/h velocity), velocity clamped, frozen on LOST         |
| Per-tile cache emits stale boxes in on-demand    | TiledOnnxDetector cached old detections from un-rerun tiles       | fixed — on-demand mode emits only this cycle's fresh detections; tracker Kalman holds rest |
| Fast cars leave a trail of LOST boxes            | Kalman has 0 velocity on first frames → predicted bbox doesn't overlap new detection → IoU=0 → new ID spawns | fixed — tracker now has a 3rd association pass: centroid distance gated by predicted box size + class. Tune via TrackerConfig.motion_distance_factor (default 2.0) |
| Boxes "eject" / shoot off in random directions    | distance-only match has a large residual → full Kalman update inferred a huge velocity → next predict flies the box | fixed — distance-only matches use a soft update (snap position+size, don't infer velocity). Max speed clamped at 50 px/frame |
| Live pipeline catches only ~3 % of reference     | DetectorConfig.max_detections capped at 100 — the heavy reference was emitting 800+ per frame; we threw away 80–90 % of true positives | fixed — default raised to 1000. Override via `--max-detections N`. At 2×2 tiles this jumps recall from 13 % → 73 % on hwy00 |
| Activity Monitor "GPU" at 1 %                    | macOS GPU column doesn't show ANE                                 | ANE is busy via CoreML EP — `powermetrics --samplers ane` to confirm                       |
| `lowlatcv` segfaults on macOS with `imshow`      | cv2 + pygame both bundle SDL2 — known objc class clash warning    | use `--display-backend sdl` (default); the cv2 fallback was removed                       |
| `Error in building plan` from CoreML EP          | model imgsz ≠ tensor imgsz                                        | re-export the ONNX at the exact imgsz you're feeding (no `dynamic=True` for CoreML EP)    |

## Known gaps (work in progress)

Authoritative running list lives at [`docs/plan/phase-3a-quality.md`](docs/plan/phase-3a-quality.md).
Highlights:

**Tracking:**
- Stale-detection drag under async at high worker latency — fast horizontal
  cars get yanked back to old positions because Kalman receives measurements
  from frame T-N at its T-th prediction. Proper fix is per-lane Kalman
  rewind.
- No appearance features → ID swaps still possible in dense traffic.

**Detection:**
- `pedestrian` / `people` / `bicycle` recall near zero on aerial 4K.
- **NMM (Non-Maximum Merging) at tile aggregation** — currently NMS *drops*
  the lower-score of two near-duplicate boundary detections; NMM would
  *merge* them. Better stability on objects straddling tile edges.
- **Batched tile inference** — today the tile loop calls `session.run` 9
  times for `tiles=3x3` (~450 ms). Batching to one `session.run` over
  `(9, 3, H, W)` would likely halve the wall time. CoreML EP compiles per
  fixed batch size so the ONNX export needs `dynamic={"images": {0:"batch"}}`
  or a fixed `batch=N`. Cheapest 2× speedup probably available.
- **Auto-slice sizing** — pick `tile_rows × tile_cols` from a target
  object-pixel range (à la SAHI's `auto_slice_resolution`) instead of the
  user guessing the grid by hand.

**Pipeline:**
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
| `--max-detections N`       | both  | hard cap on detections per frame (default 1000)   |
| `--tracker-iou-threshold X` | both | IoU floor for tracker association                 |
| `--tracker-motion-distance-factor X` | both | distance gate for the motion-distance pass (0 = off) |
| `--tracker-max-age N`      | both  | unmatched frames before ACTIVE → LOST             |
| `--tracker-lost-age N`     | both  | further unmatched frames before LOST → DEAD       |
| `--tracker-min-hits N`     | both  | matches needed before TENTATIVE → ACTIVE          |
| `--export-jsonl PATH`      | both  | per-frame JSONL export (detections + tracks)      |
| `--debug`                  | run   | open the separate metrics + pause/step window     |
| `--debug-tiles`            | run   | paint per-tile activity rectangles on scene (onnx-tiled only) |
| `--vlm fake\|ollama\|fastflowlm\|none` | both | VLM backend (fastflowlm = NPU)         |
| `--vlm-model NAME`         | both  | Ollama / FastFlowLM model name (e.g. `moondream`, `gemma4-it:e4b`) |
| `--vlm-host URL`           | both  | Ollama base URL                                   |
| `--vlm-prompt TEXT`        | both  | per-track prompt                                  |
| `--vlm-cooldown SECONDS`   | both  | per-track refresh interval                        |
| `--vlm-rate HZ`            | both  | global rate limit                                 |
| `--vlm-fake-latency S`     | both  | FakeVLM synthetic latency                         |
| `--report-format table\|json\|csv` | bench |                                           |
| `--report-path PATH`       | bench | write report to file                              |
