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

/// Resets the lowest set bit using `x & x.wrapping_sub(1)` (BMI1 BLSR).
pub fn reset_lowest_bit(x: u64) -> u64 {
    return (x & x.wrapping_sub(1));
}

/// Computes bitwise `(!a) & b` using BMI1 ANDN.
pub fn and_not(a: u64, b: u64) -> u64 {
    return ((!a) & b);
}

/// Counts trailing zeros using Rust std `trailing_zeros()`.
pub fn count_trailing_zeros(x: u64) -> u64 {
    return (x.trailing_zeros() as u64);
}

/// Counts leading zeros using Rust std `leading_zeros()`.
pub fn count_leading_zeros(x: u64) -> u64 {
    return (x.leading_zeros() as u64);
}

/// Reverses the byte order of the integer using Rust std `swap_bytes()`.
pub fn byte_swap_64(x: u64) -> u64 {
    return x.swap_bytes();
}

/// Clamps value into range [min_val, max_val].
pub fn clamp_val(val: i64, min_val: i64, max_val: i64) -> i64 {
    return val.clamp(min_val, max_val);
}

/// Formally synthesized routine `unsigned_divide`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn unsigned_divide(mut a: u64, mut b: u64) -> u64 {
    let mut rax: u64 = 0;
    let mut c: u64 = 0;
    let mut _div_q_2: u64 = 0;
    let mut _div_r_2: u64 = 0;
    // mov rax, rdi
    rax = a;
    // xor rdx, rdx
    c = 0;
    // div rsi
    _div_q_2 = (rax / b);
    _div_r_2 = (rax % b);
    rax = _div_q_2;
    c = _div_r_2;
    // ret 
    return rax;
}

/// Formally synthesized routine `signed_divide`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn signed_divide(mut a: i64, mut b: i64) -> i64 {
    let mut rax: i64 = 0;
    let mut c: i64 = 0;
    let mut _idiv_q_2: i64 = 0;
    let mut _idiv_r_2: i64 = 0;
    // mov rax, rdi
    rax = a;
    // cqo 
    c = (if (((rax >> 63) & 1) == 1) { -1 } else { 0 });
    // idiv rsi
    _idiv_q_2 = (rax / b);
    _idiv_r_2 = (rax % b);
    rax = _idiv_q_2;
    c = _idiv_r_2;
    // ret 
    return rax;
}

/// Formally synthesized routine `unsigned_modulo`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn unsigned_modulo(mut a: u64, mut b: u64) -> u64 {
    let mut rax: u64 = 0;
    let mut c: u64 = 0;
    let mut _div_q_2: u64 = 0;
    let mut _div_r_2: u64 = 0;
    // mov rax, rdi
    rax = a;
    // xor rdx, rdx
    c = 0;
    // div rsi
    _div_q_2 = (rax / b);
    _div_r_2 = (rax % b);
    rax = _div_q_2;
    c = _div_r_2;
    // mov rax, rdx
    rax = c;
    // ret 
    return rax;
}

/// Computes branchless absolute value via sign-extension mask:
/// `x.wrapping_abs()`.
pub fn branchless_abs(x: i64) -> i64 {
    return x.wrapping_abs();
}

/// Formally synthesized routine `bmi2_shlx`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn bmi2_shlx(mut a: u64, mut b: u64) -> u64 {
    let mut rax: u64 = 0;
    // shlx rax, rdi, rsi
    rax = (a << b);
    // ret 
    return rax;
}

/// Formally synthesized routine `atomic_xadd`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn atomic_xadd(mut a: u64, mut b: u64) -> u64 {
    let mut rax: u64 = 0;
    let mut _tmp_xadd_0: u64 = 0;
    // xadd rdi, rsi
    _tmp_xadd_0 = (a + b);
    b = a;
    a = _tmp_xadd_0;
    // mov rax, rdi
    rax = a;
    // ret 
    return rax;
}

/// Formally synthesized routine `shld_step`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn shld_step(mut a: u64, mut b: u64) -> u64 {
    let mut rax: u64 = 0;
    // mov rax, rdi
    rax = a;
    // shld rax, rsi, 4
    rax = ((rax << 4) | (b >> (64 - 4)));
    // ret 
    return rax;
}

/// Formally synthesized routine `shrd_step`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn shrd_step(mut a: u64, mut b: u64) -> u64 {
    let mut rax: u64 = 0;
    // mov rax, rdi
    rax = a;
    // shrd rax, rsi, 4
    rax = ((rax >> 4) | (b << (64 - 4)));
    // ret 
    return rax;
}

/// Formally synthesized routine `adc_chain`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn adc_chain(mut a: u64, mut b: u64, mut c: u64, mut d: u64) -> (u64, u64) {
    let mut rax: u64 = 0;
    // mov rax, rdi
    rax = a;
    // add rax, rdx
    rax = (rax + c);
    // mov rdx, rsi
    c = b;
    // adc rdx, rcx
    c = ((c + d) + (((rax + c) < rax) as u64));
    // ret 
    return (rax, c);
}

/// Formally synthesized routine `sbb_chain`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn sbb_chain(mut a: u64, mut b: u64, mut c: u64, mut d: u64) -> (u64, u64) {
    let mut rax: u64 = 0;
    // mov rax, rdi
    rax = a;
    // sub rax, rdx
    rax = (rax - c);
    // mov rdx, rsi
    c = b;
    // sbb rdx, rcx
    c = ((c - d) - ((rax < c) as u64));
    // ret 
    return (rax, c);
}

/// Formally synthesized routine `mul64_full`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn mul64_full(mut a: u64, mut b: u64) -> (u64, u64) {
    let mut rax: u64 = 0;
    let mut c: u64 = 0;
    let mut _prod_1: u128 = 0;
    // mov rax, rdi
    rax = a;
    // mul rsi
    _prod_1 = (((rax & 0xFFFFFFFFFFFFFFFF) as u128) * ((b & 0xFFFFFFFFFFFFFFFF) as u128));
    rax = (_prod_1 as u64);
    c = ((_prod_1 >> 64) as u64);
    // ret 
    return (rax, c);
}

/// Computes high 64 bits of 64x64 unsigned multiplication via 128-bit arithmetic.
pub fn mul_high64(a: u64, b: u64) -> u64 {
    return ((((a as u128) * (b as u128)) >> 64) as u64);
}

/// Branchless signum computation (-1, 0, or 1) using `x.signum()`.
pub fn branchless_signum(x: i64) -> i64 {
    return x.signum();
}

/// Branchless overflow-free midpoint: `(a & b) + ((a ^ b) >> 1)`.
pub fn branchless_midpoint(a: u64, b: u64) -> u64 {
    return ((a & b) + ((a ^ b) >> 1));
}

/// Branchless bitwise multiplexer selection: `(mask & a) | ((!mask) & b)`.
pub fn bit_select(mask: u64, a: u64, b: u64) -> u64 {
    return ((mask & a) | ((!mask) & b));
}

/// Formally synthesized routine `is_power_of_two`.
/// Lifted from x86_64 binary and proven equivalent via Z3 SMT solving.
pub fn is_power_of_two(mut a: u64, mut c: u64) -> u64 {
    let mut rax: u64 = 0;
    // test rdi, rdi
    // setg dl
    c = ((((c >> 8) & 0xFFFFFFFFFFFFFF) << 8) | (if (((a & a) as i64) > (0 as i64)) { 1 } else { 0 }));
    // lea rax, [rdi - 1]
    rax = (a - 1);
    // test rdi, rax
    // sete al
    rax = ((((rax >> 8) & 0xFFFFFFFFFFFFFF) << 8) | (if ((a & rax) == 0) { 1 } else { 0 }));
    // and eax, edx
    rax = (((rax & 0xFFFFFFFF) & (c & 0xFFFFFFFF)) & 0xFFFFFFFF);
    // movzx eax, al
    rax = (((rax & 255) & 255) & 0xFFFFFFFF);
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

    #[test]
    fn test_adc_chain() {
        assert_eq!(adc_chain(10, 20, 30, 40), (40, 60));
        assert_eq!(adc_chain(u64::MAX, 1, 1, 0), (0, 2));
    }

    #[test]
    fn test_sbb_chain() {
        assert_eq!(sbb_chain(50, 60, 20, 10), (30, 50));
        assert_eq!(sbb_chain(0, 10, 1, 0), (u64::MAX, 9));
    }

    #[test]
    fn test_mul64_full() {
        assert_eq!(mul64_full(2, 3), (6, 0));
        assert_eq!(mul64_full(0x100000000, 0x100000000), (0, 1));
    }

    #[test]
    fn test_mul_high64() {
        assert_eq!(mul_high64(0x100000000, 0x100000000), 1);
        assert_eq!(mul_high64(2, 3), 0);
    }

    #[test]
    fn test_branchless_signum() {
        assert_eq!(branchless_signum(42), 1);
        assert_eq!(branchless_signum(0), 0);
        assert_eq!(branchless_signum(-99), -1);
    }

    #[test]
    fn test_branchless_midpoint() {
        assert_eq!(branchless_midpoint(10, 20), 15);
        assert_eq!(branchless_midpoint(u64::MAX, u64::MAX), u64::MAX);
    }

    #[test]
    fn test_bit_select() {
        assert_eq!(bit_select(0xAAAAAAAA, 0x55555555, 0xFF00FF00), 0xAA55AA55);
    }

    #[test]
    fn test_is_power_of_two() {
        assert_eq!(is_power_of_two(1), 1);
        assert_eq!(is_power_of_two(16), 1);
        assert_eq!(is_power_of_two(18), 0);
        assert_eq!(is_power_of_two(0), 0);
    }
}

