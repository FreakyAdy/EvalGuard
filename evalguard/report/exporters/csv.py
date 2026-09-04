"""CSV report exporter for spreadsheet and tabular analysis."""

from __future__ import annotations

import csv
import io

from evalguard.report.schema import EvalGuardReport


class CsvExporter:
    """Exports task audit records to CSV format."""

    @classmethod
    def export(cls, report: EvalGuardReport) -> str:
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow([
            "benchmark_id",
            "agent_id",
            "harness_name",
            "task_id",
            "agent_passed",
            "duration_seconds",
            "violations_count",
            "violation_types",
            "reward_hack_confidence",
            "tamper_events_count",
            "mutation_pass_rate",
            "is_contaminated",
            "contamination_methods",
            "test_integrity_status",
            "reference_solver_passed",
            "trivially_permissive",
        ])

        for t in report.tasks:
            viol_types = ";".join({v.violation_type.value for v in t.violations})
            hack_score = t.reward_hack.confidence_score if t.reward_hack else 0.0
            tamper_count = len(t.reward_hack.tamper_events) if t.reward_hack else 0
            mut_pass_rate = t.reward_hack.mutation_pass_rate if t.reward_hack else 1.0

            is_contam = any(cf.is_contaminated for cf in t.contamination_flags)
            contam_methods = ";".join({cf.method.value for cf in t.contamination_flags if cf.is_contaminated})

            t_status = t.test_integrity.status.value if t.test_integrity else "PASS"
            ref_passed = t.test_integrity.reference_solver_passed if t.test_integrity else None
            triv_perm = t.test_integrity.trivially_permissive if t.test_integrity else False

            writer.writerow([
                report.benchmark_id,
                report.agent_id,
                report.harness_name,
                t.task_id,
                t.agent_passed,
                t.duration_seconds,
                len(t.violations),
                viol_types,
                hack_score,
                tamper_count,
                mut_pass_rate,
                is_contam,
                contam_methods,
                t_status,
                ref_passed if ref_passed is not None else "",
                triv_perm,
            ])

        return output.getvalue()
