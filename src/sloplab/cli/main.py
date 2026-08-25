"""SlopLab command-line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
    corpus_root = _resolve_corpus_root(config.corpus_root, _Path(suite))
    try:
        canonical, _derived = discover_fixtures(corpus_root)
    except FixtureError as exc:
        raise click.ClickException(str(exc)) from exc
    if not canonical:
        raise click.ClickException(
            f"no canonical fixtures discovered under '{corpus_root}' - "
            f"check 'corpus_root' in {suite}"
        )

    result = materialize_suite(config, canonical, _Path(out), corpus_root_resolved=corpus_root)
    click.echo(result.summary())
    if result.safety_violations:
        raise SystemExit(1)


def _resolve_suite_index(cases: str) -> tuple[Path, Path, Path]:
    """Return (index_path, corpus_root, materialized_root) from a cases argument.

    Accepts a suite-index.jsonl file or any directory containing one. The corpus
    root is read from the index header when present (written by ``materialize``),
    otherwise the current working directory is assumed.
    """
    from sloplab.mutations.materialize import SUITE_INDEX_NAME
    from sloplab.scoring.harness import read_suite_index

    path = Path(cases)
    if path.is_file() and path.name == SUITE_INDEX_NAME:
        index_path = path
        materialized_root = path.parent
    elif path.is_dir():
        candidate = path / SUITE_INDEX_NAME
        if not candidate.is_file():
            raise click.ClickException(f"no {SUITE_INDEX_NAME} found under '{cases}'")
        index_path = candidate
        materialized_root = path
    else:
        raise click.ClickException(
            f"'{cases}' must be a {SUITE_INDEX_NAME} file or a directory containing one"
        )

    header, _entries = read_suite_index(index_path)
    corpus_root_str = (header or {}).get("corpus_root")
    if not corpus_root_str:
        return index_path, Path.cwd(), materialized_root
    candidate = Path(corpus_root_str)
    if candidate.is_absolute() and candidate.is_dir():
        return index_path, candidate, materialized_root
    for anchor in [Path.cwd(), *index_path.absolute().parents]:
        resolved = anchor / candidate
        if resolved.is_dir():
            return index_path, resolved, materialized_root
    raise click.ClickException(
        f"corpus_root '{corpus_root_str}' from suite index does not exist relative to "
        f"the current directory or the index location"
    )


def _run_evaluators_over_suite(
    evaluators: tuple[str, ...],
    index_path: Path,
    corpus_root: Path,
    materialized_root: Path,
    out_dir: Path,
    suite_name: str,
    base_seed: int,
) -> list[Any]:
    import json

    from sloplab.evaluators.base import get_evaluator
    from sloplab.models.run import EvaluatorInfo
    from sloplab.reporting.writers import (
        default_run_metadata,
        write_run_jsonl,
    )
    from sloplab.scoring.harness import build_cases, run_suite
    from sloplab.scoring.metrics import compute_metrics

    cases = build_cases(index_path, corpus_root, materialized_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[Any] = []
    infos: list[EvaluatorInfo] = []
    bundles: list[Any] = []

    for evaluator_name in evaluators:
        evaluator = get_evaluator(evaluator_name)
        run_records = run_suite(evaluator, cases)
        records.extend(run_records)
        infos.append(EvaluatorInfo(name=evaluator.name, version=evaluator.version))
        bundle = compute_metrics(run_records, evaluator.name)
        bundles.append(bundle)

        metrics_path = out_dir / f"metrics-{evaluator_name}.json"
        from sloplab.reporting.writers import metrics_to_dict

        metrics_path.write_text(json.dumps(metrics_to_dict(bundle), indent=2), encoding="utf-8")

    metadata = default_run_metadata(
        suite_name=suite_name,
        base_seed=base_seed,
        evaluators=infos,
        suite_config={"index": str(index_path), "corpus_root": str(corpus_root)},
        suite_hash=_hash_file(index_path),
    )
    write_run_jsonl(out_dir / "run.jsonl", metadata, records)
    return bundles


def _resolve_corpus_root(corpus_root: str, suite_path: Path) -> Path:
    """Resolve a suite's ``corpus_root`` robustly.

    Relative paths are tried against, in order: the current working directory,
    the suite file's directory, and its grandparent (repo-root style layouts).
    Absolute paths pass through unchanged.
    """
    candidate = Path(corpus_root)
    if candidate.is_absolute():
        return candidate
    anchors = [Path.cwd(), *suite_path.absolute().parents]
    for anchor in anchors:
        resolved = anchor / candidate
        if resolved.is_dir():
            return resolved
    raise click.ClickException(
        f"corpus_root '{corpus_root}' does not exist relative to any of {[str(a) for a in anchors]}"
    )


def _hash_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@cli.command()
@click.argument("cases", type=click.Path(exists=True, path_type=str))
@click.option("--evaluator", "evaluators", multiple=True, required=True)
@click.option("--out", type=click.Path(path_type=str), required=True)
def evaluate(cases: str, evaluators: tuple[str, ...], out: str) -> None:
    """Run evaluators over a materialized suite (directory with suite-index.jsonl)."""
    from pathlib import Path as _Path

    from sloplab.reporting.writers import write_markdown_report

    index_path, corpus_root, materialized_root = _resolve_suite_index(cases)
    out_dir = _Path(out)
    bundles = _run_evaluators_over_suite(
        evaluators, index_path, corpus_root, materialized_root, out_dir, "evaluate", 0
    )
    write_markdown_report(out_dir / "report.md", bundles, "SlopLab evaluation results")
    click.echo(f"wrote {out_dir / 'run.jsonl'}, metrics and report.md")


@cli.command()
@click.argument("suite", type=click.Path(exists=True, path_type=str))
@click.option("--evaluator", "evaluators", multiple=True, required=True)
@click.option("--out", type=click.Path(path_type=str), required=True)
@click.option(
    "--materialize/--no-materialize",
    "do_materialize",
    default=True,
    help="Re-materialize the suite before evaluating.",
)
def benchmark(suite: str, evaluators: tuple[str, ...], out: str, do_materialize: bool) -> None:
    """Materialize and evaluate a full suite, then score it."""
    from pathlib import Path as _Path

    from sloplab.corpus.loader import FixtureError, discover_fixtures
    from sloplab.mutations.materialize import SUITE_INDEX_NAME, load_suite_config, materialize_suite
    from sloplab.reporting.writers import write_markdown_report, write_records_csv

    suite_path = _Path(suite)
    config = load_suite_config(suite_path)
    out_dir = _Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if do_materialize:
        corpus_root = _resolve_corpus_root(config.corpus_root, suite_path)
        try:
            canonical, _derived = discover_fixtures(corpus_root)
        except FixtureError as exc:
            raise click.ClickException(str(exc)) from exc
        if not canonical:
            raise click.ClickException(
                f"no canonical fixtures discovered under '{corpus_root}' - "
                f"check 'corpus_root' in {suite}"
            )
        result = materialize_suite(config, canonical, out_dir, corpus_root_resolved=corpus_root)
        click.echo(result.summary())
    else:
        corpus_root = _resolve_corpus_root(config.corpus_root, suite_path)

    index_path = out_dir / SUITE_INDEX_NAME
    bundles = _run_evaluators_over_suite(
        evaluators,
        index_path,
        corpus_root,
        out_dir,
        out_dir,
        config.name,
        config.base_seed,
    )
    _, records = __import__(
        "sloplab.reporting.writers", fromlist=["read_run_jsonl"]
    ).read_run_jsonl(out_dir / "run.jsonl")
    write_records_csv(out_dir / "results.csv", records)
    write_markdown_report(out_dir / "report.md", bundles, f"SlopLab benchmark: {config.name}")
    click.echo(f"benchmark complete; results in {out_dir}")


@cli.command()
@click.argument("results", nargs=-1, required=True, type=click.Path(exists=True, path_type=str))
def compare(results: tuple[str, ...]) -> None:
    """Compare metric summaries from two or more result files."""
    import json
    from pathlib import Path as _Path

    if len(results) < 1:
        raise click.ClickException("compare needs at least one result file or directory")

    summaries: dict[str, dict[str, Any]] = {}
    for result_path in results:
        path = _Path(result_path)
        metrics_dir = path.parent if path.name == "run.jsonl" else path
        metric_files = sorted(metrics_dir.glob("metrics-*.json"))
        for mfile in metric_files:
            data = json.loads(mfile.read_text())
            name = data.get("evaluator_name", mfile.stem)
            summaries[f"{name} ({mfile.parent.name})"] = data

    if not summaries:
        raise click.ClickException(f"no metrics-*.json files found for {results}")

    keys = [
        ("decision_accuracy", "accuracy"),
        ("mutation_detection_rate", "mutation detection"),
        ("false_reassurance_rate", "false reassurance (lower=better)"),
        ("over_rejection_rate", "over-rejection (lower=better)"),
        ("robustness_delta", "robustness delta"),
        ("presentation_susceptibility", "presentation susceptibility (lower=better)"),
        ("calibration_error", "calibration error (lower=better)"),
        ("robustness_score", "aux robustness score"),
    ]
    header = f"{'metric':<38}" + "".join(f"{n[:28]:>30}" for n in summaries)
    click.echo(header)
    click.echo("-" * len(header))
    for key, label in keys:
        row = f"{label:<38}"
        for name in summaries:
            value = summaries[name].get(key)
            row += f"{('n/a' if value is None else format(value, '.3f')):>30}"
        click.echo(row)


@cli.command()
@click.argument("results", type=click.Path(exists=True, path_type=str))
@click.option("--format", "fmt", type=click.Choice(["markdown"]), default="markdown")
@click.option("--out", type=click.Path(path_type=str), default=None)
def report(results: str, fmt: str, out: str | None) -> None:
    """Render a human-readable report from a run.jsonl file."""
    from pathlib import Path as _Path

    _ = fmt
    from sloplab.reporting.writers import read_run_jsonl, write_markdown_report
    from sloplab.scoring.metrics import compute_metrics

    metadata, records = read_run_jsonl(_Path(results))
    if not records:
        raise click.ClickException(f"no case records found in {results}")

    by_evaluator: dict[str, list[Any]] = {}
    for record in records:
        by_evaluator.setdefault(record.evaluator_name, []).append(record)

    bundles = [compute_metrics(recs, name) for name, recs in sorted(by_evaluator.items())]
    rendered = write_markdown_report(
        _Path(out) if out else _Path(results).parent / "report.md",
        bundles,
        f"SlopLab results ({metadata.suite_name if metadata else 'unknown suite'})",
    )
    click.echo(rendered.read_text())


def main() -> None:  # pragma: no cover - console entry point
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()
