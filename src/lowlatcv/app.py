"""Typer CLI entry point and pipeline wiring (Dependency Injection root).

Exposes ``lowlatcv run`` and ``lowlatcv bench`` subcommands, builds a
``Pipeline`` for the active ``PipelineConfig`` via :func:`build_pipeline`
(Source → Preprocess → Sink today; detector / tracker / overlay / VLM slot
in here as later phases land), and drives it on the asyncio event loop with
a ``Tracer`` and a chosen ``Reporter``.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from pathlib import Path
from typing import Any

import typer

from lowlatcv.config import PipelineConfig, SinkConfig
from lowlatcv.metrics.reporter import CSVReporter, JSONReporter, Reporter, TableReporter
from lowlatcv.metrics.tracer import Tracer
from lowlatcv.pipeline import sink as sink_module
from lowlatcv.pipeline import source as source_module
from lowlatcv.pipeline.preprocess import Preprocess
from lowlatcv.pipeline.runner import Pipeline

log = logging.getLogger(__name__)
app = typer.Typer(no_args_is_help=True, add_completion=False)


def _make_reporter(fmt: str) -> Reporter:
    if fmt == "json":
        return JSONReporter()
    if fmt == "csv":
        return CSVReporter()
    if fmt == "table":
        return TableReporter()
    raise typer.BadParameter(f"unknown report format: {fmt}")


def build_pipeline(
    cfg: PipelineConfig,
    tracer: Tracer,
    frame_limit: int | None = None,
) -> Pipeline:
    """Wire Source → Preprocess → Sink. Real CV stages land in phases 3+."""
    source = source_module.from_uri(cfg.source.uri, cfg.source, frame_limit=frame_limit)
    preprocess = Preprocess(cfg.preprocess)
    sink = sink_module.from_config(cfg.sink)
    stages: list[Any] = [source, preprocess, sink]
    return Pipeline(stages, tracer, queue_size=cfg.queue_size)


async def _drive(cfg: PipelineConfig, frame_limit: int | None, fmt: str) -> str:
    tracer = Tracer()
    reporter = _make_reporter(fmt)
    tracer.subscribe(reporter)
    pipeline = build_pipeline(cfg, tracer, frame_limit=frame_limit)
    await pipeline.run()
    return reporter.render()


@app.command()
def run(
    source: str | None = typer.Option(None, help="video source URI / device index / RTSP URL"),
    config: Path | None = typer.Option(None, help="YAML config overlay"),
    frames: int = typer.Option(0, help="stop after N frames (0 = run to EOF)"),
    display: bool = typer.Option(False, help="show display window"),
    sink: str | None = typer.Option(None, help="sink kind: display / null / file"),
    output: Path | None = typer.Option(None, help="file sink path"),
) -> None:
    """Run the pipeline end-to-end."""
    cfg = PipelineConfig.load(config)
    if source is not None:
        cfg = dataclasses.replace(cfg, source=dataclasses.replace(cfg.source, uri=source))
    sink_cfg = cfg.sink
    if display:
        sink_cfg = dataclasses.replace(sink_cfg, kind="display")
    if sink is not None:
        sink_cfg = dataclasses.replace(sink_cfg, kind=sink)  # type: ignore[arg-type]
    if output is not None:
        sink_cfg = dataclasses.replace(sink_cfg, output=str(output))
    cfg = dataclasses.replace(cfg, sink=sink_cfg)
    limit = frames if frames > 0 else None
    report = asyncio.run(_drive(cfg, limit, cfg.metrics.format))
    typer.echo(report)


@app.command()
def bench(
    source: str | None = typer.Option(None, help="video source URI"),
    config: Path | None = typer.Option(None, help="YAML config overlay"),
    frames: int = typer.Option(1000, help="benchmark over N frames"),
    report_format: str = typer.Option("table", "--report-format"),
    report_path: Path | None = typer.Option(None, "--report-path"),
) -> None:
    """Run benchmark mode and report latency. Sink is forced to null."""
    cfg = PipelineConfig.load(config)
    if source is not None:
        cfg = dataclasses.replace(cfg, source=dataclasses.replace(cfg.source, uri=source))
    cfg = dataclasses.replace(cfg, sink=SinkConfig(kind="null"))
    limit = frames if frames > 0 else None
    report = asyncio.run(_drive(cfg, limit, report_format))
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
