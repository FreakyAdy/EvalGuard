"""SARIF (Static Analysis Results Interchange Format) exporter for GitHub Security."""

from __future__ import annotations

import json
from typing import Any

from evalguard.report.schema import EvalGuardReport


class SarifExporter:
    """Exports EvalGuard integrity violations and tamper events to standard SARIF v2.1.0."""

    @classmethod
    def export(cls, report: EvalGuardReport) -> str:
        rules: list[dict[str, Any]] = [
            {
                "id": "EG001",
                "name": "FilesystemBoundaryViolation",
                "shortDescription": {"text": "Agent wrote to path outside hermetic boundary"},
                "defaultConfiguration": {"level": "error"},
            },
            {
                "id": "EG002",
                "name": "GhostProcessLeak",
                "shortDescription": {"text": "Process spawned during task survived teardown"},
                "defaultConfiguration": {"level": "warning"},
            },
            {
                "id": "EG003",
                "name": "DirectTestTampering",
                "shortDescription": {"text": "Agent modified or deleted benchmark test fixture"},
                "defaultConfiguration": {"level": "error"},
            },
            {
                "id": "EG004",
                "name": "IndirectEnvironmentTampering",
                "shortDescription": {
                    "text": "Agent injected conftest.py or manipulated sys.path/mocks"
                },
                "defaultConfiguration": {"level": "error"},
            },
            {
                "id": "EG005",
                "name": "RewardHackingProbeDivergence",
                "shortDescription": {
                    "text": "Agent failed semantically equivalent mutated test probes"
                },
                "defaultConfiguration": {"level": "warning"},
            },
        ]

        results: list[dict[str, Any]] = []

        for task in report.tasks:
            # Boundary violations
            for v in task.violations:
                rule_id = "EG001" if v.violation_type.value == "filesystem" else "EG002"
                results.append(
                    {
                        "ruleId": rule_id,
                        "message": {"text": f"[{task.task_id}] {v.detail}"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": v.target},
                                }
                            }
                        ],
                    }
                )

            # Tamper events
            if task.reward_hack:
                for te in task.reward_hack.tamper_events:
                    rule_id = "EG003" if "direct" in te.tamper_type.value else "EG004"
                    loc: dict[str, Any] = {
                        "physicalLocation": {
                            "artifactLocation": {"uri": te.file_path},
                        }
                    }
                    if te.line_number:
                        loc["physicalLocation"]["region"] = {"startLine": te.line_number}

                    results.append(
                        {
                            "ruleId": rule_id,
                            "message": {"text": f"[{task.task_id}] {te.description}"},
                            "locations": [loc],
                        }
                    )

        sarif_doc = {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "EvalGuard",
                            "semanticVersion": report.schema_version,
                            "informationUri": "https://github.com/evalguard/evalguard",
                            "rules": rules,
                        }
                    },
                    "results": results,
                }
            ],
        }

        return json.dumps(sarif_doc, indent=2)
