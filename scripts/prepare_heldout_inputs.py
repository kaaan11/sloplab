"""Export private, synthetic card inputs without publishing answer keys.

The source YAML and generated views must remain under the Git-ignored
``heldout-private/`` directory. This command makes no model calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import yaml
from export_card_inputs import build_input_markdown, build_template, serialize_view
from jsonschema import Draft202012Validator

from sloplab.safety.policy import validate_content_safety

REPO_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = (REPO_ROOT / "heldout-private").resolve()
SCHEMA_PATH = REPO_ROOT / "cards/schema/case-card-v0.1.schema.json"


def _inside_private(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(PRIVATE_ROOT):
        raise ValueError(f"path must stay within {PRIVATE_ROOT}")
    return resolved


def prepare(source: Path, out: Path) -> dict[str, str]:
    source = _inside_private(source)
    out = _inside_private(out)
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {"scenarios"}:
        raise ValueError("source must contain only a scenarios list")
    scenarios = payload["scenarios"]
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("scenarios must be a nonempty list")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator({"$defs": schema["$defs"], "$ref": "#/$defs/visible_input"})
    hashes: dict[str, str] = {}
    for scenario in scenarios:
        if not isinstance(scenario, dict) or set(scenario) != {"card_id", "input"}:
            raise ValueError("each scenario must contain only card_id and input")
        card_id, view = scenario["card_id"], scenario["input"]
        if not isinstance(card_id, str) or re.fullmatch(r"c[0-9]{2,}", card_id) is None:
            raise ValueError("invalid card_id")
        if card_id in hashes:
            raise ValueError(f"duplicate card_id {card_id}")
        if not isinstance(view, dict):
            raise ValueError(f"{card_id}: input must be a mapping")
        errors = sorted(validator.iter_errors(view), key=lambda e: e.message)
        if errors:
            raise ValueError(f"{card_id}: {[error.message for error in errors]}")
        text = "\n".join(
            item["text"] for section in ("context", "report", "artifacts") for item in view[section]
        )
        text += "\n" + "\n".join(item["statement"] for item in view["claims"])
        safety = validate_content_safety(text)
        if safety:
            raise ValueError(f"{card_id}: content safety check failed: {safety}")
        full_view = {"schema_version": "case-card-v0.1", **view}
        data = serialize_view(full_view)
        card_dir = out / card_id
        card_dir.mkdir(parents=True, exist_ok=True)
        (card_dir / "input.json").write_bytes(data)
        (card_dir / "input.md").write_bytes(build_input_markdown(full_view))
        claim_ids = [item["id"] for item in full_view["claims"]]
        (card_dir / "owner-judgment.template.yaml").write_bytes(build_template(card_id, claim_ids))
        hashes[card_id] = hashlib.sha256(data).hexdigest()
    manifest = {"schema_version": "private-inputs-v0.1", "input_sha256": hashes}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return hashes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    hashes = prepare(args.source, args.out)
    print(f"Prepared {len(hashes)} private inputs at {_inside_private(args.out)}")


if __name__ == "__main__":
    main()
