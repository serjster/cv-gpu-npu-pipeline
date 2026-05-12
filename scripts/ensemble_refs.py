#!/usr/bin/env python3
"""Consensus filter across multiple reference JSONLs (Plan B).

Each input JSONL is a single-model pseudo-GT produced by
``build_reference.py``. The output JSONL keeps only detections that appear
in **at least N** models at IoU >= ``--match-iou`` (default 2 of 2 for a
two-model ensemble). Detections that one model picks up but the other
disagrees on (e.g. yolov8x's factory-yard false positives that yolov11x
doesn't see) get dropped.

Tracks are passed through from the **first** input — consensus only
filters detections. Use the first input as the model whose tracker output
you trust most.

Usage::

    uv run python scripts/ensemble_refs.py \\
      --input data/refs/hwy00-v8x.jsonl \\
      --input data/refs/hwy00-v11x.jsonl \\
      --out   data/refs/hwy00-consensus.jsonl \\
      --min-models 2 --match-iou 0.5
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def iou(a: list[int], b: list[int]) -> float:
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


def consensus_for_frame(
    detection_sets: list[list[dict[str, Any]]],
    min_models: int,
    match_iou: float,
) -> list[dict[str, Any]]:
    """Return detections from set 0 that have a matching detection in at least
    ``min_models - 1`` of the other sets (same class, IoU >= threshold)."""
    if not detection_sets:
        return []
    if min_models <= 1:
        return list(detection_sets[0])
    primary = detection_sets[0]
    others = detection_sets[1:]
    consensus: list[dict[str, Any]] = []
    for d in primary:
        agree = 1  # itself
        for o in others:
            matched = False
            for o_d in o:
                if o_d.get("class_id") != d.get("class_id"):
                    continue
                if iou(o_d["bbox"], d["bbox"]) >= match_iou:
                    matched = True
                    break
            if matched:
                agree += 1
        if agree >= min_models:
            consensus.append(d)
    return consensus


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--input",
        type=Path,
        action="append",
        required=True,
        help="reference JSONL — pass multiple times (first is the primary)",
    )
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--match-iou", type=float, default=0.5)
    p.add_argument(
        "--min-models",
        type=int,
        default=2,
        help="keep detection only if at least this many models agree",
    )
    args = p.parse_args()
    if len(args.input) < 2:
        raise SystemExit("ensemble needs >= 2 inputs")
    if args.min_models > len(args.input):
        raise SystemExit(f"--min-models {args.min_models} > number of inputs {len(args.input)}")

    runs = [load_jsonl(p) for p in args.input]
    by_frame: list[dict[int, dict[str, Any]]] = [{r["frame_id"]: r for r in run} for run in runs]
    primary = runs[0]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    total_primary = 0
    total_kept = 0
    with args.out.open("w") as fout:
        for ref_row in primary:
            fid = ref_row["frame_id"]
            sets = []
            for idx, by in enumerate(by_frame):
                r = by.get(fid)
                if r is None and idx > 0:
                    # missing in a non-primary → can't form full consensus this frame.
                    sets.append([])
                else:
                    sets.append((r or {}).get("detections", []))
            kept = consensus_for_frame(sets, args.min_models, args.match_iou)
            total_primary += len(sets[0])
            total_kept += len(kept)
            out_row = {
                "frame_id": fid,
                "timestamp_ns": ref_row.get("timestamp_ns"),
                "detections": kept,
                # Pass tracks through from primary.
                "tracks": ref_row.get("tracks", []),
            }
            fout.write(json.dumps(out_row, separators=(",", ":")))
            fout.write("\n")
    print(f"primary detections: {total_primary}")
    print(f"consensus kept:     {total_kept}")
    if total_primary:
        kept_pct = 100 * total_kept / total_primary
        print(f"retention:          {kept_pct:.1f}%")


if __name__ == "__main__":
    main()
