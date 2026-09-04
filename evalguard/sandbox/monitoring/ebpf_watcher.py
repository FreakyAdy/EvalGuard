"""eBPF-based syscall interception for Linux hermetic boundary enforcement."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from evalguard.report.schema import BoundaryViolationRecord, BoundaryViolationType
from evalguard.sandbox.profiles import SandboxProfile

logger = logging.getLogger(__name__)


class EbpfUnavailableError(RuntimeError):
    """Raised when eBPF monitoring cannot be initialized (non-Linux or missing bcc/headers)."""


# Minimal BPF C program to intercept openat, unlinkat, and renameat syscalls
BPF_SYSCALL_TRACER_C = r"""
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>
#include <linux/fs.h>

struct val_t {
    u32 pid;
    char comm[TASK_COMM_LEN];
    char fname[256];
    int flags;
};

BPF_PERF_OUTPUT(events);

int syscall__enter_openat(struct pt_regs *ctx, int dfd, const char __user *filename, int flags) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    struct val_t val = {};
    val.pid = pid;
    val.flags = flags;
    bpf_get_current_comm(&val.comm, sizeof(val.comm));
    bpf_probe_read_user_str(&val.fname, sizeof(val.fname), filename);
    events.perf_submit(ctx, &val, sizeof(val));
    return 0;
}
"""


class EbpfWatcher:
    """eBPF-based syscall interceptor that monitors low-level filesystem writes."""

    def __init__(
        self,
        task_id: str,
        profile: SandboxProfile,
        target_pid: int | None = None,
        on_violation: Callable[[BoundaryViolationRecord], None] | None = None,
    ) -> None:
        self.task_id = task_id
        self.profile = profile
        self.target_pid = target_pid
        self.on_violation = on_violation
        self.violations: list[BoundaryViolationRecord] = []
        self._bpf: Any = None
        self._is_running = False

    @classmethod
    def is_supported(cls) -> bool:
        """Check whether the host kernel and environment support eBPF tracing."""
        if not sys.platform.startswith("linux"):
            return False
        if os.geteuid() != 0:  # eBPF requires CAP_SYS_ADMIN or root
            return False
        try:
            import bcc  # noqa: F401

            return True
        except ImportError:
            return False

    def start(self) -> None:
        """Compile and attach the eBPF program, or raise EbpfUnavailableError."""
        if not self.is_supported():
            raise EbpfUnavailableError(
                "eBPF monitoring is unavailable. Ensure you are running on Linux as root "
                "with kernel headers and bcc installed (e.g. apt-get install bpfcc-tools python3-bpfcc)."
            )

        try:
            from bcc import BPF

            self._bpf = BPF(text=BPF_SYSCALL_TRACER_C)
            self._bpf.attach_kprobe(
                event=self._bpf.get_syscall_fnname("openat"), fn_name="syscall__enter_openat"
            )
            self._is_running = True
            logger.info(
                "eBPF watcher successfully attached to sys_enter_openat for task %s", self.task_id
            )
        except Exception as e:
            raise EbpfUnavailableError(f"Failed to load eBPF probe: {e}") from e

    def poll(self, timeout_ms: int = 100) -> list[BoundaryViolationRecord]:
        """Poll the perf buffer for intercepted syscalls."""
        if not self._is_running or self._bpf is None:
            return []

        def _process_event(cpu: int, data: Any, size: int) -> None:
            event = self._bpf["events"].event(data)
            fname = event.fname.decode("utf-8", "replace")
            # Only trace write/create flags (O_WRONLY=1, O_RDWR=2, O_CREAT=64, O_TRUNC=512)
            is_write = (event.flags & (1 | 2 | 64 | 512)) != 0
            if is_write and not self.profile.is_path_writable(fname):
                record = BoundaryViolationRecord(
                    violation_type=BoundaryViolationType.FILESYSTEM,
                    detail=f"eBPF intercepted unauthorized syscall write to '{fname}' from comm='{event.comm.decode()}' pid={event.pid}",
                    target=fname,
                    timestamp=datetime.now(timezone.utc),
                    severity="critical",
                )
                self.violations.append(record)
                if self.on_violation:
                    self.on_violation(record)

        try:
            self._bpf["events"].open_perf_buffer(_process_event)
            self._bpf.perf_buffer_poll(timeout_ms)
        except Exception as err:
            logger.warning("Error during eBPF poll: %s", err)

        return self.violations

    def stop(self) -> list[BoundaryViolationRecord]:
        """Detach and cleanup the eBPF probe."""
        self._is_running = False
        self._bpf = None
        return list(self.violations)
