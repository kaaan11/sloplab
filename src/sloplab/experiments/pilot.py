"""Budgeted pilot runner for the opt-in LLM evaluator (V0.2, V27).

Enforces the experiment config's hard limits (max requests, retries) and records
request/error/timeout counters into provenance. Transport is injected, so nothing
here performs live calls; raw model responses are never stored - only normalized,
schema-validated records.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sloplab.evaluators.llm.adapter import LLMResponse
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.runner import current_commit_sha, sha256_file
from sloplab.models.run import CaseRecord
from sloplab.scoring.comparison import repeat_stability
from sloplab.scoring.harness import SuiteCase


class BudgetExhausted(Exception):
    """Raised when the configured request budget is spent."""


class CountingClient:
    """Client wrapper enforcing the request budget and counting outcomes."""

    def __init__(self, inner: Any, max_requests: int) -> None:
        self._inner = inner
        self._max_requests = max_requests
        self.requests = 0
        self.errors = 0
        self.timeouts = 0

    def complete(self, prompt: str) -> LLMResponse:
        if self.requests >= self._max_requests:
            raise BudgetExhausted(f"request budget exhausted ({self._max_requests} requests)")
        self.requests += 1
        try:
            inner = self._inner
            complete_fn = inner.complete
            response: LLMResponse = complete_fn(prompt)
            return response
        except TimeoutError:
            self.timeouts += 1
            self.errors += 1
            raise
        except Exception:
            self.errors += 1
            raise


@dataclass
class PilotRunResult:
    out_dir: Path
    records_path: Path
    manifest_path: Path
    evaluations_attempted: int = 0
    failed_evaluations: int = 0
    skipped_by_budget: int = 0
    counters: dict[str, int] = field(default_factory=dict)
    stability: dict[str, object] = field(default_factory=dict)


class ThrottledClient:
    """Transport wrapper enforcing minimum spacing between requests.

    - Sleeps so that at least ``min_interval_ms`` milliseconds elapse between the
      starts of consecutive ``complete()`` calls (pacing is mandatory whenever
      ``min_interval_ms > 0``; a value of 0 disables pacing).
    - Honors HTTP 429 responses: when the raised error carries status code 429,
      waits for its ``Retry-After`` value (integer seconds or HTTP-date) before
      re-raising, so the evaluator's retry loop retries only after the wait.
    - ``sleep_cap_s`` optionally bounds any single sleep (test hook and safety
      valve); ``None`` honors requested waits in full.
    """

    def __init__(
        self,
        inner: Any,
        *,
        min_interval_ms: int = 0,
        sleep_cap_s: float | None = None,
    ) -> None:
        self._inner = inner
        self._min_interval_s = max(0, min_interval_ms) / 1000.0
        self._sleep_cap_s = sleep_cap_s
        self._last_dispatch: float | None = None

    def _sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        if self._sleep_cap_s is not None:
            seconds = min(seconds, self._sleep_cap_s)
        time.sleep(seconds)

    @staticmethod
    def _retry_after_seconds(exc: Exception) -> float | None:
        import math

        headers = getattr(exc, "headers", None)
        if getattr(exc, "code", None) != 429 or headers is None:
            return None
        raw = headers.get("Retry-After")
        if raw is None:
            return None
        try:
            seconds = float(raw)
        except ValueError:
            try:
                from email.utils import parsedate_to_datetime

                target = parsedate_to_datetime(raw)
                delta = target.timestamp() - time.time()
                return max(0.0, delta)
            except (TypeError, ValueError):
                return None
        # Non-finite values (e.g. "inf") would hang the run forever; treat them
        # as absent and let the evaluator's retry loop proceed after pacing.
        if not math.isfinite(seconds):
            return None
        return max(0.0, seconds)

    def complete(self, prompt: str) -> LLMResponse:
        now = time.monotonic()
        if self._last_dispatch is not None and self._min_interval_s > 0:
            self._sleep(self._min_interval_s - (now - self._last_dispatch))
        self._last_dispatch = time.monotonic()
        try:
            response: LLMResponse = self._inner.complete(prompt)
            return response
        except Exception as exc:  # noqa: BLE001 - transport errors are re-raised
            retry_after = self._retry_after_seconds(exc)
            if retry_after is not None:
                self._sleep(retry_after)
            raise


def _document_for(case: SuiteCase, corpus_root: Path) -> Any:
    from sloplab.corpus.loader import load_derived_fixture

    if case.kind == "canonical" and case.canonical_fixture is not None:
        return case.canonical_fixture.report
    if case.fixture_dir is not None:
        return load_derived_fixture(case.fixture_dir, case.fixture_dir.parents[2]).report
    raise ValueError(f"case {case.case_id} is not loadable")


def run_llm_pilot(
    config: LLMPilotConfig,
    evaluator: object,
    cases: list[SuiteCase],
    repo_root: Path,
    out_dir: Path,
) -> PilotRunResult:
    """Evaluate selected cases across ``config.repeats`` repeats under hard budgets.

    ``evaluator`` must be an :class:`LlmEvaluator` built around a
    :class:`CountingClient` so every underlying request counts against the budget.
    """
    from sloplab.evaluators.llm.adapter import LlmEvaluator
    from sloplab.models.enums import Decision
    from sloplab.models.evaluation import EvaluationContext

    assert isinstance(evaluator, LlmEvaluator)
    selected = cases[: config.max_cases] if config.max_cases else list(cases)

    client = evaluator._client  # noqa: SLF001 - harness wiring by design
    if not isinstance(client, CountingClient):
        raise ValueError("pilot requires an LlmEvaluator built around CountingClient")

    # Effective hard cap: the tighter of config budget and the client's own cap.
    effective_cap = min(config.budget.max_requests, client._max_requests)  # noqa: SLF001

    all_records: list[CaseRecord] = []
    repeat_sets: list[list[CaseRecord]] = []
    skipped_by_budget = 0
    budget_spent = False

    for repeat in range(config.repeats):
        repeat_records: list[CaseRecord] = []
        for case in selected:
            # Clean pre-check: once the budget is spent, stop dispatching work.
            # (The counting client also hard-raises mid-case as a safety net.)
            if client.requests >= effective_cap:
                skipped_by_budget += (
                    len(selected)
                    - len(repeat_records)
                    + (config.repeats - repeat - 1) * len(selected)
                )
                budget_spent = True
                break
            document = _document_for(case, repo_root)
            context = EvaluationContext(
                report=document,
                case_id=case.case_id,
                labels={"expected_decision": case.expected_decision},
            )
            result = evaluator.evaluate(document, context)
            record = CaseRecord.from_result(
                result,
                case_id=case.case_id,
                case_kind="canonical",
                report_class=case.report_class,
                expected_decision=(
                    Decision(case.expected_decision) if case.expected_decision else None
                ),
                parent_id=case.parent_id,
                operator=case.operator,
                seed=case.seed,
            )
            record.evaluation_metadata["repeat_index"] = repeat
            repeat_records.append(record)
        repeat_sets.append(repeat_records)
        all_records.extend(repeat_records)
        if budget_spent:
            break

    stability = (
        repeat_stability(repeat_sets).as_dict()
        if len(repeat_sets) >= 2 and all(repeat_sets)
        else {}
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    records_path = out_dir / "records.jsonl"
    records_path.write_text(
        "".join(r.model_dump_json() + "\n" for r in all_records), encoding="utf-8"
    )

    manifest = {
        "experiment_name": config.name,
        "kind": "llm-pilot",
        "commit_sha": current_commit_sha(repo_root),
        "base_seed": config.base_seed,
        "repeats": config.repeats,
        "selected_cases": len(selected),
        "budget": config.budget.model_dump(),
        "counters": {
            "requests": client.requests,
            "errors": client.errors,
            "timeouts": client.timeouts,
        },
        "stability": stability,
        "prompt_hash": sha256_file(repo_root / config.prompt_file),
        "model_env": config.model_env,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "raw model responses are not stored; only normalized records",
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    failed = sum(1 for r in all_records if r.evaluation_metadata.get("failed"))
    return PilotRunResult(
        out_dir=out_dir,
        records_path=records_path,
        manifest_path=manifest_path,
        evaluations_attempted=len(all_records),
        failed_evaluations=failed,
        skipped_by_budget=skipped_by_budget,
        counters={
            "requests": client.requests,
            "errors": client.errors,
            "timeouts": client.timeouts,
        },
        stability=stability,
    )
