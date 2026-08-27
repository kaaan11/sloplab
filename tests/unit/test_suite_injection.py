"""Tests for v1-injection benchmark suite configuration, materialization and reporting (Phase 9)."""

from __future__ import annotations

from pathlib import Path

from sloplab.corpus.loader import discover_fixtures
from sloplab.evaluators.base import get_evaluator
from sloplab.mutations.materialize import (
    SUITE_INDEX_NAME,
    load_suite_config,
    materialize_suite,
)
from sloplab.reporting.writers import write_markdown_report
from sloplab.scoring.harness import build_cases, run_suite
from sloplab.scoring.metrics import compute_metrics

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_v1_injection_suite_loads_and_validates() -> None:
    suite_file = REPO_ROOT / "benchmarks/suites/v1-injection.yaml"
    assert suite_file.is_file()

    config = load_suite_config(suite_file)
    assert config.name == "v1-injection"
    assert config.base_seed == 20260828
    assert "evaluator_override_injection" in config.policies["valid"].operators
    assert "markdown_polyglot_injection" in config.policies["valid"].operators
    assert "evaluator_override_injection" in config.policies["invalid"].operators
    assert "markdown_polyglot_injection" in config.policies["invalid"].operators


def test_v1_injection_suite_materializes_and_scores(tmp_path: Path) -> None:
    suite_file = REPO_ROOT / "benchmarks/suites/v1-injection.yaml"
    config = load_suite_config(suite_file)
    corpus_root = REPO_ROOT / "corpus"

    canonical, _ = discover_fixtures(corpus_root)
    # Subset of 3 fixtures for quick unit test execution
    test_fixtures = canonical[:3]

    out_dir = tmp_path / "v1-injection-run"
    result = materialize_suite(config, test_fixtures, out_dir, corpus_root_resolved=corpus_root)

    assert result.cases_written > 0
    assert (out_dir / SUITE_INDEX_NAME).is_file()

    # Build cases and run evaluator
    cases = build_cases(out_dir / SUITE_INDEX_NAME, corpus_root, out_dir)
    assert len(cases) > len(test_fixtures)

    evaluator = get_evaluator("rules-baseline")
    records = run_suite(evaluator, cases, concurrency=2)
    assert len(records) == len(cases)

    bundle = compute_metrics(records, evaluator.name)
    assert bundle.injection_resistance_rate is not None
    assert bundle.attack_success_rate is not None
    assert bundle.injection_cases_count > 0

    report_md = out_dir / "report.md"
    write_markdown_report(report_md, [bundle], "Test Injection Suite")
    report_text = report_md.read_text(encoding="utf-8")
    assert "Injection resistance rate (IRR):" in report_text
    assert "Attack success rate (ASR):" in report_text
