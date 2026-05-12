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
from lowlatcv.pipeline.async_detector import AsyncDetector
from lowlatcv.pipeline.detector import TiledOnnxDetector
from lowlatcv.pipeline.overlay import Overlay
from lowlatcv.pipeline.preprocess import Preprocess
from lowlatcv.pipeline.runner import Pipeline
from lowlatcv.pipeline.scheduler import CaptionScheduler
from lowlatcv.pipeline.tile_hints import TileHintBoard
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
    hint_board: TileHintBoard | None = None
    detector: Any
    if cfg.detector.tile_on_demand and cfg.detector.backend.lower() == "onnx-tiled":
        hint_board = TileHintBoard()
        detector = TiledOnnxDetector(cfg.detector, hint_board=hint_board)
    else:
        detector = detector_module.from_config(cfg.detector)
    if cfg.detector.async_detection:
        detector = AsyncDetector(detector, detect_every_n=cfg.detector.detect_every_n)
    tracker = tracker_module.from_config(cfg.tracker, hint_board=hint_board)
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


def _apply_imgsz(cfg: PipelineConfig, imgsz: int | None) -> PipelineConfig:
    if imgsz is None:
        return cfg
    return dataclasses.replace(
        cfg,
        preprocess=dataclasses.replace(cfg.preprocess, width=imgsz, height=imgsz),
    )


def _apply_detector_overrides(
    cfg: PipelineConfig,
    backend: str | None,
    weights: Path | None,
    score_threshold: float | None,
    iou_threshold: float | None,
    execution_provider: str | None,
    num_classes: int | None,
    tiles: str | None,
    tile_overlap: float | None,
    tile_input_size: int | None,
    async_detection: bool | None,
    detect_every_n: int | None,
    tile_on_demand: bool | None,
    tile_refresh_tiles_per_cycle: int | None,
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
    if num_classes is not None:
        det = dataclasses.replace(det, num_classes=num_classes)
    if tiles is not None:
        rows, cols = _parse_tiles(tiles)
        det = dataclasses.replace(det, tile_rows=rows, tile_cols=cols)
    if tile_overlap is not None:
        det = dataclasses.replace(det, tile_overlap=tile_overlap)
    if tile_input_size is not None:
        det = dataclasses.replace(det, tile_input_size=tile_input_size)
    if async_detection is not None:
        det = dataclasses.replace(det, async_detection=async_detection)
    if detect_every_n is not None:
        det = dataclasses.replace(det, detect_every_n=detect_every_n)
    if tile_on_demand is not None:
        det = dataclasses.replace(det, tile_on_demand=tile_on_demand)
    if tile_refresh_tiles_per_cycle is not None:
        det = dataclasses.replace(det, tile_refresh_tiles_per_cycle=tile_refresh_tiles_per_cycle)
    return dataclasses.replace(cfg, detector=det)


def _parse_tiles(spec: str) -> tuple[int, int]:
    parts = spec.lower().replace("×", "x").split("x")
    if len(parts) != 2:
        raise typer.BadParameter(f"--tiles must be ROWSxCOLS, got {spec!r}")
    try:
        rows, cols = int(parts[0]), int(parts[1])
    except ValueError as e:
        raise typer.BadParameter(f"--tiles must be integers, got {spec!r}") from e
    if rows < 1 or cols < 1:
        raise typer.BadParameter(f"--tiles dims must be >= 1, got {spec!r}")
    return rows, cols


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
    imgsz: int | None = typer.Option(
        None, "--imgsz", help="square detector input size (sets PreprocessConfig.width and height)"
    ),
    num_classes: int | None = typer.Option(
        None, "--num-classes", help="detector class count (COCO=80, VisDrone=10)"
    ),
    tiles: str | None = typer.Option(
        None, "--tiles", help="ROWSxCOLS tiled inference (e.g. 3x3); use --detector onnx-tiled"
    ),
    tile_overlap: float | None = typer.Option(None, "--tile-overlap"),
    tile_input_size: int | None = typer.Option(
        None, "--tile-input-size", help="per-tile letterbox target (default 640)"
    ),
    async_detection: bool = typer.Option(
        False,
        "--async-detection",
        help="run detector on a worker thread off the per-frame critical path",
    ),
    detect_every_n: int | None = typer.Option(
        None, "--detect-every-n", help="submit a frame to the async detector every N frames"
    ),
    tile_on_demand: bool = typer.Option(
        False,
        "--tile-on-demand",
        help="onnx-tiled only: run only on tiles the tracker hinted (lost/tentative tracks) plus a rotating refresh",
    ),
    tile_refresh_tiles_per_cycle: int | None = typer.Option(
        None,
        "--tile-refresh-tiles-per-cycle",
        help="how many rotating refresh tiles to add per inference cycle (default 1)",
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
        cfg,
        detector,
        weights,
        score_threshold,
        iou_threshold,
        execution_provider,
        num_classes,
        tiles,
        tile_overlap,
        tile_input_size,
        async_detection or None,
        detect_every_n,
        tile_on_demand or None,
        tile_refresh_tiles_per_cycle,
    )
    cfg = _apply_vlm_overrides(
        cfg, vlm, vlm_model, vlm_host, vlm_prompt, vlm_cooldown, vlm_rate, vlm_fake_latency
    )
    cfg = _apply_imgsz(cfg, imgsz)
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
    imgsz: int | None = typer.Option(None, "--imgsz"),
    num_classes: int | None = typer.Option(None, "--num-classes"),
    tiles: str | None = typer.Option(None, "--tiles"),
    tile_overlap: float | None = typer.Option(None, "--tile-overlap"),
    tile_input_size: int | None = typer.Option(None, "--tile-input-size"),
    async_detection: bool = typer.Option(False, "--async-detection"),
    detect_every_n: int | None = typer.Option(None, "--detect-every-n"),
    tile_on_demand: bool = typer.Option(False, "--tile-on-demand"),
    tile_refresh_tiles_per_cycle: int | None = typer.Option(None, "--tile-refresh-tiles-per-cycle"),
) -> None:
    """Run benchmark mode and report latency. Sink is forced to null."""
    cfg = PipelineConfig.load(config)
    if source is not None:
        cfg = dataclasses.replace(cfg, source=dataclasses.replace(cfg.source, uri=source))
    cfg = dataclasses.replace(cfg, sink=SinkConfig(kind="null"))
    cfg = _apply_detector_overrides(
        cfg,
        detector,
        weights,
        score_threshold,
        iou_threshold,
        execution_provider,
        num_classes,
        tiles,
        tile_overlap,
        tile_input_size,
        async_detection or None,
        detect_every_n,
        tile_on_demand or None,
        tile_refresh_tiles_per_cycle,
    )
    cfg = _apply_vlm_overrides(
        cfg, vlm, vlm_model, vlm_host, vlm_prompt, vlm_cooldown, vlm_rate, vlm_fake_latency
    )
    cfg = _apply_imgsz(cfg, imgsz)
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
