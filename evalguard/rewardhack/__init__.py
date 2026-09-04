"""Reward hacking detection layer: static tampering analysis, dynamic mutation probing, trajectory inspection."""

from evalguard.report.schema import (
    MutationProbeResult,
    RewardHackRecord,
    TamperEventRecord,
    TamperType,
    TrajectoryAnalysisRecord,
)
from evalguard.rewardhack.auditor import RewardHackAuditor
from evalguard.rewardhack.mutations import (
    ALL_MUTATION_STRATEGIES,
    AssertionEquivalenceMutator,
    AssertionReorderMutator,
    MutatedTest,
    MutationStrategy,
    NumericEpsilonMutator,
    PythonVariableMutator,
    StringNormalizationMutator,
)
from evalguard.rewardhack.tamper_detector import TamperDetector
from evalguard.rewardhack.trajectory_analyzer import (
    TrajectoryAnalyzer,
    TrajectoryEvent,
)

# Backwards compatible alias
AuditReport = RewardHackRecord
TamperEvent = TamperEventRecord

__all__ = [
    "ALL_MUTATION_STRATEGIES",
    "AssertionEquivalenceMutator",
    "AssertionReorderMutator",
    "AuditReport",
    "MutatedTest",
    "MutationProbeResult",
    "MutationStrategy",
    "NumericEpsilonMutator",
    "PythonVariableMutator",
    "RewardHackAuditor",
    "RewardHackRecord",
    "StringNormalizationMutator",
    "TamperDetector",
    "TamperEvent",
    "TamperEventRecord",
    "TamperType",
    "TrajectoryAnalysisRecord",
    "TrajectoryAnalyzer",
    "TrajectoryEvent",
]
