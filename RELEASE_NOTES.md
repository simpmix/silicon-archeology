# 🚀 Release Notes: Silicon Archeology v0.2.1

We are proud to announce the release of **Silicon Archeology v0.2.1** — an aggressively hardened, polished, and expanded SMT-driven binary-to-compilable-Rust re-synthesis engine.

---

## 🌟 Highlights & New Features in v0.2.1

### 1. Critical Bug Fixes & Lifter Soundness
- **Division Modulo Correctness**: Fixed a fatal bug in the x86 lifter where sequential assignments `Assign(rax, quotient)` and `Assign(rdx, remainder)` caused `rdx` to compute `quotient % divisor` instead of `dividend % divisor`. Introduced SSA temporaries (`_div_q`, `_div_r`, `_idiv_q`, `_idiv_r`) to guarantee mathematically sound, independent evaluation of quotient and remainder.
- **Signed Modulo SMT Precision**: Fixed `Op.REM` in `SymbolicExecutor` which previously mapped to Z3's Euclidean modulo `bvsmod` (`left % right`); corrected to true truncated signed remainder `z3.SRem(left, right)` matching C/Rust/x86 `idiv` hardware semantics.
- **Signedness Propagation**: Enhanced `TypeInference` with a multi-pass fixed-point propagation algorithm ensuring signed types (`i64`/`i32`) flow backwards across register copy assignments (e.g. `mov rax, rdi` followed by `idiv rsi` correctly marks `rdi` as `i64`).
- **Negative Integer Literal Compilation**: Fixed `RustLiteral` and `Constant` emitting overflowing positive hex literals for signed types; signed literals now emit valid Rust expressions (e.g. `-1` and `-42i64`) without triggering `deny(overflowing_literals)` errors.
- **Test Harness Literal Formatting**: Fixed `_compile_and_test` in `ReSynthesisPipeline` dynamically inspecting AST parameter and return types to format test arguments accurately for signed functions (`-7i64`).

### 2. Expanded x86/x86_64 Instruction Coverage & Hardware Semantics
- **BMI2 Non-Flag Shift Instructions**: Added `shlx`, `shrx`, `sarx` (dynamic and register shifts without affecting EFLAGS).
- **Atomic Exchanges & Compare-and-Swap**:
  - `xadd` (exchange and add) with full flag updates.
  - `cmpxchg` (compare and exchange / CAS).
- **Double-Precision Shifts**:
  - `shld` (shift left double precision).
  - `shrd` (shift right double precision).
- **BMI1 & BMI2 Instructions**:
  - `blsr` (reset lowest set bit: `(x - 1) & x`)
  - `blsi` (isolate lowest set bit: `(-x) & x`)
  - `blsmsk` (mask up to lowest set bit: `(x - 1) ^ x`)
  - `bzhi` (zero high bits starting at specified bit index)
  - `andn` (bitwise AND NOT: `(!a) & b`)
  - `bextr` (bitfield extract with dynamic start & length control word)
- **Sign Extension Family**: `cqo`, `cdq`, `cdqe`, `cbw`, `cwde`, `cwd`.

### 3. Expanded Idiom Recognition
- Added automated matchers for:
  - `match_branchless_abs`: Matches `cqo / cdq; xor rax, rdx; sub rax, rdx` -> `x.wrapping_abs()`.
  - `match_reset_lowest_set_bit` (`blsr`)
  - `match_and_not` (`andn`)
  - `match_count_trailing_zeros` (`tzcnt` / `bsf`)
  - `match_count_leading_zeros` (`lzcnt` / `bsr`)
  - `match_byte_swap` (`bswap` / `.swap_bytes()`)
  - `match_clamp` (`val.clamp(min, max)`)
  - Hardened `match_gcd` against false positive loop captures.

### 4. Expanded Verification & Standalone Crate
- `tests/`: Test suite expanded from 54 to **67 tests** with a 100% pass rate.
- `resynthesized_crate/`: Expanded from 15 to **22 verified routines** with complete formal SMT certificates (`.proof.json`) and summary manifest.
- Verified to pass both `cargo check` and `cargo check --tests` cleanly in 0.31s.

---

## 📦 What's Included

- `silicon_archeology/`: Core re-synthesis framework (`ir/`, `lifter/`, `symbolic/`, `synthesizer/`, `verifier/`, `cli.py`, `pipeline.py`).
- `tests/`: 67 automated unit and integration tests with 100% pass rate.
- `examples/`:
  - `01_branchless_algorithms.py`: Branchless min/max, popcount, bit-twiddling.
  - `02_murmur_hash_round.py`: 64-bit Murmur3 avalanche mixer.
  - `03_tea_cipher_block.py`: 32-bit TEA cipher Feistel round.
  - `04_full_resynthesis_to_crate.py`: End-to-end multi-routine batch synthesizer (22 verified routines).
- `resynthesized_crate/`: Generated Rust crate with 22 verified routines and proof certificates.

---

## 🔮 Roadmap
- Support for ARM64 (AArch64) disassembly and lifting.
- SIMD / AVX-512 vector instruction re-synthesis into `std::simd` (portable SIMD).
- Automatic loop invariant generation using Craig interpolation in Z3.
- Interactive Ghidra and IDA Pro plugins.
