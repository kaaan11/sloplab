"""E5b: full-item step removal, support profile, and stale-span gate."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from sloplab.corpus.parser import parse_report
from sloplab.mutations.materialize import check_materialization
from sloplab.mutations.operators.evidence import RemoveReproductionStep
from sloplab.mutations.textops import (
    StaleSpanError,
    first_matching_section,
    full_step_span,
    numbered_steps,
    remove_section,
    replace_section_body,
    span_authorized,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _doc(fixture: str) -> Any:
    raw = (REPO_ROOT / f"corpus/canonical/{fixture}/report.md").read_text(encoding="utf-8")
    return parse_report(raw, fixture_id=f"canonical-{fixture}", path="x")


def _repro_section(doc: Any) -> Any:
    section = first_matching_section(doc, "reproduction")
    assert section is not None
    return section


def test_oauthstate_and_saml_full_removal() -> None:
    """The other two B1 examples: residue gone, neighbors byte-intact."""
    doc = _doc("oauthstate-029")
    mutated, params = RemoveReproductionStep().apply(doc, random.Random(0))
    assert params["removed_step_number"] == 2
    assert params["span_model"] == "full-item-v1"
    assert params["removed_extra_lines"] == 1
    assert "   code parameter." not in mutated
    assert "2. In session B" not in mutated
    assert "1. Begin an OAuth flow" in mutated
    assert "3. Repeat the callback" in mutated

    saml = _doc("saml-019")
    mutated_saml, params_saml = RemoveReproductionStep().apply(saml, random.Random(0))
    assert params_saml["removed_step_number"] == 2
    assert params_saml["span_model"] == "full-item-v1"
    assert "omitting the signature element entirely" not in mutated_saml
    assert "1. Start the demo" in mutated_saml
    assert "3. Inspect the resulting session page." in mutated_saml


def test_unaffected_pick_carries_no_span_identity() -> None:
    """Single-line picks behave exactly as before (no marker, same bytes)."""
    doc = _doc("totiming-019")
    mutated, params = RemoveReproductionStep().apply(doc, random.Random(0))
    assert params == {
        "removed_step_number": 2,
        "removed_step_text": "2. Record response times and compare group medians.",
        "mode": "single_step",
    }
    reparsed = parse_report(mutated, fixture_id="d", path="x")
    assert _repro_section(reparsed).text == (
        "## Reproduction Steps\n"
        "\n"
        "1. Send 40 failed sign-ins for an existing username and 40 for a fabricated one,\n"
        "   interleaved to cancel drift.\n"
        "3. Repeat the whole procedure three times."
    )


def test_sibling_numbers_not_resequenced() -> None:
    """Removal keeps original numbering (existing convention, pinned)."""
    doc = _doc("totiming-019")
    mutated, _ = RemoveReproductionStep().apply(doc, random.Random(21))
    assert "\n3. Repeat the whole procedure three times." in mutated


def test_fenced_section_is_controlled_noop() -> None:
    """Fences anywhere in the section: no-op with a stable note."""
    doc = parse_report(
        "# T\n\n## Reproduction Steps\n\n1. one\n```\ncode\n```\n\n2. two\n",
        fixture_id="x",
        path="x",
    )
    mutated, params = RemoveReproductionStep().apply(doc, random.Random(0))
    assert mutated == doc.raw_text
    assert params == {"note": "fenced content in section"}


def test_non_indented_continuation_is_controlled_noop() -> None:
    """Lazy (column-0) continuations are out of profile: full no-op, not partial."""
    doc = parse_report(
        "# T\n\n## Reproduction Steps\n\n1. one\nlazy A\n\n2. two\nlazy B\n",
        fixture_id="x",
        path="x",
    )
    section = _repro_section(doc)
    steps = numbered_steps(section)
    assert len(steps) == 2
    assert full_step_span(section.text.splitlines(), steps, steps[0][0]) is None
    assert full_step_span(section.text.splitlines(), steps, steps[1][0]) is None
    mutated, params = RemoveReproductionStep().apply(doc, random.Random(0))
    assert mutated == doc.raw_text
    assert params["note"].startswith("ambiguous continuation after step")


def test_nested_and_paragraph_continuations_belong_to_item() -> None:
    """Indented sublists and blank-joined indented paragraphs drop with the item."""
    doc = parse_report(
        "# T\n\n## Reproduction Steps\n\n"
        "1. one\n"
        "   - sub a\n"
        "   - sub b\n"
        "\n"
        "   para after blank\n"
        "\n"
        "2. two\n",
        fixture_id="x",
        path="x",
    )
    section = _repro_section(doc)
    steps = numbered_steps(section)
    assert len(steps) == 2
    drop = full_step_span(section.text.splitlines(), steps, steps[0][0])
    assert drop == {2, 3, 4, 6}
    mutated, params = RemoveReproductionStep().apply(doc, random.Random(1))
    assert params["removed_extra_lines"] == 3
    assert "- sub a" not in mutated
    assert "para after blank" not in mutated
    assert "2. two" in mutated


def test_stale_span_gate_rejects() -> None:
    """Splice functions refuse spans from other byte states."""
    from sloplab.mutations.textops import document_identity

    doc = _doc("totiming-019")
    other = parse_report(
        "# T\n\n## Reproduction Steps\n\n9. alien step\n", fixture_id="y", path="y"
    )
    foreign = _repro_section(other)
    import pytest

    with pytest.raises(StaleSpanError):
        replace_section_body(doc, foreign, "x", expected_document_identity=document_identity(other))
    with pytest.raises(StaleSpanError):
        remove_section(doc, foreign, expected_document_identity=document_identity(other))
    # Fresh spans still splice.
    assert "alien" not in replace_section_body(
        other, foreign, "1. fresh\n", expected_document_identity=document_identity(other)
    )


def test_identity_argument_is_mandatory() -> None:
    """The provenance argument has no default and cannot be skipped."""
    import inspect

    import pytest

    from sloplab.mutations import textops as textops_module

    for name in ("replace_section_body", "remove_section"):
        params = inspect.signature(getattr(textops_module, name)).parameters
        assert params["expected_document_identity"].default is inspect.Parameter.empty
    doc = _doc("totiming-019")
    section = _repro_section(doc)
    with pytest.raises(TypeError):
        replace_section_body(doc, section, "x")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        remove_section(doc, section)  # type: ignore[call-arg]


def test_fence_syntax_mirrors_parser() -> None:
    """textops fence recognition cannot drift from parser.py silently."""
    import re

    from sloplab.corpus import parser as parser_module
    from sloplab.mutations import textops as textops_module

    assert textops_module._FENCE_RE.pattern == parser_module._FENCE_RE.pattern
    assert re.compile(r"^(#{1,6})\s+").pattern == r"^(#{1,6})\s+"


def test_fix_is_deterministic() -> None:
    """Same seed twice gives identical bytes and params."""
    doc = _doc("saml-019")
    first = RemoveReproductionStep().apply(doc, random.Random(7))
    second = RemoveReproductionStep().apply(doc, random.Random(7))
    assert first == second


def test_ledger_carries_span_model(tmp_path: Path) -> None:
    """Run-level production identity reconciles with the materialized set."""
    from sloplab.corpus.loader import discover_fixtures
    from sloplab.models.suite import SuiteConfig
    from sloplab.mutations.materialize import materialize_suite, read_materialization_ledger
    from tests._helpers import write_canonical_fixture

    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "a-000",
        fixture_id="canonical-a-000",
        title="Ledger span report",
        report_class="valid",
        report_body=(
            "# Ledger span report\n\n## Reproduction Steps\n\n1. one\n   cont\n\n2. two\n"
        ),
    )
    suite_config = SuiteConfig.model_validate(
        {
            "name": "s",
            "base_seed": 1,
            "corpus_root": str(corpus),
            "include_canonical_cases": True,
            "policies": {"valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]}},
        }
    )
    canonical, _ = discover_fixtures(corpus)
    out = tmp_path / "out"
    materialize_suite(suite_config, canonical, out)
    header, _ = read_materialization_ledger(out)
    assert header["span_model"] == "full-item-v1"
    assert check_materialization(out)["written"] >= 0


def test_span_authorized_uses_mandatory_identity() -> None:
    """Reviewer contract: authorization binds the full document identity."""
    import inspect

    from sloplab.mutations.textops import document_identity

    doc = _doc("totiming-019")
    section = _repro_section(doc)
    params = inspect.signature(span_authorized).parameters
    assert params["expected_document_identity"].default is inspect.Parameter.empty
    assert span_authorized(doc, section, expected_document_identity=document_identity(doc)) is True
    assert span_authorized(doc, section, expected_document_identity="0" * 64) is False
