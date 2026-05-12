# ast-index Rules — `cv-gpu-npu-pipeline`

Real-time CV pipeline (Python reference for AMD Versal AI Edge / XDNA NPU).
Single source root, Python-only, package name `lowlatcv` under `src/`.
The planned module layout in `CLAUDE.md` is the source of truth for the
symbol examples below — some files may not exist yet during early
scaffolding, but the names are stable.

## Keep the index up to date

After pulling, rebasing, or finishing a multi-file edit, run:

```bash
ast-index update
```

Only changed files are reindexed (seconds). A full `ast-index rebuild` is
only needed if the index appears corrupted or after a tool upgrade.

## Mandatory search rules

1. **ALWAYS use ast-index FIRST** for any code-search task.
2. **NEVER duplicate results** — if ast-index returned hits, that IS the
   complete answer. Do not re-run grep to "double-check".
3. Use the Grep tool **only when** ast-index returned empty, or for
   regex / string-literal patterns that are not symbol names (log
   messages, config keys, model repo IDs, env vars like
   `PYTORCH_ENABLE_MPS_FALLBACK`).

## Mandatory read rules

1. **Before `Read`-ing any file over 500 lines, run `ast-index outline
   <file>` first.**
2. Use the outline to locate the specific symbol / line range you need,
   then `Read` that slice via `offset` / `limit`.
3. Never bulk-read large files without an outline — it wastes the agent's
   context window and produces worse answers.
4. Reference docs under `docs/research/` and `docs/coding/design_patterns/`
   are prose, not code — ast-index will not index them. Read them
   directly when looking up FPGA pipeline stages or pattern definitions.

## Rules for subagents

When you spawn a subagent for code search (via the Agent/Task tool), the
subagent does **not** inherit this file. Include the block below verbatim
in the subagent's prompt:

```
Use `ast-index` via Bash for code search (NOT grep / the Grep tool):
  ast-index search "query"           — universal search
  ast-index file "Name"              — find a file by name fragment
  ast-index symbol "Name"            — find a symbol definition
  ast-index class "Name"             — find a class / protocol / dataclass
  ast-index usages "Name"            — every usage of a symbol
  ast-index callers "func"           — functions that call this one
  ast-index implementations "Proto"  — concrete implementers of a Protocol
  ast-index refs "Name"              — cross-references (defs + imports + usages)
Use Grep ONLY if ast-index returned empty.

Before Read-ing any file over 500 lines, FIRST run
  ast-index outline <file>
to get its structure, then Read only the targeted slice via offset/limit.
Never bulk-read large files.
```

## Command cheat sheet

Grouped by intent. Full list and flags: `ast-index --help`.

- **Search:** `search`, `file`, `symbol`, `class`
- **Usages & flow:** `usages`, `callers`, `call-tree`, `refs`
- **Hierarchy:** `implementations`, `hierarchy`
- **Modules / deps:** `module`, `deps`, `dependents`, `api`, `unused-deps`
- **Files:** `outline`, `imports`, `changed`
- **Quality:** `todo`, `deprecated`, `unused-symbols`
- **Index mgmt:** `rebuild`, `update`, `stats`

## Common use cases (project-specific)

Symbols below come from the planned layout in `CLAUDE.md`. Use them as
pattern-match examples; substitute concrete names you've located.

- `ast-index implementations "Stage"` — every stage that conforms to the
  `Stage` protocol (`FrameSource`, `Preprocess`, `Detector`, `Tracker`,
  `VLM`, `Overlay`, `Sink`). Use this when adding a new stage or auditing
  the pipeline graph.
- `ast-index implementations "FrameSource"` / `"FrameSink"` — concrete
  source/sink backends (file, camera, RTSP / display, file, null).
- `ast-index callers "tracer.span"` — every stage instrumented for the
  latency report. Catching a stage missing instrumentation is the usual
  reason for a hole in the percentile table.
- `ast-index usages "Frame"` / `"Detection"` / `"Track"` / `"Caption"` —
  who reads/writes the immutable dataclasses crossing stage boundaries.
- `ast-index callers "Pipeline.start"` — entry points that build and run
  the orchestrator (CLI commands, tests, benchmarks).
- `ast-index deps "lowlatcv.pipeline.vlm"` — what the VLM stage pulls in
  (transformers, torch). Use before gating a heavy import.
- `ast-index dependents "lowlatcv.models.frame"` — what depends on the
  core dataclasses; touching `Frame` ripples widely.
- `ast-index call-tree "Detector.process" -d 3` — trace what runs on the
  per-frame critical path. Anything surprising here means a latency
  regression.
- `ast-index changed` — symbols modified in your current branch. Useful
  for "what am I actually changing?" PR summaries.
- `ast-index outline src/lowlatcv/pipeline/runner.py` — structure before
  reading the orchestrator.
- `ast-index todo` — TODO / FIXME / HACK across the tree.

## Scoping searches

Symbol-returning commands accept scope filters — use them to kill noise:

```bash
ast-index usages "Frame" --module lowlatcv.pipeline      # only pipeline package
ast-index search "tracer.span" --in-file detector.py     # only inside this file
ast-index symbol "Stage" --type class                    # only class-kind symbols (incl. Protocol)
```

## When `ast-index` returns empty

Legitimate reasons:

- Symbol genuinely doesn't exist yet (this project is being scaffolded;
  many planned modules in `CLAUDE.md` are unwritten).
- Index is stale — run `ast-index update` and retry.
- Dynamic / deferred imports: heavy deps (`torch`, `coremltools`,
  `transformers`) are imported inside stage methods, not at module top.
  `imports` queries on those stage files won't show them — read the
  function body or `grep` the import line.
- You're searching for a string literal (log message, env var, model
  repo ID, ffmpeg flag) — use Grep.
- Code lives in third-party site-packages (under `.venv/`) — ast-index
  only indexes the project tree. Read those files directly.

Do **not** fall back to bulk `Read` of files in these cases. Use Grep with
a specific pattern, or `outline` + targeted `Read`.
