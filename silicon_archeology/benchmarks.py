"""
Automated Benchmarking Suite for Silicon Archeology Re-Synthesis Engine.
Measures lifting latency, Z3 SMT verification latency, synthesis speed, and throughput.
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
import time
import json
import statistics

from silicon_archeology.pipeline import ReSynthesisPipeline


@dataclass
class RoutineBenchmarkResult:
    routine_name: str
    bytes_count: int
    lifting_time_ms: float
    solving_time_ms: float
    compiles_successfully: bool
    is_equivalent: bool
    proof_status: str


@dataclass
class BenchmarkSuiteSummary:
    total_routines: int
    proven_count: int
    mean_solving_ms: float
    median_solving_ms: float
    min_solving_ms: float
    max_solving_ms: float
    total_duration_sec: float
    throughput_routines_per_sec: float
    results: List[RoutineBenchmarkResult]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


BENCHMARK_ROUTINES = [
    ("add_two", bytes.fromhex("48 89 f8 48 01 f0 c3")),
    ("branchless_min", bytes.fromhex("48 39 f7 48 0f 4f fe 48 89 f8 c3")),
    ("isolate_lowest_bit", bytes.fromhex("48 89 f8 48 f7 d8 48 21 f8 c3")),
    ("popcount_builtin", bytes.fromhex("f3 48 0f b8 c7 c3")),
    ("murmur3_fmix64", bytes.fromhex("48 89 f8 48 b9 cd 8c 55 ed d7 af 51 ff 48 0f af c1 48 89 c2 48 c1 ea 21 48 31 d0 c3")),
    ("tea_round", bytes.fromhex("89 f0 c1 e0 04 01 c8 41 89 f1 41 01 d1 44 31 c8 41 89 f2 41 c1 ea 05 45 01 c2 44 31 d0 01 f8 c3")),
    ("polynomial_eval", bytes.fromhex("48 8d 44 7f 07 c3")),
    ("rc4_prga_step", bytes.fromhex("ff c7 81 e7 ff 00 00 00 01 d6 81 e6 ff 00 00 00 48 89 f0 c3")),
    ("reset_lowest_bit", bytes.fromhex("c4 e2 f8 f3 cf c3")),
    ("and_not", bytes.fromhex("c4 e2 c0 f2 c6 c3")),
    ("count_trailing_zeros", bytes.fromhex("f3 48 0f bc c7 c3")),
    ("count_leading_zeros", bytes.fromhex("f3 48 0f bd c7 c3")),
    ("byte_swap_64", bytes.fromhex("48 89 f8 48 0f c8 c3")),
    ("branchless_midpoint", bytes.fromhex("48 89 f8 48 21 f0 48 89 fa 48 31 f2 48 d1 ea 48 01 d0 c3")),
    ("bit_select", bytes.fromhex("48 89 f8 48 21 f0 48 f7 d7 48 21 d7 48 09 f8 c3")),
    ("mul_high64", bytes.fromhex("48 89 f8 48 f7 e6 48 89 d0 c3")),
    ("adc_chain", bytes.fromhex("48 89 f8 48 01 d0 48 89 f2 48 11 ca c3")),
    ("sbb_chain", bytes.fromhex("48 89 f8 48 29 d0 48 89 f2 48 19 ca c3")),
    ("mul64_full", bytes.fromhex("48 89 f8 48 f7 e6 c3")),
    ("branchless_signum", bytes.fromhex("48 83 ff 00 0f 9f c0 0f 9c c2 0f b6 c0 0f b6 d2 29 d0 48 98 c3")),
]


class BenchmarkRunner:
    def __init__(self, mode: int = 64):
        self.pipeline = ReSynthesisPipeline(mode=mode)

    def run_benchmark(self, routines: Optional[List[Tuple[str, bytes]]] = None) -> BenchmarkSuiteSummary:
        suite = routines or BENCHMARK_ROUTINES
        results: List[RoutineBenchmarkResult] = []
        overall_start = time.perf_counter()

        for name, code in suite:
            t0 = time.perf_counter()
            cfg = self.pipeline.lifter.lift_bytes(code)
            lift_ms = (time.perf_counter() - t0) * 1000.0

            res = self.pipeline.process(name=name, code_bytes=code)
            results.append(RoutineBenchmarkResult(
                routine_name=name,
                bytes_count=len(code),
                lifting_time_ms=lift_ms,
                solving_time_ms=res.certificate.verification_time_ms,
                compiles_successfully=res.compiles_successfully,
                is_equivalent=res.is_equivalent,
                proof_status=res.certificate.status
            ))

        total_sec = time.perf_counter() - overall_start
        solving_times = [r.solving_time_ms for r in results]
        proven_count = sum(1 for r in results if r.is_equivalent)

        return BenchmarkSuiteSummary(
            total_routines=len(results),
            proven_count=proven_count,
            mean_solving_ms=statistics.mean(solving_times) if solving_times else 0.0,
            median_solving_ms=statistics.median(solving_times) if solving_times else 0.0,
            min_solving_ms=min(solving_times) if solving_times else 0.0,
            max_solving_ms=max(solving_times) if solving_times else 0.0,
            total_duration_sec=total_sec,
            throughput_routines_per_sec=len(results) / total_sec if total_sec > 0 else 0.0,
            results=results
        )

    def print_report(self, summary: BenchmarkSuiteSummary) -> None:
        print("=" * 80)
        print("  SILICON ARCHEOLOGY: SMT ENGINE BENCHMARK REPORT")
        print("=" * 80)
        print(f"  Total Routines Verified:   {summary.total_routines}")
        print(f"  Formally Proven (UNSAT):   {summary.proven_count} / {summary.total_routines} ({summary.proven_count/summary.total_routines*100:.1f}%)")
        print(f"  Mean SMT Solving Latency:  {summary.mean_solving_ms:.2f} ms")
        print(f"  Median Solving Latency:    {summary.median_solving_ms:.2f} ms")
        print(f"  Min / Max Solving Latency: {summary.min_solving_ms:.2f} ms / {summary.max_solving_ms:.2f} ms")
        print(f"  Engine Throughput:         {summary.throughput_routines_per_sec:.1f} routines / sec")
        print(f"  Total Benchmark Time:      {summary.total_duration_sec:.2f} s")
        print("-" * 80)
        print(f"  {'Routine Name':<24} {'Bytes':<8} {'Lift(ms)':<10} {'SMT(ms)':<10} {'Status':<18} {'rustc'}")
        print("-" * 80)
        for r in summary.results:
            print(f"  {r.routine_name:<24} {r.bytes_count:<8} {r.lifting_time_ms:<10.2f} {r.solving_time_ms:<10.2f} {r.proof_status:<18} {r.compiles_successfully}")
        print("=" * 80)
