"""Documentation-consistency guards: cited numbers must match reality.

Regression guard for the maintenance-audit finding that documentation cited
fixture/case counts from an earlier corpus size (v0.2.1, M06), extended at v0.2.2
(R05) to cover the dataset card, suite/study config descriptions, the walkthrough,
and the packaging metadata - not just the README.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from sloplab import __version__
from sloplab.corpus.loader import discover_fixtures

REPO_ROOT = Path(__file__).resolve().parents[2]

README = REPO_ROOT / "README.md"
DATASET_CARD = REPO_ROOT / "docs" / "dataset-card.md"
SUITE_YAML = REPO_ROOT / "benchmarks" / "suites" / "v1-core.yaml"
WALKTHROUGH = REPO_ROOT / "examples" / "walkthrough.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _committed_example_counts() -> tuple[int, int, int]:
    """(total, canonical, mutated) case counts from the committed reference run."""
    index = REPO_ROOT / "benchmarks" / "results" / "v1-core-example" / "suite-index.jsonl"
    total = canonical = mutated = 0
    for raw in index.read_text(encoding="utf-8").splitlines():
        entry = __import__("json").loads(raw)
        if entry.get("record_type") != "suite_case":
            continue
        total += 1
        if entry["kind"] == "canonical":
            canonical += 1
        else:
            mutated += 1
    return total, canonical, mutated


def test_readme_fixture_count_matches_corpus() -> None:
    """The quick-start comment must cite the real number of fixture files."""
    canonical, _derived = discover_fixtures(REPO_ROOT / "corpus")
    readme = README.read_text(encoding="utf-8")

    match = re.search(r"\((\d+) fixture files", readme)
    assert match, "README quick-start fixture-count comment missing"
    assert int(match.group(1)) == len(canonical)


def test_readme_logical_report_count_matches_corpus() -> None:
    """Pair members share one logical report; the cited logical count accounts for it."""
    canonical, _derived = discover_fixtures(REPO_ROOT / "corpus")
    pair_files = sum(1 for f in canonical if f.manifest.pair_id)
    logical_reports = len(canonical) - pair_files // 2

    readme = README.read_text(encoding="utf-8")
    match = re.search(r"(\d+) logical reports\)", readme)
    assert match, "README logical-report count comment missing"
    assert int(match.group(1)) == logical_reports


def test_dataset_card_composition_matches_corpus() -> None:
    """Dataset card must describe the real corpus size and class split (R05)."""
    canonical, _derived = discover_fixtures(REPO_ROOT / "corpus")
    classes: dict[str, int] = {}
    pair_files = 0
    for fixture in canonical:
        classes[fixture.manifest.report_class.value] = (
            classes.get(fixture.manifest.report_class.value, 0) + 1
        )
        if fixture.manifest.pair_id:
            pair_files += 1

    card = DATASET_CARD.read_text(encoding="utf-8")
    match = re.search(r"Composition \((\d+) canonical fixtures\)", card)
    assert match, "dataset card composition header missing"
    assert int(match.group(1)) == len(canonical)

    valid_standalone = classes.get("valid", 0)
    review = classes.get("review", 0)
    invalid_standalone = classes.get("invalid", 0) - pair_files
    pairs = pair_files // 2
    for count, label in (
        (valid_standalone, r"(\d+) `valid`"),
        (invalid_standalone, r"(\d+) standalone `invalid`"),
        (review, r"(\d+) `review`"),
        (pairs, r"(\d+) presentation pairs"),
    ):
        m = re.search(label, card)
        assert m, f"dataset card class line missing: {label}"
        assert int(m.group(1)) == count, f"dataset card {label} != corpus ({count})"


def test_dataset_card_version_matches_package() -> None:
    card = DATASET_CARD.read_text(encoding="utf-8")
    match = re.search(r"\*\*Version:\*\* (\S+)", card)
    assert match, "dataset card version line missing"
    assert match.group(1) == __version__


def test_suite_description_counts_match_committed_reference() -> None:
    """Suite config counts must match the committed v1-core example run (R05)."""
    total, canonical_n, mutated_n = _committed_example_counts()
    description = yaml.safe_load(SUITE_YAML.read_text(encoding="utf-8"))["description"]

    m_canon = re.search(r"(\d+) canonical fixtures", description)
    m_derived = re.search(r"exactly (\d+) derived cases", description)
    m_total = re.search(r"total of (\d+) evaluations", description)
    assert m_canon and m_derived and m_total, "suite description count phrases missing"
    assert int(m_canon.group(1)) == canonical_n
    assert int(m_derived.group(1)) == mutated_n
    assert int(m_total.group(1)) == total


def test_walkthrough_case_count_matches_committed_reference() -> None:
    total, _canonical, _mutated = _committed_example_counts()
    walkthrough = WALKTHROUGH.read_text(encoding="utf-8")
    match = re.search(r"(\d+) scored cases", walkthrough)
    assert match, "walkthrough scored-cases figure missing"
    assert int(match.group(1)) == total


def test_pyproject_documentation_url_points_at_repository() -> None:
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'Documentation\s*=\s*"(https://github\.com/[^/]+/[^/]+)/', pyproject)
    assert match, "pyproject Documentation URL missing"
    assert match.group(1).endswith("/sloplab"), match.group(1)
    assert "kaaan11" in match.group(0)


def test_packaging_version_is_not_a_prelease_marker() -> None:
    """v0.2.1 audit P2-2: package version must track the release line."""
    assert not re.match(r"\d+\.\d+\.\d+(rc|a|b|\.dev)\d*$", __version__), __version__
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert match and match.group(1) == __version__
