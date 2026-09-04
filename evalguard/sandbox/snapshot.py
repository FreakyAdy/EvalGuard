"""Content-addressed (SHA-256) workspace snapshotting and diffing."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from evalguard.report.schema import SnapshotDiffRecord


def compute_file_sha256(file_path: Path | str, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hex digest of a file in streaming chunks."""
    hasher = hashlib.sha256()
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Cannot hash non-existent or non-file path: {path}")

    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


class WorkspaceSnapshot:
    """Content-addressed manifest of a directory tree at a point in time."""

    def __init__(
        self,
        root_path: Path | str,
        manifest: dict[str, str] | None = None,
        file_sizes: dict[str, int] | None = None,
    ) -> None:
        self.root_path = Path(root_path).resolve()
        self.manifest: dict[str, str] = manifest or {}  # relative_path -> sha256
        self.file_sizes: dict[str, int] = file_sizes or {}  # relative_path -> size in bytes

    @classmethod
    def capture(
        cls,
        root_path: Path | str,
        ignore_patterns: set[str] | None = None,
    ) -> WorkspaceSnapshot:
        """Capture a content-addressed snapshot of root_path."""
        root = Path(root_path).resolve()
        manifest: dict[str, str] = {}
        file_sizes: dict[str, int] = {}

        if not root.exists():
            return cls(root_path=root, manifest=manifest, file_sizes=file_sizes)

        default_ignore = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
        ignores = default_ignore | (ignore_patterns or set())

        for dirpath, dirnames, filenames in os.walk(root):
            # Prune ignored directories in-place
            dirnames[:] = [d for d in dirnames if d not in ignores]

            for fname in filenames:
                if fname.endswith(".pyc") or fname in ignores:
                    continue

                full_path = Path(dirpath) / fname
                # Skip broken symlinks or non-regular files
                if not full_path.is_file():
                    continue

                try:
                    rel_path = full_path.relative_to(root).as_posix()
                    file_sha = compute_file_sha256(full_path)
                    file_size = full_path.stat().st_size
                    manifest[rel_path] = file_sha
                    file_sizes[rel_path] = file_size
                except (PermissionError, FileNotFoundError, OSError):
                    # In hermetic testing, ephemeral files may vanish or be unreadable
                    continue

        return cls(root_path=root, manifest=manifest, file_sizes=file_sizes)

    def diff(self, other: WorkspaceSnapshot) -> SnapshotDiffRecord:
        """Compare this snapshot (before) against another (after)."""
        before_keys = set(self.manifest.keys())
        after_keys = set(other.manifest.keys())

        added = sorted(list(after_keys - before_keys))
        removed = sorted(list(before_keys - after_keys))

        modified: list[str] = []
        for common_file in before_keys & after_keys:
            if self.manifest[common_file] != other.manifest[common_file]:
                modified.append(common_file)
        modified.sort()

        return SnapshotDiffRecord(
            added_files=added,
            removed_files=removed,
            modified_files=modified,
            total_files_before=len(before_keys),
            total_files_after=len(after_keys),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to serializable dictionary."""
        return {
            "root_path": str(self.root_path),
            "total_files": len(self.manifest),
            "manifest": self.manifest,
            "file_sizes": self.file_sizes,
        }

    def to_json(self, path: Path | str | None = None) -> str:
        """Serialize snapshot manifest to JSON."""
        data_str = json.dumps(self.to_dict(), indent=2, sort_keys=True)
        if path:
            dest = Path(path).resolve()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(data_str, encoding="utf-8")
        return data_str
