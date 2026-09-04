"""Cross-harness consistency auditing to detect harness-dependent tasks."""

from __future__ import annotations

import logging
from typing import Any

from evalguard.adapters.base import HarnessAdapter
from evalguard.report.schema import TaskIntegrityStatus, TestIntegrityRecord

logger = logging.getLogger(__name__)


class CrossHarnessAuditor:
    """Executes identical benchmark tasks across two harness backends to identify environment leaks."""

    def __init__(self, adapter_a: HarnessAdapter, adapter_b: HarnessAdapter) -> None:
        self.adapter_a = adapter_a
        self.adapter_b = adapter_b

    def audit_task(self, task_id: str, agent: Any) -> TestIntegrityRecord:
        """Run task on both harnesses and flag divergence."""
        res_a = self.adapter_a.run_task(agent, task_id)
        res_b = self.adapter_b.run_task(agent, task_id)

        diverges = (res_a.passed != res_b.passed)
        evidence: list[str] = []
        status = TaskIntegrityStatus.PASS

        if diverges:
            status = TaskIntegrityStatus.INVALID
            evidence.append(
                f"CROSS-HARNESS DIVERGENCE: Task {task_id} yielded conflicting outcomes: "
                f"{self.adapter_a.name}={res_a.passed} vs {self.adapter_b.name}={res_b.passed}. "
                f"Task result is brittle and dependent on harness environment artifacts."
            )
        else:
            evidence.append(
                f"Cross-harness consistent ({self.adapter_a.name}={res_a.passed}, {self.adapter_b.name}={res_b.passed})"
            )

        return TestIntegrityRecord(
            status=status,
            cross_harness_divergence=diverges,
            evidence=evidence,
        )
