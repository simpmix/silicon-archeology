"""
Tests for Inductive Loop Invariant Synthesizer and Formal Verifier.
"""

import pytest
import z3
from silicon_archeology.verifier.invariants import InductiveLoopVerifier, InductiveProofCertificate
from silicon_archeology.ir.cfg import ControlFlowGraph, BasicBlock, Loop
from silicon_archeology.ir.instructions import Assign, BinaryExpr, Op, Var, Constant, Branch


def test_inductive_loop_verifier_simple_loop():
    verifier = InductiveLoopVerifier()
    cfg = ControlFlowGraph(entry_label="header")
    
    header = BasicBlock("header")
    # rax := rax + 1
    header.stmts.append(Assign(Var("rax", 64), BinaryExpr(Op.ADD, Var("rax", 64), Constant(1, 64), 64)))
    cfg.add_block(header)

    loop = Loop(header="header", latch="header", body={"header"}, exits=set())
    cfg.loops.append(loop)

    cert = verifier.verify_loop_invariant(loop, cfg)
    assert cert.status == "PROVEN_INDUCTIVE"
    assert cert.base_case_holds is True
    assert cert.inductive_step_holds is True
    assert len(cert.proof_hash) == 64


def test_analyze_cfg_loops():
    verifier = InductiveLoopVerifier()
    cfg = ControlFlowGraph(entry_label="entry")
    
    entry = BasicBlock("entry")
    header = BasicBlock("loop_header")
    header.stmts.append(Assign(Var("rcx", 64), BinaryExpr(Op.SUB, Var("rcx", 64), Constant(1, 64), 64)))
    
    cfg.add_block(entry)
    cfg.add_block(header)

    loop = Loop(header="loop_header", latch="loop_header", body={"loop_header"}, exits={("loop_header", "entry")})
    cfg.loops.append(loop)

    certs = verifier.analyze_cfg_loops(cfg)
    assert len(certs) == 1
    assert certs[0].status == "PROVEN_INDUCTIVE"


def test_inductive_loop_invariant_step_failure():
    verifier = InductiveLoopVerifier()
    cfg = ControlFlowGraph(entry_label="header")
    header = BasicBlock("header")
    # rax := rax + 2
    header.stmts.append(Assign(Var("rax", 64), BinaryExpr(Op.ADD, Var("rax", 64), Constant(2, 64), 64)))
    cfg.add_block(header)

    loop = Loop(header="header", latch="header", body={"header"}, exits=set())
    cfg.loops.append(loop)

    # Invariant: rax <= 10. But with step +2, rax=10 goes to 12, violating rax <= 10
    inv = lambda st: z3.ULE(st.read_reg("rax"), z3.BitVecVal(10, 64))
    pre = lambda st: z3.ULE(st.read_reg("rax"), z3.BitVecVal(10, 64))
    cert = verifier.verify_loop_invariant(loop, cfg, invariant_predicate=inv, precondition_predicate=pre)
    assert cert.status == "FAILED_STEP"
    assert cert.base_case_holds is True
    assert cert.inductive_step_holds is False
    assert cert.counterexample is not None


def test_inductive_loop_base_case_failure():
    verifier = InductiveLoopVerifier()
    cfg = ControlFlowGraph(entry_label="header")
    header = BasicBlock("header")
    header.stmts.append(Assign(Var("rax", 64), BinaryExpr(Op.ADD, Var("rax", 64), Constant(1, 64), 64)))
    cfg.add_block(header)

    loop = Loop(header="header", latch="header", body={"header"}, exits=set())
    cfg.loops.append(loop)

    # Pre: rax == 20, Inv: rax <= 10 -> Base case must fail
    pre = lambda st: st.read_reg("rax") == z3.BitVecVal(20, 64)
    inv = lambda st: z3.ULE(st.read_reg("rax"), z3.BitVecVal(10, 64))
    cert = verifier.verify_loop_invariant(loop, cfg, invariant_predicate=inv, precondition_predicate=pre)
    assert cert.status == "FAILED_BASE"
    assert cert.base_case_holds is False


def test_inductive_loop_termination_ranking():
    verifier = InductiveLoopVerifier()
    cfg = ControlFlowGraph(entry_label="header")
    header = BasicBlock("header")
    # rcx := rcx - 1
    header.stmts.append(Assign(Var("rcx", 64), BinaryExpr(Op.SUB, Var("rcx", 64), Constant(1, 64), 64)))
    # branch if rcx > 0 stay in loop
    guard_cond = BinaryExpr(Op.UGT, Var("rcx", 64), Constant(0, 64), 1)
    header.stmts.append(Branch(guard_cond, "header", "exit"))
    cfg.add_block(header)

    exit_bb = BasicBlock("exit")
    cfg.add_block(exit_bb)

    loop = Loop(header="header", latch="header", body={"header"}, exits={("header", "exit")})
    cfg.loops.append(loop)

    inv = lambda st: z3.UGE(st.read_reg("rcx"), z3.BitVecVal(0, 64))
    pre = lambda st: z3.UGT(st.read_reg("rcx"), z3.BitVecVal(0, 64))
    rank = lambda st: st.read_reg("rcx")
    cert = verifier.verify_loop_invariant(loop, cfg, invariant_predicate=inv, precondition_predicate=pre, ranking_metric=rank)
    assert cert.status == "PROVEN_INDUCTIVE"
    assert "Formally proven well-founded" in (cert.termination_metric or "")
