from __future__ import annotations

import contextlib
import time
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Span:
    stage: str
    started_ns: int
    ended_ns: int
    queue_depth_in: int | None

    @property
    def duration_ns(self) -> int:
        return self.ended_ns - self.started_ns


@dataclass(frozen=True, slots=True)
class Percentiles:
    count: int
    p50_ns: int
    p90_ns: int
    p99_ns: int
    max_ns: int


class SpanSink(Protocol):
    def emit(self, span: Span) -> None: ...


class Tracer:
    """Observer hub for stage spans. Owns a sliding-window aggregator per stage."""

    def __init__(self, window: int = 1024) -> None:
        self._sinks: list[SpanSink] = []
        self._window = window
        self._buffers: dict[str, deque[Span]] = {}

    def subscribe(self, sink: SpanSink) -> None:
        self._sinks.append(sink)

    @contextlib.contextmanager
    def span(
        self,
        stage: str,
        queue_depth_in: int | None = None,
    ) -> Iterator[None]:
        started = time.perf_counter_ns()
        try:
            yield
        finally:
            ended = time.perf_counter_ns()
            s = Span(stage=stage, started_ns=started, ended_ns=ended, queue_depth_in=queue_depth_in)
            buf = self._buffers.get(stage)
            if buf is None:
                buf = deque(maxlen=self._window)
                self._buffers[stage] = buf
            buf.append(s)
            for sink in self._sinks:
                sink.emit(s)

    def stats(self, stage: str) -> Percentiles | None:
        buf = self._buffers.get(stage)
        if not buf:
            return None
        return percentiles([s.duration_ns for s in buf])

    def stages(self) -> list[str]:
        return list(self._buffers.keys())


def percentiles(samples: list[int]) -> Percentiles:
    if not samples:
        return Percentiles(count=0, p50_ns=0, p90_ns=0, p99_ns=0, max_ns=0)
    sorted_ns = sorted(samples)
    n = len(sorted_ns)

    def q(p: float) -> int:
        idx = max(0, min(n - 1, int(round(p * (n - 1)))))
        return sorted_ns[idx]

    return Percentiles(
        count=n,
        p50_ns=q(0.50),
        p90_ns=q(0.90),
        p99_ns=q(0.99),
        max_ns=sorted_ns[-1],
    )
