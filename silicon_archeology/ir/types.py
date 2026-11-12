"""
Intermediate Representation types and register definitions for x86/x86_64.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Union, Dict, Tuple


class RegWidth(Enum):
    BYTE = 8
    WORD = 16
    DWORD = 32
    QWORD = 64


class Flag(Enum):
    CF = "CF"  # Carry flag
    ZF = "ZF"  # Zero flag
    SF = "SF"  # Sign flag
    OF = "OF"  # Overflow flag
    PF = "PF"  # Parity flag
    AF = "AF"  # Auxiliary carry flag


# Register mapping to (parent 64-bit register, bit offset, bit size)
X86_REGISTER_MAP: Dict[str, Tuple[str, int, int]] = {
    # 64-bit
    "rax": ("rax", 0, 64),
    "rbx": ("rbx", 0, 64),
    "rcx": ("rcx", 0, 64),
    "rdx": ("rdx", 0, 64),
    "rsi": ("rsi", 0, 64),
    "rdi": ("rdi", 0, 64),
    "rbp": ("rbp", 0, 64),
    "rsp": ("rsp", 0, 64),
    "r8":  ("r8",  0, 64),
    "r9":  ("r9",  0, 64),
    "r10": ("r10", 0, 64),
    "r11": ("r11", 0, 64),
    "r12": ("r12", 0, 64),
    "r13": ("r13", 0, 64),
    "r14": ("r14", 0, 64),
    "r15": ("r15", 0, 64),

    # 32-bit (x86-64 zeroes upper 32 bits on 32-bit write)
    "eax": ("rax", 0, 32),
    "ebx": ("rbx", 0, 32),
    "ecx": ("rcx", 0, 32),
    "edx": ("rdx", 0, 32),
    "esi": ("rsi", 0, 32),
    "edi": ("rdi", 0, 32),
    "ebp": ("rbp", 0, 32),
    "esp": ("rsp", 0, 32),
    "r8d":  ("r8",  0, 32),
    "r9d":  ("r9",  0, 32),
    "r10d": ("r10", 0, 32),
    "r11d": ("r11", 0, 32),
    "r12d": ("r12", 0, 32),
    "r13d": ("r13", 0, 32),
    "r14d": ("r14", 0, 32),
    "r15d": ("r15", 0, 32),

    # 16-bit
    "ax": ("rax", 0, 16),
    "bx": ("rbx", 0, 16),
    "cx": ("rcx", 0, 16),
    "dx": ("rdx", 0, 16),
    "si": ("rsi", 0, 16),
    "di": ("rdi", 0, 16),
    "bp": ("rbp", 0, 16),
    "sp": ("rsp", 0, 16),
    "r8w":  ("r8",  0, 16),
    "r9w":  ("r9",  0, 16),
    "r10w": ("r10", 0, 16),
    "r11w": ("r11", 0, 16),
    "r12w": ("r12", 0, 16),
    "r13w": ("r13", 0, 16),
    "r14w": ("r14", 0, 16),
    "r15w": ("r15", 0, 16),

    # 8-bit low
    "al": ("rax", 0, 8),
    "bl": ("rbx", 0, 8),
    "cl": ("rcx", 0, 8),
    "dl": ("rdx", 0, 8),
    "sil": ("rsi", 0, 8),
    "dil": ("rdi", 0, 8),
    "bpl": ("rbp", 0, 8),
    "spl": ("rsp", 0, 8),
    "r8b":  ("r8",  0, 8),
    "r9b":  ("r9",  0, 8),
    "r10b": ("r10", 0, 8),
    "r11b": ("r11", 0, 8),
    "r12b": ("r12", 0, 8),
    "r13b": ("r13", 0, 8),
    "r14b": ("r14", 0, 8),
    "r15b": ("r15", 0, 8),

    # 8-bit high (legacy)
    "ah": ("rax", 8, 8),
    "bh": ("rbx", 8, 8),
    "ch": ("rcx", 8, 8),
    "dh": ("rdx", 8, 8),
}


def normalize_reg(name: str) -> Tuple[str, int, int]:
    """Returns (canonical_64bit_name, offset_bits, width_bits)."""
    clean = name.lower().strip()
    if clean in X86_REGISTER_MAP:
        return X86_REGISTER_MAP[clean]
    # Default fallback
    return (clean, 0, 64)
