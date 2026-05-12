"""Object detection stage: ``Detector`` Protocol + concrete backends + factory.

``Detector.process`` takes a preprocessed ``Frame`` (carrying ``tensor`` and
``letterbox`` metadata) and returns the same ``Frame`` with ``detections``
populated. Strategy pattern: ``FakeDetector`` for deterministic tests,
``OnnxDetector`` for ONNX Runtime on any execution provider (CPU / CoreML /
ROCm / MIGraphX / CUDA), ``CoreMLDetector`` for ``.mlpackage`` weights via
``coremltools`` (Apple Silicon), ``TiledOnnxDetector`` for SAHI-style
tiled inference on small objects (e.g. aerial / drone footage where the
model trained on COCO street-view scale otherwise sees a few-pixel car).
Heavy backend imports are gated inside ``setup`` so the wrong-platform
import never runs.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from typing import TYPE_CHECKING, Any, Protocol

import cv2
import numpy as np
from numpy.typing import NDArray

from lowlatcv.config import DetectorConfig
from lowlatcv.models.frame import Detection, Frame
from lowlatcv.pipeline.detector_post import (
    decode_yolov8,
    filter_threshold_and_nms,
    nms,
    unletterbox_xyxy,
)
from lowlatcv.pipeline.tile_hints import TileHintBoard

log = logging.getLogger(__name__)


class Detector(Protocol):
    name: str

    async def setup(self) -> None: ...
    async def process(self, item: Frame) -> Frame: ...
    async def teardown(self) -> None: ...


class FakeDetector:
    """Deterministic stub for tests and weights-less smoke runs.

    Emits a single bbox covering the central 50%×50% region of the frame
    with score 0.9 and class id 0. Useful for piping real frames through
    the entire graph without weights.
    """

    name = "detector"

    def __init__(self, cfg: DetectorConfig | None = None) -> None:
        self._cfg = cfg or DetectorConfig()

    async def setup(self) -> None: ...

    async def process(self, item: Frame) -> Frame:
        h, w = item.image.shape[:2]
        x1 = int(w * 0.25)
        y1 = int(h * 0.25)
        x2 = int(w * 0.75)
        y2 = int(h * 0.75)
        det = Detection(bbox=(x1, y1, x2, y2), score=0.9, class_id=0)
        return dataclasses.replace(item, detections=(det,))

    async def teardown(self) -> None: ...


class OnnxDetector:
    """ONNX Runtime backend. Execution provider chosen via ``DetectorConfig.execution_provider``.

    Default EP order per profile is set up at construction time; concrete
    EPs are validated against the runtime's available providers on
    ``setup``. The model graph is expected to follow the YOLOv8 head
    convention ``(1, 4 + num_classes, N)``.
    """

    name = "detector"

    def __init__(self, cfg: DetectorConfig) -> None:
        if cfg.weights is None:
            raise ValueError("OnnxDetector requires DetectorConfig.weights")
        self._cfg = cfg
        self._session: Any = None
        self._input_name: str = ""
        self._input_hw: tuple[int, int] = (0, 0)

    async def setup(self) -> None:
        import onnxruntime as ort

        providers = self._select_providers(ort)
        loop = asyncio.get_running_loop()
        self._session = await loop.run_in_executor(
            None, lambda: ort.InferenceSession(self._cfg.weights, providers=providers)
        )
        meta = self._session.get_inputs()[0]
        self._input_name = meta.name
        shape = meta.shape
        # Expected NCHW [N, 3, H, W]; H, W may be dynamic strings.
        h = int(shape[2]) if isinstance(shape[2], int) else 640
        w = int(shape[3]) if isinstance(shape[3], int) else 640
        self._input_hw = (h, w)
        log.info(
            "OnnxDetector loaded weights=%s providers=%s input=%s shape=%s",
            self._cfg.weights,
            providers,
            self._input_name,
            (h, w),
        )

    def _select_providers(self, ort: Any) -> list[str]:
        available = set(ort.get_available_providers())
        requested = self._cfg.execution_provider
        if requested is not None:
            if requested not in available:
                raise RuntimeError(
                    f"execution provider {requested!r} not available; available={sorted(available)}"
                )
            return (
                [requested, "CPUExecutionProvider"]
                if requested != "CPUExecutionProvider"
                else [requested]
            )
        for candidate in (
            "CoreMLExecutionProvider",
            "ROCMExecutionProvider",
            "MIGraphXExecutionProvider",
            "CUDAExecutionProvider",
        ):
            if candidate in available:
                return [candidate, "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    async def process(self, item: Frame) -> Frame:
        if item.tensor is None or item.letterbox is None:
            raise RuntimeError("OnnxDetector requires a preprocessed Frame (tensor + letterbox)")
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, self._infer, item.tensor)
        dets = self._postprocess(raw, item)
        return dataclasses.replace(item, detections=dets)

    def _infer(self, tensor: NDArray[Any]) -> NDArray[Any]:
        outputs = self._session.run(None, {self._input_name: tensor})
        return np.asarray(outputs[0])

    def _postprocess(self, raw: NDArray[Any], frame: Frame) -> tuple[Detection, ...]:
        boxes, scores, class_ids = decode_yolov8(raw, self._cfg.num_classes)
        b, s, c = filter_threshold_and_nms(
            boxes,
            scores,
            class_ids,
            score_threshold=self._cfg.score_threshold,
            iou_threshold=self._cfg.nms_threshold,
            max_detections=self._cfg.max_detections,
        )
        if b.size == 0:
            return ()
        assert frame.letterbox is not None
        lb = frame.letterbox
        b = unletterbox_xyxy(
            b,
            letterbox_hw=(lb.canvas_h, lb.canvas_w),
            orig_hw=(lb.orig_h, lb.orig_w),
        )
        return tuple(
            Detection(
                bbox=(int(x1), int(y1), int(x2), int(y2)),
                score=float(score),
                class_id=int(cls),
            )
            for (x1, y1, x2, y2), score, cls in zip(b, s, c, strict=False)
        )

    async def teardown(self) -> None:
        self._session = None


class CoreMLDetector:
    """CoreML ``.mlpackage`` backend (macOS only). Lazy-imports ``coremltools``."""

    name = "detector"

    def __init__(self, cfg: DetectorConfig) -> None:
        if cfg.weights is None:
            raise ValueError("CoreMLDetector requires DetectorConfig.weights")
        self._cfg = cfg
        self._model: Any = None
        self._input_name: str = ""

    async def setup(self) -> None:
        import coremltools as ct

        loop = asyncio.get_running_loop()
        self._model = await loop.run_in_executor(None, ct.models.MLModel, self._cfg.weights)
        spec_inputs = self._model.get_spec().description.input
        if not spec_inputs:
            raise RuntimeError(f"CoreML model {self._cfg.weights} declares no inputs")
        self._input_name = spec_inputs[0].name
        log.info(
            "CoreMLDetector loaded weights=%s input=%s",
            self._cfg.weights,
            self._input_name,
        )

    async def process(self, item: Frame) -> Frame:
        if item.tensor is None or item.letterbox is None:
            raise RuntimeError("CoreMLDetector requires a preprocessed Frame (tensor + letterbox)")
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, self._predict, item.tensor)
        dets = self._postprocess(raw, item)
        return dataclasses.replace(item, detections=dets)

    def _predict(self, tensor: NDArray[Any]) -> NDArray[Any]:
        out = self._model.predict({self._input_name: tensor})
        value = next(iter(out.values()))
        return np.asarray(value)

    def _postprocess(self, raw: NDArray[Any], frame: Frame) -> tuple[Detection, ...]:
        boxes, scores, class_ids = decode_yolov8(raw, self._cfg.num_classes)
        b, s, c = filter_threshold_and_nms(
            boxes,
            scores,
            class_ids,
            score_threshold=self._cfg.score_threshold,
            iou_threshold=self._cfg.nms_threshold,
            max_detections=self._cfg.max_detections,
        )
        if b.size == 0:
            return ()
        assert frame.letterbox is not None
        lb = frame.letterbox
        b = unletterbox_xyxy(
            b,
            letterbox_hw=(lb.canvas_h, lb.canvas_w),
            orig_hw=(lb.orig_h, lb.orig_w),
        )
        return tuple(
            Detection(
                bbox=(int(x1), int(y1), int(x2), int(y2)),
                score=float(score),
                class_id=int(cls),
            )
            for (x1, y1, x2, y2), score, cls in zip(b, s, c, strict=False)
        )

    async def teardown(self) -> None:
        self._model = None


class TiledOnnxDetector:
    """SAHI-style tiled ONNX inference.

    Slices ``Frame.image`` into ``tile_rows × tile_cols`` overlapping tiles,
    letterboxes each tile to ``tile_input_size`` (square), runs ONNX inference
    per tile, decodes + NMS in tile-local coords, shifts boxes back to the
    original frame, then a final global NMS dedupes detections that cross
    tile boundaries. Designed for footage where the trained-resolution
    target (e.g. COCO street view) is much smaller than the tile-local view
    — typical aerial / drone scenes where a car covers 5–10 px in a
    whole-frame letterbox but 30–60 px in a 3×3 tile.

    Ignores ``Frame.tensor`` and ``Frame.letterbox`` — works directly off
    ``image`` so the Preprocess stage upstream is effectively a no-op when
    this backend is selected.
    """

    name = "detector"

    def __init__(
        self,
        cfg: DetectorConfig,
        hint_board: TileHintBoard | None = None,
    ) -> None:
        if cfg.weights is None:
            raise ValueError("TiledOnnxDetector requires DetectorConfig.weights")
        if cfg.tile_rows < 1 or cfg.tile_cols < 1:
            raise ValueError("tile_rows and tile_cols must be >= 1")
        if not (0.0 <= cfg.tile_overlap < 0.95):
            raise ValueError("tile_overlap must be in [0.0, 0.95)")
        self._cfg = cfg
        self._session: Any = None
        self._input_name: str = ""
        self._effective_tile_input: int = cfg.tile_input_size
        # Tile-on-demand state: per-tile latest detection lists (in original
        # frame coords) so the aggregate output stays full-frame even when
        # only a subset of tiles was rerun this cycle. None entry = never run.
        self._hint_board = hint_board
        self._per_tile: dict[tuple[int, int], list[Detection]] = {}

    async def setup(self) -> None:
        import onnxruntime as ort

        providers = _select_providers(ort, self._cfg.execution_provider)
        loop = asyncio.get_running_loop()
        self._session = await loop.run_in_executor(
            None, lambda: ort.InferenceSession(self._cfg.weights, providers=providers)
        )
        meta = self._session.get_inputs()[0]
        self._input_name = meta.name
        # The ONNX model is normally exported with a FIXED imgsz (e.g. 640) — the
        # CoreML EP compiles for that exact shape and fails at run-time when fed
        # anything else. Auto-detect the model's expected H/W and override
        # tile_input_size when they disagree, so the user can't accidentally
        # combine `--tile-input-size 1280` with a 640-only export.
        shape = meta.shape
        model_h = int(shape[2]) if isinstance(shape[2], int) else 0
        model_w = int(shape[3]) if isinstance(shape[3], int) else 0
        if model_h > 0 and model_w > 0 and model_h == model_w:
            if model_h != self._cfg.tile_input_size:
                log.warning(
                    "tile_input_size=%d disagrees with model fixed imgsz=%d; using %d",
                    self._cfg.tile_input_size,
                    model_h,
                    model_h,
                )
            self._effective_tile_input = model_h
        log.info(
            "TiledOnnxDetector loaded weights=%s providers=%s tiles=%dx%d overlap=%.2f tile_input=%d",
            self._cfg.weights,
            providers,
            self._cfg.tile_rows,
            self._cfg.tile_cols,
            self._cfg.tile_overlap,
            self._effective_tile_input,
        )

    async def process(self, item: Frame) -> Frame:
        loop = asyncio.get_running_loop()
        dets = await loop.run_in_executor(None, self._infer_blocking, item.image)
        return dataclasses.replace(item, detections=dets)

    def _infer_blocking(self, image: NDArray[np.uint8]) -> tuple[Detection, ...]:
        H, W = image.shape[:2]
        rows = self._cfg.tile_rows
        cols = self._cfg.tile_cols
        # Decide which tiles to run this cycle.
        if self._cfg.tile_on_demand and self._hint_board is not None:
            to_run = self._hint_board.select_tiles(
                rows, cols, H, W, self._cfg.tile_refresh_tiles_per_cycle
            )
        else:
            to_run = {(r, c) for r in range(rows) for c in range(cols)}

        for r, c in to_run:
            self._per_tile[(r, c)] = self._run_one_tile(image, r, c)

        return self._aggregate()

    def _run_one_tile(self, image: NDArray[np.uint8], r: int, c: int) -> list[Detection]:
        H, W = image.shape[:2]
        rows = self._cfg.tile_rows
        cols = self._cfg.tile_cols
        ov = self._cfg.tile_overlap
        tile_h = H / rows
        tile_w = W / cols
        oy = int(round(tile_h * ov))
        ox = int(round(tile_w * ov))
        y1 = max(0, int(round(r * tile_h)) - (oy if r > 0 else 0))
        y2 = min(H, int(round((r + 1) * tile_h)) + (oy if r < rows - 1 else 0))
        x1 = max(0, int(round(c * tile_w)) - (ox if c > 0 else 0))
        x2 = min(W, int(round((c + 1) * tile_w)) + (ox if c < cols - 1 else 0))
        if y2 <= y1 or x2 <= x1:
            return []
        tile = image[y1:y2, x1:x2]
        tensor, lb = _letterbox_for_inference(tile, self._effective_tile_input)
        raw = self._session.run(None, {self._input_name: tensor})[0]
        boxes, scores, class_ids = decode_yolov8(np.asarray(raw), self._cfg.num_classes)
        b, s, cl = filter_threshold_and_nms(
            boxes,
            scores,
            class_ids,
            score_threshold=self._cfg.score_threshold,
            iou_threshold=self._cfg.nms_threshold,
            max_detections=self._cfg.max_detections,
        )
        if b.size == 0:
            return []
        b = unletterbox_xyxy(b, letterbox_hw=lb, orig_hw=(y2 - y1, x2 - x1))
        b[:, [0, 2]] += x1
        b[:, [1, 3]] += y1
        return [
            Detection(
                bbox=(int(bx1), int(by1), int(bx2), int(by2)),
                score=float(score),
                class_id=int(cls),
            )
            for (bx1, by1, bx2, by2), score, cls in zip(b, s, cl, strict=False)
        ]

    def _aggregate(self) -> tuple[Detection, ...]:
        if not self._per_tile:
            return ()
        all_dets: list[Detection] = []
        for dets in self._per_tile.values():
            all_dets.extend(dets)
        if not all_dets:
            return ()
        boxes = np.array([d.bbox for d in all_dets], dtype=np.float32)
        scores = np.array([d.score for d in all_dets], dtype=np.float32)
        keep = nms(boxes, scores, iou_threshold=self._cfg.nms_threshold)
        if keep.size > self._cfg.max_detections:
            keep = keep[: self._cfg.max_detections]
        return tuple(all_dets[int(i)] for i in keep)

    async def teardown(self) -> None:
        self._session = None


def _select_providers(ort: Any, requested: str | None) -> list[str]:
    available = set(ort.get_available_providers())
    if requested is not None:
        if requested not in available:
            raise RuntimeError(
                f"execution provider {requested!r} not available; available={sorted(available)}"
            )
        return (
            [requested, "CPUExecutionProvider"]
            if requested != "CPUExecutionProvider"
            else [requested]
        )
    for candidate in (
        "CoreMLExecutionProvider",
        "ROCMExecutionProvider",
        "MIGraphXExecutionProvider",
        "CUDAExecutionProvider",
    ):
        if candidate in available:
            return [candidate, "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def _letterbox_for_inference(
    tile: NDArray[np.uint8], target: int
) -> tuple[NDArray[np.float32], tuple[int, int]]:
    h, w = tile.shape[:2]
    scale = min(target / w, target / h)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(tile, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((target, target, 3), 114, dtype=np.uint8)
    top = (target - new_h) // 2
    left = (target - new_w) // 2
    canvas[top : top + new_h, left : left + new_w] = resized
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    arr = rgb.astype(np.float32, copy=False) / np.float32(255.0)
    arr = np.transpose(arr, (2, 0, 1))[None]
    return np.ascontiguousarray(arr), (target, target)


def from_config(cfg: DetectorConfig) -> Detector:
    """Factory Method: select a detector backend from ``DetectorConfig.backend``."""
    backend = cfg.backend.lower()
    if backend == "fake":
        return FakeDetector(cfg)
    if backend == "onnx-tiled":
        return TiledOnnxDetector(cfg)
    if backend == "onnx":
        return OnnxDetector(cfg)
    if backend == "coreml":
        return CoreMLDetector(cfg)
    raise ValueError(f"unknown detector backend: {cfg.backend}")


if not TYPE_CHECKING:
    Detector.from_config = staticmethod(from_config)
