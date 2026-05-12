from __future__ import annotations

import asyncio
import logging
from typing import Any

from lowlatcv.metrics.tracer import Tracer
from lowlatcv.pipeline.stage import Stage, StageRunner

log = logging.getLogger(__name__)


class Pipeline:
    """Facade over the stage graph: setup forward, run all stages, teardown reverse."""

    def __init__(
        self,
        stages: list[Stage[Any, Any]],
        tracer: Tracer,
        queue_size: int = 2,
    ) -> None:
        if not stages:
            raise ValueError("pipeline requires at least one stage")
        self._stages = stages
        self._tracer = tracer
        self._queue_size = queue_size
        self._tasks: list[asyncio.Task[None]] = []
        self._queues: list[asyncio.Queue[Any]] = []
        self._started = False

    async def start(self) -> None:
        for stage in self._stages:
            await stage.setup()
        self._queues = [
            asyncio.Queue(maxsize=self._queue_size) for _ in range(len(self._stages) - 1)
        ]
        for i, stage in enumerate(self._stages):
            in_q = self._queues[i - 1] if i > 0 else None
            out_qs = [self._queues[i]] if i < len(self._stages) - 1 else []
            runner: StageRunner[Any, Any] = StageRunner(stage, in_q, out_qs, self._tracer)
            self._tasks.append(asyncio.create_task(runner.run(), name=stage.name))
        self._started = True

    async def await_completion(self) -> None:
        if not self._tasks:
            return
        done, pending = await asyncio.wait(self._tasks, return_when=asyncio.FIRST_EXCEPTION)
        exc: BaseException | None = None
        for t in done:
            e = t.exception()
            if e is not None:
                exc = e
                break
        if exc is not None:
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            raise exc
        if pending:
            await asyncio.gather(*pending)

    async def stop(self) -> None:
        for t in self._tasks:
            if not t.done():
                t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._teardown()

    async def _teardown(self) -> None:
        for stage in reversed(self._stages):
            try:
                await stage.teardown()
            except Exception:
                log.exception("teardown failed: %s", stage.name)

    async def run(self) -> None:
        await self.start()
        try:
            await self.await_completion()
        finally:
            for t in self._tasks:
                if not t.done():
                    t.cancel()
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
            await self._teardown()
