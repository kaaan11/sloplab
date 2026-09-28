"""Issue #61: committed deterministic results are bound to evaluator behavior.

The #49 lock test (``test_study_v02_lock.py``) recomputes the committed
analysis from the committed ``records.jsonl`` but never runs the evaluators,
so an evaluator change with stale committed records stays green. This test
regenerates the deterministic study into a temporary directory with the
current evaluator code and compares ``decision``, ``correct`` and the sorted
finding codes per ``(evaluator, case_id[, repeat])`` against the committed
records. Rationale text, numeric formatting, timestamps and paths are
deliberately NOT compared (issue #53: Python-version-dependent text).

This test runs in the normal CI matrix (3.11/3.12/3.13), so it also serves
issue #53's "decision/correct identical across versions" requirement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sloplab.experiments.runner import load_study_config
from sloplab.experiments.study import run_deterministic_study
from sloplab.models.run import CaseRecord
from sloplab.reporting.writers import read_run_jsonl

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_CONFIG = REPO_ROOT / "experiments" / "configs" / "deterministic-study-v0.2.yaml"
COMMITTED_RECORDS = (
    REPO_ROOT / "experiments" / "results" / "deterministic" / "study-v02" / "records.jsonl"
)

EXPECTED_CASE_ROWS = 594
MAX_REPORTED_MISMATCHES = 10


def _key(record: CaseRecord) -> tuple[str, str, Any]:
    repeat = record.evaluation_metadata.get("repeat_index", 0)
    return (record.evaluator_name, record.case_id, repeat)


def _codes(record: CaseRecord) -> list[str]:
    return sorted(str(finding.get("code")) for finding in record.findings)


def _snapshot(record: CaseRecord) -> tuple[str, bool, tuple[str, ...]]:
    return (str(record.decision), bool(record.correct), tuple(_codes(record)))


def test_regenerated_results_match_committed_records(tmp_path: Path) -> None:
    """Regenerating the study must reproduce committed decisions/correct/codes."""
    result = run_deterministic_study(
        load_study_config(STUDY_CONFIG), STUDY_CONFIG, tmp_path / "regen"
    )
    _, fresh = read_run_jsonl(result.records_path)
    _, committed = read_run_jsonl(COMMITTED_RECORDS)
    assert len(committed) == EXPECTED_CASE_ROWS, (
        f"committed records changed shape: {len(committed)} != {EXPECTED_CASE_ROWS}"
    )

    fresh_by_key = {_key(r): r for r in fresh}
    committed_by_key = {_key(r): r for r in committed}
    assert len(fresh_by_key) == len(fresh), "regenerated keys are not unique"
    assert len(committed_by_key) == len(committed), "committed keys are not unique"

    problems: list[str] = []
    for key in sorted(set(committed_by_key) - set(fresh_by_key)):
        problems.append(f"{key}: missing from regenerated records")
    for key in sorted(set(fresh_by_key) - set(committed_by_key)):
        problems.append(f"{key}: unexpected extra regenerated record")
    for key in sorted(set(committed_by_key) & set(fresh_by_key)):
        old = _snapshot(committed_by_key[key])
        new = _snapshot(fresh_by_key[key])
        if old != new:
            problems.append(
                f"{key}: committed(decision={old[0]}, correct={old[1]}, "
                f"codes={list(old[2])}) != regenerated(decision={new[0]}, "
                f"correct={new[1]}, codes={list(new[2])})"
            )
    assert not problems, (
        "regenerated study differs from committed records "
        f"({len(problems)} mismatches; evaluator behavior changed without "
        "regenerating experiments/results/deterministic/study-v02). First "
        f"{min(len(problems), MAX_REPORTED_MISMATCHES)}:\n"
        + "\n".join(problems[:MAX_REPORTED_MISMATCHES])
    )
