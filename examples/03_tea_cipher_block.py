"""
Example 3: Tiny Encryption Algorithm (TEA) Cipher Core Re-Synthesis & Equivalence Proof.

Demonstrates:
1. Re-synthesizing x86_64 32-bit sub-register arithmetic (eax, esi, ecx, edx, r8d, r9d, r10d)
2. Handling zero-extension and modular Feistel round structure
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
    print("  SILICON ARCHEOLOGY: EXAMPLE 3 - TEA CIPHER CORE RE-SYNTHESIS")
    print("=" * 80)

    # x86_64 TEA encryption round:
    #   mov eax, esi          ; v1
    #   shl eax, 4
    #   add eax, ecx          ; + k0
    #   mov r9d, esi
    #   add r9d, edx          ; + sum
    #   xor eax, r9d
    #   mov r10d, esi
    #   shr r10d, 5
    #   add r10d, r8d         ; + k1
    #   xor eax, r10d
    #   add eax, edi          ; + v0
    #   ret
    code = bytes.fromhex("89 f0 c1 e0 04 01 c8 41 89 f1 41 01 d1 44 31 c8 41 89 f2 41 c1 ea 05 45 01 c2 44 31 d0 01 f8 c3")

    disasm = Disassembler(mode=64)
    insns = disasm.disassemble(code, base_address=0x1000)

    print("\n[1] Disassembled x86_64 TEA Round Instructions:")
    for insn in insns:
        print(f"    0x{insn.address:04x}: {insn.mnemonic:7s} {insn.op_str}")

    print("\n[2] Executing Formal Re-Synthesis Pipeline...")
    pipeline = ReSynthesisPipeline(mode=64)
    res = pipeline.process(name="tea_round", code_bytes=code)

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

    proof_file = os.path.join(os.path.dirname(__file__), "tea_round.proof.json")
    with open(proof_file, "w", encoding="utf-8") as f:
        f.write(res.certificate.to_json())
    print(f"\n[+] Proof certificate exported to: {proof_file}")


if __name__ == "__main__":
    main()
