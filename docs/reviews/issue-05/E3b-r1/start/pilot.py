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
from sloplab.evaluators.llm.failures import (
    BudgetExhausted,
    DeadlineExceeded,
    EvaluationFailure,
    raise_if_failed_result,
)
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.runner import current_commit_sha
from sloplab.models.run import CaseRecord
from sloplab.scoring.comparison import repeat_stability
from sloplab.scoring.harness import SuiteCase


class CountingClient:
    """Client wrapper enforcing the request budget and counting outcomes.

    This is the single reservation owner for physical dispatches. It sits
    directly around the transport (``ThrottledClient(CountingClient(...))``),
    so every reservation is immediately followed by the physical transport
    start with no refusal path in between: pacing and ``Retry-After`` waits
    (with their deadline refusals) happen *above* the reservation, and the
    pre-dispatch deadline check below refuses *before* incrementing. Hence a
    single counter holds by construction:

    ``physical_dispatches == reservations consumed == transport starts``.

    No separate reservation counter exists, so no cancel/consume semantics
    are needed. Single-threaded dispatch cannot interleave, but no
    cross-thread atomicity is claimed.

    Inner-transport contract: :class:`BudgetExhausted` and
    :class:`DeadlineExceeded` from ``inner.complete()`` mean the transport
    did not start, so the reservation is returned unconsumed and no error
    is recorded. Any error after a real transport start (success, timeout,
    429, transport error) keeps its reservation as a physical dispatch.
    """

    def __init__(self, inner: Any, max_requests: int) -> None:
        self._inner = inner
        self._max_requests = max_requests
        self._deadline_monotonic: float | None = None
        self.physical_dispatches = 0
        self.errors = 0
        self.timeouts = 0

    def _reserve_or_raise(self) -> None:
        if self.physical_dispatches >= self._max_requests:
            raise BudgetExhausted(f"request budget exhausted ({self._max_requests} requests)")
        self.physical_dispatches += 1

    def set_deadline(self, deadline_monotonic: float | None) -> None:
        """Arm (or clear) the run deadline; forwarded inward when supported."""
        self._deadline_monotonic = deadline_monotonic
        setter = getattr(self._inner, "set_deadline", None)
        if callable(setter):
            setter(deadline_monotonic)

    def complete(self, prompt: str) -> LLMResponse:
        # Pre-dispatch deadline refusal consumes nothing: neither a
        # reservation nor a physical dispatch.
        if self._deadline_monotonic is not None and time.monotonic() >= self._deadline_monotonic:
            raise DeadlineExceeded("run deadline expired before dispatch")
        self._reserve_or_raise()
        try:
            inner = self._inner
            complete_fn = inner.complete
            response: LLMResponse = complete_fn(prompt)
            return response
        except (BudgetExhausted, DeadlineExceeded):
            # Pre-dispatch refusal from below (spent budget, or the run
            # deadline expiring between the two checks): the transport never
            # started, so the reservation is returned and nothing is counted
            # as physical, error, or timeout. The hard cap is preserved.
            self.physical_dispatches -= 1
            raise
        except TimeoutError:
            self.timeouts += 1
            self.errors += 1
            raise
        except Exception:
            self.errors += 1
            raise


@dataclass
class PilotRunResult:
    """Outcome of one pilot invocation.

    ``evaluations_attempted`` counts dispatched evaluations (successful +
    failed) and excludes ``not_run`` plans, so it is NOT equal to the records
    line count when failures exist. ``successful`` equals the scored records.
    """

    out_dir: Path
    records_path: Path
    manifest_path: Path
    outcomes_path: Path | None = None
    completion_path: Path | None = None
    evaluations_attempted: int = 0
    failed_evaluations: int = 0
    skipped_by_budget: int = 0
    planned: int = 0
    successful: int = 0
    failed: int = 0
    not_run: int = 0
    scored: int = 0
    counters: dict[str, int] = field(default_factory=dict)
    stability: dict[str, object] = field(default_factory=dict)
    coverage: dict[str, object] = field(default_factory=dict)


class OutcomeCoverageError(ValueError):
    """The outcome ledger does not reconcile with the planned repeat union."""


OUTCOMES_SCHEMA_VERSION = 1
NOT_RUN_BUDGET_REASON = "budget_exhausted"
NOT_RUN_DEADLINE_REASON = "deadline_exceeded"


def _success_outcome(case_id: str, evaluator_name: str, repeat: int) -> dict[str, Any]:
    return {
        "schema_version": OUTCOMES_SCHEMA_VERSION,
        "status": "success",
        "case_id": case_id,
        "evaluator_name": evaluator_name,
        "repeat_index": repeat,
        "record_ref": {"case_id": case_id, "repeat_index": repeat},
    }


def _failed_outcome(
    case_id: str, evaluator_name: str, repeat: int, failure: EvaluationFailure
) -> dict[str, Any]:
    return {
        "schema_version": OUTCOMES_SCHEMA_VERSION,
        "status": "failed",
        "case_id": case_id,
        "evaluator_name": evaluator_name,
        "repeat_index": repeat,
        "error_kind": failure.error_kind,
        "adapter_attempts": failure.adapter_attempts,
        "rendered_prompt_hash": failure.rendered_prompt_hash,
        "detail": failure.detail,
    }


def _not_run_outcome(case_id: str, evaluator_name: str, repeat: int, reason: str) -> dict[str, Any]:
    return {
        "schema_version": OUTCOMES_SCHEMA_VERSION,
        "status": "not_run",
        "case_id": case_id,
        "evaluator_name": evaluator_name,
        "repeat_index": repeat,
        "reason": reason,
    }


def check_outcome_coverage(
    outcomes: list[Any],
    *,
    case_ids: list[str],
    evaluator_name: str,
    repeats: int,
) -> list[str]:
    """Reconcile ledger keys 1:1 with the planned (case, evaluator, repeat) union.

    The planned union is set by selection identity (``case_ids`` in order) plus
    evaluator plus repeat count. Missing, duplicate, foreign, or malformed rows
    are coverage errors; an empty list means clean.
    """
    errors: list[str] = []
    expected = {(cid, evaluator_name, r) for r in range(repeats) for cid in case_ids}
    seen: list[tuple[Any, Any, Any]] = []
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            errors.append("malformed outcome row (not an object)")
            continue
        try:
            key = (outcome["case_id"], outcome["evaluator_name"], outcome["repeat_index"])
        except KeyError as exc:
            errors.append(f"malformed outcome row (missing {exc})")
            continue
        if outcome.get("status") not in ("success", "failed", "not_run"):
            errors.append(f"malformed outcome row for {key} (bad status)")
        seen.append(key)
    for key in sorted(set(seen) - expected):
        errors.append(f"foreign outcome for {key}")
    counts: dict[tuple[Any, Any, Any], int] = {}
    for key in seen:
        counts[key] = counts.get(key, 0) + 1
    for key in sorted(k for k, n in counts.items() if n > 1):
        errors.append(f"duplicate outcome for {key}")
    for key in sorted(expected - set(seen)):
        errors.append(f"missing outcome for {key}")
    return errors


class ThrottledClient:
    """Transport wrapper enforcing minimum spacing between requests.

    Wiring order is ``ThrottledClient(CountingClient(transport))``: pacing
    and ``Retry-After`` waits (with their deadline refusals) happen *before*
    the budget reservation, so a refused wait consumes neither reservation
    nor physical dispatch.

    - Sleeps so that at least ``min_interval_ms`` milliseconds elapse between
      the starts of consecutive *real* dispatches (pacing is mandatory
      whenever ``min_interval_ms > 0``; a value of 0 disables pacing). The
      pacing baseline (``_last_dispatch``) advances only when the inner call
      actually starts; pre-dispatch refusals (budget/deadline) leave it
      untouched.
    - Honors HTTP 429 responses: when the raised error carries status code
      429, waits for its ``Retry-After`` value (integer seconds or HTTP-date)
      before re-raising, so the evaluator's retry loop retries only after the
      wait. ``Retry-After`` waits are always honored in full and are never
      shortened by ``sleep_cap_s``.
    - ``sleep_cap_s`` bounds pacing sleeps only (test hook and safety valve);
      ``None`` honors pacing waits in full.
    - ``deadline_monotonic`` optionally refuses waits that would cross a
      monotonic run deadline, raising :class:`DeadlineExceeded` instead of
      sleeping. Pacing, per-request timeouts, and Retry-After waits stay
      separate contracts.
    """

    def __init__(
        self,
        inner: Any,
        *,
        min_interval_ms: int = 0,
        sleep_cap_s: float | None = None,
        deadline_monotonic: float | None = None,
    ) -> None:
        self._inner = inner
        self._min_interval_ms = max(0, min_interval_ms)
        self._min_interval_s = self._min_interval_ms / 1000.0
        self._sleep_cap_s = sleep_cap_s
        self._deadline_monotonic = deadline_monotonic
        self._last_dispatch: float | None = None

    def set_deadline(self, deadline_monotonic: float | None) -> None:
        """Arm (or clear) the run deadline; forwarded inward when supported."""
        self._deadline_monotonic = deadline_monotonic
        setter = getattr(self._inner, "set_deadline", None)
        if callable(setter):
            setter(deadline_monotonic)

    def _sleep(self, seconds: float) -> None:
        """Bounded sleep for pacing waits (the ``sleep_cap_s`` test hook)."""
        if seconds <= 0:
            return
        if self._sleep_cap_s is not None:
            seconds = min(seconds, self._sleep_cap_s)
        time.sleep(seconds)

    def _sleep_full(self, seconds: float) -> None:
        """Uncapped sleep for provider ``Retry-After`` waits (never shortened)."""
        if seconds <= 0:
            return
        time.sleep(seconds)

    def _sleep_or_raise(self, seconds: float, *, capped: bool) -> None:
        """Sleep unless the wait crosses the armed deadline (then refuse).

        ``capped=True`` applies the pacing ``sleep_cap_s`` hook; provider
        ``Retry-After`` waits pass ``capped=False`` and are honored in full.
        """
        if seconds <= 0:
            return
        if (
            self._deadline_monotonic is not None
            and time.monotonic() + seconds > self._deadline_monotonic
        ):
            raise DeadlineExceeded(f"required wait {seconds:.3f}s does not fit the run deadline")
        if capped:
            self._sleep(seconds)
        else:
            self._sleep_full(seconds)

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
            self._sleep_or_raise(self._min_interval_s - (now - self._last_dispatch), capped=True)
        start = time.monotonic()
        try:
            response: LLMResponse = self._inner.complete(prompt)
        except (BudgetExhausted, DeadlineExceeded):
            # Pre-dispatch refusal from below (spent budget or expired run
            # deadline): no transport started, so the pacing baseline is
            # left untouched and the refusal propagates unchanged.
            raise
        except Exception as exc:  # noqa: BLE001 - transport errors are re-raised
            # A transport call really started (even a 429 arrived over the
            # wire), so the pacing baseline advances before any backoff wait.
            self._last_dispatch = start
            retry_after = self._retry_after_seconds(exc)
            if retry_after is not None:
                self._sleep_or_raise(retry_after, capped=False)
            raise
        self._last_dispatch = start
        return response


def _document_for(case: SuiteCase, corpus_root: Path) -> Any:
    """Return the run input report for ``case`` (E1b snapshot first).

    Delegates to :func:`sloplab.scoring.harness.case_document`: cases from
    :func:`build_cases` use their stored report, so later disk changes cannot
    alter pilot inputs. ``corpus_root`` is kept for signature compatibility with
    the legacy disk-reload path, which serves only directly constructed cases
    without a snapshot.
    """
    from sloplab.scoring.harness import case_document

    _ = corpus_root
    return case_document(case)


def build_pilot_client_chain(
    transport: Any,
    *,
    min_interval_ms: int,
    max_requests: int,
    sleep_cap_s: float | None = None,
) -> ThrottledClient:
    """Build the single canonical pilot execution chain from config values.

    This is the one constructor for the production path
    (``scripts/llm_bench.py``) and for test doubles: pacing outside, the
    single budget owner directly around the transport. ``sleep_cap_s`` is a
    pacing-only test hook; production passes ``None``.
    """
    counting = CountingClient(transport, max_requests=max_requests)
    return ThrottledClient(counting, min_interval_ms=min_interval_ms, sleep_cap_s=sleep_cap_s)


def _normalize_pilot_chain(
    client: Any,
    *,
    min_interval_ms: int,
) -> tuple[Any, CountingClient]:
    """Validate (or canonicalize) an evaluator client chain pre-dispatch.

    Returns ``(outer_client, budget_owner)``. A bare :class:`CountingClient`
    is normalized by wrapping it with the configured pacing, so direct pilot
    calls apply exactly the production setup. Anything else that is not the
    canonical ``ThrottledClient(CountingClient(transport))`` shape — missing
    or double budget owner, misordered wrappers, extra throttles, or a pacing
    value diverging from config — is rejected with an explanatory
    :class:`ValueError` before any dispatch. There is no silent bypass.
    """
    nodes: list[Any] = []
    seen = client
    while seen is not None and hasattr(seen, "_inner"):
        nodes.append(seen)
        seen = seen._inner
    owners = [node for node in nodes if isinstance(node, CountingClient)]
    throttles = [node for node in nodes if isinstance(node, ThrottledClient)]
    if not owners:
        raise ValueError("pilot requires an LlmEvaluator built around CountingClient")
    if len(owners) > 1:
        raise ValueError(
            "pilot chain has more than one CountingClient budget owner; "
            "use build_pilot_client_chain for a single owner"
        )
    if len(throttles) > 1:
        raise ValueError(
            "pilot chain has more than one ThrottledClient; "
            "use build_pilot_client_chain for a single pacing owner"
        )
    counting = owners[0]
    if not throttles:
        if nodes != [counting]:
            raise ValueError(
                "pilot chain has a foreign wrapper around the budget owner; "
                "use build_pilot_client_chain for the canonical shape"
            )
        # Bare budget owner: normalize to the canonical setup with config pacing.
        return (
            ThrottledClient(counting, min_interval_ms=min_interval_ms),
            counting,
        )
    throttle = throttles[0]
    if nodes != [throttle, counting]:
        raise ValueError(
            "pilot chain is not ThrottledClient(CountingClient(transport)); "
            "use build_pilot_client_chain for the canonical shape"
        )
    if throttle._min_interval_ms != max(0, min_interval_ms):  # noqa: SLF001
        raise ValueError(
            f"pilot chain pacing ({throttle._min_interval_ms} ms) diverges from "  # noqa: SLF001
            f"config ({min_interval_ms} ms)"
        )
    return throttle, counting


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
    The client chain is validated (or normalized to the canonical
    ``ThrottledClient(CountingClient(transport))`` setup from config) before
    any dispatch, so direct pilot calls apply exactly the production pacing,
    deadline, and hard-cap policy. The config prompt file is resolved once here
    and bound to a copy of the evaluator; the caller's evaluator object is
    never mutated.
    """
    from sloplab.evaluators.llm.adapter import (
        PROMPT_RENDERER_VERSION,
        LlmEvaluator,
        load_prompt_template,
    )
    from sloplab.experiments.bundle import invalidate_completion
    from sloplab.models.enums import Decision
    from sloplab.models.evaluation import EvaluationContext

    # A reused output directory must stop looking complete before any part of
    # the replacement run begins, including model dispatch.
    invalidate_completion(out_dir)

    assert isinstance(evaluator, LlmEvaluator)
    # Single execution boundary: validate or canonicalize the chain before any
    # dispatch. Config pacing/deadline/cap values cannot diverge from the
    # wrappers; miswired chains fail here with a config error, never silently.
    outer_client, counting = _normalize_pilot_chain(
        evaluator._client,  # noqa: SLF001 - harness wiring by design
        min_interval_ms=config.budget.min_interval_ms,
    )
    # Resolve + freeze the prompt before any dispatch or output: later file
    # changes or deletion cannot alter sent text or manifest identity. A relative
    # prompt_file resolves against repo_root; an absolute one passes through
    # unchanged (pathlib behaviour, kept intentionally).
    loaded_prompt = load_prompt_template(repo_root / config.prompt_file)
    active = evaluator.with_prompt(loaded_prompt.text)
    # Bind the validated (possibly normalized) chain to the pilot-local copy;
    # the caller's evaluator object keeps its original client.
    active._client = outer_client  # noqa: SLF001 - harness wiring by design
    selected = cases[: config.max_cases] if config.max_cases else list(cases)

    # A directly supplied client may intentionally enforce a tighter safety cap.
    # Record the applied value separately so provenance never claims the looser
    # config cap was effective.
    effective_cap = min(config.budget.max_requests, counting._max_requests)  # noqa: SLF001

    # Monotonic run deadline (None disables it); armed into the transport chain
    # so oversized pacing/Retry-After waits refuse instead of sleeping through it,
    # and so each HTTP dispatch is bounded by the remaining run time.
    run_deadline: float | None = None
    if config.budget.deadline_s is not None:
        run_deadline = time.monotonic() + config.budget.deadline_s
    outer_client.set_deadline(run_deadline)

    def _remaining_plans(repeat: int, index: int) -> list[tuple[int, SuiteCase]]:
        """Unstarted (repeat, case) plans from ``index`` on, in ledger order."""
        pending: list[tuple[int, SuiteCase]] = [
            (repeat, pending_case) for pending_case in selected[index:]
        ]
        for later in range(repeat + 1, config.repeats):
            pending.extend((later, pending_case) for pending_case in selected)
        return pending

    all_records: list[CaseRecord] = []
    success_by_repeat: list[list[CaseRecord]] = []
    outcomes: list[dict[str, Any]] = []
    successful = 0
    failed = 0
    not_run = 0
    skipped_by_budget = 0
    budget_spent = False
    evaluator_name = active.name

    for repeat in range(config.repeats):
        repeat_success: list[CaseRecord] = []
        for index, case in enumerate(selected):
            # Clean pre-check: once the budget is spent, stop dispatching work.
            # (The counting client also hard-raises mid-case as a safety net.)
            # Every unstarted plan becomes an explicit not_run outcome row.
            if counting.physical_dispatches >= effective_cap:
                for pending_repeat, pending_case in _remaining_plans(repeat, index):
                    outcomes.append(
                        _not_run_outcome(
                            pending_case.case_id,
                            evaluator_name,
                            pending_repeat,
                            NOT_RUN_BUDGET_REASON,
                        )
                    )
                    not_run += 1
                    skipped_by_budget += 1
                budget_spent = True
                break
            if run_deadline is not None and time.monotonic() >= run_deadline:
                for pending_repeat, pending_case in _remaining_plans(repeat, index):
                    outcomes.append(
                        _not_run_outcome(
                            pending_case.case_id,
                            evaluator_name,
                            pending_repeat,
                            NOT_RUN_DEADLINE_REASON,
                        )
                    )
                    not_run += 1
                budget_spent = True
                break
            document = _document_for(case, repo_root)
            # Data minimization, not a sandbox: the LLM sees no ground truth.
            context = EvaluationContext(report=document, case_id=case.case_id, labels={})
            try:
                result = raise_if_failed_result(active.evaluate(document, context))
            except EvaluationFailure as exc:
                outcomes.append(_failed_outcome(case.case_id, evaluator_name, repeat, exc))
                failed += 1
                continue
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
            repeat_success.append(record)
            all_records.append(record)
            outcomes.append(_success_outcome(case.case_id, evaluator_name, repeat))
            successful += 1
        success_by_repeat.append(repeat_success)
        if budget_spent:
            break

    # Stability only on full success coverage: a case missing from any repeat
    # must not read as unanimous via union counting (E2b owns coverage checks).
    full_coverage = (
        len(selected) > 0
        and len(success_by_repeat) == config.repeats
        and all(len(rs) == len(selected) for rs in success_by_repeat)
    )
    if len(success_by_repeat) >= 2 and full_coverage:
        stability = repeat_stability(success_by_repeat).as_dict()
        stability_omitted_reason: str | None = None
    elif config.repeats < 2 or not selected:
        stability = {}
        stability_omitted_reason = "single-repeat-or-empty"
    else:
        stability = {}
        stability_omitted_reason = "incomplete-success-coverage"

    planned = successful + failed + not_run
    scored = successful
    coverage_errors = check_outcome_coverage(
        outcomes,
        case_ids=[case.case_id for case in selected],
        evaluator_name=evaluator_name,
        repeats=config.repeats,
    )
    if coverage_errors:
        raise OutcomeCoverageError(
            f"pilot ledger does not reconcile: {coverage_errors[0]}"
            + (f" (+{len(coverage_errors) - 1} more)" if len(coverage_errors) > 1 else "")
        )
    coverage: dict[str, object] = {
        "expected": len(selected) * config.repeats,
        "successful": successful,
        "complete": full_coverage,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    records_path = out_dir / "records.jsonl"
    records_path.write_text(
        "".join(r.model_dump_json() + "\n" for r in all_records), encoding="utf-8"
    )
    outcomes_path = out_dir / "outcomes.jsonl"
    outcomes_path.write_text(
        "".join(json.dumps(outcome, sort_keys=True) + "\n" for outcome in outcomes),
        encoding="utf-8",
    )

    manifest = {
        "experiment_name": config.name,
        "kind": "llm-pilot",
        "commit_sha": current_commit_sha(repo_root),
        "base_seed": config.base_seed,
        "repeats": config.repeats,
        "selected_cases": len(selected),
        "budget": config.budget.model_dump(),
        "effective_max_requests": effective_cap,
        "counters": {
            "physical_dispatches": counting.physical_dispatches,
            "errors": counting.errors,
            "timeouts": counting.timeouts,
        },
        "planned": planned,
        "successful": successful,
        "failed": failed,
        "not_run": not_run,
        "scored": scored,
        "stability": stability,
        "stability_omitted_reason": stability_omitted_reason,
        "coverage": coverage,
        # Technical publication vs scientific sufficiency are separate fields
        # and must never be equated: bundle_complete says every bundle file
        # was published (the marker below covers them); coverage_sufficient
        # says every planned case x repeat succeeded (full_coverage).
        "bundle_complete": True,
        "coverage_sufficient": full_coverage,
        # SHA-256 of the original UTF-8 template bytes frozen at pilot start
        # (no newline normalization); the same bytes every dispatch rendered.
        "prompt_hash": loaded_prompt.sha256,
        "prompt_renderer_version": PROMPT_RENDERER_VERSION,
        "model_env": config.model_env,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "raw model responses are not stored; only normalized records",
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # Publish last: the completion marker covers records, outcomes, and the
    # manifest, so the bundle never looks complete before all three exist.
    from sloplab.experiments.bundle import write_completion

    completion_path = write_completion(out_dir, kind="llm-pilot")

    return PilotRunResult(
        out_dir=out_dir,
        records_path=records_path,
        manifest_path=manifest_path,
        outcomes_path=outcomes_path,
        completion_path=completion_path,
        evaluations_attempted=successful + failed,
        failed_evaluations=failed,
        skipped_by_budget=not_run,
        planned=planned,
        successful=successful,
        failed=failed,
        not_run=not_run,
        scored=scored,
        counters={
            "physical_dispatches": counting.physical_dispatches,
            "errors": counting.errors,
            "timeouts": counting.timeouts,
        },
        stability=stability,
        coverage=coverage,
    )
