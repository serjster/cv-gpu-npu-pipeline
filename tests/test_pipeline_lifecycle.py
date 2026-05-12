from __future__ import annotations

import asyncio
from typing import Any

import pytest

from lowlatcv.metrics.tracer import Tracer
from lowlatcv.pipeline.runner import Pipeline
from lowlatcv.pipeline.stage import EOF


class _Recording:
    def __init__(self, name: str, ops: list[str]) -> None:
        self.name = name
        self._ops = ops

    async def setup(self) -> None:
        self._ops.append(f"setup:{self.name}")

    async def process(self, item: Any) -> Any:
        return item

    async def teardown(self) -> None:
        self._ops.append(f"teardown:{self.name}")


class _RecordingSource(_Recording):
    def __init__(self, name: str, ops: list[str], n: int) -> None:
        super().__init__(name, ops)
        self._n = n
        self._i = 0

    async def process(self, item: Any) -> Any:
        if self._i >= self._n:
            return EOF
        self._i += 1
        return self._i


def test_pipeline_runs_eof_with_setup_forward_teardown_reverse() -> None:
    ops: list[str] = []
    stages: list[Any] = [
        _RecordingSource("a", ops, 3),
        _Recording("b", ops),
        _Recording("c", ops),
    ]
    tracer = Tracer()
    pipeline = Pipeline(stages, tracer)
    asyncio.run(pipeline.run())

    setups = [o for o in ops if o.startswith("setup:")]
    teardowns = [o for o in ops if o.startswith("teardown:")]
    assert setups == ["setup:a", "setup:b", "setup:c"]
    assert teardowns == ["teardown:c", "teardown:b", "teardown:a"]

    assert tracer.stats("a") is not None
    assert tracer.stats("b") is not None
    assert tracer.stats("c") is not None


def test_pipeline_propagates_stage_exception_and_still_tears_down() -> None:
    ops: list[str] = []

    class _Boom(_Recording):
        async def process(self, item: Any) -> Any:
            raise RuntimeError("boom")

    stages: list[Any] = [
        _RecordingSource("a", ops, 5),
        _Boom("b", ops),
        _Recording("c", ops),
    ]
    tracer = Tracer()
    pipeline = Pipeline(stages, tracer)

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(pipeline.run())

    assert "teardown:a" in ops
    assert "teardown:b" in ops
    assert "teardown:c" in ops


def test_pipeline_rejects_empty_stage_list() -> None:
    with pytest.raises(ValueError, match="at least one stage"):
        Pipeline([], Tracer())
