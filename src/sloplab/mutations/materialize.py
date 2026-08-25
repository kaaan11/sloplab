"""Materialization: execute planned mutations and write derived fixture directories."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from sloplab import __version__
from sloplab.corpus.loader import CanonicalFixture
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.base import get_operator
from sloplab.mutations.planner import PlannedMutation, plan_suite
from sloplab.safety.policy import validate_content_safety

SUITE_INDEX_NAME = "suite-index.jsonl"


@dataclass
class MaterializationResult:
    out_root: Path
    cases_written: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)
    safety_violations: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"materialized {self.cases_written} derived cases into {self.out_root}",
        ]
        for case_id, reason in self.skipped:
            lines.append(f"  skipped {case_id}: {reason}")
        for violation in self.safety_violations:
            lines.append(f"  SAFETY: {violation}")
        return "\n".join(lines)


def _write_derived_case(
    plan: PlannedMutation,
    mutated_text: str,
    parameters: dict[str, Any],
    out_root: Path,
) -> Path:
    case_dir = out_root / "adversarial" / plan.parent_id.removeprefix("canonical-") / plan.case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    report_rel = f"adversarial/{plan.parent_id.removeprefix('canonical-')}/{plan.case_id}/report.md"
    (case_dir / "report.md").write_text(mutated_text, encoding="utf-8")

    manifest_data = {
        "schema_version": 1,
        "id": plan.case_id,
        "parent_id": plan.parent_id,
        "operator": plan.operator_name,
        "category": plan.spec.category.value,
        "parameters": {"choices": parameters},
        "seed": plan.seed,
        "variant_index": plan.variant_index,
        "base_seed": plan.base_seed,
        "expected_decision": plan.expected_decision.value,
        "expected_effect": {
            "report_validity": plan.expected_effect.report_validity,
            "claim_quality": plan.expected_effect.claim_quality,
            "presentation_strength": plan.expected_effect.presentation_strength,
        },
        "expected_dimensions": plan.expected_dimensions,
        "generator_version": __version__,
        "report": {"path": report_rel},
    }
    (case_dir / "mutation-manifest.yaml").write_text(
        yaml.safe_dump(manifest_data, sort_keys=False), encoding="utf-8"
    )
    return case_dir


def _index_line(plan: PlannedMutation, case_dir: Path) -> dict[str, Any]:
    return {
        "record_type": "suite_case",
        "case_id": plan.case_id,
        "kind": "mutated",
        "parent_id": plan.parent_id,
        "operator": plan.operator_name,
        "expected_decision": plan.expected_decision.value,
        "report_class": plan.parent.manifest.report_class.value,
        # path relative to the materialization output root (parents[2] == out_root)
        "manifest_path": str(
            (case_dir / "mutation-manifest.yaml").relative_to(case_dir.parents[2])
        ),
    }


def materialize_suite(
    config: SuiteConfig,
    fixtures: list[CanonicalFixture],
    out_root: Path,
) -> MaterializationResult:
    """Apply every planned mutation and write derived cases under ``out_root``."""
    result = MaterializationResult(out_root=out_root)
    plans, _group_counts = plan_suite(config, fixtures)

    seen_ids: set[str] = set()
    index_lines: list[dict[str, Any]] = []

    for plan in plans:
        if plan.case_id in seen_ids:
            result.skipped.append((plan.case_id, "duplicate case id"))
            continue
        operator = get_operator(plan.operator_name)
        rng = random.Random(plan.seed)
        mutated_text, parameters = operator.apply(plan.parent.report, rng)

        if any(k == "note" for k in parameters):
            result.skipped.append((plan.case_id, str(parameters.get("note"))))
            continue

        violations = validate_content_safety(mutated_text)
        if violations:
            result.safety_violations.extend(f"{plan.case_id}: {v}" for v in violations)
            continue

        case_dir = _write_derived_case(plan, mutated_text, parameters, out_root)
        seen_ids.add(plan.case_id)
        index_lines.append(_index_line(plan, case_dir))
        result.cases_written += 1

    if config.include_canonical_cases:
        for fixture in fixtures:
            index_lines.append(
                {
                    "record_type": "suite_case",
                    "case_id": fixture.fixture_id,
                    "kind": "canonical",
                    "parent_id": None,
                    "operator": None,
                    "expected_decision": fixture.manifest.expected_decision().value,
                    "report_class": fixture.manifest.report_class.value,
                    "manifest_path": None,
                }
            )

    index_lines.sort(key=lambda line: line["case_id"])
    (out_root / SUITE_INDEX_NAME).write_text(
        "".join(json.dumps(line, sort_keys=True) + "\n" for line in index_lines),
        encoding="utf-8",
    )
    return result


def load_suite_config(path: Path) -> SuiteConfig:
    """Load and validate a suite YAML file with an actionable error message."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    from pydantic import ValidationError

    from sloplab.corpus.loader import format_validation_error

    try:
        return SuiteConfig.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(
            f"{path}: suite configuration invalid\n{format_validation_error(exc)}"
        ) from exc
