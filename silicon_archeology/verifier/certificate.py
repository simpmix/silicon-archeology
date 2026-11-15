"""
Verification Certificate model and serialization.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import json
import hashlib
import time


@dataclass
class FormalCertificate:
    target_routine: str
    status: str  # "PROVEN_EQUIVALENT", "DISPROVED", "TIMEOUT"
    solver: str
    solver_version: str
    theorem: str
    num_paths_verified: int
    inputs_verified: List[str]
    outputs_verified: List[str]
    verification_time_ms: float
    proof_hash: str
    counterexample: Optional[Dict[str, int]] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FormalCertificate":
        return cls(
            target_routine=data.get("target_routine", ""),
            status=data.get("status", "UNKNOWN"),
            solver=data.get("solver", "Z3"),
            solver_version=data.get("solver_version", ""),
            theorem=data.get("theorem", ""),
            num_paths_verified=data.get("num_paths_verified", 1),
            inputs_verified=data.get("inputs_verified", []),
            outputs_verified=data.get("outputs_verified", []),
            verification_time_ms=data.get("verification_time_ms", 0.0),
            proof_hash=data.get("proof_hash", ""),
            counterexample=data.get("counterexample", None),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "FormalCertificate":
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def generate_hash(cls, routine_name: str, theorem: str, time_stamp: float) -> str:
        payload = f"{routine_name}:{theorem}:{time_stamp}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
