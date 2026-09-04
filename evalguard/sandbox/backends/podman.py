"""Podman container sandboxing backend for rootless container execution."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from evalguard.sandbox.backends.base import CommandResult, SandboxBackend
from evalguard.sandbox.profiles import SandboxProfile

logger = logging.getLogger(__name__)


class PodmanBackend(SandboxBackend):
    """Hermetic isolation backend using Podman (daemonless, rootless)."""

    def __init__(
        self,
        task_id: str,
        profile: SandboxProfile,
        base_image: str = "docker.io/library/python:3.11-slim",
    ) -> None:
        super().__init__(task_id, profile)
        self.base_image = base_image
        self.container_name = f"evalguard-podman-{task_id}-{id(self)}"
        self._is_running = False

    @classmethod
    def backend_name(cls) -> str:
        return "podman"

    @classmethod
    def is_available(cls) -> bool:
        """Check if podman binary is in PATH and can run version."""
        if not shutil.which("podman"):
            return False
        try:
            res = subprocess.run(
                ["podman", "version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            return False

    def setup(self) -> None:
        """Start a podman container with workspace mount."""
        workspace_host = str(Path(self.profile.task_workspace_root).resolve())

        cmd = [
            "podman",
            "run",
            "-d",
            "--name",
            self.container_name,
            "-v",
            f"{workspace_host}:/workspace:rw,z",
            "-w",
            "/workspace",
            f"--memory={self.profile.max_memory_mb}m",
        ]

        if not self.profile.allow_outbound_network:
            cmd.extend(["--network", "none"])

        cmd.extend([self.base_image, "sleep", "infinity"])

        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self._is_running = True

    def run_command(
        self,
        cmd: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> CommandResult:
        """Execute command in running podman container."""
        if not self._is_running:
            raise RuntimeError(f"Cannot exec in non-running podman container '{self.container_name}'")

        exec_cmd = ["podman", "exec"]
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
                stderr=f"Podman command timed out after {timeout or self.profile.timeout_seconds}s",
            )

    def teardown(self) -> None:
        """Stop and remove the podman container."""
        if self._is_running:
            subprocess.run(
                ["podman", "rm", "-f", self.container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            self._is_running = False
