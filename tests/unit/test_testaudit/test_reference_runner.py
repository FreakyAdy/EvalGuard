"""Unit tests for ReferenceRunner and StatisticalDetector test audits."""

from __future__ import annotations

import pytest

from evalguard.report.schema import TaskIntegrityStatus
from evalguard.testaudit.reference_runner import ReferenceRunner
from evalguard.testaudit.statistical_detector import StatisticalDetector


def test_reference_runner_detects_flawed_test() -> None:
    # Test executor where reference solution fails the assertions
    def broken_test_executor(sol: str, test: str) -> bool:
        if "correct_reference" in sol:
            return False  # test incorrectly rejects correct solution
        return True

    runner = ReferenceRunner(test_executor=broken_test_executor)
    rec = runner.audit_task_tests(
        task_id="flawed_01",
        test_code="assert False",
        reference_solution="def correct_reference(): pass",
    )
    assert rec.status == TaskIntegrityStatus.INVALID
    assert rec.reference_solver_passed is False
    assert len(rec.evidence) >= 1


def test_reference_runner_detects_permissive_test() -> None:
    # Test executor that accepts empty or trivial pass
    def overly_permissive_executor(sol: str, test: str) -> bool:
        return True  # accepts everything!

    runner = ReferenceRunner(test_executor=overly_permissive_executor)
    rec = runner.audit_task_tests(
        task_id="perm_01",
        test_code="pass",
        reference_solution="def real_code(): pass",
    )
    assert rec.trivially_permissive is True
    assert rec.status in (TaskIntegrityStatus.SUSPECT, TaskIntegrityStatus.INVALID)


def test_statistical_detector_universal_pass_fail() -> None:
    detector = StatisticalDetector(min_cohort_size=10)

    # 100% pass
    all_pass = [True] * 20
    rec_pass = detector.check_task_cohort("task_easy", all_pass)
    assert rec_pass.status == TaskIntegrityStatus.SUSPECT
    assert "UNIVERSAL PASS ANOMALY" in rec_pass.evidence[0]

    # 100% fail
    all_fail = [False] * 20
    rec_fail = detector.check_task_cohort("task_impossible", all_fail)
    assert rec_fail.status == TaskIntegrityStatus.SUSPECT
    assert "UNIVERSAL FAIL ANOMALY" in rec_fail.evidence[0]


@pytest.mark.parametrize(
    ("pass_threshold", "fail_threshold"),
    [
        (1.01, 0.02),
        (-0.01, 0.0),
        (0.98, 1.01),
        (0.98, -0.01),
        (0.98, 0.99),
        (float("nan"), 0.02),
        (0.98, float("nan")),
    ],
)
def test_statistical_detector_rejects_invalid_thresholds(
    pass_threshold: float, fail_threshold: float
) -> None:
    with pytest.raises(ValueError, match="threshold"):
        StatisticalDetector(
            universal_pass_threshold=pass_threshold,
            universal_fail_threshold=fail_threshold,
        )


@pytest.mark.parametrize("min_cohort_size", [0, -1, True, 1.5])
def test_statistical_detector_rejects_invalid_minimum_cohort_size(
    min_cohort_size: int,
) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        StatisticalDetector(min_cohort_size=min_cohort_size)


def test_test_auditor_export_github_issue() -> None:
    from evalguard.testaudit.auditor import TestAuditor

    auditor = TestAuditor()
    rec = auditor.audit_task(
        task_id="test_issue_01",
        test_code="",
        cohort_outcomes=[False] * 15 + [True],
    )
    md = auditor.export_github_issue_markdown("SWE-bench", "test_issue_01", rec)
    assert "EvalGuard Test Integrity Report" in md
    assert "SWE-bench" in md
