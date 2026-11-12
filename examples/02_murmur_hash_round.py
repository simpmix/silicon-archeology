"""
Example 2: Murmur3 64-bit Avalanche Mixer Re-Synthesis & Equivalence Proof.

Demonstrates:
1. Re-synthesizing x86_64 64-bit constant multiplication, shifts, and xors
2. Generating the SMT verification theorem over 2^64 state space
3. Formally proving mathematical equivalence via Z3 BitVec logic
4. Verifying compilable memory-safe Rust with native rustc
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from silicon_archeology.pipeline import ReSynthesisPipeline
from silicon_archeology.lifter.decoder import Disassembler


def main():
    print("=" * 80)
    print("  SILICON ARCHEOLOGY: EXAMPLE 2 - MURMUR3 64-BIT MIXER RE-SYNTHESIS")
    print("=" * 80)

    # x86_64 Murmur3 finalizer mix round:
    #   mov rax, rdi
    #   movabs rcx, 0xff51afd7ed558ccd
    #   imul rax, rcx
    #   mov rdx, rax
    #   shr rdx, 33
    #   xor rax, rdx
    #   ret
    code = bytes.fromhex("48 89 f8 48 b9 cd 8c 55 ed d7 af 51 ff 48 0f af c1 48 89 c2 48 c1 ea 21 48 31 d0 c3")

    disasm = Disassembler(mode=64)
    insns = disasm.disassemble(code, base_address=0x1000)

    print("\n[1] Disassembled x86_64 Instructions:")
    for insn in insns:
        print(f"    0x{insn.address:04x}: {insn.mnemonic:7s} {insn.op_str}")

    print("\n[2] Executing Formal Re-Synthesis Pipeline...")
    pipeline = ReSynthesisPipeline(mode=64)
    res = pipeline.process(name="murmur3_fmix64", code_bytes=code)

    print("\n[3] Synthesized Rust Code:")
    print("--------------------------------------------------------------------------------")
    print(res.rust_source)
    print("--------------------------------------------------------------------------------")

    print("\n[4] SMT Formal Equivalence Certificate:")
    print(f"    Target Routine:  {res.certificate.target_routine}")
    print(f"    Status:          {res.certificate.status}")
    print(f"    Theorem:         {res.certificate.theorem}")
    print(f"    Solver:          {res.certificate.solver} v{res.certificate.solver_version}")
    print(f"    Solving Time:    {res.certificate.verification_time_ms:.2f} ms")
    print(f"    Proof Hash:      {res.certificate.proof_hash}")
    print(f"    rustc Compiles:  {res.compiles_successfully}")

    proof_file = os.path.join(os.path.dirname(__file__), "murmur3_fmix64.proof.json")
    with open(proof_file, "w", encoding="utf-8") as f:
        f.write(res.certificate.to_json())
    print(f"\n[+] Proof certificate exported to: {proof_file}")


if __name__ == "__main__":
    main()
