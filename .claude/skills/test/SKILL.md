---
name: test
description: Run the pytest suite. Use when the user asks to "run tests", "test", or "check tests". Also use after making code changes to verify they pass.
argument-hint: "[pytest args, e.g. tests/test_tracker.py::test_id_persistence]"
allowed-tools: Bash(uv run pytest *)
---

Run the test suite with pytest:

```bash
uv run pytest -q
```

Useful filters:

```bash
# A single test file
uv run pytest tests/test_tracker.py -q

# A single test by node id
uv run pytest tests/test_tracker.py::test_id_persistence -q

# Show prints + full tracebacks (debugging a failure)
uv run pytest -vv -s tests/test_tracker.py

# Run in parallel (after `uv add --dev pytest-xdist`)
uv run pytest -n auto -q
```

Notes:

- The detector and VLM stages have a `FakeBackend` (deterministic, no model download). CI tests must use it; do not pull real weights inside the test process.
- The integration test runs the full pipeline on a 30-frame fixture clip in `tests/fixtures/`.
- A latency-regression test compares `bench` JSON output against a stored baseline with a tolerance band. If you intentionally change a stage's perf, update the baseline in the same commit and explain why.
