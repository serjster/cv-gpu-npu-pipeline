"""VLM captioning: ``VLM`` Protocol + backends + ``VLMWorker`` + ``CaptionResultStore``.

The VLM lives **off** the per-frame critical path. Captioning is driven
from the orchestrator main loop indirectly: ``CaptionScheduler``
(see ``pipeline.scheduler``) emits ``CaptionRequest`` Commands into a
bounded ``queue.Queue``; a ``VLMWorker`` thread (or process) pulls
those commands and calls ``VLM.caption`` which produces a ``Caption``.
Captions are joined back into the per-frame path through
``CaptionResultStore``, a thread-safe ``dict[track_id, Caption]`` that
the overlay stage reads each frame. The per-frame stages never
``await`` the VLM and never block on its queue (the scheduler uses
``put_nowait`` and applies an explicit drop policy on Full).
"""

from __future__ import annotations

import base64
import contextlib
import json
import logging
import queue
import threading
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any, Protocol

import cv2
from numpy.typing import NDArray

from lowlatcv.config import VLMConfig
from lowlatcv.models.caption import Caption, CaptionRequest

log = logging.getLogger(__name__)


class VLM(Protocol):
    """Strategy for image-to-text models. ``caption`` is **sync** — workers run in threads."""

    name: str

    async def setup(self) -> None: ...
    def caption(self, request: CaptionRequest) -> Caption: ...
    async def teardown(self) -> None: ...


class CaptionResultStore:
    """Thread-safe ``dict[track_id, Caption]`` — the join point between the VLM
    worker and the overlay stage on the per-frame critical path."""

    def __init__(self) -> None:
        self._data: dict[int, Caption] = {}
        self._lock = threading.Lock()

    def put(self, caption: Caption) -> None:
        with self._lock:
            self._data[caption.track_id] = caption

    def get(self, track_id: int) -> Caption | None:
        with self._lock:
            return self._data.get(track_id)

    def drop(self, track_id: int) -> None:
        with self._lock:
            self._data.pop(track_id, None)

    def snapshot(self) -> dict[int, Caption]:
        with self._lock:
            return dict(self._data)


class FakeVLM:
    """Deterministic stub backend for tests and weights-less smoke runs.

    Optional ``latency_s`` lets a test artificially slow the VLM down to
    prove that the per-frame critical path is unaffected (phase 5
    bench proof).
    """

    name = "fake-vlm"

    def __init__(
        self,
        latency_s: float = 0.0,
        prefix: str = "fake",
        crash: bool = False,
    ) -> None:
        self._latency = latency_s
        self._prefix = prefix
        self._crash = crash

    async def setup(self) -> None: ...

    def caption(self, request: CaptionRequest) -> Caption:
        if self._latency:
            time.sleep(self._latency)
        if self._crash:
            raise RuntimeError("fake vlm crash")
        text = f"{self._prefix} track={request.track_id} frame={request.frame_id}"
        return Caption(
            track_id=request.track_id,
            text=text,
            model="fake",
            ts_ns=time.perf_counter_ns(),
        )

    async def teardown(self) -> None: ...


class OllamaVLM:
    """HTTP-client backend for a local Ollama server.

    Encodes the crop as JPEG, base64-encodes it, POSTs to ``/api/generate``
    with the configured prompt. Returns the response text as a ``Caption``.
    Ollama abstracts the host accelerator — ROCm on Linux, Metal on macOS.
    """

    name = "ollama-vlm"

    def __init__(self, cfg: VLMConfig) -> None:
        self._cfg = cfg
        self._endpoint = cfg.host.rstrip("/") + "/api/generate"

    async def setup(self) -> None:
        log.info(
            "OllamaVLM endpoint=%s model=%s prompt=%r timeout=%ss",
            self._endpoint,
            self._cfg.model,
            self._cfg.prompt,
            self._cfg.request_timeout_s,
        )

    def caption(self, request: CaptionRequest) -> Caption:
        crop = request.crop
        if not isinstance(crop, (bytes, bytearray)):
            crop = _encode_jpeg(crop)
        prompt = request.prompt or self._cfg.prompt
        body = json.dumps(
            {
                "model": self._cfg.model,
                "prompt": prompt,
                "images": [base64.b64encode(crop).decode("ascii")],
                "stream": False,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self._endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._cfg.request_timeout_s) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise RuntimeError(f"ollama request failed: {e}") from e
        text = str(payload.get("response", "")).strip()
        return Caption(
            track_id=request.track_id,
            text=text,
            model=self._cfg.model,
            ts_ns=time.perf_counter_ns(),
        )

    async def teardown(self) -> None: ...


class FastFlowLMVLM:
    """HTTP-client backend for a local FastFlowLM ``flm serve`` server.

    Runs the VLM on the AMD Ryzen AI NPU (XDNA2). FLM exposes an
    OpenAI-compatible ``/v1/chat/completions`` endpoint on port 52625 by
    default. The image is sent inline as a base64 ``data:image/jpeg``
    content part — the same shape an OpenAI client would use.

    Linux-only — XDNA2 NPU (Strix / Strix Halo / Kraken / Gorgon Point) is
    a prerequisite. On macOS use ``CoreMLVLM`` (Phase 6 macOS half) or
    ``OllamaVLM`` (Metal GPU). The Strategy split keeps the per-frame
    plumbing identical; only the backend swaps.
    """

    name = "flm-vlm"
    DEFAULT_HOST = "http://localhost:52625"

    def __init__(self, cfg: VLMConfig) -> None:
        self._cfg = cfg
        host = cfg.host
        # If the user opted into this backend but left the Ollama default
        # host untouched, swap to FLM's port so the request actually lands.
        if host == VLMConfig().host:
            host = self.DEFAULT_HOST
        self._endpoint = host.rstrip("/") + "/v1/chat/completions"

    async def setup(self) -> None:
        log.info(
            "FastFlowLMVLM endpoint=%s model=%s prompt=%r timeout=%ss",
            self._endpoint,
            self._cfg.model,
            self._cfg.prompt,
            self._cfg.request_timeout_s,
        )

    def caption(self, request: CaptionRequest) -> Caption:
        crop = request.crop
        if not isinstance(crop, (bytes, bytearray)):
            crop = _encode_jpeg(crop)
        prompt = request.prompt or self._cfg.prompt
        data_url = "data:image/jpeg;base64," + base64.b64encode(crop).decode("ascii")
        body = json.dumps(
            {
                "model": self._cfg.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": data_url}},
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                "stream": False,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self._endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._cfg.request_timeout_s) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise RuntimeError(f"fastflowlm request failed: {e}") from e
        try:
            text = str(payload["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"fastflowlm response missing content: {payload!r}") from e
        return Caption(
            track_id=request.track_id,
            text=text,
            model=self._cfg.model,
            ts_ns=time.perf_counter_ns(),
        )

    async def teardown(self) -> None: ...


def _encode_jpeg(image: NDArray[Any]) -> bytes:
    ok, buf = cv2.imencode(".jpg", image)
    if not ok:
        raise RuntimeError("cv2.imencode failed for VLM crop")
    return bytes(buf)


class VLMWorker:
    """Background thread (or process) that pulls ``CaptionRequest``\\s and calls
    the VLM. Crashes are contained: the worker logs the exception and keeps
    pulling so the pipeline carries on without captions for the failing track."""

    def __init__(
        self,
        vlm: VLM,
        store: CaptionResultStore,
        request_queue: queue.Queue[CaptionRequest | None],
    ) -> None:
        self._vlm = vlm
        self._store = store
        self._q = request_queue
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="vlm-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        with contextlib.suppress(queue.Full):
            self._q.put_nowait(None)
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break
            try:
                cap = self._vlm.caption(item)
                self._store.put(cap)
            except Exception:
                log.exception("vlm worker error for track %s", item.track_id)


def from_config(cfg: VLMConfig) -> VLM | None:
    """Factory Method: select a VLM backend from ``VLMConfig.backend``.

    Returns ``None`` for ``backend="none"`` so the pipeline can skip wiring
    a worker entirely. Tests use ``backend="fake"``.
    """
    backend = cfg.backend.lower()
    if backend == "none":
        return None
    if backend == "fake":
        return FakeVLM(latency_s=cfg.fake_latency_s)
    if backend == "ollama":
        return OllamaVLM(cfg)
    if backend == "fastflowlm":
        return FastFlowLMVLM(cfg)
    raise ValueError(f"unknown VLM backend: {cfg.backend}")


if not TYPE_CHECKING:
    VLM.from_config = staticmethod(from_config)
