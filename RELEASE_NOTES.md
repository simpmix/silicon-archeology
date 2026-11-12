# 🚀 Release Notes: Silicon Archeology v0.2.0

We are proud to announce the release of **Silicon Archeology v0.2.0** — an aggressively hardened, polished, and expanded SMT-driven binary-to-compilable-Rust re-synthesis engine.

---

## 🌟 Highlights & New Features in v0.2.0

### 1. Expanded x86/x86_64 Instruction Coverage & Hardware Semantics
- **BMI1 & BMI2 Instructions**: Full lifting, symbolic transfer, and synthesis for:
  - `blsr` (reset lowest set bit: `(x - 1) & x`)
  - `blsi` (isolate lowest set bit: `(-x) & x`)
  - `blsmsk` (mask up to lowest set bit: `(x - 1) ^ x`)
  - `bzhi` (zero high bits starting at specified bit index)
  - `andn` (bitwise AND NOT: `(!a) & b`)
  - `bextr` (bitfield extract with dynamic start & length control word)
- **Bit Counting & Scans**:
  - `tzcnt` / `bsf` -> `val.trailing_zeros() as u64`
  - `lzcnt` / `bsr` -> `val.leading_zeros() as u64`
  - `bt`, `bts`, `btr`, `btc` (bit test, test-and-set, test-and-reset, test-and-complement)
- **Endian Byte Manipulation**:
  - `bswap` lifted via dedicated `Op.BSWAP` and synthesized into idiomatic `val.swap_bytes()`
- **Sign Extension Instructions**:
  - `cqo` (sign-extend RAX to RDX:RAX)
  - `cdq` (sign-extend EAX to EDX:EAX)
  - `cdqe` (sign-extend EAX to 64-bit RAX)
  - `cbw`, `cwde`, `cwd`
- **Integer Division & Modulo**:
  - Full mathematical modeling of `div` and `idiv` (both 64-bit and 32-bit quotient & remainder)
- **Conditional Set (SETcc)**:
  - Universal predicate synthesis for `sete`, `setne`, `setl`, `setle`, `setg`, `setge`, `setb`, `setbe`, `seta`, `setae`, `sets`, `setns`
- **Register Exchanges**:
  - `xchg` with safe SSA temporary assignment
- **Complex Memory Displacements & RIP-Relative Addressing**:
  - Clean `(base + idx*scale - disp)` synthesis preventing unsigned overflow panics
  - Exact concrete address calculation for PC-relative `[rip + disp]` references

### 2. Synthesizer & Relooper Hardening
- **Zeroing Idiom Recognition**: `xor reg, reg` and `sub reg, reg` (in both 64-bit and 32-bit zero-extended forms) are recognized as register-clearing writes rather than reads, eliminating spurious parameter generation.
- **64-bit Shift Overflow Prevention**: Safe `u128` widening on chained concatenations avoiding rustc `attempt to shift left by 64_i32` compile errors.
- **Preconditioned Equivalence Certification**: Precondition solver support for bounded primitives like `val.clamp(min, max)` (`min <= max`).
- **Bounded Loop Unrolling**: Symbolic interpreter in pipeline unrolls `RustWhile` loops up to configurable bound (8 iterations).

### 3. Expanded Idiom Recognition
- Added automated matchers for:
  - `match_reset_lowest_set_bit` (`blsr`)
  - `match_and_not` (`andn`)
  - `match_count_trailing_zeros` (`tzcnt` / `bsf`)
  - `match_count_leading_zeros` (`lzcnt` / `bsr`)
  - `match_byte_swap` (`bswap` / `.swap_bytes()`)
  - `match_clamp` (`val.clamp(min, max)`)

### 4. Expanded Verification & Standalone Crate
- `tests/`: Test suite expanded from 33 to **54 tests** with a 100% pass rate.
- `resynthesized_crate/`: Expanded from 8 to **15 verified routines** with complete formal SMT certificates (`.proof.json`) and summary manifest.
- Verified to pass both `cargo check` and `cargo check --tests` cleanly in 0.31s.

---

## 📦 What's Included

- `silicon_archeology/`: Core re-synthesis framework (`ir/`, `lifter/`, `symbolic/`, `synthesizer/`, `verifier/`, `cli.py`, `pipeline.py`).
- `tests/`: 54 automated unit and integration tests with 100% pass rate.
- `examples/`:
  - `01_branchless_algorithms.py`: Branchless min/max, popcount, bit-twiddling.
  - `02_murmur_hash_round.py`: 64-bit Murmur3 avalanche mixer.
  - `03_tea_cipher_block.py`: 32-bit TEA cipher Feistel round.
  - `04_full_resynthesis_to_crate.py`: End-to-end multi-routine batch synthesizer (15 verified routines).
- `resynthesized_crate/`: Generated Rust crate with 15 verified routines and proof certificates.

---

## 🔮 Roadmap
- Support for ARM64 (AArch64) disassembly and lifting.
- SIMD / AVX-512 vector instruction re-synthesis into `std::simd` (portable SIMD).
- Automatic loop invariant generation using Craig interpolation in Z3.
- Interactive Ghidra and IDA Pro plugins.
