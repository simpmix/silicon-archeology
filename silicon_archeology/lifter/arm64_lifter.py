"""
ARM64 (AArch64) to Micro-IR Lifter.
"""

from typing import List, Dict, Tuple, Optional, Any
from silicon_archeology.lifter.decoder import DecodedInsn, DecodedOperand, MemRef, Disassembler
from silicon_archeology.ir.types import normalize_reg
from silicon_archeology.ir.instructions import (
    Expr, Var, Constant, BinaryExpr, UnaryExpr, ExtractExpr, ConcatExpr,
    IteExpr, MemLoad, Stmt, Assign, MemStore, Branch, Jump, Return, Nop, Comment, Op
)
from silicon_archeology.ir.cfg import ControlFlowGraph, BasicBlock


class Arm64Lifter:
    def __init__(self):
        self.disasm = Disassembler(mode=64, arch="arm64")

    def lift_bytes(self, code: bytes, base_address: int = 0x1000) -> ControlFlowGraph:
        insns = self.disasm.disassemble(code, base_address)
        return self.lift_instructions(insns)

    def lift_instructions(self, insns: List[DecodedInsn]) -> ControlFlowGraph:
        cfg = ControlFlowGraph(entry_label=f"loc_{insns[0].address:x}" if insns else "entry")
        if not insns:
            return cfg

        leaders = {insns[0].address}
        addr_to_insn = {i.address: i for i in insns}

        for idx, insn in enumerate(insns):
            m = insn.mnemonic
            if m.startswith("b") or m in ("cbz", "cbnz"):
                if insn.operands and insn.operands[-1].type_name == "imm":
                    target = insn.operands[-1].value
                    if target in addr_to_insn:
                        leaders.add(target)
                if idx + 1 < len(insns):
                    leaders.add(insns[idx + 1].address)
            elif m == "ret":
                if idx + 1 < len(insns):
                    leaders.add(insns[idx + 1].address)

        current_bb: Optional[BasicBlock] = None
        last_cmp_info: Dict[str, Any] = {}

        for idx, insn in enumerate(insns):
            if insn.address in leaders:
                block_label = f"loc_{insn.address:x}"
                if current_bb is not None and current_bb.terminator is None:
                    current_bb.add_stmt(Jump(block_label))
                current_bb = cfg.get_or_create_block(block_label)

            stmts = self._lift_instruction(insn, idx, insns, last_cmp_info)
            for stmt in stmts:
                current_bb.add_stmt(stmt)

        cfg.finalize_edges()
        cfg.compute_dominators()
        cfg.detect_loops()
        return cfg

    def _resolve_operand(self, op: DecodedOperand) -> Expr:
        if op.type_name == "imm":
            val = op.value & ((1 << op.size_bits) - 1) if op.value < 0 else op.value
            return Constant(val, op.size_bits)
        elif op.type_name == "reg":
            canon, offset, width = normalize_reg(op.value)
            full_w = max(width, 64)
            parent_var = Var(canon, full_w)
            if offset == 0 and width == full_w:
                return parent_var
            return ExtractExpr(parent_var, offset + width - 1, offset)
        elif op.type_name == "mem":
            addr_expr = self._resolve_mem_addr(op.value)
            return MemLoad(addr_expr, op.size_bits)
        raise ValueError(f"Unknown operand type: {op}")

    def _resolve_mem_addr(self, mem: MemRef) -> Expr:
        parts: List[Expr] = []
        if mem.base:
            canon, _, _ = normalize_reg(mem.base)
            parts.append(Var(canon, 64))
        if mem.index:
            canon, _, _ = normalize_reg(mem.index)
            idx_var = Var(canon, 64)
            if mem.scale > 1:
                parts.append(BinaryExpr(Op.MUL, idx_var, Constant(mem.scale, 64), 64))
            else:
                parts.append(idx_var)

        if not parts:
            return Constant(mem.disp, 64)

        expr = parts[0]
        for p in parts[1:]:
            expr = BinaryExpr(Op.ADD, expr, p, 64)

        if mem.disp != 0:
            if mem.disp > 0:
                expr = BinaryExpr(Op.ADD, expr, Constant(mem.disp, 64), 64)
            else:
                expr = BinaryExpr(Op.SUB, expr, Constant(-mem.disp, 64), 64)
        return expr

    def _assign_to_dest(self, dest_op: DecodedOperand, expr: Expr) -> List[Stmt]:
        if dest_op.type_name == "reg":
            canon, offset, width = normalize_reg(dest_op.value)
            if canon in ("xzr", "wzr"):
                return []  # Discard write to zero register
            full_w = max(width, 64)
            parent_var = Var(canon, full_w)
            if expr.bit_width > width:
                expr = ExtractExpr(expr, width - 1, 0)
            elif expr.bit_width < width:
                expr = ConcatExpr([Constant(0, width - expr.bit_width), expr], width)

            if width == 64:
                return [Assign(parent_var, expr)]
            elif width == 32:
                # ARM64 zero-extends 32-bit register writes to 64-bit
                zero_ext = ConcatExpr([Constant(0, 32), expr], 64)
                return [Assign(parent_var, zero_ext)]
            return [Assign(parent_var, expr)]
        elif dest_op.type_name == "mem":
            addr = self._resolve_mem_addr(dest_op.value)
            if expr.bit_width > dest_op.size_bits:
                expr = ExtractExpr(expr, dest_op.size_bits - 1, 0)
            return [MemStore(addr, expr, dest_op.size_bits)]
        return []

    def _lift_instruction(
        self, insn: DecodedInsn, idx: int, all_insns: List[DecodedInsn],
        last_cmp_info: Dict[str, Any]
    ) -> List[Stmt]:
        stmts: List[Stmt] = [Comment(f"{insn.mnemonic} {insn.op_str}")]
        m = insn.mnemonic
        ops = insn.operands

        if m in ("mov", "movz"):
            if len(ops) >= 2:
                src = self._resolve_operand(ops[1])
                stmts.extend(self._assign_to_dest(ops[0], src))

        elif m == "mvn":
            src = self._resolve_operand(ops[1])
            res = UnaryExpr(Op.NOT, src, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "neg":
            src = self._resolve_operand(ops[1])
            res = UnaryExpr(Op.NEG, src, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m in ("add", "adds"):
            # 3 operands: dst, src1, src2
            src1 = self._resolve_operand(ops[1])
            src2 = self._resolve_operand(ops[2])
            w = ops[0].size_bits
            res = BinaryExpr(Op.ADD, src1, src2, w)
            stmts.extend(self._assign_to_dest(ops[0], res))
            if m == "adds":
                last_cmp_info["type"] = "cmp"
                last_cmp_info["op0"] = res
                last_cmp_info["op1"] = Constant(0, w)

        elif m in ("sub", "subs"):
            src1 = self._resolve_operand(ops[1])
            src2 = self._resolve_operand(ops[2])
            w = ops[0].size_bits
            res = BinaryExpr(Op.SUB, src1, src2, w)
            stmts.extend(self._assign_to_dest(ops[0], res))
            if m == "subs":
                last_cmp_info["type"] = "cmp"
                last_cmp_info["op0"] = src1
                last_cmp_info["op1"] = src2

        elif m in ("and", "ands", "orr", "eor"):
            src1 = self._resolve_operand(ops[1])
            src2 = self._resolve_operand(ops[2])
            w = ops[0].size_bits
            op_map = {"and": Op.AND, "ands": Op.AND, "orr": Op.OR, "eor": Op.XOR}
            res = BinaryExpr(op_map[m], src1, src2, w)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m in ("lsl", "lsr", "asr", "ror"):
            src1 = self._resolve_operand(ops[1])
            src2 = self._resolve_operand(ops[2])
            w = ops[0].size_bits
            op_map = {"lsl": Op.SHL, "lsr": Op.SHR, "asr": Op.SAR, "ror": Op.ROR}
            res = BinaryExpr(op_map[m], src1, src2, w)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "mul":
            src1 = self._resolve_operand(ops[1])
            src2 = self._resolve_operand(ops[2])
            res = BinaryExpr(Op.MUL, src1, src2, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "udiv":
            src1 = self._resolve_operand(ops[1])
            src2 = self._resolve_operand(ops[2])
            res = BinaryExpr(Op.UDIV, src1, src2, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "sdiv":
            src1 = self._resolve_operand(ops[1])
            src2 = self._resolve_operand(ops[2])
            res = BinaryExpr(Op.DIV, src1, src2, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "clz":
            src = self._resolve_operand(ops[1])
            res = UnaryExpr(Op.CLZ, src, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "rev":
            src = self._resolve_operand(ops[1])
            res = UnaryExpr(Op.BSWAP, src, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "cmp":
            op0 = self._resolve_operand(ops[0])
            op1 = self._resolve_operand(ops[1])
            last_cmp_info["type"] = "cmp"
            last_cmp_info["op0"] = op0
            last_cmp_info["op1"] = op1

        elif m == "csel":
            # csel dst, src1, src2, cond
            # Capstone op_str has cond as last word
            parts = insn.op_str.split(",")
            cc = parts[-1].strip().lower() if len(parts) >= 4 else "eq"
            cond = self._build_arm_cond(cc, last_cmp_info)
            src1 = self._resolve_operand(ops[1])
            src2 = self._resolve_operand(ops[2])
            ite = IteExpr(cond, src1, src2, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], ite))

        elif m == "cset":
            parts = insn.op_str.split(",")
            cc = parts[-1].strip().lower() if len(parts) >= 2 else "eq"
            cond = self._build_arm_cond(cc, last_cmp_info)
            w = ops[0].size_bits
            ite = IteExpr(cond, Constant(1, w), Constant(0, w), w)
            stmts.extend(self._assign_to_dest(ops[0], ite))

        elif m == "ldr":
            src = self._resolve_operand(ops[1])
            stmts.extend(self._assign_to_dest(ops[0], src))

        elif m == "str":
            src = self._resolve_operand(ops[0])
            addr = self._resolve_mem_addr(ops[1].value)
            stmts.append(MemStore(addr, src, ops[0].size_bits))

        elif m == "b":
            target = f"loc_{ops[0].value:x}"
            stmts.append(Jump(target))

        elif m.startswith("b."):
            cc = m[2:].lower()
            cond = self._build_arm_cond(cc, last_cmp_info)
            target = f"loc_{ops[0].value:x}"
            fallthrough = f"loc_{all_insns[idx + 1].address:x}" if idx + 1 < len(all_insns) else "end"
            stmts.append(Branch(cond, target, fallthrough))

        elif m == "cbz":
            reg = self._resolve_operand(ops[0])
            cond = BinaryExpr(Op.EQ, reg, Constant(0, reg.bit_width), 1)
            target = f"loc_{ops[1].value:x}"
            fallthrough = f"loc_{all_insns[idx + 1].address:x}" if idx + 1 < len(all_insns) else "end"
            stmts.append(Branch(cond, target, fallthrough))

        elif m == "cbnz":
            reg = self._resolve_operand(ops[0])
            cond = BinaryExpr(Op.NE, reg, Constant(0, reg.bit_width), 1)
            target = f"loc_{ops[1].value:x}"
            fallthrough = f"loc_{all_insns[idx + 1].address:x}" if idx + 1 < len(all_insns) else "end"
            stmts.append(Branch(cond, target, fallthrough))

        elif m == "ret":
            stmts.append(Return(Var("x0", 64)))

        elif m == "nop":
            stmts.append(Nop())

        else:
            stmts.append(Comment(f"UNHANDLED_ARM64: {insn}"))

        return stmts

    def _build_arm_cond(self, cc: str, cmp_info: Dict[str, Any]) -> Expr:
        op0 = cmp_info.get("op0")
        op1 = cmp_info.get("op1")
        if op0 is not None and op1 is not None:
            if cc in ("eq", "e"):
                return BinaryExpr(Op.EQ, op0, op1, 1)
            elif cc in ("ne",):
                return BinaryExpr(Op.NE, op0, op1, 1)
            elif cc in ("lt",):
                return BinaryExpr(Op.LT, op0, op1, 1)
            elif cc in ("le",):
                return BinaryExpr(Op.LE, op0, op1, 1)
            elif cc in ("gt",):
                return BinaryExpr(Op.GT, op0, op1, 1)
            elif cc in ("ge",):
                return BinaryExpr(Op.GE, op0, op1, 1)
            elif cc in ("lo", "cc"):
                return BinaryExpr(Op.ULT, op0, op1, 1)
            elif cc in ("ls",):
                return BinaryExpr(Op.ULE, op0, op1, 1)
            elif cc in ("hi",):
                return BinaryExpr(Op.UGT, op0, op1, 1)
            elif cc in ("hs", "cs"):
                return BinaryExpr(Op.UGE, op0, op1, 1)
        return Constant(1, 1)


ARM64Lifter = Arm64Lifter

