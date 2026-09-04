"""End-to-end integration test exercising the complete EvalGuard audit pipeline."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from evalguard.adapters.subprocess_adapter import GenericSubprocessAdapter
from evalguard.contamination.auditor import ContaminationAuditor
from evalguard.report.builder import ReportBuilder
from evalguard.report.exporters import MarkdownExporter
from evalguard.rewardhack.auditor import RewardHackAuditor
from evalguard.sandbox.profiles import SandboxProfile
from evalguard.testaudit.auditor import TestAuditor


def test_full_evalguard_audit_pipeline() -> None:
    with tempfile.TemporaryDirectory() as td:
        base_dir = Path(td)
        task_ws = base_dir / "task_int_001"
        task_ws.mkdir()

        # 1. Setup profile
        profile = SandboxProfile(
            name="integration-pipeline",
            task_workspace_root=str(task_ws),
            timeout_seconds=30,
        )

        # 2. Setup adapter
        adapter = GenericSubprocessAdapter(
            name="integration-adapter",
            workspace_base_dir=str(base_dir),
        )

        # Agent writes a solution inside workspace
        def mock_agent(ctx: Any) -> bool:
            (Path(ctx.workspace_root) / "calc.py").write_text("def add(a, b): return a + b\n")
            return True

        # 3. Execute task under hermetic sandboxing
        task_record = adapter.run_task_with_audit(
            agent=mock_agent,
            task_id="task_int_001",
            profile=profile,
            sandbox_backend="host",
        )

        assert task_record.agent_passed is True
        assert task_record.snapshot_diff is not None
        assert "calc.py" in task_record.snapshot_diff.added_files

        # 4. Run Reward Hacking Auditor
        test_source = "def test_add():\n    assert add(2, 3) == 5\n"
        rh_auditor = RewardHackAuditor(
            task=type("Task", (), {"workspace_root": str(task_ws)})(),
            agent_result=task_record,
            test_sources={"test_calc.py": test_source},
            workspace_root=str(task_ws),
        )
        task_record.reward_hack = rh_auditor.run(mutation_rounds=2)
        assert task_record.reward_hack.confidence_score <= 0.3

        # 5. Run Contamination Auditor
        contam_auditor = ContaminationAuditor(benchmark_name="humaneval")
        task_record.contamination_flags = contam_auditor.audit_task(
            task_id="HumanEval/0",
            agent_solution_or_training_text="def add(a, b): return a + b\n",
            agent_cutoff_date="2024-01-01",
        )

        # 6. Run Test Case Integrity Auditor
        test_auditor = TestAuditor()
        task_record.test_integrity = test_auditor.audit_task(
            task_id="task_int_001",
            test_code=test_source,
            cohort_outcomes=[True] * 8 + [False] * 2,  # 80% pass rate
        )

        # 7. Assemble Complete Report
        builder = ReportBuilder(
            benchmark_id="IntegrationBenchmark",
            agent_id="BenchmarkAgent",
            harness_name=adapter.name,
        )
        builder.add_task_result(task_record)
        report = builder.build()

        assert report.summary.total_tasks == 1
        assert report.summary.agent_passed_tasks == 1

        # 8. Export Report
        md = MarkdownExporter.export(report)
        assert "IntegrationBenchmark" in md
        assert "task_int_001" in md
