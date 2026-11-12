# Show HN: Silicon Archeology – SMT-Driven Binary-to-Compilable-Rust Re-Synthesis

**Link**: https://github.com/simpmix/silicon-archeology

Hey HN!

Over the past decade, decompilers like Ghidra and IDA Pro Hex-Rays have made immense strides in turning stripped binaries into human-readable pseudo-C. But if you have ever tried to take that pseudo-code and actually recompile it, let alone migrate it into a memory-safe language like Rust, you immediately hit a wall:

1. **Goto spaghetti and fake control-flow loops** that fail the borrow checker.
2. **Implicit undefined behavior**: signed integer overflows, undefined shifts, unaligned pointer arithmetic.
3. **Zero correctness guarantees**: a decompiler is a collection of heuristic AST rewriters; there is no proof that the decompiled code computes the same mathematical function as the binary.

We built **Silicon Archeology** to approach reverse engineering from a completely different direction: **SMT-driven formal re-synthesis**.

### How it works

Instead of heuristic AST transformations, Silicon Archeology:
1. **Lifts** machine instructions (x86 / x86_64) into a clean, bit-precise Micro-IR with explicit x86 flag synthesis (ZF, SF, CF, OF) and exact hardware sub-register zero-extension semantics.
2. **Computes symbolic transfer functions** using the Z3 Theorem Prover (`QF_BV` BitVector and Array theories), deriving closed-form input-to-output relations across all reachable paths.
3. **Re-synthesizes structured Rust ASTs** using an enhanced Relooper CFG structuring engine and algorithmic idiom recognition (`count_ones()`, `rotate_left()`, `wrapping_neg()`, `std::cmp::min/max`).
4. **Formally proves mathematical equivalence**: It asks Z3 whether there exists *any* 64-bit input valuation where the synthesized Rust code produces a different output from the binary:
   $$\exists \vec{x} \text{ s.t. } \mathcal{F}_{\text{binary}}(\vec{x}) \neq \mathcal{F}_{\text{rust}}(\vec{x})$$
   When Z3 answers **UNSAT**, it generates a cryptographic proof certificate (`.proof.json`). If it answers **SAT**, it gives you the exact counterexample input that broke equivalence.
5. **Generates a standalone, compilable Rust crate** (`Cargo.toml` + `src/lib.rs`) and compiles it natively with `rustc` / `cargo check`.

### Example: Branchless Minimum

Raw bytes: `48 39 f7 48 0f 4f fe 48 89 f8 c3` (x86_64 `cmp rdi, rsi; cmovg rdi, rsi; mov rax, rdi; ret`)

Conventional decompiler output:
```c
__int64 f(__int64 a1, __int64 a2) {
  __int64 v2;
  v2 = a1;
  if (a1 > a2) v2 = a2;
  return v2;
}
```

Silicon Archeology output:
```rust
/// Computes minimum of two numbers via signed conditional move.
pub fn branchless_min(a: i64, b: i64) -> i64 {
    return std::cmp::min(a, b);
}
```
**SMT Verification**:
- Theorem: `∀ inputs . F_bin(inputs) ≡ F_rust(inputs) on [rax]`
- Status: `PROVEN_EQUIVALENT` (Z3 solving time: 62 ms)
- Native compiler check: `cargo check` PASS

### Try it out

```bash
git clone https://github.com/simpmix/silicon-archeology.git
cd silicon-archeology
pip install -r requirements.txt
python -m silicon_archeology.cli pipeline "48 89 f8 48 01 f0 c3" --name add_two
```

We've open-sourced the entire engine under dual MIT/Apache-2.0 licenses. Would love your feedback on the SMT formalization and CFG structuring!
