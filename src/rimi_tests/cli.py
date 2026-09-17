"""`rimi` — the command line.

Only `lint` runs today (step T1). The other commands are declared so that the shape
of the tool is visible, and each says which step brings it. None of them calls a model.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__, checks, convention, loader

console = Console()
PLANNED = 2  # exit code for a command that exists but is not implemented yet


def _planned(command: str, step: str) -> None:
    console.print(f"[yellow]`rimi {command}` arrives with step {step}.[/yellow] "
                  "See docs/ and the specification for what it will do.")
    sys.exit(PLANNED)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="rimi")
def main() -> None:
    """Run the test cases of the rimi. convention against several models."""


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path), default="cases")
@click.option("--strict-variants", is_flag=True,
              help=f"Treat fewer than {loader.CAMPAIGN_MIN_VARIANTS} variants as an error (campaign rules).")
@click.option("--quiet", is_flag=True, help="Only print problems.")
def lint(path: Path, strict_variants: bool, quiet: bool) -> None:
    """Validate test cases: schema, rule, checks, tools, variants."""
    result = loader.load(path, strict_variants=strict_variants)

    for problem in result.problems:
        colour = "red" if problem.severity == "error" else "yellow"
        console.print(f"[{colour}]{problem.severity}[/{colour}] {problem}")

    if not quiet and result.cases:
        table = Table(title=f"{len(result.cases)} case(s) in {path}", title_justify="left",
                      header_style="bold")
        table.add_column("rule")
        table.add_column("case")
        table.add_column("lang")
        table.add_column("variants", justify="right")
        table.add_column("runs", justify="right")
        table.add_column("checks")
        table.add_column("case_sha256")
        for case in result.cases:
            names = [c["check"] for c in case.expected_checks]
            table.add_row(case.rule, case.id, case.language, str(len(case.variants)), str(case.runs),
                          ", ".join(names), case.case_sha256[:12] + "…")
        console.print(table)

    if result.cases and not quiet:
        console.print(f"set fingerprint: [bold]{result.fingerprint()[:16]}…[/bold]")

    errors, warnings = len(result.errors), len(result.warnings)
    if errors:
        console.print(f"[red]{errors} error(s)[/red], {warnings} warning(s)")
        sys.exit(1)
    console.print(f"[green]ok[/green] — {len(result.cases)} case(s), {warnings} warning(s)")


@main.command(name="checks")
def list_checks() -> None:
    """List the available checks, built-in and contributed."""
    table = Table(title="checks", title_justify="left", header_style="bold")
    table.add_column("name")
    table.add_column("typed")
    table.add_column("parameters")
    table.add_column("what it verifies")
    for name, spec in sorted(checks.registry().items()):
        parameters = ", ".join(list(spec.required) + [f"[{o}]" for o in spec.optional]) or "—"
        table.add_row(name, "yes" if spec.typed else "no", parameters, spec.summary)
    console.print(table)


@main.group(name="convention")
def convention_group() -> None:
    """The convention this runner follows."""


@convention_group.command(name="status")
def convention_status() -> None:
    """Show the pinned convention and where it comes from."""
    versions = convention.available()
    if not versions:
        console.print("[red]no convention projection bundled[/red]")
        sys.exit(1)
    for version in versions:
        index = convention.load(version)
        table = Table(title=f"convention {version}", title_justify="left", header_style="bold")
        table.add_column("part")
        table.add_column("rules", justify="right")
        for part in ("A", "B", "C"):
            table.add_row(part, str(sum(1 for r in index.rules.values() if r.part == part)))
        console.print(table)
        console.print(f"source: {index.source.get('url', '—')}")
        console.print(f"text sha256: {index.text_sha256}")
        console.print("[dim]local projection; replaced by the signed convention.json of the "
                      "convention repository (task R06)[/dim]")


@convention_group.command(name="update")
def convention_update() -> None:
    """Pin another version of the convention (rimi.lock)."""
    _planned("convention update", "T2")


@convention_group.command(name="diff")
def convention_diff() -> None:
    """Show what changed between two versions, and which cases to review."""
    _planned("convention diff", "T2")


@main.command()
@click.option("--profile", default="dev", show_default=True)
def estimate(profile: str) -> None:
    """Cost and number of calls, before paying anything."""
    _planned("estimate", "T2")


@main.command()
@click.option("--profile", default="dev", show_default=True)
@click.option("--out", type=click.Path(path_type=Path), default="runs")
@click.option("--resume", is_flag=True)
@click.option("--no-cache", is_flag=True)
def run(profile: str, out: Path, resume: bool, no_cache: bool) -> None:
    """Run the cases against the models of the profile."""
    _planned("run", "T2")


@main.command()
@click.argument("run_dir", type=click.Path(path_type=Path))
def report(run_dir: Path) -> None:
    """Turn a run into report.md, report.json and summary.csv."""
    _planned("report", "T3")


@main.command()
@click.option("--level", type=click.Choice(["A", "AA", "AAA"]), required=True)
@click.option("--report", "report_path", type=click.Path(path_type=Path), required=True)
def conform(level: str, report_path: Path) -> None:
    """Verdict and exit code for continuous integration."""
    _planned("conform", "T3")


@main.command()
@click.argument("target", type=click.Path(path_type=Path))
@click.option("--transcripts", is_flag=True, help="Recompute everything from the raw transcripts.")
def verify(target: Path, transcripts: bool) -> None:
    """Verify a proof bundle offline: chain, Merkle root, counts, signature."""
    _planned("verify", "T7")


@main.command(name="judge-audit")
@click.argument("run_dir", type=click.Path(path_type=Path))
@click.option("--sample", default=50, show_default=True)
def judge_audit(run_dir: Path, sample: int) -> None:
    """Measure the agreement between the LLM judge and a human reading."""
    _planned("judge-audit", "T3")


if __name__ == "__main__":  # pragma: no cover
    main()
