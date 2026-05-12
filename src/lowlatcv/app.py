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
from lowlatcv.pipeline import detector as detector_module
from lowlatcv.pipeline import sink as sink_module
from lowlatcv.pipeline import source as source_module
from lowlatcv.pipeline import tracker as tracker_module
from lowlatcv.pipeline import vlm as vlm_module
from lowlatcv.pipeline.overlay import Overlay
from lowlatcv.pipeline.preprocess import Preprocess
from lowlatcv.pipeline.runner import Pipeline
from lowlatcv.pipeline.scheduler import CaptionScheduler
from lowlatcv.pipeline.vlm import CaptionResultStore

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
    raw: bool = False,
    pace: bool = False,
) -> Pipeline:
    """Wire the stage graph.

    Full graph: Source → Preprocess → Detector → Overlay → Sink.
    ``raw=True``: Source → Sink only — pure decode-and-display passthrough.
    ``pace=True``: source throttles to SourceConfig.target_fps (or the file's
    intrinsic FPS) so visual playback runs at real-time; bench leaves it off.
    """
    source = source_module.from_uri(cfg.source.uri, cfg.source, frame_limit=frame_limit, pace=pace)
    sink = sink_module.from_config(cfg.sink)
    if raw:
        stages: list[Any] = [source, sink]
        return Pipeline(stages, tracer, queue_size=cfg.queue_size)
    preprocess = Preprocess(cfg.preprocess)
    detector = detector_module.from_config(cfg.detector)
    tracker = tracker_module.from_config(cfg.tracker)
    caption_store = CaptionResultStore()
    vlm = vlm_module.from_config(cfg.vlm)
    scheduler = CaptionScheduler(cfg.vlm, caption_store, vlm=vlm)
    overlay = Overlay(cfg.overlay, caption_store=caption_store, caption_chars=cfg.vlm.caption_chars)
    stages = [source, preprocess, detector, tracker, scheduler, overlay, sink]
    return Pipeline(stages, tracer, queue_size=cfg.queue_size)


async def _drive(
    cfg: PipelineConfig,
    frame_limit: int | None,
    fmt: str,
    raw: bool = False,
    pace: bool = False,
) -> str:
    tracer = Tracer()
    reporter = _make_reporter(fmt)
    tracer.subscribe(reporter)
    pipeline = build_pipeline(cfg, tracer, frame_limit=frame_limit, raw=raw, pace=pace)
    await pipeline.run()
    return reporter.render()


def _apply_vlm_overrides(
    cfg: PipelineConfig,
    backend: str | None,
    model: str | None,
    host: str | None,
    prompt: str | None,
    cooldown: float | None,
    rate_hz: float | None,
    fake_latency: float | None,
) -> PipelineConfig:
    v = cfg.vlm
    if backend is not None:
        v = dataclasses.replace(v, backend=backend)
    if model is not None:
        v = dataclasses.replace(v, model=model)
    if host is not None:
        v = dataclasses.replace(v, host=host)
    if prompt is not None:
        v = dataclasses.replace(v, prompt=prompt)
    if cooldown is not None:
        v = dataclasses.replace(v, refresh_seconds=cooldown)
    if rate_hz is not None:
        v = dataclasses.replace(v, rate_limit_hz=rate_hz)
    if fake_latency is not None:
        v = dataclasses.replace(v, fake_latency_s=fake_latency)
    return dataclasses.replace(cfg, vlm=v)


def _apply_detector_overrides(
    cfg: PipelineConfig,
    backend: str | None,
    weights: Path | None,
    score_threshold: float | None,
    iou_threshold: float | None,
    execution_provider: str | None,
) -> PipelineConfig:
    det = cfg.detector
    if backend is not None:
        det = dataclasses.replace(det, backend=backend)
    if weights is not None:
        det = dataclasses.replace(det, weights=str(weights))
    if score_threshold is not None:
        det = dataclasses.replace(det, score_threshold=score_threshold)
    if iou_threshold is not None:
        det = dataclasses.replace(det, nms_threshold=iou_threshold)
    if execution_provider is not None:
        det = dataclasses.replace(det, execution_provider=execution_provider)
    return dataclasses.replace(cfg, detector=det)


@app.command()
def run(
    source: str | None = typer.Option(None, help="video source URI / device index / RTSP URL"),
    config: Path | None = typer.Option(None, help="YAML config overlay"),
    frames: int = typer.Option(0, help="stop after N frames (0 = run to EOF)"),
    display: bool = typer.Option(False, help="show display window"),
    sink: str | None = typer.Option(None, help="sink kind: display / null / file"),
    output: Path | None = typer.Option(None, help="file sink path"),
    detector: str | None = typer.Option(None, help="detector backend: fake / onnx / coreml"),
    weights: Path | None = typer.Option(None, help="detector weights path"),
    score_threshold: float | None = typer.Option(None, "--score-threshold"),
    iou_threshold: float | None = typer.Option(None, "--iou-threshold"),
    execution_provider: str | None = typer.Option(
        None,
        "--execution-provider",
        help="onnxruntime EP, e.g. CoreMLExecutionProvider / ROCMExecutionProvider / CPUExecutionProvider",
    ),
    raw: bool = typer.Option(
        False,
        "--raw",
        help="passthrough mode: Source → Sink only, no preprocess/detector/overlay (baseline decode+display cost).",
    ),
    vsync: bool = typer.Option(False, "--vsync", help="enable display vsync"),
    fps: float | None = typer.Option(
        None,
        "--fps",
        help="pace the source to N fps (default: file's intrinsic FPS; --fps 0 = no pacing).",
    ),
    vlm: str | None = typer.Option(None, "--vlm", help="VLM backend: fake / ollama / none"),
    vlm_model: str | None = typer.Option(None, "--vlm-model", help="Ollama model name"),
    vlm_host: str | None = typer.Option(None, "--vlm-host"),
    vlm_prompt: str | None = typer.Option(None, "--vlm-prompt"),
    vlm_cooldown: float | None = typer.Option(
        None, "--vlm-cooldown", help="per-track cooldown seconds"
    ),
    vlm_rate: float | None = typer.Option(None, "--vlm-rate", help="global rate limit Hz"),
    vlm_fake_latency: float | None = typer.Option(
        None, "--vlm-fake-latency", help="FakeVLM synthetic latency (s) for the no-impact proof"
    ),
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
    if vsync:
        sink_cfg = dataclasses.replace(sink_cfg, vsync=True)
    cfg = dataclasses.replace(cfg, sink=sink_cfg)
    cfg = _apply_detector_overrides(
        cfg, detector, weights, score_threshold, iou_threshold, execution_provider
    )
    cfg = _apply_vlm_overrides(
        cfg, vlm, vlm_model, vlm_host, vlm_prompt, vlm_cooldown, vlm_rate, vlm_fake_latency
    )
    # Pacing: default on (real-time playback). --fps 0 disables. --fps N overrides.
    if fps is None:
        pace = True
    elif fps == 0:
        pace = False
    else:
        cfg = dataclasses.replace(cfg, source=dataclasses.replace(cfg.source, target_fps=fps))
        pace = True
    limit = frames if frames > 0 else None
    report = asyncio.run(_drive(cfg, limit, cfg.metrics.format, raw=raw, pace=pace))
    typer.echo(report)


@app.command()
def bench(
    source: str | None = typer.Option(None, help="video source URI"),
    config: Path | None = typer.Option(None, help="YAML config overlay"),
    frames: int = typer.Option(1000, help="benchmark over N frames"),
    report_format: str = typer.Option("table", "--report-format"),
    report_path: Path | None = typer.Option(None, "--report-path"),
    detector: str | None = typer.Option(None, help="detector backend: fake / onnx / coreml"),
    weights: Path | None = typer.Option(None, help="detector weights path"),
    score_threshold: float | None = typer.Option(None, "--score-threshold"),
    iou_threshold: float | None = typer.Option(None, "--iou-threshold"),
    execution_provider: str | None = typer.Option(None, "--execution-provider"),
    vlm: str | None = typer.Option(None, "--vlm"),
    vlm_model: str | None = typer.Option(None, "--vlm-model"),
    vlm_host: str | None = typer.Option(None, "--vlm-host"),
    vlm_prompt: str | None = typer.Option(None, "--vlm-prompt"),
    vlm_cooldown: float | None = typer.Option(None, "--vlm-cooldown"),
    vlm_rate: float | None = typer.Option(None, "--vlm-rate"),
    vlm_fake_latency: float | None = typer.Option(None, "--vlm-fake-latency"),
) -> None:
    """Run benchmark mode and report latency. Sink is forced to null."""
    cfg = PipelineConfig.load(config)
    if source is not None:
        cfg = dataclasses.replace(cfg, source=dataclasses.replace(cfg.source, uri=source))
    cfg = dataclasses.replace(cfg, sink=SinkConfig(kind="null"))
    cfg = _apply_detector_overrides(
        cfg, detector, weights, score_threshold, iou_threshold, execution_provider
    )
    cfg = _apply_vlm_overrides(
        cfg, vlm, vlm_model, vlm_host, vlm_prompt, vlm_cooldown, vlm_rate, vlm_fake_latency
    )
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
