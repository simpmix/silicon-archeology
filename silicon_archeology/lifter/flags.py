"""
x86 Flag computation expressions for symbolic analysis and synthesis.
"""

from silicon_archeology.ir.instructions import (
    Expr, Var, Constant, BinaryExpr, UnaryExpr, ExtractExpr, Op
)


def flag_zero(res: Expr) -> Expr:
    """ZF is 1 if res == 0, else 0."""
    return BinaryExpr(Op.EQ, res, Constant(0, res.bit_width), 1)


def flag_sign(res: Expr) -> Expr:
    """SF is the most significant bit of res."""
    return ExtractExpr(res, res.bit_width - 1, res.bit_width - 1)


def flag_carry_add(a: Expr, b: Expr, res: Expr) -> Expr:
    """CF for ADD: unsigned overflow occurs when res < a."""
    return BinaryExpr(Op.ULT, res, a, 1)


def flag_carry_sub(a: Expr, b: Expr) -> Expr:
    """CF for SUB: unsigned borrow occurs when a < b."""
    return BinaryExpr(Op.ULT, a, b, 1)


def flag_overflow_add(a: Expr, b: Expr, res: Expr) -> Expr:
    """OF for ADD: signed overflow occurs when operands have same sign, result has different sign."""
    w = res.bit_width
    # ((a ^ ~b) & (a ^ res)) >> (w - 1)
    not_b = UnaryExpr(Op.NOT, b, w)
    xor1 = BinaryExpr(Op.XOR, a, not_b, w)
    xor2 = BinaryExpr(Op.XOR, a, res, w)
    and_expr = BinaryExpr(Op.AND, xor1, xor2, w)
    return ExtractExpr(and_expr, w - 1, w - 1)


def flag_overflow_sub(a: Expr, b: Expr, res: Expr) -> Expr:
    """OF for SUB: signed overflow occurs when operands have different signs, result differs from a."""
    w = res.bit_width
    xor1 = BinaryExpr(Op.XOR, a, b, w)
    xor2 = BinaryExpr(Op.XOR, a, res, w)
    and_expr = BinaryExpr(Op.AND, xor1, xor2, w)
    return ExtractExpr(and_expr, w - 1, w - 1)
