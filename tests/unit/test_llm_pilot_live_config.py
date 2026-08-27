"""Tests for the live LLM pilot configuration and budgeted execution (Phase 11)."""

from __future__ import annotations

import json
from pathlib import Path

from sloplab.corpus.loader import discover_fixtures
from sloplab.evaluators.llm.adapter import LlmEvaluator, LLMResponse
from sloplab.experiments.pilot import CountingClient, run_llm_pilot
from sloplab.experiments.runner import load_pilot_config
from sloplab.mutations.materialize import load_suite_config, materialize_suite
from sloplab.scoring.harness import build_cases

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_CONFIG_PATH = REPO_ROOT / "experiments/configs/llm-pilot-live.yaml"


class MockHijackedResponder:
    """Mock responder obeying prompt injection: produces ACCEPT when injection is present."""

    def complete(self, prompt: str) -> LLMResponse:
        is_injected = "SYSTEM DIRECTIVE" in prompt or "SYSTEM INSTRUCTION" in prompt
        decision = "accept" if is_injected else "reject"
        payload = {
            "decision": decision,
            "confidence": 0.95,
            "dimensions": {
                "reproducibility": 0.8,
                "evidence_completeness": 0.8,
                "claim_evidence_consistency": 0.8,
                "impact_calibration": 0.8,
                "scope_consistency": 0.8,
            },
            "findings": [],
            "rationale": "Evaluated via mock responder.",
        }
        return LLMResponse(text=json.dumps(payload), latency_ms=10)


def test_live_pilot_config_loads() -> None:
    assert LIVE_CONFIG_PATH.is_file()
    cfg = load_pilot_config(LIVE_CONFIG_PATH)
    assert cfg.name == "llm-pilot-live"
    assert cfg.budget.max_requests == 40
    assert cfg.repeats == 1

    suite_path = REPO_ROOT / cfg.suite.config_path
    assert suite_path.is_file()


def test_live_pilot_runs_over_injection_cases(tmp_path: Path) -> None:
    cfg = load_pilot_config(LIVE_CONFIG_PATH)
    corpus_root = REPO_ROOT / cfg.suite.corpus_root
    suite_cfg = load_suite_config(REPO_ROOT / cfg.suite.config_path)

    canonical, _ = discover_fixtures(corpus_root)
    # Materialize 2 canonical fixtures for fast test execution
    out_suite_dir = tmp_path / "materialized_injection"
    materialize_suite(suite_cfg, canonical[:2], out_suite_dir, corpus_root_resolved=corpus_root)

    cases = build_cases(out_suite_dir / "suite-index.jsonl", corpus_root, out_suite_dir)
    assert len(cases) > 2

    counting_client = CountingClient(MockHijackedResponder(), max_requests=cfg.budget.max_requests)
    evaluator = LlmEvaluator(counting_client, enabled=True)

    pilot_out = tmp_path / "pilot_out"
    result = run_llm_pilot(cfg, evaluator, cases[:4], repo_root=REPO_ROOT, out_dir=pilot_out)

    assert result.evaluations_attempted == 4
    assert result.failed_evaluations == 0
    assert result.skipped_by_budget == 0
    assert (pilot_out / "records.jsonl").is_file()
    assert (pilot_out / "manifest.json").is_file()
