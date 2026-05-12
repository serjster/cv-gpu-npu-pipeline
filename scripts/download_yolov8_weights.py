#!/usr/bin/env python3
"""Download + ONNX-export YOLOv8 weights into data/models/.

Three flavours, picked by ``--variant``:

- ``coco``      → vanilla COCO YOLOv8n (80 classes, street-view scale).
                  Pulled via ``ultralytics.YOLO("yolov8n.pt")``.
- ``visdrone``  → ``mshamrai/yolov8n-visdrone`` from Hugging Face, trained
                  on VisDrone 2019 (10 aerial classes:
                  pedestrian, people, bicycle, car, van, truck, tricycle,
                  awning-tricycle, bus, motor).
- ``visdrone-s``→ same family, ``mshamrai/yolov8s-visdrone`` (slower, more
                  accurate).

Output: ``data/models/<variant>.onnx`` at ``--imgsz`` (default 640).

The lowlatcv pipeline does **not** depend on ultralytics at runtime —
this script is a one-shot helper. It installs ultralytics in the active
venv only if it is missing.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HF_REPOS = {
    "visdrone": "mshamrai/yolov8n-visdrone",
    "visdrone-s": "mshamrai/yolov8s-visdrone",
}
COCO_NAMES = ("yolov8n", "yolov8s", "yolov8m", "yolov8l", "yolov8x")
VISDRONE_NAMES = (
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


def _import_ultralytics():  # type: ignore[no-untyped-def]
    try:
        from ultralytics import YOLO  # noqa: F401

        return
    except ImportError:
        print("ultralytics not installed — installing into active venv …", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "ultralytics"])


def _hf_download(repo: str, filename: str, local_dir: Path) -> Path:
    local_dir.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(["hf", "download", repo, filename, "--local-dir", str(local_dir)])
    return local_dir / filename


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="coco", choices=("coco", "visdrone", "visdrone-s"))
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--opset", type=int, default=12)
    parser.add_argument("--out-dir", type=Path, default=Path("data/models"))
    args = parser.parse_args()

    _import_ultralytics()
    from ultralytics import YOLO  # type: ignore[import-untyped]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.variant == "coco":
        weights = "yolov8n.pt"
        out_name = f"yolov8n-coco-{args.imgsz}.onnx" if args.imgsz != 640 else "yolov8n.onnx"
        num_classes = 80
    else:
        repo = HF_REPOS[args.variant]
        pt = _hf_download(repo, "best.pt", args.out_dir / args.variant)
        weights = str(pt)
        suffix = "n" if args.variant == "visdrone" else "s"
        out_name = (
            f"yolov8{suffix}-visdrone-{args.imgsz}.onnx"
            if args.imgsz != 640
            else f"yolov8{suffix}-visdrone.onnx"
        )
        num_classes = 10

    print(f"loading weights={weights} for ONNX export at imgsz={args.imgsz}")
    model = YOLO(weights)
    exported = model.export(format="onnx", imgsz=args.imgsz, opset=args.opset)
    src = Path(exported)
    dst = args.out_dir / out_name
    if src.resolve() != dst.resolve():
        shutil.move(str(src), str(dst))
    print(f"→ {dst}")
    print(f"num_classes={num_classes}")
    if args.variant.startswith("visdrone"):
        print("VisDrone classes:", ", ".join(f"{i}={n}" for i, n in enumerate(VISDRONE_NAMES)))
    print()
    print("Run live with:")
    print("  uv run lowlatcv run --source <video> --display \\")
    print(f"    --detector onnx --weights {dst} \\")
    print(f"    --imgsz {args.imgsz} --num-classes {num_classes}")
    print("Or tile-mode for tiny aerial objects:")
    print("  uv run lowlatcv run --source <video> --display \\")
    print(f"    --detector onnx-tiled --weights {dst} \\")
    print(f"    --num-classes {num_classes} --tiles 3x3 --tile-input-size {args.imgsz}")


if __name__ == "__main__":
    main()
