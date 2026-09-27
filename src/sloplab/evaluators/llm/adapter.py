"""Optional strict-JSON LLM evaluator adapter.

Design constraints (decision D-0010):

- Disabled by default. Constructing an adapter without explicit configuration
  raises; nothing in tests or CI constructs one with live settings.
- Strict output contract (enforced since A-008): after stripping surrounding
  whitespace and at most one enclosing Markdown code fence (```` ```json ```` or a
  bare ```` ``` ````), the response must be exactly one JSON object and nothing
  else. Anything else raises a typed :class:`EvaluationFailure`, never a crash
  and never an invented decision.
- Schema: top-level keys are limited to ``decision``, ``confidence``,
  ``dimensions``, ``findings``, ``rationale`` (unknown keys are rejected;
  ``findings`` and ``rationale`` may be omitted). ``confidence`` and every
  dimension score must be a JSON number (booleans rejected) in ``[0, 1]``;
  ``dimensions`` must hold exactly the five normalized keys; ``NaN``/``Infinity``
  literals are rejected as invalid JSON. Individual ``findings`` entries stay
  sanitized, not rejected: malformed entries are dropped (pre-existing
  behavior, tested).
- Failure codes (``error_kind`` / ``detail``, see ``failures.py``): JSON syntax
  (``parse.empty_response``, ``parse.no_json_object``, ``parse.invalid_json``,
  and the strict-format code ``parse.extra_text`` for a JSON object surrounded
  by other text); schema (``parse.non_object``, ``parse.unknown_keys``,
  ``parse.invalid_*``); ``refusal`` (``refusal.provider`` for a provider-native
  refusal field, ``refusal.text_pattern`` for a response containing no ``{``
  whose start matches :data:`REFUSAL_PATTERNS`); ``http-permanent``
  (``http.<status>`` for 4xx other than 408/429). All of these are terminal:
  retrying the same prompt is not expected to change them. Refusal detection is
  a conservative surface-form rule, not a semantic judgement; everything it
  misses stays a ``parse`` failure.
- Why strict rather than tolerant (A-008): the previous parser extracted the
  first-to-last brace span (``\\{.*\\}``) and ignored unknown keys, so it was
  weaker than this docstring promised. No recorded live pilot depends on the
  tolerant behavior (no LLM bundle is committed), both shipped prompts already
  ask for ONLY a JSON object, and tolerant extraction would silently repair
  outputs that the contract classifies as format failures. Extra text around a
  valid object is kept observable under its own code (``parse.extra_text``)
  rather than being repaired.
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
from sloplab.evaluators.llm.failures import (
    DeadlineExceeded,
    EvaluationFailure,
    classify_dispatch_error,
)
from sloplab.models.enums import DIMENSIONS
from sloplab.models.evaluation import DimensionScores, EvaluationContext, EvaluationResult
from sloplab.models.report import ReportDocument

#: Tolerant brace span, used ONLY to diagnose ``parse.extra_text`` after the
#: strict whole-document parse failed; never to accept a response.
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

#: At most one Markdown code fence enclosing the whole (stripped) response.
_FENCE_RE = re.compile(r"```(?:json)?\s*(?P<body>.*?)\s*```", re.DOTALL | re.IGNORECASE)

#: Top-level keys the normalized schema allows.
_ALLOWED_KEYS = frozenset({"decision", "confidence", "dimensions", "findings", "rationale"})

#: Conservative refusal pattern set (A-008). Applied only when the stripped
#: response contains no ``{`` at all and is at most
#: :data:`REFUSAL_MAX_CHARS` long; each pattern must match at the very start
#: (after an optional apology such as "I'm sorry," / "Sorry," / "I apologize,").
#: Anything else without JSON stays ``parse.no_json_object``.
REFUSAL_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(
        r"\A(?:(?:i['’]?m sorry|i am sorry|sorry|i apologi[sz]e)[,.!]?\s+(?:but\s+)?)?" + body,
        re.IGNORECASE,
    )
    for body in (
        r"i (?:cannot|can['’]?t|can not|won['’]?t|will not|am unable to|"
        r"am not able to)\s+"
        r"(?:help|assist|comply|provide|evaluate|complete|fulfill|process|do)\b",
        r"i['’]?m (?:unable|not able) to\s+"
        r"(?:help|assist|comply|provide|evaluate|complete|fulfill|process|do)\b",
        r"i (?:must|have to) decline\b",
    )
)
REFUSAL_MAX_CHARS = 500

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
    """One completion. ``provider_refusal`` is True only when the provider's
    response carried an explicit refusal field (e.g. OpenAI-compatible
    ``message.refusal``); the refusal text itself is never stored."""

    text: str
    latency_ms: int
    provider_refusal: bool = False


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

        Success keeps returning :class:`EvaluationResult`. Terminal errors
        (JSON syntax / strict-format / schema failures, refusals, permanent
        HTTP 4xx, spent budget, refused deadline waits) raise immediately
        without retry; timeouts, transports, and explicit rate-limit
        backpressure use the configured retries. Every attempt of one call
        renders the same prompt. ``adapter_attempts`` counts logical attempts
        performed, not physical dispatches.
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
                # getattr: duck-typed test transports predate the field.
                if getattr(response, "provider_refusal", False) is True:
                    raise _ResponseFailure("refusal.provider", error_kind="refusal")
                payload = self._parse_json(response.text)
                return self._to_result(payload, context.case_id, response.latency_ms, rendered_hash)
            except _ResponseFailure as exc:
                raise EvaluationFailure(
                    error_kind=exc.error_kind,
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
        """Strictly parse ``text`` into a schema-valid payload (see module docstring)."""
        payload = _load_strict_document(text if isinstance(text, str) else "")
        if not isinstance(payload, dict):
            raise _ResponseFailure("parse.non_object")
        if set(payload) - _ALLOWED_KEYS:
            raise _ResponseFailure("parse.unknown_keys")

        decision = payload.get("decision")
        if decision not in ("accept", "reject", "needs_manual_review"):
            raise _ResponseFailure("parse.invalid_decision")

        confidence = payload.get("confidence")
        if not _is_unit_number(confidence):
            raise _ResponseFailure("parse.invalid_confidence")

        dimensions = payload.get("dimensions")
        if (
            not isinstance(dimensions, dict)
            or set(dimensions) != set(DIMENSIONS)
            or not all(_is_unit_number(v) for v in dimensions.values())
        ):
            raise _ResponseFailure("parse.invalid_dimensions")
        try:
            DimensionScores.from_dict({k: float(v) for k, v in dimensions.items()})
        except (TypeError, ValueError) as exc:
            raise _ResponseFailure("parse.invalid_dimensions") from exc

        findings = payload.get("findings", [])
        if not isinstance(findings, list):
            raise _ResponseFailure("parse.invalid_findings")
        if not isinstance(payload.get("rationale", ""), str):
            raise _ResponseFailure("parse.invalid_rationale")
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
            severity_raw = raw.get("severity", "medium")
            if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]*", code):
                try:
                    severity = Severity(severity_raw)
                except (TypeError, ValueError):
                    severity = Severity.MEDIUM
                findings.append(
                    Finding(
                        code=code,
                        severity=severity,
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


class _ResponseFailure(Exception):
    """Internal terminal response failure carrying ledger-safe stable codes."""

    def __init__(self, code: str, *, error_kind: str = "parse") -> None:
        self.code = code
        self.error_kind = error_kind
        super().__init__(code)


def _reject_constant(name: str) -> Any:
    """``json.loads`` hook: ``NaN``/``Infinity`` are not valid strict JSON."""
    raise ValueError(f"non-standard JSON constant {name}")


def _is_unit_number(value: object) -> bool:
    """A JSON number (not a boolean) within ``[0, 1]``."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= value <= 1.0


def _is_refusal(stripped: str) -> bool:
    """Conservative surface-form refusal rule (see :data:`REFUSAL_PATTERNS`)."""
    if "{" in stripped or len(stripped) > REFUSAL_MAX_CHARS:
        return False
    return any(pattern.match(stripped) for pattern in REFUSAL_PATTERNS)


def _has_embedded_object(document: str) -> bool:
    """True when a JSON object is decodable somewhere inside ``document``.

    Diagnostic only (distinguishes ``parse.extra_text`` from
    ``parse.invalid_json``); a response is never accepted through this path.
    """
    start = document.find("{")
    if start >= 0:
        try:
            obj, _ = json.JSONDecoder(parse_constant=_reject_constant).raw_decode(document, start)
        except ValueError:
            obj = None
        if isinstance(obj, dict):
            return True
    match = _JSON_OBJECT_RE.search(document)
    if match:
        try:
            obj = json.loads(match.group(0), parse_constant=_reject_constant)
        except ValueError:
            return False
        return isinstance(obj, dict)
    return False


def _load_strict_document(text: str) -> Any:
    """Decode ``text`` as exactly one JSON document.

    Surrounding whitespace and at most one enclosing code fence are removed;
    nothing else is repaired. Raises :class:`_ResponseFailure` with a syntax or
    refusal code.
    """
    stripped = text.strip()
    if not stripped:
        raise _ResponseFailure("parse.empty_response")
    fence = _FENCE_RE.fullmatch(stripped)
    document = fence.group("body") if fence else stripped
    try:
        return json.loads(document, parse_constant=_reject_constant)
    except ValueError as exc:  # JSONDecodeError subclasses ValueError
        if "{" not in stripped:
            if _is_refusal(stripped):
                raise _ResponseFailure("refusal.text_pattern", error_kind="refusal") from exc
            raise _ResponseFailure("parse.no_json_object") from exc
        if _has_embedded_object(document):
            raise _ResponseFailure("parse.extra_text") from exc
        raise _ResponseFailure("parse.invalid_json") from exc


class HttpLLMClient:
    """Minimal HTTP client for live use. Never used with live settings by tests/CI.

    Requires an explicit API key via environment variable; performs a single
    non-streaming completion call per ``complete`` invocation. ``timeout_s``
    bounds each request; production wiring passes ``budget.request_timeout_s``
    so the config file is the single source of truth.

    A monotonic run deadline can be armed via :meth:`set_deadline` (the pilot
    forwards it through the wrapper chain). Before every HTTP dispatch the
    remaining run time is computed: the ``urlopen`` timeout becomes
    ``min(timeout_s, remaining)`` so no request outlives the run, and an
    already-expired deadline raises :class:`DeadlineExceeded` without any
    HTTP call.
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
        self._deadline_monotonic: float | None = None
        self._api_key = os.environ.get(api_key_env, "")
        if not self._api_key:
            raise AdapterError(f"environment variable {api_key_env!r} must contain an API key")
        _ = urllib.request  # keep import surface explicit

    def set_deadline(self, deadline_monotonic: float | None) -> None:
        """Arm (or clear) the monotonic run deadline for future dispatches."""
        self._deadline_monotonic = deadline_monotonic

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
        timeout = self._timeout_s
        if self._deadline_monotonic is not None:
            remaining = self._deadline_monotonic - time.monotonic()
            if remaining <= 0:
                raise DeadlineExceeded("run deadline expired before HTTP dispatch")
            timeout = min(timeout, remaining)
        start = time.monotonic()
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = _json.loads(response.read().decode())
        latency = int((time.monotonic() - start) * 1000)
        message = payload.get("choices", [{}])[0].get("message", {})
        content = message.get("content")
        # A null/absent content becomes "" (-> parse.empty_response), never a
        # transport error. An explicit OpenAI-compatible ``refusal`` string is
        # surfaced as a flag only; its text is not stored.
        refusal = message.get("refusal")
        return LLMResponse(
            text=content if isinstance(content, str) else "",
            latency_ms=latency,
            provider_refusal=isinstance(refusal, str) and bool(refusal.strip()),
        )


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
