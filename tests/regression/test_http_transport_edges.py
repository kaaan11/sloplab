"""Transport envelopes, credential boundaries, and obsolete HTTP date handling."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
from datetime import UTC, datetime
from email.message import Message
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from sloplab.evaluators.jev.transport import parse_retry_after
from sloplab.evaluators.llm.adapter import HttpLLMClient
from sloplab.evaluators.llm.failures import EvaluationFailure
from sloplab.experiments.pilot import ThrottledClient
from tests.regression.test_llm_failure_taxonomy import _evaluate


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_llm_redirect_never_dispatches_to_destination(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    destination_requests: list[str | None] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.read_request()

        def do_GET(self) -> None:
            self.read_request()

        def read_request(self) -> None:
            if self.path == "/source":
                self.send_response(status)
                # A distinct hostname represents a different credential origin.
                self.send_header("Location", f"http://localhost:{server.server_port}/target")
            else:
                destination_requests.append(self.headers.get("Authorization"))
                self.send_response(200)
            self.end_headers()

        def log_message(self, *args: Any) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01))
    thread.start()
    monkeypatch.setenv("EDGE_KEY", "credential-canary")
    client = HttpLLMClient(
        model="m",
        api_key_env="EDGE_KEY",
        endpoint=f"http://127.0.0.1:{server.server_port}/source",
    )
    try:
        with pytest.raises(urllib.error.HTTPError) as caught:
            client.complete("p")
        assert caught.value.code == status
        caught.value.close()
        assert destination_requests == []
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


@pytest.mark.parametrize(
    "envelope",
    [
        [],
        None,
        42,
        "text",
        {},
        {"choices": []},
        {"choices": None},
        {"choices": {}},
        {"choices": [None]},
        {"choices": [42]},
        {"choices": [{"message": []}]},
        {"choices": [{"message": None}]},
    ],
)
def test_malformed_provider_envelopes_are_terminal_parse_failures(
    monkeypatch: pytest.MonkeyPatch, envelope: Any
) -> None:
    import urllib.request

    from tests.regression.test_llm_failure_taxonomy import _FakeHttpResponse

    body = json.dumps(envelope).encode()
    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *handlers: type(
            "Opener",
            (),
            {"open": staticmethod(lambda request, timeout=None: _FakeHttpResponse(body))},
        )(),
    )
    monkeypatch.setenv("EDGE_KEY", "k")
    client = HttpLLMClient(model="m", api_key_env="EDGE_KEY", endpoint="https://example.invalid")
    with pytest.raises(EvaluationFailure) as caught:
        _evaluate(client, max_retries=3)
    assert (caught.value.error_kind, caught.value.detail) == ("parse", "parse.empty_response")
    assert caught.value.adapter_attempts == 1


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="requires POSIX timezone control")
@pytest.mark.parametrize("zone", ["UTC0", "EST5"])
@pytest.mark.parametrize(
    "raw",
    [
        "Sun Nov  6 08:49:37 1994",
        "Sunday, 06-Nov-94 08:49:37 GMT",
        "Sun, 06 Nov 1994 08:49:37 GMT",
    ],
)
def test_retry_after_dates_use_utc_in_both_clients(
    monkeypatch: pytest.MonkeyPatch, zone: str, raw: str
) -> None:
    headers = Message()
    headers["Retry-After"] = raw
    now = datetime(1994, 11, 6, 8, 49, 28, tzinfo=UTC).timestamp()
    error = urllib.error.HTTPError("https://example.invalid", 429, "limited", headers, None)
    try:
        with monkeypatch.context() as scoped:
            scoped.setenv("TZ", zone)
            time.tzset()
            scoped.setattr(time, "time", lambda: now)
            assert parse_retry_after(headers) == 9.0
            assert ThrottledClient._retry_after_seconds(error) == 9.0
    finally:
        time.tzset()
