---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Testing

## Framework

Use **pytest** via `uv run`:

```bash
uv run pytest -q
```

## Coverage

```bash
uv run pytest --cov=src --cov-report=term-missing -q
```

## Test Organization

Use `pytest.mark` for test categorization:

```python
import pytest

@pytest.mark.unit
def test_detector_outputs_detections():
    backend = FakeBackend()
    detector = Detector(backend)
    ...

@pytest.mark.integration
def test_pipeline_end_to_end():
    pipeline = build_pipeline(PipelineConfig(...))
    ...
```

## Conventions

- Detector, tracker, and VLM stages must use a `FakeBackend` in unit tests (deterministic, no model download)
- Integration tests exercise the full pipeline on fixtures in `tests/fixtures/`
- Latency-regression tests compare `bench` JSON output against a stored baseline with tolerance

## Reference

See skill: `test` for project-specific pytest invocation and fixture conventions.
