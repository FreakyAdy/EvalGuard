"""Unit tests for GenericSubprocessAdapter and AdapterVerifier."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

from evalguard.adapters.subprocess_adapter import GenericSubprocessAdapter
from evalguard.adapters.verifier import AdapterVerifier


def python_cmd(code: str) -> list[str]:
    """Build a cross-platform command that runs the given snippets with the current interpreter."""
    return [sys.executable, "-c", code]


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


def test_agent_timeout_returns_failed_result_with_timeout_error() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = GenericSubprocessAdapter(workspace_base_dir=td)
        ctx = adapter.setup_task("task_timeout")
        ctx.timeout_seconds = 1
        res = adapter.run_task(python_cmd("import time; time.sleep(30)"), "task_timeout")
        assert res.passed is False
        assert res.error == "TimeoutExpired"
        assert "timed out" in res.output
        assert res.duration_seconds < 10
        adapter.teardown_task("task_timeout")


def test_nonzero_agent_exit_fails_with_exit_code_in_error() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = GenericSubprocessAdapter(workspace_base_dir=td)
        res = adapter.run_task(python_cmd("raise SystemExit(3)"), "task_exit3")
        assert res.passed is False
        assert res.error == "Non-zero exit code: 3"
        assert "[AGENT STDOUT]" in res.output


def test_zero_agent_exit_passes_with_no_error() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = GenericSubprocessAdapter(workspace_base_dir=td)
        res = adapter.run_task(python_cmd("raise SystemExit(0)"), "task_exit0")
        assert res.passed is True
        assert res.error is None


def test_large_agent_output_is_fully_captured_with_streams() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = GenericSubprocessAdapter(workspace_base_dir=td)
        res = adapter.run_task(
            python_cmd(
                "import sys; sys.stdout.write('x' * (2 * 1024 * 1024)); "
                "sys.stderr.write('y' * (256 * 1024))"
            ),
            "task_large",
        )
        assert res.passed is True
        assert "[AGENT STDOUT]" in res.output
        assert "[AGENT STDERR]" in res.output
        assert res.output.count("x") == 2 * 1024 * 1024
        assert res.output.count("y") == 256 * 1024


def test_test_command_determines_pass_independently_of_agent_exit() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = GenericSubprocessAdapter(
            workspace_base_dir=td,
            test_command_builder=lambda ctx: python_cmd("raise SystemExit(0)"),
        )
        res = adapter.run_task(python_cmd("raise SystemExit(3)"), "task_v_pass")
        assert res.passed is True
        assert res.error is None
        assert "[TEST STDOUT]" in res.output
        adapter.teardown_task("task_v_pass")


def test_failing_test_command_fails_task_and_reports_test_exit() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = GenericSubprocessAdapter(
            workspace_base_dir=td,
            test_command_builder=lambda ctx: python_cmd("raise SystemExit(2)"),
        )
        res = adapter.run_task(python_cmd("raise SystemExit(0)"), "task_v_fail")
        assert res.passed is False
        assert res.error == "Test command failed with exit code: 2"
        adapter.teardown_task("task_v_fail")


def test_test_command_start_failure_marks_failed_with_test_error() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = GenericSubprocessAdapter(
            workspace_base_dir=td,
            test_command_builder=lambda ctx: ["definitely-not-a-real-binary-xyz"],
        )
        res = adapter.run_task(python_cmd("raise SystemExit(0)"), "task_v_noexec")
        assert res.passed is False
        assert res.error == "Test command failed to execute"
        assert "[TEST ERROR]" in res.output
        adapter.teardown_task("task_v_noexec")


def test_missing_agent_executable_reports_failure() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = GenericSubprocessAdapter(workspace_base_dir=td)
        res = adapter.run_task(["definitely-not-a-real-binary-xyz"], "task_noexec")
        assert res.passed is False
        assert res.error


def test_invalid_agent_type_raises_type_error() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = GenericSubprocessAdapter(workspace_base_dir=td)
        with pytest.raises(TypeError, match="Agent must be command list"):
            adapter.run_task(12345, "task_badagent")


def test_run_task_creates_context_implicitly() -> None:
    with tempfile.TemporaryDirectory() as td:
        adapter = GenericSubprocessAdapter(workspace_base_dir=td)
        res = adapter.run_task(python_cmd("raise SystemExit(0)"), "task_implicit")
        assert res.passed is True
        assert "task_implicit" in adapter._active_contexts
        adapter.reset_environment()
        assert not adapter._active_contexts
