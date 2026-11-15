"""
Tests for Inductive Loop Invariant Synthesizer and Formal Verifier.
"""

import pytest
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
