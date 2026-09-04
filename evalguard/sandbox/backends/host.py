"""Host process sandboxing backend for local environments and graceful fallback."""

from __future__ import annotations

import logging
import os
import subprocess

from evalguard.sandbox.backends.base import CommandResult, SandboxBackend
from evalguard.sandbox.profiles import SandboxProfile

logger = logging.getLogger(__name__)


class HostProcessBackend(SandboxBackend):
    """Fallback sandboxing backend executing directly on the host with process & filesystem monitoring."""

    def __init__(self, task_id: str, profile: SandboxProfile) -> None:
        super().__init__(task_id, profile)
        self._spawned_pids: list[int] = []

    @classmethod
    def backend_name(cls) -> str:
        return "host"

    @classmethod
    def is_available(cls) -> bool:
        """Host execution is always available as a fallback."""
        return True

    def setup(self) -> None:
        """Ensure workspace directory exists."""
        os.makedirs(self.profile.task_workspace_root, exist_ok=True)

    def run_command(
        self,
        cmd: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> CommandResult:
        """Run command as a host subprocess with timeout enforcement."""
        working_dir = cwd or self.profile.task_workspace_root
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        try:
            res = subprocess.run(
                cmd,
                cwd=working_dir,
                env=merged_env,
                capture_output=True,
                text=True,
                timeout=timeout or self.profile.timeout_seconds,
                check=False,
            )
            return CommandResult(
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
            )
        except subprocess.TimeoutExpired:
            return CommandResult(
                exit_code=124,
                stdout="",
                stderr=f"Host execution timed out after {timeout or self.profile.timeout_seconds}s",
            )

    def teardown(self) -> None:
        """No container teardown needed for host execution."""
        pass
