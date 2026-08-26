"""Regression tests for the v0.2.2 remediation (audit findings R01-R04, R06).

Each test maps to a finding from the independent v0.2.1 audit; see
docs/remediation-audit-v0.2.2.md for the full mapping.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import yaml
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.corpus.loader import discover_fixtures, load_canonical_fixture
from sloplab.corpus.parser import parse_report
from sloplab.models.enums import DIMENSIONS, Decision, MutationCategory
from sloplab.models.evaluation import DimensionScores, EvaluationContext, EvaluationResult
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.base import _REGISTRY, MutationSpec, register
from sloplab.mutations.materialize import MaterializationResult, materialize_suite
from sloplab.mutations.operators.impact import ImpactInflation
from sloplab.mutations.operators.presentation import (
    ConfidenceOverstatement,
    ProfessionalizeLanguage,
)
from sloplab.mutations.operators.references import AddIrrelevantDetail
from sloplab.scoring.harness import SuiteCase, opaque_case_handle, run_case

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_UNSAFE_OP_NAME = "unsafe_probe"


class _UnsafeProbeOperator:
    """Deliberate policy violator used to prove output boundaries enforce safety."""

    spec = MutationSpec(
        name=_UNSAFE_OP_NAME,
        category=MutationCategory.IMPACT,
        description="Test-only operator that emits non-reserved identifiers.",
    )

    def apply(
        self,
        document: Any,
        rng: random.Random,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        _ = rng, parameters
        mutated = document.raw_text + "\n\nSee CVE-2024-1337 at https://evil.attacker.com/x.\n"
        return mutated, {"injected": "unsafe"}


def _register_unsafe_operator() -> None:
    register(_UnsafeProbeOperator())


def _unregister_unsafe_operator() -> None:
    _REGISTRY.pop(_UNSAFE_OP_NAME, None)


def _write_suite(path: Path, *, operators: list[str], variants: int) -> Path:
    suite = {
        "name": "remediation-suite",
        "base_seed": 4242,
        "corpus_root": str(path),
        "include_canonical_cases": True,
        "policies": {
            "valid": {"variants_per_fixture": variants, "operators": operators},
            "invalid": {"variants_per_fixture": variants, "operators": operators},
            "review": {"variants_per_fixture": variants, "operators": operators},
        },
    }
    suite_path = path / "suite.yaml"
    suite_path.write_text(yaml.safe_dump(suite), encoding="utf-8")
    return suite_path


class _SpyEvaluator:
    """Records exactly what the harness hands to an evaluator."""

    name = "spy"
    version = "0.0.0"

    def __init__(self) -> None:
        self.contexts: list[EvaluationContext] = []
        self.documents: list[Any] = []

    def evaluate(self, report: Any, context: EvaluationContext) -> EvaluationResult:
        self.documents.append(report)
        self.contexts.append(context)
        dims = {d: 0.5 for d in DIMENSIONS}
        return EvaluationResult(
            evaluator_name=self.name,
            evaluator_version=self.version,
            case_id=context.case_id,
            decision=Decision.ACCEPT,
            confidence=0.5,
            dimensions=DimensionScores.from_dict(dims),
            findings=[],
            rationale="spy",
            metadata={},
        )


# ---------------------------------------------------------------------------
# R01 - no derived case may equal its parent
# ---------------------------------------------------------------------------


class TestR01NoOpElimination:
    def test_confidence_overstatement_noop_emits_note(self) -> None:
        text = "# T\n\n## Summary\n\nPlain declarative prose with no hedges.\n"
        doc = parse_report(text, fixture_id="canonical-noop-001", path="x")
        mutated, params = ConfidenceOverstatement().apply(doc, random.Random(1))
        assert mutated == text
        assert "note" in params

    def test_materializer_skips_unchanged_text(self, tmp_path: Path, make_fixture: Any) -> None:
        make_fixture(
            tmp_path,
            "inv-001",
            fixture_id="canonical-inv-001",
            title="Hedge free invalid report",
            report_class="invalid",
        )
        suite_path = _write_suite(tmp_path, operators=["confidence_overstatement"], variants=2)
        config = SuiteConfig.model_validate(yaml.safe_load(suite_path.read_text()))
        canonical, _ = discover_fixtures(tmp_path)
        result = materialize_suite(config, canonical, tmp_path / "out")
        assert result.cases_written == 0
        reasons = " | ".join(reason for _, reason in result.skipped)
        assert "no hedged language found" in reasons or "no textual change" in reasons
        assert not (tmp_path / "out" / "adversarial").exists() or not any(
            (tmp_path / "out" / "adversarial").rglob("report.md")
        )

    def test_written_derived_cases_differ_from_parents(
        self, tmp_path: Path, make_fixture: Any
    ) -> None:
        make_fixture(
            tmp_path,
            "val-001",
            fixture_id="canonical-val-001",
            title="Valid remediation report",
            report_class="valid",
        )
        suite_path = _write_suite(tmp_path, operators=["impact_inflation"], variants=1)
        config = SuiteConfig.model_validate(yaml.safe_load(suite_path.read_text()))
        canonical, _ = discover_fixtures(tmp_path)
        result = materialize_suite(config, canonical, tmp_path / "out")
        assert result.cases_written == 1
        parents = {f.fixture_id: f.report.raw_text for f in canonical}
        for manifest_path in (tmp_path / "out").rglob("mutation-manifest.yaml"):
            man = yaml.safe_load(manifest_path.read_text())
            written = manifest_path.parent.joinpath("report.md").read_text()
            parent_short = man["parent_id"].removeprefix("canonical-")
            parent = parents[f"canonical-{parent_short}"]
            assert written != parent, f"clone detected for {man['id']}"


# ---------------------------------------------------------------------------
# R02 - word-boundary-safe impact inflation
# ---------------------------------------------------------------------------


class TestR02InflationBoundaries:
    def test_nearby_words_are_never_corrupted(self) -> None:
        text = (
            "# T\n\n## Impact\n\n"
            "The login flow continues; operators may allow repeated attempts. "
            "The window below shows a shallow config of limited value. "
            "Severity is medium.\n"
        )
        doc = parse_report(text, fixture_id="canonical-flow-001", path="x")
        mutated, params = ImpactInflation().apply(doc, random.Random(5))
        for intact in ("login flow", "allow repeated", "window below", "shallow"):
            assert intact in mutated, intact
        assert params["calibration_replacements"] == ["medium->critical"]
        assert "critical" in mutated.split("## Impact", 1)[1]

    def test_phrase_replacement_wins_over_single_word(self) -> None:
        text = "# T\n\n## Impact\n\nExposure is low to medium in this deployment configuration.\n"
        doc = parse_report(text, fixture_id="canonical-phrase-001", path="x")
        _, params = ImpactInflation().apply(doc, random.Random(5))
        assert params["calibration_replacements"] == ["low to medium->critical"]

    def test_case_preserved_for_non_matches(self) -> None:
        text = "# T\n\n## Impact\n\nNo calibrated severity language here at all.\n"
        doc = parse_report(text, fixture_id="canonical-none-001", path="x")
        _, params = ImpactInflation().apply(doc, random.Random(5))
        assert params["calibration_replacements"] == []


# ---------------------------------------------------------------------------
# R03 - safety enforcement at every output boundary
# ---------------------------------------------------------------------------


class TestR03SafetyBoundaries:
    def setup_method(self) -> None:
        _register_unsafe_operator()

    def teardown_method(self) -> None:
        _unregister_unsafe_operator()

    def test_materializer_refuses_unsafe_output(self, tmp_path: Path, make_fixture: Any) -> None:
        make_fixture(
            tmp_path,
            "val-002",
            fixture_id="canonical-val-002",
            title="Unsafe boundary report",
            report_class="valid",
        )
        suite_path = _write_suite(tmp_path, operators=[_UNSAFE_OP_NAME], variants=1)
        config = SuiteConfig.model_validate(yaml.safe_load(suite_path.read_text()))
        canonical, _ = discover_fixtures(tmp_path)
        result: MaterializationResult = materialize_suite(config, canonical, tmp_path / "out")
        assert result.safety_violations, "unsafe operator output must be flagged"
        assert result.cases_written == 0
        assert not list((tmp_path / "out").rglob("report.md"))

    def test_cli_mutate_blocks_unsafe_output(self, tmp_path: Path, make_fixture: Any) -> None:
        fixture_dir = make_fixture(
            tmp_path,
            "val-003",
            fixture_id="canonical-val-003",
            title="Mutate safety report",
            report_class="valid",
        )
        out_dir = tmp_path / "mutated-out"
        result = CliRunner().invoke(
            cli,
            [
                "mutate",
                str(fixture_dir),
                "--operator",
                _UNSAFE_OP_NAME,
                "--seed",
                "1",
                "--out",
                str(out_dir),
            ],
        )
        assert result.exit_code != 0, result.output
        assert "SAFETY" in result.output
        assert not (out_dir / "report.md").exists()


# ---------------------------------------------------------------------------
# R04 - evaluators receive identity-free input
# ---------------------------------------------------------------------------


class TestR04OpaqueIdentity:
    def test_canonical_case_input_is_identity_free(self, tmp_path: Path, make_fixture: Any) -> None:
        fixture_dir = make_fixture(
            tmp_path,
            "val-004",
            fixture_id="canonical-val-004",
            title="Opaque canonical report",
            report_class="valid",
        )
        canon = load_canonical_fixture(fixture_dir, tmp_path)
        case = SuiteCase(
            case_id="canonical-val-004",
            kind="canonical",
            parent_id=None,
            operator=None,
            report_class="valid",
            expected_decision="accept",
            expected_dimensions={},
            seed=None,
            fixture_dir=None,
            canonical_fixture=canon,
        )
        spy = _SpyEvaluator()
        record = run_case(spy, case)
        handle = opaque_case_handle("canonical-val-004")
        assert spy.contexts[0].case_id == handle
        assert handle.startswith("case-") and handle != "canonical-val-004"
        assert spy.documents[0].fixture_id == handle
        assert spy.documents[0].path == handle
        assert record.case_id == "canonical-val-004"

    def test_mutated_case_hides_operator_identity(self, tmp_path: Path, make_fixture: Any) -> None:
        make_fixture(
            tmp_path,
            "val-005",
            fixture_id="canonical-val-005",
            title="Opaque mutated report",
            report_class="valid",
        )
        suite_path = _write_suite(tmp_path, operators=["impact_inflation"], variants=1)
        config = SuiteConfig.model_validate(yaml.safe_load(suite_path.read_text()))
        canonical, _ = discover_fixtures(tmp_path)
        out_root = tmp_path / "out"
        materialize_suite(config, canonical, out_root)

        from sloplab.scoring.harness import build_cases

        cases = build_cases(out_root / "suite-index.jsonl", tmp_path, out_root)
        mutated = [c for c in cases if c.kind == "mutated"]
        assert mutated, "expected one mutated case"
        spy = _SpyEvaluator()
        record = run_case(spy, mutated[0])
        seen_id = spy.contexts[0].case_id
        seen_path = spy.documents[0].path
        for leak_source in (seen_id, seen_path, spy.documents[0].fixture_id):
            assert "impact" not in leak_source.lower()
            assert "inflation" not in leak_source.lower()
            assert leak_source != mutated[0].case_id
        assert record.case_id == mutated[0].case_id
        assert record.operator == "impact_inflation"

    def test_handle_is_deterministic_and_distinct(self) -> None:
        a = opaque_case_handle("mut-x-impact-inflation-01")
        b = opaque_case_handle("mut-x-impact-inflation-01")
        c = opaque_case_handle("mut-y-remove-reproduction-step-01")
        assert a == b
        assert a != c
        assert "impact" not in a and "remove" not in c


# ---------------------------------------------------------------------------
# R06 - fence awareness and provenance accuracy
# ---------------------------------------------------------------------------


class TestR06FenceAwarenessAndProvenance:
    def test_professionalize_leaves_code_fences_intact(self) -> None:
        text = (
            "# T\n\n## Summary\n\nThis bug! It doesn't look right.\n\n"
            "## Reproduction Steps\n\n1. Run the script.\n\n"
            "```bash\n"
            '# don\'t panic!\necho "$a" != "$b"\n'
            "```\n"
        )
        doc = parse_report(text, fixture_id="canonical-fence-001", path="x")
        mutated, params = ProfessionalizeLanguage().apply(doc, random.Random(3))
        fence_block = '```bash\n# don\'t panic!\necho "$a" != "$b"\n```'
        assert fence_block in mutated, "fenced code must remain byte-identical"
        body = mutated.split("## Summary", 1)[1].split("## Reproduction", 1)[0]
        assert "defect." in body and "does not" in body  # register + contraction upgrades
        assert "bug" not in body.lower()
        assert isinstance(params["transformations"], list)

    def test_confidence_overstatement_skips_fences(self) -> None:
        text = (
            "# T\n\n## Observed Result\n\n```\nif user may allow this:\n"
            '    log("possibly bad")\n```\n\nNo hedged prose outside the block.\n'
        )
        doc = parse_report(text, fixture_id="canonical-fence-002", path="x")
        mutated, params = ConfidenceOverstatement().apply(doc, random.Random(3))
        assert mutated == text
        assert "note" in params

    def test_confidence_overstatement_edits_prose_not_fences(self) -> None:
        text = (
            "# T\n\n## Observed Result\n\n```\nmay allow\n```\n\n"
            "The endpoint may allow cross-tenant reads.\n"
        )
        doc = parse_report(text, fixture_id="canonical-fence-003", path="x")
        mutated, params = ConfidenceOverstatement().apply(doc, random.Random(3))
        assert "```\nmay allow\n```" in mutated
        assert "The endpoint allows cross-tenant reads." in mutated
        assert params["certainty_upgrades"] == ["may allow->allows"]

    def test_add_irrelevant_detail_records_actual_heading(self) -> None:
        text = "# T\n\n## Summary\n\nBody.\n"
        headings_seen: set[str] = set()
        for seed in range(8):
            doc = parse_report(text, fixture_id=f"canonical-noise-{seed:03d}", path="x")
            mutated, params = AddIrrelevantDetail().apply(doc, random.Random(seed))
            heading = params["appended_noise_block_heading"]
            assert heading is not None
            headings_seen.add(heading)
            assert f"## {heading}" in mutated
        assert headings_seen == {"Additional Context", "Background Information"}
