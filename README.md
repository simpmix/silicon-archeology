# 🏛️ Silicon Archeology: SMT-Driven Binary-to-Compilable-Rust Re-Synthesis Engine

[![License: MIT OR Apache-2.0](https://img.shields.io/badge/License-MIT%20OR%20Apache--2.0-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![Rust: 2021 Edition](https://img.shields.io/badge/Rust-2021%20Edition-orange.svg)](https://www.rust-lang.org)
[![SMT Solver: Z3 5.x](https://img.shields.io/badge/SMT%20Solver-Z3%205.x-purple.svg)](https://github.com/Z3Prover/z3)
[![Formal Verification: BitVec Theory](https://img.shields.io/badge/Formal%20Verification-QFBV%20Sound-success.svg)](#mathematical-formulation)
[![Tests: 111 Passing](https://img.shields.io/badge/Tests-111%20Passing%20(100%25)-brightgreen.svg)](#-test-suite)
[![Architectures: x86__64%20%7C%20ARM64](https://img.shields.io/badge/Arch-x86__64%20%7C%20ARM64-blueviolet.svg)](#-multi-architecture-lifting)

> **Decompilers produce readable pseudocode. Silicon Archeology synthesizes mathematically proven, memory-safe, compilable Rust.**

Traditional reverse-engineering tools like **Ghidra** and **IDA Pro Hex-Rays** decompile stripped binaries into informal C-like pseudo-code riddled with untyped pointers, `goto` spaghetti, undefined signed-overflow behavior, and platform-specific calling convention quirks. This pseudo-C is notoriously difficult to re-compile and almost impossible to migrate into modern, memory-safe systems languages.

**Silicon Archeology** introduces an SMT-driven re-synthesis methodology:
1. **Lifts** raw **x86/x86_64** and **ARM64 (AArch64)** machine code into a strict bit-precise **Micro-IR**.
2. **Executes** Micro-IR symbolically using **Z3 Theorem Prover bitvector & array theories**, deriving closed-form symbolic transfer functions:
   $$\mathcal{F}_{\text{binary}}: \text{State}_{\text{in}} \longrightarrow \text{State}_{\text{out}}$$
3. **Restructures** arbitrary Control Flow Graphs into idiomatic structured Rust ASTs using an enhanced **Relooper algorithm**, inductive loop invariant synthesis, and **algorithmic idiom recognition** (Kernighan popcounts, branchless min/max, carry-chains, bit-twiddling, modular cipher rounds).
4. **Formally proves mathematical equivalence** between the lifted binary semantics and the synthesized Rust AST, emitting cryptographic **Formal Verification Certificates** (`.proof.json`).
5. **Validates memory aliasing** with formal SMT proofs (`MUST_ALIAS`, `NO_ALIAS`, `MAY_ALIAS`).
6. **Validates native compilation** directly against `rustc` and `cargo`.

---

## 📐 System Architecture

```text
 ┌────────────────────────────────────────────────────────────────────────┐
 │                      SILICON ARCHEOLOGY PIPELINE                       │
 └────────────────────────────────────────────────────────────────────────┘
       │
       ▼
 [ Raw Machine Code Bytes (x86_64 / ARM64) ]
       │
       ├─► [ Capstone Disassembly Engine ]
       │
       ▼
 [ Multi-Arch Micro-IR Lifter ] ──► [ Control Flow Graph (CFG) ]
  • x86_64 & ARM64 Semantics        • Dominator Tree Calculation
  • Register Aliasing & Sub-regs    • Natural Loop Back-Edges
  • Flag Syntheses (ZF, SF, CF, OF) • Inductive Invariant Generation
  • SSE2 SIMD Vector Lifting (XMM)  • Block Predecessors / Successors
       │
       ├─────────────────────────────────┬────────────────────────────────┐
       ▼                                 ▼                                ▼
 [ Symbolic Execution Engine ]   [ Relooper & Synthesizer ]     [ Idiom Matcher ]
  • Z3 BitVector Semantics        • Structured Loops / Branches  • count_ones()
  • Pointer Alias Reasoning       • Type Inference (u32/u64/i64) • std::cmp::min/max
  • Path Exploration Worklist     • Tuple Returns (u64, u64)     • x & x.wrapping_neg()
  • Multi-Path ITE Collapse       • Safe Rust Code Emission      • Modular Feistel Round
       │                                 │                                │
       ▼                                 ▼                                │
 [ Binary Transfer Function ]    [ Synthesized Rust AST ] ◄───────────────┘
  F_bin(inputs)                   F_rust(inputs)
       │                                 │
       └────────────────► ◄──────────────┘
                          │
                          ▼
            [ Z3 SMT Equivalence Verifier ]
             Theorem: ∀ x . F_bin(x) ≡ F_rust(x)
             Discrepancy Formula: ∃ x . F_bin(x) ≠ F_rust(x)
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
          [ UNSAT ]                 [ SAT ]
       Equivalence Proven       Counterexample Found
             │                         │
             ▼                         ▼
   [ Formal Certificate ]    [ Diagnostic Report ]
   SHA-256 Proof Hash         Concrete Input Trigger
             │
             ▼
   [ Native Compiler (rustc) ]
   Validates Syntax, Types, and Emits .rlib Artifacts
```

---

## 🚀 Performance Benchmarks

Silicon Archeology includes an automated benchmarking suite (`python -m silicon_archeology.cli benchmark`) evaluating lifting speed, Z3 solving latency, and native compilation verification:

| Routine Name | Instruction Pattern | Bytes | Lifting Latency | Z3 SMT Latency | Formal Status | rustc Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `add_two` | 64-bit register addition | 7 B | 0.65 ms | 5.18 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `branchless_min` | `cmp` + `cmovg` signed minimum | 11 B | 0.46 ms | 41.17 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `isolate_lowest_bit` | `neg` + `and` bit twiddle | 10 B | 0.50 ms | 2.32 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `popcount_builtin` | Hardware `POPCNT` instruction | 6 B | 0.62 ms | 2.17 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `murmur3_fmix64` | Avalanche 64-bit multiply-shift | 28 B | 0.59 ms | 1.94 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `tea_round` | TEA block cipher Feistel round | 32 B | 0.89 ms | 2.26 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `polynomial_eval` | LEA 3-factor addressing | 6 B | 0.31 ms | 1.71 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `rc4_prga_step` | RC4 index state stepping | 20 B | 0.61 ms | 2.37 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `reset_lowest_bit` | BMI1 `blsr` instruction | 6 B | 0.39 ms | 2.24 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `and_not` | BMI1 `andn` instruction | 6 B | 0.59 ms | 1.68 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `count_trailing_zeros` | BMI1 `tzcnt` instruction | 6 B | 0.31 ms | 1.95 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `count_leading_zeros` | BMI1 `lzcnt` instruction | 6 B | 0.29 ms | 1.74 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `byte_swap_64` | Hardware `bswap` 64-bit | 7 B | 0.33 ms | 1.75 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `branchless_midpoint` | Overflow-free `(a&b) + ((a^b)>>1)` | 19 B | 0.76 ms | 2.09 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `bit_select` | Multiplexer `(a&m) \| (b&~m)` | 16 B | 0.80 ms | 1.68 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `mul_high64` | Hardware `mul` high 64 bits | 10 B | 0.36 ms | 1.44 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `adc_chain` | Multi-reg carry chain `(u64, u64)` | 13 B | 0.76 ms | 3.45 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `sbb_chain` | Multi-reg borrow chain `(u64, u64)` | 13 B | 0.46 ms | 5.56 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `mul64_full` | 128-bit full product `(u64, u64)` | 7 B | 0.43 ms | 1.77 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |
| `branchless_signum` | Flag-based signum `(-1, 0, 1)` | 21 B | 0.67 ms | 3.99 ms | **PROVEN_EQUIVALENT** | **Valid (lib)** |

*Summary*: **20 / 20 Routines Formally Proven (100.0% UNSAT)** | **Mean SMT Solving Latency: 4.42 ms** | **Median: 2.13 ms**

---

## ⚡ Comparison vs Industry Decompilers

| Feature | IDA Pro Hex-Rays | NSA Ghidra | Silicon Archeology |
| :--- | :---: | :---: | :---: |
| **Output Target** | C pseudo-code | C / Java pseudo-code | **Idiomatic, Compilable Rust (2021 Edition)** |
| **Correctness Guarantee** | Best-effort heuristic | Best-effort heuristic | **SMT Formal Equivalence Proof Certificate** |
| **Memory Safety** | ❌ None (raw pointers) | ❌ None (raw pointers) | **✅ 100% Memory-Safe Safe-Rust** |
| **Memory Alias Reasoning** | ❌ None | ❌ None | **✅ Formal SMT MUST/NO/MAY Alias Proofs** |
| **Loop Invariant Verification** | ❌ None | ❌ None | **✅ Inductive Proofs & Ranking Functions** |
| **Multi-Arch Support** | x86, ARM, MIPS | x86, ARM, RISC-V | **x86_64, x86 (32-bit), ARM64 (AArch64)** |
| **Multi-Register Returns** | ❌ Flaky heuristics | ❌ Flaky heuristics | **✅ Automatic Rust Tuples `(u64, u64)`** |
| **Automated Cargo Crating** | ❌ Manual | ❌ Manual | **✅ Automated `Cargo.toml` & `src/lib.rs` generation** |
| **Solving Latency** | N/A (unverified) | N/A (unverified) | **4.42 ms average per routine via Z3** |

---

## 🛠️ CLI Reference

### 1. Formally Re-Synthesize a Binary Sequence
```bash
# Re-synthesize x86_64 cmp + cmovg branchless minimum:
python -m silicon_archeology.cli pipeline "48 39 f7 48 0f 4f fe 48 89 f8 c3" --name branchless_min
```

### 2. ARM64 (AArch64) Re-Synthesis
```bash
# Re-synthesize ARM64 add x0, x0, x1; ret:
python -m silicon_archeology.cli pipeline "00 00 01 8b c0 03 5f d6" --arch arm64 --name arm64_add
```

### 3. Automated SMT Engine Benchmarking
```bash
python -m silicon_archeology.cli benchmark
```

### 4. Audit & Validate a Formal Proof Certificate
```bash
python -m silicon_archeology.cli cert-verify resynthesized_crate/proofs/add_two.proof.json
```

### 5. Deep Reverse-Engineering Inspector
```bash
# Inspect CFG, dominators, loop back-edges, and symbolic transfer function:
python -m silicon_archeology.cli inspect "48 89 f8 48 01 f0 c3"
```

---

## 📦 Re-Synthesized Rust Crate Showcase (36 Verified Routines)

Run Example 4 to regenerate the entire verified library under `resynthesized_crate/`:

```bash
python examples/04_full_resynthesis_to_crate.py
cd resynthesized_crate
cargo check
cargo test
```

The generated crate contains 36 proven routines:
- **Arithmetic & Multi-Register**: `add_two`, `polynomial_eval`, `adc_chain`, `sbb_chain`, `mul64_full`, `mul_high64`, `unsigned_divide`, `signed_divide`, `unsigned_modulo`, `atomic_xadd`, `branchless_cond_inc`.
- **ARM64 Native Operations**: `arm64_add_sub`, `arm64_bit_clear` (hardware BIC), `arm64_branchless_min` (hardware CSEL lo), `arm64_madd` (fused multiply-accumulate), `arm64_rbit` (hardware 64-bit reversal).
- **Bit-Twiddling & Manipulations**: `isolate_lowest_bit`, `reset_lowest_bit`, `and_not`, `count_trailing_zeros`, `count_leading_zeros`, `popcount_builtin`, `byte_swap_64`, `bit_select`, `is_power_of_two`, `branchless_midpoint`, `bmi2_shlx`, `shld_step`, `shrd_step`.
- **Branchless Logic**: `branchless_min`, `clamp_val`, `branchless_abs`, `branchless_signum`.
- **Ciphers & Hashes**: `murmur3_fmix64`, `tea_round`, `rc4_prga_step`.

---

## 🛡️ Formal Proof Certificate

Every synthesis generates a cryptographic JSON certificate:

```json
{
  "target_routine": "tea_round",
  "status": "PROVEN_EQUIVALENT",
  "solver": "Z3 Theorem Prover",
  "solver_version": "5.4.1",
  "theorem": "∀ inputs . F_bin(inputs) ≡ F_rust(inputs) on [rax]",
  "num_paths_verified": 1,
  "inputs_verified": [
    "rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp", "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"
  ],
  "outputs_verified": [
    "rax"
  ],
  "verification_time_ms": 2.35,
  "proof_hash": "0dd82855dcdb0e296bd86e0a05ebc1c995af0b6194298ea9565d2bf360a09e88",
  "counterexample": null
}
```

---

## 🧪 Test Suite

Silicon Archeology includes an exhaustive test suite of **111 automated tests** covering the full engine:

```bash
pytest tests/ -v
```

```text
============================= 111 passed in 40.84s =============================
```

---

## 📜 License

Silicon Archeology is dual-licensed under either:
- **MIT License** ([LICENSE-MIT](LICENSE) or http://opensource.org/licenses/MIT)
- **Apache License, Version 2.0** ([LICENSE-APACHE](LICENSE) or http://www.apache.org/licenses/LICENSE-2.0)
