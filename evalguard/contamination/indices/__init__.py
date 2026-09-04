"""Benchmark contamination indices repository and factory functions."""

from evalguard.contamination.indices.base import BenchmarkContaminationIndex
from evalguard.contamination.indices.humaneval_index import create_humaneval_index
from evalguard.contamination.indices.livecodebench_index import (
    create_livecodebench_index,
)
from evalguard.contamination.indices.mbpp_index import create_mbpp_index
from evalguard.contamination.indices.swebench_index import create_swebench_index

BUILTIN_INDICES = {
    "humaneval": create_humaneval_index,
    "swebench": create_swebench_index,
    "swebench-verified": create_swebench_index,
    "mbpp": create_mbpp_index,
    "livecodebench": create_livecodebench_index,
}


def get_benchmark_index(name: str) -> BenchmarkContaminationIndex:
    """Retrieve pre-built benchmark contamination index by name."""
    norm = name.lower().replace("_", "-")
    if norm in BUILTIN_INDICES:
        return BUILTIN_INDICES[norm]()
    raise KeyError(f"No pre-built index for '{name}'. Available: {list(BUILTIN_INDICES.keys())}")


__all__ = [
    "BUILTIN_INDICES",
    "BenchmarkContaminationIndex",
    "create_humaneval_index",
    "create_livecodebench_index",
    "create_mbpp_index",
    "create_swebench_index",
    "get_benchmark_index",
]
