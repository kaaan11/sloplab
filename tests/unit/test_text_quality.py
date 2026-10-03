"""Content-only text control: useful quality changes, conservative decision semantics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.corpus.parser import parse_report
from sloplab.evaluators.base import Evaluator, evaluator_requires_labels, get_evaluator
from sloplab.evaluators.text_quality import TextQualityBaselineEvaluator
from sloplab.experiments.runner import load_study_config
from sloplab.experiments.study import run_deterministic_study
from sloplab.models.enums import Decision
from sloplab.models.evaluation import EvaluationContext, EvaluationResult
from sloplab.reporting.writers import read_run_jsonl
from tests._byoe_helpers import tiny_suite

RICH = """\
# Synthetic local trace note

## Summary
TraceRelay returns a digest matching the selected synthetic trace fixture.

## Affected Component
TraceRelay

## Affected Versions
2.3.0

## Preconditions
An isolated container has a pinned configuration and synthetic trace fixture.

## Reproduction Steps
1. Launch isolated TraceRelay container using explicit pinned test configuration.
2. Load sample trace file containing four labeled synthetic records.
3. Compare returned digest against saved reference output after completion.

## Observed Result
TraceRelay returns a digest matching the selected synthetic trace fixture.

## Expected Security Boundary
Each isolated container retains its own independently configured synthetic trace fixture.
"""


def evaluate(text: str) -> EvaluationResult:
    report = parse_report(text, fixture_id="opaque", path="opaque")
    return TextQualityBaselineEvaluator().evaluate(
        report, EvaluationContext(report=report, case_id="opaque")
    )


def codes(result: EvaluationResult) -> set[str]:
    return {finding.code for finding in result.findings}


def test_registered_quality_control_has_explicit_unknown_semantics() -> None:
    evaluator = get_evaluator("text-quality-baseline")
    assert isinstance(evaluator, Evaluator)
    assert evaluator_requires_labels(evaluator) is False
    result = evaluate(RICH)
    assert result.dimensions.reproducibility == result.dimensions.evidence_completeness == 1.0
    assert result.metadata["summary_observed_cosine"] == 1.0
    assert result.decision == Decision.NEEDS_MANUAL_REVIEW
    assert result.confidence == 0.5
    assert result.metadata["confidence_kind"] == "fixed_uncalibrated_control"
    for dimension in result.metadata["unassessed_dimensions"]:
        assert result.dimensions.as_dict()[dimension] == 0.5
    assert "TEXT_SEMANTICS_UNASSESSED" in codes(result)


@pytest.mark.parametrize("body", ["", "# Title only", "!!!", "## Summary\n\n```text\n```"])
def test_empty_or_unusual_content_returns_valid_zero_quality(body: str) -> None:
    result = evaluate(body)
    assert result.dimensions.reproducibility == 0.0
    assert result.dimensions.evidence_completeness == 0.0
    assert result.metadata["summary_observed_cosine"] is None
    assert result.decision == Decision.NEEDS_MANUAL_REVIEW
    assert "TEXT_NO_DETAILED_STEPS" in codes(result)
    assert all(0.0 <= score <= 1.0 for score in result.dimensions.as_dict().values())


def test_headings_do_not_fill_sections_and_children_supply_content() -> None:
    headings = "\n\n".join(
        f"## {heading}"
        for heading in (
            "Summary",
            "Affected Component",
            "Affected Versions",
            "Preconditions",
            "Reproduction Steps",
            "Observed Result",
            "Expected Security Boundary",
        )
    )
    empty = evaluate(headings)
    assert empty.dimensions.evidence_completeness == 0.0
    assert sum(f.code.startswith("TEXT_EMPTY_") for f in empty.findings) == 7
    nested = evaluate("## Observed Result\n\n### Trace\n\nOne two three four five six.")
    assert nested.metadata["section_content_scores"]["observed_result"] == 1.0
    assert nested.metadata["section_unique_tokens"]["observed_result"] == 6


def test_evidence_removal_lowers_score_without_changing_claim_decision() -> None:
    removed = RICH.replace(
        "## Observed Result\n"
        "TraceRelay returns a digest matching the selected synthetic trace fixture.\n",
        "",
    )
    result = evaluate(removed)
    assert result.dimensions.evidence_completeness == pytest.approx(6 / 7, abs=1e-6)
    assert "TEXT_MISSING_OBSERVED_RESULT" in codes(result)
    assert result.decision == evaluate(RICH).decision


def test_repeated_steps_and_word_padding_do_not_improve_quality() -> None:
    one = "## Reproduction Steps\n1. Load sample trace fixture.\n"
    duplicates = one + "2. LOAD SAMPLE TRACE FIXTURE!\n3. Load sample trace fixture.\n"
    first, repeated = evaluate(one), evaluate(duplicates)
    assert repeated.dimensions == first.dimensions
    assert repeated.metadata["ordered_steps"] == 3
    assert repeated.metadata["distinct_content_steps"] == 1
    assert "TEXT_DUPLICATE_STEPS" in codes(repeated)
    assert repeated.metadata["duplicate_line_ratio"] == pytest.approx(2 / 3, abs=1e-6)
    assert (
        evaluate("## Summary\ntrace ").dimensions.evidence_completeness
        == evaluate("## Summary\n" + "trace " * 1000).dimensions.evidence_completeness
    )


@pytest.mark.parametrize(
    "fenced",
    [
        "```text\n1. Fake ordered sample line.\n```",
        "\u00a0```text\n1. Fake ordered sample line.\n\u00a0```",
        "~~~text\n1. Fake ordered sample line.\n~~~",
        "````\n1. Fake ordered sample line.\n```\n2. Still fenced sample line.\n````",
        "```\n1. Fake ordered sample line.\n~~~\n2. Still fenced sample line.\n```",
        "```\n1. Fake ordered sample line.\n``` not-a-close\n2. Still fenced sample line.\n```",
    ],
)
def test_numbered_code_lines_are_not_reproduction_steps(fenced: str) -> None:
    result = evaluate(f"## Reproduction Steps\n{fenced}\n1. Load actual synthetic fixture.\n")
    assert result.metadata["ordered_steps"] == 1
    assert result.metadata["distinct_content_steps"] == 1


def test_indented_code_and_stop_word_steps_supply_no_detail() -> None:
    result = evaluate(
        "## Reproduction Steps\n    1. Indented code sample.\n"
        "\t1. Tab indented code sample.\n1. The and it.\n"
    )
    assert result.metadata["ordered_steps"] == 1
    assert result.metadata["distinct_content_steps"] == 0
    assert result.dimensions.reproducibility == 0.0


def test_unicode_normalization_and_lexical_overlap_are_diagnostics() -> None:
    same = evaluate("## Summary\nＣＡＦÉ\n## Observed Result\ncafe\u0301\n")
    assert same.metadata["summary_observed_cosine"] == 1.0
    disjoint = evaluate("## Summary\nalpha\n## Observed Result\nbeta\n")
    assert disjoint.metadata["summary_observed_cosine"] == 0.0
    # Identical prose can repeat a false claim; overlap never decides its truth.
    assert same.dimensions.claim_evidence_consistency == 0.5
    assert same.decision == disjoint.decision == Decision.NEEDS_MANUAL_REVIEW


def test_labels_paths_case_names_and_call_order_supply_no_signal() -> None:
    evaluator = TextQualityBaselineEvaluator()
    first = parse_report(RICH, fixture_id="valid", path="accept.md")
    a = evaluator.evaluate(first, EvaluationContext(report=first, case_id="A", labels={}))
    other = first.model_copy(update={"fixture_id": "invalid", "path": "fabricated_identifier.md"})
    b = evaluator.evaluate(
        other,
        EvaluationContext(
            report=other,
            case_id="B",
            labels={"expected_decision": "reject", "expected_dimensions": {"reproducibility": 0}},
        ),
    )
    evaluator.evaluate(
        parse_report("", fixture_id="x", path="x"), EvaluationContext(report=None, case_id="x")
    )
    again = evaluator.evaluate(first, EvaluationContext(report=first, case_id="A"))
    assert a.model_dump(exclude={"case_id"}) == b.model_dump(exclude={"case_id"})
    assert a.model_dump_json() == again.model_dump_json()
    assert b.case_id == "B"


def test_benchmark_evaluate_and_html_accept_new_builtin(tmp_path: Path) -> None:
    suite = tiny_suite(tmp_path)
    runner = CliRunner()
    out = tmp_path / "run"
    result = runner.invoke(
        cli,
        [
            "benchmark",
            str(suite),
            "--evaluator",
            "rules-baseline",
            "--evaluator",
            "text-quality-baseline",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    _, records = read_run_jsonl(out / "run.jsonl")
    assert len(records) == 8
    assert {r.evaluator_name for r in records} == {"rules-baseline", "text-quality-baseline"}
    metrics = json.loads((out / "metrics-text-quality-baseline.json").read_text())
    assert metrics["decision_accuracy"] == 0.5  # two accept and two review targets
    replay = tmp_path / "replay"
    result = runner.invoke(
        cli,
        [
            "evaluate",
            str(out),
            "--evaluator",
            "text-quality-baseline",
            "--out",
            str(replay),
        ],
    )
    assert result.exit_code == 0, result.output
    _, replayed = read_run_jsonl(replay / "run.jsonl")
    assert [r.model_dump() for r in replayed] == [
        r.model_dump() for r in records if r.evaluator_name == "text-quality-baseline"
    ]
    html = tmp_path / "report.html"
    result = runner.invoke(
        cli, ["report", str(out / "run.jsonl"), "--format", "html", "--out", str(html)]
    )
    assert result.exit_code == 0, result.output
    assert "text-quality-baseline" in html.read_text()


def test_study_records_and_recipe_are_repeatable(tmp_path: Path) -> None:
    suite = tiny_suite(tmp_path)
    path = tmp_path / "study.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "name": "text-control-test",
                "base_seed": 7,
                "suite": {"config_path": str(suite), "corpus_root": str(tmp_path / "corpus")},
                "evaluators": [{"name": "text-quality-baseline"}],
                "analysis": {"bootstrap_resamples": 100},
            }
        )
    )
    config = load_study_config(path)
    a = run_deterministic_study(config, path, tmp_path / "a")
    b = run_deterministic_study(config, path, tmp_path / "b")
    assert a.records_path.read_bytes() == b.records_path.read_bytes()
    assert a.case_count == 4
    manifest = json.loads(a.manifest_path.read_text())
    assert manifest["evaluators"] == [{"name": "text-quality-baseline", "version": "0.1.0"}]
