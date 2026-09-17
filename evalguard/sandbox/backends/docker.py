"""Docker container sandboxing backend."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from evalguard.sandbox.backends.base import CommandResult, SandboxBackend
from evalguard.sandbox.profiles import SandboxProfile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DockerDiagnostic:
    """Structured result of probing the local Docker installation.

    ``available`` is ``True`` only when both the CLI binary is on ``PATH``
    and the daemon answers ``docker info`` successfully.
    """

    available: bool
    reason: str
    hints: tuple[str, ...] = ()

    @classmethod
    def ok(cls) -> DockerDiagnostic:
        """Return a diagnostic representing a healthy Docker installation."""
        return cls(available=True, reason="Docker daemon is reachable and healthy.")

    @staticmethod
    def platform_hints() -> tuple[str, ...]:
        """Return actionable instructions for the current platform."""
        if sys.platform == "darwin":
            return (
                "Start Docker Desktop:\n    open -a Docker",
                "Wait for the whale icon to stop animating before re-running.",
            )
        if sys.platform.startswith("win"):
            return (
                "Start Docker Desktop from the Start menu or run:\n    & \"C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe\"",
                "If Docker Desktop reports 'no daemon', relaunch it and retry.",
            )
        return (
            "Start the Docker daemon (needs sudo unless you are in the docker group):\n    sudo systemctl start docker",
            "Enable auto-start on boot:\n    sudo systemctl enable --now docker",
            "After starting, verify with:\n    docker info",
        )


class DockerBackend(SandboxBackend):
    """Hermetic isolation backend using Docker containers."""

    def __init__(
        self,
        task_id: str,
        profile: SandboxProfile,
        base_image: str = "python:3.11-slim",
    ) -> None:
        super().__init__(task_id, profile)
        self.base_image = base_image
        self.container_name = f"evalguard-{task_id}-{id(self)}"
        self._is_running = False

    @classmethod
    def backend_name(cls) -> str:
        return "docker"

    @classmethod
    def diagnose(cls) -> DockerDiagnostic:
        """Probe the local Docker installation and return a structured reason.

        This is the diagnostic core used by :meth:`is_available` and surfaced
        by the CLI when a requested backend fails to come up. It distinguishes
        three failure modes so callers can emit actionable guidance:
        binary missing on ``PATH``, daemon unreachable, and probe timeout.
        """
        docker_bin = shutil.which("docker")
        if docker_bin is None:
            hints = (
                "Install the Docker CLI and add it to PATH:",
                "    https://docs.docker.com/get-docker/",
                DockerDiagnostic.platform_hints()[0],
            )
            return DockerDiagnostic(
                available=False,
                reason=(
                    "Docker CLI not found on PATH. The 'docker' executable is required "
                    "before the daemon can be reached."
                ),
                hints=hints,
            )

        try:
            res = subprocess.run(
                ["docker", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=3,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return DockerDiagnostic(
                available=False,
                reason=(
                    "Docker daemon did not respond to 'docker info' within 3s. "
                    "The CLI is present but the daemon is likely not running."
                ),
                hints=DockerDiagnostic.platform_hints(),
            )
        except Exception as exc:  # pragma: no cover - defensive
            return DockerDiagnostic(
                available=False,
                reason=f"Docker probe failed unexpectedly: {exc}",
                hints=DockerDiagnostic.platform_hints(),
            )

        if res.returncode != 0:
            stderr_tail = (res.stderr or b"").decode("utf-8", errors="replace").strip().splitlines()
            detail = stderr_tail[-1] if stderr_tail else "docker info failed"
            return DockerDiagnostic(
                available=False,
                reason=(
                    f"Docker daemon is unreachable ({detail}). The CLI is present "
                    "but the daemon is not answering 'docker info'."
                ),
                hints=DockerDiagnostic.platform_hints(),
            )

        return DockerDiagnostic.ok()

    @classmethod
    def is_available(cls) -> bool:
        """Check if docker binary is present and daemon is reachable."""
        return cls.diagnose().available

    def setup(self) -> None:
        """Start an idle container with workspace volume mounts."""
        workspace_host = str(Path(self.profile.task_workspace_root).resolve())

        cmd = [
            "docker",
            "run",
            "-d",
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

        logger.debug("Starting docker container: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self._is_running = True

    def run_command(
        self,
        cmd: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> CommandResult:
        """Execute command in running container via docker exec."""
        if not self._is_running:
            raise RuntimeError(f"Cannot exec in non-running container '{self.container_name}'")

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
                stderr=f"Command timed out after {timeout or self.profile.timeout_seconds}s",
            )

    def teardown(self) -> None:
        """Stop and remove the container."""
        if self._is_running:
            subprocess.run(
                ["docker", "rm", "-f", self.container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            self._is_running = False
