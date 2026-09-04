"""Base class and structure for pre-built benchmark contamination indices."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evalguard.contamination.lexical import (
    LexicalDetector,
    LexicalMatchResult,
    extract_ngrams,
    tokenize_code_or_text,
)


class BenchmarkContaminationIndex:
    """An index of canonical tasks, descriptions, and solutions for a benchmark."""

    def __init__(
        self,
        benchmark_name: str,
        tasks: dict[str, dict[str, Any]] | None = None,
        corpus_disclosure_date: str | None = None,
    ) -> None:
        self.benchmark_name = benchmark_name
        self.tasks: dict[str, dict[str, Any]] = (
            tasks or {}
        )  # task_id -> {prompt, solution, test, ...}
        self.corpus_disclosure_date = corpus_disclosure_date
        self._ngram_index: dict[tuple[str, ...], set[str]] = {}

    def add_task(
        self,
        task_id: str,
        prompt: str,
        solution: str = "",
        test_fixture: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a benchmark task to the index."""
        self.tasks[task_id] = {
            "prompt": prompt,
            "solution": solution,
            "test_fixture": test_fixture,
            "metadata": metadata or {},
        }
        # Index 6-grams from prompt and solution
        tokens = tokenize_code_or_text(f"{prompt}\n{solution}")
        for ng in extract_ngrams(tokens, 6):
            if ng not in self._ngram_index:
                self._ngram_index[ng] = set()
            self._ngram_index[ng].add(task_id)

    def scan_candidate(
        self,
        candidate_text: str,
        detector: LexicalDetector | None = None,
    ) -> list[tuple[str, LexicalMatchResult]]:
        """Scan candidate agent training or generation text against all indexed tasks."""
        det = detector or LexicalDetector()
        cand_tokens = tokenize_code_or_text(candidate_text)
        cand_ngrams = extract_ngrams(cand_tokens, 6)

        # Find candidate task IDs with overlapping ngrams
        candidate_task_ids: set[str] = set()
        for ng in cand_ngrams:
            if ng in self._ngram_index:
                candidate_task_ids.update(self._ngram_index[ng])

        results: list[tuple[str, LexicalMatchResult]] = []
        for tid in candidate_task_ids:
            task_data = self.tasks[tid]
            ref_combined = f"{task_data['prompt']}\n{task_data['solution']}"
            res = det.compare(candidate_text, ref_combined)
            if res.is_contaminated or res.containment_score > 0.15:
                results.append((tid, res))

        # Sort by containment score descending
        results.sort(key=lambda x: x[1].containment_score, reverse=True)
        return results

    def save(self, file_path: str | Path) -> None:
        """Serialize index to JSON."""
        dest = Path(file_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "benchmark_name": self.benchmark_name,
            "corpus_disclosure_date": self.corpus_disclosure_date,
            "tasks": self.tasks,
        }
        dest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, file_path: str | Path) -> BenchmarkContaminationIndex:
        """Load index from JSON."""
        path = Path(file_path).resolve()
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        idx = cls(
            benchmark_name=data.get("benchmark_name", "unknown"),
            corpus_disclosure_date=data.get("corpus_disclosure_date"),
        )
        for tid, tinfo in data.get("tasks", {}).items():
            idx.add_task(
                task_id=tid,
                prompt=tinfo.get("prompt", ""),
                solution=tinfo.get("solution", ""),
                test_fixture=tinfo.get("test_fixture", ""),
                metadata=tinfo.get("metadata", {}),
            )
        return idx
