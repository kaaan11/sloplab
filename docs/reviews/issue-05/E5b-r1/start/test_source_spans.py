"""E5a: source-range editing characterization (behavior pinned, not fixed)."""

from __future__ import annotations

import hashlib
import random
from pathlib import Path
from typing import Any

from sloplab.corpus.loader import discover_fixtures
from sloplab.corpus.parser import parse_report
from sloplab.models.report import ReportSection, SourceLocation
from sloplab.mutations.materialize import load_suite_config, materialize_suite
from sloplab.mutations.operators.evidence import RemoveReproductionStep
from sloplab.mutations.textops import (
    document_identity,
    first_matching_section,
    numbered_steps,
    remove_section,
    replace_section_body,
    span_authorized,
    step_lines,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _totiming_doc() -> Any:
    raw = (REPO_ROOT / "corpus/canonical/totiming-019/report.md").read_text(encoding="utf-8")
    return parse_report(raw, fixture_id="canonical-totiming-019", path="x")


def _repro_section(doc: Any) -> Any:
    section = first_matching_section(doc, "reproduction")
    assert section is not None
    return section


def test_b1_full_item_removal() -> None:
    """B1 fixed (full-item-v1): the whole multi-line step goes, neighbors stay.

    E5a pinned the residue as the defect; E5b removes the full item span.
    """
    doc = _totiming_doc()
    mutated, params = RemoveReproductionStep().apply(doc, random.Random(21))
    assert params["mode"] == "single_step"
    assert params["removed_step_number"] == 1
    assert params["removed_step_text"].startswith("1. Send 40 failed sign-ins")
    assert params["span_model"] == "full-item-v1"
    assert params["removed_extra_lines"] == 1
    assert "1. Send 40 failed sign-ins" not in mutated
    # The continuation line is gone with its step: no orphan remains.
    assert "interleaved to cancel drift" not in mutated
    reparsed = parse_report(mutated, fixture_id="d", path="x")
    assert _repro_section(reparsed).text == (
        "## Reproduction Steps\n"
        "\n"
        "2. Record response times and compare group medians.\n"
        "3. Repeat the whole procedure three times."
    )


def test_whole_section_mode_when_fewer_than_two_steps() -> None:
    """Single-step sections are removed whole (mode recorded)."""
    doc = parse_report(
        "# T\n\n## Reproduction Steps\n\n1. Only step here.\n\n## Next\n\nBody.\n",
        fixture_id="x",
        path="x",
    )
    mutated, params = RemoveReproductionStep().apply(doc, random.Random(0))
    assert params["mode"] == "whole_section"
    assert "Only step here" not in mutated
    assert "## Next" in mutated


def test_missing_section_is_controlled_noop() -> None:
    """No matching section: input unchanged plus a stable note."""
    doc = parse_report("# T\n\n## Summary\n\nBody.\n", fixture_id="x", path="x")
    mutated, params = RemoveReproductionStep().apply(doc, random.Random(0))
    assert mutated == doc.raw_text
    assert params == {"note": "no reproduction steps section found"}


def test_numbered_step_syntax_edges() -> None:
    """Step regex: markers, indents, multi-digit match; lookalikes do not."""
    doc = parse_report(
        "# T\n\n## Reproduction Steps\n\n"
        "1. one\n"
        "  2) two indented\n"
        "10. ten\n"
        "1.2 dotted\n"
        "(3) parenthesized\n"
        "v2.0 version\n"
        "Step 4. spelled\n",
        fixture_id="x",
        path="x",
    )
    section = _repro_section(doc)
    assert numbered_steps(section) == [(2, 1), (3, 2), (4, 3)]
    assert step_lines(section) == ["1. one", "  2) two indented", "10. ten"]


def test_fence_contents_stay_in_body_but_hide_headings() -> None:
    """Fenced `#` lines never break sections; fenced steps still match."""
    doc = parse_report(
        "# T\n\n## Reproduction Steps\n\n```\n# not a heading\n"
        "1. fenced step\n```\n\n1. real step\n",
        fixture_id="x",
        path="x",
    )
    assert [s.heading for s in doc.sections] == ["T", "Reproduction Steps"]
    assert numbered_steps(_repro_section(doc)) == [(4, 1), (7, 2)]


def test_tilde_and_long_fences() -> None:
    """~~~ and ```` fences open; same-char markers close regardless of length."""
    doc = parse_report(
        "# T\n\n~~~\n# hidden\n~~~\n\n## A\n\nbody\n\n````\n# also hidden\n```\n\n## B\n\nend\n",
        fixture_id="x",
        path="x",
    )
    assert [s.heading for s in doc.sections] == ["T", "A", "B"]


def test_unclosed_fence_swallows_rest() -> None:
    """An unclosed fence hides every later heading (pinned limitation)."""
    doc = parse_report("# T\n\n```\n# hidden\n\n## Lost\n\nbody\n", fixture_id="x", path="x")
    assert [s.heading for s in doc.sections] == ["T"]


def test_mixed_fence_types_do_not_close() -> None:
    """A ``` block is not closed by ~~~ (first-char tracking)."""
    doc = parse_report("# T\n\n```\n~~~\n\n## Hidden\n\nx\n", fixture_id="x", path="x")
    assert [s.heading for s in doc.sections] == ["T"]


def test_crlf_locations_hold_but_output_normalizes() -> None:
    """CRLF input parses at the right lines; output joins with LF."""
    raw = "## H\r\n\r\n1. a\r\n   cont\r\n"
    doc = parse_report(raw, fixture_id="x", path="x")
    assert numbered_steps(doc.sections[0]) == [(2, 1)]
    assert "\r" not in replace_section_body(doc, doc.sections[0], "1. b")
    assert "\r" not in remove_section(doc, doc.sections[0])


def test_utf8_passthrough() -> None:
    """Non-ASCII bytes survive replace and remove paths."""
    doc = parse_report("# T\n\n## Café ✓\n\nnaïve → ok ✓\n", fixture_id="x", path="x")
    assert "Café ✓" in replace_section_body(doc, doc.sections[1], "neue ✓")
    assert "✓" not in remove_section(doc, doc.sections[1])


def test_remove_section_swallows_one_blank() -> None:
    """Middle removal leaves a single blank line, never doubled blanks."""
    doc = parse_report("# T\n\na\n\n## Mid\n\nb\n\n## End\n\nc\n", fixture_id="x", path="x")
    assert remove_section(doc, doc.sections[1]) == "# T\n\na\n\n## End\n\nc"


def test_replace_section_body_keeps_heading() -> None:
    """Replacement swaps the body; empty body leaves the heading alone."""
    doc = parse_report("# T\n\n## Mid\n\nold body\n", fixture_id="x", path="x")
    assert replace_section_body(doc, doc.sections[1], "new") == "# T\n\n## Mid\nnew"
    assert replace_section_body(doc, doc.sections[1], "") == "# T\n\n## Mid"


def test_fresh_spans_authorize_corpus_wide() -> None:
    """Every parser-produced section of every canonical fixture authorizes."""
    canonical, _ = discover_fixtures(REPO_ROOT / "corpus")
    assert len(canonical) > 0
    total = 0
    for fixture in canonical:
        doc = parse_report(fixture.report.raw_text, fixture_id=fixture.fixture_id, path="x")
        for section in doc.sections:
            total += 1
            assert span_authorized(
                doc, section, expected_document_identity=document_identity(doc)
            ), (fixture.fixture_id, section.heading)
    assert total > 500


def test_stale_span_rejected_after_edit() -> None:
    """A span captured before mutation no longer authorizes afterwards."""
    doc = _totiming_doc()
    stale = _repro_section(doc)
    identity = document_identity(doc)
    assert span_authorized(doc, stale, expected_document_identity=identity)
    mutated, _ = RemoveReproductionStep().apply(doc, random.Random(21))
    changed = parse_report(mutated, fixture_id="d", path="x")
    assert not span_authorized(changed, stale, expected_document_identity=identity)


def test_wrong_parent_section_rejected() -> None:
    """A section from another document does not authorize here."""
    doc = _totiming_doc()
    other_raw = (REPO_ROOT / "corpus/canonical/oauthstate-029/report.md").read_text(
        encoding="utf-8"
    )
    other = parse_report(other_raw, fixture_id="other", path="x")
    assert not span_authorized(
        doc,
        _repro_section(other),
        expected_document_identity=document_identity(other),
    )


def test_wrong_parent_rejected_when_local_span_matches() -> None:
    parent = parse_report(
        "# T\n\n## Reproduction Steps\n\n1. same\n\n## Tail\n\nparent\n",
        fixture_id="parent",
        path="parent",
    )
    other = parse_report(
        "# T\n\n## Reproduction Steps\n\n1. same\n\n## Tail\n\nother\n",
        fixture_id="other",
        path="other",
    )
    assert parent.sections[1] == other.sections[1]
    assert document_identity(parent) != document_identity(other)
    assert not span_authorized(
        other,
        parent.sections[1],
        expected_document_identity=document_identity(parent),
    )


def test_crafted_spans_rejected() -> None:
    """Out-of-bounds, heading-mismatch, and level-mismatch spans fail."""
    doc = _totiming_doc()
    section = _repro_section(doc)
    loc = section.location
    assert not span_authorized(
        doc,
        ReportSection(
            heading=section.heading,
            level=section.level,
            location=SourceLocation(start_line=9999, end_line=9999),
            text=section.text,
        ),
        expected_document_identity=document_identity(doc),
    )
    assert not span_authorized(
        doc,
        ReportSection(
            heading="Wrong Heading",
            level=section.level,
            location=loc,
            text=section.text,
        ),
        expected_document_identity=document_identity(doc),
    )
    assert not span_authorized(
        doc,
        ReportSection(
            heading=section.heading,
            level=section.level + 1,
            location=loc,
            text=section.text,
        ),
        expected_document_identity=document_identity(doc),
    )


def test_preamble_span_bound() -> None:
    """Heading-less spans authorize only at document start."""
    doc = parse_report("preamble text\n\n# T\n\nbody\n", fixture_id="x", path="x")
    assert doc.sections[0].heading is None
    assert span_authorized(doc, doc.sections[0], expected_document_identity=document_identity(doc))
    moved = ReportSection(
        heading=None,
        level=0,
        location=SourceLocation(start_line=5, end_line=5),
        text=doc.sections[0].text,
    )
    assert not span_authorized(doc, moved, expected_document_identity=document_identity(doc))


def test_document_identity_is_content_hash() -> None:
    """Identity follows bytes, not labels."""
    doc = _totiming_doc()
    assert document_identity(doc) == hashlib.sha256(doc.raw_text.encode("utf-8")).hexdigest()
    relabeled = parse_report(doc.raw_text, fixture_id="other", path="elsewhere")
    assert document_identity(relabeled) == document_identity(doc)


def test_single_step_parent_bound() -> None:
    """Second-generation edits re-resolve from the immediate parent only."""
    doc = _totiming_doc()
    parent_span = _repro_section(doc)
    first, _ = RemoveReproductionStep().apply(doc, random.Random(21))
    child = parse_report(first, fixture_id="d", path="x")
    # Grandparent span is stale against the child document.
    assert not span_authorized(
        child, parent_span, expected_document_identity=document_identity(doc)
    )
    # A fresh application resolves the child's own steps (single step).
    before = len(numbered_steps(_repro_section(child)))
    second, params = RemoveReproductionStep().apply(child, random.Random(1))
    assert params["mode"] == "single_step"
    after_child = parse_report(second, fixture_id="d2", path="x")
    assert len(numbered_steps(_repro_section(after_child))) == before - 1


def test_materialize_matches_committed_bundle_except_b1_fix(tmp_path: Path) -> None:
    """Impact reconciliation: only B1-fixed derivatives differ, and how.

    The E5a byte-identity premise is superseded by the fix: exactly the
    derivatives whose picked step had continuations change (report residue
    lines gone, manifest params gain span_model), everything else stays
    byte-identical, and counts reconcile with the E5a inventory.
    """
    config = load_suite_config(REPO_ROOT / "benchmarks/suites/v1-core.yaml")
    canonical, _ = discover_fixtures(REPO_ROOT / "corpus")
    out = tmp_path / "out"
    result = materialize_suite(config, canonical, out)
    assert result.cases_written == 237
    committed = REPO_ROOT / "benchmarks/results/v1-core-example/adversarial"
    fresh = {
        str(p.relative_to(out / "adversarial")): p.read_bytes()
        for p in sorted((out / "adversarial").rglob("*"))
        if p.is_file()
    }
    stored = {
        str(p.relative_to(committed)): p.read_bytes()
        for p in sorted(committed.rglob("*"))
        if p.is_file()
    }
    assert set(fresh) == set(stored)
    differing = sorted(k for k in fresh if fresh[k] != stored[k])
    reports = sorted(k for k in differing if k.endswith("report.md"))
    manifests = sorted(k for k in differing if k.endswith("mutation-manifest.yaml"))
    assert len(differing) == len(reports) + len(manifests) == 6
    # The three changed derivatives are exactly E5a inventory members.
    assert {Path(k).parts[0] for k in reports} == {"oauthstate-029", "saml-019", "totiming-019"}
    import difflib
    import json

    for report in reports:
        old_lines = stored[report].decode().splitlines()
        new_lines = fresh[report].decode().splitlines()
        delta = [
            line
            for line in difflib.unified_diff(old_lines, new_lines, lineterm="")
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        ]
        # Residue lines removed, nothing added, neighbors intact.
        assert delta and all(line.startswith("-") for line in delta), report
        manifest = str(Path(report).parent / "mutation-manifest.yaml")
        assert manifest in manifests
    # Manifests differ only by the added span identity keys.
    import yaml

    for manifest in manifests:
        old_doc = yaml.safe_load(stored[manifest].decode())
        new_doc = yaml.safe_load(fresh[manifest].decode())
        assert set(new_doc) == set(old_doc)
        old_params = old_doc["parameters"]["choices"]
        new_params = new_doc["parameters"]["choices"]
        assert set(new_params) - set(old_params) == {"span_model", "removed_extra_lines"}
        assert new_params["span_model"] == "full-item-v1"
        assert all(old_doc[k] == new_doc[k] for k in old_doc if k != "parameters")
    # Suite index body identical; header differs only by machine corpus_root.
    old = (
        (REPO_ROOT / "benchmarks/results/v1-core-example/suite-index.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    new = (out / "suite-index.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in old[1:]] == [json.loads(line) for line in new[1:]]
    old_header = json.loads(old[0])
    assert set(old_header) == set(json.loads(new[0]))
    # Ledger counts unchanged (fix changes bytes, not populations).
    assert "planned 280" in result.summary()
    assert "written 237" in result.summary()
