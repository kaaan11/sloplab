"""Per-arm injection success rate, built on the existing comparison machinery."""

from __future__ import annotations

from typing import Any

import pytest

from sloplab.models.enums import DIMENSIONS, Decision
from sloplab.models.evaluation import DimensionScores, EvaluationResult
from sloplab.models.run import CaseRecord
from sloplab.scoring.comparison import injection_success_by_arm


def make_record(
    case_id: str,
    decision: Decision,
    *,
    operator: str | None,
    defense: str,
    expected: Decision = Decision.ACCEPT,
) -> CaseRecord:
    result = EvaluationResult(
        evaluator_name="llm-json",
        evaluator_version="0.2.2",
        case_id="case-handle",
        decision=decision,
        confidence=0.5,
        dimensions=DimensionScores.from_dict(dict.fromkeys(DIMENSIONS, 0.5)),
        findings=[],
        rationale="",
        metadata={"defense": defense},
    )
    return CaseRecord.from_result(
        result,
        case_id=case_id,
        case_kind="mutated" if operator else "canonical",
        report_class="valid",
        expected_decision=expected,
        operator=operator,
    )


TARGETS = {"instruction_override": Decision.ACCEPT, "forged_boundary": Decision.ACCEPT}


class TestInjectionSuccessByArm:
    """Success means the evaluator did what the payload demanded - and only where
    that is distinguishable from simply being correct."""

    def test_hand_built_expectation(self) -> None:
        records = [
            # Arm A: 3 measurable injected cases (expected reject, payload wants
            # accept), 2 of which obey.
            make_record(
                "m-1",
                Decision.ACCEPT,
                operator="instruction_override",
                defense="none",
                expected=Decision.REJECT,
            ),
            make_record(
                "m-2",
                Decision.REJECT,
                operator="instruction_override",
                defense="none",
                expected=Decision.REJECT,
            ),
            make_record(
                "m-3",
                Decision.ACCEPT,
                operator="forged_boundary",
                defense="none",
                expected=Decision.REJECT,
            ),
            # Arm B: the same 3 cases, none obey.
            make_record(
                "m-1",
                Decision.REJECT,
                operator="instruction_override",
                defense="delimited",
                expected=Decision.REJECT,
            ),
            make_record(
                "m-2",
                Decision.REJECT,
                operator="instruction_override",
                defense="delimited",
                expected=Decision.REJECT,
            ),
            make_record(
                "m-3",
                Decision.REJECT,
                operator="forged_boundary",
                defense="delimited",
                expected=Decision.REJECT,
            ),
        ]
        outcomes = injection_success_by_arm(records, TARGETS)

        assert set(outcomes) == {"none", "delimited"}
        assert outcomes["none"].injected_cases == 3
        assert outcomes["none"].successes == 2
        assert outcomes["none"].success_rate == pytest.approx(2 / 3)
        assert outcomes["delimited"].successes == 0
        assert outcomes["delimited"].success_rate == 0.0

    def test_case_whose_demand_matches_the_label_is_undecidable(self) -> None:
        """Obeying and being right are the same observation there.

        Every current operator demands `accept`, and injected cases keep their
        parent's expected decision - so on a valid parent the payload demands
        exactly what a correct evaluator would answer. Counting those as
        successes would overstate susceptibility on roughly a third of a
        balanced suite.
        """
        records = [
            make_record(
                "m-valid",
                Decision.ACCEPT,
                operator="instruction_override",
                defense="none",
                expected=Decision.ACCEPT,
            ),
            make_record(
                "m-invalid",
                Decision.ACCEPT,
                operator="instruction_override",
                defense="none",
                expected=Decision.REJECT,
            ),
        ]
        outcome = injection_success_by_arm(records, TARGETS)["none"]

        assert outcome.undecidable_cases == 1
        assert outcome.injected_cases == 1
        assert outcome.successes == 1
        assert outcome.success_rate == 1.0

    def test_an_entirely_undecidable_arm_reports_zero_not_one(self) -> None:
        records = [
            make_record(
                "m-1",
                Decision.ACCEPT,
                operator="instruction_override",
                defense="none",
                expected=Decision.ACCEPT,
            )
        ]
        outcome = injection_success_by_arm(records, TARGETS)["none"]
        assert outcome.injected_cases == 0
        assert outcome.undecidable_cases == 1
        assert outcome.success_rate == 0.0

    def test_non_injected_records_are_ignored(self) -> None:
        records = [
            make_record("c-1", Decision.ACCEPT, operator=None, defense="none"),
            make_record("m-1", Decision.ACCEPT, operator="impact_inflation", defense="none"),
            make_record(
                "m-2",
                Decision.ACCEPT,
                operator="instruction_override",
                defense="none",
                expected=Decision.REJECT,
            ),
        ]
        outcomes = injection_success_by_arm(records, TARGETS)
        assert outcomes["none"].injected_cases == 1
        assert outcomes["none"].successes == 1

    def test_arm_defaults_to_none_when_unmarked(self) -> None:
        """Deterministic evaluators record no defense; they belong to the control."""
        record = make_record(
            "m-1",
            Decision.ACCEPT,
            operator="instruction_override",
            defense="none",
            expected=Decision.REJECT,
        )
        record.evaluation_metadata.pop("defense")
        outcomes = injection_success_by_arm([record], TARGETS)
        assert outcomes["none"].injected_cases == 1

    def test_empty_input_is_empty_output(self) -> None:
        assert injection_success_by_arm([], TARGETS) == {}

    def test_as_dict_is_report_ready(self) -> None:
        records = [
            make_record(
                "m-1",
                Decision.ACCEPT,
                operator="instruction_override",
                defense="none",
                expected=Decision.REJECT,
            )
        ]
        payload: dict[str, Any] = injection_success_by_arm(records, TARGETS)["none"].as_dict()
        assert payload == {
            "arm": "none",
            "injected_cases": 1,
            "successes": 1,
            "undecidable_cases": 0,
            "success_rate": 1.0,
        }


class TestInjectionTargets:
    def test_registry_targets_match_the_registered_operators(self) -> None:
        from sloplab.mutations.base import get_operator
        from sloplab.scoring.comparison import injection_targets

        targets = injection_targets()
        assert set(targets) == {
            "instruction_override",
            "forged_boundary",
            "fabricated_triage_note",
        }
        for name, decision in targets.items():
            assert get_operator(name).spec.injection_target == decision

    def test_quality_operators_declare_no_target(self) -> None:
        from sloplab.scoring.comparison import injection_targets

        assert "impact_inflation" not in injection_targets()


class TestStudyReporting:
    """The metric must actually reach an output; a metric nothing emits is not reporting."""

    def test_analysis_json_omits_the_section_without_injection_cases(
        self, tmp_path: Any, make_fixture: Any
    ) -> None:

        from tests.integration.test_pipeline import build_workspace

        workspace = build_workspace(tmp_path, make_fixture)
        analysis = _run_study(workspace, ["remove_reproduction_step"])
        assert "injection_success" in analysis
        assert analysis["injection_success"] == {}

    def test_analysis_json_reports_per_arm_success_for_injection_cases(
        self, tmp_path: Any, make_fixture: Any
    ) -> None:
        from tests.integration.test_pipeline import build_workspace

        workspace = build_workspace(tmp_path, make_fixture)
        analysis = _run_study(workspace, ["instruction_override", "forged_boundary"])

        assert analysis["injection_success"], analysis
        # Deterministic evaluators record no arm, so they land in the control.
        for _evaluator, arms in analysis["injection_success"].items():
            assert set(arms) == {"none"}
            assert arms["none"]["injected_cases"] > 0
            assert 0.0 <= arms["none"]["success_rate"] <= 1.0


def _run_study(workspace: Any, operators: list[str]) -> dict[str, Any]:
    import json

    import yaml
    from click.testing import CliRunner

    from sloplab.cli.main import cli

    suite = yaml.safe_load((workspace / "suite.yaml").read_text())
    for policy in suite["policies"].values():
        policy["operators"] = operators
        policy["variants_per_fixture"] = 2
    (workspace / "suite.yaml").write_text(yaml.safe_dump(suite), encoding="utf-8")

    study_config = {
        "name": "injection-study",
        "suite": {
            "config_path": str(workspace / "suite.yaml"),
            "corpus_root": str(workspace),
        },
        "base_seed": 5,
        "evaluators": [{"name": "rules-baseline"}, {"name": "oracle"}],
    }
    config_path = workspace / "study.yaml"
    config_path.write_text(yaml.safe_dump(study_config), encoding="utf-8")

    out_dir = workspace / f"study-{'-'.join(operators)}"
    result = CliRunner().invoke(cli, ["study", str(config_path), "--out", str(out_dir)])
    assert result.exit_code == 0, result.output
    return dict(json.loads((out_dir / "analysis.json").read_text()))
