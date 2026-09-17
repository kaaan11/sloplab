"""E1d phase-specific comparison (lives in the delivery; not project code).

Usage (repo root):
  uv run --offline --frozen python docs/reviews/issue-05/E1d/helpers/compare_e1d.py \
    /tmp/sloplab-e0-zVHDyy/run-a /tmp/sloplab-e1d-jJOgHz/run

Unlike the E0 rev3 helper (exact set equality, left untouched), this allows
EXACTLY one extra file in the new run: input-identity.json. Any other
new/missing file, any raw difference in the shared 479 data/index files beyond
the manifest time fields, or any internal inconsistency in input-identity.json
fails with a nonzero exit.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ALLOWED_EXTRA = {"input-identity.json"}
MANIFEST_ALLOW = {"started_at", "finished_at"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def full_tree(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): sha256_file(p)
        for p in sorted(q for q in root.rglob("*") if q.is_file())
    }


def canon(obj: object) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def tagged(identity_type: str, fields: dict[str, object]) -> dict[str, object]:
    return {"domain": "sloplab.input", "type": identity_type, "version": 1, **fields}


def check_identity_file(new_root: Path) -> bool:
    """Re-verify input-identity.json bindings from its own rows + run records."""
    ok = True
    identity = json.loads((new_root / "input-identity.json").read_bytes())
    if identity.get("schema_version") != 1:
        print("identity: bad schema_version")
        return False
    rows = identity.get("cases", [])
    if not isinstance(rows, list) or not rows:
        print("identity: empty or missing cases")
        return False
    for row in rows:
        for key in ("report_hash", "target_hash", "input_hash"):
            if not HEX64.match(str(row.get(key, ""))):
                print(f"identity: row {row.get('case_id')} bad {key}")
                ok = False
    print(f"identity: {len(rows)} rows read; 64-hex lowercase OK")
    # 1. selection/inputs recomputed from rows.
    case_ids = [row["case_id"] for row in rows]
    selection_expect = hashlib.sha256(
        canon(tagged("selection", {"case_ids": case_ids}))
    ).hexdigest()
    if selection_expect != identity.get("selection_hash"):
        print("identity: selection_hash MISMATCH")
        ok = False
    else:
        print("identity: selection_hash OK")
    inputs_expect = hashlib.sha256(canon(tagged("inputs", {"inputs": rows}))).hexdigest()
    if inputs_expect != identity.get("inputs_hash"):
        print("identity: inputs_hash MISMATCH")
        ok = False
    else:
        print("identity: inputs_hash OK")
    # 2. per-row input_hash binds the row's report/target hashes.
    for row in rows:
        input_expect = hashlib.sha256(
            canon(
                tagged(
                    "input",
                    {"report_hash": row["report_hash"], "target_hash": row["target_hash"]},
                )
            )
        ).hexdigest()
        if input_expect != row["input_hash"]:
            print(f"identity: input_hash MISMATCH for {row['case_id']}")
            ok = False
    print(f"identity: per-row input_hash checked for {len(rows)} rows")
    # 3. order/count agreement with run records (first evaluator block).
    records = [
        json.loads(line)
        for line in (new_root / "records.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    evaluators = sorted({r["evaluator_name"] for r in records})
    block = len(rows)
    first_block = [r["case_id"] for r in records[:block]]
    if first_block != case_ids:
        print("identity: case order does not match first evaluator record order")
        ok = False
    else:
        print(f"identity: order matches records ({block} cases x {len(evaluators)} evaluators)")
    if len(records) != block * len(evaluators):
        print("identity: record count is not cases x evaluators")
        ok = False
    return ok


def main() -> int:
    ref_root, new_root = (Path(a) for a in sys.argv[1:3])
    ok = True
    tree_ref, tree_new = full_tree(ref_root), full_tree(new_root)
    only_new = sorted(set(tree_new) - set(tree_ref))
    only_missing = sorted(set(tree_ref) - set(tree_new))
    if only_new == sorted(ALLOWED_EXTRA) and not only_missing:
        print(f"file-set: only allowed extra {sorted(ALLOWED_EXTRA)}")
    else:
        print(f"file-set DIFFERENT (new: {only_new}, missing: {only_missing})")
        ok = False
    shared = set(tree_ref) & set(tree_new)
    bad = sorted(n for n in shared if n != "manifest.json" and tree_ref[n] != tree_new[n])
    if bad:
        print(f"shared raw DIFFERENT ({len(bad)} files): {bad[:10]}")
        ok = False
    else:
        print(f"shared raw IDENTICAL ({len(shared) - 1} files besides manifest)")
    man_ref = json.loads((ref_root / "manifest.json").read_text(encoding="utf-8"))
    man_new = json.loads((new_root / "manifest.json").read_text(encoding="utf-8"))
    man_diff = sorted(k for k in set(man_ref) | set(man_new) if man_ref.get(k) != man_new.get(k))
    unexplained = [k for k in man_diff if k not in MANIFEST_ALLOW]
    print(f"manifest.json differing fields: {man_diff}")
    if unexplained:
        print(f"manifest.json UNEXPLAINED: {unexplained}")
        ok = False
    if not check_identity_file(new_root):
        ok = False
        print("identity file checks FAILED")
    else:
        print("identity file checks OK")
    print(f"RESULT: {'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
