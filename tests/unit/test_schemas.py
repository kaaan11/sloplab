"""Schema validation tests for manifests and evaluation results."""

from typing import Any

import pytest
from pydantic import ValidationError

from sloplab.models import (
    DIMENSIONS,
    Decision,
    DimensionScores,
    EvaluationResult,
    GroundTruth,
    MutationManifest,
    ReportClass,
    SuiteConfig,
    canonical_expected_decision,
)


def canonical_manifest_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "canonical-authz-001",
        "title": "Missing authorization check in sample object lookup",
        "report_class": "valid",
        "ground_truth": {
            "reproducible": True,
            "impact_class": "medium",
            "required_evidence": ["reproduction_steps"],
        },
        "report": {"path": "canonical/authz-001/report.md"},
    }
    data.update(overrides)
    return data


class TestCanonicalManifest:
    def test_valid_manifest_loads(self) -> None:
        from sloplab.models import CanonicalManifest

        manifest = CanonicalManifest.model_validate(canonical_manifest_data())
        assert manifest.id == "canonical-authz-001"
        assert manifest.license == "CC0-1.0"
        assert manifest.expected_decision() == Decision.ACCEPT

    def test_unknown_field_fails_with_name(self) -> None:
        from sloplab.models import CanonicalManifest

        with pytest.raises(ValidationError) as excinfo:
            CanonicalManifest.model_validate(canonical_manifest_data(valdity="valid"))
        assert "valdity" in str(excinfo.value)

    def test_invalid_id_pattern_rejected(self) -> None:
        from sloplab.models import CanonicalManifest

        with pytest.raises(ValidationError):
            CanonicalManifest.model_validate(canonical_manifest_data(id="Canonical_Authz"))

    def test_presentation_pair_requires_pair_id(self) -> None:
        from sloplab.models import CanonicalManifest

        with pytest.raises(ValidationError) as excinfo:
            CanonicalManifest.model_validate(
                canonical_manifest_data(report_class="presentation_pair")
            )
        assert "pair_id" in str(excinfo.value)

    def test_expected_dimension_validation(self) -> None:
        gt = GroundTruth(expected_dimensions={"reproducibility": 0.9})
        assert gt.expected_dimensions["reproducibility"] == 0.9

        with pytest.raises(ValidationError) as excinfo:
            GroundTruth(expected_dimensions={"not_a_dimension": 0.5})
        assert "not_a_dimension" in str(excinfo.value)

        with pytest.raises(ValidationError):
            GroundTruth(expected_dimensions={"reproducibility": 1.5})

    def test_class_decision_defaults(self) -> None:
        assert canonical_expected_decision(ReportClass.VALID) == Decision.ACCEPT
        assert canonical_expected_decision(ReportClass.INVALID) == Decision.REJECT
        assert canonical_expected_decision(ReportClass.REVIEW) == Decision.NEEDS_MANUAL_REVIEW


class TestMutationManifest:
    @staticmethod
    def mutation_manifest_data(**overrides: Any) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": "mut-authz-001-impact-inflation-01",
            "parent_id": "canonical-authz-001",
            "operator": "impact_inflation",
            "category": "impact",
            "seed": 481516,
            "variant_index": 0,
            "base_seed": 20260825,
            "expected_decision": "needs_manual_review",
            "generator_version": "0.1.0",
            "report": {"path": "adversarial/x/report.md"},
        }
        data.update(overrides)
        return data

    def test_valid_mutation_manifest(self) -> None:
        manifest = MutationManifest.model_validate(self.mutation_manifest_data())
        assert manifest.expected_decision == Decision.NEEDS_MANUAL_REVIEW

    def test_bad_decision_rejected_with_message(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            MutationManifest.model_validate(self.mutation_manifest_data(expected_decision="maybe"))
        assert "maybe" in str(excinfo.value)

    def test_parent_id_pattern_enforced(self) -> None:
        with pytest.raises(ValidationError):
            MutationManifest.model_validate(self.mutation_manifest_data(parent_id="mut-other"))


class TestEvaluationResult:
    @staticmethod
    def result_data(**overrides: Any) -> dict[str, Any]:
        data: dict[str, Any] = {
            "evaluator_name": "rules-baseline",
            "evaluator_version": "0.1.0",
            "case_id": "canonical-authz-001",
            "decision": "accept",
            "confidence": 0.7,
            "dimensions": {d: 0.8 for d in DIMENSIONS},
        }
        data.update(overrides)
        return data

    def test_round_trip(self) -> None:
        result = EvaluationResult.model_validate(self.result_data())
        assert result.decision == Decision.ACCEPT
        assert result.dimensions.as_dict()[DIMENSIONS[0]] == 0.8

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            EvaluationResult.model_validate(self.result_data(confidence=2.0))

    def test_finding_code_style(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            EvaluationResult.model_validate(
                self.result_data(findings=[{"code": "missing_step", "severity": "low"}])
            )
        assert "missing_step" in str(excinfo.value)

    def test_missing_dimensions_rejected(self) -> None:
        dims = {d: 0.5 for d in DIMENSIONS if d != "scope_consistency"}
        with pytest.raises(ValueError, match="missing dimension"):
            DimensionScores.from_dict(dims)


class TestSuiteConfig:
    @staticmethod
    def suite_data(**overrides: Any) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": "v1-core",
            "base_seed": 20260825,
            "policies": {
                "valid": {"variants_per_fixture": 8, "operators": ["impact_inflation"]},
                "invalid": {"variants_per_fixture": 4, "operators": ["professionalize_language"]},
            },
        }
        data.update(overrides)
        return data

    def test_suite_loads(self) -> None:
        suite = SuiteConfig.model_validate(self.suite_data())
        assert suite.policies[ReportClass.VALID].variants_per_fixture == 8

    def test_duplicate_operators_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SuiteConfig.model_validate(
                self.suite_data(
                    policies={
                        "valid": {
                            "variants_per_fixture": 8,
                            "operators": ["impact_inflation", "impact_inflation"],
                        }
                    }
                )
            )

    def test_empty_policies_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SuiteConfig.model_validate(self.suite_data(policies={}))

    def test_case_estimation(self) -> None:
        suite = SuiteConfig.model_validate(self.suite_data())
        counts = suite.estimated_case_count({"valid": 12, "invalid": 10})
        assert counts == {"valid": 96, "invalid": 40}
