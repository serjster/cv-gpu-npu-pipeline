"""``JsonlExportSink``: tap stage that writes per-frame detections + tracks to JSONL.

One line per frame::

    {"frame_id": 0, "timestamp_ns": 12345, "detections": [...], "tracks": [...]}

Each detection is ``{bbox: [x1,y1,x2,y2], score, class_id}``; each track is
the same plus ``track_id``, ``state``, ``age``, ``frames_since_match``.

Pass-through on the ``Frame`` it consumes so the same instance can be
chained before the real sink (``Source → ... → Overlay → JsonlExportSink
→ DisplaySink``) and live runs export the same format as the offline
reference builder. Used by ``scripts/build_reference.py`` and the
``--export-jsonl`` CLI flag.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import IO, Any

from lowlatcv.models.frame import Detection, Frame, Track

log = logging.getLogger(__name__)


class JsonlExportSink:
    name = "export_jsonl"

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._fh: IO[str] | None = None
        self._count = 0

    async def setup(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._path.open("w")
        log.info("JsonlExportSink writing → %s", self._path)

    async def process(self, item: Frame) -> Frame:
        if self._fh is None:
            return item
        record: dict[str, Any] = {
            "frame_id": item.id,
            "timestamp_ns": item.timestamp_ns,
            "detections": [_det_dict(d) for d in item.detections],
            "tracks": [_track_dict(t) for t in item.tracks],
        }
        self._fh.write(json.dumps(record, separators=(",", ":")))
        self._fh.write("\n")
        self._count += 1
        return item

    async def teardown(self) -> None:
        if self._fh is not None:
            self._fh.flush()
            self._fh.close()
            self._fh = None
            log.info("JsonlExportSink closed (%d frames → %s)", self._count, self._path)


def _det_dict(d: Detection) -> dict[str, Any]:
    return {
        "bbox": [int(d.bbox[0]), int(d.bbox[1]), int(d.bbox[2]), int(d.bbox[3])],
        "score": float(d.score),
        "class_id": int(d.class_id),
    }


def _track_dict(t: Track) -> dict[str, Any]:
    return {
        "track_id": int(t.track_id),
        "bbox": [int(t.bbox[0]), int(t.bbox[1]), int(t.bbox[2]), int(t.bbox[3])],
        "score": float(t.score),
        "class_id": int(t.class_id),
        "state": t.state.value,
        "age": int(t.age),
        "hits": int(t.hits),
        "frames_since_match": int(t.frames_since_match),
        "last_seen_frame": int(t.last_seen_frame),
    }
