# 🏗️ Silicon Archeology: Technical Architecture Specification

This document provides a comprehensive technical specification of **Silicon Archeology**, detailing the design, formal semantics, and algorithms of each subsystem.

---

## 1. Micro-IR Architecture

Silicon Archeology targets a minimal, bit-precise intermediate representation (Micro-IR) tailored for SMT solving and high-level control-flow restructuring.

### 1.1 Type System & Value Domains
- **Widths**: First-class support for arbitrary bit-widths $\mathbb{B}^w$ where $w \in \{1, 8, 16, 32, 64\}$.
- **Sign Semantics**: Values are stored as unsigned BitVectors $\mathbb{Z} / 2^w \mathbb{Z}$; signed interpretations are applied via explicit signed operators (`Op.LT`, `Op.LE`, `Op.GT`, `Op.GE`, `Op.SAR`).
- **Flags**: 1-bit boolean register terms (`__zf`, `__sf`, `__cf`, `__of`, `__pf`, `__af`).

### 1.2 Instruction Classes
Micro-IR separates statements from side-effect-free pure expressions:
```text
Expressions (Expr):
  Constant(value, bit_width)
  Var(name, bit_width)
  UnaryExpr(op, operand, bit_width)
  BinaryExpr(op, left, right, bit_width)
  ExtractExpr(expr, high, low)
  ConcatExpr([parts], bit_width)
  IteExpr(cond, then_expr, else_expr, bit_width)
  MemLoad(addr, bit_width)

Statements (Stmt):
  Assign(dest, expr)
  MemStore(addr, expr, bit_width)
  Branch(cond, target, fallthrough)
  Jump(target)
  Return(value)
  Nop()
  Comment(text)
```

---

## 2. x86_64 Lifter & Flag Synthesis

The lifter (`silicon_archeology.lifter.x86_lifter.X86Lifter`) translates Capstone disassembled instructions into Micro-IR Basic Blocks.

### 2.1 x86-64 Register Aliasing Rules
x86-64 has complex aliasing rules across sub-registers:
1. **64-bit Writes**: Directly overwrites parent register (e.g., `rax`).
2. **32-bit Writes**: Hardware zeroes the upper 32 bits of the 64-bit register:
   $$\text{reg}_{64} \longleftarrow \text{Concat}(0_{32}, \text{val}_{32})$$
3. **16-bit Writes**: Preserves upper 48 bits:
   $$\text{reg}_{64} \longleftarrow \text{Concat}(\text{reg}_{64}[63:16], \text{val}_{16})$$
4. **8-bit Low Writes (`al`, `bl`, etc.)**: Preserves upper 56 bits:
   $$\text{reg}_{64} \longleftarrow \text{Concat}(\text{reg}_{64}[63:8], \text{val}_{8})$$
5. **8-bit High Writes (`ah`, `bh`, `ch`, `dh`)**: Preserves upper 48 bits and lowest 8 bits:
   $$\text{reg}_{64} \longleftarrow \text{Concat}(\text{reg}_{64}[63:16], \text{val}_{8}, \text{reg}_{64}[7:0])$$

### 2.2 Algebraic Flag Synthesis
Rather than maintaining an opaque state machine, flags are synthesized as pure boolean/bit expressions:
- **Zero Flag ($\text{ZF}$)**:
  $$\text{ZF}(R) \coloneqq (R == 0)$$
- **Sign Flag ($\text{SF}$)**:
  $$\text{SF}(R) \coloneqq R[w-1]$$
- **Carry Flag ($\text{CF}$)**:
  $$\text{CF}_{\text{add}}(A, B, R) \coloneqq R <_u A, \qquad \text{CF}_{\text{sub}}(A, B) \coloneqq A <_u B$$
- **Overflow Flag ($\text{OF}$)**:
  $$\text{OF}_{\text{add}}(A, B, R) \coloneqq ((A \oplus \neg B) \land (A \oplus R))[w-1]$$
  $$\text{OF}_{\text{sub}}(A, B, R) \coloneqq ((A \oplus B) \land (A \oplus R))[w-1]$$

---

## 3. Symbolic Execution & Memory Modeling

### 3.1 Z3 Little-Endian Memory Theory
Memory is modeled using Z3's quantifier-free theory of Arrays (`Array(BitVec(64), BitVec(8))`):
$$\text{Memory} : \mathbb{B}^{64} \longrightarrow \mathbb{B}^8$$
- Multi-byte reads/writes are reconstructed using little-endian concatenation:
  $$\text{Read}_{32}(A) = \text{Concat}(\text{Select}(M, A+3), \text{Select}(M, A+2), \text{Select}(M, A+1), \text{Select}(M, A))$$

### 3.2 Path Exploration & ITE Collapse
The symbolic executor traverses the CFG using a bounded worklist algorithm:
1. Tracks path condition $\Pi \in \text{Bool}$.
2. Branches split the state into $(\Pi \land C, \text{State}_{\text{then}})$ and $(\Pi \land \neg C, \text{State}_{\text{else}})$.
3. Paths are simplified and collapsed into nested If-Then-Else (`ITE`) expressions for each observable output register.

---

## 4. Control-Flow Structuring: The Relooper Engine

The Relooper algorithm converts arbitrary graphs of basic blocks into structured Rust syntax (`while`, `loop`, `if-else`, `break`):

1. **Dominance Frontier & Natural Loops**:
   - Computes immediate dominators $\text{idom}(n)$ using iterative dataflow analysis.
   - Detects back-edges $u \to v$ where $v \in \text{dom}(u)$, establishing $v$ as the loop header.
2. **Loop Structuring**:
   - Clean conditional loops where the header branch exits or repeats are synthesized directly into `while (cond) { body }`.
   - Complex multi-exit loops are synthesized into `loop { ... if exit { break; } }`.
3. **Linear Fallthrough**:
   - Consecutive blocks without branches are linearized into sequential statement blocks.

---

## 5. Algorithmic Idiom Recognition

Silicon Archeology includes pattern-matching engines that recognize idiomatic algorithms and synthesize idiomatic Rust standard library primitives:

| Binary Pattern | Lifted Micro-IR | Synthesized Rust |
| :--- | :--- | :--- |
| `neg rdi; and rax, rdi` | `(-x) & x` | `x & x.wrapping_neg()` |
| `blsr rax, rdi` | `(x - 1) & x` | `x & x.wrapping_sub(1)` |
| `andn rax, rdi, rsi` | `(!a) & b` | `(!a) & b` |
| `bextr rax, rdi, rsi` | `(src >> start) & mask` | `(src >> start) & mask` |
| `tzcnt rax, rdi` | `ctz(x)` | `x.trailing_zeros() as u64` |
| `lzcnt rax, rdi` | `clz(x)` | `x.leading_zeros() as u64` |
| `bswap rax` | `bswap(x)` | `x.swap_bytes()` |
| `popcnt rax, rdi` | `popcnt(x)` | `x.count_ones() as u64` |
| `cmp rdi, rsi; cmovg rdi, rsi` | `if a > b then b else a` (signed) | `std::cmp::min(a, b)` |
| `cmp rdi, rsi; cmovl rdi, rsi` | `if a < b then b else a` (signed) | `std::cmp::max(a, b)` |
| `cmp ... cmovl ... cmp ... cmovg` | `clamp(val, min, max)` | `val.clamp(min, max)` |
| `rol rdi, k` | `rotate_left(x, k)` | `x.rotate_left(k)` |
| `xor rdx, rdx; div rsi` | `rax u/ rsi, rax u% rsi` | `(a / b), (a % b)` |
| `cmp rdi, rsi; sete al` | `if a == b then 1 else 0` | `if a == b { 1 } else { 0 }` |
| `imul rax, c; shr rdx, 33; xor ...` | Avalanche multiplier round | `(rax * c) ^ (rax >> 33)` |

---

## 6. SMT Equivalence Verification Engine

### 6.1 Formal Proof Construction
For any lifted routine, we construct the formula:
$$\Phi_{\text{equiv}} \coloneqq \bigwedge_{r \in \mathcal{O}} \left( \mathcal{F}_{\text{binary}}(\vec{x})_r == \mathcal{F}_{\text{rust}}(\vec{x})_r \right)$$

The verifier asserts the negation (discrepancy):
$$\exists \vec{x} \in \mathbb{B}^{64 \times k} \quad \text{s.t.} \quad \neg \Phi_{\text{equiv}}$$

- If Z3 returns **UNSAT**: It is mathematically impossible for any input to cause the synthesized Rust code to differ from the binary code. A formal proof certificate is generated.
- If Z3 returns **SAT**: A concrete input valuation $\vec{x}_{\text{counter}}$ is extracted from the model, diagnosing the exact discrepancy.

### 6.2 Certificate Format
Certificates contain:
- Target routine identifier
- Z3 solver version
- Formal theorem string
- Evaluated input & output symbols
- Elapsed verification time
- SHA-256 proof hash binding the theorem, timestamp, and target
