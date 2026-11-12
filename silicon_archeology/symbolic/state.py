"""
Symbolic execution state mapping registers and flags to Z3 BitVec terms.
"""

from typing import Dict, Optional, Set
import z3
from silicon_archeology.symbolic.memory import SymbolicMemory
from silicon_archeology.ir.types import normalize_reg


class SymbolicState:
    def __init__(self, prefix: str = "init"):
        self.prefix = prefix
        self.registers: Dict[str, z3.BitVecRef] = {}
        self.memory = SymbolicMemory(name=f"mem_{prefix}")
        self.path_condition: z3.BoolRef = z3.BoolVal(True)
        self.inputs: Dict[str, z3.BitVecRef] = {}

        # Initialize canonical 64-bit registers as unconstrained symbolic variables
        canonical_regs = [
            "rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp",
            "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"
        ]
        for reg in canonical_regs:
            sym = z3.BitVec(f"{prefix}_{reg}", 64)
            self.registers[reg] = sym
            self.inputs[reg] = sym

        # Internal flag symbols
        for flag in ("__zf", "__cf", "__sf", "__of", "__pf", "__af"):
            self.registers[flag] = z3.BitVec(f"{prefix}_{flag}", 1)

    def clone(self) -> "SymbolicState":
        copy_st = SymbolicState(prefix=self.prefix)
        copy_st.registers = dict(self.registers)
        copy_st.memory = self.memory.clone()
        copy_st.path_condition = self.path_condition
        copy_st.inputs = dict(self.inputs)
        return copy_st

    def read_reg(self, name: str) -> z3.BitVecRef:
        canon, offset, width = normalize_reg(name)
        if canon not in self.registers:
            self.registers[canon] = z3.BitVec(f"{self.prefix}_{canon}", 64)

        full = self.registers[canon]
        if offset == 0 and width == 64:
            return z3.simplify(full)
        return z3.simplify(z3.Extract(offset + width - 1, offset, full))

    def write_reg(self, name: str, value: z3.BitVecRef) -> None:
        canon, offset, width = normalize_reg(name)
        if canon not in self.registers:
            self.registers[canon] = z3.BitVec(f"{self.prefix}_{canon}", 64)

        # Ensure value size matches requested width
        if value.size() < width:
            value = z3.ZeroExt(width - value.size(), value)
        elif value.size() > width:
            value = z3.Extract(width - 1, 0, value)

        if width == 64:
            self.registers[canon] = z3.simplify(value)
        elif width == 32:
            # x86-64 zeroes high 32 bits
            self.registers[canon] = z3.simplify(z3.ZeroExt(32, value))
        elif width == 16:
            high_48 = z3.Extract(63, 16, self.registers[canon])
            self.registers[canon] = z3.simplify(z3.Concat(high_48, value))
        elif width == 8:
            if offset == 0:
                high_56 = z3.Extract(63, 8, self.registers[canon])
                self.registers[canon] = z3.simplify(z3.Concat(high_56, value))
            elif offset == 8:  # AH, BH, CH, DH
                high_48 = z3.Extract(63, 16, self.registers[canon])
                low_8 = z3.Extract(7, 0, self.registers[canon])
                self.registers[canon] = z3.simplify(z3.Concat(high_48, value, low_8))

    def add_constraint(self, cond: z3.BoolRef) -> None:
        self.path_condition = z3.And(self.path_condition, cond)
