"""
Command Line Interface for Silicon Archeology.
SMT-Driven Binary-to-Compilable-Rust Re-Synthesis Engine.
"""

import argparse
import sys
import os
import binascii

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from silicon_archeology.lifter.decoder import Disassembler
from silicon_archeology.lifter.x86_lifter import X86Lifter
from silicon_archeology.symbolic.executor import SymbolicExecutor
from silicon_archeology.synthesizer.rust_emitter import RustEmitter
from silicon_archeology.pipeline import ReSynthesisPipeline


def parse_bytes(input_str: str) -> bytes:
    """Parses hex string or binary file."""
    if os.path.isfile(input_str):
        with open(input_str, "rb") as f:
            return f.read()
    # Try hex string
    clean_hex = input_str.replace(" ", "").replace("\n", "").replace("0x", "").replace(",", "")
    return binascii.unhexlify(clean_hex)


def cmd_disassemble(args):
    data = parse_bytes(args.target)
    disasm = Disassembler(mode=args.mode)
    insns = disasm.disassemble(data, base_address=args.base)
    print(f"\n[+] Disassembly ({len(insns)} instructions):")
    for insn in insns:
        print(f"  {insn}")


def cmd_lift(args):
    data = parse_bytes(args.target)
    lifter = X86Lifter(mode=args.mode)
    cfg = lifter.lift_bytes(data, base_address=args.base)
    print(f"\n[+] Lifted Micro-IR CFG ({len(cfg.blocks)} basic blocks):")
    for label, bb in cfg.blocks.items():
        print(f"\nBlock {label}: (preds: {list(bb.predecessors)}, succs: {list(bb.successors)})")
        for s in bb.stmts:
            print(f"    {s}")


def cmd_symbolic(args):
    data = parse_bytes(args.target)
    lifter = X86Lifter(mode=args.mode)
    cfg = lifter.lift_bytes(data, base_address=args.base)
    sym = SymbolicExecutor(cfg)
    tf = sym.compute_transfer_function(function_name=args.name)
    print(f"\n[+] Symbolic Transfer Function ({len(tf.paths)} paths explored):")
    for reg, expr in tf.combined_outputs.items():
        print(f"  {reg} := {expr}")


def cmd_synthesize(args):
    data = parse_bytes(args.target)
    lifter = X86Lifter(mode=args.mode)
    cfg = lifter.lift_bytes(data, base_address=args.base)
    emitter = RustEmitter(cfg, name=args.name)
    ast = emitter.synthesize()
    print("\n[+] Synthesized Rust Source Code:")
    print("---------------------------------")
    print(ast.emit())
    print("---------------------------------")


def cmd_pipeline(args):
    data = parse_bytes(args.target)
    pipe = ReSynthesisPipeline(mode=args.mode)
    res = pipe.process(name=args.name, code_bytes=data, base_address=args.base)
    print(f"\n{'='*70}")
    print(f"  SILICON ARCHEOLOGY: FORMAL RE-SYNTHESIS REPORT")
    print(f"  Target Routine: {res.routine_name}")
    print(f"{'='*70}\n")
    print("[1] Synthesized Idiomatic Rust Code:")
    print(res.rust_source)
    print("\n[2] SMT Equivalence Verification:")
    print(f"  Status:       {res.certificate.status}")
    print(f"  Theorem:      {res.certificate.theorem}")
    print(f"  Solver:       {res.certificate.solver} v{res.certificate.solver_version}")
    print(f"  Solving Time: {res.certificate.verification_time_ms:.2f} ms")
    print(f"  Proof Hash:   {res.certificate.proof_hash}")
    print("\n[3] Native Compiler (rustc) Verification:")
    print(f"  Compiles:     {res.compiles_successfully}")
    print(f"  Test Status:  {res.test_passed}")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(res.rust_source)
        cert_path = args.output + ".proof.json"
        with open(cert_path, "w", encoding="utf-8") as f:
            f.write(res.certificate.to_json())
        print(f"\n[+] Rust source saved to: {args.output}")
        print(f"[+] Formal certificate saved to: {cert_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Silicon Archeology: SMT-Driven Binary-to-Compilable-Rust Re-Synthesis Engine"
    )
    parser.add_argument("--mode", type=int, default=64, choices=[32, 64], help="x86 architecture mode (32 or 64)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # disasm
    p_disasm = subparsers.add_parser("disasm", help="Disassemble binary bytes")
    p_disasm.add_argument("target", help="Hex string or path to binary file")
    p_disasm.add_argument("--base", type=lambda x: int(x, 0), default=0x1000, help="Base address")
    p_disasm.set_defaults(func=cmd_disassemble)

    # lift
    p_lift = subparsers.add_parser("lift", help="Lift machine code to Micro-IR CFG")
    p_lift.add_argument("target", help="Hex string or path to binary file")
    p_lift.add_argument("--base", type=lambda x: int(x, 0), default=0x1000, help="Base address")
    p_lift.set_defaults(func=cmd_lift)

    # symbolic
    p_sym = subparsers.add_parser("symbolic", help="Compute symbolic transfer function")
    p_sym.add_argument("target", help="Hex string or path to binary file")
    p_sym.add_argument("--name", default="routine", help="Routine name")
    p_sym.add_argument("--base", type=lambda x: int(x, 0), default=0x1000, help="Base address")
    p_sym.set_defaults(func=cmd_symbolic)

    # synthesize
    p_syn = subparsers.add_parser("synthesize", help="Synthesize Rust code from binary")
    p_syn.add_argument("target", help="Hex string or path to binary file")
    p_syn.add_argument("--name", default="synthesized_routine", help="Routine name")
    p_syn.add_argument("--base", type=lambda x: int(x, 0), default=0x1000, help="Base address")
    p_syn.set_defaults(func=cmd_synthesize)

    # pipeline
    p_pipe = subparsers.add_parser("pipeline", help="Run full pipeline: lift, synthesize, prove, rustc compile")
    p_pipe.add_argument("target", help="Hex string or path to binary file")
    p_pipe.add_argument("--name", default="routine", help="Routine name")
    p_pipe.add_argument("--base", type=lambda x: int(x, 0), default=0x1000, help="Base address")
    p_pipe.add_argument("--output", "-o", default=None, help="Output Rust file path")
    p_pipe.set_defaults(func=cmd_pipeline)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
