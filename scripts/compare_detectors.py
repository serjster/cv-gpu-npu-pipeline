#!/usr/bin/env python3
"""Render the same video frame through multiple detector configurations.

Visual side-by-side of YOLO families / weights / input sizes. Drops one
annotated JPEG per config plus a grid composite so you can flip through
and eyeball which detector is finding what.

Usage::

    uv run python scripts/compare_detectors.py \\
      --source data/b3d/videos/hwy00.mp4 --frame 100 \\
      --out-dir /tmp/cmp \\
      --config yolov8n-visdrone-1280:data/models/yolov8n-visdrone-1280.onnx:1280 \\
      --config yolov11n-visdrone-1280:data/models/yolov11n-visdrone-1280.onnx:1280 \\
      --config yolo26m-visdrone-1280:data/models/yolo26m-visdrone-1280.onnx:1280

Each ``--config`` is ``LABEL:WEIGHTS:IMGSZ``. Order of configs is preserved
in the grid (top-left → top-right → bottom-left → bottom-right …).
"""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from lowlatcv.config import DetectorConfig, PreprocessConfig
from lowlatcv.models.frame import Frame
from lowlatcv.pipeline.detector import OnnxDetector
from lowlatcv.pipeline.preprocess import Preprocess

VISDRONE_CLASSES = (
    "pedestrian",
    "people",
    "bicycle",
    "car",
    "van",
    "truck",
    "tricycle",
    "awning-tri",
    "bus",
    "motor",
)

# BGR colour per VisDrone class — green for cars, distinct accents per type.
CLASS_COLORS: dict[str, tuple[int, int, int]] = {
    "car": (0, 255, 0),
    "van": (0, 200, 200),
    "truck": (255, 128, 0),
    "bus": (0, 128, 255),
    "motor": (255, 0, 255),
    "bicycle": (255, 255, 0),
    "tricycle": (200, 200, 200),
    "awning-tri": (180, 180, 180),
    "pedestrian": (0, 0, 255),
    "people": (0, 0, 200),
}


def parse_config(spec: str) -> tuple[str, Path, int]:
    parts = spec.split(":")
    if len(parts) != 3:
        raise SystemExit(f"--config must be LABEL:WEIGHTS:IMGSZ, got {spec!r}")
    return parts[0], Path(parts[1]), int(parts[2])


async def run_one(
    weights: Path,
    imgsz: int,
    img: NDArray[np.uint8],
    num_classes: int,
    score_threshold: float,
    iou_threshold: float,
) -> tuple[list, float]:
    pre = Preprocess(PreprocessConfig(width=imgsz, height=imgsz, layout="NCHW", normalize=True))
    det = OnnxDetector(
        DetectorConfig(
            backend="onnx",
            weights=str(weights),
            num_classes=num_classes,
            score_threshold=score_threshold,
            nms_threshold=iou_threshold,
            max_detections=1000,
        )
    )
    await pre.setup()
    await det.setup()
    try:
        f = Frame(id=0, timestamp_ns=time.perf_counter_ns(), image=img.copy())
        f = await pre.process(f)
        t0 = time.perf_counter()
        f = await det.process(f)
        dt_ms = (time.perf_counter() - t0) * 1000
        return list(f.detections), dt_ms
    finally:
        await det.teardown()


def render(
    img: NDArray[np.uint8],
    dets: list,
    title: str,
    dt_ms: float,
    class_names: tuple[str, ...],
) -> NDArray[np.uint8]:
    out = img.copy()
    counts: dict[str, int] = {}
    for d in dets:
        name = class_names[d.class_id] if 0 <= d.class_id < len(class_names) else str(d.class_id)
        counts[name] = counts.get(name, 0) + 1
        colour = CLASS_COLORS.get(name, (200, 200, 200))
        x1, y1, x2, y2 = d.bbox
        cv2.rectangle(out, (x1, y1), (x2, y2), colour, 2)
    h, w = out.shape[:2]
    cv2.rectangle(out, (0, 0), (w, 110), (0, 0, 0), -1)
    summary = " ".join(f"{n}={c}" for n, c in sorted(counts.items(), key=lambda x: -x[1])[:6])
    cv2.putText(out, title, (15, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
    cv2.putText(
        out,
        f"{len(dets)} dets  {dt_ms:.0f} ms  {summary}",
        (15, 85),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (200, 255, 200),
        2,
    )
    return out


def build_grid(panels: list[NDArray[np.uint8]]) -> NDArray[np.uint8]:
    if not panels:
        raise ValueError("no panels to grid")
    n = len(panels)
    cols = 2 if n > 1 else 1
    rows = (n + cols - 1) // cols
    h, w = panels[0].shape[:2]
    grid = np.zeros((h * rows, w * cols, 3), dtype=np.uint8)
    for i, p in enumerate(panels):
        r, c = divmod(i, cols)
        grid[r * h : (r + 1) * h, c * w : (c + 1) * w] = p
    return grid


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True, help="video file")
    p.add_argument("--frame", type=int, default=100, help="0-indexed frame to grab")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument(
        "--config",
        action="append",
        required=True,
        help="LABEL:WEIGHTS:IMGSZ — pass multiple times",
    )
    p.add_argument("--num-classes", type=int, default=10)
    p.add_argument("--score-threshold", type=float, default=0.30)
    p.add_argument("--iou-threshold", type=float, default=0.45)
    p.add_argument(
        "--scaled-width",
        type=int,
        default=1280,
        help="downscale each rendered panel to this width (saves disk + viewer-friendly)",
    )
    args = p.parse_args()

    cap = cv2.VideoCapture(str(args.source))
    cap.set(cv2.CAP_PROP_POS_FRAMES, args.frame)
    ok, img = cap.read()
    cap.release()
    if not ok:
        raise SystemExit(f"failed to read frame {args.frame} of {args.source}")
    print(f"frame {args.frame}: shape={img.shape}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    panels: list[NDArray[np.uint8]] = []
    for spec in args.config:
        label, weights, imgsz = parse_config(spec)
        dets, dt_ms = asyncio.run(
            run_one(
                weights,
                imgsz,
                img,
                args.num_classes,
                args.score_threshold,
                args.iou_threshold,
            )
        )
        print(f"  {label:30s} | {len(dets):4d} dets | {dt_ms:6.1f} ms")
        rendered = render(img, dets, label, dt_ms, VISDRONE_CLASSES)
        h, w = rendered.shape[:2]
        scaled = cv2.resize(rendered, (args.scaled_width, int(args.scaled_width * h / w)))
        fname = args.out_dir / f"{label.replace(' ', '_')}.jpg"
        cv2.imwrite(str(fname), scaled, [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"    saved {fname}")
        panels.append(scaled)

    grid = build_grid(panels)
    # Limit grid height so it stays viewer-friendly.
    target_h = 1440
    if grid.shape[0] > target_h:
        new_w = int(grid.shape[1] * target_h / grid.shape[0])
        grid = cv2.resize(grid, (new_w, target_h))
    grid_path = args.out_dir / "grid.jpg"
    cv2.imwrite(str(grid_path), grid, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"grid → {grid_path}")


if __name__ == "__main__":
    main()
