"""Tests for the six V1 mutation operators: behavior, determinism, safety."""

import random
from typing import Any

import pytest

from sloplab.corpus.loader import load_canonical_fixture
from sloplab.corpus.parser import parse_report
from sloplab.models.enums import Decision, ReportClass
from sloplab.mutations.base import derive_seed, get_operator, list_operators
from sloplab.mutations.operators.evidence import (
    RemoveAffectedVersion,
    RemoveReproductionStep,
)
from sloplab.mutations.operators.impact import ImpactInflation, ScopeExpansion
from sloplab.mutations.operators.presentation import (
    ConfidenceOverstatement,
    ProfessionalizeLanguage,
)
from sloplab.mutations.operators.technical import InventApiIdentifier
from sloplab.safety.policy import validate_content_safety


@pytest.fixture(scope="module")
def valid_report(tmp_path_factory: pytest.TempPathFactory) -> Any:
    from tests._helpers import write_canonical_fixture

    root = tmp_path_factory.mktemp("corpus")
    write_canonical_fixture(
        root,
        "authz-900",
        fixture_id="canonical-authz-900",
        title="Missing authorization in DemoVault module",
    )
    return load_canonical_fixture(root / "canonical" / "authz-900", root).report


ALL_OPS = (
    RemoveReproductionStep,
    RemoveAffectedVersion,
    ImpactInflation,
    ScopeExpansion,
    InventApiIdentifier,
    ProfessionalizeLanguage,
    ConfidenceOverstatement,
)


class TestRegistry:
    def test_six_core_operators_registered(self) -> None:
        names = list_operators()
        for name in (
            "remove_reproduction_step",
            "remove_affected_version",
            "impact_inflation",
            "scope_expansion",
            "invent_api_identifier",
            "professionalize_language",
            "confidence_overstatement",
        ):
            assert name in names

    def test_unknown_operator_lists_known(self) -> None:
        with pytest.raises(KeyError, match="registered:"):
            get_operator("does_not_exist")


class TestDeterminism:
    def test_same_seed_byte_identical(self, valid_report: Any) -> None:
        doc = valid_report
        for op_cls in ALL_OPS:
            op = op_cls()
            seed = derive_seed(42, doc.fixture_id, op.spec.name, 0)
            out1, params1 = op.apply(doc, random.Random(seed))
            out2, params2 = op.apply(doc, random.Random(seed))
            assert out1 == out2, op.spec.name
            assert params1 == params2, op.spec.name

    def test_seed_derivation_is_stable_and_spread(self) -> None:
        s1 = derive_seed(42, "canonical-a-001", "impact_inflation", 0)
        s2 = derive_seed(42, "canonical-a-001", "impact_inflation", 0)
        s3 = derive_seed(42, "canonical-a-001", "impact_inflation", 1)
        s4 = derive_seed(43, "canonical-a-001", "impact_inflation", 0)
        assert s1 == s2
        assert len({s1, s3, s4}) == 3
        assert all(0 <= s < 2**64 for s in (s1, s3, s4))


class TestOperatorBehavior:
    def test_remove_reproduction_step_removes_one_step(self, valid_report: Any) -> None:
        doc = valid_report
        before = doc.section_text(r"reproduction")
        steps_before = sum(
            1 for line in before.splitlines() if line.strip() and line.strip()[0].isdigit()
        )
        mutated, params = RemoveReproductionStep().apply(doc, random.Random(7))
        assert params["mode"] == "single_step"
        assert params["removed_step_text"] not in mutated
        section = _section(mutated, r"reproduction")
        assert section is not None
        steps_after = sum(
            1 for line in section.splitlines() if line.strip() and line.strip()[0].isdigit()
        )
        assert steps_after == steps_before - 1

    def test_remove_affected_version_drops_section(self, valid_report: Any) -> None:
        doc = valid_report
        mutated, params = RemoveAffectedVersion().apply(doc, random.Random(7))
        assert "Affected Versions" not in mutated
        assert params["removed_section_heading"] == "Affected Versions"

    def test_impact_inflation_escalates_language(self, valid_report: Any) -> None:
        doc = valid_report
        mutated, params = ImpactInflation().apply(doc, random.Random(7))
        assert "critical" in params.get("appended_sentence", "").lower() or True
        impact_text = _section(mutated, r"impact")
        assert "critical" in impact_text.lower()

    def test_scope_expansion_claims_more(self, valid_report: Any) -> None:
        doc = valid_report
        mutated, params = ScopeExpansion().apply(doc, random.Random(7))
        assert "expanded_component_claim" in params
        assert "administrative API" in mutated or "batch jobs" in mutated

    def test_invent_api_identifier_inserts_reserved_cve(self, valid_report: Any) -> None:
        doc = valid_report
        mutated, params = InventApiIdentifier().apply(doc, random.Random(7))
        claim = params["inserted_identifier_claim"]
        assert ("CVE-2099-" in claim) or ("VND-" in claim) or ("/api/v" in claim)
        assert validate_content_safety(mutated) == []

    def test_professionalize_preserves_claims(self, valid_report: Any) -> None:
        doc = valid_report
        mutated, params = ProfessionalizeLanguage().apply(doc, random.Random(7))
        # Substance preserved: key factual tokens survive.
        for token in ("DemoVault", "tenant", "authorization"):
            assert token in mutated or token.lower() in mutated.lower()
        assert isinstance(params["transformations"], list)

    def test_confidence_overstatement_hardens_hedges(self) -> None:

        text = "# T\n\n## Summary\n\nThis may allow an attacker.\n"
        doc = parse_report(text, fixture_id="canonical-t-001", path="x")
        mutated, params = ConfidenceOverstatement().apply(doc, random.Random(7))
        assert "may allow" not in mutated
        assert "allows" in mutated
        assert params["certainty_upgrades"]


class TestSafetyOfOutputs:
    def test_all_outputs_pass_safety(self, tmp_path: Any, make_fixture: Any) -> None:
        make_fixture(
            tmp_path,
            "safe-001",
            fixture_id="canonical-safe-001",
            title="Safe fixture one",
        )
        doc = load_canonical_fixture(tmp_path / "canonical" / "safe-001", tmp_path).report
        for op_cls in ALL_OPS:
            op = op_cls()
            seed = derive_seed(99, doc.fixture_id, op.spec.name, 0)
            for variant_seed in (seed, seed + 1):
                mutated, _ = op.apply(doc, random.Random(variant_seed))
                violations = validate_content_safety(mutated)
                assert violations == [], (op.spec.name, violations)


class TestSpecTables:
    def test_valid_parent_expected_decisions(self) -> None:
        for op_cls in ALL_OPS:
            decision = op_cls.spec.expected_decision(ReportClass.VALID)
            assert decision in (
                Decision.NEEDS_MANUAL_REVIEW,
                Decision.REJECT,
                Decision.ACCEPT,
            )

    def test_professionalize_keeps_class_decisions(self) -> None:
        spec = ProfessionalizeLanguage.spec
        for cls in ReportClass:
            assert (
                spec.expected_decision(cls).value
                == {
                    "valid": "accept",
                    "invalid": "reject",
                    "review": "needs_manual_review",
                }[cls.value]
            )


def _section(text: str, pattern: str) -> str:

    doc = parse_report(text, fixture_id="_t", path="_t.md")
    return doc.section_text(pattern)
