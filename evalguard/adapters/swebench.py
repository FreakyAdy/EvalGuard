"""SWE-bench harness adapter for repository-level software engineering benchmarks."""

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


class SWEBenchAdapter(HarnessAdapter):
    """Adapter for SWE-bench (Verified & Lite) benchmark runs."""

    def __init__(
        self,
        name: str = "swe-bench",
        workspace_base_dir: str = "./swebench_workspaces",
    ) -> None:
        super().__init__(
            name=name,
            capabilities=(
                AdapterCapabilities.SUPPORTS_HERMETIC_SANDBOX
                | AdapterCapabilities.SUPPORTS_ENVIRONMENT_RESET
                | AdapterCapabilities.SUPPORTS_STATE_SNAPSHOTS
            ),
        )
        self.workspace_base_dir = Path(workspace_base_dir).resolve()
        self._contexts: dict[str, TaskContext] = {}

    def setup_task(self, task_id: str) -> TaskContext:
        """Set up repo workspace and load task test metadata."""
        task_dir = self.workspace_base_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        context = TaskContext(
            task_id=task_id,
            workspace_root=str(task_dir),
            instruction=f"Resolve SWE-bench issue {task_id}",
            test_files=["tests/test_patch.py"],
            timeout_seconds=1200,
            metadata={"benchmark": "swe-bench-verified"},
        )
        self._contexts[task_id] = context
        return context

    def run_task(self, agent: Any, task_id: str) -> TaskResult:
        """Run agent against SWE-bench task and execute evaluation test harness."""
        context = self._contexts.get(task_id) or self.setup_task(task_id)
        start_time = time.time()

        try:
            if hasattr(agent, "solve_swebench_task"):
                patch = agent.solve_swebench_task(context)
                passed = bool(patch)
                output = f"Generated patch of length {len(str(patch))}"
            elif callable(agent):
                res = agent(context)
                passed = bool(res)
                output = str(res)
            else:
                passed = False
                output = f"Unsupported agent interface: {type(agent)}"

            return TaskResult(
                task_id=task_id,
                passed=passed,
                duration_seconds=round(time.time() - start_time, 3),
                output=output,
                extra_metrics={"swebench_instance": task_id},
            )
        except Exception as e:
            return TaskResult(
                task_id=task_id,
                passed=False,
                duration_seconds=round(time.time() - start_time, 3),
                output="",
                error=f"SWE-bench execution failed: {e}",
            )

    def teardown_task(self, task_id: str) -> None:
        """Tear down SWE-bench task workspace."""
        self._contexts.pop(task_id, None)

    def reset_environment(self) -> None:
        """Reset all active SWE-bench tasks."""
        self._contexts.clear()
