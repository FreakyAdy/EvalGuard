"""Unit tests for TamperDetector static AST and snapshot analysis."""

from __future__ import annotations

import tempfile
from pathlib import Path

from evalguard.report.schema import TamperType
from evalguard.rewardhack.tamper_detector import TamperDetector
from evalguard.sandbox.snapshot import WorkspaceSnapshot


def test_tamper_detector_direct_test_file_modification() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        test_file = root / "test_suite.py"
        test_file.write_text("def test_one(): assert True")

        snap_before = WorkspaceSnapshot.capture(root)

        # Agent modifies test file
        test_file.write_text("def test_one(): pass  # hacked")
        snap_after = WorkspaceSnapshot.capture(root)

        events = TamperDetector.check_snapshots(snap_before, snap_after)
        assert len(events) == 1
        assert events[0].tamper_type == TamperType.DIRECT_TEST_MODIFICATION
        assert "test_suite.py" in events[0].file_path


def test_tamper_detector_conftest_injection() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "conftest.py").write_text(
            "import pytest\n@pytest.fixture(autouse=True)\ndef bypass(): pass"
        )

        events = TamperDetector.check_indirect_tampering(root, ["conftest.py"])
        assert len(events) >= 1
        types = [e.tamper_type for e in events]
        assert TamperType.CONFTEST_INJECTION in types


def test_tamper_detector_sys_path_manipulation() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        code = "import sys\nsys.path.insert(0, '/tmp/evil')\n"
        (root / "solver.py").write_text(code)

        events = TamperDetector.check_indirect_tampering(root, ["solver.py"])
        assert len(events) == 1
        assert events[0].tamper_type == TamperType.SYS_PATH_MANIPULATION
