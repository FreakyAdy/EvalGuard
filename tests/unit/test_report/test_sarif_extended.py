"""Unit tests for SARIF export format and rule mapping."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from evalguard.report.builder import ReportBuilder
from evalguard.report.exporters.sarif import SarifExporter
from evalguard.report.schema import (
    BoundaryViolationRecord,
    BoundaryViolationType,
    RewardHackRecord,
    TamperEventRecord,
    TamperType,
    TaskAuditRecord,
)


def test_sarif_exporter_full_rules() -> None:
    now = datetime.now(timezone.utc)
    v1 = BoundaryViolationRecord(
        violation_type=BoundaryViolationType.FILESYSTEM,
        severity="high",
        target="/outside/boundary.txt",
        detail="Wrote outside boundary",
        timestamp=now,
    )
    v2 = BoundaryViolationRecord(
        violation_type=BoundaryViolationType.GHOST_PROCESS,
        severity="medium",
        target="pid:9999",
        detail="Ghost process remaining",
        timestamp=now,
    )
    rh = RewardHackRecord(
        tamper_events=[
            TamperEventRecord(
                tamper_type=TamperType.DIRECT_TEST_MODIFICATION,
                file_path="tests/test_foo.py",
                description="Deleted assertion",
                line_number=42,
            ),
            TamperEventRecord(
                tamper_type=TamperType.SYS_PATH_MANIPULATION,
                file_path="src/agent.py",
                description="Injected sys.path manipulation",
                line_number=None,
            ),
        ]
    )

    task1 = TaskAuditRecord(
        task_id="task_sarif_001",
        agent_passed=True,
        duration_seconds=5.0,
        violations=[v1, v2],
        reward_hack=rh,
    )

    builder = ReportBuilder(benchmark_id="swebench", agent_id="agent_1")
    builder.add_task_result(task1)
    report = builder.build()

    sarif_str = SarifExporter.export(report)
    assert sarif_str
    parsed = json.loads(sarif_str)

    assert parsed["version"] == "2.1.0"
    assert len(parsed["runs"]) == 1
    run = parsed["runs"][0]
    results = run["results"]
    assert len(results) == 4

    rule_ids = {r["ruleId"] for r in results}
    assert "EG001" in rule_ids
    assert "EG002" in rule_ids
    assert "EG003" in rule_ids
    assert "EG004" in rule_ids

    # Check that EG003 has region startLine
    eg003 = next(r for r in results if r["ruleId"] == "EG003")
    assert eg003["locations"][0]["physicalLocation"]["region"]["startLine"] == 42
