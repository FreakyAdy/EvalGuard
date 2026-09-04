"""Generic subprocess adapter for harnesses running agents as CLI/script processes."""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from evalguard.adapters.base import (
    AdapterCapabilities,
    HarnessAdapter,
    TaskContext,
    TaskResult,
)

logger = logging.getLogger(__name__)


class GenericSubprocessAdapter(HarnessAdapter):
    """Universal adapter for harnesses that run agents as subprocess commands.

    Adapter authors provide a command-builder function or command list template.
    """

    def __init__(
        self,
        name: str = "generic-subprocess",
        workspace_base_dir: str = "./eval_workspaces",
        command_builder: Callable[[TaskContext], list[str]] | None = None,
        test_command_builder: Callable[[TaskContext], list[str]] | None = None,
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
        self.command_builder = command_builder
        self.test_command_builder = test_command_builder
        self._active_contexts: dict[str, TaskContext] = {}

    def setup_task(self, task_id: str) -> TaskContext:
        """Create task workspace directory and return TaskContext."""
        task_dir = self.workspace_base_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        context = TaskContext(
            task_id=task_id,
            workspace_root=str(task_dir),
            instruction=f"Execute task {task_id}",
            timeout_seconds=300,
        )
        self._active_contexts[task_id] = context
        return context

    def run_task(self, agent: Any, task_id: str) -> TaskResult:
        """Run the agent process in the task workspace and run test command if provided."""
        context = self._active_contexts.get(task_id)
        if not context:
            context = self.setup_task(task_id)

        start_time = time.time()
        output_chunks: list[str] = []

        # 1. Determine agent command
        if self.command_builder:
            cmd = self.command_builder(context)
        elif isinstance(agent, (list, tuple)):
            cmd = [str(arg) for arg in agent]
        elif isinstance(agent, str):
            cmd = agent.split()
        elif hasattr(agent, "get_command"):
            cmd = agent.get_command(context)
        elif callable(agent):
            # Callable Python agent running in-process or returning command
            res = agent(context)
            if isinstance(res, TaskResult):
                return res
            if isinstance(res, bool):
                return TaskResult(
                    task_id=task_id,
                    passed=res,
                    duration_seconds=round(time.time() - start_time, 3),
                    output=f"Callable agent returned boolean result: {res}",
                )
            if isinstance(res, str):
                cmd = res.split()
            elif isinstance(res, (list, tuple)):
                cmd = [str(x) for x in res]
            else:
                return TaskResult(
                    task_id=task_id,
                    passed=bool(res),
                    duration_seconds=round(time.time() - start_time, 3),
                    output=str(res),
                )
        else:
            raise TypeError(
                f"Agent must be command list, command string, or callable with command_builder. Got: {type(agent)}"
            )

        # 2. Execute agent subprocess
        try:
            agent_proc = subprocess.run(
                cmd,
                cwd=context.workspace_root,
                capture_output=True,
                text=True,
                timeout=context.timeout_seconds,
                check=False,
            )
            output_chunks.append(f"[AGENT STDOUT]\n{agent_proc.stdout}")
            if agent_proc.stderr:
                output_chunks.append(f"[AGENT STDERR]\n{agent_proc.stderr}")
            agent_exit = agent_proc.returncode
        except subprocess.TimeoutExpired:
            return TaskResult(
                task_id=task_id,
                passed=False,
                duration_seconds=time.time() - start_time,
                output="Agent execution timed out",
                error="TimeoutExpired",
            )
        except Exception as e:
            return TaskResult(
                task_id=task_id,
                passed=False,
                duration_seconds=time.time() - start_time,
                output="",
                error=str(e),
            )

        # 3. If a verification test command is provided, run it to determine pass/fail
        passed = (agent_exit == 0)
        if self.test_command_builder:
            test_cmd = self.test_command_builder(context)
            try:
                test_proc = subprocess.run(
                    test_cmd,
                    cwd=context.workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=context.timeout_seconds,
                    check=False,
                )
                output_chunks.append(f"[TEST STDOUT]\n{test_proc.stdout}")
                if test_proc.stderr:
                    output_chunks.append(f"[TEST STDERR]\n{test_proc.stderr}")
                passed = (test_proc.returncode == 0)
            except Exception as test_err:
                passed = False
                output_chunks.append(f"[TEST ERROR] {test_err}")

        return TaskResult(
            task_id=task_id,
            passed=passed,
            duration_seconds=round(time.time() - start_time, 3),
            output="\n".join(output_chunks),
            error=None if passed else f"Non-zero exit code: {agent_exit}",
        )

    def teardown_task(self, task_id: str) -> None:
        """Remove task context from active dict."""
        self._active_contexts.pop(task_id, None)

    def reset_environment(self) -> None:
        """Clean all active task contexts."""
        self._active_contexts.clear()
