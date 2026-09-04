"""Abstract base class for container and virtualization sandboxing backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import NamedTuple

from evalguard.sandbox.profiles import SandboxProfile


class CommandResult(NamedTuple):
    """Result of running a command inside a sandbox backend."""

    exit_code: int
    stdout: str
    stderr: str


class SandboxBackend(ABC):
    """Abstract interface for hermetic task execution backends."""

    def __init__(self, task_id: str, profile: SandboxProfile) -> None:
        self.task_id = task_id
        self.profile = profile

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Return True if this backend is installed and operational on the host."""
        ...

    @classmethod
    @abstractmethod
    def backend_name(cls) -> str:
        """Name of the backend."""
        ...

    @abstractmethod
    def setup(self) -> None:
        """Initialize the isolated container or virtual machine."""
        ...

    @abstractmethod
    def run_command(
        self,
        cmd: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> CommandResult:
        """Execute a command inside the isolated environment."""
        ...

    @abstractmethod
    def teardown(self) -> None:
        """Destroy the container or VM and release all allocated resources."""
        ...
