"""
Tests for extended features: multi-register returns, SSE2 SIMD lifting,
advanced bit-manipulation idioms, certificate serialization, and CLI commands.
"""

import os
import json
import pytest
from silicon_archeology.pipeline import ReSynthesisPipeline
from silicon_archeology.lifter.x86_lifter import X86Lifter
from silicon_archeology.verifier.certificate import FormalCertificate
from silicon_archeology.benchmarks import BenchmarkRunner
from silicon_archeology.cli import parse_bytes


def test_multi_register_adc_chain():
    pipe = ReSynthesisPipeline(mode=64)
    # adc_chain: 128-bit addition with carry returning (rax, rdx)
    code = bytes.fromhex("48 89 f8 48 01 d0 48 89 f2 48 11 ca c3")
    res = pipe.process("adc_chain", code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True
    assert "(u64, u64)" in res.rust_source


def test_multi_register_sbb_chain():
    pipe = ReSynthesisPipeline(mode=64)
    # sbb_chain: 128-bit subtraction with borrow returning (rax, rdx)
    code = bytes.fromhex("48 89 f8 48 29 d0 48 89 f2 48 19 ca c3")
    res = pipe.process("sbb_chain", code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True
    assert "(u64, u64)" in res.rust_source


def test_multi_register_mul64_full():
    pipe = ReSynthesisPipeline(mode=64)
    # mul64_full: 64x64 full 128-bit multiplication returning (rax, rdx)
    code = bytes.fromhex("48 89 f8 48 f7 e6 c3")
    res = pipe.process("mul64_full", code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True
    assert "(u64, u64)" in res.rust_source


def test_mul_high64():
    pipe = ReSynthesisPipeline(mode=64)
    # mul_high64: returns rdx (high 64 bits)
    code = bytes.fromhex("48 89 f8 48 f7 e6 48 89 d0 c3")
    res = pipe.process("mul_high64", code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True


def test_branchless_signum():
    pipe = ReSynthesisPipeline(mode=64)
    code = bytes.fromhex("48 83 ff 00 0f 9f c0 0f 9c c2 0f b6 c0 0f b6 d2 29 d0 48 98 c3")
    res = pipe.process("branchless_signum", code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True


def test_branchless_midpoint():
    pipe = ReSynthesisPipeline(mode=64)
    code = bytes.fromhex("48 89 f8 48 21 f0 48 89 fa 48 31 f2 48 d1 ea 48 01 d0 c3")
    res = pipe.process("branchless_midpoint", code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True


def test_bit_select():
    pipe = ReSynthesisPipeline(mode=64)
    code = bytes.fromhex("48 89 f8 48 21 f0 48 f7 d7 48 21 d7 48 09 f8 c3")
    res = pipe.process("bit_select", code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True


def test_is_power_of_two():
    pipe = ReSynthesisPipeline(mode=64)
    code = bytes.fromhex("48 85 ff 0f 9f c2 48 8d 47 ff 48 85 c7 0f 94 c0 21 d0 0f b6 c0 c3")
    res = pipe.process("is_power_of_two", code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True
    assert "(x: u64)" in res.rust_source


def test_branchless_cond_inc():
    pipe = ReSynthesisPipeline(mode=64)
    code = bytes.fromhex("48 83 ff 00 0f 9f c0 0f b6 c0 48 01 f8 c3")
    res = pipe.process("branchless_cond_inc", code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True


def test_sse2_simd_lifting():
    lifter = X86Lifter(mode=64)
    # pxor xmm0, xmm1; paddd xmm0, xmm1; ret
    code = bytes.fromhex("66 0f ef c1 66 0f fe c1 c3")
    cfg = lifter.lift_bytes(code)
    assert len(cfg.blocks) == 1
    stmts = list(cfg.blocks.values())[0].stmts
    targets = [s.dest.name for s in stmts if hasattr(s, "dest")]
    assert "xmm0" in targets


def test_certificate_serialization_roundtrip():
    cert = FormalCertificate(
        target_routine="test_routine",
        status="PROVEN_EQUIVALENT",
        solver="Z3 Theorem Prover",
        solver_version="4.12.2",
        theorem="∀ x . f(x) == g(x)",
        num_paths_verified=1,
        inputs_verified=["rdi"],
        outputs_verified=["rax"],
        verification_time_ms=1.23,
        proof_hash="a" * 64,
        counterexample=None
    )
    json_str = cert.to_json()
    loaded = FormalCertificate.from_json(json_str)
    assert loaded.target_routine == cert.target_routine
    assert loaded.status == cert.status
    assert loaded.proof_hash == cert.proof_hash
    assert loaded.verification_time_ms == cert.verification_time_ms


def test_benchmark_runner_subset():
    runner = BenchmarkRunner(mode=64)
    sub = [
        ("add_two", bytes.fromhex("48 89 f8 48 01 f0 c3")),
        ("popcount_builtin", bytes.fromhex("f3 48 0f b8 c7 c3")),
    ]
    summary = runner.run_benchmark(routines=sub)
    assert summary.total_routines == 2
    assert summary.proven_count == 2
    assert summary.mean_solving_ms > 0


def test_cli_parse_bytes_formats():
    assert parse_bytes("48 89 f8 c3") == b"\x48\x89\xf8\xc3"
    assert parse_bytes("0x48, 0x89, 0xf8, 0xc3") == b"\x48\x89\xf8\xc3"


def test_arm64_decoder_operand_widths():
    from silicon_archeology.lifter.decoder import Disassembler
    dis = Disassembler(arch="arm64")
    # add w0, w0, w1; ret
    code = bytes.fromhex("00 00 01 0b c0 03 5f d6")
    insns = dis.disassemble(code)
    assert len(insns) == 2
    assert insns[0].operands[0].size_bits == 32
    assert insns[0].operands[1].size_bits == 32


def test_formal_certificate_status_integrity():
    cert = FormalCertificate(
        target_routine="integrity_check",
        status="PROVEN_EQUIVALENT",
        solver="Z3",
        solver_version="5.4.1",
        theorem="theorem",
        num_paths_verified=1,
        inputs_verified=["rdi"],
        outputs_verified=["rax"],
        verification_time_ms=2.5,
        proof_hash="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    )
    assert len(cert.proof_hash) == 64
    assert cert.status == "PROVEN_EQUIVALENT"


def test_multi_arch_pipeline_selector():
    pipe_x86 = ReSynthesisPipeline(mode=64, arch="x86_64")
    pipe_arm = ReSynthesisPipeline(arch="arm64")
    assert pipe_x86.arch == "x86_64"
    assert pipe_arm.arch == "arm64"


def test_inductive_loop_proof_hash():
    from silicon_archeology.verifier.invariants import InductiveLoopVerifier, Loop
    from silicon_archeology.ir.cfg import ControlFlowGraph, BasicBlock
    from silicon_archeology.ir.instructions import Assign, BinaryExpr, Op, Var, Constant
    verifier = InductiveLoopVerifier()
    cfg = ControlFlowGraph(entry_label="h")
    bb = BasicBlock("h")
    bb.stmts.append(Assign(Var("rax", 64), BinaryExpr(Op.ADD, Var("rax", 64), Constant(1, 64), 64)))
    cfg.add_block(bb)
    lp = Loop(header="h", latch="h", body={"h"})
    cert = verifier.verify_loop_invariant(lp, cfg)
    assert cert.status == "PROVEN_INDUCTIVE"
    assert len(cert.proof_hash) == 64


def test_arm64_benchmark_runner():
    runner = BenchmarkRunner(arch="arm64")
    sub = [
        ("arm64_add", bytes.fromhex("00 00 01 8b c0 03 5f d6")),
        ("arm64_bic", bytes.fromhex("00 00 21 8a c0 03 5f d6")),
    ]
    summary = runner.run_benchmark(routines=sub)
    assert summary.total_routines == 2
    assert summary.proven_count == 2
    assert summary.mean_solving_ms > 0


def test_memory_alias_wrap_around_protection():
    from silicon_archeology.symbolic.alias_analyzer import MemoryAliasAnalyzer, AliasResult
    from silicon_archeology.ir.instructions import Constant
    analyzer = MemoryAliasAnalyzer()
    # High address near 2^64-1 vs low address
    addr_high = Constant(0xFFFFFFFFFFFFFFF8, 64)
    addr_low = Constant(0x0000000000000004, 64)
    res = analyzer.query_alias(addr_high, 8, addr_low, 8)
    # Must NOT alias even with wrap around
    assert res.result == AliasResult.NO_ALIAS

