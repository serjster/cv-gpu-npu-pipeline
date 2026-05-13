# Data-Oriented Design (DOD)

Data-Oriented Design organizes code around how data flows through the system rather than around object hierarchies. Where OOP asks "what things are," DOD asks "what transformations happen to what data."

DOD and OOP are not mutually exclusive. Use OOP for module boundaries, dependency injection, and API surfaces. Use DOD for the data layout and processing within those modules.

## Core Principles

### 1. Data and Logic Are Separate Concerns

Data structures hold state. Functions transform state. They live in different places.

```
// OOP-only: behavior and data fused
class Detector {
    pixels: Vec<u8>,
    width: usize,
    height: usize,
    edges: Vec<f32>,
    tiles: Vec<Tile>,
    fn detect(&mut self) { ... }
}

// DOD: data is plain, functions are standalone transformations
struct ScreenBuffer { pixels: Vec<u8>, width: usize, height: usize }
struct EdgeMap { edges: Vec<f32>, width: usize, height: usize }
struct TileGrid { tiles: Vec<Tile>, rows: usize, cols: usize }

fn compute_edges(input: &ScreenBuffer) -> EdgeMap { ... }
fn merge_tiles(edges: &EdgeMap, params: &TileParams) -> TileGrid { ... }
fn filter_regions(grid: &TileGrid, params: &FilterParams) -> Vec<DetectedElement> { ... }
```

**Why:** Each function is independently testable, composable, and replaceable. The data flows through a pipeline rather than being trapped inside an object.

### 2. Prefer Flat, Contiguous Data

Arrays of structs (AoS) vs structs of arrays (SoA) — choose based on access pattern.

```
// AoS: good when you access all fields of one item together
struct Hint { x: f32, y: f32, label: String, display_id: u32 }
hints: Vec<Hint>

// SoA: good when you process one field across all items (SIMD-friendly)
struct HintBatch {
    xs: Vec<f32>,
    ys: Vec<f32>,
    labels: Vec<String>,
    display_ids: Vec<u32>,
}
```

**Guideline:** Start with AoS (simpler). Switch to SoA only when profiling shows a hot loop that processes a single field across many items (e.g., computing distances between all hint positions).

### 3. Design Data for the Transform, Not the Domain

Don't model the "real world." Model what the code actually does with the data.

```
// Domain-modeled (mirrors the "real world"):
struct Display { id: u32, outputs: Vec<Output>, monitors: Vec<Monitor> }
struct Output { surfaces: Vec<Surface>, mode: Mode }

// Transform-modeled (mirrors what the code does):
struct CaptureTarget { output_id: u32, width: u32, height: u32, scale: f32 }
struct DamageRegion { x: u32, y: u32, w: u32, h: u32 }
```

The first models a display hierarchy. The second models exactly the data needed to capture a frame. No more, no less.

### 4. Make Data Flow Explicit

Data should flow through the system in one direction. Each stage receives input and produces output. No hidden state, no spooky action at a distance.

```
capture → grayscale → blur → edges → tiles → merge → filter → label → render
   ↓          ↓         ↓       ↓        ↓        ↓        ↓       ↓       ↓
ScreenBuf  GrayBuf  BlurBuf  EdgeMap  TileGrid  Regions  Elements  Hints  PixelBuf
```

Each arrow is a pure function. Each box is a plain data structure. The pipeline is composable — you can skip stages, add stages, or replace stages without touching the others.

### 5. Batch Over Individual

Process collections, not individual items. This enables SIMD, parallelism, and better cache utilization.

```
// Individual: one at a time, cache-hostile
for hint in &hints {
    render_single_hint(hint, &mut buffer);
}

// Batch: all at once, can use SIMD/parallel
render_hint_batch(&hints, &mut buffer);

// Even better: separate the hot data
let positions: Vec<(f32, f32)> = hints.iter().map(|h| (h.x, h.y)).collect();
let screen_coords = convert_coordinates_batch(&positions, &display_info);
```

### 6. Minimize Indirection

Pointers, trait objects, and reference chains cause cache misses. Prefer IDs and indices over references for large collections.

```
// Indirection-heavy:
struct Hint { display: &Display, point: &DetectedElement }

// ID-based (flat, serializable, cache-friendly):
struct Hint { display_id: u32, element_index: usize, x: f32, y: f32, label: String }
```

Use trait objects (`dyn Trait`) at module boundaries for dependency injection. Use concrete types and IDs within hot paths.

## When to Apply DOD vs OOP

| Context | Approach |
|---------|----------|
| Module boundaries, public APIs | OOP (traits, dependency injection) |
| Configuration, UI state | OOP (structs with methods) |
| Detection pipeline inner loop | DOD (plain data + free functions) |
| Processing collections of items | DOD (batch transforms, SoA if needed) |
| Rendering hint labels | DOD (batch render into pixel buffer) |
| Coordinator state machine | OOP (state pattern or enum-based FSM) |
| System integration (capture, input, tray) | OOP (trait abstractions for platform swap) |

## DOD Checklist

Before writing a data-intensive module:

- [ ] What is the input data shape? What is the output?
- [ ] What transforms happen between input and output?
- [ ] Can each transform be a standalone function?
- [ ] Is the data laid out for the access pattern? (AoS vs SoA)
- [ ] Are collections processed in batch, not individually?
- [ ] Is the data flow unidirectional and explicit?
- [ ] Are hot-path data structures flat with minimal indirection?

## Relationship to SOLID

DOD complements SOLID:

- **SRP**: Each transform function has a single responsibility by definition.
- **OCP**: New pipeline stages are added without modifying existing ones.
- **DIP**: Module boundaries use trait abstractions; data flows through them.
- **ISP**: Data structs contain only the fields their consumer needs.

The key difference: SOLID organizes abstractions. DOD organizes data. Both are needed.

## Further Reading

- **Data-Oriented Design** by Richard Fabian (dataorienteddesign.com)
- **Mike Acton's CppCon 2014 talk**: "Data-Oriented Design and C++"
- **Catherine West's RustConf 2018 talk**: "Using Rust for Game Development" (ECS architecture)
- **Andrew Kelley's "Practical DOD"**: Applying DOD principles in systems programming
