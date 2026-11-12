"""
Disassembler wrapper using Capstone for x86 and x86_64 machine code.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import capstone
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_MODE_32


@dataclass
class DecodedOperand:
    type_name: str          # 'reg', 'imm', 'mem'
    value: Any              # reg name str, int imm, or MemRef
    size_bits: int          # 8, 16, 32, 64


@dataclass
class MemRef:
    base: Optional[str] = None
    index: Optional[str] = None
    scale: int = 1
    disp: int = 0
    size_bits: int = 64

    def __str__(self) -> str:
        parts = []
        if self.base:
            parts.append(self.base)
        if self.index:
            parts.append(f"{self.index}*{self.scale}" if self.scale > 1 else self.index)
        if self.disp != 0:
            parts.append(f"+{hex(self.disp)}" if self.disp > 0 else hex(self.disp))
        inner = " + ".join(parts).replace(" + -", " - ")
        return f"[{inner or '0'}]"


@dataclass
class DecodedInsn:
    address: int
    size: int
    mnemonic: str
    op_str: str
    bytes: bytes
    operands: List[DecodedOperand]

    def __str__(self) -> str:
        return f"0x{self.address:04x}: {self.mnemonic:7s} {self.op_str}"


class Disassembler:
    def __init__(self, mode: int = 64):
        arch_mode = CS_MODE_64 if mode == 64 else CS_MODE_32
        self.md = Cs(CS_ARCH_X86, arch_mode)
        self.md.detail = True
        self.mode = mode

    def disassemble(self, code: bytes, base_address: int = 0x1000) -> List[DecodedInsn]:
        results = []
        for insn in self.md.disasm(code, base_address):
            operands: List[DecodedOperand] = []
            for op in insn.operands:
                size_bits = op.size * 8 if op.size > 0 else 64
                if op.type == capstone.x86.X86_OP_REG:
                    reg_name = insn.reg_name(op.reg)
                    operands.append(DecodedOperand("reg", reg_name, size_bits))
                elif op.type == capstone.x86.X86_OP_IMM:
                    operands.append(DecodedOperand("imm", op.imm, size_bits))
                elif op.type == capstone.x86.X86_OP_MEM:
                    base = insn.reg_name(op.mem.base) if op.mem.base != 0 else None
                    index = insn.reg_name(op.mem.index) if op.mem.index != 0 else None
                    mem_ref = MemRef(
                        base=base,
                        index=index,
                        scale=op.mem.scale,
                        disp=op.mem.disp,
                        size_bits=size_bits
                    )
                    operands.append(DecodedOperand("mem", mem_ref, size_bits))

            results.append(DecodedInsn(
                address=insn.address,
                size=insn.size,
                mnemonic=insn.mnemonic.lower(),
                op_str=insn.op_str,
                bytes=bytes(insn.bytes),
                operands=operands
            ))
        return results
