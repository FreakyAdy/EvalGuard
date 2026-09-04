"""gVisor (runsc) sandboxing backend for application kernel isolation."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from evalguard.sandbox.backends.base import CommandResult, SandboxBackend
from evalguard.sandbox.profiles import SandboxProfile

logger = logging.getLogger(__name__)


class GVisorBackend(SandboxBackend):
    """Sandboxing backend using gVisor's runsc sandbox runtime via Docker."""

    def __init__(
        self,
        task_id: str,
        profile: SandboxProfile,
        base_image: str = "python:3.11-slim",
    ) -> None:
        super().__init__(task_id, profile)
        self.base_image = base_image
        self.container_name = f"evalguard-gvisor-{task_id}-{id(self)}"
        self._is_running = False

    @classmethod
    def backend_name(cls) -> str:
        return "gvisor"

    @classmethod
    def is_available(cls) -> bool:
        """Check if runsc binary exists and Docker daemon has runsc runtime configured."""
        if not shutil.which("runsc") and not shutil.which("docker"):
            return False
        try:
            # Check if docker has runsc runtime configured
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            return "runsc" in res.stdout
        except Exception:
            return False

    def setup(self) -> None:
        """Launch gVisor isolated container with --runtime=runsc."""
        workspace_host = str(Path(self.profile.task_workspace_root).resolve())

        cmd = [
            "docker",
            "run",
            "-d",
            "--runtime=runsc",
            "--name",
            self.container_name,
            "-v",
            f"{workspace_host}:/workspace:rw",
            "-w",
            "/workspace",
            f"--memory={self.profile.max_memory_mb}m",
        ]

        if not self.profile.allow_outbound_network:
            cmd.extend(["--network", "none"])

        cmd.extend([self.base_image, "tail", "-f", "/dev/null"])

        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self._is_running = True

    def run_command(
        self,
        cmd: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> CommandResult:
        """Execute inside gVisor container."""
        if not self._is_running:
            raise RuntimeError(f"gVisor container '{self.container_name}' is not running")

        exec_cmd = ["docker", "exec"]
        if cwd:
            exec_cmd.extend(["-w", cwd])
        if env:
            for k, v in env.items():
                exec_cmd.extend(["-e", f"{k}={v}"])

        exec_cmd.append(self.container_name)
        exec_cmd.extend(cmd)

        try:
            res = subprocess.run(
                exec_cmd,
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
                stderr=f"gVisor task execution timed out after {timeout or self.profile.timeout_seconds}s",
            )

    def teardown(self) -> None:
        """Tear down gVisor container."""
        if self._is_running:
            subprocess.run(
                ["docker", "rm", "-f", self.container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            self._is_running = False
