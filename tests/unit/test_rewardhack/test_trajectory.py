"""Unit tests for TrajectoryAnalyzer anomaly scoring."""

from __future__ import annotations

from evalguard.rewardhack.trajectory_analyzer import (
    TrajectoryAnalyzer,
    TrajectoryEvent,
)


def test_trajectory_analyzer_anomalous_zero_shot() -> None:
    analyzer = TrajectoryAnalyzer(task_complexity_baseline_seconds=120.0)
    # Agent solved it in 1.5 seconds with 1 direct edit and zero prior test runs
    events = [
        TrajectoryEvent(action_type="edit", timestamp_offset=1.2, target="solution.py"),
    ]
    rec = analyzer.analyze(events, total_duration_seconds=1.5, final_passed=True)
    assert rec.trajectory_anomaly_score >= 0.7
    assert rec.first_attempt_success is True
    assert len(rec.notes) >= 2


def test_trajectory_analyzer_clean_iterative_solve() -> None:
    analyzer = TrajectoryAnalyzer(task_complexity_baseline_seconds=60.0)
    events = [
        TrajectoryEvent(action_type="edit", timestamp_offset=15.0),
        TrajectoryEvent(action_type="test", timestamp_offset=25.0, success=False),
        TrajectoryEvent(action_type="edit", timestamp_offset=40.0),
        TrajectoryEvent(action_type="test", timestamp_offset=55.0, success=True),
    ]
    rec = analyzer.analyze(events, total_duration_seconds=65.0, final_passed=True)
    assert rec.trajectory_anomaly_score == 0.0
    assert rec.first_attempt_success is False
