"""E2a: typed failures, outcome ledger, and label capability. No live calls."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from sloplab.corpus.loader import discover_fixtures
from sloplab.evaluators.llm.adapter import LlmEvaluator, LLMResponse, PromptTemplateError
from sloplab.evaluators.llm.failures import EvaluationFailure
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.pilot import CountingClient, run_llm_pilot
from sloplab.models.evaluation import EvaluationContext, EvaluationResult
from sloplab.models.report import ReportDocument
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.materialize import materialize_suite
from sloplab.scoring.harness import build_cases, run_case
from tests._helpers import write_canonical_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "llm_bench_e2a", REPO_ROOT / "scripts" / "llm_bench.py"
)
assert _spec is not None and _spec.loader is not None
llm_bench: ModuleType = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(llm_bench)

TEMPLATE_MARKER = "E2A-LEDGER-MARKER"


def _valid_payload_text() -> str:
    return json.dumps(
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


class _RecordingTransport:
    def __init__(self, payload_text: str, hook: Any = None) -> None:
        self.payload_text = payload_text
        self.hook = hook
        self.prompts: list[str] = []
        self.calls = 0

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        self.prompts.append(prompt)
        if self.hook is not None and self.calls == 1:
            self.hook()
        return LLMResponse(text=self.payload_text, latency_ms=1)


class _FailCallsTransport(_RecordingTransport):
    """Fails exactly the given 1-indexed dispatch numbers; succeeds otherwise."""

    def __init__(self, fail_calls: set[int]) -> None:
        super().__init__(_valid_payload_text())
        self.fail_calls = fail_calls

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        self.prompts.append(prompt)
        if self.calls in self.fail_calls:
            raise TimeoutError("simulated timeout")
        return LLMResponse(text=self.payload_text, latency_ms=1)


class _FailingTransport(_RecordingTransport):
    def __init__(self) -> None:
        super().__init__(_valid_payload_text())

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        self.prompts.append(prompt)
        raise TimeoutError("simulated outage")


def _workspace(tmp_path: Path, review: bool = False) -> dict[str, Any]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "a-000",
        fixture_id="canonical-a-000",
        title="Ledger clean report",
        report_class="valid",
    )
    write_canonical_fixture(
        corpus,
        "b-000",
        fixture_id="canonical-b-000",
        title="Ledger second report",
        report_class="valid",
    )
    policies: dict[str, Any] = {
        "valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]},
    }
    if review:
        write_canonical_fixture(
            corpus,
            "r-000",
            fixture_id="canonical-r-000",
            title="Ledger review report",
            report_class="review",
        )
        policies["review"] = {"variants_per_fixture": 0, "operators": ["impact_inflation"]}
    suite = {
        "name": "ledger-suite",
        "base_seed": 21,
        "corpus_root": str(corpus),
        "include_canonical_cases": True,
        "policies": policies,
    }
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(yaml.safe_dump(suite), encoding="utf-8")
    config = SuiteConfig.model_validate(yaml.safe_load(suite_path.read_text(encoding="utf-8")))
    canonical, _ = discover_fixtures(corpus)
    out_root = tmp_path / "out"
    materialize_suite(config, canonical, out_root)
    cases = build_cases(out_root / "suite-index.jsonl", corpus, out_root)
    return {"corpus": corpus, "out": out_root, "cases": cases}


def _write_template(tmp_path: Path, text: str | None = None) -> Path:
    path = tmp_path / "triage-e2a.md"
    path.write_text(
        text if text is not None else f"Route carefully. {TEMPLATE_MARKER}\n\n{{report_text}}\n",
        encoding="utf-8",
    )
    return path


def _pilot_config(
    prompt_file: Path, max_requests: int = 50, repeats: int = 1, max_cases: int | None = None
) -> LLMPilotConfig:
    return LLMPilotConfig.model_validate(
        {
            "schema_version": 2,
            "name": "ledger-pilot",
            "suite": {"config_path": "benchmarks/suites/v1-core.yaml", "corpus_root": "corpus"},
            "base_seed": 21,
            "repeats": repeats,
            "model_env": "E2A_MODEL",
            "endpoint_env": "E2A_ENDPOINT",
            "api_key_env": "E2A_API_KEY",
            "prompt_file": str(prompt_file),
            "budget": {"max_requests": max_requests},
            "case_selection": "canonical_first",
            "max_cases": max_cases,
        }
    )


def _run_pilot(
    tmp_path: Path,
    prompt_file: Path,
    cases: list[Any],
    transport: Any,
    max_retries: int = 0,
    repeats: int = 1,
    max_requests: int = 50,
    out_name: str = "pilot-out",
) -> Any:
    counting = CountingClient(transport, max_requests)
    evaluator = LlmEvaluator(client=counting, max_retries=max_retries, enabled=True)
    return run_llm_pilot(
        _pilot_config(prompt_file, max_requests=max_requests, repeats=repeats),
        evaluator,
        cases,
        tmp_path,
        tmp_path / out_name,
    )


def _read_outcomes(result: Any) -> list[dict[str, Any]]:
    assert result.outcomes_path is not None
    return [
        json.loads(line)
        for line in result.outcomes_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_records(result: Any) -> list[dict[str, Any]]:
    text = result.records_path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _assert_ledger_equation(manifest: dict[str, Any]) -> None:
    assert manifest["planned"] == (
        manifest["successful"] + manifest["failed"] + manifest["not_run"]
    )
    assert manifest["scored"] == manifest["successful"]


def test_review_failure_never_becomes_accuracy_success(tmp_path: Path) -> None:
    """Timeout/parse failures on review-expected cases yield no success records."""
    paths = _workspace(tmp_path, review=True)
    review_cases = [c for c in paths["cases"] if c.report_class == "review"]
    assert review_cases
    template = _write_template(tmp_path)
    failing = _FailingTransport()
    result = _run_pilot(tmp_path, template, review_cases[:1], failing)
    assert _read_records(result) == []
    outcomes = _read_outcomes(result)
    assert len(outcomes) == 1 and outcomes[0]["status"] == "failed"
    assert outcomes[0]["error_kind"] == "timeout"
    for key in ("decision", "confidence", "dimensions"):
        assert key not in outcomes[0]
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    _assert_ledger_equation(manifest)
    assert manifest["scored"] == 0
    assert result.failed_evaluations == 1

    bad_payload = _RecordingTransport("definitely not json {{{")
    report = review_cases[0].report
    assert report is not None
    with pytest.raises(EvaluationFailure) as exc_info:
        LlmEvaluator(client=CountingClient(bad_payload, max_requests=5), enabled=True).evaluate(
            report,
            EvaluationContext(report=report, case_id="x", labels={}),
        )
    assert exc_info.value.error_kind == "parse"


def test_mixed_success_failure_not_run_ledger(tmp_path: Path) -> None:
    """Every plan yields exactly one outcome; counts balance; refs resolve."""
    paths = _workspace(tmp_path)
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:2]
    assert len(cases) == 2
    template = _write_template(tmp_path)
    transport = _FailCallsTransport({2, 4})
    result = _run_pilot(tmp_path, template, cases, transport, repeats=2, max_requests=50)
    outcomes = _read_outcomes(result)
    assert len(outcomes) == 4
    assert [(o["repeat_index"], o["case_id"]) for o in outcomes] == [
        (r, c.case_id) for r in (0, 1) for c in cases
    ]
    assert len({(o["case_id"], o["repeat_index"]) for o in outcomes}) == 4
    assert [o["status"] for o in outcomes] == ["success", "failed", "success", "failed"]
    for outcome in outcomes:
        if outcome["status"] == "failed":
            for key in ("decision", "confidence", "dimensions"):
                assert key not in outcome
            assert outcome["error_kind"] == "timeout"
    records = _read_records(result)
    refs = {(r["case_id"], r["evaluation_metadata"]["repeat_index"]) for r in records}
    assert len(records) == 2
    for outcome in outcomes:
        if outcome["status"] == "success":
            ref_key = (outcome["case_id"], outcome["repeat_index"])
            assert outcome["record_ref"] == {"case_id": ref_key[0], "repeat_index": ref_key[1]}
            assert ref_key in refs
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    _assert_ledger_equation(manifest)
    assert manifest["successful"] == len(records) == 2
    assert result.evaluations_attempted == 4
    assert result.failed_evaluations == 2


def test_budget_overflow_records_not_run_with_reason(tmp_path: Path) -> None:
    """Spent budget stops dispatch; unstarted plans are explicit not_run rows."""
    paths = _workspace(tmp_path)
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:2]
    template = _write_template(tmp_path)
    result = _run_pilot(tmp_path, template, cases, _FailingTransport(), repeats=2, max_requests=3)
    outcomes = _read_outcomes(result)
    assert len(outcomes) == 4
    assert sorted(o["status"] for o in outcomes) == ["failed", "failed", "failed", "not_run"]
    not_run = [o for o in outcomes if o["status"] == "not_run"]
    assert len(not_run) == 1
    assert not_run[0]["reason"] == "budget_exhausted"
    assert not_run[0]["repeat_index"] == 1
    assert _read_records(result) == []
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    _assert_ledger_equation(manifest)
    assert manifest["not_run"] == 1
    assert manifest["failed"] == 3
    assert result.skipped_by_budget == 1
    assert result.evaluations_attempted == 3


def test_all_failed_is_valid_technical_result(tmp_path: Path) -> None:
    """Total failure: empty records file plus a complete ledger."""
    paths = _workspace(tmp_path)
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:1]
    template = _write_template(tmp_path)
    result = _run_pilot(tmp_path, template, cases, _FailingTransport(), repeats=2)
    assert result.records_path.read_bytes() == b""
    outcomes = _read_outcomes(result)
    assert len(outcomes) == 2
    assert all(o["status"] == "failed" for o in outcomes)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    _assert_ledger_equation(manifest)
    assert (manifest["successful"], manifest["scored"]) == (0, 0)
    assert result.evaluations_attempted == result.failed_evaluations == 2


def test_retry_success_and_persistent_failure_hashes(tmp_path: Path) -> None:
    """Retry reuses one render; failure attempts and hashes are exact."""

    def _raise_once() -> None:
        raise TimeoutError("simulated timeout")

    paths = _workspace(tmp_path)
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:1]
    template = _write_template(tmp_path)
    recorder = _RecordingTransport(_valid_payload_text(), hook=_raise_once)
    counting = CountingClient(recorder, max_requests=50)
    evaluator = LlmEvaluator(client=counting, max_retries=1, enabled=True)
    result = run_llm_pilot(
        _pilot_config(template), evaluator, cases, tmp_path, tmp_path / "o-retry"
    )
    assert recorder.calls == 2
    assert recorder.prompts[0] == recorder.prompts[1]
    assert counting.physical_dispatches == 2
    records = _read_records(result)
    assert len(records) == 1
    expected = hashlib.sha256(recorder.prompts[0].encode("utf-8")).hexdigest()
    assert records[0]["evaluation_metadata"]["rendered_prompt_hash"] == expected
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["prompt_hash"] == hashlib.sha256(template.read_bytes()).hexdigest()

    failing = _FailingTransport()
    counting2 = CountingClient(failing, max_requests=50)
    evaluator2 = LlmEvaluator(client=counting2, max_retries=2, enabled=True)
    result2 = run_llm_pilot(
        _pilot_config(template), evaluator2, cases, tmp_path, tmp_path / "o-fail3"
    )
    outcomes2 = _read_outcomes(result2)
    assert len(outcomes2) == 1
    assert outcomes2[0]["adapter_attempts"] == 3
    assert (
        outcomes2[0]["rendered_prompt_hash"]
        == hashlib.sha256(failing.prompts[0].encode("utf-8")).hexdigest()
    )
    assert all(p == failing.prompts[0] for p in failing.prompts)


def test_legacy_placeholder_rejected_unexpected_propagates_config_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy failed results never record; unexpected/config errors keep meaning."""

    class _LegacyStub:
        name = "legacy-stub"
        version = "0"

        def __init__(self, rendered: str) -> None:
            self.rendered = rendered

        def evaluate(self, report: ReportDocument, context: Any) -> Any:
            from sloplab.models.enums import Decision
            from sloplab.models.evaluation import DimensionScores

            return EvaluationResult(
                evaluator_name=self.name,
                evaluator_version=self.version,
                case_id=context.case_id,
                decision=Decision.NEEDS_MANUAL_REVIEW,
                confidence=0.0,
                dimensions=DimensionScores.from_dict(
                    {
                        "reproducibility": 0.5,
                        "evidence_completeness": 0.5,
                        "claim_evidence_consistency": 0.5,
                        "impact_calibration": 0.5,
                        "scope_consistency": 0.5,
                    }
                ),
                findings=[],
                rationale="legacy",
                metadata={"failed": True, "rendered_prompt_hash": self.rendered},
            )

    paths = _workspace(tmp_path)
    case = next(c for c in paths["cases"] if c.kind == "mutated")
    with pytest.raises(EvaluationFailure) as exc_info:
        run_case(_LegacyStub("abc123"), case)
    assert exc_info.value.error_kind == "legacy"
    assert "decision" not in exc_info.value.__dict__
    assert exc_info.value.rendered_prompt_hash == "abc123"

    with pytest.raises(EvaluationFailure) as exc_info2:
        bare = _LegacyStub("")
        run_case(bare, case)
    assert exc_info2.value.rendered_prompt_hash == ""

    template = _write_template(tmp_path)
    counting = CountingClient(_RecordingTransport(_valid_payload_text()), max_requests=50)
    boom = LlmEvaluator(client=counting, max_retries=0, enabled=True)

    def _explode(self: Any, report: Any, context: Any) -> Any:
        _ = (self, report, context)
        raise RuntimeError("simulated bug")

    # Class-level patch: the pilot binds a fresh copy via with_prompt, so an
    # instance attribute would not survive; the fixture auto-undoes this.
    monkeypatch.setattr(LlmEvaluator, "evaluate", _explode)
    with pytest.raises(RuntimeError, match="simulated bug"):
        run_llm_pilot(_pilot_config(template), boom, [case], tmp_path, tmp_path / "o-boom")
    assert not (tmp_path / "o-boom").exists()

    with pytest.raises(PromptTemplateError, match="does-not-exist"):
        run_llm_pilot(
            _pilot_config(tmp_path / "does-not-exist.md"),
            boom,
            [case],
            tmp_path,
            tmp_path / "o-cfg",
        )
    assert not (tmp_path / "o-cfg").exists()


def test_partial_success_omits_stability_with_reason(tmp_path: Path) -> None:
    """Missing success repeats are not counted unanimous; the gap is reported."""
    paths = _workspace(tmp_path)
    cases = [c for c in paths["cases"] if c.kind == "mutated"][:1]
    template = _write_template(tmp_path)
    transport = _FailCallsTransport({2})
    result = _run_pilot(tmp_path, template, cases, transport, repeats=3)
    assert len(_read_records(result)) == 2
    assert result.stability == {}
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["stability"] == {}
    assert manifest["stability_omitted_reason"] == "incomplete-success-coverage"
    _assert_ledger_equation(manifest)


def test_labels_capability_gate(tmp_path: Path) -> None:
    """Content evaluators see empty labels; the oracle opts in and still decides."""

    class _LabelSpy:
        name = "label-spy"
        version = "0"

        def __init__(self) -> None:
            self.seen: list[dict[str, Any]] = []

        def evaluate(self, report: ReportDocument, context: Any) -> Any:
            self.seen.append(dict(context.labels))
            context.labels["injected"] = True
            dims = context.labels.get("expected_dimensions")
            if isinstance(dims, dict):
                dims.clear()
            from sloplab.evaluators.base import get_evaluator

            return get_evaluator("rules-baseline").evaluate(report, context)

    from sloplab.evaluators.base import get_evaluator

    paths = _workspace(tmp_path)
    case = next(c for c in paths["cases"] if c.kind == "canonical")
    pristine = dict(case.expected_dimensions)
    assert pristine
    spy = _LabelSpy()
    run_case(spy, case)
    assert spy.seen == [{}]
    oracle_records = [
        run_case(get_evaluator("oracle"), case),
        run_case(get_evaluator("oracle"), case),
    ]
    assert all(r.correct for r in oracle_records)
    assert dict(case.expected_dimensions) == pristine


def test_script_and_pilot_share_ledger_accounting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    """The script prints ledger states; failures never become success lines."""
    monkeypatch.setenv("SLOPLAB_LLM_MODEL", "openai/gpt-oss-20b:free")
    monkeypatch.setenv("SLOPLAB_LLM_ENDPOINT", "https://example.invalid/v1")
    monkeypatch.setenv("SLOPLAB_LLM_API_KEY", "test-key-never-logged")

    class _AlwaysFail:
        def __init__(self, **kwargs: Any) -> None:
            self.calls = 0

        def complete(self, prompt: str) -> Any:
            self.calls += 1
            _ = prompt
            raise TimeoutError("simulated outage")

    monkeypatch.setattr(llm_bench, "HttpLLMClient", _AlwaysFail)
    out = tmp_path / "llm-bench-results.jsonl"
    rc = llm_bench.main(["--max-cases", "1", "--repeats", "1", "--out", str(out)])
    assert rc == 0
    assert out.read_bytes() == b""
    bundle = tmp_path / "llm-bench-results.bundle"
    outcomes = [
        json.loads(line)
        for line in (bundle / "outcomes.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(outcomes) == 1 and outcomes[0]["status"] == "failed"
    assert outcomes[0]["error_kind"] == "timeout"
    assert "decision" not in outcomes[0]
    printed = capsys.readouterr().out
    assert "FAILED-EVAL (timeout)" in printed
    assert "failed evaluations: 1/1" in printed
    assert "test-key-never-logged" not in printed
    assert "test-key-never-logged" not in (bundle / "outcomes.jsonl").read_text(encoding="utf-8")
