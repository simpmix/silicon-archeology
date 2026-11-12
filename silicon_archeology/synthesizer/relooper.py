"""
Relooper CFG structuring algorithm to synthesize clean high-level Rust control flow.
"""

from typing import Dict, List, Set, Optional, Tuple, Any
from silicon_archeology.ir.cfg import ControlFlowGraph, BasicBlock, Loop
from silicon_archeology.ir.instructions import (
    Stmt, Assign, MemStore, Branch, Jump, Return, Nop, Comment,
    Expr, Var, Constant, BinaryExpr, UnaryExpr, ExtractExpr, Op, ConcatExpr,
    IteExpr, MemLoad
)
from silicon_archeology.synthesizer.ast import (
    RustStmt, RustLet, RustAssignStmt, RustReturn, RustWhile,
    RustLoop, RustIfStmt, RustBreak, RustContinue, RustComment,
    RustExpr, RustIdent, RustLiteral, RustBinaryOp, RustUnaryOp, RustCast,
    RustMethodCall, RustIfExpr, RustIndex
)


class Relooper:
    def __init__(self, cfg: ControlFlowGraph):
        self.cfg = cfg
        self.loop_headers = {lp.header: lp for lp in cfg.loops}

    def structure(self) -> List[RustStmt]:
        """Structures the CFG into a sequence of Rust statements."""
        if not self.cfg.blocks:
            return []

        visited: Set[str] = set()
        return self._structure_subgraph(self.cfg.entry_label, visited, stop_at=None)

    def _convert_expr_to_rust(self, expr: Expr) -> RustExpr:
        if isinstance(expr, Constant):
            return RustLiteral(expr.value)
        elif isinstance(expr, Var):
            canon = expr.name.lower()
            return RustIdent(canon)
        elif isinstance(expr, UnaryExpr):
            if expr.op == Op.POPCNT:
                inner = self._convert_expr_to_rust(expr.operand)
                return RustCast(RustMethodCall(inner, "count_ones"), "u64" if expr.bit_width == 64 else "u32")
            elif expr.op == Op.CTZ:
                inner = self._convert_expr_to_rust(expr.operand)
                return RustCast(RustMethodCall(inner, "trailing_zeros"), "u64" if expr.bit_width == 64 else "u32")
            elif expr.op == Op.CLZ:
                inner = self._convert_expr_to_rust(expr.operand)
                return RustCast(RustMethodCall(inner, "leading_zeros"), "u64" if expr.bit_width == 64 else "u32")
            elif expr.op == Op.BSWAP:
                inner = self._convert_expr_to_rust(expr.operand)
                return RustMethodCall(inner, "swap_bytes")
            op_map = {Op.NOT: "!", Op.NEG: "-"}
            return RustUnaryOp(op_map.get(expr.op, "!"), self._convert_expr_to_rust(expr.operand))
        elif isinstance(expr, BinaryExpr):
            if expr.op == Op.ROL:
                left_r = self._convert_expr_to_rust(expr.left)
                if isinstance(expr.right, Constant):
                    arg = RustLiteral(expr.right.value, type_suffix="u32")
                else:
                    arg = RustCast(self._convert_expr_to_rust(expr.right), "u32")
                return RustMethodCall(left_r, "rotate_left", [arg])
            elif expr.op == Op.ROR:
                left_r = self._convert_expr_to_rust(expr.left)
                if isinstance(expr.right, Constant):
                    arg = RustLiteral(expr.right.value, type_suffix="u32")
                else:
                    arg = RustCast(self._convert_expr_to_rust(expr.right), "u32")
                return RustMethodCall(left_r, "rotate_right", [arg])

            op_map = {
                Op.ADD: "+", Op.SUB: "-", Op.MUL: "*", Op.DIV: "/", Op.UDIV: "/",
                Op.REM: "%", Op.UREM: "%", Op.AND: "&", Op.OR: "|", Op.XOR: "^",
                Op.SHL: "<<", Op.SHR: ">>", Op.SAR: ">>",
                Op.EQ: "==", Op.NE: "!=", Op.LT: "<", Op.LE: "<=",
                Op.GT: ">", Op.GE: ">=", Op.ULT: "<", Op.ULE: "<=",
                Op.UGT: ">", Op.UGE: ">="
            }
            op_str = op_map.get(expr.op, "+")
            left_r = self._convert_expr_to_rust(expr.left)
            right_r = self._convert_expr_to_rust(expr.right)
            return RustBinaryOp(op_str, left_r, right_r)
        elif isinstance(expr, ExtractExpr):
            shift = expr.low
            inner_r = self._convert_expr_to_rust(expr.expr)
            if shift == 0 and expr.bit_width == 64:
                return inner_r
            mask = (1 << expr.bit_width) - 1
            if shift > 0:
                inner_r = RustBinaryOp(">>", inner_r, RustLiteral(shift))
            return RustBinaryOp("&", inner_r, RustLiteral(mask))
        elif isinstance(expr, ConcatExpr):
            if len(expr.parts) == 2 and isinstance(expr.parts[0], Constant) and expr.parts[0].value == 0:
                low_r = self._convert_expr_to_rust(expr.parts[1])
                mask = (1 << expr.parts[1].bit_width) - 1
                return RustBinaryOp("&", low_r, RustLiteral(mask))
            acc = self._convert_expr_to_rust(expr.parts[0])
            for p in expr.parts[1:]:
                if p.bit_width >= 64:
                    acc = RustCast(acc, "u128")
                    acc = RustBinaryOp("<<", acc, RustLiteral(p.bit_width))
                    p_rust = RustCast(self._convert_expr_to_rust(p), "u128")
                    acc = RustBinaryOp("|", acc, p_rust)
                else:
                    acc = RustBinaryOp("<<", acc, RustLiteral(p.bit_width))
                    acc = RustBinaryOp("|", acc, self._convert_expr_to_rust(p))
            if expr.bit_width <= 64 and any(p.bit_width >= 64 for p in expr.parts[1:]):
                acc = RustCast(acc, "u64")
            return acc
        elif isinstance(expr, IteExpr):
            cond_r = self._convert_expr_to_rust(expr.cond)
            then_r = self._convert_expr_to_rust(expr.then_expr)
            else_r = self._convert_expr_to_rust(expr.else_expr)
            return RustIfExpr(cond=cond_r, then_expr=then_r, else_expr=else_r)
        elif isinstance(expr, MemLoad):
            addr_r = self._convert_expr_to_rust(expr.addr)
            return RustIndex(base=RustIdent("mem"), index=addr_r)
        return RustLiteral(0)

    def _convert_stmt_to_rust(self, stmt: Stmt) -> Optional[RustStmt]:
        if isinstance(stmt, Assign):
            dest_name = stmt.dest.name.lower()
            if dest_name.startswith("__"):
                return None  # Drop intermediate flag assignments
            val_r = self._convert_expr_to_rust(stmt.expr)
            return RustAssignStmt(dest=RustIdent(dest_name), value=val_r)
        elif isinstance(stmt, MemStore):
            addr_r = self._convert_expr_to_rust(stmt.addr)
            val_r = self._convert_expr_to_rust(stmt.expr)
            return RustAssignStmt(dest=RustIndex(base=RustIdent("mem"), index=addr_r), value=val_r)
        elif isinstance(stmt, Return):
            if stmt.value:
                return RustReturn(expr=self._convert_expr_to_rust(stmt.value))
            return RustReturn(expr=None)
        elif isinstance(stmt, Comment):
            return RustComment(text=stmt.text)
        return None

    def _structure_subgraph(
        self, curr_label: str, visited: Set[str], stop_at: Optional[str]
    ) -> List[RustStmt]:
        stmts: List[RustStmt] = []
        curr = curr_label

        while curr and curr != stop_at:
            if curr in visited:
                break
            visited.add(curr)

            bb = self.cfg.blocks.get(curr)
            if not bb:
                break

            # If this block is a loop header
            if curr in self.loop_headers:
                loop = self.loop_headers[curr]
                loop_stmts = self._structure_loop(loop, visited)
                stmts.extend(loop_stmts)
                # Next node is the loop exit
                exit_targets = [e[1] for e in loop.exits]
                if exit_targets:
                    curr = exit_targets[0]
                    continue
                else:
                    break

            # Add regular statements from basic block
            for s in bb.stmts:
                r_stmt = self._convert_stmt_to_rust(s)
                if r_stmt:
                    stmts.append(r_stmt)

            term = bb.terminator

            if isinstance(term, Return):
                break

            elif isinstance(term, Jump):
                curr = term.target

            elif isinstance(term, Branch):
                # If-else structure
                cond_r = self._convert_expr_to_rust(term.cond)
                target = term.target
                fallthrough = term.fallthrough

                # Check if target or fallthrough is stop_at
                then_visited = set(visited)
                else_visited = set(visited)

                then_stmts = self._structure_subgraph(target, then_visited, stop_at)
                else_stmts = self._structure_subgraph(fallthrough, else_visited, stop_at)

                stmts.append(RustIfStmt(cond=cond_r, then_body=then_stmts, else_body=else_stmts))
                visited.update(then_visited)
                visited.update(else_visited)
                break
            else:
                break

        return stmts

    def _structure_loop(self, loop: Loop, visited: Set[str]) -> List[RustStmt]:
        header_bb = self.cfg.blocks[loop.header]
        term = header_bb.terminator

        # Check if the loop is a clean `while (cond)`:
        # Header has a Branch where one branch stays in loop and the other exits
        if isinstance(term, Branch):
            target_in_loop = term.target in loop.body
            fall_in_loop = term.fallthrough in loop.body

            if target_in_loop and not fall_in_loop:
                # while (cond) { body }
                cond_r = self._convert_expr_to_rust(term.cond)
                body_visited = set(visited) | {loop.header}
                body_stmts = self._structure_subgraph(term.target, body_visited, stop_at=loop.header)
                return [RustWhile(cond=cond_r, body=body_stmts)]

            elif fall_in_loop and not target_in_loop:
                # while (!cond) { body }
                cond_r = RustUnaryOp("!", self._convert_expr_to_rust(term.cond))
                body_visited = set(visited) | {loop.header}
                body_stmts = self._structure_subgraph(term.fallthrough, body_visited, stop_at=loop.header)
                return [RustWhile(cond=cond_r, body=body_stmts)]

        # General loop construct
        loop_visited = set(visited) | {loop.header}
        # Extract body statements
        inner_stmts: List[RustStmt] = []
        for s in header_bb.stmts:
            r_stmt = self._convert_stmt_to_rust(s)
            if r_stmt:
                inner_stmts.append(r_stmt)

        if isinstance(term, Branch):
            cond_r = self._convert_expr_to_rust(term.cond)
            # Exit check
            if term.target not in loop.body:
                inner_stmts.append(RustIfStmt(
                    cond=cond_r,
                    then_body=[RustBreak()],
                    else_body=[]
                ))
                next_in_loop = term.fallthrough
            else:
                inner_stmts.append(RustIfStmt(
                    cond=RustUnaryOp("!", cond_r),
                    then_body=[RustBreak()],
                    else_body=[]
                ))
                next_in_loop = term.target

            rest_stmts = self._structure_subgraph(next_in_loop, loop_visited, stop_at=loop.header)
            inner_stmts.extend(rest_stmts)

        return [RustLoop(body=inner_stmts)]
