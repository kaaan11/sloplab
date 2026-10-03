"""Prepare a blinded second-human packet: nine cards and 18 public realized pairs."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from heldout_panel import PACKET, load_owner_sheet
from prepare_heldout_inputs import REPO_ROOT, _inside_private
from realized_edit_panel import MODELS, load_pairs

DEFAULT_ANNOTATIONS = (
    REPO_ROOT
    / "experiments/results/model-panel/coverage-recovery-2026-10-03"
    / "realized-edits/annotations.jsonl"
)


def select_pairs(
    pairs: list[dict[str, str]], annotations: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """Three per operator; prioritize uncertain/disputed pairs, then fixed hash order."""
    by_id = {p["mutation_id"]: p for p in pairs}
    votes: dict[str, list[dict[str, str]]] = defaultdict(list)
    seen = set()
    for row in annotations:
        key = row["mutation_id"], row["model"]
        if key in seen or key[0] not in by_id or key[1] not in MODELS:
            raise ValueError("unknown or duplicate annotation slot")
        seen.add(key)
        if row["status"] == "success":
            votes[key[0]].append(row["vote"])
    if len(seen) != len(pairs) * len(MODELS):
        raise ValueError("annotation population is incomplete")

    def priority(pair: dict[str, str]) -> tuple[int, str]:
        current = votes[pair["mutation_id"]]
        values = [{v[axis] for v in current} for axis in ("quality_changed", "action_changed")]
        uncertain = any("uncertain" in vs for vs in values)
        disputed = any(len(vs) > 1 for vs in values)
        rank = 0 if uncertain else 1 if disputed else 2
        return rank, hashlib.sha256(("second-human-v1:" + pair["mutation_id"]).encode()).hexdigest()

    by_operator: dict[str, list[dict[str, str]]] = defaultdict(list)
    for pair in pairs:
        by_operator[pair["operator"]].append(pair)
    selected = []
    for operator, candidates in sorted(by_operator.items()):
        if len(candidates) < 3:
            raise ValueError(f"{operator}: too few realized pairs for the review quota")
        selected.extend(sorted(candidates, key=priority)[:3])
    return sorted(
        selected,
        key=lambda p: hashlib.sha256(("review-order:" + p["mutation_id"]).encode()).hexdigest(),
    )


def prepare(out: Path, annotations: Path) -> dict[str, Any]:
    out = _inside_private(out)
    _, _, views = load_owner_sheet()
    # An existing filled owner sheet validates inputs but is never copied to reviewers.
    rows = [json.loads(line) for line in annotations.read_text().splitlines()]
    selected = select_pairs(load_pairs(), rows)
    if len(selected) != 18:
        raise ValueError("expected six operators and 18 review pairs")
    out.mkdir(parents=True, exist_ok=False)
    out.chmod(0o700)
    visible = out / "reviewer-packet"
    visible.mkdir()
    card_judgments = {}
    for card_id, view in sorted(views.items()):
        dest = visible / "cards" / card_id
        dest.mkdir(parents=True)
        for name in ("input.json", "input.md"):
            (dest / name).write_bytes((PACKET / card_id / name).read_bytes())
        card_judgments[card_id] = {
            "action": "",
            "confidence": "",
            "rationale": "",
            "claims": {c["id"]: "" for c in view["claims"]},
        }
    pair_judgments = {}
    admin = {}
    for index, pair in enumerate(selected, 1):
        opaque = f"p{index:02d}"
        dest = visible / "pairs" / opaque
        dest.mkdir(parents=True)
        (dest / "input.md").write_text(
            f"# Pair {opaque}\n\n## Report A\n\n{pair['report_a']}"
            f"\n\n## Report B\n\n{pair['report_b']}"
        )
        pair_judgments[opaque] = {
            "quality_changed": "",
            "action_changed": "",
            "quality_reason": "",
            "action_reason": "",
        }
        admin[opaque] = {
            "mutation_id": pair["mutation_id"],
            "operator": pair["operator"],
            "input_sha256": hashlib.sha256((dest / "input.md").read_bytes()).hexdigest(),
        }
    (visible / "judgment-sheet.json").write_text(
        json.dumps(
            {
                "judge": "",
                "judged_date": "",
                "cards": card_judgments,
                "pairs": pair_judgments,
            },
            indent=2,
        )
        + "\n"
    )
    (visible / "rubric.md").write_bytes((REPO_ROOT / "docs/case-card-rubric-v0.1.md").read_bytes())
    (visible / "README.md").write_text(
        "# Independent human review\n\n"
        "Türkçe yönerge: README.tr.md.\n\n"
        "Complete judgment-sheet.json before looking at prior owner/model judgments, "
        "author keys, source manifests or repository annotation outputs. The judge must "
        "be a different human from the first owner reviewer. All scenarios are synthetic.\n\n"
        "For cards, use verify/request_specific_information/likely_out_of_scope; "
        "confidence low/medium/high; claim status supported/missing/contradictory. "
        "For pairs, quality_changed and action_changed each use yes/no/uncertain. "
        "Give brief evidence-grounded reasons. See rubric.md.\n\n"
        "The pair sample targets annotation uncertainty/disagreement and balances "
        "operators; it is not a random prevalence sample. Nine cards and 18 pairs "
        "contain prior project/provider exposure, and are not a new held-out set. "
        "Return only the filled judgment sheet; do not modify input files.\n"
    )
    (visible / "README.tr.md").write_text(
        "# Bağımsız insan değerlendirmesi\n\n"
        "Bu paket 9 senaryo kartı ve 18 rapor çifti içerir. Senaryolar sentetiktir. "
        "İlk değerlendirmeyi yapan kişiden farklı bir insan doldurmalıdır. "
        "Önceki insan/model yanıtlarını, yazar anahtarlarını veya depodaki sonuçları "
        "görmeden kendi değerlendirmeni tamamla. Gerçek sistemlerde deneme yapman gerekmiyor.\n\n"
        "## Doldurma adımları\n\n"
        "1. `judgment-sheet.json` dosyasını bir metin düzenleyicide aç. "
        "`judge` alanına adını veya takma adını, `judged_date` alanına "
        "YYYY-AA-GG biçiminde tarihi yaz.\n"
        "2. `cards/c04`–`cards/c12` klasörlerindeki `input.md` dosyalarını oku. "
        "Her kartın formdaki kendi bölümünü doldur. İddia kimlikleri "
        "`input.json` dosyasında da bulunur.\n"
        "3. `pairs/p01`–`pairs/p18` içindeki `input.md` dosyalarında A ve B "
        "raporlarını karşılaştır; her çift için iki ekseni ayrı değerlendir.\n"
        "4. Bütün boş alanları doldur; dosya yapısını ve kimlikleri değiştirme. "
        "JSON içindeki yanıtları çift tırnak arasında yaz. "
        "Yalnızca doldurduğun `judgment-sheet.json` dosyasını geri gönder.\n\n"
        "## Kart yanıtları\n\n"
        "- `action`: `verify` = belirtilen kapsam içi iddiayı doğrulamaya girişmek "
        "için yeterli bilgi var; `request_specific_information` = bunu engelleyen "
        "önemli bir eksik veya çelişki var; `likely_out_of_scope` = açık politika "
        "veya tehdit modeli bildirilen davranışı kapsam dışında bırakıyor.\n"
        "- `confidence`: `low`, `medium` veya `high`. Bu güven, seçtiğin sonraki "
        "adıma ilişkindir; güvenlik açığının var olma olasılığı değildir. "
        "Açık politika ve kanıtlar kararı belirliyorsa `high`, ilgili bir yorum "
        "belirsizse `medium`, seçim çok sınırlı bilgiye dayanıyorsa `low` kullan.\n"
        "- `rationale`: Türkçe kısa gerekçe; belirleyici kanıtı, eksik bilgiyi "
        "veya politika maddesini belirt.\n"
        "- `claims`: her iddia için `supported` = sunulan kanıt destekliyor; "
        "`missing` = gerekli kanıt yok; `contradictory` = sunulan kanıt veya "
        "açık bağlam iddiayla çelişiyor. Akla yatkın olmak tek başına destek değildir.\n\n"
        "## Rapor çifti yanıtları\n\n"
        "- `quality_changed`: bilginin yeterliliği, iddia/kanıt tutarlılığı, "
        "etkinin ölçülü anlatılması veya anlaşılabilirlik anlamlı biçimde "
        "değişti mi? `yes`, `no` veya `uncertain`.\n"
        "- `action_changed`: A yerine B okunduğunda insanın yukarıdaki sonraki "
        "adımı değişmeli mi? `yes`, `no` veya `uncertain`.\n"
        "- `quality_reason` ve `action_reason`: her eksen için ayrı kısa gerekçe.\n\n"
        "Önemli bilgi veya gerekli sürüm eksikliği, yeni bir çelişki, desteksiz "
        "etki artışı ve anlamı etkileyen belirsizlik kaliteyi değiştirebilir. "
        "Kozmetik yazım tercihi tek başına anlamlı değişiklik sayılmayabilir. "
        "Eksik bilgi yalnızca belirtilen politika veya temel iddia için "
        "gerekliyse sonraki adımı engeller. Metin politika veya değişikliğin "
        "önemini belirlemeye yetmiyorsa `uncertain` kullan; örtük kural uydurma. "
        "Kaliteli yazılmış bir rapor yine de kapsam dışında olabilir. "
        "Tam İngilizce rubrik `rubric.md` dosyasındadır.\n\n"
        "## Örnek form değerleri\n\n"
        "Bir kartta `action` için `request_specific_information`, `confidence` "
        "için `medium`, gerekçede hangi bilginin eksik olduğunu yazabilirsin. "
        "Bu yalnızca biçim örneğidir; hiçbir kartın doğru yanıtını belirtmez.\n\n"
        "Çift seçimi önceki anotasyonlardaki belirsizlik/ayrışmaya odaklanır "
        "ve işlem türlerini dengeler; rastgele yaygınlık örneklemi değildir. "
        "Bu girdiler daha önce proje/sağlayıcı tarafından görülmüştür. "
        "Yeni bir görülmemiş test kümesi olarak yorumlanamaz.\n"
    )
    protocol = {
        "schema_version": "second-human-review-v1",
        "cards": len(views),
        "pairs": len(selected),
        "selection": (
            "three per operator; uncertain first, disagreement next, deterministic hash ties"
        ),
        "annotations_sha256": hashlib.sha256(annotations.read_bytes()).hexdigest(),
        "pair_mapping": admin,
        "reviewer_file_sha256": {
            p.relative_to(visible).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(visible.rglob("*"))
            if p.is_file()
        },
    }
    path = out / "admin-protocol.json"
    path.write_text(json.dumps(protocol, indent=2) + "\n")
    path.chmod(0o600)
    archive = out / "reviewer-packet.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as zipped:
        for relative in protocol["reviewer_file_sha256"]:
            zipped.write(visible / relative, arcname=f"reviewer-packet/{relative}")
    archive.chmod(0o600)
    return {
        "cards": len(views),
        "pairs": len(selected),
        "reviewer_files": len(protocol["reviewer_file_sha256"]),
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.write:
        _inside_private(args.out)
        selected = select_pairs(
            load_pairs(), [json.loads(line) for line in args.annotations.read_text().splitlines()]
        )
        print(f"review preflight: nine cards and {len(selected)} public pairs")
        return
    print(json.dumps(prepare(args.out, args.annotations)))


if __name__ == "__main__":
    main()
