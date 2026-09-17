"""E1d: snapshot'lardan türetilmiş yol-bağımsız girdi kimlikleri.

Kapsam: input-identity.json sözleşmesi (report/target/input/selection/inputs
hash'leri, canonical serializer, snapshot zorunluluğu, sıra duyarlılığı) ve
deterministik study bağlantısı. Tam tarif/ortam kimliği sonraki pakettir.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from sloplab.corpus.loader import discover_fixtures
from sloplab.experiments.input_identity import (
    InputIdentityError,
    build_input_identity,
)
from sloplab.experiments.runner import load_study_config
from sloplab.experiments.study import run_deterministic_study
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.materialize import materialize_suite
from sloplab.scoring.harness import SuiteCase, build_cases
from tests._helpers import write_canonical_fixture

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _canon(obj: Any) -> bytes:
    """Independent canonical encoding per schema-contract.md (test-local)."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _digest(obj: Any) -> str:
    return hashlib.sha256(_canon(obj)).hexdigest()


def _workspace(tmp_path: Path) -> dict[str, Any]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "v-000",
        fixture_id="canonical-v-000",
        title="Identity valid report",
        report_class="valid",
    )
    write_canonical_fixture(
        corpus,
        "i-000",
        fixture_id="canonical-i-000",
        title="Identity invalid report",
        report_class="invalid",
    )
    suite = {
        "name": "identity-suite",
        "base_seed": 21,
        "corpus_root": str(corpus),
        "include_canonical_cases": True,
        "policies": {
            "valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]},
            "invalid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]},
        },
    }
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(yaml.safe_dump(suite), encoding="utf-8")
    config = SuiteConfig.model_validate(yaml.safe_load(suite_path.read_text(encoding="utf-8")))
    canonical, _ = discover_fixtures(corpus)
    out_root = tmp_path / "out"
    materialize_suite(config, canonical, out_root)
    cases = build_cases(out_root / "suite-index.jsonl", corpus, out_root)
    assert cases
    return {"corpus": corpus, "suite": suite_path, "out": out_root, "cases": cases}


def _study_yaml(
    tmp_path: Path, suite_path: Path, corpus: Path, evaluators: list[str], name: str
) -> Path:
    payload = {
        "name": name,
        "suite": {"config_path": str(suite_path), "corpus_root": str(corpus)},
        "base_seed": 21,
        "evaluators": [{"name": e} for e in evaluators],
    }
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def _expected_report_object(text: str) -> dict[str, Any]:
    return {"domain": "sloplab.input", "type": "report", "version": 1, "text": text}


def _expected_target_object(decision: str | None, dims: dict[str, float]) -> dict[str, Any]:
    return {
        "domain": "sloplab.input",
        "type": "target",
        "version": 1,
        "expected_decision": decision,
        "expected_dimensions": dims,
    }


def test_deterministic_key_order_free_and_independently_recomputed(tmp_path: Path) -> None:
    """Same snapshots/order give same identity; key order is irrelevant."""
    cases = _workspace(tmp_path)["cases"]
    first = build_input_identity(cases)
    assert first["schema_version"] == 1
    assert build_input_identity(cases) == first
    for row in first["cases"]:
        for key in ("report_hash", "target_hash", "input_hash"):
            assert HEX64.match(row[key]), key
    assert HEX64.match(first["selection_hash"])
    assert HEX64.match(first["inputs_hash"])

    reshuffled = []
    for case in cases:
        reversed_dims = dict(reversed(list(case.expected_dimensions.items())))
        reshuffled.append(dataclasses.replace(case, expected_dimensions=reversed_dims))
    assert build_input_identity(reshuffled) == first

    case = cases[0]
    assert case.report is not None
    row = first["cases"][0]
    assert row["report_hash"] == _digest(_expected_report_object(case.report.raw_text))
    assert row["target_hash"] == _digest(
        _expected_target_object(case.expected_decision, dict(case.expected_dimensions))
    )
    assert row["input_hash"] == _digest(
        {
            "domain": "sloplab.input",
            "type": "input",
            "version": 1,
            "report_hash": row["report_hash"],
            "target_hash": row["target_hash"],
        }
    )
    assert first["selection_hash"] == _digest(
        {
            "domain": "sloplab.input",
            "type": "selection",
            "version": 1,
            "case_ids": [c.case_id for c in cases],
        }
    )
    assert first["inputs_hash"] == _digest(
        {"domain": "sloplab.input", "type": "inputs", "version": 1, "inputs": first["cases"]}
    )


def test_raw_text_change_moves_report_input_inputs_only(tmp_path: Path) -> None:
    """Same case_id with different text: report/input/inputs change, rest stays."""
    cases = _workspace(tmp_path)["cases"]
    before = build_input_identity(cases)
    victim = cases[0]
    assert victim.report is not None
    changed = dataclasses.replace(
        victim, report=victim.report.model_copy(update={"raw_text": victim.report.raw_text + "\nX"})
    )
    after = build_input_identity([changed, *cases[1:]])
    assert after["cases"][0]["report_hash"] != before["cases"][0]["report_hash"]
    assert after["cases"][0]["input_hash"] != before["cases"][0]["input_hash"]
    assert after["inputs_hash"] != before["inputs_hash"]
    assert after["cases"][0]["target_hash"] == before["cases"][0]["target_hash"]
    assert after["selection_hash"] == before["selection_hash"]
    assert after["cases"][1:] == before["cases"][1:]


def test_target_change_moves_target_input_inputs_only(tmp_path: Path) -> None:
    """Changed target value/decision: target/input/inputs change, rest stays."""
    cases = _workspace(tmp_path)["cases"]
    before = build_input_identity(cases)
    victim = cases[0]
    dims = dict(victim.expected_dimensions)
    key = next(iter(dims)) if dims else "reproducibility"
    dims[key] = 0.123
    changed_dims = dataclasses.replace(victim, expected_dimensions=dims)
    after_dims = build_input_identity([changed_dims, *cases[1:]])
    assert after_dims["cases"][0]["target_hash"] != before["cases"][0]["target_hash"]
    assert after_dims["cases"][0]["input_hash"] != before["cases"][0]["input_hash"]
    assert after_dims["inputs_hash"] != before["inputs_hash"]
    assert after_dims["cases"][0]["report_hash"] == before["cases"][0]["report_hash"]
    assert after_dims["selection_hash"] == before["selection_hash"]

    flipped = dataclasses.replace(
        victim,
        expected_decision="reject" if victim.expected_decision != "reject" else "accept",
    )
    after_decision = build_input_identity([flipped, *cases[1:]])
    assert after_decision["cases"][0]["target_hash"] != before["cases"][0]["target_hash"]


def test_missing_dimension_differs_from_explicit_and_nan_rejected(tmp_path: Path) -> None:
    """Missing dim != explicit 0.5; NaN/Infinity fail loudly, never silently."""
    cases = _workspace(tmp_path)["cases"]
    base = build_input_identity(cases)
    victim = cases[0]
    empty = dataclasses.replace(victim, expected_dimensions={})
    explicit = dataclasses.replace(victim, expected_dimensions={"reproducibility": 0.5})
    assert (
        build_input_identity([empty, *cases[1:]])["cases"][0]["target_hash"]
        != build_input_identity([explicit, *cases[1:]])["cases"][0]["target_hash"]
    )
    assert base["cases"][0]["target_hash"] not in (
        build_input_identity([empty, *cases[1:]])["cases"][0]["target_hash"],
    )
    for bad in (float("nan"), float("inf"), float("-inf")):
        poisoned = dataclasses.replace(victim, expected_dimensions={"reproducibility": bad})
        with pytest.raises(ValueError, match="[Jj]SON|serializ|target"):
            build_input_identity([poisoned, *cases[1:]])


def test_order_change_moves_selection_inputs_and_evaluators_do_not(tmp_path: Path) -> None:
    """Reordered cases change selection/inputs; evaluator list changes nothing."""
    paths = _workspace(tmp_path)
    cases = paths["cases"]
    before = build_input_identity(cases)
    reversed_cases = list(reversed(cases))
    after = build_input_identity(reversed_cases)
    assert after["selection_hash"] != before["selection_hash"]
    assert after["inputs_hash"] != before["inputs_hash"]
    by_id_before = {r["case_id"]: r for r in before["cases"]}
    by_id_after = {r["case_id"]: r for r in after["cases"]}
    assert by_id_before == by_id_after

    study_a = _study_yaml(tmp_path, paths["suite"], paths["corpus"], ["rules-baseline"], "a")
    study_b = _study_yaml(
        tmp_path, paths["suite"], paths["corpus"], ["evidence-graph-baseline"], "b"
    )
    run_deterministic_study(load_study_config(study_a), study_a, tmp_path / "run-a")
    run_deterministic_study(load_study_config(study_b), study_b, tmp_path / "run-b")
    assert (tmp_path / "run-a" / "input-identity.json").read_bytes() == (
        tmp_path / "run-b" / "input-identity.json"
    ).read_bytes()


def test_two_roots_same_content_same_identity_no_paths(tmp_path: Path) -> None:
    """Identical files under different tmp roots give identical identities."""
    first = _workspace(tmp_path / "root-a")
    second = _workspace(tmp_path / "root-b")
    id_a = build_input_identity(first["cases"])
    id_b = build_input_identity(second["cases"])
    assert id_a == id_b
    text_a = json.dumps(id_a, sort_keys=True)
    assert str(tmp_path / "root-a") not in text_a
    assert str(tmp_path / "root-b") not in text_a


def test_disk_change_ignored_loader_untouched_empty_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Post-build disk edits don't move identity; loader never called; empty refused."""
    import sloplab.corpus.loader as loader_module
    import sloplab.scoring.harness as harness_module

    paths = _workspace(tmp_path)
    cases = paths["cases"]
    mutated = [c for c in cases if c.kind == "mutated"]
    assert mutated
    before = build_input_identity(cases)
    for case in mutated:
        assert case.fixture_dir is not None
        (case.fixture_dir / "report.md").write_text("# Changed\n\nOther.\n", encoding="utf-8")
        (case.fixture_dir / "mutation-manifest.yaml").write_text("not: [valid\n")
    calls: list[str] = []

    def _boom(*args: Any, **kwargs: Any) -> Any:
        calls.append("loader")
        raise AssertionError("identity must not touch the loader")

    monkeypatch.setattr(harness_module, "load_derived_fixture", _boom)
    monkeypatch.setattr(loader_module, "load_derived_fixture", _boom)
    assert build_input_identity(cases) == before
    assert calls == []

    orphan = SuiteCase(
        case_id="orphan-001",
        kind="mutated",
        parent_id=None,
        operator=None,
        report_class="valid",
        expected_decision=None,
        expected_dimensions={},
        seed=None,
        fixture_dir=None,
    )
    with pytest.raises(InputIdentityError, match="snapshot"):
        build_input_identity([orphan])


def test_study_file_matches_case_and_record_order(tmp_path: Path) -> None:
    """Identity file: one row per case, same order as evaluator records."""
    paths = _workspace(tmp_path)
    study_path = _study_yaml(
        tmp_path,
        paths["suite"],
        paths["corpus"],
        ["rules-baseline", "evidence-graph-baseline"],
        "order",
    )
    result = run_deterministic_study(load_study_config(study_path), study_path, tmp_path / "run")
    identity = json.loads((tmp_path / "run" / "input-identity.json").read_text(encoding="utf-8"))
    assert identity["schema_version"] == 1
    assert len(identity["cases"]) == result.case_count
    records = [
        json.loads(line)
        for line in (tmp_path / "run" / "records.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == result.case_count * 2
    first_eval_order = [r["case_id"] for r in records[: result.case_count]]
    assert [row["case_id"] for row in identity["cases"]] == first_eval_order
