"""SlopLab command-line interface."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import click

from sloplab import __version__
from sloplab.evaluators.base import Evaluator
from sloplab.experiments.bundle import BundleError, open_result_dir
from sloplab.scoring.metrics import MetricBundle


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="sloplab")
def cli() -> None:
    """Adversarial testing framework for vulnerability-report triage evaluators."""


@cli.command("add-report")
@click.argument("report", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--corpus",
    default="corpus",
    show_default=True,
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option("--ui", is_flag=True, help="Open the optional terminal Report Builder.")
def add_report(report: Path, corpus: Path, ui: bool = False) -> None:
    """Add a synthetic canonical report with a validated, confirmed transaction."""
    if ui:
        from sloplab.corpus.add_report import AddReportError
        from sloplab.tui.launch import run_report_builder

        try:
            run_report_builder(report, corpus)
        except AddReportError as exc:
            raise click.ClickException(str(exc)) from exc
    else:
        from sloplab.cli.add_report import run_add_report

        run_add_report(report, corpus)


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

    from sloplab.safety.policy import validate_content_safety

    violations = validate_content_safety(mutated_text)
    if violations:
        for violation in violations:
            click.echo(f"SAFETY: {violation}", err=True)
        raise click.ClickException(
            f"mutation output for '{operator}' violates the content safety policy; "
            f"no file was written"
        )

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
    evaluators: Sequence[Evaluator | str],
    index_path: Path,
    corpus_root: Path,
    materialized_root: Path,
    out_dir: Path,
    suite_name: str,
    base_seed: int,
) -> list[Any]:
    import json

    from sloplab.evaluators.base import get_evaluator
    from sloplab.models.run import CaseRecord, EvaluatorInfo
    from sloplab.reporting.outcomes import (
        OUTCOMES_HASH_KEY,
        OUTCOMES_NAME,
        safe_error_kind,
        write_failure_outcomes,
    )
    from sloplab.reporting.writers import (
        default_run_metadata,
        write_run_jsonl,
    )
    from sloplab.scoring.harness import CaseOutcome, build_cases, run_suite_with_outcomes
    from sloplab.scoring.metrics import compute_metrics

    cases = build_cases(index_path, corpus_root, materialized_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[CaseRecord] = []
    failures: list[CaseOutcome] = []
    infos: list[EvaluatorInfo] = []
    bundles: list[Any] = []

    for selected in evaluators:
        # Names remain supported for existing internal callers. CLI selection
        # resolves all imports/collisions before any output or evaluation begins.
        evaluator = get_evaluator(selected) if isinstance(selected, str) else selected
        from sloplab.evaluators.external import ExternalEvaluatorError

        try:
            run_records, failed = run_suite_with_outcomes(evaluator, cases)
        except ExternalEvaluatorError as exc:
            raise click.ClickException(str(exc)) from exc
        for outcome in failed:
            assert outcome.failure is not None
            click.echo(
                f"FAILED-EVAL ({safe_error_kind(outcome.failure.error_kind)}): "
                f"{outcome.case_id} by {outcome.evaluator_name} — "
                "isolated, not scored",
                err=True,
            )
        records.extend(run_records)
        failures.extend(failed)
        infos.append(EvaluatorInfo(name=evaluator.name, version=evaluator.version))
        bundle = compute_metrics(run_records, evaluator.name)
        bundles.append(bundle)

        metrics_path = out_dir / _metrics_filename(evaluator.name)
        from sloplab.reporting.writers import metrics_to_dict

        metrics_path.write_text(json.dumps(metrics_to_dict(bundle), indent=2), encoding="utf-8")

    outcomes_hash = write_failure_outcomes(out_dir / OUTCOMES_NAME, failures)
    metadata = default_run_metadata(
        suite_name=suite_name,
        base_seed=base_seed,
        evaluators=infos,
        suite_config={
            "index": str(index_path),
            "corpus_root": str(corpus_root),
            OUTCOMES_HASH_KEY: outcomes_hash,
        },
        suite_hash=_hash_file(index_path),
    )
    write_run_jsonl(out_dir / "run.jsonl", metadata, records)
    return bundles


def _metrics_filename(name: str) -> str:
    """Keep established built-in filenames; external names are not filesystem paths."""
    import hashlib
    import re

    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,79}", name) or name.startswith("sha256-"):
        name = "sha256-" + hashlib.sha256(name.encode("utf-8")).hexdigest()
    return f"metrics-{name}.json"


def _select_evaluators(names: tuple[str, ...], modules: tuple[str, ...]) -> list[Evaluator]:
    from sloplab.evaluators.external import ExternalEvaluatorError, resolve_evaluators

    try:
        return resolve_evaluators(names, modules)
    except ExternalEvaluatorError as exc:
        raise click.ClickException(str(exc)) from exc


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
@click.option(
    "--evaluator", "evaluators", multiple=True, help="Built-in evaluator name; repeatable."
)
@click.option(
    "--evaluator-module",
    "evaluator_modules",
    multiple=True,
    help="Trusted local Python FILE.py:ATTR or MODULE:ATTR; repeatable, not sandboxed.",
)
@click.option("--out", type=click.Path(path_type=str), required=True)
def evaluate(
    cases: str, evaluators: tuple[str, ...], out: str, evaluator_modules: tuple[str, ...] = ()
) -> None:
    """Run evaluators over a materialized suite (directory with suite-index.jsonl)."""
    from pathlib import Path as _Path

    from sloplab.reporting.writers import write_markdown_report

    selected = _select_evaluators(evaluators, evaluator_modules)
    index_path, corpus_root, materialized_root = _resolve_suite_index(cases)
    out_dir = _Path(out)
    bundles = _run_evaluators_over_suite(
        selected, index_path, corpus_root, materialized_root, out_dir, "evaluate", 0
    )
    write_markdown_report(out_dir / "report.md", bundles, "SlopLab evaluation results")
    click.echo(f"wrote {out_dir / 'run.jsonl'}, metrics and report.md")


@cli.command()
@click.argument("suite", type=click.Path(exists=True, path_type=str))
@click.option(
    "--evaluator", "evaluators", multiple=True, help="Built-in evaluator name; repeatable."
)
@click.option(
    "--evaluator-module",
    "evaluator_modules",
    multiple=True,
    help="Trusted local Python FILE.py:ATTR or MODULE:ATTR; repeatable, not sandboxed.",
)
@click.option("--out", type=click.Path(path_type=str), required=True)
@click.option(
    "--materialize/--no-materialize",
    "do_materialize",
    default=True,
    help="Re-materialize the suite before evaluating.",
)
def benchmark(
    suite: str,
    evaluators: tuple[str, ...],
    out: str,
    do_materialize: bool,
    evaluator_modules: tuple[str, ...] = (),
) -> None:
    """Materialize and evaluate a full suite, then score it."""
    from pathlib import Path as _Path

    from sloplab.corpus.loader import FixtureError, discover_fixtures
    from sloplab.mutations.materialize import (
        LEDGER_FILE_NAME,
        SUITE_INDEX_NAME,
        load_suite_config,
        materialize_suite,
        read_materialization_ledger,
    )
    from sloplab.reporting.writers import write_markdown_report, write_records_csv

    selected = _select_evaluators(evaluators, evaluator_modules)
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

    ledger_path = out_dir / LEDGER_FILE_NAME
    if ledger_path.is_file():
        try:
            ledger_header, _ledger_rows = read_materialization_ledger(out_dir)
        except (OSError, ValueError) as exc:
            raise click.ClickException(f"invalid materialization ledger: {exc}") from exc
        if int(ledger_header.get("safety_blocked", 0)) > 0:
            raise click.ClickException(
                "materialization contains safety-blocked cases; "
                "refusing to evaluate a partial unsafe suite"
            )

    index_path = out_dir / SUITE_INDEX_NAME
    bundles = _run_evaluators_over_suite(
        selected,
        index_path,
        corpus_root,
        out_dir,
        out_dir,
        config.name,
        config.base_seed,
    )
    try:
        open_result_dir(out_dir / "run.jsonl", purpose="benchmark csv/report")
    except BundleError as exc:
        raise click.ClickException(str(exc)) from exc
    _, records = __import__(
        "sloplab.reporting.writers", fromlist=["read_run_jsonl"]
    ).read_run_jsonl(out_dir / "run.jsonl")
    write_records_csv(out_dir / "results.csv", records)
    write_markdown_report(out_dir / "report.md", bundles, f"SlopLab benchmark: {config.name}")
    click.echo(f"benchmark complete; results in {out_dir}")


@cli.command()
@click.argument("config", type=click.Path(exists=True, path_type=str))
@click.option("--out", type=click.Path(path_type=str), required=True)
def study(config: str, out: str) -> None:
    """Run a deterministic evaluator study with comparative analysis (V0.2)."""
    import json
    from dataclasses import asdict
    from pathlib import Path as _Path

    from sloplab.experiments.runner import load_study_config
    from sloplab.experiments.study import StudyConfigError, run_deterministic_study
    from sloplab.reporting.writers import read_run_jsonl, write_records_csv
    from sloplab.scoring.comparison import (
        bootstrap_accuracy_ci,
        error_taxonomy,
        paired_win_loss,
        per_class_metrics,
        per_operator_metrics,
    )
    from sloplab.scoring.metrics import compute_metrics

    try:
        cfg = load_study_config(_Path(config))
    except ValueError as exc:
        raise click.ClickException(f"invalid study config: {exc}") from exc
    out_dir = _Path(out)
    from sloplab.experiments.bundle import finish_publish

    try:
        result = run_deterministic_study(cfg, _Path(config), out_dir)
    except StudyConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    # Analysis options come from the frozen in-run copy, never by re-reading
    # the mutable original config after the run.
    analysis_cfg = result.recipe.analysis
    assert analysis_cfg is not None

    # Publisher-internal read of this invocation's own just-written records:
    # same-process-bound and mid-publish by construction (the in-progress
    # marker is still present), so the consumption boundary — which must
    # refuse in-progress bundles — cannot gate it without deadlocking
    # publication. Cross-time/cross-process reads of this directory always
    # go through open_result_dir and refuse until finish_publish.
    _meta, records = read_run_jsonl(result.records_path)
    by_evaluator: dict[str, list[Any]] = {}
    for record in records:
        by_evaluator.setdefault(record.evaluator_name, []).append(record)

    bundles: dict[str, MetricBundle] = {
        n: compute_metrics(rs, n) for n, rs in sorted(by_evaluator.items())
    }
    names = sorted(by_evaluator)
    comparisons = [
        paired_win_loss(by_evaluator[a], by_evaluator[b])
        for i, a in enumerate(names)
        for b in names[i + 1 :]
    ]
    taxonomy_counts = {n: error_taxonomy(rs).counts for n, rs in sorted(by_evaluator.items())}
    taxonomies_full = {n: error_taxonomy(rs).as_dict() for n, rs in sorted(by_evaluator.items())}
    per_op = {
        n: {op: asdict(bundle) for op, bundle in per_operator_metrics(rs).items()}
        for n, rs in sorted(by_evaluator.items())
    }
    per_cls = {
        n: {cls: asdict(bundle) for cls, bundle in per_class_metrics(rs).items()}
        for n, rs in sorted(by_evaluator.items())
    }
    cis = {
        n: bootstrap_accuracy_ci(
            rs,
            resamples=analysis_cfg.bootstrap_resamples,
            ci=analysis_cfg.bootstrap_ci,
            seed=analysis_cfg.bootstrap_seed,
        )
        for n, rs in sorted(by_evaluator.items())
    }

    analysis = {
        "bundles": {n: asdict(b) for n, b in bundles.items()},
        "paired_comparisons": [c.as_dict() for c in comparisons],
        "error_taxonomy": taxonomies_full,
        "per_operator": per_op,
        "per_class": per_cls,
        "bootstrap_accuracy_ci": {
            n: {"low": lo, "point": pt, "high": hi} for n, (lo, pt, hi) in cis.items()
        },
    }
    analysis_path = out_dir / "analysis.json"
    analysis_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")

    write_records_csv(out_dir / "results.csv", records)
    _write_comparison_markdown(
        out_dir / "report.md", bundles, comparisons, cis, taxonomy_counts, result.experiment_name
    )
    # Versioned analysis under a separate name: bound to the exact records
    # bytes, outcomes source, selection coverage, and definition version;
    # historical analysis.json is never overwritten or replaced. Evaluators
    # with zero successes stay visible with scored=0 and undefined metrics
    # (no invented decisions or scored records).
    from sloplab.reporting.analysis import write_versioned_analysis
    from sloplab.reporting.writers import metrics_to_dict as _metrics_to_dict
    from sloplab.scoring.metrics import compute_metrics as _compute_metrics

    failed_by_evaluator: dict[str, int] = {}
    outcomes_path = out_dir / "outcomes.jsonl"
    if outcomes_path.is_file():
        for line in outcomes_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("status") == "failed":
                evaluator_name = row.get("evaluator_name", "?")
                failed_by_evaluator[evaluator_name] = failed_by_evaluator.get(evaluator_name, 0) + 1
    versioned_names = sorted(set(names) | set(failed_by_evaluator))
    versioned_bundles = {n: _metrics_to_dict(b) for n, b in bundles.items()}
    for name in versioned_names:
        if name not in versioned_bundles:
            versioned_bundles[name] = _metrics_to_dict(_compute_metrics([], name))
    write_versioned_analysis(
        out_dir,
        records_path=result.records_path,
        bundles=versioned_bundles,
        coverage={
            n: {
                "planned": result.case_count,
                "scored": len(by_evaluator.get(n, [])),
                "failed": failed_by_evaluator.get(n, 0),
                "not_run": 0,
            }
            for n in versioned_names
        },
        outcomes_path=outcomes_path if outcomes_path.is_file() else None,
    )
    # Close the publish cycle last: verifiable completion first, in-progress
    # marker removed after it. Only then does the bundle read complete.
    finish_publish(out_dir, kind="study")
    click.echo(f"study complete -> {out_dir} ({result.case_count} cases, {len(names)} evaluators)")


def _write_comparison_markdown(
    path: Path,
    bundles: dict[str, MetricBundle],
    comparisons: list[Any],
    cis: dict[str, tuple[float, float, float]],
    taxonomies: dict[str, dict[str, int]],
    title: str,
) -> None:
    lines: list[str] = [f"# Evaluator study: {title}", ""]
    for name, b in sorted(bundles.items()):
        lo, point, hi = cis.get(name, (0.0, 0.0, 0.0))
        lines += [
            f"## `{name}`",
            "",
            f"- Decision accuracy: **{point:.3f}** (95% bootstrap CI {lo:.3f}-{hi:.3f})",
            f"- Mutation detection rate: {b.mutation_detection_rate}",
            f"- False reassurance rate: **{b.false_reassurance_rate}**",
            f"- Over-rejection rate: {b.over_rejection_rate}",
            f"- Robustness delta (drift): {b.robustness_delta}",
            f"- Presentation susceptibility: {b.presentation_susceptibility}",
            f"- Calibration error (ECE): {b.calibration_error}",
        ]
        if b.per_class_accuracy:
            lines.append("- Accuracy by report class:")
            for cls, acc in b.per_class_accuracy.items():
                lines.append(f"    - {cls}: {acc:.3f}")
        tax_counts = taxonomies.get(name, {})
        if tax_counts:
            lines.append("- Error taxonomy:")
            for code, count in sorted(tax_counts.items()):
                lines.append(f"    - {code}: {count}")
        lines.append("")

    if comparisons:
        lines += ["## Paired comparison", ""]
        for c in comparisons:
            d = c.as_dict()
            lines.append(
                f"- `{d['evaluator_a']}` vs `{d['evaluator_b']}`: "
                f"{d['a_wins']} wins / {d['b_wins']} losses / {d['ties']} ties "
                f"(win rate {d['a_win_rate']:.3f})"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


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
        try:
            mode = open_result_dir(path, purpose="compare")
        except BundleError as exc:
            raise click.ClickException(str(exc)) from exc
        if mode == "legacy":
            click.echo(
                f"note: {path} is a legacy bundle without integrity guarantees",
                err=True,
            )
        metrics_dir = path.parent if path.name == "run.jsonl" else path
        versioned = sorted(metrics_dir.glob("analysis-v*.json"))
        if len(versioned) > 1:
            raise click.ClickException(
                f"ambiguous versioned analyses in {metrics_dir}: {[v.name for v in versioned]}"
            )
        if versioned:
            # Same verified analysis report consumes: version, records hash,
            # and coverage are enforced by the reader, not re-derived here.
            from sloplab.reporting.analysis import AnalysisError, read_versioned_analysis

            try:
                document = read_versioned_analysis(versioned[0])
            except AnalysisError as exc:
                raise click.ClickException(str(exc)) from exc
            for name in document.get("evaluators", []):
                summaries[f"{name} ({metrics_dir.name})"] = document["bundles"][name]
            continue
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
@click.option("--format", "fmt", type=click.Choice(["markdown", "html"]), default="markdown")
@click.option("--out", type=click.Path(path_type=str), default=None)
@click.option(
    "--analysis",
    "analysis_path",
    type=click.Path(exists=True, path_type=str),
    default=None,
    help="Render from a verified versioned analysis instead of recomputing.",
)
def report(results: str, fmt: str, out: str | None, analysis_path: str | None) -> None:
    """Render a human-readable report from a run.jsonl file."""
    from pathlib import Path as _Path

    from sloplab.reporting.writers import read_run_jsonl, write_markdown_report
    from sloplab.scoring.metrics import compute_metrics

    if fmt == "html":
        if analysis_path is not None:
            raise click.ClickException(
                "HTML reporting currently requires run.jsonl because operator breakdown "
                "and execution outcomes are not fully represented in the analysis artifact. "
                "Omit --analysis, or use --format markdown."
            )
        from sloplab.reporting.html import write_html_report

        try:
            rendered = write_html_report(
                _Path(results), _Path(out) if out else _Path(results).parent / "report.html"
            )
        except (ValueError, OSError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"wrote offline HTML report: {rendered}")
        return

    if analysis_path is not None:
        # Same verified analysis report consumes: no recomputation, no drift.
        from sloplab.reporting.analysis import AnalysisError, read_versioned_analysis

        try:
            document = read_versioned_analysis(_Path(analysis_path))
        except AnalysisError as exc:
            raise click.ClickException(str(exc)) from exc
        bundles = [
            MetricBundle(**document["bundles"][name]) for name in document.get("evaluators", [])
        ]
        rendered = write_markdown_report(
            _Path(out) if out else _Path(analysis_path).parent / "report.md",
            bundles,
            f"SlopLab results (analysis v{document.get('analysis_version')})",
        )
        click.echo(rendered.read_text())
        return

    try:
        mode = open_result_dir(_Path(results), purpose="report")
    except BundleError as exc:
        raise click.ClickException(str(exc)) from exc
    if mode == "legacy":
        click.echo(
            f"note: {results} is a legacy bundle without integrity guarantees",
            err=True,
        )
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
