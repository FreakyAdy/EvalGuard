"""Disclosure timeline analysis for pre-training cutoff vs benchmark release date."""

from __future__ import annotations

import logging
from datetime import date, datetime

from evalguard.report.schema import ContaminationFlag, ContaminationType

logger = logging.getLogger(__name__)


def parse_date(d: str | date | datetime) -> date:
    """Parse string (YYYY-MM-DD) or datetime into a standard date object."""
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").date()
    except Exception as e:
        raise ValueError(f"Invalid date format: '{d}'. Expected YYYY-MM-DD.") from e


class TimelineAuditor:
    """Evaluates whether an agent's training data cutoff postdates benchmark disclosure."""

    def __init__(self, benchmark_disclosure_date: str | date | datetime) -> None:
        self.disclosure_date = parse_date(benchmark_disclosure_date)

    def evaluate_agent(
        self,
        agent_cutoff_date: str | date | datetime | None,
        task_id: str = "general",
    ) -> ContaminationFlag:
        """Compare agent cutoff date against benchmark disclosure timeline."""
        if not agent_cutoff_date:
            return ContaminationFlag(
                method=ContaminationType.TIMELINE,
                score=0.5,
                threshold=0.0,
                is_contaminated=False,
                details=f"Agent pre-training cutoff date undisclosed for task {task_id}; exposure undetermined.",
            )

        agent_date = parse_date(agent_cutoff_date)
        days_after_disclosure = (agent_date - self.disclosure_date).days

        if days_after_disclosure > 0:
            is_exposed = True
            details = (
                f"POTENTIALLY EXPOSED: Agent cutoff date ({agent_date}) postdates benchmark "
                f"disclosure date ({self.disclosure_date}) by {days_after_disclosure} days. "
                f"Benchmark artifacts were publicly disclosed prior to model training."
            )
            score = 1.0
        else:
            is_exposed = False
            details = (
                f"CLEAN TIMELINE: Agent cutoff date ({agent_date}) predates benchmark "
                f"disclosure date ({self.disclosure_date}) by {abs(days_after_disclosure)} days."
            )
            score = 0.0

        return ContaminationFlag(
            method=ContaminationType.TIMELINE,
            score=score,
            threshold=0.0,
            is_contaminated=is_exposed,
            details=details,
        )
