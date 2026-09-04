"""Rich terminal summary viewer for EvalGuard reports."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from evalguard.report.schema import EvalGuardReport, TaskIntegrityStatus


class ReportViewer:
    """Renders comprehensive, beautifully styled terminal views of EvalGuard reports."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def view(self, report: EvalGuardReport) -> None:
        """Render the complete report to stdout."""
        # 1. Header Banner
        header_text = Text()
        header_text.append(f"Report ID: {report.report_id}\n", style="bold cyan")
        header_text.append(
            f"Benchmark: {report.benchmark_id}  |  Agent: {report.agent_id}  |  Harness: {report.harness_name}\n"
        )
        header_text.append(
            f"Timestamp: {report.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}  |  Schema: v{report.schema_version}"
        )

        self.console.print(
            Panel(
                header_text,
                title="[bold green][EvalGuard] Benchmark Integrity Audit[/bold green]",
                border_style="green",
            )
        )

        # 2. Key Metrics Summary Table
        s = report.summary
        metric_table = Table(title="Audit Executive Summary", border_style="dim")
        metric_table.add_column("Metric", style="bold")
        metric_table.add_column("Value", justify="right")
        metric_table.add_column("Status / Implication")

        metric_table.add_row("Total Tasks Audited", str(s.total_tasks), "100%")
        metric_table.add_row(
            "Agent Passing Tasks (Nominal)",
            str(s.agent_passed_tasks),
            f"{(s.agent_passed_tasks / s.total_tasks * 100) if s.total_tasks else 0:.1f}% raw pass rate",
        )

        clean_style = "green" if s.clean_passed_tasks > 0 else "red"
        metric_table.add_row(
            "Clean Passing Tasks (Verified)",
            f"[{clean_style}]{s.clean_passed_tasks}[/{clean_style}]",
            "No violations, hacking, or contamination",
        )

        viol_style = "red" if s.tasks_with_violations > 0 else "green"
        metric_table.add_row(
            "Boundary Violations",
            f"[{viol_style}]{s.boundary_violations_total} (in {s.tasks_with_violations} tasks)[/{viol_style}]",
            "Hermetic isolation compromised",
        )

        hack_style = "red" if s.tasks_with_reward_hack > 0 else "green"
        metric_table.add_row(
            "Reward Hacking Flags",
            f"[{hack_style}]{s.tasks_with_reward_hack}[/{hack_style}]",
            "Test tampering or mutated probe failures",
        )

        contam_style = "yellow" if s.tasks_with_contamination > 0 else "green"
        metric_table.add_row(
            "Contaminated Tasks",
            f"[{contam_style}]{s.tasks_with_contamination}[/{contam_style}]",
            "Lexical, semantic, or timeline exposure",
        )

        test_style = "magenta" if s.suspect_or_invalid_tests > 0 else "green"
        metric_table.add_row(
            "Flawed / Suspect Tests",
            f"[{test_style}]{s.suspect_or_invalid_tests}[/{test_style}]",
            "Reference solution failed or trivial pass",
        )

        self.console.print(metric_table)
        self.console.print()

        # 3. Per-Task Breakdown Table
        task_table = Table(title="Per-Task Integrity Details", border_style="dim", show_lines=True)
        task_table.add_column("Task ID", style="cyan")
        task_table.add_column("Agent Result", justify="center")
        task_table.add_column("Violations", justify="center")
        task_table.add_column("Hack Score", justify="center")
        task_table.add_column("Contam.", justify="center")
        task_table.add_column("Test Case", justify="center")

        for t in report.tasks:
            agent_str = "[green]PASS[/green]" if t.agent_passed else "[red]FAIL[/red]"

            if t.violations:
                viol_types = ",".join({v.violation_type.value for v in t.violations})
                viol_str = f"[bold red]VIOLATION: {len(t.violations)} ({viol_types})[/bold red]"
            else:
                viol_str = "[green]hermetic[/green]"

            hack_score = t.reward_hack.confidence_score if t.reward_hack else 0.0
            if hack_score >= 0.7:
                hack_str = f"[bold red]{hack_score:.2f}[/bold red]"
            elif hack_score >= 0.3:
                hack_str = f"[yellow]{hack_score:.2f}[/yellow]"
            else:
                hack_str = f"[green]{hack_score:.2f}[/green]"

            has_contam = any(cf.is_contaminated for cf in t.contamination_flags)
            contam_str = "[yellow]FLAGGED[/yellow]" if has_contam else "[dim]clean[/dim]"

            t_status = t.test_integrity.status if t.test_integrity else TaskIntegrityStatus.PASS
            if t_status == TaskIntegrityStatus.INVALID:
                test_str = "[bold red]INVALID[/bold red]"
            elif t_status == TaskIntegrityStatus.SUSPECT:
                test_str = "[bold yellow]SUSPECT[/bold yellow]"
            else:
                test_str = "[green]VALID[/green]"

            task_table.add_row(t.task_id, agent_str, viol_str, hack_str, contam_str, test_str)

        self.console.print(task_table)
