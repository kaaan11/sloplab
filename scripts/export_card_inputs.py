#!/usr/bin/env python3
"""Export the annotator-visible input view of one or more case cards.

Reads card.yaml files (full cards with answer keys) and writes, for each card,
``<out>/<card_id>/input.json`` containing ONLY the annotator-visible view:
schema_version, opaque_id, context, report, artifacts, claims, plus a note that
this is the annotator-visible view. Answer-bearing material (review,
provenance, identity fields) is never exported.

For each card the script also writes ``<out>/<card_id>/owner-judgment.template.yaml``
-- the per-card blind-review template with one card-level action, confidence
and one-line rationale, per-claim status entries for exactly that card's claim
ids, empty answer values and a neutral comment header. The owner copies it to
``owner-judgment.yaml`` and fills it in.

Output is deterministic: fixed key order, 2-space indent, ensure_ascii=False,
UTF-8 bytes, trailing newline. With ``--check``, existing input.json files are
regenerated in memory and byte-compared; any mismatch fails with exit code 1.

A malformed card is reported as a single clean line on stderr (no traceback)
and makes the run exit with code 2.

No network access and no model calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

VISIBLE_VIEW_NOTE = (
    "Annotator-visible view of a case card. Contains only the neutral input "
    "context, report, artifacts and claim inventory. The card's review, "
    "provenance and answer key are intentionally excluded."
)

TEMPLATE_NAME = "owner-judgment.template.yaml"

CLAIM_ID_RE = re.compile(r"^C[0-9]{1,2}$")

# Neutral, identical for every card: enum values only, in schema order, no
# defaults, no per-card hints.
TEMPLATE_HEADER = """\
# Owner-judgment template for this card. Copy it to owner-judgment.yaml in the
# same directory and fill in every field before looking at the answer key.
# Allowed values (choose exactly one per field; leave nothing empty):
#   action: verify, request_specific_information, likely_out_of_scope
#   confidence: low, medium, high
#   per-claim status: supported, missing, contradictory
# rationale: one short free-text line for the card as a whole (single line).
# Optional: per-claim note (one line) and action_claim_ids (the claim ids the
# chosen action is about; may stay empty).
"""


def _claim_ids(card: dict) -> list[str]:
    """Extract and validate the claim ids of a card's input view."""
    claims = card.get("input", {}).get("claims") if isinstance(card.get("input"), dict) else None
    if not isinstance(claims, list) or not claims:
        raise ValueError("card input has no 'claims' list")
    ids: list[str] = []
    for index, claim in enumerate(claims, start=1):
        if not isinstance(claim, dict):
            raise ValueError(f"claim {index} is not a mapping")
        claim_id = claim.get("id")
        if not isinstance(claim_id, str) or not CLAIM_ID_RE.match(claim_id):
            raise ValueError(f"claim {index} has a missing or malformed id: {claim_id!r}")
        ids.append(claim_id)
    return ids


def build_template(card_id: str, claim_ids: list[str]) -> bytes:
    """Render the empty per-card owner-judgment template (deterministic)."""
    lines = TEMPLATE_HEADER.splitlines()
    lines.append("schema_version: owner-judgment-v0.1")
    lines.append(f"card_id: {card_id}")
    lines.append('judge: ""')
    lines.append('judged_date: ""')
    lines.append('action: ""')
    lines.append("action_claim_ids: []")
    lines.append('confidence: ""')
    lines.append('rationale: ""')
    lines.append("claims:")
    for claim_id in claim_ids:
        lines.append(f"- claim_id: {claim_id}")
        lines.append('  status: ""')
    return ("\n".join(lines) + "\n").encode("utf-8")


def export_view(card: dict) -> dict:
    """Return the annotator-visible input view of a card mapping."""
    visible = card.get("input")
    if not isinstance(visible, dict):
        raise ValueError("card has no 'input' mapping")
    view = {
        "schema_version": card["schema_version"],
        "opaque_id": visible["opaque_id"],
        "context": visible["context"],
        "report": visible["report"],
        "artifacts": visible["artifacts"],
        "claims": visible["claims"],
        "note": VISIBLE_VIEW_NOTE,
    }
    return view


def serialize_view(view: dict) -> bytes:
    """Deterministic serialization: sorted keys, 2-space indent, trailing newline."""
    text = json.dumps(view, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return text.encode("utf-8")


def load_card(path: Path) -> dict:
    card = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(card, dict):
        raise ValueError("expected a mapping")
    card_id = card.get("card_id")
    if not isinstance(card_id, str) or not card_id:
        raise ValueError("missing string 'card_id'")
    return card


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cards", nargs="+", type=Path, help="path(s) to card.yaml")
    parser.add_argument("--out", type=Path, required=True, help="output directory")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify existing input.json files match regeneration instead of writing",
    )
    args = parser.parse_args(argv)

    ok = True
    malformed = False
    for card_path in args.cards:
        try:
            card = load_card(card_path)
            card_id = card["card_id"]
            view = export_view(card)
            data = serialize_view(view)
            template_data = build_template(card_id, _claim_ids(card))
        except Exception as exc:  # noqa: BLE001 - CLI boundary, report cleanly
            message = " ".join(str(exc).split())
            print(f"{card_path}: {message}", file=sys.stderr)
            malformed = True
            continue
        out_path = args.out / card_id / "input.json"
        template_path = args.out / card_id / TEMPLATE_NAME
        if args.check:
            for path, data_bytes in (
                (out_path, data),
                (template_path, template_data),
            ):
                if not path.exists():
                    print(f"CHECK FAIL: missing {path}", file=sys.stderr)
                    ok = False
                    continue
                if path.read_bytes() != data_bytes:
                    print(f"CHECK FAIL: {path} differs from regeneration", file=sys.stderr)
                    ok = False
                    continue
                print(f"CHECK OK: {path} sha256={hashlib.sha256(data_bytes).hexdigest()}")
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(data)
            print(f"WROTE {out_path} sha256={hashlib.sha256(data).hexdigest()}")
            template_path.write_bytes(template_data)
            print(f"WROTE {template_path} sha256={hashlib.sha256(template_data).hexdigest()}")
    if malformed:
        return 2
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
