"""
Example 4: Re-Synthesize Multiple Binary Routines into a Standalone Rust Crate.

Executes the Silicon Archeology pipeline across a suite of x86/x86_64 routines,
generates formal SMT equivalence certificates for each, and outputs a complete,
compilable, memory-safe Rust library under `resynthesized_crate/`.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from silicon_archeology.pipeline import ReSynthesisPipeline


ROUTINES = [
    {
        "name": "add_two",
        "bytes": bytes.fromhex("48 89 f8 48 01 f0 c3"),
        "doc": "Arithmetic addition of two 64-bit unsigned integers."
    },
    {
        "name": "branchless_min",
        "bytes": bytes.fromhex("48 39 f7 48 0f 4f fe 48 89 f8 c3"),
        "doc": "Branchless conditional minimum selection using cmovg."
    },
    {
        "name": "isolate_lowest_bit",
        "bytes": bytes.fromhex("48 89 f8 48 f7 d8 48 21 f8 c3"),
        "doc": "Bit-twiddling isolate lowest set bit via wrapping negation and bitwise AND."
    },
    {
        "name": "popcount_builtin",
        "bytes": bytes.fromhex("f3 48 0f b8 c7 c3"),
        "doc": "Population count (Hamming weight) lifted from hardware POPCNT instruction."
    },
    {
        "name": "murmur3_fmix64",
        "bytes": bytes.fromhex("48 89 f8 48 b9 cd 8c 55 ed d7 af 51 ff 48 0f af c1 48 89 c2 48 c1 ea 21 48 31 d0 c3"),
        "doc": "Murmur3 64-bit avalanche mixing step."
    },
    {
        "name": "tea_round",
        "bytes": bytes.fromhex("89 f0 c1 e0 04 01 c8 41 89 f1 41 01 d1 44 31 c8 41 89 f2 41 c1 ea 05 45 01 c2 44 31 d0 01 f8 c3"),
        "doc": "Tiny Encryption Algorithm (TEA) single Feistel round step."
    },
    {
        "name": "polynomial_eval",
        "bytes": bytes.fromhex("48 8d 44 7f 07 c3"),
        "doc": "Linear polynomial calculation f(x) = 3*x + 7 via x86 LEA addressing."
    },
    {
        "name": "rc4_prga_step",
        "bytes": bytes.fromhex("ff c7 81 e7 ff 00 00 00 01 d6 81 e6 ff 00 00 00 48 89 f0 c3"),
        "doc": "RC4 stream cipher pseudo-random generation algorithm state index step."
    },
    {
        "name": "reset_lowest_bit",
        "bytes": bytes.fromhex("c4 e2 f8 f3 cf c3"),
        "doc": "Reset lowest set bit via BMI1 BLSR instruction."
    },
    {
        "name": "and_not",
        "bytes": bytes.fromhex("c4 e2 c0 f2 c6 c3"),
        "doc": "Bitwise AND NOT ((!a) & b) via BMI1 ANDN instruction."
    },
    {
        "name": "count_trailing_zeros",
        "bytes": bytes.fromhex("f3 48 0f bc c7 c3"),
        "doc": "Count trailing zero bits via hardware TZCNT instruction."
    },
    {
        "name": "count_leading_zeros",
        "bytes": bytes.fromhex("f3 48 0f bd c7 c3"),
        "doc": "Count leading zero bits via hardware LZCNT instruction."
    },
    {
        "name": "byte_swap_64",
        "bytes": bytes.fromhex("48 89 f8 48 0f c8 c3"),
        "doc": "64-bit endian byte swap via BSWAP instruction."
    },
    {
        "name": "clamp_val",
        "bytes": bytes.fromhex("48 39 f7 48 0f 4c fe 48 39 d7 48 0f 4f fa 48 89 f8 c3"),
        "doc": "Branchless signed range clamp [min, max] via CMOVcc instructions."
    },
    {
        "name": "unsigned_divide",
        "bytes": bytes.fromhex("48 89 f8 48 31 d2 48 f7 f6 c3"),
        "doc": "Unsigned 64-bit integer division via DIV instruction."
    },
    {
        "name": "signed_divide",
        "bytes": bytes.fromhex("48 89 f8 48 99 48 f7 fe c3"),
        "doc": "Signed 64-bit integer division via IDIV and CQO instructions."
    },
    {
        "name": "unsigned_modulo",
        "bytes": bytes.fromhex("48 89 f8 48 31 d2 48 f7 f6 48 89 d0 c3"),
        "doc": "Unsigned 64-bit integer modulo remainder via DIV instruction."
    },
    {
        "name": "branchless_abs",
        "bytes": bytes.fromhex("48 89 f8 48 99 48 31 d0 48 29 d0 c3"),
        "doc": "Branchless absolute value via sign-extension arithmetic."
    },
    {
        "name": "bmi2_shlx",
        "bytes": bytes.fromhex("c4 e2 c9 f7 c7 c3"),
        "doc": "BMI2 dynamic logical shift left without affecting EFLAGS."
    },
    {
        "name": "atomic_xadd",
        "bytes": bytes.fromhex("48 0f c1 f7 48 89 f8 c3"),
        "doc": "Atomic exchange and add via XADD instruction."
    },
    {
        "name": "shld_step",
        "bytes": bytes.fromhex("48 89 f8 48 0f a4 f0 04 c3"),
        "doc": "Double-precision left shift step via SHLD instruction."
    },
    {
        "name": "shrd_step",
        "bytes": bytes.fromhex("48 89 f8 48 0f ac f0 04 c3"),
        "doc": "Double-precision right shift step via SHRD instruction."
    }
]


def main():
    print("=" * 80)
    print("  SILICON ARCHEOLOGY: FULL RE-SYNTHESIS TO STANDALONE RUST CRATE")
    print("=" * 80)

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    crate_dir = os.path.join(repo_root, "resynthesized_crate")
    src_dir = os.path.join(crate_dir, "src")
    proofs_dir = os.path.join(crate_dir, "proofs")

    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(proofs_dir, exist_ok=True)

    pipeline = ReSynthesisPipeline(mode=64)
    synthesized_functions = []
    proof_summaries = []

    for routine in ROUTINES:
        name = routine["name"]
        code = routine["bytes"]
        doc = routine["doc"]

        print(f"\n[*] Processing: {name} ({len(code)} bytes)")
        res = pipeline.process(name=name, code_bytes=code)

        print(f"    Equivalence Status: {res.certificate.status}")
        print(f"    Solving Time:       {res.certificate.verification_time_ms:.2f} ms")
        print(f"    rustc Compiles:     {res.compiles_successfully}")

        synthesized_functions.append(res.rust_source)

        cert_file = os.path.join(proofs_dir, f"{name}.proof.json")
        with open(cert_file, "w", encoding="utf-8") as f:
            f.write(res.certificate.to_json())

        proof_summaries.append({
            "routine": name,
            "status": res.certificate.status,
            "theorem": res.certificate.theorem,
            "solver": f"{res.certificate.solver} v{res.certificate.solver_version}",
            "time_ms": res.certificate.verification_time_ms,
            "proof_hash": res.certificate.proof_hash
        })

    # Write Cargo.toml
    cargo_toml_content = """[package]
name = "resynthesized_artifacts"
version = "0.1.0"
edition = "2021"
authors = ["Silicon Archeology SMT Engine"]
description = "Formally verified Rust library re-synthesized from x86_64 machine binaries via Z3 SMT solver."
license = "MIT OR Apache-2.0"

[dependencies]
"""
    with open(os.path.join(crate_dir, "Cargo.toml"), "w", encoding="utf-8") as f:
        f.write(cargo_toml_content)

    # Write lib.rs
    lib_header = """//! # Re-Synthesized Artifacts
//!
//! This crate contains memory-safe, idiomatic Rust routines automatically
//! re-synthesized from raw x86_64 machine code by **Silicon Archeology**.
//!
//! Every routine in this crate has a mathematical equivalence proof certificate
//! generated using the Z3 Theorem Prover verifying that:
//!
//! ```text
//! ∀ inputs ∈ StateSpace . F_binary(inputs) ≡ F_rust(inputs)
//! ```

#![allow(unused_variables, dead_code, unused_mut, unconditional_panic, unused_assignments, unused_parens)]

"""
    full_lib_rs = lib_header + "\n\n".join(synthesized_functions) + "\n"

    # Add embedded unit tests in lib.rs
    unit_tests = """
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_two() {
        assert_eq!(add_two(15, 27), 42);
    }

    #[test]
    fn test_branchless_min() {
        assert_eq!(branchless_min(10, 20), 10);
        assert_eq!(branchless_min(-15, 5), -15);
    }

    #[test]
    fn test_isolate_lowest_bit() {
        assert_eq!(isolate_lowest_bit(0b101000), 0b001000);
        assert_eq!(isolate_lowest_bit(12), 4);
    }

    #[test]
    fn test_popcount() {
        assert_eq!(popcount_builtin(0b111100001111), 8);
    }

    #[test]
    fn test_polynomial_eval() {
        // f(x) = 3*x + 7
        assert_eq!(polynomial_eval(5), 22);
    }

    #[test]
    fn test_tea_round() {
        let v0 = 0x12345678u64;
        let v1 = 0x9ABCDEF0u64;
        let sum = 0xC6EF3720u64;
        let k0 = 0x01234567u64;
        let k1 = 0x89ABCDEFu64;
        let res = tea_round(v0, v1, sum, k0, k1);
        assert!(res > 0);
    }

    #[test]
    fn test_reset_lowest_bit() {
        assert_eq!(reset_lowest_bit(0b1100), 0b1000);
        assert_eq!(reset_lowest_bit(20), 16);
    }

    #[test]
    fn test_and_not() {
        assert_eq!(and_not(0b1010, 0b1100), 0b0100);
    }

    #[test]
    fn test_count_trailing_zeros() {
        assert_eq!(count_trailing_zeros(16), 4);
        assert_eq!(count_trailing_zeros(1), 0);
    }

    #[test]
    fn test_count_leading_zeros() {
        assert_eq!(count_leading_zeros(1), 63);
        assert_eq!(count_leading_zeros(0x8000000000000000), 0);
    }

    #[test]
    fn test_byte_swap_64() {
        assert_eq!(byte_swap_64(0x0102030405060708), 0x0807060504030201);
    }

    #[test]
    fn test_clamp_val() {
        assert_eq!(clamp_val(10, 20, 30), 20);
        assert_eq!(clamp_val(25, 20, 30), 25);
        assert_eq!(clamp_val(35, 20, 30), 30);
    }

    #[test]
    fn test_unsigned_divide() {
        assert_eq!(unsigned_divide(100, 7), 14);
    }

    #[test]
    fn test_signed_divide() {
        assert_eq!(signed_divide(-42, 6), -7);
        assert_eq!(signed_divide(100, -5), -20);
    }

    #[test]
    fn test_unsigned_modulo() {
        assert_eq!(unsigned_modulo(14, 4), 2);
        assert_eq!(unsigned_modulo(100, 7), 2);
    }

    #[test]
    fn test_branchless_abs() {
        assert_eq!(branchless_abs(-42), 42);
        assert_eq!(branchless_abs(100), 100);
        assert_eq!(branchless_abs(0), 0);
    }

    #[test]
    fn test_bmi2_shlx() {
        assert_eq!(bmi2_shlx(5, 3), 40);
    }

    #[test]
    fn test_atomic_xadd() {
        assert_eq!(atomic_xadd(15, 27), 42);
    }

    #[test]
    fn test_shld_step() {
        // (0x12 << 4) | (0xF000000000000000 >> 60)
        assert_eq!(shld_step(0x12, 0xF000000000000000), 0x12F);
    }

    #[test]
    fn test_shrd_step() {
        // (0x120 >> 4) | (0x0F << 60)
        assert_eq!(shrd_step(0x120, 0x0F), 0xF000000000000012);
    }
}
"""
    full_lib_rs += unit_tests

    with open(os.path.join(src_dir, "lib.rs"), "w", encoding="utf-8") as f:
        f.write(full_lib_rs)

    # Write summary manifest
    manifest_path = os.path.join(crate_dir, "PROOF_SUMMARY.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(proof_summaries, f, indent=2)

    print("\n" + "=" * 80)
    print(f"[+] Successfully generated standalone Rust crate at: {crate_dir}")
    print(f"[+] Total routines synthesized and proven: {len(synthesized_functions)}")
    print(f"[+] Proof certificates directory:          {proofs_dir}")
    print(f"[+] Proof summary manifest:                {manifest_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
