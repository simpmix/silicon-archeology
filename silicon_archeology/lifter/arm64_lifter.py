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
            is_branch = m == "b" or m.startswith("b.") or m in ("cbz", "cbnz", "tbz", "tbnz", "bl", "blr", "br")
            if is_branch:
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
            expr = Constant(val, op.size_bits)
        elif op.type_name == "reg":
            canon, offset, width = normalize_reg(op.value)
            full_w = max(width, 64)
            parent_var = Var(canon, full_w)
            if offset == 0 and width == full_w:
                expr = parent_var
            else:
                expr = ExtractExpr(parent_var, offset + width - 1, offset)
        elif op.type_name == "mem":
            addr_expr = self._resolve_mem_addr(op.value)
            expr = MemLoad(addr_expr, op.size_bits)
        else:
            raise ValueError(f"Unknown operand type: {op}")

        # Apply extension if present (e.g. uxtw, sxtw, uxtb, etc.)
        if op.ext_type != 0:
            ext = op.ext_type
            w = expr.bit_width
            if ext in (1, 5) and w > 8:  # byte
                slice_expr = ExtractExpr(expr, 7, 0)
                if ext == 1:
                    expr = ConcatExpr([Constant(0, w - 8), slice_expr], w)
                else:
                    sign = ExtractExpr(slice_expr, 7, 7)
                    sign_pad = IteExpr(BinaryExpr(Op.EQ, sign, Constant(1, 1), 1), Constant((1 << (w - 8)) - 1, w - 8), Constant(0, w - 8), w - 8)
                    expr = ConcatExpr([sign_pad, slice_expr], w)
            elif ext in (2, 6) and w > 16:  # halfword
                slice_expr = ExtractExpr(expr, 15, 0)
                if ext == 2:
                    expr = ConcatExpr([Constant(0, w - 16), slice_expr], w)
                else:
                    sign = ExtractExpr(slice_expr, 15, 15)
                    sign_pad = IteExpr(BinaryExpr(Op.EQ, sign, Constant(1, 1), 1), Constant((1 << (w - 16)) - 1, w - 16), Constant(0, w - 16), w - 16)
                    expr = ConcatExpr([sign_pad, slice_expr], w)
            elif ext in (3, 7) and w > 32:  # word (32-bit)
                slice_expr = ExtractExpr(expr, 31, 0)
                if ext == 3:
                    expr = ConcatExpr([Constant(0, w - 32), slice_expr], w)
                else:
                    sign = ExtractExpr(slice_expr, 31, 31)
                    sign_pad = IteExpr(BinaryExpr(Op.EQ, sign, Constant(1, 1), 1), Constant((1 << (w - 32)) - 1, w - 32), Constant(0, w - 32), w - 32)
                    expr = ConcatExpr([sign_pad, slice_expr], w)

        # Apply shift if present
        if op.shift_type != 0 and op.shift_value > 0:
            w = expr.bit_width
            shift_amt = Constant(op.shift_value, w)
            if op.shift_type == 1:  # LSL
                expr = BinaryExpr(Op.SHL, expr, shift_amt, w)
            elif op.shift_type == 3:  # LSR
                expr = BinaryExpr(Op.SHR, expr, shift_amt, w)
            elif op.shift_type == 4:  # ASR
                expr = BinaryExpr(Op.SAR, expr, shift_amt, w)
            elif op.shift_type == 5:  # ROR
                expr = BinaryExpr(Op.ROR, expr, shift_amt, w)

        return expr

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

        elif m == "movk":
            if len(ops) >= 2:
                val = ops[1].value & 0xFFFF
                shift = ops[1].shift_value
                w = ops[0].size_bits
                cur = self._resolve_operand(ops[0])
                mask = ~((0xFFFF) << shift) & ((1 << w) - 1)
                cleared = BinaryExpr(Op.AND, cur, Constant(mask, w), w)
                res = BinaryExpr(Op.OR, cleared, Constant(val << shift, w), w)
                stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "mvn":
            src = self._resolve_operand(ops[1])
            res = UnaryExpr(Op.NOT, src, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "neg":
            src = self._resolve_operand(ops[1])
            res = UnaryExpr(Op.NEG, src, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m in ("add", "adds"):
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
            if m == "ands":
                last_cmp_info["type"] = "cmp"
                last_cmp_info["op0"] = res
                last_cmp_info["op1"] = Constant(0, w)

        elif m in ("bic", "bics"):
            src1 = self._resolve_operand(ops[1])
            src2 = self._resolve_operand(ops[2])
            w = ops[0].size_bits
            not_src2 = UnaryExpr(Op.NOT, src2, w)
            res = BinaryExpr(Op.AND, src1, not_src2, w)
            stmts.extend(self._assign_to_dest(ops[0], res))
            if m == "bics":
                last_cmp_info["type"] = "cmp"
                last_cmp_info["op0"] = res
                last_cmp_info["op1"] = Constant(0, w)

        elif m == "eon":
            src1 = self._resolve_operand(ops[1])
            src2 = self._resolve_operand(ops[2])
            w = ops[0].size_bits
            not_src2 = UnaryExpr(Op.NOT, src2, w)
            res = BinaryExpr(Op.XOR, src1, not_src2, w)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "orn":
            src1 = self._resolve_operand(ops[1])
            src2 = self._resolve_operand(ops[2])
            w = ops[0].size_bits
            not_src2 = UnaryExpr(Op.NOT, src2, w)
            res = BinaryExpr(Op.OR, src1, not_src2, w)
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

        elif m == "madd":
            src1 = self._resolve_operand(ops[1])
            src2 = self._resolve_operand(ops[2])
            src3 = self._resolve_operand(ops[3])
            w = ops[0].size_bits
            prod = BinaryExpr(Op.MUL, src1, src2, w)
            res = BinaryExpr(Op.ADD, src3, prod, w)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "msub":
            src1 = self._resolve_operand(ops[1])
            src2 = self._resolve_operand(ops[2])
            src3 = self._resolve_operand(ops[3])
            w = ops[0].size_bits
            prod = BinaryExpr(Op.MUL, src1, src2, w)
            res = BinaryExpr(Op.SUB, src3, prod, w)
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

        elif m == "rbit":
            src = self._resolve_operand(ops[1])
            w = ops[0].size_bits
            bits = [ExtractExpr(src, i, i) for i in range(w)]
            res = ConcatExpr(bits, w)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "cmp":
            op0 = self._resolve_operand(ops[0])
            op1 = self._resolve_operand(ops[1])
            last_cmp_info["type"] = "cmp"
            last_cmp_info["op0"] = op0
            last_cmp_info["op1"] = op1

        elif m == "tst":
            op0 = self._resolve_operand(ops[0])
            op1 = self._resolve_operand(ops[1])
            w = op0.bit_width
            and_expr = BinaryExpr(Op.AND, op0, op1, w)
            last_cmp_info["type"] = "cmp"
            last_cmp_info["op0"] = and_expr
            last_cmp_info["op1"] = Constant(0, w)

        elif m == "csel":
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

        elif m in ("cinc", "csinc"):
            parts = insn.op_str.split(",")
            cc = parts[-1].strip().lower()
            cond = self._build_arm_cond(cc, last_cmp_info)
            w = ops[0].size_bits
            if m == "cinc":
                src = self._resolve_operand(ops[1])
                res = IteExpr(cond, BinaryExpr(Op.ADD, src, Constant(1, w), w), src, w)
            else:
                src1 = self._resolve_operand(ops[1])
                src2 = self._resolve_operand(ops[2])
                res = IteExpr(cond, src1, BinaryExpr(Op.ADD, src2, Constant(1, w), w), w)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m in ("cinv", "csinv"):
            parts = insn.op_str.split(",")
            cc = parts[-1].strip().lower()
            cond = self._build_arm_cond(cc, last_cmp_info)
            w = ops[0].size_bits
            if m == "cinv":
                src = self._resolve_operand(ops[1])
                res = IteExpr(cond, UnaryExpr(Op.NOT, src, w), src, w)
            else:
                src1 = self._resolve_operand(ops[1])
                src2 = self._resolve_operand(ops[2])
                res = IteExpr(cond, src1, UnaryExpr(Op.NOT, src2, w), w)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m in ("cneg", "csneg"):
            parts = insn.op_str.split(",")
            cc = parts[-1].strip().lower()
            cond = self._build_arm_cond(cc, last_cmp_info)
            w = ops[0].size_bits
            if m == "cneg":
                src = self._resolve_operand(ops[1])
                res = IteExpr(cond, UnaryExpr(Op.NEG, src, w), src, w)
            else:
                src1 = self._resolve_operand(ops[1])
                src2 = self._resolve_operand(ops[2])
                res = IteExpr(cond, src1, UnaryExpr(Op.NEG, src2, w), w)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m in ("ldr", "ldrb", "ldrh", "ldrsw", "ldrsb", "ldrsh"):
            src = self._resolve_operand(ops[1])
            target_w = ops[0].size_bits
            if m in ("ldrsb", "ldrsh", "ldrsw"):
                # Sign extension
                src_w = 8 if m == "ldrsb" else (16 if m == "ldrsh" else 32)
                slice_val = ExtractExpr(src, src_w - 1, 0)
                sign = ExtractExpr(slice_val, src_w - 1, src_w - 1)
                pad_w = target_w - src_w
                sign_pad = IteExpr(BinaryExpr(Op.EQ, sign, Constant(1, 1), 1), Constant((1 << pad_w) - 1, pad_w), Constant(0, pad_w), pad_w)
                ext = ConcatExpr([sign_pad, slice_val], target_w)
                stmts.extend(self._assign_to_dest(ops[0], ext))
            else:
                stmts.extend(self._assign_to_dest(ops[0], src))

        elif m in ("str", "strb", "strh"):
            src = self._resolve_operand(ops[0])
            addr = self._resolve_mem_addr(ops[1].value)
            store_w = 8 if m == "strb" else (16 if m == "strh" else ops[0].size_bits)
            store_src = ExtractExpr(src, store_w - 1, 0) if src.bit_width > store_w else src
            stmts.append(MemStore(addr, store_src, store_w))

        elif m in ("sxtb", "sxth", "sxtw"):
            src = self._resolve_operand(ops[1])
            src_w = 8 if m == "sxtb" else (16 if m == "sxth" else 32)
            target_w = ops[0].size_bits
            slice_val = ExtractExpr(src, src_w - 1, 0)
            sign = ExtractExpr(slice_val, src_w - 1, src_w - 1)
            pad_w = target_w - src_w
            sign_pad = IteExpr(BinaryExpr(Op.EQ, sign, Constant(1, 1), 1), Constant((1 << pad_w) - 1, pad_w), Constant(0, pad_w), pad_w)
            ext = ConcatExpr([sign_pad, slice_val], target_w)
            stmts.extend(self._assign_to_dest(ops[0], ext))

        elif m in ("uxtb", "uxth"):
            src = self._resolve_operand(ops[1])
            src_w = 8 if m == "uxtb" else 16
            target_w = ops[0].size_bits
            slice_val = ExtractExpr(src, src_w - 1, 0)
            ext = ConcatExpr([Constant(0, target_w - src_w), slice_val], target_w)
            stmts.extend(self._assign_to_dest(ops[0], ext))

        elif m == "b":
            target = f"loc_{ops[0].value:x}"
            stmts.append(Jump(target))

        elif m.startswith("b."):
            cc = m[2:].lower()
            cond = self._build_arm_cond(cc, last_cmp_info)
            target = f"loc_{ops[0].value:x}"
            fallthrough = f"loc_{all_insns[idx + 1].address:x}" if idx + 1 < len(all_insns) else "end"
            stmts.append(Branch(cond, target, fallthrough))

        elif m in ("cbz", "cbnz"):
            reg = self._resolve_operand(ops[0])
            op_cmp = Op.EQ if m == "cbz" else Op.NE
            cond = BinaryExpr(op_cmp, reg, Constant(0, reg.bit_width), 1)
            target = f"loc_{ops[1].value:x}"
            fallthrough = f"loc_{all_insns[idx + 1].address:x}" if idx + 1 < len(all_insns) else "end"
            stmts.append(Branch(cond, target, fallthrough))

        elif m in ("tbz", "tbnz"):
            reg = self._resolve_operand(ops[0])
            bit_idx = ops[1].value
            bit_val = ExtractExpr(reg, bit_idx, bit_idx)
            op_cmp = Op.EQ if m == "tbz" else Op.NE
            cond = BinaryExpr(op_cmp, bit_val, Constant(0, 1), 1)
            target = f"loc_{ops[2].value:x}"
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
            elif cc in ("mi",):
                # Negative (SF=1)
                diff = BinaryExpr(Op.SUB, op0, op1, op0.bit_width)
                sign = ExtractExpr(diff, op0.bit_width - 1, op0.bit_width - 1)
                return BinaryExpr(Op.EQ, sign, Constant(1, 1), 1)
            elif cc in ("pl",):
                # Positive or zero (SF=0)
                diff = BinaryExpr(Op.SUB, op0, op1, op0.bit_width)
                sign = ExtractExpr(diff, op0.bit_width - 1, op0.bit_width - 1)
                return BinaryExpr(Op.EQ, sign, Constant(0, 1), 1)
        return Constant(1, 1)


ARM64Lifter = Arm64Lifter
