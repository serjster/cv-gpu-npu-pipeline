from __future__ import annotations

import asyncio
import logging
from typing import Any, Final, Protocol, TypeVar

from lowlatcv.metrics.tracer import Tracer

InT_contra = TypeVar("InT_contra", contravariant=True)
OutT_co = TypeVar("OutT_co", covariant=True)


class _EOFType:
    _instance: _EOFType | None = None

    def __new__(cls) -> _EOFType:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "<EOF>"


EOF: Final[_EOFType] = _EOFType()


class Stage(Protocol[InT_contra, OutT_co]):
    name: str

    async def setup(self) -> None: ...

    async def process(self, item: InT_contra) -> OutT_co | None: ...

    async def teardown(self) -> None: ...


log = logging.getLogger(__name__)


class StageRunner[InT, OutT]:
    """Pull-process-push loop. Source stages pass ``in_q=None`` and emit ``EOF`` to end."""

    def __init__(
        self,
        stage: Stage[InT, OutT],
        in_q: asyncio.Queue[Any] | None,
        out_qs: list[asyncio.Queue[Any]],
        tracer: Tracer,
    ) -> None:
        self._stage = stage
        self._in_q = in_q
        self._out_qs = out_qs
        self._tracer = tracer

    async def run(self) -> None:
        while True:
            if self._in_q is None:
                item: Any = None
                qd: int | None = None
            else:
                item = await self._in_q.get()
                if item is EOF:
                    await self._broadcast(EOF)
                    return
                qd = self._in_q.qsize()

            with self._tracer.span(self._stage.name, queue_depth_in=qd):
                result = await self._stage.process(item)

            if result is EOF:
                await self._broadcast(EOF)
                return
            if result is None:
                continue
            await self._broadcast(result)

    async def _broadcast(self, item: Any) -> None:
        for q in self._out_qs:
            await q.put(item)
