"""Harness adapters and verification tooling for benchmark integration."""

from evalguard.adapters.base import (
    AdapterCapabilities,
    AgentProtocol,
    HarnessAdapter,
    TaskContext,
    TaskResult,
)
from evalguard.adapters.openenv import OpenEnvAdapter
from evalguard.adapters.subprocess_adapter import GenericSubprocessAdapter
from evalguard.adapters.swebench import SWEBenchAdapter
from evalguard.adapters.terminal_bench import TerminalBenchAdapter
from evalguard.adapters.verifier import (
    AdapterCheckResult,
    AdapterValidationReport,
    AdapterVerifier,
)

__all__ = [
    "AdapterCapabilities",
    "AdapterCheckResult",
    "AdapterValidationReport",
    "AdapterVerifier",
    "AgentProtocol",
    "GenericSubprocessAdapter",
    "HarnessAdapter",
    "OpenEnvAdapter",
    "SWEBenchAdapter",
    "TaskContext",
    "TaskResult",
    "TerminalBenchAdapter",
]
