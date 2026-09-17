"""E0 envanter üretici (teslim dizininde yaşar; projeye eklenmez).

Başlangıç envanterleriyle birebir aynı kapsam ve biçimi üretir, böylece
çıktılar `cmp` ile doğrulanabilir:
  source-config: 32 dosyalık sabit liste (1 mutlak yollu rapor dahil)
  corpus-canonical: corpus/canonical altında rglob-sıralı tüm dosyalar
  study-v02: experiments/results/deterministic/study-v02 altında rglob-sıralı dosyalar

Kullanım (repo kökünden):
  uv run --offline --frozen python docs/reviews/issue-05/E0/helpers/make_inventories_e0.py --verify-start
  uv run --offline --frozen python docs/reviews/issue-05/E0/helpers/make_inventories_e0.py --tag end

--verify-start: üç envanteri geçici dizine yeniden üretip başlangıç
dosyalarıyla bayt-bayt karşılaştırır (üretim mantığının eşdeğerlik kanıtı).
--tag end: docs/reviews/issue-05/E0/inventories/ altına *-end.sha256 dosyalarını yazar.
Üretim zamanı dosya içine gömülmez (başlangıç/bitiş diff'i temiz kalsın diye);
zaman damgası çağıran tarafın günlüğüne yazılır.
"""

from __future__ import annotations

import argparse
import hashlib
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
INV_DIR = REPO_ROOT / "docs/reviews/issue-05/E0/inventories"

SOURCE_FILES = [
    "pyproject.toml",
    "uv.lock",
    ".github/workflows/ci.yml",
    "docs/reproducibility.md",
    "src/sloplab/experiments/study.py",
    "src/sloplab/experiments/runner.py",
    "src/sloplab/experiments/config.py",
    "experiments/configs/deterministic-study-v0.2.yaml",
    "benchmarks/suites/v1-core.yaml",
    "src/sloplab/cli/main.py",
    "src/sloplab/mutations/textops.py",
    "src/sloplab/mutations/base.py",
    "src/sloplab/mutations/planner.py",
    "src/sloplab/mutations/materialize.py",
    "src/sloplab/mutations/operators/evidence.py",
    "src/sloplab/corpus/parser.py",
    "src/sloplab/evaluators/llm/adapter.py",
    "src/sloplab/experiments/pilot.py",
    "scripts/llm_bench.py",
    "experiments/prompts/triage-v1.md",
    "src/sloplab/scoring/metrics.py",
    "src/sloplab/scoring/comparison.py",
    "src/sloplab/scoring/harness.py",
    "src/sloplab/models/run.py",
    "src/sloplab/models/evaluation.py",
    "src/sloplab/models/enums.py",
    "src/sloplab/reporting/writers.py",
    "src/sloplab/models/suite.py",
    "src/sloplab/models/manifest.py",
    "/home/kaan/GPT-Pro/reports/issue-05-Sloplab.report.md",
    "docs/issue-05-engineering-assessment-and-plan.md",
    "docs/issue-05-E0-task.md",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_source_lines() -> list[str]:
    lines = []
    for f in SOURCE_FILES:
        p = Path(f) if not f.startswith("/") else Path(f)
        lines.append(f"{sha256_file(p)}  {f}")
    return lines


def build_tree_lines(root: Path) -> list[str]:
    # Başlangıç üretimiyle aynı: sıralı rglob, yalnız dosyalar, as_posix göreli yol.
    lines = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            lines.append(f"{sha256_file(p)}  {p.as_posix()}")
    return lines


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-start", action="store_true")
    parser.add_argument("--tag", default=None)
    args = parser.parse_args()

    import os

    os.chdir(REPO_ROOT)
    if args.verify_start:
        cases = [
            ("source-config-inventory-start.sha256", build_source_lines()),
            (
                "corpus-canonical-inventory-start.sha256",
                build_tree_lines(Path("corpus/canonical")),
            ),
            (
                "study-v02-inventory-start.sha256",
                build_tree_lines(Path("experiments/results/deterministic/study-v02")),
            ),
        ]
        ok = True
        with tempfile.TemporaryDirectory() as tmp:
            for name, lines in cases:
                regen = Path(tmp) / name
                write_lines(regen, lines)
                ref = INV_DIR / name
                same = regen.read_bytes() == ref.read_bytes()
                print(f"{name}: {'IDENTICAL' if same else 'DIFFERENT'} ({len(lines)} lines)")
                ok &= same
        return 0 if ok else 1

    if args.tag:
        out_src = INV_DIR / f"source-config-inventory-{args.tag}.sha256"
        out_corpus = INV_DIR / f"corpus-canonical-inventory-{args.tag}.sha256"
        out_old = INV_DIR / f"study-v02-inventory-{args.tag}.sha256"
        src_lines = build_source_lines()
        corpus_lines = build_tree_lines(Path("corpus/canonical"))
        old_lines = build_tree_lines(Path("experiments/results/deterministic/study-v02"))
        write_lines(out_src, src_lines)
        write_lines(out_corpus, corpus_lines)
        write_lines(out_old, old_lines)
        print(f"wrote {out_src} ({len(src_lines)} files)")
        print(f"wrote {out_corpus} ({len(corpus_lines)} files)")
        print(f"wrote {out_old} ({len(old_lines)} files)")
        return 0

    parser.print_usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
