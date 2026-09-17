"""E0 ham karşılaştırma yardımcısı, rev3 (teslim dizininde yaşar; projeye eklenmez).

Kullanım (repo kökünden):
  uv run --offline --frozen python docs/reviews/issue-05/E0/helpers/compare_e0.py \
    /tmp/sloplab-e0-zVHDyy/run-a /tmp/sloplab-e0-zVHDyy/run-b \
    experiments/results/deterministic/study-v02

Politika: docs/reviews/issue-05/E0/comparison-policy.md
rev2'den farklar (satır-sonu sıkılaştırması):
- A/B suite-index.jsonl: ham bayt eşitliği zorunludur. `splitlines()` normalizasyonu
  LF/CRLF farkını gizleyebileceği için satır-bazlı karşılaştırma karar vermez;
  karar `read_bytes()` eşitliğidir.
- Tarihsel suite-index.jsonl: header (ilk `\n` öncesi) JSON olarak parse edilir ve
  yalnız `corpus_root` anahtar farkına izin verilir; header sonrası gövde HAM
  BAYTLARLA karşılaştırılır (satır sonları dahil). CRLF'li gövde reddedilir.
- rev2'nin kapalı allowlist'leri aynen korunur (aşağıda).
Çıkış kodu: A/B açıklanmayan farksız VE tarihsel farklar allowlist içindeyse 0,
aksi halde 1.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

AB_MANIFEST_ALLOW = {"started_at", "finished_at"}
HIST_MANIFEST_ALLOW = {"commit_sha", "corpus_root", "started_at", "finished_at", "suite_hash"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def full_tree(root: Path) -> dict[str, str]:
    """Kök altındaki TÜM dosyalar: göreli yol -> SHA-256."""
    out: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        out[path.relative_to(root).as_posix()] = sha256_file(path)
    return out


def check_set(label: str, tree_a: dict[str, str], tree_b: dict[str, str]) -> bool:
    only_a = sorted(set(tree_a) - set(tree_b))
    only_b = sorted(set(tree_b) - set(tree_a))
    if only_a or only_b:
        print(f"{label} file-set DIFFERENT")
        for name in only_a:
            print(f"  only-in-a: {name}")
        for name in only_b:
            print(f"  only-in-b: {name}")
        return False
    print(f"{label} file-set IDENTICAL ({len(tree_a)} files)")
    return True


def check_hashes(
    label: str,
    tree_a: dict[str, str],
    tree_b: dict[str, str],
    skip: set[str],
) -> bool:
    bad = sorted(
        name
        for name in set(tree_a) & set(tree_b)
        if name not in skip and tree_a[name] != tree_b[name]
    )
    if bad:
        print(f"{label} hash DIFFERENT ({len(bad)} files):")
        for name in bad:
            print(f"  {name} ({tree_a[name][:12]} vs {tree_b[name][:12]})")
        return False
    compared = len(set(tree_a) & set(tree_b) - skip)
    print(f"{label} hash IDENTICAL ({compared} files compared, skipped: {sorted(skip)})")
    return True


def check_manifest(label: str, path_a: Path, path_b: Path, allow: set[str]) -> bool:
    man_a = json.loads(path_a.read_text(encoding="utf-8"))
    man_b = json.loads(path_b.read_text(encoding="utf-8"))
    diff = sorted(k for k in set(man_a) | set(man_b) if man_a.get(k) != man_b.get(k))
    unexplained = [k for k in diff if k not in allow]
    print(f"{label} manifest.json differing fields: {diff} (allow: {sorted(allow)})")
    if unexplained:
        print(f"{label} manifest.json UNEXPLAINED fields: {unexplained}")
        return False
    return True


def check_suite_index(label: str, path_a: Path, path_b: Path, historical: bool) -> bool:
    """suite-index.jsonl denetimi. Karar ham baytlarladır; splitlines() normalizasyonu
    karar vermez (LF/CRLF gizlenemez).

    - A/B (historical=False): ham bayt eşitliği zorunlu.
    - Tarihsel: gövde (ilk b'\\n' sonrası, satır sonları dahil ham) eşit olmalı;
      header JSON parse edilip yalnız corpus_root farkına izin verilir.
    Tanı için header/gövde ayrıştırması yazdırılır ama A/B'de ham farkı kurtarmaz.
    """
    raw_a = path_a.read_bytes()
    raw_b = path_b.read_bytes()
    if raw_a == raw_b:
        print(f"{label} suite-index.jsonl raw hash IDENTICAL")
        return True
    print(f"{label} suite-index.jsonl raw hash DIFFERENT")
    try:
        head_a_raw, body_a = raw_a.split(b"\n", 1)
        head_b_raw, body_b = raw_b.split(b"\n", 1)
    except ValueError:
        print(f"{label} suite-index.jsonl has no newline — unexplained")
        return False
    print(f"{label} suite-index.jsonl body raw bytes: "
          f"{'IDENTICAL' if body_a == body_b else 'DIFFERENT'} (line endings included)")
    try:
        head_a = json.loads(head_a_raw.decode("utf-8"))
        head_b = json.loads(head_b_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"{label} suite-index.jsonl header unparsable: {exc} — unexplained")
        return False
    hdiff = sorted(k for k in set(head_a) | set(head_b) if head_a.get(k) != head_b.get(k))
    if historical:
        if body_a == body_b and hdiff == ["corpus_root"]:
            print(f"{label} suite-index.jsonl header differs only in corpus_root "
                  f"({head_a['corpus_root']} vs {head_b['corpus_root']}) — explained")
            return True
        print(f"{label} suite-index.jsonl UNEXPLAINED "
              f"(header diff keys: {hdiff}) — rejected")
        return False
    print(f"{label} A/B requires raw byte equality (header diff keys: {hdiff}) — rejected")
    return False


def main() -> int:
    run_a, run_b, old = (Path(a) for a in sys.argv[1:4])
    ok = True

    print("== A/B (run-a vs run-b) ==")
    tree_a, tree_b = full_tree(run_a), full_tree(run_b)
    ok &= check_set("A/B", tree_a, tree_b)
    ok &= check_hashes("A/B", tree_a, tree_b, skip={"manifest.json", "suite-index.jsonl"})
    ok &= check_manifest("A/B", run_a / "manifest.json", run_b / "manifest.json",
                         AB_MANIFEST_ALLOW)
    ok &= check_suite_index("A/B", run_a / "suite-index.jsonl", run_b / "suite-index.jsonl",
                            historical=False)

    print("== historical (study-v02 vs run-a) ==")
    tree_o, tree_n = full_tree(old), full_tree(run_a)
    ok &= check_set("old/new", tree_o, tree_n)
    ok &= check_hashes("old/new", tree_o, tree_n,
                       skip={"manifest.json", "suite-index.jsonl"})
    ok &= check_manifest("old/new", old / "manifest.json", run_a / "manifest.json",
                         HIST_MANIFEST_ALLOW)
    ok &= check_suite_index("old/new", old / "suite-index.jsonl", run_a / "suite-index.jsonl",
                            historical=True)

    print(f"RESULT: {'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
