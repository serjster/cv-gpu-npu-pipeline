#!/usr/bin/env python3
"""Build a per-frame "ground-truth-ish" reference for a video.

Runs the full lowlatcv pipeline offline with whatever model + tile config
you point it at — no time budget — and writes per-frame JSONL via
``JsonlExportSink``. Designed for heavy models (e.g.
``yolov8x-visdrone-1920``) tiled across the frame so detection quality is
the best the available weights can produce. Used as a pseudo-GT for
diffing against the real-time pipeline.

Usage::

    uv run python scripts/build_reference.py \\
      --source data/b3d/videos/hwy00.mp4 \\
      --weights data/models/yolov8x-visdrone-1920.onnx \\
      --imgsz 1920 --tiles 3x3 \\
      --out data/refs/hwy00-x-1920-3x3.jsonl \\
      --frames 60
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import time
from pathlib import Path

from lowlatcv.app import build_pipeline
from lowlatcv.config import (
    DetectorConfig,
    PipelineConfig,
    PreprocessConfig,
    SinkConfig,
    SourceConfig,
)
from lowlatcv.metrics.reporter import TableReporter
from lowlatcv.metrics.tracer import Tracer


def parse_tiles(spec: str | None) -> tuple[int, int]:
    if spec is None:
        return 1, 1
    parts = spec.lower().split("x")
    if len(parts) != 2:
        raise SystemExit(f"--tiles must be ROWSxCOLS, got {spec!r}")
    return int(parts[0]), int(parts[1])


async def main_async(args: argparse.Namespace) -> None:
    rows, cols = parse_tiles(args.tiles)
    backend = "onnx-tiled" if (rows * cols) > 1 else "onnx"
    cfg = PipelineConfig(
        source=SourceConfig(uri=str(args.source)),
        preprocess=PreprocessConfig(width=args.imgsz, height=args.imgsz),
        detector=DetectorConfig(
            backend=backend,
            weights=str(args.weights),
            num_classes=args.num_classes,
            score_threshold=args.score_threshold,
            nms_threshold=args.iou_threshold,
            max_detections=args.max_detections,
            tile_rows=rows,
            tile_cols=cols,
            tile_overlap=args.tile_overlap,
            tile_input_size=args.imgsz,
        ),
        sink=SinkConfig(kind="null"),
    )
    tracer = Tracer()
    reporter = TableReporter()
    tracer.subscribe(reporter)

    frame_limit = args.frames if args.frames > 0 else None
    args.out.parent.mkdir(parents=True, exist_ok=True)

    print(f"running offline reference → {args.out}")
    t0 = time.perf_counter()
    pipeline = build_pipeline(
        cfg,
        tracer,
        frame_limit=frame_limit,
        export_jsonl=args.out,
    )
    await pipeline.run()
    dt = time.perf_counter() - t0
    print(f"done in {dt:.1f}s")
    print(reporter.render())


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--weights", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--imgsz", type=int, default=1920)
    p.add_argument("--tiles", type=str, default="3x3", help="ROWSxCOLS (1x1 = no tiling)")
    p.add_argument("--tile-overlap", type=float, default=0.2)
    p.add_argument("--num-classes", type=int, default=10)
    p.add_argument("--score-threshold", type=float, default=0.30)
    p.add_argument("--iou-threshold", type=float, default=0.45)
    p.add_argument("--max-detections", type=int, default=1000)
    p.add_argument("--frames", type=int, default=0, help="0 = whole video")
    args = p.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    # dataclasses import kept to keep mypy quiet about replace usage above.
    _ = dataclasses
    main()
