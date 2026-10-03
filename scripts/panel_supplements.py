"""Validate separately registered coverage supplements without replacing past ledgers."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def rows_sha256(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_supplements(
    root: Path, kind: str, original_protocol: Path, base_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, str], int]]:
    """Bind each supplement to the entire prior history, known missing slots and cap."""
    identity_field = "card_id" if kind == "cards" else "batch_id"
    rows = list(base_rows)
    metadata: list[dict[str, Any]] = []
    limits: dict[tuple[str, str], int] = {}
    protocol_sha = hashlib.sha256(original_protocol.read_bytes()).hexdigest()
    settings = json.loads(original_protocol.read_text())["request_settings"]
    histories: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        histories[row[identity_field], row["model"]].append(row)
    for path in sorted((root / "coverage-supplements" / kind).glob("*/protocol.json")):
        protocol = json.loads(path.read_text())
        if (
            protocol["schema_version"] != "panel-coverage-supplement-v1"
            or protocol["kind"] != kind
            or protocol["base_protocol_sha256"] != protocol_sha
            or protocol["prior_rows_sha256"] != rows_sha256(rows)
            or protocol["request_settings"] != settings
        ):
            raise ValueError("supplement differs from frozen protocol or prior history")
        if protocol["max_attempts_per_slot"] != 3:
            raise ValueError("unsupported supplemental attempt cap")
        slots = {}
        for slot in protocol["slots"]:
            key = slot[identity_field], slot["model"]
            if key in slots or key not in histories:
                raise ValueError("unknown or duplicate supplemental slot")
            history = histories[key]
            if slot["previous_attempts"] != len(history) or any(
                r["status"] == "success" for r in history
            ):
                raise ValueError("supplement targets a changed or successful slot")
            slots[key] = slot["previous_attempts"]
            limits[key] = slot["previous_attempts"] + 3
        if protocol["max_requests"] != len(slots) * 3:
            raise ValueError("supplement request cap differs from its slot plan")
        ledger = path.with_name("requests.jsonl")
        extra = [json.loads(line) for line in ledger.read_text().splitlines()]
        if len(extra) > protocol["max_requests"]:
            raise ValueError("supplement exceeds physical request cap")
        for row in extra:
            key = row[identity_field], row["model"]
            history = histories[key]
            if key not in slots or any(r["status"] == "success" for r in history):
                raise ValueError("unknown or post-success supplemental request")
            attempt = len(history) - slots[key] + 1
            if (
                row["attempt"] != len(history) + 1
                or row["supplement_attempt"] != attempt
                or attempt > 3
                or row["source_run"] != path.parent.name
            ):
                raise ValueError("invalid supplemental attempt history")
            if row["status"] not in {"success", "http_error", "invalid_or_transport_error"}:
                raise ValueError("unknown supplemental request status")
            history.append(row)
            rows.append(row)
        metadata.append(
            {
                "run_id": path.parent.name,
                "protocol_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "ledger_sha256": hashlib.sha256(ledger.read_bytes()).hexdigest(),
                "physical_requests": len(extra),
            }
        )
    return rows, metadata, limits
