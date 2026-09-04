"""Hermetic isolation and boundary monitoring layer."""

from evalguard.report.schema import (
    BoundaryViolationRecord,
    BoundaryViolationType,
    SnapshotDiffRecord,
)
from evalguard.sandbox.backends import (
    DockerBackend,
    FirecrackerBackend,
    GVisorBackend,
    HostProcessBackend,
    PodmanBackend,
    SandboxBackend,
    detect_available_backend,
    get_backend,
)
from evalguard.sandbox.harness_sandbox import HarnessSandbox
from evalguard.sandbox.monitoring.ebpf_watcher import EbpfUnavailableError, EbpfWatcher
from evalguard.sandbox.monitoring.inotify_watcher import InotifyWatcher
from evalguard.sandbox.monitoring.process_monitor import ProcessMonitor
from evalguard.sandbox.profiles import ProfileValidationError, SandboxProfile
from evalguard.sandbox.snapshot import WorkspaceSnapshot, compute_file_sha256

# Backwards compatible alias: BoundaryViolation -> BoundaryViolationRecord
BoundaryViolation = BoundaryViolationRecord

__all__ = [
    "BoundaryViolation",
    "BoundaryViolationRecord",
    "BoundaryViolationType",
    "DockerBackend",
    "EbpfUnavailableError",
    "EbpfWatcher",
    "FirecrackerBackend",
    "GVisorBackend",
    "HarnessSandbox",
    "HostProcessBackend",
    "InotifyWatcher",
    "PodmanBackend",
    "ProcessMonitor",
    "ProfileValidationError",
    "SandboxBackend",
    "SandboxProfile",
    "SnapshotDiffRecord",
    "WorkspaceSnapshot",
    "compute_file_sha256",
    "detect_available_backend",
    "get_backend",
]
