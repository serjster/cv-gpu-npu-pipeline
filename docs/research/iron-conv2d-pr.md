# IRON Conv2D operator — PR progress tracker

**Goal:** upstream a `Conv2D` operator to AMD's IRON repo
(`github.com/amd/IRON`). IRON's operator library has gemm, gemv, mha,
norms, activations — **no convolution at all**. This closes that gap and
gets convolution working on AIE2P / Strix Halo through IRON.

This doc tracks the PR specifically. For the wider "run YOLO on the NPU"
objective see `npu-yolo-roadmap.md`; for the full investigation log see
`amd-xdna-npu-context.md`.

---

## Where the work lives

- **IRON checkout:** `~/.local/share/iron-work/iron`
- **Branch:** `conv2d-operator` (off `devel`, which is 0 behind
  `origin/devel` and pins `mlir_aie==0.0.1.2026033104+e4f35d6` — exactly
  the wheel in the iron-venv).
- **PR target branch:** `devel` (per `CONTRIBUTING.md`).
- **Operator files:** `iron/operators/conv2d/{op,design,reference,test}.py`
  plus a one-line registration in `iron/operators/__init__.py`.

### Build / test environment

```bash
IRON_VENV=~/.local/share/iron-venv          # python 3.12
XRT=~/.local/share/xilinx-xrt/opt/xilinx/xrt
SP="$IRON_VENV/lib/python3.12/site-packages"
export PEANO_INSTALL_DIR="$SP/llvm-aie"
export MLIR_AIE_DIR="$SP/mlir_aie"
export PATH="$IRON_VENV/bin:$XRT/bin:$PATH"
export LD_LIBRARY_PATH="$XRT/lib:${LD_LIBRARY_PATH:-}"
export XILINX_XRT="$XRT"
export PYTHONPATH="$XRT/python:${PYTHONPATH:-}"
cd ~/.local/share/iron-work/iron

python3 -m pytest iron/operators/conv2d/test.py -q -p no:cacheprovider
$IRON_VENV/bin/black --check iron/operators/conv2d/
$IRON_VENV/bin/reuse lint
```

---

## Status

| Task | State |
|------|-------|
| #29 Study IRON operator base class + test harness | ✅ done |
| #30 Create `conv2d-operator` branch | ✅ done |
| #31 Build Conv2D 1×1 operator | ✅ done |
| #32 Compile + run 1×1 on the NPU, verify | ✅ done |
| #33 Write test.py + pass black / reuse lint | ✅ done |
| #34 Extend to general K×K (im2col) | ✅ done |
| #36 On-NPU im2col as a DMA access pattern | IN PROGRESS — **design decision pending, see below** |
| #35 Open DRAFT PR to IRON `devel` | ⛔ blocked by #36 (user wants on-NPU im2col first) + needs the user's fork |

### Done — committed on `conv2d-operator`

Three commits:
1. `Add Conv2D operator (1x1 convolution)`
2. `Add Conv2D 1x1 test suite`
3. `Extend Conv2D to general KxK convolutions`

**What works today:** `Conv2D(MLIROperator)` — NHWC input / OIYX weight /
NHWC output, general `kernel_size` / `stride` / `padding` (square
kernels, equal stride+padding per axis). The convolution is **im2col +
GEMM**: `Conv2D.im2col()` and `Conv2D.flatten_weight()` are host-side
prep helpers (mirroring how the GEMM operator expects its caller to
prepare B), and `conv2d_design` delegates to GEMM's `my_matmul` — so the
NPU side is purely the matmul on the existing AIE2P `aie2p/mm.cc` kernel.
1×1 conv is the degenerate case where im2col is a reshape.

**Verified:** 50 parametrized pytest cases (1×1 channel projections, 3×3
same-padding, 3×3 strided/downsampling; 2- and 8-column; batch 1 and 2)
all compile through the standard xclbin path and verify on the NPU
against the `torch.nn.functional.conv2d` golden reference within rel/abs
tol 0.01. `black` and `reuse lint` both pass (the CONTRIBUTING.md CI
gates).

This rides GEMM's existing AIE2P path, so it sidesteps every blocker
from the fused-chain investigation — no full-ELF, no compiler bug.

---

## In progress — #36, on-NPU im2col

The user asked for on-NPU im2col **before** opening the PR: replace the
host-side im2col copy with a DMA gather, so the NPU reads the NHWC input
directly.

### Design findings so far

**The full im2col gather is a clean 6D affine DMA access pattern** over
the NHWC input:

- sizes:   `[batch, out_H, out_W, C_in, kH, kW]`
- strides: `[Hp·Wp·C_in, stride·Wp·C_in, stride·C_in, 1, Wp·C_in, C_in]`
  (`Hp`, `Wp` = padded input height/width)

The dest order in the `(M, K)` im2col matrix is `(b, oy, ox)` then
`(c_in, kh, kw)` — exactly this loop nest. Overlapping reads (each input
element read up to `ks²` times) are fine; a TAP is just an affine index
generator.

**Insertion point:** GEMM's runtime A path is
`rt.fill(A_l3l2_fifos[col].prod(), A, tap=A_tiles[tile_offset], ...)` in
`gemm/design.py` (~line 716). `A_tiles` is a *list* of
`(mem_tile_m_A, k)` tile TAPs over a flat `(M, K)` buffer. To do on-NPU
im2col we make `A` the NHWC input buffer and make each `A_tiles[i]` an
im2col TAP into it. The L2 / L1 / compute side is **untouched** — it
still sees `(M, K)` tiles, just gathered from a smaller buffer.

### Open complications (the reason #36 isn't trivial)

1. **Per-tile slicing.** Slicing the 6D pattern per `(mem_tile_m_A, k)`
   tile is only clean if tiles align to conv structure: k-tiles on `ks²`
   multiples, m-tiles on `out_W` row boundaries.
2. **DMA dimension limit.** AIE2P DMA descriptors are 3D/4D; a 6D
   pattern must be split — some dims in the descriptor, the rest as a
   runtime loop of `rt.fill` calls. Same territory as the earlier
   3D/4D-pad work (see `amd-xdna-npu-context.md`).
3. **Padding breaks the flattened-M affine collapse.** With `pad > 0`,
   `Wp ≠ out_W`, so `(oy, ox)` can't collapse into a single affine `m`
   stride — tiles must be row-aligned and a host **border-pad** is still
   needed (cheap: O(input), not O(ks²·input)).

### DECISION PENDING — resume here

Two questions were put to the user and **not yet answered** (the
question prompt was interrupted):

**Q1 — scope of the first on-NPU im2col cut:**
- (a) No-padding first — cleanest affine case, fully on-NPU gather;
  padding stays host border-pad as a follow-up. Fastest to a working PR.
- (b) Full incl. padding — host border-pad + affine TAP on the padded
  buffer, from the start.
- (c) Investigate taplib / AIE2P DMA-dim limits first, then decide scope
  from facts.

**Q2 — how much of `my_matmul` to fork:**
- (a) Parameterize `my_matmul` with an optional A-access-pattern hook —
  minimal duplication, but touches shared GEMM code (reviewers may push
  back).
- (b) Fork the array-build into `conv2d/design.py`, swap only the A path
  — no risk to GEMM, ~780 lines duplicated.
- (c) Decide after the spike.

**Recommended starting point:** Q1→(c) then (a); Q2→(c) then (a). I.e.
spike the taplib/DMA-dim limits, implement no-padding on-NPU im2col
first, prefer parameterizing `my_matmul` over forking. But this is the
user's call — resume by getting Q1/Q2 answered.

---

## Remaining for the PR (#35)

- Finish #36 (on-NPU im2col).
- The user **has a GitHub fork already** — need the fork's remote
  URL/name to push `conv2d-operator` to it.
- Open a `DRAFT:`-prefixed PR to `devel` using IRON's PR template
  (Summary / Added / Changed / Removed). Reference any related issue.
- Opening the PR is a visible action on AMD's public repo — get explicit
  user go-ahead before pushing / creating it.

### Possible follow-ups to mention in the PR description

- im2col as an on-NPU DMA access pattern (this *is* #36 — may land in
  the same PR or as a follow-up depending on Q1).
- `dilation`, grouped conv, non-square kernels.
