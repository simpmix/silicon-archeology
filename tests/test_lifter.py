"""
Unit tests for x86 Lifter and Micro-IR translation.
"""

import pytest
from silicon_archeology.lifter.decoder import Disassembler, DecodedOperand, MemRef
from silicon_archeology.lifter.x86_lifter import X86Lifter
from silicon_archeology.ir.instructions import (
    Assign, Branch, Jump, Return, BinaryExpr, UnaryExpr, Constant, Var, Op
)
from silicon_archeology.ir.types import normalize_reg


def test_register_normalization():
    assert normalize_reg("rax") == ("rax", 0, 64)
    assert normalize_reg("eax") == ("rax", 0, 32)
    assert normalize_reg("ax") == ("rax", 0, 16)
    assert normalize_reg("al") == ("rax", 0, 8)
    assert normalize_reg("ah") == ("rax", 8, 8)
    assert normalize_reg("r8d") == ("r8", 0, 32)
    assert normalize_reg("r15b") == ("r15", 0, 8)


def test_decoder_disassembly():
    disasm = Disassembler(mode=64)
    # mov rax, rdi; add rax, rsi; ret
    code = bytes.fromhex("48 89 f8 48 01 f0 c3")
    insns = disasm.disassemble(code, base_address=0x1000)
    assert len(insns) == 3
    assert insns[0].mnemonic == "mov"
    assert insns[1].mnemonic == "add"
    assert insns[2].mnemonic == "ret"
    assert insns[0].operands[0].value == "rax"
    assert insns[0].operands[1].value == "rdi"


def test_lifter_arithmetic_instructions():
    lifter = X86Lifter(mode=64)
    # xor eax, eax; inc rax; dec rax; neg rax; not rax; ret
    code = bytes.fromhex("31 c0 48 ff c0 48 ff c8 48 f7 d8 48 f7 d0 c3")
    cfg = lifter.lift_bytes(code)
    assert len(cfg.blocks) >= 1
    stmts = cfg.blocks[cfg.entry_label].stmts
    mnemonics = [s.text.split()[0] for s in stmts if hasattr(s, "text")]
    assert "xor" in mnemonics
    assert "inc" in mnemonics
    assert "dec" in mnemonics
    assert "neg" in mnemonics
    assert "not" in mnemonics
    assert isinstance(stmts[-1], Return)


def test_lifter_shifts_and_rotates():
    lifter = X86Lifter(mode=64)
    # shl rax, 3; shr rax, 2; sar rax, 1; rol rax, 4; ror rax, 4; ret
    code = bytes.fromhex("48 c1 e0 03 48 c1 e8 02 48 d1 f8 48 c1 c0 04 48 c1 c8 04 c3")
    cfg = lifter.lift_bytes(code)
    stmts = cfg.blocks[cfg.entry_label].stmts
    mnemonics = [s.text.split()[0] for s in stmts if hasattr(s, "text")]
    assert "shl" in mnemonics
    assert "shr" in mnemonics
    assert "sar" in mnemonics
    assert "rol" in mnemonics
    assert "ror" in mnemonics


def test_lifter_branching_and_cfg():
    lifter = X86Lifter(mode=64)
    # cmp rdi, rsi
    # jge loc_greater
    # mov rax, rdi
    # ret
    # loc_greater:
    # mov rax, rsi
    # ret
    # 48 39 f7 7d 04 48 89 f8 c3 48 89 f0 c3
    code = bytes.fromhex("48 39 f7 7d 04 48 89 f8 c3 48 89 f0 c3")
    cfg = lifter.lift_bytes(code, base_address=0x1000)
    assert len(cfg.blocks) >= 2
    entry_bb = cfg.blocks[cfg.entry_label]
    assert any(isinstance(s, Branch) for s in entry_bb.stmts)
    # Ensure edges and dominators are computed
    assert len(cfg.dominators) > 0


def test_lifter_loop_detection():
    lifter = X86Lifter(mode=64)
    # Entry: mov eax, 10
    # loop_top: dec eax; jnz loop_top; ret
    # b8 0a 00 00 00 ff c8 75 fc c3
    code = bytes.fromhex("b8 0a 00 00 00 ff c8 75 fc c3")
    cfg = lifter.lift_bytes(code, base_address=0x1000)
    loops = cfg.detect_loops()
    assert len(loops) == 1
    assert loops[0].header != ""
    assert loops[0].latch != ""
