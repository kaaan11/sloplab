"""Mock-based tests for the budgeted LLM pilot runner (V27). No live calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sloplab.evaluators.llm.adapter import LlmEvaluator
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.pilot import CountingClient, run_llm_pilot
from sloplab.experiments.runner import load_pilot_config
from sloplab.scoring.harness import build_cases

REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT_CONFIG = REPO_ROOT / "experiments/configs/llm-pilot-v0.2.yaml"

VALID_PAYLOAD = json.dumps(
    {
        "decision": "accept",
        "confidence": 0.8,
        "dimensions": {
            d: 0.7
            for d in (
                "reproducibility",
                "evidence_completeness",
                "claim_evidence_consistency",
                "impact_calibration",
                "scope_consistency",
            )
        },
        "findings": [],
        "rationale": "ok",
    }
)


class StaticResponder:
    """Transport double returning a fixed valid payload."""

    def __init__(self, payload_text: str) -> None:
        self.payload_text = payload_text

    def complete(self, prompt: str) -> Any:
        _ = prompt

        class _R:
            text = self.payload_text
            latency_ms = 1

        return _R()


class TimeoutResponder:
    def complete(self, prompt: str) -> Any:
        raise TimeoutError("simulated timeout")


def canonical_cases(n: int) -> list[Any]:
    example_dir = REPO_ROOT / "benchmarks/results/v1-core-example"
    cases = build_cases(
        example_dir / "suite-index.jsonl",
        REPO_ROOT / "corpus",
        example_dir,
    )
    return [c for c in cases if c.kind == "canonical"][:n]


def make_evaluator(inner: Any, max_requests: int = 1000) -> tuple[LlmEvaluator, CountingClient]:
    client = CountingClient(inner, max_requests)
    evaluator = LlmEvaluator(client=client, max_retries=0, enabled=True)
    return evaluator, client


class TestBudgetEnforcement:
    def test_budget_stops_dispatch_and_counts_skips(self, tmp_path: Path) -> None:
        config: LLMPilotConfig = load_pilot_config(PILOT_CONFIG)
        config.max_cases = 2
        config.repeats = 3

        evaluator, client = make_evaluator(StaticResponder(VALID_PAYLOAD), max_requests=4)
        result = run_llm_pilot(config, evaluator, canonical_cases(2), REPO_ROOT, tmp_path / "out")
        assert client.requests == 4
        assert result.skipped_by_budget > 0
        assert result.counters["requests"] == 4
        # 2 cases in repeat 1 (budget 4 -> 2 requests each? no: 1 request per case)
        assert len(json.loads("[]")) == 0  # sanity no-op

    def test_full_pilot_within_budget_is_stable(self, tmp_path: Path) -> None:
        config: LLMPilotConfig = load_pilot_config(PILOT_CONFIG)
        config.max_cases = 1
        repeats = config.repeats

        evaluator, client = make_evaluator(StaticResponder(VALID_PAYLOAD))
        result = run_llm_pilot(config, evaluator, canonical_cases(1), REPO_ROOT, tmp_path / "o")
        assert result.evaluations_attempted == repeats
        assert result.failed_evaluations == 0
        assert client.requests == repeats
        manifest = json.loads(result.manifest_path.read_text())
        assert manifest["stability"]["unanimous_cases"] == 1
        assert manifest["prompt_hash"]


class TestFailureAccounting:
    def test_timeouts_become_failed_records_and_are_counted(self, tmp_path: Path) -> None:
        config: LLMPilotConfig = load_pilot_config(PILOT_CONFIG)
        config.max_cases = 1
        counting = CountingClient(TimeoutResponder(), max_requests=10)
        evaluator = LlmEvaluator(client=counting, max_retries=1, enabled=True)

        result = run_llm_pilot(config, evaluator, canonical_cases(1), REPO_ROOT, tmp_path / "o")
        assert result.counters["timeouts"] >= 1
        records = [json.loads(l) for l in result.records_path.read_text().splitlines()]
        assert records and all(r["evaluation_metadata"].get("failed") for r in records)
