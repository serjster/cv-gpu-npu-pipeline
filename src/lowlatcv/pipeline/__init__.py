"""Stage graph: protocols, orchestrator, and concrete stage implementations.

Re-exports the ``Stage`` protocol + ``StageRunner`` pull/process/push loop,
the ``Pipeline`` Facade, and the concrete ``FrameSource`` / ``Preprocess`` /
``FrameSink`` backends. Detector / Tracker / Overlay / VLM stages land here
as later phases plug them in.
"""

from lowlatcv.pipeline.detector import CoreMLDetector, Detector, FakeDetector, OnnxDetector
from lowlatcv.pipeline.overlay import Overlay
from lowlatcv.pipeline.preprocess import Preprocess
from lowlatcv.pipeline.runner import Pipeline
from lowlatcv.pipeline.scheduler import CaptionScheduler
from lowlatcv.pipeline.sink import FileSink, FrameSink, NullSink, SDLDisplaySink
from lowlatcv.pipeline.source import FileSource, FrameSource, WebcamSource
from lowlatcv.pipeline.stage import EOF, Stage, StageRunner
from lowlatcv.pipeline.tracker import ByteTracker, Tracker
from lowlatcv.pipeline.vlm import VLM, CaptionResultStore, FakeVLM, OllamaVLM, VLMWorker

__all__ = [
    "EOF",
    "VLM",
    "ByteTracker",
    "CaptionResultStore",
    "CaptionScheduler",
    "CoreMLDetector",
    "Detector",
    "FakeDetector",
    "FakeVLM",
    "FileSink",
    "FileSource",
    "FrameSink",
    "FrameSource",
    "NullSink",
    "OllamaVLM",
    "OnnxDetector",
    "Overlay",
    "Pipeline",
    "Preprocess",
    "SDLDisplaySink",
    "Stage",
    "StageRunner",
    "Tracker",
    "VLMWorker",
    "WebcamSource",
]
