---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Security

## Secret Management

Load secrets from `.env` (never committed) and fail fast if missing:

```python
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("VLM_API_KEY")
if not api_key:
    raise RuntimeError("VLM_API_KEY not set in .env")
```

Never log secrets, embed them in source, or serialize them to disk.

## Dependency Security

- `ruff check` with security rules enabled catches common vulnerability patterns
- Heavy ML dependencies (`torch`, `transformers`, `coremltools`) are gated behind the stage that needs them — not imported at module top level
- Model weights are fetched via `hf download` with SHA verification

## Reference

See `docs/coding/design_patterns/` for project-specific guidance.
