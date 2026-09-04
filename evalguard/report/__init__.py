"""EvalGuard reporting, audit document generation, and diffing."""

from evalguard.report.builder import ReportBuilder
from evalguard.report.diff import ReportDiffer, ReportDiffResult, TaskDiffEntry
from evalguard.report.exporters import (
    CsvExporter,
    HtmlExporter,
    MarkdownExporter,
    SarifExporter,
)
from evalguard.report.schema import (
    BoundaryViolationRecord,
    BoundaryViolationType,
    ContaminationFlag,
    ContaminationType,
    EvalGuardReport,
    MutationProbeResult,
    ReportSummary,
    RewardHackRecord,
    SnapshotDiffRecord,
    TamperEventRecord,
    TamperType,
    TaskAuditRecord,
    TaskIntegrityRecord,
    TaskIntegrityStatus,
    TrajectoryAnalysisRecord,
)
from evalguard.report.viewer import ReportViewer

__all__ = [
    "BoundaryViolationRecord",
    "BoundaryViolationType",
    "ContaminationFlag",
    "ContaminationType",
    "CsvExporter",
    "EvalGuardReport",
    "HtmlExporter",
    "MarkdownExporter",
    "MutationProbeResult",
    "ReportBuilder",
    "ReportDiffResult",
    "ReportDiffer",
    "ReportSummary",
    "ReportViewer",
    "RewardHackRecord",
    "SarifExporter",
    "SnapshotDiffRecord",
    "TamperEventRecord",
    "TamperType",
    "TaskAuditRecord",
    "TaskDiffEntry",
    "TaskIntegrityRecord",
    "TaskIntegrityStatus",
    "TrajectoryAnalysisRecord",
]
