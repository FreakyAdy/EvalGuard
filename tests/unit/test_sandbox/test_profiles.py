"""Unit tests for SandboxProfile YAML parsing, path validation, and writability checks."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from evalguard.sandbox.profiles import ProfileValidationError, SandboxProfile


def test_sandbox_profile_default_initialization() -> None:
    profile = SandboxProfile()
    assert profile.name == "default-profile"
    assert profile.max_memory_mb == 4096
    assert profile.prevent_ghost_processes is True
    assert profile.is_path_writable(profile.task_workspace_root)


def test_sandbox_profile_from_yaml() -> None:
    yaml_text = """
    name: test-profile
    task_workspace_root: ./custom_ws
    allowed_write_paths:
      - ./custom_ws
      - /tmp/custom
    denied_write_paths:
      - /etc
      - ~/.ssh
    allowed_env_vars:
      - PATH
      - HOME
    timeout_seconds: 400
    allow_outbound_network: false
    """
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w+", delete=False) as f:
        f.write(yaml_text)
        temp_path = f.name

    try:
        profile = SandboxProfile.from_yaml(temp_path)
        assert profile.name == "test-profile"
        assert profile.timeout_seconds == 400
        assert profile.allow_outbound_network is False
        assert profile.is_path_writable("./custom_ws/file.py")
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_sandbox_profile_denied_paths_override() -> None:
    profile = SandboxProfile(
        task_workspace_root="./ws",
        denied_write_paths=["./ws/forbidden"],
        allowed_write_paths=["./ws"],
    )
    assert profile.is_path_writable("./ws/allowed.py") is True
    assert profile.is_path_writable("./ws/forbidden/hack.py") is False


def test_sandbox_profile_validation_error_on_overlap() -> None:
    with pytest.raises(ProfileValidationError):
        SandboxProfile(
            task_workspace_root="/etc",
            denied_write_paths=["/etc"],
        ).validate_paths()
