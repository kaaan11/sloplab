#!/usr/bin/env python3
"""Export the annotator-visible input view of one or more case cards.

Reads card.yaml files (full cards with answer keys) and writes, for each card,
``<out>/<card_id>/input.json`` containing ONLY the annotator-visible view:
schema_version, opaque_id, context, report, artifacts, claims, plus a note that
this is the annotator-visible view. Answer-bearing material (review,
provenance, identity fields) is never exported.

Output is deterministic: fixed key order, 2-space indent, ensure_ascii=False,
UTF-8 bytes, trailing newline. With ``--check``, existing input.json files are
regenerated in memory and byte-compared; any mismatch fails with exit code 1.

No network access and no model calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

VISIBLE_VIEW_NOTE = (
    "Annotator-visible view of a case card. Contains only the neutral input "
    "context, report, artifacts and claim inventory. The card's review, "
    "provenance and answer key are intentionally excluded."
)


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
        raise ValueError(f"{path}: expected a mapping")
    card_id = card.get("card_id")
    if not isinstance(card_id, str) or not card_id:
        raise ValueError(f"{path}: missing string 'card_id'")
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
    for card_path in args.cards:
        card = load_card(card_path)
        card_id = card["card_id"]
        view = export_view(card)
        data = serialize_view(view)
        out_path = args.out / card_id / "input.json"
        if args.check:
            if not out_path.exists():
                print(f"CHECK FAIL: missing {out_path}", file=sys.stderr)
                ok = False
                continue
            existing = out_path.read_bytes()
            if existing != data:
                print(f"CHECK FAIL: {out_path} differs from regeneration", file=sys.stderr)
                ok = False
                continue
            print(f"CHECK OK: {out_path} sha256={hashlib.sha256(data).hexdigest()}")
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(data)
            print(f"WROTE {out_path} sha256={hashlib.sha256(data).hexdigest()}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
