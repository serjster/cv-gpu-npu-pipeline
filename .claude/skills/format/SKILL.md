---
name: format
description: Format Python code with ruff. Use when the user asks to "format", "reformat", or before committing.
argument-hint: "[paths, default 'src tests']"
allowed-tools: Bash(uv run ruff format src tests), Bash(uv run ruff format --check src tests)
---

This project uses **ruff format** as the single auto-formatter (no black, no autopep8). Settings live in `pyproject.toml` under `[tool.ruff]`.

```bash
# Apply formatting in place
uv run ruff format src tests

# Check only (CI-style, non-zero exit if a file would change)
uv run ruff format --check src tests
```

## Conventions ruff handles

- **Indentation**: 4 spaces.
- **Quotes**: double quotes (ruff default).
- **Line length**: 100 (set in `pyproject.toml`).
- **Trailing commas**: in multi-line collections / arg lists.
- **Imports**: sorted by `ruff check --select I` (isort rules).

## Conventions ruff does NOT enforce — keep them yourself

- **No comments that restate the code.** Docstrings on public APIs only when behaviour is non-obvious.
- **Type-annotate everything.** `mypy --strict` is the target.
- **Prefer `@dataclass(frozen=True, slots=True)`** over plain classes for value types.
- **One module per concern**: a stage is a module, not a sub-package, until it grows.

If the file you're editing diverges from ruff output, run `ruff format` on it before committing — but never reformat unrelated files in a code-change commit.
