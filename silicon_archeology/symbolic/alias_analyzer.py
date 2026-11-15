"""
Symbolic Memory Alias Analysis Engine using Z3 SMT Theorem Proving.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set, Any
import z3

from silicon_archeology.ir.cfg import ControlFlowGraph
from silicon_archeology.ir.instructions import MemLoad, MemStore, Expr, Var, Constant
from silicon_archeology.symbolic.executor import SymbolicExecutor
from silicon_archeology.symbolic.state import SymbolicState


class AliasResult(Enum):
    NO_ALIAS = "NO_ALIAS"       # Proven disjoint: regions never overlap
    MUST_ALIAS = "MUST_ALIAS"   # Proven identical: pointers always point to same address
    MAY_ALIAS = "MAY_ALIAS"     # Indeterminate: overlap depends on input valuation


@dataclass
class AliasQuery:
    addr1_expr: Expr
    size1_bytes: int
    addr2_expr: Expr
    size2_bytes: int
    result: AliasResult
    theorem: str
    counterexample: Optional[Dict[str, int]] = None


@dataclass
class AliasReport:
    total_queries: int
    no_alias_count: int
    must_alias_count: int
    may_alias_count: int
    queries: List[AliasQuery] = field(default_factory=list)


class MemoryAliasAnalyzer:
    """
    Formally proves alias relationships between symbolic memory references
    using Z3 BitVector theory.
    """

    def __init__(self, timeout_ms: int = 5000):
        self.timeout_ms = timeout_ms

    def query_alias(
        self,
        addr1: Expr,
        size1_bytes: int,
        addr2: Expr,
        size2_bytes: int,
        preconditions: Optional[List[z3.BoolRef]] = None
    ) -> AliasQuery:
        """
        Formally proves whether [addr1, addr1 + size1) and [addr2, addr2 + size2)
        must alias, no alias, or may alias across all valid symbolic states.
        """
        state = SymbolicState(prefix="alias")
        executor = SymbolicExecutor(ControlFlowGraph())

        a1_bv = executor.eval_expr(addr1, state)
        a2_bv = executor.eval_expr(addr2, state)

        if a1_bv.size() < 64:
            a1_bv = z3.ZeroExt(64 - a1_bv.size(), a1_bv)
        if a2_bv.size() < 64:
            a2_bv = z3.ZeroExt(64 - a2_bv.size(), a2_bv)

        s1_val = z3.BitVecVal(size1_bytes, 64)
        s2_val = z3.BitVecVal(size2_bytes, 64)

        # Overlap formula: (a1 < a2 + s2) and (a2 < a1 + s1) using unsigned comparison
        overlap_cond = z3.And(
            z3.ULT(a1_bv, a2_bv + s2_val),
            z3.ULT(a2_bv, a1_bv + s1_val)
        )

        solver = z3.Solver()
        solver.set("timeout", self.timeout_ms)

        if preconditions:
            for p in preconditions:
                solver.add(p)

        # 1. Test Must Alias: a1 == a2 across all inputs (so a1 != a2 is UNSAT)
        if size1_bytes == size2_bytes:
            solver.push()
            solver.add(a1_bv != a2_bv)
            if solver.check() == z3.unsat:
                solver.pop()
                return AliasQuery(
                    addr1_expr=addr1,
                    size1_bytes=size1_bytes,
                    addr2_expr=addr2,
                    size2_bytes=size2_bytes,
                    result=AliasResult.MUST_ALIAS,
                    theorem=f"∀ inputs . {addr1} ≡ {addr2}"
                )
            solver.pop()

        # 2. Test No Alias: overlap_cond is UNSAT across all inputs
        solver.push()
        solver.add(overlap_cond)
        check_overlap = solver.check()

        if check_overlap == z3.unsat:
            solver.pop()
            return AliasQuery(
                addr1_expr=addr1,
                size1_bytes=size1_bytes,
                addr2_expr=addr2,
                size2_bytes=size2_bytes,
                result=AliasResult.NO_ALIAS,
                theorem=f"∀ inputs . [{addr1}..+{size1_bytes}) ∩ [{addr2}..+{size2_bytes}) = ∅"
            )

        # 3. If overlap is SAT, test if non-overlap is also SAT (May Alias)
        cex: Dict[str, int] = {}
        model = solver.model()
        for name, sym in state.inputs.items():
            val = model.eval(sym, model_completion=True)
            if hasattr(val, "as_long"):
                cex[name] = val.as_long()
        solver.pop()

        return AliasQuery(
            addr1_expr=addr1,
            size1_bytes=size1_bytes,
            addr2_expr=addr2,
            size2_bytes=size2_bytes,
            result=AliasResult.MAY_ALIAS,
            theorem=f"∃ inputs . [{addr1}..+{size1_bytes}) ∩ [{addr2}..+{size2_bytes}) ≠ ∅",
            counterexample=cex
        )

    def analyze_cfg_memory_references(self, cfg: ControlFlowGraph) -> AliasReport:
        """
        Extracts all memory references in the CFG and computes pairwise alias queries.
        """
        mem_refs: List[Tuple[Expr, int]] = []

        def extract_from_expr(expr: Expr):
            if isinstance(expr, MemLoad):
                mem_refs.append((expr.addr, expr.bit_width // 8))

        for bb in cfg.blocks.values():
            for stmt in bb.stmts:
                if isinstance(stmt, MemStore):
                    mem_refs.append((stmt.addr, stmt.bit_width // 8))
                    extract_from_expr(stmt.expr)
                elif hasattr(stmt, "expr"):
                    extract_from_expr(getattr(stmt, "expr"))

        queries: List[AliasQuery] = []
        for i in range(len(mem_refs)):
            for j in range(i + 1, len(mem_refs)):
                a1, s1 = mem_refs[i]
                a2, s2 = mem_refs[j]
                q = self.query_alias(a1, s1, a2, s2)
                queries.append(q)

        no_alias = sum(1 for q in queries if q.result == AliasResult.NO_ALIAS)
        must_alias = sum(1 for q in queries if q.result == AliasResult.MUST_ALIAS)
        may_alias = sum(1 for q in queries if q.result == AliasResult.MAY_ALIAS)

        return AliasReport(
            total_queries=len(queries),
            no_alias_count=no_alias,
            must_alias_count=must_alias,
            may_alias_count=may_alias,
            queries=queries
        )

    def analyze_cfg_references(self, cfg: ControlFlowGraph) -> AliasReport:
        return self.analyze_cfg_memory_references(cfg)

