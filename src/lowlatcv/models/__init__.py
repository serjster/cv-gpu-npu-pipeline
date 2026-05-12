"""Immutable value objects exchanged across stage boundaries.

Re-exports the frozen+slots dataclasses (``Frame``, ``Detection``, ``Track``,
``Caption``, ``CaptionRequest``). No raw dicts cross stage queues.
"""

from lowlatcv.models.caption import Caption, CaptionRequest
from lowlatcv.models.frame import Detection, Frame, LetterboxMeta, Track

__all__ = ["Caption", "CaptionRequest", "Detection", "Frame", "LetterboxMeta", "Track"]
