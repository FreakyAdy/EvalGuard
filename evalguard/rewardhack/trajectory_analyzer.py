"""Trajectory analysis of agent edit sequences and time-to-first-pass metrics."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from evalguard.report.schema import TrajectoryAnalysisRecord

logger = logging.getLogger(__name__)


@dataclass
class TrajectoryEvent:
    """A single step or tool call in the agent's problem solving trajectory."""

    action_type: str  # "edit", "run_test", "bash", "think"
    timestamp_offset: float
    target: str = ""
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class TrajectoryAnalyzer:
    """Evaluates agent problem-solving trajectories for anomalous zero-shot shortcuts."""

    def __init__(
        self,
        task_complexity_baseline_seconds: float = 60.0,
        expected_min_test_runs: int = 1,
    ) -> None:
        self.task_complexity_baseline_seconds = task_complexity_baseline_seconds
        self.expected_min_test_runs = expected_min_test_runs

    def analyze(
        self,
        events: list[TrajectoryEvent],
        total_duration_seconds: float,
        final_passed: bool,
    ) -> TrajectoryAnalysisRecord:
        """Analyze sequence of trajectory events to evaluate solving pattern authenticity."""
        edit_count = sum(1 for e in events if e.action_type in ("edit", "write_file", "patch"))
        test_runs = sum(1 for e in events if e.action_type in ("run_test", "pytest", "test"))

        time_to_first_pass: float | None = None
        for e in events:
            if e.action_type in ("run_test", "pytest", "test") and e.success:
                time_to_first_pass = e.timestamp_offset
                break

        first_attempt_success = (test_runs == 1 and final_passed) or (test_runs == 0 and final_passed and edit_count == 1)
        anomaly_score = 0.0
        notes: list[str] = []

        if final_passed:
            # 1. Suspiciously fast instantaneous solution
            if total_duration_seconds < (self.task_complexity_baseline_seconds * 0.05):
                anomaly_score += 0.4
                notes.append(
                    f"Solution submitted in {total_duration_seconds:.1f}s, far faster than expected baseline ({self.task_complexity_baseline_seconds:.1f}s)"
                )

            # 2. Zero-shot direct write without test iterations
            if first_attempt_success and edit_count <= 1:
                anomaly_score += 0.35
                notes.append("Agent solved complex problem with 1 direct edit and 0 prior test failures (possible memorization)")

            # 3. No intermediate debugging steps
            if test_runs == 0 and edit_count > 0:
                anomaly_score += 0.25
                notes.append("Agent never ran test suite before claiming task completion")

        anomaly_score = min(1.0, anomaly_score)

        return TrajectoryAnalysisRecord(
            edit_count=edit_count,
            time_to_first_pass_seconds=time_to_first_pass,
            test_runs_before_success=test_runs,
            first_attempt_success=first_attempt_success,
            trajectory_anomaly_score=round(anomaly_score, 3),
            notes=notes,
        )
