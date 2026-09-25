"""Jev typed request/response mapping (A-004). Offline: the socket guard is autouse."""

from __future__ import annotations

import copy
import hashlib
import math
import re
from pathlib import Path

import pytest

from sloplab.evaluators.jev.failures import (
    RESPONSE_BAD_DISTRIBUTION,
    RESPONSE_UNKNOWN_OPTION,
    JevResponseError,
)
from sloplab.evaluators.jev.mapping import (
    CRITERIA_SOURCE,
    DECISION_CRITERIA,
    DECISION_ORDER,
    DIMENSION_ANCHORS,
    SCORE_GUIDANCE,
    TRIAGE_V1,
    DecisionCriteria,
    LabelMap,
    build_request,
    decode_response,
    encode_request,
    validate_model_id,
)
from sloplab.models.enums import DIMENSIONS, Decision
from tests._jev_fakes import REPORT_TEXT, block_network, valid_body

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL = "typesafe/jev-1.13"

#: SHA-256 of the identity-map wire bytes for REPORT_TEXT. Changing the mapping,
#: criteria, or anchors must be a deliberate, versioned change that updates this.
WIRE_SNAPSHOT_SHA256 = "43b98e7d275d71606ecaa03b93d465e0c367264f81bac85cb1ee3f0a2fe2910a"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    block_network(monkeypatch)


def _all_label_maps() -> list[LabelMap]:
    maps = [LabelMap.identity()]
    maps += [LabelMap.permuted(seed) for seed in range(8)]
    maps += [LabelMap.random_tokens(seed) for seed in range(8)]
    return maps


def _triage_v1_definitions() -> dict[str, str]:
    """Parse the three decision bullets of triage-v1.md, joining wrapped lines."""
    text = (REPO_ROOT / CRITERIA_SOURCE).read_text(encoding="utf-8")
    pattern = re.compile(
        r'^- "(accept|reject|needs_manual_review)": (.*?)(?=^- "|^\s*$)', re.S | re.M
    )
    return {m.group(1): " ".join(m.group(2).split()) for m in pattern.finditer(text)}


class TestRequestSnapshot:
    """Acceptance 1: three options, five scores, ``state`` = report text."""

    def test_body_shape(self) -> None:
        body = build_request(REPORT_TEXT, model_id=MODEL, label_map=LabelMap.identity())
        assert list(body) == ["model", "state", "questions"]
        assert body["model"] == MODEL
        assert body["state"] == REPORT_TEXT
        questions = body["questions"]
        assert list(questions) == ["decision"] + [f"dim_{d}" for d in DIMENSIONS]

        decision = questions["decision"]
        assert set(decision) == {"type", "instructions", "criteria"}
        assert decision["type"] == "choice"
        assert list(decision["criteria"]) == ["accept", "reject", "needs_manual_review"]

        for dimension in DIMENSIONS:
            question = questions[f"dim_{dimension}"]
            assert set(question) == {"type", "instructions", "criteria"}
            assert question["type"] == "score"
            assert question["criteria"] == list(DIMENSION_ANCHORS[dimension].anchors)
            assert 2 <= len(question["criteria"]) <= 10
            # Question ids are invisible to the model: the meaning is in the text.
            assert question["instructions"].endswith(SCORE_GUIDANCE)

    def test_state_is_exact_report_text(self) -> None:
        tricky = '# Rapor\n\n{report_text} {} "quotes" ünicode\t\n'
        body = build_request(tricky, model_id=MODEL, label_map=LabelMap.identity())
        assert body["state"] == tricky
        assert isinstance(body["state"], str)

    def test_wire_bytes_snapshot(self) -> None:
        body = build_request(REPORT_TEXT, model_id=MODEL, label_map=LabelMap.identity())
        assert hashlib.sha256(encode_request(body)).hexdigest() == WIRE_SNAPSHOT_SHA256

    def test_build_is_deterministic(self) -> None:
        a = build_request(REPORT_TEXT, model_id=MODEL, label_map=LabelMap.permuted(3))
        b = build_request(REPORT_TEXT, model_id=MODEL, label_map=LabelMap.permuted(3))
        assert encode_request(a) == encode_request(b)


class TestCriteriaDerivation:
    """Acceptance 2: criteria are the triage-v1 definitions, string-equal."""

    def test_criteria_match_triage_v1_verbatim(self) -> None:
        definitions = _triage_v1_definitions()
        assert set(definitions) == {d.value for d in Decision}
        for decision in Decision:
            assert DECISION_CRITERIA[decision] == definitions[decision.value]

    def test_request_carries_the_derived_criteria(self) -> None:
        definitions = _triage_v1_definitions()
        body = build_request(REPORT_TEXT, model_id=MODEL, label_map=LabelMap.identity())
        assert body["questions"]["decision"]["criteria"] == definitions

    def test_score_guidance_is_a_triage_v1_excerpt(self) -> None:
        text = " ".join((REPO_ROOT / CRITERIA_SOURCE).read_text(encoding="utf-8").split())
        assert SCORE_GUIDANCE.removeprefix("Score ") in text


class TestLabelBinding:
    """Acceptance 3: only keys change; descriptions stay byte-identical; inverse is exact."""

    def test_descriptions_byte_identical_across_maps(self) -> None:
        reference = build_request(REPORT_TEXT, model_id=MODEL, label_map=LabelMap.identity())
        ref_criteria = reference["questions"]["decision"]["criteria"]
        ref_values = [v.encode("utf-8") for v in ref_criteria.values()]
        for label_map in _all_label_maps()[1:]:
            body = build_request(REPORT_TEXT, model_id=MODEL, label_map=label_map)
            criteria = body["questions"]["decision"]["criteria"]
            assert [v.encode("utf-8") for v in criteria.values()] == ref_values
            assert list(criteria) != list(ref_criteria)  # keys did change
            # Wire level: renaming the reference keys reproduces the exact bytes,
            # so nothing but the option keys differs.
            renamed = copy.deepcopy(reference)
            renamed["questions"]["decision"]["criteria"] = {
                label_map.option_for(Decision(k)): v for k, v in ref_criteria.items()
            }
            assert encode_request(body) == encode_request(renamed)

    def test_permutation_swaps_names_not_descriptions(self) -> None:
        label_map = LabelMap.permuted(0)
        assert set(label_map.keys()) == {d.value for d in Decision}
        assert label_map != LabelMap.identity()
        criteria = build_request(REPORT_TEXT, model_id=MODEL, label_map=label_map)["questions"][
            "decision"
        ]["criteria"]
        for key, description in criteria.items():
            assert description == DECISION_CRITERIA[label_map.resolve(key)]

    def test_inverse_mapping_yields_the_bound_decision(self) -> None:
        for label_map in _all_label_maps():
            for decision in DECISION_ORDER:
                assert label_map.resolve(label_map.option_for(decision)) is decision
                decoded = decode_response(valid_body(label_map, selected=decision), label_map)
                assert decoded.decision is decision
                assert decoded.selected_option == label_map.option_for(decision)

    def test_swapped_name_resolves_by_binding_not_by_spelling(self) -> None:
        swapped = LabelMap(
            kind="permutation",
            bindings=(
                ("reject", Decision.ACCEPT),
                ("accept", Decision.REJECT),
                ("needs_manual_review", Decision.NEEDS_MANUAL_REVIEW),
            ),
            seed=None,
        )
        body = valid_body(swapped, selected=Decision.REJECT)
        assert body["answers"]["decision"]["choice"] == "accept"
        decoded = decode_response(body, swapped)
        assert decoded.decision is Decision.REJECT
        assert decoded.decision_probabilities == {
            "accept": 0.2,
            "reject": 0.1,
            "needs_manual_review": 0.7,
        }

    def test_generators_are_seeded_and_deterministic(self) -> None:
        assert LabelMap.permuted(5) == LabelMap.permuted(5)
        assert LabelMap.random_tokens(5) == LabelMap.random_tokens(5)
        assert len({LabelMap.random_tokens(s).keys() for s in range(8)}) == 8
        for seed in range(8):
            tokens = LabelMap.random_tokens(seed).keys()
            assert not set(tokens) & {d.value for d in Decision}
            assert all(re.fullmatch(r"[a-z]{6}", t) for t in tokens)
            assert LabelMap.permuted(seed) != LabelMap.identity()

    def test_label_map_ids(self) -> None:
        assert LabelMap.identity().id == "identity"
        assert LabelMap.permuted(1).id.startswith("permutation:seed=1:")
        assert LabelMap.random_tokens(1).id.startswith("tokens:seed=1:")
        ids = {m.id for m in _all_label_maps()}
        distinct = {m.bindings for m in _all_label_maps()}
        assert len(ids) >= len(distinct)

    @pytest.mark.parametrize(
        "bindings",
        [
            (("a", Decision.ACCEPT), ("a", Decision.REJECT), ("c", Decision.NEEDS_MANUAL_REVIEW)),
            (("a", Decision.REJECT), ("b", Decision.ACCEPT), ("c", Decision.NEEDS_MANUAL_REVIEW)),
            (("a", Decision.ACCEPT), ("b", Decision.REJECT)),
            (("", Decision.ACCEPT), ("b", Decision.REJECT), ("c", Decision.NEEDS_MANUAL_REVIEW)),
        ],
    )
    def test_invalid_label_maps_rejected(self, bindings: tuple[tuple[str, Decision], ...]) -> None:
        with pytest.raises(ValueError):
            LabelMap(kind="custom", bindings=bindings)


class TestModelPinning:
    """Acceptance 4: floating ids are refused."""

    @pytest.mark.parametrize(
        "model_id",
        [
            "jev-latest",
            "~typesafe/jev-latest",
            "typesafe/jev-latest",
            "typesafe/Jev-LATEST",
            "~typesafe/jev-1.13",
            "",
            " typesafe/jev-1.13",
        ],
    )
    def test_floating_or_bad_ids_rejected(self, model_id: str) -> None:
        with pytest.raises(ValueError):
            validate_model_id(model_id)
        with pytest.raises(ValueError):
            build_request(REPORT_TEXT, model_id=model_id, label_map=LabelMap.identity())

    @pytest.mark.parametrize("model_id", ["typesafe/jev-1.13", "jev-1.13.0"])
    def test_pinned_ids_accepted(self, model_id: str) -> None:
        assert validate_model_id(model_id) == model_id


class TestDecode:
    def test_dimension_normalization_is_score_over_top_level(self) -> None:
        decoded = decode_response(valid_body(), LabelMap.identity())
        for index, dimension in enumerate(DIMENSIONS):
            score = 0.5 + 0.25 * index
            assert decoded.dimension_scores[dimension] == pytest.approx(score)
            assert decoded.dimension_values[dimension] == pytest.approx(score / 2)

    def test_unknown_probability_key_is_unknown_option(self) -> None:
        body = valid_body()
        body["answers"]["decision"]["probabilities"]["maybe"] = 0.0
        with pytest.raises(JevResponseError) as info:
            decode_response(body, LabelMap.identity())
        assert info.value.code == RESPONSE_UNKNOWN_OPTION

    def test_missing_probability_key_is_bad_distribution(self) -> None:
        body = valid_body()
        del body["answers"]["decision"]["probabilities"]["reject"]
        with pytest.raises(JevResponseError) as info:
            decode_response(body, LabelMap.identity())
        assert info.value.code == RESPONSE_BAD_DISTRIBUTION

    def test_sum_tolerance_edges(self) -> None:
        # Three options: rounding alone can move the sum by up to 0.015.
        ok = valid_body(
            probabilities={
                Decision.ACCEPT: 0.2,
                Decision.REJECT: 0.1,
                Decision.NEEDS_MANUAL_REVIEW: 0.71,
            }
        )
        decoded = decode_response(ok, LabelMap.identity())
        assert math.fsum(decoded.decision_probabilities.values()) == pytest.approx(1.0)
        assert decoded.decision_probabilities["needs_manual_review"] == pytest.approx(0.71 / 1.01)
        bad = valid_body(
            probabilities={
                Decision.ACCEPT: 0.2,
                Decision.REJECT: 0.1,
                Decision.NEEDS_MANUAL_REVIEW: 0.72,
            }
        )
        with pytest.raises(JevResponseError) as info:
            decode_response(bad, LabelMap.identity())
        assert info.value.code == RESPONSE_BAD_DISTRIBUTION

    def test_rounded_score_distribution_is_renormalized(self) -> None:
        body = valid_body()
        dim = next(iter(DIMENSIONS))
        levels = body["answers"][f"dim_{dim}"]["probabilities"]
        first = next(iter(levels))
        levels[first] = levels[first] + 0.01
        decoded = decode_response(body, LabelMap.identity())
        assert math.fsum(decoded.dimension_probabilities[dim].values()) == pytest.approx(1.0)

    def test_bool_is_not_a_number(self) -> None:
        body = valid_body()
        body["answers"]["dim_reproducibility"]["score"] = True
        with pytest.raises(JevResponseError):
            decode_response(body, LabelMap.identity())


class TestOptionOrder:
    """A-007 L3: option order is a separate stimulus from option names."""

    def test_default_order_is_canonical(self) -> None:
        body = build_request("r", model_id="typesafe/jev-1.13", label_map=LabelMap.identity())
        assert list(body["questions"]["decision"]["criteria"]) == [d.value for d in DECISION_ORDER]

    def test_reversed_order_keeps_descriptions_bound(self) -> None:
        order = tuple(reversed(DECISION_ORDER))
        base = build_request("r", model_id="typesafe/jev-1.13", label_map=LabelMap.identity())
        flipped = build_request(
            "r", model_id="typesafe/jev-1.13", label_map=LabelMap.identity(), option_order=order
        )
        criteria = flipped["questions"]["decision"]["criteria"]
        assert list(criteria) == [d.value for d in order]
        assert criteria == base["questions"]["decision"]["criteria"]
        assert encode_request(flipped) != encode_request(base)

    @pytest.mark.parametrize(
        "order",
        [
            (Decision.ACCEPT, Decision.REJECT),
            (Decision.ACCEPT, Decision.ACCEPT, Decision.REJECT),
            (Decision.ACCEPT, Decision.REJECT, Decision.NEEDS_MANUAL_REVIEW, Decision.ACCEPT),
        ],
    )
    def test_invalid_orders_rejected(self, order: tuple[Decision, ...]) -> None:
        with pytest.raises(ValueError, match="option_order"):
            build_request(
                "r", model_id="typesafe/jev-1.13", label_map=LabelMap.identity(), option_order=order
            )


class TestDecisionCriteria:
    """Criteria are a versioned stimulus; triage-v1 stays the default."""

    def test_default_is_triage_v1(self) -> None:
        body = build_request("r", model_id="typesafe/jev-1.13", label_map=LabelMap.identity())
        assert TRIAGE_V1.version == "triage-v1"
        assert body["questions"]["decision"]["criteria"] == {
            d.value: DECISION_CRITERIA[d] for d in DECISION_ORDER
        }

    def test_custom_criteria_replace_only_descriptions(self) -> None:
        custom = DecisionCriteria(
            version="exp-1", texts={d: f"describes {d.value}" for d in DECISION_ORDER}
        )
        base = build_request("r", model_id="typesafe/jev-1.13", label_map=LabelMap.identity())
        body = build_request(
            "r", model_id="typesafe/jev-1.13", label_map=LabelMap.identity(), criteria=custom
        )
        assert body["questions"]["decision"]["criteria"] == {
            d.value: f"describes {d.value}" for d in DECISION_ORDER
        }
        base["questions"]["decision"].pop("criteria")
        body["questions"]["decision"].pop("criteria")
        assert body == base

    def test_criteria_bind_to_decisions_under_permutation(self) -> None:
        custom = DecisionCriteria(
            version="exp-1", texts={d: f"describes {d.value}" for d in DECISION_ORDER}
        )
        label_map = LabelMap.permuted(seed=0)
        body = build_request(
            "r", model_id="typesafe/jev-1.13", label_map=label_map, criteria=custom
        )
        for key, text in body["questions"]["decision"]["criteria"].items():
            assert text == f"describes {label_map.resolve(key).value}"

    def test_sha256_is_stable_and_version_sensitive_only_by_text(self) -> None:
        texts = {d: f"t {d.value}" for d in DECISION_ORDER}
        a = DecisionCriteria(version="a", texts=texts)
        b = DecisionCriteria(version="b", texts=dict(texts))
        assert a.sha256 == b.sha256
        assert a.sha256 != TRIAGE_V1.sha256

    @pytest.mark.parametrize(
        "texts",
        [
            {Decision.ACCEPT: "x", Decision.REJECT: "y"},
            {Decision.ACCEPT: "x", Decision.REJECT: "y", Decision.NEEDS_MANUAL_REVIEW: " "},
        ],
    )
    def test_invalid_criteria_rejected(self, texts: dict[Decision, str]) -> None:
        with pytest.raises(ValueError, match="criteria"):
            DecisionCriteria(version="bad", texts=texts)

    def test_blank_version_rejected(self) -> None:
        with pytest.raises(ValueError, match="version"):
            DecisionCriteria(version=" ", texts={d: "x" for d in DECISION_ORDER})
