# AGENTS.md

Operating manual for AI coding agents (Claude Code, Codex CLI, Cursor, etc.) working in this repository.

## Mission

This project is an FPGA-pipeline emulator written in Python. Every change must keep the abstraction faithful to the dataflow model described in `ARCHITECTURE.md` (independent stages, bounded queues, back-pressure, per-stage latency tracing). If a change blurs the stage boundaries — e.g. a stage that secretly does work belonging to another stage, or a global mutable state shared across stages — reject the change or refactor.

## Principles

- **DRY** — Extract shared logic only after the third concrete usage (Rule of Three). Two near-duplicates beat a premature abstraction.
- **SOLID** — Each stage has one responsibility. Stages depend on the `Stage` protocol, not on each other. New stages plug in by composition, not by editing existing stages.
- **TDD** — For new behaviour, write the failing test first. Run `uv run pytest` after every change.
- **Design Patterns** — Consult `.claude/skills/design-patterns/SKILL.md` and `docs/coding/design_patterns/` before introducing a new abstraction.

## Skills

Available under `.claude/skills/`:

- `lint` — `ruff check` + `mypy` over `src/` and `tests/`.
- `test` — `uv run pytest`.
- `format` — `ruff format`.
- `todo` — manage `TODO.md` at project root.
- `design-patterns` — SOLID, GoF, anti-patterns (Python-flavoured).
- `hf-cli` — Hugging Face Hub CLI for fetching detector / VLM weights.

## Coding rules (Python)

- Python 3.13+. Type-annotate everything. `mypy --strict` is the target.
- Prefer `dataclasses` (or `attrs`) over dicts for structured data. No primitive obsession.
- Prefer `Protocol` over ABCs for stage / strategy interfaces.
- No `print` in library code — use `logging` with the per-module logger (`logger = logging.getLogger(__name__)`).
- No global mutable state. Pipeline wiring lives in `lowlatcv.app`.
- Stages must accept their dependencies via `__init__` (constructor injection). No service locators, no singletons except `logging`.
- Async I/O (`asyncio`) is allowed; CPU-bound stages run in a worker thread or process via the `Stage` runner so the event loop stays responsive.
- Use `numpy` views, not copies, when handing frames between stages on the same process. Document any copy with a one-line comment.
- Latency tracing is mandatory for every stage — wrap work in `tracer.span("stage_name")` so benchmarks remain meaningful.

## Definition of done

A change is done when:

1. New behaviour has tests; they pass under `uv run pytest`.
2. `ruff check`, `ruff format --check`, and `mypy src` are all clean.
3. The dataflow diagram in `ARCHITECTURE.md` still matches the code; if not, update the diagram in the same commit.
4. If a new stage was added, it appears in the FPGA-mapping table in `ARCHITECTURE.md` with a note on how it would be implemented on the Versal target.

## What not to do

- Do not import a heavy ML framework at module top level — gate it behind the stage that needs it, so `lowlatcv --help` stays snappy.
- Do not add a "framework" or plugin system before there are 3+ concrete stages that need it.
- Do not block the per-frame loop on the VLM. The VLM is intentionally off the critical path; it runs on a sparse schedule and posts results back asynchronously.
- Do not introduce features the FPGA target cannot reasonably implement (e.g. dynamic Python callbacks inside the hot loop). Keep parity in mind.
