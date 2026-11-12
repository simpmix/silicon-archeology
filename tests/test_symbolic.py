"""
Unit tests for Symbolic Execution engine, memory model, and transfer function generation.
"""

import pytest
import z3
from silicon_archeology.symbolic.state import SymbolicState
from silicon_archeology.symbolic.memory import SymbolicMemory
from silicon_archeology.symbolic.executor import SymbolicExecutor
from silicon_archeology.ir.cfg import ControlFlowGraph, BasicBlock
from silicon_archeology.ir.instructions import (
    Assign, Branch, Jump, Return, BinaryExpr, UnaryExpr, Constant, Var, Op, MemLoad, MemStore
)


def test_symbolic_state_read_write():
    state = SymbolicState(prefix="test")
    # 64-bit write
    state.write_reg("rax", z3.BitVecVal(0x1122334455667788, 64))
    assert state.read_reg("rax").as_long() == 0x1122334455667788

    # 32-bit write should zero-extend upper 32 bits
    state.write_reg("eax", z3.BitVecVal(0x99AABBCC, 32))
    assert state.read_reg("rax").as_long() == 0x0000000099AABBCC
    assert state.read_reg("eax").as_long() == 0x99AABBCC

    # 16-bit write should preserve upper 48 bits
    state.write_reg("ax", z3.BitVecVal(0x1234, 16))
    assert state.read_reg("rax").as_long() == 0x0000000099AA1234


def test_symbolic_memory_little_endian():
    mem = SymbolicMemory(name="test_mem")
    addr = z3.BitVecVal(0x2000, 64)
    val = z3.BitVecVal(0x0102030405060708, 64)

    mem.write(addr, val, 64)

    # Read back 64-bit
    read64 = mem.read(addr, 64)
    s = z3.Solver()
    s.add(read64 != val)
    assert s.check() == z3.unsat

    # Read individual bytes
    # Little-endian: lowest byte at addr+0 is 0x08
    b0 = mem.read(addr, 8)
    s0 = z3.Solver()
    s0.add(b0 != z3.BitVecVal(0x08, 8))
    assert s0.check() == z3.unsat

    b7 = mem.read(addr + z3.BitVecVal(7, 64), 8)
    s7 = z3.Solver()
    s7.add(b7 != z3.BitVecVal(0x01, 8))
    assert s7.check() == z3.unsat


def test_symbolic_executor_arithmetic():
    cfg = ControlFlowGraph(entry_label="entry")
    bb = cfg.get_or_create_block("entry")
    # rax = (rdi * 2) + rsi
    rdi = Var("rdi", 64)
    rsi = Var("rsi", 64)
    rax = Var("rax", 64)
    mult = BinaryExpr(Op.MUL, rdi, Constant(2, 64), 64)
    res = BinaryExpr(Op.ADD, mult, rsi, 64)
    bb.add_stmt(Assign(rax, res))
    bb.add_stmt(Return(rax))

    executor = SymbolicExecutor(cfg)
    tf = executor.compute_transfer_function(function_name="calc")
    assert "rax" in tf.combined_outputs

    # Verify that rax == in_rdi * 2 + in_rsi
    s = z3.Solver()
    in_rdi = tf.input_symbols["rdi"]
    in_rsi = tf.input_symbols["rsi"]
    expected = (in_rdi * 2) + in_rsi
    s.add(tf.combined_outputs["rax"] != expected)
    assert s.check() == z3.unsat


def test_symbolic_executor_multi_path():
    cfg = ControlFlowGraph(entry_label="entry")
    b_entry = cfg.get_or_create_block("entry")
    b_then = cfg.get_or_create_block("then_blk")
    b_else = cfg.get_or_create_block("else_blk")

    rdi = Var("rdi", 64)
    rax = Var("rax", 64)

    # if rdi > 10 goto then_blk else goto else_blk
    cond = BinaryExpr(Op.GT, rdi, Constant(10, 64), 1)
    b_entry.add_stmt(Branch(cond, "then_blk", "else_blk"))

    # then_blk: rax = 100; ret
    b_then.add_stmt(Assign(rax, Constant(100, 64)))
    b_then.add_stmt(Return(rax))

    # else_blk: rax = 200; ret
    b_else.add_stmt(Assign(rax, Constant(200, 64)))
    b_else.add_stmt(Return(rax))

    cfg.finalize_edges()

    executor = SymbolicExecutor(cfg)
    tf = executor.compute_transfer_function(function_name="branch_test")
    assert len(tf.paths) == 2

    # Check that when in_rdi = 15, rax = 100
    s = z3.Solver()
    in_rdi = tf.input_symbols["rdi"]
    s.add(in_rdi == 15)
    s.add(tf.combined_outputs["rax"] != 100)
    assert s.check() == z3.unsat

    # Check that when in_rdi = 5, rax = 200
    s2 = z3.Solver()
    s2.add(in_rdi == 5)
    s2.add(tf.combined_outputs["rax"] != 200)
    assert s2.check() == z3.unsat


def test_symbolic_ctz_clz_bswap():
    cfg = ControlFlowGraph(entry_label="entry")
    bb = cfg.get_or_create_block("entry")
    rdi = Var("rdi", 64)
    rax = Var("rax", 64)
    # rax = ctz(rdi)
    bb.add_stmt(Assign(rax, UnaryExpr(Op.CTZ, rdi, 64)))
    bb.add_stmt(Return(rax))

    executor = SymbolicExecutor(cfg)
    tf = executor.compute_transfer_function(function_name="ctz_calc")
    assert "rax" in tf.combined_outputs

    s = z3.Solver()
    in_rdi = tf.input_symbols["rdi"]
    # For rdi = 0b1000 (8), ctz is 3
    s.add(in_rdi == 8)
    s.add(tf.combined_outputs["rax"] != 3)
    assert s.check() == z3.unsat


def test_symbolic_bmi_blsr():
    from silicon_archeology.lifter.x86_lifter import X86Lifter
    # blsr rax, rdi; ret
    code = bytes.fromhex("c4 e2 f8 f3 cf c3")
    lifter = X86Lifter(mode=64)
    cfg = lifter.lift_bytes(code)
    executor = SymbolicExecutor(cfg)
    tf = executor.compute_transfer_function(function_name="blsr_fn")
    assert "rax" in tf.combined_outputs

    s = z3.Solver()
    in_rdi = tf.input_symbols["rdi"]
    # For rdi = 12 (0b1100), blsr gives 8 (0b1000)
    s.add(in_rdi == 12)
    s.add(tf.combined_outputs["rax"] != 8)
    assert s.check() == z3.unsat


def test_symbolic_signed_remainder():
    # Verify Op.REM uses truncated signed remainder (z3.SRem)
    cfg = ControlFlowGraph(entry_label="entry")
    bb = cfg.get_or_create_block("entry")
    # rax = (-10) % 3 -> should be -1
    rem = BinaryExpr(Op.REM, Constant(-10, 64), Constant(3, 64), 64)
    bb.add_stmt(Assign(Var("rax", 64), rem))
    bb.add_stmt(Return(Var("rax", 64)))

    executor = SymbolicExecutor(cfg)
    tf = executor.compute_transfer_function("rem_fn")
    s = z3.Solver()
    s.add(tf.combined_outputs["rax"] != z3.BitVecVal(-1, 64))
    assert s.check() == z3.unsat


def test_symbolic_bmi2_shlx_shrx():
    from silicon_archeology.lifter.x86_lifter import X86Lifter
    # shlx rax, rdi, rsi; ret
    code = bytes.fromhex("c4 e2 c9 f7 c7 c3")
    lifter = X86Lifter(mode=64)
    cfg = lifter.lift_bytes(code)
    executor = SymbolicExecutor(cfg)
    tf = executor.compute_transfer_function("shlx_fn")

    s = z3.Solver()
    in_rdi = tf.input_symbols["rdi"]
    in_rsi = tf.input_symbols["rsi"]
    s.add(in_rdi == 7)
    s.add(in_rsi == 2)
    s.add(tf.combined_outputs["rax"] != 28)
    assert s.check() == z3.unsat
