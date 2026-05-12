from __future__ import annotations

import asyncio
from typing import Any

from lowlatcv.metrics.tracer import Span, Tracer
from lowlatcv.pipeline.runner import Pipeline
from lowlatcv.pipeline.stage import EOF


class _FastSource:
    name = "src"

    def __init__(self, n: int) -> None:
        self._n = n
        self._i = 0

    async def setup(self) -> None: ...

    async def process(self, item: Any) -> Any:
        if self._i >= self._n:
            return EOF
        self._i += 1
        return self._i

    async def teardown(self) -> None: ...


class _SlowMid:
    name = "slow"

    async def setup(self) -> None: ...

    async def process(self, item: int) -> int:
        await asyncio.sleep(0.005)
        return item

    async def teardown(self) -> None: ...


class _Drain:
    name = "sink"

    async def setup(self) -> None: ...

    async def process(self, item: int) -> None:
        return None

    async def teardown(self) -> None: ...


def test_back_pressure_keeps_queue_depth_under_or_equal_maxsize() -> None:
    depths: list[int] = []

    class _R:
        def emit(self, s: Span) -> None:
            if s.queue_depth_in is not None:
                depths.append(s.queue_depth_in)

    async def go() -> None:
        tracer = Tracer()
        tracer.subscribe(_R())
        stages: list[Any] = [_FastSource(30), _SlowMid(), _Drain()]
        await Pipeline(stages, tracer, queue_size=2).run()

    asyncio.run(go())
    assert depths
    assert max(depths) <= 2
