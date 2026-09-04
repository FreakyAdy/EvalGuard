"""Standard schema and Pydantic models for EvalGuard reports."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class BoundaryViolationType(str, Enum):
    """Types of isolation boundary violations detected in sandboxes."""

    FILESYSTEM = "filesystem"
    ENV_VAR = "env_var"
    GHOST_PROCESS = "ghost_process"
    NETWORK_SOCKET = "network_socket"
    SHARED_MEMORY = "shared_memory"


class BoundaryViolationRecord(BaseModel):
    """Record of a boundary violation during task execution."""

    model_config = ConfigDict(frozen=True)

    violation_type: BoundaryViolationType
    detail: str
    target: str = Field(description="Target file, env var name, PID, or socket address")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    severity: str = Field(default="high", description="Severity level: low, medium, high, critical")


class SnapshotDiffRecord(BaseModel):
    """Summary of changes between pre-task and post-task workspace snapshots."""

    model_config = ConfigDict(frozen=True)

    added_files: list[str] = Field(default_factory=list)
    removed_files: list[str] = Field(default_factory=list)
    modified_files: list[str] = Field(default_factory=list)
    total_files_before: int = 0
    total_files_after: int = 0


class TamperType(str, Enum):
    """Categorization of agent test tampering methods."""

    DIRECT_TEST_MODIFICATION = "direct_test_modification"
    CONFTEST_INJECTION = "conftest_injection"
    SYS_PATH_MANIPULATION = "sys_path_manipulation"
    MOCK_INTERCEPTION = "mock_interception"


class TamperEventRecord(BaseModel):
    """Record of test tampering detected by static analysis."""

    model_config = ConfigDict(frozen=True)

    tamper_type: TamperType
    file_path: str
    description: str
    line_number: int | None = None
    code_snippet: str | None = None


class MutationProbeResult(BaseModel):
    """Result of a single test mutation probe round."""

    mutation_id: str
    strategy: str
    original_passed: bool
    mutated_passed: bool
    diff_summary: str = ""


class TrajectoryAnalysisRecord(BaseModel):
    """Analysis of agent's edit and solution trajectory."""

    edit_count: int = 0
    time_to_first_pass_seconds: float | None = None
    test_runs_before_success: int = 0
    first_attempt_success: bool = False
    trajectory_anomaly_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="0.0 = typical iterative solving, 1.0 = highly anomalous one-shot bypass",
    )
    notes: list[str] = Field(default_factory=list)


class RewardHackRecord(BaseModel):
    """Audit report for reward hacking detection on a single task."""

    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="0.0 = clean, 1.0 = definite reward hacking",
    )
    tamper_events: list[TamperEventRecord] = Field(default_factory=list)
    mutation_rounds_total: int = 0
    mutation_rounds_passed: int = 0
    mutation_pass_rate: float = 1.0
    mutation_probes: list[MutationProbeResult] = Field(default_factory=list)
    trajectory: TrajectoryAnalysisRecord | None = None


class ContaminationType(str, Enum):
    """Methods used to detect benchmark contamination."""

    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    TIMELINE = "timeline"
    DIFFERENTIAL = "differential"


class ContaminationFlag(BaseModel):
    """Contamination detection finding."""

    method: ContaminationType
    score: float = Field(description="Detection metric (e.g. n-gram jaccard, cosine similarity, z-score)")
    threshold: float
    is_contaminated: bool
    details: str
    matched_reference: str | None = None


class TaskIntegrityStatus(str, Enum):
    """Integrity evaluation of the benchmark test case itself."""

    PASS = "PASS"
    SUSPECT = "SUSPECT"
    INVALID = "INVALID"


class TestIntegrityRecord(BaseModel):
    """Audit of the benchmark test case's correctness."""

    status: TaskIntegrityStatus = TaskIntegrityStatus.PASS
    reference_solver_passed: bool | None = None
    trivially_permissive: bool = False
    universal_pass_rate: float | None = None
    cross_harness_divergence: bool = False
    evidence: list[str] = Field(default_factory=list)


# Alias for backward/naming consistency
TaskIntegrityRecord = TestIntegrityRecord


class TaskAuditRecord(BaseModel):
    """Complete audit record for a single benchmark task execution."""

    task_id: str
    agent_passed: bool
    duration_seconds: float = 0.0
    violations: list[BoundaryViolationRecord] = Field(default_factory=list)
    snapshot_diff: SnapshotDiffRecord | None = None
    reward_hack: RewardHackRecord | None = None
    contamination_flags: list[ContaminationFlag] = Field(default_factory=list)
    test_integrity: TestIntegrityRecord | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReportSummary(BaseModel):
    """Aggregated summary of an EvalGuard audit run."""

    total_tasks: int = 0
    agent_passed_tasks: int = 0
    boundary_violations_total: int = 0
    tasks_with_violations: int = 0
    tasks_with_reward_hack: int = 0
    tasks_with_contamination: int = 0
    suspect_or_invalid_tests: int = 0
    clean_passed_tasks: int = 0


class EvalGuardReport(BaseModel):
    """The canonical EvalGuard audit report."""

    schema_version: str = Field(default="1.0.0", description="Version of the EvalGuard schema")
    report_id: str = Field(default_factory=lambda: f"eg-{uuid4().hex[:12]}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    benchmark_id: str
    agent_id: str
    harness_name: str = "unknown"
    summary: ReportSummary = Field(default_factory=ReportSummary)
    tasks: list[TaskAuditRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
