"""
End-to-end integration tests for Silicon Archeology pipeline.
"""

import pytest
from silicon_archeology.pipeline import ReSynthesisPipeline


def test_pipeline_add_two_routine():
    pipe = ReSynthesisPipeline(mode=64)
    # mov rax, rdi; add rax, rsi; ret
    code = bytes.fromhex("48 89 f8 48 01 f0 c3")
    res = pipe.process(name="add_two", code_bytes=code)

    assert res.routine_name == "add_two"
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True
    assert res.test_passed is True
    assert "pub fn add_two" in res.rust_source


def test_pipeline_bitwise_xor_swap():
    pipe = ReSynthesisPipeline(mode=64)
    # xor rdi, rsi
    # mov rax, rdi
    # ret
    # 48 31 f7 48 89 f8 c3
    code = bytes.fromhex("48 31 f7 48 89 f8 c3")
    res = pipe.process(name="xor_inputs", code_bytes=code)

    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True


def test_pipeline_polynomial_calc():
    pipe = ReSynthesisPipeline(mode=64)
    # rax = (rdi * 3) + 7
    # lea rax, [rdi + rdi*2 + 7]
    # ret
    # 48 8d 44 7f 07 c3
    code = bytes.fromhex("48 8d 44 7f 07 c3")
    res = pipe.process(name="poly_calc", code_bytes=code)

    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True


def test_pipeline_branchless_min_idiom():
    pipe = ReSynthesisPipeline(mode=64)
    # cmp rdi, rsi
    # cmovg rdi, rsi
    # mov rax, rdi
    # ret
    # 48 39 f7 48 0f 4f fe 48 89 f8 c3
    code = bytes.fromhex("48 39 f7 48 0f 4f fe 48 89 f8 c3")
    res = pipe.process(name="min_val", code_bytes=code)

    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True
    assert "std::cmp::min" in res.rust_source


def test_pipeline_with_sample_tests():
    pipe = ReSynthesisPipeline(mode=64)
    # mov rax, rdi; add rax, rsi; ret
    code = bytes.fromhex("48 89 f8 48 01 f0 c3")
    sample_tests = [
        ([10, 20], 30),
        ([0, 0], 0),
        ([1000, 2000], 3000),
    ]
    res = pipe.process(name="add_two_tested", code_bytes=code, sample_tests=sample_tests)

    assert res.is_equivalent is True
    assert res.compiles_successfully is True
    assert res.test_passed is True


def test_pipeline_rotate_and_mask():
    pipe = ReSynthesisPipeline(mode=64)
    # rol rdi, 13
    # mov rax, rdi
    # and rax, 0xff
    # ret
    # 48 c1 c7 0d 48 89 f8 48 81 e0 ff 00 00 00 c3
    code = bytes.fromhex("48 c1 c7 0d 48 89 f8 48 81 e0 ff 00 00 00 c3")
    res = pipe.process(name="rol_and_mask", code_bytes=code)

    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True
    assert "0xFF" in res.rust_source or "255" in res.rust_source


def test_pipeline_certificate_integrity():
    pipe = ReSynthesisPipeline(mode=64)
    code = bytes.fromhex("48 31 f7 48 89 f8 c3")
    res = pipe.process(name="xor_fn", code_bytes=code)

    cert = res.certificate
    assert cert.status == "PROVEN_EQUIVALENT"
    assert cert.solver == "Z3 Theorem Prover"
    assert "xor_fn" in cert.target_routine
    assert cert.verification_time_ms > 0
    assert len(cert.proof_hash) == 64
    # Ensure JSON serializable
    parsed = eval(cert.to_json().replace("true", "True").replace("false", "False").replace("null", "None"))
    assert parsed["status"] == "PROVEN_EQUIVALENT"


def test_pipeline_unnamed_branchless_idiom():
    pipe = ReSynthesisPipeline(mode=64)
    # Routine without 'min' in name: must still detect idiom and prove equivalent
    code = bytes.fromhex("48 39 f7 48 0f 4f fe 48 89 f8 c3")
    res = pipe.process(name="routine", code_bytes=code)

    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True
    assert "std::cmp::min" in res.rust_source


def test_pipeline_movsxd():
    pipe = ReSynthesisPipeline(mode=64)
    # movsxd rax, edi; ret
    code = bytes.fromhex("48 63 c7 c3")
    res = pipe.process(name="sign_extend_test", code_bytes=code)

    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True


def test_pipeline_bswap():
    pipe = ReSynthesisPipeline(mode=64)
    # mov rax, rdi; bswap rax; ret
    code = bytes.fromhex("48 89 f8 48 0f c8 c3")
    res = pipe.process(name="byte_reverse", code_bytes=code)

    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True


def test_pipeline_bmi_blsr():
    pipe = ReSynthesisPipeline(mode=64)
    # blsr rax, rdi; ret
    code = bytes.fromhex("c4 e2 f8 f3 cf c3")
    res = pipe.process(name="blsr_routine", code_bytes=code)

    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True
    assert "wrapping_sub" in res.rust_source or "blsr" in res.rust_source


def test_pipeline_bmi_andn():
    pipe = ReSynthesisPipeline(mode=64)
    # andn rax, rdi, rsi; ret
    code = bytes.fromhex("c4 e2 c0 f2 c6 c3")
    res = pipe.process(name="andn_routine", code_bytes=code)

    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True
    assert "!" in res.rust_source


def test_pipeline_bmi_bextr():
    pipe = ReSynthesisPipeline(mode=64)
    # bextr rax, rdi, rsi; ret
    code = bytes.fromhex("c4 e2 c8 f7 c7 c3")
    res = pipe.process(name="bextr_routine", code_bytes=code)

    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True


def test_pipeline_bit_counting_tzcnt_lzcnt():
    pipe = ReSynthesisPipeline(mode=64)
    # tzcnt rax, rdi; ret
    code_tz = bytes.fromhex("f3 48 0f bc c7 c3")
    res_tz = pipe.process(name="tz_routine", code_bytes=code_tz)
    assert res_tz.is_equivalent is True
    assert res_tz.compiles_successfully is True
    assert "trailing_zeros" in res_tz.rust_source

    # lzcnt rax, rdi; ret
    code_lz = bytes.fromhex("f3 48 0f bd c7 c3")
    res_lz = pipe.process(name="lz_routine", code_bytes=code_lz)
    assert res_lz.is_equivalent is True
    assert res_lz.compiles_successfully is True
    assert "leading_zeros" in res_lz.rust_source


def test_pipeline_division_and_modulo():
    pipe = ReSynthesisPipeline(mode=64)
    # mov rax, rdi; xor rdx, rdx; div rsi; ret
    code_div = bytes.fromhex("48 89 f8 48 31 d2 48 f7 f6 c3")
    res_div = pipe.process(name="div_routine", code_bytes=code_div)
    assert res_div.is_equivalent is True
    assert res_div.compiles_successfully is True


def test_pipeline_setcc_predicate():
    pipe = ReSynthesisPipeline(mode=64)
    # cmp rdi, rsi; sete al; movzx rax, al; ret
    code = bytes.fromhex("48 39 f7 0f 94 c0 48 0f b6 c0 c3")
    res = pipe.process(name="is_equal_predicate", code_bytes=code)
    assert res.is_equivalent is True
    assert res.compiles_successfully is True


def test_pipeline_branchless_clamp():
    pipe = ReSynthesisPipeline(mode=64)
    # cmp rdi, rsi; cmovl rdi, rsi; cmp rdi, rdx; cmovg rdi, rdx; mov rax, rdi; ret
    code = bytes.fromhex("48 39 f7 48 0f 4c fe 48 39 d7 48 0f 4f fa 48 89 f8 c3")
    res = pipe.process(name="clamp_val", code_bytes=code)
    assert res.is_equivalent is True
    assert res.certificate.status == "PROVEN_EQUIVALENT"
    assert res.compiles_successfully is True
    assert "clamp" in res.rust_source


def test_pipeline_three_operand_imul():
    pipe = ReSynthesisPipeline(mode=64)
    # imul rax, rdi, 42; ret
    code = bytes.fromhex("48 6b c7 2a c3")
    res = pipe.process(name="imul_fixed", code_bytes=code)
    assert res.is_equivalent is True
    assert res.compiles_successfully is True
    assert "42" in res.rust_source or "0x2A" in res.rust_source


def test_pipeline_cqo_sign_extension():
    pipe = ReSynthesisPipeline(mode=64)
    # mov rax, rdi; cqo; mov rax, rdx; ret
    code = bytes.fromhex("48 89 f8 48 99 48 89 d0 c3")
    res = pipe.process(name="cqo_sign_extract", code_bytes=code)
    assert res.is_equivalent is True
    assert res.compiles_successfully is True
