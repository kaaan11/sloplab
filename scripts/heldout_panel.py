"""Run a private three-family case-card panel after the owner's blind judgments.

Default invocation is a dry preflight. ``--run`` dispatches at most 81 requests
(nine cards, three families, at most three attempts each). All responses remain
under the Git-ignored heldout-private directory; stdout contains counts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, ValidationError
from panel_pacing import MIN_INTERVAL_SECONDS, pace_request
from prepare_heldout_inputs import PRIVATE_ROOT, _inside_private

ROOT = PRIVATE_ROOT / "v0.1"
PACKET = ROOT / "owner-packet"
SHEET = PACKET / "judgment-sheet.yaml"
MANIFEST = PACKET / "manifest.json"
RESULTS = ROOT / "panel-results.jsonl"
FREEZE = ROOT / "owner-freeze.json"
MODELS = (
    "qwen/qwen3.8-27b:free",
    "dots-studio/dots-3-note-preview:free",
    "liquid/lfm-2.5-2.6b:free",
)
MODEL_REQUEST_SETTINGS = {
    model: {
        "max_tokens": 4096 if model.startswith("liquid/") else 2048,
        "reasoning": {"enabled": model.startswith("liquid/")},
    }
    for model in MODELS
}
EXCLUDED = {"openai", "meta-llama", "anthropic"}
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
MAX_ATTEMPTS = 3
MAX_REQUESTS = 81


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_owner_sheet() -> tuple[dict[str, Any], str, dict[str, dict[str, Any]]]:
    """Reject incomplete or changed input views before any provider request."""
    _inside_private(SHEET)
    sheet_bytes = SHEET.read_bytes()
    sheet = yaml.safe_load(sheet_bytes)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    hashes = manifest["input_sha256"]
    if not isinstance(sheet, dict) or set(sheet) != {"judge", "judged_date", "cards"}:
        raise ValueError("owner sheet has unexpected or missing fields")
    if not isinstance(sheet["judge"], str) or not sheet["judge"].strip():
        raise ValueError("owner judge is missing")
    try:
        judged = date.fromisoformat(str(sheet["judged_date"]))
    except ValueError as exc:
        raise ValueError("owner judged_date must be ISO format") from exc
    if judged > datetime.now(UTC).date():
        raise ValueError("owner judged_date is in the future")
    if not isinstance(sheet["cards"], dict) or set(sheet["cards"]) != set(hashes):
        raise ValueError("owner sheet card IDs differ from private input manifest")
    views: dict[str, dict[str, Any]] = {}
    for card_id, expected_hash in sorted(hashes.items()):
        data = (PACKET / card_id / "input.json").read_bytes()
        if _sha(data) != expected_hash:
            raise ValueError(f"{card_id}: input hash changed")
        view = json.loads(data)
        claim_ids = {claim["id"] for claim in view["claims"]}
        judgment = sheet["cards"][card_id]
        if not isinstance(judgment, dict) or set(judgment) != {
            "action",
            "confidence",
            "rationale",
            "claims",
        }:
            raise ValueError(f"{card_id}: incomplete judgment")
        if judgment["action"] not in {
            "verify",
            "request_specific_information",
            "likely_out_of_scope",
        }:
            raise ValueError(f"{card_id}: invalid action")
        if judgment["confidence"] not in {"low", "medium", "high"}:
            raise ValueError(f"{card_id}: invalid confidence")
        if not isinstance(judgment["rationale"], str) or not judgment["rationale"].strip():
            raise ValueError(f"{card_id}: missing rationale")
        claims = judgment["claims"]
        if not isinstance(claims, dict) or set(claims) != claim_ids:
            raise ValueError(f"{card_id}: claim IDs differ from input")
        if any(v not in {"supported", "missing", "contradictory"} for v in claims.values()):
            raise ValueError(f"{card_id}: invalid claim status")
        views[card_id] = view
    return sheet, _sha(sheet_bytes), views


def _output_schema(claim_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["verify", "request_specific_information", "likely_out_of_scope"],
            },
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "rationale": {"type": "string"},
            "claims": {
                "type": "array",
                "minItems": len(claim_ids),
                "maxItems": len(claim_ids),
                "items": {
                    "type": "object",
                    "properties": {
                        "claim_id": {"type": "string", "enum": claim_ids},
                        "status": {
                            "type": "string",
                            "enum": ["supported", "missing", "contradictory"],
                        },
                        "note": {"type": "string"},
                    },
                    "required": ["claim_id", "status", "note"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["action", "confidence", "rationale", "claims"],
        "additionalProperties": False,
    }


def _request(model: str, view: dict[str, Any], api_key: str) -> tuple[dict[str, Any], str]:
    claim_ids = [claim["id"] for claim in view["claims"]]
    schema = _output_schema(claim_ids)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Review a fully synthetic vulnerability report for the next human triage step. "
                    "Use only the supplied input. 'verify' means ready for a human "
                    "verification attempt, "
                    "not proof of a vulnerability. Treat policy facts as authoritative. "
                    "For each claim, judge support from supplied evidence, "
                    "not general plausibility. 'supported' means the supplied package "
                    "supports it; 'missing' means material evidence is absent; "
                    "'contradictory' requires evidence or authoritative context "
                    "that contradicts it. 'request_specific_information' is for a material "
                    "gap or unresolved conflict; 'likely_out_of_scope' is for stated "
                    "program policy or threat-model exclusions. Return one action, "
                    "ordinal action confidence, a brief rationale, and exactly one "
                    "entry for each supplied claim ID. Never add or duplicate claims."
                ),
            },
            {"role": "user", "content": json.dumps(view, ensure_ascii=False, sort_keys=True)},
        ],
        "temperature": 0,
        **MODEL_REQUEST_SETTINGS[model],
        "provider": {"require_parameters": True},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "case_card_vote", "strict": True, "schema": schema},
        },
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    pace_request()
    with urllib.request.urlopen(request, timeout=90) as response:
        raw = response.read().decode("utf-8")
    result = json.loads(raw)
    content = result["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError(
            f"empty model content; finish_reason={result['choices'][0].get('finish_reason')}"
        )
    vote = json.loads(content)
    Draft202012Validator(schema).validate(vote)
    actual_ids = [claim["claim_id"] for claim in vote["claims"]]
    if len(actual_ids) != len(claim_ids) or set(actual_ids) != set(claim_ids):
        raise ValueError("model vote has missing or duplicate claim IDs")
    return vote, raw


def _catalog_models(model_ids: tuple[str, ...] = MODELS) -> dict[str, dict[str, Any]]:
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30) as response:
        catalog = json.load(response)["data"]
    matched = {entry["id"]: entry for entry in catalog if entry["id"] in model_ids}
    if set(matched) != set(model_ids):
        raise ValueError("one or more panel models are unavailable")
    families = {model.split("/", 1)[0] for model in model_ids}
    if len(families) != 3 or families & EXCLUDED:
        raise ValueError("panel violates family exclusion rule")
    for model, entry in matched.items():
        if not model.endswith(":free") or any(
            float(entry["pricing"].get(field, "0")) != 0
            for field in ("prompt", "completion", "request")
        ):
            raise ValueError(f"{model}: panel requires zero-cost free models")
        if "structured_outputs" not in entry["supported_parameters"]:
            raise ValueError(f"{model}: structured output unavailable")
    return matched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", action="store_true", help="dispatch provider requests")
    parser.add_argument("--resume", action="store_true", help="retain completed votes and attempts")
    args = parser.parse_args()
    sheet, sheet_sha, views = load_owner_sheet()
    catalog = _catalog_models()
    if len(views) * len(MODELS) * MAX_ATTEMPTS > MAX_REQUESTS:
        raise ValueError("request plan exceeds hard cap")
    print(
        f"preflight: {len(views)} owner-judged cards, {len(MODELS)} allowed families, "
        f"cap {MAX_REQUESTS} requests"
    )
    if not args.run:
        return
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is unavailable")
    if not args.resume and (RESULTS.exists() or FREEZE.exists()):
        raise ValueError("panel already started; preserve existing private records")
    freeze = {
        "schema_version": "owner-freeze-v0.1",
        "frozen_at": datetime.now(UTC).isoformat(),
        "judged_date": str(sheet["judged_date"]),
        "owner_sheet_sha256": sheet_sha,
        "input_sha256": json.loads(MANIFEST.read_text(encoding="utf-8"))["input_sha256"],
        "model_ids": list(MODELS),
        "resolved_model_ids": {m: catalog[m].get("canonical_slug", m) for m in MODELS},
        "max_requests": MAX_REQUESTS,
        "max_attempts_per_vote": MAX_ATTEMPTS,
        "min_interval_seconds": MIN_INTERVAL_SECONDS,
        "script_sha256": _sha(Path(__file__).read_bytes()),
        "catalog": {m: catalog[m] for m in MODELS},
        "request_settings": {
            model: {"temperature": 0, "structured_outputs": True, **settings}
            for model, settings in MODEL_REQUEST_SETTINGS.items()
        },
    }
    prior: dict[tuple[str, str], list[dict[str, Any]]] = {}
    if args.resume:
        stored = json.loads(FREEZE.read_text(encoding="utf-8"))
        for field in ("owner_sheet_sha256", "input_sha256", "model_ids", "request_settings"):
            if stored[field] != freeze[field]:
                raise ValueError(f"resume would change frozen {field}")
        for line in RESULTS.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            key = row["card_id"], row["model"]
            if row["card_id"] not in views or row["model"] not in MODELS:
                raise ValueError("unknown prior vote")
            history = prior.setdefault(key, [])
            if row["attempt"] != len(history) + 1:
                raise ValueError("duplicate or nonsequential prior attempt")
            history.append(row)
        fd = os.open(RESULTS, os.O_WRONLY | os.O_APPEND)
    else:
        FREEZE.write_text(json.dumps(freeze, indent=2) + "\n", encoding="utf-8")
        os.chmod(FREEZE, 0o600)
        fd = os.open(RESULTS, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    success = sum(any(r["status"] == "success" for r in rows) for rows in prior.values())
    failure = 0
    requests = sum(len(rows) for rows in prior.values())
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        for card_id, view in sorted(views.items()):
            for model in MODELS:
                previous = prior.get((card_id, model), [])
                if any(r["status"] == "success" for r in previous):
                    continue
                if len(previous) >= MAX_ATTEMPTS:
                    failure += 1
                    continue
                for attempt in range(len(previous) + 1, MAX_ATTEMPTS + 1):
                    if requests >= MAX_REQUESTS:
                        raise RuntimeError("hard request cap reached")
                    requests += 1
                    row: dict[str, Any] = {"card_id": card_id, "model": model, "attempt": attempt}
                    try:
                        vote, raw = _request(model, view, api_key)
                        response = json.loads(raw)
                        row.update(
                            {
                                "status": "success",
                                "vote": vote,
                                "response_sha256": _sha(raw.encode()),
                                "response_id": response.get("id"),
                                "response_model": response.get("model"),
                                "provider": response.get("provider"),
                                "usage": response.get("usage"),
                                "recorded_at": datetime.now(UTC).isoformat(),
                            }
                        )
                        success += 1
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
                        json.JSONDecodeError,
                    ) as exc:
                        row.update(
                            {
                                "status": "invalid_or_transport_error",
                                "error_type": type(exc).__name__,
                                "error": str(exc),
                            }
                        )
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
                        raise RuntimeError(
                            f"provider returned HTTP {row['http_status']}; stopped panel early"
                        )
                    if row["status"] == "success":
                        break
                    if attempt == MAX_ATTEMPTS:
                        failure += 1
                    time.sleep(1)
    print(
        f"panel complete: {success} successful votes, {failure} failed votes, "
        f"{requests} physical requests"
    )


if __name__ == "__main__":
    main()
