---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Hooks

## PostToolUse Hooks

Configure in `.claude/settings.local.json`:

- **ruff format**: Auto-run `uv run ruff format` on edited `.py` files
- **ruff check**: Auto-run `uv run ruff check` on edited `.py` files
- **mypy**: Auto-run `uv run mypy src` on edited `.py` files

## Warnings

- Warn about `print()` statements in edited files — use `logging.getLogger(__name__)` instead
- Warn about missing type annotations on new functions — `mypy --strict` requires them
