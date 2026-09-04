"""Pytest plugin providing fixtures and test assertions for adapter authors."""

from __future__ import annotations

from typing import Any

import pytest

from evalguard.adapters.base import HarnessAdapter
from evalguard.adapters.verifier import AdapterValidationReport, AdapterVerifier


@pytest.fixture
def evalguard_verifier() -> Any:
    """Fixture returning a factory function to verify a HarnessAdapter."""

    def _verify(adapter: HarnessAdapter) -> AdapterValidationReport:
        verifier = AdapterVerifier(adapter)
        report = verifier.verify_all()
        if not report.all_passed:
            failed_checks = [c for c in report.checks if not c.passed]
            msg = "\n".join(f"- {c.check_name}: {c.message}" for c in failed_checks)
            pytest.fail(f"EvalGuard Adapter verification failed for '{adapter.name}':\n{msg}")
        return report

    return _verify
