"""`rimi` — the command line.

`lint`, `checks` and `convention status` need nothing but the files. `estimate` and
`run` are the engine (step T2): they read models.yaml, call models through LiteLLM
with your keys, and write a run directory whose proof bundle can be checked later.
The report, the judge and `rimi verify` arrive with the following steps.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.table import Table

from . import __version__, checks, convention, loader, providers, runner, stats
from . import report as report_module

console = Console()
PLANNED = 2  # exit code for a command that exists but is not implemented yet
PROFILES_FILE = "profiles.yaml"


def _planned(command: str, step: str) -> None:
    console.print(f"[yellow]`rimi {command}` arrives with step {step}.[/yellow] "
                  "See docs/ and the specification for what it will do.")
    sys.exit(PLANNED)


def _fail(message: str, code: int = 1) -> None:
    console.print(f"[red]{message}[/red]")
    sys.exit(code)


def load_profile(name: str, path: str | Path = PROFILES_FILE) -> dict:
    """Read one profile from profiles.yaml, with the defaults of the specification."""
    defaults = {
        "dev": {"models": 1, "variants": 3, "runs": 1, "declarable": False},
        "campaign": {"models": 5, "providers": 3, "variants": 10, "runs": 5, "declarable": True},
    }
    path = Path(path)
    profiles = {}
    if path.exists():
        profiles = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("profiles", {})
    profile = profiles.get(name) or defaults.get(name)
    if profile is None:
        _fail(f"unknown profile {name!r}; known: {', '.join(sorted(set(profiles) | set(defaults)))}")
    return {**defaults.get(name, {}), **profile, "name": name}


def _cases_or_exit(path: Path, strict: bool = False) -> loader.LoadResult:
    result = loader.load(path, strict_variants=strict)
    if not result.ok:
        for problem in result.errors:
            console.print(f"[red]error[/red] {problem}")
        _fail(f"{len(result.errors)} invalid case(s): fix them before running")
    if not result.cases:
        _fail(f"no case found in {path}")
    return result


def _models_or_exit(models_file: Path, names: tuple[str, ...], limit: int | None,
                    require_key: bool) -> list[providers.ModelSpec]:
    try:
        declared = providers.load_models(models_file)
        return providers.select(declared, list(names) or None, limit, require_key=require_key)
    except providers.ProviderError as exc:
        _fail(str(exc))
        return []  # unreachable, keeps type checkers happy


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
        _fail("no convention projection bundled")
    lock = convention.read_lock()
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
    console.print(f"pinned: [bold]{lock['convention_version']}[/bold]" if lock
                  else "[dim]not pinned yet: the first run writes rimi.lock[/dim]")
    console.print("[dim]local projection; replaced by the signed convention.json of the "
                  "convention repository (task R06)[/dim]")


@convention_group.command(name="update")
@click.option("--version", "version", required=True, help="Version to pin, e.g. 0.3.0.")
def convention_update(version: str) -> None:
    """Pin another version of the convention (rimi.lock). Always an explicit decision."""
    try:
        lock = convention.write_lock(version)
    except convention.ConventionNotAvailableError as exc:
        _fail(str(exc))
    console.print(f"[green]pinned[/green] convention {lock['convention_version']} in {convention.LOCK_FILE}")


@convention_group.command(name="diff")
def convention_diff() -> None:
    """Show what changed between two versions, and which cases to review."""
    _planned("convention diff", "T3")


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path), default="cases")
@click.option("--profile", default="dev", show_default=True)
@click.option("--models-file", type=click.Path(path_type=Path), default=providers.DEFAULT_MODELS_FILE)
@click.option("--model", "model_names", multiple=True, help="Run these models instead of the first ones.")
def estimate(path: Path, profile: str, models_file: Path, model_names: tuple[str, ...]) -> None:
    """Cost and number of calls, before paying anything."""
    settings = load_profile(profile)
    result = _cases_or_exit(path)
    models = _models_or_exit(models_file, model_names, settings.get("models"), require_key=False)
    # A campaign runs the second arm too: an estimate that leaves it out is half the bill.
    plan = runner.build_plan(result.cases, models, variants=settings.get("variants"),
                             runs=settings.get("runs"),
                             remedy_arm=bool(settings.get("declarable")))

    table = Table(title=f"estimate · profile {profile}", title_justify="left", header_style="bold")
    table.add_column("model")
    table.add_column("calls", justify="right")
    table.add_column("prompt tokens", justify="right")
    table.add_column("cost (USD)", justify="right")
    total_cost, unknown = 0.0, False
    for model in models:
        calls = [e for e in plan if e.model.name == model.name]
        tokens = 0
        for execution in calls:
            counted = providers.count_tokens(model, runner.build_messages(execution.case, execution.variant))
            tokens += counted if counted is not None else 0
        output_guess = int(model.params.get("max_tokens", 512) or 512) // 2
        cost = providers.price(model, tokens, output_guess * len(calls))
        if cost is None:
            unknown = True
        else:
            total_cost += cost
        table.add_row(model.name, str(len(calls)), f"{tokens:,}",
                      "—" if cost is None else f"{cost:.4f}")
    console.print(table)
    console.print(f"total: [bold]{len(plan)}[/bold] call(s), "
                  f"about [bold]{total_cost:.4f} USD[/bold]"
                  + (" (some prices unknown to LiteLLM)" if unknown else ""))
    console.print("[dim]output tokens are a guess: half of max_tokens per call[/dim]")


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path), default="cases")
@click.option("--profile", default="dev", show_default=True)
@click.option("--out", type=click.Path(path_type=Path), default="runs", show_default=True)
@click.option("--models-file", type=click.Path(path_type=Path), default=providers.DEFAULT_MODELS_FILE)
@click.option("--model", "model_names", multiple=True, help="Run these models instead of the first ones.")
@click.option("--workers", default=4, show_default=True, help="Bounded parallelism.")
@click.option("--runs", type=int, default=None,
              help="Runs per variant, overriding the profile. A verdict needs "
                   f"{stats.required_trials()} trials to establish 95% from a perfect score.")
@click.option("--resume", is_flag=True, help="Skip the calls already in the chained log.")
@click.option("--no-cache", is_flag=True, help="Force real calls.")
def run(path: Path, profile: str, out: Path, models_file: Path, model_names: tuple[str, ...],
        workers: int, runs: int | None, resume: bool, no_cache: bool) -> None:
    """Run the cases against the models of the profile."""
    from .cache import Cache

    settings = load_profile(profile)
    result = _cases_or_exit(path, strict=bool(settings.get("declarable")))
    try:
        lock = convention.check_versions({c.convention_version for c in result.cases})
    except convention.VersionMismatchError as exc:
        _fail(str(exc))
    models = _models_or_exit(models_file, model_names, settings.get("models"), require_key=True)
    # A remedy is Draft until a campaign has measured it, so the second arm runs in a
    # campaign only: the case is run without the clause, then with it.
    remedy_arm = bool(settings.get("declarable"))
    plan = runner.build_plan(result.cases, models, variants=settings.get("variants"),
                             runs=runs or settings.get("runs"), remedy_arm=remedy_arm)
    trials = (min(settings.get("variants") or 0, 10) or 10) * (runs or settings.get("runs") or 1)
    with_remedy = sum(1 for c in result.cases if c.data.get("remedy"))

    console.print(f"profile [bold]{profile}[/bold] · {len(result.cases)} case(s) · "
                  f"{len(models)} model(s) · [bold]{len(plan)}[/bold] call(s)")
    if with_remedy:
        console.print(f"{with_remedy} case(s) carry a remedy clause — "
                      + (f"second arm included ({len(plan)} calls in total)" if remedy_arm
                         else "second arm skipped: it only runs in a campaign"))
    if not settings.get("declarable"):
        console.print("[yellow]exploratory run: this profile is not declarable[/yellow]")
    if settings.get("declarable") and trials < stats.required_trials():
        console.print(f"[yellow]{trials} trials per obligation: a perfect score would still be "
                      f"inconclusive — {stats.required_trials()} are needed to establish "
                      f"{stats.MUST_THRESHOLD:.0%} (use --runs)[/yellow]")

    directory = runner.run_directory(out, unique=True, resume=resume)
    paths = runner.bundle_paths(directory)
    paths["bundle"].mkdir(parents=True, exist_ok=True)
    manifest = {
        "profile": profile,
        "convention": lock,
        "cases": [c.identity() for c in result.cases],
        "cases_fingerprint": result.fingerprint(),
        "models": [{"name": m.name, "litellm_id": m.litellm_id, "provider": m.provider,
                    "params": m.params} for m in models],
        "expected_executions": len(plan),
        "declarable": bool(settings.get("declarable")),
        "preregistered": False,  # pre-registration arrives with step T8
    }
    paths["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = runner.execute(plan, cache=Cache(enabled=not no_cache),
                             workers=workers, resume=resume, directory=directory)

    table = Table(title=f"run · {directory}", title_justify="left", header_style="bold")
    table.add_column("case")
    table.add_column("model")
    table.add_column("passed", justify="right")
    for (case_name, model_name), (passed, total) in sorted(summary.by_case_and_model().items()):
        table.add_row(case_name, model_name, f"{passed}/{total}")
    console.print(table)

    failures = [r for r in summary.results if not r["passed"]]
    for failure in failures[:5]:
        reasons = ", ".join(f"{c['check']}: {c['detail']}" for c in failure["checks"] if c["ok"] is False)
        if failure.get("answered_with_tool_call"):
            reasons += " (the model answered with a tool call, not with text)"
        console.print(f"[red]fail[/red] {failure['case']} @ {failure['model']} "
                      f"(variant {failure['variant_index']}) — {reasons}")
        console.print(f"       [dim]{runner.failure_excerpt(failure['response'])}[/dim]")
    if len(failures) > 5:
        console.print(f"[dim]… and {len(failures) - 5} more failure(s)[/dim]")

    for error in summary.errors[:5]:
        console.print(f"[red]error[/red] {error}")

    console.print(f"expected {summary.expected} call(s), realised {summary.realised}"
                  + (f", skipped {summary.skipped}" if summary.skipped else "")
                  + f" · cache {summary.cache_stats}")
    billed = summary.cost(billed_only=True)
    console.print(f"pass rate: [bold]{summary.pass_rate():.0%}[/bold] · "
                  f"cost: [bold]{billed:.4f} USD[/bold] billed"
                  + (f" ({summary.cost():.4f} USD without the cache)" if billed < summary.cost() else ""))
    console.print(f"proof bundle: {paths['bundle']} (chain.jsonl, manifest.json, raw/)")
    console.print("[dim]report, thresholds and `rimi conform` arrive with step T3[/dim]")
    if summary.errors:
        sys.exit(1)


@main.command()
@click.argument("run_dir", type=click.Path(exists=True, path_type=Path))
@click.option("--cases", "cases_path", type=click.Path(exists=True, path_type=Path), default="cases",
              help="Where the cases live, to quote the tool results a finding rests on.")
def report(run_dir: Path, cases_path: Path) -> None:
    """Turn a run into report.md, report.json and summary.csv."""
    loaded = loader.load(cases_path)
    cases = {f"{c.rule}/{c.id}": c.data for c in loaded.cases}
    built = report_module.build(run_dir, cases)
    paths = report_module.write(built)

    table = Table(title=f"verdicts · {run_dir}", title_justify="left", header_style="bold")
    table.add_column("case")
    table.add_column("model")
    table.add_column("arm")
    table.add_column("obligation")
    table.add_column("result")
    for assessment in built.assessments:
        colour = {"pass": "green", "fail": "red"}.get(assessment["verdict"], "yellow")
        table.add_row(assessment["case"], assessment["model"], assessment["arm"],
                      assessment["obligation"][:46],
                      f"[{colour}]{assessment['verdict']}[/{colour}] {assessment['sentence']}")
    console.print(table)
    console.print(f"{len(built.findings)} finding(s), "
                  f"{sum(1 for f in built.findings if not f.complete)} incomplete · "
                  f"{len(built.no_validated_remedy)} without a validated remedy · "
                  f"{len(built.not_auditable)} not auditable")
    if built.counts.get("gap"):
        console.print(f"[red]gap of {built.counts['gap']} execution(s) between expected and realised[/red]")
    console.print(f"written: {paths['md']}, {paths['json']}, {paths['csv']}")


@main.command()
@click.option("--level", type=click.Choice(["A", "AA", "AAA"]), required=True)
@click.option("--report", "report_path", type=click.Path(exists=True, path_type=Path), required=True,
              help="report.json produced by `rimi report`.")
def conform(level: str, report_path: Path) -> None:
    """Verdict and exit code for continuous integration."""
    payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
    built = report_module.Report(run_dir=Path(payload.get("run", ".")))
    built.manifest = {"convention": payload.get("convention", {}), "profile": payload.get("profile"),
                      "declarable": payload.get("profile") == "campaign",
                      "models": payload.get("models", [])}
    built.assessments = payload.get("assessments", [])
    version = payload.get("convention", {}).get("convention_version") or "0.3.0"
    outcome = report_module.conformance(built, level, convention.load(version))

    console.print(f"level [bold]{level}[/bold]: [bold]{outcome['verdict']}[/bold]")
    if outcome["rules_not_in_the_convention"]:
        console.print("[yellow]rules measured but not in the convention — a level cannot rest on them: "
                      + ", ".join(outcome["rules_not_in_the_convention"]) + "[/yellow]")
    if outcome["rules_not_accepted_yet"]:
        console.print("[yellow]rules still Draft or Proposed: a level cannot be claimed on them — "
                      + ", ".join(outcome["rules_not_accepted_yet"]) + "[/yellow]")
    for failed in outcome["failed_obligations"]:
        console.print(f"[red]fail[/red] {failed}")
    for pending in outcome["inconclusive_obligations"]:
        console.print(f"[yellow]inconclusive[/yellow] {pending} — more runs needed")
    if not outcome["declarable_profile"]:
        console.print("[yellow]this run used a profile that is not declarable[/yellow]")
    sys.exit(0 if outcome["verdict"] == "claimable" else 1)


@main.command()
@click.option("--successes", type=int, required=True, help="Runs that passed.")
@click.option("--trials", type=int, required=True, help="Runs made.")
@click.option("--threshold", type=float, default=stats.MUST_THRESHOLD, show_default=True,
              help="0.95 for a MUST, 0.80 for a SHOULD.")
@click.option("--alpha", type=float, default=stats.DEFAULT_ALPHA, show_default=True)
def verdict(successes: int, trials: int, threshold: float, alpha: float) -> None:
    """What a score establishes: pass, fail, or not enough runs yet."""
    try:
        assessment = stats.assess(successes, trials, threshold, alpha)
    except ValueError as exc:
        _fail(str(exc))
    colour = {"pass": "green", "fail": "red"}.get(assessment.verdict.value, "yellow")
    console.print(f"[{colour}]{assessment.verdict.value.upper()}[/{colour}] — {assessment.sentence()}")
    console.print(f"Clopper-Pearson, one-sided, alpha={alpha}: "
                  f"[{assessment.lower:.4f}, {assessment.upper:.4f}]")
    console.print(f"a perfect score establishes {threshold:.0%} in "
                  f"[bold]{stats.required_trials(threshold, alpha)}[/bold] runs one-sided "
                  f"({stats.required_trials_two_sided(threshold, alpha)} two-sided)")


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
