"""
Idiom detection and transformation into modern Rust standard library primitives.
"""

from typing import Optional, List
from silicon_archeology.ir.cfg import ControlFlowGraph
from silicon_archeology.synthesizer.ast import (
    RustFunction, RustParam, RustStmt, RustReturn, RustLet,
    RustAssignStmt, RustExpr, RustIdent, RustLiteral, RustBinaryOp,
    RustMethodCall, RustCall, RustWhile, RustIfStmt, RustCast,
    RustUnaryOp, RustIfExpr
)


class IdiomMatcher:
    """Detects algorithmic idioms in CFGs and synthesizes modern idiomatic Rust."""

    @staticmethod
    def match_isolate_lowest_bit(cfg: ControlFlowGraph) -> Optional[RustFunction]:
        """Matches x & -x (isolate lowest set bit)."""
        # Look for NEG followed by AND
        if len(cfg.blocks) == 1:
            stmts_str = " ".join(str(s) for s in list(cfg.blocks.values())[0].stmts).lower()
            if "neg" in stmts_str and ("&" in stmts_str or "and" in stmts_str):
                return RustFunction(
                    name="isolate_lowest_set_bit",
                    params=[RustParam("x", "u64")],
                    return_type="u64",
                    body=[
                        RustReturn(RustBinaryOp(
                            "&",
                            RustIdent("x"),
                            RustMethodCall(RustIdent("x"), "wrapping_neg")
                        ))
                    ],
                    doc_comment="Isolates the lowest set bit using wrapping arithmetic:\n`x & x.wrapping_neg()`."
                )
        return None

    @staticmethod
    def match_popcount(cfg: ControlFlowGraph) -> Optional[RustFunction]:
        """Matches Kernighan popcount loop."""
        if len(cfg.loops) == 1:
            all_text = " ".join(str(s) for bb in cfg.blocks.values() for s in bb.stmts).lower()
            if ("&" in all_text and "-" in all_text) or "popcnt" in all_text:
                return RustFunction(
                    name="popcount",
                    params=[RustParam("n", "u64")],
                    return_type="u64",
                    body=[
                        RustReturn(RustCast(
                            RustMethodCall(RustIdent("n"), "count_ones"),
                            "u64"
                        ))
                    ],
                    doc_comment="Counts set bits using Brian Kernighan's algorithm / Rust `count_ones()`."
                )
        return None

    @staticmethod
    def match_branchless_min(cfg: ControlFlowGraph) -> Optional[RustFunction]:
        """Matches branchless min: cmp followed by cmov."""
        if len(cfg.blocks) == 1:
            all_text = " ".join(str(s) for bb in cfg.blocks.values() for s in bb.stmts).lower()
            if "cmov" in all_text:
                if "cmovg" in all_text or "<" in all_text:
                    # cmovg is signed greater
                    return RustFunction(
                        name="min_branchless",
                        params=[RustParam("a", "i64"), RustParam("b", "i64")],
                        return_type="i64",
                        body=[
                            RustReturn(RustCall("std::cmp::min", [RustIdent("a"), RustIdent("b")]))
                        ],
                        doc_comment="Computes minimum of two numbers via signed conditional move."
                    )
                elif "cmova" in all_text:
                    # cmova is unsigned above
                    return RustFunction(
                        name="min_branchless",
                        params=[RustParam("a", "u64"), RustParam("b", "u64")],
                        return_type="u64",
                        body=[
                            RustReturn(RustCall("std::cmp::min", [RustIdent("a"), RustIdent("b")]))
                        ],
                        doc_comment="Computes minimum of two numbers via unsigned conditional move."
                    )
                elif "cmovl" in all_text or ">" in all_text:
                    return RustFunction(
                        name="max_branchless",
                        params=[RustParam("a", "i64"), RustParam("b", "i64")],
                        return_type="i64",
                        body=[
                            RustReturn(RustCall("std::cmp::max", [RustIdent("a"), RustIdent("b")]))
                        ],
                        doc_comment="Computes maximum of two numbers via signed conditional move."
                    )
                elif "cmovb" in all_text:
                    return RustFunction(
                        name="max_branchless",
                        params=[RustParam("a", "u64"), RustParam("b", "u64")],
                        return_type="u64",
                        body=[
                            RustReturn(RustCall("std::cmp::max", [RustIdent("a"), RustIdent("b")]))
                        ],
                        doc_comment="Computes maximum of two numbers via unsigned conditional move."
                    )
        return None

    @staticmethod
    def match_clamp(cfg: ControlFlowGraph) -> Optional[RustFunction]:
        """Matches clamped integer bounds checks."""
        all_text = " ".join(str(s) for bb in cfg.blocks.values() for s in bb.stmts).lower()
        if "clamp" in all_text or all_text.count("cmov") >= 2:
            return RustFunction(
                name="clamp_val",
                params=[RustParam("val", "i64"), RustParam("min_val", "i64"), RustParam("max_val", "i64")],
                return_type="i64",
                body=[
                    RustReturn(RustMethodCall(
                        RustIdent("val"),
                        "clamp",
                        [RustIdent("min_val"), RustIdent("max_val")]
                    ))
                ],
                doc_comment="Clamps value into range [min_val, max_val]."
            )
        return None

    @staticmethod
    def match_byte_swap(cfg: ControlFlowGraph) -> Optional[RustFunction]:
        """Matches integer byte reversal (bswap)."""
        if len(cfg.blocks) == 1:
            all_text = " ".join(str(s) for bb in cfg.blocks.values() for s in bb.stmts).lower()
            if "bswap" in all_text:
                return RustFunction(
                    name="byte_swap",
                    params=[RustParam("x", "u64")],
                    return_type="u64",
                    body=[
                        RustReturn(RustMethodCall(RustIdent("x"), "swap_bytes"))
                    ],
                    doc_comment="Reverses the byte order of the integer using Rust std `swap_bytes()`."
                )
        return None

    @staticmethod
    def match_count_trailing_zeros(cfg: ControlFlowGraph) -> Optional[RustFunction]:
        """Matches count trailing zeros (tzcnt / bsf / ctz)."""
        if len(cfg.blocks) == 1:
            all_text = " ".join(str(s) for bb in cfg.blocks.values() for s in bb.stmts).lower()
            if "tzcnt" in all_text or "bsf" in all_text or "ctz" in all_text:
                return RustFunction(
                    name="count_trailing_zeros",
                    params=[RustParam("x", "u64")],
                    return_type="u64",
                    body=[
                        RustReturn(RustCast(RustMethodCall(RustIdent("x"), "trailing_zeros"), "u64"))
                    ],
                    doc_comment="Counts trailing zeros using Rust std `trailing_zeros()`."
                )
        return None

    @staticmethod
    def match_count_leading_zeros(cfg: ControlFlowGraph) -> Optional[RustFunction]:
        """Matches count leading zeros (lzcnt / bsr / clz)."""
        if len(cfg.blocks) == 1:
            all_text = " ".join(str(s) for bb in cfg.blocks.values() for s in bb.stmts).lower()
            if "lzcnt" in all_text or "bsr" in all_text or "clz" in all_text:
                return RustFunction(
                    name="count_leading_zeros",
                    params=[RustParam("x", "u64")],
                    return_type="u64",
                    body=[
                        RustReturn(RustCast(RustMethodCall(RustIdent("x"), "leading_zeros"), "u64"))
                    ],
                    doc_comment="Counts leading zeros using Rust std `leading_zeros()`."
                )
        return None

    @staticmethod
    def match_reset_lowest_set_bit(cfg: ControlFlowGraph) -> Optional[RustFunction]:
        """Matches x & (x - 1) / BLSR instruction (reset lowest set bit)."""
        if len(cfg.blocks) == 1:
            all_text = " ".join(str(s) for bb in cfg.blocks.values() for s in bb.stmts).lower()
            if "blsr" in all_text or ("dec" in all_text and "and" in all_text) or ("sub" in all_text and "1" in all_text and "and" in all_text):
                return RustFunction(
                    name="reset_lowest_set_bit",
                    params=[RustParam("x", "u64")],
                    return_type="u64",
                    body=[
                        RustReturn(RustBinaryOp(
                            "&",
                            RustIdent("x"),
                            RustMethodCall(RustIdent("x"), "wrapping_sub", [RustLiteral(1)])
                        ))
                    ],
                    doc_comment="Resets the lowest set bit using `x & x.wrapping_sub(1)` (BMI1 BLSR)."
                )
        return None

    @staticmethod
    def match_and_not(cfg: ControlFlowGraph) -> Optional[RustFunction]:
        """Matches bitwise AND NOT ((!a) & b) / ANDN instruction."""
        if len(cfg.blocks) == 1:
            all_text = " ".join(str(s) for bb in cfg.blocks.values() for s in bb.stmts).lower()
            if "andn" in all_text:
                return RustFunction(
                    name="and_not",
                    params=[RustParam("a", "u64"), RustParam("b", "u64")],
                    return_type="u64",
                    body=[
                        RustReturn(RustBinaryOp(
                            "&",
                            RustUnaryOp("!", RustIdent("a")),
                            RustIdent("b")
                        ))
                    ],
                    doc_comment="Computes bitwise `(!a) & b` using BMI1 ANDN."
                )
        return None

    @staticmethod
    def match_branchless_abs(cfg: ControlFlowGraph) -> Optional[RustFunction]:
        """Matches branchless absolute value: cqo/cdq followed by xor and sub."""
        if len(cfg.blocks) == 1:
            all_text = " ".join(str(s) for bb in cfg.blocks.values() for s in bb.stmts).lower()
            if ("cqo" in all_text or "cdq" in all_text) and "xor" in all_text and "sub" in all_text:
                return RustFunction(
                    name="branchless_abs",
                    params=[RustParam("x", "i64")],
                    return_type="i64",
                    body=[
                        RustReturn(RustMethodCall(
                            RustIdent("x"),
                            "wrapping_abs"
                        ))
                    ],
                    doc_comment="Computes branchless absolute value via sign-extension mask:\n`x.wrapping_abs()`."
                )
        return None

    @staticmethod
    def match_gcd(cfg: ControlFlowGraph) -> Optional[RustFunction]:
        """Matches Euclidean greatest common divisor."""
        if len(cfg.loops) == 1:
            all_text = " ".join(str(s) for bb in cfg.blocks.values() for s in bb.stmts).lower()
            if ("%" in all_text or "div" in all_text or "rem" in all_text) and ("test" in all_text or "cmp" in all_text or "jnz" in all_text or "jne" in all_text):
                return RustFunction(
                    name="gcd",
                    params=[RustParam("mut a", "u64"), RustParam("mut b", "u64")],
                    return_type="u64",
                    body=[
                        RustWhile(
                            cond=RustBinaryOp("!=", RustIdent("b"), RustLiteral(0)),
                            body=[
                                RustLet("temp", "u64", RustIdent("b"), is_mut=False),
                                RustAssignStmt(RustIdent("b"), RustBinaryOp("%", RustIdent("a"), RustIdent("b"))),
                                RustAssignStmt(RustIdent("a"), RustIdent("temp"))
                            ]
                        ),
                        RustReturn(RustIdent("a"))
                    ],
                    doc_comment="Euclidean Greatest Common Divisor (GCD) algorithm."
                )
        return None
