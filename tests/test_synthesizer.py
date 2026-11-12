"""
Unit tests for Synthesizer: Relooper, Type Inference, Idiom Matching, and Rust code emission.
"""

import pytest
from silicon_archeology.ir.cfg import ControlFlowGraph
from silicon_archeology.ir.instructions import (
    Assign, Branch, Jump, Return, BinaryExpr, UnaryExpr, Constant, Var, Op, Comment
)
from silicon_archeology.synthesizer.ast import (
    RustFunction, RustParam, RustReturn, RustLet, RustAssignStmt, RustIdent, RustLiteral, RustBinaryOp
)
from silicon_archeology.synthesizer.relooper import Relooper
from silicon_archeology.synthesizer.type_infer import TypeInference
from silicon_archeology.synthesizer.idioms import IdiomMatcher
from silicon_archeology.synthesizer.rust_emitter import RustEmitter


def test_type_inference_signed_and_parameters():
    cfg = ControlFlowGraph(entry_label="entry")
    bb = cfg.get_or_create_block("entry")
    rdi = Var("rdi", 64)
    rsi = Var("rsi", 64)
    rax = Var("rax", 64)
    # Signed comparison rdi < rsi
    cond = BinaryExpr(Op.LT, rdi, rsi, 1)
    bb.add_stmt(Assign(rax, cond))
    bb.add_stmt(Return(rax))

    ti = TypeInference(cfg)
    params, type_map, ret_type = ti.analyze()
    assert "rdi" in params
    assert "rsi" in params
    assert type_map["rdi"] == "i64"
    assert type_map["rsi"] == "i64"


def test_relooper_linear_sequence():
    cfg = ControlFlowGraph(entry_label="entry")
    bb = cfg.get_or_create_block("entry")
    bb.add_stmt(Assign(Var("rax", 64), Constant(42, 64)))
    bb.add_stmt(Return(Var("rax", 64)))

    relooper = Relooper(cfg)
    stmts = relooper.structure()
    assert len(stmts) >= 1
    # Check emitted Rust source
    fn = RustFunction(name="test_fn", body=stmts)
    src = fn.emit()
    assert "rax = 42;" in src
    assert "return rax;" in src


def test_idiom_isolate_lowest_set_bit():
    cfg = ControlFlowGraph(entry_label="entry")
    bb = cfg.get_or_create_block("entry")
    bb.add_stmt(Comment("neg rdi"))
    bb.add_stmt(Comment("and rax, rdi"))
    bb.add_stmt(Return(Var("rax", 64)))

    fn = IdiomMatcher.match_isolate_lowest_bit(cfg)
    assert fn is not None
    src = fn.emit()
    assert "x.wrapping_neg()" in src
    assert "pub fn isolate_lowest_set_bit" in src


def test_idiom_popcount():
    cfg = ControlFlowGraph(entry_label="entry")
    b0 = cfg.get_or_create_block("loc_1000")
    b1 = cfg.get_or_create_block("loc_1004")
    b0.add_stmt(Comment("popcnt rax, rdi"))
    b0.add_stmt(Jump("loc_1004"))
    b1.add_stmt(Return(Var("rax", 64)))
    cfg.finalize_edges()
    cfg.loops.append(object())  # Mock 1 loop

    fn = IdiomMatcher.match_popcount(cfg)
    assert fn is not None
    src = fn.emit()
    assert "count_ones" in src


def test_rust_emitter_synthesize():
    cfg = ControlFlowGraph(entry_label="entry")
    bb = cfg.get_or_create_block("entry")
    # rax = rdi + rsi
    rdi = Var("rdi", 64)
    rsi = Var("rsi", 64)
    rax = Var("rax", 64)
    bb.add_stmt(Assign(rax, BinaryExpr(Op.ADD, rdi, rsi, 64)))
    bb.add_stmt(Return(rax))

    emitter = RustEmitter(cfg, name="add_nums")
    fn = emitter.synthesize()
    src = fn.emit()

    assert "pub fn add_nums" in src
    assert "mut a: u64" in src
    assert "mut b: u64" in src
    assert "let mut rax: u64 = 0;" in src
    assert "return rax;" in src


def test_type_inference_memstore_and_ite():
    from silicon_archeology.ir.instructions import MemStore, MemLoad, IteExpr
    cfg = ControlFlowGraph(entry_label="entry")
    bb = cfg.get_or_create_block("entry")
    rdi = Var("rdi", 64)
    rsi = Var("rsi", 64)
    # MemStore at rdi of rsi
    bb.add_stmt(MemStore(rdi, rsi, 64))
    bb.add_stmt(Return(Var("rax", 64)))

    ti = TypeInference(cfg)
    params, type_map, ret_type = ti.analyze()
    assert "rdi" in params
    assert "rsi" in params


def test_rust_emitter_loop_renaming():
    from silicon_archeology.lifter.x86_lifter import X86Lifter
    # CFG with a loop: test rsi, rsi; jz end; loop: dec rsi; jmp loop
    code = bytes.fromhex("48 85 f6 74 06 48 ff ce eb f7 c3")
    lifter = X86Lifter(mode=64)
    cfg = lifter.lift_bytes(code)
    emitter = RustEmitter(cfg, name="loop_test")
    fn = emitter.synthesize()
    src = fn.emit()
    assert "pub fn loop_test" in src
    # 'rsi' should be renamed to 'b' in executable statements (not comments)
    code_lines = [l for l in src.splitlines() if not l.strip().startswith("//")]
    code_text = "\n".join(code_lines)
    assert "rsi" not in code_text
    assert "b" in code_text

