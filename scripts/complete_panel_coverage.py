"""Register a bounded coverage supplement; preserve frozen inputs/models and prior failures."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import heldout_panel as cards
import realized_edit_panel as edits
from jsonschema import ValidationError
from panel_supplements import load_supplements, rows_sha256


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("cards", "edits"), required=True)
    parser.add_argument("--run-id", required=True, help="monotonically ordered identifier")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", args.run_id):
        raise ValueError("invalid run ID")
    root = cards.ROOT
    identity_field = "card_id" if args.kind == "cards" else "batch_id"
    if args.kind == "cards":
        _, owner_sha, inputs = cards.load_owner_sheet()
        base_protocol = cards.FREEZE
        frozen = json.loads(base_protocol.read_text())
        if owner_sha != frozen["owner_sheet_sha256"]:
            raise ValueError("owner reference changed")
        if json.loads(cards.MANIFEST.read_text())["input_sha256"] != frozen["input_sha256"]:
            raise ValueError("card inputs changed")
        settings = {
            m: {"temperature": 0, "structured_outputs": True, **s}
            for m, s in cards.MODEL_REQUEST_SETTINGS.items()
        }
        models = cards.MODELS
        base_rows = read_rows(cards.RESULTS)
        old = root / "panel-supplemental.jsonl"
        if old.exists():
            old_protocol = json.loads(old.with_name("panel-supplemental-protocol.json").read_text())
            if (
                old_protocol["original_freeze_sha256"]
                != hashlib.sha256(base_protocol.read_bytes()).hexdigest()
            ):
                raise ValueError("legacy supplement protocol changed")
            base_rows.extend(read_rows(old))
    else:
        base_protocol = edits.PROTOCOL
        frozen = json.loads(base_protocol.read_text())
        pairs = edits.load_pairs()
        hashes = {
            p["mutation_id"]: hashlib.sha256(
                json.dumps({k: p[k] for k in ("report_a", "report_b")}, sort_keys=True).encode()
            ).hexdigest()
            for p in pairs
        }
        inputs = {b["batch_id"]: b for b in edits.load_batches(pairs)}
        if (
            hashes != frozen["input_sha256"]
            or {k: [p["mutation_id"] for p in b["pairs"]] for k, b in inputs.items()}
            != frozen["batch_mapping"]
        ):
            raise ValueError("public pair inputs or batches changed")
        settings = {
            m: {**s, "max_tokens": s["max_tokens"] * 2}
            for m, s in edits.MODEL_REQUEST_SETTINGS.items()
        }
        models = edits.MODELS
        base_rows = read_rows(edits.RESULTS)
    if list(models) != frozen["model_ids"] or settings != frozen["request_settings"]:
        raise ValueError("frozen model set or request settings changed")
    rows, metadata, _ = load_supplements(root, args.kind, base_protocol, base_rows)
    if args.resume and (not metadata or args.run_id != metadata[-1]["run_id"]):
        raise ValueError("only the latest supplemental ledger may be resumed")
    histories: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        histories[row[identity_field], row["model"]].append(row)
    slots = [
        {identity_field: identifier, "model": model, "previous_attempts": len(history)}
        for (identifier, model), history in sorted(histories.items())
        if not any(r["status"] == "success" for r in history)
    ]
    print(f"coverage preflight: {len(slots)} missing slots; new cap {len(slots) * 3} requests")
    if not args.run:
        return
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is unavailable")
    cards._catalog_models(models)
    run_root = root / "coverage-supplements" / args.kind / args.run_id
    protocol_path = run_root / "protocol.json"
    ledger = run_root / "requests.jsonl"
    if args.resume:
        protocol = json.loads(protocol_path.read_text())
        slots = protocol["slots"]
    else:
        if metadata and args.run_id <= metadata[-1]["run_id"]:
            raise ValueError("run ID must follow existing supplement IDs")
        run_root.mkdir(parents=True, exist_ok=False)
        protocol = {
            "schema_version": "panel-coverage-supplement-v1",
            "kind": args.kind,
            "registered_at": datetime.now(UTC).isoformat(),
            "base_protocol_sha256": hashlib.sha256(base_protocol.read_bytes()).hexdigest(),
            "prior_rows_sha256": rows_sha256(rows),
            "max_attempts_per_slot": 3,
            "max_requests": len(slots) * 3,
            "slots": slots,
            "request_settings": settings,
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
        with protocol_path.open("x") as output:
            json.dump(protocol, output, indent=2)
        protocol_path.chmod(0o600)
        ledger.touch(mode=0o600, exist_ok=False)
    used = len(read_rows(ledger))
    with ledger.open("a") as output:
        for slot in slots:
            identity = slot[identity_field], slot["model"]
            history = histories[identity]
            if any(r["status"] == "success" for r in history):
                continue
            previous = slot["previous_attempts"]
            for attempt in range(len(history) - previous + 1, 4):
                if used >= protocol["max_requests"]:
                    raise ValueError("supplement physical request cap reached")
                used += 1
                if args.kind == "cards":
                    row = {identity_field: identity[0], "model": identity[1]}
                    try:
                        vote, raw = cards._request(identity[1], inputs[identity[0]], api_key)
                        response = json.loads(raw)
                        row.update(
                            status="success",
                            vote=vote,
                            usage=response.get("usage"),
                            response_model=response.get("model"),
                            provider=response.get("provider"),
                            response_id=response.get("id"),
                            response_sha256=hashlib.sha256(raw.encode()).hexdigest(),
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
                        ValidationError,
                    ) as exc:
                        row.update(
                            status="invalid_or_transport_error",
                            error_type=type(exc).__name__,
                            error=str(exc),
                        )
                else:
                    row = edits.vote(inputs[identity[0]], identity[1], api_key)
                row.update(
                    attempt=previous + attempt,
                    supplement_attempt=attempt,
                    source_run=args.run_id,
                    recorded_at=datetime.now(UTC).isoformat(),
                )
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
                output.flush()
                history.append(row)
                print(f"coverage request {used}: {row['status']}", flush=True)
                if row["status"] == "success":
                    break
                if row.get("http_status") in {401, 402, 403, 404}:
                    raise RuntimeError("provider access failure; supplement stopped")
                if attempt < 3:
                    print("waiting 60 seconds before next bounded attempt", flush=True)
                    time.sleep(60)
    load_supplements(root, args.kind, base_protocol, base_rows)
    print("coverage supplement complete; raw ledger is private")


if __name__ == "__main__":
    main()
