from __future__ import annotations

import asyncio
from pathlib import Path

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from lowlatcv.config import SourceConfig
from lowlatcv.models.frame import Frame
from lowlatcv.pipeline.source import EOF, FileSource, WebcamSource, from_uri


def _write_fixture_clip(path: Path, n_frames: int, height: int = 64, width: int = 64) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 30.0, (width, height))
    if not writer.isOpened():
        raise RuntimeError("cv2.VideoWriter failed to open")
    for i in range(n_frames):
        img: NDArray[np.uint8] = np.full((height, width, 3), (i * 13) % 255, dtype=np.uint8)
        writer.write(img)
    writer.release()


def test_file_source_yields_exact_frame_count(tmp_path: Path) -> None:
    clip = tmp_path / "clip.mp4"
    _write_fixture_clip(clip, n_frames=7)

    async def go() -> list[Frame]:
        src = FileSource(str(clip))
        await src.setup()
        try:
            out: list[Frame] = []
            while True:
                r = await src.process(None)
                if r is EOF:
                    break
                assert isinstance(r, Frame)
                out.append(r)
            return out
        finally:
            await src.teardown()

    frames = asyncio.run(go())
    assert len(frames) == 7
    assert all(f.image.shape == (64, 64, 3) for f in frames)
    assert [f.id for f in frames] == list(range(7))


def test_file_source_honours_frame_limit(tmp_path: Path) -> None:
    clip = tmp_path / "clip.mp4"
    _write_fixture_clip(clip, n_frames=20)

    async def go() -> int:
        src = FileSource(str(clip), frame_limit=5)
        await src.setup()
        try:
            count = 0
            while True:
                r = await src.process(None)
                if r is EOF:
                    break
                count += 1
            return count
        finally:
            await src.teardown()

    assert asyncio.run(go()) == 5


def test_frame_source_factory_routes_by_uri_scheme(tmp_path: Path) -> None:
    clip = tmp_path / "clip.mp4"
    _write_fixture_clip(clip, n_frames=2)
    cfg = SourceConfig()

    assert isinstance(from_uri(str(clip), cfg), FileSource)
    assert isinstance(from_uri(f"file://{clip}", cfg), FileSource)
    assert isinstance(from_uri("rtsp://example/x", cfg), FileSource)
    assert isinstance(from_uri("webcam:0", cfg), WebcamSource)
    assert isinstance(from_uri("0", cfg), WebcamSource)


def test_webcam_source_opens_and_closes_or_skips() -> None:
    probe = cv2.VideoCapture(0)
    try:
        if not probe.isOpened():
            pytest.skip("no webcam device available")
    finally:
        probe.release()

    async def go() -> None:
        src = WebcamSource(device_index=0)
        await src.setup()
        await src.teardown()

    asyncio.run(go())
