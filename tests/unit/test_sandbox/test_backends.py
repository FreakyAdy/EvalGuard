"""Unit tests for sandbox backend detection and HostProcessBackend execution."""

from __future__ import annotations

import tempfile

from evalguard.sandbox.backends import (
    BACKEND_REGISTRY,
    HostProcessBackend,
    detect_available_backend,
    get_backend,
)
from evalguard.sandbox.profiles import SandboxProfile


def test_detect_available_backend() -> None:
    backend_cls = detect_available_backend()
    assert backend_cls in BACKEND_REGISTRY.values()


def test_host_process_backend_run_command() -> None:
    with tempfile.TemporaryDirectory() as td:
        profile = SandboxProfile(task_workspace_root=td)
        backend = HostProcessBackend(task_id="host_test", profile=profile)
        backend.setup()

        res = backend.run_command(["python", "-c", "print('hello backend')"])
        assert res.exit_code == 0
        assert "hello backend" in res.stdout
        backend.teardown()


def test_get_backend_factory() -> None:
    profile = SandboxProfile()
    b = get_backend("host", "t1", profile)
    assert isinstance(b, HostProcessBackend)
