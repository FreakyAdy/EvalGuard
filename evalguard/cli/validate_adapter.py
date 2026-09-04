"""CLI command for validating harness adapter compliance."""

from __future__ import annotations

import importlib
import sys
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from evalguard.adapters.base import HarnessAdapter
from evalguard.adapters.verifier import AdapterVerifier

console = Console()


@click.group(name="adapter")
def adapter_group() -> None:
    """Validate and test custom harness adapter implementations."""
    pass


@adapter_group.command(name="validate")
@click.argument("adapter_target")
def validate_adapter(adapter_target: str) -> None:
    """Validate that a custom HarnessAdapter complies with EvalGuard contracts.

    ADAPTER_TARGET format: 'module.submodule:ClassName' or 'module.submodule:factory_func'
    """
    console.print(f"[bold cyan]Validating harness adapter:[/bold cyan] {adapter_target}")

    if ":" not in adapter_target:
        console.print("[bold red]Invalid target format. Use 'module.path:ClassName'[/bold red]")
        sys.exit(1)

    mod_name, attr_name = adapter_target.split(":", 1)

    try:
        mod = importlib.import_module(mod_name)
        obj = getattr(mod, attr_name)

        if isinstance(obj, type) and issubclass(obj, HarnessAdapter):
            adapter_cls: Any = obj
            adapter = adapter_cls()
        elif callable(obj):
            adapter = obj()
        elif isinstance(obj, HarnessAdapter):
            adapter = obj
        else:
            console.print(
                f"[bold red]Target '{adapter_target}' is not an instance or subclass of HarnessAdapter[/bold red]"
            )
            sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]Failed to load adapter target '{adapter_target}':[/bold red] {e}")
        sys.exit(1)

    verifier = AdapterVerifier(adapter)
    report = verifier.verify_all()

    table = Table(title=f"Adapter Verification: {adapter.name}", border_style="dim")
    table.add_column("Contract Check", style="cyan")
    table.add_column("Result", justify="center")
    table.add_column("Message")

    for c in report.checks:
        res_str = "[green]PASS[/green]" if c.passed else "[bold red]FAIL[/bold red]"
        table.add_row(c.check_name, res_str, c.message)

    console.print(table)

    if report.all_passed:
        console.print(
            f"\n[bold green]SUCCESS: Adapter '{adapter.name}' is fully compliant with EvalGuard v1.0 specifications![/bold green]"
        )
        sys.exit(0)
    else:
        console.print(
            f"\n[bold red]FAILURE: Adapter '{adapter.name}' failed one or more contract checks.[/bold red]"
        )
        sys.exit(1)
