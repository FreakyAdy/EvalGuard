"""Validation suite for verifying external harness adapter implementations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from evalguard.adapters.base import HarnessAdapter, TaskContext, TaskResult

logger = logging.getLogger(__name__)


@dataclass
class AdapterCheckResult:
    """Result of an individual check in the adapter validation suite."""

    check_name: str
    passed: bool
    message: str
    details: str = ""


@dataclass
class AdapterValidationReport:
    """Consolidated report produced by validating an adapter."""

    adapter_name: str
    all_passed: bool
    checks: list[AdapterCheckResult] = field(default_factory=list)


class AdapterVerifier:
    """Test suite that external harness maintainers can execute against their adapter."""

    def __init__(self, adapter: HarnessAdapter) -> None:
        self.adapter = adapter
        self.results: list[AdapterCheckResult] = []

    def verify_all(self) -> AdapterValidationReport:
        """Run all verification tests against the adapter."""
        self.results.clear()

        self._test_setup_task()
        self._test_run_task_interface()
        self._test_teardown_task()
        self._test_reset_environment()
        self._test_audit_wrapping()

        all_ok = all(r.passed for r in self.results)
        return AdapterValidationReport(
            adapter_name=self.adapter.name,
            all_passed=all_ok,
            checks=list(self.results),
        )

    def _test_setup_task(self) -> None:
        try:
            ctx = self.adapter.setup_task("verify_task_001")
            if not isinstance(ctx, TaskContext):
                self.results.append(
                    AdapterCheckResult(
                        check_name="setup_task_type",
                        passed=False,
                        message=f"setup_task must return a TaskContext, got {type(ctx)}",
                    )
                )
                return

            if not ctx.workspace_root or not Path(ctx.workspace_root).exists():
                self.results.append(
                    AdapterCheckResult(
                        check_name="workspace_root_exists",
                        passed=False,
                        message=f"TaskContext.workspace_root must point to an existing directory: {ctx.workspace_root}",
                    )
                )
                return

            self.results.append(
                AdapterCheckResult(
                    check_name="setup_task",
                    passed=True,
                    message="setup_task successfully initialized valid TaskContext",
                )
            )
        except Exception as e:
            self.results.append(
                AdapterCheckResult(
                    check_name="setup_task",
                    passed=False,
                    message=f"setup_task raised unhandled exception: {e}",
                )
            )

    def _test_run_task_interface(self) -> None:
        try:
            # Pass a simple no-op agent callable
            def dummy_agent(ctx: TaskContext) -> bool:
                return True

            res = self.adapter.run_task(dummy_agent, "verify_task_001")
            if not isinstance(res, TaskResult):
                self.results.append(
                    AdapterCheckResult(
                        check_name="run_task_type",
                        passed=False,
                        message=f"run_task must return TaskResult, got {type(res)}",
                    )
                )
                return

            if not isinstance(res.passed, bool):
                self.results.append(
                    AdapterCheckResult(
                        check_name="run_task_passed_bool",
                        passed=False,
                        message=f"TaskResult.passed must be a bool, got {type(res.passed)}",
                    )
                )
                return

            self.results.append(
                AdapterCheckResult(
                    check_name="run_task",
                    passed=True,
                    message="run_task successfully returned valid TaskResult",
                )
            )
        except Exception as e:
            self.results.append(
                AdapterCheckResult(
                    check_name="run_task",
                    passed=False,
                    message=f"run_task raised unhandled exception: {e}",
                )
            )

    def _test_teardown_task(self) -> None:
        try:
            self.adapter.teardown_task("verify_task_001")
            self.results.append(
                AdapterCheckResult(
                    check_name="teardown_task",
                    passed=True,
                    message="teardown_task completed without exception",
                )
            )
        except Exception as e:
            self.results.append(
                AdapterCheckResult(
                    check_name="teardown_task",
                    passed=False,
                    message=f"teardown_task raised unhandled exception: {e}",
                )
            )

    def _test_reset_environment(self) -> None:
        try:
            self.adapter.reset_environment()
            self.results.append(
                AdapterCheckResult(
                    check_name="reset_environment",
                    passed=True,
                    message="reset_environment completed cleanly",
                )
            )
        except Exception as e:
            self.results.append(
                AdapterCheckResult(
                    check_name="reset_environment",
                    passed=False,
                    message=f"reset_environment raised exception: {e}",
                )
            )

    def _test_audit_wrapping(self) -> None:
        try:

            def dummy_agent(ctx: TaskContext) -> bool:
                return True

            audit_rec = self.adapter.run_task_with_audit(
                dummy_agent, "verify_audit_002", sandbox_backend="host"
            )
            if audit_rec.task_id != "verify_audit_002":
                self.results.append(
                    AdapterCheckResult(
                        check_name="audit_wrapping",
                        passed=False,
                        message=f"Audit task_id mismatch: expected verify_audit_002, got {audit_rec.task_id}",
                    )
                )
                return

            self.results.append(
                AdapterCheckResult(
                    check_name="audit_wrapping",
                    passed=True,
                    message="run_task_with_audit correctly wraps execution inside sandbox and logs snapshot",
                )
            )
        except Exception as e:
            self.results.append(
                AdapterCheckResult(
                    check_name="audit_wrapping",
                    passed=False,
                    message=f"run_task_with_audit failed: {e}",
                )
            )
