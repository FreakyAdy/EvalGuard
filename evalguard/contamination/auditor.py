"""Unified contamination auditor combining lexical, semantic, timeline, and differential analysis."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from evalguard.contamination.differential import DifferentialAnalyzer
from evalguard.contamination.indices import (
    BenchmarkContaminationIndex,
    get_benchmark_index,
)
from evalguard.contamination.lexical import LexicalDetector
from evalguard.contamination.semantic import SemanticDetector
from evalguard.contamination.timeline import TimelineAuditor
from evalguard.report.schema import ContaminationFlag, ContaminationType

logger = logging.getLogger(__name__)


class ContaminationAuditor:
    """Multi-signal benchmark contamination auditor."""

    def __init__(
        self,
        benchmark_name: str,
        index: BenchmarkContaminationIndex | None = None,
        lexical_detector: LexicalDetector | None = None,
        semantic_detector: SemanticDetector | None = None,
        outlier_threshold: float = 2.5,
    ) -> None:
        self.benchmark_name = benchmark_name
        try:
            self.index = index or get_benchmark_index(benchmark_name)
        except KeyError:
            self.index = index or BenchmarkContaminationIndex(benchmark_name)

        self.lexical_detector = lexical_detector or LexicalDetector()
        self.semantic_detector = semantic_detector or SemanticDetector()
        self.differential_analyzer = DifferentialAnalyzer(outlier_z_threshold=outlier_threshold)

        disclosure_date = self.index.corpus_disclosure_date or "2024-01-01"
        self.timeline_auditor = TimelineAuditor(benchmark_disclosure_date=disclosure_date)

    def audit_task(
        self,
        task_id: str,
        agent_solution_or_training_text: str,
        agent_cutoff_date: str | None = None,
        cohort_task_scores: Mapping[str, float] | None = None,
        target_agent_id: str = "target_agent",
    ) -> list[ContaminationFlag]:
        """Perform comprehensive multi-signal contamination audit on a single task."""
        flags: list[ContaminationFlag] = []

        # 1. Timeline disclosure audit
        timeline_flag = self.timeline_auditor.evaluate_agent(agent_cutoff_date, task_id=task_id)
        flags.append(timeline_flag)

        # 2. Differential cohort analysis
        if cohort_task_scores:
            diff_flag = self.differential_analyzer.analyze_task_cohort(
                task_id=task_id,
                target_agent_id=target_agent_id,
                cohort_scores=cohort_task_scores,
            )
            if diff_flag:
                flags.append(diff_flag)

        # 3. Lexical and Semantic matching against task in index
        if task_id in self.index.tasks:
            task_data = self.index.tasks[task_id]
            ref_content = f"{task_data['prompt']}\n{task_data['solution']}"

            # Lexical check
            lex_res = self.lexical_detector.compare(agent_solution_or_training_text, ref_content)
            flags.append(
                ContaminationFlag(
                    method=ContaminationType.LEXICAL,
                    score=lex_res.containment_score,
                    threshold=self.lexical_detector.containment_threshold,
                    is_contaminated=lex_res.is_contaminated,
                    details=(
                        f"Lexical overlap: containment={lex_res.containment_score:.3f}, "
                        f"jaccard={lex_res.jaccard_similarity:.3f}, exact_6grams={lex_res.exact_match_count}, "
                        f"longest_contiguous_tokens={lex_res.longest_contiguous_tokens}"
                    ),
                    matched_reference=f"{self.benchmark_name}:{task_id}",
                )
            )

            # Semantic check
            sem_score, sem_contaminated = self.semantic_detector.compare(
                agent_solution_or_training_text,
                ref_content,
            )
            flags.append(
                ContaminationFlag(
                    method=ContaminationType.SEMANTIC,
                    score=sem_score,
                    threshold=self.semantic_detector.similarity_threshold,
                    is_contaminated=sem_contaminated,
                    details=f"Semantic embedding cosine similarity={sem_score:.3f}",
                    matched_reference=f"{self.benchmark_name}:{task_id}",
                )
            )

        return flags
