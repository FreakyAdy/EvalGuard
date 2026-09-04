"""Integration tests for OpenEnvAdapter and TerminalBenchAdapter."""

from __future__ import annotations

import tempfile
from pathlib import Path

from evalguard.adapters.openenv import OpenEnvAdapter
from evalguard.adapters.terminal_bench import TerminalBenchAdapter


def test_openenv_adapter_integration() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = OpenEnvAdapter(workspace_base_dir=td)
        ctx = adapter.setup_task("openenv_task_01")
        assert Path(ctx.workspace_root).exists()

        # Run with mock policy
        res = adapter.run_task(lambda c: {"passed": True, "reward": 1.0}, "openenv_task_01")
        assert res.passed is True
        adapter.teardown_task("openenv_task_01")
        adapter.reset_environment()


def test_terminal_bench_adapter_integration() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = TerminalBenchAdapter(workspace_base_dir=td)
        ctx = adapter.setup_task("tb_task_01")
        assert Path(ctx.workspace_root).exists()

        # Run with mock agent
        res = adapter.run_task(lambda c: True, "tb_task_01")
        assert res.passed is True
        adapter.teardown_task("tb_task_01")
        adapter.reset_environment()
