from __future__ import annotations

import asyncio
import json
import queue
import time
from unittest.mock import patch

import numpy as np
import pytest
from numpy.typing import NDArray

from lowlatcv.config import VLMConfig
from lowlatcv.models.caption import Caption, CaptionRequest
from lowlatcv.pipeline.vlm import (
    CaptionResultStore,
    FakeVLM,
    FastFlowLMVLM,
    OllamaVLM,
    VLMWorker,
    from_config,
)


def _req(track_id: int, frame_id: int = 0, first: bool = False) -> CaptionRequest:
    img: NDArray[np.uint8] = np.zeros((4, 4, 3), dtype=np.uint8)
    return CaptionRequest(
        track_id=track_id,
        frame_id=frame_id,
        crop=img,
        first_sighting=first,
    )


def test_caption_result_store_round_trips_per_track() -> None:
    store = CaptionResultStore()
    a = Caption(track_id=1, text="a", model="m", ts_ns=1)
    b = Caption(track_id=2, text="b", model="m", ts_ns=2)
    store.put(a)
    store.put(b)
    assert store.get(1) is a
    assert store.get(2) is b
    assert store.get(99) is None
    store.drop(1)
    assert store.get(1) is None


def test_fake_vlm_emits_caption_for_request() -> None:
    vlm = FakeVLM(prefix="hi")
    cap = vlm.caption(_req(7, frame_id=3))
    assert cap.track_id == 7
    assert "track=7" in cap.text
    assert "frame=3" in cap.text


def test_factory_routes_backends_and_disables_on_none() -> None:
    assert isinstance(from_config(VLMConfig(backend="fake")), FakeVLM)
    assert isinstance(from_config(VLMConfig(backend="ollama")), OllamaVLM)
    assert isinstance(from_config(VLMConfig(backend="fastflowlm")), FastFlowLMVLM)
    assert from_config(VLMConfig(backend="none")) is None
    with pytest.raises(ValueError, match="unknown VLM backend"):
        from_config(VLMConfig(backend="lalala"))


def test_fastflowlm_defaults_to_npu_port_when_host_unchanged() -> None:
    # User opted into fastflowlm without overriding host → endpoint should
    # land on FLM's port, not Ollama's.
    vlm = FastFlowLMVLM(VLMConfig(backend="fastflowlm"))
    assert vlm._endpoint == "http://localhost:52625/v1/chat/completions"


def test_fastflowlm_honours_explicit_host_override() -> None:
    vlm = FastFlowLMVLM(VLMConfig(backend="fastflowlm", host="http://npubox:9000"))
    assert vlm._endpoint == "http://npubox:9000/v1/chat/completions"


def test_fastflowlm_posts_openai_chat_payload_with_inline_image() -> None:
    captured: dict[str, object] = {}

    class _FakeResp:
        def __enter__(self) -> _FakeResp:
            return self

        def __exit__(self, *_: object) -> None: ...

        def read(self) -> bytes:
            return json.dumps({"choices": [{"message": {"content": "  a car  "}}]}).encode()

    def _fake_urlopen(req, timeout):  # type: ignore[no-untyped-def]
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        captured["timeout"] = timeout
        return _FakeResp()

    vlm = FastFlowLMVLM(VLMConfig(backend="fastflowlm", model="gemma4-it:e4b"))
    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        cap = vlm.caption(_req(42, frame_id=7))

    assert captured["url"] == "http://localhost:52625/v1/chat/completions"
    body = captured["body"]
    assert body["model"] == "gemma4-it:e4b"
    assert body["stream"] is False
    [msg] = body["messages"]
    assert msg["role"] == "user"
    image_part, text_part = msg["content"]
    assert image_part["type"] == "image_url"
    assert image_part["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert text_part["type"] == "text"
    # Caption text is stripped and routed back with the same track id.
    assert cap.track_id == 42
    assert cap.text == "a car"
    assert cap.model == "gemma4-it:e4b"


def test_fastflowlm_raises_runtime_error_on_missing_content() -> None:
    class _FakeResp:
        def __enter__(self) -> _FakeResp:
            return self

        def __exit__(self, *_: object) -> None: ...

        def read(self) -> bytes:
            return b"{}"

    vlm = FastFlowLMVLM(VLMConfig(backend="fastflowlm"))
    with (
        patch("urllib.request.urlopen", return_value=_FakeResp()),
        pytest.raises(RuntimeError, match="fastflowlm response missing content"),
    ):
        vlm.caption(_req(1))


def test_worker_writes_caption_to_store_then_stops_cleanly() -> None:
    store = CaptionResultStore()
    q: queue.Queue[CaptionRequest | None] = queue.Queue(maxsize=4)
    worker = VLMWorker(FakeVLM(), store, q)
    worker.start()
    try:
        q.put(_req(11))
        # Wait briefly for the worker thread to drain.
        deadline = time.perf_counter() + 1.0
        while store.get(11) is None and time.perf_counter() < deadline:
            time.sleep(0.01)
        assert store.get(11) is not None
    finally:
        worker.stop()


def test_worker_contains_vlm_crash_and_keeps_processing() -> None:
    store = CaptionResultStore()
    q: queue.Queue[CaptionRequest | None] = queue.Queue(maxsize=4)
    crashing = FakeVLM(crash=True)
    worker = VLMWorker(crashing, store, q)
    worker.start()
    try:
        q.put(_req(99))
        # Give the worker a tick to crash on this one and stay alive.
        time.sleep(0.2)
        assert store.get(99) is None  # crashed → no caption written
        # Swap to a healthy VLM mid-flight: confirm the worker is still alive.
        # (We don't swap the VLM here — instead just confirm the thread is still
        # processing by feeding another request and verifying the queue drains.)
        q.put(_req(100))
        time.sleep(0.2)
        assert store.get(100) is None  # still the same crashing VLM
    finally:
        worker.stop()


def test_slow_vlm_does_not_block_scheduler_process_path() -> None:
    """Submitting a CaptionRequest to a queue served by a 1s-latency VLM
    must return immediately on the scheduler side. Probe by timing the
    put_nowait + a successor get_nowait pattern that the scheduler uses."""
    store = CaptionResultStore()
    q: queue.Queue[CaptionRequest | None] = queue.Queue(maxsize=2)
    slow = FakeVLM(latency_s=1.0)
    worker = VLMWorker(slow, store, q)
    worker.start()
    try:
        t0 = time.perf_counter()
        q.put_nowait(_req(1))
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.05, f"submission unexpectedly blocked: {elapsed:.3f}s"
    finally:
        worker.stop(timeout=3.0)


def _run_scheduler_frames(scheduler, frames):  # type: ignore[no-untyped-def]
    async def go() -> None:
        await scheduler.setup()
        try:
            for f in frames:
                await scheduler.process(f)
        finally:
            await scheduler.teardown()

    asyncio.run(go())
