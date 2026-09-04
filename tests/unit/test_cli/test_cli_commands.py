"""Unit tests for EvalGuard Click CLI commands."""

from __future__ import annotations

import tempfile
from pathlib import Path

from click.testing import CliRunner

from evalguard.cli.main import cli
from evalguard.report.builder import ReportBuilder
from evalguard.report.schema import TaskAuditRecord


def test_cli_version_and_help() -> None:
    runner = CliRunner()
    res_help = runner.invoke(cli, ["--help"])
    assert res_help.exit_code == 0
    assert "EvalGuard" in res_help.output

    res_ver = runner.invoke(cli, ["--version"])
    assert res_ver.exit_code == 0
    assert "0.1.0" in res_ver.output


def test_cli_report_view_diff_export() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        r1_path = root / "report1.json"
        r2_path = root / "report2.json"

        b1 = ReportBuilder("bench1", "agent1")
        b1.add_task_result(TaskAuditRecord(task_id="t1", agent_passed=True))
        r1 = b1.build()
        r1_path.write_text(r1.model_dump_json(), encoding="utf-8")

        b2 = ReportBuilder("bench1", "agent2")
        b2.add_task_result(TaskAuditRecord(task_id="t1", agent_passed=False))
        r2 = b2.build()
        r2_path.write_text(r2.model_dump_json(), encoding="utf-8")

        # 1. view command
        res_view = runner.invoke(cli, ["report", "view", str(r1_path)])
        assert res_view.exit_code == 0
        assert "t1" in res_view.output

        # 2. diff command
        res_diff = runner.invoke(cli, ["report", "diff", str(r1_path), str(r2_path)])
        assert res_diff.exit_code == 0
        assert "Divergent Tasks" in res_diff.output

        # 3. export commands
        for fmt in ["markdown", "html", "csv", "sarif"]:
            out_file = root / f"out.{fmt}"
            res_exp = runner.invoke(cli, ["report", "export", str(r1_path), "--format", fmt, "--output", str(out_file)])
            assert res_exp.exit_code == 0
            assert out_file.exists()


def test_cli_contamination_audit() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        corpus = Path(td) / "corpus.txt"
        corpus.write_text("def has_close_elements(numbers, threshold):\n    for idx, elem in enumerate(numbers):\n        pass\n")
        out_json = Path(td) / "contam_out.json"

        res = runner.invoke(cli, [
            "contamination", "audit",
            "--benchmark", "humaneval",
            "--agent-corpus", str(corpus),
            "--disclosure-date", "2021-07-07",
            "--cutoff-date", "2024-01-01",
            "--output", str(out_json),
        ])
        assert res.exit_code == 0
        assert out_json.exists()


def test_cli_adapter_validate() -> None:
    runner = CliRunner()
    res = runner.invoke(cli, ["adapter", "validate", "evalguard.adapters:GenericSubprocessAdapter"])
    assert res.exit_code == 0
    assert "SUCCESS" in res.output


def test_cli_audit_run() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        out_json = Path(td) / "audit_record.json"
        res = runner.invoke(cli, [
            "audit", "run",
            "--task-id", "cli_test_task",
            "--command", "python -c \"print('ok')\"",
            "--backend", "host",
            "--output", str(out_json),
        ])
        assert res.exit_code == 0
        assert out_json.exists()
