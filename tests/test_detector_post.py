from __future__ import annotations

import numpy as np
import pytest

from lowlatcv.pipeline.detector_post import (
    decode_yolov8,
    filter_threshold_and_nms,
    nms,
    unletterbox_xyxy,
)


def test_nms_collapses_overlapping_boxes_to_highest_score() -> None:
    boxes = np.array(
        [
            [0, 0, 10, 10],
            [1, 1, 11, 11],
            [2, 2, 12, 12],
            [100, 100, 200, 200],
        ],
        dtype=np.float32,
    )
    scores = np.array([0.5, 0.9, 0.6, 0.8], dtype=np.float32)
    keep = nms(boxes, scores, iou_threshold=0.5)
    # The three overlapping near-origin boxes collapse to index 1 (highest score)
    # and the disjoint box at index 3 survives.
    assert set(keep.tolist()) == {1, 3}


def test_nms_empty_input_returns_empty() -> None:
    empty = np.empty((0, 4), dtype=np.float32)
    keep = nms(empty, np.empty((0,), dtype=np.float32), iou_threshold=0.5)
    assert keep.shape == (0,)


def test_decode_yolov8_accepts_canonical_shape() -> None:
    num_classes = 80
    n_anchors = 10
    out = np.zeros((1, 4 + num_classes, n_anchors), dtype=np.float32)
    # one anchor has a strong class 5 hit at (cx, cy, w, h) = (50, 60, 20, 30)
    out[0, 0, 0] = 50.0
    out[0, 1, 0] = 60.0
    out[0, 2, 0] = 20.0
    out[0, 3, 0] = 30.0
    out[0, 4 + 5, 0] = 0.95

    boxes, scores, cls = decode_yolov8(out, num_classes=num_classes)
    assert boxes.shape == (n_anchors, 4)
    # cxcywh (50, 60, 20, 30) → xyxy (40, 45, 60, 75)
    assert boxes[0].tolist() == [40.0, 45.0, 60.0, 75.0]
    assert scores[0] == np.float32(0.95)
    assert cls[0] == 5


def test_unletterbox_xyxy_inverts_centred_padding() -> None:
    # 640×640 canvas, original 320×640 (portrait stretched)
    boxes = np.array([[160.0, 160.0, 480.0, 480.0]], dtype=np.float32)
    out = unletterbox_xyxy(boxes, letterbox_hw=(640, 640), orig_hw=(320, 640))
    # scale = min(640/640, 640/320) = 1.0; pad_x = 0; pad_y = (640 - 320)/2 = 160
    # so y coords have 160 subtracted before /1.0 → (0, 320)
    assert out[0].tolist() == [160.0, 0.0, 480.0, 320.0]


def test_filter_threshold_and_nms_drops_low_scores_and_caps_count() -> None:
    boxes = np.array(
        [
            [0, 0, 10, 10],
            [50, 50, 60, 60],
            [100, 100, 110, 110],
            [200, 200, 210, 210],
        ],
        dtype=np.float32,
    )
    scores = np.array([0.05, 0.9, 0.8, 0.7], dtype=np.float32)
    cls = np.array([0, 1, 2, 3], dtype=np.int64)
    b, s, c = filter_threshold_and_nms(
        boxes, scores, cls, score_threshold=0.1, iou_threshold=0.5, max_detections=2
    )
    assert s.tolist() == pytest.approx([0.9, 0.8], abs=1e-5)
    assert c.tolist() == [1, 2]
    assert b.shape == (2, 4)
