"""Unit tests for content-addressed SHA-256 workspace snapshotting and diffing."""

from __future__ import annotations

import tempfile
from pathlib import Path

from evalguard.sandbox.snapshot import WorkspaceSnapshot, compute_file_sha256


def test_compute_file_sha256() -> None:
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
        f.write("hello evalguard")
        path = f.name

    try:
        digest = compute_file_sha256(path)
        assert len(digest) == 64
        # Verify deterministic hash
        assert digest == compute_file_sha256(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_workspace_snapshot_capture_and_diff() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "a.py").write_text("print('a')")
        (root / "b.txt").write_text("initial b")

        snap1 = WorkspaceSnapshot.capture(root)
        assert "a.py" in snap1.manifest
        assert "b.txt" in snap1.manifest

        # Mutate workspace: modify b.txt, add c.py, remove a.py
        (root / "a.py").unlink()
        (root / "b.txt").write_text("modified b")
        (root / "c.py").write_text("print('c')")

        snap2 = WorkspaceSnapshot.capture(root)
        diff = snap1.diff(snap2)

        assert diff.added_files == ["c.py"]
        assert diff.removed_files == ["a.py"]
        assert diff.modified_files == ["b.txt"]
        assert diff.total_files_before == 2
        assert diff.total_files_after == 2


def test_workspace_snapshot_ignores_cache() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pycache = root / "__pycache__"
        pycache.mkdir()
        (pycache / "compiled.pyc").write_text("bytecode")
        (root / "valid.py").write_text("code")

        snap = WorkspaceSnapshot.capture(root)
        assert "valid.py" in snap.manifest
        assert len(snap.manifest) == 1
