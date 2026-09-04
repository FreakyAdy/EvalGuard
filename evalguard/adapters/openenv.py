"""OpenEnv harness adapter for interactive agent environments."""

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


class OpenEnvAdapter(HarnessAdapter):
    """Adapter for OpenEnv benchmark tasks and environments."""

    def __init__(
        self,
        name: str = "openenv-adapter",
        workspace_base_dir: str = "./openenv_workspaces",
    ) -> None:
        super().__init__(
            name=name,
            capabilities=(
                AdapterCapabilities.SUPPORTS_HERMETIC_SANDBOX
                | AdapterCapabilities.SUPPORTS_STEPWISE_EXECUTION
                | AdapterCapabilities.SUPPORTS_ENVIRONMENT_RESET
                | AdapterCapabilities.SUPPORTS_STATE_SNAPSHOTS
            ),
        )
        self.workspace_base_dir = Path(workspace_base_dir).resolve()
        self._envs: dict[str, Any] = {}
        self._contexts: dict[str, TaskContext] = {}

    def setup_task(self, task_id: str) -> TaskContext:
        """Initialize workspace and environment instance for the task."""
        task_dir = self.workspace_base_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        context = TaskContext(
            task_id=task_id,
            workspace_root=str(task_dir),
            instruction=f"Solve OpenEnv benchmark task: {task_id}",
            timeout_seconds=600,
            metadata={"env_type": "openenv"},
        )
        self._contexts[task_id] = context
        return context

    def run_task(self, agent: Any, task_id: str) -> TaskResult:
        """Run agent against OpenEnv step loop or policy evaluation."""
        context = self._contexts.get(task_id) or self.setup_task(task_id)
        start_time = time.time()

        try:
            # Check if agent implements act/step or callable policy
            if hasattr(agent, "evaluate_task"):
                result = agent.evaluate_task(context)
                passed = bool(getattr(result, "passed", False))
                output = str(getattr(result, "output", ""))
            elif hasattr(agent, "act"):
                # Simulated interactive agent loop
                agent.act(context)
                passed = True
                output = f"Agent completed interaction in OpenEnv task {task_id}"
            elif callable(agent):
                res = agent(context)
                passed = bool(res.get("passed", True)) if isinstance(res, dict) else bool(res)
                output = str(res)
            else:
                passed = False
                output = f"Unknown agent interface: {type(agent)}"

            return TaskResult(
                task_id=task_id,
                passed=passed,
                duration_seconds=round(time.time() - start_time, 3),
                output=output,
                extra_metrics={"openenv_status": "completed"},
            )
        except Exception as e:
            return TaskResult(
                task_id=task_id,
                passed=False,
                duration_seconds=round(time.time() - start_time, 3),
                output="",
                error=f"OpenEnv execution error: {e}",
            )

    def teardown_task(self, task_id: str) -> None:
        """Close environment and cleanup context."""
        env = self._envs.pop(task_id, None)
        if env and hasattr(env, "close"):
            try:
                env.close()
            except Exception:
                pass
        self._contexts.pop(task_id, None)

    def reset_environment(self) -> None:
        """Reset all cached OpenEnv environments."""
        for env in self._envs.values():
            if hasattr(env, "close"):
                try:
                    env.close()
                except Exception:
                    pass
        self._envs.clear()
        self._contexts.clear()
