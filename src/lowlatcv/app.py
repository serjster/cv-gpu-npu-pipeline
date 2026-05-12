from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import typer
from numpy.typing import NDArray

from lowlatcv.config import PipelineConfig
from lowlatcv.metrics.reporter import CSVReporter, JSONReporter, Reporter, TableReporter
from lowlatcv.metrics.tracer import Tracer
from lowlatcv.models.frame import Frame
from lowlatcv.pipeline.runner import Pipeline
from lowlatcv.pipeline.stage import EOF

log = logging.getLogger(__name__)
app = typer.Typer(no_args_is_help=True, add_completion=False)


class _StubSource:
    name = "source"

    def __init__(self, frames: int, height: int, width: int) -> None:
        self._frames = frames
        self._height = height
        self._width = width
        self._i = 0

    async def setup(self) -> None: ...

    async def process(self, item: Any) -> Any:
        if self._i >= self._frames:
            return EOF
        image: NDArray[np.uint8] = np.zeros((self._height, self._width, 3), dtype=np.uint8)
        f = Frame(id=self._i, timestamp_ns=time.perf_counter_ns(), image=image)
        self._i += 1
        return f

    async def teardown(self) -> None: ...


class _Passthrough:
    def __init__(self, name: str) -> None:
        self.name = name

    async def setup(self) -> None: ...

    async def process(self, item: Frame) -> Frame:
        return item

    async def teardown(self) -> None: ...


class _NullSink:
    name = "sink"

    async def setup(self) -> None: ...

    async def process(self, item: Frame) -> None:
        return None

    async def teardown(self) -> None: ...


def _make_reporter(fmt: str) -> Reporter:
    if fmt == "json":
        return JSONReporter()
    if fmt == "csv":
        return CSVReporter()
    if fmt == "table":
        return TableReporter()
    raise typer.BadParameter(f"unknown report format: {fmt}")


def _build_stub_pipeline(cfg: PipelineConfig, tracer: Tracer, frames: int) -> Pipeline:
    stages: list[Any] = [
        _StubSource(frames=frames, width=cfg.preprocess.width, height=cfg.preprocess.height),
        _Passthrough("preprocess"),
        _Passthrough("detector"),
        _Passthrough("tracker"),
        _Passthrough("overlay"),
        _NullSink(),
    ]
    return Pipeline(stages, tracer, queue_size=cfg.queue_size)


async def _drive(cfg: PipelineConfig, frames: int, fmt: str) -> str:
    tracer = Tracer()
    reporter = _make_reporter(fmt)
    tracer.subscribe(reporter)
    pipeline = _build_stub_pipeline(cfg, tracer, frames=frames)
    await pipeline.run()
    return reporter.render()


@app.command()
def run(
    source: str | None = typer.Option(None, help="video source URI / device index / RTSP URL"),
    config: Path | None = typer.Option(None, help="YAML config overlay"),
    frames: int = typer.Option(10, help="stop after N frames (phase-1 stub)"),
    display: bool = typer.Option(False, help="show display window (phase-2)"),
) -> None:
    """Run the pipeline. Phase 1: passthrough stub."""
    cfg = PipelineConfig.load(config)
    typer.echo("phase-1: stub pipeline (real stages land in phase 2+)")
    report = asyncio.run(_drive(cfg, frames, cfg.metrics.format))
    typer.echo(report)


@app.command()
def bench(
    source: str | None = typer.Option(None, help="video source URI"),
    config: Path | None = typer.Option(None, help="YAML config overlay"),
    frames: int = typer.Option(1000, help="benchmark over N frames"),
    report_format: str = typer.Option("table", "--report-format"),
    report_path: Path | None = typer.Option(None, "--report-path"),
) -> None:
    """Run benchmark mode and report latency."""
    cfg = PipelineConfig.load(config)
    report = asyncio.run(_drive(cfg, frames, report_format))
    if report_path is not None:
        report_path.write_text(report)
        typer.echo(f"wrote report → {report_path}")
    else:
        typer.echo(report)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    app()


if __name__ == "__main__":
    main()
