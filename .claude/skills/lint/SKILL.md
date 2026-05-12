---
name: lint
description: Run ruff + mypy to check for lint errors, formatting violations, and type errors. Use when the user asks to "lint", "check code quality", or "check for errors". Also use after making code changes to verify they pass static analysis.
argument-hint: []
allowed-tools: Bash(uv run ruff check src tests), Bash(uv run ruff format --check src tests), Bash(uv run mypy src)
---

This project uses **ruff** for linting + formatting and **mypy** for type checking. Run all three after code changes:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
```

- **ruff check** — lint rules (pyflakes, pycodestyle, isort, bugbear, etc.). Real errors must be fixed.
- **ruff format --check** — verifies formatting matches `ruff format`. To fix in place: drop `--check`.
- **mypy src** — strict type checking on `src/`. Targets `mypy --strict`. New code must be fully annotated.

If `uv run` is slow on a fresh machine, that's `uv sync` populating the venv — only happens once.

Common false positives:

- `ruff` warning about an unused import in a stub: usually means the symbol is gated behind a `TYPE_CHECKING` block. Verify before "fixing".
- `mypy` complaining about `cv2` / `transformers` having no stubs: add an override to `pyproject.toml`:
  ```toml
  [[tool.mypy.overrides]]
  module = ["cv2.*", "transformers.*"]
  ignore_missing_imports = true
  ```
