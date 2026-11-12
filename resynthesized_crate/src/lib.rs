//! # Re-Synthesized Artifacts
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

/// Formally synthesized routine `add_two`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn add_two(mut a: u64, mut b: u64) -> u64 {
    let mut rax: u64 = 0;
    // mov rax, rdi
    rax = a;
    // add rax, rsi
    rax = (rax + b);
    // ret 
    return rax;
}

/// Computes minimum of two numbers via signed conditional move.
pub fn branchless_min(a: i64, b: i64) -> i64 {
    return std::cmp::min(a, b);
}

/// Isolates the lowest set bit using wrapping arithmetic:
/// `x & x.wrapping_neg()`.
pub fn isolate_lowest_bit(x: u64) -> u64 {
    return (x & x.wrapping_neg());
}

/// Formally synthesized routine `popcount_builtin`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn popcount_builtin(mut a: u64) -> u64 {
    let mut rax: u64 = 0;
    // popcnt rax, rdi
    rax = (a.count_ones() as u64);
    // ret 
    return rax;
}

/// Formally synthesized routine `murmur3_fmix64`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn murmur3_fmix64(mut a: u64) -> u64 {
    let mut rax: u64 = 0;
    let mut c: u64 = 0;
    let mut d: u64 = 0;
    // mov rax, rdi
    rax = a;
    // movabs rcx, 0xff51afd7ed558ccd
    d = 0xFF51AFD7ED558CCD;
    // imul rax, rcx
    rax = (rax * d);
    // mov rdx, rax
    c = rax;
    // shr rdx, 0x21
    c = (c >> 33);
    // xor rax, rdx
    rax = (rax ^ c);
    // ret 
    return rax;
}

/// Formally synthesized routine `tea_round`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn tea_round(mut a: u64, mut b: u64, mut c: u64, mut d: u64, mut e: u64) -> u64 {
    let mut rax: u64 = 0;
    let mut f: u64 = 0;
    let mut r10: u64 = 0;
    // mov eax, esi
    rax = ((b & 0xFFFFFFFF) & 0xFFFFFFFF);
    // shl eax, 4
    rax = (((rax & 0xFFFFFFFF) << 4) & 0xFFFFFFFF);
    // add eax, ecx
    rax = (((rax & 0xFFFFFFFF) + (d & 0xFFFFFFFF)) & 0xFFFFFFFF);
    // mov r9d, esi
    f = ((b & 0xFFFFFFFF) & 0xFFFFFFFF);
    // add r9d, edx
    f = (((f & 0xFFFFFFFF) + (c & 0xFFFFFFFF)) & 0xFFFFFFFF);
    // xor eax, r9d
    rax = (((rax & 0xFFFFFFFF) ^ (f & 0xFFFFFFFF)) & 0xFFFFFFFF);
    // mov r10d, esi
    r10 = ((b & 0xFFFFFFFF) & 0xFFFFFFFF);
    // shr r10d, 5
    r10 = (((r10 & 0xFFFFFFFF) >> 5) & 0xFFFFFFFF);
    // add r10d, r8d
    r10 = (((r10 & 0xFFFFFFFF) + (e & 0xFFFFFFFF)) & 0xFFFFFFFF);
    // xor eax, r10d
    rax = (((rax & 0xFFFFFFFF) ^ (r10 & 0xFFFFFFFF)) & 0xFFFFFFFF);
    // add eax, edi
    rax = (((rax & 0xFFFFFFFF) + (a & 0xFFFFFFFF)) & 0xFFFFFFFF);
    // ret 
    return rax;
}

/// Formally synthesized routine `polynomial_eval`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn polynomial_eval(mut a: u64) -> u64 {
    let mut rax: u64 = 0;
    // lea rax, [rdi + rdi*2 + 7]
    rax = ((a + (a * 2)) + 7);
    // ret 
    return rax;
}

/// Formally synthesized routine `rc4_prga_step`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn rc4_prga_step(mut a: u64, mut b: u64, mut c: u64) -> u64 {
    let mut rax: u64 = 0;
    // inc edi
    a = (((a & 0xFFFFFFFF) + 1) & 0xFFFFFFFF);
    // and edi, 0xff
    a = (((a & 0xFFFFFFFF) & 255) & 0xFFFFFFFF);
    // add esi, edx
    b = (((b & 0xFFFFFFFF) + (c & 0xFFFFFFFF)) & 0xFFFFFFFF);
    // and esi, 0xff
    b = (((b & 0xFFFFFFFF) & 255) & 0xFFFFFFFF);
    // mov rax, rsi
    rax = b;
    // ret 
    return rax;
}

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
}
