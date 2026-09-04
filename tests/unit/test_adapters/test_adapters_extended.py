"""Extended tests for OpenEnvAdapter, TerminalBenchAdapter, verifier, and pytest plugin."""

from __future__ import annotations

import tempfile
from typing import Any

import pytest

from evalguard.adapters.base import HarnessAdapter, TaskContext
from evalguard.adapters.openenv import OpenEnvAdapter
from evalguard.adapters.pytest_plugin import evalguard_verifier
from evalguard.adapters.terminal_bench import TerminalBenchAdapter
from evalguard.adapters.verifier import AdapterVerifier


class MockEvalAgent:
    def evaluate_task(self, ctx: TaskContext) -> Any:
        class Res:
            passed = True
            output = "evaluated successfully"

        return Res()


class MockActAgent:
    def act(self, ctx: TaskContext) -> None:
        pass


class MockFailingAgent:
    def __call__(self, ctx: TaskContext) -> Any:
        raise RuntimeError("Agent crashed during task")


class MockTerminalAgent:
    def execute_terminal_task(self, ctx: TaskContext) -> dict[str, Any]:
        return {"passed": True, "output": "command ran"}


class BrokenAdapter(HarnessAdapter):
    """Adapter that intentionally violates the HarnessAdapter contract for verifier testing."""

    def __init__(self) -> None:
        super().__init__(name="broken-adapter")

    def setup_task(self, task_id: str) -> Any:
        return "not-a-task-context"

    def run_task(self, agent: Any, task_id: str) -> Any:
        return "not-a-task-result"

    def teardown_task(self, task_id: str) -> None:
        raise RuntimeError("Teardown error")

    def reset_environment(self) -> None:
        raise RuntimeError("Reset error")


def test_openenv_adapter_agent_variants() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = OpenEnvAdapter(workspace_base_dir=td)

        # 1. evaluate_task agent
        res1 = adapter.run_task(MockEvalAgent(), "task_openenv_1")
        assert res1.passed is True
        assert "evaluated successfully" in res1.output

        # 2. act agent
        res2 = adapter.run_task(MockActAgent(), "task_openenv_2")
        assert res2.passed is True

        # 3. dictionary-returning callable
        res3 = adapter.run_task(lambda ctx: {"passed": True}, "task_openenv_3")
        assert res3.passed is True

        # 4. unknown agent interface
        res4 = adapter.run_task(12345, "task_openenv_4")
        assert res4.passed is False
        assert "Unknown agent interface" in res4.output

        # 5. crashing agent
        res5 = adapter.run_task(MockFailingAgent(), "task_openenv_5")
        assert res5.passed is False
        assert "Agent crashed during task" in (res5.error or "")

        adapter.teardown_task("task_openenv_1")
        adapter.reset_environment()


def test_terminal_bench_adapter_variants() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = TerminalBenchAdapter(workspace_base_dir=td)

        # 1. execute_terminal_task agent
        res1 = adapter.run_task(MockTerminalAgent(), "tb_task_1")
        assert res1.passed is True

        # 2. boolean callable agent
        res2 = adapter.run_task(lambda ctx: True, "tb_task_2")
        assert res2.passed is True

        # 3. invalid agent interface
        res3 = adapter.run_task(None, "tb_task_3")
        assert res3.passed is False
        assert "Invalid agent" in (res3.error or "")

        # 4. crashing agent
        res4 = adapter.run_task(MockFailingAgent(), "tb_task_4")
        assert res4.passed is False
        assert "Agent crashed" in (res4.error or "")

        adapter.teardown_task("tb_task_1")
        adapter.reset_environment()


def test_adapter_verifier_broken_adapter() -> None:
    broken = BrokenAdapter()
    verifier = AdapterVerifier(broken)
    report = verifier.verify_all()
    assert report.all_passed is False
    assert len(report.checks) >= 4
    failures = [c for c in report.checks if not c.passed]
    assert len(failures) >= 3


def test_pytest_plugin_fixture() -> None:
    # Test fixture factory with valid adapter
    fixture_func = evalguard_verifier.__wrapped__()
    with tempfile.TemporaryDirectory() as td:
        adapter = OpenEnvAdapter(workspace_base_dir=td)
        report = fixture_func(adapter)
        assert report.all_passed is True

    # Test fixture factory fails on broken adapter
    broken = BrokenAdapter()
    with pytest.raises(pytest.fail.Exception):
        fixture_func(broken)
