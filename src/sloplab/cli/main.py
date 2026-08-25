"""SlopLab command-line interface."""

from __future__ import annotations

from pathlib import Path

import click

from sloplab import __version__


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="sloplab")
def cli() -> None:
    """Adversarial testing framework for vulnerability-report triage evaluators."""


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=str))
def validate(path: str) -> None:
    """Validate a corpus fixture or directory of fixtures."""
    from sloplab.corpus.loader import FixtureError, discover_fixtures
    from sloplab.corpus.validation import validate_corpus

    root = Path(path)
    try:
        canonical, derived = discover_fixtures(root)
    except FixtureError as exc:
        raise click.ClickException(str(exc)) from exc

    if not canonical and not derived:
        raise click.ClickException(
            f"no fixtures found under '{path}' (expected */{'manifest.yaml'} or "
            f"*/mutation-manifest.yaml directories)"
        )

    result = validate_corpus(canonical, derived, corpus_root=root)
    click.echo(result.render())
    if not result.ok:
        raise SystemExit(1)


@cli.command()
@click.argument("fixture", type=click.Path(exists=True, path_type=str))
@click.option("--operator", required=True, help="Mutation operator name.")
@click.option("--seed", default=0, show_default=True, type=int, help="Base seed.")
@click.option("--out", type=click.Path(path_type=str), default=None, help="Output directory.")
def mutate(fixture: str, operator: str, seed: int, out: str | None) -> None:
    """Apply one mutation operator to a fixture."""
    import random
    from pathlib import Path as _Path

    from sloplab.corpus.loader import FixtureError, load_canonical_fixture
    from sloplab.mutations.base import derive_seed, get_operator

    fixture_path = _Path(fixture)
    try:
        loaded = load_canonical_fixture(
            fixture_path,
            fixture_path.parent.parent if fixture_path.name != "canonical" else fixture_path.parent,
        )
    except FixtureError:
        # Allow pointing directly at the report.md file too.
        parent_dir = fixture_path.parent
        try:
            loaded = load_canonical_fixture(parent_dir, parent_dir.parent.parent)
        except FixtureError as exc:
            raise click.ClickException(str(exc)) from exc

    op = get_operator(operator)
    mutation_seed = derive_seed(seed, loaded.fixture_id, operator, 0)
    mutated_text, params = op.apply(loaded.report, random.Random(mutation_seed))

    if out:
        out_dir = _Path(out)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.md").write_text(mutated_text, encoding="utf-8")
        click.echo(f"wrote {out_dir / 'report.md'}")
    else:
        click.echo(mutated_text)
    click.echo(f"# operator: {operator}", err=True)
    click.echo(f"# seed: {mutation_seed}", err=True)
    click.echo(f"# parameters: {params}", err=True)


@cli.command("materialize")
@click.argument("suite", type=click.Path(exists=True, path_type=str))
@click.option("--out", required=True, type=click.Path(path_type=str), help="Output directory.")
def materialize(suite: str, out: str) -> None:
    """Materialize a benchmark suite from canonical fixtures."""
    from pathlib import Path as _Path

    from sloplab.corpus.loader import FixtureError, discover_fixtures
    from sloplab.mutations.materialize import load_suite_config, materialize_suite

    config = load_suite_config(_Path(suite))
    corpus_root = _Path(config.corpus_root)
    try:
        canonical, _derived = discover_fixtures(corpus_root)
    except FixtureError as exc:
        raise click.ClickException(str(exc)) from exc
    if not canonical:
        raise click.ClickException(f"no canonical fixtures found under '{config.corpus_root}'")

    result = materialize_suite(config, canonical, _Path(out))
    click.echo(result.summary())
    if result.safety_violations:
        raise SystemExit(1)


@cli.command()
@click.argument("cases", type=click.Path(exists=True, path_type=str))
@click.option("--evaluator", "evaluators", multiple=True, required=True)
@click.option("--out", type=click.Path(path_type=str), default=None)
def evaluate(cases: str, evaluators: tuple[str, ...], out: str | None) -> None:
    """Run evaluators over a case directory or JSONL file."""
    click.echo(f"evaluate: not implemented yet (cases={cases})")


@cli.command()
@click.argument("suite", type=click.Path(exists=True, path_type=str))
@click.option("--evaluator", "evaluators", multiple=True, required=True)
@click.option("--out", type=click.Path(path_type=str), required=True)
def benchmark(suite: str, evaluators: tuple[str, ...], out: str) -> None:
    """Materialize and evaluate a full suite, then score it."""
    click.echo(f"benchmark: not implemented yet (suite={suite})")


@cli.command()
@click.argument("results", nargs=-1, required=True, type=click.Path(exists=True, path_type=str))
def compare(results: tuple[str, ...]) -> None:
    """Compare metric summaries from two or more result files."""
    click.echo("compare: not implemented yet")


@cli.command()
@click.argument("results", type=click.Path(exists=True, path_type=str))
@click.option("--format", "fmt", type=click.Choice(["markdown"]), default="markdown")
def report(results: str, fmt: str) -> None:
    """Render a human-readable report from result files."""
    click.echo(f"report: not implemented yet (results={results}, format={fmt})")


def main() -> None:  # pragma: no cover - console entry point
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()
