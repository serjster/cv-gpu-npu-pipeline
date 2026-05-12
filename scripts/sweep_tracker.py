#!/usr/bin/env python3
"""Tracker config sweep — diff each variant against the reference.

Runs ``lowlatcv bench`` in a loop with different tracker / detector knobs
exported to JSONL, then ``diff_runs.py`` against the same reference, and
prints a summary table so you can see which knob actually moves P/R/F1
and ID switches.

Usage::

    uv run python scripts/sweep_tracker.py \\
      --source data/b3d/videos/hwy00.mp4 \\
      --reference data/refs/hwy00-consensus.jsonl \\
      --frames 60 \\
      --weights data/models/yolov8n-visdrone-1280.onnx --imgsz 1280
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# Sweep grid (small by default; expand here when chasing a specific knob).
# These vary TRACKER behaviour, not detector NMS — to actually move ID-switch
# and recall under matched detection sets.
SWEEPS: list[dict[str, Any]] = [
    {"label": "baseline", "extra": []},
    {"label": "trk_iou=0.10", "extra": ["--tracker-iou-threshold", "0.10"]},
    {"label": "trk_iou=0.30", "extra": ["--tracker-iou-threshold", "0.30"]},
    {"label": "motion=1.0", "extra": ["--tracker-motion-distance-factor", "1.0"]},
    {"label": "motion=3.0", "extra": ["--tracker-motion-distance-factor", "3.0"]},
    {"label": "motion=0", "extra": ["--tracker-motion-distance-factor", "0"]},
    {"label": "max_age=5", "extra": ["--tracker-max-age", "5"]},
    {"label": "max_age=20", "extra": ["--tracker-max-age", "20"]},
    {"label": "min_hits=1", "extra": ["--tracker-min-hits", "1"]},
]


def run_diff(reference: Path, ours: Path) -> dict[str, float]:
    """Invoke diff_runs.py and parse its output for the metrics we care about."""
    out = subprocess.check_output(
        [
            sys.executable,
            str(Path(__file__).parent / "diff_runs.py"),
            "--reference",
            str(reference),
            "--ours",
            str(ours),
            "--match-iou",
            "0.5",
        ],
        text=True,
    )
    metrics: dict[str, float] = {}
    for line in out.splitlines():
        m = re.search(r"P=([\d.]+)\s+R=([\d.]+)\s+F1=([\d.]+)", line)
        if m:
            metrics["P"] = float(m.group(1))
            metrics["R"] = float(m.group(2))
            metrics["F1"] = float(m.group(3))
        m = re.search(r"TP=(\d+)\s+FP=(\d+)\s+FN=(\d+)", line)
        if m:
            metrics["TP"] = int(m.group(1))
            metrics["FP"] = int(m.group(2))
            metrics["FN"] = int(m.group(3))
        m = re.search(r"ID switches across reference:\s+(\d+)", line)
        if m:
            metrics["id_switches"] = int(m.group(1))
    return metrics


def run_pipeline(
    source: Path, weights: Path, imgsz: int, frames: int, extra: list[str], jsonl: Path
) -> None:
    cmd = [
        "uv",
        "run",
        "lowlatcv",
        "bench",
        "--source",
        str(source),
        "--frames",
        str(frames),
        "--detector",
        "onnx",
        "--weights",
        str(weights),
        "--num-classes",
        "10",
        "--imgsz",
        str(imgsz),
        "--export-jsonl",
        str(jsonl),
        *extra,
    ]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--weights", type=Path, required=True)
    p.add_argument("--imgsz", type=int, default=1280)
    p.add_argument("--frames", type=int, default=60)
    p.add_argument("--out-dir", type=Path, default=Path("data/refs/sweep"))
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, dict[str, float]]] = []
    for sweep in SWEEPS:
        label = sweep["label"]
        jsonl = args.out_dir / f"sweep_{label.replace(' ', '_').replace('=', '_')}.jsonl"
        print(f"\n=== {label} ===")
        run_pipeline(args.source, args.weights, args.imgsz, args.frames, sweep["extra"], jsonl)
        metrics = run_diff(args.reference, jsonl)
        print(json.dumps(metrics, indent=2))
        rows.append((label, metrics))

    print("\n=== SUMMARY ===")
    print(
        f"{'config':<18} | {'P':>6} | {'R':>6} | {'F1':>6} | {'TP':>5} | {'FP':>5} | {'FN':>6} | {'IDsw':>5}"
    )
    print("-" * 78)
    for label, m in rows:
        print(
            f"{label:<18} | {m.get('P', 0):>6.3f} | {m.get('R', 0):>6.3f} | "
            f"{m.get('F1', 0):>6.3f} | {int(m.get('TP', 0)):>5d} | {int(m.get('FP', 0)):>5d} | "
            f"{int(m.get('FN', 0)):>6d} | {int(m.get('id_switches', 0)):>5d}"
        )


if __name__ == "__main__":
    _ = tempfile  # kept for future randomized temp paths
    main()
