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
from sloplab.evaluators.llm.failures import (
    DeadlineExceeded,
    EvaluationFailure,
    ResponseTooLarge,
    classify_dispatch_error,
)
from sloplab.experiments.pilot import CountingClient, ThrottledClient
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


def test_deadline_interrupts_a_continuously_streamed_local_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = json.dumps({"choices": [{"message": {"content": "x" * 200}}]}).encode()
    request_closed = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            for offset in range(0, len(body), 8):
                try:
                    self.wfile.write(body[offset : offset + 8])
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    request_closed.set()
                    return
                time.sleep(0.03)

        def log_message(self, *args: Any) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server_thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01))
    server_thread.start()
    monkeypatch.setenv("STREAM_KEY", "test-key")
    transport = HttpLLMClient(
        model="m",
        api_key_env="STREAM_KEY",
        endpoint=f"http://127.0.0.1:{server.server_port}/completion",
        timeout_s=2,
        max_response_bytes=1024,
    )
    counting = CountingClient(transport, max_requests=1)
    throttled = ThrottledClient(counting, min_interval_ms=0)
    throttled.set_deadline(time.monotonic() + 0.4)
    started = time.monotonic()

    try:
        with pytest.raises(DeadlineExceeded) as caught:
            throttled.complete("prompt")
        elapsed = time.monotonic() - started
        assert caught.value.dispatch_started is True
        assert counting.physical_dispatches == 1
        assert counting.errors == 1
        assert throttled._last_dispatch is not None  # noqa: SLF001
        assert elapsed < 0.8
        assert request_closed.wait(1)
    finally:
        server.shutdown()
        server_thread.join(timeout=2)
        server.server_close()


def test_oversized_response_is_typed_and_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    class _OversizedResponse:
        def __init__(self) -> None:
            self.body = b"x" * 100
            self.offset = 0
            self.closed = False

        def __enter__(self) -> _OversizedResponse:
            return self

        def __exit__(self, *args: Any) -> None:
            self.closed = True

        def read1(self, size: int) -> bytes:
            chunk = self.body[self.offset : self.offset + size]
            self.offset += len(chunk)
            return chunk

    import urllib.request

    response = _OversizedResponse()
    monkeypatch.setenv("OVERSIZED_KEY", "test-key")
    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *handlers: type(
            "Opener", (), {"open": staticmethod(lambda request, timeout=None: response)}
        )(),
    )
    client = HttpLLMClient(
        model="m",
        api_key_env="OVERSIZED_KEY",
        endpoint="https://example.invalid/v1",
        max_response_bytes=8,
    )

    with pytest.raises(ResponseTooLarge) as caught:
        client.complete("prompt")

    assert caught.value.limit == 8
    assert caught.value.observed_bytes == 9
    assert response.offset == 9
    assert response.closed is True
    assert classify_dispatch_error(caught.value) == (
        "transport",
        "transport.response_too_large",
        False,
    )


def test_cancelled_response_read_closes_the_http_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class _CancelledResponse:
        closed = False

        def __enter__(self) -> _CancelledResponse:
            return self

        def __exit__(self, *args: Any) -> None:
            self.closed = True

        def read1(self, size: int) -> bytes:
            _ = size
            raise KeyboardInterrupt

    import urllib.request

    response = _CancelledResponse()
    monkeypatch.setenv("CANCEL_KEY", "test-key")
    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *handlers: type(
            "Opener", (), {"open": staticmethod(lambda request, timeout=None: response)}
        )(),
    )
    counting = CountingClient(
        HttpLLMClient(model="m", api_key_env="CANCEL_KEY", endpoint="https://example.invalid/v1"),
        max_requests=1,
    )

    with pytest.raises(KeyboardInterrupt):
        counting.complete("prompt")

    assert response.closed is True
    assert counting.physical_dispatches == 1


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
