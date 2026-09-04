"""Reference solver execution and trivial-permissiveness test verification."""

from __future__ import annotations

import logging
from collections.abc import Callable

from evalguard.report.schema import TaskIntegrityStatus, TestIntegrityRecord

logger = logging.getLogger(__name__)

# Canonical trivial dummy solutions to check if test is overly permissive
TRIVIAL_SOLUTIONS = [
    "",
    "def solution(*args, **kwargs): return None\n",
    "def solution(*args, **kwargs): return True\n",
    "def solution(*args, **kwargs): return False\n",
    "def solution(*args, **kwargs): return 0\n",
    "pass\n",
]


class ReferenceRunner:
    """Validates benchmark test correctness by evaluating against reference and trivial solutions."""

    def __init__(
        self,
        reference_solver: Callable[[str], str | bool] | None = None,
        test_executor: Callable[[str, str], bool] | None = None,
    ) -> None:
        self.reference_solver = reference_solver
        self.test_executor = test_executor

    def audit_task_tests(
        self,
        task_id: str,
        test_code: str,
        reference_solution: str | None = None,
    ) -> TestIntegrityRecord:
        """Evaluate if reference solution passes and trivial solutions fail."""
        evidence: list[str] = []
        status = TaskIntegrityStatus.PASS
        ref_passed: bool | None = None
        trivially_permissive = False

        if not self.test_executor:
            # If no dynamic test executor is provided, mark as unverified
            return TestIntegrityRecord(
                status=TaskIntegrityStatus.PASS,
                reference_solver_passed=None,
                trivially_permissive=False,
                evidence=["Test executor not configured; reference dynamic check skipped."],
            )

        # 1. Evaluate Reference Solver
        ref_sol = reference_solution
        if ref_sol is None and self.reference_solver is not None:
            res = self.reference_solver(task_id)
            ref_sol = str(res) if res is not None else None

        if ref_sol is not None:
            try:
                ref_passed = self.test_executor(ref_sol, test_code)
                if not ref_passed:
                    status = TaskIntegrityStatus.INVALID
                    evidence.append(
                        f"CRITICAL TEST FLAW: Canonical reference solution failed test fixture for task {task_id}. "
                        "The benchmark test itself is broken, outdated, or overly restrictive."
                    )
            except Exception as e:
                status = TaskIntegrityStatus.INVALID
                ref_passed = False
                evidence.append(f"Reference solution execution crashed test runner: {e}")

        # 2. Check for Overly Permissive Tests (False Positives)
        permissive_hits: list[str] = []
        for dummy in TRIVIAL_SOLUTIONS:
            try:
                dummy_passed = self.test_executor(dummy, test_code)
                if dummy_passed:
                    permissive_hits.append(dummy.strip() or "<empty>")
            except Exception:
                # Expected to fail / raise
                pass

        if permissive_hits:
            trivially_permissive = True
            if status != TaskIntegrityStatus.INVALID:
                status = TaskIntegrityStatus.SUSPECT
            evidence.append(
                f"OVERLY PERMISSIVE TEST: Test case accepted trivial non-solution(s): {permissive_hits}. "
                "Agents can pass this test without writing functional code."
            )

        return TestIntegrityRecord(
            status=status,
            reference_solver_passed=ref_passed,
            trivially_permissive=trivially_permissive,
            evidence=evidence,
        )
