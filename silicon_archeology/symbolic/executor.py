"""
Symbolic Execution Engine evaluating Micro-IR into Z3 expressions.
"""

from typing import Dict, List, Optional, Tuple, Set, Any
import z3
from silicon_archeology.ir.cfg import ControlFlowGraph, BasicBlock
from silicon_archeology.ir.instructions import (
    Expr, Var, Constant, BinaryExpr, UnaryExpr, ExtractExpr,
    ConcatExpr, IteExpr, MemLoad, Stmt, Assign, MemStore, Branch, Jump, Return, Nop, Comment, Op
)
from silicon_archeology.symbolic.state import SymbolicState
from silicon_archeology.symbolic.transfer_function import TransferFunction, PathSummary


class SymbolicExecutor:
    def __init__(self, cfg: ControlFlowGraph, max_paths: int = 32, max_loop_unroll: int = 8):
        self.cfg = cfg
        self.max_paths = max_paths
        self.max_loop_unroll = max_loop_unroll

    def eval_expr(self, expr: Expr, state: SymbolicState) -> z3.BitVecRef:
        """Evaluates an IR expression into a Z3 BitVec expression."""
        if isinstance(expr, Constant):
            return z3.BitVecVal(expr.value, expr.bit_width)

        elif isinstance(expr, Var):
            canon = expr.name.lower()
            if canon.startswith("__"):
                # Internal flag
                if canon not in state.registers:
                    state.registers[canon] = z3.BitVec(f"{state.prefix}_{canon}", 1)
                return state.registers[canon]
            return state.read_reg(canon)

        elif isinstance(expr, UnaryExpr):
            val = self.eval_expr(expr.operand, state)
            if expr.op == Op.NOT:
                return ~val
            elif expr.op == Op.NEG:
                return -val
            elif expr.op == Op.POPCNT:
                w = val.size()
                bits = [z3.ZeroExt(w - 1, z3.Extract(i, i, val)) for i in range(w)]
                total = bits[0]
                for b in bits[1:]:
                    total = total + b
                return total
            raise NotImplementedError(f"Unhandled unary op {expr.op}")

        elif isinstance(expr, BinaryExpr):
            left = self.eval_expr(expr.left, state)
            right = self.eval_expr(expr.right, state)

            # Sizing harmonization if needed
            if left.size() != right.size():
                target_sz = max(left.size(), right.size())
                if left.size() < target_sz:
                    left = z3.ZeroExt(target_sz - left.size(), left)
                if right.size() < target_sz:
                    right = z3.ZeroExt(target_sz - right.size(), right)

            w = left.size()
            op = expr.op
            if op == Op.ADD:
                return left + right
            elif op == Op.SUB:
                return left - right
            elif op == Op.MUL:
                return left * right
            elif op == Op.DIV:
                return left / right
            elif op == Op.UDIV:
                return z3.UDiv(left, right)
            elif op == Op.REM:
                return left % right
            elif op == Op.UREM:
                return z3.URem(left, right)
            elif op == Op.AND:
                return left & right
            elif op == Op.OR:
                return left | right
            elif op == Op.XOR:
                return left ^ right
            elif op == Op.SHL:
                return left << right
            elif op == Op.SHR:
                return z3.LShR(left, right)
            elif op == Op.SAR:
                return left >> right
            elif op == Op.ROL:
                # Rotate left
                if isinstance(expr.right, Constant):
                    return z3.RotateLeft(left, expr.right.value % w)
                return (left << (right % w)) | z3.LShR(left, (w - (right % w)))
            elif op == Op.ROR:
                if isinstance(expr.right, Constant):
                    return z3.RotateRight(left, expr.right.value % w)
                return z3.LShR(left, (right % w)) | (left << (w - (right % w)))

            # Comparisons return a 1-bit BitVec: 1 if true, 0 if false
            elif op == Op.EQ:
                return z3.If(left == right, z3.BitVecVal(1, 1), z3.BitVecVal(0, 1))
            elif op == Op.NE:
                return z3.If(left != right, z3.BitVecVal(1, 1), z3.BitVecVal(0, 1))
            elif op == Op.LT:
                return z3.If(left < right, z3.BitVecVal(1, 1), z3.BitVecVal(0, 1))
            elif op == Op.LE:
                return z3.If(left <= right, z3.BitVecVal(1, 1), z3.BitVecVal(0, 1))
            elif op == Op.GT:
                return z3.If(left > right, z3.BitVecVal(1, 1), z3.BitVecVal(0, 1))
            elif op == Op.GE:
                return z3.If(left >= right, z3.BitVecVal(1, 1), z3.BitVecVal(0, 1))
            elif op == Op.ULT:
                return z3.If(z3.ULT(left, right), z3.BitVecVal(1, 1), z3.BitVecVal(0, 1))
            elif op == Op.ULE:
                return z3.If(z3.ULE(left, right), z3.BitVecVal(1, 1), z3.BitVecVal(0, 1))
            elif op == Op.UGT:
                return z3.If(z3.UGT(left, right), z3.BitVecVal(1, 1), z3.BitVecVal(0, 1))
            elif op == Op.UGE:
                return z3.If(z3.UGE(left, right), z3.BitVecVal(1, 1), z3.BitVecVal(0, 1))

            raise NotImplementedError(f"Unhandled binary op {op}")

        elif isinstance(expr, ExtractExpr):
            inner = self.eval_expr(expr.expr, state)
            return z3.Extract(expr.high, expr.low, inner)

        elif isinstance(expr, ConcatExpr):
            evaled_parts = [self.eval_expr(p, state) for p in expr.parts]
            res = evaled_parts[0]
            for p in evaled_parts[1:]:
                res = z3.Concat(res, p)
            return res

        elif isinstance(expr, IteExpr):
            c_bv = self.eval_expr(expr.cond, state)
            c_bool = (c_bv == z3.BitVecVal(1, 1)) if c_bv.size() == 1 else (c_bv != 0)
            then_v = self.eval_expr(expr.then_expr, state)
            else_v = self.eval_expr(expr.else_expr, state)
            return z3.If(c_bool, then_v, else_v)

        elif isinstance(expr, MemLoad):
            addr = self.eval_expr(expr.addr, state)
            return state.memory.read(addr, expr.bit_width)

        raise TypeError(f"Unknown expression type {type(expr)}")

    def eval_bool(self, expr: Expr, state: SymbolicState) -> z3.BoolRef:
        """Evaluates an IR condition into a Z3 boolean formula."""
        bv = self.eval_expr(expr, state)
        if bv.size() == 1:
            return bv == z3.BitVecVal(1, 1)
        return bv != z3.BitVecVal(0, bv.size())

    def execute_block(self, block: BasicBlock, state: SymbolicState) -> None:
        """Executes all non-branch statements in a basic block."""
        for stmt in block.stmts:
            if isinstance(stmt, Assign):
                val = self.eval_expr(stmt.expr, state)
                state.write_reg(stmt.dest.name, val)
            elif isinstance(stmt, MemStore):
                addr = self.eval_expr(stmt.addr, state)
                val = self.eval_expr(stmt.expr, state)
                state.memory.write(addr, val, stmt.bit_width)
            elif isinstance(stmt, (Comment, Nop, Branch, Jump, Return)):
                pass

    def compute_transfer_function(self, function_name: str = "routine") -> TransferFunction:
        """
        Explores all reachable paths through the CFG, accumulating constraints
        and computing the composite TransferFunction.
        """
        init_state = SymbolicState(prefix="in")
        tf = TransferFunction(name=function_name, input_symbols=dict(init_state.inputs))

        solver = z3.Solver()
        # Path exploration queue: (current_block_label, current_state, visit_counts)
        worklist: List[Tuple[str, SymbolicState, Dict[str, int]]] = [
            (self.cfg.entry_label, init_state, {})
        ]

        completed_paths: List[PathSummary] = []

        while worklist and len(completed_paths) < self.max_paths:
            block_label, state, visits = worklist.pop(0)
            visits = dict(visits)
            visits[block_label] = visits.get(block_label, 0) + 1

            if visits[block_label] > self.max_loop_unroll:
                continue

            bb = self.cfg.blocks.get(block_label)
            if not bb:
                continue

            # Execute statements
            self.execute_block(bb, state)
            term = bb.terminator

            if isinstance(term, Return) or term is None:
                # Path terminated
                completed_paths.append(PathSummary(
                    condition=z3.simplify(state.path_condition),
                    register_effects={r: z3.simplify(v) for r, v in state.registers.items() if not r.startswith("__")},
                    memory_writes=[]
                ))

            elif isinstance(term, Jump):
                worklist.append((term.target, state, visits))

            elif isinstance(term, Branch):
                cond_z3 = self.eval_bool(term.cond, state)

                # Then branch (target)
                then_state = state.clone()
                then_state.add_constraint(cond_z3)
                solver.push()
                solver.add(then_state.path_condition)
                if solver.check() != z3.unsat:
                    worklist.append((term.target, then_state, visits))
                solver.pop()

                # Else branch (fallthrough)
                else_state = state.clone()
                else_state.add_constraint(z3.Not(cond_z3))
                solver.push()
                solver.add(else_state.path_condition)
                if solver.check() != z3.unsat:
                    worklist.append((term.fallthrough, else_state, visits))
                solver.pop()

        tf.paths = completed_paths
        tf.collapse_into_ite()
        return tf
