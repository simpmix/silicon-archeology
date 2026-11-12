"""
Transfer function representation capturing symbolic input-to-output relations.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import z3


@dataclass
class PathSummary:
    condition: z3.BoolRef
    register_effects: Dict[str, z3.BitVecRef]
    memory_writes: List[Tuple[z3.BitVecRef, z3.BitVecRef, int]]  # (addr, val, bit_width)


@dataclass
class TransferFunction:
    name: str
    input_symbols: Dict[str, z3.BitVecRef]
    paths: List[PathSummary] = field(default_factory=list)
    combined_outputs: Dict[str, z3.BitVecRef] = field(default_factory=dict)

    def collapse_into_ite(self) -> Dict[str, z3.BitVecRef]:
        """
        Collapses multiple execution paths into single conditional ITE expressions
        for each output register.
        """
        if not self.paths:
            return self.combined_outputs

        if len(self.paths) == 1:
            self.combined_outputs = dict(self.paths[0].register_effects)
            return self.combined_outputs

        # Multi-path conditional combination
        all_regs = set()
        for p in self.paths:
            all_regs.update(p.register_effects.keys())

        result: Dict[str, z3.BitVecRef] = {}
        for reg in all_regs:
            # Build right-to-left chained ITE
            current_expr = None
            for p in reversed(self.paths):
                val = p.register_effects.get(reg, self.input_symbols.get(reg, z3.BitVecVal(0, 64)))
                if current_expr is None:
                    current_expr = val
                else:
                    current_expr = z3.If(p.condition, val, current_expr)
            result[reg] = z3.simplify(current_expr)

        self.combined_outputs = result
        return self.combined_outputs
