---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Coding Style

## Standards

- Follow **PEP 8** conventions
- Use **type annotations** on all function signatures — `mypy --strict` is the target
- Python 3.13+: prefer `str | None` over `Optional[str]`, `list[Foo]` over `List[Foo]`

## Immutability

Prefer `@dataclass(frozen=True, slots=True)` for value types:

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Detection:
    class_id: int
    bbox: tuple[float, float, float, float]
    confidence: float

@dataclass(frozen=True, slots=True)
class Frame:
    index: int
    image: "np.ndarray"
    timestamp_ns: int
```

Avoid plain `dict`/`tuple` crossing stage boundaries — use typed dataclasses.

## Formatting

- **ruff format** for code formatting and import sorting (100-char line length, per `pyproject.toml`)
- **ruff check** for linting (pyflakes, pycodestyle, isort, bugbear)
- Run `uv run ruff format src tests && uv run ruff check src tests && uv run mypy src` before committing

## Reference

See skill: `design-patterns` for comprehensive Python idioms and SOLID patterns.
