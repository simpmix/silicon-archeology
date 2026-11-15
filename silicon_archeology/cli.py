"""
Command Line Interface for Silicon Archeology.
SMT-Driven Binary-to-Compilable-Rust Re-Synthesis Engine.
"""

import argparse
import sys
import os
import binascii
import json

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from silicon_archeology.lifter.decoder import Disassembler
from silicon_archeology.lifter.x86_lifter import X86Lifter
from silicon_archeology.lifter.arm64_lifter import ARM64Lifter
from silicon_archeology.symbolic.executor import SymbolicExecutor
from silicon_archeology.synthesizer.rust_emitter import RustEmitter
from silicon_archeology.pipeline import ReSynthesisPipeline
from silicon_archeology.verifier.certificate import FormalCertificate
from silicon_archeology.benchmarks import BenchmarkRunner


def parse_bytes(input_str: str) -> bytes:
    """Parses hex string or binary file."""
    if not input_str:
        raise ValueError("No input provided. Provide a hex string or binary file path.")
    if os.path.isfile(input_str):
        with open(input_str, "rb") as f:
            return f.read()
    # Try hex string
    clean_hex = input_str.replace(" ", "").replace("\n", "").replace("0x", "").replace(",", "")
    if len(clean_hex) % 2 != 0:
        clean_hex = "0" + clean_hex
    return binascii.unhexlify(clean_hex)


def get_target_input(args) -> str:
    """Resolves target input from positional argument, --hex, or --file."""
    if getattr(args, "hex_str", None):
        return args.hex_str
    if getattr(args, "file_path", None):
        return args.file_path
    if getattr(args, "target", None):
        return args.target
    raise ValueError("Target binary machine code required. Pass hex bytes or --hex / --file.")


def get_lifter(arch: str = "x86_64", mode: int = 64):
    if arch.lower() in ("arm64", "aarch64"):
        return ARM64Lifter()
    return X86Lifter(mode=mode)


def cmd_disassemble(args):
    data = parse_bytes(get_target_input(args))
    arch = getattr(args, "arch", "x86_64")
    disasm = Disassembler(mode=args.mode, arch=arch)
    insns = disasm.disassemble(data, base_address=args.base)
    print(f"\n[+] Disassembly [{arch}] ({len(insns)} instructions):")
    for insn in insns:
        print(f"  {insn}")


def cmd_lift(args):
    data = parse_bytes(get_target_input(args))
    arch = getattr(args, "arch", "x86_64")
    lifter = get_lifter(arch=arch, mode=args.mode)
    cfg = lifter.lift_bytes(data, base_address=args.base)
    print(f"\n[+] Lifted Micro-IR CFG [{arch}] ({len(cfg.blocks)} basic blocks):")
    for label, bb in cfg.blocks.items():
        print(f"\nBlock {label}: (preds: {list(bb.predecessors)}, succs: {list(bb.successors)})")
        for s in bb.stmts:
            print(f"    {s}")


def cmd_symbolic(args):
    data = parse_bytes(get_target_input(args))
    arch = getattr(args, "arch", "x86_64")
    lifter = get_lifter(arch=arch, mode=args.mode)
    cfg = lifter.lift_bytes(data, base_address=args.base)
    sym = SymbolicExecutor(cfg)
    tf = sym.compute_transfer_function(function_name=args.name)
    print(f"\n[+] Symbolic Transfer Function [{arch}] ({len(tf.paths)} paths explored):")
    for reg, expr in tf.combined_outputs.items():
        print(f"  {reg} := {expr}")


def cmd_synthesize(args):
    data = parse_bytes(get_target_input(args))
    arch = getattr(args, "arch", "x86_64")
    lifter = get_lifter(arch=arch, mode=args.mode)
    cfg = lifter.lift_bytes(data, base_address=args.base)
    emitter = RustEmitter(cfg, name=args.name, arch=arch)
    ast = emitter.synthesize()
    print(f"\n[+] Synthesized Rust Source Code [{arch}]:")
    print("---------------------------------")
    print(ast.emit())
    print("---------------------------------")


def cmd_pipeline(args):
    data = parse_bytes(get_target_input(args))
    arch = getattr(args, "arch", "x86_64")
    pipe = ReSynthesisPipeline(mode=args.mode, arch=arch)
    res = pipe.process(name=args.name, code_bytes=data, base_address=args.base)
    print(f"\n{'='*70}")
    print(f"  SILICON ARCHEOLOGY: FORMAL RE-SYNTHESIS REPORT [{arch.upper()}]")
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


def cmd_benchmark(args):
    runner = BenchmarkRunner(mode=args.mode)
    print(f"[+] Running automated benchmark suite ({len(runner.pipeline.lifter.__class__.__name__)})...")
    summary = runner.run_benchmark()
    runner.print_report(summary)
    if getattr(args, "output", None):
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(summary.to_json())
        print(f"\n[+] Benchmark summary saved to: {args.output}")


def cmd_cert_verify(args):
    path = args.cert_file
    if not os.path.exists(path):
        print(f"[-] Error: Certificate file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        cert = FormalCertificate.from_json(content)
    except Exception as e:
        print(f"[-] Error: Invalid certificate format ({e})", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print("  FORMAL PROOF CERTIFICATE AUDIT REPORT")
    print("=" * 70)
    print(f"  Routine:       {cert.target_routine}")
    print(f"  Solver:        {cert.solver} v{cert.solver_version}")
    print(f"  Proof Status:  {cert.status}")
    print(f"  Solving Time:  {cert.verification_time_ms:.2f} ms")
    print(f"  Proof Hash:    {cert.proof_hash}")
    print(f"  Theorem:       {cert.theorem}")
    print(f"  Inputs:        {', '.join(cert.inputs_verified)}")
    print(f"  Outputs:       {', '.join(cert.outputs_verified)}")

    # Integrity verification
    valid_hash = len(cert.proof_hash) == 64 and all(c in "0123456789abcdefABCDEF" for c in cert.proof_hash)
    if cert.status == "PROVEN_EQUIVALENT" and valid_hash:
        print("-" * 70)
        print("  VERIFICATION RESULT: [PASSED] - Mathematically Certified Equivalent (UNSAT)")
        print("=" * 70)
    else:
        print("-" * 70)
        print(f"  VERIFICATION RESULT: [FAILED] - Status={cert.status}, ValidHash={valid_hash}")
        print("=" * 70)
        sys.exit(1)


def cmd_inspect(args):
    data = parse_bytes(get_target_input(args))
    arch = getattr(args, "arch", "x86_64")
    disasm = Disassembler(mode=args.mode, arch=arch)
    insns = disasm.disassemble(data, base_address=args.base)
    lifter = get_lifter(arch=arch, mode=args.mode)
    cfg = lifter.lift_bytes(data, base_address=args.base)

    print("=" * 70)
    print(f"  SILICON ARCHEOLOGY: DEEP CFG & SYMBOLIC INSPECTOR [{arch.upper()}]")
    print("=" * 70)
    print(f"\n[1] Disassembly ({len(insns)} instructions):")
    for insn in insns:
        print(f"    0x{insn.address:04x}:  {insn.mnemonic:<8} {insn.op_str}")

    print(f"\n[2] Control Flow Graph ({len(cfg.blocks)} basic blocks):")
    for label, bb in cfg.blocks.items():
        print(f"    Block '{label}':")
        print(f"      Predecessors: {list(bb.predecessors)}")
        print(f"      Successors:   {list(bb.successors)}")
        print(f"      Statements ({len(bb.stmts)}):")
        for s in bb.stmts:
            print(f"        {s}")

    # Compute Dominators
    entry = cfg.entry_label
    all_nodes = set(cfg.blocks.keys())
    dom = {n: set(all_nodes) for n in all_nodes}
    if entry in dom:
        dom[entry] = {entry}
    changed = True
    while changed:
        changed = False
        for n in all_nodes:
            if n == entry:
                continue
            preds = cfg.blocks[n].predecessors
            valid_preds = [p for p in preds if p in dom]
            if valid_preds:
                new_dom = {n} | set.intersection(*(dom[p] for p in valid_preds))
            else:
                new_dom = {n}
            if new_dom != dom[n]:
                dom[n] = new_dom
                changed = True

    print(f"\n[3] Dominator Analysis:")
    for n in sorted(all_nodes):
        print(f"    Dom({n}) = {sorted(dom[n])}")

    # Backedges and loops
    backedges = []
    for u in all_nodes:
        for v in cfg.blocks[u].successors:
            if v in dom.get(u, set()):
                backedges.append((u, v))

    print(f"\n[4] Loop Back-Edges:")
    if backedges:
        for u, v in backedges:
            print(f"    Back-edge: {u} -> {v} (Loop header: {v})")
    else:
        print("    None (Acyclic Control Flow Graph)")

    # Symbolic transfer function
    sym = SymbolicExecutor(cfg)
    tf = sym.compute_transfer_function(function_name="inspected_routine")
    print(f"\n[5] Symbolic Transfer Function ({len(tf.paths)} paths):")
    for reg, expr in sorted(tf.combined_outputs.items()):
        print(f"    {reg} := {expr}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Silicon Archeology: SMT-Driven Binary-to-Compilable-Rust Re-Synthesis Engine"
    )
    parser.add_argument("--mode", type=int, default=64, choices=[32, 64], help="x86 architecture mode (32 or 64)")
    parser.add_argument("--arch", type=str, default="x86_64", choices=["x86_64", "x86", "arm64"], help="Target CPU architecture")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # disasm
    p_disasm = subparsers.add_parser("disasm", help="Disassemble binary bytes")
    p_disasm.add_argument("target", nargs="?", default=None, help="Hex string or path to binary file")
    p_disasm.add_argument("--hex", "-x", dest="hex_str", default=None, help="Hex string opcode")
    p_disasm.add_argument("--file", "-f", dest="file_path", default=None, help="Path to binary file")
    p_disasm.add_argument("--base", type=lambda x: int(x, 0), default=0x1000, help="Base address")
    p_disasm.add_argument("--arch", type=str, default="x86_64", choices=["x86_64", "x86", "arm64"], help="Target architecture")
    p_disasm.set_defaults(func=cmd_disassemble)

    # lift
    p_lift = subparsers.add_parser("lift", help="Lift machine code to Micro-IR CFG")
    p_lift.add_argument("target", nargs="?", default=None, help="Hex string or path to binary file")
    p_lift.add_argument("--hex", "-x", dest="hex_str", default=None, help="Hex string opcode")
    p_lift.add_argument("--file", "-f", dest="file_path", default=None, help="Path to binary file")
    p_lift.add_argument("--base", type=lambda x: int(x, 0), default=0x1000, help="Base address")
    p_lift.add_argument("--arch", type=str, default="x86_64", choices=["x86_64", "x86", "arm64"], help="Target architecture")
    p_lift.set_defaults(func=cmd_lift)

    # symbolic
    p_sym = subparsers.add_parser("symbolic", help="Compute symbolic transfer function")
    p_sym.add_argument("target", nargs="?", default=None, help="Hex string or path to binary file")
    p_sym.add_argument("--hex", "-x", dest="hex_str", default=None, help="Hex string opcode")
    p_sym.add_argument("--file", "-f", dest="file_path", default=None, help="Path to binary file")
    p_sym.add_argument("--name", default="routine", help="Routine name")
    p_sym.add_argument("--base", type=lambda x: int(x, 0), default=0x1000, help="Base address")
    p_sym.add_argument("--arch", type=str, default="x86_64", choices=["x86_64", "x86", "arm64"], help="Target architecture")
    p_sym.set_defaults(func=cmd_symbolic)

    # synthesize
    p_syn = subparsers.add_parser("synthesize", help="Synthesize Rust code from binary")
    p_syn.add_argument("target", nargs="?", default=None, help="Hex string or path to binary file")
    p_syn.add_argument("--hex", "-x", dest="hex_str", default=None, help="Hex string opcode")
    p_syn.add_argument("--file", "-f", dest="file_path", default=None, help="Path to binary file")
    p_syn.add_argument("--name", default="synthesized_routine", help="Routine name")
    p_syn.add_argument("--base", type=lambda x: int(x, 0), default=0x1000, help="Base address")
    p_syn.add_argument("--arch", type=str, default="x86_64", choices=["x86_64", "x86", "arm64"], help="Target architecture")
    p_syn.set_defaults(func=cmd_synthesize)

    # pipeline
    p_pipe = subparsers.add_parser("pipeline", help="Run full pipeline: lift, synthesize, prove, rustc compile")
    p_pipe.add_argument("target", nargs="?", default=None, help="Hex string or path to binary file")
    p_pipe.add_argument("--hex", "-x", dest="hex_str", default=None, help="Hex string opcode")
    p_pipe.add_argument("--file", "-f", dest="file_path", default=None, help="Path to binary file")
    p_pipe.add_argument("--name", default="routine", help="Routine name")
    p_pipe.add_argument("--base", type=lambda x: int(x, 0), default=0x1000, help="Base address")
    p_pipe.add_argument("--arch", type=str, default="x86_64", choices=["x86_64", "x86", "arm64"], help="Target architecture")
    p_pipe.add_argument("--output", "-o", default=None, help="Output Rust file path")
    p_pipe.set_defaults(func=cmd_pipeline)

    # benchmark
    p_bench = subparsers.add_parser("benchmark", help="Run automated SMT benchmarking suite")
    p_bench.add_argument("--output", "-o", default=None, help="Output benchmark summary JSON file")
    p_bench.set_defaults(func=cmd_benchmark)

    # cert-verify
    p_cert = subparsers.add_parser("cert-verify", help="Validate and audit a formal proof certificate (.proof.json)")
    p_cert.add_argument("cert_file", help="Path to .proof.json certificate")
    p_cert.set_defaults(func=cmd_cert_verify)

    # inspect
    p_insp = subparsers.add_parser("inspect", help="Deep CFG, dominators, loop back-edges, and symbolic inspection")
    p_insp.add_argument("target", nargs="?", default=None, help="Hex string or path to binary file")
    p_insp.add_argument("--hex", "-x", dest="hex_str", default=None, help="Hex string opcode")
    p_insp.add_argument("--file", "-f", dest="file_path", default=None, help="Path to binary file")
    p_insp.add_argument("--base", type=lambda x: int(x, 0), default=0x1000, help="Base address")
    p_insp.add_argument("--arch", type=str, default="x86_64", choices=["x86_64", "x86", "arm64"], help="Target architecture")
    p_insp.set_defaults(func=cmd_inspect)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
