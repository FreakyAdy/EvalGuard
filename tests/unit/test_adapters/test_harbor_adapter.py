"""Tests for the optional Harbor CLI adapter without installing Harbor."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from evalguard.adapters.base import AdapterCapabilities
from evalguard.adapters.harbor import HarborAdapter


def make_task(tmp_path: Path) -> Path:
    """Create a minimal local Harbor task definition."""
    task_path = tmp_path / "hello-world"
    task_path.mkdir()
    (task_path / "task.toml").write_text(
        '[task]\nname = "test/hello-world"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    return task_path


def make_adapter(
    tmp_path: Path,
    task_path: Path,
    *,
    success_threshold: float = 1.0,
) -> HarborAdapter:
    """Build an adapter with an isolated output directory."""
    return HarborAdapter(
        task_paths={"hello": task_path},
        model_name="test-provider/test-model",
        jobs_dir=tmp_path / "jobs",
        success_threshold=success_threshold,
    )


def mock_harbor_success(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reward: int | float = 1.0,
    returncode: int = 0,
) -> None:
    """Replace Harbor CLI execution and write a realistic per-trial reward file."""

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        jobs_root = Path(command[command.index("--jobs-dir") + 1])
        job_name = command[command.index("--job-name") + 1]
        result_path = jobs_root / job_name / "trial-1" / "result.json"
        result_path.parent.mkdir(parents=True)
        result_path.write_text(
            json.dumps(
                {
                    "task_name": "hello-world",
                    "verifier_result": {"rewards": {"reward": reward}},
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            args=command,
            returncode=returncode,
            stdout="Harbor run finished",
            stderr="",
        )

    monkeypatch.setattr("evalguard.adapters.harbor.subprocess.run", fake_run)


def test_harbor_adapter_runs_cli_and_reads_verifier_reward(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_path = make_task(tmp_path)
    adapter = make_adapter(tmp_path, task_path)
    mock_harbor_success(monkeypatch, reward=1.0)

    result = adapter.run_task("mock-agent", "hello")

    assert result.passed is True
    assert result.error is None
    assert result.extra_metrics["harbor_mean_reward"] == 1.0
    assert result.extra_metrics["harbor_reward_key"] == "reward"
    assert "[HARBOR STDOUT]" in result.output
    assert adapter.capabilities & AdapterCapabilities.SUPPORTS_SUBPROCESS_AGENT


def test_harbor_adapter_fails_when_reward_is_below_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = make_adapter(tmp_path, make_task(tmp_path), success_threshold=0.75)
    mock_harbor_success(monkeypatch, reward=0.5)

    result = adapter.run_task("mock-agent", "hello")

    assert result.passed is False
    assert result.extra_metrics["harbor_mean_reward"] == 0.5
    assert "below the configured threshold" in (result.error or "")


def test_harbor_adapter_reports_nonzero_cli_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = make_adapter(tmp_path, make_task(tmp_path))
    mock_harbor_success(monkeypatch, reward=1.0, returncode=3)

    result = adapter.run_task("mock-agent", "hello")

    assert result.passed is False
    assert result.error == "Harbor exited with code 3"


def test_harbor_adapter_does_not_treat_missing_reward_as_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = make_adapter(tmp_path, make_task(tmp_path))

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        jobs_root = Path(command[command.index("--jobs-dir") + 1])
        job_name = command[command.index("--job-name") + 1]
        result_path = jobs_root / job_name / "trial-1" / "result.json"
        result_path.parent.mkdir(parents=True)
        result_path.write_text(
            json.dumps({"verifier_result": {"rewards": {"correctness": 1.0}}}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "finished", "")

    monkeypatch.setattr("evalguard.adapters.harbor.subprocess.run", fake_run)
    result = adapter.run_task("mock-agent", "hello")

    assert result.passed is False
    assert "no numeric 'reward' reward" in (result.error or "")


def test_harbor_adapter_reports_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = make_adapter(tmp_path, make_task(tmp_path))

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            command=command,
            timeout=kwargs["timeout"],
            output="partial stdout",
            stderr="timed out",
        )

    monkeypatch.setattr("evalguard.adapters.harbor.subprocess.run", fake_run)
    result = adapter.run_task("mock-agent", "hello")

    assert result.passed is False
    assert result.error == "TimeoutExpired"
    assert "partial stdout" in result.output
    assert "timed out" in result.output


def test_harbor_adapter_validates_task_mapping_and_task_definition(
    tmp_path: Path,
) -> None:
    task_path = make_task(tmp_path)
    adapter = make_adapter(tmp_path, task_path)

    with pytest.raises(KeyError, match="Unknown Harbor task ID"):
        adapter.setup_task("missing")

    invalid_task = tmp_path / "no-task-config"
    invalid_task.mkdir()
    invalid_adapter = make_adapter(tmp_path, invalid_task)
    with pytest.raises(FileNotFoundError, match="task.toml"):
        invalid_adapter.setup_task("hello")


def test_harbor_adapter_rejects_invalid_agent_argument(
    tmp_path: Path,
) -> None:
    adapter = make_adapter(tmp_path, make_task(tmp_path))

    result = adapter.run_task(None, "hello")

    assert result.passed is False
    assert "Harbor CLI agent name string" in (result.error or "")
