"""One registered diagnostic request for a public synthetic canonical case."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from heldout_panel import MODELS as CARD_MODELS
from heldout_panel import _catalog_models
from panel_pacing import pace_request
from prepare_heldout_inputs import REPO_ROOT, _inside_private
from realized_edit_panel import MODELS as EDIT_MODELS

from sloplab.evaluators.llm.adapter import (
    LLM_OUTPUT_SCHEMA,
    FlakyThenSuccessClient,
    LlmEvaluator,
    _ResponseFailure,
    load_prompt_template,
    render_file_template,
)
from sloplab.scoring.harness import build_cases, case_document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--model", choices=sorted(set(CARD_MODELS + EDIT_MODELS)), required=True)
    parser.add_argument(
        "--out", type=Path, required=True, help="new directory under heldout-private"
    )
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    out = _inside_private(args.out)
    suite = REPO_ROOT / "benchmarks/results/v1-core-example/suite-index.jsonl"
    cases = build_cases(suite, REPO_ROOT / "corpus", suite.parent)
    case = next((c for c in cases if c.case_id == args.case_id and c.kind == "canonical"), None)
    if case is None:
        raise ValueError("unknown canonical case")
    prompt_source = load_prompt_template(REPO_ROOT / "experiments/prompts/triage-v1.md")
    prompt = render_file_template(prompt_source.text, case_document(case).raw_text)
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "sloplab_triage_v1",
                "strict": True,
                "schema": LLM_OUTPUT_SCHEMA,
            },
        },
        "provider": {"require_parameters": True},
        "temperature": 0,
    }
    body = json.dumps(payload).encode()
    print("diagnostic preflight: one request; original public report and strict pilot schema")
    if not args.run:
        return
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise ValueError("OPENROUTER_API_KEY is unavailable")
    models = CARD_MODELS if args.model in CARD_MODELS else EDIT_MODELS
    catalog = _catalog_models(models)
    out.mkdir(parents=True, exist_ok=False)
    protocol = {
        "registered_at": datetime.now(UTC).isoformat(),
        "case_id": case.case_id,
        "model": args.model,
        "catalog_entry": catalog[args.model],
        "max_requests": 1,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "request_sha256": hashlib.sha256(body).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "payload": payload,
    }
    protocol_file = out / "protocol.json"
    with protocol_file.open("x") as output:
        json.dump(protocol, output, indent=2)
    protocol_file.chmod(0o600)
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    row: dict[str, Any] = {"case_id": case.case_id, "model": args.model, "physical_requests": 1}
    try:
        pace_request()
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode()
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
        vote = LlmEvaluator(FlakyThenSuccessClient(0, ""), enabled=True)._parse_json(content)
        row.update(
            status="success",
            vote=vote,
            response_sha256=hashlib.sha256(raw.encode()).hexdigest(),
            response_id=data.get("id"),
            provider=data.get("provider"),
            usage=data.get("usage"),
        )
    except urllib.error.HTTPError as exc:
        row.update(
            status="http_error",
            http_status=exc.code,
            response_body=exc.read().decode("utf-8", "replace"),
        )
    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        KeyError,
        IndexError,
        _ResponseFailure,
    ) as exc:
        row.update(
            status="invalid_or_transport_error", error_type=type(exc).__name__, error=str(exc)
        )
    finally:
        row["recorded_at"] = datetime.now(UTC).isoformat()
        result = out / "result.json"
        with result.open("x") as output:
            json.dump(row, output, indent=2)
        result.chmod(0o600)
    print(f"diagnostic complete: {row['status']}; raw response/error stays private")


if __name__ == "__main__":
    main()
