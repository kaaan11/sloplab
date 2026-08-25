"""Tests for mutation planning and suite materialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from sloplab.corpus.loader import discover_fixtures
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.materialize import SUITE_INDEX_NAME, load_suite_config, materialize_suite
from sloplab.mutations.planner import plan_suite


def make_config(tmp_path: Path, **overrides: Any) -> SuiteConfig:
    data: dict[str, Any] = {
        "name": "test-suite",
        "base_seed": 7,
        "corpus_root": str(tmp_path / "canonical"),
        "policies": {
            "valid": {
                "variants_per_fixture": 4,
                "operators": [
                    "remove_reproduction_step",
                    "impact_inflation",
                    "scope_expansion",
                    "invent_api_identifier",
                ],
            },
            "invalid": {
                "variants_per_fixture": 1,
                "operators": ["professionalize_language"],
            },
        },
    }
    data.update(overrides)
    return SuiteConfig.model_validate(data)


@pytest.fixture()
def corpus(tmp_path: Path, make_fixture: Any) -> Path:
    for i in range(3):
        make_fixture(
            tmp_path,
            f"val-{i:03d}",
            fixture_id=f"canonical-val-{i:03d}",
            title=f"Valid report {i}",
            report_class="valid",
        )
    for i in range(2):
        make_fixture(
            tmp_path,
            f"inv-{i:03d}",
            fixture_id=f"canonical-inv-{i:03d}",
            title=f"Invalid report {i}",
            report_class="invalid",
        )
    return tmp_path


class TestPlanner:
    def test_plan_counts_and_rotation(self, corpus: Path) -> None:
        fixtures, _ = discover_fixtures(corpus)
        config = make_config(corpus)
        plans, group_counts = plan_suite(config, fixtures)
        assert len(plans) == 3 * 4 + 2 * 1 == 14
        assert group_counts == {"valid": 3, "invalid": 2}
        # Rotation spreads operators across fixtures.
        valid_plans = [p for p in plans if p.parent_id.startswith("canonical-val")]
        first_ops = [p.operator_name for p in valid_plans if p.variant_index == 0]
        assert len(set(first_ops)) > 1

    def test_expected_decision_follows_spec(self, corpus: Path) -> None:
        fixtures, _ = discover_fixtures(corpus)
        config = make_config(corpus)
        plans, _ = plan_suite(config, fixtures)
        by_op = {p.operator_name: p.expected_decision.value for p in plans if p.parent_id != "x"}
        assert by_op.get("remove_reproduction_step") == "needs_manual_review"
        assert by_op.get("impact_inflation") == "needs_manual_review"
        assert by_op.get("professionalize_language") == "reject"

    def test_case_ids_unique_and_wellformed(self, corpus: Path) -> None:
        fixtures, _ = discover_fixtures(corpus)
        config = make_config(corpus)
        plans, _ = plan_suite(config, fixtures)
        ids = [p.case_id for p in plans]
        assert len(ids) == len(set(ids))
        import re

        pattern = re.compile(r"^mut-[a-z0-9]+(-[a-z0-9]+)*$")
        assert all(pattern.match(i) for i in ids)


class TestMaterialization:
    def test_materializes_reports_manifests_index(self, corpus: Path) -> None:
        fixtures, _ = discover_fixtures(corpus)
        config = make_config(corpus)
        out = corpus / "out"
        result = materialize_suite(config, fixtures, out)
        assert result.cases_written == 14
        assert result.safety_violations == []
        index_path = out / SUITE_INDEX_NAME
        lines = [json.loads(line) for line in index_path.read_text().splitlines()]
        assert lines[0]["record_type"] == "suite_header"
        assert lines[0]["corpus_root"] == config.corpus_root
        kinds: dict[str, int] = {}
        for line in lines:
            if line.get("record_type") != "suite_case":
                continue
            kinds[line["kind"]] = kinds.get(line["kind"], 0) + 1
        assert kinds == {"mutated": 14, "canonical": 5}

        one_dir = next(out.glob("adversarial/*/*/"))
        manifest = yaml.safe_load((one_dir / "mutation-manifest.yaml").read_text())
        assert manifest["parent_id"].startswith("canonical-")
        assert manifest["expected_decision"] in {"accept", "reject", "needs_manual_review"}
        assert (one_dir / "report.md").exists()

    def test_materialization_is_deterministic(self, corpus: Path) -> None:
        fixtures, _ = discover_fixtures(corpus)
        config = make_config(corpus)
        out_a, out_b = corpus / "a", corpus / "b"
        ra = materialize_suite(config, fixtures, out_a)
        rb = materialize_suite(config, fixtures, out_b)
        assert ra.cases_written == rb.cases_written
        a_bytes = sorted(p.read_bytes() for p in out_a.rglob("*") if p.is_file())
        b_bytes = sorted(p.read_bytes() for p in out_b.rglob("*") if p.is_file())
        assert a_bytes == b_bytes

    def test_derived_cases_pass_corpus_loading(self, corpus: Path) -> None:
        from sloplab.corpus.loader import load_derived_fixture

        fixtures, _ = discover_fixtures(corpus)
        config = make_config(corpus)
        out = corpus / "out"
        materialize_suite(config, fixtures, out)
        loaded = 0
        for case_dir in out.glob("adversarial/*/*/"):
            derived = load_derived_fixture(case_dir, out)
            assert derived.manifest.parent_id.startswith("canonical-")
            assert derived.report.raw_text  # non-empty
            loaded += 1
        assert loaded == 14


class TestSuiteConfigLoading:
    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        path = tmp_path / "suite.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "name": "s",
                    "base_seed": 1,
                    "policies": {
                        "review": {"variants_per_fixture": 1, "operators": ["impact_inflation"]}
                    },
                }
            )
        )
        config = load_suite_config(path)
        assert config.name == "s"

    def test_invalid_yaml_gives_actionable_error(self, tmp_path: Path) -> None:
        path = tmp_path / "suite.yaml"
        path.write_text(yaml.safe_dump({"name": "s", "oops": 1}))
        with pytest.raises(ValueError, match="oops"):
            load_suite_config(path)
