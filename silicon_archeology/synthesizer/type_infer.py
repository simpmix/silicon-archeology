"""
Type inference engine for synthesizing idiomatic Rust types from binary operations.
"""

from typing import Dict, Set, List, Tuple, Any, Optional
from silicon_archeology.ir.cfg import ControlFlowGraph
from silicon_archeology.ir.instructions import (
    Assign, MemStore, Branch, Return, BinaryExpr, UnaryExpr,
    Var, Constant, Op, Stmt, ExtractExpr, ConcatExpr, IteExpr, MemLoad, Comment
)


class TypeInference:
    def __init__(self, cfg: ControlFlowGraph):
        self.cfg = cfg
        self.signed_regs: Set[str] = set()
        self.width_32_regs: Set[str] = set()
        self.read_before_written: List[str] = []

    def analyze(self) -> Tuple[List[str], Dict[str, str], str]:
        """
        Returns:
            (param_names, type_map, return_type)
        """
        written: Set[str] = set()
        read_order: List[str] = []

        # Known standard parameter registers across System V and Windows x64
        candidate_params = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]

        for label in self.cfg.reverse_post_order():
            bb = self.cfg.blocks.get(label)
            if not bb:
                continue

            for stmt in bb.stmts:
                # Collect reads
                reads = self._collect_reads(stmt)
                for r in reads:
                    canon = r.lower()
                    if canon not in written and canon not in read_order and canon in candidate_params:
                        read_order.append(canon)

                # Collect writes
                if isinstance(stmt, Assign):
                    dest = stmt.dest.name.lower()
                    written.add(dest)

                # Check operations for signedness and widths
                self._inspect_signedness(stmt)

        # Sort parameters according to canonical ABI order
        read_order = sorted(read_order, key=lambda r: candidate_params.index(r) if r in candidate_params else 999)

        type_map: Dict[str, str] = {}
        for reg in read_order:
            is_signed = reg in self.signed_regs
            is_32 = reg in self.width_32_regs
            if is_signed:
                type_map[reg] = "i32" if is_32 else "i64"
            else:
                type_map[reg] = "u32" if is_32 else "u64"

        # Return type (rax)
        ret_signed = "rax" in self.signed_regs
        ret_32 = "rax" in self.width_32_regs
        if ret_signed:
            return_type = "i32" if ret_32 else "i64"
        else:
            return_type = "u32" if ret_32 else "u64"

        return read_order, type_map, return_type

    def _collect_reads(self, stmt: Stmt) -> Set[str]:
        reads: Set[str] = set()
        if isinstance(stmt, Assign):
            # Recognize self-clearing zeroing idioms (e.g. xor r, r or sub r, r)
            expr = stmt.expr
            if isinstance(expr, BinaryExpr) and expr.op in (Op.XOR, Op.SUB):
                if str(expr.left) == str(expr.right):
                    return reads
            elif isinstance(expr, ConcatExpr) and len(expr.parts) == 2:
                inner = expr.parts[1]
                if isinstance(inner, BinaryExpr) and inner.op in (Op.XOR, Op.SUB):
                    if str(inner.left) == str(inner.right):
                        return reads
            self._expr_reads(stmt.expr, reads)
        elif isinstance(stmt, MemStore):
            self._expr_reads(stmt.addr, reads)
            self._expr_reads(stmt.expr, reads)
        elif isinstance(stmt, Branch):
            self._expr_reads(stmt.cond, reads)
        elif isinstance(stmt, Return) and stmt.value:
            self._expr_reads(stmt.value, reads)
        return reads

    def _expr_reads(self, expr: Any, reads: Set[str]) -> None:
        if isinstance(expr, Var):
            if not expr.name.startswith("__"):
                reads.add(expr.name)
        elif isinstance(expr, (BinaryExpr, UnaryExpr)):
            if hasattr(expr, "left"):
                self._expr_reads(expr.left, reads)
            if hasattr(expr, "right"):
                self._expr_reads(expr.right, reads)
            if hasattr(expr, "operand"):
                self._expr_reads(expr.operand, reads)
        elif isinstance(expr, ExtractExpr):
            self._expr_reads(expr.expr, reads)
        elif isinstance(expr, ConcatExpr):
            for p in expr.parts:
                self._expr_reads(p, reads)
        elif isinstance(expr, IteExpr):
            self._expr_reads(expr.cond, reads)
            self._expr_reads(expr.then_expr, reads)
            self._expr_reads(expr.else_expr, reads)
        elif isinstance(expr, MemLoad):
            self._expr_reads(expr.addr, reads)

    def _inspect_signedness(self, stmt: Stmt) -> None:
        def extract_reg(e: Any) -> Optional[str]:
            if isinstance(e, Var):
                return e.name
            if isinstance(e, ExtractExpr) and isinstance(e.expr, Var):
                return e.expr.name
            return None

        if isinstance(stmt, Assign):
            expr = stmt.expr
            if isinstance(expr, BinaryExpr):
                if expr.op in (Op.LT, Op.LE, Op.GT, Op.GE, Op.SAR):
                    r_left = extract_reg(expr.left)
                    if r_left:
                        self.signed_regs.add(r_left)
                    r_right = extract_reg(expr.right)
                    if r_right:
                        self.signed_regs.add(r_right)
                    self.signed_regs.add(stmt.dest.name)
                if expr.bit_width == 32:
                    self.width_32_regs.add(stmt.dest.name)
        elif isinstance(stmt, Branch):
            cond = stmt.cond
            if isinstance(cond, BinaryExpr):
                if cond.op in (Op.LT, Op.LE, Op.GT, Op.GE):
                    r_left = extract_reg(cond.left)
                    if r_left:
                        self.signed_regs.add(r_left)
                    r_right = extract_reg(cond.right)
                    if r_right:
                        self.signed_regs.add(r_right)
