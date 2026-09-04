"""CLI subcommand for training data contamination auditing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from evalguard.contamination.auditor import ContaminationAuditor

console = Console()


@click.group(name="contamination")
def contamination_group() -> None:
    """Audit training data contamination and disclosure timelines."""
    pass


@contamination_group.command(name="audit")
@click.option(
    "--benchmark",
    "-b",
    required=True,
    help="Benchmark name (e.g. humaneval, swebench-verified, mbpp)",
)
@click.option(
    "--agent-corpus",
    "-c",
    type=click.Path(exists=True),
    required=True,
    help="Path to agent training text or manifest JSON",
)
@click.option("--disclosure-date", "-d", help="Benchmark disclosure date (YYYY-MM-DD)")
@click.option("--cutoff-date", help="Agent pre-training cutoff date (YYYY-MM-DD)")
@click.option("--output", "-o", type=click.Path(), help="Output path for contamination report JSON")
def audit_contamination(
    benchmark: str,
    agent_corpus: str,
    disclosure_date: str | None,
    cutoff_date: str | None,
    output: str | None,
) -> None:
    """Audit an agent training corpus against benchmark index for lexical, semantic, and timeline contamination."""
    console.print(f"[bold cyan]Auditing contamination for benchmark:[/bold cyan] {benchmark}")

    corpus_path = Path(agent_corpus).resolve()
    # Read text or json manifest
    if corpus_path.suffix == ".json":
        try:
            data = json.loads(corpus_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                corpus_text = "\n".join(str(x) for x in data)
            elif isinstance(data, dict):
                corpus_text = "\n".join(f"{k}: {v}" for k, v in data.items())
            else:
                corpus_text = str(data)
        except Exception as e:
            console.print(f"[red]Failed to read JSON corpus: {e}[/red]")
            sys.exit(1)
    else:
        corpus_text = corpus_path.read_text(encoding="utf-8", errors="replace")

    auditor = ContaminationAuditor(benchmark_name=benchmark)
    if disclosure_date:
        auditor.timeline_auditor.disclosure_date = auditor.timeline_auditor.disclosure_date

    # Scan against tasks in index
    all_flags = []
    matched_tasks = 0

    table = Table(title=f"Contamination Audit Findings: {benchmark}", border_style="dim")
    table.add_column("Task / Signal", style="cyan")
    table.add_column("Method", justify="center")
    table.add_column("Contaminated?", justify="center")
    table.add_column("Score", justify="right")
    table.add_column("Details")

    # 1. Timeline check
    timeline_flag = auditor.timeline_auditor.evaluate_agent(cutoff_date)
    all_flags.append(timeline_flag.model_dump())
    tl_status = (
        "[bold red]EXPOSED[/bold red]" if timeline_flag.is_contaminated else "[green]CLEAN[/green]"
    )
    table.add_row(
        "Global Timeline",
        "timeline",
        tl_status,
        f"{timeline_flag.score:.1f}",
        timeline_flag.details,
    )

    # 2. Lexical & Semantic checks across indexed tasks
    for tid, tinfo in auditor.index.tasks.items():
        ref_text = f"{tinfo['prompt']}\n{tinfo['solution']}"
        lex_res = auditor.lexical_detector.compare(corpus_text, ref_text)
        if lex_res.is_contaminated or lex_res.containment_score > 0.15:
            matched_tasks += 1
            sem_score, sem_contam = auditor.semantic_detector.compare(corpus_text, ref_text)
            c_status = (
                "[bold red]FLAGGED[/bold red]"
                if (lex_res.is_contaminated or sem_contam)
                else "[yellow]SUSPECT[/yellow]"
            )
            details = f"Containment: {lex_res.containment_score:.2f}, Semantic Sim: {sem_score:.2f}"
            table.add_row(
                tid, "lexical+semantic", c_status, f"{lex_res.containment_score:.2f}", details
            )
            all_flags.append(
                {
                    "task_id": tid,
                    "lexical_containment": lex_res.containment_score,
                    "semantic_similarity": sem_score,
                    "is_contaminated": (lex_res.is_contaminated or sem_contam),
                }
            )

    console.print(table)
    console.print(
        f"Tasks scanned: {len(auditor.index.tasks)} | Matched with flags: {matched_tasks}"
    )

    if output:
        out_path = Path(output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        report_data = {
            "benchmark": benchmark,
            "agent_corpus": str(corpus_path),
            "disclosure_date": disclosure_date,
            "cutoff_date": cutoff_date,
            "flags": all_flags,
        }
        out_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        console.print(f"[green]Contamination report saved to: {out_path}[/green]")
