"""Pre-built reference index for MBPP (Mostly Basic Python Problems)."""

from __future__ import annotations

from evalguard.contamination.indices.base import BenchmarkContaminationIndex


def create_mbpp_index() -> BenchmarkContaminationIndex:
    """Create benchmark index for MBPP (disclosed August 2021)."""
    idx = BenchmarkContaminationIndex(
        benchmark_name="mbpp",
        corpus_disclosure_date="2021-08-15",
    )

    idx.add_task(
        task_id="mbpp/1",
        prompt="Write a function to find the minimum cost path to reach (m, n) from (0, 0) for the given cost matrix cost[][] and a position (m, n).",
        solution="def min_cost(cost, m, n):\n    tc = [[0 for x in range(n+1)] for x in range(m+1)]\n    tc[0][0] = cost[0][0]\n",
        test_fixture="assert min_cost([[1, 2, 3], [4, 8, 2], [1, 5, 3]], 2, 2) == 8",
    )
    return idx
