"""Blind three-family semantic audit of all 141 decision-preserving v1 edits.

The model sees only report A and report B in a hash-randomized order. It does
not see the operator, authored label, report class, or numeric dimension targets.
Votes are exploratory independent model annotations, not human ground truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

import yaml
from heldout_panel import MODELS, _catalog_models
from jsonschema import Draft202012Validator, ValidationError
from prepare_heldout_inputs import PRIVATE_ROOT

from sloplab.models.enums import ReportClass, canonical_expected_decision

REPO_ROOT = Path(__file__).resolve().parents[1]
VARIANTS = REPO_ROOT / "benchmarks/results/v1-core-example/adversarial"
CORPUS = REPO_ROOT / "corpus/canonical"
RESULTS = PRIVATE_ROOT / "v0.1/realized-edit-votes.jsonl"
MAX_REQUESTS = 423
SCHEMA = {
    "type": "object",
    "properties": {
        "quality_changed": {"type": "string", "enum": ["yes", "no", "uncertain"]},
        "action_changed": {"type": "string", "enum": ["yes", "no", "uncertain"]},
        "quality_reason": {"type": "string"},
        "action_reason": {"type": "string"},
    },
    "required": ["quality_changed", "action_changed", "quality_reason", "action_reason"],
    "additionalProperties": False,
}


def load_pairs() -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for path in sorted(VARIANTS.glob("**/mutation-manifest.yaml")):
        mutation = yaml.safe_load(path.read_text(encoding="utf-8"))
        parent_id = mutation["parent_id"].removeprefix("canonical-")
        parent_dir = CORPUS / parent_id
        parent = yaml.safe_load((parent_dir / "manifest.yaml").read_text(encoding="utf-8"))
        target = canonical_expected_decision(ReportClass(parent["report_class"]))
        if mutation["expected_decision"] != target:
            continue
        parent_report = (parent_dir / "report.md").read_text(encoding="utf-8")
        child_report = (path.parent / "report.md").read_text(encoding="utf-8")
        if parent_report == child_report:
            raise ValueError(f"{mutation['id']}: byte-identical pair")
        swapped = int(hashlib.sha256(mutation["id"].encode()).hexdigest(), 16) % 2 == 1
        pairs.append(
            {
                "mutation_id": mutation["id"],
                "operator": mutation["operator"],
                "report_a": child_report if swapped else parent_report,
                "report_b": parent_report if swapped else child_report,
                "swapped": str(swapped),
            }
        )
    if len(pairs) != 141:
        raise ValueError(f"expected 141 realized edits, got {len(pairs)}")
    return pairs


def vote(pair: dict[str, str], model: str, key: str) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are independently comparing two versions of one fully synthetic "
                    "vulnerability report. Judge two separate axes. Quality changed means "
                    "the completeness, consistency, calibration, or clarity of the report "
                    "materially changed, whether better or worse. Action changed means a "
                    "human triager should take a different next step (attempt verification, "
                    "request specific information, or route as likely out of scope). A report "
                    "can change quality without changing action. Use 'uncertain' where program "
                    "policy or evidence is insufficient. Do not assume an omitted version field "
                    "always blocks verification. Give brief reasons grounded in the text."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Report A:\n" + pair["report_a"] + "\n\nReport B:\n" + pair["report_b"]
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": 450,
        "provider": {"require_parameters": True},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "realized_edit_vote", "strict": True, "schema": SCHEMA},
        },
    }
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    row: dict[str, Any] = {"mutation_id": pair["mutation_id"], "model": model}
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read().decode("utf-8")
        content = json.loads(raw)["choices"][0]["message"]["content"]
        decision = json.loads(content)
        Draft202012Validator(SCHEMA).validate(decision)
        row.update(
            {
                "status": "success",
                "vote": decision,
                "response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            }
        )
    except urllib.error.HTTPError as exc:
        row.update(
            {
                "status": "http_error",
                "http_status": exc.code,
                "response_body": exc.read().decode("utf-8", "replace"),
            }
        )
    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        KeyError,
        IndexError,
        ValidationError,
    ) as exc:
        row.update(
            {
                "status": "invalid_or_transport_error",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", action="store_true", help="dispatch provider requests")
    args = parser.parse_args()
    pairs = load_pairs()
    _catalog_models()
    if len(pairs) * len(MODELS) != MAX_REQUESTS:
        raise ValueError("request plan differs from registered cap")
    print(f"preflight: {len(pairs)} pairs, {len(MODELS)} families, {MAX_REQUESTS} requests")
    if not args.run:
        return
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise ValueError("OPENROUTER_API_KEY is unavailable")
    if RESULTS.exists():
        raise ValueError("private result ledger already exists; do not overwrite")
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(RESULTS, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    jobs = [(pair, model) for pair in pairs for model in MODELS]
    success = 0
    with os.fdopen(fd, "w", encoding="utf-8") as output, ThreadPoolExecutor(max_workers=3) as pool:
        job_iter = iter(jobs)
        pending = set()
        for _ in range(3):
            pair, model = next(job_iter)
            pending.add(pool.submit(vote, pair, model, key))
        while pending:
            finished, pending = wait(pending, return_when=FIRST_COMPLETED)
            fatal = None
            for future in finished:
                row = future.result()
                success += row["status"] == "success"
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
                output.flush()
                if row["status"] == "http_error" and row["http_status"] in {
                    400,
                    401,
                    402,
                    403,
                    404,
                    429,
                }:
                    fatal = row["http_status"]
            if fatal is not None:
                for future in pending:
                    future.cancel()
                raise RuntimeError(f"provider returned HTTP {fatal}; stopped panel early")
            for _ in finished:
                next_job = next(job_iter, None)
                if next_job is not None:
                    pair, model = next_job
                    pending.add(pool.submit(vote, pair, model, key))
    print(f"realized-edit panel: {success}/{len(jobs)} valid votes; raw ledger is private")


if __name__ == "__main__":
    main()
