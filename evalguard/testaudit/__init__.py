"""Benchmark test case integrity auditing layer."""

from evalguard.report.schema import TaskIntegrityStatus, TestIntegrityRecord
from evalguard.testaudit.auditor import TestAuditor
from evalguard.testaudit.cross_harness import CrossHarnessAuditor
from evalguard.testaudit.reference_runner import (
    TRIVIAL_SOLUTIONS,
    ReferenceRunner,
)
from evalguard.testaudit.statistical_detector import StatisticalDetector

# Aliases
TaskIntegrityReport = TestIntegrityRecord

__all__ = [
    "CrossHarnessAuditor",
    "ReferenceRunner",
    "StatisticalDetector",
    "TRIVIAL_SOLUTIONS",
    "TaskIntegrityReport",
    "TaskIntegrityStatus",
    "TestAuditor",
    "TestIntegrityRecord",
]
