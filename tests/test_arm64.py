"""
Tests for ARM64 (AArch64) lifter, symbolic execution, and re-synthesis pipeline.
"""

import pytest
from silicon_archeology.lifter.decoder import Disassembler
from silicon_archeology.lifter.arm64_lifter import ARM64Lifter
from silicon_archeology.symbolic.executor import SymbolicExecutor
from silicon_archeology.synthesizer.rust_emitter import RustEmitter
from silicon_archeology.pipeline import ReSynthesisPipeline


def test_arm64_disassembler():
    dis = Disassembler(arch="arm64")
    # add x0, x0, x1; ret
    code = bytes.fromhex("00 00 01 8b c0 03 5f d6")
    insns = dis.disassemble(code)
    assert len(insns) == 2
    assert insns[0].mnemonic == "add"
    assert insns[0].operands[0].value == "x0"
    assert insns[0].operands[1].value == "x0"
    assert insns[0].operands[2].value == "x1"
    assert insns[1].mnemonic == "ret"


def test_arm64_lifter_arithmetic():
    lifter = ARM64Lifter()
    # add x0, x0, x1; ret
    code = bytes.fromhex("00 00 01 8b c0 03 5f d6")
    cfg = lifter.lift_bytes(code)
    assert len(cfg.blocks) == 1
    block = list(cfg.blocks.values())[0]
    # Check that statements include assignment to x0 and return
    assignments = [s for s in block.stmts if hasattr(s, "dest") and s.dest.name == "x0"]
    assert len(assignments) >= 1
    assert block.stmts[-1].__class__.__name__ == "Return"


def test_arm64_lifter_bitwise():
    lifter = ARM64Lifter()
    # eor x0, x0, x1; ret
    code = bytes.fromhex("00 00 01 ca c0 03 5f d6")
    cfg = lifter.lift_bytes(code)
    assert len(cfg.blocks) == 1
    block = list(cfg.blocks.values())[0]
    assigns = [s for s in block.stmts if hasattr(s, "dest") and s.dest.name == "x0"]
    assert len(assigns) == 1
    assert assigns[0].expr.op.name == "XOR"


def test_arm64_lifter_multiplication():
    lifter = ARM64Lifter()
    # mul x0, x0, x1; ret
    code = bytes.fromhex("00 7c 01 9b c0 03 5f d6")
    cfg = lifter.lift_bytes(code)
    block = list(cfg.blocks.values())[0]
    assigns = [s for s in block.stmts if hasattr(s, "dest") and s.dest.name == "x0"]
    assert len(assigns) == 1
    assert assigns[0].expr.op.name == "MUL"


def test_arm64_lifter_csel():
    lifter = ARM64Lifter()
    # cmp x0, x1; csel x0, x0, x1, eq; ret
    code = bytes.fromhex("1f 00 01 eb 00 00 81 9a c0 03 5f d6")
    cfg = lifter.lift_bytes(code)
    block = list(cfg.blocks.values())[0]
    ite_assigns = [s for s in block.stmts if hasattr(s, "expr") and s.expr.__class__.__name__ == "IteExpr"]
    assert len(ite_assigns) >= 1


def test_arm64_symbolic_execution():
    lifter = ARM64Lifter()
    # add x0, x0, x1; ret
    code = bytes.fromhex("00 00 01 8b c0 03 5f d6")
    cfg = lifter.lift_bytes(code)
    executor = SymbolicExecutor(cfg)
    tf = executor.compute_transfer_function("arm64_add")
    assert "x0" in tf.combined_outputs


def test_arm64_pipeline_add():
    pipe = ReSynthesisPipeline(arch="arm64")
    # add x0, x0, x1; ret
    code = bytes.fromhex("00 00 01 8b c0 03 5f d6")
    res = pipe.process("arm64_add", code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True
    assert "fn arm64_add" in res.rust_source


def test_arm64_pipeline_sub():
    pipe = ReSynthesisPipeline(arch="arm64")
    # sub x0, x0, x1; ret
    code = bytes.fromhex("00 00 01 cb c0 03 5f d6")
    res = pipe.process("arm64_sub", code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True


def test_arm64_pipeline_eor():
    pipe = ReSynthesisPipeline(arch="arm64")
    # eor x0, x0, x1; ret
    code = bytes.fromhex("00 00 01 ca c0 03 5f d6")
    res = pipe.process("arm64_xor", code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True


def test_arm64_pipeline_mul():
    pipe = ReSynthesisPipeline(arch="arm64")
    # mul x0, x0, x1; ret
    code = bytes.fromhex("00 7c 01 9b c0 03 5f d6")
    res = pipe.process("arm64_mul", code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True


def test_arm64_pipeline_bic():
    pipe = ReSynthesisPipeline(arch="arm64")
    # bic x0, x0, x1; ret (x0 = x0 & ~x1)
    code = bytes.fromhex("00 00 21 8a c0 03 5f d6")
    res = pipe.process("arm64_bic", code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True


def test_arm64_shifted_register_add():
    lifter = ARM64Lifter()
    # add x0, x1, x2, lsl #3; ret
    code = bytes.fromhex("20 0c 02 8b c0 03 5f d6")
    cfg = lifter.lift_bytes(code)
    stmts = list(cfg.blocks.values())[0].stmts
    add_stmt = [s for s in stmts if hasattr(s, "dest") and s.dest.name == "x0"][0]
    assert "<<" in str(add_stmt.expr)


def test_arm64_madd():
    pipe = ReSynthesisPipeline(arch="arm64")
    # madd x0, x0, x1, x2; ret -> x0 = x2 + (x0 * x1)
    code = bytes.fromhex("00 08 01 9b c0 03 5f d6")
    res = pipe.process("arm64_madd", code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True


def test_arm64_movk():
    lifter = ARM64Lifter()
    # movz x0, #0; movk x0, #0x1234, lsl #16; ret
    code = bytes.fromhex("00 00 80 d2 80 46 a2 f2 c0 03 5f d6")
    cfg = lifter.lift_bytes(code)
    block = list(cfg.blocks.values())[0]
    assigns = [s for s in block.stmts if hasattr(s, "dest") and s.dest.name == "x0"]
    assert len(assigns) == 2
