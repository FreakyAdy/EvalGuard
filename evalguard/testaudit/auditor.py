"""Benchmark test case integrity auditor and GitHub issue generator."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from evalguard.adapters.base import HarnessAdapter
from evalguard.report.schema import TaskIntegrityStatus, TestIntegrityRecord
from evalguard.testaudit.cross_harness import CrossHarnessAuditor
from evalguard.testaudit.reference_runner import ReferenceRunner
from evalguard.testaudit.statistical_detector import StatisticalDetector

logger = logging.getLogger(__name__)


class TestAuditor:
    """Comprehensive auditor for benchmark test case correctness, stability, and integrity."""

    __test__ = False  # Prevent pytest from treating this as a test class

    def __init__(
        self,
        reference_solver: Callable[[str], str | bool] | None = None,
        test_executor: Callable[[str, str], bool] | None = None,
        universal_pass_threshold: float = 0.98,
        universal_fail_threshold: float = 0.02,
    ) -> None:
        self.reference_runner = ReferenceRunner(reference_solver, test_executor)
        self.statistical_detector = StatisticalDetector(
            universal_pass_threshold=universal_pass_threshold,
            universal_fail_threshold=universal_fail_threshold,
        )

    def audit_task(
        self,
        task_id: str,
        test_code: str,
        reference_solution: str | None = None,
        cohort_outcomes: Sequence[bool] | Mapping[str, bool] | None = None,
        alternate_adapter_pair: tuple[HarnessAdapter, HarnessAdapter, Any] | None = None,
    ) -> TestIntegrityRecord:
        """Run full test case integrity validation on a task."""
        all_evidence: list[str] = []
        worst_status = TaskIntegrityStatus.PASS
        ref_passed: bool | None = None
        trivially_permissive = False
        univ_rate: float | None = None
        cross_diverges = False

        # 1. Reference and trivial solution evaluation
        if test_code:
            ref_rec = self.reference_runner.audit_task_tests(
                task_id=task_id,
                test_code=test_code,
                reference_solution=reference_solution,
            )
            all_evidence.extend(ref_rec.evidence)
            ref_passed = ref_rec.reference_solver_passed
            trivially_permissive = ref_rec.trivially_permissive
            if ref_rec.status == TaskIntegrityStatus.INVALID:
                worst_status = TaskIntegrityStatus.INVALID
            elif ref_rec.status == TaskIntegrityStatus.SUSPECT and worst_status != TaskIntegrityStatus.INVALID:
                worst_status = TaskIntegrityStatus.SUSPECT

        # 2. Statistical anomaly detection
        if cohort_outcomes:
            stat_rec = self.statistical_detector.check_task_cohort(task_id, cohort_outcomes)
            all_evidence.extend(stat_rec.evidence)
            univ_rate = stat_rec.universal_pass_rate
            if stat_rec.status == TaskIntegrityStatus.SUSPECT and worst_status != TaskIntegrityStatus.INVALID:
                worst_status = TaskIntegrityStatus.SUSPECT

        # 3. Cross-harness consistency check
        if alternate_adapter_pair:
            h1, h2, agent = alternate_adapter_pair
            checker = CrossHarnessAuditor(h1, h2)
            cross_rec = checker.audit_task(task_id, agent)
            all_evidence.extend(cross_rec.evidence)
            cross_diverges = cross_rec.cross_harness_divergence
            if cross_rec.status == TaskIntegrityStatus.INVALID:
                worst_status = TaskIntegrityStatus.INVALID

        return TestIntegrityRecord(
            status=worst_status,
            reference_solver_passed=ref_passed,
            trivially_permissive=trivially_permissive,
            universal_pass_rate=univ_rate,
            cross_harness_divergence=cross_diverges,
            evidence=all_evidence,
        )

    def export_github_issue_markdown(
        self,
        benchmark_name: str,
        task_id: str,
        record: TestIntegrityRecord,
    ) -> str:
        """Format an audit finding as a Markdown GitHub Issue ready to file on benchmark repository."""
        lines = [
            f"## [EvalGuard Test Integrity Report] Task `{task_id}` Status: **{record.status.value}**",
            "",
            f"**Benchmark**: `{benchmark_name}`  ",
            f"**Task ID**: `{task_id}`  ",
            f"**Integrity Status**: `{record.status.value}`  ",
            "",
            "### Summary of Findings",
        ]

        if record.reference_solver_passed is False:
            lines.append("- :x: **Reference Solution Failed**: The official reference solver fails this test.")
        if record.trivially_permissive:
            lines.append("- :warning: **Overly Permissive**: Test accepts trivial non-functional code.")
        if record.universal_pass_rate is not None:
            lines.append(f"- :bar_chart: **Cohort Pass Rate**: `{record.universal_pass_rate:.1%}`")
        if record.cross_harness_divergence:
            lines.append("- :repeat: **Cross-Harness Divergence**: Results differ across sandboxing environments.")

        lines.extend([
            "",
            "### Audit Evidence",
            "```text",
        ])
        for ev in record.evidence:
            lines.append(f"- {ev}")
        lines.extend([
            "```",
            "",
            "> *Report generated automatically by EvalGuard Benchmark Integrity Infrastructure.*",
        ])

        return "\n".join(lines)
