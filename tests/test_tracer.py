from __future__ import annotations

from lowlatcv.metrics.tracer import Span, Tracer, percentiles


def test_percentiles_on_arithmetic_progression() -> None:
    # nearest-rank with round(p * (n-1)) over 1..100 →
    # p50 = idx 50 → 51; p90 = idx 89 → 90; p99 = idx 98 → 99; max = 100.
    p = percentiles(list(range(1, 101)))
    assert p.count == 100
    assert p.p50_ns == 51
    assert p.p90_ns == 90
    assert p.p99_ns == 99
    assert p.max_ns == 100
    assert p.p50_ns <= p.p90_ns <= p.p99_ns <= p.max_ns


def test_percentiles_empty() -> None:
    p = percentiles([])
    assert p.count == 0
    assert p.p50_ns == 0
    assert p.p90_ns == 0
    assert p.p99_ns == 0
    assert p.max_ns == 0


def test_tracer_records_per_stage_stats() -> None:
    tr = Tracer()
    for _ in range(10):
        with tr.span("a"):
            pass
    for _ in range(5):
        with tr.span("b"):
            pass
    a = tr.stats("a")
    b = tr.stats("b")
    assert a is not None
    assert a.count == 10
    assert b is not None
    assert b.count == 5
    assert tr.stats("nope") is None


def test_tracer_nested_spans_isolated() -> None:
    tr = Tracer()
    with tr.span("outer"), tr.span("inner"):
        pass
    with tr.span("outer"), tr.span("inner"):
        pass
    inner = tr.stats("inner")
    outer = tr.stats("outer")
    assert inner is not None
    assert inner.count == 2
    assert outer is not None
    assert outer.count == 2


def test_tracer_emits_span_with_queue_depth_to_subscribers() -> None:
    tr = Tracer()
    received: list[Span] = []

    class _Recorder:
        def emit(self, s: Span) -> None:
            received.append(s)

    tr.subscribe(_Recorder())
    with tr.span("s", queue_depth_in=7):
        pass
    assert len(received) == 1
    assert received[0].stage == "s"
    assert received[0].queue_depth_in == 7
    assert received[0].duration_ns >= 0
