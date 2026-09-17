"""E1e phase-specific comparison (lives in the delivery; not project code).

Usage (repo root):
  uv run --offline --frozen python docs/reviews/issue-05/E1e/helpers/compare_e1e.py \
    /tmp/sloplab-e1d-jJOgHz/run /tmp/sloplab-e1e-w2dMaH/run

The E0/E1d helpers demand exact set equality and are left untouched, so they
reject the intentional addition. This helper allows EXACTLY one extra file in
the new run: execution-recipe.json. Everything else must be raw-identical
(manifest: only started_at/finished_at), and execution-recipe.json is
re-verified: schema, 64-hex hashes, section/settings/execution recomputation,
inputs/selection agreement with input-identity.json, and case/record order.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ALLOWED_EXTRA = {"execution-recipe.json"}
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


def tagged(identity_type: str, fields: dict[str, object]) -> str:
    return hashlib.sha256(
        canon({"domain": "sloplab.recipe", "type": identity_type, "version": 1, **fields})
    ).hexdigest()


def check_recipe_file(new_root: Path) -> bool:
    """Re-verify execution-recipe.json from its own sections + sibling files."""
    ok = True
    recipe = json.loads((new_root / "execution-recipe.json").read_bytes())
    if recipe.get("schema_version") != 1:
        print("recipe: bad schema_version")
        return False
    for key in (
        "generation_hash",
        "evaluation_hash",
        "analysis_hash",
        "settings_hash",
        "inputs_hash",
        "selection_hash",
        "execution_hash",
    ):
        if not HEX64.match(str(recipe.get(key, ""))):
            print(f"recipe: bad {key}")
            ok = False
    for section, identity_type in (
        ("generation", "generation"),
        ("evaluation", "evaluation"),
        ("analysis", "analysis"),
    ):
        if tagged(identity_type, recipe[section]) != recipe[f"{identity_type}_hash"]:
            print(f"recipe: {identity_type}_hash MISMATCH")
            ok = False
        else:
            print(f"recipe: {identity_type}_hash OK")
    settings_expect = tagged(
        "settings",
        {
            "generation_hash": recipe["generation_hash"],
            "evaluation_hash": recipe["evaluation_hash"],
            "analysis_hash": recipe["analysis_hash"],
        },
    )
    if settings_expect != recipe["settings_hash"]:
        print("recipe: settings_hash MISMATCH")
        ok = False
    else:
        print("recipe: settings_hash OK")
    execution_expect = tagged(
        "execution",
        {
            "inputs_hash": recipe["inputs_hash"],
            "selection_hash": recipe["selection_hash"],
            "settings_hash": recipe["settings_hash"],
        },
    )
    if execution_expect != recipe["execution_hash"]:
        print("recipe: execution_hash MISMATCH")
        ok = False
    else:
        print("recipe: execution_hash OK")
    identity = json.loads((new_root / "input-identity.json").read_bytes())
    if (
        recipe["inputs_hash"] != identity["inputs_hash"]
        or recipe["selection_hash"] != identity["selection_hash"]
    ):
        print("recipe: inputs/selection disagree with input-identity.json")
        ok = False
    else:
        print("recipe: inputs/selection agree with input-identity.json")
    records = [
        json.loads(line)
        for line in (new_root / "records.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    evaluators = sorted({r["evaluator_name"] for r in records})
    block = len(identity["cases"])
    if [r["case_id"] for r in records[:block]] != [c["case_id"] for c in identity["cases"]]:
        print("recipe: identity order does not match first evaluator record order")
        ok = False
    else:
        print(f"recipe: order matches records ({block} cases x {len(evaluators)} evaluators)")
    for area in ("locations", "metadata"):
        if area not in recipe:
            print(f"recipe: missing {area}")
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
    if not check_recipe_file(new_root):
        ok = False
        print("recipe file checks FAILED")
    else:
        print("recipe file checks OK")
    print(f"RESULT: {'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
