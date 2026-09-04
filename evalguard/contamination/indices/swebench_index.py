"""Pre-built reference index for SWE-bench / SWE-bench Verified."""

from __future__ import annotations

from evalguard.contamination.indices.base import BenchmarkContaminationIndex


def create_swebench_index() -> BenchmarkContaminationIndex:
    """Create benchmark index for SWE-bench (disclosed October 2023, Verified August 2024)."""
    idx = BenchmarkContaminationIndex(
        benchmark_name="swebench-verified",
        corpus_disclosure_date="2024-08-14",
    )

    idx.add_task(
        task_id="django__django-11099",
        prompt="UsernameValidator regex allows trailing newline in username.",
        solution="diff --git a/django/contrib/auth/validators.py b/django/contrib/auth/validators.py\n-regex = r'^[\\w.@+-]+$'\n+regex = r'\\A[\\w.@+-]+\\Z'",
        test_fixture="def test_trailing_newline(): assert not validator('user\\n')",
    )
    idx.add_task(
        task_id="sympy__sympy-13480",
        prompt="Integral calculation with hyperbolic functions raises TypeError.",
        solution="diff --git a/sympy/functions/elementary/hyperbolic.py\n+if isinstance(arg, Symbol): return False",
    )
    return idx
