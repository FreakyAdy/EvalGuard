"""Unit tests for SWEBenchAdapter execution and context management."""

from __future__ import annotations

import tempfile
from pathlib import Path

from evalguard.adapters.swebench import SWEBenchAdapter


def test_swebench_adapter_lifecycle() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = SWEBenchAdapter(workspace_base_dir=td)
        ctx = adapter.setup_task("django__django-11099")
        assert Path(ctx.workspace_root).exists()

        # Run with mock callable agent
        res = adapter.run_task(lambda c: "diff --git a/file b/file", "django__django-11099")
        assert res.passed is True
        assert res.duration_seconds >= 0.0

        adapter.teardown_task("django__django-11099")
        adapter.reset_environment()
