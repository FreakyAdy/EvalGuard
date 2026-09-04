"""Unit tests for TimelineAuditor disclosure dates and DifferentialAnalyzer outliers."""

from __future__ import annotations

from evalguard.contamination.differential import DifferentialAnalyzer
from evalguard.contamination.timeline import TimelineAuditor


def test_timeline_auditor_postdated_agent() -> None:
    auditor = TimelineAuditor(benchmark_disclosure_date="2024-01-15")
    flag = auditor.evaluate_agent(agent_cutoff_date="2024-06-01")
    assert flag.is_contaminated is True
    assert flag.score == 1.0
    assert "POTENTIALLY EXPOSED" in flag.details


def test_timeline_auditor_predated_agent() -> None:
    auditor = TimelineAuditor(benchmark_disclosure_date="2024-01-15")
    flag = auditor.evaluate_agent(agent_cutoff_date="2023-11-01")
    assert flag.is_contaminated is False
    assert flag.score == 0.0
    assert "CLEAN TIMELINE" in flag.details


def test_differential_analyzer_detects_outlier() -> None:
    analyzer = DifferentialAnalyzer(outlier_z_threshold=2.5)
    cohort = {f"agent_{i}": 0.02 for i in range(15)}
    cohort["suspicious_agent"] = 1.0
    flag = analyzer.analyze_task_cohort(
        task_id="hard_task_42",
        target_agent_id="suspicious_agent",
        cohort_scores=cohort,
    )
    assert flag is not None
    assert flag.is_contaminated is True
    assert flag.score > 2.5
