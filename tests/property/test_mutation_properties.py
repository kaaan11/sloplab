"""Property-style tests: invariants that must hold for every mutation output."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from sloplab.corpus.loader import load_canonical_fixture
from sloplab.corpus.parser import parse_report
from sloplab.mutations.base import derive_seed, get_operator, list_operators
from sloplab.safety.policy import validate_content_safety

VARIANTS_PER_OP = 6


@pytest.fixture(scope="module")
def sample_reports(tmp_path_factory: pytest.TempPathFactory) -> list[Any]:
    from tests._helpers import write_canonical_fixture

    root = tmp_path_factory.mktemp("prop-corpus")
    specs = [
        ("val-a", "canonical-val-a", "Valid property report A", "valid"),
        ("inv-b", "canonical-inv-b", "Invalid property report B", "invalid"),
        ("rev-c", "canonical-rev-c", "Review property report C", "review"),
    ]
    docs = []
    for short, fid, title, cls in specs:
        write_canonical_fixture(root, short, fixture_id=fid, title=title, report_class=cls)
        docs.append(load_canonical_fixture(root / "canonical" / short, root).report)
    return docs


def test_provenance_invariants(sample_reports: list[Any]) -> None:
    """Every operator preserves parent identity markers and emits provenance data."""
    for doc in sample_reports:
        for op_name in list_operators():
            op = get_operator(op_name)
            for variant in range(VARIANTS_PER_OP):
                seed = derive_seed(1234, doc.fixture_id, op_name, variant)
                mutated, params = op.apply(doc, random.Random(seed))
                # Provenance: parameters are always a dict with recorded choices.
                assert isinstance(params, dict), (op_name, variant)
                # Structural integrity: mutated text parses and keeps the H1.
                reparsed = parse_report(mutated, fixture_id=doc.fixture_id, path=doc.path)
                assert reparsed.title == doc.title or mutated == doc.raw_text, (
                    op_name,
                    variant,
                )
                _ = seed


def test_safety_across_seeds(sample_reports: list[Any]) -> None:
    """No operator ever emits content outside reserved namespaces."""
    for doc in sample_reports:
        for op_name in list_operators():
            op = get_operator(op_name)
            for variant in range(VARIANTS_PER_OP):
                seed = derive_seed(777, doc.fixture_id, op_name, variant)
                mutated, _ = op.apply(doc, random.Random(seed))
                violations = validate_content_safety(mutated)
                assert violations == [], (op_name, variant, violations)


def test_determinism_property(sample_reports: list[Any]) -> None:
    """(input, seed) fully determines output - no hidden state."""
    for doc in sample_reports:
        for op_name in list_operators():
            op = get_operator(op_name)
            seeds = [derive_seed(42, doc.fixture_id, op_name, v) for v in range(3)]
            outputs = [op.apply(doc, random.Random(s))[0] for s in seeds]
            outputs_again = [op.apply(doc, random.Random(s))[0] for s in seeds]
            assert outputs == outputs_again


def test_no_mutation_crashes_on_minimal_report() -> None:
    """Operators degrade gracefully on reports missing every optional section."""
    from sloplab.corpus.parser import parse_report

    minimal = parse_report(
        "# Bare report\n\nJust a paragraph.\n", fixture_id="canonical-min-001", path="x"
    )
    for op_name in list_operators():
        op = get_operator(op_name)
        mutated, params = op.apply(minimal, random.Random(1))
        assert isinstance(mutated, str)
        assert isinstance(params, dict)


def test_materialized_corpus_stays_safe(tmp_path: Path) -> None:
    """End-to-end: generated adversarial fixtures all pass safety validation."""
    from tests._helpers import write_canonical_fixture

    write_canonical_fixture(
        tmp_path, "s-001", fixture_id="canonical-s-001", title="Safe one", report_class="valid"
    )
    write_canonical_fixture(
        tmp_path, "s-002", fixture_id="canonical-s-002", title="Safe two", report_class="invalid"
    )
    from sloplab.corpus.loader import discover_fixtures
    from sloplab.models.suite import SuiteConfig
    from sloplab.mutations.materialize import materialize_suite

    config = SuiteConfig.model_validate(
        {
            "name": "safety-prop",
            "base_seed": 5,
            "corpus_root": str(tmp_path),
            "policies": {
                "valid": {"variants_per_fixture": 2, "operators": list_operators()},
                "invalid": {
                    "variants_per_fixture": 1,
                    "operators": ["professionalize_language"],
                },
            },
        }
    )
    canonical, _ = discover_fixtures(tmp_path)
    out = tmp_path / "out"
    result = materialize_suite(config, canonical, out)
    assert result.safety_violations == []
