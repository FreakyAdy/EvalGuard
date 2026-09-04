"""CLI subcommands for running hermetic audits and sandbox sessions."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from evalguard.adapters.subprocess_adapter import GenericSubprocessAdapter
from evalguard.report.schema import TaskAuditRecord
from evalguard.sandbox.profiles import SandboxProfile

console = Console()


@click.group(name="audit")
def audit_group() -> None:
    """Run benchmark task audits and boundary enforcement."""
    pass


@audit_group.command(name="run")
@click.option("--task-id", "-t", required=True, help="Task identifier")
@click.option("--profile", "-p", type=click.Path(exists=True), help="Path to SandboxProfile YAML")
@click.option("--command", "-c", required=True, help="Agent shell command to execute")
@click.option("--backend", "-b", default="auto", help="Isolation backend: auto, docker, podman, host, gvisor")
@click.option("--output", "-o", type=click.Path(), help="Output path for audit record JSON")
def run_audit(
    task_id: str,
    profile: str | None,
    command: str,
    backend: str,
    output: str | None,
) -> None:
    """Execute an agent command inside an EvalGuard hermetic sandbox."""
    sb_profile = SandboxProfile.from_yaml(profile) if profile else SandboxProfile(name=f"audit-{task_id}")

    console.print(f"[bold cyan]Running task audit:[/bold cyan] {task_id} (backend={backend})")

    adapter = GenericSubprocessAdapter(
        name="cli-audit-adapter",
        workspace_base_dir=sb_profile.task_workspace_root,
    )

    try:
        audit_record: TaskAuditRecord = adapter.run_task_with_audit(
            agent=command,
            task_id=task_id,
            profile=sb_profile,
            sandbox_backend=backend,
        )

        console.print(f"Task outcome: [{'green' if audit_record.agent_passed else 'red'}]{'PASS' if audit_record.agent_passed else 'FAIL'}[/]")
        console.print(f"Duration: {audit_record.duration_seconds}s")
        console.print(f"Boundary violations detected: {len(audit_record.violations)}")

        for v in audit_record.violations:
            console.print(f"  - [{v.severity.upper()}] {v.violation_type.value}: {v.detail}")

        if output:
            out_path = Path(output).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(audit_record.model_dump_json(indent=2), encoding="utf-8")
            console.print(f"[green]Audit record saved to: {out_path}[/green]")

    except Exception as e:
        console.print(f"[bold red]Audit failed:[/bold red] {e}")
        sys.exit(1)
