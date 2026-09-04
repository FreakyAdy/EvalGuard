"""Unit tests for CrossHarnessAuditor divergence detection."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from evalguard.adapters.subprocess_adapter import GenericSubprocessAdapter
from evalguard.report.schema import TaskIntegrityStatus
from evalguard.testaudit.cross_harness import CrossHarnessAuditor


def test_cross_harness_auditor_divergence() -> None:
    with tempfile.TemporaryDirectory() as td:
        ws1 = Path(td) / "harness_1"
        ws2 = Path(td) / "harness_2"
        h1 = GenericSubprocessAdapter(name="harness-1", workspace_base_dir=str(ws1))
        h2 = GenericSubprocessAdapter(name="harness-2", workspace_base_dir=str(ws2))

        # Agent behaves differently on harness 1 vs 2
        def agent(ctx: Any) -> bool:
            return "harness_1" in ctx.workspace_root

        checker = CrossHarnessAuditor(h1, h2)
        rec = checker.audit_task("task_diverge_01", agent)
        assert rec.status == TaskIntegrityStatus.INVALID
        assert rec.cross_harness_divergence is True
        assert len(rec.evidence) >= 1
