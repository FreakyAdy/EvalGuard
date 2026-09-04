"""Unit tests for RewardHackAuditor composite orchestration."""

from __future__ import annotations

import tempfile
from typing import Any

from evalguard.report.schema import TaskAuditRecord
from evalguard.rewardhack.auditor import RewardHackAuditor


def test_reward_hack_auditor_detects_probe_divergence() -> None:
    test_src = "def test_answer():\n    assert answer == 42\n"

    # Evaluator simulates an agent that hardcoded output to pass original syntax
    # but fails when assertion is flipped (42 == answer)
    def hardcoded_evaluator(ws_root: str, mutation: Any) -> bool:
        return False  # fails mutated test

    with tempfile.TemporaryDirectory() as td:
        task = type("Task", (), {"workspace_root": td})()
        agent_res = TaskAuditRecord(task_id="t1", agent_passed=True)

        auditor = RewardHackAuditor(
            task=task,
            agent_result=agent_res,
            test_sources={"test_main.py": test_src},
            workspace_root=td,
        )

        report = auditor.run(mutation_rounds=2, test_evaluator=hardcoded_evaluator)
        assert report.mutation_pass_rate == 0.0
        assert report.confidence_score >= 0.7
