"""E1b: build_cases snapshot'ları çalışma boyunca sabit kalır.

Kapsam: türev/kanonik rapor ve hedefler build anında saklanır; run_case ve pilot
belge seçimi diskten yeniden yüklemez. R04 kimlik gizleme korunur; sıra/seed/hedef
değişmez. Legacy fallback (snapshotsız doğrudan kurucular) belgeli ve sınırlıdır.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from sloplab.corpus.loader import discover_fixtures, load_canonical_fixture
from sloplab.evaluators.base import get_evaluator
from sloplab.evaluators.llm.adapter import LlmEvaluator, LLMResponse
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.pilot import CountingClient, _document_for, run_llm_pilot
from sloplab.models.evaluation import EvaluationContext, EvaluationResult
from sloplab.models.report import ReportDocument
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.materialize import materialize_suite
from sloplab.scoring.harness import (
    SuiteCase,
    build_cases,
    case_document,
    opaque_case_handle,
    run_case,
)
from tests._helpers import write_canonical_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]


class _SpyEvaluator:
    """Records evaluator-visible inputs, then delegates to a real baseline.

    Genuinely consumes labels for target verification, so it declares the
    label capability (E2a); content evaluators under test must not rely on it.
    """

    name = "spy"
    version = "0"
    requires_labels = True

    def __init__(self, delegate: str) -> None:
        self.delegate = delegate
        self.seen_texts: list[str] = []
        self.seen_dims: list[dict[str, float]] = []
        self.seen_decisions: list[str | None] = []
        self.seen_ids: list[tuple[str, str, str]] = []

    def evaluate(self, report: ReportDocument, context: EvaluationContext) -> EvaluationResult:
        self.seen_texts.append(report.raw_text)
        self.seen_dims.append(dict(context.labels.get("expected_dimensions", {})))
        decision = context.labels.get("expected_decision")
        self.seen_decisions.append(str(decision) if decision is not None else None)
        self.seen_ids.append((context.case_id, report.fixture_id, report.path))
        return get_evaluator(self.delegate).evaluate(report, context)


class _MutatingEvaluator(_SpyEvaluator):
    """Spy that also corrupts its own mutable label copy in place."""

    def evaluate(self, report: ReportDocument, context: EvaluationContext) -> EvaluationResult:
        result = super().evaluate(report, context)
        dims = context.labels.get("expected_dimensions")
        if isinstance(dims, dict):
            dims.clear()
            dims["reproducibility"] = 0.0
        return result


class _PromptRecorder:
    """Fake transport that records prompts and returns a fixed valid payload."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> LLMResponse:
        self.prompts.append(prompt)
        payload = {
            "decision": "accept",
            "confidence": 0.8,
            "dimensions": {
                "reproducibility": 0.7,
                "evidence_completeness": 0.7,
                "claim_evidence_consistency": 0.7,
                "impact_calibration": 0.7,
                "scope_consistency": 0.7,
            },
            "findings": [],
            "rationale": "ok",
        }
        return LLMResponse(text=json.dumps(payload), latency_ms=1)


def _materialized_workspace(tmp_path: Path) -> dict[str, Path]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "v-000",
        fixture_id="canonical-v-000",
        title="Snapshot valid report",
        report_class="valid",
    )
    write_canonical_fixture(
        corpus,
        "i-000",
        fixture_id="canonical-i-000",
        title="Snapshot invalid report",
        report_class="invalid",
    )
    suite = {
        "name": "snapshot-suite",
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
    return {"corpus": corpus, "suite": suite_path, "out": out_root}


def _pilot_config() -> LLMPilotConfig:
    return LLMPilotConfig.model_validate(
        {
            "schema_version": 2,
            "name": "snapshot-pilot",
            "suite": {"config_path": "benchmarks/suites/v1-core.yaml", "corpus_root": "corpus"},
            "base_seed": 21,
            "repeats": 1,
            "model_env": "E1B_MODEL",
            "endpoint_env": "E1B_ENDPOINT",
            "api_key_env": "E1B_API_KEY",
            "prompt_file": "experiments/prompts/triage-v1.md",
            "budget": {"max_requests": 50},
            "case_selection": "canonical_first",
            "max_cases": None,
        }
    )


def test_derived_disk_change_invisible_to_evaluators(tmp_path: Path) -> None:
    """Corrupt derived files after build: spies still see first text/targets."""
    paths = _materialized_workspace(tmp_path)
    cases = build_cases(paths["out"] / "suite-index.jsonl", paths["corpus"], paths["out"])
    mutated = [c for c in cases if c.kind == "mutated"]
    assert mutated, "expected mutated cases"
    assert all(c.report is not None for c in mutated)
    original = {
        c.case_id: (
            c.report.raw_text if c.report is not None else "",
            c.expected_decision,
            dict(c.expected_dimensions),
        )
        for c in mutated
    }
    for case in mutated:
        assert case.fixture_dir is not None
        (case.fixture_dir / "report.md").write_text(
            "# Changed\n\nTotally different text.\n", encoding="utf-8"
        )
        (case.fixture_dir / "mutation-manifest.yaml").write_text(
            "not: [valid, yaml-mapping\n  broken: {", encoding="utf-8"
        )
    spy_a = _SpyEvaluator("rules-baseline")
    spy_b = _SpyEvaluator("evidence-graph-baseline")
    records_a = [run_case(spy_a, c) for c in mutated]
    records_b = [run_case(spy_b, c) for c in mutated]
    assert len(spy_a.seen_texts) == len(mutated) == len(spy_b.seen_texts)
    for index, (case, seen_a, seen_b, rec_a, rec_b) in enumerate(
        zip(mutated, spy_a.seen_texts, spy_b.seen_texts, records_a, records_b, strict=True)
    ):
        first_text, first_decision, first_dims = original[case.case_id]
        assert seen_a == first_text
        assert seen_b == first_text
        assert "Totally different" not in seen_a
        assert spy_a.seen_dims[index] == first_dims
        assert spy_b.seen_dims[index] == first_dims
        assert rec_a.expected_decision is not None
        assert rec_b.expected_decision is not None
        assert rec_a.expected_decision.value == rec_b.expected_decision.value == first_decision
        assert rec_a.expected_dimensions == rec_b.expected_dimensions == first_dims


def test_derived_files_removed_after_build_still_evaluates(tmp_path: Path) -> None:
    """Only this test's tmp files are removed; snapshot cases still evaluate."""
    paths = _materialized_workspace(tmp_path)
    cases = build_cases(paths["out"] / "suite-index.jsonl", paths["corpus"], paths["out"])
    mutated = [c for c in cases if c.kind == "mutated"]
    assert mutated
    for case in mutated:
        assert case.fixture_dir is not None
        shutil.rmtree(case.fixture_dir)
    spy = _SpyEvaluator("rules-baseline")
    records = [run_case(spy, c) for c in mutated]
    assert len(records) == len(mutated)
    assert all(r.case_id == c.case_id for r, c in zip(records, mutated, strict=True))


def test_loader_raise_after_build_touches_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Snapshot run_case and pilot doc selection never call the loader again."""
    import sloplab.scoring.harness as harness_module

    loader_calls: list[str] = []

    def _boom(*args: Any, **kwargs: Any) -> Any:
        loader_calls.append("load_derived_fixture")
        raise AssertionError("loader must not be called after build_cases")

    monkeypatch.setattr(harness_module, "load_derived_fixture", _boom)
    paths = _materialized_workspace(tmp_path)
    # build_cases itself is out of scope here: restore the real loader for it.
    monkeypatch.undo()
    cases = build_cases(paths["out"] / "suite-index.jsonl", paths["corpus"], paths["out"])
    monkeypatch.setattr(harness_module, "load_derived_fixture", _boom)
    mutated = [c for c in cases if c.kind == "mutated"]
    assert mutated
    spy = _SpyEvaluator("rules-baseline")
    for case in mutated:
        run_case(spy, case)
        assert case_document(case).raw_text == (case.report.raw_text if case.report else None)
        assert _document_for(case, tmp_path).raw_text == (
            case.report.raw_text if case.report else None
        )
    assert loader_calls == []


def test_canonical_disk_change_ineffective(tmp_path: Path) -> None:
    """Overwriting a canonical report after build does not change evaluation input."""
    paths = _materialized_workspace(tmp_path)
    cases = build_cases(paths["out"] / "suite-index.jsonl", paths["corpus"], paths["out"])
    canonical = [c for c in cases if c.kind == "canonical"]
    assert canonical
    first_texts = [c.report.raw_text if c.report is not None else "" for c in canonical]
    (paths["corpus"] / "canonical" / "v-000" / "report.md").write_text(
        "# Replaced\n\nNothing like the original.\n", encoding="utf-8"
    )
    spy = _SpyEvaluator("rules-baseline")
    for case in canonical:
        run_case(spy, case)
    assert spy.seen_texts == first_texts
    assert all("Nothing like the original" not in seen for seen in spy.seen_texts)


def test_label_mutation_isolated_between_evaluators_and_records(tmp_path: Path) -> None:
    """An evaluator corrupting its label copy affects neither the next run nor records."""
    paths = _materialized_workspace(tmp_path)
    cases = build_cases(paths["out"] / "suite-index.jsonl", paths["corpus"], paths["out"])
    case = next(c for c in cases if c.kind == "mutated")
    pristine = dict(case.expected_dimensions)
    assert pristine
    bad = _MutatingEvaluator("rules-baseline")
    good = _SpyEvaluator("rules-baseline")
    rec_bad = run_case(bad, case)
    rec_good = run_case(good, case)
    assert good.seen_dims and good.seen_dims[0] == pristine
    assert rec_bad.expected_dimensions == pristine
    assert rec_good.expected_dimensions == pristine
    assert case.expected_dimensions == pristine
    rec_bad.expected_dimensions["reproducibility"] = -1.0
    assert case.expected_dimensions == pristine
    assert rec_good.expected_dimensions == pristine


def test_legacy_direct_constructors_still_load(tmp_path: Path) -> None:
    """Pre-snapshot direct constructors keep working via the documented fallback."""
    fixture_dir = write_canonical_fixture(
        tmp_path,
        "v-009",
        fixture_id="canonical-v-009",
        title="Legacy direct report",
        report_class="valid",
    )
    canon = load_canonical_fixture(fixture_dir, tmp_path)
    legacy_canonical = SuiteCase(
        case_id="canonical-v-009",
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
    assert legacy_canonical.report is None
    assert case_document(legacy_canonical).raw_text == canon.report.raw_text

    paths = _materialized_workspace(tmp_path)
    cases = build_cases(paths["out"] / "suite-index.jsonl", paths["corpus"], paths["out"])
    snapshot_case = next(c for c in cases if c.kind == "mutated")
    assert snapshot_case.fixture_dir is not None
    legacy_mutated = SuiteCase(
        case_id=snapshot_case.case_id,
        kind="mutated",
        parent_id=snapshot_case.parent_id,
        operator=snapshot_case.operator,
        report_class=snapshot_case.report_class,
        expected_decision=snapshot_case.expected_decision,
        expected_dimensions=dict(snapshot_case.expected_dimensions),
        seed=snapshot_case.seed,
        fixture_dir=snapshot_case.fixture_dir,
    )
    assert legacy_mutated.report is None
    expected_text = snapshot_case.report.raw_text if snapshot_case.report else ""
    assert case_document(legacy_mutated).raw_text == expected_text


def test_build_cases_always_snapshots(tmp_path: Path) -> None:
    """Every build_cases result carries its loaded report (never the fallback)."""
    paths = _materialized_workspace(tmp_path)
    cases = build_cases(paths["out"] / "suite-index.jsonl", paths["corpus"], paths["out"])
    assert cases
    for case in cases:
        assert case.report is not None, case.case_id
        assert case.report.raw_text
        assert case_document(case) is case.report


def test_pilot_uses_snapshot_after_disk_change(tmp_path: Path) -> None:
    """Fake-transport pilot prompts carry the build-time text, not later disk text."""
    paths = _materialized_workspace(tmp_path)
    cases = build_cases(paths["out"] / "suite-index.jsonl", paths["corpus"], paths["out"])
    mutated = [c for c in cases if c.kind == "mutated"]
    assert mutated
    first_texts = [c.report.raw_text if c.report is not None else "" for c in mutated]
    for case in mutated:
        assert case.fixture_dir is not None
        (case.fixture_dir / "report.md").write_text(
            "# Pilot changed\n\nLater disk text.\n", encoding="utf-8"
        )
    recorder = _PromptRecorder()
    evaluator = LlmEvaluator(
        client=CountingClient(recorder, max_requests=50), max_retries=0, enabled=True
    )
    config = _pilot_config()
    result = run_llm_pilot(config, evaluator, mutated, REPO_ROOT, tmp_path / "pilot-out")
    assert result.evaluations_attempted == len(mutated)
    assert len(recorder.prompts) == len(mutated)
    for prompt, first in zip(recorder.prompts, first_texts, strict=True):
        assert first in prompt
        assert "Later disk text" not in prompt


def test_pilot_doc_selection_ignores_loader_after_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_document_for serves snapshot cases without touching the loader."""
    import sloplab.scoring.harness as harness_module

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("loader must not be called for snapshot cases")

    paths = _materialized_workspace(tmp_path)
    cases = build_cases(paths["out"] / "suite-index.jsonl", paths["corpus"], paths["out"])
    monkeypatch.setattr(harness_module, "load_derived_fixture", _boom)
    for case in cases:
        doc = _document_for(case, tmp_path)
        assert doc.raw_text == (case.report.raw_text if case.report is not None else "")


def test_r04_identity_hygiene_preserved_with_snapshot(tmp_path: Path) -> None:
    """Opaque handles still hide real identity on the snapshot path."""
    paths = _materialized_workspace(tmp_path)
    cases = build_cases(paths["out"] / "suite-index.jsonl", paths["corpus"], paths["out"])
    mutated = [c for c in cases if c.kind == "mutated"]
    assert mutated
    spy = _SpyEvaluator("rules-baseline")
    records = [run_case(spy, c) for c in mutated]
    for case, record, (ctx_id, fix_id, path) in zip(mutated, records, spy.seen_ids, strict=True):
        handle = opaque_case_handle(case.case_id)
        assert (ctx_id, fix_id, path) == (handle, handle, handle)
        assert case.case_id not in (ctx_id, fix_id, path)
        if case.operator:
            assert case.operator not in fix_id + path
        assert record.case_id == case.case_id
        assert record.evaluator_name == "rules-baseline"
        assert re.fullmatch(r"case-[0-9a-f]{16}", handle)


def test_unloadable_case_still_rejected() -> None:
    """A case with neither snapshot nor loadable source keeps failing loudly."""
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
    with pytest.raises(ValueError, match="not loadable"):
        case_document(orphan)
