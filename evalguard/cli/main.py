"""Main Click CLI root for EvalGuard."""

from __future__ import annotations

import logging

import click

from evalguard.cli.audit import audit_group
from evalguard.cli.contamination import contamination_group
from evalguard.cli.report import report_group
from evalguard.cli.validate_adapter import adapter_group


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version="0.1.0", prog_name="evalguard")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose debug logging")
def cli(verbose: bool) -> None:
    """EvalGuard - Benchmark Integrity Infrastructure for Agent Evaluations.

    Audit sandboxing boundaries, detect reward hacking, analyze contamination,
    and verify test case integrity across SWE-bench, Terminal-Bench, OpenEnv, and custom harnesses.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


cli.add_command(audit_group, name="audit")
cli.add_command(contamination_group, name="contamination")
cli.add_command(report_group, name="report")
cli.add_command(adapter_group, name="adapter")

if __name__ == "__main__":
    cli()
