"""Filesystem boundary watcher using watchdog (inotify/ReadDirectoryChanges/FSEvents)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from evalguard.report.schema import BoundaryViolationRecord, BoundaryViolationType
from evalguard.sandbox.profiles import SandboxProfile

logger = logging.getLogger(__name__)


class BoundaryViolationHandler(FileSystemEventHandler):
    """Event handler that validates file system operations against a SandboxProfile."""

    def __init__(
        self,
        task_id: str,
        profile: SandboxProfile,
        on_violation: Callable[[BoundaryViolationRecord], None] | None = None,
    ) -> None:
        super().__init__()
        self.task_id = task_id
        self.profile = profile
        self.on_violation = on_violation
        self.violations: list[BoundaryViolationRecord] = []

    def _check_and_record(self, path: str, op: str) -> None:
        if not self.profile.is_path_writable(path):
            detail = (
                f"Filesystem boundary violation in task {self.task_id}: unauthorized {op} "
                f"at path '{path}' outside permitted boundaries."
            )
            record = BoundaryViolationRecord(
                violation_type=BoundaryViolationType.FILESYSTEM,
                detail=detail,
                target=path,
                timestamp=datetime.now(timezone.utc),
                severity="critical",
            )
            self.violations.append(record)
            if self.on_violation:
                self.on_violation(record)

    def on_created(self, event: FileSystemEvent) -> None:
        self._check_and_record(str(event.src_path), "create")

    def on_modified(self, event: FileSystemEvent) -> None:
        self._check_and_record(str(event.src_path), "modify")

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._check_and_record(str(event.src_path), "delete")

    def on_moved(self, event: FileSystemEvent) -> None:
        self._check_and_record(str(event.src_path), "move_from")
        if hasattr(event, "dest_path") and event.dest_path:
            self._check_and_record(str(event.dest_path), "move_to")


class InotifyWatcher:
    """Filesystem watcher that enforces sandbox boundary integrity during task runs."""

    def __init__(
        self,
        task_id: str,
        profile: SandboxProfile,
        watch_paths: list[str | Path] | None = None,
        on_violation: Callable[[BoundaryViolationRecord], None] | None = None,
    ) -> None:
        self.task_id = task_id
        self.profile = profile
        self.watch_paths = [Path(p).resolve() for p in (watch_paths or [profile.task_workspace_root])]
        self.handler = BoundaryViolationHandler(task_id, profile, on_violation)
        self.observer: Any = None

    def start(self) -> None:
        """Start the filesystem observer."""
        self.observer = Observer()
        for p in self.watch_paths:
            if p.exists():
                self.observer.schedule(self.handler, str(p), recursive=True)
                logger.debug("Watching directory for boundary violations: %s", p)
        self.observer.start()

    def stop(self) -> list[BoundaryViolationRecord]:
        """Stop observer and return any violations captured."""
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2.0)
            self.observer = None
        return list(self.handler.violations)
