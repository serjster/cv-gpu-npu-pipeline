---
name: design-patterns
description: Enforce modern design patterns, SOLID principles, and DRY when writing new code or refactoring. Auto-invoked when creating new classes, modules, or refactoring existing code. Consults project reference documentation under docs/coding/design_patterns/.
user-invocable: false
---

# Design Patterns & SOLID Principles

When writing new code or refactoring existing code, apply modern design patterns, SOLID principles, and DRY. This skill provides the rules and pointers to detailed reference material in the project.

## When This Skill Applies

- Creating new classes, modules, or packages
- Refactoring existing code
- Reviewing code for structural issues
- Designing APIs or abstractions
- Any task involving class hierarchies, interfaces, or dependency management

## Rules

### SOLID — Always Apply

1. **Single Responsibility (SRP)**: Each class/module has one reason to change. If a class handles both data and I/O, split it.
2. **Open/Closed (OCP)**: Use protocols and polymorphism so new behavior is added by extension, not modification.
3. **Liskov Substitution (LSP)**: Subclasses must be drop-in replacements for their base type. Never leave protocol methods unimplemented or throw `fatalError` for required methods.
4. **Interface Segregation (ISP)**: Prefer small, focused protocols over fat interfaces. A consumer should not depend on methods it doesn't use.
5. **Dependency Inversion (DIP)**: High-level modules depend on abstractions (protocols), not concrete implementations. Inject dependencies via constructor.

### DRY — With Judgment

- Extract shared logic only when there are **3+ concrete usages** (Rule of Three). Two similar blocks are fine — premature abstraction is worse than mild duplication.
- Prefer composition over inheritance for code reuse.

### Design Patterns — Reach for When Appropriate

Consult the reference docs when you recognize these situations:

| Situation | Pattern | Reference |
|-----------|---------|-----------|
| Need to create objects without specifying exact class | Factory / Abstract Factory | `docs/coding/design_patterns/dp_factory_method_uml.md` |
| Want to add behavior without modifying existing code | Decorator | `docs/coding/design_patterns/dp_decorator_uml.md` |
| Need to switch between algorithms at runtime | Strategy | `docs/coding/design_patterns/dp_strategy_uml.md` |
| Object behavior changes based on internal state | State | `docs/coding/design_patterns/dp_state_uml.md` |
| Need to decouple event producers from consumers | Observer | `docs/coding/design_patterns/dp_observer_uml.md` |
| Want to simplify a complex subsystem | Facade | `docs/coding/design_patterns/dp_facade_uml.md` |
| Need to adapt an incompatible interface | Adapter | `docs/coding/design_patterns/dp_adapter_uml.md` |
| Need to traverse a collection without exposing internals | Iterator | `docs/coding/design_patterns/dp_iterator_uml.md` |
| Need to encapsulate a request as an object | Command | `docs/coding/design_patterns/dp_command_uml.md` |
| Need to define a skeleton algorithm with variable steps | Template Method | `docs/coding/design_patterns/dp_template_method_uml.md` |
| Need to treat individual objects and compositions uniformly | Composite | `docs/coding/design_patterns/dp_composite_uml.md` |
| Need to control access to an object | Proxy | `docs/coding/design_patterns/dp_proxy_uml.md` |
| Need to reduce coupling between components | Mediator | `docs/coding/design_patterns/dp_mediator_uml.md` |

### Anti-Patterns — Actively Avoid

- **God Object**: One class doing everything. Apply SRP.
- **Shotgun Surgery**: One change requires touching many files. Apply OCP + DIP.
- **Feature Envy**: A class constantly reaching into another's data. Move the behavior.
- **Refused Bequest**: Subclass inherits methods it can't fulfill. Redesign hierarchy (LSP).
- **Primitive Obsession**: Using raw dicts/tuples where a struct or named type would be clearer.

### Python-Specific Conventions

- **`typing.Protocol`** is the primary abstraction mechanism — prefer it over ABCs for structural typing of stages, sources, sinks, and backends.
- **`@dataclass(frozen=True, slots=True)`** for value types (`Frame`, `Detection`, `Track`, `Caption`). Avoid raw dicts crossing stage boundaries — primitive obsession.
- **Constructor injection** is the standard pattern — pass dependencies via `__init__`, not module-level globals or singletons.
- **No global mutable state.** Pipeline wiring lives in `lowlatcv.app.build_pipeline(cfg)`.
- **`asyncio`** for the orchestrator and I/O-bound stages. CPU-bound stages run in worker threads / processes via `loop.run_in_executor` so the event loop stays responsive.
- **Bounded queues** between stages (`asyncio.Queue(maxsize=2)` default) so back-pressure is visible — mirrors AXI-Stream `tready` on the FPGA target.
- **Type-annotate everything.** `mypy --strict` is the target. New code without annotations fails review.
- **`logging.getLogger(__name__)`** in every module. No `print` in library code.
- **Factory methods** as `classmethod` constructors: `Detector.from_config(cfg)`, `VLM.from_config(cfg)` build the right backend.
- **Configuration presets** as module-level constants on the config dataclass: `DetectorConfig.YOLOV8N_DEFAULT`, etc.
- **No heavy imports at module top level** in stages — gate `torch`, `coremltools`, `transformers` behind the stage that needs them, so `lowlatcv --help` stays snappy.

### Patterns Already in Use in This Project

| Pattern | Where Used |
|---------|-----------|
| **Pipeline (Pipes & Filters)** | Core architecture — bounded queues between independent stages, each a pure transform |
| **Producer-Consumer** | `FrameSource` → queue → `Detector` → queue → `Tracker` → … with back-pressure |
| **Strategy** | Detector / Tracker / VLM backends are swappable behind the `Stage` protocol — same interface, different model |
| **Observer** | `tracer` publishes per-span timings to subscribed reporters (CLI, JSON, Prometheus) |
| **Facade** | `Pipeline` in `runner.py` hides graph construction + lifecycle behind `start()` / `stop()` / `await_completion()` |
| **Command** | VLM jobs queued as `CaptionRequest` objects, processed off the per-frame critical path |
| **Factory Method** | `Detector.from_config(cfg)`, `VLM.from_config(cfg)` |
| **Adapter** | OpenCV / ffmpeg / CoreML wrappers adapt third-party APIs to the internal `Frame` / `Detection` types |
| **Dependency Injection** | All wiring in `lowlatcv.app.build_pipeline(cfg)` — manual constructor injection, no framework |

## Reference Documentation

For detailed explanations, UML diagrams, and code examples:

- **SOLID overview**: `docs/coding/design_patterns/solid_overview.md`
- **SOLID with UML**: `docs/coding/design_patterns/solid_with_uml.md`
- **Individual SOLID principles**: `docs/coding/design_patterns/solid_1_srp.md` through `solid_5_dip.md`
- **All patterns with UML**: `docs/coding/design_patterns/design_patterns_uml_examples.md`
- **Code examples**: `docs/coding/design_patterns/examples/` (C++ but patterns are language-agnostic)
- **Anti-patterns**: `docs/coding/design_patterns/examples/antipatterns.h`
