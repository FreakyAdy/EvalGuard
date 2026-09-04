"""Unit tests for HarnessSandbox context manager and boundary enforcement."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from evalguard.report.schema import BoundaryViolationType
from evalguard.sandbox.harness_sandbox import HarnessSandbox
from evalguard.sandbox.profiles import SandboxProfile


def test_harness_sandbox_clean_run() -> None:
    with tempfile.TemporaryDirectory() as td:
        profile = SandboxProfile(task_workspace_root=td)
        with HarnessSandbox(task_id="clean_01", profile=profile, backend="host") as sb:
            (Path(td) / "solution.py").write_text("def solve(): return 42")

        violations = sb.get_violations()
        diff = sb.get_snapshot_diff()

        assert "solution.py" in diff.added_files
        assert len(violations) == 0


def test_harness_sandbox_detects_unauthorized_env_mutation() -> None:
    with tempfile.TemporaryDirectory() as td:
        profile = SandboxProfile(task_workspace_root=td, allowed_env_vars=["PATH", "HOME"])
        with HarnessSandbox(task_id="env_test_01", profile=profile, backend="host") as sb:
            os.environ["LEAKED_SECRET_VAR"] = "compromised"

        try:
            violations = sb.get_violations()
            env_violations = [
                v for v in violations if v.violation_type == BoundaryViolationType.ENV_VAR
            ]
            assert len(env_violations) > 0
            assert "LEAKED_SECRET_VAR" in env_violations[0].detail
        finally:
            os.environ.pop("LEAKED_SECRET_VAR", None)
