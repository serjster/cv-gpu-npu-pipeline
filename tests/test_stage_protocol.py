from __future__ import annotations

import asyncio
from typing import Any

from lowlatcv.metrics.tracer import Tracer
from lowlatcv.pipeline.stage import EOF, StageRunner


class _Counter:
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


class _Plus10:
    name = "plus10"

    async def setup(self) -> None: ...

    async def process(self, item: int) -> int:
        return item + 10

    async def teardown(self) -> None: ...


class _Collect:
    name = "sink"

    def __init__(self) -> None:
        self.received: list[int] = []

    async def setup(self) -> None: ...

    async def process(self, item: int) -> None:
        self.received.append(item)
        return None

    async def teardown(self) -> None: ...


def test_stage_runner_chains_three_stages_to_eof() -> None:
    async def go() -> _Collect:
        tracer = Tracer()
        src = _Counter(5)
        mid = _Plus10()
        sink = _Collect()
        q1: asyncio.Queue[Any] = asyncio.Queue(maxsize=2)
        q2: asyncio.Queue[Any] = asyncio.Queue(maxsize=2)
        r1: StageRunner[Any, int] = StageRunner(src, None, [q1], tracer)
        r2: StageRunner[int, int] = StageRunner(mid, q1, [q2], tracer)
        r3: StageRunner[int, None] = StageRunner(sink, q2, [], tracer)
        await asyncio.gather(r1.run(), r2.run(), r3.run())
        return sink

    sink = asyncio.run(go())
    assert sink.received == [11, 12, 13, 14, 15]


def test_stage_runner_skips_none_results() -> None:
    class _OddOnly:
        name = "odd"

        async def setup(self) -> None: ...

        async def process(self, item: int) -> int | None:
            return item if item % 2 == 1 else None

        async def teardown(self) -> None: ...

    async def go() -> _Collect:
        tracer = Tracer()
        src = _Counter(6)
        mid = _OddOnly()
        sink = _Collect()
        q1: asyncio.Queue[Any] = asyncio.Queue(maxsize=2)
        q2: asyncio.Queue[Any] = asyncio.Queue(maxsize=2)
        await asyncio.gather(
            StageRunner(src, None, [q1], tracer).run(),
            StageRunner(mid, q1, [q2], tracer).run(),
            StageRunner(sink, q2, [], tracer).run(),
        )
        return sink

    sink = asyncio.run(go())
    assert sink.received == [1, 3, 5]
