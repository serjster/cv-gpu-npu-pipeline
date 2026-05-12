"""Pipeline configuration: frozen dataclasses + YAML overlay + env override loader.

Defines ``PipelineConfig`` and one sub-config per stage (source, preprocess,
detector, tracker, vlm, overlay, sink, metrics) plus a ``profile`` switch
that selects between the macOS and Linux/AMD runtime profiles. Values come
from defaults, optional YAML overlay (``--config``), then ``LOWLATCV_*``
environment overrides (e.g. ``LOWLATCV_SOURCE__URI=...``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Literal, cast, get_type_hints

import yaml


@dataclass(frozen=True, slots=True)
class SourceConfig:
    uri: str = "0"
    target_fps: float | None = None
    hw_decoder: str | None = None


@dataclass(frozen=True, slots=True)
class PreprocessConfig:
    width: int = 640
    height: int = 640
    layout: Literal["NCHW", "NHWC"] = "NCHW"
    normalize: bool = True


@dataclass(frozen=True, slots=True)
class DetectorConfig:
    backend: str = "fake"
    weights: str | None = None
    score_threshold: float = 0.25
    nms_threshold: float = 0.45
    max_detections: int = 100
    execution_provider: str | None = None
    num_classes: int = 80


@dataclass(frozen=True, slots=True)
class TrackerConfig:
    iou_threshold: float = 0.3
    max_age: int = 30
    min_hits: int = 3


@dataclass(frozen=True, slots=True)
class VLMConfig:
    backend: str = "stub"
    weights: str | None = None
    max_in_flight: int = 1
    refresh_seconds: float | None = None
    drop_policy: Literal["block", "drop_oldest_non_first"] = "drop_oldest_non_first"


@dataclass(frozen=True, slots=True)
class OverlayConfig:
    color: tuple[int, int, int] = (0, 255, 0)
    font_scale: float = 0.5
    draw_caption: bool = True


@dataclass(frozen=True, slots=True)
class SinkConfig:
    kind: Literal["display", "file", "null"] = "null"
    output: str | None = None
    codec: str = "h264"


@dataclass(frozen=True, slots=True)
class MetricsConfig:
    report_interval_s: float | None = None
    format: Literal["table", "json", "csv"] = "table"
    output: str | None = None


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    source: SourceConfig = field(default_factory=SourceConfig)
    preprocess: PreprocessConfig = field(default_factory=PreprocessConfig)
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    tracker: TrackerConfig = field(default_factory=TrackerConfig)
    vlm: VLMConfig = field(default_factory=VLMConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    sink: SinkConfig = field(default_factory=SinkConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    queue_size: int = 2
    profile: Literal["macos", "linux-amd"] = "macos"

    @classmethod
    def load(cls, yaml_path: Path | str | None = None) -> PipelineConfig:
        data: dict[str, Any] = {}
        if yaml_path is not None:
            with open(yaml_path) as f:
                loaded = yaml.safe_load(f) or {}
            if not isinstance(loaded, dict):
                raise ValueError(f"{yaml_path}: top-level must be a mapping")
            data = loaded
        data = _apply_env_overlay(data)
        return cast("PipelineConfig", _build(cls, data))


_ENV_PREFIX = "LOWLATCV_"


def _apply_env_overlay(data: dict[str, Any]) -> dict[str, Any]:
    for k, v in os.environ.items():
        if not k.startswith(_ENV_PREFIX):
            continue
        path = k[len(_ENV_PREFIX) :].lower().split("__")
        node = data
        for p in path[:-1]:
            child = node.get(p)
            if not isinstance(child, dict):
                child = {}
                node[p] = child
            node = child
        node[path[-1]] = _coerce(v)
    return data


def _coerce(v: str) -> Any:
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "none", ""):
        return None
    try:
        if "." in v:
            return float(v)
        return int(v)
    except ValueError:
        return v


def _build(cls: Any, data: dict[str, Any]) -> Any:
    types = get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        val = data[f.name]
        ftype = types.get(f.name, Any)
        if isinstance(ftype, type) and is_dataclass(ftype) and isinstance(val, dict):
            val = _build(ftype, val)
        kwargs[f.name] = val
    return cls(**kwargs)
