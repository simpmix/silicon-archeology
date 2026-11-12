"""
Micro-IR Expression and Statement definitions for symbolic lifting and synthesis.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Union, Dict, Any


class Op(Enum):
    # Arithmetic
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    UDIV = "u/"
    REM = "%"
    UREM = "u%"
    NEG = "neg"
    POPCNT = "popcnt"
    CTZ = "ctz"
    CLZ = "clz"
    BSWAP = "bswap"

    # Bitwise
    AND = "&"
    OR = "|"
    XOR = "^"
    NOT = "~"
    SHL = "<<"
    SHR = ">>"    # Logical right shift (zero fill)
    SAR = "s>>"   # Arithmetic right shift (sign fill)
    ROL = "rol"
    ROR = "ror"

    # Comparisons
    EQ = "=="
    NE = "!="
    LT = "<"      # Signed
    LE = "<="     # Signed
    GT = ">"      # Signed
    GE = ">="     # Signed
    ULT = "u<"    # Unsigned
    ULE = "u<="   # Unsigned
    UGT = "u>"    # Unsigned
    UGE = "u>="   # Unsigned

    # Condition flags
    OVERFLOW_ADD = "overflow_add"
    OVERFLOW_SUB = "overflow_sub"
    CARRY_ADD = "carry_add"
    CARRY_SUB = "carry_sub"


class Expr:
    bit_width: int

    def __repr__(self) -> str:
        return self.__str__()


@dataclass(frozen=True)
class Var(Expr):
    name: str
    bit_width: int = 64

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Constant(Expr):
    value: int
    bit_width: int = 64

    def __str__(self) -> str:
        if self.bit_width <= 64:
            mask = (1 << self.bit_width) - 1
            val = self.value & mask
            if val > 0xFFFF:
                return f"0x{val:X}_{self.bit_width}"
            return f"{val}_{self.bit_width}"
        return f"{self.value}_{self.bit_width}"


@dataclass(frozen=True)
class UnaryExpr(Expr):
    op: Op
    operand: Expr
    bit_width: int

    def __str__(self) -> str:
        return f"({self.op.value} {self.operand})"


@dataclass(frozen=True)
class BinaryExpr(Expr):
    op: Op
    left: Expr
    right: Expr
    bit_width: int

    def __str__(self) -> str:
        return f"({self.left} {self.op.value} {self.right})"


@dataclass(frozen=True)
class ExtractExpr(Expr):
    expr: Expr
    high: int
    low: int

    @property
    def bit_width(self) -> int:
        return self.high - self.low + 1

    def __str__(self) -> str:
        return f"{self.expr}[{self.high}:{self.low}]"


@dataclass(frozen=True)
class ConcatExpr(Expr):
    parts: List[Expr]
    bit_width: int

    def __str__(self) -> str:
        return f"concat({', '.join(str(p) for p in self.parts)})"


@dataclass(frozen=True)
class IteExpr(Expr):
    cond: Expr
    then_expr: Expr
    else_expr: Expr
    bit_width: int

    def __str__(self) -> str:
        return f"(if {self.cond} then {self.then_expr} else {self.else_expr})"


@dataclass(frozen=True)
class MemLoad(Expr):
    addr: Expr
    bit_width: int

    def __str__(self) -> str:
        return f"*((u{self.bit_width}*){self.addr})"


# --- Statements ---

class Stmt:
    pass


@dataclass
class Assign(Stmt):
    dest: Var
    expr: Expr

    def __str__(self) -> str:
        return f"{self.dest} := {self.expr}"


@dataclass
class MemStore(Stmt):
    addr: Expr
    expr: Expr
    bit_width: int

    def __str__(self) -> str:
        return f"*((u{self.bit_width}*){self.addr}) := {self.expr}"


@dataclass
class Branch(Stmt):
    cond: Expr
    target: str
    fallthrough: str

    def __str__(self) -> str:
        return f"if {self.cond} goto {self.target} else goto {self.fallthrough}"


@dataclass
class Jump(Stmt):
    target: str

    def __str__(self) -> str:
        return f"goto {self.target}"


@dataclass
class Return(Stmt):
    value: Optional[Expr] = None

    def __str__(self) -> str:
        return f"return {self.value}" if self.value else "return"


@dataclass
class Nop(Stmt):
    def __str__(self) -> str:
        return "nop"


@dataclass
class Comment(Stmt):
    text: str

    def __str__(self) -> str:
        return f"// {self.text}"
