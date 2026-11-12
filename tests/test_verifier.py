"""
Unit tests for SMT Equivalence Verifier and proof certificate generation.
"""

import pytest
import z3
from silicon_archeology.verifier.equivalence import EquivalenceVerifier
from silicon_archeology.verifier.certificate import FormalCertificate


def test_equivalence_identical_functions():
    verifier = EquivalenceVerifier(timeout_ms=5000)
    x = z3.BitVec("in_rdi", 64)
    # F_bin = x + x
    bin_out = {"rax": x + x}
    # F_rust = x * 2
    rust_out = {"rax": x * 2}

    is_equiv, cert = verifier.verify_transfer_functions(
        routine_name="double",
        bin_outputs=bin_out,
        rust_outputs=rust_out,
        input_symbols={"rdi": x}
    )

    assert is_equiv is True
    assert cert is not None
    assert cert.status == "PROVEN_EQUIVALENT"
    assert cert.counterexample is None
    assert len(cert.proof_hash) == 64


def test_equivalence_bitwise_identity():
    verifier = EquivalenceVerifier(timeout_ms=5000)
    x = z3.BitVec("in_rdi", 64)
    # F_bin = (x << 3) - x
    bin_out = {"rax": (x << 3) - x}
    # F_rust = x * 7
    rust_out = {"rax": x * 7}

    is_equiv, cert = verifier.verify_transfer_functions(
        routine_name="mul_7",
        bin_outputs=bin_out,
        rust_outputs=rust_out,
        input_symbols={"rdi": x}
    )

    assert is_equiv is True
    assert cert.status == "PROVEN_EQUIVALENT"


def test_non_equivalence_counterexample():
    verifier = EquivalenceVerifier(timeout_ms=5000)
    x = z3.BitVec("in_rdi", 64)
    # F_bin = x + 1
    bin_out = {"rax": x + 1}
    # F_rust = x + 2 (Buggy implementation)
    rust_out = {"rax": x + 2}

    is_equiv, cert = verifier.verify_transfer_functions(
        routine_name="buggy_inc",
        bin_outputs=bin_out,
        rust_outputs=rust_out,
        input_symbols={"rdi": x}
    )

    assert is_equiv is False
    assert cert is not None
    assert cert.status == "DISPROVED"
    assert cert.counterexample is not None
    assert "rdi" in cert.counterexample


def test_certificate_json_serialization():
    cert = FormalCertificate(
        target_routine="test_routine",
        status="PROVEN_EQUIVALENT",
        solver="Z3 Theorem Prover",
        solver_version="5.4.1",
        theorem="∀ x . F(x) = G(x)",
        num_paths_verified=1,
        inputs_verified=["rdi", "rsi"],
        outputs_verified=["rax"],
        verification_time_ms=12.34,
        proof_hash="abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
        counterexample=None
    )
    json_str = cert.to_json()
    assert "PROVEN_EQUIVALENT" in json_str
    assert "test_routine" in json_str
    assert "proof_hash" in json_str
