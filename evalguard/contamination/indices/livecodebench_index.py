"""Pre-built reference index for LiveCodeBench."""

from __future__ import annotations

from evalguard.contamination.indices.base import BenchmarkContaminationIndex


def create_livecodebench_index() -> BenchmarkContaminationIndex:
    """Create benchmark index for LiveCodeBench (continuous releases from 2024-05 onwards)."""
    idx = BenchmarkContaminationIndex(
        benchmark_name="livecodebench",
        corpus_disclosure_date="2024-05-01",
    )

    idx.add_task(
        task_id="LCB/2024-05/001",
        prompt="Solve LeetCode Biweekly Contest 130 Problem D.",
        solution="class Solution:\n    def minimumCost(self, target: str, words: List[str], costs: List[int]) -> int:\n        # Trie + DP\n        pass",
        test_fixture="assert Solution().minimumCost('abcdef', ['abdef','abc','d','def','ef'], [100,1,1,10,5]) == 7",
    )
    return idx
