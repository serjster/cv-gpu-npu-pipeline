#!/usr/bin/env python3
"""Diff two JSONL pipeline exports — reference vs ours.

Both files must be the JSONL format written by ``JsonlExportSink``. Per
frame we compute detection P/R/F1 against the reference at the configured
match IoU, plus a track-ID consistency score: for each *reference* track
we identify the our-track that overlaps it most often, then count how
often the assignment switches (ID switches per reference track).

Usage::

    uv run python scripts/diff_runs.py \\
      --reference data/refs/hwy00-x-1920-3x3.jsonl \\
      --ours      data/refs/hwy00-n-1280-live.jsonl \\
      --match-iou 0.5
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


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


def match_frame_detections(
    ref_dets: list[dict[str, Any]],
    our_dets: list[dict[str, Any]],
    iou_threshold: float,
) -> tuple[int, int, int]:
    """Return (tp, fp, fn) for one frame, ignoring class for now."""
    used_r: set[int] = set()
    tp = 0
    # sort ours by score desc so the best detection gets first pick of GT
    our_sorted = sorted(our_dets, key=lambda d: -d.get("score", 0.0))
    for od in our_sorted:
        best_iou = 0.0
        best_idx = -1
        for ri, rd in enumerate(ref_dets):
            if ri in used_r:
                continue
            if od.get("class_id") != rd.get("class_id"):
                continue
            v = iou(od["bbox"], rd["bbox"])
            if v > best_iou:
                best_iou = v
                best_idx = ri
        if best_iou >= iou_threshold and best_idx >= 0:
            used_r.add(best_idx)
            tp += 1
    fp = len(our_dets) - tp
    fn = len(ref_dets) - tp
    return tp, fp, fn


def analyse_track_consistency(
    ref_runs: list[dict[str, Any]],
    our_runs: list[dict[str, Any]],
    iou_threshold: float,
) -> dict[str, int]:
    """For each reference track, see which our-track overlaps it most each frame
    and count how often that assignment changes."""
    # Build per-frame index by frame_id
    our_by_frame = {r["frame_id"]: r for r in our_runs}
    assigned: dict[int, list[int | None]] = defaultdict(list)
    for ref in ref_runs:
        fid = ref["frame_id"]
        our = our_by_frame.get(fid)
        if our is None:
            continue
        for rt in ref.get("tracks", []):
            best_iou = 0.0
            best_id: int | None = None
            for ot in our.get("tracks", []):
                v = iou(rt["bbox"], ot["bbox"])
                if v > best_iou and v >= iou_threshold:
                    best_iou = v
                    best_id = ot["track_id"]
            assigned[rt["track_id"]].append(best_id)
    switches = 0
    covered = 0
    for assigns in assigned.values():
        if not assigns:
            continue
        covered += 1
        prev: int | None = None
        for a in assigns:
            if a is not None and prev is not None and a != prev:
                switches += 1
            if a is not None:
                prev = a
    return {
        "ref_tracks_total": len(assigned),
        "ref_tracks_with_match": covered,
        "id_switches": switches,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--ours", type=Path, required=True)
    ap.add_argument("--match-iou", type=float, default=0.5)
    args = ap.parse_args()

    ref = load_jsonl(args.reference)
    ours = load_jsonl(args.ours)

    ref_by_frame = {r["frame_id"]: r for r in ref}
    common = sorted(set(ref_by_frame) & {r["frame_id"] for r in ours})
    our_by_frame = {r["frame_id"]: r for r in ours}

    total_tp = total_fp = total_fn = 0
    for fid in common:
        tp, fp, fn = match_frame_detections(
            ref_by_frame[fid].get("detections", []),
            our_by_frame[fid].get("detections", []),
            args.match_iou,
        )
        total_tp += tp
        total_fp += fp
        total_fn += fn

    prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
    rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0

    track_stats = analyse_track_consistency(ref, ours, args.match_iou)

    print(f"reference: {args.reference}  ({len(ref)} frames)")
    print(f"ours:      {args.ours}  ({len(ours)} frames)")
    print(f"common frames: {len(common)}")
    print()
    print(f"DETECTIONS @ IoU>={args.match_iou}:")
    print(f"  TP={total_tp}  FP={total_fp}  FN={total_fn}")
    print(f"  P={prec:.3f}  R={rec:.3f}  F1={f1:.3f}")
    print()
    print("TRACK CONSISTENCY:")
    print(f"  reference tracks total:        {track_stats['ref_tracks_total']}")
    print(f"  reference tracks ever matched: {track_stats['ref_tracks_with_match']}")
    print(f"  ID switches across reference:  {track_stats['id_switches']}")


if __name__ == "__main__":
    main()
