"""Typed Jev transports: plain HTTPS and a physical dispatch counter (A-004).

No SDK is used: SDK-internal retries could not be counted (R1-510). The only
retry loop lives in :class:`~sloplab.evaluators.jev.evaluator.JevEvaluator`,
above :class:`CountingTransport`, so every attempt is a counted dispatch.

Supported targets (same path, ``POST {base_url}/v1/systemone``):

- OpenRouter: ``https://openrouter.ai/api`` with model ``typesafe/jev-1.13``
  (the chosen access path, decision K-C).
- TypeSafe native: ``https://api.typesafe.ai``.

Importing this module performs no network calls; nothing in tests or CI
constructs :class:`HttpJevTransport` against a live endpoint.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from email.message import Message
from typing import Any, Protocol

from sloplab.evaluators.jev.failures import (
    TRANSPORT_ERROR,
    BudgetExceeded,
    JevConfigError,
    JevHttpPermanent,
    JevRateLimited,
    JevTimeout,
    JevTransportError,
)
from sloplab.evaluators.jev.mapping import encode_request

OPENROUTER_BASE_URL = "https://openrouter.ai/api"
TYPESAFE_NATIVE_BASE_URL = "https://api.typesafe.ai"
SYSTEMONE_PATH = "/v1/systemone"
OPENROUTER_MODEL_ID = "typesafe/jev-1.13"
DEFAULT_API_KEY_ENV = "SLOPLAB_JEV_API_KEY"

#: Retriable backpressure statuses (``Retry-After`` honored).
RATE_LIMIT_STATUSES = frozenset({429, 529})
#: Statuses treated as request timeouts (retriable).
TIMEOUT_STATUSES = frozenset({408, 504})


@dataclass(frozen=True)
class JevResponse:
    """A 2xx HTTP response: raw body bytes plus transport facts.

    ``raw`` is kept verbatim so ``response_sha256`` hashes exactly what was
    received; decoding happens in the evaluator.
    """

    raw: bytes
    status: int = 200
    latency_ms: int = 0

    @classmethod
    def from_json(cls, body: Any, *, status: int = 200, latency_ms: int = 0) -> JevResponse:
        """Test/fixture helper: encode ``body`` as compact UTF-8 JSON."""
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return cls(raw=raw, status=status, latency_ms=latency_ms)


class JevTransport(Protocol):
    """One call is one physical request attempt; implementations never retry."""

    def decide(self, body: dict[str, Any]) -> JevResponse: ...  # pragma: no cover


def validate_base_url(base_url: str) -> str:
    """Return the normalized base URL, rejecting anything but plain ``https``.

    Credentials, query strings, and fragments in the URL are refused; a
    trailing slash is dropped so ``{base_url}/v1/systemone`` is well formed.
    """
    parts = urllib.parse.urlsplit(base_url)
    if parts.scheme != "https":
        raise JevConfigError(f"Jev base URL must use https, got scheme {parts.scheme!r}")
    if not parts.hostname:
        raise JevConfigError("Jev base URL must name a host")
    if parts.username is not None or parts.password is not None:
        raise JevConfigError("Jev base URL must not embed credentials")
    if parts.query or parts.fragment:
        raise JevConfigError("Jev base URL must not carry a query or fragment")
    return base_url.rstrip("/")


def parse_retry_after(headers: Message | None) -> float | None:
    """Parse ``Retry-After`` (delta seconds or HTTP-date); ``None`` if unusable."""
    if headers is None:
        return None
    raw = headers.get("Retry-After")
    if raw is None:
        return None
    try:
        seconds = float(raw)
    except ValueError:
        from email.utils import parsedate_to_datetime

        try:
            target = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
        return max(0.0, target.timestamp() - time.time())
    if not math.isfinite(seconds):
        return None
    return max(0.0, seconds)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects: they could downgrade to http or forward the key."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _open(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
    """Perform exactly one HTTPS exchange (no redirects); tests replace this."""
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(request, timeout=timeout) as response:
        status = int(response.status)
        raw: bytes = response.read()
    return status, raw


def _classify_http_error(exc: urllib.error.HTTPError) -> JevTransportError:
    status = int(exc.code)
    if status in RATE_LIMIT_STATUSES:
        return JevRateLimited(status=status, retry_after_s=parse_retry_after(exc.headers))
    if status in TIMEOUT_STATUSES:
        return JevTimeout(status=status)
    return JevHttpPermanent(status=status)


class HttpJevTransport:
    """Minimal ``POST {base_url}/v1/systemone`` client. Never live in tests/CI.

    The API key is read once from the environment variable ``api_key_env``;
    it is never accepted as an argument, logged, or included in ``repr``.
    Each :meth:`decide` performs one request with no retry and no redirect.
    HTTP errors map to typed transport errors: 429/529 -> rate limited
    (with ``Retry-After``), 408/504 and socket timeouts -> timeout, every
    other status -> permanent. Error bodies are never read or copied.
    """

    def __init__(
        self,
        base_url: str,
        api_key_env: str = DEFAULT_API_KEY_ENV,
        timeout_s: float = 60.0,
    ) -> None:
        self.base_url = validate_base_url(base_url)
        self.endpoint = f"{self.base_url}{SYSTEMONE_PATH}"
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise JevConfigError("timeout_s must be a positive finite number")
        self.timeout_s = float(timeout_s)
        if not api_key_env:
            raise JevConfigError("api_key_env must name an environment variable")
        self.api_key_env = api_key_env
        key = os.environ.get(api_key_env, "")
        if not key.strip():
            raise JevConfigError(f"environment variable {api_key_env!r} must contain an API key")
        self._api_key = key.strip()

    @classmethod
    def openrouter(
        cls, *, api_key_env: str = DEFAULT_API_KEY_ENV, timeout_s: float = 60.0
    ) -> HttpJevTransport:
        return cls(OPENROUTER_BASE_URL, api_key_env=api_key_env, timeout_s=timeout_s)

    @classmethod
    def typesafe_native(
        cls, *, api_key_env: str = DEFAULT_API_KEY_ENV, timeout_s: float = 60.0
    ) -> HttpJevTransport:
        return cls(TYPESAFE_NATIVE_BASE_URL, api_key_env=api_key_env, timeout_s=timeout_s)

    def __repr__(self) -> str:
        return (
            f"HttpJevTransport(endpoint={self.endpoint!r}, api_key_env={self.api_key_env!r}, "
            f"timeout_s={self.timeout_s!r})"
        )

    def decide(self, body: dict[str, Any]) -> JevResponse:
        request = urllib.request.Request(
            self.endpoint,
            data=encode_request(body),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )
        start = time.monotonic()
        try:
            status, raw = _open(request, self.timeout_s)
        except urllib.error.HTTPError as exc:
            raise _classify_http_error(exc) from None
        except TimeoutError:
            raise JevTimeout() from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise JevTimeout() from None
            raise JevTransportError(TRANSPORT_ERROR) from None
        except OSError:
            raise JevTransportError(TRANSPORT_ERROR) from None
        latency_ms = int((time.monotonic() - start) * 1000)
        return JevResponse(raw=raw, status=status, latency_ms=latency_ms)


@dataclass
class DispatchCounters:
    """Counters owned by :class:`CountingTransport` (all physical)."""

    physical_dispatches: int = 0
    refused: int = 0
    errors: int = 0
    by_code: dict[str, int] = field(default_factory=dict)


class CountingTransport:
    """Physical dispatch counter with a hard cap (R1-510).

    The reservation is taken under a lock *immediately before* the inner
    ``decide`` call, and the inner transport never refuses before sending,
    so ``physical_dispatches`` is an upper bound that equals real sends:
    a dispatch that fails after the reservation (timeout, HTTP error) stays
    counted. When the cap is spent, :class:`BudgetExceeded` is raised and the
    inner transport is not called at all. Retries pass through here and are
    counted like first attempts. The lock makes reservation atomic across
    threads; the cap can never be exceeded, even under concurrency.
    """

    def __init__(self, inner: JevTransport, *, max_requests: int) -> None:
        if isinstance(max_requests, bool) or not isinstance(max_requests, int):
            raise JevConfigError("max_requests must be an integer")
        if max_requests < 0:
            raise JevConfigError("max_requests must be >= 0")
        self._inner = inner
        self.max_requests = max_requests
        self.counters = DispatchCounters()
        self._lock = threading.Lock()

    @property
    def physical_dispatches(self) -> int:
        return self.counters.physical_dispatches

    @property
    def remaining(self) -> int:
        return self.max_requests - self.counters.physical_dispatches

    def _reserve_or_raise(self) -> None:
        with self._lock:
            if self.counters.physical_dispatches >= self.max_requests:
                self.counters.refused += 1
                raise BudgetExceeded(
                    f"Jev dispatch cap reached ({self.max_requests} physical requests)"
                )
            self.counters.physical_dispatches += 1

    def decide(self, body: dict[str, Any]) -> JevResponse:
        self._reserve_or_raise()
        try:
            return self._inner.decide(body)
        except JevTransportError as exc:
            with self._lock:
                self.counters.errors += 1
                self.counters.by_code[exc.code] = self.counters.by_code.get(exc.code, 0) + 1
            raise
        except Exception:
            with self._lock:
                self.counters.errors += 1
            raise
