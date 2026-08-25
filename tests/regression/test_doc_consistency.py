"""Documentation-consistency guard: README corpus numbers must match reality.

Regression guard for the maintenance-audit finding that README cited fixture/case
counts from an earlier corpus size.
"""

from __future__ import annotations

import re
from pathlib import Path

from sloplab.corpus.loader import discover_fixtures

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_readme_fixture_count_matches_corpus() -> None:
    """The quick-start comment must cite the real number of fixture files."""
    canonical, _derived = discover_fixtures(REPO_ROOT / "corpus")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    match = re.search(r"\((\d+) fixture files", readme)
    assert match, "README quick-start fixture-count comment missing"
    assert int(match.group(1)) == len(canonical)


def test_readme_logical_report_count_matches_corpus() -> None:
    """Pair members share one logical report; the cited logical count accounts for it."""
    canonical, _derived = discover_fixtures(REPO_ROOT / "corpus")
    pair_files = sum(1 for f in canonical if f.manifest.pair_id)
    logical_reports = len(canonical) - pair_files // 2

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"(\d+) logical reports\)", readme)
    assert match, "README logical-report count comment missing"
    assert int(match.group(1)) == logical_reports
