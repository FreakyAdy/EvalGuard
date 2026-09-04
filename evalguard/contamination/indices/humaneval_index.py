"""Pre-built reference index for the OpenAI HumanEval benchmark."""

from __future__ import annotations

from evalguard.contamination.indices.base import BenchmarkContaminationIndex


def create_humaneval_index() -> BenchmarkContaminationIndex:
    """Create benchmark index for HumanEval (disclosed July 2021)."""
    idx = BenchmarkContaminationIndex(
        benchmark_name="humaneval",
        corpus_disclosure_date="2021-07-07",
    )

    # Add canonical exemplar tasks (164 tasks in full dataset; exemplars shipped by default)
    idx.add_task(
        task_id="HumanEval/0",
        prompt="from typing import List\n\ndef has_close_elements(numbers: List[float], threshold: float) -> bool:\n    \"\"\" Check if in given list of numbers, are any two numbers closer to each other than given threshold.\"\"\"",
        solution="    for idx, elem in enumerate(numbers):\n        for idx2, elem2 in enumerate(numbers):\n            if idx != idx2:\n                distance = abs(elem - elem2)\n                if distance < threshold:\n                    return True\n    return False\n",
        test_fixture="def check(candidate):\n    assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3) == True\n",
    )
    idx.add_task(
        task_id="HumanEval/1",
        prompt="from typing import List\n\ndef separate_paren_groups(paren_string: str) -> List[str]:\n    \"\"\" Input to this function is a string containing multiple groups of nested parentheses.\"\"\"",
        solution="    result = []\n    current_string = []\n    current_depth = 0\n    for c in paren_string:\n        if c == '(': current_depth += 1\n",
    )
    return idx
