"""E1c: pilot prompt binding — sent text and recorded identity come from one frozen template.

Scope: file-template loading/validation, single-pass rendering, with_prompt binding
without mutating the caller, manifest prompt_hash meaning, and per-observation
rendered_prompt_hash (success, retry, and failure paths). No live calls.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from sloplab.corpus.loader import discover_fixtures
from sloplab.evaluators.llm.adapter import (
    PROMPT_RENDERER_VERSION,
    PROMPT_TEMPLATE,
    LlmEvaluator,
    LLMResponse,
    PromptTemplateError,
    load_prompt_template,
)
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.pilot import CountingClient, _document_for, run_llm_pilot
from sloplab.models.evaluation import EvaluationContext
from sloplab.models.suite import SuiteConfig
from sloplab.mutations.materialize import materialize_suite
from sloplab.scoring.harness import build_cases
from tests._helpers import write_canonical_fixture

TEMPLATE_MARKER = "E1C-UNIQUE-INSTRUCTION-MARKER"


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
    """Fake transport recording prompts; hook runs before the first response."""

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


class _FailingTransport:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.calls = 0

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        self.prompts.append(prompt)
        raise TimeoutError("simulated outage")


def _materialized_mutated_cases(tmp_path: Path) -> list[Any]:
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus,
        "v-000",
        fixture_id="canonical-v-000",
        title="Prompt binding valid report",
        report_class="valid",
    )
    write_canonical_fixture(
        corpus,
        "i-000",
        fixture_id="canonical-i-000",
        title="Prompt binding invalid report",
        report_class="invalid",
    )
    suite = {
        "name": "prompt-suite",
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
    mutated = [c for c in cases if c.kind == "mutated"]
    assert mutated
    return mutated


def _write_template(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _pilot_config(prompt_file: Path, max_requests: int = 50, repeats: int = 1) -> LLMPilotConfig:
    return LLMPilotConfig.model_validate(
        {
            "schema_version": 2,
            "name": "prompt-pilot",
            "suite": {"config_path": "benchmarks/suites/v1-core.yaml", "corpus_root": "corpus"},
            "base_seed": 21,
            "repeats": repeats,
            "model_env": "E1C_MODEL",
            "endpoint_env": "E1C_ENDPOINT",
            "api_key_env": "E1C_API_KEY",
            "prompt_file": str(prompt_file),
            "budget": {"max_requests": max_requests},
            "case_selection": "canonical_first",
            "max_cases": None,
        }
    )


def _run_pilot(
    tmp_path: Path,
    prompt_file: Path,
    cases: list[Any],
    transport: Any,
    max_retries: int = 0,
    repeats: int = 1,
    out_name: str = "pilot-out",
) -> Any:
    counting = CountingClient(transport, max_requests=50)
    evaluator = LlmEvaluator(client=counting, max_retries=max_retries, enabled=True)
    return run_llm_pilot(
        _pilot_config(prompt_file, repeats=repeats),
        evaluator,
        cases,
        tmp_path,
        tmp_path / out_name,
    )


def _record_map(result: Any) -> dict[str, Any]:
    return {
        json.loads(line)["case_id"]: json.loads(line)
        for line in result.records_path.read_text(encoding="utf-8").splitlines()
    }


def test_file_instructions_used_and_hashes_bound(tmp_path: Path) -> None:
    """Sent text carries file instructions; both hashes verify independently."""
    template = _write_template(
        tmp_path, "triage-e1c.md", f"Route carefully. {TEMPLATE_MARKER}\n\n{{report_text}}\n"
    )
    cases = _materialized_mutated_cases(tmp_path)
    transport = _RecordingTransport(_valid_payload_text())
    result = _run_pilot(tmp_path, template, cases, transport)
    assert transport.calls == len(cases) > 0
    assert all(TEMPLATE_MARKER in prompt for prompt in transport.prompts)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["prompt_hash"] == hashlib.sha256(template.read_bytes()).hexdigest()
    assert manifest["prompt_renderer_version"] == PROMPT_RENDERER_VERSION
    by_case = _record_map(result)
    for case, prompt in zip(cases, transport.prompts, strict=True):
        record = by_case[case.case_id]
        assert (
            record["evaluation_metadata"]["rendered_prompt_hash"]
            == hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        )


def test_midrun_change_and_delete_frozen(tmp_path: Path) -> None:
    """Rewriting/deleting the template mid-run changes neither text nor identity."""
    template = _write_template(
        tmp_path, "triage-e1c.md", f"First version. {TEMPLATE_MARKER}\n\n{{report_text}}\n"
    )
    first_bytes = template.read_bytes()
    cases = _materialized_mutated_cases(tmp_path)[:1]

    def _sabotage() -> None:
        template.write_text("Second version, must never send.\n\n{report_text}\n")
        template.unlink()

    transport = _RecordingTransport(_valid_payload_text(), hook=_sabotage)
    result = _run_pilot(tmp_path, template, cases, transport, repeats=2)
    assert not template.exists()
    assert len(transport.prompts) == 2
    assert transport.prompts[0] == transport.prompts[1]
    assert TEMPLATE_MARKER in transport.prompts[0]
    assert "Second version" not in transport.prompts[1]
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["prompt_hash"] == hashlib.sha256(first_bytes).hexdigest()


def test_template_identity_across_runs_and_reports(tmp_path: Path) -> None:
    """Different template -> different identity; same template -> per-report renders."""
    template_a = _write_template(tmp_path, "a.md", f"Alpha. {TEMPLATE_MARKER}\n\n{{report_text}}\n")
    template_b = _write_template(tmp_path, "b.md", "Beta instructions.\n\n{report_text}\n")
    cases = _materialized_mutated_cases(tmp_path)
    assert len(cases) >= 2
    transport_a = _RecordingTransport(_valid_payload_text())
    result_a = _run_pilot(tmp_path, template_a, [cases[0]], transport_a, out_name="o-a")
    transport_b = _RecordingTransport(_valid_payload_text())
    result_b = _run_pilot(tmp_path, template_b, [cases[0]], transport_b, out_name="o-b")
    manifest_a = json.loads(result_a.manifest_path.read_text(encoding="utf-8"))
    manifest_b = json.loads(result_b.manifest_path.read_text(encoding="utf-8"))
    assert transport_a.prompts != transport_b.prompts
    assert manifest_a["prompt_hash"] != manifest_b["prompt_hash"]

    transport_c = _RecordingTransport(_valid_payload_text())
    result_c = _run_pilot(tmp_path, template_a, cases[:2], transport_c, out_name="o-c")
    manifest_c = json.loads(result_c.manifest_path.read_text(encoding="utf-8"))
    assert manifest_c["prompt_hash"] == manifest_a["prompt_hash"]
    by_case = _record_map(result_c)
    hash_0 = by_case[cases[0].case_id]["evaluation_metadata"]["rendered_prompt_hash"]
    hash_1 = by_case[cases[1].case_id]["evaluation_metadata"]["rendered_prompt_hash"]
    assert hash_0 != hash_1
    assert transport_c.prompts[0] != transport_c.prompts[1]


def test_retry_and_failure_carry_same_rendered_hash(tmp_path: Path) -> None:
    """Retries reuse one render; failed records hash the prompt actually sent."""
    template = _write_template(
        tmp_path, "triage-e1c.md", f"Retry check. {TEMPLATE_MARKER}\n\n{{report_text}}\n"
    )
    cases = _materialized_mutated_cases(tmp_path)[:1]

    def _raise_once() -> None:
        raise TimeoutError("simulated timeout")

    recorder = _RecordingTransport(_valid_payload_text(), hook=_raise_once)
    counting = CountingClient(recorder, max_requests=50)
    evaluator = LlmEvaluator(client=counting, max_retries=1, enabled=True)
    result = run_llm_pilot(
        _pilot_config(template), evaluator, cases, tmp_path, tmp_path / "o-retry"
    )
    assert recorder.calls == 2
    assert recorder.prompts[0] == recorder.prompts[1]
    record = _record_map(result)[cases[0].case_id]
    assert not record["evaluation_metadata"].get("failed")
    assert (
        record["evaluation_metadata"]["rendered_prompt_hash"]
        == hashlib.sha256(recorder.prompts[0].encode("utf-8")).hexdigest()
    )

    failing = _FailingTransport()
    result3 = _run_pilot(tmp_path, template, cases, failing, out_name="o-fail")
    assert result3.outcomes_path is not None
    outcomes3 = [
        json.loads(line)
        for line in result3.outcomes_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(outcomes3) == 1 and outcomes3[0]["status"] == "failed"
    assert "decision" not in outcomes3[0]
    assert (
        outcomes3[0]["rendered_prompt_hash"]
        == hashlib.sha256(failing.prompts[0].encode("utf-8")).hexdigest()
    )
    assert result3.records_path.read_text(encoding="utf-8") == ""


def test_render_edges_preserved_and_invalid_rejected(tmp_path: Path) -> None:
    """Braces/CRLF/Unicode/in-report placeholders survive; bad templates dispatch nothing."""
    template = tmp_path / "edge.md"
    edge_text = (
        'Güvenlik değerlendirmesi — naïve café.\r\n{"k": 1} and {} stay.\r\n{report_text}\r\n'
    )
    template.write_bytes(edge_text.encode())
    report_text = "Body with {report_text} and {} plus Ünïcode—ok."
    from sloplab.corpus.parser import parse_report

    doc = parse_report(f"# T\n\n## Summary\n\n{report_text}\n", fixture_id="x", path="x")
    recorder = _RecordingTransport(_valid_payload_text())
    counting = CountingClient(recorder, max_requests=50)
    evaluator = LlmEvaluator(client=counting, max_retries=0, enabled=True)
    bound = evaluator.with_prompt(load_prompt_template(template).text)
    result = bound.evaluate(doc, EvaluationContext(report=doc, case_id="x", labels={}))
    sent = recorder.prompts[0]
    assert '{"k": 1} and {} stay.' in sent
    assert "\r\n" in sent
    assert "Güvenlik değerlendirmesi — naïve café." in sent
    assert "Body with {report_text} and {} plus Ünïcode—ok." in sent
    assert (
        result.metadata["rendered_prompt_hash"] == hashlib.sha256(sent.encode("utf-8")).hexdigest()
    )
    # No silent newline normalization in identity either.
    assert (
        hashlib.sha256(template.read_bytes()).hexdigest()
        != hashlib.sha256(template.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    )

    cases = _materialized_mutated_cases(tmp_path)
    bad_contents: list[bytes] = [
        b"No placeholder here.\n",
        b"One {report_text} and another {report_text}.\n",
        b"\xff\xfe not utf-8\n",
    ]
    for index, bad in enumerate(bad_contents):
        bad_path = tmp_path / f"bad-{index}.md"
        bad_path.write_bytes(bad)
        boom = _RecordingTransport(_valid_payload_text())
        out_dir = tmp_path / f"bad-out-{index}"
        out_dir.mkdir()
        sentinel = out_dir / "sentinel.txt"
        sentinel.write_text("do not touch", encoding="utf-8")
        with pytest.raises(PromptTemplateError):
            _run_pilot(tmp_path, bad_path, cases[:1], boom, out_name=f"bad-out-{index}")
        assert boom.calls == 0
        assert [p.name for p in sorted(out_dir.iterdir())] == ["sentinel.txt"]
    missing = tmp_path / "does-not-exist.md"
    with pytest.raises(PromptTemplateError):
        load_prompt_template(missing)
    ghost = _RecordingTransport(_valid_payload_text())
    with pytest.raises(PromptTemplateError):
        _run_pilot(tmp_path, missing, cases[:1], ghost, out_name="ghost-out")
    assert ghost.calls == 0
    assert not (tmp_path / "ghost-out").exists()


def test_standalone_default_prompt_byte_stable() -> None:
    """Default construction still sends the historical str.format rendering."""
    from sloplab.corpus.parser import parse_report

    doc = parse_report("# T\n\n## Summary\n\nBody {with} braces.\n", fixture_id="x", path="x")
    recorder = _RecordingTransport(_valid_payload_text())
    evaluator = LlmEvaluator(client=CountingClient(recorder, max_requests=10), enabled=True)
    from sloplab.models.evaluation import EvaluationContext

    evaluator.evaluate(doc, EvaluationContext(report=doc, case_id="x", labels={}))
    assert recorder.prompts == [PROMPT_TEMPLATE.format(report_text=doc.raw_text)]


def test_binding_leaves_caller_unchanged(tmp_path: Path) -> None:
    """with_prompt copies; caller keeps default, client and retries are shared."""
    from sloplab.corpus.parser import parse_report
    from sloplab.models.evaluation import EvaluationContext

    recorder = _RecordingTransport(_valid_payload_text())
    counting = CountingClient(recorder, max_requests=50)
    caller = LlmEvaluator(client=counting, max_retries=2, enabled=True)
    bound = caller.with_prompt(f"Custom. {TEMPLATE_MARKER}\n\n{{report_text}}\n")
    assert bound is not caller
    assert bound._client is counting  # noqa: SLF001 - shared client, counters kept
    assert bound._max_retries == 2  # noqa: SLF001 - retry settings kept
    doc = parse_report("# T\n\n## Summary\n\nHello.\n", fixture_id="x", path="x")
    caller.evaluate(doc, EvaluationContext(report=doc, case_id="x", labels={}))
    assert recorder.prompts == [PROMPT_TEMPLATE.format(report_text=doc.raw_text)]
    bound.evaluate(doc, EvaluationContext(report=doc, case_id="x", labels={}))
    assert TEMPLATE_MARKER in recorder.prompts[1]

    template = _write_template(
        tmp_path, "triage-e1c.md", f"Pilot file. {TEMPLATE_MARKER}\n\n{{report_text}}\n"
    )
    cases = _materialized_mutated_cases(tmp_path)[:1]
    before = len(recorder.prompts)
    caller2 = LlmEvaluator(
        client=CountingClient(recorder, max_requests=50), max_retries=0, enabled=True
    )
    run_llm_pilot(_pilot_config(template), caller2, cases, tmp_path, tmp_path / "o-bind")
    assert TEMPLATE_MARKER in recorder.prompts[before]
    # The caller's own evaluator still renders the default template afterwards.
    caller2.evaluate(doc, EvaluationContext(report=doc, case_id="x", labels={}))
    assert recorder.prompts[-1] == PROMPT_TEMPLATE.format(report_text=doc.raw_text)
    with pytest.raises(PromptTemplateError):
        caller.with_prompt("no placeholder here")


def test_snapshot_cases_reach_pilot_with_stored_report(tmp_path: Path) -> None:
    """E1b snapshot path feeds the pilot; doc selection needs no reload."""
    cases = _materialized_mutated_cases(tmp_path)
    for case in cases:
        assert case.report is not None
        assert _document_for(case, tmp_path).raw_text == case.report.raw_text
