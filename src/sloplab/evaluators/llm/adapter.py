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

    client = HttpLLMClient(model="...", api_key_env="SLOPLAB_LLM_API_KEY")
    evaluator = LlmEvaluator(client=client)
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

from sloplab import __version__
from sloplab.models.evaluation import DimensionScores, EvaluationContext, EvaluationResult
from sloplab.models.report import ReportDocument

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

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

    def evaluate(
        self,
        report: ReportDocument,
        context: EvaluationContext,
    ) -> EvaluationResult:
        _ = context.labels  # deliberately unused; the adapter is content-based
        prompt = PROMPT_TEMPLATE.format(report_text=report.raw_text)

        last_error = ""
        for _attempt in range(self._max_retries + 1):
            try:
                response = self._client.complete(prompt)
                payload = self._parse_json(response.text)
                return self._to_result(payload, context.case_id, response.latency_ms)
            except _ParseFailure as exc:
                last_error = str(exc)
            except Exception as exc:  # transport failures -> retry then fail
                last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(0)  # no real sleeping in-process; hooks for real clients

        return self._failed_result(context.case_id, last_error)

    # --- parsing ---------------------------------------------------------

    def _parse_json(self, text: str) -> dict[str, Any]:
        match = _JSON_OBJECT_RE.search(text)
        if not match:
            raise _ParseFailure("no JSON object found in response")
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise _ParseFailure(f"invalid JSON ({exc})") from exc
        if not isinstance(payload, dict):
            raise _ParseFailure("top-level JSON value is not an object")

        decision = payload.get("decision")
        if decision not in ("accept", "reject", "needs_manual_review"):
            raise _ParseFailure(f"invalid decision {decision!r}")

        confidence = payload.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
            raise _ParseFailure(f"confidence out of range: {confidence!r}")

        dimensions = payload.get("dimensions")
        if not isinstance(dimensions, dict):
            raise _ParseFailure("dimensions must be an object")
        try:
            DimensionScores.from_dict({k: float(v) for k, v in dimensions.items()})
        except (TypeError, ValueError) as exc:
            raise _ParseFailure(f"dimension scores invalid: {exc}") from exc

        findings = payload.get("findings", [])
        if not isinstance(findings, list):
            raise _ParseFailure("findings must be a list")
        return payload

    def _to_result(
        self, payload: dict[str, Any], case_id: str, latency_ms: int
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
            },
        )

    def _failed_result(self, case_id: str, error: str) -> EvaluationResult:
        """Schema-valid placeholder marking evaluation failure (never a decision)."""
        from sloplab.models.enums import Decision
        from sloplab.models.evaluation import DimensionScores

        return EvaluationResult(
            evaluator_name=self.name,
            evaluator_version=self.version,
            case_id=case_id,
            decision=Decision.NEEDS_MANUAL_REVIEW,
            confidence=0.0,
            dimensions=DimensionScores(
                reproducibility=0.5,
                evidence_completeness=0.5,
                claim_evidence_consistency=0.5,
                impact_calibration=0.5,
                scope_consistency=0.5,
            ),
            findings=[],
            rationale=f"LLM evaluation failed after retries: {error}",
            metadata={"adapter": "strict-json", "failed": True},
        )


class _ParseFailure(Exception):
    pass


class HttpLLMClient:
    """Minimal HTTP client for live use. Never imported by tests/CI paths.

    Requires an explicit API key via environment variable; performs a single
    non-streaming completion call per ``complete`` invocation.
    """

    def __init__(self, *, model: str, api_key_env: str, endpoint: str) -> None:
        import urllib.request

        self._model = model
        self._endpoint = endpoint
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
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
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
