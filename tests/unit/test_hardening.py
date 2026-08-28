"""Hardening and resilience tests.

Covers IPv6 SSRF bypass prevention, Path Traversal defense, and HTTP response robustness.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sloplab.corpus.loader import FixtureError, _load_report_document
from sloplab.evaluators.llm.adapter import HttpLLMClient
from sloplab.safety.policy import find_unsafe_urls, validate_content_safety

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ipv6_url_safety_enforcement() -> None:
    # Loopback IPv6 is allowed
    safe_text = "Testing local service on http://[::1]:8000/api/v1"
    assert find_unsafe_urls(safe_text) == []
    assert validate_content_safety(safe_text) == []

    # Public IPv6 addresses must be flagged as unsafe
    unsafe_text = "Exfiltrating to public DNS http://[2001:4860:4860::8888]/leak and https://[2606:4700:4700::1111]/drop"
    violations = find_unsafe_urls(unsafe_text)
    assert len(violations) == 2
    assert "http://[2001:4860:4860::8888]/leak" in violations
    assert "https://[2606:4700:4700::1111]/drop" in violations

    safety_violations = validate_content_safety(unsafe_text)
    assert len(safety_violations) == 2


def test_path_traversal_defense_in_report_loader(tmp_path: Path) -> None:
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    manifest_path = corpus_root / "manifest.yaml"
    manifest_path.write_text("dummy: 1", encoding="utf-8")

    # Path traversal attempting to break out of corpus_root
    with pytest.raises(FixtureError, match="attempts path traversal outside root"):
        _load_report_document(
            manifest_path=manifest_path,
            corpus_root=corpus_root,
            report_rel_path="../../../etc/passwd",
            fixture_id="test-id",
            fallback_title="Test Title",
        )


def test_http_llm_client_empty_choices_and_alternative_payloads() -> None:
    with patch.dict(os.environ, {"TEST_KEY": "secret"}):
        client = HttpLLMClient(
            model="test-model",
            api_key_env="TEST_KEY",
            endpoint="http://localhost:11434/v1/chat/completions",
            timeout_s=10.0,
        )

    def _mock_urlopen(payload_dict: dict[str, object]) -> MagicMock:
        cm = MagicMock()
        cm.__enter__.return_value.read.return_value = json.dumps(payload_dict).encode("utf-8")
        return cm

    # 1. Empty choices list: should not raise IndexError
    with patch("urllib.request.urlopen", return_value=_mock_urlopen({"choices": []})):
        res1 = client.complete("test")
        assert res1.text == ""

    # 2. Ollama direct message format: {"message": {"content": "verdict"}}
    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen({"message": {"content": '{"decision": "accept"}'}}),
    ):
        res2 = client.complete("test")
        assert res2.text == '{"decision": "accept"}'

    # 3. Direct response string format: {"response": "raw output"}
    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen({"response": "direct output"}),
    ):
        res3 = client.complete("test")
        assert res3.text == "direct output"
