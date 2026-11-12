"""
Rust AST representation and code generator.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any


class RustASTNode:
    def emit(self, indent: int = 0) -> str:
        raise NotImplementedError


# --- Expressions ---

class RustExpr(RustASTNode):
    pass


@dataclass
class RustIdent(RustExpr):
    name: str

    def emit(self, indent: int = 0) -> str:
        return self.name


@dataclass
class RustLiteral(RustExpr):
    value: Any
    type_suffix: Optional[str] = None

    def emit(self, indent: int = 0) -> str:
        suffix = self.type_suffix or ""
        if isinstance(self.value, bool):
            return "true" if self.value else "false"
        if isinstance(self.value, int):
            if self.value < 0:
                val = self.value & 0xFFFFFFFFFFFFFFFF
                return f"0x{val:X}{suffix}"
            elif self.value > 0xFFFF:
                return f"0x{self.value:X}{suffix}"
            return f"{self.value}{suffix}"
        return f"{self.value}{suffix}"


@dataclass
class RustBinaryOp(RustExpr):
    op: str
    left: RustExpr
    right: RustExpr

    def emit(self, indent: int = 0) -> str:
        return f"({self.left.emit(indent)} {self.op} {self.right.emit(indent)})"


@dataclass
class RustUnaryOp(RustExpr):
    op: str
    operand: RustExpr

    def emit(self, indent: int = 0) -> str:
        return f"({self.op}{self.operand.emit(indent)})"


@dataclass
class RustCast(RustExpr):
    expr: RustExpr
    target_type: str

    def emit(self, indent: int = 0) -> str:
        return f"({self.expr.emit(indent)} as {self.target_type})"


@dataclass
class RustMethodCall(RustExpr):
    receiver: RustExpr
    method: str
    args: List[RustExpr] = field(default_factory=list)

    def emit(self, indent: int = 0) -> str:
        args_str = ", ".join(a.emit(indent) for a in self.args)
        return f"{self.receiver.emit(indent)}.{self.method}({args_str})"


@dataclass
class RustCall(RustExpr):
    function: str
    args: List[RustExpr] = field(default_factory=list)

    def emit(self, indent: int = 0) -> str:
        args_str = ", ".join(a.emit(indent) for a in self.args)
        return f"{self.function}({args_str})"


@dataclass
class RustIfExpr(RustExpr):
    cond: RustExpr
    then_expr: RustExpr
    else_expr: RustExpr

    def emit(self, indent: int = 0) -> str:
        return f"if {self.cond.emit(indent)} {{ {self.then_expr.emit(indent)} }} else {{ {self.else_expr.emit(indent)} }}"


@dataclass
class RustIndex(RustExpr):
    base: RustExpr
    index: RustExpr

    def emit(self, indent: int = 0) -> str:
        return f"{self.base.emit(indent)}[{self.index.emit(indent)}]"


# --- Statements ---

class RustStmt(RustASTNode):
    pass


@dataclass
class RustLet(RustStmt):
    name: str
    type_annot: Optional[str] = None
    value: Optional[RustExpr] = None
    is_mut: bool = False

    def emit(self, indent: int = 0) -> str:
        pad = "    " * indent
        mut_str = "mut " if self.is_mut else ""
        type_str = f": {self.type_annot}" if self.type_annot else ""
        val_str = f" = {self.value.emit(indent)}" if self.value else ""
        return f"{pad}let {mut_str}{self.name}{type_str}{val_str};"


@dataclass
class RustAssignStmt(RustStmt):
    dest: RustExpr
    value: RustExpr
    op: str = "="

    def emit(self, indent: int = 0) -> str:
        pad = "    " * indent
        return f"{pad}{self.dest.emit(indent)} {self.op} {self.value.emit(indent)};"


@dataclass
class RustReturn(RustStmt):
    expr: Optional[RustExpr] = None

    def emit(self, indent: int = 0) -> str:
        pad = "    " * indent
        if self.expr:
            return f"{pad}return {self.expr.emit(indent)};"
        return f"{pad}return;"


@dataclass
class RustWhile(RustStmt):
    cond: RustExpr
    body: List[RustStmt] = field(default_factory=list)

    def emit(self, indent: int = 0) -> str:
        pad = "    " * indent
        lines = [f"{pad}while {self.cond.emit(indent)} {{"]
        for s in self.body:
            lines.append(s.emit(indent + 1))
        lines.append(f"{pad}}}")
        return "\n".join(lines)


@dataclass
class RustLoop(RustStmt):
    body: List[RustStmt] = field(default_factory=list)

    def emit(self, indent: int = 0) -> str:
        pad = "    " * indent
        lines = [f"{pad}loop {{"]
        for s in self.body:
            lines.append(s.emit(indent + 1))
        lines.append(f"{pad}}}")
        return "\n".join(lines)


@dataclass
class RustIfStmt(RustStmt):
    cond: RustExpr
    then_body: List[RustStmt] = field(default_factory=list)
    else_body: List[RustStmt] = field(default_factory=list)

    def emit(self, indent: int = 0) -> str:
        pad = "    " * indent
        lines = [f"{pad}if {self.cond.emit(indent)} {{"]
        for s in self.then_body:
            lines.append(s.emit(indent + 1))
        if self.else_body:
            lines.append(f"{pad}}} else {{")
            for s in self.else_body:
                lines.append(s.emit(indent + 1))
        lines.append(f"{pad}}}")
        return "\n".join(lines)


@dataclass
class RustBreak(RustStmt):
    def emit(self, indent: int = 0) -> str:
        return f"{'    ' * indent}break;"


@dataclass
class RustContinue(RustStmt):
    def emit(self, indent: int = 0) -> str:
        return f"{'    ' * indent}continue;"


@dataclass
class RustComment(RustStmt):
    text: str

    def emit(self, indent: int = 0) -> str:
        return f"{'    ' * indent}// {self.text}"


@dataclass
class RustParam:
    name: str
    type_name: str


@dataclass
class RustFunction(RustASTNode):
    name: str
    params: List[RustParam] = field(default_factory=list)
    return_type: str = "u64"
    body: List[RustStmt] = field(default_factory=list)
    is_pub: bool = True
    doc_comment: Optional[str] = None

    def emit(self, indent: int = 0) -> str:
        pad = "    " * indent
        lines = []
        if self.doc_comment:
            for dline in self.doc_comment.splitlines():
                lines.append(f"{pad}/// {dline}")
        pub_str = "pub " if self.is_pub else ""
        params_str = ", ".join(f"{p.name}: {p.type_name}" for p in self.params)
        ret_str = f" -> {self.return_type}" if self.return_type != "()" else ""
        lines.append(f"{pad}{pub_str}fn {self.name}({params_str}){ret_str} {{")
        for stmt in self.body:
            lines.append(stmt.emit(indent + 1))
        lines.append(f"{pad}}}")
        return "\n".join(lines)
