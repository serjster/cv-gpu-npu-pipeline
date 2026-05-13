---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Patterns

## Protocol (Duck Typing)

`typing.Protocol` is the primary abstraction — prefer it over ABCs for structural subtyping:

```python
from typing import Protocol

class Stage(Protocol):
    async def process(self, input_data: object) -> object: ...
    def stop(self) -> None: ...
```

Protocols enable swappable backends (detector, tracker, VLM) behind a common interface without inheritance.

## Dataclasses as DTOs

Use `@dataclass(frozen=True, slots=True)` for data crossing stage boundaries:

```python
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class Detection:
    class_id: int
    bbox: tuple[float, float, float, float]
    confidence: float

@dataclass(frozen=True, slots=True)
class Track:
    id: int
    bbox: tuple[float, float, float, float]
    trajectory: tuple[tuple[float, float], ...] = field(default=())
```

No primitive obsession — avoid raw `dict` flowing between stages.

## Context Managers & Generators

- Use context managers (`with` statement) for deterministic resource cleanup
- Use generators for frame iteration and lazy evaluation:

```python
from collections.abc import Iterator

def iter_frames(path: str) -> Iterator[Frame]:
    cap = cv2.VideoCapture(path)
    try:
        idx = 0
        while True:
            ret, img = cap.read()
            if not ret:
                break
            yield Frame(index=idx, image=img, timestamp_ns=cap.get(cv2.CAP_PROP_POS_MSEC) * 1_000_000)
            idx += 1
    finally:
        cap.release()
```

## Dependency Injection

Stages receive dependencies via `__init__` — no service locators, no module-level globals:

```python
class Detector:
    def __init__(self, model: ModelBackend, confidence: float = 0.5) -> None:
        self._model = model
        self._confidence = confidence
```

Factory methods as `classmethod` constructors: `Detector.from_config(cfg)`.

## Reference

See skill: `design-patterns` for comprehensive patterns including SOLID, composition, and dependency management.
