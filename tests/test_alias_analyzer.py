"""
Tests for Symbolic Memory Alias Analysis Engine.
"""

import pytest
import z3
from silicon_archeology.symbolic.alias_analyzer import MemoryAliasAnalyzer, AliasResult
from silicon_archeology.ir.instructions import Var, Constant, BinaryExpr, Op, MemLoad, MemStore, Assign
from silicon_archeology.ir.cfg import ControlFlowGraph, BasicBlock


def test_must_alias_identical():
    analyzer = MemoryAliasAnalyzer()
    rdi = Var("rdi", 64)
    # [rdi] vs [rdi]
    res = analyzer.query_alias(rdi, 8, rdi, 8)
    assert res.result == AliasResult.MUST_ALIAS


def test_must_alias_equivalent_expressions():
    analyzer = MemoryAliasAnalyzer()
    rdi = Var("rdi", 64)
    # [rdi + 8] vs [rdi + 8]
    addr1 = BinaryExpr(Op.ADD, rdi, Constant(8, 64), 64)
    addr2 = BinaryExpr(Op.ADD, rdi, Constant(8, 64), 64)
    res = analyzer.query_alias(addr1, 8, addr2, 8)
    assert res.result == AliasResult.MUST_ALIAS


def test_no_alias_disjoint_offsets():
    analyzer = MemoryAliasAnalyzer()
    rdi = Var("rdi", 64)
    # [rdi] of size 8 vs [rdi + 8] of size 8
    # Addresses are rdi .. rdi+8 and rdi+8 .. rdi+16 -> Disjoint (assuming no overflow)
    addr1 = rdi
    addr2 = BinaryExpr(Op.ADD, rdi, Constant(8, 64), 64)
    # With precondition that rdi < 0xFFFFFFFFFFFFFFF0 to prevent overflow
    rdi_bv = z3.BitVec("alias_in_rdi", 64)
    precond = [z3.ULT(rdi_bv, z3.BitVecVal(0xFFFFFFFFFFFFFFF0, 64))]
    res = analyzer.query_alias(addr1, 8, addr2, 8, preconditions=precond)
    assert res.result == AliasResult.NO_ALIAS


def test_no_alias_constant_addresses():
    analyzer = MemoryAliasAnalyzer()
    addr1 = Constant(0x1000, 64)
    addr2 = Constant(0x2000, 64)
    res = analyzer.query_alias(addr1, 16, addr2, 16)
    assert res.result == AliasResult.NO_ALIAS


def test_may_alias_independent_pointers():
    analyzer = MemoryAliasAnalyzer()
    rdi = Var("rdi", 64)
    rsi = Var("rsi", 64)
    # [rdi] vs [rsi] can overlap if rdi == rsi
    res = analyzer.query_alias(rdi, 8, rsi, 8)
    assert res.result == AliasResult.MAY_ALIAS
    assert res.counterexample is not None


def test_cfg_references_analysis():
    analyzer = MemoryAliasAnalyzer()
    cfg = ControlFlowGraph(entry_label="entry")
    bb = BasicBlock("entry")
    rdi = Var("rdi", 64)
    rsi = Var("rsi", 64)
    # Store to [rdi] and Load from [rdi]
    bb.stmts.append(MemStore(rdi, rsi, 64))
    bb.stmts.append(Assign(Var("rax", 64), MemLoad(rdi, 64)))
    cfg.add_block(bb)

    report = analyzer.analyze_cfg_references(cfg)
    assert report.total_queries == 1
    assert report.must_alias_count == 1
