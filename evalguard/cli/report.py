"""CLI commands for inspecting, diffing, and exporting EvalGuard audit reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console

from evalguard.report.diff import ReportDiffer
from evalguard.report.exporters import (
    CsvExporter,
    HtmlExporter,
    MarkdownExporter,
    SarifExporter,
)
from evalguard.report.schema import EvalGuardReport
from evalguard.report.viewer import ReportViewer

console = Console()


@click.group(name="report")
def report_group() -> None:
    """Inspect, compare, and export EvalGuard audit reports."""
    pass


@report_group.command(name="view")
@click.argument("report_file", type=click.Path(exists=True))
def view_report(report_file: str) -> None:
    """Render an audit report in the terminal with styled summary and metrics."""
    try:
        data = json.loads(Path(report_file).read_text(encoding="utf-8"))
        report = EvalGuardReport.model_validate(data)
        ReportViewer(console).view(report)
    except Exception as e:
        console.print(f"[bold red]Failed to load report '{report_file}':[/bold red] {e}")
        sys.exit(1)


@report_group.command(name="diff")
@click.argument("report_a", type=click.Path(exists=True))
@click.argument("report_b", type=click.Path(exists=True))
def diff_reports(report_a: str, report_b: str) -> None:
    """Compare two audit reports side-by-side to highlight regressions or leaks."""
    try:
        diff_res = ReportDiffer.diff_files(report_a, report_b)
        ReportDiffer.render_diff(diff_res, console)
    except Exception as e:
        console.print(f"[bold red]Failed to diff reports:[/bold red] {e}")
        sys.exit(1)


@report_group.command(name="export")
@click.argument("report_file", type=click.Path(exists=True))
@click.option(
    "--format",
    "-f",
    type=click.Choice(["markdown", "html", "csv", "sarif"], case_sensitive=False),
    default="markdown",
    help="Export format",
)
@click.option("--output", "-o", type=click.Path(), required=True, help="Destination file path")
def export_report(report_file: str, format: str, output: str) -> None:
    """Export an audit report to Markdown, HTML, CSV, or SARIF."""
    try:
        data = json.loads(Path(report_file).read_text(encoding="utf-8"))
        report = EvalGuardReport.model_validate(data)

        fmt = format.lower()
        if fmt == "markdown":
            content = MarkdownExporter.export(report)
        elif fmt == "html":
            content = HtmlExporter.export(report)
        elif fmt == "csv":
            content = CsvExporter.export(report)
        elif fmt == "sarif":
            content = SarifExporter.export(report)
        else:
            raise ValueError(f"Unsupported format: {format}")

        dest = Path(output).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        console.print(f"[green]Successfully exported {fmt.upper()} report to: {dest}[/green]")

    except Exception as e:
        console.print(f"[bold red]Export failed:[/bold red] {e}")
        sys.exit(1)
