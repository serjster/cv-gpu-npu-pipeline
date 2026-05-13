# Data-Oriented Design

When writing data-intensive or performance-sensitive code, apply DOD principles alongside OOP/SOLID. See `docs/coding/data_oriented_design.md` for full reference.

## Rules

1. **Separate data from logic.** Data structures are plain (no behavior). Functions transform data. No god-objects that mix state, I/O, and computation.

2. **Design data for the transform, not the domain.** Each struct contains exactly the fields its consumers need. Don't model hierarchies that mirror the "real world" — model what the code actually does.

3. **Make data flow explicit.** Processing pipelines should be a chain of `input → transform → output`. Each stage is a pure function where possible. No hidden mutation or shared mutable state between stages.

4. **Batch over individual.** Process collections as a whole, not one item at a time. This enables SIMD, parallelism, and cache-friendly access patterns.

5. **Minimize indirection on hot paths.** Use IDs/indices instead of references for large collections. Use concrete types in inner loops — reserve Protocol dispatch for module boundaries.

6. **Start with AoS, switch to SoA when profiling demands it.** Don't prematurely optimize data layout. Array-of-structs is simpler and usually sufficient.

## Where DOD Applies in lowlatcv

- Frame pipeline: numpy array views → bounded queues → stage transforms → output
- Detection: image tensors → preprocess → model forward → NMS → `Detection` dataclasses
- Tracking: detections → Kalman predict/update → assignment → `Track` dataclasses
- Latency tracing: per-stage span timing → aggregated percentile report

## Where OOP Applies Instead

- Module boundaries: Protocol for `Stage`, `FrameSource`, `FrameSink`
- Orchestrator: `Pipeline` class wiring stages and queues
- Configuration: dataclasses with factory presets (`DetectorConfig.YOLOV8N_DEFAULT`)
- Backend integration: platform-specific adapters behind Protocol interfaces