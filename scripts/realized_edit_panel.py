"""Blind three-family semantic audit of all 141 decision-preserving v1 edits.

The model sees three report A/B pairs per request, with opaque pair handles.
It does not see the operator, authored label, class, or numeric dimension targets.
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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from heldout_panel import MODEL_REQUEST_SETTINGS as CARD_REQUEST_SETTINGS
from heldout_panel import _catalog_models
from jsonschema import Draft202012Validator, ValidationError
from panel_pacing import MIN_INTERVAL_SECONDS, pace_request
from prepare_heldout_inputs import PRIVATE_ROOT

from sloplab.models.enums import ReportClass, canonical_expected_decision

REPO_ROOT = Path(__file__).resolve().parents[1]
VARIANTS = REPO_ROOT / "benchmarks/results/v1-core-example/adversarial"
CORPUS = REPO_ROOT / "corpus/canonical"
RESULTS = PRIVATE_ROOT / "v0.1/realized-edit-votes.jsonl"
PROTOCOL = PRIVATE_ROOT / "v0.1/realized-edit-protocol.json"
MAX_REQUESTS = 240
MAX_ATTEMPTS = 3
BATCH_SIZE = 3
MODELS = (
    "dots-studio/dots-3-note-preview:free",
    "liquid/lfm-2.5-2.6b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
)
MODEL_REQUEST_SETTINGS = {
    MODELS[0]: CARD_REQUEST_SETTINGS[MODELS[0]],
    MODELS[1]: CARD_REQUEST_SETTINGS[MODELS[1]],
    MODELS[2]: {"max_tokens": 4096, "reasoning": {"enabled": True}},
}
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


def load_batches(pairs: list[dict[str, str]]) -> list[dict[str, Any]]:
    ordered = sorted(pairs, key=lambda p: hashlib.sha256(p["mutation_id"].encode()).hexdigest())
    return [
        {
            "batch_id": f"batch-{index // BATCH_SIZE:03d}",
            "pairs": ordered[index : index + BATCH_SIZE],
        }
        for index in range(0, len(ordered), BATCH_SIZE)
    ]


def vote(batch: dict[str, Any], model: str, key: str) -> dict[str, Any]:
    handles = {
        "edit-" + hashlib.sha256(pair["mutation_id"].encode()).hexdigest()[:16]: pair
        for pair in batch["pairs"]
    }
    schema = {
        "type": "object",
        "properties": {
            "pairs": {
                "type": "array",
                "minItems": len(handles),
                "maxItems": len(handles),
                "items": {
                    **SCHEMA,
                    "properties": {
                        **SCHEMA["properties"],
                        "pair_id": {"type": "string", "enum": list(handles)},
                    },
                    "required": [*SCHEMA["required"], "pair_id"],
                },
            }
        },
        "required": ["pairs"],
        "additionalProperties": False,
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Compare each supplied pair of versions of a fully synthetic "
                    "vulnerability report separately. Return exactly one entry for each "
                    "opaque pair ID, without duplicates. Judge two axes. Quality changed means "
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
                "content": json.dumps(
                    {
                        "pairs": [
                            {
                                "pair_id": handle,
                                "report_a": pair["report_a"],
                                "report_b": pair["report_b"],
                            }
                            for handle, pair in handles.items()
                        ]
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0,
        **MODEL_REQUEST_SETTINGS[model],
        "max_tokens": MODEL_REQUEST_SETTINGS[model]["max_tokens"] * 2,
        "provider": {"require_parameters": True},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "realized_edit_votes", "strict": True, "schema": schema},
        },
    }
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    row: dict[str, Any] = {"batch_id": batch["batch_id"], "model": model}
    try:
        pace_request()
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read().decode("utf-8")
        response_data = json.loads(raw)
        content = response_data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                "empty model content; "
                f"finish_reason={response_data['choices'][0].get('finish_reason')}"
            )
        decision = json.loads(content)
        Draft202012Validator(schema).validate(decision)
        ids = [item["pair_id"] for item in decision["pairs"]]
        if len(ids) != len(handles) or set(ids) != set(handles):
            raise ValueError("missing or duplicate pair IDs in batch response")
        row.update(
            {
                "status": "success",
                "votes": [
                    {
                        "mutation_id": handles[item["pair_id"]]["mutation_id"],
                        "vote": {k: v for k, v in item.items() if k != "pair_id"},
                    }
                    for item in decision["pairs"]
                ],
                "response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "response_id": response_data.get("id"),
                "response_model": response_data.get("model"),
                "provider": response_data.get("provider"),
                "usage": response_data.get("usage"),
                "recorded_at": datetime.now(UTC).isoformat(),
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
    parser.add_argument("--resume", action="store_true", help="retain prior votes and attempts")
    args = parser.parse_args()
    pairs = load_pairs()
    batches = load_batches(pairs)
    catalog = _catalog_models(MODELS)
    if len(batches) * len(MODELS) > MAX_REQUESTS:
        raise ValueError("request plan exceeds registered cap")
    print(
        f"preflight: {len(pairs)} pairs, {len(batches)} batches, "
        f"{len(MODELS)} families, cap {MAX_REQUESTS} requests"
    )
    if not args.run:
        return
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise ValueError("OPENROUTER_API_KEY is unavailable")
    if not args.resume and (RESULTS.exists() or PROTOCOL.exists()):
        raise ValueError("private result ledger already exists; do not overwrite")
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    protocol = {
        "schema_version": "realized-edit-protocol-v0.1",
        "registered_at": datetime.now(UTC).isoformat(),
        "model_ids": list(MODELS),
        "catalog": catalog,
        "max_requests": MAX_REQUESTS,
        "max_attempts_per_vote": MAX_ATTEMPTS,
        "batch_size": BATCH_SIZE,
        "batch_mapping": {b["batch_id"]: [p["mutation_id"] for p in b["pairs"]] for b in batches},
        "min_interval_seconds": MIN_INTERVAL_SECONDS,
        "request_settings": {
            model: {**settings, "max_tokens": settings["max_tokens"] * 2}
            for model, settings in MODEL_REQUEST_SETTINGS.items()
        },
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_sha256": {
            p["mutation_id"]: hashlib.sha256(
                json.dumps({k: p[k] for k in ("report_a", "report_b")}, sort_keys=True).encode()
            ).hexdigest()
            for p in pairs
        },
    }
    prior: dict[tuple[str, str], list[dict[str, Any]]] = {}
    if args.resume:
        registered = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        for field in (
            "model_ids",
            "input_sha256",
            "request_settings",
            "max_requests",
            "batch_mapping",
        ):
            if registered[field] != protocol[field]:
                raise ValueError(f"resume would change registered {field}")
        for line in RESULTS.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            identity = row["batch_id"], row["model"]
            if row["batch_id"] not in protocol["batch_mapping"] or row["model"] not in MODELS:
                raise ValueError("unknown prior vote")
            history = prior.setdefault(identity, [])
            if row["attempt"] != len(history) + 1:
                raise ValueError("duplicate or nonsequential prior attempt")
            history.append(row)
        fd = os.open(RESULTS, os.O_WRONLY | os.O_APPEND)
    else:
        PROTOCOL.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
        os.chmod(PROTOCOL, 0o600)
        fd = os.open(RESULTS, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    jobs = [
        (batch, model)
        for batch in batches
        for model in MODELS
        if not any(r["status"] == "success" for r in prior.get((batch["batch_id"], model), []))
        and len(prior.get((batch["batch_id"], model), [])) < MAX_ATTEMPTS
    ]
    prior_requests = sum(len(rows) for rows in prior.values())
    if prior_requests + len(jobs) > MAX_REQUESTS:
        os.close(fd)
        raise ValueError("resume would exceed physical request cap")
    success = sum(any(r["status"] == "success" for r in rows) for rows in prior.values())
    completed = 0
    with os.fdopen(fd, "w", encoding="utf-8") as output, ThreadPoolExecutor(max_workers=3) as pool:
        job_iter = iter(jobs)
        pending = {}
        for _ in range(min(3, len(jobs))):
            batch, model = next(job_iter)
            pending[pool.submit(vote, batch, model, key)] = (batch["batch_id"], model)
        while pending:
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            fatal = None
            for future in finished:
                row = future.result()
                identity = pending.pop(future)
                row["attempt"] = len(prior.get(identity, [])) + 1
                success += row["status"] == "success"
                completed += 1
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
                    row = future.result()
                    row["attempt"] = len(prior.get(pending[future], [])) + 1
                    output.write(json.dumps(row, ensure_ascii=False) + "\n")
                output.flush()
                raise RuntimeError(f"provider returned HTTP {fatal}; stopped panel early")
            for _ in finished:
                next_job = next(job_iter, None)
                if next_job is not None:
                    batch, model = next_job
                    pending[pool.submit(vote, batch, model, key)] = (batch["batch_id"], model)
            if completed % 10 == 0:
                print(
                    f"progress: {success} valid batches; {prior_requests + completed} requests",
                    flush=True,
                )
    print(
        f"realized-edit panel: {success}/{len(batches) * len(MODELS)} valid batches; "
        "raw ledger is private"
    )


if __name__ == "__main__":
    main()
