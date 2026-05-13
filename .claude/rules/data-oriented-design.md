# Data-Oriented Design

When writing data-intensive or performance-sensitive code, apply DOD principles alongside OOP/SOLID. See `docs/coding/data_oriented_design.md` for full reference.

## Rules

1. **Separate data from logic.** Data structures are plain (no behavior). Functions transform data. No god-objects that mix state, I/O, and computation.

2. **Design data for the transform, not the domain.** Each struct contains exactly the fields its consumers need. Don't model hierarchies that mirror the "real world" — model what the code actually does.

3. **Make data flow explicit.** Processing pipelines should be a chain of `input → transform → output`. Each stage is a pure function where possible. No hidden mutation or shared mutable state between stages.

4. **Batch over individual.** Process collections as a whole, not one item at a time. This enables SIMD, parallelism, and cache-friendly access patterns.

5. **Minimize indirection on hot paths.** Use IDs/indices instead of references for large collections. Use concrete types in inner loops — reserve trait objects (`dyn Trait`) for module boundaries.

6. **Start with AoS, switch to SoA when profiling demands it.** Don't prematurely optimize data layout. Array-of-structs is simpler and usually sufficient.

## Where DOD Applies in KayZeer

- Detection pipeline: pixel buffers → edge maps → tile grids → detected elements
- Label assignment: element positions → spatial scoring → label strings
- Overlay rendering: hint data → batch render to pixel buffer
- Damage tracking: damage rects → tile overlap calculation → incremental re-detection

## Where OOP Applies Instead

- Module boundaries: traits for `ScreenCapturing`, `EventPosting`, `OverlayPresenting`
- Coordinator: state machine with enum-based states
- Configuration: structs with validation methods
- System integration: platform-specific implementations behind trait abstractions