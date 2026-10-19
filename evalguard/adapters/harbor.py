"""Harbor CLI adapter for local task directories and reward-bearing trial results."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from evalguard.adapters.base import (
    AdapterCapabilities,
    HarnessAdapter,
    TaskContext,
    TaskResult,
)

logger = logging.getLogger(__name__)


class HarborAdapter(HarnessAdapter):
    """Run one local Harbor task through its CLI and read the verifier reward.

    Harbor is intentionally invoked as a subprocess so EvalGuard does not need
    to install Harbor's dependency tree into its own Python environment. Pass
    the Harbor CLI agent name as the agent argument to run_task and configure
    the model when constructing this adapter.
    """

    def __init__(
        self,
        task_paths: Mapping[str, str | Path],
        model_name: str,
        jobs_dir: str | Path = "./evalguard_harbor_jobs",
        harbor_command: str = "harbor",
        reward_key: str = "reward",
        success_threshold: float = 1.0,
        timeout_seconds: int = 1200,
    ) -> None:
        """Configure local task IDs, a Harbor model, and the result output root."""
        if not task_paths:
            raise ValueError("task_paths must contain at least one task ID and path")
        if not model_name.strip():
            raise ValueError("model_name must not be empty")
        if not harbor_command.strip():
            raise ValueError("harbor_command must not be empty")
        if not reward_key.strip():
            raise ValueError("reward_key must not be empty")
        if not math.isfinite(success_threshold):
            raise ValueError("success_threshold must be finite")
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        if any(not key.strip() for key in task_paths):
            raise ValueError("task IDs must not be empty")

        super().__init__(
            name="harbor",
            capabilities=(
                AdapterCapabilities.SUPPORTS_SUBPROCESS_AGENT
                | AdapterCapabilities.SUPPORTS_STATE_SNAPSHOTS
            ),
        )
        self.task_paths = {
            task_id: Path(path).expanduser().resolve() for task_id, path in task_paths.items()
        }
        self.model_name = model_name
        self.jobs_dir = Path(jobs_dir).expanduser().resolve()
        self.harbor_command = harbor_command
        self.reward_key = reward_key
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        self._contexts: dict[str, TaskContext] = {}

    @staticmethod
    def _safe_task_name(task_id: str) -> str:
        """Return a filesystem-safe, collision-resistant output directory name."""
        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", task_id).strip("-_")[:36] or "task"
        digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:10]
        return f"{slug}-{digest}"

    def setup_task(self, task_id: str) -> TaskContext:
        """Validate a mapped local Harbor task and prepare a per-task results root."""
        if task_id not in self.task_paths:
            raise KeyError(f"Unknown Harbor task ID: {task_id}")

        task_path = self.task_paths[task_id]
        if not task_path.is_dir():
            raise FileNotFoundError(f"Harbor task directory does not exist: {task_path}")
        if not (task_path / "task.toml").is_file():
            raise FileNotFoundError(f"Harbor task directory has no task.toml file: {task_path}")

        output_root = self.jobs_dir / self._safe_task_name(task_id)
        output_root.mkdir(parents=True, exist_ok=True)
        context = TaskContext(
            task_id=task_id,
            workspace_root=str(output_root),
            instruction=f"Run Harbor task {task_id}",
            timeout_seconds=self.timeout_seconds,
            metadata={
                "harness": "harbor",
                "task_path": str(task_path),
                "jobs_dir": str(output_root),
            },
        )
        self._contexts[task_id] = context
        return context

    @staticmethod
    def _as_text(value: str | bytes | None) -> str:
        """Normalize subprocess output from completed and timed-out processes."""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value or ""

    @staticmethod
    def _result_reward_values(job_dir: Path, reward_key: str) -> list[float]:
        """Read numeric rewards from Harbor's per-trial result.json records."""
        rewards: list[float] = []
        for result_path in sorted(job_dir.rglob("result.json")):
            try:
                payload = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                logger.debug("Skipping unreadable Harbor result file: %s", result_path)
                continue

            if not isinstance(payload, dict):
                continue
            verifier_result = payload.get("verifier_result")
            if not isinstance(verifier_result, dict):
                continue
            values = verifier_result.get("rewards")
            if not isinstance(values, dict):
                continue

            reward = values.get(reward_key)
            if (
                isinstance(reward, int | float)
                and not isinstance(reward, bool)
                and math.isfinite(float(reward))
            ):
                rewards.append(float(reward))

        return rewards

    def run_task(self, agent: Any, task_id: str) -> TaskResult:
        """Run one Harbor task and derive pass/fail from its configured reward."""
        context = self._contexts.get(task_id)
        if context is None:
            context = self.setup_task(task_id)

        if not isinstance(agent, str) or not agent.strip():
            return TaskResult(
                task_id=task_id,
                passed=False,
                duration_seconds=0.0,
                error="HarborAdapter expects a non-empty Harbor CLI agent name string.",
            )

        task_path = str(context.metadata["task_path"])
        jobs_root = Path(context.workspace_root)
        job_name = f"evalguard-{uuid4().hex[:12]}"
        job_dir = jobs_root / job_name
        command = [
            self.harbor_command,
            "run",
            "-p",
            task_path,
            "-a",
            agent,
            "-m",
            self.model_name,
            "--jobs-dir",
            str(jobs_root),
            "--job-name",
            job_name,
            "--n-attempts",
            "1",
        ]

        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=task_path,
                capture_output=True,
                text=True,
                timeout=context.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = (
                f"[HARBOR STDOUT]\n{self._as_text(exc.stdout)}\n"
                f"[HARBOR STDERR]\n{self._as_text(exc.stderr)}"
            )
            return TaskResult(
                task_id=task_id,
                passed=False,
                duration_seconds=round(time.perf_counter() - started, 3),
                output=output,
                error="TimeoutExpired",
            )
        except OSError as exc:
            return TaskResult(
                task_id=task_id,
                passed=False,
                duration_seconds=round(time.perf_counter() - started, 3),
                output="",
                error=f"Failed to start Harbor CLI: {exc}",
            )

        duration = round(time.perf_counter() - started, 3)
        output = f"[HARBOR STDOUT]\n{completed.stdout}\n[HARBOR STDERR]\n{completed.stderr}"
        if completed.returncode != 0:
            return TaskResult(
                task_id=task_id,
                passed=False,
                duration_seconds=duration,
                output=output,
                error=f"Harbor exited with code {completed.returncode}",
            )

        rewards = self._result_reward_values(job_dir, self.reward_key)
        if not rewards:
            return TaskResult(
                task_id=task_id,
                passed=False,
                duration_seconds=duration,
                output=output,
                error=(
                    f"Harbor exited successfully but produced no numeric "
                    f"'{self.reward_key}' reward in per-trial result.json files "
                    f"under {job_dir}"
                ),
            )

        mean_reward = sum(rewards) / len(rewards)
        passed = mean_reward >= self.success_threshold
        return TaskResult(
            task_id=task_id,
            passed=passed,
            duration_seconds=duration,
            output=output,
            error=None
            if passed
            else (
                f"Mean Harbor reward {mean_reward:g} is below the configured "
                f"threshold {self.success_threshold:g}"
            ),
            extra_metrics={
                "harbor_reward_key": self.reward_key,
                "harbor_rewards": rewards,
                "harbor_mean_reward": mean_reward,
                "harbor_reward_threshold": self.success_threshold,
            },
        )

    def teardown_task(self, task_id: str) -> None:
        """Forget task metadata while preserving Harbor output files for auditing."""
        self._contexts.pop(task_id, None)

    def reset_environment(self) -> None:
        """Clear active task contexts without deleting retained trial evidence."""
        self._contexts.clear()
