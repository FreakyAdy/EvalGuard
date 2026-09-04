"""Terminal-Bench harness adapter for shell and CLI evaluation benchmarks."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from evalguard.adapters.base import (
    AdapterCapabilities,
    HarnessAdapter,
    TaskContext,
    TaskResult,
)

logger = logging.getLogger(__name__)


class TerminalBenchAdapter(HarnessAdapter):
    """Adapter for Terminal-Bench benchmark tasks enforcing terminal session boundaries."""

    def __init__(
        self,
        name: str = "terminal-bench",
        workspace_base_dir: str = "./tb_workspaces",
    ) -> None:
        super().__init__(
            name=name,
            capabilities=(
                AdapterCapabilities.SUPPORTS_HERMETIC_SANDBOX
                | AdapterCapabilities.SUPPORTS_SUBPROCESS_AGENT
                | AdapterCapabilities.SUPPORTS_ENVIRONMENT_RESET
                | AdapterCapabilities.SUPPORTS_STATE_SNAPSHOTS
            ),
        )
        self.workspace_base_dir = Path(workspace_base_dir).resolve()
        self._contexts: dict[str, TaskContext] = {}

    def setup_task(self, task_id: str) -> TaskContext:
        """Create terminal workspace directory and prepare bash context."""
        task_dir = self.workspace_base_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        context = TaskContext(
            task_id=task_id,
            workspace_root=str(task_dir),
            instruction=f"Terminal-Bench task: {task_id}",
            timeout_seconds=450,
            metadata={"shell": "bash"},
        )
        self._contexts[task_id] = context
        return context

    def run_task(self, agent: Any, task_id: str) -> TaskResult:
        """Execute Terminal-Bench agent and evaluate terminal exit state."""
        context = self._contexts.get(task_id) or self.setup_task(task_id)
        start_time = time.time()

        if hasattr(agent, "execute_terminal_task"):
            try:
                res = agent.execute_terminal_task(context)
                return TaskResult(
                    task_id=task_id,
                    passed=bool(res.get("passed", True)),
                    duration_seconds=round(time.time() - start_time, 3),
                    output=str(res.get("output", "")),
                )
            except Exception as e:
                return TaskResult(
                    task_id=task_id,
                    passed=False,
                    duration_seconds=round(time.time() - start_time, 3),
                    output="",
                    error=str(e),
                )
        elif callable(agent):
            try:
                res = agent(context)
                return TaskResult(
                    task_id=task_id,
                    passed=bool(res),
                    duration_seconds=round(time.time() - start_time, 3),
                    output=str(res),
                )
            except Exception as e:
                return TaskResult(
                    task_id=task_id,
                    passed=False,
                    duration_seconds=round(time.time() - start_time, 3),
                    output="",
                    error=str(e),
                )
        else:
            return TaskResult(
                task_id=task_id,
                passed=False,
                duration_seconds=round(time.time() - start_time, 3),
                output="",
                error="Invalid agent passed to TerminalBenchAdapter",
            )

    def teardown_task(self, task_id: str) -> None:
        """Remove task context."""
        self._contexts.pop(task_id, None)

    def reset_environment(self) -> None:
        """Reset all active contexts."""
        self._contexts.clear()
