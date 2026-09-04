"""Benchmark contamination auditing layer: lexical, semantic, timeline, differential."""

from evalguard.contamination.auditor import ContaminationAuditor
from evalguard.contamination.differential import DifferentialAnalyzer
from evalguard.contamination.indices import (
    BenchmarkContaminationIndex,
    create_humaneval_index,
    create_livecodebench_index,
    create_mbpp_index,
    create_swebench_index,
    get_benchmark_index,
)
from evalguard.contamination.lexical import (
    LexicalDetector,
    LexicalMatchResult,
    extract_ngrams,
    levenshtein_distance,
    tokenize_code_or_text,
)
from evalguard.contamination.semantic import (
    EmbeddingBackend,
    SemanticDetector,
    SentenceTransformersBackend,
    SimpleTfIdfBackend,
    cosine_similarity,
)
from evalguard.contamination.timeline import TimelineAuditor, parse_date
from evalguard.report.schema import ContaminationFlag, ContaminationType

# Aliases
CosineSimilarityBackend = SimpleTfIdfBackend
ContaminationReport = list[ContaminationFlag]

__all__ = [
    "BenchmarkContaminationIndex",
    "ContaminationAuditor",
    "ContaminationFlag",
    "ContaminationReport",
    "ContaminationType",
    "CosineSimilarityBackend",
    "DifferentialAnalyzer",
    "EmbeddingBackend",
    "LexicalDetector",
    "LexicalMatchResult",
    "SemanticDetector",
    "SentenceTransformersBackend",
    "SimpleTfIdfBackend",
    "TimelineAuditor",
    "cosine_similarity",
    "create_humaneval_index",
    "create_livecodebench_index",
    "create_mbpp_index",
    "create_swebench_index",
    "extract_ngrams",
    "get_benchmark_index",
    "levenshtein_distance",
    "parse_date",
    "tokenize_code_or_text",
]
