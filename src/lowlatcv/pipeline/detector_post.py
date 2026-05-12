"""Pure postprocessing for detector outputs.

Decoupled from any model backend so a new detector only needs to produce a
raw output tensor — thresholding, NMS, and the inverse-letterbox coord
transform live here as pure numpy functions and are unit-testable in
isolation.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray


def nms(
    boxes_xyxy: NDArray[np.float32],
    scores: NDArray[np.float32],
    iou_threshold: float,
) -> NDArray[np.int64]:
    """Greedy NMS. Returns indices into ``boxes_xyxy`` to keep, ordered by descending score."""
    if boxes_xyxy.size == 0:
        return np.empty((0,), dtype=np.int64)
    x1 = boxes_xyxy[:, 0]
    y1 = boxes_xyxy[:, 1]
    x2 = boxes_xyxy[:, 2]
    y2 = boxes_xyxy[:, 3]
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(x1[i], x1[rest])
        yy1 = np.maximum(y1[i], y1[rest])
        xx2 = np.minimum(x2[i], x2[rest])
        yy2 = np.minimum(y2[i], y2[rest])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        union = areas[i] + areas[rest] - inter
        iou = np.where(union > 0, inter / union, 0.0)
        order = rest[iou <= iou_threshold]
    return np.asarray(keep, dtype=np.int64)


def decode_yolov8(
    output: NDArray[Any],
    num_classes: int,
) -> tuple[NDArray[np.float32], NDArray[np.float32], NDArray[np.int64]]:
    """Decode a raw YOLOv8-style detection head into ``(boxes_xyxy, scores, class_ids)``.

    Auto-detects the output format:

    1. Anchor-grid (YOLOv8, v11): shape ``(1, 4 + num_classes, N)`` or
       ``(1, N, 4 + num_classes)``. Boxes are in cxcywh letterboxed pixels;
       per-anchor class scores are sigmoid-applied. We argmax to pick the
       winning class.
    2. NMS-free / one-shot (YOLOv10, YOLO26): shape ``(1, N, 6)`` where each
       row is ``[x1, y1, x2, y2, score, class_id]`` already in xyxy pixel
       space and already filtered by the model's internal NMS — we just
       have to score-threshold and unletterbox downstream.
    """
    out = np.asarray(output, dtype=np.float32)
    if out.ndim != 3 or out.shape[0] != 1:
        raise ValueError(f"unexpected detector output shape: {out.shape}")
    arr = out[0]
    expected_anchor = 4 + num_classes

    # NMS-free / one-shot format
    if arr.ndim == 2 and arr.shape[1] == 6:
        boxes_xyxy = arr[:, :4].astype(np.float32, copy=True)
        scores = arr[:, 4].astype(np.float32, copy=True)
        class_ids = arr[:, 5].astype(np.int64, copy=True)
        return boxes_xyxy, scores, class_ids

    if arr.shape[0] == expected_anchor:
        arr = arr.T
    elif arr.shape[1] != expected_anchor:
        raise ValueError(
            f"unexpected detector channel dim: {arr.shape}, "
            f"expected last={expected_anchor} (anchor-grid) or 6 (NMS-free)"
        )
    boxes_cxcywh = arr[:, :4]
    cls_scores = arr[:, 4 : 4 + num_classes]
    class_ids = cls_scores.argmax(axis=1).astype(np.int64)
    scores = cls_scores.max(axis=1).astype(np.float32)
    boxes_xyxy = _cxcywh_to_xyxy(boxes_cxcywh).astype(np.float32)
    return boxes_xyxy, scores, class_ids


def _cxcywh_to_xyxy(boxes: NDArray[np.float32]) -> NDArray[np.float32]:
    cx, cy, w, h = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    half_w = w / 2.0
    half_h = h / 2.0
    return np.stack([cx - half_w, cy - half_h, cx + half_w, cy + half_h], axis=1)


def unletterbox_xyxy(
    boxes_xyxy: NDArray[np.float32],
    letterbox_hw: tuple[int, int],
    orig_hw: tuple[int, int],
) -> NDArray[np.float32]:
    """Map xyxy boxes from letterboxed coords back to the original frame."""
    lb_h, lb_w = letterbox_hw
    orig_h, orig_w = orig_hw
    scale = min(lb_w / orig_w, lb_h / orig_h)
    pad_x = (lb_w - orig_w * scale) / 2.0
    pad_y = (lb_h - orig_h * scale) / 2.0
    out = boxes_xyxy.astype(np.float32, copy=True)
    out[:, [0, 2]] = (out[:, [0, 2]] - pad_x) / scale
    out[:, [1, 3]] = (out[:, [1, 3]] - pad_y) / scale
    out[:, [0, 2]] = np.clip(out[:, [0, 2]], 0, orig_w)
    out[:, [1, 3]] = np.clip(out[:, [1, 3]], 0, orig_h)
    return out


def filter_threshold_and_nms(
    boxes_xyxy: NDArray[np.float32],
    scores: NDArray[np.float32],
    class_ids: NDArray[np.int64],
    score_threshold: float,
    iou_threshold: float,
    max_detections: int,
) -> tuple[NDArray[np.float32], NDArray[np.float32], NDArray[np.int64]]:
    mask = scores >= score_threshold
    if not mask.any():
        return (
            np.empty((0, 4), dtype=np.float32),
            np.empty((0,), dtype=np.float32),
            np.empty((0,), dtype=np.int64),
        )
    b = boxes_xyxy[mask]
    s = scores[mask]
    c = class_ids[mask]
    keep = nms(b, s, iou_threshold)
    if keep.size > max_detections:
        keep = keep[:max_detections]
    return b[keep], s[keep], c[keep]
