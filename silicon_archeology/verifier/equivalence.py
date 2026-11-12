"""
SMT Equivalence Verifier between lifted x86 binary semantics and Rust AST semantics.
"""

from typing import Dict, List, Optional, Tuple, Any
import time
import z3
from silicon_archeology.symbolic.transfer_function import TransferFunction
from silicon_archeology.verifier.certificate import FormalCertificate


class EquivalenceVerifier:
    def __init__(self, timeout_ms: int = 10000):
        self.timeout_ms = timeout_ms

    def verify_transfer_functions(
        self,
        routine_name: str,
        bin_outputs: Dict[str, z3.BitVecRef],
        rust_outputs: Dict[str, z3.BitVecRef],
        input_symbols: Dict[str, z3.BitVecRef],
        preconditions: Optional[List[z3.BoolRef]] = None
    ) -> Tuple[bool, Optional[FormalCertificate]]:
        """
        Formally verifies that for all valuations satisfying preconditions,
        bin_outputs == rust_outputs for all output registers.
        """
        start_time = time.perf_counter()
        solver = z3.Solver()
        solver.set("timeout", self.timeout_ms)

        if preconditions:
            for p in preconditions:
                solver.add(p)

        # Check equivalence across all common outputs (e.g. rax)
        common_outputs = [r for r in bin_outputs if r in rust_outputs]
        if not common_outputs:
            raise ValueError(f"No common outputs to verify: bin={list(bin_outputs.keys())}, rust={list(rust_outputs.keys())}")

        discrepancies = []
        for out_name in common_outputs:
            bin_val = bin_outputs[out_name]
            rust_val = rust_outputs[out_name]

            # Harmonize widths if needed
            if bin_val.size() != rust_val.size():
                target_sz = max(bin_val.size(), rust_val.size())
                if bin_val.size() < target_sz:
                    bin_val = z3.ZeroExt(target_sz - bin_val.size(), bin_val)
                if rust_val.size() < target_sz:
                    rust_val = z3.ZeroExt(target_sz - rust_val.size(), rust_val)

            discrepancies.append(bin_val != rust_val)

        # Discrepancy assertion: exists any input where outputs differ
        solver.add(z3.Or(*discrepancies))

        check_res = solver.check()
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        theorem_str = f"∀ inputs . F_bin(inputs) ≡ F_rust(inputs) on [{', '.join(common_outputs)}]"

        if check_res == z3.unsat:
            # Equivalence proven mathematically!
            cert = FormalCertificate(
                target_routine=routine_name,
                status="PROVEN_EQUIVALENT",
                solver="Z3 Theorem Prover",
                solver_version=z3.get_version_string(),
                theorem=theorem_str,
                num_paths_verified=1,
                inputs_verified=list(input_symbols.keys()),
                outputs_verified=common_outputs,
                verification_time_ms=elapsed_ms,
                proof_hash=FormalCertificate.generate_hash(routine_name, theorem_str, time.time()),
                counterexample=None
            )
            return True, cert

        elif check_res == z3.sat:
            # Counterexample found
            model = solver.model()
            cex: Dict[str, int] = {}
            for name, sym in input_symbols.items():
                val = model.eval(sym, model_completion=True)
                if hasattr(val, "as_long"):
                    cex[name] = val.as_long()

            cert = FormalCertificate(
                target_routine=routine_name,
                status="DISPROVED",
                solver="Z3 Theorem Prover",
                solver_version=z3.get_version_string(),
                theorem=theorem_str,
                num_paths_verified=1,
                inputs_verified=list(input_symbols.keys()),
                outputs_verified=common_outputs,
                verification_time_ms=elapsed_ms,
                proof_hash="00000000000000000000000000000000",
                counterexample=cex
            )
            return False, cert

        else:
            # Timeout / Unknown
            cert = FormalCertificate(
                target_routine=routine_name,
                status="TIMEOUT",
                solver="Z3 Theorem Prover",
                solver_version=z3.get_version_string(),
                theorem=theorem_str,
                num_paths_verified=1,
                inputs_verified=list(input_symbols.keys()),
                outputs_verified=common_outputs,
                verification_time_ms=elapsed_ms,
                proof_hash="TIMEOUT",
                counterexample=None
            )
            return False, cert
