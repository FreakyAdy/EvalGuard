"""Unit tests for pre-built benchmark indices and serialization."""

from __future__ import annotations

import tempfile
from pathlib import Path

from evalguard.contamination.indices import (
    BenchmarkContaminationIndex,
    get_benchmark_index,
)


def test_builtin_indices_retrieve() -> None:
    for name in ["humaneval", "swebench", "mbpp", "livecodebench"]:
        idx = get_benchmark_index(name)
        assert idx.benchmark_name != ""
        assert len(idx.tasks) > 0


def test_benchmark_index_save_and_load() -> None:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        temp_file = f.name

    try:
        idx = BenchmarkContaminationIndex("custom_bench", corpus_disclosure_date="2024-02-01")
        idx.add_task(
            task_id="t1",
            prompt="def solve(x): return x * 2",
            solution="def solve(x): return x * 2",
        )
        idx.save(temp_file)

        loaded = BenchmarkContaminationIndex.load(temp_file)
        assert loaded.benchmark_name == "custom_bench"
        assert loaded.corpus_disclosure_date == "2024-02-01"
        assert "t1" in loaded.tasks
    finally:
        Path(temp_file).unlink(missing_ok=True)
