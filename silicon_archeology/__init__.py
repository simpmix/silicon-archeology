"""
Silicon Archeology: SMT-Driven Binary-to-Compilable-Rust Re-Synthesis Engine.
"""

__version__ = "0.1.0"
__author__ = "Silicon Archeology Authors"

from silicon_archeology.pipeline import ReSynthesisPipeline, PipelineResult
from silicon_archeology.lifter.x86_lifter import X86Lifter
from silicon_archeology.symbolic.executor import SymbolicExecutor
from silicon_archeology.verifier.equivalence import EquivalenceVerifier
from silicon_archeology.synthesizer.rust_emitter import RustEmitter

__all__ = [
    "ReSynthesisPipeline",
    "PipelineResult",
    "X86Lifter",
    "SymbolicExecutor",
    "EquivalenceVerifier",
    "RustEmitter",
]
