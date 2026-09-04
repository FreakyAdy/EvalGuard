"""Fluent builder for constructing and computing aggregated EvalGuard reports."""

from __future__ import annotations

from typing import Any

from evalguard.report.schema import (
    EvalGuardReport,
    ReportSummary,
    TaskAuditRecord,
    TaskIntegrityStatus,
)


class ReportBuilder:
    """Builder for assembling TaskAuditRecords into an EvalGuardReport."""

    def __init__(
        self,
        benchmark_id: str,
        agent_id: str,
        harness_name: str = "unknown",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.benchmark_id = benchmark_id
        self.agent_id = agent_id
        self.harness_name = harness_name
        self.metadata = metadata or {}
        self.tasks: list[TaskAuditRecord] = []

    def add_task_result(self, task: TaskAuditRecord) -> ReportBuilder:
        """Add a completed task audit record."""
        self.tasks.append(task)
        return self

    def build(self) -> EvalGuardReport:
        """Calculate summary statistics and build the immutable report."""
        total_tasks = len(self.tasks)
        passed_tasks = sum(1 for t in self.tasks if t.agent_passed)
        violations_total = sum(len(t.violations) for t in self.tasks)
        tasks_with_violations = sum(1 for t in self.tasks if len(t.violations) > 0)

        tasks_with_reward_hack = sum(
            1 for t in self.tasks if t.reward_hack and t.reward_hack.confidence_score >= 0.5
        )

        tasks_with_contamination = sum(
            1 for t in self.tasks if any(cf.is_contaminated for cf in t.contamination_flags)
        )

        suspect_or_invalid_tests = sum(
            1
            for t in self.tasks
            if t.test_integrity
            and t.test_integrity.status
            in (TaskIntegrityStatus.SUSPECT, TaskIntegrityStatus.INVALID)
        )

        clean_passed_tasks = sum(
            1
            for t in self.tasks
            if t.agent_passed
            and len(t.violations) == 0
            and (not t.reward_hack or t.reward_hack.confidence_score < 0.2)
            and not any(cf.is_contaminated for cf in t.contamination_flags)
            and (not t.test_integrity or t.test_integrity.status == TaskIntegrityStatus.PASS)
        )

        summary = ReportSummary(
            total_tasks=total_tasks,
            agent_passed_tasks=passed_tasks,
            boundary_violations_total=violations_total,
            tasks_with_violations=tasks_with_violations,
            tasks_with_reward_hack=tasks_with_reward_hack,
            tasks_with_contamination=tasks_with_contamination,
            suspect_or_invalid_tests=suspect_or_invalid_tests,
            clean_passed_tasks=clean_passed_tasks,
        )

        return EvalGuardReport(
            benchmark_id=self.benchmark_id,
            agent_id=self.agent_id,
            harness_name=self.harness_name,
            summary=summary,
            tasks=self.tasks,
            metadata=self.metadata,
        )
