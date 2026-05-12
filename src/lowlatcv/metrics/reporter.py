"""Span Observer subscribers that render per-stage percentile snapshots.

``Reporter`` is the base aggregator (``emit`` collects spans, ``snapshot``
returns per-stage ``Percentiles``). ``TableReporter`` / ``JSONReporter`` /
``CSVReporter`` are the three output formats picked by ``--report-format``
or ``MetricsConfig.format``.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from dataclasses import asdict

from lowlatcv.metrics.tracer import Percentiles, Span, percentiles


class Reporter:
    """Base Observer subscriber. Aggregates spans into per-stage percentile snapshots."""

    def __init__(self) -> None:
        self._buckets: dict[str, list[int]] = defaultdict(list)

    def emit(self, span: Span) -> None:
        self._buckets[span.stage].append(span.duration_ns)

    def snapshot(self) -> dict[str, Percentiles]:
        return {stage: percentiles(samples) for stage, samples in self._buckets.items()}

    def render(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError


class TableReporter(Reporter):
    def render(self) -> str:
        snap = self.snapshot()
        header = ("stage", "n", "p50_ms", "p90_ms", "p99_ms", "max_ms")
        rows: list[tuple[str, ...]] = [header]
        for stage, p in snap.items():
            rows.append(
                (
                    stage,
                    str(p.count),
                    f"{p.p50_ns / 1e6:.3f}",
                    f"{p.p90_ns / 1e6:.3f}",
                    f"{p.p99_ns / 1e6:.3f}",
                    f"{p.max_ns / 1e6:.3f}",
                )
            )
        widths = [max(len(r[i]) for r in rows) for i in range(len(header))]
        lines = ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in rows]
        sep = "  ".join("-" * widths[i] for i in range(len(header)))
        lines.insert(1, sep)
        return "\n".join(lines)


class JSONReporter(Reporter):
    def render(self) -> str:
        return json.dumps(
            {stage: asdict(p) for stage, p in self.snapshot().items()},
            indent=2,
        )


class CSVReporter(Reporter):
    def render(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["stage", "count", "p50_ns", "p90_ns", "p99_ns", "max_ns"])
        for stage, p in self.snapshot().items():
            w.writerow([stage, p.count, p.p50_ns, p.p90_ns, p.p99_ns, p.max_ns])
        return buf.getvalue()
