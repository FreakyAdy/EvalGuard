"""Unit tests for HarnessSandbox context manager and boundary enforcement."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from evalguard.report.schema import BoundaryViolationRecord, BoundaryViolationType
from evalguard.sandbox.harness_sandbox import HarnessSandbox
from evalguard.sandbox.monitoring.process_monitor import ProcessMonitor
from evalguard.sandbox.profiles import SandboxProfile


def _ignore_host_process_noise(
    _monitor: ProcessMonitor,
    _task_id: str,
    _excluded_pids: set[int] | None = None,
) -> list[BoundaryViolationRecord]:
    """Return no ghost-process violations for tests isolating other behavior."""
    return []


def _record_empty_process_baseline(monitor: ProcessMonitor) -> None:
    """Use a deterministic baseline for a synthetic network-violation test."""
    monitor._pre_task_pids = set()


def test_harness_sandbox_clean_run(monkeypatch: pytest.MonkeyPatch) -> None:
    # The host backend observes host-wide state. Background Windows services can
    # create processes and sockets during this test, so isolate those observations.
    monkeypatch.setattr(
        HarnessSandbox, "_capture_network_connections", lambda _sandbox: set()
    )
    monkeypatch.setattr(
        ProcessMonitor, "detect_ghost_processes", _ignore_host_process_noise
    )

    with tempfile.TemporaryDirectory() as td:
        profile = SandboxProfile(task_workspace_root=td)
        with HarnessSandbox(task_id="clean_01", profile=profile, backend="host") as sb:
            (Path(td) / "solution.py").write_text("def solve(): return 42")

        violations = sb.get_violations()
        diff = sb.get_snapshot_diff()

        assert "solution.py" in diff.added_files
        assert len(violations) == 0


def test_harness_sandbox_detects_new_task_network_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connections = iter(
        [
            set(),
            {(999_999, ("127.0.0.1", 12345), ("203.0.113.1", 443))},
        ]
    )
    monkeypatch.setattr(
        HarnessSandbox,
        "_capture_network_connections",
        lambda _sandbox: next(connections),
    )
    monkeypatch.setattr(
        ProcessMonitor, "record_pre_task_state", _record_empty_process_baseline
    )
    monkeypatch.setattr(
        ProcessMonitor, "detect_ghost_processes", _ignore_host_process_noise
    )

    with tempfile.TemporaryDirectory() as td:
        profile = SandboxProfile(task_workspace_root=td)
        with HarnessSandbox(
            task_id="network_01", profile=profile, backend="host"
        ) as sb:
            (Path(td) / "solution.py").write_text("def solve(): return 42")

    network_violations = [
        violation
        for violation in sb.get_violations()
        if violation.violation_type == BoundaryViolationType.NETWORK_SOCKET
    ]
    assert len(network_violations) == 1
    assert "203.0.113.1" in network_violations[0].detail


def test_harness_sandbox_detects_unauthorized_env_mutation() -> None:
    with tempfile.TemporaryDirectory() as td:
        profile = SandboxProfile(
            task_workspace_root=td, allowed_env_vars=["PATH", "HOME"]
        )
        with HarnessSandbox(
            task_id="env_test_01", profile=profile, backend="host"
        ) as sb:
            os.environ["LEAKED_SECRET_VAR"] = "compromised"

        try:
            violations = sb.get_violations()
            env_violations = [
                v
                for v in violations
                if v.violation_type == BoundaryViolationType.ENV_VAR
            ]
            assert len(env_violations) > 0
            assert "LEAKED_SECRET_VAR" in env_violations[0].detail
        finally:
            os.environ.pop("LEAKED_SECRET_VAR", None)
