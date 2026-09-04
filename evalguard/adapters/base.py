"""Abstract Base Class and data models for benchmark harness adapters."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Flag, auto
from typing import Any, Protocol, runtime_checkable

from evalguard.report.schema import (
    BoundaryViolationRecord,
    SnapshotDiffRecord,
    TaskAuditRecord,
)
from evalguard.sandbox.harness_sandbox import HarnessSandbox
from evalguard.sandbox.profiles import SandboxProfile


class AdapterCapabilities(Flag):
    """Capabilities supported by a benchmark harness adapter."""

    NONE = 0
    SUPPORTS_HERMETIC_SANDBOX = auto()
    SUPPORTS_STEPWISE_EXECUTION = auto()
    SUPPORTS_ENVIRONMENT_RESET = auto()
    SUPPORTS_STATE_SNAPSHOTS = auto()
    SUPPORTS_SUBPROCESS_AGENT = auto()


@dataclass
class TaskContext:
    """Context and metadata initialized for a specific benchmark task."""

    task_id: str
    workspace_root: str
    instruction: str = ""
    test_files: list[str] = field(default_factory=list)
    timeout_seconds: int = 600
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Execution outcome produced by the harness."""

    task_id: str
    passed: bool
    duration_seconds: float
    output: str = ""
    error: str | None = None
    extra_metrics: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class AgentProtocol(Protocol):
    """Minimal protocol that benchmark agents are expected to fulfill."""

    def act(self, task_context: TaskContext) -> Any:
        """Perform agent action(s) for the assigned task."""
        ...


class HarnessAdapter(ABC):
    """Abstract interface that connects EvalGuard to external benchmark harnesses.

    Design philosophy: Wrap, not patch.
    Existing harnesses integrate with EvalGuard in under a day by subclassing
    this interface without needing to alter their internal codebases.
    """

    def __init__(self, name: str, capabilities: AdapterCapabilities = AdapterCapabilities.NONE) -> None:
        self.name = name
        self.capabilities = capabilities

    @abstractmethod
    def setup_task(self, task_id: str) -> TaskContext:
        """Prepare the environment, fixtures, and context for the given task."""
        ...

    @abstractmethod
    def run_task(self, agent: Any, task_id: str) -> TaskResult:
        """Run the agent on the task using the native harness."""
        ...

    @abstractmethod
    def teardown_task(self, task_id: str) -> None:
        """Clean up task-specific resources."""
        ...

    @abstractmethod
    def reset_environment(self) -> None:
        """Perform full harness reset between benchmark runs."""
        ...

    def run_task_with_audit(
        self,
        agent: Any,
        task_id: str,
        profile: SandboxProfile | None = None,
        sandbox_backend: str = "auto",
    ) -> TaskAuditRecord:
        """Execute task inside HarnessSandbox, capturing violations, snapshots, and metrics."""
        task_context = self.setup_task(task_id)

        # Merge or default the sandbox profile
        sb_profile = profile or SandboxProfile(
            name=f"{self.name}-{task_id}",
            task_workspace_root=task_context.workspace_root,
            timeout_seconds=task_context.timeout_seconds,
        )

        start_time = time.time()
        violations: list[BoundaryViolationRecord] = []
        snapshot_diff: SnapshotDiffRecord | None = None
        task_result: TaskResult

        try:
            with HarnessSandbox(task_id=task_id, profile=sb_profile, backend=sandbox_backend) as sb:
                task_result = self.run_task(agent, task_id)
            violations = sb.get_violations()
            snapshot_diff = sb.get_snapshot_diff()
        finally:
            self.teardown_task(task_id)

        duration = time.time() - start_time

        return TaskAuditRecord(
            task_id=task_id,
            agent_passed=task_result.passed,
            duration_seconds=round(duration, 3),
            violations=violations,
            snapshot_diff=snapshot_diff,
            metadata={
                "harness": self.name,
                "output_snippet": task_result.output[:300] if task_result.output else "",
                "extra_metrics": task_result.extra_metrics,
            },
        )
