"""Tests for statistical and multi-agent cohort test auditing."""

from __future__ import annotations

import pytest

from evalguard.report.schema import TaskIntegrityStatus
from evalguard.testaudit.statistical_detector import CohortMatrixAuditor


def _agent_runs(pass_rates: list[float], trials: int = 10) -> dict[str, list[bool]]:
    """Build deterministic repeated outcomes with the requested pass rates."""
    runs: dict[str, list[bool]] = {}
    for index, rate in enumerate(pass_rates):
        passed = round(rate * trials)
        runs[f"agent-{index:02d}"] = [True] * passed + [False] * (trials - passed)
    return runs


def test_cohort_matrix_detects_universal_pass_and_fail() -> None:
    auditor = CohortMatrixAuditor()
    all_pass = auditor.analyze_task("too-easy", _agent_runs([1.0] * 10))
    all_fail = auditor.analyze_task("impossible", _agent_runs([0.0] * 10))

    assert all_pass.status == TaskIntegrityStatus.SUSPECT
    assert "universal_pass" in all_pass.flags
    assert all_pass.mean_pass_rate == 1.0
    assert all_pass.pass_rate_stddev == 0.0
    assert set(all_pass.z_scores.values()) == {None}

    assert all_fail.status == TaskIntegrityStatus.SUSPECT
    assert "universal_fail" in all_fail.flags
    assert all_fail.mean_pass_rate == 0.0


def test_cohort_matrix_detects_outlier_agent_with_z_score() -> None:
    auditor = CohortMatrixAuditor()
    rates = [0.8] * 9 + [0.0]
    analysis = auditor.analyze_task("outlier-task", _agent_runs(rates))

    assert analysis.status == TaskIntegrityStatus.SUSPECT
    assert "agent_outlier" in analysis.flags
    assert analysis.z_scores["agent-09"] is not None
    assert analysis.z_scores["agent-09"] <= -auditor.z_score_threshold
    assert analysis.pass_rate_stddev > 0.0


def test_cohort_matrix_detects_polarized_cohort_and_exports_issue() -> None:
    auditor = CohortMatrixAuditor()
    analysis = auditor.analyze_task(
        "model-split",
        _agent_runs([0.0] * 5 + [1.0] * 5),
    )

    assert analysis.status == TaskIntegrityStatus.SUSPECT
    assert "high_pass_rate_dispersion" in analysis.flags
    assert "polarized_cohort" in analysis.flags
    assert analysis.bimodality_coefficient is not None

    markdown = auditor.export_flawed_test_issue("ExampleBench", analysis)
    assert "EvalGuard Cohort Integrity Report" in markdown
    assert "polarized_cohort" in markdown
    assert "agent-00" in markdown
    assert "**Mean per-agent pass rate:** 50.0%" in markdown
    assert "| 0.0% |" in markdown
    assert "| 100.0% |" in markdown


def test_cohort_matrix_does_not_flag_uniform_intermediate_performance() -> None:
    auditor = CohortMatrixAuditor()
    analysis = auditor.analyze_task(
        "middle",
        _agent_runs([0.5] * 10),
    )

    assert analysis.status == TaskIntegrityStatus.PASS
    assert analysis.flags == ()
    assert analysis.mean_pass_rate == 0.5
    assert analysis.pass_rate_stddev == 0.0
    assert analysis.bimodality_coefficient is None


def test_cohort_matrix_marks_small_cohort_as_insufficient() -> None:
    auditor = CohortMatrixAuditor(min_agent_count=10)
    analysis = auditor.analyze_task("small", _agent_runs([1.0] * 4))

    assert analysis.insufficient_data is True
    assert analysis.status == TaskIntegrityStatus.PASS
    assert analysis.flags == ()
    assert analysis.mean_pass_rate == 1.0


def test_cohort_matrix_analyzes_multiple_tasks() -> None:
    auditor = CohortMatrixAuditor()
    result = auditor.analyze_matrix(
        {
            "easy": _agent_runs([1.0] * 10),
            "hard": _agent_runs([0.0] * 10),
        }
    )

    assert result["easy"].flags == ("universal_pass",)
    assert result["hard"].flags == ("universal_fail",)


@pytest.mark.parametrize(
    "agent_runs",
    [
        {},
        {"agent": []},
        {"": [True]},
        {"agent": ["yes"]},
        {"agent": [1, 0]},
        {"agent": "true"},
    ],
)
def test_cohort_matrix_rejects_invalid_outcomes(agent_runs: dict) -> None:
    auditor = CohortMatrixAuditor()
    with pytest.raises(ValueError):
        auditor.analyze_task("task", agent_runs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"universal_pass_threshold": float("nan")},
        {"universal_fail_threshold": 0.99},
        {"min_agent_count": True},
        {"min_agent_count": 1},
        {"z_score_threshold": 0.0},
        {"pass_rate_stddev_threshold": 1.1},
        {"bimodality_threshold": -0.1},
    ],
)
def test_cohort_matrix_rejects_invalid_configuration(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        CohortMatrixAuditor(**kwargs)


def test_cohort_matrix_issue_export_requires_an_anomaly() -> None:
    auditor = CohortMatrixAuditor()
    analysis = auditor.analyze_task("normal", _agent_runs([0.5] * 10))

    with pytest.raises(ValueError, match="Only flagged"):
        auditor.export_flawed_test_issue("ExampleBench", analysis)
