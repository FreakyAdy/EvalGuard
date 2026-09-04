"""Unit tests for GenericSubprocessAdapter and AdapterVerifier."""

from __future__ import annotations

import tempfile
from pathlib import Path

from evalguard.adapters.subprocess_adapter import GenericSubprocessAdapter
from evalguard.adapters.verifier import AdapterVerifier


def test_subprocess_adapter_lifecycle() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = GenericSubprocessAdapter(
            name="unit-subprocess",
            workspace_base_dir=td,
        )

        ctx = adapter.setup_task("task_01")
        assert Path(ctx.workspace_root).exists()

        # Run with callable agent
        res = adapter.run_task(lambda c: True, "task_01")
        assert res.passed is True
        assert res.duration_seconds >= 0.0

        adapter.teardown_task("task_01")
        adapter.reset_environment()


def test_adapter_verifier_suite() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = GenericSubprocessAdapter(workspace_base_dir=td)
        verifier = AdapterVerifier(adapter)
        report = verifier.verify_all()
        assert report.all_passed is True
        assert len(report.checks) == 5
