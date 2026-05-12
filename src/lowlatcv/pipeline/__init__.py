"""Stage graph: protocols, orchestrator, and concrete stage implementations.

Re-exports the ``Stage`` protocol + ``StageRunner`` pull/process/push loop,
the ``Pipeline`` Facade, and the concrete ``FrameSource`` / ``Preprocess`` /
``FrameSink`` backends. Detector / Tracker / Overlay / VLM stages land here
as later phases plug them in.
"""

from lowlatcv.pipeline.preprocess import Preprocess
from lowlatcv.pipeline.runner import Pipeline
from lowlatcv.pipeline.sink import DisplaySink, FileSink, FrameSink, NullSink
from lowlatcv.pipeline.source import FileSource, FrameSource, WebcamSource
from lowlatcv.pipeline.stage import EOF, Stage, StageRunner

__all__ = [
    "EOF",
    "DisplaySink",
    "FileSink",
    "FileSource",
    "FrameSink",
    "FrameSource",
    "NullSink",
    "Pipeline",
    "Preprocess",
    "Stage",
    "StageRunner",
    "WebcamSource",
]
