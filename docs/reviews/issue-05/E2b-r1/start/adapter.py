"""Optional strict-JSON LLM evaluator adapter.

Design constraints (decision D-0010):

- Disabled by default. Constructing an adapter without explicit configuration
  raises; nothing in tests or CI constructs one with live settings.
- Strict output contract: the model must return a single JSON object matching the
  normalized schema; anything else becomes a *failed evaluation record*, never a
  crash and never an invented decision.
- The transport is abstracted behind ``LLMClient`` so tests can inject canned or
  failing responses without any network access.

Live usage (NOT used by tests/CI)::

    from sloplab.evaluators.llm.adapter import LlmEvaluator, HttpLLMClient

    client = HttpLLMClient(
        model="...", api_key_env="SLOPLAB_LLM_API_KEY",
        endpoint="https://openrouter.ai/api/v1/chat/completions",
    )
    evaluator = LlmEvaluator(client=client, enabled=True)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from sloplab import __version__
from sloplab.evaluators.llm.failures import EvaluationFailure, classify_dispatch_error
from sloplab.models.evaluation import DimensionScores, EvaluationContext, EvaluationResult
from sloplab.models.report import ReportDocument

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

#: Version of the file-template renderer recorded in pilot manifests.
#: Bump when render semantics change; the legacy ``PROMPT_TEMPLATE`` path below
#: keeps its historical ``str.format`` behavior byte-for-byte.
PROMPT_RENDERER_VERSION = "file-template-v1"

REPORT_TEXT_PLACEHOLDER = "{report_text}"

PROMPT_TEMPLATE = """\
You are a vulnerability-report triage evaluator. Classify the report below.

Return ONLY a JSON object with exactly these keys:
{{
  "decision": "accept" | "reject" | "needs_manual_review",
  "confidence": <float 0..1>,
  "dimensions": {{
    "reproducibility": <0..1>,
    "evidence_completeness": <0..1>,
    "claim_evidence_consistency": <0..1>,
    "impact_calibration": <0..1>,
    "scope_consistency": <0..1>
  }},
  "findings": [{{"code": "UPPER_SNAKE", "severity": "info|low|medium|high|critical",
                 "evidence": "..."}}],
  "rationale": "<one paragraph>"
}}

Report:
---
{report_text}
---
"""


class AdapterError(Exception):
    """Raised for configuration problems at construction time."""


class PromptTemplateError(ValueError):
    """A pilot prompt template cannot be used (unreadable, or placeholder defect)."""


@dataclass(frozen=True)
class LoadedPromptTemplate:
    """A prompt template resolved once at pilot start.

    ``text`` is the decoded template every dispatch renders; ``sha256`` is the
    SHA-256 of the original UTF-8 template bytes (no newline normalization).
    """

    text: str
    sha256: str


def load_prompt_template(path: Path) -> LoadedPromptTemplate:
    """Read and validate a pilot prompt template file.

    The file must decode as UTF-8 and contain exactly one ``{report_text}``
    placeholder. Raises :class:`PromptTemplateError` before any dispatch.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PromptTemplateError(f"cannot read prompt template '{path}': {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PromptTemplateError(f"prompt template '{path}' is not valid UTF-8: {exc}") from exc
    validate_prompt_template(text, source=str(path))
    return LoadedPromptTemplate(text=text, sha256=hashlib.sha256(raw).hexdigest())


def validate_prompt_template(template: str, *, source: str = "prompt template") -> None:
    """Require exactly one ``{report_text}`` placeholder in ``template``."""
    found = template.count(REPORT_TEXT_PLACEHOLDER)
    if found != 1:
        raise PromptTemplateError(
            f"{source} must contain exactly one '{REPORT_TEXT_PLACEHOLDER}' "
            f"placeholder, found {found}"
        )


def render_file_template(template: str, report_text: str) -> str:
    """Render a validated file template with a single-pass substitution.

    Only the defined ``{report_text}`` placeholder is processed: JSON braces,
    ``{}``, Unicode, and placeholder-looking report content pass through
    literally and are never reinterpreted. Never ``str.format`` a file template.
    """
    validate_prompt_template(template)
    return template.replace(REPORT_TEXT_PLACEHOLDER, report_text)


@dataclass(frozen=True)
class LLMResponse:
    text: str
    latency_ms: int


class LLMClient(Protocol):
    """Transport abstraction; implementations own retries/timeouts."""

    def complete(self, prompt: str) -> LLMResponse: ...  # pragma: no cover


class LlmEvaluator:
    """Strict-JSON adapter implementing the standard evaluator protocol."""

    name = "llm-json"
    version = __version__
    # Content-based: evaluates report text only; never needs ground-truth labels.
    requires_labels = False

    def __init__(
        self,
        client: LLMClient,
        *,
        max_retries: int = 2,
        enabled: bool = False,
    ) -> None:
        if not enabled:
            raise AdapterError(
                "LlmEvaluator is disabled by default; construct with enabled=True "
                "after explicitly configuring a client"
            )
        if client is None:
            raise AdapterError("LlmEvaluator requires an LLMClient instance")
        self._client = client
        self._max_retries = max_retries
        self._prompt_template = PROMPT_TEMPLATE
        self._legacy_format = True

    def with_prompt(self, template: str) -> LlmEvaluator:
        """Return a copy bound to a validated file template.

        The caller's evaluator is left unchanged (same default/custom prompt).
        The copy shares the same client object (no counter reset) and retry
        settings; only the render source differs.
        """
        validate_prompt_template(template)
        bound = LlmEvaluator(client=self._client, max_retries=self._max_retries, enabled=True)
        bound._prompt_template = template
        bound._legacy_format = False
        return bound

    def _render(self, report_text: str) -> str:
        """Render the sendable prompt for ``report_text``.

        The default template keeps its historical ``str.format`` behavior
        byte-for-byte (it carries doubled JSON braces); file templates use the
        single-pass renderer so their braces stay literal.
        """
        if self._legacy_format:
            return PROMPT_TEMPLATE.format(report_text=report_text)
        return render_file_template(self._prompt_template, report_text)

    def evaluate(
        self,
        report: ReportDocument,
        context: EvaluationContext,
    ) -> EvaluationResult:
        """Return the normalized triage observation, or raise EvaluationFailure.

        Success keeps returning :class:`EvaluationResult`. Terminal local
        errors (unparseable responses, spent budget, refused deadline waits)
        raise immediately without retry; timeouts, transports, and explicit
        rate-limit backpressure use the configured retries. Every attempt of
        one call renders the same prompt. ``adapter_attempts`` counts logical
        attempts performed, not physical dispatches.
        """
        _ = context.labels  # deliberately unused; the adapter is content-based
        prompt = self._render(report.raw_text)
        rendered_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        attempts = self._max_retries + 1

        last_kind = "transport"
        last_detail = "transport.error"
        for attempt in range(1, attempts + 1):
            try:
                response = self._client.complete(prompt)
                payload = self._parse_json(response.text)
                return self._to_result(payload, context.case_id, response.latency_ms, rendered_hash)
            except _ParseFailure as exc:
                raise EvaluationFailure(
                    error_kind="parse",
                    adapter_attempts=attempt,
                    rendered_prompt_hash=rendered_hash,
                    detail=exc.code,
                ) from exc
            except Exception as exc:  # noqa: BLE001 - classified below, never copied
                kind, detail, retriable = classify_dispatch_error(exc)
                if not retriable:
                    raise EvaluationFailure(
                        error_kind=kind,
                        adapter_attempts=attempt,
                        rendered_prompt_hash=rendered_hash,
                        detail=detail,
                    ) from exc
                last_kind, last_detail = kind, detail
            time.sleep(0)  # no real sleeping in-process; hooks for real clients

        raise EvaluationFailure(
            error_kind=last_kind,
            adapter_attempts=attempts,
            rendered_prompt_hash=rendered_hash,
            detail=last_detail,
        )

    # --- parsing ---------------------------------------------------------

    def _parse_json(self, text: str) -> dict[str, Any]:
        match = _JSON_OBJECT_RE.search(text)
        if not match:
            raise _ParseFailure("parse.no_json_object")
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise _ParseFailure("parse.invalid_json") from exc
        if not isinstance(payload, dict):
            raise _ParseFailure("parse.non_object")

        decision = payload.get("decision")
        if decision not in ("accept", "reject", "needs_manual_review"):
            raise _ParseFailure("parse.invalid_decision")

        confidence = payload.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
            raise _ParseFailure("parse.invalid_confidence")

        dimensions = payload.get("dimensions")
        if not isinstance(dimensions, dict):
            raise _ParseFailure("parse.invalid_dimensions")
        try:
            DimensionScores.from_dict({k: float(v) for k, v in dimensions.items()})
        except (TypeError, ValueError) as exc:
            raise _ParseFailure("parse.invalid_dimensions") from exc

        findings = payload.get("findings", [])
        if not isinstance(findings, list):
            raise _ParseFailure("parse.invalid_findings")
        return payload

    def _to_result(
        self, payload: dict[str, Any], case_id: str, latency_ms: int, rendered_hash: str
    ) -> EvaluationResult:
        from sloplab.models.enums import Decision, Severity
        from sloplab.models.evaluation import Finding

        dims_raw = {k: float(v) for k, v in payload["dimensions"].items()}
        findings: list[Finding] = []
        for raw in payload.get("findings", []):
            if not isinstance(raw, dict):
                continue
            code = raw.get("code")
            severity = raw.get("severity", "medium")
            if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]*", code):
                findings.append(
                    Finding(
                        code=code,
                        severity=Severity(severity)
                        if severity in Severity.__members__
                        else Severity.MEDIUM,
                        evidence=str(raw.get("evidence", ""))[:200],
                    )
                )

        rationale = str(payload.get("rationale", ""))[:1000]
        return EvaluationResult(
            evaluator_name=self.name,
            evaluator_version=self.version,
            case_id=case_id,
            decision=Decision(payload["decision"]),
            confidence=float(payload["confidence"]),
            dimensions=DimensionScores.from_dict(dims_raw),
            findings=findings,
            rationale=rationale,
            metadata={
                "latency_ms": latency_ms,
                "adapter": "strict-json",
                "failed": False,
                # Identity of the sent prompt text (UTF-8 SHA-256); not a full
                # request hash (no model/sampling/transport data included).
                "rendered_prompt_hash": rendered_hash,
            },
        )


class _ParseFailure(Exception):
    """Internal parser failure carrying a ledger-safe stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class HttpLLMClient:
    """Minimal HTTP client for live use. Never imported by tests/CI paths.

    Requires an explicit API key via environment variable; performs a single
    non-streaming completion call per ``complete`` invocation. ``timeout_s``
    bounds each request; production wiring passes ``budget.request_timeout_s``
    so the config file is the single source of truth.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key_env: str,
        endpoint: str,
        timeout_s: float = 60.0,
    ) -> None:
        import urllib.request

        if timeout_s <= 0:
            raise AdapterError("timeout_s must be positive")
        self._model = model
        self._endpoint = endpoint
        self._timeout_s = timeout_s
        self._api_key = os.environ.get(api_key_env, "")
        if not self._api_key:
            raise AdapterError(f"environment variable {api_key_env!r} must contain an API key")
        _ = urllib.request  # keep import surface explicit

    def complete(self, prompt: str) -> LLMResponse:
        import json as _json
        import urllib.error
        import urllib.request

        body = _json.dumps(
            {"model": self._model, "messages": [{"role": "user", "content": prompt}]}
        ).encode()
        request = urllib.request.Request(
            self._endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )
        start = time.monotonic()
        with urllib.request.urlopen(request, timeout=self._timeout_s) as response:  # noqa: S310
            payload = _json.loads(response.read().decode())
        latency = int((time.monotonic() - start) * 1000)
        text = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        return LLMResponse(text=text, latency_ms=latency)


class FlakyThenSuccessClient:
    """Test double: raises N times, then returns a canned response."""

    def __init__(self, failures: int, response_text: str) -> None:
        self.remaining_failures = failures
        self.response_text = response_text
        self.calls = 0

    def complete(self, prompt: str) -> LLMResponse:
        self.calls += 1
        _ = prompt
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            raise TimeoutError("simulated timeout")
        return LLMResponse(text=self.response_text, latency_ms=12)
