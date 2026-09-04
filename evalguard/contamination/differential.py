"""Differential performance analysis across multiple agents to flag statistical outliers."""

from __future__ import annotations

import statistics
from collections.abc import Mapping

from evalguard.report.schema import ContaminationFlag, ContaminationType


class DifferentialAnalyzer:
    """Detects statistical outlier performance on individual tasks across a cohort of agents.

    If an agent dramatically outperforms the rest of the field on a specific task (Z-score > 2.5),
    this indicates task-specific memorization/contamination rather than general model capability.
    """

    def __init__(self, outlier_z_threshold: float = 2.5) -> None:
        self.outlier_z_threshold = outlier_z_threshold

    def analyze_task_cohort(
        self,
        task_id: str,
        target_agent_id: str,
        # agent_id -> score or pass_rate (0.0 to 1.0)
        cohort_scores: Mapping[str, float],
    ) -> ContaminationFlag | None:
        """Analyze whether target agent is a statistical outlier on this specific task."""
        if len(cohort_scores) < 3:
            # Need at least 3 agents to compute a meaningful Z-score
            return None

        scores = list(cohort_scores.values())
        mean_score = statistics.mean(scores)
        stdev_score = statistics.stdev(scores) if len(scores) > 1 else 0.0

        target_score = cohort_scores.get(target_agent_id)
        if target_score is None:
            return None

        if stdev_score == 0.0:
            z_score = 0.0
        else:
            z_score = (target_score - mean_score) / stdev_score

        is_outlier = z_score >= self.outlier_z_threshold and target_score > 0.8

        details = (
            f"Differential analysis for {target_agent_id} on {task_id}: "
            f"score={target_score:.2f}, cohort_mean={mean_score:.2f}, stdev={stdev_score:.2f}, Z={z_score:.2f}. "
        )
        if is_outlier:
            details += (
                f"STATISTICAL OUTLIER: Agent performance exceeds cohort by Z={z_score:.2f} (> {self.outlier_z_threshold}), "
                "suggesting task-specific data contamination."
            )
        else:
            details += "Performance within expected cohort distribution."

        return ContaminationFlag(
            method=ContaminationType.DIFFERENTIAL,
            score=round(z_score, 2),
            threshold=self.outlier_z_threshold,
            is_contaminated=is_outlier,
            details=details,
        )
