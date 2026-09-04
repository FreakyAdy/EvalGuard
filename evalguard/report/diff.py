"""Semantic diffing and comparison between two EvalGuard reports."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from evalguard.report.schema import EvalGuardReport


@dataclass
class TaskDiffEntry:
    """Discrepancy detected for a single task between two audit runs."""

    task_id: str
    pass_status_changed: bool
    status_a: bool
    status_b: bool
    hack_score_delta: float
    violations_count_delta: int
    contamination_status_changed: bool
    notes: list[str] = field(default_factory=list)


@dataclass
class ReportDiffResult:
    """Summary of changes between report A (baseline) and report B (candidate)."""

    benchmark_id: str
    agent_a_id: str
    agent_b_id: str
    total_tasks_compared: int
    flip_pass_to_fail: list[str]
    flip_fail_to_pass: list[str]
    new_violations: list[str]
    new_reward_hacks: list[str]
    new_contaminations: list[str]
    task_diffs: list[TaskDiffEntry]


class ReportDiffer:
    """Computes semantic diffs between two benchmark audit reports."""

    @classmethod
    def diff_files(cls, path_a: str | Path, path_b: str | Path) -> ReportDiffResult:
        """Load two report JSON files and compute the diff."""
        data_a = json.loads(Path(path_a).read_text(encoding="utf-8"))
        data_b = json.loads(Path(path_b).read_text(encoding="utf-8"))
        report_a = EvalGuardReport.model_validate(data_a)
        report_b = EvalGuardReport.model_validate(data_b)
        return cls.diff_reports(report_a, report_b)

    @classmethod
    def diff_reports(cls, a: EvalGuardReport, b: EvalGuardReport) -> ReportDiffResult:
        """Compare two EvalGuardReport instances."""
        tasks_a = {t.task_id: t for t in a.tasks}
        tasks_b = {t.task_id: t for t in b.tasks}
        common_ids = sorted(list(set(tasks_a.keys()) & set(tasks_b.keys())))

        flip_pass_to_fail: list[str] = []
        flip_fail_to_pass: list[str] = []
        new_violations: list[str] = []
        new_reward_hacks: list[str] = []
        new_contaminations: list[str] = []
        task_diffs: list[TaskDiffEntry] = []

        for tid in common_ids:
            ta = tasks_a[tid]
            tb = tasks_b[tid]
            notes: list[str] = []

            # 1. Pass status flips
            pass_changed = (ta.agent_passed != tb.agent_passed)
            if pass_changed:
                if ta.agent_passed and not tb.agent_passed:
                    flip_pass_to_fail.append(tid)
                    notes.append("Regressed: PASS -> FAIL")
                else:
                    flip_fail_to_pass.append(tid)
                    notes.append("Improved: FAIL -> PASS")

            # 2. Boundary violations
            viol_delta = len(tb.violations) - len(ta.violations)
            if len(tb.violations) > len(ta.violations):
                new_violations.append(tid)
                notes.append(f"New boundary violations: +{viol_delta}")

            # 3. Reward hack confidence delta
            ha = ta.reward_hack.confidence_score if ta.reward_hack else 0.0
            hb = tb.reward_hack.confidence_score if tb.reward_hack else 0.0
            hack_delta = round(hb - ha, 3)
            if ha < 0.5 <= hb:
                new_reward_hacks.append(tid)
                notes.append(f"Reward hack flagged in B: {ha:.2f} -> {hb:.2f}")

            # 4. Contamination flags
            ca = any(cf.is_contaminated for cf in ta.contamination_flags)
            cb = any(cf.is_contaminated for cf in tb.contamination_flags)
            contam_changed = (ca != cb)
            if not ca and cb:
                new_contaminations.append(tid)
                notes.append("Newly flagged as contaminated in B")

            if notes or pass_changed or abs(hack_delta) > 0.15:
                task_diffs.append(
                    TaskDiffEntry(
                        task_id=tid,
                        pass_status_changed=pass_changed,
                        status_a=ta.agent_passed,
                        status_b=tb.agent_passed,
                        hack_score_delta=hack_delta,
                        violations_count_delta=viol_delta,
                        contamination_status_changed=contam_changed,
                        notes=notes,
                    )
                )

        return ReportDiffResult(
            benchmark_id=a.benchmark_id,
            agent_a_id=a.agent_id,
            agent_b_id=b.agent_id,
            total_tasks_compared=len(common_ids),
            flip_pass_to_fail=flip_pass_to_fail,
            flip_fail_to_pass=flip_fail_to_pass,
            new_violations=new_violations,
            new_reward_hacks=new_reward_hacks,
            new_contaminations=new_contaminations,
            task_diffs=task_diffs,
        )

    @classmethod
    def render_diff(cls, diff: ReportDiffResult, console: Console | None = None) -> None:
        """Render diff to Rich terminal."""
        con = console or Console()
        title = f"EvalGuard Report Diff: {diff.agent_a_id} vs {diff.agent_b_id} ({diff.benchmark_id})"
        con.print(Panel(f"Compared {diff.total_tasks_compared} shared task(s).", title=title, border_style="blue"))

        table = Table(title="Divergent Tasks", border_style="dim", show_lines=True)
        table.add_column("Task ID", style="cyan")
        table.add_column("Agent A Passed", justify="center")
        table.add_column("Agent B Passed", justify="center")
        table.add_column("Hack Score Δ", justify="right")
        table.add_column("Violations Δ", justify="right")
        table.add_column("Notes")

        for d in diff.task_diffs:
            a_str = "[green]PASS[/green]" if d.status_a else "[red]FAIL[/red]"
            b_str = "[green]PASS[/green]" if d.status_b else "[red]FAIL[/red]"
            h_delta_str = f"{d.hack_score_delta:+.2f}"
            v_delta_str = f"{d.violations_count_delta:+d}"
            table.add_row(d.task_id, a_str, b_str, h_delta_str, v_delta_str, "; ".join(d.notes))

        con.print(table)
