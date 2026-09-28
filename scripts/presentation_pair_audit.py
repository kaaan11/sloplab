"""Report authored plain/polished pairs separately from derived presentation mutations.

Usage: uv run python scripts/presentation_pair_audit.py
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from sloplab.reporting.writers import read_run_jsonl
from sloplab.scoring.audits import audit_authored_pairs

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    roles: dict[str, tuple[str, str]] = {}
    for path in sorted((REPO_ROOT / "corpus" / "canonical").glob("*/manifest.yaml")):
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        pair_id, role = manifest.get("pair_id"), manifest.get("pair_role")
        if pair_id is not None:
            if not isinstance(pair_id, str) or not isinstance(role, str):
                raise ValueError(f"invalid pair metadata in {path}")
            roles[manifest["id"]] = (pair_id, role)
    if len(roles) != 16:
        raise ValueError(f"expected 16 authored pair members, found {len(roles)}")
    _, records = read_run_jsonl(REPO_ROOT / "benchmarks/results/v1-core-example/run.jsonl")
    audit = audit_authored_pairs(records, roles)
    print(json.dumps({name: result.as_dict() for name, result in audit.items()}, indent=2))


if __name__ == "__main__":
    main()
