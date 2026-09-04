"""Sandbox configuration profiles for task boundaries."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


def normalize_path(path: str | Path) -> str:
    """Resolve symlinks, 8.3 Windows short paths, and user homes to canonical normcase path."""
    try:
        resolved = Path(path).expanduser().resolve()
        return os.path.normcase(str(resolved))
    except Exception:
        return os.path.normcase(os.path.abspath(os.path.expanduser(str(path))))


class ProfileValidationError(Exception):
    """Raised when a sandbox profile fails validation."""


class SandboxProfile(BaseModel):
    """Specification of hermetic boundaries for a benchmark task.

    Maintainers ship this as a YAML file alongside benchmark definitions.
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="default-profile", description="Name of the benchmark profile")
    task_workspace_root: str = Field(
        default="./workspace",
        description="Root directory where the agent is allowed to write",
    )
    allowed_write_paths: list[str] = Field(
        default_factory=lambda: ["./workspace", "/tmp/agent_scratch"],
        description="Relative or absolute paths where writes are explicitly permitted",
    )
    denied_write_paths: list[str] = Field(
        default_factory=lambda: ["/etc", "/usr", "/var", "/bin", "/sbin", "~/.ssh", "~/.aws"],
        description="Explicitly forbidden paths even if workspace is mounted parent",
    )
    allowed_env_vars: list[str] = Field(
        default_factory=lambda: [
            "PATH",
            "HOME",
            "USER",
            "LANG",
            "LC_ALL",
            "PYTHONPATH",
            "VIRTUAL_ENV",
            "TERM",
            "TMPDIR",
            "EVALGUARD_TASK_ID",
        ],
        description="Environment variables permitted to be read or modified",
    )
    allowed_network_cidrs: list[str] = Field(
        default_factory=list,
        description="CIDR blocks allowed for outbound network traffic (empty = airgapped)",
    )
    allow_outbound_network: bool = Field(
        default=False,
        description="If False, all outbound sockets constitute a boundary violation",
    )
    max_memory_mb: int = Field(
        default=4096,
        description="Maximum memory allocated to the task sandbox",
    )
    timeout_seconds: int = Field(
        default=600,
        description="Hard task timeout in seconds before terminating sandbox",
    )
    prevent_ghost_processes: bool = Field(
        default=True,
        description="Flag any process surviving task exit as a ghost process violation",
    )
    track_shared_memory: bool = Field(
        default=True,
        description="Monitor /dev/shm and IPC memory allocations",
    )

    @classmethod
    def from_yaml(cls, path: str | Path) -> SandboxProfile:
        """Load a sandbox profile from a YAML file."""
        file_path = Path(path).resolve()
        if not file_path.is_file():
            raise FileNotFoundError(f"Sandbox profile not found: {file_path}")

        try:
            with open(file_path, encoding="utf-8") as f:
                data: dict[str, Any] = yaml.safe_load(f) or {}
        except Exception as e:
            raise ProfileValidationError(f"Failed to parse YAML from {file_path}: {e}") from e

        profile = cls.model_validate(data)
        profile.validate_paths()
        return profile

    def to_yaml(self, path: str | Path | None = None) -> str:
        """Serialize profile to YAML string or write to file."""
        data = self.model_dump()
        yaml_content = str(yaml.dump(data, sort_keys=False, default_flow_style=False))
        if path:
            dest = Path(path).resolve()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(yaml_content, encoding="utf-8")
        return yaml_content

    def validate_paths(self) -> None:
        """Validate path constraints and check for nonsensical overlap."""
        norm_workspace = normalize_path(self.task_workspace_root)

        for denied in self.denied_write_paths:
            norm_denied = normalize_path(denied)
            if norm_workspace == norm_denied:
                raise ProfileValidationError(
                    f"Conflict in profile '{self.name}': workspace root '{self.task_workspace_root}' "
                    f"is explicitly listed in denied_write_paths."
                )

    def is_path_writable(self, target_path: str | Path) -> bool:
        """Check whether a given path is legally writable under this profile."""
        norm_target = normalize_path(target_path)

        # 1. Denied paths take absolute priority
        for denied in self.denied_write_paths:
            norm_denied = normalize_path(denied)
            if norm_target == norm_denied or norm_target.startswith(norm_denied + os.sep):
                return False

        # 2. Check if it is inside task workspace root
        norm_workspace = normalize_path(self.task_workspace_root)
        if norm_target == norm_workspace or norm_target.startswith(norm_workspace + os.sep):
            return True

        # 3. Check allowed write paths
        for allowed in self.allowed_write_paths:
            norm_allowed = normalize_path(allowed)
            if norm_target == norm_allowed or norm_target.startswith(norm_allowed + os.sep):
                return True

        return False
