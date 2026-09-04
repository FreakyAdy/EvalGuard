"""Statistical anomaly detection for universally passing or failing benchmark test cases."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence

from evalguard.report.schema import TaskIntegrityStatus, TestIntegrityRecord

logger = logging.getLogger(__name__)


class StatisticalDetector:
    """Audits task pass rates across multi-agent benchmark runs to detect degenerate tests."""

    def __init__(
        self,
        universal_pass_threshold: float = 0.98,
        universal_fail_threshold: float = 0.02,
        min_cohort_size: int = 10,
    ) -> None:
        self.universal_pass_threshold = universal_pass_threshold
        self.universal_fail_threshold = universal_fail_threshold
        self.min_cohort_size = min_cohort_size

    def check_task_cohort(
        self,
        task_id: str,
        # Sequence of booleans (whether each agent in benchmark passed) or dict of agent_id -> bool
        agent_outcomes: Sequence[bool] | Mapping[str, bool],
    ) -> TestIntegrityRecord:
        """Evaluate if task exhibits extreme degenerate pass rates across the agent population."""
        outcomes = (
            list(agent_outcomes.values())
            if isinstance(agent_outcomes, Mapping)
            else list(agent_outcomes)
        )
        cohort_size = len(outcomes)

        if cohort_size < self.min_cohort_size:
            return TestIntegrityRecord(
                status=TaskIntegrityStatus.PASS,
                evidence=[
                    f"Cohort size ({cohort_size}) below statistical minimum ({self.min_cohort_size})"
                ],
            )

        passed_count = sum(1 for o in outcomes if o)
        pass_rate = passed_count / cohort_size

        evidence: list[str] = []
        status = TaskIntegrityStatus.PASS

        if pass_rate >= self.universal_pass_threshold:
            status = TaskIntegrityStatus.SUSPECT
            evidence.append(
                f"UNIVERSAL PASS ANOMALY: {passed_count}/{cohort_size} agents passed ({pass_rate:.1%}). "
                f"Test may be a tautology, too trivial, or not asserting task completion."
            )
        elif pass_rate <= self.universal_fail_threshold:
            status = TaskIntegrityStatus.SUSPECT
            evidence.append(
                f"UNIVERSAL FAIL ANOMALY: Only {passed_count}/{cohort_size} agents passed ({pass_rate:.1%}). "
                f"Test case may be broken, impossible, or asserting unstated environment requirements."
            )

        return TestIntegrityRecord(
            status=status,
            universal_pass_rate=round(pass_rate, 4),
            evidence=evidence,
        )
