from __future__ import annotations

import asyncio
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from lowlatcv.app import build_pipeline
from lowlatcv.config import (
    DetectorConfig,
    OverlayConfig,
    PipelineConfig,
    PreprocessConfig,
    SinkConfig,
    SourceConfig,
)
from lowlatcv.metrics.tracer import Tracer


def _write_fixture_clip(path: Path, n_frames: int, h: int = 64, w: int = 64) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 30.0, (w, h))
    if not writer.isOpened():
        raise RuntimeError("cv2.VideoWriter failed to open")
    for i in range(n_frames):
        img: NDArray[np.uint8] = np.full((h, w, 3), (i * 17) % 255, dtype=np.uint8)
        writer.write(img)
    writer.release()


def test_pipeline_with_fake_detector_drains_to_eof(tmp_path: Path) -> None:
    clip = tmp_path / "clip.mp4"
    _write_fixture_clip(clip, n_frames=8)

    cfg = PipelineConfig(
        source=SourceConfig(uri=str(clip)),
        preprocess=PreprocessConfig(width=320, height=320),
        detector=DetectorConfig(backend="fake"),
        overlay=OverlayConfig(),
        sink=SinkConfig(kind="null"),
    )
    tracer = Tracer()
    pipeline = build_pipeline(cfg, tracer)
    asyncio.run(pipeline.run())

    # Every stage was traced — five rows in the report.
    for stage in ("source", "preprocess", "detector", "overlay", "sink"):
        s = tracer.stats(stage)
        assert s is not None, f"missing stats for {stage}"
        assert s.count > 0
