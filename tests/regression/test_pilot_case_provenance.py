"""A-008: pilot success records take case provenance from the actual case.

``case_kind`` used to be hard-coded to ``"canonical"``; a mutated case passed
to the pilot therefore produced wrong provenance. No live calls.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from sloplab.corpus.loader import discover_fixtures
from sloplab.evaluators.llm.adapter import LlmEvaluator, LLMResponse
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.pilot import CountingClient, run_llm_pilot
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.materialize import materialize_suite
from sloplab.scoring.harness import SuiteCase, build_cases
from tests._helpers import write_canonical_fixture

VALID_PAYLOAD = json.dumps(
    {
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
)


class _Transport:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt: str) -> LLMResponse:
        _ = prompt
        self.calls += 1
        return LLMResponse(text=VALID_PAYLOAD, latency_ms=1)


def _cases(tmp_path: Path) -> list[SuiteCase]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus, "p-000", fixture_id="canonical-p-000", title="Provenance report"
    )
    suite = {
        "name": "provenance-suite",
        "base_seed": 5,
        "corpus_root": str(corpus),
        "include_canonical_cases": True,
        "policies": {"valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]}},
    }
    config = SuiteConfig.model_validate(suite)
    canonical, _ = discover_fixtures(corpus)
    out_root = tmp_path / "out"
    materialize_suite(config, canonical, out_root)
    return build_cases(out_root / "suite-index.jsonl", corpus, out_root)


def _run(tmp_path: Path, cases: list[SuiteCase], transport: _Transport) -> Any:
    template = tmp_path / "prompt.md"
    template.write_text("Route.\n\n{report_text}\n", encoding="utf-8")
    config = LLMPilotConfig.model_validate(
        {
            "schema_version": 2,
            "name": "provenance-pilot",
            "suite": {"config_path": "benchmarks/suites/v1-core.yaml", "corpus_root": "corpus"},
            "base_seed": 5,
            "repeats": 1,
            "model_env": "A008_MODEL",
            "endpoint_env": "A008_ENDPOINT",
            "api_key_env": "A008_API_KEY",
            "prompt_file": str(template),
            "budget": {"max_requests": 20, "min_interval_ms": 0},
            "case_selection": "canonical_first",
        }
    )
    evaluator = LlmEvaluator(client=CountingClient(transport, 20), max_retries=0, enabled=True)
    return run_llm_pilot(config, evaluator, cases, tmp_path, tmp_path / "pilot")


def test_mutated_case_records_keep_real_provenance(tmp_path: Path) -> None:
    cases = _cases(tmp_path)
    mutated = [c for c in cases if c.kind == "mutated"]
    canonical = [c for c in cases if c.kind == "canonical"]
    assert mutated and canonical

    result = _run(tmp_path, canonical + mutated, _Transport())
    records = {
        rec["case_id"]: rec
        for rec in (
            json.loads(line)
            for line in result.records_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    assert len(records) == len(canonical) + len(mutated)
    for case in mutated:
        record = records[case.case_id]
        assert record["case_kind"] == "mutated"
        assert case.parent_id is not None and case.operator is not None
        assert record["parent_id"] == case.parent_id
        assert record["operator"] == case.operator
        assert record["seed"] == case.seed
    for case in canonical:
        record = records[case.case_id]
        assert record["case_kind"] == "canonical"
        assert record["parent_id"] is None
        assert record["operator"] is None


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"kind": "paraphrase"}, "unknown kind"),
        ({"parent_id": None}, "lacks parent_id/operator"),
        ({"operator": None}, "lacks parent_id/operator"),
    ],
)
def test_inconsistent_case_provenance_fails_before_dispatch(
    tmp_path: Path, change: dict[str, Any], message: str
) -> None:
    cases = _cases(tmp_path)
    mutated = next(c for c in cases if c.kind == "mutated")
    broken = dataclasses.replace(mutated, **change)
    transport = _Transport()
    with pytest.raises(ValueError, match=message):
        _run(tmp_path, [broken], transport)
    assert transport.calls == 0
    assert not (tmp_path / "pilot").exists()
