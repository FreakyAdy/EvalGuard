"""Tests for the interactive, self-contained HTML report exporter."""

from __future__ import annotations

import re

from evalguard.report.exporters.html import HtmlExporter
from evalguard.report.schema import (
    BoundaryViolationRecord,
    BoundaryViolationType,
    ContaminationFlag,
    ContaminationType,
    EvalGuardReport,
    MutationProbeResult,
    ReportSummary,
    RewardHackRecord,
    SnapshotDiffRecord,
    TamperEventRecord,
    TamperType,
    TaskAuditRecord,
    TaskIntegrityStatus,
    TestIntegrityRecord,
)


def _sample_report() -> EvalGuardReport:
    violation = BoundaryViolationRecord(
        violation_type=BoundaryViolationType.FILESYSTEM,
        detail='Unexpected content: </script><script>alert("x")</script>',
        target="/tmp/<img src=x onerror=alert(1)>",
        severity="critical",
    )
    tamper = TamperEventRecord(
        tamper_type=TamperType.DIRECT_TEST_MODIFICATION,
        file_path="tests/test_example.py",
        description="Removed a security assertion",
        line_number=42,
        code_snippet='assert "</script><script>alert(1)</script>" not in output',
    )
    reward_hack = RewardHackRecord(
        confidence_score=0.85,
        mutation_rounds_total=3,
        mutation_rounds_passed=1,
        tamper_events=[tamper],
        mutation_probes=[
            MutationProbeResult(
                mutation_id="probe-1",
                strategy="assertion_inversion",
                original_passed=True,
                mutated_passed=False,
                diff_summary="The assertion no longer accepts the mutated result.",
            )
        ],
    )
    integrity = TestIntegrityRecord(
        status=TaskIntegrityStatus.SUSPECT,
        reference_solver_passed=True,
        universal_pass_rate=0.99,
        evidence=["Universal pass anomaly was detected."],
    )
    flagged_task = TaskAuditRecord(
        task_id='task<&"unsafe',
        agent_passed=False,
        duration_seconds=1.25,
        violations=[violation],
        snapshot_diff=SnapshotDiffRecord(
            added_files=["src/new.py"],
            removed_files=["tests/old_test.py"],
            modified_files=["tests/test_example.py"],
            total_files_before=3,
            total_files_after=3,
        ),
        reward_hack=reward_hack,
        contamination_flags=[
            ContaminationFlag(
                method=ContaminationType.LEXICAL,
                score=0.91,
                threshold=0.85,
                is_contaminated=True,
                details="High lexical overlap with a public benchmark.",
                matched_reference="benchmark/reference.py",
            )
        ],
        test_integrity=integrity,
    )
    clean_task = TaskAuditRecord(
        task_id="clean_task",
        agent_passed=True,
        duration_seconds=0.4,
    )
    return EvalGuardReport(
        benchmark_id='bench<&"unsafe',
        agent_id="agent/example",
        harness_name="local",
        summary=ReportSummary(
            total_tasks=2,
            agent_passed_tasks=1,
            clean_passed_tasks=1,
            boundary_violations_total=1,
            tasks_with_reward_hack=1,
            tasks_with_contamination=1,
            suspect_or_invalid_tests=1,
        ),
        tasks=[flagged_task, clean_task],
    )


def test_html_export_has_search_filters_details_and_download_controls() -> None:
    rendered = HtmlExporter.export(_sample_report())

    for control in (
        'id="task-search"',
        'id="severity-filter"',
        'id="theme-toggle"',
        'id="export-json"',
        'id="export-csv"',
        'id="result-count"',
        'id="no-results"',
    ):
        assert control in rendered

    for detail in (
        "Inspect task evidence",
        "Boundary violations",
        "Workspace snapshot",
        "Reward-hacking evidence",
        "Mutation probes",
        "Contamination",
        "Test integrity",
    ):
        assert detail in rendered

    assert "data-theme" in rendered
    assert "addEventListener" in rendered
    assert "createObjectURL" in rendered
    assert "https://" not in rendered


def test_html_export_escapes_untrusted_markup_and_json_script_content() -> None:
    rendered = HtmlExporter.export(_sample_report())

    assert "&lt;img src=x onerror=alert(1)&gt;" in rendered
    assert "&lt;script&gt;" in rendered
    assert "<img src=x onerror=alert(1)>" not in rendered
    assert '</script><script>alert("x")</script>' not in rendered
    assert "\\u003c/script\\u003e\\u003cscript\\u003e" in rendered


def test_html_export_supports_severity_and_evidence_search() -> None:
    rendered = HtmlExporter.export(_sample_report())

    assert 'data-severity="critical"' in rendered
    assert 'data-severity="none"' in rendered
    assert "security assertion" in rendered.casefold()
    assert "benchmark/reference.py" in rendered
    assert 'option value="critical"' in rendered
    assert 'option value="none"' in rendered
    assert re.search(r"function applyFilters\(\)", rendered)


def test_html_export_embeds_the_complete_report_for_json_and_csv() -> None:
    rendered = HtmlExporter.export(_sample_report())
    payload_match = re.search(
        r'<script type="application/json" id="report-data">(.*?)</script>',
        rendered,
        flags=re.DOTALL,
    )
    assert payload_match is not None
    payload = payload_match.group(1)
    assert "\\u003c/script\\u003e" in payload
    assert "evalguard-report.json" in rendered
    assert "evalguard-report.csv" in rendered
    assert "boundary_violation_severities" in rendered
    assert "boundary_violation_types" in rendered
    assert "function csvCell(value)" in rendered
    assert "downloadFile(filename, content, mimeType)" in rendered


def test_html_export_handles_empty_reports_without_division_errors() -> None:
    report = EvalGuardReport(
        benchmark_id="empty",
        agent_id="none",
        summary=ReportSummary(),
        tasks=[],
    )

    rendered = HtmlExporter.export(report)

    assert "Raw pass rate" in rendered
    assert "0%" in rendered
    assert 'id="no-results"' in rendered
    assert "Showing " in rendered
