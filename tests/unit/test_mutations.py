"""Tests for mutation operators: behavior, determinism, safety."""

import random
import re
from typing import Any

import pytest

import sloplab.mutations.base as base_module
import sloplab.mutations.operators.presentation as presentation_module
from sloplab.corpus.loader import load_canonical_fixture
from sloplab.corpus.parser import parse_report
from sloplab.models.enums import Decision, ReportClass
from sloplab.mutations.base import derive_seed, get_operator, list_operators, register
from sloplab.mutations.operators.evidence import (
    RemoveAffectedVersion,
    RemoveReproductionStep,
)
from sloplab.mutations.operators.impact import (
    _INFLATION_SENTENCES,
    ImpactInflation,
    ScopeExpansion,
)
from sloplab.mutations.operators.presentation import (
    AddAuthorizationPreamble,
    ConfidenceOverstatement,
    ProfessionalizeLanguage,
    ProfessionalizeStyle,
)
from sloplab.mutations.operators.references import (
    AddIrrelevantDetail,
    ContradictObservedResult,
    FabricateReference,
    ImpossiblePrecondition,
    MisattributeCve,
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
    ProfessionalizeStyle,
    AddAuthorizationPreamble,
    ConfidenceOverstatement,
    FabricateReference,
    MisattributeCve,
    ImpossiblePrecondition,
    ContradictObservedResult,
    AddIrrelevantDetail,
)


class TestRegistry:
    def test_fourteen_operators_registered(self) -> None:
        assert len(list_operators()) == 14

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
    def test_fabricate_reference_uses_reserved_domains(self, valid_report: Any) -> None:
        doc = valid_report
        mutated, params = FabricateReference().apply(doc, random.Random(3))
        assert "### References" in mutated or "References" in params.get(
            "appended_reference_block", ""
        )
        assert validate_content_safety(mutated) == []

    def test_misattribute_cve_inserts_fake_year(self, valid_report: Any) -> None:
        doc = valid_report
        mutated, params = MisattributeCve().apply(doc, random.Random(3))
        assert "CVE-2099-" in params["inserted_attribution"]
        assert validate_content_safety(mutated) == []

    def test_impossible_precondition_adds_contradiction(self, valid_report: Any) -> None:
        doc = valid_report
        mutated, params = ImpossiblePrecondition().apply(doc, random.Random(3))
        assert params["inserted_precondition"] in mutated
        precond = _section(mutated, r"preconditions")
        assert precond is not None and params["inserted_precondition"] in precond

    def test_contradict_observed_negates_outcome(self, valid_report: Any) -> None:
        doc = valid_report
        mutated, _ = ContradictObservedResult().apply(doc, random.Random(3))
        observed = _section(mutated, r"observed")
        assert observed is not None and ("403" in observed or "could not reproduce" in observed)

    def test_add_irrelevant_detail_appends_section(self, valid_report: Any) -> None:
        doc = valid_report
        mutated, params = AddIrrelevantDetail().apply(doc, random.Random(3))
        assert len(mutated) > len(doc.raw_text)
        assert params["appended_noise_block_heading"]

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
        assert params["appended_sentence"] in _INFLATION_SENTENCES
        assert params["appended_sentence"] in mutated
        impact_text = _section(mutated, r"impact")
        assert "critical" in impact_text.lower()

    def test_impact_inflation_ignores_non_impacted_heading(self) -> None:
        text = """# T

## Non-Impacted Systems

The backup service is explicitly not impacted.

## Impact

Low impact on demo data.
"""
        doc = parse_report(text, fixture_id="canonical-impact-001", path="x")
        mutated, _ = ImpactInflation().apply(doc, random.Random(7))
        non_impacted = _section(mutated, r"^Non-Impacted Systems$")
        impact = _section(mutated, r"^Impact$")

        assert "explicitly not impacted" in non_impacted
        assert "critical" in impact.lower()

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

    def test_professionalize_collapses_exclamation_run_to_single_period(self) -> None:
        text = "# T\n\n## Summary\n\nThis is broken!! Another issue!\n"
        doc = parse_report(text, fixture_id="canonical-punct-001", path="x")
        mutated, _ = ProfessionalizeLanguage().apply(doc, random.Random(7))

        assert "!!" not in mutated
        assert ".." not in mutated
        assert "functionally incorrect." in mutated

    def test_style_and_provenance_interventions_are_separate(self) -> None:
        text = "# T\n\n## Summary\n\nThis bug doesn't work!!\n"
        doc = parse_report(text, fixture_id="canonical-style-001", path="x")
        style, _ = ProfessionalizeStyle().apply(doc, random.Random(7))
        provenance, _ = AddAuthorizationPreamble().apply(doc, random.Random(7))
        legacy, _ = ProfessionalizeLanguage().apply(doc, random.Random(7))

        assert "authorized testing" not in style
        assert "does not" in style and "defect" in style
        assert "authorized testing" in provenance
        assert "doesn't" in provenance and "bug" in provenance
        styled_doc = parse_report(style, fixture_id="canonical-style-001", path="x")
        combined, _ = AddAuthorizationPreamble().apply(styled_doc, random.Random(7))
        assert combined.rstrip("\n") == legacy.rstrip("\n")
        assert style.endswith("\n") and provenance.endswith("\n")

    def test_confidence_overstatement_hardens_hedges(self) -> None:

        text = "# T\n\n## Summary\n\nThis may allow an attacker.\n"
        doc = parse_report(text, fixture_id="canonical-t-001", path="x")
        mutated, params = ConfidenceOverstatement().apply(doc, random.Random(7))
        assert "may allow" not in mutated
        assert "allows" in mutated
        assert params["certainty_upgrades"]

    def test_confidence_overstatement_matches_likely_as_whole_word(self) -> None:
        text = (
            "# T\n\n## Summary\n\n"
            "An unlikely outcome has low likelihood. This is likely exploitable.\n"
        )
        doc = parse_report(text, fixture_id="canonical-likely-001", path="x")
        mutated, _ = ConfidenceOverstatement().apply(doc, random.Random(7))

        assert "unlikely" in mutated.lower()
        # Preserve adjacent prose as well as the boundary-sensitive "unlikely".
        assert "likelihood" in mutated.lower()
        assert "certainly exploitable" in mutated.lower()

    def test_confidence_overstatement_hyphen_safe_boundaries(self) -> None:
        """Every hedge phrase is compiled with hyphen-aware lookarounds."""
        for phrase, replacement in ConfidenceOverstatement._HEDGES:
            pattern = ConfidenceOverstatement._compile_hedge(phrase)
            assert pattern.search(phrase) is not None
            assert pattern.pattern == r"(?<![\w-])" + re.escape(phrase) + r"(?![\w-])"
            # 'likely' inside 'unlikely'/'likelihood' must not match.
            if phrase == "likely":
                assert not pattern.search("unlikely")
                assert not pattern.search("likelihood")
                assert replacement == "certainly"


HEDGE_PATTERN_EXPECTED = r"(?<" + "!" + r"[\w-])likely(?" + "!" + r"[\w-])"


class TestHedgePatternContract:
    """Binding contract ('Uygulama sözleşmesi' 2026-09-27 + 'Sözleşme düzeltmesi')."""

    def test_compiled_hedge_pattern_has_two_ascii_33_chars(self) -> None:
        export = getattr(presentation_module, "HEDGE", None)
        assert export is not None, "HEDGE must be exposed for the contract test"
        assert export.pattern.count(chr(33)) == 2
        assert export.pattern == HEDGE_PATTERN_EXPECTED

    def test_hyphen_boundary_behavior_table(self) -> None:
        """Binding behavior table through the real HEDGE export and the operator.

        Deliberately does NOT rebuild the regex locally: a locally constructed
        pattern passes even when ``src/sloplab/mutations`` regresses (review F1,
        MED). Everything here goes through ``presentation_module.HEDGE``,
        ``ConfidenceOverstatement._compile_hedge`` and ``apply``.
        """
        hedge = getattr(presentation_module, "HEDGE", None)
        assert hedge is not None, "HEDGE must be exposed for the contract test"
        assert hedge.pattern.count(chr(33)) == 2
        assert hedge.pattern == HEDGE_PATTERN_EXPECTED
        compiled = ConfidenceOverstatement._compile_hedge("likely")
        assert compiled.pattern == hedge.pattern

        yes_no = {
            "This is likely exploitable.": True,  # 'likely' transforms
            "An unlikely outcome.": False,
            "Low likelihood of loss.": False,
            "It was likely-ish today.": False,
            "The most-likely path.": False,
        }
        for text, expected in yes_no.items():
            assert bool(hedge.search(text)) is expected, text
            assert bool(compiled.search(text)) is expected, text
            doc = parse_report(
                f"# T\n\n## Summary\n\n{text}\n",
                fixture_id="canonical-hedge-table-001",
                path="x",
            )
            mutated, params = ConfidenceOverstatement().apply(doc, random.Random(7))
            if expected:
                assert "certainly" in mutated.lower(), text
            else:
                assert mutated == doc.raw_text, text
                assert params == {"note": "no hedged language found outside code fences"}


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
    @pytest.mark.parametrize(
        ("op_cls", "valid_decision"),
        [
            (RemoveReproductionStep, Decision.NEEDS_MANUAL_REVIEW),
            (RemoveAffectedVersion, Decision.ACCEPT),
            (ImpactInflation, Decision.NEEDS_MANUAL_REVIEW),
            (ScopeExpansion, Decision.NEEDS_MANUAL_REVIEW),
            (InventApiIdentifier, Decision.NEEDS_MANUAL_REVIEW),
            (ProfessionalizeLanguage, Decision.ACCEPT),
            (ProfessionalizeStyle, Decision.ACCEPT),
            (AddAuthorizationPreamble, Decision.ACCEPT),
            (ConfidenceOverstatement, Decision.ACCEPT),
            (FabricateReference, Decision.NEEDS_MANUAL_REVIEW),
            (MisattributeCve, Decision.NEEDS_MANUAL_REVIEW),
            (ImpossiblePrecondition, Decision.REJECT),
            (ContradictObservedResult, Decision.REJECT),
            (AddIrrelevantDetail, Decision.ACCEPT),
        ],
    )
    def test_expected_decisions_by_parent_class(
        self, op_cls: Any, valid_decision: Decision
    ) -> None:
        assert op_cls.spec.expected_decision(ReportClass.VALID) == valid_decision
        assert op_cls.spec.expected_decision(ReportClass.INVALID) == Decision.REJECT
        assert op_cls.spec.expected_decision(ReportClass.REVIEW) == Decision.NEEDS_MANUAL_REVIEW

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


@pytest.mark.parametrize(
    "first_name, second_name", [("foo_bar", "foo-bar"), ("foo-bar", "foo_bar")]
)
def test_registry_rejects_colliding_case_id_slugs(
    monkeypatch: pytest.MonkeyPatch, first_name: str, second_name: str
) -> None:
    from dataclasses import replace

    monkeypatch.setattr(base_module, "_REGISTRY", {})
    first, second = ProfessionalizeStyle(), ProfessionalizeStyle()
    first.spec = replace(first.spec, name=first_name)
    second.spec = replace(second.spec, name=second_name)
    register(first)
    with pytest.raises(ValueError, match="case-id slug 'foo-bar'.*already used"):
        register(second)
    assert list_operators() == [first_name]
    assert get_operator(first_name) is first


@pytest.mark.parametrize(
    "op_cls",
    [
        ProfessionalizeStyle,
        ProfessionalizeLanguage,
        ConfidenceOverstatement,
        AddAuthorizationPreamble,
    ],
)
@pytest.mark.parametrize("fence", ["~~~", "~~~~", "```", "````"])
def test_presentation_operators_preserve_fenced_code(op_cls: Any, fence: str) -> None:
    other = "```" if fence.startswith("~") else "~~~"
    code = (
        f"{fence}text\n# fake title\ncapture( 'payload-1' ) may allow a bug!!\n"
        f"{other}\n{fence[:3]}not a closer\n{fence[:-1]}\n# another fake title\n{fence}\n"
    )
    doc = parse_report(
        code + "# Real title\n\nthis bug may allow access!!\n", fixture_id="fenced", path="x"
    )
    mutated, _ = op_cls().apply(doc, random.Random(7))
    assert mutated.startswith(code)
    if op_cls in (ProfessionalizeLanguage, AddAuthorizationPreamble):
        assert mutated.index("authorized testing") > mutated.index("# Real title")
    if op_cls is ConfidenceOverstatement:
        assert "this bug allows access" in mutated
    if op_cls in (ProfessionalizeStyle, ProfessionalizeLanguage):
        assert "This defect may allow access." in mutated


@pytest.mark.parametrize(
    "phrase, replacement",
    [
        ("may allow", "allows"),
        ("might allow", "allows"),
        ("could potentially allow", "allows"),
        ("could allow", "allows"),
        ("possibly", "certainly"),
        ("potentially", "definitively"),
        ("appears to be", "is"),
        ("appears to", "does"),
        ("suggesting that", "proving that"),
        ("likely", "certainly"),
        ("unclear whether", "confirmed that"),
    ],
)
@pytest.mark.parametrize(
    "case_style",
    ["lowercase", "sentence-initial", "title", "all-caps", "mixed-lowercase", "mixed-capitalised"],
)
def test_confidence_overstatement_preserves_case(
    phrase: str, replacement: str, case_style: str
) -> None:
    upgrade = f"{phrase}->{replacement}"
    if case_style == "sentence-initial":
        phrase, replacement = phrase.capitalize(), replacement.capitalize()
    elif case_style == "title":
        phrase, replacement = phrase.title(), replacement.capitalize()
    elif case_style == "all-caps":
        phrase, replacement = phrase.upper(), replacement.upper()
    elif case_style == "mixed-lowercase":
        phrase = phrase[0] + phrase[1:].upper()
    elif case_style == "mixed-capitalised":
        phrase = "".join(
            char.upper() if index % 2 == 0 else char for index, char in enumerate(phrase)
        )
        replacement = replacement.capitalize()
    fenced = f"```text\n{phrase} access.\n```\n\n"
    text = f"# T\n\n{fenced}{phrase} access."
    doc = parse_report(text, fixture_id="certainty", path="x")

    mutated, params = ConfidenceOverstatement().apply(doc, random.Random(7))

    assert mutated == f"# T\n\n{fenced}{replacement} access."
    assert params["certainty_upgrades"] == [upgrade]


@pytest.mark.parametrize(
    "op_cls, expected",
    [
        (
            ProfessionalizeLanguage,
            "# T\n\nThis report summarizes findings obtained exclusively through authorized "
            "testing of a sandboxed demo environment.\n\nThis Defect is Functionally incorrect.",
        ),
        (ProfessionalizeStyle, "# T\n\nThis Defect is Functionally incorrect."),
    ],
)
def test_professionalization_preserves_historical_all_caps_output(
    op_cls: Any, expected: str
) -> None:
    doc = parse_report("# T\n\nThis BUG is BROKEN.", fixture_id="register", path="x")

    mutated, params = op_cls().apply(doc, random.Random(7))

    assert mutated == expected
    assert params["transformations"] == ["register:bug", "register:broken"]


def test_confidence_overstatement_uses_grammatical_copula() -> None:
    doc = parse_report("# T\n\nThe flag appears to be set.\n", fixture_id="copula", path="x")
    mutated, params = ConfidenceOverstatement().apply(doc, random.Random(7))
    assert "The flag is set." in mutated
    assert params["certainty_upgrades"] == ["appears to be->is"]


def test_confidence_overstatement_preserves_non_copula_rewrite() -> None:
    doc = parse_report(
        "# T\n\nThe flaw appears to allow access.\n", fixture_id="non-copula", path="x"
    )
    mutated, params = ConfidenceOverstatement().apply(doc, random.Random(7))
    assert "The flaw does allow access." in mutated
    assert params["certainty_upgrades"] == ["appears to->does"]
