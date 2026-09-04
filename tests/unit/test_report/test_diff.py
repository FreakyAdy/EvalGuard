"""Unit tests for ReportDiffer and report exporters (Markdown, HTML, CSV, SARIF)."""

from __future__ import annotations

import json

from evalguard.report.builder import ReportBuilder
from evalguard.report.diff import ReportDiffer
from evalguard.report.exporters import (
    CsvExporter,
    HtmlExporter,
    MarkdownExporter,
    SarifExporter,
)
from evalguard.report.schema import TaskAuditRecord


def test_report_diff_computation() -> None:
    b1 = ReportBuilder(benchmark_id="B", agent_id="A1")
    b1.add_task_result(TaskAuditRecord(task_id="t1", agent_passed=True))
    b1.add_task_result(TaskAuditRecord(task_id="t2", agent_passed=False))
    r1 = b1.build()

    b2 = ReportBuilder(benchmark_id="B", agent_id="A2")
    b2.add_task_result(TaskAuditRecord(task_id="t1", agent_passed=False))  # flipped
    b2.add_task_result(TaskAuditRecord(task_id="t2", agent_passed=True))  # improved
    r2 = b2.build()

    diff = ReportDiffer.diff_reports(r1, r2)
    assert diff.total_tasks_compared == 2
    assert "t1" in diff.flip_pass_to_fail
    assert "t2" in diff.flip_fail_to_pass


def test_report_exporters_valid_output() -> None:
    builder = ReportBuilder(benchmark_id="TestBench", agent_id="AgentZero")
    builder.add_task_result(TaskAuditRecord(task_id="t1", agent_passed=True))
    report = builder.build()

    # Markdown
    md = MarkdownExporter.export(report)
    assert "# EvalGuard Audit Report" in md
    assert "t1" in md

    # HTML
    html_out = HtmlExporter.export(report)
    assert "<!DOCTYPE html>" in html_out
    assert "TestBench" in html_out

    # CSV
    csv_out = CsvExporter.export(report)
    assert "benchmark_id,agent_id" in csv_out
    assert "AgentZero" in csv_out

    # SARIF
    sarif_str = SarifExporter.export(report)
    sarif_json = json.loads(sarif_str)
    assert sarif_json["version"] == "2.1.0"
    assert sarif_json["runs"][0]["tool"]["driver"]["name"] == "EvalGuard"
