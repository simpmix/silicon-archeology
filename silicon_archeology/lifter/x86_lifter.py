"""
x86 and x86_64 to Micro-IR Lifter.
"""

from typing import List, Dict, Tuple, Optional, Any
from silicon_archeology.lifter.decoder import DecodedInsn, DecodedOperand, MemRef, Disassembler
from silicon_archeology.ir.types import normalize_reg
from silicon_archeology.ir.instructions import (
    Expr, Var, Constant, BinaryExpr, UnaryExpr, ExtractExpr, ConcatExpr,
    IteExpr, MemLoad, Stmt, Assign, MemStore, Branch, Jump, Return, Nop, Comment, Op
)
from silicon_archeology.ir.cfg import ControlFlowGraph, BasicBlock
from silicon_archeology.lifter.flags import (
    flag_zero, flag_sign, flag_carry_add, flag_carry_sub,
    flag_overflow_add, flag_overflow_sub
)


class X86Lifter:
    def __init__(self, mode: int = 64):
        self.mode = mode
        self.disasm = Disassembler(mode=mode)

    def lift_bytes(self, code: bytes, base_address: int = 0x1000) -> ControlFlowGraph:
        insns = self.disasm.disassemble(code, base_address)
        return self.lift_instructions(insns)

    def lift_instructions(self, insns: List[DecodedInsn]) -> ControlFlowGraph:
        cfg = ControlFlowGraph(entry_label=f"loc_{insns[0].address:x}" if insns else "entry")
        if not insns:
            return cfg

        # Identify leader addresses for basic blocks:
        # 1. First instruction
        # 2. Target of any branch or jump
        # 3. Instruction following any branch, jump, or return
        leaders = {insns[0].address}
        addr_to_insn = {i.address: i for i in insns}

        for idx, insn in enumerate(insns):
            m = insn.mnemonic
            if m.startswith("j") or m == "jmp":
                if insn.operands and insn.operands[0].type_name == "imm":
                    target = insn.operands[0].value
                    if target in addr_to_insn:
                        leaders.add(target)
                if idx + 1 < len(insns):
                    leaders.add(insns[idx + 1].address)
            elif m == "ret":
                if idx + 1 < len(insns):
                    leaders.add(insns[idx + 1].address)

        # Build blocks
        current_bb: Optional[BasicBlock] = None
        last_cmp_info: Dict[str, Any] = {}  # Tracks last cmp/test for clean condition synthesis

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

    def _resolve_operand(self, op: DecodedOperand, next_ip: Optional[int] = None) -> Expr:
        if op.type_name == "imm":
            return Constant(op.value, op.size_bits)
        elif op.type_name == "reg":
            canon, offset, width = normalize_reg(op.value)
            parent_var = Var(canon, 64)
            if offset == 0 and width == 64:
                return parent_var
            return ExtractExpr(parent_var, offset + width - 1, offset)
        elif op.type_name == "mem":
            addr_expr = self._resolve_mem_addr(op.value, next_ip)
            return MemLoad(addr_expr, op.size_bits)
        raise ValueError(f"Unknown operand type: {op}")

    def _resolve_mem_addr(self, mem: MemRef, next_ip: Optional[int] = None) -> Expr:
        if mem.base == "rip" and next_ip is not None:
            return Constant(next_ip + mem.disp, 64)
        parts: List[Expr] = []
        if mem.base:
            if mem.base == "rip" and next_ip is not None:
                parts.append(Constant(next_ip, 64))
            else:
                canon, _, _ = normalize_reg(mem.base)
                parts.append(Var(canon, 64))
        if mem.index:
            canon, _, _ = normalize_reg(mem.index)
            idx_var = Var(canon, 64)
            if mem.scale > 1:
                idx_expr = BinaryExpr(Op.MUL, idx_var, Constant(mem.scale, 64), 64)
                parts.append(idx_expr)
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

    def _assign_to_dest(self, dest_op: DecodedOperand, expr: Expr, next_ip: Optional[int] = None) -> List[Stmt]:
        if dest_op.type_name == "reg":
            canon, offset, width = normalize_reg(dest_op.value)
            parent_var = Var(canon, 64)
            if expr.bit_width > width:
                expr = ExtractExpr(expr, width - 1, 0)
            elif expr.bit_width < width:
                expr = ConcatExpr([Constant(0, width - expr.bit_width), expr], width)

            if width == 64:
                return [Assign(parent_var, expr)]
            elif width == 32:
                # x86-64 zero-extends 32-bit register writes to 64-bit!
                zero_ext = ConcatExpr([Constant(0, 32), expr], 64)
                return [Assign(parent_var, zero_ext)]
            elif width == 16:
                # Retains top 48 bits: concat(parent[63:16], expr)
                high_part = ExtractExpr(parent_var, 63, 16)
                full = ConcatExpr([high_part, expr], 64)
                return [Assign(parent_var, full)]
            elif width == 8:
                if offset == 0:  # e.g., AL
                    high_part = ExtractExpr(parent_var, 63, 8)
                    full = ConcatExpr([high_part, expr], 64)
                    return [Assign(parent_var, full)]
                elif offset == 8:  # e.g., AH
                    high_part = ExtractExpr(parent_var, 63, 16)
                    low_part = ExtractExpr(parent_var, 7, 0)
                    full = ConcatExpr([high_part, expr, low_part], 64)
                    return [Assign(parent_var, full)]
        elif dest_op.type_name == "mem":
            addr = self._resolve_mem_addr(dest_op.value, next_ip)
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

        # Data Movement
        if m in ("mov", "movabs"):
            src = self._resolve_operand(ops[1])
            stmts.extend(self._assign_to_dest(ops[0], src))

        elif m == "movzx":
            src = self._resolve_operand(ops[1])
            dest_width = ops[0].size_bits
            zero_bits = dest_width - src.bit_width
            if zero_bits > 0:
                extended = ConcatExpr([Constant(0, zero_bits), src], dest_width)
            else:
                extended = src
            stmts.extend(self._assign_to_dest(ops[0], extended))

        elif m in ("movsx", "movsxd"):
            src = self._resolve_operand(ops[1])
            dest_width = ops[0].size_bits
            pad_len = dest_width - src.bit_width
            if pad_len > 0:
                sign_bit = ExtractExpr(src, src.bit_width - 1, src.bit_width - 1)
                sign_pads = IteExpr(
                    BinaryExpr(Op.EQ, sign_bit, Constant(1, 1), 1),
                    Constant((1 << pad_len) - 1, pad_len),
                    Constant(0, pad_len),
                    pad_len
                )
                extended = ConcatExpr([sign_pads, src], dest_width)
            else:
                extended = src
            stmts.extend(self._assign_to_dest(ops[0], extended))

        elif m == "lea":
            addr = self._resolve_mem_addr(ops[1].value)
            stmts.extend(self._assign_to_dest(ops[0], addr))

        # Arithmetic
        elif m in ("add", "sub", "and", "or", "xor"):
            dst_val = self._resolve_operand(ops[0])
            src_val = self._resolve_operand(ops[1])
            op_map = {
                "add": Op.ADD, "sub": Op.SUB, "and": Op.AND,
                "or": Op.OR, "xor": Op.XOR
            }
            res = BinaryExpr(op_map[m], dst_val, src_val, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))
            # Track flags update
            stmts.append(Assign(Var("__zf", 1), flag_zero(res)))
            stmts.append(Assign(Var("__sf", 1), flag_sign(res)))
            if m == "add":
                stmts.append(Assign(Var("__cf", 1), flag_carry_add(dst_val, src_val, res)))
                stmts.append(Assign(Var("__of", 1), flag_overflow_add(dst_val, src_val, res)))
            elif m == "sub":
                stmts.append(Assign(Var("__cf", 1), flag_carry_sub(dst_val, src_val)))
                stmts.append(Assign(Var("__of", 1), flag_overflow_sub(dst_val, src_val, res)))
            elif m in ("and", "or", "xor"):
                stmts.append(Assign(Var("__cf", 1), Constant(0, 1)))
                stmts.append(Assign(Var("__of", 1), Constant(0, 1)))

        elif m == "neg":
            dst_val = self._resolve_operand(ops[0])
            res = UnaryExpr(Op.NEG, dst_val, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))
            stmts.append(Assign(Var("__zf", 1), flag_zero(res)))
            stmts.append(Assign(Var("__sf", 1), flag_sign(res)))
            # CF is 1 if operand was non-zero
            stmts.append(Assign(Var("__cf", 1), BinaryExpr(Op.NE, dst_val, Constant(0, ops[0].size_bits), 1)))

        elif m == "not":
            dst_val = self._resolve_operand(ops[0])
            res = UnaryExpr(Op.NOT, dst_val, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "popcnt":
            src = self._resolve_operand(ops[1])
            res = UnaryExpr(Op.POPCNT, src, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))
            stmts.append(Assign(Var("__zf", 1), flag_zero(res)))

        elif m == "inc":
            dst_val = self._resolve_operand(ops[0])
            res = BinaryExpr(Op.ADD, dst_val, Constant(1, ops[0].size_bits), ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))
            stmts.append(Assign(Var("__zf", 1), flag_zero(res)))
            stmts.append(Assign(Var("__sf", 1), flag_sign(res)))

        elif m == "dec":
            dst_val = self._resolve_operand(ops[0])
            res = BinaryExpr(Op.SUB, dst_val, Constant(1, ops[0].size_bits), ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))
            stmts.append(Assign(Var("__zf", 1), flag_zero(res)))
            stmts.append(Assign(Var("__sf", 1), flag_sign(res)))

        elif m == "imul":
            if len(ops) == 1:
                # 1-operand: RDX:RAX = RAX * op0
                src = self._resolve_operand(ops[0])
                rax = Var("rax", 64)
                res = BinaryExpr(Op.MUL, rax, src, 64)
                stmts.append(Assign(rax, res))
            elif len(ops) == 2:
                dst_val = self._resolve_operand(ops[0])
                src_val = self._resolve_operand(ops[1])
                res = BinaryExpr(Op.MUL, dst_val, src_val, ops[0].size_bits)
                stmts.extend(self._assign_to_dest(ops[0], res))
            elif len(ops) == 3:
                src1 = self._resolve_operand(ops[1])
                src2 = self._resolve_operand(ops[2])
                res = BinaryExpr(Op.MUL, src1, src2, ops[0].size_bits)
                stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "mul":
            src = self._resolve_operand(ops[0])
            rax = Var("rax", 64)
            res = BinaryExpr(Op.MUL, rax, src, 64)
            stmts.append(Assign(rax, res))

        # Shifts
        elif m in ("shl", "sal", "shr", "sar"):
            dst_val = self._resolve_operand(ops[0])
            shift_val = self._resolve_operand(ops[1])
            op_map = {
                "shl": Op.SHL, "sal": Op.SHL,
                "shr": Op.SHR, "sar": Op.SAR
            }
            res = BinaryExpr(op_map[m], dst_val, shift_val, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))
            stmts.append(Assign(Var("__zf", 1), flag_zero(res)))
            stmts.append(Assign(Var("__sf", 1), flag_sign(res)))

        elif m in ("rol", "ror"):
            dst_val = self._resolve_operand(ops[0])
            shift_val = self._resolve_operand(ops[1])
            op_code = Op.ROL if m == "rol" else Op.ROR
            res = BinaryExpr(op_code, dst_val, shift_val, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "bswap":
            dst_val = self._resolve_operand(ops[0])
            w = ops[0].size_bits
            res = UnaryExpr(Op.BSWAP, dst_val, w)
            stmts.extend(self._assign_to_dest(ops[0], res))

        # BMI1 / BMI2 and Bit Manipulation
        elif m == "blsr":
            src_val = self._resolve_operand(ops[1])
            one = Constant(1, ops[0].size_bits)
            sub_val = BinaryExpr(Op.SUB, src_val, one, ops[0].size_bits)
            res = BinaryExpr(Op.AND, src_val, sub_val, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))
            stmts.append(Assign(Var("__zf", 1), flag_zero(res)))
            stmts.append(Assign(Var("__sf", 1), flag_sign(res)))
            stmts.append(Assign(Var("__cf", 1), BinaryExpr(Op.EQ, src_val, Constant(0, ops[0].size_bits), 1)))
            stmts.append(Assign(Var("__of", 1), Constant(0, 1)))

        elif m == "blsi":
            src_val = self._resolve_operand(ops[1])
            neg_val = UnaryExpr(Op.NEG, src_val, ops[0].size_bits)
            res = BinaryExpr(Op.AND, src_val, neg_val, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))
            stmts.append(Assign(Var("__zf", 1), flag_zero(res)))
            stmts.append(Assign(Var("__sf", 1), flag_sign(res)))
            stmts.append(Assign(Var("__cf", 1), BinaryExpr(Op.NE, src_val, Constant(0, ops[0].size_bits), 1)))
            stmts.append(Assign(Var("__of", 1), Constant(0, 1)))

        elif m == "blsmsk":
            src_val = self._resolve_operand(ops[1])
            one = Constant(1, ops[0].size_bits)
            sub_val = BinaryExpr(Op.SUB, src_val, one, ops[0].size_bits)
            res = BinaryExpr(Op.XOR, src_val, sub_val, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))
            stmts.append(Assign(Var("__zf", 1), Constant(0, 1)))
            stmts.append(Assign(Var("__sf", 1), flag_sign(res)))
            stmts.append(Assign(Var("__cf", 1), BinaryExpr(Op.EQ, src_val, Constant(0, ops[0].size_bits), 1)))
            stmts.append(Assign(Var("__of", 1), Constant(0, 1)))

        elif m == "bzhi":
            src_val = self._resolve_operand(ops[1])
            idx_raw = self._resolve_operand(ops[2])
            w = ops[0].size_bits
            idx_byte = ExtractExpr(idx_raw, 7, 0)
            idx_val = ConcatExpr([Constant(0, w - 8), idx_byte], w)
            one = Constant(1, w)
            shift = BinaryExpr(Op.SHL, one, idx_val, w)
            mask = BinaryExpr(Op.SUB, shift, one, w)
            masked = BinaryExpr(Op.AND, src_val, mask, w)
            res = IteExpr(BinaryExpr(Op.UGE, idx_val, Constant(w, w), 1), src_val, masked, w)
            stmts.extend(self._assign_to_dest(ops[0], res))
            stmts.append(Assign(Var("__zf", 1), flag_zero(res)))
            stmts.append(Assign(Var("__sf", 1), flag_sign(res)))
            stmts.append(Assign(Var("__cf", 1), BinaryExpr(Op.UGE, idx_val, Constant(w, w), 1)))
            stmts.append(Assign(Var("__of", 1), Constant(0, 1)))

        elif m == "andn":
            src1_val = self._resolve_operand(ops[1])
            src2_val = self._resolve_operand(ops[2])
            not_src1 = UnaryExpr(Op.NOT, src1_val, ops[0].size_bits)
            res = BinaryExpr(Op.AND, not_src1, src2_val, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], res))
            stmts.append(Assign(Var("__zf", 1), flag_zero(res)))
            stmts.append(Assign(Var("__sf", 1), flag_sign(res)))
            stmts.append(Assign(Var("__cf", 1), Constant(0, 1)))
            stmts.append(Assign(Var("__of", 1), Constant(0, 1)))

        elif m == "bextr":
            src_val = self._resolve_operand(ops[1])
            ctrl_val = self._resolve_operand(ops[2])
            w = ops[0].size_bits
            start_byte = ExtractExpr(ctrl_val, 7, 0)
            start_w = ConcatExpr([Constant(0, w - 8), start_byte], w)
            len_byte = ExtractExpr(ctrl_val, 15, 8)
            len_w = ConcatExpr([Constant(0, w - 8), len_byte], w)
            shifted = BinaryExpr(Op.SHR, src_val, start_w, w)
            one = Constant(1, w)
            mask_val = BinaryExpr(Op.SUB, BinaryExpr(Op.SHL, one, len_w, w), one, w)
            mask = IteExpr(
                BinaryExpr(Op.UGE, len_w, Constant(w, w), 1),
                Constant((1 << w) - 1, w),
                mask_val,
                w
            )
            res = IteExpr(
                BinaryExpr(Op.EQ, len_w, Constant(0, w), 1),
                Constant(0, w),
                BinaryExpr(Op.AND, shifted, mask, w),
                w
            )
            stmts.extend(self._assign_to_dest(ops[0], res))
            stmts.append(Assign(Var("__zf", 1), flag_zero(res)))
            stmts.append(Assign(Var("__cf", 1), Constant(0, 1)))
            stmts.append(Assign(Var("__of", 1), Constant(0, 1)))

        elif m in ("tzcnt", "bsf"):
            src_val = self._resolve_operand(ops[1])
            w = ops[0].size_bits
            res = UnaryExpr(Op.CTZ, src_val, w)
            stmts.extend(self._assign_to_dest(ops[0], res))
            stmts.append(Assign(Var("__zf", 1), flag_zero(res)))
            stmts.append(Assign(Var("__cf", 1), BinaryExpr(Op.EQ, src_val, Constant(0, w), 1)))

        elif m == "lzcnt":
            src_val = self._resolve_operand(ops[1])
            w = ops[0].size_bits
            res = UnaryExpr(Op.CLZ, src_val, w)
            stmts.extend(self._assign_to_dest(ops[0], res))
            stmts.append(Assign(Var("__zf", 1), flag_zero(res)))
            stmts.append(Assign(Var("__cf", 1), BinaryExpr(Op.EQ, src_val, Constant(0, w), 1)))

        elif m == "bsr":
            src_val = self._resolve_operand(ops[1])
            w = ops[0].size_bits
            clz_val = UnaryExpr(Op.CLZ, src_val, w)
            res = BinaryExpr(Op.SUB, Constant(w - 1, w), clz_val, w)
            stmts.extend(self._assign_to_dest(ops[0], res))
            stmts.append(Assign(Var("__zf", 1), BinaryExpr(Op.EQ, src_val, Constant(0, w), 1)))

        elif m in ("bt", "bts", "btr", "btc"):
            dst_val = self._resolve_operand(ops[0])
            bit_val = self._resolve_operand(ops[1])
            w = ops[0].size_bits
            one = Constant(1, w)
            bit_mask = BinaryExpr(Op.SHL, one, bit_val, w)
            test_bit = BinaryExpr(Op.AND, dst_val, bit_mask, w)
            stmts.append(Assign(Var("__cf", 1), BinaryExpr(Op.NE, test_bit, Constant(0, w), 1)))
            if m == "bts":
                new_dst = BinaryExpr(Op.OR, dst_val, bit_mask, w)
                stmts.extend(self._assign_to_dest(ops[0], new_dst))
            elif m == "btr":
                not_mask = UnaryExpr(Op.NOT, bit_mask, w)
                new_dst = BinaryExpr(Op.AND, dst_val, not_mask, w)
                stmts.extend(self._assign_to_dest(ops[0], new_dst))
            elif m == "btc":
                new_dst = BinaryExpr(Op.XOR, dst_val, bit_mask, w)
                stmts.extend(self._assign_to_dest(ops[0], new_dst))

        # Sign Extension & Division / Modulo
        elif m == "cqo":
            rax = Var("rax", 64)
            sign_bit = ExtractExpr(rax, 63, 63)
            sign_ext = IteExpr(
                BinaryExpr(Op.EQ, sign_bit, Constant(1, 1), 1),
                Constant(0xFFFFFFFFFFFFFFFF, 64),
                Constant(0, 64),
                64
            )
            stmts.append(Assign(Var("rdx", 64), sign_ext))

        elif m == "cdq":
            rax = Var("rax", 64)
            sign_bit = ExtractExpr(rax, 31, 31)
            sign_ext = IteExpr(
                BinaryExpr(Op.EQ, sign_bit, Constant(1, 1), 1),
                Constant(0x00000000FFFFFFFF, 64),
                Constant(0, 64),
                64
            )
            stmts.append(Assign(Var("rdx", 64), sign_ext))

        elif m == "cdqe":
            rax = Var("rax", 64)
            eax = ExtractExpr(rax, 31, 0)
            sign_bit = ExtractExpr(rax, 31, 31)
            pad = IteExpr(
                BinaryExpr(Op.EQ, sign_bit, Constant(1, 1), 1),
                Constant(0xFFFFFFFF, 32),
                Constant(0, 32),
                32
            )
            stmts.append(Assign(rax, ConcatExpr([pad, eax], 64)))

        elif m == "cbw":
            rax = Var("rax", 64)
            al = ExtractExpr(rax, 7, 0)
            sign_bit = ExtractExpr(rax, 7, 7)
            pad = IteExpr(
                BinaryExpr(Op.EQ, sign_bit, Constant(1, 1), 1),
                Constant(0xFF, 8),
                Constant(0, 8),
                8
            )
            ax = ConcatExpr([pad, al], 16)
            stmts.append(Assign(rax, ConcatExpr([ExtractExpr(rax, 63, 16), ax], 64)))

        elif m == "cwde":
            rax = Var("rax", 64)
            ax = ExtractExpr(rax, 15, 0)
            sign_bit = ExtractExpr(rax, 15, 15)
            pad = IteExpr(
                BinaryExpr(Op.EQ, sign_bit, Constant(1, 1), 1),
                Constant(0xFFFF, 16),
                Constant(0, 16),
                16
            )
            eax = ConcatExpr([pad, ax], 32)
            stmts.append(Assign(rax, ConcatExpr([Constant(0, 32), eax], 64)))

        elif m == "cwd":
            rax = Var("rax", 64)
            sign_bit = ExtractExpr(rax, 15, 15)
            sign_ext = IteExpr(
                BinaryExpr(Op.EQ, sign_bit, Constant(1, 1), 1),
                Constant(0xFFFF, 16),
                Constant(0, 16),
                16
            )
            rdx = Var("rdx", 64)
            stmts.append(Assign(rdx, ConcatExpr([ExtractExpr(rdx, 63, 16), sign_ext], 64)))

        elif m == "div":
            src = self._resolve_operand(ops[0])
            w = ops[0].size_bits
            rax = Var("rax", 64)
            rdx = Var("rdx", 64)
            if w == 64:
                quotient = BinaryExpr(Op.UDIV, rax, src, 64)
                remainder = BinaryExpr(Op.UREM, rax, src, 64)
                stmts.append(Assign(rax, quotient))
                stmts.append(Assign(rdx, remainder))
            elif w == 32:
                eax = ExtractExpr(rax, 31, 0)
                quotient = BinaryExpr(Op.UDIV, eax, src, 32)
                remainder = BinaryExpr(Op.UREM, eax, src, 32)
                stmts.extend(self._assign_to_dest(DecodedOperand("reg", "eax", 32), quotient))
                stmts.extend(self._assign_to_dest(DecodedOperand("reg", "edx", 32), remainder))

        elif m == "idiv":
            src = self._resolve_operand(ops[0])
            w = ops[0].size_bits
            rax = Var("rax", 64)
            rdx = Var("rdx", 64)
            if w == 64:
                quotient = BinaryExpr(Op.DIV, rax, src, 64)
                remainder = BinaryExpr(Op.REM, rax, src, 64)
                stmts.append(Assign(rax, quotient))
                stmts.append(Assign(rdx, remainder))
            elif w == 32:
                eax = ExtractExpr(rax, 31, 0)
                quotient = BinaryExpr(Op.DIV, eax, src, 32)
                remainder = BinaryExpr(Op.REM, eax, src, 32)
                stmts.extend(self._assign_to_dest(DecodedOperand("reg", "eax", 32), quotient))
                stmts.extend(self._assign_to_dest(DecodedOperand("reg", "edx", 32), remainder))

        # Data Exchange
        elif m == "xchg":
            op0_val = self._resolve_operand(ops[0])
            op1_val = self._resolve_operand(ops[1])
            tmp_var = Var(f"_tmp_swap_{idx}", ops[0].size_bits)
            stmts.append(Assign(tmp_var, op0_val))
            stmts.extend(self._assign_to_dest(ops[0], op1_val))
            stmts.extend(self._assign_to_dest(ops[1], tmp_var))

        # Conditional Set (SETcc)
        elif m.startswith("set") and len(m) in (4, 5):
            cc = m[3:]
            cond = self._build_branch_condition(cc, last_cmp_info)
            w = ops[0].size_bits
            one = Constant(1, w)
            zero = Constant(0, w)
            res = IteExpr(cond, one, zero, w)
            stmts.extend(self._assign_to_dest(ops[0], res))

        elif m == "push":
            src = self._resolve_operand(ops[0])
            rsp = Var("rsp", 64)
            w = ops[0].size_bits // 8
            new_rsp = BinaryExpr(Op.SUB, rsp, Constant(w, 64), 64)
            stmts.append(Assign(rsp, new_rsp))
            stmts.append(MemStore(new_rsp, src, ops[0].size_bits))

        elif m == "pop":
            rsp = Var("rsp", 64)
            w = ops[0].size_bits // 8
            loaded = MemLoad(rsp, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], loaded))
            new_rsp = BinaryExpr(Op.ADD, rsp, Constant(w, 64), 64)
            stmts.append(Assign(rsp, new_rsp))

        # Comparisons
        elif m == "cmp":
            op0 = self._resolve_operand(ops[0])
            op1 = self._resolve_operand(ops[1])
            last_cmp_info["type"] = "cmp"
            last_cmp_info["op0"] = op0
            last_cmp_info["op1"] = op1
            diff = BinaryExpr(Op.SUB, op0, op1, ops[0].size_bits)
            stmts.append(Assign(Var("__zf", 1), flag_zero(diff)))
            stmts.append(Assign(Var("__sf", 1), flag_sign(diff)))
            stmts.append(Assign(Var("__cf", 1), flag_carry_sub(op0, op1)))
            stmts.append(Assign(Var("__of", 1), flag_overflow_sub(op0, op1, diff)))

        elif m == "test":
            op0 = self._resolve_operand(ops[0])
            op1 = self._resolve_operand(ops[1])
            last_cmp_info["type"] = "test"
            last_cmp_info["op0"] = op0
            last_cmp_info["op1"] = op1
            res = BinaryExpr(Op.AND, op0, op1, ops[0].size_bits)
            stmts.append(Assign(Var("__zf", 1), flag_zero(res)))
            stmts.append(Assign(Var("__sf", 1), flag_sign(res)))
            stmts.append(Assign(Var("__cf", 1), Constant(0, 1)))
            stmts.append(Assign(Var("__of", 1), Constant(0, 1)))

        # Conditional Moves (CMOVcc)
        elif m.startswith("cmov"):
            cond = self._build_branch_condition(m[4:], last_cmp_info)
            dst_val = self._resolve_operand(ops[0])
            src_val = self._resolve_operand(ops[1])
            ite = IteExpr(cond, src_val, dst_val, ops[0].size_bits)
            stmts.extend(self._assign_to_dest(ops[0], ite))

        # Jumps and Control Flow
        elif m == "jmp":
            target = f"loc_{ops[0].value:x}"
            stmts.append(Jump(target))

        elif m.startswith("j") and m not in ("jmp",):
            cond_name = m[1:]
            cond = self._build_branch_condition(cond_name, last_cmp_info)
            target = f"loc_{ops[0].value:x}"
            fallthrough = f"loc_{all_insns[idx + 1].address:x}" if idx + 1 < len(all_insns) else "end"
            stmts.append(Branch(cond, target, fallthrough))

        elif m == "ret":
            # Convention: return rax
            stmts.append(Return(Var("rax", 64)))

        elif m == "nop":
            stmts.append(Nop())

        else:
            # Fallback representation
            stmts.append(Comment(f"UNHANDLED: {insn}"))

        return stmts

    def _build_branch_condition(self, cc: str, cmp_info: Dict[str, Any]) -> Expr:
        """
        Synthesizes a clean high-level boolean condition expression based on
        the condition code (cc) and the prior comparison/test instruction.
        """
        op0 = cmp_info.get("op0")
        op1 = cmp_info.get("op1")
        cmp_type = cmp_info.get("type", "cmp")

        if op0 is not None and op1 is not None:
            if cmp_type == "cmp":
                if cc in ("e", "z"):
                    return BinaryExpr(Op.EQ, op0, op1, 1)
                elif cc in ("ne", "nz"):
                    return BinaryExpr(Op.NE, op0, op1, 1)
                elif cc in ("l", "nge"):
                    return BinaryExpr(Op.LT, op0, op1, 1)
                elif cc in ("le", "ng"):
                    return BinaryExpr(Op.LE, op0, op1, 1)
                elif cc in ("g", "nle"):
                    return BinaryExpr(Op.GT, op0, op1, 1)
                elif cc in ("ge", "nl"):
                    return BinaryExpr(Op.GE, op0, op1, 1)
                elif cc in ("b", "c", "nae"):
                    return BinaryExpr(Op.ULT, op0, op1, 1)
                elif cc in ("be", "na"):
                    return BinaryExpr(Op.ULE, op0, op1, 1)
                elif cc in ("a", "nbe"):
                    return BinaryExpr(Op.UGT, op0, op1, 1)
                elif cc in ("ae", "nc", "nb"):
                    return BinaryExpr(Op.UGE, op0, op1, 1)
                elif cc == "s":
                    diff = BinaryExpr(Op.SUB, op0, op1, op0.bit_width)
                    return BinaryExpr(Op.LT, diff, Constant(0, op0.bit_width), 1)
                elif cc == "ns":
                    diff = BinaryExpr(Op.SUB, op0, op1, op0.bit_width)
                    return BinaryExpr(Op.GE, diff, Constant(0, op0.bit_width), 1)

            elif cmp_type == "test":
                and_expr = BinaryExpr(Op.AND, op0, op1, op0.bit_width)
                zero = Constant(0, op0.bit_width)
                if cc in ("e", "z"):
                    return BinaryExpr(Op.EQ, and_expr, zero, 1)
                elif cc in ("ne", "nz"):
                    return BinaryExpr(Op.NE, and_expr, zero, 1)
                elif cc == "s":
                    sign_bit = ExtractExpr(and_expr, op0.bit_width - 1, op0.bit_width - 1)
                    return BinaryExpr(Op.EQ, sign_bit, Constant(1, 1), 1)
                elif cc == "ns":
                    sign_bit = ExtractExpr(and_expr, op0.bit_width - 1, op0.bit_width - 1)
                    return BinaryExpr(Op.EQ, sign_bit, Constant(0, 1), 1)

        # Fallback to flag variables
        if cc in ("e", "z"):
            return BinaryExpr(Op.EQ, Var("__zf", 1), Constant(1, 1), 1)
        elif cc in ("ne", "nz"):
            return BinaryExpr(Op.EQ, Var("__zf", 1), Constant(0, 1), 1)
        elif cc in ("b", "c"):
            return BinaryExpr(Op.EQ, Var("__cf", 1), Constant(1, 1), 1)
        elif cc in ("ae", "nc"):
            return BinaryExpr(Op.EQ, Var("__cf", 1), Constant(0, 1), 1)
        elif cc == "s":
            return BinaryExpr(Op.EQ, Var("__sf", 1), Constant(1, 1), 1)
        elif cc == "ns":
            return BinaryExpr(Op.EQ, Var("__sf", 1), Constant(0, 1), 1)

        # Default true
        return Constant(1, 1)
