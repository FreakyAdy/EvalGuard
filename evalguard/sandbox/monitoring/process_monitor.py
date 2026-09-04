"""Process tree monitoring and ghost process leak detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import psutil

from evalguard.report.schema import BoundaryViolationRecord, BoundaryViolationType

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """Snapshot of a process running on the host system."""

    pid: int
    name: str
    cmdline: list[str]
    create_time: float
    ppid: int | None


class ProcessMonitor:
    """Monitors process creation during a benchmark task and flags lingering ghost processes."""

    def __init__(self) -> None:
        self._pre_task_pids: set[int] = set()
        self._pre_task_processes: dict[int, ProcessInfo] = {}
        self._is_active: bool = False

    def record_pre_task_state(self) -> None:
        """Capture the active process table prior to agent execution."""
        self._pre_task_pids.clear()
        self._pre_task_processes.clear()

        for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time", "ppid"]):
            try:
                info = proc.info
                pid = info["pid"]
                if pid is None:
                    continue
                self._pre_task_pids.add(pid)
                self._pre_task_processes[pid] = ProcessInfo(
                    pid=pid,
                    name=info.get("name") or "",
                    cmdline=info.get("cmdline") or [],
                    create_time=info.get("create_time") or 0.0,
                    ppid=info.get("ppid"),
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        self._is_active = True
        logger.debug("Captured %d baseline PIDs before task start", len(self._pre_task_pids))

    def detect_ghost_processes(
        self,
        task_id: str,
        excluded_pids: set[int] | None = None,
    ) -> list[BoundaryViolationRecord]:
        """Detect any processes that were spawned during the task and linger after task teardown."""
        if not self._is_active:
            return []

        violations: list[BoundaryViolationRecord] = []
        ignored_pids = set(excluded_pids or set())
        current_pids: set[int] = set()

        ignored_proc_names = {
            "brave.exe",
            "chrome.exe",
            "msedge.exe",
            "firefox.exe",
            "explorer.exe",
            "svchost.exe",
            "code.exe",
            "searchindexer.exe",
            "dwm.exe",
            "runtimebroker.exe",
            "taskhostw.exe",
        }

        for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time", "ppid"]):
            try:
                info = proc.info
                pid = info["pid"]
                if pid is None or pid in ignored_pids:
                    continue

                proc_name = (info.get("name") or "unknown").lower()
                if proc_name in ignored_proc_names:
                    continue

                current_pids.add(pid)

                # Process was NOT present prior to task execution
                if pid not in self._pre_task_pids:
                    proc_name = info.get("name") or "unknown"
                    cmdline_str = " ".join(info.get("cmdline") or [])
                    detail = (
                        f"Ghost process leak detected for task {task_id}: PID {pid} ('{proc_name}') "
                        f"spawned during task window and still running. Cmdline: {cmdline_str[:160]}"
                    )
                    violations.append(
                        BoundaryViolationRecord(
                            violation_type=BoundaryViolationType.GHOST_PROCESS,
                            detail=detail,
                            target=f"pid:{pid}:{proc_name}",
                            timestamp=datetime.now(timezone.utc),
                            severity="high",
                        )
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        self._is_active = False
        return violations
