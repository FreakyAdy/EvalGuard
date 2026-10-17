"""Statistical anomaly detection for universally passing or failing benchmark test cases."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

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
        if not 0.0 <= universal_pass_threshold <= 1.0:
            raise ValueError("universal_pass_threshold must be between 0 and 1")
        if not 0.0 <= universal_fail_threshold <= 1.0:
            raise ValueError("universal_fail_threshold must be between 0 and 1")
        if universal_fail_threshold >= universal_pass_threshold:
            raise ValueError("universal_fail_threshold must be lower than universal_pass_threshold")
        if (
            isinstance(min_cohort_size, bool)
            or not isinstance(min_cohort_size, int)
            or min_cohort_size < 1
        ):
            raise ValueError("min_cohort_size must be a positive integer")

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


@dataclass(frozen=True)
class CohortTaskAnalysis:
    """Structured analysis of one benchmark task across agent runs."""

    task_id: str
    agent_count: int
    trial_counts: dict[str, int]
    pass_counts: dict[str, int]
    pass_rates: dict[str, float]
    mean_pass_rate: float
    pass_rate_stddev: float
    z_scores: dict[str, float | None]
    bimodality_coefficient: float | None
    flags: tuple[str, ...]
    insufficient_data: bool
    status: TaskIntegrityStatus


class CohortMatrixAuditor:
    """Detect degenerate and cohort-dependent benchmark tasks from repeated agent outcomes.

    The matrix maps task IDs to agent IDs to repeated Boolean outcomes. Each agent
    contributes one pass rate, so agents with more trials do not dominate the
    cohort summary. The auditor reports universal pass/fail behavior, dispersion,
    per-agent z-score outliers, cohort polarization, and a moment-based bimodality
    coefficient. These are screening signals, not proof that a task is defective.
    """

    def __init__(
        self,
        universal_pass_threshold: float = 0.98,
        universal_fail_threshold: float = 0.02,
        min_agent_count: int = 10,
        z_score_threshold: float = 2.5,
        pass_rate_stddev_threshold: float = 0.25,
        bimodality_threshold: float = 5.0 / 9.0,
    ) -> None:
        for name, threshold in (
            ("universal_pass_threshold", universal_pass_threshold),
            ("universal_fail_threshold", universal_fail_threshold),
            ("pass_rate_stddev_threshold", pass_rate_stddev_threshold),
            ("bimodality_threshold", bimodality_threshold),
        ):
            if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
                raise ValueError(f"{name} must be a finite number between 0 and 1")

        if universal_fail_threshold >= universal_pass_threshold:
            raise ValueError("universal_fail_threshold must be lower than universal_pass_threshold")
        if (
            isinstance(min_agent_count, bool)
            or not isinstance(min_agent_count, int)
            or min_agent_count < 2
        ):
            raise ValueError("min_agent_count must be an integer of at least 2")
        if not math.isfinite(z_score_threshold) or z_score_threshold <= 0.0:
            raise ValueError("z_score_threshold must be a finite positive number")

        self.universal_pass_threshold = universal_pass_threshold
        self.universal_fail_threshold = universal_fail_threshold
        self.min_agent_count = min_agent_count
        self.z_score_threshold = z_score_threshold
        self.pass_rate_stddev_threshold = pass_rate_stddev_threshold
        self.bimodality_threshold = bimodality_threshold

    def analyze_task(
        self,
        task_id: str,
        agent_runs: Mapping[str, Sequence[bool]],
    ) -> CohortTaskAnalysis:
        """Analyze one task's repeated outcomes for every agent in the cohort."""
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        if not isinstance(agent_runs, Mapping) or not agent_runs:
            raise ValueError("agent_runs must be a non-empty mapping of agent IDs to outcomes")

        pass_counts: dict[str, int] = {}
        trial_counts: dict[str, int] = {}
        pass_rates: dict[str, float] = {}

        for agent_id, outcomes in agent_runs.items():
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise ValueError("agent IDs must be non-empty strings")
            if isinstance(outcomes, (str, bytes)) or not isinstance(outcomes, Sequence):
                raise ValueError(f"Outcomes for agent '{agent_id}' must be a sequence of booleans")
            if not outcomes:
                raise ValueError(f"Outcomes for agent '{agent_id}' must not be empty")
            if any(not isinstance(outcome, bool) for outcome in outcomes):
                raise ValueError(f"Outcomes for agent '{agent_id}' must contain only booleans")

            trials = len(outcomes)
            passed = sum(outcomes)
            trial_counts[agent_id] = trials
            pass_counts[agent_id] = passed
            pass_rates[agent_id] = passed / trials

        rates = list(pass_rates.values())
        agent_count = len(rates)
        mean_pass_rate = sum(rates) / agent_count
        variance = sum((rate - mean_pass_rate) ** 2 for rate in rates) / agent_count
        pass_rate_stddev = math.sqrt(variance)

        if pass_rate_stddev == 0.0:
            z_scores: dict[str, float | None] = {agent_id: None for agent_id in pass_rates}
        else:
            z_scores = {
                agent_id: (rate - mean_pass_rate) / pass_rate_stddev
                for agent_id, rate in pass_rates.items()
            }

        bimodality = self._bimodality_coefficient(rates)
        insufficient_data = agent_count < self.min_agent_count
        flags: list[str] = []

        if not insufficient_data:
            if mean_pass_rate >= self.universal_pass_threshold:
                flags.append("universal_pass")
            elif mean_pass_rate <= self.universal_fail_threshold:
                flags.append("universal_fail")

            if pass_rate_stddev >= self.pass_rate_stddev_threshold:
                flags.append("high_pass_rate_dispersion")

            outliers = [
                agent_id
                for agent_id, z_score in z_scores.items()
                if z_score is not None and abs(z_score) >= self.z_score_threshold
            ]
            if outliers:
                flags.append("agent_outlier")

            if bimodality is not None and bimodality >= self.bimodality_threshold:
                flags.append("bimodal_pass_rate_distribution")

            low_performers = sum(rate <= self.universal_fail_threshold for rate in rates)
            high_performers = sum(rate >= self.universal_pass_threshold for rate in rates)
            required_group_size = max(2, math.ceil(agent_count * 0.2))
            if low_performers >= required_group_size and high_performers >= required_group_size:
                flags.append("polarized_cohort")

        return CohortTaskAnalysis(
            task_id=task_id,
            agent_count=agent_count,
            trial_counts=trial_counts,
            pass_counts=pass_counts,
            pass_rates=pass_rates,
            mean_pass_rate=round(mean_pass_rate, 4),
            pass_rate_stddev=round(pass_rate_stddev, 4),
            z_scores={
                agent_id: None if z_score is None else round(z_score, 4)
                for agent_id, z_score in z_scores.items()
            },
            bimodality_coefficient=(None if bimodality is None else round(bimodality, 4)),
            flags=tuple(flags),
            insufficient_data=insufficient_data,
            status=TaskIntegrityStatus.SUSPECT if flags else TaskIntegrityStatus.PASS,
        )

    def analyze_matrix(
        self,
        matrix: Mapping[str, Mapping[str, Sequence[bool]]],
    ) -> dict[str, CohortTaskAnalysis]:
        """Analyze a complete task -> agent -> repeated-outcome matrix."""
        if not isinstance(matrix, Mapping) or not matrix:
            raise ValueError("matrix must contain at least one task")
        return {
            task_id: self.analyze_task(task_id, agent_runs)
            for task_id, agent_runs in matrix.items()
        }

    def export_flawed_test_issue(
        self,
        benchmark_name: str,
        analysis: CohortTaskAnalysis,
    ) -> str:
        """Render an anomaly finding as GitHub Issue Markdown."""
        if not isinstance(benchmark_name, str) or not benchmark_name.strip():
            raise ValueError("benchmark_name must be a non-empty string")
        if not analysis.flags:
            raise ValueError("Only flagged cohort anomalies can be exported as issues")

        def md_cell(value: str) -> str:
            return value.replace("|", "\\|")

        flag_text = ", ".join(f"`{flag}`" for flag in analysis.flags)
        bimodality_text = (
            "n/a"
            if analysis.bimodality_coefficient is None
            else f"{analysis.bimodality_coefficient:.3f}"
        )
        lines = [
            f"## EvalGuard Cohort Integrity Report: Task {md_cell(analysis.task_id)}",
            "",
            f"**Benchmark:** {md_cell(benchmark_name)}",
            f"**Agents:** {analysis.agent_count}",
            f"**Mean per-agent pass rate:** {analysis.mean_pass_rate:.1%}",
            f"**Pass-rate standard deviation:** {analysis.pass_rate_stddev:.3f}",
            f"**Bimodality coefficient:** {bimodality_text}",
            f"**Flags:** {flag_text}",
            "",
            "### Per-agent outcomes",
            "",
            "| Agent | Passed trials | Trials | Pass rate | Z-score |",
            "|---|---:|---:|---:|---:|",
        ]
        for agent_id in sorted(analysis.pass_rates):
            z_score = analysis.z_scores[agent_id]
            z_display = "n/a" if z_score is None else f"{z_score:+.2f}"
            lines.append(
                f"| {md_cell(agent_id)} | {analysis.pass_counts[agent_id]} | "
                f"{analysis.trial_counts[agent_id]} | "
                f"{analysis.pass_rates[agent_id]:.1%} | {z_display} |"
            )
        lines.extend(
            [
                "",
                "### Interpretation",
                "",
                "These statistics are screening signals, not proof that a benchmark task "
                "is defective. Review the task specification and environment before changing "
                "the test or excluding the result.",
                "",
                "> Generated by EvalGuard's multi-agent cohort auditor.",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _bimodality_coefficient(values: Sequence[float]) -> float | None:
        """Return the finite-sample bimodality coefficient, or None if undefined."""
        n = len(values)
        if n < 4:
            return None

        mean = sum(values) / n
        centered = [value - mean for value in values]
        second_moment = sum(value**2 for value in centered) / n
        if second_moment == 0.0:
            return None

        third_moment = sum(value**3 for value in centered) / n
        fourth_moment = sum(value**4 for value in centered) / n
        skewness = third_moment / (second_moment**1.5)
        excess_kurtosis = fourth_moment / (second_moment**2) - 3.0
        correction = 3.0 * (n - 1) ** 2 / ((n - 2) * (n - 3))
        denominator = excess_kurtosis + correction
        if denominator <= 0.0:
            return None

        coefficient = (skewness**2 + 1.0) / denominator
        return coefficient if math.isfinite(coefficient) else None
