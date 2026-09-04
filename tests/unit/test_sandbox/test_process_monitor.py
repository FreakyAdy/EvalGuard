"""Unit tests for ProcessMonitor and ghost process leak detection."""

from __future__ import annotations

import subprocess
import sys

from evalguard.report.schema import BoundaryViolationType
from evalguard.sandbox.monitoring.process_monitor import ProcessMonitor


def test_process_monitor_captures_baseline() -> None:
    monitor = ProcessMonitor()
    monitor.record_pre_task_state()
    assert monitor._is_active is True
    assert len(monitor._pre_task_pids) > 0


def test_process_monitor_detects_ghost_process() -> None:
    monitor = ProcessMonitor()
    monitor.record_pre_task_state()

    # Spawn a background lingering process
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(2)"])
    try:
        violations = monitor.detect_ghost_processes(task_id="ghost_test_01")
        ghost_pids = [
            int(v.target.split(":")[1])
            for v in violations
            if v.violation_type == BoundaryViolationType.GHOST_PROCESS
        ]
        assert proc.pid in ghost_pids
    finally:
        proc.terminate()
        proc.wait()
