# 📢 Silicon Archeology: Launch & Distribution Kit

This kit contains distribution materials, social media copy, and community announcements to launch and market **Silicon Archeology** across developer ecosystems.

---

## 1. Twitter / X Thread

### Tweet 1 (Hook + Link)
🚨 Decompilers give you readable C pseudocode.
We built a system that re-synthesizes raw x86_64 binaries into memory-safe, compilable Rust — and mathematically PROVES equivalence with Z3.

Introducing Silicon Archeology 🏛️🦀
👉 https://github.com/silicon-archeology/silicon-archeology

Here’s how SMT-driven re-synthesis works 🧵👇

### Tweet 2 (The Problem)
Ghidra and IDA Pro Hex-Rays are engineering masterpieces, but their output is informal pseudo-C:
❌ goto spaghetti
❌ Unchecked raw pointers
❌ Undefined signed overflow
❌ Zero correctness guarantees

Trying to port this into Rust by hand is a nightmare.

### Tweet 3 (The Insight)
Instead of syntactic AST rewriting, treat reverse engineering as an SMT synthesis problem:
1. Lift x86_64 to Micro-IR
2. Symbolically execute via Z3 BitVectors to derive closed-form transfer functions:
   F_bin: State_in -> State_out

### Tweet 4 (The Equivalence Theorem)
We synthesize structured Rust ASTs using Relooper + idiom matching (count_ones, min/max, wrapping_neg).
Then we ask Z3:
Does there exist ANY 64-bit input where F_bin(x) != F_rust(x)?

UNSAT = 100% Proven Equivalent.
SAT = Concrete counterexample found.

### Tweet 5 (Results)
Every synthesis emits a cryptographic `.proof.json` certificate with a SHA-256 theorem hash.
We ran it on Murmur3 mixers, TEA cipher Feistel blocks, and branchless algorithms.
Average verification time: < 10ms.
Native check: `cargo check` PASS.

Check it out and star the repo! ⭐
https://github.com/silicon-archeology/silicon-archeology

---

## 2. Reddit r/rust & r/ReverseEngineering Post

**Title**: [Project] Silicon Archeology: SMT-Driven Binary-to-Compilable-Rust Re-Synthesis Engine (Proven via Z3)

**Body**:
Hey everyone,

We've been working on a project called **Silicon Archeology** that bridges formal methods, binary analysis, and Rust language synthesis.

Instead of traditional decompiler approaches that produce loose pseudo-C, Silicon Archeology:
1. Disassembles and lifts x86/x86_64 machine code into a bit-precise Micro-IR with explicit flag synthesis (ZF, SF, CF, OF) and hardware 32-bit zero-extension rules.
2. Symbolically executes the routine in Z3's BitVector and Array theories, deriving closed-form input-to-output transfer functions.
3. Structures CFGs into clean, high-level Rust statements (`while`, `loop`, `if-else`) via Relooper, recognizing standard library idioms like `count_ones()`, `wrapping_neg()`, and `rotate_left()`.
4. Formally proves mathematical equivalence using Z3 SMT solving (`UNSAT` on discrepancy assertion), emitting a JSON proof certificate.
5. Emits a full, compilable standalone Rust crate ready for `cargo check` and `cargo test`.

We have an example crate in the repository containing re-synthesized routines for Murmur3 64-bit avalanche mixing, TEA cipher blocks, and branchless algorithms:
https://github.com/silicon-archeology/silicon-archeology

All feedback, PRs, and critiques on our symbolic memory model and CFG structuring are welcome!

---

## 3. Lobste.rs Submission

**Title**: Silicon Archeology: SMT-driven x86 binary re-synthesis to compilable Rust
**URL**: https://github.com/silicon-archeology/silicon-archeology
**Tags**: `rust`, `reversing`, `formalmethods`, `compilers`

**Commentary**:
Silicon Archeology uses Z3's QF_BV theory to formally verify that re-synthesized Rust functions compute the identical mathematical function as raw x86_64 binary code across the entire 64-bit state space. The pipeline includes an automated Relooper structuring engine and exports formal certificates along with compilable Cargo crates.
