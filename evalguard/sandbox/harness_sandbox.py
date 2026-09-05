"""Hermetic sandboxing manager for agent evaluations."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

from evalguard.report.schema import (
    BoundaryViolationRecord,
    BoundaryViolationType,
    SnapshotDiffRecord,
)
from evalguard.sandbox.backends import SandboxBackend, get_backend
from evalguard.sandbox.monitoring.ebpf_watcher import EbpfUnavailableError, EbpfWatcher
from evalguard.sandbox.monitoring.inotify_watcher import InotifyWatcher
from evalguard.sandbox.monitoring.process_monitor import ProcessMonitor
from evalguard.sandbox.profiles import SandboxProfile
from evalguard.sandbox.snapshot import WorkspaceSnapshot

logger = logging.getLogger(__name__)


class HarnessSandbox:
    """A harness-agnostic sandboxing context manager enforcing and verifying hermetic boundaries."""

    def __init__(
        self,
        task_id: str,
        profile: SandboxProfile | None = None,
        backend: str = "auto",
        on_violation: Callable[[BoundaryViolationRecord], None] | None = None,
    ) -> None:
        self.task_id = task_id
        self.profile = profile or SandboxProfile()
        self.backend_name = backend
        self.on_violation_callback = on_violation

        self._violations: list[BoundaryViolationRecord] = []
        self._pre_snapshot: WorkspaceSnapshot | None = None
        self._post_snapshot: WorkspaceSnapshot | None = None
        self._snapshot_diff: SnapshotDiffRecord | None = None

        self._process_monitor = ProcessMonitor()
        self._inotify_watcher: InotifyWatcher | None = None
        self._ebpf_watcher: EbpfWatcher | None = None

        self._backend: SandboxBackend | None = None
        self._pre_env: dict[str, str] = {}
        self._pre_connections: set[Any] = set()
        self._pre_shm_files: set[str] = set()

    def _record_violation(self, violation: BoundaryViolationRecord) -> None:
        """Append violation to internal list and notify callback if set."""
        self._violations.append(violation)
        logger.warning(
            "Boundary violation in task %s [%s]: %s",
            self.task_id,
            violation.violation_type.value,
            violation.detail,
        )
        if self.on_violation_callback:
            try:
                self.on_violation_callback(violation)
            except Exception as e:
                logger.error("Error in on_violation callback: %s", e)

    def _capture_shm_state(self) -> set[str]:
        """Capture files in /dev/shm if present (Linux shared memory)."""
        shm_path = Path("/dev/shm")
        if shm_path.exists() and shm_path.is_dir():
            try:
                return {p.name for p in shm_path.iterdir()}
            except (PermissionError, OSError):
                return set()
        return set()

    def _capture_network_connections(self) -> set[Any]:
        """Capture active outbound network connections."""
        connections = set()
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.status == "ESTABLISHED" and conn.raddr:
                    connections.add((conn.pid, conn.laddr, conn.raddr))
        except (psutil.AccessDenied, PermissionError, OSError):
            pass
        return connections

    def __enter__(self) -> HarnessSandbox:
        """Initialize isolation, snapshot state, and start monitoring."""
        logger.info("Entering hermetic sandbox for task '%s'", self.task_id)

        # 1. Capture pre-execution environment variables
        self._pre_env = dict(os.environ)

        # 2. Capture baseline shared memory & network sockets
        if self.profile.track_shared_memory:
            self._pre_shm_files = self._capture_shm_state()
        if not self.profile.allow_outbound_network:
            self._pre_connections = self._capture_network_connections()

        # 3. Capture baseline process table
        self._process_monitor.record_pre_task_state()

        # 4. Capture content-addressed pre-execution snapshot
        workspace_path = Path(self.profile.task_workspace_root).resolve()
        workspace_path.mkdir(parents=True, exist_ok=True)
        self._pre_snapshot = WorkspaceSnapshot.capture(workspace_path)

        # 5. Initialize backend
        self._backend = get_backend(self.backend_name, self.task_id, self.profile)
        try:
            self._backend.setup()
        except Exception as e:
            if not self.backend_name or self.backend_name == "auto":
                logger.warning(
                    "Backend '%s' failed setup (%s). Falling back to host process isolation.",
                    self._backend.backend_name(),
                    e,
                )
                from evalguard.sandbox.backends.host import HostProcessBackend

                self._backend = HostProcessBackend(self.task_id, self.profile)
                self._backend.setup()
            else:
                raise

        # 6. Start eBPF watcher if supported; otherwise fallback to inotify/watchdog
        try:
            self._ebpf_watcher = EbpfWatcher(
                self.task_id,
                self.profile,
                on_violation=self._record_violation,
            )
            self._ebpf_watcher.start()
        except (EbpfUnavailableError, Exception) as e:
            logger.debug("eBPF watcher unavailable (%s), using inotify watcher", e)
            self._ebpf_watcher = None
            watch_dirs = [workspace_path]
            try:
                import tempfile
                temp_root = Path(tempfile.gettempdir()).resolve()
                ws_parent = workspace_path.parent.resolve()
                if (
                    ws_parent.exists()
                    and ws_parent != temp_root
                    and ws_parent != Path.home().resolve()
                    and ws_parent != ws_parent.parent
                ):
                    watch_dirs.append(ws_parent)
            except Exception:
                pass

            self._inotify_watcher = InotifyWatcher(
                self.task_id,
                self.profile,
                watch_paths=watch_dirs,
                on_violation=self._record_violation,
            )
            self._inotify_watcher.start()

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Tear down isolation, detect boundary leaks, and generate post-snapshot."""
        logger.info("Exiting sandbox for task '%s'", self.task_id)

        # 1. Stop watchers and collect filesystem violations
        if self._ebpf_watcher:
            ebpf_violations = self._ebpf_watcher.stop()
            for v in ebpf_violations:
                if v not in self._violations:
                    self._record_violation(v)
            self._ebpf_watcher = None

        if self._inotify_watcher:
            inotify_violations = self._inotify_watcher.stop()
            for v in inotify_violations:
                if v not in self._violations:
                    self._record_violation(v)
            self._inotify_watcher = None

        # 2. Teardown backend container / processes
        if self._backend:
            try:
                self._backend.teardown()
            except Exception as e:
                logger.warning("Error during backend teardown: %s", e)
            self._backend = None

        # 3. Detect ghost processes
        if self.profile.prevent_ghost_processes:
            ghost_violations = self._process_monitor.detect_ghost_processes(self.task_id)
            for gv in ghost_violations:
                self._record_violation(gv)

        # 4. Check for unauthorized environment variable mutations
        allowed_env = set(self.profile.allowed_env_vars)
        current_env = dict(os.environ)
        for key, val in current_env.items():
            if key not in allowed_env:
                if key not in self._pre_env:
                    self._record_violation(
                        BoundaryViolationRecord(
                            violation_type=BoundaryViolationType.ENV_VAR,
                            detail=f"Unauthorized environment variable created: '{key}'",
                            target=f"env:{key}",
                            timestamp=datetime.now(timezone.utc),
                            severity="medium",
                        )
                    )
                elif self._pre_env[key] != val:
                    self._record_violation(
                        BoundaryViolationRecord(
                            violation_type=BoundaryViolationType.ENV_VAR,
                            detail=f"Unauthorized environment variable modified: '{key}'",
                            target=f"env:{key}",
                            timestamp=datetime.now(timezone.utc),
                            severity="medium",
                        )
                    )

        # 5. Check for lingering shared memory allocations
        if self.profile.track_shared_memory:
            post_shm = self._capture_shm_state()
            leaked_shm = post_shm - self._pre_shm_files
            for shm_item in leaked_shm:
                self._record_violation(
                    BoundaryViolationRecord(
                        violation_type=BoundaryViolationType.SHARED_MEMORY,
                        detail=f"Lingering shared memory segment leaked into /dev/shm: '{shm_item}'",
                        target=f"shm:{shm_item}",
                        timestamp=datetime.now(timezone.utc),
                        severity="high",
                    )
                )

        # 6. Check for unauthorized outbound sockets
        if not self.profile.allow_outbound_network:
            post_conns = self._capture_network_connections()
            new_conns = post_conns - self._pre_connections
            for conn in new_conns:
                pid = conn[0]
                is_task_pid = pid is not None and pid not in self._process_monitor._pre_task_pids
                if is_task_pid or self.backend_name in ("docker", "podman", "gvisor"):
                    self._record_violation(
                        BoundaryViolationRecord(
                            violation_type=BoundaryViolationType.NETWORK_SOCKET,
                            detail=f"Unauthorized outbound network socket opened to remote endpoint {conn[2]} by PID {pid}",
                            target=f"socket:{conn[2]}",
                            timestamp=datetime.now(timezone.utc),
                            severity="critical",
                        )
                    )

        # 7. Capture post-execution content-addressed workspace snapshot and diff
        workspace_path = Path(self.profile.task_workspace_root).resolve()
        self._post_snapshot = WorkspaceSnapshot.capture(workspace_path)
        if self._pre_snapshot:
            self._snapshot_diff = self._pre_snapshot.diff(self._post_snapshot)

    def get_violations(self) -> list[BoundaryViolationRecord]:
        """Return all boundary violations recorded during the sandbox session."""
        return list(self._violations)

    def get_snapshot(self) -> tuple[WorkspaceSnapshot, WorkspaceSnapshot]:
        """Return (pre_snapshot, post_snapshot)."""
        if self._pre_snapshot is None or self._post_snapshot is None:
            raise RuntimeError(
                "Snapshots are only available after exiting or capturing inside sandbox context."
            )
        return (self._pre_snapshot, self._post_snapshot)

    def get_snapshot_diff(self) -> SnapshotDiffRecord:
        """Return the diff between pre and post execution snapshots."""
        if self._snapshot_diff is None:
            if self._pre_snapshot and self._post_snapshot:
                self._snapshot_diff = self._pre_snapshot.diff(self._post_snapshot)
            else:
                raise RuntimeError("Snapshot diff is only available after exiting sandbox context.")
        return self._snapshot_diff
