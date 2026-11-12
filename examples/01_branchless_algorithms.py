"""
Example 1: Branchless Algorithms Re-Synthesis & SMT Equivalence Verification.

Demonstrates:
1. Lifting x86_64 binary sequences implementing branchless min/max and bit-twiddling
2. Generating Micro-IR Control Flow Graphs
3. Idiom detection & modern Rust AST synthesis
4. SMT formal proof generation using Z3
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from silicon_archeology.pipeline import ReSynthesisPipeline
from silicon_archeology.lifter.decoder import Disassembler


def main():
    print("=" * 80)
    print("  SILICON ARCHEOLOGY: EXAMPLE 1 - BRANCHLESS ALGORITHMS RE-SYNTHESIS")
    print("=" * 80)

    pipeline = ReSynthesisPipeline(mode=64)
    disasm = Disassembler(mode=64)

    routines = [
        (
            "branchless_min",
            bytes.fromhex("48 39 f7 48 0f 4f fe 48 89 f8 c3"),
            "x86_64 cmp + cmovg branchless signed minimum"
        ),
        (
            "isolate_lowest_bit",
            bytes.fromhex("48 89 f8 48 f7 d8 48 21 f8 c3"),
            "x86_64 neg + and (isolate lowest set bit: x & -x)"
        ),
        (
            "popcount_builtin",
            bytes.fromhex("f3 48 0f b8 c7 c3"),
            "x86_64 popcnt rax, rdi (population count)"
        )
    ]

    for name, code, desc in routines:
        print(f"\n[*] Processing Routine: {name}")
        print(f"    Description: {desc}")
        print(f"    Raw Bytes:   {code.hex(' ')}")

        # Step 1: Disassembly
        insns = disasm.disassemble(code, base_address=0x1000)
        print("    Disassembly:")
        for insn in insns:
            print(f"      0x{insn.address:04x}: {insn.mnemonic:7s} {insn.op_str}")

        # Step 2: Re-synthesis & Formal Verification
        res = pipeline.process(name=name, code_bytes=code)

        print("\n    [+] Formally Re-Synthesized Rust:")
        for line in res.rust_source.splitlines():
            print(f"        {line}")

        print(f"\n    [+] Verification Theorem: {res.certificate.theorem}")
        print(f"    [+] SMT Proof Status:     {res.certificate.status}")
        print(f"    [+] Solver:               {res.certificate.solver} v{res.certificate.solver_version}")
        print(f"    [+] Verification Time:    {res.certificate.verification_time_ms:.2f} ms")
        print(f"    [+] Proof Hash:           {res.certificate.proof_hash}")
        print(f"    [+] Native rustc Check:   {res.compiles_successfully}")
        print("-" * 80)


if __name__ == "__main__":
    main()
