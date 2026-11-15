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
    def __init__(self, mode: int = 64, arch: str = "x86"):
        self.mode = mode
        self.arch = arch.lower()
        if self.arch in ("arm64", "aarch64"):
            self.md = Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
        else:
            arch_mode = CS_MODE_64 if mode == 64 else CS_MODE_32
            self.md = Cs(CS_ARCH_X86, arch_mode)
        self.md.detail = True

    def disassemble(self, code: bytes, base_address: int = 0x1000) -> List[DecodedInsn]:
        results = []
        is_arm64 = self.arch in ("arm64", "aarch64")
        reg_type = capstone.arm64.ARM64_OP_REG if is_arm64 else capstone.x86.X86_OP_REG
        imm_type = capstone.arm64.ARM64_OP_IMM if is_arm64 else capstone.x86.X86_OP_IMM
        mem_type = capstone.arm64.ARM64_OP_MEM if is_arm64 else capstone.x86.X86_OP_MEM

        for insn in self.md.disasm(code, base_address):
            operands: List[DecodedOperand] = []
            for op in insn.operands:
                size_bits = getattr(op, "size", 0) * 8
                if size_bits == 0:
                    size_bits = 64
                if op.type == reg_type:
                    reg_name = insn.reg_name(op.reg)
                    if is_arm64:
                        if reg_name.startswith("w"):
                            size_bits = 32
                        elif reg_name.startswith("x") or reg_name == "sp":
                            size_bits = 64
                    operands.append(DecodedOperand("reg", reg_name, size_bits))
                elif op.type == imm_type:
                    operands.append(DecodedOperand("imm", op.imm, size_bits))
                elif op.type == mem_type:
                    base = insn.reg_name(op.mem.base) if op.mem.base != 0 else None
                    index = insn.reg_name(op.mem.index) if getattr(op.mem, "index", 0) != 0 else None
                    scale = getattr(op.mem, "scale", 1)
                    disp = getattr(op.mem, "disp", 0)
                    mem_ref = MemRef(
                        base=base,
                        index=index,
                        scale=scale,
                        disp=disp,
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
