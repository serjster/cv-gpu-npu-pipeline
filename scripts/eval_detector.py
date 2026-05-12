#!/usr/bin/env python3
"""Evaluate a configured detector against VisDrone ground truth.

Loads the VisDrone 2019 DET samples.json (FiftyOne export), picks images by
path, runs ``OnnxDetector`` or ``TiledOnnxDetector`` over each, and computes
per-class precision / recall / F1 / AP@0.5 plus an overall summary. Useful
to tell whether tweaking ``--imgsz``, switching weights, or enabling tiling
actually helped on real labeled aerial scenes, rather than eyeballing.

Usage::

    uv run python scripts/eval_detector.py \\
      --samples-json data/visdrone-sample/samples.json \\
      --image data/visdrone-sample/data/0000126_11844_d_0000130.jpg \\
      --weights data/models/yolov8n-visdrone.onnx --num-classes 10

    # Tiled
    uv run python scripts/eval_detector.py ... --tiles 3x3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from lowlatcv.config import DetectorConfig, PreprocessConfig
from lowlatcv.models.frame import Detection, Frame
from lowlatcv.pipeline.detector import OnnxDetector, TiledOnnxDetector
from lowlatcv.pipeline.preprocess import Preprocess

# VisDrone categories (mshamrai yolov8n-visdrone training class ids match).
VISDRONE_CLASSES = (
    "pedestrian",
    "people",
    "bicycle",
    "car",
    "van",
    "truck",
    "tricycle",
    "awning-tricycle",
    "bus",
    "motor",
)
LABEL_TO_ID = {name: i for i, name in enumerate(VISDRONE_CLASSES)}


def load_gt(
    samples_json: Path, image_rel: str
) -> tuple[list[tuple[int, tuple[int, int, int, int]]], int, int]:
    """Return (list of (class_id, xyxy)), width, height for ``image_rel`` (matching ``filepath``)."""
    with open(samples_json) as f:
        data = json.load(f)
    for s in data["samples"]:
        if s["filepath"].endswith(image_rel) or image_rel.endswith(s["filepath"]):
            W = s["metadata"]["width"]
            H = s["metadata"]["height"]
            gt: list[tuple[int, tuple[int, int, int, int]]] = []
            for d in s["ground_truth"]["detections"]:
                label = d["label"]
                if label not in LABEL_TO_ID:
                    continue  # skip "ignore_regions", "others"
                x, y, w, h = d["bounding_box"]
                x1 = int(x * W)
                y1 = int(y * H)
                x2 = int((x + w) * W)
                y2 = int((y + h) * H)
                gt.append((LABEL_TO_ID[label], (x1, y1, x2, y2)))
            return gt, W, H
    raise SystemExit(f"image {image_rel!r} not found in {samples_json}")


def iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    aa = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    bb = max(0, bx2 - bx1) * max(0, by2 - by1)
    return inter / (aa + bb - inter)


def evaluate(
    detections: list[Detection],
    gt: list[tuple[int, tuple[int, int, int, int]]],
    iou_threshold: float = 0.5,
    class_agnostic: bool = False,
) -> dict[str, dict[str, float]]:
    """Per-class precision / recall / F1 + AP@iou_threshold (very rough single-class AP).

    Match each detection (sorted by score desc) to the highest-IoU unmatched GT
    of the same class. Anything matched = TP; remaining detections = FP;
    remaining GT = FN. Compute precision recall per class, plus an "all"
    aggregate.
    """
    dets_sorted = sorted(detections, key=lambda d: -d.score)
    gt_by_class: dict[int, list[tuple[int, tuple[int, int, int, int]]]] = defaultdict(list)
    for i, (c, b) in enumerate(gt):
        gt_by_class[c].append((i, b))
    matched_gt: set[int] = set()
    tp_by_class: dict[int, int] = defaultdict(int)
    fp_by_class: dict[int, int] = defaultdict(int)

    for d in dets_sorted:
        target_classes = list(gt_by_class.keys()) if class_agnostic else [d.class_id]
        best_iou = 0.0
        best_idx = -1
        for cls in target_classes:
            for gi, gb in gt_by_class.get(cls, []):
                if gi in matched_gt:
                    continue
                v = iou(d.bbox, gb)
                if v > best_iou:
                    best_iou = v
                    best_idx = gi
        if best_iou >= iou_threshold and best_idx >= 0:
            matched_gt.add(best_idx)
            tp_by_class[d.class_id] += 1
        else:
            fp_by_class[d.class_id] += 1

    fn_by_class: dict[int, int] = defaultdict(int)
    for ci, items in gt_by_class.items():
        fn_by_class[ci] = sum(1 for gi, _ in items if gi not in matched_gt)

    results: dict[str, dict[str, float]] = {}
    classes = set(tp_by_class) | set(fp_by_class) | set(fn_by_class)
    total_tp = total_fp = total_fn = 0
    for c in sorted(classes):
        tp = tp_by_class[c]
        fp = fp_by_class[c]
        fn = fn_by_class[c]
        total_tp += tp
        total_fp += fp
        total_fn += fn
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
        gt_count = sum(1 for ci, _ in gt if ci == c)
        results[VISDRONE_CLASSES[c] if c < len(VISDRONE_CLASSES) else str(c)] = {
            "gt": float(gt_count),
            "tp": float(tp),
            "fp": float(fp),
            "fn": float(fn),
            "precision": prec,
            "recall": rec,
            "f1": f1,
        }
    prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
    rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    results["__overall__"] = {
        "gt": float(len(gt)),
        "tp": float(total_tp),
        "fp": float(total_fp),
        "fn": float(total_fn),
        "precision": prec,
        "recall": rec,
        "f1": f1,
    }
    return results


async def run_detector(
    weights: Path,
    image: NDArray[np.uint8],
    *,
    num_classes: int,
    score_threshold: float,
    iou_threshold: float,
    tiles: tuple[int, int] | None,
    tile_overlap: float,
    tile_input_size: int,
    imgsz: int,
) -> tuple[list[Detection], float]:
    if tiles is None:
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
        pre = Preprocess(PreprocessConfig(width=imgsz, height=imgsz, layout="NCHW", normalize=True))
        await pre.setup()
        await det.setup()
        f = Frame(id=0, timestamp_ns=time.perf_counter_ns(), image=image)
        f = await pre.process(f)
        t0 = time.perf_counter()
        f = await det.process(f)
        dt = (time.perf_counter() - t0) * 1000
        await det.teardown()
        return list(f.detections), dt
    rows, cols = tiles
    det_t = TiledOnnxDetector(
        DetectorConfig(
            backend="onnx-tiled",
            weights=str(weights),
            num_classes=num_classes,
            score_threshold=score_threshold,
            nms_threshold=iou_threshold,
            max_detections=1000,
            tile_rows=rows,
            tile_cols=cols,
            tile_overlap=tile_overlap,
            tile_input_size=tile_input_size,
        )
    )
    await det_t.setup()
    f = Frame(id=0, timestamp_ns=time.perf_counter_ns(), image=image)
    t0 = time.perf_counter()
    f = await det_t.process(f)
    dt = (time.perf_counter() - t0) * 1000
    await det_t.teardown()
    return list(f.detections), dt


def render_table(results: dict[str, dict[str, float]]) -> str:
    headers = ("class", "gt", "tp", "fp", "fn", "P", "R", "F1")
    rows = [headers]
    for cls in sorted(results.keys(), key=lambda c: (c == "__overall__", c)):
        r = results[cls]
        rows.append(
            (
                cls,
                f"{int(r['gt'])}",
                f"{int(r['tp'])}",
                f"{int(r['fp'])}",
                f"{int(r['fn'])}",
                f"{r['precision']:.2f}",
                f"{r['recall']:.2f}",
                f"{r['f1']:.2f}",
            )
        )
    widths = [max(len(r[i]) for r in rows) for i in range(len(headers))]
    lines = ["  ".join(c.ljust(widths[i]) for i, c in enumerate(r)) for r in rows]
    lines.insert(1, "  ".join("-" * widths[i] for i in range(len(headers))))
    return "\n".join(lines)


def parse_tiles(spec: str | None) -> tuple[int, int] | None:
    if spec is None:
        return None
    parts = spec.lower().split("x")
    if len(parts) != 2:
        raise SystemExit(f"--tiles must be ROWSxCOLS, got {spec!r}")
    return int(parts[0]), int(parts[1])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--samples-json", type=Path, required=True)
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--weights", type=Path, required=True)
    p.add_argument("--num-classes", type=int, default=10)
    p.add_argument("--score-threshold", type=float, default=0.25)
    p.add_argument("--iou-threshold", type=float, default=0.45)
    p.add_argument("--match-iou", type=float, default=0.5, help="IoU floor for TP")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--tiles", type=str, default=None, help="ROWSxCOLS for tiled inference")
    p.add_argument("--tile-overlap", type=float, default=0.2)
    p.add_argument("--tile-input-size", type=int, default=640)
    p.add_argument(
        "--class-agnostic",
        action="store_true",
        help="match a detection against any class GT (locate-only metric)",
    )
    p.add_argument(
        "--save-render",
        type=Path,
        default=None,
        help="optional path to save image with GT (red) + dets (green) overlaid",
    )
    args = p.parse_args()

    # Match against samples.json's "data/<file>" form.
    candidate = f"data/{args.image.name}"
    gt, W, H = load_gt(args.samples_json, candidate)

    image = cv2.imread(str(args.image))
    if image is None:
        raise SystemExit(f"failed to read {args.image}")
    if image.shape[1] != W or image.shape[0] != H:
        raise SystemExit(f"image dims {image.shape[:2]} mismatch GT {(H, W)}")

    dets, dt_ms = asyncio.run(
        run_detector(
            args.weights,
            image,
            num_classes=args.num_classes,
            score_threshold=args.score_threshold,
            iou_threshold=args.iou_threshold,
            tiles=parse_tiles(args.tiles),
            tile_overlap=args.tile_overlap,
            tile_input_size=args.tile_input_size,
            imgsz=args.imgsz,
        )
    )
    results = evaluate(dets, gt, iou_threshold=args.match_iou, class_agnostic=args.class_agnostic)
    print(f"image: {args.image.name}  {W}x{H}")
    print(f"weights: {args.weights}")
    if args.tiles:
        print(
            f"mode: tiled {args.tiles} overlap={args.tile_overlap} tile_input={args.tile_input_size}"
        )
    else:
        print(f"mode: single imgsz={args.imgsz}")
    print(
        f"score_threshold={args.score_threshold} nms_iou={args.iou_threshold} match_iou={args.match_iou}"
        + (" class-agnostic" if args.class_agnostic else "")
    )
    print(f"detections={len(dets)}  gt_objects={len(gt)}  detector_time={dt_ms:.1f}ms")
    print()
    print(render_table(results))

    if args.save_render is not None:
        for _cid, b in gt:
            cv2.rectangle(image, (b[0], b[1]), (b[2], b[3]), (0, 0, 255), 2)
        for d in dets:
            cv2.rectangle(image, (d.bbox[0], d.bbox[1]), (d.bbox[2], d.bbox[3]), (0, 255, 0), 2)
        cv2.imwrite(str(args.save_render), image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"\nrendered to {args.save_render}  (GT=red  pred=green)")


if __name__ == "__main__":
    main()
