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
    def generate_hash(cls, routine_name: str, theorem: str, time_stamp: float) -> str:
        payload = f"{routine_name}:{theorem}:{time_stamp}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
