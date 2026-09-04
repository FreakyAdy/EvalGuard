"""Unit tests for backend auto-detection, fallback, and container backends."""

from __future__ import annotations

import tempfile
from unittest.mock import MagicMock, patch

import pytest

from evalguard.sandbox.backends.detector import (
    detect_available_backend,
    get_backend,
)
from evalguard.sandbox.backends.docker import DockerBackend
from evalguard.sandbox.backends.firecracker import FirecrackerBackend
from evalguard.sandbox.backends.gvisor import GVisorBackend
from evalguard.sandbox.backends.host import HostProcessBackend
from evalguard.sandbox.backends.podman import PodmanBackend
from evalguard.sandbox.profiles import SandboxProfile


def test_detector_fallback_to_host() -> None:
    with patch.object(GVisorBackend, "is_available", return_value=False), \
         patch.object(FirecrackerBackend, "is_available", return_value=False), \
         patch.object(DockerBackend, "is_available", return_value=False), \
         patch.object(PodmanBackend, "is_available", return_value=False):
        backend_cls = detect_available_backend()
        assert backend_cls == HostProcessBackend


def test_get_backend_variants() -> None:
    with tempfile.TemporaryDirectory() as td:
        profile = SandboxProfile(
            task_workspace_root=td,
            read_write_paths=[td],
        )

        # 1. Auto backend
        b_auto = get_backend("auto", "task_auto", profile)
        assert b_auto is not None

        # 2. Host backend
        b_host = get_backend("host", "task_host", profile)
        assert isinstance(b_host, HostProcessBackend)

        # 3. Unknown backend raises ValueError
        with pytest.raises(ValueError, match="Unknown sandbox backend"):
            get_backend("unknown_backend_xyz", "task_err", profile)


def test_docker_backend_mocked() -> None:
    with tempfile.TemporaryDirectory() as td:
        profile = SandboxProfile(
            task_workspace_root=td,
            read_write_paths=[td],
        )
        backend = DockerBackend("task_docker_1", profile)
        assert backend.backend_name() == "docker"

        with patch("shutil.which", return_value="/usr/bin/docker"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            assert DockerBackend.is_available() is True

            # Test setup
            backend.setup()
            assert backend._is_running is True

            # Test run_command
            mock_run.return_value = MagicMock(returncode=0, stdout="hello", stderr="")
            res = backend.run_command(["echo", "hello"])
            assert res.exit_code == 0
            assert res.stdout == "hello"

            # Test teardown
            backend.teardown()
            assert backend._is_running is False


def test_podman_backend_mocked() -> None:
    with tempfile.TemporaryDirectory() as td:
        profile = SandboxProfile(
            task_workspace_root=td,
            read_write_paths=[td],
        )
        backend = PodmanBackend("task_podman_1", profile)
        assert backend.backend_name() == "podman"

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            assert PodmanBackend.is_available() is True

            backend.setup()
            assert backend._is_running is True

            mock_run.return_value = MagicMock(returncode=0, stdout="podman-out", stderr="")
            res = backend.run_command(["echo", "hi"])
            assert res.stdout == "podman-out"

            backend.teardown()
            assert backend._is_running is False


def test_gvisor_backend_mocked() -> None:
    with tempfile.TemporaryDirectory() as td:
        profile = SandboxProfile(
            task_workspace_root=td,
            read_write_paths=[td],
        )
        backend = GVisorBackend("task_gvisor_1", profile)
        assert backend.backend_name() == "gvisor"

        with patch("shutil.which", return_value="/usr/bin/runsc"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Runtimes: runsc runc", stderr="")
            assert GVisorBackend.is_available() is True

            backend.setup()
            assert backend._is_running is True

            mock_run.return_value = MagicMock(returncode=0, stdout="gvisor-out", stderr="")
            res = backend.run_command(["date"])
            assert res.stdout == "gvisor-out"

            backend.teardown()
            assert backend._is_running is False
